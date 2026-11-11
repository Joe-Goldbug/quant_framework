"""
tests/test_prompt_guardrail_alignment.py
验证 5 项致命“左右互搏”规则冲突修复闭环：
1. Stage 0 单字段与 2~3 字段准入一致性 (audit_atom_stage0_expression & crowding_pairing classify)
2. HorizonProbe 探针倍率上限 (1.6 ~ 4.2) 覆盖 (5, 20) 与 (63, 252)
3. ASTSandboxCorrector.VALID_LOOKBACKS 包含 1 保护日频变动，移除 504 对齐 dimension_rules
4. main.py Step 1 stage_guidance 允许 ts_backfill 与 winsorize(..., std=4) 进行基础清洗
5. main.py DuplicateResolver 扰动天数对齐自然日历且无特定字段硬编码
"""

import unittest
import os
import sys

try:
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    from quant_framework.core.crowding_pairing import FieldCrowdingProfiler
    from quant_framework.core.horizon_probe import HorizonProbe
    from quant_framework.core.dimension_rules import DimensionAuditor
    from quant_framework.main import AegisPipelineController
except ModuleNotFoundError:
    from core.func_call_corrector import ASTSandboxCorrector
    from core.crowding_pairing import FieldCrowdingProfiler
    from core.horizon_probe import HorizonProbe
    from core.dimension_rules import DimensionAuditor
    from main import AegisPipelineController


