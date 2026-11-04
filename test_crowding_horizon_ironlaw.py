"""
test_crowding_horizon_ironlaw.py
针对「ProdCorr 0.7164 > 0.70 仍被放行」这一真实事故的回归测试套件。

覆盖 4 条破局机制:
    1. 铁律 A  冷热非对称配对 (FieldCrowdingProfiler / enforce_stage0_pairing)
    2. 铁律 B  非 rank 外壳占比 >= 40% (SwarmAuditor)
    3. 双窗口敏感性成对验证 (HorizonProbe: PLATEAU / SPIKE)
    4. ProdCorr 多字段名读取 + 未核实拦截 + 冠军资格硬过滤
"""

import os
import sys
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

from quant_framework.core.crowding_pairing import FieldCrowdingProfiler, enforce_stage0_pairing
from quant_framework.core.horizon_probe import HorizonProbe
from quant_framework.core.swarm_auditor import SwarmAuditor
from quant_framework.core.gatekeeper import Gatekeeper


FIELDS = {
    "total_assets": {"coverage": 0.98, "alpha_count": 480, "type": "MATRIX"},
    "revenue_total": {"coverage": 0.95, "alpha_count": 390, "type": "MATRIX"},
    "analyst_eps_mean": {"coverage": 0.88, "alpha_count": 210, "type": "MATRIX"},
    "litigation_word_count": {"coverage": 0.31, "alpha_count": 0, "type": "MATRIX"},
    "supply_chain_lead_time": {"coverage": 0.42, "alpha_count": 0, "type": "MATRIX"},
    "niche_segment_margin": {"coverage": 0.55, "alpha_count": 3, "type": "MATRIX"},
}


class TestIronLawA(unittest.TestCase):
    def test_crowding_tier_and_pairing(self):
        prof = FieldCrowdingProfiler(FIELDS)
        self.assertEqual(prof.tier("litigation_word_count"), "COLD")
        self.assertEqual(prof.tier("total_assets"), "HOT")
        ok = prof.classify(["litigation_word_count", "total_assets"])
        self.assertTrue(ok["is_asymmetric"])
        self.assertEqual(ok["main_anchor"], "litigation_word_count")
        self.assertEqual(ok["normalizer"], "total_assets")

        bad = prof.classify(["total_assets", "revenue_total"])
        self.assertFalse(bad["is_asymmetric"])
        self.assertIn("缺少低拥挤度主锚字段", bad["issues"][0])

    def test_zero_alpha_count_is_coldest_not_hottest(self):
        """回归: alpha_count=0 的字段曾被 bisect_right 误判为最拥挤"""
        prof = FieldCrowdingProfiler(FIELDS)
        self.assertLessEqual(prof.percentile("litigation_word_count"), 0.40)
        self.assertGreater(prof.percentile("total_assets"), 0.70)

    def test_enforce_rejects_crowded_seeds(self):
        prof = FieldCrowdingProfiler(FIELDS)
        seeds = [
            {"id": "S1", "fields_used": ["litigation_word_count", "total_assets"], "expression": "divide(a,b)"},
            {"id": "S2", "fields_used": ["total_assets", "revenue_total"], "expression": "divide(c,d)"},
        ]
        kept, rejected, report = enforce_stage0_pairing(seeds, prof, expected_count=2, strict=True)
        self.assertEqual([s["id"] for s in kept], ["S1"])
        self.assertEqual([r["id"] for r in rejected], ["S2"])
        self.assertFalse(report["should_reject_all"])

    def test_enforce_degrades_when_no_alpha_count(self):
        """字段画像缺失 alpha_count 时不得误杀全部种子"""
        prof = FieldCrowdingProfiler({"f1": {"coverage": 0.9}, "f2": {"coverage": 0.8}})
        seeds = [{"id": "S1", "fields_used": ["f1", "f2"], "expression": "subtract(f1,f2)"}]
        kept, rejected, report = enforce_stage0_pairing(seeds, prof, expected_count=1, strict=True)
        self.assertTrue(report["skipped"])
        self.assertEqual(len(kept), 1)


