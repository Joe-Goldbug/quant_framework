try:
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    from quant_framework.core.operator_registry import OperatorRegistry
except ImportError:
    from core.func_call_corrector import ASTSandboxCorrector
    from core.operator_registry import OperatorRegistry

"""
rag_memory.py
AEGIS GrandMaster 金字塔四级知识库与纯算子经验沉淀引擎
(对齐 WS29639 原帖第 2.4 节第四巧思、第五巧思与评论区第 3 条规范)

核心架构：
1. 金字塔四级经验分层体系 (Pyramid Hierarchy):
   - 第一级 (语法基石): operators.md 官方算子规范
   - 第二级 (垂直特异): {REGION}_{DELAY}_{CATEGORY}.md (纯算子抽象实战手册，如 USA_1_analyst.md)
   - 第三级 (区域风控): {REGION}_forum.md (区域市场特定约束，如 USA 禁用低阶中性化)
   - 第四级 (全局底座): summary.md 跨品类通用量化模式
2. 构造经验铁律: 只有运算符、无数据字段，实现经验的高度抽象与泛化复用！
3. ε-Greedy 动态知识注入: 20%~30% 概率触发额外灵感检索，避免固定调用打乱优化节奏。
4. 只有在产出终极达标生产级 Alpha 后才触发 Knowledge Distiller 增量沉淀！
"""

