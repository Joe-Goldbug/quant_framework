"""
core/campaign_store.py
AEGIS V4.1 战役三文件收敛状态机存储 (3-File Convergence Store)

彻底终结工作目录碎片文件爆炸 (`batch_*.json`, `diagnosis_*.json`, `.agent_tasks/`, 乱写 `.py`)：
每个 V4.1 战役目录仅允许包含 3 类正式文件 (+ 可选只读 artifacts/):
  1. `campaign.db`          — 唯一状态与实验谱系事实源 (SQLite WAL)
  2. `RESEARCH_TREE.md`     — 每次状态跃迁自动生成的只读研究谱系视图
  3. `certified_champions.json` — 仅由 ProductionGate ALL PASS 终审后追加写入的发证冠军库
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple


ALLOWED_CAMPAIGN_FILES: Set[str] = {
    "campaign.db",
    "campaign.db-wal",
    "campaign.db-shm",
    "RESEARCH_TREE.md",
    "certified_champions.json",
}
ALLOWED_CAMPAIGN_DIRS: Set[str] = {"artifacts"}


def check_directory_hygiene(campaign_dir: str, strict: bool = True) -> Dict[str, Any]:
    """
    检查 V4.1 战役目录卫生: 拦截擅自新建的 .py 脚本、.agent_tasks 邮箱、散落 .txt/.json 碎片。
    仅放行 {campaign.db, campaign.db-wal, campaign.db-shm, RESEARCH_TREE.md, certified_champions.json} 与 artifacts/。
    """
    if not campaign_dir or not os.path.exists(campaign_dir):
        return {"clean": True, "rogue_files": [], "campaign_dir": campaign_dir}

    rogue: List[str] = []
    for entry in sorted(os.listdir(campaign_dir)):
        full = os.path.join(campaign_dir, entry)
        if os.path.isdir(full):
            if entry not in ALLOWED_CAMPAIGN_DIRS:
                rogue.append(entry + "/")
        else:
            if entry not in ALLOWED_CAMPAIGN_FILES:
                rogue.append(entry)

    return {
        "clean": len(rogue) == 0,
        "rogue_files": rogue,
        "campaign_dir": campaign_dir,
        "strict": strict,
    }


def archive_legacy_scripts(campaigns_root: str, recursive: bool = True) -> Dict[str, Any]:
    """
    将历史遗留目录中的游离 `.py` 临时脚本无损归档至 `_legacy_scripts_archive/`（保留相对目录层级）。
    绝不删除任何历史文件。
    """
    if not campaigns_root or not os.path.exists(campaigns_root):
        return {"archived_count": 0, "archived_files": []}

    root_abs = os.path.abspath(campaigns_root)
    archive_dir = os.path.join(root_abs, "_legacy_scripts_archive")
    archived: List[str] = []

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root_abs):
            dirnames[:] = sorted(d for d in dirnames if d != "_legacy_scripts_archive")
            for fname in sorted(filenames):
                if not fname.endswith(".py"):
                    continue
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, root_abs)
                dst = os.path.join(archive_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    stem, ext = os.path.splitext(dst)
                    dst = f"{stem}_{int(time.time())}{ext}"
                shutil.move(src, dst)
                archived.append(rel)
    else:
        for entry in sorted(os.listdir(root_abs)):
            if entry == "_legacy_scripts_archive":
                continue
            full = os.path.join(root_abs, entry)
            if os.path.isfile(full) and entry.endswith(".py"):
                os.makedirs(archive_dir, exist_ok=True)
                dst = os.path.join(archive_dir, entry)
                if os.path.exists(dst):
                    stem, ext = os.path.splitext(entry)
                    dst = os.path.join(archive_dir, f"{stem}_{int(time.time())}{ext}")
                shutil.move(full, dst)
                archived.append(entry)

    return {
        "archived_count": len(archived),
        "archived_files": archived,
        "archive_dir": archive_dir if archived else None,
    }


class CampaignStore:
    """基于单一 campaign.db 的 V4.1 三文件收敛存储管理器"""

    def __init__(self, campaign_dir: str):
        self.campaign_dir = os.path.abspath(campaign_dir)
        os.makedirs(self.campaign_dir, exist_ok=True)
        self.db_path = os.path.join(self.campaign_dir, "campaign.db")
        self.tree_md_path = os.path.join(self.campaign_dir, "RESEARCH_TREE.md")
        self.champions_path = os.path.join(self.campaign_dir, "certified_champions.json")
        self._init_schema()
        if not os.path.exists(self.champions_path):
            with open(self.champions_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    delay INTEGER NOT NULL,
                    category TEXT DEFAULT 'other',
                    seed_alpha_id TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dataset_profiles (
                    campaign_id TEXT PRIMARY KEY,
                    effective_rank REAL NOT NULL,
                    has_vector_fields INTEGER DEFAULT 0,
                    field_count INTEGER DEFAULT 0,
                    eigen_spectrum_json TEXT DEFAULT '[]',
                    profile_json TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hypotheses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    economic_mechanism TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    field_roles_json TEXT NOT NULL,
                    mechanism_intents_json TEXT NOT NULL,
                    falsification_criterion TEXT NOT NULL,
                    parent_alpha_id TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    UNIQUE(campaign_id, hypothesis_id)
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    slot INTEGER DEFAULT 1,
                    mode TEXT NOT NULL,
                    expression TEXT NOT NULL,
                    canonical_key TEXT NOT NULL,
                    topology_key TEXT DEFAULT '',
                    core_skeleton TEXT NOT NULL,
                    settings_json TEXT DEFAULT '{}',
                    change_axis TEXT DEFAULT '',
                    prediction TEXT DEFAULT '',
                    sharpe REAL,
                    is_core_sharpe REAL,
                    holdout_2y_sharpe REAL,
                    fitness REAL,
                    turnover REAL,
                    margin_bps REAL,
                    prod_corr REAL,
                    self_corr REAL,
                    fail_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    checks_json TEXT DEFAULT '[]',
                    raw_result_json TEXT DEFAULT '{}',
                    alpha_id TEXT,
                    status TEXT DEFAULT 'RECORDED',
                    vec_ops_json TEXT DEFAULT '[]',
                    mechanism_families_json TEXT DEFAULT '[]',
                    fields_used_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS verdicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    alpha_id TEXT,
                    expression TEXT,
                    verdict TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}',
                    rationale TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_jobs (
                    job_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    hypothesis_id TEXT DEFAULT '',
                    mode TEXT DEFAULT 'discovery',
                    status TEXT DEFAULT 'QUEUED',
                    payload_json TEXT NOT NULL,
                    progress_json TEXT DEFAULT '{}',
                    summary_json TEXT DEFAULT '{}',
                    error_message TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exp_campaign_skel
                    ON experiments(campaign_id, core_skeleton);
                CREATE INDEX IF NOT EXISTS idx_exp_campaign_canon
                    ON experiments(campaign_id, canonical_key);
                CREATE INDEX IF NOT EXISTS idx_jobs_campaign_status
                    ON pending_jobs(campaign_id, status);
                """
            )
            # Safe migration for existing campaign.db files created before V4.1.1
            cols = {row[1] for row in conn.execute("PRAGMA table_info(experiments)").fetchall()}
            if "topology_key" not in cols:
                conn.execute("ALTER TABLE experiments ADD COLUMN topology_key TEXT DEFAULT ''")
            if "fields_used_json" not in cols:
                conn.execute("ALTER TABLE experiments ADD COLUMN fields_used_json TEXT DEFAULT '[]'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exp_campaign_topo ON experiments(campaign_id, topology_key)"
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def init_campaign(
        self,
        campaign_id: str,
        region: str,
        universe: str,
        dataset_id: str,
        delay: int = 1,
        category: str = "other",
        seed_alpha_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Dict[str, Any]:
        region_u = str(region).strip().upper()
        universe_u = str(universe).strip().upper()
        dataset_l = str(dataset_id).strip().lower()
        delay_i = int(delay)
        now = self._now()

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if row is not None:
                # Enforce immutable Scope Lock when reloading an existing campaign
                if (
                    row["region"].upper() != region_u
                    or row["universe"].upper() != universe_u
                    or row["dataset_id"].lower() != dataset_l
                    or int(row["delay"]) != delay_i
                ):
                    raise ValueError(
                        f"【Scope Lock 冲突】战役 '{campaign_id}' 已锁定在 "
                        f"{row['region']}/{row['universe']}/delay={row['delay']}/{row['dataset_id']}，"
                        f"严禁擅自切换为 {region_u}/{universe_u}/delay={delay_i}/{dataset_l}！"
                    )
                if metadata:
                    merged_meta = json.loads(row["metadata_json"] or "{}")
                    merged_meta.update(metadata)
                    conn.execute(
                        "UPDATE campaigns SET metadata_json = ?, updated_at = ? WHERE campaign_id = ?",
                        (json.dumps(merged_meta, ensure_ascii=False), now, campaign_id),
                    )
                    conn.commit()
            else:
                conn.execute(
                    """
                    INSERT INTO campaigns
                    (campaign_id, region, universe, dataset_id, delay, category, seed_alpha_id, status, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
                    """,
                    (
                        campaign_id, region_u, universe_u, dataset_l, delay_i,
                        str(category or "other").lower(),
                        seed_alpha_id,
                        json.dumps(metadata or {}, ensure_ascii=False),
                        now, now,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

        self.render_research_tree(campaign_id)
        return self.get_campaign(campaign_id) or {}

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if row is None:
                return None
            out = dict(row)
            out["metadata"] = json.loads(out.pop("metadata_json", "{}") or "{}")
            return out
        finally:
            conn.close()

    def save_dataset_profile(
        self,
        campaign_id: str,
        effective_rank: float,
        has_vector_fields: bool,
        field_count: int,
        eigen_spectrum: Optional[List[float]] = None,
        profile_data: Optional[dict] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO dataset_profiles
                (campaign_id, effective_rank, has_vector_fields, field_count, eigen_spectrum_json, profile_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    float(effective_rank),
                    1 if has_vector_fields else 0,
                    int(field_count),
                    json.dumps(eigen_spectrum or [], ensure_ascii=False),
                    json.dumps(profile_data or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.render_research_tree(campaign_id)
        return self.get_dataset_profile(campaign_id) or {}

    def get_dataset_profile(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM dataset_profiles WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if row is None:
                return None
            out = dict(row)
            out["has_vector_fields"] = bool(out.get("has_vector_fields"))
            out["eigen_spectrum"] = json.loads(out.pop("eigen_spectrum_json", "[]") or "[]")
            out["profile"] = json.loads(out.pop("profile_json", "{}") or "{}")
            return out
        finally:
            conn.close()

    def register_hypothesis(
        self,
        campaign_id: str,
        hypothesis_id: str,
        economic_mechanism: str,
        counterparty: str,
        field_roles: Any,
        mechanism_intents: List[str],
        falsification_criterion: str,
        parent_alpha_id: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> Dict[str, Any]:
        now = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO hypotheses
                (campaign_id, hypothesis_id, economic_mechanism, counterparty, field_roles_json,
                 mechanism_intents_json, falsification_criterion, parent_alpha_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    hypothesis_id,
                    economic_mechanism,
                    counterparty,
                    json.dumps(field_roles, ensure_ascii=False),
                    json.dumps(mechanism_intents, ensure_ascii=False),
                    falsification_criterion,
                    parent_alpha_id,
                    status,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.render_research_tree(campaign_id)
        return self.get_hypothesis(campaign_id, hypothesis_id) or {}

    def get_hypothesis(self, campaign_id: str, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM hypotheses WHERE campaign_id = ? AND hypothesis_id = ?",
                (campaign_id, hypothesis_id),
            ).fetchone()
            if row is None:
                return None
            out = dict(row)
            out["field_roles"] = json.loads(out.pop("field_roles_json", "[]") or "[]")
            out["mechanism_intents"] = json.loads(out.pop("mechanism_intents_json", "[]") or "[]")
            return out
        finally:
            conn.close()

    def list_hypotheses(self, campaign_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM hypotheses WHERE campaign_id = ? ORDER BY id ASC",
                (campaign_id,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["field_roles"] = json.loads(d.pop("field_roles_json", "[]") or "[]")
                d["mechanism_intents"] = json.loads(d.pop("mechanism_intents_json", "[]") or "[]")
                out.append(d)
            return out
        finally:
            conn.close()

    def update_hypothesis_status(self, campaign_id: str, hypothesis_id: str, status: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE hypotheses SET status = ? WHERE campaign_id = ? AND hypothesis_id = ?",
                (status, campaign_id, hypothesis_id),
            )
            conn.commit()
        finally:
            conn.close()
        self.render_research_tree(campaign_id)

    def count_core_skeleton(self, campaign_id: str, core_skeleton: str) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND core_skeleton = ? AND mode != 'control'",
                (campaign_id, core_skeleton),
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def count_topology_key(self, campaign_id: str, topology_key: str) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND topology_key = ? AND mode != 'control'",
                (campaign_id, topology_key),
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def has_canonical_key(self, campaign_id: str, canonical_key: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM experiments WHERE campaign_id = ? AND canonical_key = ? LIMIT 1",
                (campaign_id, canonical_key),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def list_experiments(
        self,
        campaign_id: str,
        hypothesis_id: Optional[str] = None,
        topology_key: Optional[str] = None,
        core_skeleton: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM experiments WHERE campaign_id = ?"
            params: List[Any] = [campaign_id]
            if hypothesis_id is not None:
                sql += " AND hypothesis_id = ?"
                params.append(hypothesis_id)
            if topology_key is not None:
                sql += " AND topology_key = ?"
                params.append(topology_key)
            if core_skeleton is not None:
                sql += " AND core_skeleton = ?"
                params.append(core_skeleton)
            sql += " ORDER BY id ASC"
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_experiment_evidence(
        self,
        campaign_id: str,
        alpha_id: str,
        raw_result: Dict[str, Any],
        prod_corr: Optional[float] = None,
        self_corr: Optional[float] = None,
        is_core_sharpe: Optional[float] = None,
        holdout_2y_sharpe: Optional[float] = None,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE experiments
                SET raw_result_json = ?,
                    prod_corr = COALESCE(?, prod_corr),
                    self_corr = COALESCE(?, self_corr),
                    is_core_sharpe = COALESCE(?, is_core_sharpe),
                    holdout_2y_sharpe = COALESCE(?, holdout_2y_sharpe)
                WHERE campaign_id = ? AND alpha_id = ?
                """,
                (
                    json.dumps(raw_result or {}, ensure_ascii=False),
                    prod_corr,
                    self_corr,
                    is_core_sharpe,
                    holdout_2y_sharpe,
                    campaign_id,
                    alpha_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_experiment(self, campaign_id: str, rec: Dict[str, Any]) -> int:
        now = self._now()
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO experiments
                (campaign_id, hypothesis_id, slot, mode, expression, canonical_key, topology_key, core_skeleton,
                 settings_json, change_axis, prediction, sharpe, is_core_sharpe, holdout_2y_sharpe,
                 fitness, turnover, margin_bps, prod_corr, self_corr, fail_count, warning_count,
                 checks_json, raw_result_json, alpha_id, status, vec_ops_json, mechanism_families_json,
                 fields_used_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    rec.get("hypothesis_id", ""),
                    int(rec.get("slot", 1)),
                    rec.get("mode", "discovery"),
                    rec.get("expression", ""),
                    rec.get("canonical_key", ""),
                    rec.get("topology_key", ""),
                    rec.get("core_skeleton", ""),
                    json.dumps(rec.get("settings") or {}, ensure_ascii=False),
                    rec.get("change_axis", ""),
                    rec.get("prediction", ""),
                    rec.get("sharpe"),
                    rec.get("is_core_sharpe"),
                    rec.get("holdout_2y_sharpe"),
                    rec.get("fitness"),
                    rec.get("turnover"),
                    rec.get("margin_bps"),
                    rec.get("prod_corr"),
                    rec.get("self_corr"),
                    int(rec.get("fail_count", 0) or 0),
                    int(rec.get("warning_count", 0) or 0),
                    json.dumps(rec.get("checks") or [], ensure_ascii=False),
                    json.dumps(rec.get("raw_result") or {}, ensure_ascii=False),
                    rec.get("alpha_id"),
                    rec.get("status", "RECORDED"),
                    json.dumps(rec.get("vec_ops") or [], ensure_ascii=False),
                    json.dumps(rec.get("mechanism_families") or [], ensure_ascii=False),
                    json.dumps(rec.get("fields_used") or [], ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_experiment_by_alpha_id(self, campaign_id: str, alpha_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM experiments WHERE campaign_id = ? AND alpha_id = ? ORDER BY id DESC LIMIT 1",
                (campaign_id, alpha_id),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Persistent Async Job Queue (in-DB, zero extra files on disk!)
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_job_row(row: sqlite3.Row) -> Dict[str, Any]:
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json", "{}") or "{}")
        out["progress"] = json.loads(out.pop("progress_json", "{}") or "{}")
        out["summary"] = json.loads(out.pop("summary_json", "{}") or "{}")
        return out

    def enqueue_job(
        self,
        job_id: str,
        campaign_id: str,
        job_type: str,
        payload: Dict[str, Any],
        hypothesis_id: str = "",
        mode: str = "discovery",
    ) -> Dict[str, Any]:
        now = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO pending_jobs
                (job_id, campaign_id, job_type, hypothesis_id, mode, status, payload_json, progress_json, summary_json, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'QUEUED', ?, '{}', '{}', '', ?, ?)
                """,
                (
                    job_id,
                    campaign_id,
                    job_type,
                    hypothesis_id or "",
                    mode or "discovery",
                    json.dumps(payload or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_job(job_id) or {}

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM pending_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            return self._decode_job_row(row) if row is not None else None
        finally:
            conn.close()

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[Dict[str, Any]] = None,
        summary: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sets = ["updated_at = ?"]
        vals: List[Any] = [self._now()]
        if status is not None:
            sets.append("status = ?")
            vals.append(status)
        if progress is not None:
            sets.append("progress_json = ?")
            vals.append(json.dumps(progress, ensure_ascii=False))
        if summary is not None:
            sets.append("summary_json = ?")
            vals.append(json.dumps(summary, ensure_ascii=False))
        if error_message is not None:
            sets.append("error_message = ?")
            vals.append(str(error_message))
        vals.append(job_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE pending_jobs SET {', '.join(sets)} WHERE job_id = ?",
                tuple(vals),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_job(job_id)

    def list_jobs(
        self,
        campaign_id: str,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM pending_jobs WHERE campaign_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                    (campaign_id, status, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pending_jobs WHERE campaign_id = ? ORDER BY created_at DESC LIMIT ?",
                    (campaign_id, int(limit)),
                ).fetchall()
            return [self._decode_job_row(r) for r in rows]
        finally:
            conn.close()

    def get_pending_canonical_keys(self, campaign_id: str) -> Set[str]:
        """收集所有 QUEUED / RUNNING 实验作业中已占坑的 exact_canonical_key，防止重复入队。"""
        keys: Set[str] = set()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT payload_json FROM pending_jobs WHERE campaign_id = ? AND job_type = 'experiment' AND status IN ('QUEUED', 'RUNNING')",
                (campaign_id,),
            ).fetchall()
            for r in rows:
                try:
                    p = json.loads(r["payload_json"] or "{}")
                    for v in p.get("validated_variants") or []:
                        if not v.get("is_control") and v.get("canonical_key"):
                            keys.add(str(v["canonical_key"]))
                except Exception:
                    pass
        finally:
            conn.close()
        return keys

    def record_verdict(
        self,
        campaign_id: str,
        action: str,
        alpha_id: Optional[str],
        expression: Optional[str],
        verdict: str,
        details: dict,
        rationale: str = "",
    ) -> None:
        now = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO verdicts
                (campaign_id, action, alpha_id, expression, verdict, details_json, rationale, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    action,
                    alpha_id,
                    expression or "",
                    verdict,
                    json.dumps(details or {}, ensure_ascii=False),
                    rationale or "",
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.render_research_tree(campaign_id)

    def record_certified_champion(self, campaign_id: str, cert_doc: Dict[str, Any]) -> str:
        """仅在 ProductionGate ALL PASS 后写入 certified_champions.json"""
        existing: List[Dict[str, Any]] = []
        if os.path.exists(self.champions_path):
            try:
                with open(self.champions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        existing = data
            except Exception:
                existing = []

        alpha_id = cert_doc.get("alpha_id")
        expr = cert_doc.get("expression")
        entry = {
            "campaign_id": campaign_id,
            "certified_at": self._now(),
            **cert_doc,
        }
        updated = False
        for i, item in enumerate(existing):
            if (alpha_id and item.get("alpha_id") == alpha_id) or (expr and item.get("expression") == expr):
                existing[i] = entry
                updated = True
                break
        if not updated:
            existing.append(entry)

        with open(self.champions_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        self.render_research_tree(campaign_id)
        return self.champions_path

    def get_certified_champions(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.champions_path):
            return []
        try:
            with open(self.champions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_summary(self, campaign_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            hyp_rows = conn.execute(
                "SELECT * FROM hypotheses WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchall()
            exp_rows = conn.execute(
                "SELECT * FROM experiments WHERE campaign_id = ? ORDER BY id ASC",
                (campaign_id,),
            ).fetchall()
            verdict_rows = conn.execute(
                "SELECT * FROM verdicts WHERE campaign_id = ? ORDER BY id DESC",
                (campaign_id,),
            ).fetchall()
        finally:
            conn.close()

        certified = self.get_certified_champions()
        certified_exprs = {c.get("expression") for c in certified}
        certified_ids = {c.get("alpha_id") for c in certified if c.get("alpha_id")}

        tested_hyp_ids: Set[str] = set()
        families: Set[str] = set()
        vec_ops: Set[str] = set()
        core_skels: Set[str] = set()
        max_sharpe = 0.0
        best_alpha_id = None
        parent_eligible = False
        open_near_miss_leads: List[Dict[str, Any]] = []

        for h in hyp_rows:
            try:
                for intent in json.loads(h["mechanism_intents_json"] or "[]"):
                    if intent:
                        families.add(str(intent).upper())
            except Exception:
                pass

        non_control_count = 0
        fields_tested: Set[str] = set()
        hyp_score_series: Dict[str, List[float]] = {}
        for e in exp_rows:
            if e["mode"] == "control":
                continue
            non_control_count += 1
            if e["hypothesis_id"]:
                tested_hyp_ids.add(e["hypothesis_id"])
            if e["core_skeleton"]:
                core_skels.add(e["core_skeleton"])
            try:
                for vf in json.loads(e["vec_ops_json"] or "[]"):
                    vec_ops.add(vf)
            except Exception:
                pass
            try:
                for fam in json.loads(e["mechanism_families_json"] or "[]"):
                    families.add(fam)
            except Exception:
                pass
            try:
                for fu in json.loads(e["fields_used_json"] or "[]"):
                    if fu:
                        fields_tested.add(str(fu))
            except Exception:
                pass

            sh_val = e["sharpe"]
            score_for_stagnation = e["is_core_sharpe"] if e["is_core_sharpe"] is not None else sh_val
            if e["hypothesis_id"] and score_for_stagnation is not None:
                try:
                    hyp_score_series.setdefault(str(e["hypothesis_id"]), []).append(abs(float(score_for_stagnation)))
                except (TypeError, ValueError):
                    pass

            if sh_val is not None:
                try:
                    ash = abs(float(sh_val))
                    if ash > max_sharpe:
                        max_sharpe = ash
                        best_alpha_id = e["alpha_id"]
                    if ash >= 1.25:
                        parent_eligible = True
                    # Check unresolved near-miss lead
                    is_cert = (e["alpha_id"] in certified_ids) or (e["expression"] in certified_exprs)
                    if ash >= 1.25 and int(e["fail_count"] or 0) == 0 and not is_cert:
                        st = str(e["status"] or "")
                        if st in ("NEAR_MISS", "CANDIDATE", "QUALIFIED"):
                            open_near_miss_leads.append({
                                "alpha_id": e["alpha_id"],
                                "expression": e["expression"],
                                "sharpe": float(sh_val),
                                "hypothesis_id": e["hypothesis_id"],
                            })
                except (TypeError, ValueError):
                    pass

        # Compute semantic cluster coverage from profiled dataset clusters
        prof = self.get_dataset_profile(campaign_id)
        prof_clusters = (prof or {}).get("profile", {}).get("semantic_clusters") or []
        clusters_total = len(prof_clusters)
        clusters_tested = 0
        if clusters_total > 0:
            for cl in prof_clusters:
                cl_fields = set(cl.get("fields") or [])
                if cl_fields.intersection(fields_tested):
                    clusters_tested += 1
        cluster_cov = round(clusters_tested / float(clusters_total), 4) if clusters_total > 0 else 1.0

        # Detect hypothesis-level high-water-mark stagnation Tabu (>= 4 trials with last 2 failing to beat prior HWM + 0.03)
        stagnation_tabu_hypotheses: List[str] = []
        for hid, scores in hyp_score_series.items():
            if len(scores) >= 4:
                prev_hwm = max(scores[:-2])
                recent_best = max(scores[-2:])
                if (recent_best - prev_hwm) < 0.03:
                    stagnation_tabu_hypotheses.append(hid)

        return {
            "campaign_id": campaign_id,
            "hypotheses_registered": len(hyp_rows),
            "orthogonal_hypotheses_count": len(tested_hyp_ids),
            "mechanism_families_covered": sorted(families),
            "vec_scalarizers_tested": sorted(vec_ops),
            "distinct_core_skeletons_count": len(core_skels),
            "fields_tested": sorted(fields_tested),
            "semantic_clusters_total": clusters_total,
            "semantic_clusters_tested": clusters_tested,
            "semantic_cluster_coverage": cluster_cov,
            "stagnation_tabu_hypotheses": sorted(stagnation_tabu_hypotheses),
            "total_experiments": non_control_count,
            "max_abs_sharpe": round(max_sharpe, 4),
            "best_alpha_id": best_alpha_id,
            "parent_eligible": parent_eligible,
            "open_near_miss_leads": open_near_miss_leads,
            "certified_count": len(certified),
            "verdicts_count": len(verdict_rows),
        }

    def render_research_tree(self, campaign_id: str) -> str:
        """每次状态变更自动重渲染只读 RESEARCH_TREE.md"""
        camp = self.get_campaign(campaign_id)
        if not camp:
            return ""
        prof = self.get_dataset_profile(campaign_id)
        summary = self.get_summary(campaign_id)
        hyps = self.list_hypotheses(campaign_id)
        champions = self.get_certified_champions()

        conn = self._connect()
        try:
            recent_exps = conn.execute(
                "SELECT hypothesis_id, slot, mode, alpha_id, is_core_sharpe, sharpe, fitness, turnover, margin_bps, fail_count, warning_count, checks_json, status, expression "
                "FROM experiments WHERE campaign_id = ? ORDER BY id DESC LIMIT 25",
                (campaign_id,),
            ).fetchall()
            verdicts = conn.execute(
                "SELECT action, alpha_id, verdict, rationale, created_at FROM verdicts WHERE campaign_id = ? ORDER BY id DESC LIMIT 10",
                (campaign_id,),
            ).fetchall()
        finally:
            conn.close()

        lines: List[str] = [
            f"# AEGIS V4.1 Research Tree — `{campaign_id}` (Auto-Generated Read-Only)",
            "",
            "## 1. Scope Lock",
            f"- **Region**: `{camp['region']}` | **Universe**: `{camp['universe']}` | **Delay**: `{camp['delay']}` | **Dataset**: `{camp['dataset_id']}`",
        ]
        if camp.get("seed_alpha_id"):
            lines.append(f"- **Targeted Parent Seed Alpha**: `{camp['seed_alpha_id']}`")
        if prof:
            lines.append(
                f"- **Effective Rank ($C_{{eff}}$)**: `{prof['effective_rank']:.3f}` | **Fields**: `{prof['field_count']}` | **Has VECTOR**: `{prof['has_vector_fields']}`"
            )
        lines.extend([
            "",
            "## 2. Coverage & Progress",
            f"- Orthogonal Hypotheses Tested: `{summary['orthogonal_hypotheses_count']}` / Registered: `{summary['hypotheses_registered']}`",
            f"- Distinct Core Skeletons: `{summary['distinct_core_skeletons_count']}` | Total Experiments: `{summary['total_experiments']}`",
            f"- Mechanism Families Covered: `{', '.join(summary['mechanism_families_covered']) or 'None'}`",
            f"- Certified Champions: `{summary['certified_count']}` | Open Near-Miss Leads: `{len(summary['open_near_miss_leads'])}`",
            "",
            "## 3. Registered Hypotheses",
        ])
        if hyps:
            lines.append("| Hypothesis ID | Mechanism | Intents | Status |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for h in hyps:
                mech = str(h["economic_mechanism"]).replace("|", "/")[:80]
                intents = ", ".join(h["mechanism_intents"])
                lines.append(f"| `{h['hypothesis_id']}` | {mech} | `{intents}` | `{h['status']}` |")
        else:
            lines.append("_No hypotheses registered yet._")

        lines.extend(["", "## 4. Recent Experiments (Internal Holdout Masked)"])
        if recent_exps:
            _holdout_kws = ("2Y", "TWO_YEAR", "LADDER", "RECENT")
            _info_warns = {"MATCHES_THEMES", "MATCHES_COMPETITION", "MATCHES_PYRAMID"}
            lines.append("| Hyp | Mode | Alpha ID | IS Core Sharpe | Fitness | Turnover | Margin (bps) | Fails/Warns | Status | Expression |")
            lines.append("| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: | :--- | :--- |")
            for e in recent_exps:
                sh = e["is_core_sharpe"]
                sh_s = f"{sh:.2f}" if sh is not None else "N/A"
                fit_s = f"{e['fitness']:.2f}" if e["fitness"] is not None else "N/A"
                to_s = f"{e['turnover']*100:.1f}%" if e["turnover"] is not None else "N/A"
                mg_s = f"{e['margin_bps']:.1f}" if e["margin_bps"] is not None else "N/A"
                disp_fails = int(e["fail_count"] or 0)
                disp_warns = int(e["warning_count"] or 0)
                disp_status = str(e["status"] or "RECORDED")
                if str(e["mode"] or "").lower() in ("discovery", "surgery"):
                    try:
                        chk_list = json.loads(e["checks_json"] or "[]")
                    except Exception:
                        chk_list = []
                    if isinstance(chk_list, list) and chk_list:
                        disp_fails = sum(
                            1 for c in chk_list
                            if isinstance(c, dict)
                            and str(c.get("result") or "").upper() in ("FAIL", "ERROR")
                            and not any(kw in str(c.get("name") or "").upper() for kw in _holdout_kws)
                        )
                        disp_warns = sum(
                            1 for c in chk_list
                            if isinstance(c, dict)
                            and str(c.get("result") or "").upper() == "WARNING"
                            and str(c.get("name") or "").upper() not in _info_warns
                            and not any(kw in str(c.get("name") or "").upper() for kw in _holdout_kws)
                        )
                    if disp_status != "CONTROL":
                        disp_status = (
                            "NEAR_MISS"
                            if (sh is not None and abs(float(sh)) >= 1.25 and disp_fails == 0)
                            else "RECORDED"
                        )
                expr_s = str(e["expression"]).replace("\n", " ").replace("|", "/")[:70]
                lines.append(
                    f"| `{e['hypothesis_id']}` | `{e['mode']}` | `{e['alpha_id'] or '-'}` | {sh_s} | {fit_s} | {to_s} | {mg_s} | {disp_fails}/{disp_warns} | `{disp_status}` | `{expr_s}` |"
                )
        else:
            lines.append("_No experiments executed yet._")

        lines.extend(["", "## 5. Certified Champions & Verdicts"])
        if champions:
            for c in champions:
                lines.append(f"- 🏆 `{c.get('alpha_id')}` | Sharpe={c.get('sharpe')} | ProdCorr={c.get('prod_corr')} | Expr: `{str(c.get('expression', '')).replace(chr(10), ' ')}`")
        if verdicts:
            for v in verdicts:
                lines.append(f"- [{v['created_at']}] `{v['action']}` -> **{v['verdict']}** ({v['alpha_id'] or '-'}) {str(v['rationale'])[:100]}")

        md_text = "\n".join(lines) + "\n"
        with open(self.tree_md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        return self.tree_md_path
