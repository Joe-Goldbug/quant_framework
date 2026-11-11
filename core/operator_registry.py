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
        "lower", "upper", "newval", "y", "x", "d", "a", "b", "c"
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
        if os.path.exists(target_path):
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                cls._OPERATORS = {op["name"]: op for op in results if "name" in op}
                cls._OPERATORS_BY_CAT = {}
                for op in results:
                    cat = op.get("category", "General")
                    cls._OPERATORS_BY_CAT.setdefault(cat, []).append(op)
                cls._ALL_NAMES = set(cls._OPERATORS.keys())
                cls._LOADED = True
            except Exception as e:
                print(f"⚠️ [OperatorRegistry] 加载 user_operators.json 失败: {e}")

        # Fallback to standard core operators if file missing or empty
        fallback_ops = {
            "add", "subtract", "multiply", "divide", "reverse", "neg", "abs", "sign",
            "power", "signed_power", "sqrt", "log", "s_log_1p", "exp", "max", "min",
            "rank", "group_rank", "quantile", "group_quantile", "scale", "group_scale",
            "zscore", "group_zscore", "ts_mean", "ts_sum", "ts_std_dev", "ts_min", "ts_max",
            "ts_rank", "ts_delta", "ts_delay", "ts_corr", "ts_decay_linear", "ts_decay_exp_window",
            "trade_when", "if_else", "winsorize", "hump", "group_neutralize", "jump_decay",
            "ts_regression", "ts_arg_max", "ts_arg_min", "ts_skewness", "ts_kurtosis",
            "bucket", "right_tail", "left_tail", "densify", "pasteurize",
            "vec_avg", "vec_sum", "vec_max", "vec_min", "vec_stddev", "vec_range", "vec_count"
        }
        cls._ALL_NAMES = set(cls._OPERATORS.keys()) | fallback_ops
        for name in fallback_ops:
            if name not in cls._OPERATORS:
                cls._OPERATORS[name] = {"name": name, "category": "General", "definition": f"{name}(...)"}

        cls._KEEP_TOKENS = (
            cls._ALL_NAMES |
            cls.DEFAULT_GROUPS |
            cls.DEFAULT_SPECIAL_TOKENS
        )

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
