"""
test_cross_module_bugs_fix.py
针对 3 个跨模块隐藏 Bug 及清理项的回归测试套件：
1. Bug 1: gatekeeper.py audit_step1_batch 解包指标到顶层 (fitness, margin_bps, turnover 等)，诊断不失明；
2. Bug 2: dimension_rules.py 放行 2~4 个数据集字段，拦截 >= 5 个大杂烩；
3. Bug 3: AST visit_Call 仅遍历 args/keywords，不把 pasteurize 等算子误判为幻觉字段；
4. Bug 3 附带: _get_field_info 保留 type: VECTOR (即使 domain 未定义或为 unbounded)；
5. 死代码清理验证: core.agy_client.VirtualSession 不再包含已弃用的 _invoke_agy_cli*。
"""

import ast
import unittest
import os
import sys

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.gatekeeper import Gatekeeper
from core.dimension_rules import DimensionAuditor, ASTSymbolicVisitor
from core.agy_client import VirtualSession


class TestCrossModuleBugsFix(unittest.TestCase):
    def test_bug1_gatekeeper_unpacks_metrics_to_toplevel(self):
        """【Bug 1 验证】audit_step1_batch 将 fitness, margin_bps, turnover 展平到顶层"""
        sim_res = {
            "alpha_results": [
                {
                    "settings": {"regular": "group_rank(subtract(f1, f2), subindustry)"},
                    "is": {
                        "sharpe": 1.42,
                        "fitness": 1.15,
                        "turnover": 0.28,
                        "margin": 0.0016,  # 16 bps
                        "checks": [{"name": "CONCENTRATED_WEIGHT", "result": "PASS", "value": 0.05}]
                    }
                }
            ]
        }
        audit_res = Gatekeeper.audit_step1_batch(sim_res, min_sharpe=1.0)
        self.assertEqual(audit_res["qualified_count"], 1)
        q = audit_res["qualified_seeds"][0]
        
        self.assertIn("fitness", q)
        self.assertIn("margin_bps", q)
        self.assertIn("turnover", q)
        self.assertIn("fail_count", q)
        self.assertIn("cw_failed", q)

        self.assertAlmostEqual(q["fitness"], 1.15)
        self.assertAlmostEqual(q["margin_bps"], 16.0)
        self.assertAlmostEqual(q["turnover"], 0.28)
        self.assertFalse(q["cw_failed"])
        print("\n  ✅ [Bug 1 验证] audit_step1_batch 顶层指标解包与 bps 换算精确生效！")

    def test_bug2_dimension_auditor_allows_four_fields_rejects_five(self):
        """【Bug 2 验证】DimensionAuditor 允许 2~4 个正交字段，封杀 > 4 个字段"""
        fields_meta = {
            "curr_assets": {"type": "MATRIX", "domain": "unbounded"},
            "cash": {"type": "MATRIX", "domain": "unbounded"},
            "curr_liab": {"type": "MATRIX", "domain": "unbounded"},
            "total_assets": {"type": "MATRIX", "domain": "unbounded"},
            "surplus_field": {"type": "MATRIX", "domain": "unbounded"}
        }

        # 4 个字段的经典会计应计异象
        expr_4 = "group_rank(divide(subtract(subtract(curr_assets, cash), curr_liab), total_assets), subindustry)"
        res4 = DimensionAuditor.audit_expression(expr_4, fields_meta, category="fundamental")
        self.assertTrue(res4["is_valid"], f"4 字段经典异象应予通过，实测报错: {res4['issues']}")

        # 5 个字段的大杂烩违规
        expr_5 = "group_rank(divide(subtract(subtract(curr_assets, cash), curr_liab), add(total_assets, surplus_field)), subindustry)"
        res5 = DimensionAuditor.audit_expression(expr_5, fields_meta, category="fundamental")
        self.assertFalse(res5["is_valid"], "5 字段表达式必须被拦截！")
        self.assertTrue(any("字段超限违规" in issue for issue in res5["issues"]))
        print("  ✅ [Bug 2 验证] 2~4 字段复合异象放行与 5 字段大杂烩物理拦截正常！")

    def test_bug3_ast_visitor_does_not_flag_operators_as_hallucinations(self):
        """【Bug 3 验证】AST 遍历仅访问参数与关键字，不把 pasteurize 等算子当成幻觉字段"""
        fields_meta = {
            "f1": {"type": "MATRIX", "domain": "unbounded"},
            "f2": {"type": "MATRIX", "domain": "unbounded"}
        }
        # 使用不在常规白名单或前缀集合中的非典型算子 pasteurize
        expr = "group_rank(pasteurize(divide(f1, f2)), subindustry)"
        res = DimensionAuditor.audit_expression(expr, fields_meta, category="analyst")
        
        # 绝不能报 pasteurize 是非法/幻觉字段！
        for issue in res["issues"]:
            self.assertNotIn("pasteurize", issue)
        self.assertNotIn("pasteurize", res["used_fields"])
        self.assertEqual(set(res["used_fields"]), {"f1", "f2"})
        print("  ✅ [Bug 3 验证] 外部/非典型算子 AST 节点未被误判为数据集字段！")

    def test_bug3_vector_type_preserved_with_unbounded_domain(self):
        """【Bug 3 验证】_get_field_info 保留 type: VECTOR，即使 domain 未定义或为 unbounded"""
        fields_meta = {
            "custom_topic_dist": {"type": "VECTOR", "domain": "unbounded", "is_sparse": False}
        }
        visitor = ASTSymbolicVisitor(fields_meta=fields_meta, category="news", allow_pv_cross=False)
        info = visitor._get_field_info("custom_topic_dist")
        self.assertEqual(info.get("type"), "VECTOR")

        # 若直接将 VECTOR 裸传入非 vec_* 算子，必须触发 VECTOR 类型安全违规！
        expr = "group_rank(add(custom_topic_dist, 1.0), subindustry)"
        res = DimensionAuditor.audit_expression(expr, fields_meta, category="news")
        self.assertFalse(res["is_valid"])
        self.assertTrue(any("VECTOR 类型安全违规" in issue for issue in res["issues"]))
        print("  ✅ [Bug 3 验证] VECTOR 类型属性在 domain=unbounded 下完整保留并精准拦截裸调用！")

    def test_dead_cli_methods_removed(self):
        """【清理验证】VirtualSession 中已彻底移除遗留的 dead CLI 方法"""
        self.assertFalse(hasattr(VirtualSession, "_invoke_agy_cli"))
        self.assertFalse(hasattr(VirtualSession, "_invoke_agy_cli_sync"))
        print("  ✅ [清理验证] VirtualSession 废弃 CLI 同异步方法已彻底移除！")


if __name__ == "__main__":
    unittest.main()
