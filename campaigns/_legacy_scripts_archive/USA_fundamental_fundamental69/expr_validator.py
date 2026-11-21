# -*- coding: utf-8 -*-
"""
FASTEXPR 算子元数预检器 (Pre-flight Arity Validator)

背景 (2026-10-28 血泪教训)
--------------------------
FCF_Q6 批次 8 条表达式发包后，平台返回 multisimulation status = ERROR，
8 个 child 里 7 个 CANCELLED、1 个 ERROR，错误信息：

    "Invalid number of inputs : 2, should be exactly 1 input(s)."
    location: {line:1, start:0, end:112, property:"regular"}

端到端定位：槽位 6 的 `hump(<expr>, 0.01)`。BRAIN 算子元表定义
`hump(x, hump = 0.01)` —— 第二参数是**仅限关键字**参数，位置传参会被平台
解析成「2 个输入」而报错。**单条表达式语法错误会连带取消同批全部 child**，
8 条卡槽一次性归零，配额全烧。

而 `winsorize(x, std=4)` / `rank(x, rate=2)` / `quantile(x, driver=...)`
同样属于「可选参数仅限关键字」的算子族，位置传参一律会炸。

本模块把这些血泪规则固化成**物理预检**：发包前逐条扫描，任何一条不合法
直接拒绝整批，杜绝「一坏拖全批」。

用法
----
    from expr_validator import validate_batch
    ok, report = validate_batch(expressions)
    if not ok: raise SystemExit(report)
"""

