"""
knowledge_base/post_mortem_distiller.py
AEGIS 3.0 战役实战自动复盘提炼器 (Automated Post-Mortem Distiller)
(当产生突破性/达标 Alpha 时自动闭环提炼原子化 QA 并追加写入 LanceDB)
"""

import ast
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


class PostMortemDistiller:
    """
    战役结项复盘器:
    比对母本与优胜变体的 AST 拓扑差分与逐年回测数据变化，
    沉淀出具备因果权衡深度的原子化 QA 经验对。
    """
    def __init__(self, db_dir: Optional[str] = None):
        self.mgr = LanceDBQAManager(db_dir=db_dir)

    @classmethod
    def analyze_ast_diff(cls, seed_expr: str, champ_expr: str) -> Dict[str, Any]:
        """静态分析 AST 变异算子增删与结构变化"""
        def _get_ops(expr_text):
            try:
                tree = ast.parse(expr_text, mode="eval")
                return [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
            except Exception:
                return []

        seed_ops = set(_get_ops(seed_expr))
        champ_ops = set(_get_ops(champ_expr))

        added_ops = list(champ_ops - seed_ops)
        removed_ops = list(seed_ops - champ_ops)
        return {
            "seed_ops": list(seed_ops),
            "champ_ops": list(champ_ops),
            "added_ops": added_ops,
            "removed_ops": removed_ops
        }

    def distill_and_record(
        self,
        campaign_name: str,
        seed_alpha_id: str,
        seed_expr: str,
        seed_metrics: dict,
        champ_alpha_id: str,
        champ_expr: str,
        champ_metrics: dict,
        resolved_symptoms: Optional[List[str]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        比对两代 Alpha，提炼出原子化 QA 并存入 LanceDB
        """
        ast_diff = self.analyze_ast_diff(seed_expr, champ_expr)

        s_sharpe = seed_metrics.get("sharpe", 0.0)
        c_sharpe = champ_metrics.get("sharpe", 0.0)
        s_fit = seed_metrics.get("fitness", 0.0)
        c_fit = champ_metrics.get("fitness", 0.0)
        s_fails = seed_metrics.get("fail", [])
        c_fails = champ_metrics.get("fail", [])

        # 构造问题
        symptom_str = "、".join(resolved_symptoms) if resolved_symptoms else "历史特定年份失血与回测瓶颈"
        question = (
            f"在优化 Alpha [{seed_alpha_id} -> {champ_alpha_id}] 时，针对母本暴露出的 [{symptom_str}] 病灶，"
            f"如何通过 AST 算子谱重构实现突破？有哪些关键权衡取舍？"
        )

        # 构造回答
        added_str = ", ".join(ast_diff["added_ops"]) if ast_diff["added_ops"] else "无"
        removed_str = ", ".join(ast_diff["removed_ops"]) if ast_diff["removed_ops"] else "无"
        
        answer = (
            f"【微观病灶与优化背景】：\n"
            f"母本 Alpha ({seed_alpha_id}) 表现为: Sharpe={s_sharpe}, Fitness={s_fit}, Fails={len(s_fails)}。\n"
            f"核心病灶: {symptom_str}。\n\n"
            f"【AST 拓扑变异与机理】：\n"
            f"- 引入新算子: [{added_str}]；剔除算子: [{removed_str}]。\n"
            f"- 优化机理与因果逻辑: {notes or '重构了底层数据时序分布映射，消除了极端异常值对多空截面的失衡扰动。'}\n\n"
            f"【最终实战成效与权衡】：\n"
            f"优胜版本 ({champ_alpha_id}) 达成: Sharpe {s_sharpe} -> {c_sharpe}，Fitness {s_fit} -> {c_fit}，硬伤数降至 {len(c_fails)} FAIL。\n"
            f"权衡建议: 变异后需核验近 2 年夏普 (2Y Sharpe) 与生产池相关性，避免参数高原过拟合。"
        )

        tags = ["post_mortem", campaign_name] + ast_diff["added_ops"]
        qa_id = f"QA_POST_MORTEM_{champ_alpha_id}_{int(time.time())}"

        qa_record = {
            "id": qa_id,
            "question": question,
            "answer": answer,
            "symptom": symptom_str,
            "tags": tags,
            "source_type": "battle_post_mortem",
            "source_id": f"{campaign_name}_{champ_alpha_id}",
            "heat_score": 95.0,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.mgr.add_qa_records([qa_record], table_name=self.mgr.FORUM_TABLE)
        print(f"✨ [Post-Mortem] 成功提炼战役实战经验 QA: {qa_id} 并沉淀至 LanceDB！")
        return qa_record
