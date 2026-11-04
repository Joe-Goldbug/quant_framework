"""
horizon_probe.py
双窗口敏感性成对验证法 (Paired Horizon Probe) —— 参数高原压力测试器

背景问题:
    Gate 3 允许「同一 AST 骨架在单批中出现 2~4 条」，普通 Agent 视之为限制，
    顶级研究员则把它当成内置的参数敏感性压力测试器。

本模块做三件事:
    1. detect_pairs(): 从 20 个槽位中识别「同骨架 + 窗口比 ~2 倍」的成对槽位 (N 与 2N)；
    2. evaluate(): 回测完成后，逐对比较 Sharpe，给出参数高原 / 尖峰过拟合判决；
    3. annotate()/filter_parents(): 把判决写回候选字典，并剔除尖峰过拟合母本，
       防止其污染 Step 2 的演进源头 (尖峰结构在隐藏 OS 上极易失效)。

判决口径 (与研究员给定的黄金判据一致):
    PLATEAU  两个窗口 |Sharpe| 均 >= 1.0 且同号          -> 机制具备时序韧性，可作母本
    SPIKE    一窗 >= 1.0 而另一窗 < 0.5                  -> 严重依赖窗口巧合，禁止作母本
    WEAK     其余情形                                     -> 证据不足，降权处理
    NO_DATA  该槽位未跑出有效指标                          -> 不下判决
"""

import ast
import os
import re
import sys
from typing import Dict, List, Optional, Tuple, Union

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from .func_call_corrector import ASTSandboxCorrector
except (ImportError, ValueError):
    try:
        from core.func_call_corrector import ASTSandboxCorrector
    except ImportError:
        try:
            from func_call_corrector import ASTSandboxCorrector
        except ImportError:
            ASTSandboxCorrector = None


TIME_SERIES_OPS = {
    "ts_delta", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
    "ts_decay_linear", "ts_decay_exp_window", "ts_delay", "ts_corr", "ts_min",
    "ts_max", "ts_arg_max", "ts_arg_min", "ts_av_diff", "ts_scale", "ts_backfill",
    "ts_returns", "ts_ir", "ts_skewness", "ts_kurtosis", "ts_quantile",
    "ts_regression", "ts_count_nans", "ts_product", "jump_decay",
}

# 允许的窗口倍率区间: 覆盖 d=5/15 (3x) 与 d=66/132 (2x) 两种常见成对写法
RATIO_LOW, RATIO_HIGH = 1.6, 3.5


def _norm_expr(expr: str) -> str:
    return re.sub(r"\s+", "", (expr or "").strip().lower())


def extract_windows(expr: str) -> List[int]:
    """抽取表达式中所有时序算子的整数窗口参数 (跳过第一个数据参数)"""
    windows: List[int] = []
    try:
        tree = ast.parse((expr or "").strip(), mode="eval")
    except SyntaxError:
        return windows
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if fname not in TIME_SERIES_OPS:
            continue
        for arg in node.args[1:]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int) and not isinstance(arg.value, bool):
                windows.append(int(arg.value))
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int) and not isinstance(kw.value.value, bool):
                if kw.arg not in ("factor",):
                    windows.append(int(kw.value.value))
    return windows


def _skeleton(expr: str) -> str:
    if ASTSandboxCorrector is None:
        return re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", _norm_expr(expr))
    try:
        return ASTSandboxCorrector.get_canonical_skeleton(expr)
    except Exception:
        return re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", _norm_expr(expr))


def _slot_of(item: dict, idx: int) -> int:
    raw = item.get("slot")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return idx + 1


