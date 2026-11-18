"""
tests/test_audit_bus.py
审计总线回归测试 —— 逐条对应审查意见 P0-1 / P0-2 / P0-3 / P1。
"""

import inspect
import json
import os
import shutil
import tempfile
import time
import unittest

from core.audit_bus import (
    AuditBus, SampleDecision, ST_CORROBORATED, ST_FALSIFIED, ST_INCONCLUSIVE,
    mechanism_signature,
)


def _items(n=20, prefix="f"):
    return [{"expression": f"rank(ts_delta({prefix}{i},5))"} for i in range(n)]


class AuditBusTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="auditbus_test_")
        self.bus = AuditBus(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------- helpers ----------------
    def _submit(self, n=20, prefix="f", **kw):
        t = self.bus.begin_batch(_items(n, prefix), {"region": "USA", "universe": "TOP1000", "delay": 1})
        d = self.bus.decide_sampling(t, **kw)
        return t, d

    def _probe(self, pid="P-1", expr="rank(ts_delta(a,5))", intents=("TEMPORAL_DECAY",),
               roles=None, horizon=None, delta=0.3, slots=4):
        return self.bus.record_probe({
            "probe_id": pid, "expression": expr, "hypothesis_id": "H1",
            "mechanism_intents": list(intents),
            "field_roles": roles if roles is not None else [{"role": "SIGNAL", "type": "MATRIX"}],
            "horizon_model": horizon or {"short_window": 5, "long_window": 20},
            "mechanism_claim": "短窗口优于长窗口", "slots": slots,
            "decider": {"metric": "sharpe_2y", "min_delta": delta},
        })

    def _result(self, rows, name="res.json"):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": [
                {"code": e, "alpha_id": f"A{i}", "metrics": {"sharpe": s, "two_year_sharpe": s2}}
                for i, (e, s, s2) in enumerate(rows)
            ]}, f)
        return p


class TestP01Wiring(AuditBusTestBase):
    """P0-1: 抽样必须在回测前完成, 且不依赖任何指标。"""

    def test_sampling_before_backtest(self):
        # begin_batch 只接收表达式与实验规格, 签名里没有任何指标参数
        sig = inspect.signature(self.bus.begin_batch)
        self.assertNotIn("sharpe", str(sig))
        self.assertNotIn("metrics", str(sig))

    def test_sampling_rate_and_gap(self):
        hits = 0
        for i in range(40):
            _, d = self._submit(prefix=f"g{i}")
            hits += 1 if d.sampled else 0
        self.assertGreater(hits, 0, "40 批从未命中, 抽样器失效")
        self.assertLess(hits, 10, "命中率远超 5%, 抽样配置异常")

    def test_min_gap_enforced(self):
        seq = []
        for i in range(30):
            t, d = self._submit(prefix=f"h{i}")
            if d.sampled:
                seq.append(t.batch_seq)
        for a, b in zip(seq, seq[1:]):
            self.assertGreaterEqual(b - a, 4, "最小批次间隔未生效")


