"""
本地Gate校验: 验证11个候选表达式是否通过所有本地门禁
(Gate 2 AST审计, Gate 3骨架唯一性, Gate 5 Tabu, 算子白名单)
"""
import ast
import io
import json
import os
import re
import sys
from collections import Counter

import sys
sys.path.insert(0, 'D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework')

from core.func_call_corrector import ASTSandboxCorrector
from core.dimension_rules import DimensionAuditor, OperatorRegistry
from core.anti_laziness import AntiLazinessAuditor



import pathlib

# discover package root: walk up until a directory containing knowledge_base/fields/GLB/ai_news_scores.json
_cand = pathlib.Path(__file__).resolve().parent
ROOT = _cand
while _cand != _cand.parent:
    if (_cand / 'knowledge_base' / 'fields' / 'GLB' / 'ai_news_scores.json').exists():
        ROOT = _cand
        break
    _cand = _cand.parent
else:
    ROOT = _cand.parent

KB = ROOT / 'knowledge_base' / 'fields' / 'GLB'
kb_path = KB / 'ai_news_scores.json'
fs_path = KB / 'fundamental23.json'

if not kb_path.exists():
    raise FileNotFoundError(f"Missing KB file: {kb_path}")

kb = json.load(io.open(kb_path, encoding="utf-8"))
fs = kb["fields"]

if not fs_path.exists():
    raise FileNotFoundError(f"Missing KB file: {fs_path}")

fnd = json.load(io.open(fs_path, encoding="utf-8"))
known_fields = {**fs, "assets_total_2": fnd["fields"]["assets_total_2"]}

HERE = pathlib.Path(__file__).resolve().parent
cdb = os.path.join(str(HERE), "alphas_record.db")

OperatorRegistry.load()
all_ops = OperatorRegistry.get_all_operator_names()

EXPECTED_TOKENS = ["negative_score_maximum_value", "assets_total_2"]

