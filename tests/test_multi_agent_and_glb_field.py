"""
test_multi_agent_and_glb_field.py
针对 Freebuff / 外部宿主平台内置子 Agent 接口与 GLB 跨区域字段解析的专项回归测试

覆盖测试项:
1. GLB / TOPDIV3000 / fundamental23 跨区域同源继承与 List 结构多格式解析 (测试 1)
2. 命令行 --fields 与 --fields-file 显式注入画像 (测试 2)
3. SubAgent IPC 邮箱协议 (任务下发 task_*.json -> 宿主内置 Sub-Agent 响应 resp_*.json) (测试 3)
4. LLM API (OpenAI/DeepSeek 兼容) 参数构建与请求封装 (测试 4)
5. 综合端到端集成: main.py 在 GLB 市场下以 SubAgent IPC 驱动执行 Stage 0 与状态机轮询 (测试 5)
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from quant_framework.core.field_resolver import DatasetFieldResolver
from quant_framework.core.agent_backends import (
    create_agent_backend,
    SubAgentIPCBackend,
    LLMAPIBackend,
    AGYCliBackend,
    RuleMockBackend,
    extract_json_from_text
)
from quant_framework.main import AegisPipelineController


class TestMultiAgentAndGLBField(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        os.environ["AEGIS_MOCK_MODE"] = "1"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_glb_fundamental23_cross_region_inheritance(self):
        """测试 1: 验证 GLB 市场缺少缓存时，自动跨区域继承 USA fundamental23 (兼容 List 格式)"""
        resolver = DatasetFieldResolver()
        fields = resolver.resolve_fields(
            region="GLB",
            category="fundamental",
            dataset_id="fundamental23",
            allow_cross_region=True
        )

        self.assertIsInstance(fields, dict)
        self.assertGreater(len(fields), 500, "GLB fundamental23 应成功解析超过 500 个真实财务字段")
        self.assertIn("accounts_cash_and_equivalents", fields)
        f_meta = fields["accounts_cash_and_equivalents"]
        self.assertEqual(f_meta.get("type"), "MATRIX")
        self.assertGreater(f_meta.get("coverage", 0), 0.5)
        print(f"  ✅ [测试 1 通过] 成功为 GLB/fundamental23 跨区域继承并解析 {len(fields)} 个有效字段！")

    def test_02_explicit_fields_override(self):
        """测试 2: 验证命令行 --fields 与 --fields-file 优先级与外部注入"""
        resolver = DatasetFieldResolver()

        # 1. 显式逗号字符串
        raw_arg = "custom_f1, custom_f2, custom_f3"
        f_str = resolver.resolve_fields(region="GLB", category="other", dataset_id="ds99", raw_fields_arg=raw_arg)
        self.assertEqual(list(f_str.keys()), ["custom_f1", "custom_f2", "custom_f3"])

        # 2. 外部 JSON 文件
        custom_file = os.path.join(self.test_dir, "my_custom_fields.json")
        with open(custom_file, "w", encoding="utf-8") as f:
            json.dump([
                {"id": "ext_alpha_1", "type": "MATRIX", "coverage": 0.88, "description": "外部测试字段1"},
                {"id": "ext_alpha_2", "type": "MATRIX", "coverage": 0.92, "description": "外部测试字段2"}
            ], f)

        f_file = resolver.resolve_fields(region="GLB", category="other", dataset_id="ds99", fields_file=custom_file)
        self.assertEqual(len(f_file), 2)
        self.assertIn("ext_alpha_1", f_file)
        print("  ✅ [测试 2 通过] 命令行显式指定与外部 JSON 文件注入正常！")

    def test_03_subagent_ipc_mailbox_protocol(self):
        """测试 3: 验证 SubAgent IPC 邮箱中继协议 (模拟 Freebuff 内置子智能体响应)"""
        tasks_dir = os.path.join(self.test_dir, ".agent_tasks")
        backend = SubAgentIPCBackend(tasks_dir=tasks_dir, poll_interval=0.05)

        async def _run_subagent_worker():
            """模拟外部平台 (Freebuff/Cursor) 内置 Sub-Agent: 监听并处理任务"""
            # 等待任务文件生成
            for _ in range(50):
                await asyncio.sleep(0.05)
                files = [f for f in os.listdir(tasks_dir) if f.startswith("task_") and f.endswith(".json")]
                if files:
                    task_path = os.path.join(tasks_dir, files[0])
                    with open(task_path, "r", encoding="utf-8") as tf:
                        task = json.load(tf)
                    
                    # 模拟内置子 Agent 生成回复
                    resp_path = task["expected_response_file"]
                    mock_swarm_output = [
                        {
                            "slot": 1,
                            "expression": "ts_delta(accounts_cash_and_equivalents, 5)",
                            "neutralization": "STATISTICAL",
                            "strategy": "EXPLORATION",
                            "optimize_reason": "测试外部 Sub-Agent 响应"
                        }
                    ]
                    with open(resp_path, "w", encoding="utf-8") as rf:
                        json.dump(mock_swarm_output, rf)
                    break

        async def _test_call():
            worker_task = asyncio.create_task(_run_subagent_worker())
            res = await backend.send_message(
                role="aegis-swarm-generator",
                model="builtin-subagent",
                prompt="请生成变体",
                json_mode=True,
                timeout=5
            )
            await worker_task
            return res

        result = asyncio.run(_test_call())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slot"], 1)
        print("  ✅ [测试 3 通过] SubAgent IPC 任务派发与外部子 Agent 响应读取闭环成功！")

    def test_04_llm_api_backend_builder(self):
        """测试 4: 验证 LLM API (OpenAI/DeepSeek 兼容) 参数组装"""
        api_backend = LLMAPIBackend(
            api_base="https://api.deepseek.com/v1",
            api_key="sk-test-mock-key",
            default_model="deepseek-chat"
        )
        self.assertEqual(api_backend.api_base, "https://api.deepseek.com/v1")
        self.assertEqual(api_backend.default_model, "deepseek-chat")
        self.assertEqual(api_backend.api_key, "sk-test-mock-key")

        # 测试 JSON 提取辅助函数
        raw_text = "Here is the result:\n```json\n{\"status\": \"OK\", \"count\": 20}\n```\nDone."
        extracted = extract_json_from_text(raw_text)
        self.assertEqual(extracted, {"status": "OK", "count": 20})
        print("  ✅ [测试 4 通过] LLM API 驱动初始化与 Markdown JSON 抽取器验证正常！")

    def test_05_controller_glb_stage0_and_pipeline_integration(self):
        """测试 5: AegisPipelineController 在 GLB / fundamental23 下执行 Stage 0 生成与状态机"""
        controller = AegisPipelineController(
            region="GLB",
            universe="TOPDIV3000",
            delay=1,
            category="fundamental",
            dataset_id="fundamental23",
            base_dir=self.test_dir,
            mock_only=True,
            backend_type="ipc",
            tasks_dir=os.path.join(self.test_dir, ".agent_tasks")
        )

        # 1. 验证字段成功跨区域载入
        fields = controller.load_dataset_fields()
        self.assertGreater(len(fields), 100)

        # 2. 执行阶段 0 原型生成
        seeds = controller.synthesize_stage0_seeds(count=5)
        self.assertEqual(len(seeds), 5)
        self.assertTrue(os.path.exists(controller.signals_pool_file))
        print("  ✅ [测试 5 通过] GLB 市场 + fundamental23 下成功生成 5 个纯四则运算双字段主信号原型！")


if __name__ == "__main__":
    unittest.main()
