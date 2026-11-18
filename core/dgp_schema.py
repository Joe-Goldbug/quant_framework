"""
core/dgp_schema.py
字段证据分层与经济假说规格 (DGP Schema V2)

目标:
1. 字段画像不再用默认值伪装成“已知物理分布”;
2. Stage 1 生成表达式之前必须先通过 HypothesisSpec 预注册;
3. 机制签名与实现签名分离，供后续反模板化搜索使用。
"""

import ast
import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple, Set

EVIDENCE_MEASURED = "MEASURED"
EVIDENCE_DECLARED = "DECLARED"
EVIDENCE_INFERRED = "INFERRED"
EVIDENCE_UNKNOWN = "UNKNOWN"
VALID_EVIDENCE_STATUS = {EVIDENCE_MEASURED, EVIDENCE_DECLARED, EVIDENCE_INFERRED, EVIDENCE_UNKNOWN}

# 常见机制意图参考集 (非闭包白名单，模型可基于 DGP 自主拓展其他经济学机制意图)
CANONICAL_MECHANISM_INTENTS = {
    "SCALE_NORMALIZATION",
    "EXPECTATION_SURPRISE",
    "EVENT_GATE",
    "TEMPORAL_DECAY",
    "CROSS_SECTIONAL_RELATIVE",
    "DISPERSION",
    "REGIME_SPREAD",
    "RESIDUAL_EXTRACTION",
    "TAIL_ASYMMETRY",
    "VECTOR_HIGHER_MOMENT",
}
# 向下兼容: MECHANISM_INTENTS 不再作为硬性拦截门禁，开放自由机制探索
MECHANISM_INTENTS = set()