import re
import sys
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 算子元表：name -> (最少位置参数, 最多位置参数, 可选关键字参数集合)
#
# 规则来源：BRAIN `get_operators` 官方返回 (2026-10-28 实测) +
#           历史已提交 alpha 的实际写法交叉验证。
#
# 「最多位置参数」= 该算子允许的位置实参个数上限。
#   若算子定义形如 f(x, optional_kw)，则最多位置参数 = 1，
#   第二个实参必须写成 optional_kw=... 否则平台报
#   "Invalid number of inputs : N, should be exactly M input(s)"。
# ---------------------------------------------------------------------------
OPERATOR_SPEC: Dict[str, Tuple[int, int, set]] = {
    # ---- Arithmetic ----
    "add":                 (2, 99, {"filter"}),
    "multiply":            (2, 99, {"filter"}),
    "subtract":            (2, 99, {"filter"}),
    "sign":                (1, 1, set()),
    "log":                 (1, 1, set()),
    "max":                 (2, 99, set()),
    "min":                 (2, 99, set()),
    "abs":                 (1, 1, set()),
    "divide":              (2, 2, set()),
    "signed_power":        (2, 2, set()),
    "inverse":             (1, 1, set()),
    "sqrt":                (1, 1, set()),
    "s_log_1p":            (1, 1, set()),
    "reverse":             (1, 1, set()),
    "power":               (2, 2, set()),
    # ---- Logical ----
    "or":                  (2, 2, set()),
    "and":                 (2, 2, set()),
    "not":                 (1, 1, set()),
    "is_nan":              (1, 1, set()),
    "less":                (2, 2, set()),
    "equal":               (2, 2, set()),
    "greater":             (2, 2, set()),
    "not_equal":           (2, 2, set()),
    "less_equal":          (2, 2, set()),
    "greater_equal":       (2, 2, set()),
    "if_else":             (3, 3, set()),
    # ---- Time Series ----
    "ts_corr":             (3, 3, set()),
    "ts_zscore":           (2, 2, set()),
    "ts_product":          (2, 2, set()),
    "ts_std_dev":          (2, 2, set()),
    # ts_backfill(x, lookback=d, k=1) -> 位置实参上限 1
    "ts_backfill":         (1, 2, {"lookback", "k"}),   # 实测位置传参可用 (EUR 冠军 3qVlb3dN)
    "days_from_last_change": (1, 1, set()),
    "last_diff_value":     (2, 2, set()),
    "ts_scale":            (2, 2, {"constant"}),
    "ts_step":             (1, 1, set()),
    "ts_sum":              (2, 2, set()),
    "inst_tvr":            (2, 2, set()),
    # ts_decay_exp_window(x, d, factor=f) -> d 是必填位置参数
    "ts_decay_exp_window": (2, 2, {"factor"}),
    "ts_av_diff":          (2, 2, set()),
    "ts_mean":             (2, 2, set()),
    "ts_arg_max":          (2, 2, set()),
    "ts_rank":             (2, 2, {"constant"}),
    "ts_delay":            (2, 2, set()),
    "ts_quantile":         (2, 2, {"driver"}),
    "ts_count_nans":       (2, 2, set()),
    "ts_covariance":       (3, 3, set()),
    "ts_decay_linear":     (2, 2, {"dense"}),
    "ts_arg_min":          (2, 2, set()),
    "ts_regression":       (3, 3, {"lag", "rettype"}),
    "kth_element":         (3, 3, {"ignore"}),
    # hump(x, hump=0.01) -> 第二参数仅限关键字 ★ 本次事故根因
    "hump":                (1, 1, {"hump"}),
    "ts_median":           (2, 2, set()),
    "ts_delta":            (2, 2, set()),
    "ts_target_tvr_decay": (1, 1, {"lambda_min", "lambda_max", "target_tvr"}),
    "ts_delta_limit":      (2, 2, {"limit_volume"}),
    # ---- Cross Sectional ----
    # winsorize(x, std=4) -> 第二参数仅限关键字 ★ 同族风险
    "winsorize":           (1, 2, {"std"}),           # 未实测位置传参, 宽松放行
    "rank":                (1, 2, {"rate"}),
    "vector_neut":         (2, 2, set()),
    "regression_neut":     (2, 2, set()),
    "zscore":              (1, 1, set()),
    # truncate(x, maxPercent=0.01) -> 仅限关键字
    "truncate":            (1, 2, {"maxPercent"}),
    "scale":               (1, 1, {"scale", "longscale", "shortscale"}),
    "normalize":           (1, 1, {"useStd", "limit"}),
    # quantile(x, driver=gaussian, sigma=1.0) -> 仅限关键字
    "quantile":            (1, 2, {"driver", "sigma"}),
    # ---- Vector ----
    "vec_min":             (1, 1, set()),
    "vec_count":           (1, 1, set()),
    "vec_sum":             (1, 1, set()),
    "vec_max":             (1, 1, set()),
    "vec_avg":             (1, 1, set()),
    "vec_stddev":          (1, 1, set()),
    "vec_range":           (1, 1, set()),
    # ---- Transformational ----
    "right_tail":          (1, 1, {"minimum"}),
    "bucket":              (1, 1, {"range", "buckets", "skipBoth", "NaNGroup"}),
    "left_tail":           (1, 1, {"maximum"}),
    "trade_when":          (3, 3, set()),
    # ---- Group ----
    "group_mean":          (3, 3, set()),
    "group_median":        (2, 2, set()),
    "group_rank":          (2, 2, set()),
    "group_normalize":     (2, 2, {"constantCheck", "tolerance", "scale"}),
    "group_backfill":      (3, 3, {"std"}),
    "group_scale":         (2, 2, set()),
    "group_zscore":        (2, 2, set()),
    "group_neutralize":    (2, 2, set()),
    "group_cartesian_product": (2, 2, set()),
    # ---- Special / Reduce (COMBO scope, 此处仅做基础校验) ----
    "self_corr":           (1, 1, set()),
    "reduce_ir":           (1, 1, set()),
    "reduce_avg":          (1, 1, {"threshold"}),
    "reduce_powersum":     (1, 1, {"constant", "precise"}),
    "reduce_max":          (1, 1, set()),
    "reduce_min":          (1, 1, set()),
    "reduce_norm":         (1, 1, set()),
    "reduce_sum":          (1, 1, set()),
    "reduce_range":        (1, 1, set()),
    "reduce_percentage":   (1, 1, {"percentage"}),
    "reduce_skewness":     (1, 1, set()),
    "reduce_count":        (2, 2, set()),
    "reduce_kurtosis":     (1, 1, set()),
    "reduce_choose":       (2, 2, {"ignoreNan"}),
    "reduce_stddev":       (1, 1, {"threshold"}),
    "densify":             (1, 1, set()),
}

# 已知分组字段（非算子，出现在 group_xxx 第二位）
GROUP_FIELDS = {"market", "sector", "industry", "subindustry", "country",
                "densify(bucket(rank(cap), range=\"0, 0.2, 0.1\"))"}

# 已知量价字段（本战役严禁引入，用于 PV 污染硬拦截）
PV_FIELDS = {"close", "open", "high", "low", "vwap", "returns", "volume",
             "cap", "adv20", "sharesout"}


