"""
main.py
AEGIS GrandMaster 纯 Python 状态机总控调度引擎
(完全复刻 WS29639 原帖 GrandMaster 设计：Python + AI 模式，极度节约 Token & 完全可控)

核心工程特性：
1. 纯 Python 宿主死循环接管调度，淘汰 LLM 总控与长对话上下文累积；
2. Plan 1 单步会话隔离：每次迭代仅注入 Top-5 最优标杆与随机抽样的 20 个潜力候选；
3. 阶段 0 纯四则运算双字段主信号池 (total_signals.json)，带有 times 探索计数器；
4. 阶段 1 群体发散 (func1): 锁定主信号核心，50% 全新探索 + 50% 母本演进，注入区域高阶中性化；
5. 本地 2ms AST 语法解析修复与 MD5 指纹防重 (alphas_record.db)；
6. 阶梯漏斗早停: Step 1 若无 |Sharpe| >= 1.0 立即熔断换种子，0 Token 纠缠，绝不让 AI 写千字失败总结；
7. Step 5 自动升阶: 累计 >= 3 个优质候选无缝晋级深水区精炼 (func2)；
8. 经验提炼 (Knowledge Distiller): 仅当产出终审达标 Alpha 后触发，且经验中只有运算符、无具体字段。
"""

import argparse
import ast
import asyncio
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Union

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from quant_framework.core.agy_client import GeminiClient, VirtualSession
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    from quant_framework.core.dimension_rules import DimensionAuditor
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.rag_memory import RAGMemoryEngine
    from quant_framework.core.sim_runner import SimBatchRunner, get_brain_module
except (ModuleNotFoundError, ImportError):
    from core.agy_client import GeminiClient, VirtualSession
    from core.func_call_corrector import ASTSandboxCorrector
    from core.dimension_rules import DimensionAuditor
    from core.gatekeeper import Gatekeeper
    from core.rag_memory import RAGMemoryEngine
    from core.sim_runner import SimBatchRunner, get_brain_module

try:
    from quant_framework.core.crowding_pairing import FieldCrowdingProfiler, enforce_stage0_pairing
    from quant_framework.core.horizon_probe import HorizonProbe
    from quant_framework.core.swarm_auditor import SwarmAuditor
except (ModuleNotFoundError, ImportError):
    from core.crowding_pairing import FieldCrowdingProfiler, enforce_stage0_pairing
    from core.horizon_probe import HorizonProbe
    from core.swarm_auditor import SwarmAuditor

try:
    from quant_framework.core.field_resolver import DatasetFieldResolver
except ModuleNotFoundError:
    from core.field_resolver import DatasetFieldResolver

# 全球市场动态高阶中性化字典 (对齐原帖第 6.1 节)
REGION_NEUTRALIZATIONS_DICT = {
    "USA": ["REVERSION_AND_MOMENTUM", "STATISTICAL", "CROWDING", "FAST", "SLOW"],
    "EUR": ["SUBINDUSTRY", "COUNTRY", "STATISTICAL", "REVERSION_AND_MOMENTUM"],
    "GBR": ["SUBINDUSTRY", "STATISTICAL", "REVERSION_AND_MOMENTUM"],
    "DEU": ["SUBINDUSTRY", "STATISTICAL", "REVERSION_AND_MOMENTUM"],
    "ASI": ["SUBINDUSTRY", "INDUSTRY", "MARKET"],
    "GLB": ["SUBINDUSTRY", "COUNTRY", "INDUSTRY"],
    "IND": ["SUBINDUSTRY", "INDUSTRY"],
    "MEA": ["SUBINDUSTRY", "INDUSTRY"]
}

# 冠军因子 Margin 溢价门槛 (远高于区域准入底线，确保单笔交易利润厚实)
REGION_CHAMPION_MARGIN_BPS = {
    "USA": 15.0, "EUR": 15.0,
    "ASI": 18.0, "GLB": 18.0, "GBR": 18.0, "DEU": 18.0,
    "IND": 25.0, "MEA": 25.0
}

# 事件驱动型类别: 大量股票在无信息日数值不变，必须用 trade_when 冻结持仓
EVENT_DRIVEN_CATEGORIES = {"news", "sentiment", "analyst", "socialmedia", "earnings", "insider"}


