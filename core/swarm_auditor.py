"""
swarm_auditor.py
铁律 B 的确定性执行器：减少无脑外层 rank，保留「截面残差幅度」(Cardinal Magnitude Retention)

背景问题:
    rank / group_rank 会把所有股票强行拍平成 [0,1] 均匀分布，抹杀基本面与突发事件中
    最具信息量的极端尾部幅度；同时不同特征被 rank 拍平后，截面相关性会急剧升高，
    直接把 ProdCorr 推到 0.70 以上。

本模块做四件事:
    1. outer_operator() / is_rank_outer(): 穿透 reverse/winsorize 等单调外壳，判定
       一条表达式的「最终截面形态」是否被 rank 族拍平；
    2. audit(): 统计单批 20 槽中非 rank 外壳占比、成对双窗口槽位数、外层算子直方图；
    3. enforce(): 非 rank 占比 < 40% 或成对槽位不足时物理熔断 (strict) 或返回告警；
    4. build_directive(): 生成可直接注入 Stage 1 任务卡的配额指令文本。
"""

import ast
import os
import re
import sys
from typing import Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from .horizon_probe import HorizonProbe
except (ImportError, ValueError):
    try:
        from core.horizon_probe import HorizonProbe
    except ImportError:
        try:
            from horizon_probe import HorizonProbe
        except ImportError:
            HorizonProbe = None


RANK_FAMILY = {
    "rank", "group_rank", "quantile", "group_quantile",
    "ts_rank", "normalize", "rank_by_side",
}

# 单调/等价外壳: 不改变「是否被拍平」这一性质，需要继续向内穿透
MONOTONE_WRAPPERS = {
    "reverse", "neg", "abs", "sign", "s_log_1p", "signed_power", "winsorize",
    "log", "sqrt", "exp", "power",
}

# 明确保留幅度形态的外层算子
AMPLITUDE_PRESERVING = {
    "group_neutralize", "group_zscore", "zscore", "scale", "group_scale",
    "trade_when", "if_else", "hump", "ts_decay_linear", "ts_decay_exp_window",
    "ts_mean", "ts_delta", "ts_zscore", "ts_std_dev", "add", "subtract",
    "multiply", "divide",
}


def _parse(expr: str):
    s = (expr or "").strip()
    while s.startswith("-"):
        s = s[1:].strip()
    try:
        return ast.parse(s, mode="eval")
    except SyntaxError:
        return None


def _call_name(node) -> str:
    if isinstance(node, ast.Call):
        return getattr(node.func, "id", getattr(node.func, "attr", ""))
    return ""


def _first_arg(node):
    if isinstance(node, ast.Call) and node.args:
        return node.args[0]
    return None


def outer_operator(expr: str) -> str:
    """返回表达式最外层算子名 (无法解析时用正则兜底)"""
    tree = _parse(expr)
    if tree is None:
        m = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", expr or "")
        return m.group(1) if m else ""
    return _call_name(tree.body)


def is_rank_outer(expr: str) -> bool:
    """
    判定该表达式的最终截面形态是否被 rank 族拍平。
    穿透 reverse / winsorize / s_log_1p 等单调外壳后，若最内层是 rank 族 => True。
    """
    tree = _parse(expr)
    if tree is None:
        return bool(re.search(r"(?:^|[(,]\s*)(?:group_)?rank\s*\(", expr or ""))
    node = tree.body
    for _ in range(8):
        name = _call_name(node)
        if name in RANK_FAMILY:
            return True
        if name in MONOTONE_WRAPPERS:
            node = _first_arg(node)
            if node is None:
                return False
            continue
        return False
    return False


