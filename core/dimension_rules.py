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
    def __init__(self, fields_meta: Dict[str, dict], category: str, allow_pv_cross: bool, max_operators: int = 8):
        self.fields_meta = fields_meta
        self.category = category.lower()
        self.allow_pv_cross = allow_pv_cross
        self.max_operators = max_operators
        
        self.issues: List[str] = []
        self.operator_count = 0
        self.used_fields: Set[str] = set()
        self.used_pv_fields: Set[str] = set()
        self.group_vars: Set[str] = set()
        self.called_operators: Set[str] = set()

        self.EXTERNAL_PV_FIELDS = {
            "close", "open", "high", "low", "vwap", "volume", "cap", "adv20",
            "returns", "sharesout", "split", "dividend"
        }
        # 1. 采纳 GM 铁律：物理封杀容易造成量纲混乱与过拟合的 add(+) 和 multiply(*)
        self.FORBIDDEN_OPERATORS = {"add", "multiply"}

        # 2. 经济学自然日历周期白名单：5(周), 10(双周), 20/21/22(月), 60/63(季), 120/126(半年), 250/252(年)
        # 以及向后兼容的 0, 1, 2, 3, 4 (用于 ts_delay(x, 1), rettype=0/2, driver/std 整数位等)
        self.VALID_CALENDAR_INTS = {0, 1, 2, 3, 4, 5, 10, 20, 21, 22, 60, 63, 120, 126, 250, 252}

        # 3. 标准小数参数白名单 (彻底封杀 0.13, 0.37, 1.42 等网格过拟合小数)
        self.VALID_CANONICAL_FLOATS = {
            -1.0, 0.0, 0.01, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 
            0.5, 0.7, 0.75, 0.8, 0.9, 0.95, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0
        }

        self.VALID_GROUPS = {"market", "sector", "industry", "subindustry", "country", "region"}
        self.VECTOR_WRAPPERS = {
            "vec_avg", "vec_sum", "vec_choose", "vec_count", "vec_max",
            "vec_min", "vec_std", "vec_stddev", "vec_range", "vec_norm",
            "vec_percentage", "vec_ir", "vec_skewness", "vec_kurtosis", "vec_median"
        }

    def _get_field_info(self, field_name: str) -> dict:
        meta = self.fields_meta.get(field_name, {}) if isinstance(self.fields_meta, dict) else {}
        if meta.get("domain") and meta.get("domain") != "unbounded":
            return meta

        # 真实定义域启发式纠偏 (AEGIS v3.1 修正)
        name_lower = field_name.lower()
        f_type = meta.get("type") or ("VECTOR" if ("vector" in name_lower or name_lower.startswith("vec_")) else "MATRIX")
        info = {"type": f_type, "domain": meta.get("domain", "unbounded"), "is_sparse": meta.get("is_sparse", False)}

        # 1. 深度学习收益回归预测 (prob_rank_bin1_* 等) 为无界实数
        if "prob_rank_bin" in name_lower or "return_model" in name_lower or "growth" in name_lower:
            info["domain"] = "unbounded"
            info["is_sparse"] = False
        # 2. news / sentiment 真实画像：mean_sentiment_score_transfer, max_primary_sentiment 真实值域为 [0, 1] 且稀疏！
        elif any(w in name_lower for w in ["sentiment_score", "primary_sentiment", "sentiment_transfer", "relevance", "prob_", "_prob", "probability"]):
            info["domain"] = "[0, 1]"
            info["is_sparse"] = True
        # 3. 对称得分与相关系数
        elif any(w in name_lower for w in ["sent_score", "sentiment", "zscore", "ts_corr", "correlation", "divergence", "spread_score"]):
            info["domain"] = "[-1, 1]"
            info["is_sparse"] = False

        return info

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

    def _infer_node_domain(self, node: ast.AST) -> dict:
        """递归推导 AST 节点的数值定义域与稀疏性"""
        if isinstance(node, ast.Name):
            return self._get_field_info(node.id)
        elif isinstance(node, ast.Constant):
            return {"type": "CONSTANT", "domain": "constant", "value": node.value, "is_sparse": False}
        elif isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", "")
            # 保留原定义域的平滑或截面算子
            if func_name in ("winsorize", "ts_decay_linear", "ts_decay_exp_window", "ts_mean", "ts_sum", "ts_min", "ts_max", "group_rank", "rank"):
                if node.args:
                    return self._infer_node_domain(node.args[0])
            # 偶数次方运算转为非负 [0, inf)
            elif func_name == "power":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    val = node.args[1].value
                    if isinstance(val, (int, float)) and val % 2 == 0:
                        return {"type": "MATRIX", "domain": "[0, inf)", "is_sparse": False}
                if node.args:
                    return self._infer_node_domain(node.args[0])
            # 差分与减法转为无界
            elif func_name in ("ts_delta", "subtract"):
                return {"type": "MATRIX", "domain": "unbounded", "is_sparse": False}
            # 标准化算子转为 [-1, 1] 或对齐
            elif func_name in ("group_zscore", "ts_zscore"):
                return {"type": "MATRIX", "domain": "[-1, 1]", "is_sparse": False}
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

        # 1. 双 [-1, 1] 字段乘积伪因果拦截 (支持递归子树嵌套检查，如 winsorize 嵌套)
        if func_name == "multiply" and len(node.args) >= 2:
            arg1, arg2 = node.args[0], node.args[1]
            info1 = self._infer_node_domain(arg1)
            info2 = self._infer_node_domain(arg2)
            if info1.get("domain") == "[-1, 1]" and info2.get("domain") == "[-1, 1]":
                f1 = self._extract_subtree_fields(arg1)
                f2 = self._extract_subtree_fields(arg2)
                self.issues.append(
                    f"【伪因果负负得正违规】检测到双 [-1, 1] 字段乘积 (左支: {f1}, 右支: {f2})！"
                    f"当两项同时处于极度负面时，乘积为正导致生成买入信号，存在严重伪因果！请对其中一项做正向平移 (如 add(x, 1.0)) 或使用条件门控。"
                )

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
                        f"这会导致海量无事件 0 值被偏移为 -0.5 伪空头信号，引发严重多空持仓失衡！请改用 trade_when 或 ts_zscore 自归一。"
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
        """拦截表达式中直接写的 + 或 * 符号"""
        if isinstance(node.op, (ast.Add, ast.Mult)):
            op_sym = "+" if isinstance(node.op, ast.Add) else "*"
            self.issues.append(
                f"【GM 铁律拦截】严禁使用 '{op_sym}' (add/multiply) 运算符！"
                "多特征交互请改用同量纲 subtract、规模归一 divide、正交残差 ts_regression 或条件门控 trade_when/if_else。"
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        """拦截无经济学意义的窗口天数 (如 4, 44) 与乱凑的小数参数"""
        val = node.value
        if isinstance(val, bool) or val is None or isinstance(val, str):
            return
        if isinstance(val, int):
            if abs(val) not in self.VALID_CALENDAR_INTS:
                self.issues.append(
                    f"【GM 日历周期铁律拦截】检测到无经济学意义的整数参数 '{val}'！"
                    f"时序窗口必须严格锚定自然日历周期: 5(周), 10(双周), 20/21(月), 63(季), 126(半年), 252(年)。"
                )
        elif isinstance(val, float):
            if round(val, 4) not in self.VALID_CANONICAL_FLOATS:
                self.issues.append(
                    f"【GM 反调参过拟合拦截】检测到非标准小数参数 '{val}'！"
                    f"浮点数仅允许使用标准分位或幂次常数: {sorted(list(self.VALID_CANONICAL_FLOATS))}。"
                )
        self.generic_visit(node)

    def visit_Num(self, node: ast.Num):
        val = node.n
        if isinstance(val, int):
            if abs(val) not in self.VALID_CALENDAR_INTS:
                self.issues.append(
                    f"【GM 日历周期铁律拦截】检测到无经济学意义的整数参数 '{val}'！"
                )
        elif isinstance(val, float):
            if round(val, 4) not in self.VALID_CANONICAL_FLOATS:
                self.issues.append(
                    f"【GM 反调参过拟合拦截】检测到非标准小数参数 '{val}'！"
                )
        self.generic_visit(node)


class DimensionAuditor:
    EXTERNAL_PV_FIELDS = {
        "close", "open", "high", "low", "vwap", "volume", "cap", "adv20", 
        "returns", "sharesout", "split", "dividend"
    }
    # 彻底解禁 group_neutralize，将其置空，完全放行合规截面中性化
    FORBIDDEN_OPERATORS = set()
    VALID_GROUPS = {"market", "sector", "industry", "subindustry", "country", "region"}
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
        required_fields: Optional[List[str]] = None
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
                    elif any(w in name_lower for w in ["sentiment_score", "primary_sentiment", "sentiment_transfer", "relevance", "prob_", "_prob", "probability"]):
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
            max_operators=max_operators
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
