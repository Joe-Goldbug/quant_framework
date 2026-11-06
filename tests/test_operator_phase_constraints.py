import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

from core.dimension_rules import DimensionAuditor
from core.gatekeeper import Gatekeeper
from main import AegisPipelineController

class TestOperatorPhaseConstraints(unittest.TestCase):
    def test_01_discovery_phase_strict_le_6(self):
        """测试研究挖掘阶段: 必须严格 <= 6 算子 (信号纯粹，经济学意义优先)"""
        # 普通挖掘模式: targeted_alpha_id 为 None
        ctrl_discovery = AegisPipelineController(
            region="USA", universe="TOP1000", delay=1, category="news", dataset_id="test_ds",
            targeted_alpha_id=None, mock_only=True
        )
        self.assertEqual(ctrl_discovery.max_champion_operators, 6)
        self.assertEqual(ctrl_discovery.max_ast_operators, 8)

        # 构造算子数 = 6 的因子 (应当合规)
        alpha_6_ops = {
            "expression": "group_rank(ts_decay_linear(test_f, 10), subindustry)",
            "sharpe": 1.70,
            "fitness": 1.25,
            "margin_bps": 18.0,
            "prod_corr": 0.40,
            "prod_corr_verified": True,
            "operator_count": 6
        }
        elig_6 = ctrl_discovery.champion_eligibility(alpha_6_ops)
        self.assertTrue(elig_6["eligible"], f"挖掘阶段 6 算子必须合规: {elig_6['reasons']}")

        # 构造算子数 = 7 的因子 (挖掘阶段必须硬性否决)
        alpha_7_ops = {
            "expression": "group_rank(ts_decay_linear(ts_delta(test_f, 5), 10), subindustry)",
            "sharpe": 1.80,
            "fitness": 1.30,
            "margin_bps": 20.0,
            "prod_corr": 0.40,
            "prod_corr_verified": True,
            "operator_count": 7
        }
        elig_7 = ctrl_discovery.champion_eligibility(alpha_7_ops)
        self.assertFalse(elig_7["eligible"], "挖掘阶段 7 算子必须硬性否决")
        self.assertTrue(any("7 > 6" in r for r in elig_7["reasons"]), f"原因应指明 > 6: {elig_7['reasons']}")

    def test_02_targeted_quasi_champion_phase_relaxed_to_le_10(self):
        """测试准冠军 Alpha 优化阶段: 放宽至 <= 10 算子"""
        # 准冠军优化模式: 传入 targeted_alpha_id="qMLPOJPK"
        ctrl_targeted = AegisPipelineController(
            region="GLB", universe="TOP3000", delay=1, category="other", dataset_id="techindi_model",
            targeted_alpha_id="qMLPOJPK", mock_only=True
        )
        self.assertEqual(ctrl_targeted.max_champion_operators, 10)
        self.assertEqual(ctrl_targeted.max_ast_operators, 10)

        # 准冠军优化阶段: 7 算子与 10 算子因子均允许登台
        alpha_7_ops = {
            "expression": "group_neutralize(ts_decay_linear(ts_delta(test_f, 5), 10), industry)",
            "sharpe": 1.75,
            "fitness": 1.20,
            "margin_bps": 20.0,
            "prod_corr": 0.50,
            "prod_corr_verified": True,
            "operator_count": 7
        }
        elig_7 = ctrl_targeted.champion_eligibility(alpha_7_ops)
        self.assertTrue(elig_7["eligible"], f"准冠军优化阶段 7 算子必须允许登台: {elig_7['reasons']}")

        alpha_10_ops = {
            "expression": "group_neutralize(winsorize(ts_decay_linear(test_f, 10), std=3), industry)",
            "sharpe": 1.85,
            "fitness": 1.35,
            "margin_bps": 22.0,
            "prod_corr": 0.45,
            "prod_corr_verified": True,
            "operator_count": 10
        }
        elig_10 = ctrl_targeted.champion_eligibility(alpha_10_ops)
        self.assertTrue(elig_10["eligible"], f"准冠军优化阶段 10 算子必须允许登台: {elig_10['reasons']}")

        # 算子数 = 11 (超出 10) 仍必须被否决
        alpha_11_ops = dict(alpha_10_ops, operator_count=11)
        elig_11 = ctrl_targeted.champion_eligibility(alpha_11_ops)
        self.assertFalse(elig_11["eligible"], "准冠军优化阶段超过 10 算子必须否决")
        self.assertTrue(any("11 > 10" in r for r in elig_11["reasons"]), f"原因应指明 > 10: {elig_11['reasons']}")

    def test_03_dimension_rules_default_and_override(self):
        """测试 dimension_rules.py 默认保持 8 算子审查，优化阶段才显式放宽至 10"""
        # 默认调用: 默认上限必须是 8 (9 算子应超限拦截)
        e_9_ops = "add(add(add(add(add(add(add(add(add(f1, f2), f1), f2), f1), f2), f1), f2), f1), f2)"
        res_default = DimensionAuditor.audit_expression(
            e_9_ops, known_fields=["f1", "f2"], category="news"
        )
        self.assertFalse(res_default["is_valid"])
        self.assertTrue(any("<= 8" in iss for iss in res_default["issues"]))

        # 准冠军优化阶段显式传入 max_operators=10: 9 算子放行
        res_relaxed = DimensionAuditor.audit_expression(
            e_9_ops, known_fields=["f1", "f2"], category="news", max_operators=10
        )
        self.assertTrue(res_relaxed["is_valid"], f"显式 max_operators=10 时 9 算子应放行: {res_relaxed['issues']}")

    def test_04_gatekeeper_prune_prescription_adaptive(self):
        """测试 Gatekeeper 诊断算子超限自适应签发 LE_8 或 LE_10 剪枝指令"""
        # 挖掘阶段 (默认 max_operator_limit=8): 9 算子触发 PRUNE_REDUNDANT_OPERATOR_TO_LE_8
        v_disc = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics={"turnover": 0.20},
            operator_count=9,
            max_operator_limit=8
        )
        self.assertIn("operator_count_overflow", v_disc["symptoms"])
        self.assertIn("PRUNE_REDUNDANT_OPERATOR_TO_LE_8", v_disc["allowed_mutations"])

        # 准冠军优化阶段 (max_operator_limit=10): 9 算子不超限；11 算子触发 LE_10
        v_opt_9 = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics={"turnover": 0.20},
            operator_count=9,
            max_operator_limit=10
        )
        self.assertNotIn("operator_count_overflow", v_opt_9["symptoms"])

        v_opt_11 = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics={"turnover": 0.20},
            operator_count=11,
            max_operator_limit=10
        )
        self.assertIn("operator_count_overflow", v_opt_11["symptoms"])
        self.assertIn("PRUNE_REDUNDANT_OPERATOR_TO_LE_10", v_opt_11["allowed_mutations"])

if __name__ == "__main__":
    unittest.main()
