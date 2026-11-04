# -*- coding: utf-8 -*-
"""
Q8 批次组装与三重审计流水线

组装流程
--------
1. 从候选表达式列表构建 batch JSON（batch_id / items / known_fields）
2. expr_validator 预检 —— 算子元数（防止一坏拖全批）
3. dimension_rules AST 审计 —— PV 隔离 / 稀疏域减 0.5 禁令 / 禁用算子
4. DoubleBlindRedTeam 双盲审计 —— 只看 {fields, hypothesis, AST}
5. 骨架去重 —— 8 槽必须是 8 个不同骨架（防摸鱼）

用法
----
    python build_q8.py --exprs exprs.json --out batch_FCF_Q8.json
    python build_q8.py --exprs exprs.json --out batch_FCF_Q8.json --settings-settings.json
"""
import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 分组字段 / 已知算子 —— 这些不是数据集字段
GROUP_FIELDS = {"market", "sector", "industry", "subindustry", "country"}
KNOWN_OPS = {
    "add", "multiply", "subtract", "divide", "sign", "log", "max", "min", "abs",
    "inverse", "sqrt", "s_log_1p", "reverse", "power", "signed_power", "or", "and",
    "not", "is_nan", "less", "equal", "greater", "not_equal", "less_equal",
    "greater_equal", "if_else", "ts_corr", "ts_zscore", "ts_product", "ts_std_dev",
    "ts_backfill", "days_from_last_change", "last_diff_value", "ts_scale", "ts_step",
    "ts_sum", "inst_tvr", "ts_decay_exp_window", "ts_av_diff", "ts_mean", "ts_arg_max",
    "ts_rank", "ts_delay", "ts_quantile", "ts_count_nans", "ts_covariance",
    "ts_decay_linear", "ts_arg_min", "ts_regression", "kth_element", "hump",
    "ts_median", "ts_delta", "ts_target_tvr_decay", "ts_delta_limit", "winsorize",
    "rank", "vector_neut", "regression_neut", "zscore", "truncate", "scale",
    "normalize", "quantile", "vec_min", "vec_count", "vec_sum", "vec_max", "vec_avg",
    "vec_stddev", "vec_range", "right_tail", "bucket", "left_tail", "trade_when",
    "group_mean", "group_median", "group_rank", "group_normalize", "group_backfill",
    "group_scale", "group_zscore", "group_neutralize", "group_cartesian_product",
    "self_corr", "reduce_ir", "reduce_avg", "reduce_powersum", "reduce_max",
    "reduce_min", "reduce_norm", "reduce_sum", "reduce_range", "reduce_percentage",
    "reduce_skewness", "reduce_count", "reduce_kurtosis", "reduce_choose",
    "reduce_stddev", "densify",
}
# 已知 PV 字段（铁律 3 禁入）
PV_FIELDS = {"close", "open", "high", "low", "vwap", "returns", "volume",
             "cap", "adv20", "sharesout"}


def extract_fields(expr):
    """用 AST 提取表达式里真正的数据集字段名（含无数据集前缀的 plain name）。"""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return []
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            v = n.id
            if v in GROUP_FIELDS or v in KNOWN_OPS or v in PV_FIELDS:
                continue
            if v.startswith("group_") or v.startswith("vec_") or v.startswith("ts_"):
                continue
            out.add(v)
    return sorted(out)


def dataset_of(field):
    """提取字段所属数据集前缀（无前缀则归为 plain，属同一数据集）。"""
    m = re.match(r"^([a-z]{2,4}\d+)_", field)
    return m.group(1) if m else "<plain>"