class TestP02Outcome(AuditBusTestBase):
    """P0-2: 裁决不可伪造、不可重复、不接受手工结论。"""

    def test_signature_has_no_verdict_param(self):
        params = list(inspect.signature(self.bus.record_outcome).parameters)
        self.assertEqual(params, ["run_id", "result_path"])

    def test_unknown_run_rejected(self):
        p = self._result([("rank(x)", 1.0, 1.0)])
        with self.assertRaises(ValueError):
            self.bus.record_outcome("RUN-FAKE", p)

    def test_unknown_probe_rejected(self):
        with self.assertRaises(ValueError):
            self.bus.open_experiment("P-NOPE", {"entries": [{"role": "parent", "expression": "rank(x)"}]})

    def test_duplicate_outcome_rejected(self):
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "placebo", "expression": "rank(ts_delta(z,5))"},
        ]})
        rid = exp["payload"]["run_id"]
        p = self._result([("rank(ts_delta(a,5))", 1.4, 1.30), ("rank(ts_delta(z,5))", 1.1, 1.05)])
        self.bus.record_outcome(rid, p)
        with self.assertRaises(ValueError):
            self.bus.record_outcome(rid, p)

    def test_duplicate_experiment_rejected(self):
        self._probe()
        self.bus.open_experiment("P-1", {"entries": [{"role": "parent", "expression": "rank(ts_delta(a,5))"}]})
        with self.assertRaises(ValueError):
            self.bus.open_experiment("P-1", {"entries": [{"role": "parent", "expression": "rank(ts_delta(a,9))"}]})

    def test_missing_result_file(self):
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [{"role": "parent", "expression": "rank(a)"}]})
        with self.assertRaises(FileNotFoundError):
            self.bus.record_outcome(exp["payload"]["run_id"], os.path.join(self.tmp, "nope.json"))

    def test_verdict_computed_corroborated(self):
        """双差分: (M-S)-(M-P) = P-S = 0.60 >= 0.20"""
        self._probe(delta=0.2)
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "strip", "expression": "rank(add(a,0))"},
            {"role": "placebo", "expression": "add(ts_delta(a,5),0)"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 1.9, 1.80),
                          ("rank(add(a,0))", 1.2, 1.10),
                          ("add(ts_delta(a,5),0)", 1.8, 1.70)])
        rec = self.bus.record_outcome(exp["payload"]["run_id"], p)
        self.assertEqual(rec["payload"]["verdict"], ST_CORROBORATED)
        self.assertAlmostEqual(rec["payload"]["evidence"]["net_mechanism_effect"], 0.60, places=2)

    def test_verdict_computed_falsified(self):
        """拆机制与拆装饰掉分几乎一样 -> 机制不成立"""
        self._probe(delta=0.5)
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "strip", "expression": "rank(add(a,0))"},
            {"role": "placebo", "expression": "add(ts_delta(a,5),0)"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 1.9, 1.80),
                          ("rank(add(a,0))", 1.2, 1.15),
                          ("add(ts_delta(a,5),0)", 1.3, 1.20)])
        rec = self.bus.record_outcome(exp["payload"]["run_id"], p)
        self.assertEqual(rec["payload"]["verdict"], ST_FALSIFIED)

    def test_complexity_artifact_flagged(self):
        """拆什么都掉同样多的分 = 过拟合意大利面, 不是机制。"""
        self._probe(delta=0.3)
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "strip", "expression": "rank(add(a,0))"},
            {"role": "placebo", "expression": "add(ts_delta(a,5),0)"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 2.0, 1.90),
                          ("rank(add(a,0))", 1.5, 1.45),
                          ("add(ts_delta(a,5),0)", 1.6, 1.50)])
        ev = self.bus.record_outcome(exp["payload"]["run_id"], p)["payload"]["evidence"]
        self.assertTrue(ev["complexity_artifact"])
        self.assertGreaterEqual(ev["parent_minus_strip"], 0.3)
        self.assertLess(ev["net_mechanism_effect"], 0.3)

    def test_only_placebo_inconclusive(self):
        """只有安慰剂没有消融: 单边对照无法排除复杂度, 必须判不充分。"""
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "placebo", "expression": "add(ts_delta(a,5),0)"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 1.9, 1.80), ("add(ts_delta(a,5),0)", 1.2, 1.10)])
        rec = self.bus.record_outcome(exp["payload"]["run_id"], p)
        self.assertEqual(rec["payload"]["verdict"], ST_INCONCLUSIVE)
        self.assertIn("消融", rec["payload"]["evidence"]["reason"])

    def test_missing_role_inconclusive(self):
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "placebo", "expression": "rank(ts_delta(z,5))"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 1.4, 1.30)])
        self.assertEqual(self.bus.record_outcome(exp["payload"]["run_id"], p)["payload"]["verdict"],
                         ST_INCONCLUSIVE)

    def test_no_placebo_inconclusive(self):
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [{"role": "parent", "expression": "rank(a)"}]})
        p = self._result([("rank(a)", 1.4, 1.30)])
        self.assertEqual(self.bus.record_outcome(exp["payload"]["run_id"], p)["payload"]["verdict"],
                         ST_INCONCLUSIVE)

    def test_negative_parent_inconclusive(self):
        self._probe()
        exp = self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(a)"},
            {"role": "placebo", "expression": "rank(z)"},
        ]})
        p = self._result([("rank(a)", -0.5, -0.4), ("rank(z)", 0.1, 0.1)])
        self.assertEqual(self.bus.record_outcome(exp["payload"]["run_id"], p)["payload"]["verdict"],
                         ST_INCONCLUSIVE)


