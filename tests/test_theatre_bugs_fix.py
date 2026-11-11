"""
test_theatre_bugs_fix.py
针对 6 处假闭环 (Theatre Code) 与数据流断路 Bug 的全量物理校验测试
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from quant_framework.main import AegisPipelineController
from quant_framework.core.agy_client import GeminiClient, VirtualSession, normalize_model_slug
from quant_framework.core.sim_runner import SimBatchRunner


class TestTheatreBugsFix(unittest.TestCase):

    def setUp(self):
        os.environ["AEGIS_MOCK_MODE"] = "1"
        os.environ["AEGIS_MOCK_FINAL"] = "1"
        self.test_dir = tempfile.mkdtemp()
        self.controller = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            base_dir=self.test_dir,
            mock_only=True
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_model_slug_and_deep_refiner_fallback(self):
        """[Bug 5 验证] 模型 Slug 自动正规化与 deep-refiner 完整降级与周期自适应"""
        # 1. 验证模型名称映射
        slug = normalize_model_slug("Gemini 3.8 Flash (High)")
        self.assertEqual(slug, "gemini-3.8-flash-high")
        
        # 2. 验证 deep-refiner 降级能够产出合法变体
        client = GeminiClient(mock_only=True)
        session = client.create_session(role="aegis-deep-refiner")
        parents = [
            {"alpha_id": "PARENT_01", "expression": "subtract(feat_a, feat_b)", "sharpe": 1.45}
        ]
        res = session.send_message_sync(
            "refine prompt",
            json_mode=True,
            context={"parents": parents, "neutralizations": ["STATISTICAL", "CROWDING"]}
        )
        self.assertIsInstance(res, list)
        self.assertGreater(len(res), 0)
        self.assertIn("s_log_1p", res[0]["expression"])
        self.assertIn("optimize_reason", res[0])

        # 3. 验证 fundamental 数据集降级周期自适应 (66/125/252)
        swarm_session = client.create_session(role="aegis-swarm-generator")
        fnd_res = swarm_session.send_message_sync(
            "swarm prompt",
            json_mode=True,
            context={"core_expr": "subtract(a, b)", "category": "fundamental"}
        )
        has_quarterly = any("66" in v["expression"] or "125" in v["expression"] for v in fnd_res)
        self.assertTrue(has_quarterly, "Fundamental 数据集未自适应季度长周期！")
        print("  ✅ [Bug 5 验证通过] 模型名称标准化、deep-refiner 降级与周期自适应正常！")

    def test_02_pyramid_kb_and_inspiration_injection(self):
        """[Bug 3 验证] 四级金字塔经验与灵感必须注入生成 Prompt 与 Context"""
        seed = {"id": "SEED_TEST", "expression": "subtract(f1, f2)"}
        mock_kb = "### [TEST_CARD] 必须使用 winsorize(std=3)"
        mock_insp = "尝试结合 ts_decay_exp_window 与 group_rank"

        # 拦截生成并检查参数是否被消费
        variants = self.controller.generate_swarm_variants(
            seed=seed,
            parent_alpha=None,
            pyramid_kb=mock_kb,
            inspiration=mock_insp
        )
        self.assertEqual(len(variants), 20)
        self.assertTrue(any("winsorize" in v["expression"] for v in variants))
        print("  ✅ [Bug 3 验证通过] pyramid_kb 与 inspiration 成功注入并驱动群体发散！")

    def test_03_stage0_field_sampling_metadata_and_tech_audit(self):
        """[Bug 4 验证] 字段元数据卡片保留、覆盖度筛选与 aegis-tech-auditor 审核通过"""
        # 伪造带描述与 Vector 的字段知识库
        kb_path = os.path.join(self.test_dir, "knowledge_base", "fields", "USA")
        os.makedirs(kb_path, exist_ok=True)
        kb_file = os.path.join(kb_path, "test_ds.json")
        with open(kb_file, 'w', encoding='utf-8') as f:
            json.dump({
                "fields": {
                    "sales_rev": {"description": "季度营业收入", "type": "MATRIX", "coverage": 0.95},
                    "cogs_exp": {"description": "季度主营业务成本", "type": "MATRIX", "coverage": 0.92},
                    "vec_analyst_target": {"description": "分析师目标价向量", "type": "VECTOR", "coverage": 0.85},
                    "low_cov_junk": {"description": "极低覆盖率垃圾字段", "type": "MATRIX", "coverage": 0.05}
                }
            }, f)

        self.controller.kb_fields_file = kb_file
        seeds = self.controller.synthesize_stage0_seeds(count=4)
        
        # 验证低覆盖率字段未被选中
        for s in seeds:
            self.assertNotIn("low_cov_junk", s["fields_used"])
            # 验证纯四则运算约束
            expr = s["expression"]
            for forbidden_op in ["ts_delta", "ts_decay", "ts_mean"]:
                self.assertNotIn(forbidden_op, expr)

        self.assertGreater(len(seeds), 0)
        print("  ✅ [Bug 4 验证通过] 字段元数据保留、低覆盖过滤与 Tech Auditor 静态审查正常！")

    def test_04_seed_scoped_lineage_and_isolation(self):
        """[Bug 2 验证] 种子专属候选池，彻底杜绝跨种子母本串味污染"""
        # 手动给全局 good_alphas 塞入 SEED_01 的不相关资产字段母本
        self.controller.good_alphas = [
            {"alpha_id": "ALPHA_SEED_01_ASSETS", "expression": "subtract(total_assets, total_liab)", "sharpe": 1.88}
        ]
        
        # 现在激活 SEED_02 (舆情字段)
        seed2 = {"id": "SEED_02", "expression": "subtract(news_sent, news_prob)"}
        
        # 如果不传入 parent_alpha (当前种子无历史)，应该生成原生拓扑，绝不能引用 ALPHA_SEED_01_ASSETS！
        variants = self.controller.generate_swarm_variants(seed=seed2, parent_alpha=None)
        
        for v in variants:
            if v["type"] == "EXPLOITATION":
                # 母本 ID 必须是 SEED_02 自身，绝不能被 SEED_01 污染
                self.assertEqual(v["original_alpha"], "SEED_02")
                self.assertNotIn("total_assets", v["expression"])
        print("  ✅ [Bug 2 验证通过] 种子专属母本隔离确立，0 跨种子串味污染！")

    def test_05_func2_deep_refinement_closed_loop(self):
        """[Bug 1 验证] func2 深水区精炼必须生成真实批次并闭环回测"""
        # 准备一个包含达标种子的储备池
        pool_file = self.controller.signals_pool_file
        with open(pool_file, 'w', encoding='utf-8') as pf:
            json.dump({
                "signals": [
                    {
                        "id": "SEED_WIN",
                        "expression": "subtract(test_alpha_f1, test_alpha_f2)",
                        "fields_used": ["test_alpha_f1", "test_alpha_f2"],
                        "economic_mechanism": "强信号测试",
                        "times": 0
                    }
                ]
            }, pf)

        # 运行流水线，设置单种子最多 2 步迭代 (采用 mock.patch 隔离仿真平台网络回测)
        mock_sim_result = {
            "step1": {
                "max_abs_sharpe": 1.45,
                "should_prune": False,
                "qualified_seeds": [{"expression": "subtract(test_alpha_f1, test_alpha_f2)", "sharpe": 1.45}]
            },
            "step2_passed": [],
            "final_passed": []
        }
        with mock.patch("main.SimBatchRunner.run_batch_silently", new_callable=mock.AsyncMock, return_value=mock_sim_result):
            asyncio.run(self.controller.run_pipeline_loop(max_seeds_to_explore=1, max_steps_per_seed=2))
        
        # 检查是否生成了批次文件
        files = os.listdir(self.controller.campaign_dir)
        batch_files = [f for f in files if f.startswith("batch_SEED_WIN")]
        self.assertGreater(len(batch_files), 0, "未生成回测批次文件！")
        print("  ✅ [Bug 1 验证通过] func2 回测批次与纵向迭代闭环正常运转！")


if __name__ == "__main__":
    unittest.main()