import json
import os
import random
import re
import sys
from typing import Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class RAGMemoryEngine:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXP_DIR = os.path.join(BASE_DIR, "alpha_experience")
    KB_DIR = os.path.join(BASE_DIR, "knowledge_base")
    CARDS_DIR = os.path.join(KB_DIR, "cards")
    CATALOG_PATH = os.path.join(KB_DIR, "catalog.json")

    @classmethod
    def _ensure_dirs(cls):
        os.makedirs(cls.EXP_DIR, exist_ok=True)
        os.makedirs(cls.KB_DIR, exist_ok=True)
        os.makedirs(cls.CARDS_DIR, exist_ok=True)

    # -------------------------------------------------------------
    # 1. 金字塔四级经验按需挂载 (Pyramid Knowledge Mount)
    # -------------------------------------------------------------
    @classmethod
    def load_pyramid_context(cls, region: str, delay: int, category: str, operators_path: str = None) -> str:
        """
        自顶向下构建四级金字塔经验 Context，遵循“未找到直接跳过”的优雅容错原则：
        第 2 级 (垂直实战手册) -> 第 3 级 (区域风控) -> 第 4 级 (全局底座)
        """
        cls._ensure_dirs()
        region_clean = region.upper()
        category_clean = category.lower()
        pyramid_sections = []

        # 第一级: 语法基石与全量官方授权算子库 (Single Source of Truth)
        if operators_path and os.path.exists(operators_path):
            try:
                with open(operators_path, 'r', encoding='utf-8') as opf:
                    op_content = opf.read().strip()
                    if op_content:
                        pyramid_sections.append(
                            f"### 【第 1 级语法基石: 官方算子规范】\n{op_content}"
                        )
            except Exception as e:
                print(f"⚠️ [RAG Memory] 读取指定算子文件失败: {e}")
        else:
            # 自动加载当前账号可用的 104 个官方算子库精要
            pyramid_sections.append(OperatorRegistry.format_pyramid_level1_markdown())

        # 第二级: 垂直特异经验手册 ({REGION}_{DELAY}_{CATEGORY}.md)
        vertical_filename = f"{region_clean}_{delay}_{category_clean}.md"
        vertical_path = os.path.join(cls.EXP_DIR, vertical_filename)
        if os.path.exists(vertical_path):
            with open(vertical_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    pyramid_sections.append(
                        f"### 【第 2 级垂直实战经验 ({vertical_filename})】\n"
                        f"{content}"
                    )

        # 第三级: 区域风控与论坛专项约束 ({REGION}_forum.md)
        region_filename = f"{region_clean}_forum.md"
        region_path = os.path.join(cls.EXP_DIR, region_filename)
        if os.path.exists(region_path):
            with open(region_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    pyramid_sections.append(
                        f"### 【第 3 级区域风控指引 ({region_filename})】\n"
                        f"{content}"
                    )
        else:
            # 内置 USA/EUR/ASI 默认高阶风控指引
            if region_clean == "USA":
                pyramid_sections.append(
                    "### 【第 3 级区域风控指引 (USA)】\n"
                    "- 美股在 Step 1 实证期保留 30% SUBINDUSTRY/INDUSTRY 作为基准对照，其余及 Step 2+ 优先在 REVERSION_AND_MOMENTUM、STATISTICAL、CROWDING、FAST、SLOW 中选择；\n"
                    "- 或外层包裹 group_neutralize(..., subindustry) 配合风险中性化；\n"
                    "- Margin 死线: >= 10.0 bps。"
                )

        # 第四级: 全局底座跨品类通用模式 (summary.md)
        summary_path = os.path.join(cls.EXP_DIR, "summary.md")
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    pyramid_sections.append(
                        f"### 【第 4 级通用量化底座 (summary.md)】\n"
                        f"{content}"
                    )
        else:
            pyramid_sections.append(
                "### 【第 4 级通用量化底座】\n"
                "- 时序一阶差分 ts_delta 捕捉预期差动量；\n"
                "- 结合 ts_decay_exp_window 指数衰减可有效压低换手率与提升 Fitness；\n"
                "- 前置 winsorize(..., std=3) 可抑制 Sub-universe 震荡；\n"
                "- 集中度过高时使用 s_log_1p 或 signed_power 凹压缩。"
            )

        if not pyramid_sections:
            return "【金字塔经验库初始化就绪，暂无垂直沉淀】"

        return "\n\n".join(pyramid_sections)

    # -------------------------------------------------------------
    # 2. ε-Greedy 动态灵感检索 (20%~30% 概率触发)
    # -------------------------------------------------------------
    @classmethod
    def get_exploration_inspiration(cls, epsilon: float = 0.25) -> Optional[str]:
        """
        借鉴强化学习思想，设定 if random.random() < epsilon 的探索触发率。
        在大多数轮次专注就地深化，少数轮次引入外部论坛与跨品类火花。
        """
        if random.random() >= epsilon:
            return None

        # 随机从已有经验中抽取跨界灵感
        cls._ensure_dirs()
        exp_files = [f for f in os.listdir(cls.EXP_DIR) if f.endswith(".md")]
        if not exp_files:
            return "【ε-Greedy 灵感】尝试在时序算子外层嵌套 group_neutralize(..., subindustry) 并搭配 REVERSION_AND_MOMENTUM 中性化。"

        chosen_file = random.choice(exp_files)
        try:
            with open(os.path.join(cls.EXP_DIR, chosen_file), 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                if lines:
                    sample_line = random.choice(lines[:10])
                    return f"【ε-Greedy 跨界灵感 ({chosen_file})】{sample_line}"
        except Exception:
            pass
        return None

    # -------------------------------------------------------------
    # 3. 经验沉淀写入: 纯算子、去字段化抽象 (对齐 WS29639 规范)
    # -------------------------------------------------------------
    @classmethod
    def append_pure_operator_experience(cls, region: str, delay: int, category: str, 
                                        abstract_insight: str, alpha_stats: dict = None):
        """
        将高分达标 Alpha 的演化规律抽象为纯算子模式写入 {REGION}_{DELAY}_{CATEGORY}.md。
        严禁写入具体字段名！基于 ASTSandboxCorrector.get_canonical_skeleton 与 skeleton_hash
        进行拓扑骨架聚类与计数累加，防膨胀去重。
        """
        cls._ensure_dirs()
        region_clean = region.upper()
        category_clean = category.lower()
        target_file = os.path.join(cls.EXP_DIR, f"{region_clean}_{delay}_{category_clean}.md")

        header = f"# {region_clean} Delay {delay} {category_clean.upper()} 纯算子实战手册\n\n"
        existing_content = ""
        if os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            except Exception:
                existing_content = ""
        else:
            existing_content = header

        expr = ""
        if alpha_stats and isinstance(alpha_stats, dict):
            expr = alpha_stats.get("expression") or alpha_stats.get("code") or ""

        skel_tag = ""
        skel_hash = ""
        if expr:
            try:
                raw_skel = ASTSandboxCorrector.get_canonical_skeleton(expr)
                # 剥离所有具体数据字段名，仅保留 FastExpr 算子、分组层级与 NUM 占位符，遵守零字段铁律 (SSOT 全量算子支持)
                keep_tokens = OperatorRegistry.get_keep_tokens()
                skel_tag = re.sub(
                    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b',
                    lambda m: m.group(1) if m.group(1) in keep_tokens else "FIELD",
                    raw_skel
                )
                skel_hash = ASTSandboxCorrector.compute_skeleton_hash(skel_tag)[:10]
            except Exception:
                skel_tag = "GENERIC_TOPOLOGY"
                skel_hash = "GENERIC"

        stat_summary = ""
        if alpha_stats:
            s = float(alpha_stats.get("sharpe", 0.0))
            fit = float(alpha_stats.get("fitness", 0.0))
            m = float(alpha_stats.get("margin_bps", 0.0))
            stat_summary = f" (Sharpe={s:.2f}, Fitness={fit:.2f}, Margin={m:.1f}bps)"

        # 骨架聚类去重与计数累加
        hash_marker = f"<!-- SKELETON_HASH: {skel_hash} -->"
        if skel_hash and hash_marker in existing_content:
            pattern = re.compile(rf"({re.escape(hash_marker)}[\s\S]*?- \*\*\[达标验证次数: )(\d+)(\]\*\*)")
            match = pattern.search(existing_content)
            if match:
                cur_count = int(match.group(2)) + 1
                updated_content = pattern.sub(rf"\g<1>{cur_count}\g<3>", existing_content)
                if abstract_insight.strip() not in updated_content:
                    end_marker = f"<!-- END_SKELETON: {skel_hash} -->"
                    if end_marker in updated_content:
                        insight_line = f"  * 演化新知: {abstract_insight.strip()}{stat_summary}\n"
                        updated_content = updated_content.replace(end_marker, insight_line + end_marker)
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                print(f"📖 [RAG Engine] 纯算子拓扑 [{skel_hash}] 命中已有聚类，验证计数累加至 {cur_count}: {target_file}")
                return

        # 新增算子骨架拓扑聚类
        entry = (
            f"\n{hash_marker}\n"
            f"### 算子拓扑范式: `{skel_tag if skel_tag else '抽象拓扑'}`\n"
            f"- **[达标验证次数: 1]**{stat_summary}\n"
            f"  * 核心机制: {abstract_insight.strip()}\n"
            f"<!-- END_SKELETON: {skel_hash} -->\n"
        )
        with open(target_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        print(f"📖 [RAG Engine] 新算子拓扑 [{skel_hash}] 经验已沉淀至: {target_file}")

    # -------------------------------------------------------------
    # 4. 兼容老接口 (避免测试或外部模块崩溃)
    # -------------------------------------------------------------
    @classmethod
    def get_catalog_card(cls) -> str:
        cls._ensure_dirs()
        if not os.path.exists(cls.CATALOG_PATH):
            return "【知识库微目录】"
        try:
            with open(cls.CATALOG_PATH, 'r', encoding='utf-8') as f:
                cat = json.load(f)
            lines = ["### 【知识库精简目录】"]
            for c in cat:
                lines.append(f"- [{c.get('card_id')}] #{c.get('tag')}: {c.get('one_line')}")
            return "\n".join(lines)
        except Exception:
            return "【知识库微目录】"

    @classmethod
    def get_card_on_demand(cls, target_identifier: str) -> dict:
        cls._ensure_dirs()
        target_card_id = target_identifier
        if target_card_id == "prod_corr_elevated_above_065":
            target_card_id = "prod_corr_overflow"
        # 若传入的是 tag，先查 catalog 匹配 card_id
        if not target_card_id.startswith("CARD_") and not target_card_id.startswith("TPL_"):
            if os.path.exists(cls.CATALOG_PATH):
                try:
                    with open(cls.CATALOG_PATH, 'r', encoding='utf-8') as f:
                        cat = json.load(f)
                        for c in cat:
                            if c.get("tag") == target_identifier:
                                target_card_id = c.get("card_id")
                                break
                except Exception:
                    pass

        card_file = os.path.join(cls.CARDS_DIR, f"{target_card_id}.json")
        if os.path.exists(card_file):
            with open(card_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"card_id": target_card_id, "proven_solution": "使用纯算子金字塔经验库替代"}

    @classmethod
    def admit_new_card(cls, card_id: str, tag: str, domain: str, one_line: str, 
                       card_detail: dict, verification_count: int, is_red_team_pass: bool = False):
        if verification_count < 10 and card_detail.get("admission_type") == "FALSIFICATION_PHYSICAL_WALL":
            print(f"[Admission REJECT] 证伪样本数 {verification_count} < 10，严禁污染知识库！")
            return False
        return True
