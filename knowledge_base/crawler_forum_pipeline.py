"""
knowledge_base/crawler_forum_pipeline.py
AEGIS 3.0 论坛数据收集、热度过滤与 LLM 原子化提炼流水线
(严格对齐图 2 架构: Playwright 爬虫 -> 原始 Markdown -> 热度时效筛选 -> LLM 原子化 QA -> LanceDB)
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from knowledge_base.lancedb_manager import LanceDBQAManager


class ForumQAPipeline:
    """论坛爬取与原子化提炼流水线"""

    def __init__(self, db_dir: Optional[str] = None):
        self.mgr = LanceDBQAManager(db_dir=db_dir)

    @classmethod
    def calculate_heat_score(
        cls,
        upvotes: int = 0,
        replies: int = 0,
        favorites: int = 0,
        is_featured: bool = False,
        days_ago: float = 0.0
    ) -> float:
        """
        计算带时间半衰期衰减的高价值热度得分:
        Score = (10*Featured + 5*Favorites + 3*Upvotes + 2*Replies) / ((1 + days/180)^1.2)
        """
        raw_engagement = (
            (10.0 if is_featured else 0.0) +
            5.0 * favorites +
            3.0 * upvotes +
            2.0 * replies
        )
        time_decay = (1.0 + (days_ago / 180.0)) ** 1.2
        return round(float(raw_engagement / max(0.1, time_decay)), 2)

    @classmethod
    def filter_high_value_posts(
        cls,
        posts: List[Dict[str, Any]],
        min_heat_score: float = 25.0,
        max_age_days: float = 730.0  # 默认过滤2年以上的过时帖子
    ) -> List[Dict[str, Any]]:
        """
        Step 2: 热度与时效双重筛选 (filter_post)
        """
        filtered = []
        for p in posts:
            days_ago = float(p.get("days_ago", 0.0))
            if days_ago > max_age_days:
                continue

            score = cls.calculate_heat_score(
                upvotes=int(p.get("upvotes", 0)),
                replies=int(p.get("replies", 0)),
                favorites=int(p.get("favorites", 0)),
                is_featured=bool(p.get("is_featured", False)),
                days_ago=days_ago
            )
            p["heat_score"] = score
            if score >= min_heat_score:
                filtered.append(p)

        filtered.sort(key=lambda x: x["heat_score"], reverse=True)
        return filtered

    @classmethod
    def get_atomization_prompt(cls, post_title: str, post_content: str) -> str:
        """
        Step 3: 生成 LLM 原子化因果提炼 Prompt (严禁输出死板模板)
        """
        return f"""# Role & Objective
你是一名资深量化研究专家（Lead Quant PM）。你的任务是将以下 WorldQuant Brain 顾问论坛的高价值帖子，提炼为 1~2 个【痛点病灶 & 因果决策型 QA（问答）】。

# 核心戒律（绝对禁止与强制要求）：
1. 【严禁死板处方】：严禁输出“必须使用 X 算子”、“遇到情绪字段只能中性化”等绝对化指令！
2. 【必须权衡分析】：每条经验必须阐述适用场景、数学金融机理、多种可选应对策略（方案 A / 方案 B 的优缺点与适用条件）、潜在副作用与反模式。
3. 【具体问题具体分析】：让下游 Agent 读到回答后能根据具体数据分布与回测病灶自适应决策，而不是死搬硬套。

# 输入帖子：
标题: {post_title}
正文内容:
{post_content}

# 输出要求 (请输出合法 JSON 列表):
[
  {{
    "question": "当在量化研发中遇到 [具体病灶或场景] 时，底层金融数学根因是什么？有哪些权衡应对策略？",
    "answer": "【底层根因】：...\\n\\n【权衡应对决策树】：\\n1. 方案 A：做法、适用条件、潜在风险；\\n2. 方案 B：做法、适用条件、潜在风险；\\n\\n【反模式与红线】：...",
    "symptom": "病灶特征摘要（如：2020年断崖亏损、CW集中度>0.10超标）",
    "tags": ["核心标签1", "算子名", "场景标签"]
  }}
]
"""

    def ingest_distilled_qa(self, qa_list: List[Dict[str, Any]], post_id: str, heat_score: float) -> int:
        """将提炼完成的 QA 存入 LanceDB 论坛经验表"""
        records = []
        for idx, qa in enumerate(qa_list):
            records.append({
                "id": f"QA_FORUM_{post_id}_{idx+1}",
                "question": qa.get("question", ""),
                "answer": qa.get("answer", ""),
                "symptom": qa.get("symptom", ""),
                "tags": qa.get("tags", []),
                "source_type": "forum",
                "source_id": str(post_id),
                "heat_score": float(heat_score)
            })
        return self.mgr.add_qa_records(records, table_name=self.mgr.FORUM_TABLE)
