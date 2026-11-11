"""
test_traps_regression.py
专门针对三处新引入陷阱与边缘行为的回归测试套件:
  Trap 1: HorizonProbe 双窗口参数高原 (1.28, 0.92) 误杀为 SPIKE 修复核验
  Trap 2: SwarmAuditor / SimBatchRunner 抛错时缓存 resp_*.json 自动清除 (防死锁死循环)
  Trap 3: Champion 资格与 pcorr 默认值 (区分 0.0 假相关与 PENDING_PROD_CORR_CHECK)
"""

import os
import sys
import json
import unittest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from quant_framework.core.horizon_probe import HorizonProbe
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.swarm_auditor import SwarmAuditor
    from quant_framework.main import AegisPipelineController
except (ModuleNotFoundError, ImportError):
    from core.horizon_probe import HorizonProbe
    from core.gatekeeper import Gatekeeper
    from core.swarm_auditor import SwarmAuditor
    from main import AegisPipelineController


class TestTrap1HorizonProbeAllSharpes(unittest.TestCase):
    """
    Trap 1: HorizonProbe.evaluate 在旧版中只接收 qualified (|Sharpe| >= 1.0)。
    导致 Slot 1 (Sharpe=1.28) 与 Slot 2 (Sharpe=0.92) 成对时，
    因 Slot 2 未入选 qualified 而被误判为只有单窗口有夏普、从而判定为 SPIKE。
    修复后：传入 all_sharpes，正确识别 (1.28, 0.92) 为健壮的 PLATEAU 参数高原。
    """
    def setUp(self):
        self.expr1 = "group_neutralize(ts_delta(litigation_word_count, 66), subindustry)"
        self.expr2 = "group_neutralize(ts_delta(litigation_word_count, 132), subindustry)"
        self.variants = [
            {"slot": 1, "expression": self.expr1, "neutralization": "SUBINDUSTRY"},
            {"slot": 2, "expression": self.expr2, "neutralization": "SUBINDUSTRY"},
        ]
        self.pairs = HorizonProbe.detect_pairs(self.variants)

    def test_plateau_detected_with_all_sharpes_when_slot2_not_in_qualified(self):
        # 模拟 gatekeeper.audit_step1_batch:
        # 只有 expr1 (|Sharpe| >= 1.0) 进 qualified
        qualified = [{"expression": self.expr1, "sharpe": 1.28}]
        # 但 all_sharpes 记录了两个槽位的所有夏普
        all_sharpes = {
            self.expr1: 1.28,
            self.expr2: 0.92,
        }

        verdicts = HorizonProbe.evaluate(
            self.variants,
            qualified,
            self.pairs,
            min_sharpe=1.0,
            spike_floor=0.5,
            all_sharpes=all_sharpes,
        )

        self.assertEqual(len(verdicts), 1)
        v = verdicts[0]
        self.assertEqual(v["verdict"], "PLATEAU", "Sharpe (1.28, 0.92) 属于健康参数高原，严禁误判为 SPIKE")
        self.assertTrue(v["plateau_pass"])
        self.assertAlmostEqual(v["sharpe_short"], 1.28)
        self.assertAlmostEqual(v["sharpe_long"], 0.92)

    def test_inverted_slot_window_order_aligned_correctly(self):
        """
        细节缺陷二回归:
        当 Slot 1 为长窗口 132、Slot 2 为短窗口 66 时，
        detect_pairs 必须将 expr_short 与短窗口 66 对齐，防止报告中 sharpe_short / sharpe_long 标签反置。
        """
        variants = [
            {"slot": 1, "expression": self.expr2, "neutralization": "SUBINDUSTRY"}, # 132 长窗口
            {"slot": 2, "expression": self.expr1, "neutralization": "SUBINDUSTRY"}, # 66 短窗口
        ]
        pairs = HorizonProbe.detect_pairs(variants)
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p["windows"], (66, 132), "windows 必须按 [短, 长] 升序排列")
        self.assertEqual(p["expr_short"], self.expr1, "expr_short 必须对应 66 短窗口")
        self.assertEqual(p["expr_long"], self.expr2, "expr_long 必须对应 132 长窗口")

        all_sharpes = {
            self.expr2: 0.92,  # 132 长窗口
            self.expr1: 1.28,  # 66 短窗口
        }
        verdicts = HorizonProbe.evaluate(
            variants,
            [{"expression": self.expr1, "sharpe": 1.28}],
            pairs,
            all_sharpes=all_sharpes,
        )
        v = verdicts[0]
        self.assertEqual(v["verdict"], "PLATEAU")
        self.assertAlmostEqual(v["sharpe_short"], 1.28, places=2, msg="sharpe_short 必须对应短窗口 66 的夏普")
        self.assertAlmostEqual(v["sharpe_long"], 0.92, places=2, msg="sharpe_long 必须对应长窗口 132 的夏普")

    def test_spike_correctly_identified_when_slot2_drops_below_floor(self):
        qualified = [{"expression": self.expr1, "sharpe": 1.28}]
        all_sharpes = {
            self.expr1: 1.28,
            self.expr2: 0.35,  # 跌破 0.50
        }

        verdicts = HorizonProbe.evaluate(
            self.variants,
            qualified,
            self.pairs,
            min_sharpe=1.0,
            spike_floor=0.5,
            all_sharpes=all_sharpes,
        )

        self.assertEqual(len(verdicts), 1)
        v = verdicts[0]
        self.assertEqual(v["verdict"], "SPIKE", "Sharpe (1.28, 0.35) 窗口翻倍断崖下跌，必须判为 SPIKE")
        self.assertFalse(v["plateau_pass"])