class HorizonProbe:
    """成对双窗口探针"""

    # ---------------- 1. 配对识别 ----------------
    @classmethod
    def detect_pairs(cls, variants: List[dict]) -> List[dict]:
        """
        识别同骨架 + 窗口比 ~2 倍的成对槽位。
        返回 [{"slots": (a,b), "skeleton": ..., "windows": (n, 2n),
               "expr_a": ..., "expr_b": ...}, ...]
        """
        entries = []
        for idx, v in enumerate(variants or []):
            if not isinstance(v, dict):
                continue
            expr = v.get("expression", "")
            if not expr:
                continue
            entries.append({
                "slot": _slot_of(v, idx),
                "expr": expr,
                "skel": _skeleton(expr),
                "windows": extract_windows(expr),
            })

        by_skel: Dict[str, List[dict]] = {}
        for e in entries:
            by_skel.setdefault(e["skel"], []).append(e)

        pairs: List[dict] = []
        used = set()
        for skel, group in by_skel.items():
            if len(group) < 2:
                continue
            group = sorted(group, key=lambda x: x["slot"])
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["slot"] in used or b["slot"] in used:
                        continue
                    wa, wb = a["windows"], b["windows"]
                    if not wa or not wb or len(wa) != len(wb):
                        continue
                    pair_ok = False
                    best = None
                    swap_order = False
                    for x, y in zip(wa, wb):
                        if x <= 0 or y <= 0:
                            continue
                        ratio = max(x, y) / float(min(x, y))
                        if RATIO_LOW <= ratio <= RATIO_HIGH:
                            pair_ok = True
                            best = (min(x, y), max(x, y))
                            if x > y:
                                swap_order = True
                            break
                    if not pair_ok:
                        continue
                    used.add(a["slot"])
                    used.add(b["slot"])
                    expr_short = b["expr"] if swap_order else a["expr"]
                    expr_long = a["expr"] if swap_order else b["expr"]
                    pairs.append({
                        "slots": (a["slot"], b["slot"]),
                        "skeleton": skel,
                        "windows": best,
                        "expr_short": expr_short,
                        "expr_long": expr_long,
                        "expr_a": expr_short,
                        "expr_b": expr_long,
                    })
        pairs.sort(key=lambda p: p["slots"][0])
        return pairs

    # ---------------- 2. 判决 ----------------
    @classmethod
    def evaluate(
        cls,
        variants: List[dict],
        qualified_seeds: Union[List[dict], Dict[str, float]],
        pairs: Optional[List[dict]] = None,
        min_sharpe: float = 1.0,
        spike_floor: float = 0.5,
        all_sharpes: Optional[Dict[str, float]] = None,
    ) -> List[dict]:
        """基于 Step 1 回测结果，对每对窗口给出参数高原 / 尖峰判决"""
        pairs = pairs if pairs is not None else cls.detect_pairs(variants)
        sharpe_map: Dict[str, float] = {}

        # 1. 优先载入全量回测夏普字典 (覆盖 |Sharpe| in [0.50, 0.99] 的配对窗口)
        if all_sharpes and isinstance(all_sharpes, dict):
            for k, v in all_sharpes.items():
                try:
                    sharpe_map[_norm_expr(k)] = float(v)
                except (TypeError, ValueError):
                    continue

        # 2. 从 qualified_seeds 载入 (兼容字典或列表)
        if isinstance(qualified_seeds, dict):
            for k, v in qualified_seeds.items():
                try:
                    sharpe_map[_norm_expr(k)] = float(v)
                except (TypeError, ValueError):
                    continue
        elif isinstance(qualified_seeds, list):
            for q in qualified_seeds:
                if not isinstance(q, dict):
                    continue
                try:
                    expr = q.get("expression") or q.get("code") or ""
                    if expr:
                        sharpe_map[_norm_expr(expr)] = float(q.get("sharpe"))
                except (TypeError, ValueError):
                    continue

        verdicts: List[dict] = []
        for p in pairs:
            sa = sharpe_map.get(_norm_expr(p.get("expr_a", "")))
            sb = sharpe_map.get(_norm_expr(p.get("expr_b", "")))
            short_w, long_w = p["windows"]

            if sa is None and sb is None:
                verdict = "NO_DATA"
            else:
                vals = [abs(v) for v in (sa, sb) if v is not None]
                both_pass = all(abs(v) >= min_sharpe for v in (sa, sb) if v is not None) and len(vals) == 2
                same_sign = (sa is not None and sb is not None and sa * sb > 0)
                any_spike = (len(vals) == 2 and max(vals) >= min_sharpe and min(vals) < spike_floor)
                # 兼容健康参数高原 (Parameter Plateau):
                # 例如 (1.28, 0.92): 一窗达标 (>= 1.0)，另一窗未坍塌 (>= 0.75) 且同号
                plateau_pass = bool(same_sign and len(vals) == 2 and max(vals) >= min_sharpe and min(vals) >= 0.75)

                if (both_pass or plateau_pass) and same_sign:
                    verdict = "PLATEAU"
                elif any_spike:
                    verdict = "SPIKE"
                elif len(vals) < 2:
                    verdict = "NO_DATA"
                else:
                    verdict = "WEAK"

            stable_min = None
            if sa is not None and sb is not None:
                stable_min = round(min(abs(sa), abs(sb)), 3)

            verdicts.append({
                "slots": p["slots"],
                "windows": [short_w, long_w],
                "sharpe_short": sa,
                "sharpe_long": sb,
                "stable_min_abs_sharpe": stable_min,
                "verdict": verdict,
                "plateau_pass": (verdict == "PLATEAU"),
                "skeleton": p["skeleton"],
            })
        return verdicts

    # ---------------- 3. 写回与母本过滤 ----------------
    @classmethod
    def annotate(cls, candidates: List[dict], verdicts: List[dict], pairs: List[dict]) -> dict:
        """
        把 horizon_verdict / plateau_pass 写回候选字典。
        返回 {expr_norm: verdict} 便于日志输出。
        """
        expr_to_verdict: Dict[str, str] = {}
        for p, v in zip(pairs, verdicts):
            expr_to_verdict[_norm_expr(p.get("expr_a", ""))] = v["verdict"]
            expr_to_verdict[_norm_expr(p.get("expr_b", ""))] = v["verdict"]

        for c in candidates or []:
            if not isinstance(c, dict):
                continue
            key = _norm_expr(c.get("expression", ""))
            vd = expr_to_verdict.get(key)
            c["horizon_verdict"] = vd
            c["plateau_pass"] = (vd == "PLATEAU") if vd else None
        return expr_to_verdict

    @classmethod
    def filter_parents(cls, candidates: List[dict]) -> Tuple[List[dict], List[dict]]:
        """
        母本过滤: 剔除 SPIKE (尖峰过拟合)，其余保留。
        未参与配对 (horizon_verdict is None) 的候选视为「无配对证据」，予以保留。
        """
        kept, dropped = [], []
        for c in candidates or []:
            vd = c.get("horizon_verdict")
            if vd == "SPIKE":
                dropped.append(c)
            else:
                kept.append(c)
        return kept, dropped

    # ---------------- 4. 摘要 ----------------
    @classmethod
    def summarize(cls, verdicts: List[dict]) -> dict:
        counts = {"PLATEAU": 0, "SPIKE": 0, "WEAK": 0, "NO_DATA": 0}
        for v in verdicts:
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        plateau_slots = [v["slots"] for v in verdicts if v["verdict"] == "PLATEAU"]
        spike_slots = [v["slots"] for v in verdicts if v["verdict"] == "SPIKE"]
        return {
            "pairs": len(verdicts),
            "counts": counts,
            "plateau_slots": plateau_slots,
            "spike_slots": spike_slots,
            "paired_slot_count": sum(2 for _ in verdicts),
        }

    @classmethod
    def format_report(cls, verdicts: List[dict]) -> str:
        if not verdicts:
            return "⚠️ [双窗口探针] 本批未识别到「同骨架 + 窗口 2 倍」的成对槽位，参数高原检验无法执行。"
        lines = []
        for v in verdicts:
            sa = "N/A" if v["sharpe_short"] is None else f"{v['sharpe_short']:.2f}"
            sb = "N/A" if v["sharpe_long"] is None else f"{v['sharpe_long']:.2f}"
            icon = {"PLATEAU": "🟢", "SPIKE": "🔴", "WEAK": "🟡", "NO_DATA": "⚪"}.get(v["verdict"], "⚪")
            lines.append(
                f"  {icon} slots {v['slots']} | N={v['windows'][0]} Sharpe={sa} vs 2N={v['windows'][1]} Sharpe={sb} -> {v['verdict']}"
            )
        s = cls.summarize(verdicts)
        head = (
            f"🔬 [双窗口探针] 识别 {s['pairs']} 组配对 | 参数高原 {s['counts']['PLATEAU']} 组 | "
            f"尖峰过拟合 {s['counts']['SPIKE']} 组 | 证据不足 {s['counts']['WEAK']} 组"
        )
        return head + "\n" + "\n".join(lines)


if __name__ == "__main__":
    demo = [
        {"slot": 1, "expression": "group_neutralize(ts_delta(f, 5), subindustry)"},
        {"slot": 2, "expression": "group_neutralize(ts_delta(f, 15), subindustry)"},
        {"slot": 3, "expression": "group_neutralize(ts_mean(g, 66), subindustry)"},
        {"slot": 4, "expression": "group_neutralize(ts_mean(g, 132), subindustry)"},
        {"slot": 5, "expression": "group_zscore(ts_delta(h, 5), subindustry)"},
    ]
    pairs = HorizonProbe.detect_pairs(demo)
    print("pairs:", [(p["slots"], p["windows"]) for p in pairs])
    q = [
        {"expression": demo[0]["expression"], "sharpe": 1.45},
        {"expression": demo[1]["expression"], "sharpe": -0.20},
        {"expression": demo[2]["expression"], "sharpe": 1.22},
        {"expression": demo[3]["expression"], "sharpe": 1.31},
    ]
    v = HorizonProbe.evaluate(demo, q, pairs)
    print(HorizonProbe.format_report(v))