class SwarmAuditor:
    MIN_NON_RANK_RATIO = 0.40      # 铁律 B: 至少 40% 槽位外层不用 group_rank
    MIN_PAIRED_SLOTS = 8           # 10 组骨架 x 2 槽 (20 槽批次)
    PAIRED_SLOTS_8 = 4             # 8 槽批次的最小成对槽位数

    @classmethod
    def audit(cls, variants: List[dict], parallelism: Optional[int] = None) -> dict:
        total = 0
        non_rank_slots: List[int] = []
        rank_slots: List[int] = []
        outer_hist: Dict[str, int] = {}

        for idx, v in enumerate(variants or []):
            if not isinstance(v, dict):
                continue
            expr = v.get("expression", "")
            if not expr:
                continue
            total += 1
            slot = v.get("slot")
            try:
                slot = int(slot)
            except (TypeError, ValueError):
                slot = idx + 1
            outer = outer_operator(expr) or "UNKNOWN"
            outer_hist[outer] = outer_hist.get(outer, 0) + 1
            if is_rank_outer(expr):
                rank_slots.append(slot)
            else:
                non_rank_slots.append(slot)

        pairs = HorizonProbe.detect_pairs(variants) if HorizonProbe else []
        paired_slots = sum(2 for _ in pairs)

        batch = parallelism or total or 20
        min_paired = cls.PAIRED_SLOTS_8 if batch <= 8 else cls.MIN_PAIRED_SLOTS
        ratio = (len(non_rank_slots) / total) if total else 0.0
        required_non_rank = max(1, int(round(total * cls.MIN_NON_RANK_RATIO)))

        issues: List[str] = []
        if total and ratio < cls.MIN_NON_RANK_RATIO:
            issues.append(
                f"非 rank 外壳槽位仅 {len(non_rank_slots)}/{total} ({ratio:.0%})，"
                f"低于铁律 B 要求的 {cls.MIN_NON_RANK_RATIO:.0%} (需 >= {required_non_rank} 槽)"
            )
        if total >= min_paired and paired_slots < min_paired:
            issues.append(
                f"成对双窗口槽位仅 {paired_slots} 个 (< {min_paired})，"
                f"未构成 10 组骨架 x (N, 2N) 的参数高原探针矩阵"
            )

        return {
            "total": total,
            "non_rank_count": len(non_rank_slots),
            "non_rank_ratio": round(ratio, 3),
            "required_non_rank": required_non_rank,
            "rank_outer_slots": rank_slots,
            "non_rank_outer_slots": non_rank_slots,
            "paired_slots": paired_slots,
            "min_paired_slots": min_paired,
            "pair_groups": [p["slots"] for p in pairs],
            "outer_hist": dict(sorted(outer_hist.items(), key=lambda kv: -kv[1])),
            "compliant": not issues,
            "issues": issues,
        }

    @classmethod
    def enforce(cls, variants: List[dict], step: int = 1, parallelism: Optional[int] = None,
                strict: bool = True) -> dict:
        """
        strict=True 且不达标时抛 PermissionError (与 Gate 3 骨架熔断同级)。
        step >= 2 时建议由调用方传 strict=False，因为母本病灶处方优先。
        """
        report = cls.audit(variants, parallelism=parallelism)
        tag = "铁律 B 幅度保留熔断" if step <= 1 else "铁律 B 幅度保留告警"
        if report["issues"]:
            msg = (
                f"【{tag}】本批 {report['total']} 槽的截面形态结构不合规:\n"
                + "\n".join(f"  - {i}" for i in report["issues"])
                + f"\n外层算子分布: {report['outer_hist']}\n"
                f"修正要求: 至少 {report['required_non_rank']} 槽改用 group_neutralize / group_zscore / zscore / "
                f"trade_when 等保留连续幅度的外层，并把相邻两槽组成 (N, 2N) 同骨架双窗口对。"
            )
            if strict:
                raise PermissionError(msg)
            print("⚠️ " + msg)
        else:
            print(
                f"✅ [铁律 B] 非 rank 外壳 {report['non_rank_count']}/{report['total']} "
                f"({report['non_rank_ratio']:.0%})，成对双窗口 {report['paired_slots']} 槽，形态合规。"
            )
        return report

    @classmethod
    def build_directive(cls, parallelism: int = 20, event_driven: bool = False) -> str:
        """生成可注入 Stage 1 任务卡的硬配额指令"""
        min_non_rank = max(1, int(round(parallelism * cls.MIN_NON_RANK_RATIO)))
        pairs = parallelism // 2
        lines = [
            "【铁律 B 硬配额 (本批由 Python 物理核验，不合规整批打回)】:",
            f"- 20 槽中至少 {min_non_rank} 槽 ({cls.MIN_NON_RANK_RATIO:.0%}) 的最外层不得使用 group_rank/rank，"
            f"必须改用 group_neutralize(..., subindustry) / group_zscore(..., subindustry) / zscore / trade_when；",
            f"- 采用「双窗口敏感性成对验证」: 构思 {pairs} 组正交算子拓扑骨架，每组占用 2 个相邻槽位，"
            f"分别填入 1 倍周期 N 与 2 倍周期 2N (日频 N=5 / 2N=15；季报 N=66 / 2N=132)；",
            "- 同骨架只允许窗口参数不同，其余字段与拓扑必须完全一致，否则参数高原检验无法成立；",
            "- 尖峰判据: 若 N 窗 Sharpe 达标而 2N 窗跌破 0.5，该骨架判为尖峰过拟合，禁止进入 Step 2 演进。",
        ]
        if event_driven:
            lines.append(
                "- 事件驱动数据 (news/sentiment/analyst)：推荐结合状态过滤或时序平滑算子 (如 trade_when, ts_decay_* 等) 冻结无信息日持仓，降低换手噪音。"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    demo = [
        {"slot": 1, "expression": "group_rank(ts_delta(f, 5), subindustry)"},
        {"slot": 2, "expression": "group_rank(ts_delta(f, 15), subindustry)"},
        {"slot": 3, "expression": "group_neutralize(ts_mean(g, 66), subindustry)"},
        {"slot": 4, "expression": "group_neutralize(ts_mean(g, 132), subindustry)"},
        {"slot": 5, "expression": "reverse(group_rank(winsorize(h, std=3), subindustry))"},
    ]
    rep = SwarmAuditor.audit(demo)
    print({k: rep[k] for k in ("total", "non_rank_ratio", "paired_slots", "issues", "outer_hist")})
    print(SwarmAuditor.build_directive(20, event_driven=True))
