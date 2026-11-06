"""
core/qa_rag_tool.py
AEGIS 3.0 主脑原子化 QA 检索工具 (RAG Heuristic Tool for Lead Quant PM)
支持主脑在遇到回测病灶时自适应检索因果决策启示，或由 Agent 主动调用。
"""

import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from knowledge_base.lancedb_manager import LanceDBQAManager


_GLOBAL_QA_MGR = None

def get_qa_manager() -> LanceDBQAManager:
    global _GLOBAL_QA_MGR
    if _GLOBAL_QA_MGR is None:
        _GLOBAL_QA_MGR = LanceDBQAManager()
    return _GLOBAL_QA_MGR


def search_qa_knowledge(
    query: str,
    symptom: Optional[str] = None,
    tags: Optional[List[str]] = None,
    top_k: int = 2
) -> List[Dict[str, Any]]:
    """
    检索原子化因果 QA 知识库:
    - query: 核心问题关键词 (如 "分母除零", "换手率过低", "CW集中度超标")
    - symptom: 具体病灶描述 (如 "2020年夏普负值", "LOW_SHARPE警告")
    - tags: 关联标签列表 (如 ["ts_quantile", "neutralization"])
    - top_k: 返回最佳条数 (默认 2 条高精经验)
    """
    mgr = get_qa_manager()
    return mgr.query_qa(query=query, symptom=symptom, tags=tags, top_k=top_k)


def format_qa_for_prompt(qa_records: List[Dict[str, Any]]) -> str:
    """
    将检索出的 QA 格式化为给主脑注入的思考启发 Markdown 模块 (非死板处方，提供权衡启示)
    """
    if not qa_records:
        return ""

    blocks = ["### 💡 历史实战与论坛高价值决策启发 (Heuristic QA Insights - 仅供因果权衡参考，严禁死套模板):"]
    for idx, r in enumerate(qa_records, 1):
        q = r.get("question", "")
        a = r.get("answer", "")
        tags = r.get("tags", "")
        blocks.append(f"\n#### 【启发 {idx}】{q}\n- **关联标签**: `{tags}`\n{a}")

    return "\n".join(blocks)
