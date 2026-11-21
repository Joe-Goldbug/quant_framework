# -*- coding: utf-8 -*-
"""Stage 5 · 跨数据集预检扩展（fnd17 × 伙伴集）

★ 新授权（2026-10-29 研究员指令）：
  "专注于USA top1000 基本面数据集，允许跨一个数据集，
   但是alpha表达式中最多出现来自两个不同数据集的字段"

【本模块职责】
  1. 把多个数据集的字段元数据**合并**成一张统一表，供 DimensionAuditor / RedTeam 使用。
  2. 把 field_ids() 从「只认 fnd17_ 前缀」改为「认所有已知数据集前缀」。
  3. 增设 G7 闸门：**数据集数 ≤ 2**，且字段总数仍 ∈ [2,3]。
  4. PV 污染检查扩展到跨数据集字段（伙伴集里也有 mktcap / price 类字段，必须拦）。

【为什么这样做而不是直接复用 stage3_preflight】
  stage3_preflight.field_ids() 硬编码 `\\bfnd17_[a-z0-9_]+\\b`，
  跨数据集字段会被判「字段不存在于 fundamental17 可用池」⇒ G3 直接熔断。
  这里复制一份**可参数化**的实现，避免污染已归档的单数据集战役脚本。
"""
import ast
import json
import os
import re
import sys

import _paths
ROOT = _paths.ROOT
sys.path.insert(0, ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import stage3_preflight as P
from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam

# ------------------------------------------------------------------ 数据集前缀
DATASET_PREFIXES = {
    "fundamental17": "fnd17_",
    "fundamental89": "fnd89_",
    "fundamental45": "fnd45_",
    "fundamental77": "fnd77_",
    "other466": "oth466_",
}

# 伙伴集里已知的价格/市值字段（跨数据集 PV 污染黑名单）
PARTNER_PV_FIELDS = {
    "fnd45_us_mktcap",
}


def _meta_from_rows(rows):
    """平台 get_datafields 行 → 内部 meta 形态。"""
    out = {}
    for r in rows:
        fid = r.get("id")
        if not fid:
            continue
        out[fid] = {
            "type": r.get("type") or r.get("dataType") or "MATRIX",
            "domain": "unbounded",
            "is_sparse": False,
            "description": r.get("description", ""),
            "alphaCount": r.get("alphaCount", 0),
            "coverage": r.get("coverage", 0),
        }
    return out


def load_unified_meta():
    """fnd17 本地元数据 + partner_fields.json 的伙伴集 ⇒ 统一表。"""
    meta = dict(P.load_meta())
    pf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "partner_fields.json")
    if os.path.exists(pf):
        partners = json.load(open(pf, encoding="utf-8"))
        for ds, rows in partners.items():
            meta.update(_meta_from_rows(rows))
    return meta


def dataset_of(fid):
    for ds, pfx in DATASET_PREFIXES.items():
        if fid.startswith(pfx):
            return ds
    if fid.startswith("afinn_") or fid.startswith("lm_") or fid.startswith("word_count_"):
        return "fundamental77"
    if fid.startswith("accum4q_") or fid.startswith("csjones_industry_"):
        return "fundamental89"
    return "unknown"


def field_ids(expr):
    """表达式里出现的**所有**数据集字段（不限前缀）。"""
    ids = set()
    for pfx in set(DATASET_PREFIXES.values()):
        ids.update(re.findall(r"\b" + pfx + r"[A-Za-z0-9_]+\b", expr))
    # fundamental77 命名空间较杂
    ids.update(re.findall(r"\b(?:afinn_[a-z0-9_]+|lm_[a-z0-9_]+|word_count_[a-z0-9_]+|"
                          r"fnd77_[a-z0-9_]+)\b", expr))
    return sorted(ids)


def datasets_in(expr):
    return sorted({dataset_of(f) for f in field_ids(expr)} - {"unknown"})


