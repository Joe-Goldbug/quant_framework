"""
dimension_rules.py
量纲守恒与 AST 符号推导编译器 (AEGIS v3.1 Hardness 终极加固版)
彻底解决：
1. 跨数据集 PV 污染硬封杀：在非量价分类 (news, sentiment, analyst 等) 中物理拦截外部量价字段 (close, open, high, low, returns, volume, cap 等)
2. 递归子树字段与定义域推导：
   - 深入 ast.Call 内部递归提取嵌套字段与正负号定义域
   - 即使包裹在 winsorize / ts_decay_linear 内，同样精准拦截双 [-1, 1] 裸乘与稀疏减 0.5
3. 真实字段元数据自动对齐：
   - 传入 list 时不再盲目覆盖为 unbounded，优先读取 knowledge_base/fields/ 或启发式纠偏
   - 明确 news 情绪分数为 [0, 1] 稀疏，prob_rank_bin1_* 为无界回归实数
4. 字段总数硬上限：严禁超过 3 个数据集字段 (<= 3)，杜绝多特征厨房大杂烩过拟合
5. VECTOR 类型安全核查：VECTOR 类型字段必须被 vec_* 算子包裹，严禁裸露直接参与运算
6. 纯净算子数量硬门禁：硬锁算子数 <= 11（Batch61 最小手术授权 8→11；同步放行 hump/signed_power）
"""

import ast
import json
import os
import re
import sys
from typing import Dict, List, Set, Union, Optional

try:
    from quant_framework.core.operator_registry import OperatorRegistry
