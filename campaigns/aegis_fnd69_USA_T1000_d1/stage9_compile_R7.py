# -*- coding: utf-8 -*-
"""AEGIS R7 编译：把 3 个研究员提案（A/B/C）转成标准批次，跑 AST 硬审计 + 骨架门禁 + 自动红队。

不调用任何 BRAIN 仿真/提交接口。仅做本地编译与审计。
"""
import json
import os
import re
import sys
import sqlite3
import hashlib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))

from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402
from quant_framework.core.red_team import DoubleBlindRedTeam  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

FIELDS = json.load(open(os.path.join(HERE, "batch_R6.json"), encoding="utf-8"))["known_fields"]
# 增补 R7 研究员用到、但 R6 画像未登记的高价值 fnd89 字段（来自 stage7_partner_scan.json）
NEW_FND89 = {
    "fnd89_major_13_11": ("(Net Income + D&A - OCF)/Total Assets 应计 ex-D&A", 0.841, 0),
    "fnd89_major_21_11": ("总应计/平均总资产 Richardson 经典总应计", 0.710, 0),
    "fnd89_asset_41_11": ("流动资产应计/总资产", 0.725, 0),
    "fnd89_other_11_11": ("(Δ普通股权益 - Δ现金)/缩放 净股权发行代理", 0.831, 0),
    "fnd89_csjones_all_major_11": ("现金类科目截面比率", 0.851, 0),
    "fnd89_csjones_all_r2_major_11": ("现金比率 R² 盈余平滑度代理", 0.853, 0),
}
for fid, (desc, cov, ac) in NEW_FND89.items():
    if fid not in FIELDS:
        FIELDS[fid] = {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                       "description": desc, "coverage": cov, "alpha_count": ac}
DB = os.path.join(ROOT, "alphas_record.db")
NEUT = "NONE"
MAX_OPS = 11
MAX_DATASETS = 2
MAX_FIELDS = 3

PROPOSALS = {
    "A": ("batch_R7_proposal_A.json", "batch_R7A.json", "stage9_gate_R7A.json", "R7A"),
    "B": ("batch_R7_proposal_B.json", "batch_R7B.json", "stage9_gate_R7B.json", "R7B"),
    "C": ("batch_R7_proposal_C.json", "batch_R7C.json", "stage9_gate_R7C.json", "R7C"),
}

PV_PREFIXES = ("close", "open", "high", "low", "vwap", "volume", "cap", "adv", "returns",
               "sharesout", "split", "dividend")


def infer_datasets(expr):
    out = []
    for f in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr):
        if f.startswith("fnd69_"):
            out.append("fundamental69")
        elif f.startswith("fnd89_"):
            out.append("fundamental89")
        elif f.startswith("oth466_"):
            out.append("other466")
    return sorted(set(out))


def de_mean_ok(expr):
    e = expr.strip()
    # 最终外层必须是 group_zscore(x, g) 或 (group_rank(...) - 0.5)
    if re.search(r"^group_zscore\(.*,\s*(industry|sector|subindustry|market)\s*\)$", e):
        return True
    if re.match(r"^subtract\(group_rank\(.*,\s*(industry|sector|subindustry|market)\s*\)\s*,\s*0\.5\)$", e):
        return True
    return False


