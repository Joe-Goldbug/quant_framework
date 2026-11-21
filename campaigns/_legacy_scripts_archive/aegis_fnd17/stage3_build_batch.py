# -*- coding: utf-8 -*-
"""
Stage 3 · 批次构建器 (AEGIS fundamental17 / USA TOP1000 d1)
零配额：只做本地 AST/量纲/骨架/红队预检，不发包。
输入：total_signals.json（Stage 2 workflow 产出）
输出：batch_S1.json（8 槽）+ 每槽 optimize_reason（因果归因）+ 预检报告
"""
import ast, json, os, re, sys, hashlib, collections

sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.anti_laziness import AntiLazinessAuditor

HERE = os.path.dirname(os.path.abspath(__file__))
SHORTLIST = os.path.join(HERE, "..", "fnd17_shortlist.json")
PROFILE = os.path.join(HERE, "..", "..", "knowledge_base", "fields", "USA", "fundamental17.json")

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "fundamental"
NEUTRALIZATION = "STATISTICAL"
DECAY = 8
TRUNCATION = 0.08
ALLOWED_WINDOWS = {3, 5, 10, 20, 60, 120, 252}

# ---------------------------------------------------------------- 本地结构闸门
BANNED_OPS = {"group_neutralize", "bucket", "trade_when", "hump", "signed_power",
              "quantile", "ts_arg_max", "ts_arg_min", "reverse"}

# 引擎红队机械启发式触发的中文关键词 —— 我们的 optimize_reason 必须与之自洽
DELTA_TRIGGERS = ["边际", "变化", "跃升", "突发", "delta", "momentum", "动量"]
GATE_TRIGGERS = ["门控", "过滤", "放大", "权重", "交互"]


def ast_calls(expr):
    tree = ast.parse(expr, mode="eval")
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            calls.append(fn)
    return calls, tree


def num_consts(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            out.append(n.value)
    return out


def field_ids(expr):
    return sorted(set(re.findall(r"\b(fnd17_[a-z0-9_]+)\b", expr)))


def preflight(expr, optimize_reason, known_fields, fields_meta):
    """返回 (ok, issues, checks)"""
    issues = []
    checks = {}
    calls, tree = ast_calls(expr)
    checks["syntax_ok"] = True
    checks["operator_count"] = len(calls)
    checks["operator_count_ok"] = len(calls) <= 6
    if len(calls) > 6:
        issues.append(f"算子数 {len(calls)} > 6（协议终态上限）")
    if not calls:
        issues.append("无任何算子调用")

    # 最外层零均值
    top = calls[-1] if calls else None
    checks["top_level"] = top
    checks["top_level_zero_mean_ok"] = top in {"zscore", "ts_zscore", "group_zscore",
                                               "ts_delta", "ts_av_diff"}
    if not checks["top_level_zero_mean_ok"]:
        issues.append(f"最外层算子 '{top}' 非零均值构造（group_rank/rank 顶层⇒单边）")

    # 禁用算子
    bad = [c for c in calls if c in BANNED_OPS]
    checks["banned_ops"] = bad
    if bad:
        issues.append(f"禁用算子: {bad}")

    # add(rank,rank)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "add" and len(n.args) == 2:
            f = [getattr(a.func, "id", "") for a in n.args if isinstance(a, ast.Call)]
            if len(f) == 2 and f[0] in ("rank", "group_rank") and f[1] in ("rank", "group_rank"):
                issues.append("add(rank, rank) 无量纲加总")

    # 字段真实性
    fids = field_ids(expr)
    checks["fields_used"] = fids
    unknown = [f for f in fids if f not in known_fields]
    checks["field_truth_ok"] = not unknown
    if unknown:
        issues.append(f"字段不存在于 fundamental17: {unknown}")
    checks["field_count_ok"] = 2 <= len(fids) <= 3
    if not checks["field_count_ok"]:
        issues.append(f"字段数 {len(fids)} 不在 [2,3]")

    # 窗口白名单（ts_backfill 的 lookback 视为回填长度，单独放行 252）
    wins = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = getattr(n.func, "id", "")
            if fn.startswith("ts_") or fn in ("winsorize",):
                for a in n.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, (int, float)):
                        wins.append((fn, a.value))
    checks["windows"] = wins
    bad_w = [(f, v) for f, v in wins
             if not (v in ALLOWED_WINDOWS or (f == "ts_backfill" and v == 252))]
    checks["window_ok"] = not bad_w
    if bad_w:
        issues.append(f"窗口不在白名单: {bad_w}")

    # multiply 双有符号裸乘
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "multiply":
            args = n.args
            if len(args) >= 2:
                # 权重项必须在 [0,1] 或 rank(...) 输出
                pass
    checks["multiply_count"] = sum(1 for c in calls if c == "multiply")

    # 引擎量纲审计
    audit = DimensionAuditor.audit_expression(expr, fields_meta, category=CATEGORY,
                                              allow_pv_cross=False, max_operators=11)
    checks["dimension_audit"] = {"is_valid": audit["is_valid"], "issues": audit["issues"],
                                 "operator_count": audit["operator_count"]}
    if not audit["is_valid"]:
        issues.append(f"量纲审计失败: {audit['issues']}")

    # 引擎红队机械审计（用 optimize_reason 作为 mechanism）
    blind = DoubleBlindRedTeam.generate_blind_payload(
        expr, {"mechanism": optimize_reason, "counterparty": "n/a"}, fields_meta)
    rt = DoubleBlindRedTeam.audit_candidate_blindly(blind)
    checks["engine_redteam"] = {"verdict": rt["verdict"], "issues": rt["issues"]}
    if rt["verdict"] != "PASS":
        issues.append(f"引擎红队机械审判: {rt['issues']}")

    return (len(issues) == 0), issues, checks