def _make_batch(pairs=10, non_rank_ratio=0.5):
    """构造 20 槽批次: 每 2 槽一组同骨架 (N, 2N)"""
    variants = []
    slot = 1
    n_non_rank = int(pairs * 2 * non_rank_ratio)
    for i in range(pairs):
        outer = "group_neutralize" if slot <= n_non_rank else "group_rank"
        for w in (5, 15):
            variants.append({
                "slot": slot,
                "expression": f"{outer}(ts_delta(field_{i}, {w}), subindustry)",
                "neutralization": "SUBINDUSTRY",
            })
            slot += 1
    return variants


class TestIronLawB(unittest.TestCase):
    def test_compliant_batch_passes(self):
        variants = _make_batch(10, 0.5)
        rep = SwarmAuditor.audit(variants, parallelism=20)
        self.assertTrue(rep["compliant"], rep["issues"])
        self.assertEqual(rep["non_rank_count"], 10)
        self.assertEqual(rep["paired_slots"], 20)

    def test_all_group_rank_is_blocked(self):
        variants = _make_batch(10, 0.0)
        with self.assertRaises(PermissionError):
            SwarmAuditor.enforce(variants, step=1, parallelism=20, strict=True)

    def test_reverse_group_rank_counts_as_rank(self):
        variants = [
            {"slot": 1, "expression": "reverse(group_rank(winsorize(f, std=3), subindustry))"},
            {"slot": 2, "expression": "group_zscore(g, subindustry)"},
        ]
        rep = SwarmAuditor.audit(variants, parallelism=2)
        self.assertEqual(rep["rank_outer_slots"], [1])
        self.assertEqual(rep["non_rank_outer_slots"], [2])


class TestHorizonProbe(unittest.TestCase):
    def test_detect_and_judge(self):
        variants = [
            {"slot": 1, "expression": "group_neutralize(ts_delta(f, 5), subindustry)"},
            {"slot": 2, "expression": "group_neutralize(ts_delta(f, 15), subindustry)"},
            {"slot": 3, "expression": "group_neutralize(ts_mean(g, 66), subindustry)"},
            {"slot": 4, "expression": "group_neutralize(ts_mean(g, 132), subindustry)"},
        ]
        pairs = HorizonProbe.detect_pairs(variants)
        self.assertEqual([p["slots"] for p in pairs], [(1, 2), (3, 4)])
        self.assertEqual(pairs[0]["windows"], (5, 15))
        self.assertEqual(pairs[1]["windows"], (66, 132))

        qualified = [
            {"expression": variants[0]["expression"], "sharpe": 1.45},
            {"expression": variants[1]["expression"], "sharpe": -0.20},   # 尖峰
            {"expression": variants[2]["expression"], "sharpe": 1.22},
            {"expression": variants[3]["expression"], "sharpe": 1.31},    # 参数高原
        ]
        verdicts = HorizonProbe.evaluate(variants, qualified, pairs)
        self.assertEqual([v["verdict"] for v in verdicts], ["SPIKE", "PLATEAU"])

        HorizonProbe.annotate(qualified, verdicts, pairs)
        self.assertEqual(qualified[0]["horizon_verdict"], "SPIKE")
        self.assertTrue(qualified[2]["plateau_pass"])

        kept, dropped = HorizonProbe.filter_parents(qualified)
        self.assertEqual(len(dropped), 2)
        self.assertEqual(len(kept), 2)