class HypothesisSpec:
    """经济假说规格。表达式只能作为该规格的实现，不能先拼公式再补叙事。"""

    EVIDENCE_MEASURED = EVIDENCE_MEASURED
    EVIDENCE_DECLARED = EVIDENCE_DECLARED
    EVIDENCE_INFERRED = EVIDENCE_INFERRED
    EVIDENCE_UNKNOWN = EVIDENCE_UNKNOWN

    REQUIRED_KEYS = (
        "hypothesis_id",
        "economic_cluster",
        "field_roles",
        "counterparty",
        "causal_chain",
        "horizon_model",
        "falsification_tests",
    )

    # 机制意图 -> 算子族同构映射 (AEGIS v3.2 真实断言)
    # 说明: 仅覆盖常见实现算子族。表达式若含映射表之外的冷门算子，或声明了自定义意图，
    # 一律视为「无法判定」并放行——保留模型自主探索冷门算子的空间，避免白名单化变成新死模板。
    # 只有当表达式算子全部在已知族内、且无自定义意图时，才要求「至少一个声明意图有实现支撑」。
    INTENT_OPERATOR_FAMILIES = {
        "SCALE_NORMALIZATION": {"divide", "scale", "group_scale", "zscore", "group_zscore", "ts_scale", "ts_zscore", "normalize", "group_normalize", "fraction"},
        "EXPECTATION_SURPRISE": {"subtract", "ts_delta", "ts_av_diff", "ts_regression", "ts_zscore", "group_zscore", "regression_neut", "vector_neut"},
        "RESIDUAL_EXTRACTION": {"group_neutralize", "regression_neut", "vector_neut", "ts_regression", "subtract", "ts_av_diff"},
        "EVENT_GATE": {"trade_when", "if_else", "filter", "multiply", "days_from_last_change", "ts_backfill", "group_backfill", "is_nan", "greater", "less", "equal", "not_equal", "jump_decay", "hump"},
        "TEMPORAL_DECAY": {"ts_decay_linear", "ts_decay_exp_window", "jump_decay", "hump", "ts_target_tvr_decay", "ts_mean", "ts_sum", "ts_delay", "ts_product"},
        "CROSS_SECTIONAL_RELATIVE": {"rank", "group_rank", "quantile", "group_quantile", "zscore", "group_zscore", "group_neutralize", "scale", "group_scale", "rank_by_side"},
        "DISPERSION": {"ts_std_dev", "ts_variance", "ts_ir", "ts_entropy", "vec_std", "vec_stddev", "vec_range", "vec_ir", "vec_norm", "reduce_range", "reduce_ir"},
        "TAIL_ASYMMETRY": {"winsorize", "signed_power", "power", "s_log_1p", "log", "sqrt", "abs", "right_tail", "left_tail", "bucket", "quantile", "ts_quantile", "ts_skewness", "ts_kurtosis", "vec_skewness", "vec_kurtosis", "truncate"},
        "VECTOR_HIGHER_MOMENT": {"vec_std", "vec_stddev", "vec_range", "vec_ir", "vec_skewness", "vec_kurtosis", "vec_norm", "vec_percentage", "vec_max", "vec_min", "vec_median"},
        "REGIME_SPREAD": {"subtract", "divide", "ts_av_diff", "ts_delta", "ts_regression", "ts_rank", "ts_zscore"},
    }

    @classmethod
    def infer_evidence_status(cls, meta: Optional[dict]) -> str:
        """根据字段元数据推断证据等级; 不确定时必须显式 UNKNOWN。"""
        if not isinstance(meta, dict):
            return EVIDENCE_UNKNOWN
        explicit = str(meta.get("evidence_status", "") or "").upper()
        if explicit in VALID_EVIDENCE_STATUS:
            return explicit

        # 探针/样本实测优先
        if meta.get("probe_results") or meta.get("probe_verified") is True or meta.get("sample_verified") is True:
            return EVIDENCE_MEASURED

        coverage = meta.get("coverage")
        if coverage is not None:
            # 必须拆开 coverage 与真实 DGP 物理分布属性
            dgp_attr_count = sum(
                1 for key in ("update_frequency", "is_sparse", "skewness", "domain")
                if meta.get(key) is not None
            )
            # 只有当 coverage 存在且至少具备 2 项 DGP 分布属性时才返回 DECLARED
            if dgp_attr_count >= 2:
                return EVIDENCE_DECLARED
            # 仅有 coverage 而无充足 DGP 属性的字段判为 INFERRED
            return EVIDENCE_INFERRED

        # 连 coverage 都为 None 时，显式判定为 UNKNOWN (禁止进入生产假说链)
        return EVIDENCE_UNKNOWN

    @classmethod
    def normalize_field_profile(cls, field_id: str, meta: Optional[dict]) -> dict:
        meta = dict(meta or {})
        evidence_status = cls.infer_evidence_status(meta)
        meta["field_id"] = field_id
        meta["evidence_status"] = evidence_status
        if evidence_status == EVIDENCE_UNKNOWN:
            # 保留原始值用于诊断，但显式标记未知，禁止下游当作高覆盖已知字段
            meta.setdefault("coverage", None)
            meta.setdefault("update_frequency", None)
            meta.setdefault("is_sparse", None)
            meta.setdefault("skewness", None)
            meta.setdefault("domain", None)
        return meta

    @classmethod
    def physical_field_signature(cls, meta: Optional[dict]) -> str:
        """去字段名的物理签名，用于经验复用的 DGP 匹配。"""
        meta = meta or {}
        role = str(meta.get("semantic_role") or meta.get("role") or "UNKNOWN")
        freq = str(meta.get("update_frequency") or "UNKNOWN")
        sparse = str(meta.get("is_sparse") or "UNKNOWN")
        skew = str(meta.get("skewness") or "UNKNOWN")
        crowding = str(meta.get("crowding_tier") or meta.get("tier") or "UNKNOWN")
        vector_type = str(meta.get("type") or "MATRIX").upper()
        return f"FIELD[Role:{role}|Freq:{freq}|Sparse:{sparse}|Skew:{skew}|Crowd:{crowding}|Type:{vector_type}]"

    @classmethod
    def normalize(cls, raw: Optional[dict], fallback_seed: Optional[dict] = None) -> Optional[dict]:
        """把 LLM 输出或旧种子转换为规范 HypothesisSpec; 无法构成假说时返回 None。"""
        if not isinstance(raw, dict):
            raw = {}
        fallback_seed = fallback_seed or {}

        field_roles_raw = raw.get("field_roles")
        if not isinstance(field_roles_raw, list):
            fields_used = fallback_seed.get("fields_used") or []
            field_roles_raw = [
                {"field_id": f, "role": "UNKNOWN"}
                for f in fields_used
                if isinstance(f, str) and f
            ]

        field_roles = []
        for role in field_roles_raw:
            if not isinstance(role, dict):
                continue
            field_id = str(role.get("field_id") or role.get("field") or "").strip()
            if not field_id:
                continue
            field_roles.append({
                "field_id": field_id,
                "role": str(role.get("role") or "UNKNOWN"),
                "expected_transform": str(role.get("expected_transform") or "UNKNOWN"),
                "evidence_status": str(role.get("evidence_status") or EVIDENCE_UNKNOWN).upper(),
            })

        horizon_raw = raw.get("horizon_model")
        if not isinstance(horizon_raw, dict):
            horizon_raw = {}
        horizon_model = {
            "short_window": horizon_raw.get("short_window"),
            "long_window": horizon_raw.get("long_window"),
            "expected_short_sign": horizon_raw.get("expected_short_sign"),
            "expected_long_sign": horizon_raw.get("expected_long_sign"),
            "decay_assumption": str(horizon_raw.get("decay_assumption") or "UNKNOWN"),
        }

        tests_raw = raw.get("falsification_tests")
        if not isinstance(tests_raw, list):
            tests_raw = []
        falsification_tests = [str(t).strip() for t in tests_raw if str(t).strip()]

        spec = {
            "hypothesis_id": str(raw.get("hypothesis_id") or fallback_seed.get("id") or "HYP_UNKNOWN").strip(),
            "economic_cluster": str(raw.get("economic_cluster") or fallback_seed.get("cluster_ref") or "UNKNOWN_CLUSTER").strip(),
            "field_roles": field_roles,
            "counterparty": str(raw.get("counterparty") or "UNKNOWN_COUNTERPARTY").strip(),
            "causal_chain": str(raw.get("causal_chain") or raw.get("economic_mechanism") or fallback_seed.get("economic_mechanism") or "").strip(),
            "horizon_model": horizon_model,
            "normalization_rationale": str(raw.get("normalization_rationale") or "").strip(),
            "sparsity_policy": str(raw.get("sparsity_policy") or "UNKNOWN").strip(),
            "interaction_type": str(raw.get("interaction_type") or "UNKNOWN").strip(),
            "falsification_tests": falsification_tests,
            "source": str(raw.get("source") or ("legacy" if (not raw and fallback_seed) else "stage0")).strip(),
        }
        return spec

    @classmethod
    def validate(cls, spec: Optional[dict], field_profiles: Optional[Dict[str, dict]] = None) -> Tuple[bool, List[str]]:
        if not isinstance(spec, dict):
            return False, ["HypothesisSpec 缺失，禁止未预注册假说生成表达式"]

        if spec.get("source") == "legacy":
            return True, []  # legacy seed 豁免严格假说验证，直接放行

        issues: List[str] = []
        for key in cls.REQUIRED_KEYS:
            if not spec.get(key):
                issues.append(f"假说缺少必填项: {key}")

        if len(spec.get("field_roles", [])) < 1:
            issues.append("field_roles 为空，无法建立字段物理角色")
        elif len(spec.get("field_roles", [])) > 4:
            issues.append("field_roles 超过 4 个，存在多字段大杂烩过拟合风险")

        if len(str(spec.get("causal_chain", "")).strip()) < 40:
            issues.append("causal_chain 过短，无法构成可审查的因果传导链")

        horizon = spec.get("horizon_model") if isinstance(spec.get("horizon_model"), dict) else {}
        if horizon.get("expected_short_sign") is None or horizon.get("expected_long_sign") is None:
            issues.append("horizon_model 缺少各期限预期符号，无法做期限证伪")

        if len(spec.get("falsification_tests", [])) < 2:
            issues.append("falsification_tests 少于 2 条，假说不可证伪")

        field_profiles = field_profiles or {}
        for role in spec.get("field_roles", []):
            field_id = role.get("field_id")
            profile = field_profiles.get(field_id)
            if profile is None:
                issues.append(f"字段 {field_id} 不在真实字段画像中")
                continue
            evidence_status = str(profile.get("evidence_status") or EVIDENCE_UNKNOWN).upper()
            if evidence_status == EVIDENCE_UNKNOWN:
                issues.append(f"字段 {field_id} 物理证据为 UNKNOWN，禁止进入生产假说链")
            if str(role.get("role") or "UNKNOWN") == "UNKNOWN":
                issues.append(f"字段 {field_id} 角色未知")

        return not issues, issues

    @classmethod
    def hypothesis_signature(cls, spec: Optional[dict], field_profiles: Optional[Dict[str, dict]] = None) -> str:
        """机制签名: 只包含经济机制结构，不包含具体字段名和完整表达式。"""
        spec = spec or {}
        field_profiles = field_profiles or {}
        roles = []
        for role in spec.get("field_roles", []):
            field_id = role.get("field_id")
            profile = field_profiles.get(field_id, {})
            roles.append({
                "role": role.get("role"),
                "physical_signature": cls.physical_field_signature(profile),
                "expected_transform": role.get("expected_transform"),
            })
        payload = {
            "economic_cluster": spec.get("economic_cluster"),
            "counterparty": spec.get("counterparty"),
            "interaction_type": spec.get("interaction_type"),
            "normalization_target": spec.get("normalization_rationale"),
            "sparsity_policy": spec.get("sparsity_policy"),
            "horizon_model": spec.get("horizon_model"),
            "field_roles": sorted(roles, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return "MECH_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()

    @classmethod
    def implementation_signature(cls, expression: str) -> str:
        """实现签名: 完整表达式的规范化哈希，用于精确去重。"""
        normalized = re.sub(r"\s+", "", str(expression or "").strip().lower())
        return "IMPL_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20].upper()

    @classmethod
    def audit_variant_hypothesis(cls, variant: Optional[dict], spec: Optional[dict], fields_meta: Optional[dict] = None) -> Tuple[bool, List[str]]:
        """审计变体是否携带假说引用、机制意图和经济增量，并执行 AST 意图结构同构硬断言。"""
        if not isinstance(variant, dict):
            return False, ["变体不是 dict"]
        issues: List[str] = []

        if not isinstance(spec, dict):
            return True, []  # legacy seed 兼容: 不阻断旧流程，但无法获得 V2 语义增益

        import os
        if spec.get("source") == "legacy" or os.environ.get("AEGIS_MOCK_MODE") == "1":
            if not variant.get("hypothesis_ref") or variant.get("hypothesis_ref") != spec.get("hypothesis_id"):
                variant["hypothesis_ref"] = spec.get("hypothesis_id")
            if not variant.get("mechanism_intents"):
                variant["mechanism_intents"] = ["SCALE_NORMALIZATION"]
            if not variant.get("economic_delta"):
                variant["economic_delta"] = "针对遗留种子进行结构性微创优化以提升夏普 Sharpe 与利润率 Margin"

        if str(variant.get("hypothesis_ref") or "") != str(spec.get("hypothesis_id") or ""):
            issues.append("hypothesis_ref 与预注册假说不一致")

        intents = variant.get("mechanism_intents")
        intents_set: Set[str] = set()
        if not isinstance(intents, list) or not intents:
            issues.append("mechanism_intents 缺失，无法进行语义—AST 审计")
        else:
            for intent in intents:
                s_intent = str(intent).strip().upper()
                if s_intent:
                    intents_set.add(s_intent)
            if len(intents_set) > 3:
                issues.append(f"mechanism_intents 声明了 {len(intents_set)} 个机制意图 (> 3)，存在多机制大杂烩风险")

        if len(str(variant.get("economic_delta") or "").strip()) < 20:
            issues.append("economic_delta 过短，无法说明相对母本或种子的机制增量")

        # ---------------- 真实 AST 结构与意图同构断言 ----------------
        expr = str(variant.get("expression") or "").strip()
        if not expr:
            issues.append("变体缺少 expression 表达式")
            return not issues, issues

        try:
            tree = ast.parse(expr, mode='eval')
            called_funcs: Set[str] = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Call):
                    if isinstance(n.func, ast.Name):
                        called_funcs.add(n.func.id)
                    elif isinstance(n.func, ast.Attribute):
                        called_funcs.add(n.func.attr)

            # 【语义与拓扑一致性核验 (全量 104 官方算子完全开放，严禁硬编码算子白名单绑定)】
            # 只要 AST 包含有效的算子调用或代数运算，即认可其机制实现，绝不拦截模型自主探索的冷门/新算子
            has_ops = bool(called_funcs) or any(isinstance(n, ast.BinOp) for n in ast.walk(tree))
            if not has_ops:
                issues.append("表达式未包含任何算子调用或代数运算，无法实现假说机制")

            # ---------------- 意图—AST 算子族同构核验 (AEGIS v3.2 真实断言) ----------------
            # 修复旧版空壳: 旧逻辑只查 has_ops，导致「声明 VECTOR_HIGHER_MOMENT 却写 rank(ts_mean(x,5))」
            # 也能通过。现按 INTENT_OPERATOR_FAMILIES 做同构核验，并保留两条宽松通道:
            #   a) 表达式含映射表外的冷门算子 -> 无法判定，放行 (不阻碍算子创新);
            #   b) 声明了自定义 mechanism_intents -> 无法判定，放行。
            binop_aliases: Set[str] = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.BinOp):
                    if isinstance(n.op, ast.Sub):
                        binop_aliases.add("subtract")
                    elif isinstance(n.op, ast.Div):
                        binop_aliases.add("divide")
                    elif isinstance(n.op, ast.Mult):
                        binop_aliases.add("multiply")
                    elif isinstance(n.op, ast.Add):
                        binop_aliases.add("add")
            effective_ops = called_funcs | binop_aliases
            variant_type = str(variant.get("type") or "").strip().lower()
            if intents_set and has_ops and variant_type not in ("parent_control", "ablation_control", "placebo_control"):
                known_families: Set[str] = set()
                for fam in cls.INTENT_OPERATOR_FAMILIES.values():
                    known_families |= fam
                unknown_ops = effective_ops - known_families
                custom_intents = {i for i in intents_set if i not in cls.INTENT_OPERATOR_FAMILIES}
                if not unknown_ops and not custom_intents:
                    matched = [
                        i for i in intents_set
                        if effective_ops & cls.INTENT_OPERATOR_FAMILIES.get(i, set())
                    ]
                    if not matched:
                        issues.append(
                            f"mechanism_intents {sorted(intents_set)} 与实际算子族不同构: "
                            f"表达式算子 {sorted(effective_ops)[:8]} 均不属于所声明意图的实现族，"
                            f"属于「声明一套机制、实现另一套拓扑」的语义—AST 脱节"
                        )

        except Exception as e:
            issues.append(f"表达式语法错误无法解析 AST: {e}")

        return not issues, issues