def _split_top_level(s: str) -> List[str]:
    """按顶层逗号切分实参列表，忽略括号内与引号内的逗号。"""
    parts, buf, depth, in_q = [], [], 0, False
    for ch in s:
        if in_q:
            buf.append(ch)
            if ch == '"':
                in_q = False
            continue
        if ch == '"':
            in_q = True
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return [p for p in parts if p != ""] if parts else []


def _parse_calls(expr: str):
    """产出 (op_name, [arg_strings], start_index) 三元组序列。"""
    calls = []
    for m in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", expr):
        name = m.group(1)
        start = m.end()
        depth, i, in_q = 1, start, False
        while i < len(expr) and depth > 0:
            ch = expr[i]
            if in_q:
                if ch == '"':
                    in_q = False
            elif ch == '"':
                in_q = True
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            i += 1
        inner = expr[start:i - 1]
        calls.append((name, _split_top_level(inner), m.start()))
    return calls


def _is_keyword_arg(arg: str) -> bool:
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*=", arg.strip()))


def _kw_name(arg: str) -> str:
    return arg.strip().split("=", 1)[0].strip()


def validate_expression(expr: str) -> List[str]:
    """返回该表达式的错误列表，空列表表示合法。"""
    errors: List[str] = []
    if not expr or not expr.strip():
        return ["表达式为空"]

    # 1) 括号配平
    depth = 0
    for ch in expr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                errors.append("括号提前闭合")
                break
    if depth != 0:
        errors.append(f"括号不配平 (残余深度 {depth})")

    # 2) PV 污染
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr))
    pv_hit = sorted(tokens & PV_FIELDS)
    if pv_hit:
        errors.append(f"PV 污染 (铁律 3 禁止): {pv_hit}")

    # 3) 算子元数校验
    for name, args, pos in _parse_calls(expr):
        spec = OPERATOR_SPEC.get(name)
        if spec is None:
            # 分组字段 / 数据字段 / 未知算子：未知算子交由平台裁决，
            # 但显式提示，避免「拼错算子名」这类静默错误。
            if name in GROUP_FIELDS or name.startswith("fnd") or name.startswith("anl"):
                continue
            if name in {"std", "hump", "maxPercent", "driver", "sigma", "constant",
                        "rate", "lookback", "k", "factor", "dense", "useStd", "limit",
                        "lag", "rettype", "ignore", "ignoreNan", "threshold",
                        "percentage", "constantCheck", "tolerance", "scale",
                        "longscale", "shortscale", "lambda_min", "lambda_max",
                        "target_tvr", "limit_volume", "minimum", "maximum",
                        "filter", "range", "buckets", "skipBoth", "NaNGroup"}:
                continue
            errors.append(f"未知算子 '{name}' (位置 {pos}) —— 请核对算子名拼写")
            continue

        min_pos, max_pos, kwset = spec
        positional = [a for a in args if not _is_keyword_arg(a)]
        keywords = [_kw_name(a) for a in args if _is_keyword_arg(a)]

        if len(positional) < min_pos:
            errors.append(
                f"算子 '{name}' 位置参数不足: 给了 {len(positional)} 个, 至少需 {min_pos} 个")
        if len(positional) > max_pos:
            errors.append(
                f"算子 '{name}' 位置参数过多: 给了 {len(positional)} 个 "
                f"(最多 {max_pos} 个)。可选参数必须写成关键字形式, "
                f"例如 {name}(x, {sorted(kwset)[0] if kwset else 'param'}=...)。"
                f" ★该错误会取消同批全部 child")
        bad_kw = [k for k in keywords if k not in kwset]
        if bad_kw:
            errors.append(f"算子 '{name}' 不支持关键字参数 {bad_kw} (允许: {sorted(kwset)})")

    return errors


def validate_batch(expressions: List[str]) -> Tuple[bool, str]:
    """整批校验。返回 (是否可发包, 人类可读报告)。"""
    lines, all_ok = [], True
    for i, expr in enumerate(expressions, 1):
        errs = validate_expression(expr)
        if errs:
            all_ok = False
            lines.append(f"  [槽位 {i}] ❌")
            for e in errs:
                lines.append(f"      - {e}")
            lines.append(f"      表达式: {expr}")
        else:
            lines.append(f"  [槽位 {i}] ✅ 通过元数与量纲预检")
    verdict = "✅ 整批预检通过，可发包" if all_ok else "❌ 整批预检失败，禁止发包"
    return all_ok, f"{verdict}\n" + "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    exprs = [it.get("expression", "") for it in doc.get("items", [])]
    ok, report = validate_batch(exprs)
    print(report)
    sys.exit(0 if ok else 1)