class TestProdCorrGate(unittest.TestCase):
    """核心回归: ProdCorr 0.7164 必须被拦截，且字段名不再是唯一入口"""

    def _res(self, **extra):
        base = {
            "expression": "group_neutralize(ts_delta(f, 5), subindustry)",
            "is": {
                "sharpe": 1.72,
                "fitness": 1.35,
                "margin": 0.0022,
                "turnover": 0.22,
                "checks": [],
            },
        }
        base["is"].update(extra.pop("is", {}))
        base.update(extra)
        return base

    def test_prodcorrelation_in_metrics_is_detected(self):
        res = self._res()
        res["is"]["prodCorrelation"] = 0.7164
        self.assertAlmostEqual(Gatekeeper.extract_prod_corr(res), 0.7164, places=4)
        passed = Gatekeeper.audit_final_alpha({"alpha_results": [res]}, region="USA")
        self.assertEqual(passed, [], "0.7164 >= 0.70 必须被拦截，旧实现会静默放行")

    def test_flat_pcorr_key_still_works(self):
        res = self._res(pcorr=0.58)
        self.assertAlmostEqual(Gatekeeper.extract_prod_corr(res), 0.58, places=4)
        passed = Gatekeeper.audit_final_alpha({"alpha_results": [res]}, region="USA")
        self.assertEqual(len(passed), 1)
        self.assertTrue(passed[0]["prod_corr_verified"])

    def test_unverified_prodcorr_is_blocked(self):
        res = self._res()
        self.assertIsNone(Gatekeeper.extract_prod_corr(res))
        passed = Gatekeeper.audit_final_alpha({"alpha_results": [res]}, region="USA")
        self.assertEqual(passed, [], "相关性未核实不得放行提交")

    def test_pcorr_overflow_prescription(self):
        verdict = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics={"turnover": 0.46},
            checks_parsed={},
            yearly_stats=[],
            operator_count=7,
            prod_corr=0.7164,
        )
        self.assertIn("prod_corr_overflow", verdict["symptoms"])
        self.assertIn("group_zscore", verdict["allowed_mutations"])
        # 换手 46% (>40%) 应提前解锁状态记忆算子
        self.assertIn("trade_when", verdict["allowed_mutations"])


class TestChampionEligibility(unittest.TestCase):
    def setUp(self):
        from quant_framework.main import AegisPipelineController
        self.ctl = AegisPipelineController.__new__(AegisPipelineController)
        self.ctl.region = "GLB"

    def _alpha(self, prod_corr=0.55, ops=5, margin_bps=20.0):
        expr = "group_neutralize(ts_delta(f, 66), subindustry)"
        return {
            "expression": expr,
            "sharpe": 1.70,
            "fitness": 1.30,
            "margin_bps": margin_bps,
            "prod_corr": prod_corr,
            "operator_count": ops,
        }

    def test_pcorr_over_limit_not_champion(self):
        elig = self.ctl.champion_eligibility(self._alpha(prod_corr=0.7164))
        self.assertFalse(elig["eligible"])
        self.assertTrue(any("ProdCorr" in r for r in elig["reasons"]))

    def test_unverified_not_champion(self):
        a = self._alpha()
        a.pop("prod_corr")
        elig = self.ctl.champion_eligibility(a)
        self.assertEqual(elig["status"], "PENDING_PROD_CORR_CHECK")
        self.assertFalse(elig["prod_corr_verified"])
        self.assertTrue(elig["eligible"])

    def test_operator_count_penalty(self):
        elig = self.ctl.champion_eligibility(self._alpha(ops=9))
        self.assertFalse(elig["eligible"])

    def test_score_prefers_low_corr(self):
        good = self.ctl.compute_champion_score(self._alpha(prod_corr=0.30))
        bad = self.ctl.compute_champion_score(self._alpha(prod_corr=0.69))
        self.assertGreater(good, bad)

    def test_margin_premium_flag(self):
        low = self.ctl.champion_eligibility(self._alpha(margin_bps=16.0))
        high = self.ctl.champion_eligibility(self._alpha(margin_bps=20.0))
        self.assertFalse(low["margin_premium_ok"])
        self.assertTrue(high["margin_premium_ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
