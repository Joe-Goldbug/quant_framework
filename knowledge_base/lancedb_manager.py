"""
knowledge_base/lancedb_manager.py
AEGIS 3.0 基于 LanceDB 的原子化因果 QA 知识库管理器
(严格对齐图 2 数据架构: 官方规则表 + 论坛与实战经验表，以问答形式组织，严禁死板模板)
"""

import os
import re
import json
import time
from typing import Any, Dict, List, Optional
import pyarrow as pa
import lancedb


class LanceDBQAManager:
    FORUM_TABLE = "wqb_forum_experiences"
    OFFICIAL_TABLE = "wqb_official_guides"

    QA_ARROW_SCHEMA = pa.schema([
        pa.field("id", pa.string()),
        pa.field("question", pa.string()),
        pa.field("answer", pa.string()),
        pa.field("symptom", pa.string()),
        pa.field("tags", pa.string()),          # 逗号分隔的标签字符串
        pa.field("source_type", pa.string()),   # 'forum' | 'battle_post_mortem' | 'official'
        pa.field("source_id", pa.string()),     # 帖子 ID 或战役 ID
        pa.field("heat_score", pa.float32()),   # 互动热度与时效加权分
        pa.field("created_at", pa.string()),
    ])

    def __init__(self, db_dir: Optional[str] = None):
        if db_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_dir = os.path.join(base_dir, "knowledge_base", "lancedb_data")
        self.db_dir = os.path.abspath(db_dir)
        os.makedirs(self.db_dir, exist_ok=True)
        self.db = lancedb.connect(self.db_dir)
        self._init_tables()

    def _init_tables(self):
        """确保两张核心表存在"""
        existing = set(self.db.table_names())
        if self.FORUM_TABLE not in existing:
            self.db.create_table(self.FORUM_TABLE, schema=self.QA_ARROW_SCHEMA)
        if self.OFFICIAL_TABLE not in existing:
            self.db.create_table(self.OFFICIAL_TABLE, schema=self.QA_ARROW_SCHEMA)

    def add_qa_records(self, records: List[Dict[str, Any]], table_name: str = FORUM_TABLE) -> int:
        """
        批量写入或更新原子化 QA 记录 (去重插入)
        """
        if not records:
            return 0

        tbl = self.db.open_table(table_name)
        cleaned = []
        for r in records:
            tags_val = r.get("tags", "")
            if isinstance(tags_val, list):
                tags_val = ",".join(str(t).strip() for t in tags_val)
            
            cleaned.append({
                "id": str(r.get("id", f"QA_{int(time.time()*1000)}")),
                "question": str(r.get("question", "")).strip(),
                "answer": str(r.get("answer", "")).strip(),
                "symptom": str(r.get("symptom", "")).strip(),
                "tags": str(tags_val).strip(),
                "source_type": str(r.get("source_type", "forum")),
                "source_id": str(r.get("source_id", "manual")),
                "heat_score": float(r.get("heat_score", 50.0)),
                "created_at": str(r.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")))
            })

        tbl.add(cleaned)
        return len(cleaned)

    def query_qa(
        self,
        query: str,
        symptom: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 3,
        table_name: str = FORUM_TABLE
    ) -> List[Dict[str, Any]]:
        """
        根据病灶 (Symptom)、用户查询 (Query) 和标签 (Tags) 检索最匹配的原子化 QA 决策经验
        采用多重加权相关度打分 (关键词覆盖 + 病灶重合度 + 标签重合 + 热度增益)
        """
        tbl = self.db.open_table(table_name)
        df = tbl.to_pandas()
        if df.empty:
            return []

        search_text = f"{query} {symptom or ''}".lower()
        search_tokens = set(re.findall(r'[\w\-]+', search_text))
        target_tags = set(t.lower() for t in (tags or []))

        scored_records = []
        for _, row in df.iterrows():
            q_text = str(row["question"]).lower()
            a_text = str(row["answer"]).lower()
            s_text = str(row["symptom"]).lower()
            row_tags = set(t.strip().lower() for t in str(row["tags"]).split(",") if t.strip())

            score = 0.0

            # 1. 标签强匹配增益
            common_tags = target_tags.intersection(row_tags)
            score += len(common_tags) * 30.0

            # 2. 病灶词重合度打分
            if symptom:
                symptom_tokens = set(re.findall(r'[\w\-]+', symptom.lower()))
                s_overlap = len(symptom_tokens.intersection(set(re.findall(r'[\w\-]+', s_text))))
                score += s_overlap * 20.0

            # 3. 问题与回答的词项覆盖率打分
            for tok in search_tokens:
                if tok in q_text:
                    score += 15.0
                elif tok in s_text:
                    score += 10.0
                elif tok in a_text:
                    score += 3.0

            # 4. 热度时效微调加权 (0~10分)
            heat = float(row.get("heat_score", 50.0))
            score += min(10.0, heat * 0.1)

            scored_records.append((score, row.to_dict()))

        # 按打分降序排列
        scored_records.sort(key=lambda x: x[0], reverse=True)
        top_matches = [r[1] for r in scored_records[:top_k] if r[0] > 0]
        
        # 若打分为0则保底返回热度最高的条目
        if not top_matches:
            top_matches = df.sort_values(by="heat_score", ascending=False).head(top_k).to_dict("records")

        return top_matches

    def get_stats(self) -> Dict[str, int]:
        """获取各表记录数统计"""
        stats = {}
        for t in [self.FORUM_TABLE, self.OFFICIAL_TABLE]:
            try:
                tbl = self.db.open_table(t)
                stats[t] = len(tbl.to_pandas())
            except Exception:
                stats[t] = 0
        return stats