except ModuleNotFoundError:
    try:
        from core.operator_registry import OperatorRegistry
    except ModuleNotFoundError:
        from operator_registry import OperatorRegistry

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class ASTSymbolicVisitor(ast.NodeVisitor):
    # 动态从 Single Source of Truth (user_operators.json) 挂载全量 104 个官方授权算子
    KNOWN_OPERATORS = OperatorRegistry.get_all_operator_names()
    TIME_SERIES_OPS = {
        "ts_delta", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
        "ts_decay_linear", "ts_decay_exp_window", "ts_delay", "ts_corr", "ts_min",
        "ts_max", "ts_arg_max", "ts_arg_min", "ts_av_diff", "ts_scale", "ts_backfill",
        "ts_returns", "ts_ir", "ts_skewness", "ts_kurtosis", "ts_quantile",
        "ts_regression", "ts_count_nans", "ts_product", "jump_decay",
    }
    CALENDAR_PRESETS = {1, 2, 3, 4, 5, 10, 20, 21, 22, 60, 63, 120, 126, 250, 252}

    # 非负域集合: 供乘法门控/除法归一/量纲一致性判断统一引用。
    # "(0, 1]" 是 exp() 对负半轴对数域 (-inf, 0] 的还原结果 (AEGIS v3.2)，
    # 若此处遗漏会导致 multiply(exp(prob), signal) 被误报为「无界字段裸乘」。
    NON_NEG_DOMAINS = ("[0, 1]", "(0, 1]", "[0, inf)", "constant")
    NON_NEG_BOUNDED = ("[0, 1]", "(0, 1]")

    def __init__(self, fields_meta: Dict[str, dict], category: str, allow_pv_cross: bool, max_operators: int = 8, hypothesis: Optional[dict] = None):
        self.fields_meta = fields_meta
        self.category = category.lower()
        self.allow_pv_cross = allow_pv_cross
        self.max_operators = max_operators
        self.hypothesis = hypothesis or {}
        
        self.issues: List[str] = []
        self.operator_count = 0
        self.used_fields: Set[str] = set()
        self.used_pv_fields: Set[str] = set()
        self.group_vars: Set[str] = set()
        self.called_operators: Set[str] = set()

        self.allowed_windows = set(self.CALENDAR_PRESETS)
        if isinstance(self.hypothesis, dict):
            hm = self.hypothesis.get("horizon_model") or {}
            for kw in ("short_window", "long_window", "window"):
                w = hm.get(kw)
                if isinstance(w, int) and w > 0:
                    self.allowed_windows.add(w)
                    self.allowed_windows.add(2 * w)

        self.EXTERNAL_PV_FIELDS = {
            "close", "open", "high", "low", "vwap", "volume", "cap", "adv20",
            "returns", "sharesout", "split", "dividend"
        }
        # 1. V2: 加乘不再一刀切封杀；量纲与机制合法性交给 HypothesisSpec 语义审计
        self.FORBIDDEN_OPERATORS = set()

        # 2. V2: 窗口由字段更新频率与 horizon_model 决定；这里只做物理安全边界
        self.MAX_WINDOW_DAYS = 252
        self.MAX_ABS_FLOAT_PARAM = 10.0

        self.VALID_GROUPS = {"market", "sector", "industry", "subindustry", "country", "region"}
        self.VECTOR_WRAPPERS = {
            "vec_avg", "vec_sum", "vec_choose", "vec_count", "vec_max",
            "vec_min", "vec_std", "vec_stddev", "vec_range", "vec_norm",
            "vec_percentage", "vec_ir", "vec_skewness", "vec_kurtosis", "vec_median"
        }

    def _get_field_info(self, field_name: str) -> dict:
        """
        字段物理画像解析 (AEGIS v3.2 修正):
        1. 真实画像优先: 只要 domain 显式存在且不是 None/UNKNOWN/unbounded 占位，一律信任实测值，
           禁止任何字段名启发式覆盖（如 dl_riskfree_returns 的 42 个 "(-inf, 0]" 对数概率字段）;
        2. 仅在 domain 缺失或为 unbounded 占位时，才执行保守语义回退;
        3. 剔除旧版 "名字含 probability => [0, 1] 稀疏" 的模板化误判:
           prob_rank_bin / log-softmax 类字段真实值域是 (-inf, 0] 或 unbounded。
        """
        meta = self.fields_meta.get(field_name, {}) if isinstance(self.fields_meta, dict) else {}
        raw_dom = meta.get("domain")
        f_type = meta.get("type") or ("VECTOR" if ("vector" in field_name.lower() or field_name.lower().startswith("vec_")) else "MATRIX")
        is_sparse = bool(meta.get("is_sparse", meta.get("sparse_zero", False)))

        if raw_dom is not None and str(raw_dom).strip().lower() not in ("", "none", "unknown", "unbounded"):
            # 真实画像优先: 保留原始字符串（如 "[0, 1] integer ordinal"），由调用方按语义处理
            return {"type": f_type, "domain": str(raw_dom), "is_sparse": is_sparse}

        name_lower = field_name.lower()
        dom = str(raw_dom) if raw_dom else "unbounded"

        # 1. 对数概率 / 对数似然预测 (log-softmax 输出) 位于负半轴
        if "probability_label" in name_lower or "log_prob" in name_lower or "logprob" in name_lower:
            dom = "(-inf, 0]"
            is_sparse = False
        # 2. 深度学习收益回归预测 (prob_rank_bin1_* 等) 为无界实数 (优先于 probability 子串)
        elif "prob_rank_bin" in name_lower or "return_model" in name_lower or "growth" in name_lower:
            dom = "unbounded"
            is_sparse = False
        # 3. news / sentiment 真实画像：值域 [0, 1] 且稀疏
        elif any(w in name_lower for w in ["sentiment_score", "primary_sentiment", "sentiment_transfer", "relevance"]):
            dom = "[0, 1]"
            is_sparse = True
        # 4. 对称得分与相关系数
        elif any(w in name_lower for w in ["sent_score", "sentiment", "zscore", "ts_corr", "correlation", "divergence", "spread_score"]):
            dom = "[-1, 1]"
            is_sparse = False

        return {"type": f_type, "domain": dom, "is_sparse": is_sparse}

    def _is_dataset_field(self, var_name: str) -> bool:
        if (var_name in self.VALID_GROUPS or 
            var_name in self.EXTERNAL_PV_FIELDS or 
            var_name in self.KNOWN_OPERATORS or 
            var_name in self.VECTOR_WRAPPERS or 
            var_name in self.FORBIDDEN_OPERATORS or 
            OperatorRegistry.is_valid_operator(var_name) or
            var_name.startswith("group_") or 
            var_name.startswith("vec_") or 
            var_name.startswith("ts_")):
            return False
        return True

    def _extract_subtree_fields(self, node: ast.AST) -> List[str]:
        """递归提取子树中引用的所有数据集字段"""
        fields = []
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and self._is_dataset_field(n.id):
                fields.append(n.id)
        return fields

    def _check_unbounded_addition_subtraction(self, left_node: ast.AST, right_node: ast.AST, op_name: str):
        """
        跨角色无界加减拦截：
        当两支均为 unbounded 且涉及不同底层字段时，强制要求其 semantic_role 匹配；
        若角色不同且 hypothesis 未声明 EXPECTATION_SURPRISE 或 RESIDUAL_EXTRACTION，报错拦截。
        """
        f1_list = self._extract_subtree_fields(left_node)
        f2_list = self._extract_subtree_fields(right_node)
        s1 = set(f for f in f1_list if self._is_dataset_field(f))
        s2 = set(f for f in f2_list if self._is_dataset_field(f))
        if s1 and s2 and s1 != s2:
            def _get_role(fname: str) -> Optional[str]:
                if isinstance(self.hypothesis, dict):
                    roles_list = self.hypothesis.get("field_roles", [])
                    if isinstance(roles_list, list):
                        for fr in roles_list:
                            if isinstance(fr, dict) and fr.get("field_id") == fname:
                                return fr.get("role")
                meta = self.fields_meta.get(fname, {}) if isinstance(self.fields_meta, dict) else {}
                return meta.get("semantic_role")

            roles1 = set(_get_role(f) for f in s1) - {None}
            roles2 = set(_get_role(f) for f in s2) - {None}

            if roles1 and roles2 and roles1 != roles2:
                intents = set()
                if isinstance(self.hypothesis, dict):
                    intents = set(self.hypothesis.get("mechanism_intents") or [])
                    itype = self.hypothesis.get("interaction_type")
                    if itype:
                        intents.add(itype)
                allowed_intents = {"EXPECTATION_SURPRISE", "RESIDUAL_EXTRACTION"}
                if not (intents & allowed_intents):
                    self.issues.append(
                        f"【跨角色无界加减违规】{op_name} 左右两支涉及不同语义角色的无界字段 ({s1} 角色为 {roles1} vs {s2} 角色为 {roles2})！"
                        f"严禁跨角色无界特征直接加减。若存在预期差或残差逻辑，必须在假说 mechanism_intents 中声明 EXPECTATION_SURPRISE 或 RESIDUAL_EXTRACTION。"
                    )

    def _is_non_neg_gate(self, node: ast.AST) -> bool:
        """检查节点是否为合法非负门控/权重 (常数、[0, 1]/(0, 1] 或 [0, inf))"""
        if isinstance(node, (ast.Constant, ast.Num)):
            val = node.value if isinstance(node, ast.Constant) else node.n
            return isinstance(val, (int, float)) and not isinstance(val, bool) and val >= 0
        d_info = self._infer_node_domain(node)
        return d_info.get("domain") in self.NON_NEG_DOMAINS

    def _infer_node_domain(self, node: ast.AST) -> dict:
        """递归推导 AST 节点的数值定义域与稀疏性 (覆盖全量 104 官方算子)"""
        if isinstance(node, ast.Name):
            return self._get_field_info(node.id)
        elif isinstance(node, (ast.Constant, ast.Num)):
            val = node.value if isinstance(node, ast.Constant) else node.n
            return {"type": "CONSTANT", "domain": "constant", "value": val, "is_sparse": False}
        elif isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", "")
            # 1. 排名、分位数、分桶与概率算子归一化至 [0, 1]
            if func_name in (
                "group_rank", "rank", "quantile", "ts_quantile", "ts_rank", "group_quantile",
                "rank_by_side", "sigmoid", "bucket", "right_tail", "left_tail", "fraction",
                "vec_percentage", "reduce_percentage", "kth_element", "percentile", "ts_percentage",
                "less", "greater", "equal", "not_equal", "less_equal", "greater_equal", "and", "or", "not", "is_nan"
            ):
                return {"type": "MATRIX", "domain": "[0, 1]", "is_sparse": False}

            # 2a. exp 指数还原: 负半轴对数域 (-inf, 0] -> (0, 1] 概率空间 (AEGIS v3.2)
            elif func_name == "exp":
                if node.args:
                    inner_dom = self._infer_node_domain(node.args[0]).get("domain", "unbounded")
                    if inner_dom == "(-inf, 0]":
                        return {"type": "MATRIX", "domain": "(0, 1]", "is_sparse": False}
                return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}

            # 2b. 保号压缩算子: s_log_1p 定义域为全体实数 (sign(x)*log(1+|x|))，值域继承输入符号
            elif func_name == "s_log_1p":
                if node.args:
                    return self._infer_node_domain(node.args[0])
                return {"type": "MATRIX", "domain": "unbounded", "is_sparse": False}

            # 2. 绝对值与非负离散度算子归入非负 [0, inf)
            elif func_name in (
                "abs", "sqrt", "ts_std_dev", "ts_variance", "ts_count_nans",
                "days_from_last_change", "vec_std", "vec_stddev", "vec_range", "vec_count", "vec_norm",
                "reduce_range", "reduce_norm", "reduce_powersum", "jump_decay", "hump", "ts_entropy"
            ):
                return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}

            # 3. 标准化、相关性与去相关算子归入 [-1, 1]
            elif func_name in (
                "group_zscore", "ts_zscore", "zscore", "scale", "group_scale", "group_neutralize",
                "group_normalize", "normalize", "ts_corr", "ts_partial_corr", "ts_co_skewness",
                "ts_co_kurtosis", "ts_ir", "reduce_ir", "regression_neut", "vector_neut", "sign"
            ):
                return {"type": "MATRIX", "domain": "[-1, 1]", "is_sparse": False}

            # 4. 状态保持与条件门控算子继承目标信号定义域
            elif func_name in ("trade_when", "if_else", "filter"):
                if len(node.args) >= 2:
                    return self._infer_node_domain(node.args[1])

            # 5. 保留原定义域的时序平滑、极值与修剪算子
            elif func_name in (
                "winsorize", "truncate", "ts_decay_linear", "ts_decay_exp_window", "ts_mean", "ts_sum",
                "ts_min", "ts_max", "ts_median", "ts_delay", "ts_backfill", "group_mean", "group_median",
                "group_backfill", "reduce_avg", "reduce_sum", "reduce_min", "reduce_max"
            ):
                if node.args:
                    return self._infer_node_domain(node.args[0])

            # max 带有非负常数时为非负 [0, inf)
            elif func_name in ("max", "ts_max"):
                if len(node.args) >= 2:
                    for a in node.args:
                        if isinstance(a, (ast.Constant, ast.Num)):
                            val = a.value if isinstance(a, ast.Constant) else a.n
                            if isinstance(val, (int, float)) and val >= 0:
                                return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}
                if node.args:
                    return self._infer_node_domain(node.args[0])

            # 偶数次方运算转为非负 [0, inf)
            elif func_name == "power":
                if len(node.args) >= 2 and isinstance(node.args[1], (ast.Constant, ast.Num)):
                    val = node.args[1].value if isinstance(node.args[1], ast.Constant) else node.args[1].n
                    if isinstance(val, (int, float)) and val % 2 == 0:
                        return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}
                if node.args:
                    return self._infer_node_domain(node.args[0])

            # 除法: 正数常数分母保留分子定义域; 非负/非负相除仍为非负; 其余为无界
            elif func_name == "divide":
                if len(node.args) >= 2:
                    num = self._infer_node_domain(node.args[0])
                    den_node = node.args[1]
                    if isinstance(den_node, ast.Constant) and isinstance(den_node.value, (int, float)) \
                            and not isinstance(den_node.value, bool) and den_node.value > 0:
                        return num
                    d_num = num.get("domain", "unbounded")
                    d_den = self._infer_node_domain(den_node).get("domain", "unbounded")
                    if d_num in ("[0, inf)", "[0, 1]", "(0, 1]") and d_den in ("[0, inf)", "[0, 1]", "(0, 1]"):
                        return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}
                return {"type": "MATRIX", "domain": "unbounded", "is_sparse": False}

            # 差分与减法转为无界
            elif func_name in ("ts_delta", "subtract"):
                return {"type": "MATRIX", "domain": "unbounded", "is_sparse": False}

            # VECTOR 降维包裹算子继承底层字段 domain
            elif func_name in self.VECTOR_WRAPPERS or func_name.startswith("vec_"):
                if node.args:
                    inner_d = self._infer_node_domain(node.args[0])
                    return {"type": "MATRIX", "domain": inner_d.get("domain", "unbounded"), "is_sparse": inner_d.get("is_sparse", False)}

        return {"type": "MATRIX", "domain": "unbounded", "is_sparse": False}

    def visit_Call(self, node: ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name:
            self.called_operators.add(func_name)

        # 豁免 vec_* 降维标量化包裹算子 (因 Vector 数据集是 FastExpr 语法强制要求降维，不属于人为堆砌复杂度)
        if not func_name.startswith("vec_"):
            self.operator_count += 1

        # 0.1 数学定义域硬拦截: log/sqrt 对「保证为负」的子树会产生连片 NaN (AEGIS v3.2)
        # 只拦截推导域为 "(-inf, 0]" 的情形——这是唯一「保证为负」的域。
        # unbounded / [-1, 1] 只是「可能为负」: log(cap) / sqrt(ts_corr) 等教科书级合法压缩大量存在，
        # 若一并拦截会造成全数据集假阳性（fundamental23 的 1748 个 domain=None 字段全部回退 unbounded）。
        # 另: s_log_1p 定义域为全体实数 (sign(x)*log(1+|x|))，绝不可列入负数禁令。
        if func_name in ("log", "sqrt") and node.args:
            arg_dom = self._infer_node_domain(node.args[0]).get("domain", "unbounded")
            if arg_dom == "(-inf, 0]":
                sub_f = self._extract_subtree_fields(node.args[0])
                self.issues.append(
                    f"【数学定义域违规】算子 '{func_name}' 要求输入严格为正，但内层子树 (涉及字段 {sub_f}) "
                    f"推导值域为 '{arg_dom}' (对数概率/对数似然负半轴)，会产生连片 NaN！"
                    f"请先用 exp() 还原至 (0, 1] 概率空间，或改用保号的 s_log_1p。"
                )

        # 0. 时序算子窗口参数合法性检查
        if func_name in self.TIME_SERIES_OPS or func_name.startswith("ts_"):
            for arg in node.args[1:]:
                val = None
                if isinstance(arg, ast.Constant):
                    val = arg.value
                elif isinstance(arg, ast.Num):
                    val = arg.n
                elif isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    if isinstance(arg.operand, ast.Constant) and isinstance(arg.operand.value, (int, float)):
                        val = -arg.operand.value
                    elif isinstance(arg.operand, ast.Num):
                        val = -arg.operand.n
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if val <= 0:
                        self.issues.append(
                            f"【非法窗口拦截】时序算子 '{func_name}' 的窗口参数 {val} 必须为合法正整数 (> 0)！"
                        )
                    elif val > 252:
                        self.issues.append(
                            f"【超长窗口拦截】时序算子 '{func_name}' 的窗口参数 {val} 超过平台上限 252 日！"
                        )

        # 1. 乘法门控与伪因果检查
        if func_name in ("multiply", "mul") and len(node.args) >= 2:
            arg1, arg2 = node.args[0], node.args[1]
            info1 = self._infer_node_domain(arg1)
            info2 = self._infer_node_domain(arg2)
            d1 = info1.get("domain", "unbounded")
            d2 = info2.get("domain", "unbounded")
            
            if d1 == "[-1, 1]" and d2 == "[-1, 1]":
                f1 = self._extract_subtree_fields(arg1)
                f2 = self._extract_subtree_fields(arg2)
                self.issues.append(
                    f"【伪因果负负得正违规】检测到双 [-1, 1] 字段乘积 (左支: {f1}, 右支: {f2})！"
                    f"当两项同时处于极度负面时，乘积为正导致生成买入信号，存在严重伪因果！请对其中一项做正向平移使值域非负，或使用非负条件门控滤波。"
                )
            else:
                g1 = self._is_non_neg_gate(arg1)
                g2 = self._is_non_neg_gate(arg2)
                if not (g1 or g2):
                    self.issues.append(
                        "【无界字段裸乘拦截】检测到两个无界实数字段直接裸乘 multiply(f1, f2)，严禁双 unbounded 裸乘导致方差爆炸！乘法必须作为非负门控滤波使用。"
                    )

        # 1.1 加法与减法量纲一致性检查
        if func_name in ("add", "subtract") and len(node.args) >= 2:
            arg1, arg2 = node.args[0], node.args[1]
            is_const_1 = isinstance(arg1, (ast.Constant, ast.Num))
            is_const_2 = isinstance(arg2, (ast.Constant, ast.Num))
            if not (is_const_1 or is_const_2):
                d1 = self._infer_node_domain(arg1).get("domain", "unbounded")
                d2 = self._infer_node_domain(arg2).get("domain", "unbounded")
                if (d1 in self.NON_NEG_BOUNDED and d2 == "unbounded") or (d2 in self.NON_NEG_BOUNDED and d1 == "unbounded"):
                    self.issues.append(
                        f"【量纲不一致拦截】{func_name} 左右两支存在 [0, 1] 分位数与无界原始特征混算，严禁直接相加减！请先统一量纲或通过除法归一。"
                    )
                elif d1 == "unbounded" and d2 == "unbounded":
                    self._check_unbounded_addition_subtraction(arg1, arg2, func_name)

        # 2. 黑名单算子检查
        if func_name in self.FORBIDDEN_OPERATORS:
            self.issues.append(f"使用了黑名单/有害算子: '{func_name}' (该算子在历史实测中已被证伪或废弃)")

        # 3. 分组算子合法性检查
        if func_name.startswith("group_"):
            if node.args:
                last_arg = node.args[-1]
                grp_id = None
                if isinstance(last_arg, ast.Name):
                    grp_id = last_arg.id
                elif isinstance(last_arg, ast.Constant) and isinstance(last_arg.value, str):
                    grp_id = last_arg.value
                
                if grp_id:
                    self.group_vars.add(grp_id)
                    if grp_id not in self.VALID_GROUPS:
                        self.issues.append(f"Group 算子 '{func_name}' 使用了非法分组变量: '{grp_id}' (合法项: {self.VALID_GROUPS})")
                else:
                    self.issues.append(f"Group 算子 '{func_name}' 缺少合法分组变量 (合法项: {self.VALID_GROUPS})")

        # 4. add(rank, rank) 物理拦截
        if func_name == "add" and len(node.args) >= 2:
            arg1, arg2 = node.args[0], node.args[1]
            if isinstance(arg1, ast.Call) and isinstance(arg2, ast.Call):
                f1 = getattr(arg1.func, "id", "")
                f2 = getattr(arg2.func, "id", "")
                if f1 in ("rank", "group_rank") and f2 in ("rank", "group_rank"):
                    self.issues.append("检测到无量纲 rank 加总 add(rank, rank)，此结构属于纯数学拼凑过拟合，物理拦截！")

        # 5. 稀疏 [0, 1] 字段严禁 subtract(x, 0.5) 零值偏移拦截 (支持递归子树嵌套检查)
        if func_name == "subtract" and len(node.args) >= 2:
            arg1, arg2 = node.args[0], node.args[1]
            target_node = None
            const_val = None
            if isinstance(arg2, ast.Constant):
                target_node, const_val = arg1, arg2.value
            elif isinstance(arg1, ast.Constant):
                target_node, const_val = arg2, arg1.value

            if target_node is not None and (const_val == 0.5 or const_val == 0.50):
                d_info = self._infer_node_domain(target_node)
                if d_info.get("domain") == "[0, 1]" and d_info.get("is_sparse", True):
                    sub_fields = self._extract_subtree_fields(target_node)
                    self.issues.append(
                        f"【零值偏移违规】稀疏 [0, 1] 字段子树 '{sub_fields}' 严禁直接 subtract 0.5！"
                        f"这会导致海量无事件 0 值被偏移为伪空头信号，引发严重多空持仓失衡！请结合数据时序更新特性设计状态保持或时序平滑机制。"
                    )

        # 6. VECTOR 算子包裹性检查
        for arg in node.args:
            if isinstance(arg, ast.Name):
                f_info = self._get_field_info(arg.id)
                if f_info.get("type") == "VECTOR" and not (func_name in self.VECTOR_WRAPPERS or func_name.startswith("vec_")):
                    self.issues.append(
                        f"【VECTOR 类型安全违规】VECTOR 字段 '{arg.id}' 直接作为 '{func_name}' 的参数！"
                        f"FastExpr 规则要求 VECTOR 字段必须先套用 vec_* 算子 (如 vec_avg, vec_sum, vec_choose) 降维后方可参与运算。"
                    )

        # 仅递归访问参数和关键字参数，避免将 node.func (算子名称如 sigmoid, pasteurize 等) 误判定为数据集字段
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def visit_Name(self, node: ast.Name):
        var_name = node.id
        if var_name in self.VALID_GROUPS:
            self.group_vars.add(var_name)
        elif var_name in self.EXTERNAL_PV_FIELDS:
            self.used_pv_fields.add(var_name)
            if not self.allow_pv_cross and self.category not in ("pv", "price_volume", "price", "news_pv"):
                self.issues.append(
                    f"【严重违规: 跨数据集 PV 污染】在非量价分类 ('{self.category}') 中检测到外部量价字段: '{var_name}'！"
                    f"此举会导致与已有量价因子严重共线性 (ProdCorr > 0.70)，被系统物理封杀。请改用数据集内部字段自我归一！"
                )
        elif self._is_dataset_field(var_name):
            self.used_fields.add(var_name)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        """V2: 加乘执行量纲与门控校验。"""
        self.operator_count += 1
        if isinstance(node.op, ast.Mult):
            d1 = self._infer_node_domain(node.left).get("domain", "unbounded")
            d2 = self._infer_node_domain(node.right).get("domain", "unbounded")
            is_const_1 = isinstance(node.left, (ast.Constant, ast.Num))
            is_const_2 = isinstance(node.right, (ast.Constant, ast.Num))
            g1 = is_const_1 or (d1 in self.NON_NEG_DOMAINS)
            g2 = is_const_2 or (d2 in self.NON_NEG_DOMAINS)
            if not (g1 or g2):
                self.issues.append("【无界字段裸乘拦截】检测到两个无界实数字段直接裸乘 A * B，严禁双 unbounded 裸乘导致方差爆炸！乘法必须作为非负门控滤波使用。")
        elif isinstance(node.op, (ast.Add, ast.Sub)):
            is_const_1 = isinstance(node.left, (ast.Constant, ast.Num))
            is_const_2 = isinstance(node.right, (ast.Constant, ast.Num))
            if not (is_const_1 or is_const_2):
                d1 = self._infer_node_domain(node.left).get("domain", "unbounded")
                d2 = self._infer_node_domain(node.right).get("domain", "unbounded")
                if d1 != d2 and "constant" not in (d1, d2):
                    self.issues.append(f"【量纲不一致拦截】二元运算符左右两支推断定义域不一致 ({d1} vs {d2})，严禁将不同量纲/值域字段直接加减！")
                elif d1 == "unbounded" and d2 == "unbounded":
                    op_sym = "+" if isinstance(node.op, ast.Add) else "-"
                    self._check_unbounded_addition_subtraction(node.left, node.right, op_sym)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        """V2: 不再使用固定日历/小数白名单；只做物理安全边界检查。"""
        val = node.value
        if isinstance(val, bool) or val is None or isinstance(val, str):
            return
        if isinstance(val, int):
            if abs(val) > self.MAX_WINDOW_DAYS:
                self.issues.append(
                    f"【窗口物理边界拦截】整数参数 '{val}' 超过 {self.MAX_WINDOW_DAYS} 天安全上限。"
                )
        elif isinstance(val, float):
            if abs(val) > self.MAX_ABS_FLOAT_PARAM:
                self.issues.append(
                    f"【参数物理边界拦截】浮点参数 '{val}' 超过 {self.MAX_ABS_FLOAT_PARAM} 安全上限。"
                )
        self.generic_visit(node)

    def visit_Num(self, node: ast.Num):
        """兼容旧 Python AST 的数值节点; V2 只做边界检查。"""
        val = node.n
        if isinstance(val, int):
            if abs(val) > self.MAX_WINDOW_DAYS:
                self.issues.append(f"【窗口物理边界拦截】整数参数 '{val}' 超过 {self.MAX_WINDOW_DAYS} 天安全上限。")
        elif isinstance(val, float):
            if abs(val) > self.MAX_ABS_FLOAT_PARAM:
                self.issues.append(f"【参数物理边界拦截】浮点参数 '{val}' 超过 {self.MAX_ABS_FLOAT_PARAM} 安全上限。")
        self.generic_visit(node)


class DimensionAuditor:
    EXTERNAL_PV_FIELDS = {
        "close", "open", "high", "low", "vwap", "volume", "cap", "adv20", 
        "returns", "sharesout", "split", "dividend"
    }
    # 彻底解禁 group_neutralize，将其置空，完全放行合规截面中性化
    FORBIDDEN_OPERATORS = set()
    VALID_GROUPS = {"market", "sector", "industry", "subindustry", "country", "region"}
    # 兼容旧测试/调用方的自然日历先验集合；V2 不再用它做硬拦截
    VALID_CALENDAR_INTS = {0, 1, 2, 3, 4, 5, 10, 20, 21, 22, 60, 63, 120, 126, 250, 252}
    KB_FIELDS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "fields")
    _FIELD_CACHE: Dict[str, Optional[dict]] = {}

    @classmethod
    def load_field_meta_from_kb(cls, field_name: str) -> Optional[dict]:
        """从 knowledge_base/fields/ 中跨区域搜索真实字段画像"""
        if field_name in cls._FIELD_CACHE:
            return cls._FIELD_CACHE[field_name]
        if not os.path.exists(cls.KB_FIELDS_DIR):
            cls._FIELD_CACHE[field_name] = None
            return None
        for root, _, files in os.walk(cls.KB_FIELDS_DIR):
            for f in files:
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8') as jf:
                            data = json.load(jf)
                            fields = data.get("fields", {}) if isinstance(data, dict) else {}
                            if field_name in fields:
                                info = fields[field_name]
                                domain = info.get("domain", "unbounded")
                                is_sparse = info.get("is_sparse", info.get("sparse_zero", False))
                                f_type = info.get("type", "MATRIX")
                                res = {
                                    "type": f_type,
                                    "domain": domain,
                                    "is_sparse": is_sparse,
                                    "description": info.get("description", "")
                                }
                                cls._FIELD_CACHE[field_name] = res
                                return res
                    except Exception:
                        pass
        cls._FIELD_CACHE[field_name] = None
        return None

    @classmethod
    def audit_expression(
        cls,
        expr: str,
        known_fields: Union[List[str], Dict[str, dict]] = None,
        category: str = "other",
        allow_pv_cross: bool = False,
        max_operators: int = 8,
        step: int = 1,
        allowed_operators: Optional[Set[str]] = None,
        stage0_op_count: int = 0,
        required_fields: Optional[List[str]] = None,
        hypothesis: Optional[dict] = None
    ) -> dict:
        """
        基于 Python AST 抽象语法树的确定性符号与量纲推导编译器 (AEGIS v3.1 Hardness 终极加固版)
        """
        expr_clean = expr.strip()
        issues = []

        # 1. 物理字符长度上限 (FastExpr 限制 857 字符)
        if len(expr_clean) > 857:
            issues.append(f"表达式长度 {len(expr_clean)} 超过 857 字符物理安全上限")

        # 2. 字段字典格式统一与真实画像加载 (杜绝传入 list 时的属性抹除 Bug)
        fields_meta = {}
        if isinstance(known_fields, dict):
            fields_meta = dict(known_fields)
        elif isinstance(known_fields, list):
            for f in known_fields:
                kb_meta = cls.load_field_meta_from_kb(f)
                if kb_meta:
                    fields_meta[f] = kb_meta
                else:
                    # 启发式规则纠偏，绝不盲目硬编码为 unbounded
                    name_lower = f.lower()
                    f_type = "VECTOR" if ("vector" in name_lower or name_lower.startswith("vec_")) else "MATRIX"
                    if "prob_rank_bin" in name_lower or "return_model" in name_lower or "growth" in name_lower:
                        dom = "unbounded"
                        sp = False
                    elif "probability_label" in name_lower or "log_prob" in name_lower or "logprob" in name_lower:
                        dom = "(-inf, 0]"
                        sp = False
                    elif any(w in name_lower for w in ["sentiment_score", "primary_sentiment", "sentiment_transfer", "relevance"]):
                        dom = "[0, 1]"
                        sp = True
                    elif any(w in name_lower for w in ["sent_score", "sentiment", "zscore", "corr", "correlation"]):
                        dom = "[-1, 1]"
                        sp = False
                    else:
                        dom = "unbounded"
                        sp = False
                    fields_meta[f] = {"type": f_type, "domain": dom, "is_sparse": sp}

        # 3. 语法树解析
        try:
            tree = ast.parse(expr_clean, mode='eval')
        except SyntaxError as e:
            return {
                "is_valid": False,
                "issues": [f"FastExpr 语法错误无法解析: {str(e)}"],
                "operator_count": 0,
                "used_fields": []
            }

        # 4. AST 深度静态分析与量纲类型推导
        visitor = ASTSymbolicVisitor(
            fields_meta=fields_meta,
            category=category,
            allow_pv_cross=allow_pv_cross,
            max_operators=max_operators,
            hypothesis=hypothesis
        )
        visitor.visit(tree)

        # 5. 字段总数硬上限：严禁超过 4 个数据集字段 (优先于子树算子级告警，防止大杂烩特征被次要告警淹没)
        if len(visitor.used_fields) > 4:
            issues.append(
                f"【字段超限违规】检测到使用了 {len(visitor.used_fields)} 个数据集字段: {list(visitor.used_fields)} (> 4 个上限)！"
                f"单条 Alpha 最多只允许融合 2~4 个正交字段，严禁多字段大杂烩过拟合。"
            )

        issues.extend(visitor.issues)

        # 6. 算子数量物理上限门禁 (Power Pool <= 10, 定向优化 <= 10)
        if visitor.operator_count > max_operators:
            issues.append(
                f"【算子数超标】检测到 {visitor.operator_count} 个算子，超过物理上限 (<= {max_operators})！"
                f"过多算子属于虚假繁荣与过度拟合，请精简结构。"
            )

        # 7. 检查是否至少包含 1 个有效数据集内部字段，且严禁使用非白名单/幻觉字段
        if fields_meta:
            if not (visitor.used_fields.intersection(set(fields_meta.keys()))):
                issues.append(f"未检测到属于当前数据集的有效字段！当前表达式使用的有效字段为: {list(visitor.used_fields)}")
            invalid_fields = [f for f in visitor.used_fields if f not in fields_meta]
            if invalid_fields:
                issues.append(f"【非法/幻觉字段违规】检测到非白名单字段: {invalid_fields}！所有字段必须 100% 属于当前数据集。")

        # 8. Step 1 纯净实证与核心字段锁定校验 (Clean Empirical Validation)
        if step == 1:
            STEP1_FORBIDDEN_OPERATORS = set()  # 采纳 GM 建议：解禁 winsorize, s_log_1p, signed_power 供清洗与形状映射
            forbidden_hit = visitor.called_operators.intersection(STEP1_FORBIDDEN_OPERATORS)
            if forbidden_hit:
                issues.append(
                    f"【Step 1 违规使用装潢算子】检测到非线性装潢算子: {list(forbidden_hit)}！"
                    f"Step 1 实证初筛严禁使用装潢算子虚增夏普，只能使用基础时序与截面算子干净检验假说原生预测力。"
                )
            max_step1_ops = min(max_operators, (stage0_op_count + 4) if stage0_op_count > 0 else max_operators)
            if visitor.operator_count > max_step1_ops:
                issues.append(
                    f"【Step 1 算子超限违规】算子总数 {visitor.operator_count} 超过 Step 1 上限 (<= {max_step1_ops})！"
                    f"实证初筛期严禁堆砌过多包装算子掩盖真实信号质量。"
                )

        if required_fields:
            missing_required = set(required_fields) - set(visitor.used_fields)
            if missing_required:
                issues.append(
                    f"【核心字段丢失违规】当前变体未锁定主信号核心字段: 缺失 {list(missing_required)}！"
                    f"Step 1 实证检验必须严格锁定主信号底层因果源，严禁擅自篡改核心字段。"
                )

        # 9. 平台官方算子全量合规校验 (Single Source of Truth, SSOT)
        # Agent 享有基于经济学机制自主选算子的自由，平台 104 个合法算子全量开放，仅拦截完全不存在的幻觉算子
        all_platform_ops = OperatorRegistry.get_all_operator_names()
        for op in visitor.called_operators:
            if op not in all_platform_ops and not op.startswith("vec_") and not op.startswith("group_") and not op.startswith("ts_"):
                issues.append(f"【未知/非法算子拦截】检测到非 WorldQuant Brain 平台合法算子: '{op}'！请选用官方算子库中的标准算子。")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "operator_count": visitor.operator_count,
            "called_operators": list(visitor.called_operators),
            "used_fields": list(visitor.used_fields),
            "used_pv_fields": list(visitor.used_pv_fields),
            "group_vars": list(visitor.group_vars)
        }
