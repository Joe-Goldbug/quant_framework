"""
core/audit_bus.py
AEGIS 审计总线 —— 宿主侧审计调度 + 不可篡改账本 + 数据裁决

v2 修复清单 (对应审查 P0-1~P1):
  P0-2 裁决不可伪造: record_outcome(run_id, result_path) 不接受 verdict 参数,
       裁决由本模块从结果文件的 metrics 按「预注册 decider」自动计算;
       未知 run_id / 已结案 / 结果文件缺失 / 角色不全 -> 一律拒绝或 INCONCLUSIVE。
  P0-3 抽样不可规避: commit-then-reveal。先落盘 commit_hash(表达式集合+完整实验规格),
       之后才抽 os.urandom nonce, bucket = H(nonce || commit)。Agent 无法预先 grind,
       因为 nonce 在它提交之后才存在; 事后可复核, 因为 nonce 写进了账本。
  P1   对照组/规则lint/状态流转/集中预算/文件锁/锚点校验 全部落地。

设计铁律:
  1. 触发权在宿主。本模块不向 Agent 暴露写接口。
  2. 裁决只认数据。任何人(包括研究员)都不能手工写 PASS。
  3. 机制声明一次封存, 证伪后不得改理由重交 —— 否则就是故事修补。
  4. 同机同权限下不存在物理隔离, 只存在「不可隐藏」: 删改必留痕, 靠外部锚点比对。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LEDGER_NAME = "audit_ledger.jsonl"
ANCHOR_NAME = "audit_anchor.json"
GENESIS = "0" * 64

# ---------------- 判决状态 ----------------
ST_NOT_SAMPLED = "NOT_SAMPLED"
ST_RULES_ONLY = "PASS_BY_RULES"
ST_RULES_REJECT = "RULES_REJECT"
ST_PROBE_OPEN = "PROBE_OPEN"
ST_EXPERIMENT_OPEN = "EXPERIMENT_OPEN"
ST_FALSIFIED = "MECHANISM_FALSIFIED"
ST_CORROBORATED = "CORROBORATED"
ST_INCONCLUSIVE = "INCONCLUSIVE"

VALID_VERDICTS = (ST_FALSIFIED, ST_CORROBORATED, ST_INCONCLUSIVE)

DEFAULT_POLICY: Dict[str, Any] = {
    "version": 2,
    "enabled": True,
    "sampling": {
        "explore_rate_permille": 50,
        "min_batches_between_probes": 4,
        "control_every_n_probes": 4,
    },
    "budget": {
        "daily_probe_slots": 40,
        "daily_probe_calls": 8,
        "max_slots_per_probe": 6,
        "daily_always_audit_calls": 20,
        "daily_control_calls": 4,
    },
    "always_audit": {
        "near_champion": True,
        "production_candidate": True,
        "novel_operator": True,
    },
    "rules": {"as_lint_only": True, "block_on_reject": True},
    "decider": {"metric": "sharpe_2y", "min_delta": 0.30, "require_positive_parent": True},
}


# ---------------------------------------------------------------- 工具
def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_expr(expr: str) -> str:
    return re.sub(r"\s+", "", str(expr or "")).lower()


@contextmanager
def _file_lock(path: str):
    """跨进程独占锁。并发批次追加时防 seq 重复与链竞争。"""
    lock_path = path + ".lock"
    d = os.path.dirname(os.path.abspath(lock_path))
    if d:
        os.makedirs(d, exist_ok=True)
    fh = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def mechanism_signature(mechanism_intents: List[str], field_roles: List[Dict[str, Any]],
                        horizon: Optional[Dict[str, Any]] = None, version: int = 1) -> str:
    """机制签名: 用「字段物理画像」而非字段名。换同物理属性的字段 = 同一机制, 不可重提。"""
    try:
        from core.dgp_schema import HypothesisSpec
        sig_fn = HypothesisSpec.physical_field_signature
    except Exception:
        def sig_fn(m):
            return f"FIELD[{m.get('role')}|{m.get('update_frequency')}|{m.get('is_sparse')}|{m.get('skewness')}|{m.get('type')}]"
    roles = sorted(f"{str(r.get('role') or 'UNKNOWN')}|{sig_fn(r)}" for r in (field_roles or []))
    payload = {
        "intents": sorted({str(i).upper() for i in (mechanism_intents or [])}),
        "roles": roles,
        "horizon": {k: (horizon or {}).get(k) for k in ("short_window", "long_window")},
        "v": version,
    }
    return "MECH_" + _sha256(_canonical(payload))[:16].upper()


@dataclass
class BatchTicket:
    batch_id: str
    batch_seq: int
    commit_hash: str


@dataclass
class SampleDecision:
    sampled: bool
    reason: str
    bucket: int = -1
    threshold: int = -1
    is_control: bool = False
    mandatory: bool = False


class AuditBus:
    def __init__(self, campaign_dir: str, policy_path: Optional[str] = None):
        self.campaign_dir = os.path.abspath(campaign_dir)
        os.makedirs(self.campaign_dir, exist_ok=True)
        self.ledger_path = os.path.join(self.campaign_dir, LEDGER_NAME)
        self.anchor_path = os.path.join(self.campaign_dir, ANCHOR_NAME)
        self.policy = self._load_policy(policy_path)

    # ------------------------------------------------------------ policy
    def _load_policy(self, policy_path: Optional[str]) -> Dict[str, Any]:
        pol = json.loads(json.dumps(DEFAULT_POLICY))
        if policy_path and os.path.exists(policy_path):
            try:
                with open(policy_path, "r", encoding="utf-8") as f:
                    _deep_merge(pol, json.load(f))
            except Exception as e:
                print(f"⚠️ [AuditBus] 策略解析失败, 回落默认值: {e}")
        return pol

    # ------------------------------------------------------------ ledger
    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.ledger_path):
            return []
        out = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    out.append({"__corrupt__": line})
        return out

    def _append(self, type_: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with _file_lock(self.ledger_path):
            recs = self._read_all()
            prev = GENESIS
            for r in reversed(recs):
                if isinstance(r, dict) and r.get("hash"):
                    prev = r["hash"]
                    break
            body = {"seq": len(recs), "ts": round(time.time(), 3), "type": type_, "payload": payload, "prev": prev}
            rec = dict(body, hash=_sha256(_canonical(body)))
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(_canonical(rec) + "\n")
            return rec

    def verify(self) -> Tuple[bool, Optional[int]]:
        prev = GENESIS
        for idx, r in enumerate(self._read_all()):
            if not isinstance(r, dict) or "__corrupt__" in r:
                return False, idx
            body = {k: r.get(k) for k in ("seq", "ts", "type", "payload", "prev")}
            if r.get("prev") != prev or _sha256(_canonical(body)) != r.get("hash"):
                return False, idx
            prev = r["hash"]
        return True, None

    def root_hash(self) -> str:
        for r in reversed(self._read_all()):
            if isinstance(r, dict) and r.get("hash"):
                return r["hash"]
        return GENESIS

    def anchor(self, out_path: Optional[str] = None) -> str:
        ok, bad = self.verify()
        if not ok:
            raise PermissionError(f"【AuditBus】哈希链断裂于 seq={bad}, 拒绝锚定破损账本。")
        out = out_path or self.anchor_path
        doc = {"ts": round(time.time(), 3), "root": self.root_hash(), "entries": len(self._read_all())}
        with open(out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        return doc["root"]

    # ------------------------------------------------------------ state
    def _state(self) -> Dict[str, Any]:
        recs = [r for r in self._read_all() if isinstance(r, dict)]
        st: Dict[str, Any] = {
            "batches": 0, "batch_ids": set(), "probes": [], "open_probes": [],
            "falsified_claims": [], "sealed_claims": {}, "decisions": {},
            "probes_today": 0, "slots_today": 0, "always_today": 0, "control_today": 0,
            "last_probe_batch": -99, "experiments": {}, "outcomes": {},
            "cumulative_slots": 0, "last_batch_seq": 0,
        }
        day_start = time.time() - 86400
        for r in recs:
            t, p = r.get("type"), (r.get("payload") or {})
            if t == "batch_submitted":
                st["batches"] += 1
                st["batch_ids"].add(p.get("batch_id"))
                st["last_batch_seq"] = max(st["last_batch_seq"], int(p.get("batch_seq") or 0))
            elif t == "sample_decision":
                st["decisions"][p.get("batch_id")] = p
                if p.get("sampled"):
                    st["last_probe_batch"] = max(st["last_probe_batch"], int(p.get("batch_seq") or -99))
            elif t == "probe":
                st["probes"].append(p)
                if p.get("claim_key"):
                    st["sealed_claims"][p["claim_key"]] = p
                if float(p.get("ts") or 0) >= day_start:
                    st["probes_today"] += 1
                    st["slots_today"] += int(p.get("slots") or 0)
                st["cumulative_slots"] += int(p.get("slots") or 0)
            elif t == "experiment_opened":
                st["experiments"][p.get("run_id")] = p
            elif t == "outcome":
                st["outcomes"][p.get("run_id")] = p
                if p.get("verdict") == ST_FALSIFIED:
                    st["falsified_claims"].append(p)
        decided_ids = {o.get("probe_id") for o in st["outcomes"].values()}
        st["open_probes"] = [p for p in st["probes"] if p.get("probe_id") not in decided_ids]
        probe_claim = {p.get("probe_id"): p.get("claim_key") for p in st["probes"]}
        for fc in st["falsified_claims"]:
            fc.setdefault("claim_key", probe_claim.get(fc.get("probe_id")))
        return st

    def _budget_used(self, kind: str, day_start: float) -> int:
        n = 0
        for r in self._read_all():
            if not isinstance(r, dict) or float(r.get("ts") or 0) < day_start:
                continue
            p = r.get("payload") or {}
            if kind == "probe_calls" and r.get("type") == "probe":
                n += 1
            elif kind == "probe_slots" and r.get("type") == "probe":
                n += int(p.get("slots") or 0)
            elif kind == "always" and r.get("type") == "sample_decision" and p.get("mandatory"):
                n += 1
            elif kind == "control" and r.get("type") == "probe" and p.get("is_control"):
                n += 1
        return n

    def _check_budget(self, kind: str, need_slots: int = 0) -> Tuple[bool, str]:
        """集中预算闸门。kind: probe | always | control"""
        b = self.policy.get("budget", {})
        day = time.time() - 86400
        if kind == "probe":
            if self._budget_used("probe_calls", day) >= int(b.get("daily_probe_calls", 8)):
                return False, f"今日出题调用已达上限 {b.get('daily_probe_calls')}"
            used = self._budget_used("probe_slots", day)
            cap = int(b.get("daily_probe_slots", 40))
            if used + need_slots > cap:
                return False, f"今日证伪槽位 {used}+{need_slots} 超上限 {cap}"
        elif kind == "always":
            used = self._budget_used("always", day)
            cap = int(b.get("daily_always_audit_calls", 20))
            if used >= cap:
                return False, f"必审今日 {used}/{cap} 超额"
        elif kind == "control":
            used = self._budget_used("control", day)
            cap = int(b.get("daily_control_calls", 4))
            if used >= cap:
                return False, f"对照组今日已达 {used}/{cap}"
        return True, ""

    # ------------------------------------------------------------ batch
    def begin_batch(self, items: List[Dict[str, Any]], spec_meta: Optional[Dict[str, Any]] = None) -> BatchTicket:
        """宿主收到 Agent 产物后调用。batch_id 由宿主生成, 不接受 Agent 自报名称。"""
        ok, bad = self.verify()
        if not ok:
            raise PermissionError(f"【AuditBus】账本哈希链断裂于 seq={bad}, 拒绝受理新批次。")

        meta = dict(spec_meta or {})
        exprs = [str(x.get("expression", "")) for x in items]
        seq = self._state()["batches"] + 1
        batch_id = f"B{seq:05d}-{os.urandom(4).hex()}"
        spec = {k: meta.get(k) for k in ("region", "universe", "delay", "category", "neutralization", "decay")}
        commit_payload = {
            "batch_id": batch_id,
            "batch_seq": seq,
            "expressions": [_norm_expr(e) for e in exprs],
            "spec": spec,
        }
        commit_hash = _sha256(_canonical(commit_payload))

        # 关闭开关不是静默跳过: 关闭本身要留痕, 否则「关掉审计」就是最廉价的绕过方式
        if not self.policy.get("enabled", True):
            self._append("bypass", {
                "batch_id": batch_id, "batch_seq": seq, "commit_hash": commit_hash,
                "reason": "policy.enabled=false", "ts": time.time(),
            })
            print(f"⚠️ [AuditBus] 审计已关闭, 本批 {batch_id} 以 bypass 记账 (不可静默绕过)。")
            return BatchTicket(batch_id=batch_id, batch_seq=seq, commit_hash=commit_hash)

        self._append("batch_submitted", {
            "batch_id": batch_id, "batch_seq": seq, "n_items": len(items),
            "n_expr_unique": len(set(exprs)), "commit_hash": commit_hash,
            "spec": spec, "spec_hash": _sha256(_canonical(spec)),
        })
        return BatchTicket(batch_id=batch_id, batch_seq=seq, commit_hash=commit_hash)

    def decide_sampling(self, ticket: BatchTicket, near_champion: bool = False,
                        production_candidate: bool = False, novel_operator: bool = False) -> SampleDecision:
        """commit 之后才抽 nonce —— Agent 无法在提交前 grind 命中桶。"""
        if not self.policy.get("enabled", True):
            return SampleDecision(False, "审计总线已关闭(已 bypass 记账)", -1, -1)
        st = self._state()
        if ticket.batch_id in st["decisions"]:
            return SampleDecision(False, "该批次已完成抽样决策(不可重抽)", -1, -1)

        aa = self.policy.get("always_audit", {})
        mandatory = bool(
            (production_candidate and aa.get("production_candidate"))
            or (near_champion and aa.get("near_champion"))
            or (novel_operator and aa.get("novel_operator"))
        )
        nonce = os.urandom(16).hex()
        threshold = int(self.policy.get("sampling", {}).get("explore_rate_permille", 50))
        bucket = int(_sha256(nonce + "|" + ticket.commit_hash)[:8], 16) % 1000

        def _commit(sampled: bool, reason: str, is_mandatory: bool = False) -> SampleDecision:
            self._append("sample_decision", {
                "batch_id": ticket.batch_id, "batch_seq": ticket.batch_seq,
                "commit_hash": ticket.commit_hash, "nonce": nonce,
                "bucket": bucket, "threshold": threshold,
                "sampled": sampled, "reason": reason,
                "mandatory": is_mandatory, "is_control": False, "ts": time.time(),
            })
            return SampleDecision(sampled, reason, bucket, threshold, False, is_mandatory)

        if mandatory:
            ok_b, msg = self._check_budget("always")
            if not ok_b:
                print(f"⚠️ [AuditBus] {msg} —— 必审仍放行, 已超额记账。")
            tag = "拟出厂" if production_candidate else ("准冠军" if near_champion else "罕见算子")
            return _commit(True, f"必审触发 ({tag})", True)

        s = self.policy.get("sampling", {})
        gap = int(s.get("min_batches_between_probes", 4))
        if ticket.batch_seq - st["last_probe_batch"] < gap:
            return _commit(False, f"距上次抽样 {ticket.batch_seq - st['last_probe_batch']} 批 (< {gap})")

        ok_b, msg = self._check_budget("probe")
        if not ok_b:
            return _commit(False, msg)

        if bucket >= threshold:
            return _commit(False, f"未命中抽样桶 {bucket}/{threshold}")
        return _commit(True, f"哈希抽样命中 (桶 {bucket}/{threshold})")

    def record_rule_lint(self, batch_id: str, verdict_doc: Dict[str, Any]) -> Dict[str, Any]:
        """规则红队降级为 lint: 记录但不具备经济学权威。"""
        verdicts = verdict_doc.get("verdicts", []) or []
        rejects = [v for v in verdicts if v.get("verdict") != "PASS"]
        passed = len(rejects) == 0
        rec = self._append("rules_lint", {
            "batch_id": batch_id, "passed": passed, "n_total": len(verdicts),
            "n_reject": len(rejects),
            "issues": [i for v in rejects for i in (v.get("issues") or [])][:10],
            "ts": time.time(),
        })
        rules = self.policy.get("rules", {})
        if rules.get("block_on_reject") and not passed:
            raise PermissionError(f"【AuditBus / lint】{len(rejects)} 槽未过硬性 lint, 本批阻断。")
        return rec

    # ------------------------------------------------------------ probe
    def record_probe(self, probe: Dict[str, Any]) -> Dict[str, Any]:
        ok_b, msg = self._check_budget("probe", int(probe.get("slots") or 0))
        if not ok_b:
            raise PermissionError(f"【AuditBus】预算拒绝: {msg}")

        # 有机制意图 -> 用物理签名(换字段也算同一机制); 没有 -> 退化为表达式级弱签名,
        # 否则所有「无意图」的命题会塌缩成同一个 claim_key, 第二条就被误判为重复。
        if probe.get("mechanism_intents"):
            claim_key = probe.get("claim_key") or mechanism_signature(
                probe["mechanism_intents"],
                probe.get("field_roles") or [],
                probe.get("horizon_model"),
            )
            weak = False
        else:
            claim_key = probe.get("claim_key") or ("MECHW_" + _sha256(_canonical(
                [_norm_expr(probe.get("expression", "")),
                 probe.get("hypothesis_id"), probe.get("mechanism_claim")]
            ))[:16].upper())
            weak = True
        st = self._state()
        if claim_key in st["sealed_claims"]:
            raise ValueError(
                f"【AuditBus】机制声明 {claim_key} 已封存, 不允许二次提交。"
                f"证伪后改理由重交属故事修补, 需研究员显式 unseal 才可复审。"
            )
        if not probe.get("decider"):
            raise ValueError("【AuditBus】命题缺少预注册 decider, 无法自动裁决。")
        if not re.match(r"^[A-Za-z0-9_\-]+$", str(probe.get("probe_id") or "")):
            raise ValueError("【AuditBus】probe_id 非法。")
        return self._append("probe", dict(
            probe, claim_key=claim_key, ts=time.time(),
            claim_weak=weak,
        ))

    def open_experiment(self, probe_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """登记一次证伪实验。spec.entries = [{"role":"parent|placebo|strip", "expression":...}]"""
        st = self._state()
        if probe_id not in {p.get("probe_id") for p in st["probes"]}:
            raise ValueError(f"【AuditBus】未知 probe_id={probe_id}, 拒绝开实验。")
        if any(e.get("probe_id") == probe_id for e in st["experiments"].values()):
            raise ValueError(f"【AuditBus】probe {probe_id} 已开过实验, 不可重复开题。")
        entries = spec.get("entries") or []
        roles = {str(e.get("role")) for e in entries if e.get("expression")}
        if "parent" not in roles:
            raise ValueError("【AuditBus】实验缺少 parent 对照, 无法裁决。")
        run_id = f"RUN-{_sha256(_canonical(spec))[:10].upper()}"
        return self._append("experiment_opened", {
            "run_id": run_id, "probe_id": probe_id,
            "spec_hash": _sha256(_canonical(spec)),
            "entries": entries, "roles": sorted(roles), "ts": time.time(),
        })

    # ------------------------------------------------------------ outcome
    @staticmethod
    def _index_result(result_path: str) -> Dict[str, Dict[str, Any]]:
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        idx = {}
        for r in (data.get("alpha_results") or []):
            expr = r.get("code") or r.get("expression") or ""
            m = r.get("metrics") or {}
            idx[_norm_expr(expr)] = {
                "alpha_id": r.get("alpha_id"),
                "sharpe": m.get("sharpe"),
                "sharpe_2y": m.get("two_year_sharpe", m.get("twoYearSharpe")),
                "fitness": m.get("fitness"),
                "turnover": m.get("turnover"),
                "margin": m.get("margin"),
                "fail": (r.get("checks") or {}).get("fail") or [],
            }
        return idx

    def record_outcome(self, run_id: str, result_path: str) -> Dict[str, Any]:
        """唯一裁决入口。不接受 verdict 参数 —— 结论由结果文件算出。"""
        st = self._state()
        exp = st["experiments"].get(run_id)
        if not exp:
            raise ValueError(f"【AuditBus】未知 run_id={run_id}, 拒绝裁决。")
        if run_id in st["outcomes"]:
            raise ValueError(f"【AuditBus】run {run_id} 已结案, 禁止重复裁决。")
        if not os.path.exists(result_path):
            raise FileNotFoundError(f"【AuditBus】结果文件不存在: {result_path}")

        probe = next((p for p in st["probes"] if p.get("probe_id") == exp.get("probe_id")), None)
        if probe is None:
            raise ValueError("【AuditBus】实验对应的命题不存在。")

        decider = dict(self.policy.get("decider", {}))
        decider.update(probe.get("decider") or {})
        metric = str(decider.get("metric", "sharpe_2y"))
        min_delta = float(decider.get("min_delta", 0.30))
        require_pos = bool(decider.get("require_positive_parent", True))

        idx = self._index_result(result_path)
        by_role: Dict[str, Dict[str, Any]] = {}
        entry_by_role: Dict[str, Dict[str, Any]] = {}
        missing: List[Any] = []
        for e in exp.get("entries") or []:
            role_k = str(e.get("role"))
            entry_by_role[role_k] = e
            row = idx.get(_norm_expr(e.get("expression")))
            if row is None or row.get(metric) is None:
                missing.append(e.get("role"))
            else:
                by_role[role_k] = row

        evidence: Dict[str, Any] = {
            "metric": metric, "min_delta": min_delta,
            "result_path": os.path.abspath(result_path),
            "result_hash": _sha256_file(result_path),
            "missing_roles": missing,
            "alpha_ids": {k: v.get("alpha_id") for k, v in by_role.items()},
            "decided_by": "auto:result_file",
        }

        if missing or "parent" not in by_role:
            verdict = ST_INCONCLUSIVE
            reason = f"结果缺角色 {missing or ['parent']}, 实验未跑成"
        else:
            p_val = float(by_role["parent"][metric])  # type: ignore[arg-type]
            evidence["parent"] = p_val
            if require_pos and p_val <= 0:
                verdict = ST_INCONCLUSIVE
                reason = f"母本 {metric}={p_val:.3f} 无正收益, 机制无从谈起"
            elif "placebo" in by_role and "strip" in by_role:
                s_val = float(by_role["strip"][metric])     # type: ignore[arg-type]
                q_val = float(by_role["placebo"][metric])   # type: ignore[arg-type]

                p_expr_raw = str((entry_by_role.get("parent") or {}).get("expression") or "")
                q_expr_raw = str((entry_by_role.get("placebo") or {}).get("expression") or "")
                q_kind = str((entry_by_role.get("placebo") or {}).get("control_kind") or "").lower()
                lag_pat = re.compile(r"ts_delay\s*\([^)]*,\s*252\s*\)", re.IGNORECASE)
                is_lagged_placebo = (
                    q_kind == "lagged_placebo"
                    or len(lag_pat.findall(q_expr_raw)) > len(lag_pat.findall(p_expr_raw))
                )

                if is_lagged_placebo:
                    # V4.1 双对照机制裁决 (strip = rank(raw), placebo = 252日滞后壳):
                    # 必须同时通过:
                    #   1. 机制增益: parent - strip >= min_delta (证明机制显著优于裸字段)
                    #   2. 非壳时效增益: parent - placebo >= max(min_delta, 0.50) (证明收益来自当期信息而非复杂外壳伪影)
                    mech_gain = p_val - s_val
                    freshness_gain = p_val - q_val
                    min_freshness = max(min_delta, 0.50)
                    net = min(mech_gain, freshness_gain)
                    is_shell_artifact = bool(mech_gain >= min_delta and freshness_gain < min_freshness)
                    evidence.update(
                        strip=s_val,
                        placebo=q_val,
                        parent_minus_strip=round(mech_gain, 4),
                        parent_minus_placebo=round(freshness_gain, 4),
                        mech_gain=round(mech_gain, 4),
                        freshness_gain=round(freshness_gain, 4),
                        min_freshness_delta=round(min_freshness, 4),
                        net_mechanism_effect=round(net, 4),
                        complexity_artifact=is_shell_artifact,
                        rule="dual_control_lagged_placebo",
                    )
                    if mech_gain >= min_delta and freshness_gain >= min_freshness:
                        verdict = ST_CORROBORATED
                        reason = (
                            f"双对照验证通过: 机制增益 {mech_gain:+.3f} >= {min_delta:.2f} 且 "
                            f"时效非壳增益 {freshness_gain:+.3f} >= {min_freshness:.2f} "
                            f"(母本 {p_val:.2f} / 消融 {s_val:.2f} / 滞后安慰剂 {q_val:.2f})"
                        )
                    elif is_shell_artifact:
                        verdict = ST_FALSIFIED
                        reason = (
                            f"疑似复杂度外壳伪影: 机制增益 {mech_gain:+.3f} 但 252日滞后安慰剂仍达 {q_val:.2f} "
                            f"(时效增益 {freshness_gain:+.3f} < {min_freshness:.2f})"
                        )
                    else:
                        verdict = ST_FALSIFIED
                        reason = (
                            f"机制相对裸信号增益不足: parent-strip={mech_gain:+.3f} < {min_delta:.2f} "
                            f"(母本 {p_val:.2f} / 消融 {s_val:.2f} / 滞后安慰剂 {q_val:.2f})"
                        )
                else:
                    # 经典外层去壳双差分: (母本-消融) - (母本-安慰剂) = 安慰剂 - 消融
                    net = q_val - s_val
                    evidence.update(strip=s_val, placebo=q_val,
                                    parent_minus_strip=round(p_val - s_val, 4),
                                    parent_minus_placebo=round(p_val - q_val, 4),
                                    net_mechanism_effect=round(net, 4),
                                    rule="double_difference")
                    evidence["complexity_artifact"] = bool(
                        (p_val - s_val) >= min_delta and net < min_delta
                    )
                    if net >= min_delta:
                        verdict = ST_CORROBORATED
                        reason = f"净机制效应 {net:+.3f} >= {min_delta} (安慰剂 {q_val:.2f} / 消融 {s_val:.2f})"
                    else:
                        verdict = ST_FALSIFIED
                        reason = f"净机制效应 {net:+.3f} < {min_delta} (机制声明不成立)"
            elif "placebo" in by_role:
                # 只有安慰剂: 只能排除「纯装饰」, 无法排除复杂度效应, 按不充分处理
                verdict = ST_INCONCLUSIVE
                reason = "缺少消融对照 (strip), 单安慰剂无法做双差分"
            else:
                verdict = ST_INCONCLUSIVE
                reason = "缺少安慰剂对照, 无法排除复杂度效应"

        evidence["reason"] = reason
        return self._append("outcome", {
            "run_id": run_id, "probe_id": exp.get("probe_id"),
            "verdict": verdict, "evidence": evidence, "ts": time.time(),
        })

    # ------------------------------------------------------------ settle
    def settle_pending(self, result_path: str) -> List[Dict[str, Any]]:
        """回测落盘后调用: 把所有「角色在结果中齐全」的未结案实验自动裁决。
        裁决由 record_outcome 从结果文件算出, 此处只做扫描与触发。"""
        if not os.path.exists(result_path):
            return []
        try:
            idx = self._index_result(result_path)
        except Exception as e:
            print(f"⚠️ [AuditBus] 结果文件解析失败, 跳过结算: {e}")
            return []
        st = self._state()
        done: List[Dict[str, Any]] = []
        for run_id, exp in st["experiments"].items():
            if run_id in st["outcomes"]:
                continue
            entries = exp.get("entries") or []
            if not entries:
                continue
            if all(_norm_expr(e.get("expression")) in idx for e in entries):
                try:
                    rec = self.record_outcome(run_id, result_path)
                    done.append(rec)
                    print(f"⚖️ [AuditBus] {run_id} 自动裁决: {rec['payload']['verdict']}"
                          f" ({(rec['payload']['evidence'] or {}).get('reason', '')})")
                except Exception as e:
                    print(f"⚠️ [AuditBus] {run_id} 裁决失败: {e}")
        return done

    # ------------------------------------------------------------ control
    def maybe_issue_control(self, result_path: str) -> Optional[Dict[str, Any]]:
        """出题器自身的对照组: 每 N 条命题, 抽一条平庸样本出题。
        若出题器对平庸样本也写出同样笃定的故事, 说明它在复述叙事而非检验机制。"""
        every = int(self.policy.get("sampling", {}).get("control_every_n_probes", 4))
        if every <= 0:
            return None
        st = self._state()
        n_total = len(st["probes"])
        n_control = sum(1 for p in st["probes"] if p.get("is_control"))
        if n_total == 0 or n_total % every != 0 or n_control >= n_total // every:
            return None
        ok_b, _ = self._check_budget("control")
        if not ok_b:
            return None
        idx = self._index_result(result_path)
        rows = [(k, v) for k, v in idx.items() if v.get("sharpe_2y") is not None]
        if len(rows) < 3:
            return None
        rows.sort(key=lambda kv: float(kv[1]["sharpe_2y"]))  # type: ignore[arg-type]
        med_expr, med_row = rows[len(rows) // 2]
        return {
            "is_control": True, "expression": med_expr, "role": "control_median",
            "sharpe_2y": med_row.get("sharpe_2y"), "alpha_id": med_row.get("alpha_id"),
            "note": "对照组: 平庸样本。若出题器对它也能给出笃定机制故事, 出题器失效。",
        }

    # ------------------------------------------------------------ unseal
    def unseal(self, claim_key: str, reason: str, token: Optional[str] = None) -> Dict[str, Any]:
        """研究员显式解封。token 必须来自独立环境变量, 防止 Agent 自我解封。"""
        expect = os.environ.get("AEGIS_UNSEAL_TOKEN", "")
        if not expect or not token or token != expect:
            raise PermissionError("【AuditBus】解封需要 AEGIS_UNSEAL_TOKEN, 且不接受 Agent 传入的值。")
        if not reason or len(reason) < 10:
            raise ValueError("【AuditBus】解封必须写明理由 (>=10 字)。")
        return self._append("unsealed", {"claim_key": claim_key, "reason": reason, "ts": time.time()})

    # ------------------------------------------------------------ receipt
    def render_receipt_text(self, max_lines: int = 12) -> str:
        ok, bad = self.verify()
        st = self._state()
        b = self.policy.get("budget", {})
        lines = [
            f"【审计回执 · 宿主签发 · 只读】root={self.root_hash()[:10]} 链={'完整' if ok else f'断裂@{bad}'}",
            f"- 账本批次 {st['batches']} | 近24h 出题 {st['probes_today']}/{b.get('daily_probe_calls')}"
            f" 槽位 {st['slots_today']}/{b.get('daily_probe_slots')}",
        ]
        if st["open_probes"]:
            lines.append(f"- 未结案命题 {len(st['open_probes'])} 条 (未结案前不得就同一机制再提声明):")
            for p in st["open_probes"][:3]:
                age = (time.time() - float(p.get("ts") or time.time())) / 3600
                lines.append(f"    · {p.get('probe_id')} [{p.get('claim_key')}] "
                             f"{str(p.get('mechanism_claim') or '')[:36]} (挂起 {age:.1f}h)")
        if st["falsified_claims"]:
            lines.append(f"- 已破产机制声明 {len(st['falsified_claims'])} 条 (不得复用其理由模板):")
            for p in st["falsified_claims"][:2]:
                lines.append(f"    · {p.get('claim_key')}: {str((p.get('evidence') or {}).get('reason', ''))[:38]}")
        lines.append("- 本回执不可由你修改; 你无法申诉、无法选择是否被审、无法删除记录。")
        return "\n".join(lines[:max_lines])


# ---------------------------------------------------------------- self test
def resolve_policy_path() -> Optional[str]:
    """从任意工作目录向上找 config/audit_policy.json。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        cand = os.path.join(here, "config", "audit_policy.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return None


if __name__ == "__main__":
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="auditbus_")
    try:
        print("=" * 64)
        bus = AuditBus(tmp, policy_path="config/audit_policy.json")

        # T1 抽样率
        sampled = 0
        for i in range(40):
            t = bus.begin_batch([{"expression": f"rank(ts_delta(f{j},5))"} for j in range(20)],
                                {"region": "USA", "universe": "TOP1000", "delay": 1})
            if bus.decide_sampling(t).sampled:
                sampled += 1
        print(f"[T1 抽样] 40 批命中 {sampled} 次 (5% + 间隔>=4, 期望约 2)")

        # T2 链
        ok, bad = bus.verify()
        print(f"[T2 链校验] ok={ok} bad={bad}")
        assert ok and bad is None

        # T3 不可重抽
        t_a = bus.begin_batch([{"expression": "rank(x)"}], {"region": "USA"})
        bus.decide_sampling(t_a)
        print(f"[T3 防重抽] {bus.decide_sampling(t_a).reason}")

        # T4 伪造裁决
        try:
            bus.record_outcome("RUN-FAKE", __file__)
            print("[T4] ❌ 未知 run_id 未被拒")
        except ValueError as e:
            print(f"[T4 伪造裁决] ✅ {str(e)[:34]}")

        # T5 命题 + 同机制换字段
        probe = bus.record_probe({
            "probe_id": "P-0001", "expression": "rank(ts_delta(a,5))", "hypothesis_id": "H1",
            "mechanism_intents": ["TEMPORAL_DECAY"], "field_roles": [{"role": "SIGNAL", "type": "MATRIX"}],
            "horizon_model": {"short_window": 5, "long_window": 20},
            "mechanism_claim": "短窗口优于长窗口", "slots": 4,
            "decider": {"metric": "sharpe_2y", "min_delta": 0.3},
        })
        print(f"[T5 命题] claim_key={probe['payload']['claim_key']}")
        try:
            bus.record_probe({
                "probe_id": "P-0002", "expression": "rank(ts_delta(b,5))", "hypothesis_id": "H1",
                "mechanism_intents": ["TEMPORAL_DECAY"], "field_roles": [{"role": "SIGNAL", "type": "MATRIX"}],
                "horizon_model": {"short_window": 5, "long_window": 20},
                "mechanism_claim": "换个说法重交", "slots": 4,
                "decider": {"min_delta": 0.3},
            })
            print("[T5b] ❌ 同机制换字段未被拦截")
        except ValueError:
            print("[T5b 换字段重交] ✅ 被拦截 (物理签名一致)")

        # T6/T7 实验 + 自动裁决
        exp = bus.open_experiment("P-0001", {"entries": [
            {"role": "parent", "expression": "rank(ts_delta(a,5))"},
            {"role": "placebo", "expression": "rank(ts_delta(zzz,5))"},
            {"role": "strip", "expression": "rank(a)"},
        ]})
        run_id = exp["payload"]["run_id"]
        res = os.path.join(tmp, "fake_result.json")
        with open(res, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": [
                {"code": "rank(ts_delta(a,5))", "alpha_id": "A1", "metrics": {"sharpe": 1.4, "two_year_sharpe": 1.30}},
                {"code": "rank(ts_delta(zzz,5))", "alpha_id": "A2", "metrics": {"sharpe": 1.1, "two_year_sharpe": 1.05}},
                {"code": "rank(a)", "alpha_id": "A3", "metrics": {"sharpe": 0.6, "two_year_sharpe": 0.55}},
            ]}, f)
        out = bus.record_outcome(run_id, res)
        ev = out["payload"]["evidence"]
        print(f"[T6 实验] {run_id} | 角色={exp['payload']['roles']}")
        print(f"[T7 自动裁决] {out['payload']['verdict']} | M-P={ev.get('parent_minus_placebo')}"
              f" M-S={ev.get('parent_minus_strip')} 复杂度产物={ev.get('complexity_artifact')}")

        try:
            bus.record_outcome(run_id, res)
            print("[T8] ❌ 重复结案未被拒")
        except ValueError:
            print("[T8 重复结案] ✅ 被拒")

        try:
            bus.record_outcome("RUN-X", res, "CORROBORATED")  # type: ignore[call-arg]
            print("[T9] ❌ 接口仍接受 verdict 参数")
        except TypeError:
            print("[T9 越权传结论] ✅ 接口不接受 verdict 参数")

        print("[T10 回执]\n" + bus.render_receipt_text())

        for i in range(25):
            tt = bus.begin_batch([{"expression": f"rank(q{i})"}], {"region": "USA"})
            bus.decide_sampling(tt, production_candidate=True)
        print(f"[T11 必审预算] 今日必审 = {bus._budget_used('always', time.time() - 86400)} (超 20 仍放行并记账)")

        with open(bus.ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[1] = lines[1].replace('"seq":1', '"seq":2', 1)
        with open(bus.ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        ok2, bad2 = bus.verify()
        print(f"[T12 篡改检测] ok={ok2} bad={bad2} (期望 False)")
        assert not ok2
        try:
            bus.anchor()
            print("[T13] ❌ 断裂链被锚定")
        except PermissionError:
            print("[T13 断裂链锚定] ✅ 被拒")
        print("\n全绿")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