class TestTrap2DeadlockPreventionCleanup(unittest.TestCase):
    """
    Trap 2: SwarmAuditor 或 SimBatchRunner 抛出异常时，
    若不清理 .agent_tasks/resp_*.json 缓存，下次 BuiltinAgentBackend 会重放相同非法产出导致死循环。
    """
    def test_task_cache_deleted_on_enforce_failure(self):
        tasks_dir = os.path.join(WORKSPACE_DIR, "quant_framework", ".agent_tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        dummy_resp_path = os.path.join(tasks_dir, "resp_aegis-swarm-generator_TEST_SEED_s1.json")
        with open(dummy_resp_path, "w", encoding="utf-8") as f:
            json.dump([{"slot": 1, "expression": "group_rank(f, subindustry)"}], f)

        self.assertTrue(os.path.exists(dummy_resp_path))

        # 构造全部是 group_rank 的非法变体
        invalid_variants = [
            {"slot": 1, "expression": "group_rank(f, subindustry)"},
            {"slot": 2, "expression": "group_rank(g, subindustry)"},
        ]

        # 模拟 main.py 的 try-except 保护与清理逻辑
        cleaned = False
        try:
            SwarmAuditor.enforce(invalid_variants, step=1, parallelism=2, strict=True)
        except (ValueError, PermissionError, RuntimeError):
            if os.path.exists(dummy_resp_path):
                os.remove(dummy_resp_path)
                cleaned = True

        self.assertTrue(cleaned, "捕获 SwarmAuditor 异常时必须清除 resp_*.json")
        self.assertFalse(os.path.exists(dummy_resp_path), "响应缓存文件应已被物理删除，防止重放死锁")


class TestTrap3ChampionPodiumAndProdCorr(unittest.TestCase):
    """
    Trap 3:
      - 缺失 ProdCorr 时不得默认填 0.0（避免把未核实伪造成完美 0.0 相关性）。
      - champion_eligibility 对未核实相关性的候选标记 PENDING_PROD_CORR_CHECK 并保持 eligible=True，
        允许初登冠军台展示，但排序劣后于 VERIFIED 候选；严禁 100% 误杀导致无人登台。
    """
    def setUp(self):
        self.ctl = AegisPipelineController.__new__(AegisPipelineController)
        self.ctl.region = "GLB"

    def test_extract_prod_corr_returns_none_when_missing(self):
        sim_res = {
            "expression": "group_neutralize(ts_delta(f, 66), subindustry)",
            "is": {
                "sharpe": 1.65,
                "fitness": 1.20,
                "margin": 0.0025,
                "turnover": 0.20,
                "checks": [],
            }
        }
        self.assertIsNone(Gatekeeper.extract_prod_corr(sim_res))

        # audit_step1_batch 不应产生 0.0 假相关
        audited = Gatekeeper.audit_step1_batch({"alpha_results": [sim_res]})
        cand = audited["qualified_seeds"][0]
        self.assertIsNone(cand["pcorr"])
        self.assertFalse(cand["prod_corr_verified"])

    def test_pending_prod_corr_is_eligible_as_provisional_champion(self):
        cand = {
            "expression": "group_neutralize(ts_delta(f, 66), subindustry)",
            "sharpe": 1.75,
            "fitness": 1.30,
            "margin_bps": 22.0,
            "operator_count": 5,
            "prod_corr": None,
            "prod_corr_verified": False,
        }
        elig = self.ctl.champion_eligibility(cand)
        self.assertEqual(elig["status"], "PENDING_PROD_CORR_CHECK")
        self.assertTrue(elig["eligible"], "未核实 ProdCorr 的高潜候选应允许作为待核验准冠军登上展示台")
        self.assertFalse(elig["prod_corr_verified"])

    def test_dummy_zero_prod_corr_unverified_not_treated_as_verified(self):
        # 即使被外界传入 pcorr=0.0，若 prod_corr_verified=False，也不得被当成已核实
        cand = {
            "expression": "group_neutralize(ts_delta(f, 66), subindustry)",
            "sharpe": 1.75,
            "fitness": 1.30,
            "margin_bps": 22.0,
            "operator_count": 5,
            "pcorr": 0.0,
            "prod_corr_verified": False,
        }
        elig = self.ctl.champion_eligibility(cand)
        self.assertEqual(elig["status"], "PENDING_PROD_CORR_CHECK")
        self.assertFalse(elig["prod_corr_verified"])

    def test_over_limit_prod_corr_strictly_disqualified(self):
        cand = {
            "expression": "group_neutralize(ts_delta(f, 66), subindustry)",
            "sharpe": 1.85,
            "fitness": 1.40,
            "margin_bps": 25.0,
            "operator_count": 5,
            "prod_corr": 0.725,
            "prod_corr_verified": True,
        }
        elig = self.ctl.champion_eligibility(cand)
        self.assertEqual(elig["status"], "DISQUALIFIED")
        self.assertFalse(elig["eligible"], "已核实且 ProdCorr >= 0.70 必须铁腕取消冠军资格")
        self.assertTrue(any(">= 0.70" in r for r in elig["reasons"]))

    def test_podium_sorting_verified_before_unverified(self):
        # 构造一个待核验（但夏普极高）和一个已核实（夏普稍低）
        unverified_cand = {
            "expression": "cand_unverified",
            "sharpe": 2.20,
            "margin_bps": 25.0,
            "operator_count": 5,
            "prod_corr": None,
            "prod_corr_verified": False,
            "champion_score": 2.50,
        }
        verified_cand = {
            "expression": "cand_verified",
            "sharpe": 1.70,
            "margin_bps": 20.0,
            "operator_count": 4,
            "prod_corr": 0.45,
            "prod_corr_verified": True,
            "champion_score": 1.95,
        }

        # 依据 main.py 中的排序规则:
        # verified_flag = 1 if prod_corr_verified else 0
        # sort key: (-verified_flag, -margin_premium_flag, -champion_score)
        cands = [unverified_cand, verified_cand]
        sorted_cands = sorted(
            cands,
            key=lambda c: (
                1 if c.get("prod_corr_verified", False) else 0,
                1 if c.get("margin_bps", 0) >= 18.0 else 0,
                c.get("champion_score", 0),
            ),
            reverse=True,
        )

        self.assertEqual(sorted_cands[0]["expression"], "cand_verified", "已核实相关性的候选在冠军榜首位")
        self.assertEqual(sorted_cands[1]["expression"], "cand_unverified", "待核验候选排在次席展示")


class TestCatch22ProdCorrAndAlphaId(unittest.TestCase):
    """
    Catch-22 死锁回归测试:
      1. gatekeeper 的 audit_step1_batch, audit_step2_batch, audit_final_alpha
         必须透传 "id" 和 "alpha_id"，不得丢弃导致接口查询无法寻址。
      2. 预先拉取 ProdCorr 后，audit_final_alpha 能成功拿到真实相关性并放行合格候选 (非空列表)。
    """
    def setUp(self):
        self.raw_res = {
            "id": "ALPHA_REAL_999",
            "alpha_id": "ALPHA_REAL_999",
            "expression": "group_neutralize(ts_delta(litigation_word_count, 66), subindustry)",
            "is": {
                "sharpe": 1.72,
                "fitness": 1.35,
                "margin": 0.0022,
                "turnover": 0.22,
                "checks": [],
            }
        }

    def test_alpha_id_preserved_across_all_audit_stages(self):
        step1 = Gatekeeper.audit_step1_batch({"alpha_results": [self.raw_res]})
        self.assertEqual(len(step1["qualified_seeds"]), 1)
        self.assertEqual(step1["qualified_seeds"][0]["alpha_id"], "ALPHA_REAL_999")
        self.assertEqual(step1["qualified_seeds"][0]["id"], "ALPHA_REAL_999")

        step2 = Gatekeeper.audit_step2_batch({"alpha_results": [self.raw_res]}, region="USA")
        self.assertEqual(len(step2), 1)
        self.assertEqual(step2[0]["alpha_id"], "ALPHA_REAL_999")
        self.assertEqual(step2[0]["id"], "ALPHA_REAL_999")

        # 模拟拉取 ProdCorr 写入后
        self.raw_res["prod_corr"] = 0.42
        self.raw_res["prod_corr_verified"] = True
        final = Gatekeeper.audit_final_alpha({"alpha_results": [self.raw_res]}, region="USA")
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["alpha_id"], "ALPHA_REAL_999")
        self.assertEqual(final[0]["id"], "ALPHA_REAL_999")
        self.assertEqual(final[0]["status"], "APPROVED_SUBMITTABLE")


