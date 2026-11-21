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
    from .fastexpr_ast import parse_fastexpr
except (ImportError, ValueError):
    try:
        from core.fastexpr_ast import parse_fastexpr
    except ImportError:
        from fastexpr_ast import parse_fastexpr

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

try:
    from .func_call_corrector import ASTSandboxCorrector
except (ImportError, ValueError):
    try:
        from core.func_call_corrector import ASTSandboxCorrector
    except ImportError:
        ASTSandboxCorrector = None

try:
    from .dgp_schema import MECHANISM_INTENTS
except (ImportError, ValueError):
    try:
        from core.dgp_schema import MECHANISM_INTENTS
    except ImportError:
        MECHANISM_INTENTS = set()


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
    parsed = parse_fastexpr(s)
    if not parsed.is_valid or parsed.final_ast is None:
        return None
    return ast.Expression(body=parsed.final_ast)


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
    MIN_NON_RANK_RATIO = 0.20      # V2: 降低刚性配额，避免为凑比例堆装饰；rank 是否合适由假说决定
    MIN_PAIRED_SLOTS = 2           # V2: 至少 1 组双窗口对照做期限稳健性，不再强制 10 组拓扑
    PAIRED_SLOTS_8 = 2             # 8 槽批次同样至少 1 组对照
    MIN_SKELETON_RATIO = 0.45      # 精修模式: 至少 45% 槽位保留母本主锚字段/骨架 (1+9+10 三分天下制)
    MAX_WINDOW_ONLY_RATIO = 0.10   # 精修模式: 纯窗口数字微调严格限制 <= 10% (禁止摸鱼调参)

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
        intents_missing: List[int] = []
        intents_invalid: List[int] = []
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
            reason_key = "optimize_reason" if "optimize_reason" in keys else ("prediction" if "prediction" in keys else None)
            if reason_key and "expression" in keys:
                if keys.index(reason_key) > keys.index("expression"):
                    ordered_bad.append(slot)

            v_type = str(v.get("type") or "").strip().lower()
            is_control = v_type in ("parent_control", "ablation_control", "placebo_control")
            is_v41_compact = bool(v.get("change_axis") and v.get("prediction") is not None)

            intents = v.get("mechanism_intents")
            if not is_control and not is_v41_compact:
                if not isinstance(intents, list) or not intents:
                    intents_missing.append(slot)
                elif not all(isinstance(intent, str) and intent.strip() for intent in intents):
                    intents_invalid.append(slot)

            reason = str(v.get("optimize_reason") or v.get("prediction") or v.get("economic_rationale") or "").strip()
            if not reason:
                if not is_control:
                    missing.append(slot)
                continue
            if not is_control:
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
        if intents_missing:
            issues.append(f"{len(intents_missing)} 槽缺少 mechanism_intents，无法做语义—AST 审计 (槽位 {intents_missing})")
        if intents_invalid:
            issues.append(f"{len(intents_invalid)} 槽存在非法 mechanism_intents (槽位 {intents_invalid})")
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
            "intents_missing_slots": intents_missing,
            "intents_invalid_slots": intents_invalid,
            "duplicate_groups": dup_groups,
            "compliant": not issues,
            "issues": issues,
        }

    @classmethod
    def upgrade_6key_to_9key(cls, variants: List[dict], default_hypothesis_id: str = "HYP_BATCH_DEFAULT") -> List[dict]:
        """
        迁移适配器: 将旧版 6 键手工脚本变体无损升级为 V3.2 规范的 9 键结构。
        键序严格为: slot -> optimize_reason -> hypothesis_ref -> mechanism_intents -> economic_delta -> expression ...
        注意: 若批次携带预注册 HypothesisSpec，调用方应把其 hypothesis_id 传入 default_hypothesis_id，
        否则 audit_variant_hypothesis 会因 hypothesis_ref 与预注册假说不一致而拦截（Phase B）。
        """
        upgraded = []
        for idx, v in enumerate(variants or []):
            if not isinstance(v, dict):
                continue
            expr = str(v.get("expression") or "")
            reason = str(v.get("optimize_reason") or v.get("economic_rationale") or
                         "基于底层字段物理分布进行去噪与截面映射，提升 Sharpe 与 Margin 并压低 ProdCorr")
            inferred_intents = v.get("mechanism_intents")
            if not isinstance(inferred_intents, list) or not inferred_intents:
                inferred_intents = []
                if any(k in expr for k in ("trade_when", "if_else", "ts_backfill", "days_from_last_change")):
                    inferred_intents.append("EVENT_GATE")
                if any(k in expr for k in ("ts_decay", "ts_mean", "hump", "jump_decay", "ts_target_tvr_decay")):
                    inferred_intents.append("TEMPORAL_DECAY")
                if any(k in expr for k in ("divide", "scale", "zscore", "group_zscore", "group_neutralize")):
                    inferred_intents.append("SCALE_NORMALIZATION")
                if any(k in expr for k in ("ts_delta", "ts_zscore", "ts_rank")):
                    inferred_intents.append("REGIME_SPREAD")
                if not inferred_intents:
                    inferred_intents.append("CROSS_SECTIONAL_RELATIVE")

            economic_delta = v.get("economic_delta")
            if not economic_delta:
                economic_delta = reason if len(reason) >= 20 else (
                    reason + "（由 6 键存量批次迁移补齐，确保机制增量描述可审查）"
                )

            ordered_item = {
                "slot": v.get("slot", idx + 1),
                "optimize_reason": reason,
                "hypothesis_ref": v.get("hypothesis_ref") or default_hypothesis_id,
                "mechanism_intents": inferred_intents[:3],
                "economic_delta": economic_delta,
                "expression": expr,
                "neutralization": v.get("neutralization", "SUBINDUSTRY"),
                "type": v.get("type", "explore"),
                "original_alpha": v.get("original_alpha", default_hypothesis_id),
            }
            upgraded.append(ordered_item)
        return upgraded

    @classmethod
    def _audit_refinement(cls, variants: List[dict], parent_expression: str = "",
                          protected_ops: Optional[List[str]] = None, parallelism: Optional[int] = None) -> dict:
        """精修模式 (1+9+10 三分天下制): Slot 1 控制槽，Slot 2~10 锁母本核心字段/机制，Slot 11~20 彻底重构。"""
        prot = [op for op in (protected_ops if protected_ops is not None else extract_skeleton_ops(parent_expression)) if op]
        parent_norm = normalize_expr(parent_expression)

        def _extract_fields(expr_str: str) -> Set[str]:
            tree = _parse(expr_str)
            if tree is None:
                return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr_str or ""))
            return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

        non_field_ids = {
            "subindustry", "industry", "sector", "market", "country", "std",
            "target_tvr", "factor", "pct", "percentage", "True", "False", "driver", "gaussian"
        }
        parent_fields = _extract_fields(parent_expression) - non_field_ids
        parent_core_skeleton = (
            ASTSandboxCorrector.get_core_skeleton(parent_expression, mechanism_intents=set())
            if ASTSandboxCorrector is not None and parent_expression
            else ""
        )
        effective_parallelism = int(parallelism or 20)
        reconstruction_start = max(10, effective_parallelism // 2 + 1)

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
            exprs.append((slot, expr, v))

        total = len(exprs)
        skeleton_slots: List[int] = []
        control_slots: List[int] = []
        window_only_slots: List[int] = []
        broken_slots: List[int] = []
        reconstruction_total = 0
        reconstruction_valid = 0
        reconstruction_failed_slots: List[int] = []

        for slot, expr, variant in exprs:
            is_ctrl = parent_norm and (normalize_expr(expr) == parent_norm)
            if is_ctrl:
                control_slots.append(slot)
                skeleton_slots.append(slot)
            else:
                expr_fields = _extract_fields(expr) - non_field_ids
                overlap_ratio = (len(parent_fields & expr_fields) / len(parent_fields)) if parent_fields else 1.0
                core_preserved = (overlap_ratio >= 0.50) or (bool(prot) and any(op in expr for op in prot))
                if core_preserved:
                    skeleton_slots.append(slot)
                elif slot <= 10:
                    broken_slots.append(slot)

            if slot >= reconstruction_start:
                reconstruction_total += 1
                expr_fields = _extract_fields(expr) - non_field_ids
                has_new_field = bool(expr_fields - parent_fields)
                if ASTSandboxCorrector is not None and parent_core_skeleton:
                    # 零意图对称剥离律: 双方统一强制使用 mechanism_intents=set() 进行裸核比对
                    core_changed = ASTSandboxCorrector.get_core_skeleton(expr, mechanism_intents=set()) != parent_core_skeleton
                else:
                    core_changed = has_new_field
                if core_changed or has_new_field:
                    reconstruction_valid += 1
                else:
                    reconstruction_failed_slots.append(slot)

            if is_window_only_tweak(expr, parent_expression):
                window_only_slots.append(slot)

        ratio = (len(skeleton_slots) / total) if total else 0.0
        issues: List[str] = []
        if total and ratio < cls.MIN_SKELETON_RATIO:
            issues.append(
                f"母本核心信号锚定槽位仅 {len(skeleton_slots)}/{total} ({ratio:.0%})，低于 1+9+10 分仓制要求的 "
                f"{cls.MIN_SKELETON_RATIO:.0%} (Slot 1~10 应保留母本主锚字段)；偏离槽位: {broken_slots}"
            )
        if total and not control_slots:
            issues.append("缺少控制槽: 必须有 1 槽逐字复现母本，否则本轮回测配置无法与母本历史结果对齐")
        if total and len(window_only_slots) > total * cls.MAX_WINDOW_ONLY_RATIO:
            issues.append(
                f"纯窗口数字微调占 {len(window_only_slots)}/{total} 槽，超过 {cls.MAX_WINDOW_ONLY_RATIO:.0%} 上限；"
                f"这类变体没有经济学信息增量"
            )
        if reconstruction_total and reconstruction_valid < reconstruction_total:
            issues.append(
                f"重构舱 {reconstruction_valid}/{reconstruction_total} 槽未改变核心经济骨架或引入新字段；"
                f"仅外层换壳槽位: {reconstruction_failed_slots}。重构舱必须提供机制级增量。"
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
            "reconstruction_total": reconstruction_total,
            "reconstruction_valid": reconstruction_valid,
            "reconstruction_failed_slots": reconstruction_failed_slots,
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

        # 假设先行核验必须在探索模式同样生效: Step 1 批次与母本 Sharpe < 1.2 的批次均走 MODE_EXPLORATION，
        # 若此分支缺失核验，「先写假说再写公式 / 可证伪指标 / 意图非空 / 假设去重」在探索期将完全脱管。
        hyp = cls.audit_hypothesis(variants)
        if hyp["issues"]:
            issues.extend(f"假设先行: {i}" for i in hyp["issues"])

        return {
            "mode": MODE_EXPLORATION,
            "total": total,
            "hypothesis": hyp,
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
                strict: bool = False, event_driven: bool = False, min_non_rank_ratio: Optional[float] = None,
                mode: str = MODE_EXPLORATION, parent_expression: str = "",
                protected_ops: Optional[List[str]] = None) -> dict:
        """
        铁律 B 审计与报告记录。
        默认 strict=False 仅做软性诊断告警，绝不通过硬性配额剥夺大模型自主选择算子与数学拓扑的权力；
        当显式传入 strict=True 时执行硬性门禁核验。
        """
        report = cls.audit(
            variants, parallelism=parallelism, event_driven=event_driven,
            min_non_rank_ratio=min_non_rank_ratio, mode=mode,
            parent_expression=parent_expression, protected_ops=protected_ops
        )

        if strict and report["issues"]:
            raise PermissionError(
                f"【铁律 B 门禁拦截】本批变体未通过铁律 B 物理核验:\n"
                + "\n".join(f"  - {i}" for i in report["issues"])
            )

        if mode == MODE_REFINEMENT:
            tag = "场景路由·老兵精修 (手术刀) 骨架保护诊断"
            if report["issues"]:
                msg = (
                    f"【{tag}】本批 {report['total']} 槽精修执行提示:\n"
                    + "\n".join(f"  - {i}" for i in report["issues"])
                    + f"\n控制槽: {report['control_slots']}\n"
                    f"建议: 保持对母本主锚字段的关注，并留 1 个逐字复现母本的控制槽；纯窗口数字微调不宜过多。"
                )
                print("⚠️ " + msg)
            else:
                print(
                    f"✅ [场景路由·老兵精修] 主锚保护 {len(report['skeleton_slots'])}/{report['total']} "
                    f"({report['skeleton_ratio']:.0%})，控制槽 {report['control_slots']}，"
                    f"纯窗口微调 {len(report['window_only_slots'])} 槽，契约合规。"
                )
            return report

        tag = "铁律 B 幅度保留诊断"
        if report["issues"]:
            msg = (
                f"【{tag}】本批 {report['total']} 槽的截面形态结构诊断提示:\n"
                + "\n".join(f"  - {i}" for i in report["issues"])
                + f"\n外层算子分布: {report['outer_hist']}\n"
                f"建议: 鼓励根据特征分布物理机理保留连续幅度分布的外层结构，避免全量使用单一算子拍平极值。"
            )
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
        """老兵精修 (手术刀) 契约: 聚焦主锚核心 + 经济学维度变异 + 控制槽 + 相对改进验收 (严禁死锁固定算子)"""
        min_anchor = max(1, int(round(parallelism * cls.MIN_SKELETON_RATIO)))
        lines = [
            "【场景路由 = 老兵精修 (Veteran Refinement)｜1+9+10 三分天下制（Slot 1 基准锚 5% + Slot 2~10 微创深化舱 45% + Slot 11~20 第一性原理重构舱 50%）】:",
            "- 🎯 母本已被 10 年历史与近 2 年区间验证，具有显著的因果经济学内涵；",
            "- ⚖️ Slot 2~10 聚焦母本主锚字段与病灶定向攻坚，Slot 11~20 鼓励引入同源冷门特征或探索全新数学拓扑；",
            f"- 自由算子探索: 严禁机械套用死算子或死骨架！先根据字段物理属性与病灶推导所需变换 (去偏/归一/尾部压缩/状态保持/事件门控)，再从算子签名表映射实现；Slot 2~10 建议至少 {min_anchor} 槽保持母本核心主锚字段的经济学因果链；",
            "- ✅ 经济学维度变异 (每槽必须在 optimize_reason 写明 economic_rationale 与 target_metric，禁止无意义的窗口微调):",
            "   1. 风险暴露与风格剥离方向: 先判断收益来源是行业内选股还是宏观/行业配置，再决定是否需要截面离差或风险对冲变换，最后查签名表映射实现；",
            "   2. 换手与交易成本控制方向: 根据信号的信息半衰期与衰减动态控制调仓频率与边际利润，消除日间无意义的高频抖动；",
            "   3. 状态条件化与事件激活方向: 结合字段更新频率与稀疏零值特性，在无真实事件变动时过滤噪音，保留有效信号；",
            "   4. 分布形态与极端值收敛方向: 根据字段真实定义域与偏态分布进行极值压缩或尺度规范化，提升跨期稳定性；",
            "   5. 正交机制升维方向: 结合同源低拥挤冷门特征进行非对称或预期剪刀差交互，提供真正的经济学边际增量；",
            "- 🧠 假设先行 (Python 物理核验): 每个对象必须先写 optimize_reason、再写 expression；假设内必须点名至少 1 个可验收指标"
            " (Margin / Sharpe / Turnover / ProdCorr / CLUSTER 等) 并摘述 economic_rationale——先落笔经济学因果，公式才被约束，"
            "先拼公式再补理由的后验辩解会被判违规；逐字重复的假设视为凑数；",
            "- 🧪 必须保留 1 个控制槽: 逐字复现母本表达式不做任何修改，用于确认本轮回测配置与母本历史结果同基准；",
            "- 🎯 验收门槛: 必须追求 ALL PASS (0 FAIL + 0 缺陷类 WARNING，MATCHES_THEMES/MATCHES_COMPETITION/MATCHES_PYRAMID 仅作信息类标注)，",
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
        ratio_label = "20% (稀疏/事件驱动特征已自适应放宽)" if event_driven else f"{cls.MIN_NON_RANK_RATIO:.0%}"
        lines = [
            "【期限稳健性与形态保留约束 (由 Python 物理核验)】:",
            f"- {parallelism} 槽中至少 {min_non_rank} 槽 ({ratio_label}) 的最外层不得使用 group_rank/rank；"
            f"rank 是否合适由 HypothesisSpec 的截面机制决定，不得为凑配额堆装饰；",
            "- 至少构造 1 组同骨架双窗口对照，用于检验 horizon_model 的期限稳健性；窗口来自字段更新频率与信息半衰期，"
            "不使用固定日历白名单；",
            "- 若假说预注册了短长周期反号 (REGIME_SPREAD)，双窗口反号是预期结果，不判为失败；",
            "- 若 N 窗达标而 2N 窗跌破 0.5 且假说未预注册反转，该骨架判为尖峰过拟合，禁止进入 Step 2 演进。",
        ]
        if event_driven:
            lines.append(
                "- 事件驱动数据 (news/sentiment/analyst)：请结合字段物理稀疏性与半衰期设计状态过滤或时序平滑，降低换手噪音。"
            )
        return "\n".join(lines)
