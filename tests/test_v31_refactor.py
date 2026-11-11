"""
tests/test_v31_refactor.py
AEGIS 3.1 极速吞吐与全维风控重构测试套件 (Refactor Verification Suite)
严格验证 AEGIS_HIGH_THROUGHPUT_REFACTOR_SPEC.md 落地核心指标:
1. Builtin Backend 内存直通与会话隔离 (0 磁盘文件轮询死锁)
2. AST 参数顺序自愈与纯常数微调硬拦截 (Anti-Trivial Tuning Gate)
3. Gatekeeper Master Good Flag 刚性收益单调性与时效门禁
4. Step 1 漏斗高门槛 0.05 秒极速早停 (Sharpe >= 1.2, Margin >= 5 bps)
5. LanceDB 原子化 QA 知识库半衰期衰减与回测反馈
6. 生产级 ALL PASS 严格汇报铁律 (绝对禁止私自发包提交)
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.agent_backends import BuiltinAgentBackend
from core.func_call_corrector import ASTSandboxCorrector
from core.gatekeeper import Gatekeeper
from core.sim_runner import SimBatchRunner
from core.qa_rag_tool import search_qa_knowledge, apply_experience_decay, feedback_experience_outcome
from knowledge_base.lancedb_manager import LanceDBQAManager


class TestV31Refactor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="aegis_v31_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_builtin_backend_direct_execution_no_file_lock(self):
        """[P0 验证] Builtin 后端内存直通，不依赖 .agent_tasks 磁盘轮询"""
        def dummy_handler(role, prompt, system_prompt=None, json_mode=False, context=None):
            return {"audit_passed": True, "clean_signals": []}

        backend = BuiltinAgentBackend(direct_handler=dummy_handler)
        self.assertIsNone(backend.tasks_dir)
        
        resp = backend.send_message_sync(
            role="aegis-tech-auditor",
            model="default",
            prompt="测试 Prompt",
            json_mode=True
        )
        self.assertIsInstance(resp, dict)
        self.assertTrue(resp.get("audit_passed", False))

    def test_02_ast_param_auto_healing(self):
        """[P1 验证] AST 毫秒级参数顺序自愈 (ts_decay_linear(10, x) -> ts_decay_linear(x, 10))"""
        corrector = ASTSandboxCorrector(":memory:")
        broken_expr = "group_rank(ts_decay_linear(10, subtract(test_f1, test_f2)), subindustry)"
        corrected = corrector.correct_expression(broken_expr)
        self.assertIn("ts_decay_linear(subtract(test_f1, test_f2), 10)", corrected)

    def test_03_ast_anti_trivial_tuning_gate(self):
        """[P1 验证] 纯数字常数微调硬拦截 (Anti-Trivial Tuning Gate)"""
        corrector = ASTSandboxCorrector(":memory:")
        parent_expr = "group_rank(ts_decay_linear(subtract(f1, f2), 10), subindustry)"
        
        # 变体仅仅微调了数字窗口 (10 -> 15, 10 -> 20, 10 -> 25)
        trivial_variants = [
            f"group_rank(ts_decay_linear(subtract(f1, f2), {w}), subindustry)"
            for w in [15, 20, 25, 30, 35, 40]
        ]
        
        with self.assertRaises(ValueError) as ctx:
            corrector.check_and_record_batch(
                expressions=trivial_variants,
                region="USA",
                universe="TOP1000",
                delay=1,
                neutralization="SUBINDUSTRY",
                parent_expression=parent_expr
            )
        self.assertIn("常数微调硬拦截", str(ctx.exception))

    def test_04_gatekeeper_master_good_flag(self):
        """[P1 验证] Master 级生产 Alpha 程序化 good_flag 评估器"""
        # 1. 构造一个完美的 10 年逐年正收益 Alpha
        perfect_alpha = {
            "expression": "group_neutralize(ts_decay_linear(subtract(f1, f2), 10), subindustry)",
            "sharpe": 1.75,
            "margin_bps": 12.5,
            "turnover": 0.15,
            "warning_count": 0,
            "fail_count": 0,
            "prod_corr": 0.42,
            "ladder_2y_sharpe": 1.80,
            "yearly_stats": [
                {"year": 2015 + i, "sharpe": 1.6 + 0.05 * i} for i in range(10)
            ],
            "checks": [
                {"name": "CONCENTRATED_WEIGHT", "result": "PASS"},
                {"name": "TURNOVER", "result": "PASS"}
            ]
        }
        res_perfect = Gatekeeper.compute_master_good_flag(perfect_alpha)
        self.assertTrue(res_perfect["good_flag"])
        self.assertTrue(res_perfect["is_all_pass_champion"])
        self.assertTrue(res_perfect["yearly_passed"])
        self.assertTrue(res_perfect["recent_2y_passed"])

        # 2. 构造一个严重过拟合/收益断崖的假 Alpha (2 年负收益，近 2 年夏普倒挂)
        bad_alpha = {
            "expression": "group_rank(ts_decay_linear(subtract(f1, f2), 10), subindustry)",
            "sharpe": 1.65, # 总夏普虽高
            "margin_bps": 4.0, # Margin 不足 8.0 bps
            "turnover": 0.50, # 换手率超标
            "warning_count": 1,
            "fail_count": 0,
            "prod_corr": 0.72, # 相关性超标
            "ladder_2y_sharpe": 0.85, # 近2年严重衰减
            "yearly_stats": [
                {"year": 2015, "sharpe": 3.5},
                {"year": 2016, "sharpe": 2.8},
                {"year": 2017, "sharpe": -0.5},
                {"year": 2018, "sharpe": -0.8},
                {"year": 2019, "sharpe": 0.4},
                {"year": 2020, "sharpe": 0.2},
            ]
        }
        res_bad = Gatekeeper.compute_master_good_flag(bad_alpha)
        self.assertFalse(res_bad["good_flag"])
        self.assertFalse(res_bad["is_all_pass_champion"])
        self.assertFalse(res_bad["yearly_passed"])
        self.assertFalse(res_bad["recent_2y_passed"])

    def test_05_step1_funnel_early_drop(self):
        """[P0 验证] Step 1 漏斗高门槛 (|Sharpe| >= 1.2 & Margin >= 5 bps) 0.05s 极速剪枝"""
        # 构造低劣批次 (最高 Sharpe 0.85 < 1.2)
        poor_results = [
            {
                "expression": f"expr_{i}",
                "is": {"sharpe": 0.5 + 0.05 * i, "margin": 0.0003, "turnover": 0.10, "checks": []}
            }
            for i in range(5)
        ]
        start_t = time.time()
        audit_res = Gatekeeper.audit_step1_batch(
            sim_result_data={"alpha_results": poor_results},
            expected_polarity=1,
            min_sharpe=1.2,
            min_margin_bps=5.0
        )
        elapsed = time.time() - start_t
        self.assertTrue(audit_res["should_prune"])
        self.assertEqual(audit_res["qualified_count"], 0)
        self.assertLess(elapsed, 0.5, "Step 1 漏斗判定耗时过长，未能实现极速早停！")

    def test_06_lancedb_half_life_decay_and_outcome_tracking(self):
        """[P2 验证] LanceDB 原子化 QA 知识库半衰期指数衰减与回测反馈"""
        db_path = os.path.join(self.test_dir, "lancedb_test")
        mgr = LanceDBQAManager(db_dir=db_path)
        
        # 插入两条测试经验: 一条是 30 天前的旧经验，一条是当下的新经验
        old_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 30 * 86400))
        now_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        records = [
            {
                "id": "QA_OLD_01",
                "question": "旧经验: 如何抑制回撤?",
                "answer": "旧方案",
                "symptom": "DRAWDOWN",
                "tags": "drawdown",
                "heat_score": 80.0,
                "created_at": old_time
            },
            {
                "id": "QA_NEW_01",
                "question": "新经验: 如何抑制回撤?",
                "answer": "新方案",
                "symptom": "DRAWDOWN",
                "tags": "drawdown",
                "heat_score": 80.0,
                "created_at": now_time
            }
        ]
        mgr.add_qa_records(records)
        
        # 1. 执行半衰期衰减 (半衰期 14 天，30 天经历两次半衰，预期 80 -> 20 左右)
        updated_cnt = mgr.apply_exponential_decay(half_life_days=14.0, min_heat=10.0)
        self.assertEqual(updated_cnt, 2)
        
        tbl = mgr.db.open_table(mgr.FORUM_TABLE)
        df = tbl.to_pandas()
        old_heat = float(df[df["id"] == "QA_OLD_01"]["heat_score"].values[0])
        new_heat = float(df[df["id"] == "QA_NEW_01"]["heat_score"].values[0])
        self.assertLess(old_heat, 30.0, f"旧经验未按半衰期衰减: {old_heat}")
        self.assertGreater(new_heat, 75.0, f"新经验不应过度衰减: {new_heat}")

        # 2. 测试回测反馈: QA_OLD_01 成功孵化生产级 Alpha，热度恢复 +15
        mgr.record_experience_outcome("QA_OLD_01", success=True)
        tbl = mgr.db.open_table(mgr.FORUM_TABLE)
        df = tbl.to_pandas()
        boosted_heat = float(df[df["id"] == "QA_OLD_01"]["heat_score"].values[0])
        self.assertAlmostEqual(boosted_heat, old_heat + 15.0, delta=0.5)

    def test_07_strict_reporting_protocol_zero_autonomous_submission(self):
        """[Spec 2.7 验证] 严禁系统私自提交平台池子，必须安全落盘并高亮汇报待人工复核"""
        champion_alpha = {
            "id": "ALPHA_CHAMPION_01",
            "expression": "group_neutralize(ts_decay_linear(subtract(feat_a, feat_b), 15), subindustry)",
            "sharpe": 1.68,
            "fitness": 1.35,
            "margin_bps": 10.5,
            "turnover": 0.12,
            "prod_corr": 0.45,
            "self_corr": 0.35,
            "fail_count": 0,
            "warning_count": 0,
            "yearly_stats": [[2015 + i, 1.5 + 0.05 * i] for i in range(10)],
            "is": {
                "sharpe": 1.68,
                "fitness": 1.35,
                "margin": 0.00105,
                "turnover": 0.12,
                "checks": []
            }
        }
        
        # 1. 终审核验 strict_zero_warnings=True (返回达标列表)
        approved_alphas = Gatekeeper.audit_final_alpha([champion_alpha], pcorr_max=0.65, strict_zero_warnings=True)
        self.assertEqual(len(approved_alphas), 1)

        # 2. 模拟落盘到 campaign_champions.json
        camp_dir = os.path.join(self.test_dir, "campaign")
        os.makedirs(camp_dir, exist_ok=True)
        champions_path = os.path.join(camp_dir, "campaign_champions.json")
        with open(champions_path, "w", encoding="utf-8") as f:
            json.dump([champion_alpha], f, ensure_ascii=False, indent=2)
            
        self.assertTrue(os.path.exists(champions_path))
        with open(champions_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["id"], "ALPHA_CHAMPION_01")
        # 验证该状态为未提交平台池 (待审就绪状态)
        self.assertNotIn("submitted_to_brain_pool", saved[0])

    def test_08_yearly_stats_2d_array_parsing(self):
        """[P0 核心修复验证] Brain 原生二维数组 [[year, sharpe, ...]] 正确解析，杜绝谎报 10 年 0 负夏普"""
        # 模拟 Brain /alphas/{id}/recordsets/yearly-stats 原生返回格式 (N1NzZ1jL 实测真实指标)
        brain_raw_alpha = {
            "id": "N1NzZ1jL",
            "yearly_stats": [
                [2014, 3.00, 0.25],
                [2015, 2.50, 0.20],
                [2016, 1.80, 0.15],
                [2017, 0.03, 0.02],
                [2018, 1.90, 0.16],
                [2019, 1.40, 0.11],
                [2020, -0.33, -0.0169],  # 2020 亏损！
                [2021, 1.85, 0.15],
                [2022, 0.30, 0.03],
                [2023, 1.31, 0.10],
            ],
            "metrics": {
                "sharpe": 1.35,
                "twoYearSharpe": 1.31,
                "fitness": 0.94,
                "margin": 0.0008,
                "turnover": 0.095,
                "checks": [
                    {"name": "SHARPE", "result": "FAIL", "value": 1.35, "limit": 1.58},
                    {"name": "FITNESS", "result": "FAIL", "value": 0.94, "limit": 1.0},
                    {"name": "TWO_YEAR_SHARPE", "result": "FAIL", "value": 1.31, "limit": 1.58},
                    {"name": "CLUSTER_SHARPE", "result": "WARNING", "value": 1.41, "limit": 1.58}
                ]
            }
        }

        # 1. 验证 SimBatchRunner.extract_golden_alpha_result 能正确解构二维数组
        golden = SimBatchRunner.extract_golden_alpha_result(brain_raw_alpha)
        self.assertEqual(len(golden["yearly_sharpe"]), 10)
        self.assertEqual(golden["yearly_sharpe"][0], ["2014", "3.00"])
        self.assertEqual(golden["yearly_sharpe"][6], ["2020", "-0.33"])
        self.assertEqual(golden["yearly_sharpe"][9], ["2023", "1.31"])

        # 2. 验证 compute_master_good_flag 精准捕捉 2020 负夏普，且近 2 年夏普未过线拦截
        gf = Gatekeeper.compute_master_good_flag(brain_raw_alpha)
        self.assertEqual(gf["neg_years_count"], 1)
        self.assertEqual(gf["total_years_count"], 10)
        self.assertFalse(gf["recent_2y_passed"])  # 1.31 < 1.58 必须拦截
        self.assertFalse(gf["good_flag"])  # 不合格必须被拦截
        self.assertFalse(gf["is_all_pass_champion"])

        # 3. 验证防御性拦截: 空年份列表绝对严禁误判为 0 年负夏普放行
        empty_alpha = {
            "id": "EMPTY_YEARS",
            "yearly_stats": [],
            "metrics": {"sharpe": 1.80, "margin": 0.0015, "turnover": 0.15}
        }
        gf_empty = Gatekeeper.compute_master_good_flag(empty_alpha)
        self.assertFalse(gf_empty["yearly_passed"], "空年份数据严禁通过 yearly_passed 门禁！")
        self.assertFalse(gf_empty["good_flag"])


if __name__ == "__main__":
    unittest.main()