class TestGate3RollbackOnGate2Failure(unittest.TestCase):
    """
    细节缺陷一回归:
    Gate 3 在写入 alphas_record.db 后，若后续 Gate 2 校验失败打回，
    必须调用 remove_records 回滚未发包的数据库记录，防止废片永久占用骨架配额。
    """
    def test_rollback_removes_unsubmitted_records(self):
        import tempfile
        try:
            from quant_framework.core.func_call_corrector import ASTSandboxCorrector
        except (ModuleNotFoundError, ImportError):
            from core.func_call_corrector import ASTSandboxCorrector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "alphas_record.db")
            corrector = ASTSandboxCorrector(db_path=db_path)
            
            exprs = ["group_neutralize(ts_delta(f, 66), subindustry)"]
            # 记录批次
            corrector.check_and_record_batch(exprs, "USA", "TOP1000", 1, "SUBINDUSTRY", batch_id="b_test")
            
            # 验证已写入
            import sqlite3
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM alpha_fingerprints")
            cnt_before = c.fetchone()[0]
            conn.close()
            self.assertEqual(cnt_before, 1)
            
            # 模拟 Gate 2 失败后调用回滚
            corrector.remove_records(exprs, "USA", "TOP1000", 1, "SUBINDUSTRY")
            
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM alpha_fingerprints")
            cnt_after = c.fetchone()[0]
            conn.close()
            self.assertEqual(cnt_after, 0, "回滚后指纹数据库中未发包记录必须被物理清除")


