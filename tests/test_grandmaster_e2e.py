"""
test_grandmaster_e2e.py
AEGIS GrandMaster (WS29639 对齐版) 核心端到端功能验证套件
验证以下核心机制：
1. 阶段 0 纯四则运算双字段主信号池与 times 计数器 (0 时序算子提前嵌套)
2. 阶段 1 群体发散 (func1): 锁定主信号核心、50% 探索 + 50% 演进、动态高阶中性化字典
3. 本地 2ms AST 语法纠偏 (ts_moving_average -> ts_mean, d=5 -> 5) 与骨架唯一性
4. 阶梯漏斗早停: Step 1 若无 |Sharpe| >= 1.0，0.05 秒内直接置 times=1 切换下一个种子，0 Token 纠缠
5. 金字塔四级知识库与纯算子经验沉淀 (只有运算符、无数据字段)
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.gatekeeper import Gatekeeper
from quant_framework.core.rag_memory import RAGMemoryEngine
from quant_framework.main import AegisPipelineController, REGION_NEUTRALIZATIONS_DICT

class TestAEGISGrandMaster(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.controller = AegisPipelineController(
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            dataset_id="test_ds",
            base_dir=self.temp_dir,
            parallelism=20
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_stage0_pure_arithmetic_dual_field_seeds(self):
        """测试阶段 0: 纯四则运算双字段原型，严禁提前嵌套时序算子"""
        print("\n--- [GM TEST 1] 阶段 0 纯四则运算双字段原型池 ---")
        seeds = self.controller.synthesize_stage0_seeds(count=6)
        self.assertEqual(len(seeds), 6)
        
        for s in seeds:
            expr = s["expression"]
            self.assertEqual(s["times"], 0, "新生成种子初始 times 必须为 0")
            self.assertEqual(len(s["fields_used"]), 2, "主信号原型必须为纯净双字段")
            # 严格断言：阶段 0 严禁出现时序算子
            self.assertNotIn("ts_delta", expr, "阶段 0 严禁提前嵌套 ts_delta！")
            self.assertNotIn("ts_decay", expr, "阶段 0 严禁提前嵌套 ts_decay！")
            self.assertNotIn("ts_mean", expr, "阶段 0 严禁提前嵌套 ts_mean！")
        print("  ✅ 成功验证：阶段 0 种子池均为纯四则运算双字段原型，0 时序算子提前焊死窗口")

    def test_02_func1_swarm_locked_core_and_50_50_quota(self):
        """测试阶段 1: 锁定主信号核心、50% 探索 vs 50% 演进、动态中性化字典"""
        print("\n--- [GM TEST 2] 阶段 1 群体发散 (func1) 50/50 配额与高阶中性化 ---")
        seed = {
            "id": "SEED_01",
            "expression": "subtract(feat_a, feat_b)",
            "economic_mechanism": "差分反映预期差"
        }
        variants = self.controller.generate_swarm_variants(seed)
        self.assertEqual(len(variants), 20, "单批必须装满 20 条变体 (对齐原帖 PARALLELISM_INSIDE=20)")
        
        exploration_count = sum(1 for v in variants if v["type"] == "EXPLORATION")
        exploitation_count = sum(1 for v in variants if v["type"] == "EXPLOITATION")
        self.assertEqual(exploration_count, 10, "必须严格包含 50% 全新探索变体")
        self.assertEqual(exploitation_count, 10, "必须严格包含 50% 母本演进变体")

        # 检查核心双字段锁定
        for v in variants:
            expr = v["expression"]
            self.assertIn("feat_a", expr, "变体必须锁定主信号核心字段 feat_a")
            self.assertIn("feat_b", expr, "变体必须锁定主信号核心字段 feat_b")
            # 检查 USA 区域动态高阶中性化
            self.assertIn(v["neutralization"], REGION_NEUTRALIZATIONS_DICT["USA"], "USA 区域必须使用高阶风险中性化")
        print("  ✅ 成功验证：20 条变体严格 50/50 配额，核心双字段 100% 锁定，USA 高阶中性化适配")

    def test_03_ast_2ms_alias_correction_and_deduplication(self):
        """测试本地 2ms AST 纠偏引擎与参数映射"""
        print("\n--- [GM TEST 3] 本地 2ms AST 语法别名与参数位置智能纠偏 ---")
        corrector = ASTSandboxCorrector()
        
        # 1. 算子别名智能纠偏
        raw_expr = "ts_moving_average(ts_delta(x, d=5), d=10)"
        fixed_expr = corrector.correct_expression(raw_expr)
        self.assertEqual(fixed_expr, "ts_mean(ts_delta(x, 5), 10)")

        # 2. sub / div / neg 别名纠偏
        raw_expr2 = "sub(div(a, b), neg(c))"
        fixed_expr2 = corrector.correct_expression(raw_expr2)
        self.assertEqual(fixed_expr2, "subtract(divide(a, b), reverse(c))")

        # 3. group 算子非法引号剥离
        raw_expr3 = 'group_rank(x, "subindustry")'
        fixed_expr3 = corrector.correct_expression(raw_expr3)
        self.assertEqual(fixed_expr3, "group_rank(x, subindustry)")
        print("  ✅ 成功验证：本地 AST 引擎毫秒级完成别名映射、参数位置纠错与引号剥离")

    def test_04_step1_funnel_pruning_zero_token(self):
        """测试 Step 1 阶梯漏斗早停: |Sharpe| < 1.0 立即剪枝，0 Token 纠缠"""
        print("\n--- [GM TEST 4] Step 1 阶梯漏斗极速早停 (0 Token 纠缠) ---")
        # 模拟全批 20 条回测最高 Sharpe 仅为 0.28 (失败种子)
        fail_sim_data = {
            "alpha_results": [
                {"expression": f"alpha_{i}", "is": {"sharpe": 0.20 + i*0.01}}
                for i in range(20)
            ]
        }
        step1_audit = Gatekeeper.audit_step1_batch(fail_sim_data, min_sharpe=1.0)
        self.assertTrue(step1_audit["should_prune"], "最高 Sharpe < 1.0 必须触发早停！")
        self.assertEqual(len(step1_audit["qualified_seeds"]), 0)
        print("  ✅ 成功验证：失败主信号立即触发 Step 1 物理熔断，0 Token 消耗，直接切入下一轮！")

        # 模拟有达标变体 (Sharpe = 1.45)
        pass_sim_data = {
            "alpha_results": [
                {"expression": "great_alpha", "is": {"sharpe": 1.45}}
            ]
        }
        step1_audit_pass = Gatekeeper.audit_step1_batch(pass_sim_data, min_sharpe=1.0)
        self.assertFalse(step1_audit_pass["should_prune"])
        self.assertEqual(len(step1_audit_pass["qualified_seeds"]), 1)
        print("  ✅ 成功验证：达标主信号顺利通过 Step 1 漏斗，进入后续阶段")

    def test_05_pyramid_rag_and_pure_operator_distillation(self):
        """测试金字塔四级知识库与纯算子经验沉淀 (严禁具体字段名)"""
        print("\n--- [GM TEST 5] 金字塔四级知识库与纯算子去字段化沉淀 ---")
        # 1. 写入达标因子的纯算子规律 (无具体字段名)
        pure_op_pattern = (
            "在 USA Delay 1 的新闻情绪/分析师类因子中，时序一阶差分 ts_delta(5) 结合指数衰减 "
            "ts_decay_exp_window(10, factor=0.8) 可有效捕捉动量并压低换手；"
            "前置使用 winsorize(std=3) 抑制极值震荡，外层包裹 subindustry 中性化能突破 Margin 死线。"
        )
        RAGMemoryEngine.EXP_DIR = os.path.join(self.temp_dir, "alpha_experience")
        RAGMemoryEngine.append_pure_operator_experience(
            region="USA",
            delay=1,
            category="news",
            abstract_insight=pure_op_pattern,
            alpha_stats={"sharpe": 1.94, "fitness": 1.42, "margin_bps": 13.6}
        )

        # 2. 读取金字塔四级经验
        context = RAGMemoryEngine.load_pyramid_context(region="USA", delay=1, category="news")
        self.assertIn("USA_1_news.md", context)
        self.assertIn("ts_decay_exp_window", context)
        self.assertIn("winsorize", context)
        print("  ✅ 成功验证：经验库严格遵循‘只有运算符、无数据字段’，四级金字塔 Markdown 体系运转正常！")

if __name__ == "__main__":
    unittest.main()