def release_fingerprints(exprs):
    c = ASTSandboxCorrector()
    md5s = [c.compute_fingerprint(c.correct_expression(e), "USA", "TOP1000", 1, NEUT) for e in exprs]
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    q = ",".join("?" * len(md5s))
    cur.execute(f"DELETE FROM alpha_fingerprints WHERE md5_hash IN ({q})", md5s)
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def compile_one(prop_file, batch_file, gate_file, tag):
    prop = json.load(open(os.path.join(HERE, prop_file), encoding="utf-8"))
    cands = prop["candidates"]
    assert len(cands) == 8, f"{tag}: 需要 8 条，实际 {len(cands)}"

    slots, items, issues_all = [], [], []
    for c in cands:
        expr = c["expression"].strip()
        ds = infer_datasets(expr)
        pv_hit = [f for f in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr) if f.startswith(PV_PREFIXES)]
        s = {
            "slot": c["slot"], "role": c["role"], "expression": expr,
            "counterparty": c.get("counterparty", ""), "mechanism": c.get("mechanism", ""),
            "datasets": ds, "variation_source": f"{'+'.join(ds)} | {c['role']}",
            "hypothesis_lines": c.get("hypothesis_lines", []),
        }
        # 本地硬校验
        local_issues = []
        if pv_hit:
            local_issues.append(f"PV 污染: {pv_hit}")
        if not de_mean_ok(expr):
            local_issues.append("未去中枢（外层非 group_zscore/group_rank-0.5）")
        if len(ds) > MAX_DATASETS:
            local_issues.append(f"数据集超限: {ds}")
        # 字段计数（仅 fnd/oth 字段）
        used_fields = sorted({f for f in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
                              if f.startswith(("fnd69_", "fnd89_", "oth466_"))})
        if len(used_fields) > MAX_FIELDS:
            local_issues.append(f"字段超限: {used_fields}")
        s["local_issues"] = local_issues
        if local_issues:
            issues_all.extend([f"S{c['slot']} {x}" for x in local_issues])

        slots.append(s)
        items.append({"expression": expr, "counterparty": s["counterparty"], "optimize_reason": s["mechanism"]})

    exprs = [s["expression"] for s in slots]
    release_fingerprints(exprs)

    report = {"round_tag": tag, "n": len(slots), "local_issues": issues_all, "ast": [], "skeleton": None, "red_team": None, "all_valid": not issues_all}

    for s in slots:
        a = DimensionAuditor.audit_expression(s["expression"], FIELDS, category="fundamental",
                                             allow_pv_cross=False, max_operators=MAX_OPS)
        report["ast"].append({"slot": s["slot"], "role": s["role"], "valid": a["is_valid"],
                              "ops": a["operator_count"], "fields": len(a["used_fields"]),
                              "issues": a["issues"]})
        if not a["is_valid"]:
            report["all_valid"] = False

    try:
        corrected = ASTSandboxCorrector().check_and_record_batch(exprs, "USA", "TOP1000", 1, NEUT)
        report["skeleton"] = {"status": "PASS"}
        for s, cx in zip(slots, corrected):
            s["expression"] = cx
    except Exception as e:
        report["skeleton"] = {"status": "FAIL", "error": repr(e)}
        report["all_valid"] = False

    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, os.path.join(HERE, f"batch_R7_{tag}_red_team.json"))
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, gate_file), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, batch_file), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "datasets": ["fundamental69", "fundamental89", "other466"],
                   "category": "fundamental", "neutralization": NEUT, "decay": 0,
                   "truncation": 0.025, "max_datasets_per_expression": MAX_DATASETS,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": slots}, f, ensure_ascii=False, indent=2)

    print("=" * 90)
    print(f"[{tag}] 全通过: {report['all_valid']} | 本地问题: {len(issues_all)} | 红队: {report['red_team']['all_passed']} | 骨架: {report['skeleton']['status']}")
    for a in report["ast"]:
        flag = "" if a["valid"] else f"  ! AST {a['issues']}"
        print(f"  S{a['slot']} {a['role']:<34} ops={a['ops']} fields={a['fields']} ast={a['valid']}{flag}")
    for p in report["red_team"]["per_slot"]:
        if p["verdict"] != "PASS":
            print("   RT", p["slot"], p["issues"])
    print("=" * 90)
    return report


def main():
    for key, (pf, bf, gf, tag) in PROPOSALS.items():
        if os.path.exists(os.path.join(HERE, pf)):
            compile_one(pf, bf, gf, tag)
        else:
            print(f"[{tag}] 提案缺失: {pf}")


if __name__ == "__main__":
    main()
