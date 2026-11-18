"""
tests/test_falsifiable_probe.py
独立出题器测试: 白名单、命题校验、对照构造、闭环落地。
"""

import json
import os
import shutil
import tempfile
import unittest

from core.falsifiable_probe import (
    build_blind_payload, validate_probe, materialize, render_prompt, estimate_cost,
)


def _job(expr="group_rank(divide(ts_delta(fnd69_qta, 252), ts_mean(fnd69_qta, 252)), industry)"):
    return {
        "batch_id": "B00001-abcd1234",
        "batch_seq": 1,
        "spec": {"region": "USA", "universe": "TOP1000", "delay": 1, "neutralization": "SUBINDUSTRY"},
        "hypothesis": {
            "hypothesis_id": "HYP_ASSET_GROWTH",
            "counterparty": "承销动机的卖方",
            "causal_chain": "激进扩表被证伪后杀估值",
            "horizon_model": {"short_window": 5, "long_window": 252},
        },
        "field_profiles": {
            "fnd69_qta": {"domain": "[0, +inf)", "is_sparse": False,
                          "update_frequency": "QUARTERLY", "coverage": 0.92, "description": "总资产"},
        },
        "items": [{
            "slot": 1, "expression": expr,
            "optimize_reason": "资产扩张率异象, 预期提升 Sharpe 到 1.8",
            "mechanism_intents": [],
        }],
    }


def _valid_probe():
    return {
        "abstain": False,
        "independent_mechanism": "押注激进扩表的公司随后被市场证伪并杀估值, 做空扩表最快一档",
        "counterparty": "有承销与佣金动机的卖方",
        "mechanism_claim": "公司资产扩张速度越快, 后续相对收益越差",
        "falsifiable_predictions": [
            {"prediction": "移除扩张率差分后表现显著变差", "falsify_if": "与安慰剂无差异"},
            {"prediction": "长窗口比短窗口更稳", "falsify_if": "短窗口持续占优"},
        ],
        "decider": {"metric": "sharpe_2y", "min_delta": 0.3},
    }


class TestBlindPayload(unittest.TestCase):
    def test_no_metric_no_agent_narrative(self):
        """送审材料里绝不能出现指标, 也不能出现 agent 自己写的理由。"""
        payload = build_blind_payload(_job())
        txt = json.dumps(payload, ensure_ascii=False).lower()
        for banned in ("optimize_reason", "sharpe", "fitness", "margin", "turnover"):
            self.assertNotIn(banned, txt, f"送审材料泄漏 {banned}")

    def test_prompt_only_contains_whitelist(self):
        prompt = render_prompt(build_blind_payload(_job()))
        self.assertIn("ast_expression", prompt)
        self.assertIn("fields_dictionary", prompt)
        self.assertNotIn("optimize_reason", prompt)

    def test_field_profile_attached(self):
        p = build_blind_payload(_job())
        self.assertIn("fnd69_qta", p["fields_dictionary"])
        self.assertEqual(p["fields_dictionary"]["fnd69_qta"]["domain"], "[0, +inf)")

    def test_pre_registered_hypothesis_kept(self):
        """预注册假说是 Stage0 写的, 早于表达式, 属于 E1 证据, 允许送审。"""
        p = build_blind_payload(_job())
        self.assertEqual(p["preregistered_hypothesis"]["counterparty"], "承销动机的卖方")


class TestValidation(unittest.TestCase):
    def test_accepts_valid(self):
        out = validate_probe(_valid_probe())
        self.assertFalse(out["abstain"])
        self.assertEqual(out["decider"]["rule"], "double_difference")

    def test_abstain_is_first_class(self):
        """允许弃权, 避免它为了交差而编造命题。"""
        out = validate_probe({"abstain": True, "abstain_reason": "纯堆叠, 无语义"})
        self.assertTrue(out["abstain"])

    def test_rejects_short_claim(self):
        raw = _valid_probe()
        raw["mechanism_claim"] = "会涨"
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_short_mechanism(self):
        raw = _valid_probe()
        raw["independent_mechanism"] = "看涨"
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_missing_falsify_if(self):
        raw = _valid_probe()
        raw["falsifiable_predictions"][0].pop("falsify_if")
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_single_prediction(self):
        raw = _valid_probe()
        raw["falsifiable_predictions"] = raw["falsifiable_predictions"][:1]
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_bad_metric(self):
        raw = _valid_probe()
        raw["decider"]["metric"] = "pnl"
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_absurd_delta(self):
        raw = _valid_probe()
        raw["decider"]["min_delta"] = 9.9
        with self.assertRaises(ValueError):
            validate_probe(raw)

    def test_rejects_unsupported_observable(self):
        raw = _valid_probe()
        raw["observable"] = "regime_conditional"
        with self.assertRaises(ValueError):
            validate_probe(raw)


class TestMaterialize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="probe_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_end_to_end_creates_three_roles(self):
        res = materialize(self.tmp, _job(), validate_probe(_valid_probe()))
        self.assertTrue(res["ok"], res.get("reason"))
        roles = sorted(e["role"] for e in res["entries"])
        self.assertEqual(roles, ["parent", "placebo", "strip"])
        # 三条表达式互不相同, 且对照都源自母本结构
        exprs = {e["role"]: e["expression"] for e in res["entries"]}
        self.assertEqual(len(set(exprs.values())), 3)
        self.assertTrue(os.path.exists(res["batch_path"]))

    def test_batch_file_is_submittable(self):
        res = materialize(self.tmp, _job(), validate_probe(_valid_probe()))
        with open(res["batch_path"], "r", encoding="utf-8") as f:
            batch = json.load(f)
        self.assertEqual(len(batch["items"]), 3)
        self.assertEqual([i["type"] for i in batch["items"]],
                         ["parent_control", "ablation_control", "placebo_control"])
        self.assertEqual(batch["audit_run_id"], res["run_id"])
        for k in ("region", "universe", "delay", "known_fields", "items"):
            self.assertIn(k, batch)

    def test_single_operator_skeleton_refused(self):
        """单算子骨架无法构造双对照 -> 必须拒绝, 不能降级成单边对照。"""
        res = materialize(self.tmp, _job(expr="rank(fnd69_qta)"), validate_probe(_valid_probe()))
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "controls")

    def test_duplicate_claim_refused(self):
        materialize(self.tmp, _job(), validate_probe(_valid_probe()))
        res2 = materialize(self.tmp, _job(), validate_probe(_valid_probe()))
        self.assertFalse(res2["ok"])
        self.assertIn("record_probe", str(res2["stage"]))

    def test_abstain_not_materialized(self):
        res = materialize(self.tmp, _job(), {"abstain": True, "abstain_reason": "x"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "abstain")


class TestCost(unittest.TestCase):
    def test_cost_note_mentions_slots(self):
        c = estimate_cost()
        self.assertEqual(c["backtest_slots_per_probe"], 3)

    def test_materialize_ing_changes_nothing_on_abstain(self):
        tmp = tempfile.mkdtemp(prefix="probe_abstain_")
        try:
            materialize(tmp, _job(), {"abstain": True, "abstain_reason": "x"})
            self.assertFalse(os.path.exists(os.path.join(tmp, "audit_ledger.jsonl")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