EXPRESSIONS = [
    ("E1", "group_rank(divide(group_neutralize(ts_mean(divide(negative_score_maximum_value, add(negative_score_confidence_upper_bound, 0.01)), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("D2_prime", "group_rank(divide(group_neutralize(divide(multiply(negative_score_maximum_value, negative_score_confidence_upper_bound, filter=True), add(negative_score_median_value_3, 0.01)), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("D1", "group_rank(divide(group_neutralize(ts_mean(subtract(negative_score_maximum_value, positive_score_maximum_value), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("A1", "group_rank(divide(group_neutralize(ts_mean(subtract(negative_score_maximum_value, negative_score_average_value), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("A2_prime", "group_rank(divide(group_neutralize(ts_mean(subtract(negative_score_maximum_value, negative_score_median_value_3), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("A3", "group_rank(divide(group_neutralize(ts_mean(multiply(negative_score_maximum_value, negative_score_confidence_upper_bound, filter=True), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("B1", "group_rank(divide(group_neutralize(multiply(ts_delta(negative_score_maximum_value, 1), ts_mean(negative_score_maximum_value, 250)), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("B3", "group_rank(divide(group_neutralize(divide(ts_delta(negative_score_maximum_value_3, 3), add(ts_mean(negative_score_maximum_value, 250), 0.01)), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("C1_alt", "group_rank(divide(group_neutralize(ts_mean(subtract(negative_score_maximum_value, negative_score_median_value_3), 250), country), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("D3", "group_rank(divide(group_neutralize(multiply(positive_score_maximum_value, ts_mean(negative_score_maximum_value, 250)), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("E2", "group_rank(divide(group_neutralize(multiply(ts_mean(subtract(negative_score_maximum_value, negative_score_confidence_lower_bound_3), 250), negative_score_confidence_upper_bound, filter=True), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("F1", "group_rank(divide(group_neutralize(ts_mean(divide(negative_score_maximum_value, add(negative_score_confidence_lower_bound, 0.01)), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
    ("F2", "group_rank(divide(group_neutralize(ts_mean(subtract(negative_score_maximum_value, negative_score_confidence_upper_bound), 250), subindustry), add(group_rank(assets_total_2, subindustry), 0.45)), subindustry)"),
]

TABU_PAIRS = {
    "positive_score_maximum_value:positive_score_maximum_value_3",
    "negative_score_minimum_value_2:negative_score_maximum_value",
    "negative_score_maximum_value:negative_score_median_value",
    "negative_score_maximum_value:NONE",
    "negative_score_maximum_value:negative_score_maximum_value_4",
    "negative_score_maximum_value:negative_score_maximum_value_3",
}


def count_ops(expr):
    tree = ast.parse(expr, mode="eval")
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call))


def used_fields_set(expr):
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)) & set(known_fields.keys())


def tabu_check(expr):
    tokens = [t for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr) if t in known_fields]
    if len(tokens) >= 2:
        pair = f"{tokens[0]}:{tokens[1]}"
        return pair in TABU_PAIRS, pair
    return False, None


def main():
    print(f"平台合法算子数: {len(all_ops)}")
    print()

    used_ops_in_exprs = set()
    for _, expr in EXPRESSIONS:
        tree = ast.parse(expr, mode="eval")
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                used_ops_in_exprs.add(n.func.id)

    print("=== 用到的算子合法性 ===")
    for op in sorted(used_ops_in_exprs):
        status = "OK" if op in all_ops else "UNKNOWN"
        print(f"  {status}: {op}")
    unknown = [op for op in used_ops_in_exprs if op not in all_ops]
    if unknown:
        print(f"WARNING: 未知算子 {unknown} - 可能提交后被平台拒绝")
    print()

    print("=== Gate 3 骨架唯一性 ===")
    corrector = ASTSandboxCorrector(db_path=cdb)
    skeletons = [corrector.get_canonical_skeleton(e) for _, e in EXPRESSIONS]
    skeleton_hashes = [corrector.compute_skeleton_hash(s) for s in skeletons]
    cnt = Counter(skeleton_hashes)
    dupes = {h: c for h, c in cnt.items() if c > 1}
    if dupes:
        print(f"FAIL: 发现 {len(dupes)} 个骨架重复, 可能触发 Gate 3 熔断")
        for h, c in dupes.items():
            idxs = [i for i, sh in enumerate(skeleton_hashes) if sh == h]
            print(f"  骨架哈希 {h[:8]}... 出现在索引 {idxs}")
            for i in idxs:
                print(f"    - {EXPRESSIONS[i][0]}: {EXPRESSIONS[i][1]}")
    else:
        print("所有骨架各不相同 OK")
    print()

    print("=== Gate 5 Tabu 检查 ===")
    all_tabu_safe = True
    for name, expr in EXPRESSIONS:
        tabu_hit, pair = tabu_check(expr)
        status = "TABU命中" if tabu_hit else "安全"
        if tabu_hit:
            all_tabu_safe = False
        print(f"  {name}: pair={pair or '-':40} -> {status}")
    if all_tabu_safe:
        print("全部 Tabu 安全 OK")
    print()

    print("=== 批量 AST 审计 (Gate 2) ===")
    batch_exprs = [e for _, e in EXPRESSIONS]
    try:
        corrected_exprs = corrector.check_and_record_batch(
            batch_exprs, "GLB", "MINVOL1M", 1, "COUNTRY", batch_id="validate_tmp"
        )
        print(f"Gate 3(骨架唯一性)通过, 已纠正并记录 {len(corrected_exprs)} 个表达式")
        print()
        for idx, (name, orig_expr) in enumerate(EXPRESSIONS):
            expr = corrected_exprs[idx]
            audit = DimensionAuditor.audit_expression(
                expr,
                known_fields,
                category="other",
                allow_pv_cross=False,
                max_operators=10,
                step=1,
                allowed_operators=None,
                stage0_op_count=7,
                required_fields=EXPECTED_TOKENS,
            )
            if audit["is_valid"]:
                print(f"  [{name}] OPS={count_ops(expr):2} FIELDS={len(used_fields_set(expr))} -> Gate 2通过")
            else:
                print(f"  [{name}] OPS={count_ops(expr):2} FIELDS={len(used_fields_set(expr))} -> Gate 2 FAIL")
                for issue in audit["issues"]:
                    print(f"      ! {issue}")
    except Exception as e:
        print(f"批量校验异常: {type(e).__name__}: {e}")

    print()
    print("=== 预校验总结 ===")
    all_ok = (
        len(unknown) == 0
        and not dupes
        and all_tabu_safe
    )
    print(f"算子合法: {'OK' if not unknown else 'FAIL(' + str(unknown) + ')'}")
    print(f"骨架唯一: {'OK' if not dupes else 'FAIL'}")
    print(f"Tabu安全:  {'OK' if all_tabu_safe else 'FAIL'}")
    print(f"总体: {'全部通过,准备提交' if all_ok else '存在问题,需修复'}")


if __name__ == "__main__":
    main()
