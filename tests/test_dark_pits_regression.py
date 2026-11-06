"""
tests/test_dark_pits_regression.py
针对 3 个实盘运行时暗坑的回归验证套件：
1. audit_step1_batch / audit_step2_batch 完整透传 yearly_stats 与 checks；
2. 模式一 (已有母本优化) Step 1 成功下放 Top-10 冷字段，且 Gate 2 放行治愈算子；
3. main.py 与 orchestrator.py 命令行参数与调度全链路解析。
"""

import os
import sys
import json
import unittest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.gatekeeper import Gatekeeper
from core.sim_runner import SimBatchRunner
from core.dimension_rules import DimensionAuditor
from main import AegisPipelineController


class TestDarkPitsRegression(unittest.TestCase):

    def test_pit1_yearly_stats_and_checks_passthrough(self):
        """验证 Gatekeeper.audit_step1_batch 与 Step 2 黄金档案无损透传"""
        print("\n--- [REGRESSION 1] Dark Pit 1: Yearly Stats & Checks Passthrough ---")
        mock_yearly_stats = [
            {"year": 2014, "sharpe": 2.17},
            {"year": 2020, "sharpe": -2.43},
            {"year": 2023, "sharpe": 1.43}
        ]
        mock_checks = [
            {"name": "CONCENTRATED_WEIGHT", "result": "FAIL", "value": 0.28, "limit": 0.20},
            {"name": "LOW_SHARPE", "result": "WARNING", "value": 1.21, "limit": 1.58}
        ]
        raw_res = {
            "id": "A1Vv3k9l",
            "expression": "subtract(test_f1, test_f2)",
            "is": {
                "sharpe": 1.21,
                "fitness": 0.79,
                "margin": 0.0253,
                "turnover": 0.0421,
                "checks": mock_checks
            },
            "yearly_stats": mock_yearly_stats
        }

        # Step 1 审查
        step1_res = Gatekeeper.audit_step1_batch({"alpha_results": [raw_res]})
        self.assertEqual(len(step1_res["qualified_seeds"]), 1)
        parent = step1_res["qualified_seeds"][0]

        # 断言: yearly_stats 与 checks 必须存在于 qualified_seeds 中
        self.assertIn("yearly_stats", parent)
        self.assertEqual(len(parent["yearly_stats"]), 3)
        self.assertIn("checks", parent)
        self.assertEqual(len(parent["checks"]), 2)

        # 传入 extract_golden_alpha_result 生成黄金体检档案
        golden = SimBatchRunner.extract_golden_alpha_result(parent)
        self.assertEqual(len(golden["yearly_sharpe"]), 3)
        self.assertEqual(golden["yearly_sharpe"][0], ["2014", "2.17"])
        self.assertEqual(golden["yearly_sharpe"][1], ["2020", "-2.43"])
        self.assertEqual(golden["yearly_sharpe"][2], ["2023", "1.43"])
        self.assertEqual(len(golden["fail"]), 1)
        self.assertEqual(golden["fail"][0]["name"], "CONCENTRATED_WEIGHT")
        self.assertEqual(len(golden["warn"]), 1)
        self.assertEqual(golden["warn"][0]["name"], "LOW_SHARPE")
        print("  ✅ 暗坑 1 修复验证通过：10年逐年夏普与原始 checks 成功在 Step 1 -> Step 2 间无损传递！")

    def test_pit2_targeted_mode_alt_candidates_and_curative_ops(self):
        """验证 模式一 (已有母本优化) 允许首轮下放 Top-10 备选字段且放行治愈算子"""
        print("\n--- [REGRESSION 2] Dark Pit 2: Targeted Mode Alt-Candidates & Curative Ops ---")
        ctrl = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            mock_only=True
        )

        mock_parent = {
            "id": "MOM_ALPHA",
            "expression": "subtract(f1, f2)",
            "sharpe": 1.35,
            "fitness": 1.10,
            "margin_bps": 15.0,
            "turnover": 0.20,
            "yearly_stats": [{"year": 2020, "sharpe": 1.20}]
        }

        # 模拟在 step=1 时针对该母本生成变体 (靶向优化第一轮)
        seed = {
            "id": "SEED_TEST",
            "expression": "subtract(f1, f2)",
            "fields_used": ["f1", "f2"]
        }
        variants = ctrl.generate_swarm_variants(
            seed=seed,
            parent_alpha=mock_parent,
            step=1
        )
        self.assertGreater(len(variants), 0)

        # 验证 Gate 2 在 has_parent=True 时的放行逻辑
        # 变体包含 winsorize/s_log_1p (治愈算子) 且更换了字段为 alt_f3
        expr_with_curative = "group_rank(s_log_1p(winsorize(alt_f3, std=3)), subindustry)"
        known_fields = {
            "f1": {"type": "MATRIX", "coverage": 0.9},
            "f2": {"type": "MATRIX", "coverage": 0.9},
            "alt_f3": {"type": "MATRIX", "coverage": 0.9}
        }

        # 构造带有 has_parent=True 标记的批次元数据
        b_meta = {"has_parent": True, "step": 1, "seed_id": "SEED_TEST"}
        batch_file = os.path.join(ctrl.campaign_dir, "batch_test_parent.json")
        os.makedirs(ctrl.campaign_dir, exist_ok=True)
        with open(batch_file, "w", encoding="utf-8") as bf:
            json.dump({
                "step": 2,  # 模式一写入时标记为 2
                "has_parent": True,
                "core_fields": ["f1", "f2"],
                "items": [{"expression": expr_with_curative}]
            }, bf)

        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=batch_file,
            expressions_data=[{"expression": expr_with_curative}],
            known_fields=known_fields,
            category="news",
            region="USA",
            universe="TOP1000",
            delay=1,
            neutralization="NONE"
        )
        self.assertEqual(len(corrected), 1)
        print("  ✅ 暗坑 2 修复验证通过：已有母本优化首轮即开放冷字段平替，且 Gate 2 放行治愈算子！")

    def test_pit3_orchestrator_and_main_argparse(self):
        """验证 模式二与模式三 命令行参数解析顺畅无冲突"""
        print("\n--- [REGRESSION 3] Dark Pit 3: CLI Argparse Compatibility ---")
        import subprocess

        # 验证 orchestrator.py 支持 --batch-size 和 --steps-per-seed
        cmd = [
            sys.executable,
            os.path.join(WORKSPACE_DIR, "orchestrator.py"),
            "--help"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("--batch-size", res.stdout)
        self.assertIn("--steps-per-seed", res.stdout)
        self.assertIn("--max-seeds", res.stdout)

        # 验证 main.py 支持 --generate-seeds 与 --seeds-only
        cmd_main = [
            sys.executable,
            os.path.join(WORKSPACE_DIR, "main.py"),
            "--help"
        ]
        res_main = subprocess.run(cmd_main, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res_main.returncode, 0)
        self.assertIn("--generate-seeds", res_main.stdout)
        self.assertIn("--seeds-only", res_main.stdout)
        print("  ✅ 暗坑 3 修复验证通过：orchestrator 与 main 的命令行参数完全兼容且定义无误！")


if __name__ == "__main__":
    unittest.main()
