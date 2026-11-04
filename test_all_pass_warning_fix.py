import os
import sys
import unittest
import json
import math

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

from core.gatekeeper import Gatekeeper
from core.dimension_rules import DimensionAuditor
from main import AegisPipelineController

class TestAllPassWarningResolution(unittest.TestCase):
    def test_01_gatekeeper_transparency(self):
        """测试补丁 1: audit_step1_batch 与 audit_final_alpha 完整透传 warnings 与子夏普"""
        mock_sim_result = {
            "alpha_results": [{
                "id": "alpha_test_01",
                "expression": "group_rank(ts_decay_linear(returns, 10), subindustry)",
                "is": {
                    "sharpe": 1.75,
                    "fitness": 1.20,
                    "margin": 0.0018,
                    "turnover": 0.25,
                    "checks": [
                        {"name": "CONCENTRATED_WEIGHT", "result": "WARNING", "value": 0.12},
                        {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "WARNING", "value": 0.95},
                        {"name": "CLUSTER", "result": "PASS", "value": 1.62},
                        {"name": "LADDER", "result": "PASS", "value": 1.80}
                    ]
                },
                "pcorr": 0.45,
                "neutralization": "SUBINDUSTRY"
            }]
        }

        # Step 1
        s1 = Gatekeeper.audit_step1_batch(mock_sim_result, min_sharpe=1.0)
        self.assertFalse(s1["should_prune"])
        self.assertEqual(len(s1["qualified_seeds"]), 1)
        seed_data = s1["qualified_seeds"][0]
        self.assertEqual(seed_data["warning_count"], 2)
        self.assertIn("CONCENTRATED_WEIGHT", seed_data["warnings"])
        self.assertIn("LOW_SUB_UNIVERSE_SHARPE", seed_data["warnings"])
        self.assertEqual(seed_data["cluster_sharpe"], 1.62)
        self.assertEqual(seed_data["ladder_2y_sharpe"], 1.80)
        self.assertEqual(seed_data["sub_universe_sharpe"], 0.95)

        # Final alpha
        final = Gatekeeper.audit_final_alpha(mock_sim_result, region="USA")
        self.assertEqual(len(final), 1)
        f_alpha = final[0]
        self.assertEqual(f_alpha["warning_count"], 2)
        self.assertIn("CONCENTRATED_WEIGHT", f_alpha["warnings"])
        self.assertEqual(f_alpha["sub_universe_sharpe"], 0.95)

    def test_02_gatekeeper_prescription_and_gate2_unlock(self):
        """测试补丁 2: WARNING 自动授权治愈算子，彻底消除 Gate 2 拦截"""
        parent_alpha_with_warning = {
            "expression": "group_rank(ts_decay_linear(test_f, 10), subindustry)",
            "metrics": {
                "sharpe": 1.45,
                "fitness": 1.10,
                "turnover": 0.32,
                "margin_bps": 12.0
            },
            "warning_count": 2,
            "warnings": ["CONCENTRATED_WEIGHT", "LOW_SUB_UNIVERSE_SHARPE"],
            "fails": [],
            "fail_count": 0
        }

        verdict = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics=parent_alpha_with_warning["metrics"],
            checks_parsed=parent_alpha_with_warning,
            operator_count=4,
            prod_corr=0.55
        )

        self.assertIn("cw_bottleneck", verdict["symptoms"])
        self.assertIn("sub_universe_or_2y_instability", verdict["symptoms"])
        self.assertIn("winsorize", verdict["allowed_mutations"])
        self.assertIn("s_log_1p", verdict["allowed_mutations"])
        self.assertIn("signed_power", verdict["allowed_mutations"])
        self.assertIn("trade_when", verdict["allowed_mutations"])

        # 验证 Gate 2 (DimensionAuditor.audit_expression) 处方校验：
        # Agent 主动加上 winsorize(..., std=3) 与 s_log_1p 不再被 Gate 2 拦截！
        curative_expr = "group_rank(s_log_1p(winsorize(test_f, std=3)), subindustry)"
        gate2_res = DimensionAuditor.audit_expression(
            curative_expr,
            known_fields={"test_f": {"coverage": 0.9, "category": "news"}},
            category="news",
            step=2,
            allowed_operators=verdict["allowed_mutations"]
        )
        self.assertTrue(gate2_res["is_valid"], f"Gate 2 不应误杀已授权的治愈算子: {gate2_res['issues']}")

    def test_03_champion_zero_warning_priority(self):
        """测试补丁 3: 冠军加冕优先 ALL PASS (0 FAIL + 0 WARNING)"""
        ctrl = AegisPipelineController(
            region="USA", universe="TOP1000", delay=1, category="news", dataset_id="test_ds"
        )

        # 候选 A: Sharpe 极高 (2.0)，Score 极高，但有 1 个 WARNING (未达到全绿)
        alpha_with_warn = {
            "seed_id": "SEED_01",
            "expression": "group_rank(ts_decay_linear(test_f, 10), subindustry)",
            "sharpe": 2.00,
            "fitness": 1.50,
            "margin_bps": 20.0,
            "prod_corr": 0.40,
            "prod_corr_verified": True,
            "warning_count": 1,
            "warnings": ["CONCENTRATED_WEIGHT"],
            "fail_count": 0,
            "fails": []
        }

        # 候选 B: Sharpe 稍低 (1.80)，Score 稍低，但 0 FAIL + 0 WARNING (ALL PASS 完美全绿)
        alpha_zero_warn = {
            "seed_id": "SEED_01",
            "expression": "group_rank(s_log_1p(winsorize(test_f, std=3)), subindustry)",
            "sharpe": 1.80,
            "fitness": 1.35,
            "margin_bps": 18.0,
            "prod_corr": 0.42,
            "prod_corr_verified": True,
            "warning_count": 0,
            "warnings": [],
            "fail_count": 0,
            "fails": []
        }

        elig_warn = ctrl.champion_eligibility(alpha_with_warn)
        elig_zero = ctrl.champion_eligibility(alpha_zero_warn)

        self.assertFalse(elig_warn["zero_warnings"])
        self.assertTrue(elig_zero["zero_warnings"])

        score_warn = ctrl.compute_champion_score(alpha_with_warn)
        score_zero = ctrl.compute_champion_score(alpha_zero_warn)
        self.assertGreater(score_warn, score_zero)

        # 比较排序 key:
        rank_warn = (2 if elig_warn["status"] == "VERIFIED_CHAMPION" else 1, bool(elig_warn["zero_warnings"]), bool(elig_warn["margin_premium_ok"]), score_warn)
        rank_zero = (2 if elig_zero["status"] == "VERIFIED_CHAMPION" else 1, bool(elig_zero["zero_warnings"]), bool(elig_zero["margin_premium_ok"]), score_zero)

        # 验证: 0 WARNING 全绿代表优先胜出！
        self.assertGreater(rank_zero, rank_warn, "0 WARNING 全绿因子必须优先于带警告因子夺得冠军代表！")

    def test_04_stage0_ast_field_override(self):
        """测试补丁 3 中的 Stage 0 AST 字段强制覆盖"""
        # 模拟 candidate_signals 中 LLM 伪报 fields_used
        fake_llm_signal = {
            "id": "SEED_01",
            "expression": "divide(real_field_a, real_field_b)",
            "fields_used": ["fake_cold_field_x", "fake_cold_field_y"] # LLM 伪报冷门字段
        }
        known_fields = {
            "real_field_a": {"coverage": 0.9, "category": "news"},
            "real_field_b": {"coverage": 0.85, "category": "news"}
        }
        audit_res_ast = DimensionAuditor.audit_expression(
            fake_llm_signal["expression"],
            known_fields=known_fields,
            category="news",
            allow_pv_cross=False
        )
        fake_llm_signal["fields_used"] = audit_res_ast.get("used_fields") or fake_llm_signal.get("fields_used", [])

        # 验证 fields_used 被真实 AST 字段覆盖，绝不允许伪报
        self.assertEqual(set(fake_llm_signal["fields_used"]), {"real_field_a", "real_field_b"})

if __name__ == "__main__":
    unittest.main()