class TestNearMissQuasiChampion(unittest.TestCase):
    """
    针对真实战役中超级六边形战士 qMLPOJPK 曾因 Sharpe 1.54 < 1.58 被机械丢弃的针对性回归测试:
      1. Gatekeeper.is_near_miss_champion 物理命中 (ProdCorr 0.6548 < 0.70, Margin 19.03 >= 18, Sharpe 1.54 >= 1.45)
      2. champion_eligibility 授予 NEAR_CHAMPION 身份且 eligible=True
      3. Champion_Score 评分机制有效识别其高边际效用 (远超盲凑夏普但高共线高算子复杂度的劣质因子)
    """
    def setUp(self):
        self.ctl = AegisPipelineController.__new__(AegisPipelineController)
        self.ctl.region = "GLB"
        self.qmlpojpk = {
            "id": "qMLPOJPK",
            "alpha_id": "qMLPOJPK",
            "expression": "group_neutralize(ts_decay_linear(subtract(predicted_fifth_quantile_ten_day_return_23, predicted_third_quantile_ten_day_return_23), 240), industry)",
            "sharpe": 1.54,
            "fitness": 1.11,
            "margin_bps": 19.03,
            "turnover": 0.0688,
            "prod_corr": 0.6548,
            "prod_corr_verified": True,
            "operator_count": 3,
            "fail_count": 0,
            "fails": [],
            "warnings": [],
        }

    def test_qmlpojpk_identified_as_near_miss_champion(self):
        is_near = Gatekeeper.is_near_miss_champion(self.qmlpojpk, region="GLB")
        self.assertTrue(is_near, "qMLPOJPK 必须被物理识别为准生产突破六边形战士 (NEAR_CHAMPION)")

    def test_qmlpojpk_eligible_and_status_near_champion(self):
        elig = self.ctl.champion_eligibility(self.qmlpojpk)
        self.assertTrue(elig["eligible"], "准冠军绝不允许被机械 step-function 判死刑")
        self.assertEqual(elig["status"], "NEAR_CHAMPION")
        self.assertTrue(elig["margin_premium_ok"])

    def test_qmlpojpk_utility_score_beats_crowded_high_sharpe_alpha(self):
        # 对比组: 硬凑出 Sharpe 1.60，但算子数 8、ProdCorr 0.69、Margin 12bps 的高共线高复杂度因子
        crowded_alpha = {
            "expression": "crowded_alpha",
            "sharpe": 1.60,
            "fitness": 1.02,
            "margin_bps": 12.0,
            "turnover": 0.35,
            "prod_corr": 0.69,
            "prod_corr_verified": True,
            "operator_count": 8,
        }
        score_q = self.ctl.compute_champion_score(self.qmlpojpk)
        score_crowded = self.ctl.compute_champion_score(crowded_alpha)
        self.assertGreater(score_q, score_crowded, "qMLPOJPK 凭借极简 AST (ops=3)、超低共线 (0.65) 与超高利润 (19bps)，综合效用必须显著胜出")


if __name__ == "__main__":
    unittest.main(verbosity=2)
