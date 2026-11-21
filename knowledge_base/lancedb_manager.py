"""
knowledge_base/lancedb_manager.py
AEGIS 3.0 / 4.1 原子化因果 QA 知识库管理器
优先使用 LanceDB/PyArrow；当环境缺失 pyarrow 或 lancedb 时，自动启用等效 SQLite 兜底后端，保证全功能与单元测试零依赖通过。
"""

import os
import re
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

try:
    import pyarrow as pa
    import lancedb
    _HAS_LANCEDB = True
except ImportError:
    pa = None
    lancedb = None
    _HAS_LANCEDB = False


try:
    import pandas as pd
except ImportError:
    pd = None


class _SQLiteTableAdapter:
    def __init__(self, mgr: "LanceDBQAManager", table_name: str):
        self._mgr = mgr
        self._table_name = table_name

    def add(self, records: List[Dict[str, Any]]) -> int:
        return self._mgr.add_qa_records(records, table_name=self._table_name)

    def to_pandas(self):
        rows = self._mgr._fetch_all_rows(self._table_name)
        if pd is not None:
            return pd.DataFrame(rows)
        return rows


class _SQLiteDBAdapter:
    def __init__(self, mgr: "LanceDBQAManager"):
        self._mgr = mgr

    def table_names(self) -> List[str]:
        return [self._mgr.FORUM_TABLE, self._mgr.OFFICIAL_TABLE]

    def open_table(self, table_name: str) -> _SQLiteTableAdapter:
        self._mgr._validate_table_name(table_name)
        return _SQLiteTableAdapter(self._mgr, table_name)