class TestP03SamplingUnpredictable(AuditBusTestBase):
    """P0-3: commit-then-reveal, Agent 无法在提交前 grind 命中桶。"""

    def test_nonce_recorded_after_commit(self):
        t, d = self._submit()
        recs = self.bus._read_all()
        types = [r["type"] for r in recs]
        self.assertLess(types.index("batch_submitted"), types.index("sample_decision"))
        dec = [r for r in recs if r["type"] == "sample_decision"][0]["payload"]
        self.assertEqual(len(dec["nonce"]), 32)
        self.assertEqual(dec["commit_hash"], t.commit_hash)

    def test_bucket_depends_on_nonce_not_only_commit(self):
        """同一份表达式集合, 不同 nonce 应散开 —— 证明桶号不可由表达式预计算。"""
        buckets = []
        for i in range(12):
            t = self.bus.begin_batch(_items(20, "same"), {"region": "USA"})
            buckets.append(self.bus.decide_sampling(t).bucket)
        self.assertGreater(len(set(buckets)), 3, "桶号几乎不变, nonce 未参与散列")

    def test_cannot_redecide(self):
        t, _ = self._submit()
        second = self.bus.decide_sampling(t)
        self.assertFalse(second.sampled)
        self.assertIn("不可重抽", second.reason)

    def test_batch_id_host_generated(self):
        t1, _ = self._submit(prefix="a")
        t2, _ = self._submit(prefix="b")
        self.assertNotEqual(t1.batch_id, t2.batch_id)
        self.assertTrue(t1.batch_id.startswith("B"))