class AegisPipelineController:
    def __init__(self, region: str = "USA", universe: str = "TOP1000", delay: int = 1,
                 category: str = "news", dataset_id: str = "news12", model: str = "Built-in Agent",
                 parallelism: int = 20, targeted_alpha_id: str = None, base_dir: str = None,
                 mock_only: bool = False, backend_type: str = "builtin", fields_file: str = None,
                 raw_fields_arg: str = None, allow_cross_region_fields: bool = True, tasks_dir: str = None,
                 max_operator_count: Optional[int] = None):
        self.region = region.upper()
        self.universe = universe.upper()
        self.delay = delay
        self.category = category.lower()
        self.dataset_id = dataset_id
        self.model = model
        self.parallelism = parallelism
        self.targeted_alpha_id = targeted_alpha_id
        self.mock_only = mock_only
        self.backend_type = backend_type
        self.fields_file = fields_file
        self.raw_fields_arg = raw_fields_arg
        self.allow_cross_region_fields = allow_cross_region_fields
        self.tasks_dir = tasks_dir
        
        self.is_quasi_champion_optimization = bool(self.targeted_alpha_id)
        # 研究员说明: 研究挖掘阶段要求算子尽可能简单 <= 6 (经济学意义、信号纯粹，防过拟合)。
        # 仅仅是在研究员明确说明在准冠军 alpha 基础上进入优化阶段才放宽到 <= 10 算子。
        if max_operator_count is not None:
            self.max_champion_operators = int(max_operator_count)
        else:
            self.max_champion_operators = 10 if self.is_quasi_champion_optimization else 6
        self.max_ast_operators = 10 if (self.is_quasi_champion_optimization or (max_operator_count and max_operator_count > 8)) else 8

        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        # 并发隔离: 多个 Agent 同时研究同一 (region, category, dataset) 时会互相覆盖
        # total_signals.json / 指纹库 / 回测缓存。通过环境变量追加隔离后缀，
        # 默认空字符串 => 行为与原先完全一致。
        campaign_name = f"{self.region}_{self.category}_{self.dataset_id}"
        _campaign_suffix = os.environ.get("AEGIS_CAMPAIGN_SUFFIX", "").strip()
        if _campaign_suffix:
            campaign_name = f"{campaign_name}__{_campaign_suffix}"
        self.campaign_dir = os.path.join(self.base_dir, "campaigns", campaign_name)
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        os.makedirs(self.campaign_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        self.signals_pool_file = os.path.join(self.campaign_dir, "total_signals.json")
        self.kb_fields_file = os.path.join(self.base_dir, "knowledge_base", "fields", self.region, f"{self.dataset_id}.json")
        self.corrector = ASTSandboxCorrector()
        self.field_resolver = DatasetFieldResolver(base_dir=self.base_dir)
        self.client = GeminiClient(
            default_model=self.model,
            mock_only=self.mock_only,
            backend_type=self.backend_type,
            tasks_dir=self.tasks_dir
        )
        
        # 固定战役历史文件与持久化记忆加载 (支持跨进程断点恢复)
        self.history_file = os.path.join(self.campaign_dir, "campaign_history.txt")
        self.memory_file = os.path.join(self.campaign_dir, "campaign_memory.json")
        self.good_alphas: List[dict] = []
        self.history_save: List[dict] = []
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as mf:
                    mem = json.load(mf)
                    self.good_alphas = mem.get("good_alphas", [])
                    self.history_save = mem.get("history_save", [])
            except Exception:
                pass

    def save_campaign_memory(self):
        """持久化保存全局战役记忆 (good_alphas 与 history_save)"""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as mf:
                json.dump({
                    "good_alphas": self.good_alphas,
                    "history_save": self.history_save
                }, mf, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_supported_neutralizations(self) -> List[str]:
        return REGION_NEUTRALIZATIONS_DICT.get(self.region, ["SUBINDUSTRY", "STATISTICAL"])

    # -------------------------------------------------------------
    # 阶段 0: 纯四则运算双字段主信号池管理 (Seed Reservoir)
    # -------------------------------------------------------------
    def load_signals_pool(self) -> dict:
        if os.path.exists(self.signals_pool_file):
            with open(self.signals_pool_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "region": self.region,
            "delay": self.delay,
            "universe": self.universe,
            "category": self.category,
            "dataset_id": self.dataset_id,
            "signals": []
        }

    def save_signals_pool(self, pool_data: dict):
        with open(self.signals_pool_file, 'w', encoding='utf-8') as f:
            json.dump(pool_data, f, ensure_ascii=False, indent=2)
        self.save_campaign_memory()

    def load_dataset_fields(self) -> dict:
        """通过 DatasetFieldResolver 解析字段字典，支持多格式自适应、跨区域同源继承与自定义注入"""
        effective_file = self.fields_file
        if not effective_file and hasattr(self, "kb_fields_file") and os.path.exists(self.kb_fields_file):
            effective_file = self.kb_fields_file

        return self.field_resolver.resolve_fields(
            region=self.region,
            category=self.category,
            dataset_id=self.dataset_id,
            fields_file=effective_file,
            raw_fields_arg=self.raw_fields_arg,
            allow_cross_region=self.allow_cross_region_fields
        )

    ALL_TEMPORAL_OPS = {
        "ts_delta", "ts_decay", "ts_mean", "ts_std_dev", "ts_zscore", "ts_rank",
        "ts_decay_linear", "ts_decay_exp_window", "ts_delay", "ts_corr", "ts_product",
        "ts_sum", "ts_min", "ts_max", "ts_arg_max", "ts_arg_min", "ts_median"
    }
    ALLOWED_SHOCK_TEMPORAL = {"ts_delta", "ts_decay_linear", "ts_zscore", "ts_mean"}

    @classmethod
    def _get_ast_temporal_calls(cls, expr_str: str) -> List[str]:
        try:
            tree = ast.parse(expr_str, mode='eval')
            calls = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    if n.func.id in cls.ALL_TEMPORAL_OPS or n.func.id.startswith("ts_"):
                        calls.append(n.func.id)
            return calls
        except Exception:
            return ["UNKNOWN"]

    def synthesize_stage0_seeds(self, count: int = 10) -> List[dict]:
        """
        阶段 0: 纯四则运算双字段主信号原型生成
        基于 Plan 1 独立会话由 aegis-seed-synthesizer 生成，并经 aegis-tech-auditor 严格审查
        仅使用 (+ - * /) + Vector 标量化，严禁提前嵌套时序算子！
        """
        print(f"\n🌱 【Stage 0: 离线主信号原型生成 (Seed Reservoir)】")
        fields_dict = self.load_dataset_fields()
        all_field_names = list(fields_dict.keys())
        if not all_field_names:
            raise FileNotFoundError(
                f"❌ 无法从数据集中加载有效字段画像: {self.region}/{self.dataset_id}！\n"
                f"   系统严禁使用伪造假字段推进流程，请先建立真实字段元数据画像。"
            )

        # 过滤有效覆盖率字段并使用确定性随机种子抽样，防止跨进程 Resume 时抽样字段漂移
        valid_fields = [f for f in all_field_names if fields_dict.get(f, {}).get("coverage", 1.0) >= 0.20] or all_field_names
        rng = random.Random(f"{self.region}_{self.dataset_id}")
        sampled_names = rng.sample(valid_fields, min(100, len(valid_fields))) if len(valid_fields) > 100 else valid_fields

        # 组装结构化特征卡片 (提取全部探针元数据画像，拒绝黑盒截断)
        fields_meta_list = []
        for fn in sampled_names:
            meta = fields_dict.get(fn, {})
            fields_meta_list.append({
                "name": fn,
                "type": meta.get("type", "MATRIX"),
                "description": meta.get("description", "无描述"),
                "coverage": round(meta.get("coverage", 1.0), 3),
                "alpha_count": meta.get("alpha_count", meta.get("alphaCount", 0)),
                "user_count": meta.get("user_count", meta.get("userCount", 0)),
                "domain": meta.get("domain", "unbounded"),
                "is_sparse": meta.get("is_sparse", False),
                "update_frequency": meta.get("update_frequency", "quarterly" if self.category == "fundamental" else "daily"),
                "semantic_role": meta.get("semantic_role", "Signal_Flow"),
                "skewness": meta.get("skewness", "medium")
            })

        # ---------------- 铁律 A: 拥挤度画像 + 冷热非对称配对清单 ----------------
        profiler = FieldCrowdingProfiler(fields_dict)
        fields_meta_list = profiler.annotate_cards(fields_meta_list)
        pairing_candidates = profiler.candidate_pairs(limit=8)
        prof_stats = profiler.summary()
        print(
            f"🧊 [拥挤度画像] 字段 {prof_stats['field_total']} 个 | "
            f"冷门(后40%) {prof_stats['tier_counts'].get('COLD', 0)} | "
            f"拥挤(前30%) {prof_stats['tier_counts'].get('HOT', 0)} | "
            f"可用冷热配对 {len(pairing_candidates)} 组"
        )
        if not pairing_candidates:
            print("⚠️ [铁律 A 预警] 当前字段池缺少「低拥挤主锚 x 高覆盖归一锚」的可用组合，配对校验将通过率可能偏低。")

        session = self.client.create_session(role="aegis-seed-synthesizer", model=self.model)
        prompt = (
            f"你是一位顶级的 WorldQuant 量化研究总监。请深入研读下方给定的数据集字段全量画像，构建 {count} 个高价值、低相关性、非过拟合的原生主信号假说。\n"
            f"目标配置: 区域 {self.region} | 股票池 {self.universe} | 预测延迟 Delay {self.delay} | 类别 {self.category} | 数据集 {self.dataset_id}\n\n"
            f"【核心认知准则：严禁“先想好简单公式再编造故事”！必须严格按以下四步思维链自上而下推导】：\n"
            f"1. 第一步：字段商业实质与拥挤度剖析 (dataset_field_study)\n"
            f"   - 仔细核查每个字段的 description（真实业务含义）、coverage（覆盖率）、alpha_count（已产出因子拥挤度）、alpha_pct（拥挤度分位）、crowding_tier（COLD/WARM/HOT）、domain（值域）与 update_frequency（更新周期）。\n"
            f"   - 找出该数据集中能够反映企业经营摩擦、预期偏差或资金行为异动的 3~5 个正交业务簇 (economic_clusters)。\n"
            f"   - 【低相关性铁律】：每个业务簇及后续每个信号中，必须优先选用高 coverage 但低 alpha_count（未被全平台过度挖掘）的细分字段作为核心信息源！\n"
            f"2. 第二步：深度字段语义映射 (field_semantics_mapping)\n"
            f"   - 针对选定的 2~4 个字段，逐一阐明其物理量纲与业务角色：谁是反映边际变化的【主信号源】？谁是用于剥离规模/行业基数混杂效应的【内生归一化锚点】？谁是度量信息确定性或催化强度的【状态调节项】？\n"
            f"   - 明确解释：为什么这几个字段放在一起会产生单一字段无法提供的增量信息（正交交互价值）？\n"
            f"3. 第三步：微观市场摩擦与因果传导机制 (economic_mechanism & expected_polarity)\n"
            f"   - 完整写出因果链条：[底层经营/预期/舆情发生何种结构性变动] -> [哪类市场参与者（分析师/机构/散户）因何种制度约束或认知偏误未能及时充分定价] -> [未来超额收益的释放方向与预期极性 expected_polarity (+1 代表该代数项越大未来收益越高，-1 代表越低)]。\n"
            f"4. 第四步：从机理自然涌现代数表达式 (expression)\n"
            f"   - 唯有当上述三步完全确立后，才将第三步的数学关系精确翻译为极简代数表达式。\n\n"
            f"【经济学母题词汇表 (Economic Motif Vocabulary)——只提供机制语义与变换意图，严禁套用固定死公式】：\n"
            f"- 相对利差与剪刀差 (Relative Spread / Divergence): 剥离共同宏观/行业趋势，刻画多空力量、预期差或供需剪刀差。自归一化，最纯粹正交；\n"
            f"- 规模与基数消除 (Scale & Baseline Normalization): 结合总量基准消除市值、规模或总体曝光偏倚，注意必须结合字段物理定义域（如金额/比率/概率）设计安全无偏的归一化方式；\n"
            f"- 交互调节与催化放大 (Interaction & Conditioning): 利用置信度、惊奇度或催化剂指标调节主信号的风险敞口，实现有条件的强弱放大；\n"
            f"- 分布离散度与信息不确定性 (Dispersion & Uncertainty Proxy): 刻画截面离散度、市场参与者分歧度或预期迷茫度，捕捉市场定价效率低下期；\n"
            f"- 尾心曲率与两极分化 (Tail-to-Center / Kurtosis Proxy): 刻画分布形态是两极化厚尾（高分歧/危机）还是单峰收敛，捕捉极端定价机会；\n"
            f"- 边际冲击与动态跃迁 (Temporal Shock - 仅限 SHOCK 假说): 捕捉慢变量水平值背后的突变动量或意外冲击（如超预期业绩修正、舆情突变）。\n\n"
            f"【铁律 A：主锚字段与归一化字段的“冷热非对称配对”(本批由 Python 物理校验，不合规种子直接拒收)】：\n"
            f"- 严禁全部扎堆使用 alpha_count 最高的热门字段，也严禁所有字段都从 HOT 档里挑；\n"
            f"- 每个种子的字段组合必须同时满足：\n"
            f"  * 分子主信号 = 1 个低拥挤度细分字段 (coverage >= 0.25 且 alpha_pct <= 0.40，即 COLD 档)，代表未被充分挖掘的细分业务流或特定情绪维度；\n"
            f"  * 分母/差分基准 = 1 个高覆盖度内生总量字段 (coverage >= 0.80，如总资产、总报道数、一致预期均值)，用于剥离规模噪音；\n"
            f"- 该配对既保证信号在截面上的逻辑完备性，又从源头避开全平台拥挤赛道，是 ProdCorr < 0.65 的结构性前提；\n"
            f"- 下方已给出可直接采用的冷热配对清单 (pairing_candidates)，可据此展开假说，但不得照抄公式。\n\n"
            f"【硬性反模板与阶段算子复杂度预算】：\n"
            f"- 复杂度预算：Stage 0 表达式外层总算子数必须 <= 3，保持因果逻辑极简与纯粹；\n"
            f"- 假说举证准入 (hypothesis_type)：\n"
            f"  * LEVEL (状态假说，默认)：仅使用基础代数算子 (add, subtract, multiply, divide, reverse) 与 vec_* 标量化，严禁时序与截面算子；\n"
            f"  * SHOCK (边际突变/状态冲击假说)：允许且仅允许使用恰好 1 个基础时序算子 (ts_delta, ts_decay_linear, ts_zscore, ts_mean)，且必须在因果链中举证突变逻辑并匹配 update_frequency (日频 3~21，季频 60+)；\n"
            f"- 绝对红线：Stage 0 严禁使用任何截面算子 (group_*, rank) 与非线性装潢算子 (winsorize, s_log_1p, signed_power, hump)，100% 留待 Stage 1 根据回测病灶对症解锁；严禁混入任何外部量价 (PV) 字段；\n"
            f"- 标注原因的反面清单 (Negative Anti-Patterns)：\n"
            f"  * ❌ 盲目套用非负除数：严禁机械式拼接无意义分母！若分子已是纯剪刀差，根本无需除法分母；若需除法，分母必须具备明确的内生规模/基数含义，且严防除零与符号反转；\n"
            f"  * ❌ 伪因果相乘：双 [-1, 1] 字段严禁直接相乘（负负得正造成虚假利好伪因果）；\n"
            f"  * ❌ 维度混杂加减：将不同物理量纲、未进行无量纲化或未在同一空间对齐的字段直接加减。\n\n"
            f"【候选字段全量物理画像清单 (含拥挤度分位与配对角色建议)】:\n{json.dumps(fields_meta_list, ensure_ascii=False, indent=1)}\n\n"
            f"【推荐冷热非对称配对清单】:\n{json.dumps(pairing_candidates, ensure_ascii=False, indent=1)}\n\n"
            f"【输出格式契约】必须返回严格的 JSON 对象（严格按以下键顺序输出，先完成深度研究与机理映射，最后才输出 expression）：\n"
            f"{{\n"
            f'  "dataset_field_study": {{\n'
            f'    "dataset_essence": "对该数据集底层商业生成过程、更新频率特征与核心未充分定价摩擦点的深度研判",\n'
            f'    "economic_clusters": [\n'
            f'      {{"cluster_name": "涌现维度名称", "fields": ["字段名..."], "cluster_logic": "该簇字段的内在经济关联及去混杂噪音逻辑"}}\n'
            f"    ]\n"
            f"  }},\n"
            f'  "signals": [\n'
            f"    {{\n"
            f'      "id": "SEED_01",\n'
            f'      "cluster_ref": "所属涌现维度名称",\n'
            f'      "hypothesis_type": "LEVEL",  // 假说类型: LEVEL (慢变量水平值/截面分布，纯代数) 或 SHOCK (边际突变/状态冲击，举证需要 ts_delta/ts_zscore)\n'
            f'      "fields_used": ["本次选用的 2~4 个具体字段列表"],\n'
            f'      "field_semantics_mapping": "逐一剖析所选字段的商业实质、物理量纲及为何如此组合以剥离规模或基数噪音",\n'
            f'      "economic_mechanism": "完整因果传导链：底层异动 -> 市场参与者认知摩擦/交易约束 -> 价格修正方向與持续周期",\n'
            f'      "expected_polarity": 1,\n'
            f'      "expression": "<此处填入由上方语义映射与经济机制唯一推导出的 FastExpr 表达式>"\n'
            f"    }}\n"
            f"  ]\n"
            f"}}"
        )
        context = {
            "fields": sampled_names,
            "fields_meta": fields_meta_list,
            "count": count,
            "task_tag": f"stage0_{self.dataset_id}"
        }
        raw_res = session.send_message_sync(prompt, json_mode=True, context=context)
        raw_seeds = raw_res.get("signals", []) if isinstance(raw_res, dict) else (raw_res if isinstance(raw_res, list) else [])

        # 提取代数骨架函数：先剥离 vec_* 降维算子外壳，防止 Vector 简单比率绕过门禁，防止 Agent 交出满屏同质化模板
        def _get_algebraic_skeleton(expr_str: str, known_f: set) -> str:
            norm_expr = re.sub(r'vec_(?:avg|sum|max|min)\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)', r'\1', expr_str)
            tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|\d+(?:\.\d+)?|[(),]', norm_expr)
            out = ["F" if t in known_f else ("C" if re.match(r'^\d+(?:\.\d+)?$', t) else t) for t in tokens]
            return "".join(out)

        def _get_call_skeleton(call_node, known_f: set) -> str:
            func_name = call_node.func.id if isinstance(call_node.func, ast.Name) else "func"
            args_skels = []
            for a in call_node.args:
                if isinstance(a, ast.Call):
                    args_skels.append(_get_call_skeleton(a, known_f))
                elif isinstance(a, ast.Name):
                    args_skels.append("F" if a.id in known_f else a.id)
                elif isinstance(a, ast.Constant):
                    args_skels.append("C")
                elif isinstance(a, (ast.Num, ast.Str)):
                    args_skels.append("C")
                elif isinstance(a, ast.UnaryOp):
                    args_skels.append("U")
                elif isinstance(a, ast.BinOp):
                    args_skels.append("B")
                else:
                    args_skels.append("X")
            joined = ",".join(args_skels)
            return f"{func_name}({joined})"

        def _extract_subtree_skeletons(expr_str: str, known_f: set) -> list:
            norm_expr = re.sub(r'vec_(?:avg|sum|max|min)\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)', r'\1', expr_str)
            try:
                root = ast.parse(norm_expr, mode='eval').body
            except Exception:
                return []
            subtrees = []
            for node in ast.walk(root):
                if isinstance(node, ast.Call) and node is not root:
                    has_nested = any(isinstance(arg, ast.Call) for arg in node.args)
                    if has_nested or len(node.args) >= 2:
                        sk = _get_call_skeleton(node, known_f)
                        subtrees.append(sk)
            return subtrees

        candidate_signals = []
        skeleton_counts = {}
        subtree_counts = {}
        cluster_counts = {}
        simple_ratio_count = 0
        known_set = set(all_field_names)
        max_subtree_cap = max(2, int(count * 0.35))
        max_cluster_cap = max(2, int(count * 0.35))

        if isinstance(raw_seeds, list):
            for i, item in enumerate(raw_seeds):
                cleaned = self.corrector.correct_expression(item.get("expression", ""))
                skel = _get_algebraic_skeleton(cleaned, known_set)

                # 1. 限制最简两字段比率/差分 (如 divide(F,F), divide(F,add(F,C)), subtract(F,F) 等)
                is_simple_ratio = skel in ["divide(F,F)", "divide(F,add(F,C))", "divide(F,subtract(F,C))", "subtract(F,F)"]
                max_simple = max(1, int(count * 0.25))
                if is_simple_ratio and simple_ratio_count >= max_simple:
                    continue

                # 2. 限制同一经济簇 (cluster_ref) 扎堆过度 (单批不得超过 35%，逼出跨维度多元视角)
                c_ref = (item.get("cluster_ref") or "default_cluster").strip()
                if cluster_counts.get(c_ref, 0) >= max_cluster_cap:
                    continue

                # 3. 子树母题频次硬门禁 (对所有深度 >= 2 的复合结构算子子树实施 <= 35% 截断，杜绝局部惯用语收敛)
                sub_skels = _extract_subtree_skeletons(cleaned, known_set)
                subtree_blocked = False
                for s_sk in sub_skels:
                    if subtree_counts.get(s_sk, 0) >= max_subtree_cap:
                        subtree_blocked = True
                        break
                if subtree_blocked:
                    continue

                skeleton_counts[skel] = skeleton_counts.get(skel, 0) + 1
                # 硬门禁：同一种代数骨架在单批种子中最多允许出现 3 次，超出直接按同质化模板剔除！
                if skeleton_counts[skel] <= 3:
                    if is_simple_ratio:
                        simple_ratio_count += 1
                    cluster_counts[c_ref] = cluster_counts.get(c_ref, 0) + 1
                    for s_sk in set(sub_skels):
                        subtree_counts[s_sk] = subtree_counts.get(s_sk, 0) + 1
                    candidate_signals.append({
                        "id": item.get("id", f"SEED_{i+1:02d}"),
                        "cluster_ref": c_ref,
                        "hypothesis_type": item.get("hypothesis_type", "LEVEL"),
                        "field_semantics_mapping": item.get("field_semantics_mapping", ""),
                        "economic_mechanism": item.get("economic_mechanism", "基于字段研究提出的因果假说"),
                        "expected_polarity": int(item.get("expected_polarity", 1)),
                        "expression": cleaned,
                        "fields_used": item.get("fields_used", []),
                        "times": 0
                    })

        # 直接使用毫秒级纯 Python DimensionAuditor 替代冗余的 auditor_session LLM 调用
        signals = []
        for s in candidate_signals:
            expr = s["expression"]
            audit_res_ast = DimensionAuditor.audit_expression(
                expr,
                known_fields=fields_dict,
                category=self.category,
                allow_pv_cross=False
            )
            is_valid = audit_res_ast.get("is_valid", True)

            # Stage 0 复杂度预算与举证准入 (Complexity Budget <= 3 + Evidentiary Admission)
            # 1. 物理封杀所有跨截面算子与非线性装潢算子 (一律留待 Stage 1)
            # 必须使用 Python AST 解析出的真实调用算子集合 (杜绝因字段名包含 quantile/rank 等词根发生误杀)
            called_ops = set(audit_res_ast.get("called_operators", []))
            disallowed_ops = {"rank", "group_rank", "quantile", "group_quantile", "scale", "group_scale",
                              "group_neutralize", "group_zscore", "winsorize", "signed_power", "s_log_1p", "hump", "trade_when"}
            if called_ops.intersection(disallowed_ops):
                continue

            # 2. 算子预算限制 (Stage 0 严禁复杂堆砌，总算子数 <= 3)
            op_count = audit_res_ast.get("operator_count", expr.count("("))
            if op_count > 3:
                continue

            # 3. 假说类型举证准入 (按 AST 节点调用真实次数严格校验，彻底杜绝 set 去重漏洞与 Prompt/代码矛盾)
            h_type = str(s.get("hypothesis_type", "LEVEL")).upper()
            temporal_calls = self._get_ast_temporal_calls(expr)

            if h_type == "SHOCK":
                # SHOCK 假说允许且仅允许使用恰好 1 个时序算子，且算子必须在 ALLOWED_SHOCK_TEMPORAL 白名单内
                if len(temporal_calls) != 1 or temporal_calls[0] not in self.ALLOWED_SHOCK_TEMPORAL:
                    continue
            else:
                # LEVEL 假说保持严格纯代数，严禁任何时序算子调用
                if len(temporal_calls) > 0:
                    continue

            if is_valid:
                # 强制使用 Python AST 真实提取的数据集字段列表覆盖 LLM 自报字段，杜绝虚报冷门字段绕过铁律 A
                s["fields_used"] = audit_res_ast.get("used_fields") or s.get("fields_used", [])
                signals.append(s)

        # ---------------- 铁律 A 物理校验: 未构成冷热非对称配对的种子直接拒收 ----------------
        signals, pairing_rejected, pairing_report = enforce_stage0_pairing(
            signals, profiler, expected_count=count, min_survival_ratio=0.5, strict=True
        )
        if pairing_rejected:
            print(
                f"🧊 [铁律 A 拦截] {len(pairing_rejected)} 个种子字段组合全在拥挤赛道或缺少高覆盖归一锚，已拒收:"
            )
            for r in pairing_rejected[:5]:
                print(f"   - {r['id']}: {r['fields_used']} | {'; '.join(r['issues'])}")
        if pairing_report.get("skipped"):
            print(f"⚠️ [铁律 A 降级] {pairing_report.get('reason')}")
        elif signals:
            print(
                f"🧊 [铁律 A 通过] {len(signals)} 个种子全部满足「低拥挤主锚 x 高覆盖归一锚」非对称配对 "
                f"(存活率 {pairing_report['survival_ratio']:.0%})。"
            )

        tasks_dir = self.client.tasks_dir or os.path.join(self.base_dir, ".agent_tasks")
        stage0_resp = os.path.join(tasks_dir, f"resp_aegis-seed-synthesizer_stage0_{self.dataset_id}.json")

        if not signals:
            if os.path.exists(stage0_resp):
                try:
                    os.remove(stage0_resp)
                except Exception:
                    pass
            raise RuntimeError(
                f"❌ 【Stage 0 全员合规审查被拒】候选主信号原型全部未通过技术审查 / 铁律 A 冷热配对校验！\n"
                f"   已物理清理 Stage 0 响应缓存，系统拒绝违规死模板强行入池，请重新启动大模型推演合规种子！\n"
                f"   拒收详情: {json.dumps(pairing_report.get('rejected_detail', [])[:3], ensure_ascii=False)}"
            )

        # 若因同质化或语法违规导致存活种子不足 50%，打回重造，绝不接受缩水种子池
        min_required = max(1, int(count * 0.5))
        if len(signals) < min_required:
            if os.path.exists(stage0_resp):
                try:
                    os.remove(stage0_resp)
                except Exception:
                    pass
            raise RuntimeError(
                f"❌ 【Stage 0 存活种子不足】要求生成 {count} 个，经 AST 骨架多样性与量纲门禁审查后仅存活 {len(signals)} 个 (低于最低阈值 {min_required})！\n"
                f"   已物理清理 Stage 0 响应缓存，系统拒绝缩水种子池，请重新启动大模型推演高多样性合规种子！"
            )

        pool = self.load_signals_pool()
        if isinstance(raw_res, dict) and "dataset_field_study" in raw_res:
            pool["dataset_field_study"] = raw_res["dataset_field_study"]
        pool["signals"] = signals
        pool["crowding_profile"] = prof_stats
        pool["pairing_candidates"] = pairing_candidates
        try:
            with open(os.path.join(self.campaign_dir, "stage0_pairing_report.json"), "w", encoding="utf-8") as pf:
                json.dump({
                    "crowding_profile": prof_stats,
                    "pairing_candidates": pairing_candidates,
                    "report": {k: v for k, v in pairing_report.items() if k != "rejected_detail"},
                    "rejected": pairing_report.get("rejected_detail", []),
                }, pf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [铁律 A] 配对审计报告落盘失败: {e}")
        self.save_signals_pool(pool)

        # 种子池落盘成功后，清理 Stage 0 临时任务缓存，因为种子已永久沉淀在 total_signals.json 中
        if os.path.exists(stage0_resp):
            try:
                os.remove(stage0_resp)
            except Exception:
                pass

        print(f"✅ 阶段 0 生成并通过技术审查完毕，共 {len(signals)} 个纯四则运算双字段原型写入 {self.signals_pool_file}")
        return signals

    # -------------------------------------------------------------
    # 阶段 1 群体发散 (func1): 锁定双字段，50/50 变体装载
    # -------------------------------------------------------------
    def generate_swarm_variants(
        self,
        seed: dict,
        parent_alpha: dict = None,
        pyramid_kb: str = "",
        inspiration: str = "",
        step: int = 1,
        seed_good_alphas: Optional[List[dict]] = None,
        seed_qualified_alphas: Optional[List[dict]] = None,
        is_golden_shot: bool = False
    ) -> List[dict]:
        """
        阶段 1: 群体发散 (func1)
        基于 Plan 1 独立会话由 aegis-swarm-generator 生成
        在锁定主信号双字段前提下，发散生成单批变体 (50% 全新探索 + 50% 母本演化)
        严格注入核心字段画像、更新频率调优指南、区域动态高阶中性化、四级金字塔经验库与 Top-5 历史最优标杆
        """
        core_expr = seed["expression"]
        seed_mech = seed.get("economic_mechanism", "基于字段研究提出的因果假说")
        fields_dict = self.load_dataset_fields()
        neut_list = self.get_supported_neutralizations()
        parent_id = parent_alpha.get("alpha_id", seed["id"]) if parent_alpha else seed["id"]

        # 提取核心双字段画像与更新频率
        used_field_names = seed.get("fields_used", [])
        if not used_field_names:
            ast_res = DimensionAuditor.audit_expression(core_expr, known_fields=fields_dict, category=self.category)
            used_field_names = ast_res.get("used_fields", [])

        core_fields_meta = []
        is_quarterly = False
        for fn in used_field_names:
            meta = fields_dict.get(fn, {})
            freq = meta.get("update_frequency", "quarterly" if self.category == "fundamental" else "daily")
            if "quarter" in str(freq).lower():
                is_quarterly = True
            core_fields_meta.append({
                "name": fn,
                "type": meta.get("type", "MATRIX"),
                "description": meta.get("description", "无描述"),
                "coverage": round(meta.get("coverage", 1.0), 3),
                "update_frequency": freq,
                "semantic_role": meta.get("semantic_role", "Signal_Flow"),
                "prescriptions": meta.get("prescriptions", []),
                "skewness": meta.get("skewness", "medium")
            })
        if self.category == "fundamental":
            is_quarterly = True

        frequency_guidance = (
            "【更新频率调优指南】:\n"
            "- 本信号涉及低频/季度更新特征 (quarterly fundamental)：\n"
            "  * 严禁在未经处理的情况下直接套用超短周期差分 (如 ts_delta(x, 1))，否则在无财报更新的交易日会产生大量 0 导致信号失效！\n"
            "  * 推荐使用跨季度长窗口差分/平滑 (如 ts_delta(x, 60), ts_delta(x, 252))，或截面相对排序 group_rank(..., subindustry) 与规模中性化 scale(...)；\n"
            "  * 配合 winsorize(..., std=3) 与符号幂 signed_power(...) 保持单调性。\n"
            if is_quarterly else
            "【更新频率调优指南】:\n"
            "- 本信号为高频/日频更新特征 (daily flow/news/sentiment/analyst)：\n"
            "  * 优先采用时序衰减与动量捕捉算子：ts_decay_linear(..., 10), ts_rank(..., 20), ts_zscore(..., 60)；\n"
            "  * 结合 group_neutralize(..., subindustry) 消除行业暴露风险。\n"
        )

        # ---------------- 场景路由: 老兵精修 (手术刀) vs 战场 A (开拓) ----------------
        # 母本已在历史区间验证 (|Sharpe| >= 1.2) 时，铁律 B 的 rank 配额与 N/2N 双窗口拆解会直接斩断母本骨架，
        # 必须切换到精修模式: 骨架锁定 + 经济学通道变异 + 控制槽 + 相对改进验收。
        event_driven = self.category in EVENT_DRIVEN_CATEGORIES
        _parent_expr = parent_alpha.get("expression", "") if isinstance(parent_alpha, dict) else ""
        _parent_metrics = parent_alpha.get("metrics", {}) if isinstance(parent_alpha, dict) else {}
        if not isinstance(_parent_metrics, dict):
            _parent_metrics = {}
        _parent_sharpe = 0.0
        if isinstance(parent_alpha, dict):
            try:
                _parent_sharpe = abs(float(parent_alpha.get("sharpe") or _parent_metrics.get("sharpe") or 0.0))
            except (TypeError, ValueError):
                _parent_sharpe = 0.0
        surgery_mode = bool(_parent_expr) and _parent_sharpe >= 1.2
        protected_skeleton = SwarmAuditor.extract_skeleton_ops(_parent_expr) if surgery_mode else []
        route_mode = SwarmAuditor.MODE_REFINEMENT if surgery_mode else SwarmAuditor.MODE_EXPLORATION
        if surgery_mode:
            print(
                f"🔬 [场景路由] 母本 |Sharpe|={_parent_sharpe:.2f} >= 1.2 → 切换「老兵精修 (手术刀) 模式」；"
                f"骨架锁定 = {protected_skeleton}，铁律 B 的 rank 配额与 N/2N 拆解本批停用。"
            )

        # ---------------- 铁律 B 硬配额 + 双窗口成对探针指令 (仅战场 A) ----------------
        ironlaw_directive = SwarmAuditor.build_directive(
            self.parallelism,
            event_driven=event_driven,
            mode=route_mode,
            protected_ops=protected_skeleton,
            parent_expression=_parent_expr,
        )
        pairing = seed.get("pairing") or {}
        pairing_note = ""
        if pairing.get("is_asymmetric"):
            pairing_note = (
                f"【本种子主锚配对 (铁律 A 已通过校验)】: 低拥挤主锚 = {pairing.get('main_anchor')} "
                f"(alpha_pct={pairing.get('main_anchor_alpha_pct')}), 高覆盖归一锚 = {pairing.get('normalizer')} "
                f"(coverage={pairing.get('normalizer_coverage')})。\n"
                f"演进过程中严禁把主锚字段替换回 HOT 拥挤热点，否则 ProdCorr 会立刻反弹到 0.70 以上。\n"
            )

        session = self.client.create_session(role="aegis-swarm-generator", model=self.model)

        # 种子专属母本优先，严禁回退全局标杆 (彻底切断跨种子串味泄漏)
        if step == 1 and not parent_alpha:
            top5 = []
            random20 = []
            # Step 1 清理可能遗留的历史处方锁
            rx_path = os.path.join(self.campaign_dir, "authorized_mutations.json")
            if os.path.exists(rx_path):
                try:
                    os.remove(rx_path)
                except Exception:
                    pass
            stage_guidance = (
                "【阶段科研使命: Step #1 假说多维实证检验 (Clean Empirical Validation)】:\n"
                "- 当前假说尚未经过回测检验，不存在母本 (parent_alpha 为空)，因此本轮 100% 为假说实证探索 (type 统一填 'empirical_probe')！\n"
                "- 【严禁算子暴力堆砌】：在证实该假说具备基础预测力之前，严禁盲目套用 winsorize、s_log_1p、signed_power 等非线性装潢算子！\n"
                "- 【保持极简纯净】：每条变体外层包装算子严格控制在 1~3 个以内（仅使用匹配更新频率的时序差分/均值/Z-score 与截面 group_rank / group_neutralize），从不同时间跨度与截面基准干净地检验该经济学假说是否成立。\n"
                f"- 【中性化基准约束】：在 {self.parallelism} 条实证变体中，必须保证至少 30% (>= {max(int(self.parallelism * 0.3), 1)} 条) 变体使用基础截面中性化 ('SUBINDUSTRY' 或 'INDUSTRY')，以验证信号源是否自带真实 Alpha 潜力，严禁全量寄生在高阶风险中性化残差中！\n"
            )
            output_schema_instruction = (
                f"【输出格式契约】必须返回严格的 JSON 数组，共 {self.parallelism} 个纯净实证变体对象。\n"
                f"每个对象必须包含以下 6 个键：slot, optimize_reason, expression, neutralization, type, original_alpha（注意：先写 optimize_reason 阐述实证设计理由，再写 expression！）。\n"
            )
        else:
            # Step >= 2: 仅允许从当前种子的局部结果中提取标杆，严禁回退全局 self.good_alphas / self.history_save
            if seed_good_alphas:
                top5 = sorted(seed_good_alphas, key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)[:5]
            elif seed_qualified_alphas:
                top5 = sorted(seed_qualified_alphas, key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)[:5]
            else:
                top5 = []

            # 随机采样潜力候选（严格限制在当前种子局部候选池中）
            candidate_pool = seed_qualified_alphas if seed_qualified_alphas else []
            random20 = random.sample(candidate_pool, min(20, len(candidate_pool))) if candidate_pool else []

            # 提取母本的具体回测病灶指标供 Agent 靶向诊断
            p_metrics = parent_alpha.get("metrics", {}) if (parent_alpha and isinstance(parent_alpha.get("metrics"), dict)) else {}
            p_sharpe = float(parent_alpha.get("sharpe") or p_metrics.get("sharpe") or 0.0) if parent_alpha else 0.0
            p_fit = float(parent_alpha.get("fitness") or p_metrics.get("fitness") or 0.0) if parent_alpha else 0.0
            p_turn = float(parent_alpha.get("turnover") or p_metrics.get("turnover") or 0.0) if parent_alpha else 0.0
            if parent_alpha and "margin_bps" in parent_alpha:
                p_margin = float(parent_alpha.get("margin_bps") or 0.0)
            elif p_metrics.get("margin") is not None:
                p_margin = float(p_metrics.get("margin") or 0.0) * 10000.0
            else:
                p_margin = 0.0

            # 确定性法医确诊与处方路由锁 (Gate 4 闭环)
            parent_op_count = 0
            if parent_alpha and "expression" in parent_alpha:
                try:
                    tree = ast.parse(parent_alpha["expression"], mode='eval')
                    parent_op_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call))
                except Exception:
                    parent_op_count = 0

            verdict = Gatekeeper.diagnose_and_route_prescriptions(
                alpha_metrics=p_metrics,
                checks_parsed=parent_alpha or {},
                yearly_stats=p_metrics.get("yearly_stats", []),
                operator_count=parent_op_count,
                prod_corr=(Gatekeeper.extract_prod_corr(parent_alpha) if parent_alpha else None) or (parent_alpha.get("prod_corr") if parent_alpha else None),
                max_operator_limit=getattr(self, "max_ast_operators", 8)
            )
            # 处方凭据落盘，供 Gate 4 Pre-Flight 审计核验
            rx_path = os.path.join(self.campaign_dir, "authorized_mutations.json")
            try:
                with open(rx_path, 'w', encoding='utf-8') as rf:
                    json.dump({
                        "symptoms": verdict["symptoms"],
                        "allowed_mutations": verdict["allowed_mutations"]
                    }, rf, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"⚠️ [Gatekeeper] 处方锁凭据落盘异常: {e}")

            symptoms_str = ", ".join(verdict["symptoms"]) if verdict["symptoms"] else "无严重结构性病灶"
            allowed_mutations_str = ", ".join(verdict["allowed_mutations"])
            rag_prescriptions_str = json.dumps(verdict["rag_prescriptions"], ensure_ascii=False, indent=1) if verdict["rag_prescriptions"] else "暂无匹配处方卡"

            polarity_warning = ""
            if parent_alpha and (parent_alpha.get("is_polarity_inverted") or parent_alpha.get("status") == "POLARITY_INVERTED" or p_sharpe < 0):
                polarity_warning = (
                    "\n⚠️ 【因果极性反转警示 (Polarity Inversion)】: "
                    f"当前母本回测 Sharpe={p_sharpe:.2f} 为负值，与 Stage 0 初始假说极性相反！"
                    "进入本轮迭代，Agent 必须在 optimize_reason 中从微观结构深入论述为何市场呈现反转/反应过度机制，"
                    "严禁无脑套用 reverse() 蒙混过关！若微观逻辑不成立，必须终止该分支。\n"
                )

            p_fails = parent_alpha.get("fails", []) if parent_alpha else []
            p_warnings = parent_alpha.get("warnings", []) if parent_alpha else []

            # 提取母本黄金体检档案 (包含 10年年度夏普、最近24个月月度夏普、告警项与失败项)
            from core.sim_runner import SimBatchRunner
            golden_result = SimBatchRunner.extract_golden_alpha_result(parent_alpha) if parent_alpha else {}
            yearly_sharpe_list = golden_result.get("yearly_sharpe", [])
            monthly_sharpe_list = golden_result.get("last_24_monthly_sharpe", [])
            p_warn = golden_result.get("warn", p_warnings)
            p_fail = golden_result.get("fail", p_fails)
            pc_val = golden_result.get("pc")
            sc_val = golden_result.get("sc")

            yearly_sharpe_str = " | ".join(f"{yr}: {sh}" for yr, sh in yearly_sharpe_list) if yearly_sharpe_list else "无"
            monthly_sharpe_str = " | ".join(f"{m}: {sh}" for m, sh in monthly_sharpe_list[-12:]) if monthly_sharpe_list else "无"
            
            golden_profile_str = (
                f"\n📊 【母本回测黄金体检档案 (Golden Result)】:\n"
                f"- 10年年度夏普分布 (Yearly Sharpe): {yearly_sharpe_str}\n"
                f"- 最近12个月月度夏普 (Monthly Sharpe): {monthly_sharpe_str}\n"
                f"- 平台审查告警 (Warnings): {p_warn}\n"
                f"- 平台审查失败 (Fails): {p_fail}\n"
                f"- 生产库相关性 (ProdCorr): {pc_val if pc_val is not None else '未测'} | 自相关性 (SelfCorr): {sc_val if sc_val is not None else '未测'}\n"
            )

            # 动态格式化 LanceDB 原子化 QA 知识
            qa_insights_str = ""
            try:
                from core.qa_rag_tool import format_qa_for_prompt
                qa_insights_str = format_qa_for_prompt(verdict.get("qa_prescriptions", []))
            except Exception:
                pass

            if surgery_mode:
                mission_line = (
                    f"- 🩺 【场景路由 = 老兵精修】母本 |Sharpe|={_parent_sharpe:.2f} 已是局部极值，本轮目标不是全绿，"
                    f"而是按母本病灶选一条轴做单点相对改进 (Margin 升 >= 20% / Turnover 降 >= 20%『仅当母本换手 > 30%』/ ProdCorr 降 >= 0.05)，"
                    f"且 |Sharpe| 不得低于母本。\n"
                    f"- 🚫 严禁拆解骨架 {protected_skeleton}；LOW_SHARPE / CLUSTER_TEST 等由骨架本身决定的平台告警，本轮不必强制清零。\n"
                )
            else:
                mission_line = (
                    "- 🎯 【全绿冲刺使命】: 必须对症下药将 Fails 与 Warnings 一并彻底清零（实现 0 FAIL + 0 WARNING 的 ALL PASS 状态）！\n"
                )

            stage_guidance = (
                f"【阶段科研使命: Step #{step} 基于回测病灶的靶向因子工程 (Diagnostic-Driven Engineering)】:\n"
                f"- 核心母本已证实存在显著信号！母本实测体检指标：Sharpe={p_sharpe:.2f}, Fitness={p_fit:.2f}, Turnover={p_turn:.2%}, Margin={p_margin:.2f}bps | Fails={p_fails} | Warnings={p_warnings}。\n"
                f"{golden_profile_str}\n"
                f"{mission_line}"
                f"- 🩺 【法医确诊病灶】: {symptoms_str}\n"
                f"- 💡 【专家推荐算子工具箱 (供参考，Agent 可基于因果逻辑自主选用平台合法算子)】: {allowed_mutations_str}\n"
                f"- 📋 【靶向 Tier-2 处方指引】:\n{rag_prescriptions_str}\n"
                + (f"\n{qa_insights_str}\n" if qa_insights_str else "")
                + f"{polarity_warning}"
                f"- 请严格根据确诊病灶对症下药（50% 探索新拓扑 + 50% 针对母本病灶精修），绝不盲目堆叠非线性算子！\n"
            )
            output_schema_instruction = (
                f"【输出格式契约】必须返回严格的 JSON 数组，共 {self.parallelism} 个变体对象（50% explore + 50% exploit）。\n"
                f"每个对象必须包含以下 6 个键：slot, optimize_reason, expression, neutralization, type, original_alpha（先写 optimize_reason 诊断依据，再写 expression！）。\n"
            )

        max_champ_ops = getattr(self, "max_champion_operators", 6)
        max_ast_ops = getattr(self, "max_ast_operators", 8)
        phase_name = "准冠军定向优化阶段" if getattr(self, "is_quasi_champion_optimization", False) else "常规研究挖掘阶段"
        op_constraint_directive = (
            f"【⚙️ 算子数硬约束 ({phase_name})】:\n"
            f"- 当前阶段冠军算子数硬上限 <= {max_champ_ops}，AST 语法树调用总数必须 <= {max_ast_ops}！\n"
            f"- 严禁过度嵌套复杂算子，保持因果逻辑纯净。回测前 Gate 2 将执行静态 AST 断言，超限 (>{max_ast_ops}) 物理拒收！\n"
        )

        golden_shot_directive = ""
        if is_golden_shot:
            ironlaw_directive = ""  # 解除 Golden Shot 加时赛双指令冲突: 锁定母本微调，不套用正交骨架探索
            golden_shot_directive = (
                "\n" + "🔥" * 35 + "\n"
                "🎯 【准冠军加时冲刺微调锁定 (Golden Shot Overtime Lock)】:\n"
                "- 当前进入准冠军加时冲刺！核心母本已经通过 ProdCorr (< 0.70) 与高 Margin 溢价门槛，夏普 1.45+，离生产线 1.58 仅差 0.04~0.10！\n"
                "- 🔒 【骨架拓扑硬锁定】: 严禁大幅修改公式拓扑！严禁引入任何复杂新算子！必须 100% 锁定母本的极简算子结构！\n"
                "- 🎛️ 【高精度网格微调】: 唯一允许的优化方向为精细调参：\n"
                "  1. 窗口参数平滑微调 (例如 240d -> 200d / 220d / 260d，或 20d -> 15d / 25d)；\n"
                "  2. 截面分组层级微调 (例如 industry <-> subindustry / sector)；\n"
                "  3. 极差微调 (例如 winsorize std 从 3 调为 2.5 或 3.5)。\n"
                f"- 变体的 {self.parallelism} 个槽位全部针对母本做高精度网格微调，冲刺最后 0.05 夏普实现 1.58+ 完美登顶！\n"
                + "🔥" * 35 + "\n"
            )

        # Step >= 2 或存在达标母本时: 下放同源冷门字段备选池 (Top-10 Low-Crowding Alternatives)
        alt_candidates_str = ""
        alt_candidates_list = []
        if step >= 2 or parent_alpha is not None:
            all_fields = list(fields_dict.keys())
            core_used = set(used_field_names)
            valid_candidates = [
                fn for fn in all_fields
                if fn not in core_used and fields_dict.get(fn, {}).get("coverage", 1.0) >= 0.20
            ]
            valid_candidates.sort(
                key=lambda fn: fields_dict.get(fn, {}).get("coverage", 0) / (1 + math.log1p(fields_dict.get(fn, {}).get("alpha_count", 0))),
                reverse=True
            )
            top10_alts = valid_candidates[:10]
            for fn in top10_alts:
                f_meta = fields_dict.get(fn, {})
                alt_candidates_list.append({
                    "name": fn,
                    "type": f_meta.get("type", "MATRIX"),
                    "description": f_meta.get("description", "无描述"),
                    "coverage": round(f_meta.get("coverage", 1.0), 3),
                    "alpha_count": int(f_meta.get("alpha_count", 0)),
                    "semantic_role": f_meta.get("semantic_role", "Signal_Flow")
                })
            if alt_candidates_list:
                alt_candidates_str = (
                    f"【同源冷门字段备选池 (Top-10 Low-Crowding Alternatives)】:\n"
                    f"若母本存在 ProdCorr >= 0.65、CLUSTER 告警或拥挤瓶颈，在 Step >= 2 允许直接将原主锚平替为以下同源冷门字段:\n"
                    f"{json.dumps(alt_candidates_list, ensure_ascii=False, indent=1)}\n\n"
                )

        prompt_parts = [
            f"基于主信号核心 '{core_expr}' 生成 {self.parallelism} 条群体变体。\n",
            f"当前演化轮次: Step #{step}\n",
            f"主信号假说内涵: {seed_mech}\n",
            f"目标区域: {self.region} | 股票池: {self.universe} | 预测延迟: Delay {self.delay} | 类别: {self.category}\n\n",
            f"{op_constraint_directive}\n"
        ]
        if golden_shot_directive:
            prompt_parts.append(f"{golden_shot_directive}\n")
        prompt_parts.append(f"{stage_guidance}\n")
        prompt_parts.append(f"【核心字段物理画像】:\n{json.dumps(core_fields_meta, ensure_ascii=False, indent=1)}\n\n")
        prompt_parts.append(f"{frequency_guidance}\n")
        prompt_parts.append(f"{ironlaw_directive}\n")
        if pairing_note:
            prompt_parts.append(f"{pairing_note}")
        if alt_candidates_str:
            prompt_parts.append(f"{alt_candidates_str}")
        prompt_parts.append(f"【区域动态高阶中性化白名单】:\n{neut_list}\n\n")
        if pyramid_kb:
            prompt_parts.append(f"【四级金字塔经验手册 (纯算子规则)】:\n{pyramid_kb}\n\n")
        if inspiration:
            prompt_parts.append(f"【当前探索灵感启发】:\n{inspiration}\n\n")
        if top5:
            prompt_parts.append(f"【Top-5 历史最优标杆】:\n{json.dumps(top5, ensure_ascii=False, indent=1)}\n\n")
        if parent_alpha:
            prompt_parts.append(f"【母本最优参考】: {json.dumps(parent_alpha, ensure_ascii=False)}\n\n")
        if random20:
            prompt_parts.append(f"【采样历史候选】:\n{json.dumps(random20, ensure_ascii=False, indent=1)}\n\n")
        prompt_parts.append(f"{output_schema_instruction}")
        prompt = "".join(prompt_parts)
        context = {
            "core_expr": core_expr,
            "core_fields": core_fields_meta,
            "alt_candidates": alt_candidates_list,
            "neutralizations": neut_list,
            "parallelism": self.parallelism,
            "parent_id": parent_id,
            "category": self.category,
            "region": self.region,
            "step": step,
            "pyramid_kb": pyramid_kb,
            "inspiration": inspiration,
            "top5": top5,
            "random20": random20,
            "task_tag": f"{seed['id']}_s{step}"
        }

        variants = session.send_message_sync(prompt, json_mode=True, context=context)
        if not (isinstance(variants, list) and len(variants) > 0):
            if self.client.mock_fallback or os.environ.get("AEGIS_MOCK_MODE") == "1" or self.mock_only:
                variants = session._rule_fallback(prompt, json_mode=True, context=context)
            else:
                raise RuntimeError(
                    "❌ 【严禁死模板】大模型未返回有效变体，系统已严禁回退至死模板！"
                    "请检查智能体连接或切换为有效后端 (内置 SubAgent / LLM API)！"
                )

        # ---------------- 铁律 B 物理核验: 非 rank 外壳占比 + 成对双窗口矩阵 ----------------
        mock_env = (self.client.mock_only or self.mock_only or os.environ.get("AEGIS_MOCK_MODE") == "1")
        tasks_dir = self.client.tasks_dir or os.path.join(self.base_dir, ".agent_tasks")
        swarm_resp = os.path.join(tasks_dir, f"resp_aegis-swarm-generator_{seed['id']}_s{step}.json")
        try:
            audit_report = SwarmAuditor.enforce(
                variants,
                step=step,
                parallelism=self.parallelism,
                event_driven=event_driven,
                mode=route_mode,
                parent_expression=_parent_expr,
                protected_ops=protected_skeleton,
                strict=(step <= 1 and not mock_env)
            )
        except (ValueError, PermissionError, RuntimeError) as e:
            # 物理清理违规响应缓存，彻底打破 BuiltinAgent 重试时的死锁循环
            if os.path.exists(swarm_resp):
                try:
                    os.remove(swarm_resp)
                except Exception:
                    pass
            raise e

        try:
            with open(os.path.join(self.campaign_dir, f"swarm_audit_{seed['id']}_s{step}.json"), "w", encoding="utf-8") as af:
                json.dump(audit_report, af, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return variants

    async def load_or_fetch_targeted_seed(self, alpha_id: str) -> Optional[dict]:
        """为情况二 (已有种子 Alpha) 载入母本全景画像与体检病灶"""
        # 1. 尝试从本地指定路径或缓存载入
        possible_paths = [
            os.path.join(self.campaign_dir, f"seed_{alpha_id}.json"),
            os.path.join(self.campaign_dir, f"{alpha_id}.json"),
            os.path.join(self.base_dir, "campaigns", f"seed_{alpha_id}.json"),
            os.path.join(self.base_dir, "knowledge_base", "seeds", f"{alpha_id}.json")
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        expr = data.get("code") or data.get("expression")
                        if expr:
                            print(f"📁 [SeedResolver] 从本地画像载入种子 Alpha {alpha_id}: {p}")
                            return {
                                "id": alpha_id,
                                "expression": expr,
                                "economic_mechanism": data.get("economic_mechanism", f"针对已有母本 {alpha_id} 的靶向攻坚"),
                                "metrics": data.get("metrics", {}),
                                "ra": data.get("ra", {}),
                                "checks": data.get("checks", {}),
                                "yearly_stats": data.get("yearly_stats", []),
                                "times": 0
                            }
                except Exception:
                    pass

        # 2. 尝试从 Brain 模块或 API 拉取
        bm = get_brain_module()
        if bm and hasattr(bm, "get_alpha_details"):
            try:
                import inspect
                async def _call_api(fn, *args, **kwargs):
                    if inspect.iscoroutinefunction(fn):
                        return await fn(*args, **kwargs)
                    val = fn(*args, **kwargs)
                    if inspect.iscoroutine(val):
                        return await val
                    return val

                details = await _call_api(bm.get_alpha_details, alpha_id)
                if details and isinstance(details, dict) and (details.get("code") or details.get("expression")):
                    print(f"🌐 [SeedResolver] 从 WorldQuant Brain 成功同步 Alpha {alpha_id} 详情！")
                    y_records = []
                    if hasattr(bm, "get_alpha_yearly_stats"):
                        try:
                            y_records = await _call_api(bm.get_alpha_yearly_stats, alpha_id) or []
                        except Exception:
                            pass
                    return {
                        "id": alpha_id,
                        "expression": details.get("code") or details.get("expression"),
                        "economic_mechanism": f"针对已有母本 {alpha_id} 的靶向攻坚",
                        "metrics": details.get("metrics") or details.get("is") or {},
                        "ra": details.get("ra", {}),
                        "checks": details.get("checks") or (details.get("is", {}).get("checks")) or {},
                        "yearly_stats": y_records or details.get("yearly_stats", []),
                        "times": 0
                    }
            except Exception as e:
                print(f"⚠️ 从 Brain API 拉取 Alpha {alpha_id} 详情失败: {e}")

        return None

    @classmethod
    def _prod_corr_of(cls, alpha: dict):
        """
        提取候选的 ProdCorr，返回 (value, verified)。
        2026-10-31 修复:
        1. 必须读取 pcorr / prodCorrelation 多别名；
        2. 若显式标注 prod_corr_verified=False，或值为 None，返回 (None, False)；
        3. 浮点数 0.0 若未核实 (未附带 prod_corr_verified=True)，一律视为未测量占位符，严禁当成完美正交放行。
        """
        if not isinstance(alpha, dict):
            return None, False
        metrics = alpha.get("metrics", {}) if isinstance(alpha.get("metrics"), dict) else {}

        if alpha.get("prod_corr_verified") is False or metrics.get("prod_corr_verified") is False:
            return None, False

        for box in (alpha, metrics):
            for k in ("prod_corr", "pcorr", "prodCorr", "prodCorrelation", "correlation"):
                v = box.get(k)
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv != fv:
                    continue
                # 0.0 特殊防伪: 只有显式标注了 verified 为 True 时，0.0 才算真值
                if fv == 0.0 and not (alpha.get("prod_corr_verified") or metrics.get("prod_corr_verified")):
                    continue
                if 0.0 <= fv <= 1.0:
                    return fv, True
                if 1.0 < fv <= 100.0:
                    return fv / 100.0, True
        return None, False

    @classmethod
    def _operator_count_of(cls, alpha: dict) -> int:
        op_count = int(alpha.get("operator_count", 0) or 0)
        if op_count <= 0 and alpha.get("expression"):
            try:
                tree = ast.parse(alpha["expression"], mode='eval')
                op_count = sum(
                    1 for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and not getattr(node.func, "id", "").startswith("vec_")
                )
            except Exception:
                op_count = 6
        return op_count

    @classmethod
    def compute_champion_score(cls, alpha: dict) -> float:
        """
        WorldQuant 顶级生产级高 VF 综合效用评估公式:
        Champion_Score = Fitness * ln(Margin_bps) * (1 - ProdCorr^2) * (1 - 0.04 * Operator_Count)
        优先筛选算子数 <= 6、Margin 远超区域底线（如美股 > 18 bps）、且在截面残差下稳健的高价值冠军因子。
        ProdCorr 未核实时按保守默认 0.70 计入 (杜绝未核实因子凭空获得高分反超已核实准冠军)。
        """
        metrics = alpha.get("metrics", {}) if isinstance(alpha.get("metrics"), dict) else {}
        fitness = float(alpha.get("fitness") or metrics.get("fitness") or 0.0)

        if "margin_bps" in alpha:
            margin_bps = float(alpha.get("margin_bps") or 0.0)
        elif "margin_bps" in metrics:
            margin_bps = float(metrics.get("margin_bps") or 0.0)
        elif metrics.get("margin") is not None:
            margin_bps = float(metrics.get("margin") or 0.0) * 10000.0
        else:
            raw_m = float(alpha.get("margin", 0.0))
            margin_bps = raw_m * 10000.0 if (0.0 < raw_m < 1.0) else raw_m

        # ln(Margin_bps) 保护: 当 margin_bps <= 1.0 时保护避免负数或 log 异常
        ln_margin = math.log(max(margin_bps, 1.01))

        # 核心修复 (漏洞 3): 平台相关性惩罚 (1 - ProdCorr^2): 未核实按 0.70 保守计入 (杜绝未核实因子反超已核实准冠军)
        prod_corr, verified = cls._prod_corr_of(alpha)
        if not verified or prod_corr is None:
            prod_corr = 0.70
        corr_penalty = max(0.0, 1.0 - (prod_corr ** 2))

        # 算子复杂度惩罚 (1 - 0.04 * Operator_Count)
        op_count = cls._operator_count_of(alpha)
        op_penalty = max(0.1, 1.0 - 0.04 * op_count)

        return float(fitness * ln_margin * corr_penalty * op_penalty)

    def champion_eligibility(self, alpha: dict) -> dict:
        """
        冠军资格硬过滤 (One-Champion-Per-Anchor 的最后一道防线):
        1. ProdCorr 必须 < 0.70 (若已核实且 >= 0.70，硬性否决);
        2. 若 ProdCorr 未核实 (None)，标记为 PENDING_PROD_CORR_CHECK (待核验准冠军)，
           允许登台展示作为待验代表，绝不粗暴全员抹杀；
        3. 算子数: 研究挖掘阶段必须 <= 6 (极简因子样本外泛化更强，> 6 硬性否决);
           仅在研究员明确说明在准冠军 alpha 基础上进入优化阶段时才放宽到 <= 10;
        4. Margin 达到区域溢价门槛 (如 GLB > 18 bps) 优先胜出。
        """
        reasons = []
        prod_corr, verified = self._prod_corr_of(alpha)
        pending_check = False

        if not verified or prod_corr is None:
            pending_check = True
            reasons.append("ProdCorr 待离线/实盘接口核验 (PENDING_PROD_CORR_CHECK)")
        elif prod_corr >= 0.70:
            reasons.append(f"ProdCorr {prod_corr:.4f} >= 0.70 (与生产库严重共线)")

        op_count = self._operator_count_of(alpha)
        max_ops = getattr(self, "max_champion_operators", 10 if bool(getattr(self, "targeted_alpha_id", None)) else 6)
        if op_count > max_ops:
            phase_desc = "准冠军优化阶段" if max_ops >= 10 else "研究挖掘阶段"
            reasons.append(f"算子数 {op_count} > {max_ops} ({phase_desc}非极简结构)")

        try:
            margin_bps = float(alpha.get("margin_bps") or (alpha.get("metrics") or {}).get("margin_bps") or 0.0)
        except (TypeError, ValueError):
            margin_bps = 0.0
        premium = REGION_CHAMPION_MARGIN_BPS.get(self.region, 15.0)
        if margin_bps < premium:
            reasons.append(f"Margin {margin_bps:.1f} bps 未达区域溢价门槛 {premium:.1f} bps")

        # 仅当命中严重共线 (>= 0.70) 或算子复杂度超标 (> 6) 时硬性否决
        hard_rejected = any(">= 0.70" in r or "算子数" in r for r in reasons)
        is_near = Gatekeeper.is_near_miss_champion(alpha, self.region)
        if not hard_rejected:
            if verified and prod_corr < 0.70:
                s_val = float(alpha.get("sharpe") or (alpha.get("metrics") or {}).get("sharpe") or 0.0)
                if is_near and s_val < 1.58:
                    status = "NEAR_CHAMPION"
                else:
                    status = "VERIFIED_CHAMPION"
            elif pending_check:
                status = "PENDING_PROD_CORR_CHECK"
            else:
                status = "DISQUALIFIED"
        else:
            status = "DISQUALIFIED"

        # 0 WARNING 完美全绿判定 (0 FAIL + 0 WARNING)
        warning_cnt = alpha.get("warning_count")
        fail_cnt = alpha.get("fail_count")
        if warning_cnt is None or fail_cnt is None:
            chk_parsed = Gatekeeper.parse_brain_checks(alpha)
            if warning_cnt is None:
                warning_cnt = len(chk_parsed.get("warnings", []))
            if fail_cnt is None:
                fail_cnt = chk_parsed.get("fail_count", 0)
        zero_warnings = (int(warning_cnt or 0) == 0 and int(fail_cnt or 0) == 0)

        return {
            "eligible": not hard_rejected,
            "status": status,
            "pending_prod_corr": pending_check,
            "prod_corr": prod_corr,
            "prod_corr_verified": verified,
            "operator_count": op_count,
            "margin_bps": margin_bps,
            "margin_premium_ok": margin_bps >= premium,
            "zero_warnings": zero_warnings,
            "warning_count": int(warning_cnt or 0),
            "fail_count": int(fail_cnt or 0),
            "reasons": reasons,
        }


    # -------------------------------------------------------------
    # 主状态机循环 (Pure Python State Machine Loop)
    # -------------------------------------------------------------
    async def run_pipeline_loop(self, max_seeds_to_explore: int = 50, max_steps_per_seed: int = 3):
        print("\n" + "=" * 65)
        print("🚀 【AEGIS GrandMaster 纯 Python 状态机总控启动】")
        print(f"📍 目标: {self.region} / {self.universe} / Delay {self.delay} / {self.category} / {self.dataset_id}")
        print(f"⚙️ 并发容量: {self.parallelism} 条 | 模型: {self.model}")
        print("=" * 65)

        # 1. 检查或生成主信号种子池
        pool = self.load_signals_pool()
        if self.targeted_alpha_id:
            # 模式二：靶向母本优化 (Targeted Warm-Start Mode)
            targeted_seed = next((s for s in pool.get("signals", []) if s.get("id") == self.targeted_alpha_id), None)
            if not targeted_seed:
                targeted_seed = await self.load_or_fetch_targeted_seed(self.targeted_alpha_id)
                if targeted_seed:
                    pool.setdefault("signals", []).insert(0, targeted_seed)
                    self.save_signals_pool(pool)
            if targeted_seed:
                unexplored = [targeted_seed]
                print(f"🎯 [模式二: 靶向母本激活] 锁定指定 Alpha ID: {self.targeted_alpha_id}")
            else:
                print(f"❌ 未能找到或同步 Alpha ID: {self.targeted_alpha_id}，回退至普通储备池检查。")
                unexplored = [s for s in pool.get("signals", []) if s.get("times", 0) == 0]
        else:
            if not pool.get("signals"):
                print("⚠️ 信号储备池为空，自动触发阶段 0 纯四则运算原型生成...")
                self.synthesize_stage0_seeds(count=20)
                pool = self.load_signals_pool()
            unexplored = [s for s in pool.get("signals", []) if s.get("times", 0) == 0]

        print(f"📊 当前储备池共有 {len(pool.get('signals', []))} 个主信号，待探索数量: {len(unexplored)}")

        if not unexplored:
            print("🏁 所有主信号均已探索完毕 (times > 0)！如需继续挖掘，请生成新种子或指定 ALPHA_ID。")
            return

        explored_count = 0
        known_fields = self.load_dataset_fields()
        campaign_ledger = os.path.join(self.campaign_dir, "exploration_ledger.json")

        for seed in unexplored:
            if explored_count >= max_seeds_to_explore:
                print(f"⏹️ 已达到本次运行探索上限 ({max_seeds_to_explore} 个主信号)，平稳停机。")
                break

            seed_id = seed["id"]
            core_expr = seed["expression"]
            explored_count += 1

            print("\n" + "-" * 65)
            print(f"🎯 [Cycle #{explored_count}] 激活主信号: {seed_id} (times={seed.get('times', 0)})")
            print(f"🌱 原型表达式: {core_expr}")
            print(f"💡 经济学假说: {seed.get('economic_mechanism')}")
            print("-" * 65)

            # 种子专属局部候选池，彻底杜绝跨种子母本串味污染！
            seed_good_alphas: List[dict] = []
            seed_qualified_alphas: List[dict] = []
            func2_triggered = False

            # 若为情况二靶向母本，且母本已具备达标回测体检数据，自动注入初始局部母本池
            if seed.get("metrics") and abs(float(seed.get("metrics", {}).get("sharpe") or seed.get("sharpe", 0.0))) >= 1.0:
                p_sh = float(seed.get("metrics", {}).get("sharpe") or seed.get("sharpe", 0.0))
                p_fit = float(seed.get("metrics", {}).get("fitness") or seed.get("fitness", 0.0))
                p_turn = float(seed.get("metrics", {}).get("turnover") or seed.get("turnover", 0.0))
                p_margin_bps = float(seed.get("metrics", {}).get("margin_bps", 0.0)) if "margin_bps" in seed.get("metrics", {}) else float(seed.get("metrics", {}).get("margin", 0.0)) * 10000.0
                parsed_init_chk = Gatekeeper.parse_brain_checks(seed)
                init_parent = {
                    "id": seed.get("id"),
                    "alpha_id": seed.get("id"),
                    "expression": seed["expression"],
                    "sharpe": p_sh,
                    "fitness": p_fit,
                    "turnover": p_turn,
                    "margin_bps": p_margin_bps,
                    "metrics": seed.get("metrics", {}),
                    "ra": seed.get("ra", {}),
                    "checks": seed.get("checks", {}),
                    "yearly_stats": seed.get("yearly_stats", []),
                    "fail_count": parsed_init_chk["fail_count"],
                    "fails": parsed_init_chk["fails"],
                    "warning_count": len(parsed_init_chk["warnings"]),
                    "warnings": parsed_init_chk["warnings"],
                    "cluster_sharpe": parsed_init_chk["cluster_sharpe"],
                    "ladder_2y_sharpe": parsed_init_chk["ladder_2y_sharpe"],
                    "sub_universe_sharpe": parsed_init_chk["sub_universe_sharpe"],
                    "status": "STEP1_PASSED"
                }
                seed_qualified_alphas.append(init_parent)
                if abs(p_sh) >= 1.2:
                    seed_good_alphas.append(init_parent)
                print(f"🧬 [靶向母本注入] 已载入已有回测指标: Sharpe={p_sh:.2f}, Fitness={p_fit:.2f}, Margin={p_margin_bps:.1f}bps, Turnover={p_turn:.2%}")

            step = 1
            step_limit = max_steps_per_seed
            overtime_granted = False
            while step <= step_limit:
                print(f"\n🔄 [主信号 {seed_id}] 执行 Step #{step} 演化迭代...")

                # Plan 1 会话隔离: 动态构建极简上下文
                pyramid_kb = RAGMemoryEngine.load_pyramid_context(self.region, self.delay, self.category)
                inspiration = RAGMemoryEngine.get_exploration_inspiration(0.25)
                if inspiration:
                    print(f"💡 [灵感检索] {inspiration}")

                # 母本严格来自当前种子的最优候选，绝不借用其他不相干种子的母本！
                # 若无 >= 1.2 的优秀母本，则向下兼容回退至 >= 1.0 的达标候选，桥接 1.0~1.2 缺口
                seed_best_parent = (
                    sorted(seed_good_alphas, key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)[0]
                    if seed_good_alphas else (
                        sorted(seed_qualified_alphas, key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)[0]
                        if seed_qualified_alphas else None
                    )
                )

                # 组装批次报文并管理回测检查点 (Step Checkpointing 幂等断点恢复)
                batch_filename = f"batch_{seed_id}_s{step}.json"
                batch_path = os.path.join(self.campaign_dir, batch_filename)
                sim_cache_path = os.path.join(self.campaign_dir, f"sim_res_{seed_id}_s{step}.json")

                if os.path.exists(sim_cache_path):
                    with open(sim_cache_path, 'r', encoding='utf-8') as sf:
                        sim_res = json.load(sf)
                    print(f"⏩ [断点恢复] 已加载 {seed_id} Step #{step} 历史回测结果，跳过重复回测！")
                    variants = []
                    if os.path.exists(batch_path):
                        try:
                            with open(batch_path, 'r', encoding='utf-8') as bf:
                                b_data = json.load(bf)
                                variants = b_data.get("items", [])
                        except Exception:
                            pass
                else:
                    # 阶段 1 群体变体生成 (锁定双字段，注入金字塔与灵感)
                    variants = self.generate_swarm_variants(
                        seed,
                        parent_alpha=seed_best_parent,
                        pyramid_kb=pyramid_kb,
                        inspiration=inspiration,
                        step=step,
                        seed_good_alphas=seed_good_alphas,
                        seed_qualified_alphas=seed_qualified_alphas,
                        is_golden_shot=bool(overtime_granted and step == step_limit)
                    )
                    try:
                        import ast
                        tree = ast.parse(seed.get("expression", ""), mode='eval')
                        stage0_op_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call))
                    except Exception:
                        stage0_op_count = 1

                    has_parent_flag = bool(seed_best_parent is not None)
                    effective_step = max(step, 2) if has_parent_flag else step

                    with open(batch_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "seed_id": seed_id,
                            "step": effective_step,
                            "has_parent": has_parent_flag,
                            "region": self.region,
                            "universe": self.universe,
                            "delay": self.delay,
                            "category": self.category,
                            "known_fields": known_fields,
                            "expected_polarity": seed.get("expected_polarity", 1),
                            "stage0_op_count": stage0_op_count,
                            "core_fields": seed.get("fields_used", []),
                            "max_ast_operators": getattr(self, "max_ast_operators", 8),
                            "max_champion_operators": getattr(self, "max_champion_operators", 6),
                            "is_golden_shot": bool(overtime_granted and step == step_limit),
                            "items": variants
                        }, f, ensure_ascii=False, indent=2)

                    # 执行静默并发回测
                    campaign_ledger = os.path.join(self.campaign_dir, "exploration_ledger.json")
                    try:
                        sim_res = await SimBatchRunner.run_batch_silently(
                            batch_file_path=batch_path,
                            region=self.region,
                            universe=self.universe,
                            delay=self.delay,
                            category=self.category,
                            neutralization=None,
                            ledger_path=campaign_ledger
                        )
                    except (ValueError, PermissionError, RuntimeError) as e:
                        # 物理清理违规响应缓存与批次文件，打破重试死循环
                        tasks_dir = self.client.tasks_dir or os.path.join(self.base_dir, ".agent_tasks")
                        swarm_resp = os.path.join(tasks_dir, f"resp_aegis-swarm-generator_{seed_id}_s{step}.json")
                        if os.path.exists(swarm_resp):
                            try:
                                os.remove(swarm_resp)
                            except Exception:
                                pass
                        if os.path.exists(batch_path):
                            try:
                                os.remove(batch_path)
                            except Exception:
                                pass
                        raise e

                    with open(sim_cache_path, 'w', encoding='utf-8') as sf:
                        json.dump(sim_res, sf, ensure_ascii=False, indent=2)

                # ---------------------------------------------------------
                # 阶梯漏斗早停核心 (Funnel Pruning - 0 Token 纠缠)
                # ---------------------------------------------------------
                step1_status = sim_res.get("step1", {})
                if step1_status.get("platform_failure", False):
                    print(f"⚠️ [仿真平台异常保护] {seed_id} Step #{step} 回测全部被平台取消或报错 (CANCELLED/ERROR)。")
                    print(f"   保留当前种子待平台恢复后继续重跑，严禁误判为信号失效剪枝！")
                    if os.path.exists(sim_cache_path):
                        try:
                            os.remove(sim_cache_path)
                        except Exception:
                            pass
                    break

                if step == 1 and step1_status.get("should_prune", False):
                    # Step 1 冷酷熔断：Python 直接置 times = 1，秒级切换下一个主信号，严禁调用 LLM 写总结！
                    seed["times"] = seed.get("times", 0) + 1
                    self.save_signals_pool(pool)
                    print(f"⚡ [0 Token 极速早停] {seed_id} Step 1 最高 |Sharpe| 仅为 {step1_status.get('max_abs_sharpe', 0):.2f} (< 1.0)。")
                    print(f"⏩ 立即置 times=1，0.05 秒内无缝切入下一个主信号，拒绝算力与 Token 浪费！")
                    break

                # 若通过 Step 1 或后续 Step:
                qualified = step1_status.get("qualified_seeds", [])
                print(f"🎉 [主信号 {seed_id} Step #{step} 通过] 捕获 {len(qualified)} 条达标变体 (最高 |Sharpe| = {step1_status.get('max_abs_sharpe', 0):.2f})！")

                # ---------------- 双窗口敏感性成对验证 (参数高原压力测试器) ----------------
                horizon_verdicts = sim_res.get("horizon_verdicts")
                if not horizon_verdicts:
                    horizon_pairs = HorizonProbe.detect_pairs(variants)
                    all_sh = step1_status.get("all_sharpes", {})
                    horizon_verdicts = HorizonProbe.evaluate(variants, qualified, horizon_pairs, all_sharpes=all_sh)
                    HorizonProbe.annotate(qualified, horizon_verdicts, horizon_pairs)
                    print(HorizonProbe.format_report(horizon_verdicts))
                try:
                    with open(os.path.join(self.campaign_dir, f"horizon_probe_{seed_id}_s{step}.json"), "w", encoding="utf-8") as hpf:
                        json.dump({
                            "summary": HorizonProbe.summarize(horizon_verdicts),
                            "verdicts": horizon_verdicts,
                        }, hpf, ensure_ascii=False, indent=2)
                except Exception:
                    pass

                for q in qualified:
                    q["seed_id"] = seed_id
                    seed_qualified_alphas.append(q)
                    self.history_save.append(q)
                    # 尖峰过拟合候选: 保留指标但严禁晋升为 Step 2 母本 (隐藏 OS 存活率极低)
                    if q.get("horizon_verdict") == "SPIKE":
                        print(f"   🔴 [尖峰剔除] N/2N 双窗口表现严重不一致，禁止作为演进母本: {q.get('expression', '')[:60]}")
                        continue
                    if abs(q.get("sharpe", 0.0)) >= 1.2:
                        seed_good_alphas.append(q)
                        self.good_alphas.append(q)

                # 🏛️ 准生产突破池 (Near-Miss Hall of Fame) 物理入库与基因强制沉淀
                for q in qualified:
                    if Gatekeeper.is_near_miss_champion(q, self.region):
                        q["status"] = "NEAR_CHAMPION"
                        q["near_champion"] = True
                        if not hasattr(self, "near_miss_hall_of_fame"):
                            self.near_miss_hall_of_fame = []
                        if not any(nm.get("expression") == q.get("expression") for nm in self.near_miss_hall_of_fame):
                            self.near_miss_hall_of_fame.append(q)
                            print(f"\n🏛️ 【入选准生产突破池 (Near-Miss Hall of Fame)】{q['expression'][:55]}...")
                            print(f"   Sharpe={q['sharpe']:.2f} (离1.58仅差{1.58-q['sharpe']:.2f}) | ProdCorr={q.get('prod_corr', 0.0):.4f} | Margin={q['margin_bps']:.1f}bps")
                            hm_path = os.path.join(self.campaign_dir, "near_miss_hall_of_fame.json")
                            try:
                                with open(hm_path, 'w', encoding='utf-8') as hmf:
                                    json.dump(self.near_miss_hall_of_fame, hmf, ensure_ascii=False, indent=2)
                            except Exception:
                                pass

                            # 物理触发 Knowledge Distiller 基因锁定入金字塔知识库 (不设 final_passed 门槛)
                            distill_session = self.client.create_session(role="aegis-knowledge-distiller", model=self.model)
                            distill_prompt = (
                                f"准生产突破 Alpha: {q['expression']} (Sharpe={q['sharpe']:.2f}, ProdCorr={q.get('prod_corr', 0.0):.4f}, Margin={q['margin_bps']:.1f}bps)。\n"
                                f"该因子攻克了最难的生产共线死线 (ProdCorr < 0.70) 与高利润溢价 (Margin >= 18bps)。\n"
                                f"请提炼纯算子抽象经验。严格遵循原则：只总结纯算子结构规律与风控拓扑，严禁出现任何具体数据字段名！"
                            )
                            try:
                                distill_res = await distill_session.send_message(
                                    distill_prompt,
                                    json_mode=False,
                                    context={"alpha": q, "task_tag": f"{seed_id}_s{step}_nearmiss_distill"}
                                )
                                abstract_rule = str(distill_res) if distill_res else (
                                    f"在 {self.region} Delay {self.delay} 的 {self.category.upper()} 因子中，"
                                    f"长周期时序平滑差分结合多空分位数差分与行业中性化可实现超低 ProdCorr 与高 Margin。"
                                )
                                RAGMemoryEngine.append_pure_operator_experience(
                                    region=self.region,
                                    delay=self.delay,
                                    category=self.category,
                                    abstract_insight=abstract_rule,
                                    alpha_stats=q
                                )
                            except Exception as _de:
                                print(f"⚠️ [经验提炼] 准冠军经验沉淀异常: {_de}")

                # 局部最优与全局标杆排序 (优先依据 Champion_Score 综合效用，Sharpe 绝对值为辅)
                seed_good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                self.good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                self.save_campaign_memory()

                # 记录历史文件
                with open(self.history_file, 'a', encoding='utf-8') as hf:
                    hf.write(f"\n--- Cycle {explored_count} [{seed_id} Step #{step}] ---\n")
                    for q in qualified:
                        hf.write(f"Sharpe: {q.get('sharpe'):.2f} | Expr: {q.get('expression')}\n")

                # Step 2 合规门槛核对
                step2_passed = sim_res.get("step2_passed", [])
                print(f"📋 Step 2 合规通过数: {len(step2_passed)} 条")

                # 终极生产准入门禁核对
                final_passed = sim_res.get("final_passed", [])
                if final_passed:
                    print("\n" + "🌟" * 30)
                    print(f"🏆 【诞生生产级达标 Alpha！】主信号 {seed_id} 产生 {len(final_passed)} 条达标因子！")
                    for i, f_alpha in enumerate(final_passed):
                        print(f"  - 表达式: {f_alpha['expression']}")
                        print(f"    Sharpe: {f_alpha['sharpe']:.2f} | Fitness: {f_alpha['fitness']:.2f} | Margin: {f_alpha['margin_bps']:.1f}bps")

                        # 触发经验提炼: 纯算子、去字段化抽象沉淀 (Plan 1 隔离会话)
                        distill_session = self.client.create_session(role="aegis-knowledge-distiller", model=self.model)
                        distill_prompt = (
                            f"达标 Alpha: {f_alpha['expression']} (Sharpe={f_alpha['sharpe']:.2f}, Fitness={f_alpha['fitness']:.2f})。\n"
                            f"请提炼纯算子抽象经验。严格遵循原则：只总结纯算子结构规律与风控拓扑，严禁出现任何具体数据字段名！"
                        )
                        distill_res = await distill_session.send_message(
                            distill_prompt,
                            json_mode=False,
                            context={"alpha": f_alpha, "task_tag": f"{seed_id}_s{step}_distill_{i+1}"}
                        )
                        abstract_rule = str(distill_res) if distill_res else (
                            f"在 {self.region} Delay {self.delay} 的 {self.category.upper()} 因子中，"
                            f"时序差分结合指数衰减可显著改善动量捕捉与换手率；"
                            f"前置 winsorize(std=3) 抑制子池震荡，结合高阶风险中性化可有效突破 Margin 死线。"
                        )
                        # 幂等沉淀：避免多轮断点恢复时重复追加写入经验库
                        distill_done_flag = os.path.join(self.campaign_dir, f".distilled_{seed_id}_s{step}_{i+1}.flag")
                        if not os.path.exists(distill_done_flag):
                            RAGMemoryEngine.append_pure_operator_experience(
                                region=self.region,
                                delay=self.delay,
                                category=self.category,
                                abstract_insight=abstract_rule,
                                alpha_stats=f_alpha
                            )
                            with open(distill_done_flag, "w", encoding="utf-8") as df:
                                df.write("1")
                    self.save_campaign_memory()
                    print("🌟" * 30 + "\n")

                # ---------------------------------------------------------
                # Step 5: 自动升阶深水区精炼 (func2) - 真实提交回测闭环
                # ---------------------------------------------------------
                if len(seed_good_alphas) >= 3 and not func2_triggered:
                    func2_triggered = True
                    print(f"\n🌊 [Step 5 自动升阶] 主信号 {seed_id} 优质候选达 {len(seed_good_alphas)} 个 (>= 3)，激活 func2 深水区精炼...")
                    func2_batch_filename = f"batch_{seed_id}_func2_s{step}.json"
                    func2_batch_path = os.path.join(self.campaign_dir, func2_batch_filename)
                    func2_sim_cache_path = os.path.join(self.campaign_dir, f"sim_res_{seed_id}_func2_s{step}.json")

                    if os.path.exists(func2_sim_cache_path):
                        with open(func2_sim_cache_path, 'r', encoding='utf-8') as f2_cache:
                            func2_sim_res = json.load(f2_cache)
                        print(f"⏩ [断点恢复] 已加载 {seed_id} func2 历史回测结果，跳过重复回测！")
                    else:
                        refiner_session = self.client.create_session(role="aegis-deep-refiner", model=self.model)

                        # 准备同源候选特征备选池 (严格过滤 coverage >= 0.20，确保备选特征具备高覆盖率)
                        all_fields = list(known_fields.keys())
                        core_used = set(seed.get("fields_used", []))
                        valid_candidates = [
                            fn for fn in all_fields
                            if fn not in core_used and known_fields.get(fn, {}).get("coverage", 1.0) >= 0.20
                        ]
                        # 按 coverage 高且 alpha_count 低综合排序 (优先挖掘低拥挤度冷门特征)
                        valid_candidates.sort(
                            key=lambda fn: known_fields.get(fn, {}).get("coverage", 0) / (1 + math.log1p(known_fields.get(fn, {}).get("alpha_count", 0))),
                            reverse=True
                        )
                        sampled_candidates = valid_candidates[:20] if len(valid_candidates) <= 20 else random.sample(valid_candidates, 20)

                        alt_candidates = []
                        for fn in sampled_candidates:
                            f_meta = known_fields.get(fn, {})
                            alt_candidates.append({
                                "name": fn,
                                "type": f_meta.get("type", "MATRIX"),
                                "description": f_meta.get("description", "无描述"),
                                "coverage": round(f_meta.get("coverage", 1.0), 3),
                                "update_frequency": f_meta.get("update_frequency", "quarterly" if self.category == "fundamental" else "daily"),
                                "semantic_role": f_meta.get("semantic_role", "Signal_Flow"),
                                "alpha_count": int(f_meta.get("alpha_count", 0)),
                                "domain": f_meta.get("domain", "unbounded"),
                                "is_sparse": bool(f_meta.get("is_sparse", False))
                            })

                        max_champ_ops = getattr(self, "max_champion_operators", 6)
                        max_ast_ops = getattr(self, "max_ast_operators", 8)
                        phase_name = "准冠军定向优化阶段" if getattr(self, "is_quasi_champion_optimization", False) else "常规研究挖掘阶段"
                        refiner_prompt = (
                            f"当前针对主信号 {seed_id} 累计发现 {len(seed_good_alphas)} 个达标母本 (Sharpe >= 1.2)。\n"
                            f"最优母本: {seed_good_alphas[0]['expression']} (Sharpe={seed_good_alphas[0].get('sharpe', 0.0):.2f})\n"
                            f"已达标母本清单:\n{json.dumps(seed_good_alphas[:5], ensure_ascii=False, indent=1)}\n\n"
                            f"【可选同源/同数据集特征备选池 (供特征替换)】:\n{json.dumps(alt_candidates, ensure_ascii=False, indent=1)}\n\n"
                            f"【可用高阶中性化白名单】: {self.get_supported_neutralizations()}\n\n"
                            f"{SwarmAuditor.build_directive(self.parallelism, event_driven=self.category in EVENT_DRIVEN_CATEGORIES)}\n\n"
                            f"【精炼攻坚任务契约】:\n"
                            f"1. 特征平替：利用上述备选池中高度同源特征替换原表达式中饱和特征，打破同质化；\n"
                            f"2. 算子平替与剪枝：用高效算子替代冗余算子，精简 AST 深度；\n"
                            f"3. 攻坚 CW (Crowding) 与高阶风险中性化，提升 Fitness 与 Margin；\n"
                            f"4. 【算子数硬约束 ({phase_name})】：最终表达式算子数必须 <= {max_champ_ops} (AST 节点 <= {max_ast_ops})，回测前将由 AST Auditor 静态核验硬性拦截；\n"
                            f"5. 严格返回 JSON 数组格式（共 {self.parallelism} 个变体），每个对象按顺序包含 slot, optimize_reason, expression, neutralization, type, original_alpha 六个键（先写 optimize_reason 再写 expression！）。"
                        )
                        context_refiner = {
                            "parents": seed_good_alphas[:5],
                            "neutralizations": self.get_supported_neutralizations(),
                            "category": self.category,
                            "region": self.region,
                            "known_fields": known_fields,
                            "alt_candidates": alt_candidates,
                            "parallelism": self.parallelism,
                            "task_tag": f"{seed_id}_s{step}_func2"
                        }
                        refined_variants = await refiner_session.send_message(refiner_prompt, json_mode=True, context=context_refiner)
                        if isinstance(refined_variants, list) and len(refined_variants) > 0:
                            tasks_dir = self.client.tasks_dir or os.path.join(self.base_dir, ".agent_tasks")
                            refiner_resp = os.path.join(tasks_dir, f"resp_aegis-deep-refiner_{seed_id}_s{step}_func2.json")
                            try:
                                SwarmAuditor.enforce(
                                    refined_variants,
                                    step=5,
                                    parallelism=self.parallelism,
                                    strict=False
                                )
                            except (ValueError, PermissionError, RuntimeError) as e:
                                if os.path.exists(refiner_resp):
                                    try:
                                        os.remove(refiner_resp)
                                    except Exception:
                                        pass
                                raise e

                            print(f"🌊 深水区精炼生成 {len(refined_variants)} 条攻坚变体，正在组装批次并提交并发回测...")

                            # 清理可能残留的 authorized_mutations.json，避免 func1 的局部处方锁误伤 func2
                            rx_path = os.path.join(self.campaign_dir, "authorized_mutations.json")
                            if os.path.exists(rx_path):
                                try:
                                    os.remove(rx_path)
                                except Exception:
                                    pass

                            with open(func2_batch_path, 'w', encoding='utf-8') as f2:
                                json.dump({
                                    "seed_id": f"{seed_id}_FUNC2",
                                    "step": 5,
                                    "region": self.region,
                                    "universe": self.universe,
                                    "delay": self.delay,
                                    "category": self.category,
                                    "known_fields": known_fields,
                                    "expected_polarity": seed.get("expected_polarity", 1),
                                    "core_fields": [],
                                    "max_ast_operators": getattr(self, "max_ast_operators", 8),
                                    "max_champion_operators": getattr(self, "max_champion_operators", 6),
                                    "items": refined_variants
                                }, f2, ensure_ascii=False, indent=2)

                            try:
                                func2_sim_res = await SimBatchRunner.run_batch_silently(
                                    batch_file_path=func2_batch_path,
                                    region=self.region,
                                    universe=self.universe,
                                    delay=self.delay,
                                    category=self.category,
                                    neutralization=None,
                                    ledger_path=campaign_ledger
                                )
                            except (ValueError, PermissionError, RuntimeError) as e:
                                if os.path.exists(refiner_resp):
                                    try:
                                        os.remove(refiner_resp)
                                    except Exception:
                                        pass
                                if os.path.exists(func2_batch_path):
                                    try:
                                        os.remove(func2_batch_path)
                                    except Exception:
                                        pass
                                raise e
                            with open(func2_sim_cache_path, 'w', encoding='utf-8') as f2_cache:
                                json.dump(func2_sim_res, f2_cache, ensure_ascii=False, indent=2)

                        # -----------------------------------------------------
                        # 核心成果回收：全面提取 func2 跑出的高夏普准达标候选，绝不丢弃演进成果
                        # -----------------------------------------------------
                        func2_step1 = func2_sim_res.get("step1", {})
                        func2_qualified = func2_step1.get("qualified_seeds", [])
                        if func2_qualified:
                            print(f"🌊 [func2 演进成果回收] 捕获 {len(func2_qualified)} 条优质变体 (最高 |Sharpe| = {func2_step1.get('max_abs_sharpe', 0.0):.2f})！")
                            with open(self.history_file, 'a', encoding='utf-8') as hf:
                                hf.write(f"\n--- Cycle {explored_count} [{seed_id} func2 Step #{step}] ---\n")
                                for q in func2_qualified:
                                    hf.write(f"Sharpe: {q.get('sharpe'):.2f} | Expr: {q.get('expression')}\n")
                            for q in func2_qualified:
                                q["seed_id"] = seed_id
                                seed_qualified_alphas.append(q)
                                self.history_save.append(q)
                                if abs(q.get("sharpe", 0.0)) >= 1.2:
                                    seed_good_alphas.append(q)
                                    self.good_alphas.append(q)

                            # 🏛️ 准生产突破池 (Near-Miss Hall of Fame) 物理入库与基因强制沉淀 (func2 成果回收)
                            for q in func2_qualified:
                                if Gatekeeper.is_near_miss_champion(q, self.region):
                                    q["status"] = "NEAR_CHAMPION"
                                    q["near_champion"] = True
                                    if not hasattr(self, "near_miss_hall_of_fame"):
                                        self.near_miss_hall_of_fame = []
                                    if not any(nm.get("expression") == q.get("expression") for nm in self.near_miss_hall_of_fame):
                                        self.near_miss_hall_of_fame.append(q)
                                        print(f"\n🏛️ 【func2 入选准生产突破池 (Near-Miss Hall of Fame)】{q['expression'][:55]}...")
                                        print(f"   Sharpe={q['sharpe']:.2f} (离1.58仅差{1.58-q['sharpe']:.2f}) | ProdCorr={q.get('prod_corr', 0.0):.4f} | Margin={q['margin_bps']:.1f}bps")
                                        hm_path = os.path.join(self.campaign_dir, "near_miss_hall_of_fame.json")
                                        try:
                                            with open(hm_path, 'w', encoding='utf-8') as hmf:
                                                json.dump(self.near_miss_hall_of_fame, hmf, ensure_ascii=False, indent=2)
                                        except Exception:
                                            pass

                                        # 物理触发 Knowledge Distiller 基因锁定入金字塔知识库 (幂等)
                                        func2_distill_nm_flag = os.path.join(self.campaign_dir, f".distilled_{seed_id}_s{step}_func2_nearmiss.flag")
                                        if not os.path.exists(func2_distill_nm_flag):
                                            distill_session = self.client.create_session(role="aegis-knowledge-distiller", model=self.model)
                                            distill_prompt = (
                                                f"准生产突破 Alpha (func2 深水区产出): {q['expression']} (Sharpe={q['sharpe']:.2f}, ProdCorr={q.get('prod_corr', 0.0):.4f}, Margin={q['margin_bps']:.1f}bps)。\n"
                                                f"该因子攻克了最难的生产共线死线 (ProdCorr < 0.70) 与高利润溢价 (Margin >= 18bps)。\n"
                                                f"请提炼纯算子抽象经验。严格遵循原则：只总结纯算子结构规律与风控拓扑，严禁出现任何具体数据字段名！"
                                            )
                                            try:
                                                distill_res = await distill_session.send_message(
                                                    distill_prompt,
                                                    json_mode=False,
                                                    context={"alpha": q, "task_tag": f"{seed_id}_s{step}_func2_nearmiss_distill"}
                                                )
                                                abstract_rule = str(distill_res) if distill_res else (
                                                    f"在 {self.region} Delay {self.delay} 的 {self.category.upper()} 深水区因子中，"
                                                    f"长周期时序平滑差分结合多空分位数差分与行业中性化可实现超低 ProdCorr 与高 Margin。"
                                                )
                                                RAGMemoryEngine.append_pure_operator_experience(
                                                    region=self.region,
                                                    delay=self.delay,
                                                    category=self.category,
                                                    abstract_insight=abstract_rule,
                                                    alpha_stats=q
                                                )
                                                with open(func2_distill_nm_flag, "w", encoding="utf-8") as dnf:
                                                    dnf.write("1")
                                            except Exception as _e_dist:
                                                print(f"⚠️ [Knowledge Distiller] func2 准生产经验提炼异常: {_e_dist}")

                            seed_good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                            self.good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                            self.save_campaign_memory()

                        func2_final = func2_sim_res.get("final_passed", [])
                        if func2_final:
                            print(f"🏆🏆 【深水区精炼大突破】诞生 {len(func2_final)} 条生产级达标 Alpha！")
                            for j, f_alpha in enumerate(func2_final):
                                f_alpha["seed_id"] = seed_id
                                print(f"  🌟 突破表达式: {f_alpha['expression']}")
                                print(f"     Sharpe: {f_alpha['sharpe']:.2f} | Fitness: {f_alpha['fitness']:.2f} | Margin: {f_alpha['margin_bps']:.1f}bps")
                                seed_good_alphas.append(f_alpha)
                                self.good_alphas.append(f_alpha)
                                distill_session = self.client.create_session(role="aegis-knowledge-distiller", model=self.model)
                                distill_prompt = f"达标 Alpha: {f_alpha['expression']}。请提炼纯算子抽象经验，严禁出现具体字段名！"
                                distill_res = await distill_session.send_message(
                                    distill_prompt,
                                    json_mode=False,
                                    context={"alpha": f_alpha, "task_tag": f"{seed_id}_s{step}_func2_distill_{j+1}"}
                                )
                                # 幂等沉淀：避免深水区多轮断点恢复时重复追加写入经验库
                                func2_distill_done_flag = os.path.join(self.campaign_dir, f".distilled_{seed_id}_s{step}_func2_{j+1}.flag")
                                if not os.path.exists(func2_distill_done_flag):
                                    RAGMemoryEngine.append_pure_operator_experience(
                                        region=self.region,
                                        delay=self.delay,
                                        category=self.category,
                                        abstract_insight=str(distill_res) if distill_res else "深水区精炼攻坚成功",
                                        alpha_stats=f_alpha
                                    )
                                    with open(func2_distill_done_flag, "w", encoding="utf-8") as df:
                                        df.write("1")
                            seed_good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                            self.good_alphas.sort(key=lambda x: (self.compute_champion_score(x), abs(x.get("sharpe", 0.0))), reverse=True)
                            self.save_campaign_memory()
                            # 仅当诞生 warning_count == 0 的完美全绿因子时才提前 break，否则继续攻坚消灭 Warning
                            if any(int(a.get("warning_count", 0)) == 0 for a in func2_final):
                                break

                # 状态机加时冲刺 (Golden Shot) 判定: 出现准冠军雏形或带 Warning 达标因子时物理否决 "3 步走完就走人"
                if step == step_limit and not overtime_granted:
                    near_misses = [q for q in seed_qualified_alphas if Gatekeeper.is_near_miss_champion(q, self.region)]
                    warning_champions = [
                        q for q in (seed_good_alphas + seed_qualified_alphas)
                        if abs(q.get("sharpe", 0.0)) >= 1.58 and int(q.get("warning_count", 0)) > 0
                    ]
                    overtime_candidates = near_misses + warning_champions
                    has_perfect_0w = any(
                        abs(q.get("sharpe", 0.0)) >= 1.58 and int(q.get("warning_count", 0)) == 0 and (Gatekeeper.extract_prod_corr(q) or 0.0) < 0.70
                        for q in seed_good_alphas
                    )
                    if overtime_candidates and not has_perfect_0w:
                        overtime_granted = True
                        step_limit += 1
                        best_nm = max(overtime_candidates, key=lambda x: self.compute_champion_score(x))
                        reason_msg = "冲刺 0 WARNING 全绿 (ALL PASS)" if int(best_nm.get("warning_count", 0)) > 0 else "攻坚最后微小差距"
                        print("\n" + "🔥" * 35)
                        print(f"🛑 [状态机硬拦截] 主信号 {seed_id} 触发加时冲刺候选: {best_nm['expression'][:45]}...！")
                        print(f"   (Sharpe={best_nm['sharpe']:.2f}, Warnings={best_nm.get('warning_count', 0)}, ProdCorr={best_nm.get('prod_corr', 0.0):.4f}, Margin={best_nm['margin_bps']:.1f}bps)")
                        print(f"⚡ 物理否决 '3 步走完就走人'！状态机自动签发加时冲刺 (Golden Shot)，{reason_msg}！")
                        print("🔥" * 35 + "\n")
                step += 1

            # 无论是否达标，该主信号探索轮次结束，times 递增并保存
            seed["times"] = seed.get("times", 0) + 1
            self.save_signals_pool(pool)

        # -------------------------------------------------------------
        # 收割期最后防线：「一主锚一代表（One-Champion-Per-Anchor）」综合效用评分选优
        # -------------------------------------------------------------
        champions_by_seed = {}
        corr_excluded = []
        all_harvest_candidates = self.good_alphas + [
            a for a in self.history_save if abs(a.get("sharpe", 0.0)) >= 1.2
        ]

        seen_exprs = set()
        unique_candidates = []
        for a in all_harvest_candidates:
            expr_key = a.get("expression", "").strip()
            if expr_key and expr_key not in seen_exprs:
                seen_exprs.add(expr_key)
                unique_candidates.append(a)

        for alpha in unique_candidates:
            s_id = alpha.get("seed_id", "UNKNOWN_SEED")
            score = self.compute_champion_score(alpha)
            alpha["champion_score"] = round(score, 4)

            # 冠军资格硬过滤:
            # 1. 明确共线 (ProdCorr >= 0.70) 或 复杂度超标 (算子数 > 6) 彻底剔除出领奖台
            # 2. ProdCorr 尚未核实 (None) 的标记为 "PENDING_PROD_CORR_CHECK" 准冠军登台待验
            elig = self.champion_eligibility(alpha)
            alpha["champion_eligibility"] = elig
            if not elig["eligible"]:
                corr_excluded.append({
                    "seed_id": s_id,
                    "expression": alpha.get("expression", ""),
                    "prod_corr": elig["prod_corr"],
                    "operator_count": elig["operator_count"],
                    "reasons": elig["reasons"],
                })
                continue

            prev = champions_by_seed.get(s_id)
            if prev is None:
                champions_by_seed[s_id] = alpha
            else:
                # 排序优先级: 已核实(VERIFIED) > 准生产突破(NEAR) > 待核验(PENDING) -> 0 WARNING 全绿优先 -> Margin 达标 -> Champion_Score
                def _status_rank(st):
                    if st == "VERIFIED_CHAMPION":
                        return 3
                    if st == "NEAR_CHAMPION":
                        return 2
                    return 1

                new_status_rank = _status_rank(elig.get("status"))
                old_elig = prev.get("champion_eligibility", {})
                old_status_rank = _status_rank(old_elig.get("status"))

                new_key = (new_status_rank, bool(elig.get("zero_warnings")), bool(elig.get("margin_premium_ok")), score)
                old_key = (old_status_rank, bool(old_elig.get("zero_warnings")), bool(old_elig.get("margin_premium_ok")), float(prev.get("champion_score", 0.0)))
                if new_key > old_key:
                    champions_by_seed[s_id] = alpha

        champions_list = list(champions_by_seed.values())
        champions_list.sort(
            key=lambda x: (
                3 if x.get("champion_eligibility", {}).get("status") == "VERIFIED_CHAMPION" else (2 if x.get("champion_eligibility", {}).get("status") == "NEAR_CHAMPION" else 1),
                bool(x.get("champion_eligibility", {}).get("zero_warnings")),
                bool(x.get("champion_eligibility", {}).get("margin_premium_ok")),
                x.get("champion_score", 0.0)
            ),
            reverse=True
        )
        champions_path = os.path.join(self.campaign_dir, "campaign_champions.json")
        try:
            with open(champions_path, 'w', encoding='utf-8') as cf:
                json.dump(champions_list, cf, ensure_ascii=False, indent=2)
            with open(os.path.join(self.campaign_dir, "champion_report.json"), "w", encoding="utf-8") as crf:
                json.dump({
                    "region": self.region,
                    "champion_margin_premium_bps": REGION_CHAMPION_MARGIN_BPS.get(self.region, 15.0),
                    "pcorr_max": 0.70,
                    "max_operator_count": getattr(self, "max_champion_operators", 6),
                    "champions": champions_list,
                    "excluded_by_eligibility": corr_excluded,
                }, crf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        print("\n=======================================================")
        print(f"🏁 AEGIS GrandMaster 调度闭环执行完成！")
        print(f"📈 累计发现高潜候选: {len(self.good_alphas)} 个 | 历史记录: {self.history_file}")
        if corr_excluded:
            print(f"🔗 【相关性/复杂度资格剔除】{len(corr_excluded)} 条候选虽达标但不得上冠军台:")
            for ex in corr_excluded[:5]:
                print(f"   - [{ex['seed_id']}] ProdCorr={ex['prod_corr']} ops={ex['operator_count']} | {'; '.join(ex['reasons'])}")
                print(f"     {ex['expression'][:80]}")
        if champions_list:
            print(f"🏆 【一主锚一代表 (One-Champion-Per-Anchor)】唯一冠军领奖台 (共 {len(champions_list)} 个主信号代表):")
            for rank, champ in enumerate(champions_list, 1):
                c_seed = champ.get("seed_id", "SEED")
                c_score = champ.get("champion_score", 0.0)
                c_sharpe = float(champ.get("sharpe", 0.0))
                c_fit = float(champ.get("fitness", 0.0))
                c_margin = float(champ.get("margin_bps", 0.0))
                c_expr = champ.get("expression", "")
                elig = champ.get("champion_eligibility", {})
                c_status = elig.get("status", "QUALIFIED")
                c_pc = elig.get("prod_corr")
                c_ops = elig.get("operator_count", 0)
                zero_w = elig.get("zero_warnings", False)
                w_lbl = " [ALL PASS 0W]" if zero_w else ""
                if c_status == "VERIFIED_CHAMPION":
                    status_lbl = f"【已核实冠军 VERIFIED{w_lbl}】"
                    pc_txt = f"{c_pc:.3f}" if c_pc is not None else "0.000"
                elif c_status == "NEAR_CHAMPION":
                    status_lbl = f"【准生产突破代表 NEAR_CHAMPION{w_lbl}】"
                    pc_txt = f"{c_pc:.3f}" if c_pc is not None else "0.000"
                else:
                    status_lbl = f"【待核验准冠军 PENDING{w_lbl}】"
                    pc_txt = "待核验"
                print(
                    f"  🥇 #{rank} [{c_seed}] {status_lbl} Champion_Score={c_score:.3f} | Sharpe={c_sharpe:.2f} | "
                    f"Fitness={c_fit:.2f} | Margin={c_margin:.1f}bps | ProdCorr={pc_txt} | ops={c_ops} | Expr: {c_expr}"
                )
            print(f"📁 生产池冠军报表已落地: {champions_path}")
        print("=======================================================\n")

# 兼容命令行执行 (对齐 run_this.sh 与 argparse)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS GrandMaster 纯 Python 状态机调度引擎")
    parser.add_argument("--region", default="USA")
    parser.add_argument("--universe", default="TOP1000")
    parser.add_argument("--delay", type=int, default=1)
    parser.add_argument("--category", default="news")
    parser.add_argument("--dataset", default="news12")
    parser.add_argument("--setting", default=None, help="例如: #GLB#1#MINVOL1M## 或 ALPHA_ID#...")
    parser.add_argument("--alpha-id", default=None, help="目标优化的已有 Alpha ID (情况二)")
    parser.add_argument("--model", default="Gemini 3.8 Flash (High)")
    parser.add_argument("--parallelism", type=int, default=20)
    parser.add_argument("--generate-seeds", action="store_true", help="强制生成阶段 0 主信号储备池 (生成后自动继续推进回测流水线)")
    parser.add_argument("--seeds-only", action="store_true", help="仅生成阶段 0 主信号储备池后退出")
    parser.add_argument("--mock-only", action="store_true", help="强制仅使用高保真白盒规则引擎 (毫秒级响应，仅限单元测试)")
    parser.add_argument("--backend", default="builtin", choices=["builtin", "subagent", "ipc", "file", "llm_api", "agy", "mock"], help="智能体执行后端: builtin (AI工具内置Agent, 默认0依赖) | llm_api | agy | mock")
    parser.add_argument("--fields-file", default=None, help="显式指定字段元数据画像 JSON 文件路径")
    parser.add_argument("--fields", default=None, help="显式指定逗号分隔字段名清单 (如 f1,f2,f3)")
    parser.add_argument("--ipc-dir", default=None, help="SubAgent IPC 任务交互目录 (默认 .agent_tasks)")
    parser.add_argument("--no-cross-region-fields", action="store_true", help="禁用跨区域同源字段自动继承")
    parser.add_argument("--max-operator-count", type=int, default=None, help="最大算子数约束 (默认研究挖掘阶段 <=6, 准冠军优化阶段 <=10)")
    
    # 兼容原帖 run_this.sh 纯位置参数: main.py $NOW "True" "$MODEL" "$SETTING" "$BASE_DIR" "$OPERATORS_PATH" $EXCLUDE_CATEGORY
    args, unknown = parser.parse_known_args()
    
    # 检查是否有位置参数 (来自 shell 脚本)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        pos_now = sys.argv[1] if len(sys.argv) > 1 else ""
        pos_gen_seed = sys.argv[2].lower() == "true" if len(sys.argv) > 2 else False
        pos_model = sys.argv[3] if len(sys.argv) > 3 else args.model
        pos_setting = sys.argv[4] if len(sys.argv) > 4 else ""
        pos_base_dir = sys.argv[5] if len(sys.argv) > 5 else None

        # 解析 SETTING: 如 #USA#1#TOP1000#news#news12 或 88RgeN6o#GLB#1#MINVOL10M#fundamental#fundamental23
        if pos_setting and "#" in pos_setting:
            parts = pos_setting.split("#")
            # 格式可能为: [alpha_id, region, delay, universe, category, dataset]
            if parts[0]:
                args.alpha_id = parts[0]
            if len(parts) >= 4:
                if parts[1]: args.region = parts[1]
                if parts[2]: args.delay = int(parts[2])
                if parts[3]: args.universe = parts[3]
                if len(parts) >= 5 and parts[4]: args.category = parts[4]
                if len(parts) >= 6 and parts[5]: args.dataset = parts[5]

        args.model = pos_model
        args.generate_seeds = pos_gen_seed
    elif args.setting and "#" in args.setting:
        parts = args.setting.split("#")
        if parts[0]:
            args.alpha_id = parts[0]
        if len(parts) >= 4:
            if parts[1]: args.region = parts[1]
            if parts[2]: args.delay = int(parts[2])
            if parts[3]: args.universe = parts[3]
            if len(parts) >= 5 and parts[4]: args.category = parts[4]
            if len(parts) >= 6 and parts[5]: args.dataset = parts[5]

    controller = AegisPipelineController(
        region=args.region,
        universe=args.universe,
        delay=args.delay,
        category=args.category,
        dataset_id=args.dataset,
        model=args.model,
        parallelism=args.parallelism,
        targeted_alpha_id=args.alpha_id,
        mock_only=args.mock_only,
        backend_type=args.backend,
        fields_file=args.fields_file,
        raw_fields_arg=args.fields,
        allow_cross_region_fields=not args.no_cross_region_fields,
        tasks_dir=args.ipc_dir,
        max_operator_count=args.max_operator_count
    )

    if args.generate_seeds or getattr(args, "seeds_only", False):
        # 当显式指定重新生成种子时，若非断点恢复阶段，方清理旧响应缓存
        tasks_dir = controller.client.tasks_dir or os.path.join(controller.base_dir, ".agent_tasks")
        for f in [f"resp_aegis-seed-synthesizer_stage0_{controller.dataset_id}.json",
                  f"resp_aegis-tech-auditor_stage0_audit_{controller.dataset_id}.json"]:
            p = os.path.join(tasks_dir, f)
            t_file = os.path.join(tasks_dir, f.replace("resp_", "task_"))
            if os.path.exists(p) and not os.path.exists(t_file):
                try:
                    os.remove(p)
                except Exception:
                    pass
        controller.synthesize_stage0_seeds(count=20)
        if getattr(args, "seeds_only", False):
            print("✅ 阶段 0 种子生成完毕 (--seeds-only)，平稳停机。")
            sys.exit(0)

    asyncio.run(controller.run_pipeline_loop())