class LanceDBQAManager:
    FORUM_TABLE = "wqb_forum_experiences"
    OFFICIAL_TABLE = "wqb_official_guides"

    if _HAS_LANCEDB:
        QA_ARROW_SCHEMA = pa.schema([
            pa.field("id", pa.string()),
            pa.field("question", pa.string()),
            pa.field("answer", pa.string()),
            pa.field("symptom", pa.string()),
            pa.field("tags", pa.string()),
            pa.field("source_type", pa.string()),
            pa.field("source_id", pa.string()),
            pa.field("heat_score", pa.float32()),
            pa.field("created_at", pa.string()),
        ])
    else:
        QA_ARROW_SCHEMA = None

    def __init__(self, db_dir: Optional[str] = None):
        if db_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_dir = os.path.join(base_dir, "knowledge_base", "lancedb_data")
        self.db_dir = os.path.abspath(db_dir)
        os.makedirs(self.db_dir, exist_ok=True)
        self._use_sqlite = not _HAS_LANCEDB
        if not self._use_sqlite:
            self.db = lancedb.connect(self.db_dir)
            self.sqlite_path = None
        else:
            self.sqlite_path = os.path.join(self.db_dir, "qa_fallback.sqlite")
            self.db = _SQLiteDBAdapter(self)
        self._init_tables()

    def _connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        if table_name not in (LanceDBQAManager.FORUM_TABLE, LanceDBQAManager.OFFICIAL_TABLE):
            raise ValueError(f"非法的 QA 表名: {table_name}")
        return table_name

    def _init_tables(self):
        """确保两张核心表存在"""
        if not self._use_sqlite:
            existing = set(self.db.table_names())
            if self.FORUM_TABLE not in existing:
                self.db.create_table(self.FORUM_TABLE, schema=self.QA_ARROW_SCHEMA)
            if self.OFFICIAL_TABLE not in existing:
                self.db.create_table(self.OFFICIAL_TABLE, schema=self.QA_ARROW_SCHEMA)
            return

        with self._connect_sqlite() as conn:
            for tbl in (self.FORUM_TABLE, self.OFFICIAL_TABLE):
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {tbl} (
                        id TEXT PRIMARY KEY,
                        question TEXT,
                        answer TEXT,
                        symptom TEXT,
                        tags TEXT,
                        source_type TEXT,
                        source_id TEXT,
                        heat_score REAL,
                        created_at TEXT
                    )
                    """
                )
            conn.commit()

    def add_qa_records(self, records: List[Dict[str, Any]], table_name: str = FORUM_TABLE) -> int:
        """批量写入或更新原子化 QA 记录"""
        if not records:
            return 0
        self._validate_table_name(table_name)

        cleaned = []
        for idx, r in enumerate(records):
            tags_val = r.get("tags", "")
            if isinstance(tags_val, list):
                tags_val = ",".join(str(t).strip() for t in tags_val)
            cleaned.append({
                "id": str(r.get("id", f"QA_{int(time.time()*1000)}_{idx}")),
                "question": str(r.get("question", "")).strip(),
                "answer": str(r.get("answer", "")).strip(),
                "symptom": str(r.get("symptom", "")).strip(),
                "tags": str(tags_val).strip(),
                "source_type": str(r.get("source_type", "forum")),
                "source_id": str(r.get("source_id", "manual")),
                "heat_score": float(r.get("heat_score", 50.0)),
                "created_at": str(r.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))),
            })

        if not self._use_sqlite:
            tbl = self.db.open_table(table_name)
            tbl.add(cleaned)
            return len(cleaned)

        with self._connect_sqlite() as conn:
            conn.executemany(
                f"""
                INSERT OR REPLACE INTO {table_name}
                (id, question, answer, symptom, tags, source_type, source_id, heat_score, created_at)
                VALUES (:id, :question, :answer, :symptom, :tags, :source_type, :source_id, :heat_score, :created_at)
                """,
                cleaned,
            )
            conn.commit()
        return len(cleaned)

    def _fetch_all_rows(self, table_name: str) -> List[Dict[str, Any]]:
        self._validate_table_name(table_name)
        if not self._use_sqlite:
            tbl = self.db.open_table(table_name)
            df = tbl.to_pandas()
            return [] if df.empty else df.to_dict("records")

        with self._connect_sqlite() as conn:
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            return [dict(r) for r in rows]

    def query_qa(
        self,
        query: str,
        symptom: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 3,
        table_name: str = FORUM_TABLE,
    ) -> List[Dict[str, Any]]:
        """根据病灶 (Symptom)、用户查询 (Query) 和标签 (Tags) 检索最匹配的原子化 QA 决策经验"""
        rows = self._fetch_all_rows(table_name)
        if not rows:
            return []

        search_text = f"{query} {symptom or ''}".lower()
        search_tokens = set(re.findall(r'[\w\-]+', search_text))
        target_tags = set(t.lower() for t in (tags or []))

        scored_records = []
        for row in rows:
            q_text = str(row.get("question", "")).lower()
            a_text = str(row.get("answer", "")).lower()
            s_text = str(row.get("symptom", "")).lower()
            row_tags = set(t.strip().lower() for t in str(row.get("tags", "")).split(",") if t.strip())

            score = 0.0
            common_tags = target_tags.intersection(row_tags)
            score += len(common_tags) * 30.0

            if symptom:
                symptom_tokens = set(re.findall(r'[\w\-]+', symptom.lower()))
                s_overlap = len(symptom_tokens.intersection(set(re.findall(r'[\w\-]+', s_text))))
                score += s_overlap * 20.0

            for tok in search_tokens:
                if tok in q_text:
                    score += 15.0
                elif tok in s_text:
                    score += 10.0
                elif tok in a_text:
                    score += 3.0

            heat = float(row.get("heat_score", 50.0) or 50.0)
            score += min(10.0, heat * 0.1)
            scored_records.append((score, dict(row)))

        scored_records.sort(key=lambda x: x[0], reverse=True)
        top_matches = [r[1] for r in scored_records[:top_k] if r[0] > 0]
        if not top_matches:
            rows_sorted = sorted(rows, key=lambda r: float(r.get("heat_score", 0.0) or 0.0), reverse=True)
            top_matches = rows_sorted[:top_k]
        return top_matches

    def get_stats(self) -> Dict[str, int]:
        """获取各表记录数统计"""
        stats: Dict[str, int] = {}
        for t in (self.FORUM_TABLE, self.OFFICIAL_TABLE):
            try:
                stats[t] = len(self._fetch_all_rows(t))
            except Exception:
                stats[t] = 0
        return stats

    def apply_exponential_decay(
        self,
        half_life_days: float = 14.0,
        min_heat: float = 10.0,
        table_name: str = FORUM_TABLE,
    ) -> int:
        """基于创建时间与半衰期，对经验记录执行指数衰减"""
        self._validate_table_name(table_name)
        if not self._use_sqlite:
            tbl = self.db.open_table(table_name)
            df = tbl.to_pandas()
            if df.empty:
                return 0
            now_ts = time.time()
            for idx, row in df.iterrows():
                created_str = str(row.get("created_at", ""))
                try:
                    created_ts = time.mktime(time.strptime(created_str, "%Y-%m-%d %H:%M:%S"))
                except Exception:
                    created_ts = now_ts
                delta_days = max(0.0, (now_ts - created_ts) / 86400.0)
                cur_heat = float(row.get("heat_score", 50.0))
                new_heat = max(min_heat, cur_heat * (0.5 ** (delta_days / half_life_days)))
                df.at[idx, "heat_score"] = float(new_heat)
            self.db.create_table(table_name, data=df, schema=self.QA_ARROW_SCHEMA, mode="overwrite")
            return len(df)

        rows = self._fetch_all_rows(table_name)
        if not rows:
            return 0
        now_ts = time.time()
        updates = []
        for row in rows:
            created_str = str(row.get("created_at", ""))
            try:
                created_ts = time.mktime(time.strptime(created_str, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                created_ts = now_ts
            delta_days = max(0.0, (now_ts - created_ts) / 86400.0)
            cur_heat = float(row.get("heat_score", 50.0) or 50.0)
            new_heat = float(max(min_heat, cur_heat * (0.5 ** (delta_days / half_life_days))))
            updates.append((new_heat, row["id"]))
        with self._connect_sqlite() as conn:
            conn.executemany(f"UPDATE {table_name} SET heat_score = ? WHERE id = ?", updates)
            conn.commit()
        return len(updates)

    def record_experience_outcome(
        self,
        qa_id: str,
        success: bool = True,
        table_name: str = FORUM_TABLE,
    ) -> bool:
        """根据后续回测结果反馈经验热度: 成功 (+15.0 分)，失败 (-10.0 分)"""
        self._validate_table_name(table_name)
        if not self._use_sqlite:
            tbl = self.db.open_table(table_name)
            df = tbl.to_pandas()
            if df.empty or qa_id not in df["id"].values:
                return False
            idx = df[df["id"] == qa_id].index[0]
            cur_heat = float(df.at[idx, "heat_score"])
            delta = 15.0 if success else -10.0
            df.at[idx, "heat_score"] = float(max(10.0, min(100.0, cur_heat + delta)))
            self.db.create_table(table_name, data=df, schema=self.QA_ARROW_SCHEMA, mode="overwrite")
            return True

        with self._connect_sqlite() as conn:
            row = conn.execute(f"SELECT heat_score FROM {table_name} WHERE id = ?", (qa_id,)).fetchone()
            if row is None:
                return False
            cur_heat = float(row["heat_score"] or 50.0)
            delta = 15.0 if success else -10.0
            new_heat = float(max(10.0, min(100.0, cur_heat + delta)))
            conn.execute(f"UPDATE {table_name} SET heat_score = ? WHERE id = ?", (new_heat, qa_id))
            conn.commit()
        return True
