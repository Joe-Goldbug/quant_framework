"""
core/operator_registry.py
WorldQuant Brain 算子单一事实源 (Single Source of Truth, SSOT)
从 knowledge_base/operators/user_operators.json 动态加载用户账号全量授权算子，
彻底杜绝代码中散落的硬编码白名单与虚假字段误杀。
"""
import os
import json
from typing import Dict, List, Set, Optional


class OperatorRegistry:
    _LOADED = False
    _OPERATORS: Dict[str, dict] = {}
    _OPERATORS_BY_CAT: Dict[str, List[dict]] = {}
    _ALL_NAMES: Set[str] = set()
    _KEEP_TOKENS: Set[str] = set()

    DEFAULT_GROUPS = {"market", "sector", "industry", "subindustry", "country", "region"}
    DEFAULT_SPECIAL_TOKENS = {
        "NUM", "std", "factor", "sensitivity", "force", "filter", "lag", "rettype",
        "lower", "upper", "newval", "y", "x", "d", "a", "b", "c", "target_tvr", "driver"
    }

    @classmethod
    def get_json_path(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "knowledge_base", "operators", "user_operators.json")

    @classmethod
    def load(cls, json_path: Optional[str] = None) -> None:
        if cls._LOADED and not json_path:
            return
        target_path = json_path or cls.get_json_path()
        cls._OPERATORS = {}
        cls._OPERATORS_BY_CAT = {}
        if os.path.exists(target_path):
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                cls._OPERATORS = {op["name"]: op for op in results if isinstance(op, dict) and "name" in op}
                for op in results:
                    if not isinstance(op, dict) or "name" not in op:
                        continue
                    cat = op.get("category", "General")
                    cls._OPERATORS_BY_CAT.setdefault(cat, []).append(op)
                cls._ALL_NAMES = set(cls._OPERATORS.keys())
                if cls._OPERATORS:
                    cls._LOADED = True
            except Exception as e:
                print(f"⚠️ [OperatorRegistry] 加载 user_operators.json 失败: {e}")

        # Only fall back to core authorized subset when JSON is missing or empty
        if not cls._OPERATORS:
            fallback_ops = {
                "add", "subtract", "multiply", "divide", "reverse", "abs", "sign",
                "power", "signed_power", "sqrt", "log", "s_log_1p", "max", "min",
                "rank", "group_rank", "quantile", "scale", "group_scale",
                "zscore", "group_zscore", "ts_mean", "ts_sum", "ts_std_dev",
                "ts_rank", "ts_delta", "ts_delay", "ts_corr", "ts_decay_linear", "ts_decay_exp_window",
                "trade_when", "if_else", "winsorize", "hump", "group_neutralize",
                "ts_regression", "ts_arg_max", "ts_arg_min",
                "ts_target_tvr_decay", "ts_quantile",
                "bucket", "right_tail", "left_tail", "densify",
                "vec_avg", "vec_sum", "vec_stddev"
            }
            for name in sorted(fallback_ops):
                op = {"name": name, "category": "General", "definition": f"{name}(...)"}
                cls._OPERATORS[name] = op
                cls._OPERATORS_BY_CAT.setdefault("General", []).append(op)
            cls._ALL_NAMES = set(cls._OPERATORS.keys())
            cls._LOADED = True

        cls._KEEP_TOKENS = (
            cls._ALL_NAMES |
            cls.DEFAULT_GROUPS |
            cls.DEFAULT_SPECIAL_TOKENS
        )

    @classmethod
    def lookup_operators(cls, query: str = "", category: str = "") -> List[dict]:
        """按名称/描述/分类按需检索授权算子签名，避免全量注入上下文"""
        if not cls._LOADED:
            cls.load()
        q = (query or "").strip().lower()
        cat_q = (category or "").strip().lower()
        matches: List[dict] = []
        for op in cls._OPERATORS.values():
            op_cat = str(op.get("category", ""))
            if cat_q and cat_q not in op_cat.lower():
                continue
            name = str(op.get("name", ""))
            definition = str(op.get("definition", ""))
            desc = str(op.get("description", ""))
            if q and not (q in name.lower() or q in definition.lower() or q in desc.lower() or q in op_cat.lower()):
                continue
            matches.append({
                "name": name,
                "category": op_cat,
                "scope": op.get("scope", []),
                "definition": definition,
                "description": desc,
            })
        matches.sort(key=lambda item: (0 if q and item["name"].lower().startswith(q) else 1, item["name"]))
        return matches

    @classmethod
    def format_compact_index_markdown(cls) -> str:
        """极简算子分类索引 (< 1KB): 通过 lookup_operators 按需查询精确签名"""
        if not cls._LOADED:
            cls.load()
        cat_lines = []
        for cat_key in sorted(cls._OPERATORS_BY_CAT.keys()):
            ops = cls._OPERATORS_BY_CAT[cat_key]
            sample = ", ".join(op["name"] for op in sorted(ops, key=lambda x: x["name"])[:4])
            cat_lines.append(f"- {cat_key} ({len(ops)}): {sample}...")
        lines = [
            f"### Authorized Operators ({len(cls._ALL_NAMES)} SSOT)",
            *cat_lines,
            "Query exact signatures via `lookup_operators(query, category)`.",
            "Banned aliases: exp/jump_decay/ts_max/ts_min/ts_skewness/ts_kurtosis/pasteurize/group_quantile/neg."
        ]
        return "\n".join(lines)

    @classmethod
    def get_all_operator_names(cls) -> Set[str]:
        if not cls._LOADED:
            cls.load()
        return set(cls._ALL_NAMES)

    @classmethod
    def is_valid_operator(cls, name: str) -> bool:
        if not cls._LOADED:
            cls.load()
        return name in cls._ALL_NAMES

    @classmethod
    def get_operator_meta(cls, name: str) -> Optional[dict]:
        if not cls._LOADED:
            cls.load()
        return cls._OPERATORS.get(name)

    @classmethod
    def get_keep_tokens(cls) -> Set[str]:
        if not cls._LOADED:
            cls.load()
        return set(cls._KEEP_TOKENS)

    @classmethod
    def format_pyramid_level1_markdown(cls) -> str:
        """格式化第 1 级金字塔语法基石 (按金融机制功能聚类)"""
        if not cls._LOADED:
            cls.load()
        lines = [
            "### 【第 1 级金字塔语法基石: WorldQuant Brain 官方授权可用算子库】",
            f"当前账号实际可用算子总数: {len(cls._ALL_NAMES)} 个。Agent 可根据因果机制自由组合调用，平台精确签名如下：\n"
        ]
        cat_order = [
            ("Time Series", "时序因果、平滑衰减、动态突变与高阶回归 (Time Series)"),
            ("Cross Sectional", "截面相对强弱、极值处理与分布缩放 (Cross Sectional)"),
            ("Group", "行业/板块截面中性化、聚类去噪与组内排序 (Group)"),
            ("Transformational", "尾部暴露、状态记忆过滤与非线性分桶 (Transformational)"),
            ("Arithmetic", "纯代数运算、非线性尺度变换与离散度刻画 (Arithmetic)"),
            ("Reduce", "多周期降维统计与矩阵聚合 (Reduce)"),
            ("Vector", "Vector 向量数据集标量化包裹 (Vector)"),
            ("Logical", "条件门控与逻辑比较 (Logical)")
        ]
        for cat_key, cat_title in cat_order:
            ops = cls._OPERATORS_BY_CAT.get(cat_key, [])
            if not ops:
                continue
            lines.append(f"#### {cat_title}:")
            defs = []
            for op in sorted(ops, key=lambda x: x["name"]):
                name = op["name"]
                definition = op.get("definition", f"{name}(...)")
                desc = op.get("description", "")
                defs.append(f"- `{definition}`: {desc}")
            lines.extend(defs)
            lines.append("")
        return "\n".join(lines)