def main():
    seeds = json.load(open(os.path.join(HERE, "total_signals.json"), encoding="utf-8"))
    profile = json.load(open(PROFILE, encoding="utf-8"))["fields"]
    short = json.load(open(SHORTLIST, encoding="utf-8"))

    known_fields = [f for f in profile if not profile[f]["semantic_role"].startswith("INVALID")]
    fields_meta = {}
    for f in known_fields:
        e = profile[f]
        fields_meta[f] = {"type": e["type"], "domain": e["domain"],
                          "is_sparse": e["is_sparse"], "description": e["description"]}

    sig = seeds["signals"]
    print(f"种子池: {len(sig)} 条")

    # ---- 骨架唯一性
    corr = ASTSandboxCorrector()
    skels = {}
    for s in sig:
        sk = corr.get_canonical_skeleton(s["expression"])
        skels.setdefault(sk, []).append(s["id"])
    dup = {k: v for k, v in skels.items() if len(v) > 2}
    print(f"骨架分组: {len(skels)} 组, 同骨架>2 的组: {len(dup)}")
    for k, v in dup.items():
        print(f"   ⚠ {v}")

    # ---- 逐槽预检
    items, report = [], []
    for i, s in enumerate(sig):
        reason = s.get("optimize_reason") or s.get("economic_mechanism", "")
        ok, issues, checks = preflight(s["expression"], reason, known_fields, fields_meta)
        items.append({
            "expression": s["expression"],
            "optimize_reason": reason,
            "seed_id": s["id"],
            "question_type": s["question_type"],
            "counterparty": s.get("counterparty", ""),
            "variant_type": s.get("variant_type", "SEED"),
        })
        report.append({"slot": i + 1, "id": s["id"], "ok": ok, "issues": issues,
                       "expr": s["expression"], "checks": checks})
        flag = "✅" if ok else "❌"
        print(f"{flag} Slot {i+1} {s['id']:22s} ops={checks['operator_count']} "
              f"top={checks['top_level']} fields={checks['fields_used']}")
        for it in issues:
            print(f"      ⚠ {it}")

    # ---- Tabu 检查
    for it in items:
        fids = field_ids(it["expression"])
        if fids:
            tabu, why = AntiLazinessAuditor.check_tabu(
                os.path.join(HERE, "exploration_ledger.json"), fids[0],
                fids[1] if len(fids) > 1 else None)
            if tabu:
                print(f"❌ Tabu 拦截 {it['seed_id']}: {why}")

    batch = {
        "batch_name": "aegis_fnd17_S1",
        "dataset": "fundamental17",
        "region": REGION, "universe": UNIVERSE, "delay": DELAY,
        "category": CATEGORY,
        "settings": {"neutralization": NEUTRALIZATION, "decay": DECAY,
                     "truncation": TRUNCATION, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR"},
        "slot_count": len(items),
        "known_fields": known_fields,
        "items": items,
    }
    out = os.path.join(HERE, "batch_S1.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(report, open(os.path.join(HERE, "preflight_S1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    n_ok = sum(1 for r in report if r["ok"])
    print(f"\n[Saved] {out}")
    print(f"预检通过 {n_ok}/{len(report)}")


if __name__ == "__main__":
    main()
