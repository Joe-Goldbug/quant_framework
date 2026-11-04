"""
test_hardness_e2e.py
AEGIS v3.1 Hardness 终极加固版全链路沙箱测试
全面验证 5 大漏洞打补丁后的真实硬约束闭环：
1. 补丁 1: 真实 Brain checks 列表解析 (parse_brain_checks) + 最优候选选择 + 处方锁双向闭环
2. 补丁 2: 递归子树字段提取 + 真实字段画像加载 (列表入参不抹除) + 字段数硬上限 <= 3
3. 补丁 3: 跨批次历史骨架查重熔断 (COUNT >= 4 物理拦截)
4. 补丁 4: 历史最高水位线 Tabu 算法 (拦截 0.74->0.60->0.74 震荡) + 8 槽全量扫描 (拦截 Slot 5 夹带)
5. 补丁 5: 红队通行证表达式强绑定 (拦截旧证复用)
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.gatekeeper import Gatekeeper
from quant_framework.core.anti_laziness import AntiLazinessAuditor
from quant_framework.core.rag_memory import RAGMemoryEngine
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.sim_runner import SimBatchRunner

class TestAEGISHardnessSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fields_meta = {
            "nws_sent_score": {"type": "MATRIX", "domain": "[-1, 1]", "is_sparse": False, "description": "情绪评分"},
            "prob_10d": {"type": "MATRIX", "domain": "[0, 1]", "is_sparse": True, "description": "10日看涨概率"},
            "vec_topics": {"type": "VECTOR", "domain": "unbounded", "is_sparse": False, "description": "主题分布向量"},
            "news_volume": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "description": "新闻体量"}
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_gate2_deep_ast_and_list_metadata(self):
        """测试 补丁 2: 递归子树提取、列表元数据保留与字段超限"""
        print("\n--- [TEST 1] Gate 2: Deep AST & List Metadata Preservation ---")
        # 1. 传入 list 时，真实定义域不被抹除，依然拦截 [0, 1] 稀疏减 0.5
        list_fields = ["mean_sentiment_score_transfer"]
        e1 = "group_rank(subtract(mean_sentiment_score_transfer, 0.5), subindustry)"
        res1 = DimensionAuditor.audit_expression(e1, list_fields, category="news")
        self.assertFalse(res1["is_valid"], "传入 list 时稀疏 [0, 1] 减 0.5 必须被拦截！")
        self.assertIn("零值偏移违规", res1["issues"][0])
        print("  ✅ 成功验证：传入 list 时保留真实画像，稀疏减 0.5 被精准拦截")

        # 2. 深度嵌套子树 (winsorize 内部) 的双 [-1, 1] 裸乘拦截
        list_fields2 = ["sent_score_a", "sent_score_b"]
        e2 = "group_rank(multiply(winsorize(sent_score_a, std=2.5), ts_decay_linear(sent_score_b, 5)), subindustry)"
        res2 = DimensionAuditor.audit_expression(e2, list_fields2, category="news")
        self.assertFalse(res2["is_valid"], "嵌套双 [-1, 1] 裸乘必须被拦截！")
        self.assertIn("伪因果负负得正违规", res2["issues"][0])
        print("  ✅ 成功验证：嵌套在 winsorize/ts_decay 内的双 [-1, 1] 裸乘被递归拦截")

        # 3. 字段总数超过 4 个拦截 (允许 2~4 个正交字段，封杀 > 4 个)
        list_fields4 = ["f1", "f2", "f3", "f4"]
        e_valid_4 = "group_rank(divide(subtract(subtract(f1, f2), f3), f4), subindustry)"
        res_valid_4 = DimensionAuditor.audit_expression(e_valid_4, list_fields4, category="news")
        self.assertTrue(res_valid_4["is_valid"], f"允许 4 个字段构造复合异象，却被误拦截: {res_valid_4['issues']}")

        list_fields5 = ["f1", "f2", "f3", "f4", "f5"]
        e5 = "group_rank(add(add(add(f1, f2), add(f3, f4)), f5), subindustry)"
        res5 = DimensionAuditor.audit_expression(e5, list_fields5, category="news")
        self.assertFalse(res5["is_valid"], "字段总数超过 4 个必须被拦截！")
        self.assertIn("字段超限违规", res5["issues"][0])
        print("  ✅ 成功验证：允许 2~4 字段复合异象，使用了 5 个字段的大杂烩结构被硬性拦截 (<= 4)")

    def test_02_gate3_cross_batch_skeleton_exhaustion(self):
        """测试 补丁 3: 跨批次历史骨架查重熔断 (COUNT >= 4 拦截)"""
        print("\n--- [TEST 2] Gate 3: Cross-Batch Skeleton Exhaustion Breaker ---")
        db_path = os.path.join(self.temp_dir, "test_cross_batch.db")
        corrector = ASTSandboxCorrector(db_path)

        base_skel_expr = "group_rank(ts_decay_linear(nws_sent_score, {param}), subindustry)"
        
        # 模拟在 Batch 1 中测了 2 条该骨架 (单批严格每骨架 <= 2 条)
        batch1 = [
            base_skel_expr.format(param=5), base_skel_expr.format(param=10),
            "group_rank(ts_delta(nws_sent_score, 1), subindustry)",
            "group_rank(ts_delta(nws_sent_score, 2), subindustry)",
            "group_rank(ts_decay_exp_window(nws_sent_score, 10, factor=0.5), subindustry)",
            "group_rank(ts_decay_exp_window(nws_sent_score, 15, factor=0.5), subindustry)",
            "group_rank(s_log_1p(winsorize(nws_sent_score, std=2)), subindustry)",
            "group_rank(s_log_1p(winsorize(nws_sent_score, std=3)), subindustry)"
        ]
        corrector.check_and_record_batch(batch1, "USA", "TOP1000", 1)

        # 模拟在 Batch 2 中又测了 2 条该骨架 (累计达 4 条上限)
        batch2 = [
            base_skel_expr.format(param=15), base_skel_expr.format(param=20),
            "group_rank(ts_zscore(nws_sent_score, 10), subindustry)",
            "group_rank(ts_zscore(nws_sent_score, 20), subindustry)",
            "group_rank(reverse(ts_delta(nws_sent_score, 1)), subindustry)",
            "group_rank(reverse(ts_delta(nws_sent_score, 2)), subindustry)",
            "group_rank(power(nws_sent_score, 2), subindustry)",
            "group_rank(power(nws_sent_score, 4), subindustry)"
        ]
        corrector.check_and_record_batch(batch2, "USA", "TOP1000", 1)

        # 在 Batch 3 中企图继续改参数 (第 5 次使用该骨架) -> 必须被跨批次熔断！
        batch3 = [
            base_skel_expr.format(param=25),
            "group_rank(ts_mean(nws_sent_score, 10), subindustry)",
            "group_rank(ts_mean(nws_sent_score, 20), subindustry)",
            "group_rank(ts_std_dev(nws_sent_score, 10), subindustry)",
            "group_rank(ts_std_dev(nws_sent_score, 20), subindustry)",
            "group_rank(quantile(nws_sent_score, bins=5), subindustry)",
            "group_rank(quantile(nws_sent_score, bins=10), subindustry)",
            "group_rank(reverse(nws_sent_score), subindustry)"
        ]
        with self.assertRaises(ValueError) as cm:
            corrector.check_and_record_batch(batch3, "USA", "TOP1000", 1)
        self.assertIn("跨批次骨架耗尽熔断", str(cm.exception))
        print("  ✅ 成功验证：累计测试 >= 4 次的骨架在跨批次中被硬性熔断拦截！")

    def test_03_gate4_real_brain_checks_and_prescription_lock(self):
        """测试 补丁 1: 真实 Brain API checks 解析 + 处方锁双向闭环"""
        print("\n--- [TEST 3] Gate 4: Real Brain Checks Parsing & Prescription Lock ---")
        # 1. 模拟 WorldQuant Brain 真实的返回数据结构 (只有 is.checks 列表，绝无 ra 字典)
        real_brain_alpha = {
            "is": {
                "fitness": 1.25,
                "sharpe": 1.68,
                "turnover": 0.82,
                "checks": [
                    {"name": "CONCENTRATED_WEIGHT", "result": "FAIL", "value": 0.28},
                    {"name": "CLUSTER_SHARPE", "result": "WARNING", "value": 1.35},
                    {"name": "IS_LADDER_SHARPE", "result": "PASS", "value": 1.70}
                ]
            },
            "yearly_stats": [{"long_count": 800, "short_count": 50}]
        }

        # 验证 parse_brain_checks 能真实解析 checks 列表
        parsed = Gatekeeper.parse_brain_checks(real_brain_alpha)
        self.assertEqual(parsed["fail_count"], 1)
        self.assertTrue(parsed["cw_failed"])
        self.assertEqual(parsed["cluster_sharpe"], 1.35)
        print("  ✅ 成功验证：从真实 is.checks 列表解析出 CW 违规与 Cluster Sharpe (1.35)")

        # 验证病灶法医诊断
        rx = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics=real_brain_alpha["is"],
            checks_parsed=parsed,
            yearly_stats=real_brain_alpha["yearly_stats"],
            operator_count=6
        )
        self.assertIn("cw_bottleneck", rx["symptoms"])
        self.assertIn("cluster_collinearity", rx["symptoms"])
        self.assertIn("dead_weight_imbalance", rx["symptoms"])
        self.assertIn("turnover_overflow", rx["symptoms"])

        # 2. 验证处方锁双向闭环：将处方写入 authorized_mutations.json，若下批未遵守则阻断
        campaign_dir = os.path.join(self.temp_dir, "campaign_test")
        os.makedirs(campaign_dir, exist_ok=True)
        rx_file = os.path.join(campaign_dir, "authorized_mutations.json")
        with open(rx_file, 'w', encoding='utf-8') as f:
            json.dump(rx, f)

        # 构造未遵从处方的批次 (8 槽每种骨架 <= 2 条，使用未授权算子 如 ts_mean, ts_std_dev, quantile, power)
        disobedient_batch = [
            {"expression": f"group_rank(ts_mean(news_volume, {10+i}), subindustry)", "optimize_reason": f"未按处方调优 A{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(ts_std_dev(news_volume, {10+i}), subindustry)", "optimize_reason": f"未按处方调优 B{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(power(news_volume, {2+i}), subindustry)", "optimize_reason": f"未按处方调优 C{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(reverse(ts_mean(news_volume, {20+i})), subindustry)", "optimize_reason": f"未按处方调优 D{i}"}
            for i in range(2)
        ]
        self.assertEqual(len(disobedient_batch), 8)
        batch_file = os.path.join(campaign_dir, "batch_test.json")
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump({"items": disobedient_batch, "known_fields": ["news_volume"]}, f)

        with self.assertRaises(PermissionError) as cm:
            SimBatchRunner.verify_state_token_and_gates(
                batch_file_path=batch_file,
                expressions_data=disobedient_batch,
                known_fields=["news_volume"],
                category="news",
                region="USA",
                universe="TOP1000",
                delay=1,
                neutralization="NONE"
            )
        self.assertIn("Gate 4 处方锁拦截", str(cm.exception))
        print("  ✅ 成功验证：上一轮确诊病灶后，当前批次未遵从处方被 Gate 4 物理驳回！")

    def test_04_gate5_high_water_mark_and_all_slots_scan(self):
        """测试 补丁 4: 历史最高水位线防震荡 + 8 槽全量扫描"""
        print("\n--- [TEST 4] Gate 5: High-Water Mark & All-Slots Scan ---")
        ledger_path = os.path.join(self.temp_dir, "test_hwm_ledger.json")
        sig = "nws_sent_score"
        cat = "prob_10d"

        # 模拟震荡数据：0.74 -> 0.60 -> 0.74 (未突破历史最高水位线 0.74)
        AntiLazinessAuditor.update_ledger_and_check_tabu(ledger_path, "b1", sig, cat, 0.74, ["e1"])
        AntiLazinessAuditor.update_ledger_and_check_tabu(ledger_path, "b2", sig, cat, 0.60, ["e2"])
        res = AntiLazinessAuditor.update_ledger_and_check_tabu(ledger_path, "b3", sig, cat, 0.74, ["e3"])
        self.assertTrue(res["is_tabu"], "震荡未推高水位线必须触发 Tabu 熔断！")
        print("  ✅ 成功验证：0.74 -> 0.60 -> 0.74 震荡被 High-Water Mark 算法精准熔断！")

        # 验证全槽位扫描：将已锁定的字段对藏在 Slot 5，Gate 5 依然精准抓获
        campaign_dir = os.path.join(self.temp_dir, "campaign_tabu")
        os.makedirs(campaign_dir, exist_ok=True)
        sneaky_batch = [
            {"expression": f"group_rank(ts_decay_exp_window(news_volume, {10+i}, factor=0.8), subindustry)", "optimize_reason": f"合规槽位 A{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(ts_decay_linear(news_volume, {10+i}), subindustry)", "optimize_reason": f"合规槽位 B{i}"}
            for i in range(2)
        ] + [
            # Slot 5 偷偷夹带已处于 Tabu 锁定的字段组合！
            {"expression": f"group_rank(ts_decay_exp_window(multiply({sig}, {cat}), 10, factor=0.8), subindustry)", "optimize_reason": "夹带违规字段对"}
        ] + [
            {"expression": f"group_rank(ts_delta(news_volume, {3+i}), subindustry)", "optimize_reason": f"合规槽位 C{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(s_log_1p(winsorize(news_volume, std=3)), subindustry)", "optimize_reason": "合规槽位 D"}
        ]
        self.assertEqual(len(sneaky_batch), 8)
        batch_file = os.path.join(campaign_dir, "batch_sneaky.json")
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump({"items": sneaky_batch, "known_fields": [sig, cat, "news_volume"]}, f)

        with self.assertRaises(PermissionError) as cm:
            SimBatchRunner.verify_state_token_and_gates(
                batch_file_path=batch_file,
                expressions_data=sneaky_batch,
                known_fields=[sig, cat, "news_volume"],
                category="news",
                region="USA",
                universe="TOP1000",
                delay=1,
                neutralization="NONE",
                ledger_path=ledger_path
            )
        self.assertIn("Gate 5 拦截", str(cm.exception))
        self.assertIn("Slot 5", str(cm.exception))
        print("  ✅ 成功验证：隐藏在 Slot 5 的 Tabu 违规字段对被全槽位扫描精准拦截！")

    def test_05_gate1_stale_passport_invalidation(self):
        """测试 补丁 5: 红队通行证强绑定，拦截旧证复用"""
        print("\n--- [TEST 5] Gate 1: Anti-Stale Passport Strong Binding ---")
        campaign_dir = os.path.join(self.temp_dir, "campaign_passport")
        os.makedirs(campaign_dir, exist_ok=True)
        verdict_file = os.path.join(campaign_dir, "red_team_verdict.json")

        # 写入一份伪造的上一批旧通行证 (包含完全不同的 reviewed_expr)
        fake_stale_verdict = {
            "batch_size": 8,
            "all_passed": True,
            "summary_hash": "old_fake_hash_123456",
            "verdicts": [{"verdict": "PASS", "reviewed_expr": f"old_alpha_expr_{i}"} for i in range(8)]
        }
        with open(verdict_file, 'w', encoding='utf-8') as f:
            json.dump(fake_stale_verdict, f)

        # 当前批次待测 8 条表达式 (单批每种骨架 <= 2 条，使用未测过的独立测试字段 test_feed_x)
        rnd_field = f"test_feed_x_{int(time.time()*1000)%100000}"
        new_batch = [
            {"expression": f"group_rank(ts_decay_linear({rnd_field}, {10+i}), subindustry)", "optimize_reason": f"新批次变体 A{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(ts_decay_exp_window({rnd_field}, {10+i}, factor=0.8), subindustry)", "optimize_reason": f"新批次变体 B{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(ts_delta({rnd_field}, {3+i}), subindustry)", "optimize_reason": f"新批次变体 C{i}"}
            for i in range(2)
        ] + [
            {"expression": f"group_rank(s_log_1p(winsorize({rnd_field}, std={3+i})), subindustry)", "optimize_reason": f"新批次变体 D{i}"}
            for i in range(2)
        ]
        self.assertEqual(len(new_batch), 8)
        batch_file = os.path.join(campaign_dir, "batch_new.json")
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump({"items": new_batch, "known_fields": [rnd_field]}, f)

        # 运行门禁核验：必须检测到旧通行证不匹配并触发重新盲审
        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=batch_file,
            expressions_data=new_batch,
            known_fields=[rnd_field],
            category="news",
            region="USA",
            universe="TOP1000",
            delay=1,
            neutralization="NONE"
        )
        self.assertEqual(len(corrected), 8)

        # 检查 verdict_file 已被新签发的强绑定哈希覆盖
        with open(verdict_file, 'r', encoding='utf-8') as f:
            updated_verdict = json.load(f)
        self.assertNotEqual(updated_verdict["summary_hash"], "old_fake_hash_123456")
        self.assertEqual(updated_verdict["verdicts"][0]["reviewed_expr"], new_batch[0]["expression"])
        print("  ✅ 成功验证：旧批次通行证被强制作废并重新签发强绑定凭据！")

if __name__ == "__main__":
    unittest.main()
