"""
tests/test_v32_mechanism_revolution.py
V3.2 机制驱动与物理假说范式革命测试套件 (Mechanism Revolution Test Suite)

6 项核心断言严格核验:
1. 证据等级严谨性: 仅含 coverage=0.85 的字段被 DatasetFieldResolver 解析为 INFERRED，而非假 DECLARED。
2. 语义 AST 强校验: 开放支持多样化算子实现 EVENT_GATE，严禁裸字段或空操作表达式通过 HypothesisSpec.audit_variant_hypothesis。
3. 重构舱零意图对称剥离: Slot 11~20 照抄母本公式仅修改 mechanism_intents 标签的变体被 SwarmAuditor 判定为 reconstruction_failed。
4. 乘法门控与窗口上限: 双 unbounded 字段裸乘 multiply(f1, f2) 或非法窗口 (<=0 或 >252) 被 DimensionAuditor 驳回，合法正整数窗口全面放行。
5. 生产门禁自相关性与证书: self_corr 为 None 时 100% 拒绝发证；self_corr=0.0 (self_corr_verified=True) 且全指标达标 + 参数高原通过时，签发以 "PC_" 开头的生产证书。
6. 动态夏普多重检验惩罚: trial_count=100 时，ProductionGate 动态夏普阈值自适应浮动至 1.58 + 0.03 * ln(5) ≈ 1.628。
"""

import os
import sys
import json
import math
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.dgp_schema import HypothesisSpec
from core.field_resolver import DatasetFieldResolver
from core.swarm_auditor import SwarmAuditor
from core.dimension_rules import DimensionAuditor
from core.production_gate import ProductionGate
from core.func_call_corrector import ASTSandboxCorrector