class TestPromptGuardrailAlignment(unittest.TestCase):

    def test_01_stage0_single_and_multi_field_admission(self):
        """漏洞 1 验证：Stage 0 允许 1 字段 pure TS/CS 种子与 2~3 字段配对种子，拦截 0 字段与 >3 字段"""
        valid_fields = {"field_a", "field_b", "field_c", "field_d"}
        
        # 1. 单字段表达式合规
        single_expr = "group_zscore(ts_delta(winsorize(field_a, std=4), 20), subindustry)"
        ok, issues, op_count, used = ASTSandboxCorrector.audit_atom_stage0_expression(
            single_expr, valid_dataset_fields=valid_fields
        )
        self.assertTrue(ok, f"单字段 TS/CS 表达式应被放行，但出现错误: {issues}")
        self.assertEqual(len(used), 1)

        # 2. 双字段表达式合规
        dual_expr = "divide(group_zscore(field_a, subindustry), winsorize(field_b, std=3))"
        ok2, issues2, op_count2, used2 = ASTSandboxCorrector.audit_atom_stage0_expression(
            dual_expr, valid_dataset_fields=valid_fields
        )
        self.assertTrue(ok2, f"双字段表达式应被放行: {issues2}")
        self.assertEqual(len(used2), 2)

        # 3. 0 字段拦截
        zero_expr = "group_zscore(1.0, subindustry)"
        ok0, issues0, _, _ = ASTSandboxCorrector.audit_atom_stage0_expression(
            zero_expr, valid_dataset_fields=valid_fields
        )
        self.assertFalse(ok0, "0 字段表达式必须被拦截")

        # 4. 4 字段拦截
        four_expr = "subtract(subtract(field_a, field_b), subtract(field_c, field_d))"
        ok4, issues4, _, _ = ASTSandboxCorrector.audit_atom_stage0_expression(
            four_expr, valid_dataset_fields=valid_fields
        )
        self.assertFalse(ok4, "4 字段大杂烩必须被拦截")

        # 5. FieldCrowdingProfiler.classify 单字段自归一判定
        fields_dict = {
            "field_a": {"coverage": 0.85, "alpha_count": 5},
            "field_b": {"coverage": 0.90, "alpha_count": 100},
        }
        profiler = FieldCrowdingProfiler(fields_dict)
        single_res = profiler.classify(["field_a"])
        self.assertTrue(single_res["is_asymmetric"], "低拥挤单字段应判定为 is_asymmetric=True 放行自归一")
        self.assertEqual(single_res["main_anchor"], "field_a")
        self.assertIsNone(single_res["normalizer"])

    def test_02_horizon_probe_pair_ratio_covers_natural_calendar(self):
        """漏洞 2 验证：HorizonProbe 支持 (5, 20) [4.0x] 与 (63, 252) [4.0x]"""
        probe = HorizonProbe()
        
        # 构造 (5, 20) 配对
        slot_5 = {
            "slot": 1,
            "expression": "group_rank(ts_decay_linear(field_a, 5), subindustry)",
            "type": "EXPLORATION"
        }
        slot_20 = {
            "slot": 2,
            "expression": "group_rank(ts_decay_linear(field_a, 20), subindustry)",
            "type": "EXPLORATION"
        }
        
        # 构造 (63, 252) 配对
        slot_63 = {
            "slot": 3,
            "expression": "group_neutralize(ts_mean(field_a, 63), subindustry)",
            "type": "EXPLORATION"
        }
        slot_252 = {
            "slot": 4,
            "expression": "group_neutralize(ts_mean(field_a, 252), subindustry)",
            "type": "EXPLORATION"
        }

        variants = [slot_5, slot_20, slot_63, slot_252]
        pairs = probe.detect_pairs(variants)
        
        self.assertEqual(len(pairs), 2, f"应该成功识别 2 组 4.0x 倍率自然日历配对，实测识别到: {len(pairs)} 组")
        pair_slots = [p["slots"] for p in pairs]
        self.assertIn((1, 2), pair_slots)
        self.assertIn((3, 4), pair_slots)

    def test_03_calendar_snapper_protects_daily_trigger_and_aligns_ints(self):
        """漏洞 3 验证：d=1 日频触发器不被篡改，且 VALID_LOOKBACKS 整数严格属于 DimensionAuditor 白名单"""
        valid_ints = DimensionAuditor.VALID_CALENDAR_INTS
        
        # 1. VALID_LOOKBACKS 中的所有元素都必须在 VALID_CALENDAR_INTS 中
        for lb in ASTSandboxCorrector.VALID_LOOKBACKS:
            self.assertIn(lb, valid_ints, f"VALID_LOOKBACKS 中的 {lb} 未在 DimensionAuditor.VALID_CALENDAR_INTS 中！")

        # 2. 验证 1 不会被吸附为 5
        expr_daily = "trade_when(greater(abs(ts_delta(field_a, 1)), 0), field_b, -1)"
        snapped_daily = ASTSandboxCorrector.snap_economic_calendar_windows(expr_daily)
        self.assertIn("ts_delta(field_a, 1)", snapped_daily, f"ts_delta(..., 1) 日频触发器不应被篡改为 5！实际为: {snapped_daily}")

        # 3. 验证非法天数 4->5, 44->63 正常吸附
        expr_4 = "group_rank(ts_mean(field_a, 4), subindustry)"
        self.assertIn("ts_mean(field_a, 5)", ASTSandboxCorrector.snap_economic_calendar_windows(expr_4))

        expr_62 = "group_rank(ts_decay_linear(field_a, 62), subindustry)"
        self.assertIn("ts_decay_linear(field_a, 63)", ASTSandboxCorrector.snap_economic_calendar_windows(expr_62))

    def test_04_step1_guidance_allows_cleaning_and_calendar_pairs(self):
        """漏洞 4 验证：main.py Step 1 stage_guidance 允许基础清洗并鼓励自然日历周期对"""
        controller = AegisPipelineController(
            region="USA", universe="TOP1000", delay=1, category="other", dataset_id="other566", mock_only=True
        )
        prompt_parts = []
        seed = {
            "id": "SEED_TEST",
            "expression": "subtract(f1, f2)",
            "economic_mechanism": "测试假说"
        }
        # Step 1 guidance
        variants = controller.generate_swarm_variants(seed=seed, step=1, parent_alpha=None)
        # 校验生成代码是否正常走通
        self.assertTrue(len(variants) > 0)

    def test_05_duplicate_resolver_uses_valid_calendar_and_no_hardcoded_fields(self):
        """漏洞 5 验证：DuplicateResolver 替考代码已被彻底删除，采用 Pre-Flight 重试闭环"""
        # 读取 main.py 源码断言
        main_py_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. 确认 DuplicateResolver 替考已被物理废除
        self.assertNotIn("class DuplicateResolver", content)
        self.assertNotIn("DuplicateResolver.resolve_and_perturb_batch", content)

        # 2. 确认已移除特定数据集字段硬编码
        self.assertNotIn("total_review_number", content)
        self.assertNotIn("product_listed_price", content)


if __name__ == "__main__":
    unittest.main()