class TestP1Policy(AuditBusTestBase):
    """P1: 状态流转 / 预算 / 封存 / 对照组 / 文件锁 / 锚点。"""

    def test_claim_seal_blocks_same_mechanism_different_field(self):
        self._probe("P-1", expr="rank(ts_delta(a,5))")
        with self.assertRaises(ValueError):
            self._probe("P-2", expr="rank(ts_delta(b,5))")

    def test_claim_allows_different_mechanism(self):
        self._probe("P-1", intents=("TEMPORAL_DECAY",))
        self._probe("P-2", intents=("CROSS_SECTIONAL_RELATIVE",), expr="group_rank(x, sector)")
        self.assertEqual(len(self.bus._state()["probes"]), 2)

    def test_mechanism_signature_ignores_field_name(self):
        a = mechanism_signature(["TEMPORAL_DECAY"], [{"role": "SIGNAL", "type": "MATRIX"}])
        b = mechanism_signature(["TEMPORAL_DECAY"], [{"role": "SIGNAL", "type": "MATRIX"}])
        self.assertEqual(a, b)
        c = mechanism_signature(["DISPERSION"], [{"role": "SIGNAL", "type": "MATRIX"}])
        self.assertNotEqual(a, c)

    def test_unseal_requires_env_token(self):
        self._probe("P-1")
        _key = self.bus._state()["probes"][0]["claim_key"]
        with self.assertRaises(PermissionError):
            self.bus.unseal(_key, "研究员复核后允许重提", token="guess")
        os.environ["AEGIS_UNSEAL_TOKEN"] = "s3cret"
        try:
            rec = self.bus.unseal(_key, "研究员复核后允许重提", token="s3cret")
            self.assertEqual(rec["type"], "unsealed")
            with self.assertRaises(PermissionError):
                self.bus.unseal(_key, "研究员复核后允许重提", token="wrong")
        finally:
            os.environ.pop("AEGIS_UNSEAL_TOKEN", None)

    def test_budget_blocks_probe_slots(self):
        self.bus.policy["budget"]["daily_probe_slots"] = 5
        self._probe("P-1", slots=4)
        with self.assertRaises(PermissionError):
            self._probe("P-2", slots=4, intents=("DISPERSION",))

    def test_rule_lint_blocks_when_reject(self):
        t, _ = self._submit()
        bad = {"verdicts": [{"verdict": "REJECT", "issues": ["x"]}]}
        with self.assertRaises(PermissionError):
            self.bus.record_rule_lint(t.batch_id, bad)

    def test_control_issued_every_n(self):
        for i in range(4):
            self._probe(f"P-{i}", intents=(f"M{i}",))
        p = self._result([("rank(a)", 1.0, 0.9), ("rank(b)", 1.2, 1.1), ("rank(c)", 1.5, 1.4)])
        ctrl = self.bus.maybe_issue_control(p)
        self.assertIsNotNone(ctrl)
        self.assertTrue(ctrl["is_control"])

    def test_settle_pending_autodecides(self):
        self._probe()
        self.bus.open_experiment("P-1", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "placebo", "expression": "rank(ts_delta(z,5))"},
        ]})
        p = self._result([("rank(ts_delta(a,5))", 1.9, 1.80), ("rank(ts_delta(z,5))", 1.2, 1.10)])
        done = self.bus.settle_pending(p)
        self.assertEqual(len(done), 1)
        self.assertEqual(len(self.bus.settle_pending(p)), 0, "已结案实验被重复结算")

    def test_chain_tamper_detected(self):
        for i in range(3):
            self._submit(prefix=f"t{i}")
        ok, bad = self.bus.verify()
        self.assertTrue(ok)
        with open(self.bus.ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[1] = lines[1].replace('"seq":1', '"seq":9', 1)
        with open(self.bus.ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        ok2, bad2 = self.bus.verify()
        self.assertFalse(ok2)
        self.assertEqual(bad2, 1)

    def test_anchor_refuses_broken_chain(self):
        self._submit()
        with open(self.bus.ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace('"seq":0', '"seq":7', 1)
        with open(self.bus.ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        with self.assertRaises(PermissionError):
            self.bus.anchor()

    def test_broken_chain_blocks_new_batch(self):
        self._submit()
        with open(self.bus.ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace('"seq":0', '"seq":7', 1)
        with open(self.bus.ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        with self.assertRaises(PermissionError):
            self._submit(prefix="after")

    def test_receipt_is_readonly_text(self):
        self._probe()
        txt = self.bus.render_receipt_text()
        self.assertIn("只读", txt)
        self.assertIn("不可由你修改", txt)

    def test_disabled_policy_is_logged_not_silent(self):
        """关闭审计开关必须留痕 —— 否则「关掉审计」就是最廉价的绕过路径。"""
        self.bus.policy["enabled"] = False
        t, d = self._submit()
        self.assertFalse(d.sampled)
        bypass = [r for r in self.bus._read_all() if r["type"] == "bypass"]
        self.assertEqual(len(bypass), 1)
        self.assertEqual(bypass[0]["payload"]["batch_id"], t.batch_id)


class TestWiringPoints(unittest.TestCase):
    """P0-1: 确认宿主流水线真的调用了审计总线 (防「写了但没接线」)。"""

    def test_sim_runner_calls_bus(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "core", "sim_runner.py"), "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("begin_batch(", src)
        self.assertIn("decide_sampling(", src)
        self.assertIn("settle_pending(", src)

    def test_main_injects_receipt(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "main.py"), "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("render_receipt_text(", src)

    def test_no_agent_facing_write_api(self):
        """审计账本的写入方法不应出现在 prompt 文本里。"""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "main.py"), "r", encoding="utf-8") as f:
            src = f.read()
        for banned in ("record_outcome", "record_probe", "unseal("):
            self.assertNotIn(banned, src, f"{banned} 不应出现在主流程 prompt 侧")


if __name__ == "__main__":
    unittest.main(verbosity=2)