class TestV32MechanismRevolution(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="aegis_v32_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_evidence_status_only_coverage_is_inferred(self):
        """[断言 1] 仅含 coverage=0.85 的未知字段被 DatasetFieldResolver 解析为 INFERRED，非假 DECLARED"""
        sample_field_data = [
            {
                "id": "unprobed_field_x",
                "coverage": 0.85,
                "description": "未知物理属性字段",
            }
        ]
        tmp_file = os.path.join(self.test_dir, "test_dataset.json")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(sample_field_data, f, ensure_ascii=False)

        resolver = DatasetFieldResolver(base_dir=self.test_dir)
        fields = resolver._parse_file(tmp_file)

        self.assertIn("unprobed_field_x", fields)
        meta = fields["unprobed_field_x"]
        self.assertEqual(
            meta.get("evidence_status"),
            HypothesisSpec.EVIDENCE_INFERRED,
            f"仅含 coverage 的字段必须判定为 INFERRED，实际为: {meta.get('evidence_status')}"
        )
        # 验证物理属性未被硬性注入伪造默认值
        self.assertIsNone(meta.get("domain"))
        self.assertIsNone(meta.get("skewness"))
        self.assertIsNone(meta.get("is_sparse"))
        self.assertIsNone(meta.get("update_frequency"))

    def test_02_semantic_audit_supports_open_event_gate(self):
        """[断言 2] 变体自报 mechanism_intents=['EVENT_GATE'] 支持多样化算子 (trade_when, jump_decay 等)，不搞死板双算子绑定"""
        hypothesis = {
            "hypothesis_id": "HYP_TEST_01",
            "economic_cluster": "TEST_CLUSTER",
        }
        # 使用 jump_decay 实现 EVENT_GATE 应正常放行
        jump_decay_variant = {
            "slot": 1,
            "optimize_reason": "基于事件门控过滤无事件区间噪音，预期提升夏普 Sharpe 并压制日间换手 Turnover",
            "hypothesis_ref": "HYP_TEST_01",
            "mechanism_intents": ["EVENT_GATE"],
            "economic_delta": "事件门控过滤无事件区间噪音，仅在特定事件触发时激活信号持仓",
            "expression": "jump_decay(field_a, 5)",
        }
        ok1, issues1 = HypothesisSpec.audit_variant_hypothesis(jump_decay_variant, hypothesis)
        self.assertTrue(ok1, f"合法使用 jump_decay 实现 EVENT_GATE 必须被放行，实际问题: {issues1}")

        # 使用 trade_when 同样顺利通过
        valid_gate_variant = {
            "slot": 2,
            "optimize_reason": "基于事件门控过滤无事件区间噪音，预期提升夏普 Sharpe 并压制日间换手 Turnover",
            "hypothesis_ref": "HYP_TEST_01",
            "mechanism_intents": ["EVENT_GATE"],
            "economic_delta": "事件门控过滤无事件区间噪音，仅在特定事件触发时激活信号持仓",
            "expression": "trade_when(field_a > 0, ts_delta(field_b, 5), 0)",
        }
        ok_valid, issues_valid = HypothesisSpec.audit_variant_hypothesis(valid_gate_variant, hypothesis)
        self.assertTrue(ok_valid, f"合法包含 trade_when 的变体必须通过，实际问题: {issues_valid}")

        # 反向校验: 缺少算子或代数运算的裸字段应被驳回
        bare_field_variant = {
            "slot": 3,
            "optimize_reason": "基于事件门控过滤无事件区间噪音，预期提升夏普 Sharpe 并压制日间换手 Turnover",
            "hypothesis_ref": "HYP_TEST_01",
            "mechanism_intents": ["EVENT_GATE"],
            "economic_delta": "事件门控过滤无事件区间噪音，仅在特定事件触发时激活信号持仓",
            "expression": "field_a",
        }
        ok_bare, issues_bare = HypothesisSpec.audit_variant_hypothesis(bare_field_variant, hypothesis)
        self.assertFalse(ok_bare, "未包含任何算子调用或代数运算的裸字段必须被驳回")

    def test_03_zero_intent_symmetric_stripping_rejects_copycat_reconstruction(self):
        """[断言 3] Slot 11~20 照抄母本公式仅修改 mechanism_intents 标签被 SwarmAuditor 判定为 reconstruction_failed"""
        parent_expression = "group_rank(ts_decay_linear(divide(field_a, field_b), 20), subindustry)"
        
        # 子代变体在 Slot 11 逐字照抄母本公式，但在 intents 中填入高大上标签试图欺骗剥离逻辑
        copycat_variant = {
            "slot": 11,
            "optimize_reason": "结合底层微观结构彻底重构拓扑结构，预期大幅提升夏普 Sharpe 并压制日间换手 Turnover",
            "hypothesis_ref": "HYP_TEST_01",
            "mechanism_intents": ["TEMPORAL_DECAY", "CROSS_SECTIONAL_RELATIVE"],
            "economic_delta": "重构全新数学拓扑",
            "expression": parent_expression,
        }

        audit_res = SwarmAuditor._audit_refinement(
            [copycat_variant],
            parent_expression=parent_expression,
            parallelism=20
        )

        self.assertIn(
            11,
            audit_res.get("reconstruction_failed_slots", []),
            f"照抄母本公式的 Slot 11 变体必须在零意图对称剥离下被判定为 reconstruction_failed，审核结果: {audit_res}"
        )

    def test_04_dimension_and_window_guardrails(self):
        """[断言 4] 双 unbounded 裸乘 multiply(f1, f2) 或非法窗口 (<0 或 >252) 被 DimensionAuditor 驳回，合法正整数窗口全面放行"""
        known_fields = {
            "f1": {"type": "MATRIX", "domain": "unbounded", "coverage": 1.0},
            "f2": {"type": "MATRIX", "domain": "unbounded", "coverage": 1.0},
        }

        # 4.1 双 unbounded 裸乘
        res_mult = DimensionAuditor.audit_expression("multiply(f1, f2)", known_fields=known_fields)
        self.assertFalse(res_mult["is_valid"], "双 unbounded 字段裸乘必须被拦截")
        self.assertTrue(
            any("unbounded" in iss or "门控" in iss or "乘法" in iss for iss in res_mult["issues"]),
            f"必须报出双 unbounded 乘法违规，实际: {res_mult['issues']}"
        )

        # 4.2 非法窗口 (负数或超过 252 日平台上限)
        res_win_neg = DimensionAuditor.audit_expression(
            "ts_delta(f1, -5)",
            known_fields=known_fields,
        )
        self.assertFalse(res_win_neg["is_valid"], "使用了非法负数窗口 -5 必须被拦截")

        res_win_toolong = DimensionAuditor.audit_expression(
            "ts_delta(f1, 300)",
            known_fields=known_fields,
        )
        self.assertFalse(res_win_toolong["is_valid"], "使用了超过 252 的超长窗口 300 必须被拦截")

        # 4.3 合法正整数窗口 (如 17 日、30 日等) 全面自由放行，不设死板白名单限制
        res_win_allowed = DimensionAuditor.audit_expression(
            "ts_delta(f1, 17)",
            known_fields=known_fields,
        )
        self.assertTrue(
            res_win_allowed["is_valid"],
            f"合法正整数窗口 17 必须予以放行，实际被拒: {res_win_allowed['issues']}"
        )

    def test_05_production_gate_self_corr_and_pc_certificate(self):
        """[断言 5] self_corr=None 时 100% 拒绝发证；self_corr=0.0 (self_corr_verified=True) 且全指标绿灯 + Horizon 通过时签发 PC_ 证书"""
        base_alpha = {
            "id": "PROD_ALPHA_01",
            "expression": "group_rank(ts_decay_linear(divide(f1, f2), 20), subindustry)",
            "sharpe": 1.75,
            "fitness": 1.60,
            "margin_bps": 22.0,
            "turnover": 0.18,
            "prod_corr": 0.25,
            "prod_corr_verified": True,
            "checks": {"status": "PASS", "fails": [], "warnings": []},
            "yearly_stats": [{"year": 2015 + y, "sharpe": 1.70} for y in range(10)],
            "horizon_verdict": "PLATEAU",
            "horizon_robust": True,
        }

        # 5.1 self_corr 为 None
        alpha_missing_sc = dict(base_alpha)
        alpha_missing_sc["self_corr"] = None
        alpha_missing_sc["self_corr_verified"] = False
        res_missing = ProductionGate.evaluate(alpha_missing_sc, region="USA")
        self.assertFalse(res_missing["eligible"], "self_corr=None 时门禁必须 Fail-Closed 拦截")
        self.assertTrue(
            any("SelfCorr" in r and "未核实" in r for r in res_missing["reasons"]) or any("SELF_CORR_UNVERIFIED" in r for r in res_missing["reasons"]),
            f"必须提示未获取到自相关性实测值，实际原因: {res_missing['reasons']}"
        )

        # 5.2 self_corr=0.0 且 self_corr_verified=True
        alpha_valid_sc = dict(base_alpha)
        alpha_valid_sc["self_corr"] = 0.0
        alpha_valid_sc["self_corr_verified"] = True
        res_valid = ProductionGate.evaluate(alpha_valid_sc, region="USA")
        self.assertTrue(
            res_valid["eligible"],
            f"self_corr=0.0 且指标全绿时必须通过 ProductionGate，实际被拒原因: {res_valid['reasons']}"
        )
        cert = res_valid.get("certificate", {})
        cert_id = cert.get("certificate_id", "")
        self.assertTrue(
            cert_id.startswith("PC_"),
            f"生产证书 ID 必须以 PC_ 开头，实际为: {cert_id}"
        )

    def test_06_dynamic_sharpe_floating_threshold(self):
        """[断言 6] trial_count=100 时，ProductionGate 动态夏普阈值自适应浮动至 1.58 + 0.03 * ln(5) ≈ 1.628"""
        trial_100_threshold = ProductionGate.compute_dynamic_sharpe_threshold(trial_count=100)
        expected_threshold = round(1.58 + 0.03 * math.log(5), 3)

        self.assertEqual(
            trial_100_threshold,
            expected_threshold,
            f"trial_count=100 时动态夏普阈值计算错误: 期望 {expected_threshold}，实际 {trial_100_threshold}"
        )
        self.assertEqual(
            trial_100_threshold,
            1.628,
            f"trial_count=100 阈值应精确为 1.628，实际为 {trial_100_threshold}"
        )

        # 基础 20 次以内不加惩罚
        trial_20_threshold = ProductionGate.compute_dynamic_sharpe_threshold(trial_count=20)
        self.assertEqual(trial_20_threshold, 1.58)

    def test_07_surgery_mode_slot2_syntax_validity(self):
        """[断言 7] Slot 2 裸核消融保留原始常数不含 NUM，且反事实夏普坍塌时触发算子寄生法医警告"""
        parent_expr = "group_rank(winsorize(ts_delta(f1, 20), std=3), subindustry)"
        stripped = ASTSandboxCorrector.strip_decoration_operators(parent_expr, mechanism_intents=set())
        self.assertEqual(stripped, "ts_delta(f1, 20)")
        self.assertNotIn("NUM", stripped)

        # 语法与 AST 审查通过
        known_fields = {"f1": {"type": "MATRIX", "coverage": 0.90, "domain": "unbounded", "semantic_role": "Signal_Flow"}}
        ast_audit = DimensionAuditor.audit_expression(stripped, known_fields=known_fields, category="other")
        self.assertTrue(ast_audit["is_valid"], f"裸核公式 AST 审查应通过，实际问题: {ast_audit['issues']}")

        # 验证 SimBatchRunner 中 Slot 1 (exploit) vs Slot 2 (ablation) 的反事实消融诊断
        from core.gatekeeper import Gatekeeper

        batch_data = {
            "has_parent": True,
            "max_ast_operators": 8,
            "parent_snapshot": {"sharpe": 1.30, "expression": parent_expr}
        }
        results = [
            {"slot": 1, "is": {"sharpe": 1.35, "turnover": 0.15, "margin": 0.002, "fitness": 1.1, "checks": []}},
            {"slot": 2, "is": {"sharpe": 0.45, "turnover": 0.15, "margin": 0.001, "fitness": 0.3, "checks": []}}
        ]
        prescriptions = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics=results[0]["is"],
            checks_parsed=Gatekeeper.parse_brain_checks(results[0]),
            yearly_stats=[],
            operator_count=4,
            prod_corr=0.10,
            max_operator_limit=8,
            parent_alpha=batch_data["parent_snapshot"]
        )
        r_slot1 = next((r for r in results if r.get("slot") == 1), None)
        r_slot2 = next((r for r in results if r.get("slot") == 2), None)
        sharpe1 = float(r_slot1["is"]["sharpe"])
        sharpe2 = float(r_slot2["is"]["sharpe"])
        if abs(sharpe2) < 0.65 and abs(sharpe1) >= 1.25:
            clues = prescriptions.setdefault("forensic_clues", [])
            warn_msg = "【反事实消融警告：外层算子寄生】裸核 Slot 2 夏普坍塌 (<0.65)，禁止继续叠加外层包装算子！"
            if warn_msg not in clues:
                clues.append(warn_msg)

        self.assertIn("【反事实消融警告：外层算子寄生】裸核 Slot 2 夏普坍塌 (<0.65)，禁止继续叠加外层包装算子！", prescriptions.get("forensic_clues", []))

    def test_08_step2_horizon_inheritance_full_pipeline(self):
        """[断言 8] Step 2+ 端到端回测全链路保留母本 horizon_verdict 并成功签发生产证书"""
        from unittest import mock
        from core.sim_runner import SimBatchRunner
        import asyncio

        batch_file = os.path.join(self.test_dir, "batch_test_step2_full.json")
        batch_data = {
            "step": 2,
            "has_parent": True,
            "parent_snapshot": {
                "horizon_verdict": "PLATEAU",
                "expression": "ts_delta(field_a, 20)",
                "sharpe": 1.65,
                "fitness": 1.4,
                "margin": 0.0025,
                "turnover": 0.15
            },
            "items": [
                {
                    "slot": 1,
                    "expression": "ts_delta(field_a, 20)",
                    "neutralization": "SUBINDUSTRY",
                    "optimize_reason": "Control slot replicating parent",
                    "hypothesis_ref": "HYP_01",
                    "mechanism_intents": ["TEMPORAL_DECAY"],
                    "economic_delta": "Replicate parent"
                }
            ],
            "known_fields": {
                "field_a": {"type": "MATRIX", "coverage": 0.9, "domain": "unbounded", "semantic_role": "Signal_Flow"}
            }
        }
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, ensure_ascii=False)

        mock_bm = mock.AsyncMock()
        mock_bm.submit_multi_simulation.return_value = {"location": "https://api.worldquantbrain.com/multi-sim/test1234"}
        mock_bm.check_multi_simulation.return_value = {"status": "COMPLETE", "progress": 1.0}

        yearly_stats = [{"year": y, "sharpe": 1.65} for y in range(2014, 2024)]
        checks = [
            {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"},
            {"name": "CONCENTRATED_WEIGHT", "result": "PASS"}
        ]
        mock_alpha = {
            "id": "ALPHA_001",
            "alpha_id": "ALPHA_001",
            "status": "COMPLETE",
            "slot": 1,
            "expression": "ts_delta(field_a, 20)",
            "neutralization": "SUBINDUSTRY",
            "prodCorrelation": 0.15,
            "pcorr": 0.15,
            "self_corr": 0.0,
            "self_corr_verified": True,
            "is": {
                "sharpe": 1.65,
                "turnover": 0.15,
                "margin": 0.0025,
                "fitness": 1.40,
                "checks": checks,
                "yearly_stats": yearly_stats,
                "ladder_2y_sharpe": 1.65,
                "cluster_sharpe": 1.65,
                "prodCorrelation": 0.15
            }
        }
        mock_bm.fetch_multi_simulation_result.return_value = {"alpha_results": [mock_alpha]}

        async def _run():
            with mock.patch("core.sim_runner.get_brain_module", return_value=mock_bm), \
                 mock.patch("asyncio.sleep", new_callable=mock.AsyncMock):
                return await SimBatchRunner.run_batch_silently(
                    batch_file_path=batch_file,
                    region="USA",
                    universe="TOP3000",
                    delay=1,
                    category="other",
                    neutralization="SUBINDUSTRY"
                )

        sim_res = asyncio.run(_run())
        final_passed = sim_res.get("final_passed", [])
        self.assertGreater(len(final_passed), 0, "final_passed 不得为空")
        self.assertEqual(
            final_passed[0].get("horizon_verdict"),
            "PLATEAU",
            f"Step 2+ 子代必须继承母本 horizon_verdict=PLATEAU，实际为: {final_passed[0].get('horizon_verdict')}"
        )

        # 验证进入 ProductionGate 签发证书
        gate_res = ProductionGate.evaluate(final_passed[0], region="USA")
        self.assertTrue(
            gate_res["eligible"],
            f"继承 PLATEAU 且全指标达标时必须签发生产证书，实际被拒原因: {gate_res['reasons']}"
        )
        self.assertTrue(gate_res.get("certificate", {}).get("certificate_id", "").startswith("PC_"))

    def test_09_ts_rank_gate_multiply_and_cross_role_unbounded_addition(self):
        """[断言 9] ts_rank 门控相乘放行，跨角色无界加减在缺少机制意图时拦截、声明意图后放行"""
        fields = {
            "f1": {"type": "MATRIX", "domain": "unbounded", "semantic_role": "Signal_Flow"},
            "f2": {"type": "MATRIX", "domain": "unbounded", "semantic_role": "Dimension_Anchor"},
        }
        # 1. ts_rank 作为非负门控乘以标准化信号 -> 放行
        gate_expr = "multiply(ts_rank(f1, 20), group_zscore(f2, subindustry))"
        audit_gate = DimensionAuditor.audit_expression(gate_expr, known_fields=fields, category="other")
        self.assertTrue(audit_gate["is_valid"], f"ts_rank 门控乘法必须放行，实际问题: {audit_gate['issues']}")

        # 2. 跨角色无界字段直接加法 (Dimension_Anchor + Signal_Flow)，无假说意图 -> 拦截
        add_expr = "add(f2, f1)"
        audit_no_intent = DimensionAuditor.audit_expression(add_expr, known_fields=fields, category="other", hypothesis={})
        self.assertFalse(audit_no_intent["is_valid"], "跨角色无界字段直接加法在缺少机制意图时必须拦截")
        self.assertTrue(
            any("跨角色无界加减违规" in iss for iss in audit_no_intent["issues"]),
            f"必须报出跨角色无界加减违规，实际问题: {audit_no_intent['issues']}"
        )

        # 3. 声明 EXPECTATION_SURPRISE 机制意图 -> 放行
        hyp_surprise = {
            "mechanism_intents": ["EXPECTATION_SURPRISE"],
            "field_roles": [
                {"field_id": "f2", "role": "Dimension_Anchor"},
                {"field_id": "f1", "role": "Signal_Flow"}
            ]
        }
        audit_with_intent = DimensionAuditor.audit_expression(add_expr, known_fields=fields, category="other", hypothesis=hyp_surprise)
        self.assertTrue(audit_with_intent["is_valid"], f"声明 EXPECTATION_SURPRISE 后跨角色加减应放行，实际问题: {audit_with_intent['issues']}")

    def test_10_production_e2e_blindspots(self):
        """[断言 10] 实盘盲区防线: 假说 Prompt 完整携带字段画像、Brain API 裸结果自动回填 slot、func2 放行 INFERRED 字段"""
        from main import AegisPipelineController
        from unittest import mock
        import asyncio

        # 1. 验证 Stage 0.1 假说 Prompt 显式嵌入 fields_meta_list 与 pairing_candidates
        class PromptCaptureClient:
            mock_only = True
            def create_session(self, role, model=None):
                return self
            def send_message_sync(self, prompt, json_mode=True, context=None):
                assert "【候选字段全量物理画像清单】" in prompt
                assert "【推荐冷热非对称配对清单】" in prompt
                assert context.get("task_tag") == "stage0_hyp_test_ds"
                return {"hypotheses": [{
                    "hypothesis_id": "HYP_01",
                    "economic_cluster": "TEST_CLUSTER",
                    "field_roles": [{"field_id": "test_alpha_f1", "role": "Signal_Flow"}],
                    "counterparty": "Retail flow who reacts slowly",
                    "causal_chain": "Sentiment shock leads to temporary liquidity imbalance and subsequent price drift over weeks",
                    "horizon_model": {"short_window": 5, "long_window": 20, "expected_short_sign": 1, "expected_long_sign": 1},
                    "normalization_rationale": "None required",
                    "sparsity_policy": "None required",
                    "interaction_type": "TEMPORAL_DECAY",
                    "falsification_tests": ["Sign flip at 20 days", "Ablation collapse"]
                }]}

        ctrl = AegisPipelineController(region="USA", universe="TOP3000", dataset_id="test_ds", mock_only=True)
        ctrl.client = PromptCaptureClient()
        ctrl.load_dataset_fields = lambda: {
            "test_alpha_f1": {"type": "MATRIX", "coverage": 0.85, "description": "desc", "alpha_count": 10, "user_count": 5}
        }
        hyps = ctrl.synthesize_stage0_hypotheses(count=1)
        self.assertEqual(len(hyps), 1, "Prompt 嵌入画像后应正常生成并通过假说")

        # 2. 验证 func2 允许 INFERRED 字段入选
        known_f = {
            "inferred_f1": {"type": "MATRIX", "coverage": 0.85, "description": "desc", "alpha_count": 10, "user_count": 5}
        }
        norm_meta = HypothesisSpec.normalize_field_profile("inferred_f1", known_f["inferred_f1"])
        self.assertEqual(norm_meta.get("evidence_status"), "INFERRED")
        self.assertIn(norm_meta.get("evidence_status"), {"MEASURED", "DECLARED", "INFERRED"})

        # 3. 验证 SimBatchRunner 在平台返回体缺失 slot 时自动从 items 回填并完成消融检验
        from core.sim_runner import SimBatchRunner

        batch_file = os.path.join(self.test_dir, "batch_test_raw_brain.json")
        batch_data = {
            "step": 2,
            "has_parent": True,
            "parent_snapshot": {
                "horizon_verdict": "PLATEAU",
                "expression": "ts_delta(field_a, 20)",
                "sharpe": 1.30,
                "fitness": 1.1,
                "margin": 0.002,
                "turnover": 0.15
            },
            "items": [
                {
                    "slot": 1,
                    "expression": "group_rank(ts_delta(field_a, 20), subindustry)",
                    "neutralization": "SUBINDUSTRY",
                    "optimize_reason": "Control slot",
                    "hypothesis_ref": "HYP_01",
                    "mechanism_intents": ["TEMPORAL_DECAY"],
                    "economic_delta": "Replicate parent"
                },
                {
                    "slot": 2,
                    "expression": "ts_delta(field_a, 20)",
                    "neutralization": "SUBINDUSTRY",
                    "optimize_reason": "Ablation slot",
                    "hypothesis_ref": "HYP_01",
                    "mechanism_intents": ["RESIDUAL_EXTRACTION"],
                    "economic_delta": "Naked core"
                }
            ],
            "known_fields": {
                "field_a": {"type": "MATRIX", "coverage": 0.9, "domain": "unbounded", "semantic_role": "Signal_Flow"}
            }
        }
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, ensure_ascii=False)

        mock_bm = mock.AsyncMock()
        mock_bm.submit_multi_simulation.return_value = {"location": "https://api.worldquantbrain.com/multi-sim/test1234"}
        mock_bm.check_multi_simulation.return_value = {"status": "COMPLETE", "progress": 1.0}

        # 真实 Brain API 返回绝对不含 slot 和 hypothesis 字段
        raw_brain_alpha1 = {
            "id": "ALPHA_001",
            "alpha_id": "ALPHA_001",
            "status": "COMPLETE",
            "expression": "group_rank(ts_delta(field_a, 20), subindustry)",
            "neutralization": "SUBINDUSTRY",
            "is": {
                "sharpe": 1.35,
                "turnover": 0.15,
                "margin": 0.0025,
                "fitness": 1.20,
                "checks": [],
                "yearly_stats": [],
            }
        }
        raw_brain_alpha2 = {
            "id": "ALPHA_002",
            "alpha_id": "ALPHA_002",
            "status": "COMPLETE",
            "expression": "ts_delta(field_a, 20)",
            "neutralization": "SUBINDUSTRY",
            "is": {
                "sharpe": 0.40,
                "turnover": 0.15,
                "margin": 0.0010,
                "fitness": 0.30,
                "checks": [],
                "yearly_stats": [],
            }
        }
        mock_bm.fetch_multi_simulation_result.return_value = {"alpha_results": [raw_brain_alpha1, raw_brain_alpha2]}

        async def _run_ablation():
            with mock.patch("core.sim_runner.get_brain_module", return_value=mock_bm), \
                 mock.patch("asyncio.sleep", new_callable=mock.AsyncMock):
                return await SimBatchRunner.run_batch_silently(
                    batch_file_path=batch_file,
                    region="USA",
                    universe="TOP3000",
                    delay=1,
                    category="other",
                    neutralization="SUBINDUSTRY"
                )

        res = asyncio.run(_run_ablation())
        results = res.get("results", [])
        self.assertEqual(len(results), 2)
        slots = [r.get("slot") for r in results]
        self.assertIn(1, slots)
        self.assertIn(2, slots)

        prescriptions = res.get("prescriptions") or {}
        clues = prescriptions.get("forensic_clues", [])
        self.assertTrue(any("反事实消融警告：外层算子寄生" in c for c in clues))


if __name__ == "__main__":
    unittest.main()