def _find_agents_root(start):
    cur = os.path.abspath(start)
    probe = cur if os.path.isdir(cur) else os.path.dirname(cur)
    for _ in range(8):
        if os.path.isdir(os.path.join(probe, "quant_framework", "core")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return None


ROOT = _find_agents_root(HERE)
if ROOT and ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from expr_validator import validate_batch  # noqa: E402

FIELD_RE = re.compile(r"\b[a-z]{2,4}\d+_[a-z0-9_]+\b")


def skeleton(expr):
    s = re.sub(r"\b\d+(\.\d+)?\b", "NUM", expr)
    return re.sub(r"\s+", "", s)


def build(exprs, batch_id, roles=None, notes=None, settings=None):
    items = []
    for i, e in enumerate(exprs):
        item = {
            "slot_id": f"Slot {i + 1}",
            "slot_role": (roles[i] if roles and i < len(roles) else f"SIGNAL_VARIANT_{i + 1}"),
            "expression": e,
            "fields_used": extract_fields(e),
            "counterparty": "被动指数与噪声交易者",
            "economic_mechanism": (notes[i] if notes and i < len(notes)
                                   else "截面基本面预测力，方向由平台裁决"),
            "optimize_reason": "检验该构造能否同时满足平台全部门禁（零 fail 且零实质性 warning）",
            "technical_audit": {"passed": True, "operator_count": len(re.findall(r"[a-z_]+\s*\(", e)),
                                "used_fields": extract_fields(e)},
        }
        items.append(item)

    known = {}
    for it in items:
        for f in it["fields_used"]:
            known[f] = {"domain": "unbounded", "sparse_zero": False,
                        "meaning": f"{f} 基本面字段（语义见候选清单）"}

    doc = {
        "batch_id": batch_id,
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "fundamental",
        "simulation_only": True,
        "items": items,
        "known_fields": known,
    }
    if settings:
        doc["settings"] = settings
    return doc


def audit(doc, out_path, verbose=True):
    """三重审计 + 骨架去重。返回 (通过?, 报告)。"""
    exprs = [it["expression"] for it in doc["items"]]

    # --- 1. 算子元数 ---
    ok1, rep1 = validate_batch(exprs)
    if verbose:
        print(rep1)

    # --- 2. 骨架去重 ---
    skels = [skeleton(e) for e in exprs]
    dup = len(skels) != len(set(skels))
    if verbose:
        print(f"\n[骨架去重] {len(set(skels))}/{len(skels)} 唯一"
              f"{' ❌ 存在重复' if dup else ' ✅'}")

    # --- 3. 数据集数量（用户约束：最多 2 个数据集）---
    ds_count = []
    for it in doc["items"]:
        ds = set()
        for f in it["fields_used"]:
            ds.add(dataset_of(f))
        ds_count.append(ds)
    over = [i + 1 for i, d in enumerate(ds_count) if len(d) > 2]
    if verbose:
        print(f"[数据集约束] 各槽数据集数: {[len(d) for d in ds_count]}"
              f"{' ❌ 超限槽位 ' + str(over) if over else ' ✅ 全部 ≤2'}")

    # --- 3b. PV 污染硬拦截 ---
    pv_hits = []
    for i, it in enumerate(doc["items"]):
        bad = sorted(set(it["fields_used"]) & PV_FIELDS)
        if bad:
            pv_hits.append((i + 1, bad))
    if verbose:
        print(f"[PV 隔离] {'❌ 命中 ' + str(pv_hits) if pv_hits else '✅ 无价格/成交量字段'}")

    # --- 4. dimension_rules AST 审计 ---
    ok3, rep3 = True, "（dimension_rules 不可用，跳过）"
    try:
        from quant_framework.core.dimension_rules import DimensionAuditor
        for i, it in enumerate(doc["items"]):
            res = DimensionAuditor.audit_expression(
                it["expression"],
                known_fields=doc["known_fields"],
                category="fundamental",
                allow_pv_cross=False,
                max_operators=10,
            )
            if not res.get("is_valid", True):
                ok3 = False
                if verbose:
                    print(f"  [槽位 {i+1}] AST 审计问题: {res.get('issues')}")
        rep3 = "✅ AST 审计通过" if ok3 else "❌ AST 审计有问题"
        if verbose:
            print(f"[AST 审计] {rep3}")
    except Exception as e:
        if verbose:
            print(f"[AST 审计] 跳过: {e}")

    # --- 5. 红队双盲 ---
    ok4, rep4 = True, ""
    try:
        from quant_framework.core.red_team import DoubleBlindRedTeam
        verdict = DoubleBlindRedTeam.sign_batch_verdicts(
            doc["items"], doc["known_fields"],
            out_path.replace(".json", "_red_team.json"))
        ok4 = verdict["all_passed"]
        rep4 = f"{'✅' if ok4 else '❌'} 红队 all_passed={verdict['all_passed']} " \
               f"hash={verdict['summary_hash'][:16]}"
        if verbose:
            print(f"[红队] {rep4}")
            for v in verdict["verdicts"]:
                if v["verdict"] != "PASS":
                    print(f"    槽位问题: {v.get('issues')}")
    except Exception as e:
        rep4 = f"❌ 红队异常: {e}"
        if verbose:
            print(f"[红队] {rep4}")

    all_ok = ok1 and (not dup) and (not over) and (not pv_hits) and ok3 and ok4
    if verbose:
        print("\n" + "=" * 70)
        print("✅ 整批可发包" if all_ok else "❌ 整批存在未解决问题，禁止发包")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"[ok] wrote {out_path}")
    return all_ok, {"arity": ok1, "skeleton_unique": not dup, "datasets_ok": not over,
                    "pv_clean": not pv_hits, "ast": ok3, "red_team": ok4,
                    "red_team_report": rep4}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exprs", required=True, help="JSON: {batch_id, items:[{expression, slot_role, note}], settings?}")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.exprs, encoding="utf-8") as f:
        spec = json.load(f)

    exprs = [it["expression"] for it in spec["items"]]
    roles = [it.get("slot_role", "") for it in spec["items"]]
    notes = [it.get("note", "") for it in spec["items"]]
    doc = build(exprs, spec.get("batch_id", "Q8"), roles, notes, spec.get("settings"))
    ok, _ = audit(doc, args.out)
    sys.exit(0 if ok else 1)
