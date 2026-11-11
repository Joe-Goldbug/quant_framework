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
from typing import Dict, List, Optional, Set, Any, Tuple

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

# ---------------------------------------------------------------------------
# 场景路由 (Context-Aware Routing)
#   exploration = 战场 A: 全新假说, 铁律 B (非 rank 配额 + N/2N 双窗口拆解) 必须生效
#   refinement  = 老兵精修: 母本已是经验证的局部极值, 骨架属于资产而非脚手架,
#                 铁律 B 的「砍骨架」手段在此场景下有害, 只允许经济学通道上的微创手术
# ---------------------------------------------------------------------------
MODE_EXPLORATION = "exploration"
MODE_REFINEMENT = "refinement"

# 假设先行 (Hypothesis-First) 核验参数
HYPOTHESIS_MIN_CHARS = 24          # 经济学假设最小长度，低于此值视为占位符
HYPOTHESIS_MAX_DUP_RATIO = 0.30    # 逐字重复的假设占比上限，超过即判定为批量凑数
METRIC_KEYWORDS = (
    "sharpe", "夏普", "fitness", "适应度", "margin", "边际", "bps",
    "turnover", "换手", "prodcorr", "prod_corr", "自相关", "相关性", "corr",
    "cluster", "集群", "ladder", "阶梯", "drawdown", "回撑", "warning", "告警", "fail",
)


def normalize_expr(expr: str) -> str:
    return re.sub(r"\s+", "", (expr or "").replace("'", '"'))


def mask_literals(expr: str) -> str:
    """把所有数字字面量替换为 N，用于识别「只改窗口数字」的无意义微调"""
    return re.sub(r"\d+(?:\.\d+)?", "N", normalize_expr(expr))


def is_window_only_tweak(expr: str, parent_expr: str) -> bool:
    """除数字参数外与母本逐字相同 => 纯参数微调 (无经济学信息增量)"""
    if not expr or not parent_expr:
        return False
    if normalize_expr(expr) == normalize_expr(parent_expr):
        return False
    return mask_literals(expr) == mask_literals(parent_expr)