def preflight_cross(expr, optimize_reason, counterparty, meta, phase0=True,
                    op_cap_override=None, max_datasets=2):
    """跨数据集预检。返回 {ok, issues[], checks{}}。

    与 stage3_preflight.preflight 的差异：
      - G3 字段真实性校验用统一表（而非只认 fnd17）
      - G3 字段数仍要求 2~3（跨数据集不放松简约律）
      - **G7 新增**：数据集数 ≤ max_datasets（默认 2）
      - G3 PV 污染：额外检查 PARTNER_PV_FIELDS
    """
    issues, checks = [], {}

    # ---------- G1 语法 ----------
    try:
        calls, tree, top = P.ast_calls(expr)
        checks["syntax_ok"] = True
    except SyntaxError as e:
        return {"ok": False, "issues": [f"G1 语法错误: {e}"], "checks": {"syntax_ok": False}}

    checks["top_level"] = top
    checks["operator_count"] = len(calls)

    fids = field_ids(expr)
    checks["fields_used"] = fids
    checks["field_count"] = len(fids)

    # ---------- G7 数据集数闸门（新授权的核心约束） ----------
    dss = datasets_in(expr)
    checks["datasets_used"] = dss
    checks["dataset_count"] = len(dss)
    checks["dataset_count_ok"] = len(dss) <= max_datasets
    if not checks["dataset_count_ok"]:
        issues.append(f"G7 跨数据集数 {len(dss)} > {max_datasets}（只允许最多两个数据集）: {dss}")

    # ---------- G3 战役结构契约 ----------
    op_cap = op_cap_override if op_cap_override is not None else (
        P.MAX_OPS_PHASE0 if phase0 else P.MAX_OPS_TERMINAL)
    checks["operator_count_ok"] = len(calls) <= op_cap
    if not checks["operator_count_ok"]:
        issues.append(f"G3 算子数 {len(calls)} > {op_cap}")

    checks["field_count_ok"] = P.MIN_FIELDS <= len(fids) <= P.MAX_FIELDS
    if not checks["field_count_ok"]:
        issues.append(f"G3 字段数 {len(fids)} 不在 [{P.MIN_FIELDS},{P.MAX_FIELDS}]")

    root = tree.body if isinstance(tree.body, ast.Call) else tree.body[0].value
    zm, pos = P.profile(root)
    checks["top_level_zero_mean_ok"] = bool(zm) and top not in P.FORBIDDEN_TOP
    checks["top_level_profile"] = {"zero_mean": zm, "strictly_positive": pos}
    if not checks["top_level_zero_mean_ok"]:
        issues.append(f"G3 最外层算子 '{top}' 输出非零均值（顶层 group_rank/rank ⇒ 组合单边）")

    bad_ops = [c for c in calls if c in P.BANNED_OPS]
    checks["banned_ops"] = bad_ops
    if bad_ops:
        issues.append(f"G3 黑名单算子: {sorted(set(bad_ops))}")

    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "add" and len(n.args) == 2:
            f = [getattr(a.func, "id", "") for a in n.args if isinstance(a, ast.Call)]
            if len(f) == 2 and f[0] in ("rank", "group_rank") and f[1] in ("rank", "group_rank"):
                issues.append("G3 add(rank, rank) 无量纲加总（引擎物理拦截）")

    mult_issues = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "multiply" and len(n.args) >= 2:
            legs = [P.profile(a) for a in n.args]
            if not any(leg[1] for leg in legs):
                if all(leg[0] for leg in legs):
                    mult_issues.append(
                        f"multiply 的两腿均非恒正（{', '.join(sorted(set(field_ids(ast.unparse(n)))))}）"
                        "⇒ 可能是双有符号裸乘伪因果")
    checks["multiply_legs_ok"] = not mult_issues
    if mult_issues:
        issues.append("G3 " + "; ".join(mult_issues))

    # ---------- G3 PV 污染（跨数据集扩展） ----------
    pv_hits = [t for t in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr) if t in P.PV_FIELDS]
    pv_emb = P.PV_EMBEDDED_PAT.findall(expr)
    pv_partner = sorted(set(fids) & PARTNER_PV_FIELDS)
    checks["pv_clean"] = not pv_hits and not pv_emb and not pv_partner
    if pv_hits:
        issues.append(f"G3 外部量价污染: {sorted(set(pv_hits))}")
    if pv_emb:
        issues.append(f"G3 内嵌量价字段污染: {pv_emb}")
    if pv_partner:
        issues.append(f"G3 伙伴集量价字段污染: {pv_partner}")

    # ---------- G3 字段真实性 ----------
    unknown = [f for f in fids if f not in meta]
    checks["field_truth_ok"] = not unknown
    if unknown:
        issues.append(f"G3 字段不存在于可用池: {unknown}")

    # ---------- G3 窗口白名单 ----------
    wins = P.numeric_windows(expr)
    checks["windows"] = wins
    bad_w = [(f, v) for f, v in wins
             if not (v in P.ALLOWED_WINDOWS or (f == "ts_backfill" and v in P.BACKFILL_WINDOWS))]
    checks["window_ok"] = not bad_w
    if bad_w:
        issues.append(f"G3 窗口不在白名单 {sorted(P.ALLOWED_WINDOWS)}: {bad_w}")

    # ---------- G2 引擎量纲审计（统一表） ----------
    audit = DimensionAuditor.audit_expression(expr, meta, category="fundamental",
                                              allow_pv_cross=False, max_operators=P.ENGINE_MAX_OPS)
    checks["dimension_audit"] = {"is_valid": audit["is_valid"], "issues": audit["issues"],
                                 "operator_count": audit.get("operator_count")}
    if not audit["is_valid"]:
        issues.append(f"G2 量纲审计失败: {audit['issues']}")

    # ---------- G4 单位一致性（只查 subtract 两腿） ----------
    legs = P.subtract_legs(tree, meta)
    unit_issues = []
    for a, b in legs:
        if not a or not b or "|" in a or "|" in b:
            continue
        # 跨数据集的两腿只做「族别粗筛」，不强制同族（fnd17 与 fnd89 量纲体系本就不同）
        da, db = dataset_of(a), dataset_of(b)
        if da == db:
            ua = P.unit_family(meta.get(a, {}).get("description", ""))
            ub = P.unit_family(meta.get(b, {}).get("description", ""))
            if ua != ub and "unbounded" not in (ua, ub):
                unit_issues.append(f"subtract({a}[{ua}], {b}[{ub}]) 量纲族不一致")
    checks["subtract_legs"] = legs
    checks["unit_consistent"] = not unit_issues
    if unit_issues:
        issues.append("G4 " + "; ".join(unit_issues))

    # ---------- G5 双盲红队 ----------
    blind = DoubleBlindRedTeam.generate_blind_payload(
        expr, {"mechanism": optimize_reason, "counterparty": counterparty or "未明确对手盘"},
        meta)
    rt = DoubleBlindRedTeam.audit_candidate_blindly(blind)
    checks["engine_redteam"] = {"verdict": rt["verdict"], "issues": rt["issues"]}
    if rt["verdict"] != "PASS":
        issues.append(f"G5 红队审判: {rt['issues']}")

    return {"ok": not issues, "issues": issues, "checks": checks}


if __name__ == "__main__":
    m = load_unified_meta()
    print(f"unified meta fields: {len(m)}")
    demo = ("power(subtract(group_rank(ts_backfill(fnd17_ttmopmgn,120), sector), "
            "group_rank(ts_backfill(fnd89_major_11_11,120), sector)), 3)")
    r = preflight_cross(demo, "盈利质量与账面利润率的行业相对价差",
                        "以账面利润率为唯一口径定价的被动价值资金", m)
    print(json.dumps({"ok": r["ok"], "issues": r["issues"],
                      "ds": r["checks"].get("datasets_used"),
                      "ops": r["checks"].get("operator_count"),
                      "zm": r["checks"].get("top_level_profile")},
                     ensure_ascii=False, indent=1))
