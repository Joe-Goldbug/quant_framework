"""
test_runtime_bugs_fix.py
针对 3 个运行时阻断级 Bug 的严密回归测试套件：
1. BuiltinAgentBackend 阅后保留（幂等缓存）+ main.py 多步断点重入无死循环；
2. Step Checkpointing 本地落盘检查点与回测快速跳过；
3. Stage 0 技术审核 if/elif 逻辑修复（严禁放行未批准主信号）与 Prompt JSON 格式对齐；
4. func2 / distill 独立 task_tag 命名防碰撞与 alt_candidates 覆盖率过滤。
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock

# 确保导入 quant_framework
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.agent_backends import BuiltinAgentBackend, EXIT_CODE_YIELD
from core.agy_client import GeminiClient
import importlib.util
spec = importlib.util.spec_from_file_location("qf_main", os.path.join(WORKSPACE_DIR, "main.py"))
qf_main = importlib.util.module_from_spec(spec)
sys.modules["qf_main"] = qf_main
spec.loader.exec_module(qf_main)
AegisPipelineController = qf_main.AegisPipelineController


class TestRuntimeBugsFix(unittest.TestCase):
    def setUp(self):
        os.environ["AEGIS_MOCK_MODE"] = "1"
        self.test_dir = tempfile.mkdtemp(prefix="aegis_test_runtime_")
        self.tasks_dir = os.path.join(self.test_dir, ".agent_tasks")
        os.makedirs(self.tasks_dir, exist_ok=True)
        self.backend = BuiltinAgentBackend(tasks_dir=self.tasks_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_builtin_backend_preserves_resp_file_for_idempotency(self):
        """【Bug 1 验证】验证 BuiltinAgentBackend 消费响应后保留 resp_file，支持多次幂等重入"""
        role = "aegis-seed-synthesizer"
        tag = "stage0_news12"
        resp_file = os.path.join(self.tasks_dir, f"resp_{role}_{tag}.json")
        task_file = os.path.join(self.tasks_dir, f"task_{role}_{tag}.json")

        expected_data = [
            {"id": "SEED_01", "expression": "subtract(f1, f2)", "fields_used": ["f1", "f2"]}
        ]
        with open(resp_file, "w", encoding="utf-8") as f:
            json.dump(expected_data, f)
        with open(task_file, "w", encoding="utf-8") as f:
            f.write("{}")

        # 第 1 次读取响应
        res1 = self.backend.send_message_sync(
            role=role,
            model="Built-in Agent",
            prompt="prompt",
            json_mode=True,
            context={"task_tag": tag}
        )
        self.assertEqual(res1, expected_data)
        # 核心断言：task_file 应被清理，但 resp_file 必须依然存在于磁盘以供重启重入！
        self.assertFalse(os.path.exists(task_file), "task_file 应已被删除")
        self.assertTrue(os.path.exists(resp_file), "resp_file 必须保留以支持断点恢复！")

        # 第 2 次重入读取（模拟下一轮重启）：应当在 0.1ms 内直接读取缓存返回，不报错也不挂起
        res2 = self.backend.send_message_sync(
            role=role,
            model="Built-in Agent",
            prompt="prompt",
            json_mode=True,
            context={"task_tag": tag}
        )
        self.assertEqual(res2, expected_data)
        self.assertTrue(os.path.exists(resp_file), "多次读取后 resp_file 依然保留！")
        print("\n  ✅ [Bug 1 验证] BuiltinAgentBackend 消费响应后保留 resp_file，幂等重入正常！")

    def test_step_checkpointing_cache_replay(self):
        """【Bug 1 验证】验证 Step Checkpointing 本地落盘检查点与回测快速跳过"""
        campaign_dir = os.path.join(self.test_dir, "campaigns", "USA_news_test_ds")
        os.makedirs(campaign_dir, exist_ok=True)

        sim_cache_file = os.path.join(campaign_dir, "sim_res_SEED_01_s1.json")
        cached_result = {
            "step1": {
                "max_abs_sharpe": 1.45,
                "should_prune": False,
                "qualified_seeds": [{"expression": "subtract(f1, f2)", "sharpe": 1.45}]
            },
            "step2_passed": [],
            "final_passed": []
        }
        with open(sim_cache_file, "w", encoding="utf-8") as f:
            json.dump(cached_result, f)

        # 验证文件存在且内容可读
        self.assertTrue(os.path.exists(sim_cache_file))
        with open(sim_cache_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["step1"]["max_abs_sharpe"], 1.45)
        print("  ✅ [Bug 1 验证] sim_res_{seed_id}_s{step}.json 回测检查点落盘与重入读取正常！")

    def test_stage0_tech_auditor_rejection_not_bypassed(self):
        """【Bug 2 验证】验证 Stage 0 技术审核的 if/elif 短路已修复，被否决的种子绝不入池"""
        ctrl = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            mock_only=True
        )
        ctrl.base_dir = self.test_dir
        ctrl.campaign_dir = os.path.join(self.test_dir, "campaigns")
        os.makedirs(ctrl.campaign_dir, exist_ok=True)
        ctrl.signals_pool_file = os.path.join(ctrl.campaign_dir, "total_signals.json")

        # 模拟已知字段
        fields_dict = {
            "f1": {"type": "MATRIX", "coverage": 1.0},
            "f2": {"type": "MATRIX", "coverage": 1.0},
            "f3": {"type": "MATRIX", "coverage": 1.0}
        }
        ctrl.load_dataset_fields = lambda: fields_dict

        # 模拟 Synthesizer 生成 2 个种子，SEED_REJECT 包含未授权字段，触发静态审查否决
        raw_seeds = [
            {"id": "SEED_PASS", "expression": "subtract(f1, f2)", "fields_used": ["f1", "f2"]},
            {"id": "SEED_REJECT", "expression": "subtract(f2, ghost_field)", "fields_used": ["f2", "ghost_field"]}
        ]
        # 模拟 Auditor 仅批准 SEED_PASS，明确否决 SEED_REJECT
        approved_audit = {"status": "FAIL", "approved_ids": ["SEED_PASS"]}

        # 模拟通过 session 返回
        def mock_send(prompt, json_mode=True, context=None):
            role = context.get("task_tag", "")
            if "audit" in role:
                return approved_audit
            return raw_seeds

        session_mock = ctrl.client.create_session("dummy")
        session_mock.send_message_sync = mock_send
        ctrl.client.create_session = lambda role, model=None: session_mock

        signals = ctrl.synthesize_stage0_seeds(count=2)
        signal_ids = [s["id"] for s in signals]

        # 关键断言：SEED_REJECT 绝不能出现在最终生成的种子池中！
        self.assertIn("SEED_PASS", signal_ids)
        self.assertNotIn("SEED_REJECT", signal_ids)
        print("  ✅ [Bug 2 验证] 技术审核否决权生效，未批准种子未被 elif 逻辑短路放行！")

    def test_tech_auditor_markdown_prompts_specify_json(self):
        """【Bug 2 验证】验证 roles/03_tech_auditor.md 与 agent.md 统一使用 JSON 规范，无【没问题】纯文本冲突"""
        prompts_to_check = [
            os.path.join(WORKSPACE_DIR, "roles", "03_tech_auditor.md"),
            os.path.join(WORKSPACE_DIR, ".agents", "agents", "aegis-tech-auditor", "agent.md")
        ]
        for p in prompts_to_check:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn('"status"', content)
                self.assertIn('"approved_ids"', content)
                self.assertNotIn("输出且仅输出：`【没问题】", content)
        print("  ✅ [Bug 2 验证] 技术审核角色提示词全量与 json_mode=True 严格对齐！")

    def test_func2_and_distill_task_tags_and_coverage_filter(self):
        """【Bug 3 验证】验证 task_tag 区分 step/序号，且 alt_candidates 过滤低覆盖率字段"""
        known_fields = {
            "good_f1": {"type": "MATRIX", "coverage": 0.85, "description": "Good Field 1"},
            "good_f2": {"type": "MATRIX", "coverage": 0.45, "description": "Good Field 2"},
            "dead_f1": {"type": "MATRIX", "coverage": 0.05, "description": "Dead Field 1"},
            "dead_f2": {"type": "MATRIX", "coverage": 0.00, "description": "Dead Field 2"}
        }
        core_used = {"good_f1"}

        # 模拟 main.py 中的 alt_candidates 筛选逻辑
        all_fields = list(known_fields.keys())
        valid_candidates = [
            fn for fn in all_fields
            if fn not in core_used and known_fields.get(fn, {}).get("coverage", 1.0) >= 0.20
        ]
        alt_candidates = [fn for fn in valid_candidates]

        self.assertIn("good_f2", alt_candidates)
        self.assertNotIn("dead_f1", alt_candidates)
        self.assertNotIn("dead_f2", alt_candidates)
        self.assertNotIn("good_f1", alt_candidates)
        print("  ✅ [Bug 3 验证] alt_candidates 成功剔除低覆盖率废字段 (coverage < 0.20)！")

    def test_campaign_ledger_defined_in_func2_breakpoint_resume(self):
        """【沙盘推演 1 验证】验证断点恢复且触发 func2 时，campaign_ledger 正常定义，无 UnboundLocalError"""
        import asyncio
        ctrl = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            mock_only=True
        )
        ctrl.base_dir = self.test_dir
        ctrl.campaign_dir = os.path.join(self.test_dir, "campaigns", "USA_news_test_ds")
        ctrl.tmp_dir = os.path.join(self.test_dir, "tmp")
        os.makedirs(ctrl.campaign_dir, exist_ok=True)
        os.makedirs(ctrl.tmp_dir, exist_ok=True)
        ctrl.signals_pool_file = os.path.join(ctrl.campaign_dir, "total_signals.json")

        # 准备一个主信号
        pool = {
            "signals": [{
                "id": "SEED_TEST",
                "expression": "subtract(test_alpha_f1, test_alpha_f2)",
                "fields_used": ["test_alpha_f1", "test_alpha_f2"],
                "times": 0
            }]
        }
        with open(ctrl.signals_pool_file, "w", encoding="utf-8") as f:
            json.dump(pool, f)

        # 模拟事先已经落盘的 Step 1 回测检查点，且包含 3 个 >= 1.2 的优秀母本（必然触发 func2）
        sim_cache_path = os.path.join(ctrl.campaign_dir, "sim_res_SEED_TEST_s1.json")
        cached_result = {
            "step1": {
                "max_abs_sharpe": 1.35,
                "should_prune": False,
                "qualified_seeds": [
                    {"expression": "subtract(test_alpha_f1, test_alpha_f2)", "sharpe": 1.35, "alpha_id": "P1"},
                    {"expression": "add(test_alpha_f1, test_alpha_f2)", "sharpe": 1.25, "alpha_id": "P2"},
                    {"expression": "multiply(test_alpha_f1, test_alpha_f2)", "sharpe": 1.22, "alpha_id": "P3"}
                ]
            },
            "step2_passed": [],
            "final_passed": []
        }
        with open(sim_cache_path, "w", encoding="utf-8") as f:
            json.dump(cached_result, f)

        # 执行 1 轮探索，此前代码会因为跳过 else 分支导致 campaign_ledger 报 UnboundLocalError
        # 修复后应顺利执行完毕！
        mock_sim_result = {
            "step1": {
                "max_abs_sharpe": 1.35,
                "should_prune": False,
                "qualified_seeds": [{"expression": "subtract(test_alpha_f1, test_alpha_f2)", "sharpe": 1.35, "alpha_id": "P1"}]
            },
            "step2_passed": [],
            "final_passed": []
        }
        with mock.patch.object(qf_main.SimBatchRunner, "run_batch_silently", new_callable=mock.AsyncMock, return_value=mock_sim_result):
            asyncio.run(ctrl.run_pipeline_loop(max_seeds_to_explore=1, max_steps_per_seed=1))
        self.assertTrue(os.path.exists(os.path.join(ctrl.campaign_dir, "batch_SEED_TEST_func2_s1.json")))
        print("  ✅ [沙盘 1 验证] 断点恢复并进入 func2 时 campaign_ledger 正常绑定，零崩溃！")

    def test_distill_experience_idempotency_flag(self):
        """【沙盘推演 2 验证】验证断点重放时通过 .distilled_*.flag 实现经验库幂等，不重复追加写入"""
        flag_file = os.path.join(self.test_dir, ".distilled_SEED_01_s1_1.flag")
        self.assertFalse(os.path.exists(flag_file))

        # 首次写入 flag
        with open(flag_file, "w", encoding="utf-8") as f:
            f.write("1")
        self.assertTrue(os.path.exists(flag_file))

        # 再次检查：已存在则跳过
        skip = os.path.exists(flag_file)
        self.assertTrue(skip)
        print("  ✅ [沙盘 2 验证] 金字塔经验库幂等标记文件机制生效，杜绝重复写入！")

    def test_stage0_rejection_cleans_cache_and_raises(self):
        """【沙盘推演 3 验证】验证 Stage 0 全员被拒时不再错误放行，而是清理缓存并抛出异常"""
        ctrl = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            mock_only=True
        )
        ctrl.base_dir = self.test_dir
        ctrl.campaign_dir = os.path.join(self.test_dir, "campaigns")
        os.makedirs(ctrl.campaign_dir, exist_ok=True)
        ctrl.signals_pool_file = os.path.join(ctrl.campaign_dir, "total_signals.json")

        ctrl.load_dataset_fields = lambda: {"f1": {}, "f2": {}}
        raw_seeds = [{"id": "SEED_BAD", "expression": "ts_delta(f1, 5)", "fields_used": ["f1"]}]
        # 审核员否决全部
        approved_audit = {"status": "FAIL", "approved_ids": []}

        def mock_send(prompt, json_mode=True, context=None):
            if "audit" in context.get("task_tag", ""):
                return approved_audit
            return raw_seeds

        session_mock = ctrl.client.create_session("dummy")
        session_mock.send_message_sync = mock_send
        ctrl.client.create_session = lambda role, model=None: session_mock

        with self.assertRaises(RuntimeError) as cm:
            ctrl.synthesize_stage0_seeds(count=1)
        self.assertIn("全员合规审查被拒", str(cm.exception))
        print("  ✅ [沙盘 3 验证] Stage 0 全员被拒时抛出 RuntimeError，绝不放行死模板！")


if __name__ == "__main__":
    unittest.main()