def extract_skeleton_ops(expr: str, depth: int = 3) -> List[str]:
    """
    抽取母本的「骨架算子」: 沿最外层调用链 (第一参数) 向下取 depth 层。
    例: group_zscore(ts_target_tvr_decay(multiply(a, b), target_tvr=0.12), industry)
        -> ['group_zscore', 'ts_target_tvr_decay', 'multiply']
    """
    tree = _parse(expr)
    if tree is None:
        return []
    ops: List[str] = []
    node = tree.body
    for _ in range(max(1, depth)):
        name = _call_name(node)
        if not name:
            break
        if name not in ops:
            ops.append(name)
        node = _first_arg(node)
        if node is None:
            break
    return ops


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
    MODE_EXPLORATION = MODE_EXPLORATION
    MODE_REFINEMENT = MODE_REFINEMENT
    MIN_NON_RANK_RATIO = 0.40      # 铁律 B: 至少 40% 槽位外层不用 group_rank
    MIN_PAIRED_SLOTS = 8           # 10 组骨架 x 2 槽 (20 槽批次)
    PAIRED_SLOTS_8 = 4             # 8 槽批次的最小成对槽位数
    MIN_SKELETON_RATIO = 0.60      # 精修模式: 至少 60% 槽位必须保留母本骨架算子
    MAX_WINDOW_ONLY_RATIO = 0.50   # 精修模式: 纯窗口数字微调不得超过一半槽位

    @staticmethod
    def extract_skeleton_ops(expr: str, depth: int = 3) -> List[str]:
        """母本骨架算子链 (供场景路由锁定)"""
        return extract_skeleton_ops(expr, depth)

    @classmethod
    def audit_hypothesis(cls, variants: List[dict]) -> dict:
        """
        假设先行核验: 先写经济学假设，再写表达式。

        大模型是自回归生成的 —— optimize_reason 在 JSON 中出现在 expression 之前，
        意味着推理先于公式落笔，公式只能去“满足”已经写下的因果；顺过来写就变先拼公式
        再补理由的后验辩解。因此这里物理核验三件事:
          1. 键序: optimize_reason 必须排在 expression 之前；
          2. 可证伪: 假设里必须点名 1 个以上可验收指标 (Margin/Sharpe/Turnover/ProdCorr...)，
             否则“提升信号质量”这类空话无法被回测证伪；
          3. 非凑数: 逐字重复的假设不得超过 HYPOTHESIS_MAX_DUP_RATIO。
        """
        total = 0
        ordered_bad: List[int] = []
        missing: List[int] = []
        too_short: List[int] = []
        no_metric: List[int] = []
        seen: Dict[str, List[int]] = {}

        for idx, v in enumerate(variants or []):
            if not isinstance(v, dict):
                continue
            total += 1
            try:
                slot = int(v.get("slot"))
            except (TypeError, ValueError):
                slot = idx + 1

            keys = list(v.keys())
            if "optimize_reason" in keys and "expression" in keys:
                if keys.index("optimize_reason") > keys.index("expression"):
                    ordered_bad.append(slot)

            reason = str(v.get("optimize_reason") or v.get("economic_rationale") or "").strip()
            if not reason:
                missing.append(slot)
                continue
            if len(reason) < HYPOTHESIS_MIN_CHARS:
                too_short.append(slot)
            if not any(k in reason.lower() for k in METRIC_KEYWORDS):
                no_metric.append(slot)
            seen.setdefault(reason, []).append(slot)

        dup_groups = [slots for slots in seen.values() if len(slots) > 1]
        dup_slots = sum(len(s) for s in dup_groups)

        issues: List[str] = []
        if ordered_bad:
            issues.append(
                f"{len(ordered_bad)} 槽把 expression 写在 optimize_reason 之前 (槽位 {ordered_bad}) — "
                f"属于先拼公式后补理由，假设未能约束搜索"
            )
        if missing:
            issues.append(f"{len(missing)} 槽缺少 optimize_reason 经济学假设 (槽位 {missing})")
        if too_short:
            issues.append(
                f"{len(too_short)} 槽假设不足 {HYPOTHESIS_MIN_CHARS} 字，无法构成可审查的因果论断 (槽位 {too_short})"
            )
        if no_metric:
            issues.append(
                f"{len(no_metric)} 槽假设未点名任何可验收指标 (槽位 {no_metric})，回测无法证伪该论断"
            )
        if total and (dup_slots / total) > HYPOTHESIS_MAX_DUP_RATIO:
            issues.append(
                f"逐字重复的假设涉及 {dup_slots}/{total} 槽 (> {HYPOTHESIS_MAX_DUP_RATIO:.0%})，"
                f"属于批量凑数而非逐槽因果推理"
            )

        return {
            "total": total,
            "ordered_bad_slots": ordered_bad,
            "missing_slots": missing,
            "too_short_slots": too_short,
            "no_metric_slots": no_metric,
            "duplicate_groups": dup_groups,
            "compliant": not issues,
            "issues": issues,
        }

    @classmethod
    def _audit_refinement(cls, variants: List[dict], parent_expression: str = "",
                          protected_ops: Optional[List[str]] = None, parallelism: Optional[int] = None) -> dict:
        """精修模式 (手术刀): 只核验「母本骨架是否被保护」，不要求 rank 配额与 N/2N 拆解。"""
        prot = [op for op in (protected_ops if protected_ops is not None else extract_skeleton_ops(parent_expression)) if op]
        parent_norm = normalize_expr(parent_expression)
        exprs = []
        for idx, v in enumerate(variants or []):
            if not isinstance(v, dict):
                continue
            expr = v.get("expression", "")
            if not expr:
                continue
            slot = v.get("slot")
            try:
                slot = int(slot)
            except (TypeError, ValueError):
                slot = idx + 1
            exprs.append((slot, expr))

        total = len(exprs)
        skeleton_slots: List[int] = []
        control_slots: List[int] = []
        window_only_slots: List[int] = []
        broken_slots: List[int] = []
        for slot, expr in exprs:
            if parent_norm and normalize_expr(expr) == parent_norm:
                control_slots.append(slot)
            if prot and all(op in expr for op in prot):
                skeleton_slots.append(slot)
            else:
                broken_slots.append(slot)
            if is_window_only_tweak(expr, parent_expression):
                window_only_slots.append(slot)

        ratio = (len(skeleton_slots) / total) if total else 0.0
        issues: List[str] = []
        if total and ratio < cls.MIN_SKELETON_RATIO:
            issues.append(
                f"骨架保护槽位仅 {len(skeleton_slots)}/{total} ({ratio:.0%})，低于精修模式要求的 "
                f"{cls.MIN_SKELETON_RATIO:.0%}；被拆掉母本骨架 {prot} 的槽位: {broken_slots}"
            )
        if total and not control_slots:
            issues.append("缺少控制槽: 必须有 1 槽逐字复现母本，否则本轮回测配置无法与母本历史结果对齐")
        if total and len(window_only_slots) > total * cls.MAX_WINDOW_ONLY_RATIO:
            issues.append(
                f"纯窗口数字微调占 {len(window_only_slots)}/{total} 槽，超过 {cls.MAX_WINDOW_ONLY_RATIO:.0%} 上限；"
                f"这类变体没有经济学信息增量"
            )

        hyp = cls.audit_hypothesis(variants)
        if hyp["issues"]:
            issues.extend(f"假设先行: {i}" for i in hyp["issues"])

        return {
            "mode": MODE_REFINEMENT,
            "total": total,
            "hypothesis": hyp,
            "protected_ops": prot,
            "skeleton_slots": skeleton_slots,
            "skeleton_ratio": round(ratio, 3),
            "control_slots": control_slots,
            "window_only_slots": window_only_slots,
            "broken_skeleton_slots": broken_slots,
            "compliant": not issues,
            "issues": issues,
        }

    @classmethod
    def audit(cls, variants: List[dict], parallelism: Optional[int] = None, event_driven: bool = False,
              min_non_rank_ratio: Optional[float] = None, mode: str = MODE_EXPLORATION,
              parent_expression: str = "", protected_ops: Optional[List[str]] = None) -> dict:
        if mode == MODE_REFINEMENT:
            return cls._audit_refinement(
                variants, parent_expression=parent_expression,
                protected_ops=protected_ops, parallelism=parallelism
            )
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

        if min_non_rank_ratio is not None:
            effective_min_ratio = min_non_rank_ratio
        elif event_driven:
            effective_min_ratio = 0.20  # 事件驱动/稀疏离散数据放宽至 20%，避免重尾极值破坏单调性
        else:
            effective_min_ratio = cls.MIN_NON_RANK_RATIO

        required_non_rank = max(1, int(round(total * effective_min_ratio)))

        issues: List[str] = []
        if total and ratio < effective_min_ratio:
            issues.append(
                f"非 rank 外壳槽位仅 {len(non_rank_slots)}/{total} ({ratio:.0%})，"
                f"低于铁律 B 要求的 {effective_min_ratio:.0%} (需 >= {required_non_rank} 槽)"
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
                strict: bool = True, event_driven: bool = False, min_non_rank_ratio: Optional[float] = None,
                mode: str = MODE_EXPLORATION, parent_expression: str = "",
                protected_ops: Optional[List[str]] = None) -> dict:
        """
        strict=True 且不达标时抛 PermissionError (与 Gate 3 骨架熔断同级)。
        step >= 2 时完全交由 Step 1 对照槽实测胜率决定外壳，强制 strict=False，不再硬性拦截。
        mode=refinement (老兵精修) 时铁律 B 整体停用: 骨架属于资产, 只告警不熔断。
        """
        if mode == MODE_REFINEMENT:
            strict = False   # 手术刀模式不做整批熔断, 只告警 + 记录
        elif step >= 2:
            strict = False

        report = cls.audit(
            variants, parallelism=parallelism, event_driven=event_driven,
            min_non_rank_ratio=min_non_rank_ratio, mode=mode,
            parent_expression=parent_expression, protected_ops=protected_ops
        )

        if mode == MODE_REFINEMENT:
            tag = "场景路由·老兵精修 (手术刀) 骨架保护告警"
            if report["issues"]:
                msg = (
                    f"【{tag}】本批 {report['total']} 槽未按精修契约执行:\n"
                    + "\n".join(f"  - {i}" for i in report["issues"])
                    + f"\n骨架算子: {report['protected_ops']} | 控制槽: {report['control_slots']}\n"
                    f"修正要求: 至少 {max(1, int(round(report['total'] * cls.MIN_SKELETON_RATIO)))} 槽保留母本骨架，"
                    f"并留 1 个逐字复现母本的控制槽；纯窗口数字微调不得超过半数槽位。"
                )
                print("⚠️ " + msg)
            else:
                print(
                    f"✅ [场景路由·老兵精修] 骨架保护 {len(report['skeleton_slots'])}/{report['total']} "
                    f"({report['skeleton_ratio']:.0%})，控制槽 {report['control_slots']}，"
                    f"纯窗口微调 {len(report['window_only_slots'])} 槽，契约合规。"
                )
            return report

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
    def _build_refinement_directive(cls, parallelism: int = 20, protected_ops: Optional[List[str]] = None,
                                   parent_expression: str = "", parent_settings: Optional[dict] = None) -> str:
        """老兵精修 (手术刀) 契约: 锁骨架 + 经济学通道变异 + 控制槽 + 相对改进验收"""
        prot = [op for op in (protected_ops if protected_ops is not None else extract_skeleton_ops(parent_expression)) if op]
        skeleton_str = " / ".join(prot) if prot else "母本最外层算子链"
        min_skeleton = max(1, int(round(parallelism * cls.MIN_SKELETON_RATIO)))
        lines = [
            "【场景路由 = 老兵精修 (Veteran Refinement)｜铁律 B 本批已停用】:",
            f"- 母本已被 10 年历史与近 2 年区间双重验证，骨架 [{skeleton_str}] 是资产而不是待拆的脚手架；",
            f"- 🚫 严禁把骨架 [{skeleton_str}] 中的任一算子替换或删除；严禁把外层 group_zscore 换成 group_rank/rank 来“去相关性”；",
            "   严禁把母本拆成 N/2N 双窗口孪生对——这些是战场 A 的开拓手段，用在局部极值上等于砍断脊梁；",
            f"- ✅ 骨架保留硬指标: {parallelism} 槽中至少 {min_skeleton} 槽 ({cls.MIN_SKELETON_RATIO:.0%}) 必须完整包含上述骨架算子；",
            "- ✅ 经济学通道变异 (每槽必须在 optimize_reason 写明 economic_rationale 与 target_metric，禁止只改窗口数字):",
            "   1. 风险暴露通道: 只改 group_zscore/group_neutralize 的分组层级 (industry <-> subindustry <-> sector)，验证收益来源是行业内选股还是行业配置；",
            "   2. 交易成本通道: 改 ts_target_tvr_decay 的 target_tvr (如 0.12 -> 0.08/0.15) —— 这是直接作用于换手与边际利润的旋钮，不是窗口；",
            "   3. 信号条件化通道: trade_when(信息事件条件, 母本内核, -1) 在无信息日冻结持仓，降换手抬 Margin；",
            "   4. 幅度裁剪通道: winsorize/signed_power 收紧尾部分布，改善年际夏普稳定性与 CLUSTER 告警；",
            "   5. 次要信息通道: 仅在母本内核内部追加一条同源正交字段 (multiply/add)，不新增外层、不改骨架；",
            "- 🧠 假设先行 (Python 物理核验): 每个对象必须先写 optimize_reason、再写 expression；假设内必须点名至少 1 个可验收指标"
            " (Margin / Sharpe / Turnover / ProdCorr / CLUSTER 等) 并摘述 economic_rationale——先落笔经济学因果，公式才被约束，"
            "先拼公式再补理由的后验辩解会被判违规；逐字重复的假设视为凑数；",
            "- 🧪 必须保留 1 个控制槽: 逐字复现母本表达式不做任何修改，用于确认本轮回测配置与母本历史结果同基准；",
            "- 🎯 验收门槛改为「相对母本改进」: 不追求 0 FAIL + 0 WARNING 全绿 (LOW_SHARPE / CLUSTER 这类告警由骨架本身决定，不可能清零)，",
            "   而是按母本病灶选一条轴做单点突破:",
            "   a) Margin 升 >= 20% 且 |Sharpe| 不降 (母本边际利润单薄时的主攻方向)；",
            "   b) Turnover 降 >= 20% —— 仅当母本 Turnover > 30% (换手仍高) 时适用；低换手母本严禁再降换手，那会把收益一起砍掉；",
            "   c) ProdCorr 降 >= 0.05 且 |Sharpe| 不降 (母本相关逼近 0.65 时)；",
            "   d) 后段区间 |Sharpe| 衰减收窄 (近2年 vs 10年 差距缩小)，不单独看全期均值；",
        ]
        settings = {}
        if isinstance(parent_settings, dict):
            settings = {k: parent_settings[k] for k in ("neutralization", "truncation", "decay", "nanHandling") if k in parent_settings}
        if settings:
            lines.append(
                f"- ⚖️ 基准一致性: 本轮回测配置必须与母本一致 ({settings})，否则任何对比都不成立。"
            )
        return "\n".join(lines)

    @classmethod
    def build_directive(cls, parallelism: int = 20, event_driven: bool = False,
                        mode: str = MODE_EXPLORATION, protected_ops: Optional[List[str]] = None,
                        parent_expression: str = "", parent_settings: Optional[dict] = None) -> str:
        """生成可注入 Stage 1 任务卡的指令文本 (按场景路由: 战场 A 配额 / 老兵精修契约)"""
        if mode == MODE_REFINEMENT:
            return cls._build_refinement_directive(parallelism, protected_ops, parent_expression, parent_settings)

        effective_min_ratio = 0.20 if event_driven else cls.MIN_NON_RANK_RATIO
        min_non_rank = max(1, int(round(parallelism * effective_min_ratio)))
        pairs = parallelism // 2
        ratio_label = "20% (稀疏/事件驱动特征已自适应放宽)" if event_driven else f"{cls.MIN_NON_RANK_RATIO:.0%}"
        lines = [
            "【铁律 B 硬配额 (本批由 Python 物理核验，不合规整批打回)】:",
            f"- {parallelism} 槽中至少 {min_non_rank} 槽 ({ratio_label}) 的最外层不得使用 group_rank/rank，"
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
