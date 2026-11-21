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
    def _filter_dgp_scoped_experience(cls, content: str, dgp_signatures: Optional[List[str]]) -> str:
        """只保留 DGP 物理签名匹配的实现级经验；无签名时返回空，禁止跨物理形态复用。"""
        if not dgp_signatures:
            return ""
        signature_set = {str(s) for s in dgp_signatures if s}
        blocks = content.split("<!-- SKELETON_HASH:")
        matched = []
        for block in blocks[1:]:
            if any(signature in block for signature in signature_set):
                matched.append("<!-- SKELETON_HASH:" + block)
        return "\n".join(matched).strip()

    @classmethod
    def load_pyramid_context(
        cls,
        region: str,
        delay: int,
        category: str,
        operators_path: str = None,
        dgp_signatures: Optional[List[str]] = None,
    ) -> str:
        """
        自顶向下构建四级金字塔经验 Context:
        - 第 1 级是语法事实，可全量挂载;
        - 第 2 级实现级经验必须匹配 DGP 物理签名后才挂载;
        - 第 3/4 级是风控与通用原则，不提供具体算子处方。
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
            # V4.1.1: 仅注入 <1KB 极简分类算子索引，彻底杜绝 16KB 全量算子菜单重力诱导套积木
            pyramid_sections.append(OperatorRegistry.format_compact_index_markdown())

        # 第二级: 垂直特异经验手册 ({REGION}_{DELAY}_{CATEGORY}.md)
        # V2: 仅当 DGP 物理签名匹配时才挂载实现级经验，切断跨物理形态乱套算子
        vertical_filename = f"{region_clean}_{delay}_{category_clean}.md"
        vertical_path = os.path.join(cls.EXP_DIR, vertical_filename)
        if os.path.exists(vertical_path):
            with open(vertical_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                # None 表示 legacy 调用，保留旧行为；显式签名列表为空则不挂载实现级经验
                scoped_content = content if dgp_signatures is None else cls._filter_dgp_scoped_experience(content, dgp_signatures)
                if scoped_content:
                    pyramid_sections.append(
                        f"### 【第 2 级 DGP 匹配实战经验 ({vertical_filename})】\n"
                        f"{scoped_content}"
                    )
                elif dgp_signatures:
                    pyramid_sections.append(
                        "### 【第 2 级 DGP 匹配实战经验】\n"
                        "当前字段物理签名没有历史实现级经验，请从 HypothesisSpec 第一性原理推导。"
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
                    "- 美股在 Step 1 实证期保留 30% SUBINDUSTRY/INDUSTRY 作为基准对照，其余及 Step 2+ 优先根据信号经济内涵自主选择中性化方式；\n"
                    "- Margin 生产底线: >= 10.0 bps。"
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
                "- 先声明信息事件、对手盘与期限结构，再决定数学实现；\n"
                "- 稀疏事件与连续存量字段不得共用同一套平滑假设；\n"
                "- 任何外层包装必须能通过消融检验，否则视为装饰；\n"
                "- 相关性与稳健性证据缺失时保持 PENDING，不得视为通过。"
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
        在大多数轮次专注就地深化，少数轮次引入外部论坛与跨品类启发。
        严禁泄露具体算子表达式或死模板，仅提取高维因果与病理治理启示。
        """
        if random.random() >= epsilon:
            return None

        # 随机从已有经验中抽取跨界因果启发
        cls._ensure_dirs()
        exp_files = [f for f in os.listdir(cls.EXP_DIR) if f.endswith(".md")]
        if not exp_files:
            return "【ε-Greedy 灵感】尝试从字段更新频率、零值语义与信息半衰期重新推导期限结构，先写出所需变换再查算子签名表映射实现，而不是套用历史外壳。"

        chosen_file = random.choice(exp_files)
        try:
            with open(os.path.join(cls.EXP_DIR, chosen_file), 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取所有 QA 块或启发条目，严禁输出具体代码/公式模板或劝退/换数据集暗示
            _DEFEATIST_RE = re.compile(
                r'(?:换数据集|更换数据源|更换数据集|已穷尽|因子饱和|天花板|彻底放弃|建议切换)'
            )
            sections = re.split(r'\n(?=###?\s+)', content)
            valid_insights = []
            for sec in sections:
                clean_sec = sec.strip()
                if not clean_sec or clean_sec.startswith("# "):
                    continue
                if _DEFEATIST_RE.search(clean_sec):
                    # 仅保留非劝退行；若整节以劝退结论为主则跳过
                    filtered = [
                        l.strip() for l in clean_sec.split('\n')
                        if l.strip() and not _DEFEATIST_RE.search(l)
                        and not l.strip().startswith("```")
                        and not re.search(r'^[a-z_]{2,}\([a-z0-9_,\s\(\)]+\)$', l.strip())
                    ]
                    if len(filtered) >= 2:
                        valid_insights.append("\n".join(filtered[:4]))
                    continue
                lines = [l.strip() for l in clean_sec.split('\n') if l.strip()]
                # 剔除代码块和类似单纯公式表达式的行
                meaningful_lines = [
                    l for l in lines
                    if not l.startswith("```") and not re.search(r'^[a-z_]{2,}\([a-z0-9_,\s\(\)]+\)$', l)
                ]
                if meaningful_lines:
                    valid_insights.append("\n".join(meaningful_lines[:4]))

            if valid_insights:
                chosen_insight = random.choice(valid_insights)
                return f"【ε-Greedy 跨界因果启发 ({chosen_file})】:\n{chosen_insight}"
        except Exception:
            pass
        return "【ε-Greedy 灵感】从 DGP 数据生成过程出发，根据字段连续/离散与偏态特征，动态选择截面或时序算子解耦噪声。"

    # -------------------------------------------------------------
    # 3. 经验沉淀写入: DGP 物理签名绑定的算子拓扑经验
    # -------------------------------------------------------------
    @classmethod
    def append_pure_operator_experience(cls, region: str, delay: int, category: str, 
                                        abstract_insight: str, alpha_stats: dict = None):
        """
        将生产达标 Alpha 的演化规律写入 {REGION}_{DELAY}_{CATEGORY}.md。

        V2 规则:
        1. 不写具体字段名，但必须写 DGP 物理签名 (Role/Freq/Sparse/Skew/Crowding);
        2. 缺少 DGP 签名的样本拒绝沉淀，防止变成无物理前提的纯算子模板;
        3. 检索侧只挂载签名匹配的实现级经验。
        """
        cls._ensure_dirs()
        alpha_stats = alpha_stats if isinstance(alpha_stats, dict) else {}
        dgp_signatures = alpha_stats.get("dgp_signatures") or []
        if not isinstance(dgp_signatures, list) or not dgp_signatures:
            print("🚫 [RAG Engine] 样本缺少 dgp_signatures，拒绝沉淀无物理前提的纯算子经验。")
            return False

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

        # 新增算子骨架拓扑聚类 (仅记录哈希与物理因果规律，不向 Markdown 正文暴露死骨架)
        dgp_scope = " | ".join(str(s) for s in dgp_signatures)
        entry = (
            f"\n{hash_marker}\n"
            f"### 因果机制沉淀条目 [{skel_hash}]\n"
            f"- **DGP_SCOPE**: {dgp_scope}\n"
            f"- **[达标验证次数: 1]**{stat_summary}\n"
            f"  * 核心机制: {abstract_insight.strip()}\n"
            f"<!-- END_SKELETON: {skel_hash} -->\n"
        )
        with open(target_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        print(f"📖 [RAG Engine] 新 DGP 绑定算子拓扑 [{skel_hash}] 经验已沉淀至: {target_file}")
        return True

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
