"""
main.py
AEGIS GrandMaster 纯 Python 状态机总控调度引擎
(复刻 WS29639 原帖 GrandMaster 设计：Python + AI 模式，极度节约 Token & 完全可控)

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
        if self.mock_only:
            os.environ["AEGIS_MOCK_MODE"] = "1"
        self.backend_type = backend_type
        self.fields_file = fields_file
        self.raw_fields_arg = raw_fields_arg
        self.allow_cross_region_fields = allow_cross_region_fields
        self.tasks_dir = tasks_dir
        
        self.initial_max_operator_count = max_operator_count
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
        self.corrector = ASTSandboxCorrector(db_path=os.path.join(self.campaign_dir, "alphas_record.db"))
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
        self.failed_hypotheses_digest: List[str] = []
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as mf:
                    mem = json.load(mf)
                    self.good_alphas = mem.get("good_alphas", [])
                    self.history_save = mem.get("history_save", [])
                    self.failed_hypotheses_digest = mem.get("failed_hypotheses_digest", [])
            except Exception:
                pass

    def save_campaign_memory(self):
        """持久化保存全局战役记忆 (good_alphas, history_save 与 failed_hypotheses_digest)"""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as mf:
                json.dump({
                    "good_alphas": self.good_alphas,
                    "history_save": self.history_save,
                    "failed_hypotheses_digest": getattr(self, "failed_hypotheses_digest", [])[-15:]
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
        阶段 0: ATOM Alpha 原生主信号原型生成 (Stage 0: ATOM Alpha Seed Reservoir)
        关键原则：
        1. 专攻 ATOM Alpha 范式，使用 1~3 个字段来自同一单数据集 (self.dataset_id)；
        2. 算子预算限制：总算子数 op <= 6；
        3. 严禁使用 + 和 *，以及函数形式 add 和 multiply (粗暴加乘容易造成高阶过拟合，留待组合优化阶段)；
        4. 融合单因子决策树 (截面标准化、时序滤波、同量纲剪刀差、规模比率、条件激活)；
        5. 时间窗口严格对齐自然交易日历网格 [1, 5, 10, 20, 21, 22, 60, 63, 120, 126, 250, 252]，严禁 4、44 等过拟合参数。
        """
        print(f"\n🌱 【Stage 0: ATOM Alpha 原生主信号原型生成 (op <= 6 | 严禁加乘)】")
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
            f"你是一位顶级的 WorldQuant 量化研究总监与 ATOM Alpha 架构专家。请深入研读下方给定的数据集字段画像，构建 {count} 个高价值、低相关性、非过拟合的 ATOM 原生主信号假说。\n"
            f"目标配置: 区域 {self.region} | 股票池 {self.universe} | 预测延迟 Delay {self.delay} | 类别 {self.category} | 数据集 {self.dataset_id}\n\n"
            f"【ATOM Alpha 种子挖掘核心准则 (GrandMaster 铁律)】：\n"
            f"1. 严格锁定单数据集：所有字段必须 100% 来自指定的单数据集 ({self.dataset_id})，严禁跨数据集混用外部量价 (PV) 字段；\n"
            f"2. 字段数预算：每个种子使用 1~3 个字段 (1 <= fields <= 3)：单字段走纯 TS/CS 决策树自归一，双字段走冷热非对称配对（divide / 同量纲 subtract / ts_regression / trade_when）；\n"
            f"3. 算子数量预算：表达式总算子数必须 <= 6 (op <= 6)，保持因果链条紧凑，杜绝冗余堆叠；\n"
            f"4. 🚫 【绝对红线：严禁在种子挖掘期使用加法和乘法 (+, *, add, multiply)】：\n"
            f"   - 严禁任何形式的 A + B 或 A * B，以及 add(A, B) 或 multiply(A, B)！\n"
            f"   - 原因：单特征信号尚未确立前，粗暴相加相乘属于高阶多项式样本内强行过拟合，且导致量纲混乱与负负得正伪因果。多信号组合是组合优化器的职责，严禁提前写入单因子公式！\n"
            f"5. ✅ 【推荐算子生态：融合单因子决策树 (Single Factor Decision Tree)】：\n"
            f"   - 数据清洗与极值处理：winsorize(A, std=4) 或 std=3，防止毛刺毁掉排序；\n"
            f"   - 形状映射与尾部强调：signed_power(A, 0.5)（凹函数压缩防极端值）或 signed_power(A, 2.0)，s_log_1p(A)；\n"
            f"   - 行业截面中性化：group_zscore(A, subindustry/industry), group_neutralize(A, subindustry/industry), group_rank(A, subindustry), rank(A), scale(A)；\n"
            f"   - 时间序列动态：ts_decay_linear(A, d), ts_delta(A, d), ts_zscore(A, d), ts_regression(y, x, d, rettype=0), ts_arg_max(A, d), ts_rank(A, d), ts_mean(A, d)；\n"
            f"   - 预期差/残差剪刀差：subtract(A, B) 或 A - B（必须为同一量纲，如 Actual - Estimate，或 Feature - SectorMean）；\n"
            f"   - 内生规模与强度消除：divide(A, B) 或 A / B（B 为总资产、总报道数等内生规模分母）；\n"
            f"   - 逻辑状态激活：trade_when(cond, A, -1) 或 if_else(greater(B, threshold), A, 0)；\n"
            f"6. ⏳ 【自然交易日历时间窗口铁律 (拒绝 4, 17, 44 等无意义随机数)】：\n"
            f"   - 所有时序算子的回溯天数 d 必须严格选用具有制度性/经济学含义的自然日历网格：\n"
            f"     * 5 (1周流动性/情绪反转)\n"
            f"     * 10 (双周调仓节奏)\n"
            f"     * 20 / 22 (1个月月度财报漂移/期权交割)\n"
            f"     * 63 (1季度美股10-Q季报修正)\n"
            f"     * 126 (半年度组合再平衡)\n"
            f"     * 252 (1年美股10-K年报/滚动年化Beta与波动率)\n"
            f"   - 严禁出现 4、17、44、45 等无经济学依据的局部过拟合窗口数字！\n\n"
            f"【铁律 A：主锚字段与归一化字段的冷热配对】：\n"
            f"- 分子主信号优先选用低拥挤度细分字段 (COLD 档，alpha_pct <= 0.40)；\n"
            f"- 分母/差分基准选用高覆盖度内生字段 (coverage >= 0.80)，用于剥离规模噪音。\n\n"
            f"【候选字段全量物理画像清单】:\n{json.dumps(fields_meta_list, ensure_ascii=False, indent=1)}\n\n"
            f"【推荐冷热非对称配对清单】:\n{json.dumps(pairing_candidates, ensure_ascii=False, indent=1)}\n\n"
            f"【输出格式契约】必须返回严格的 JSON 对象（先完成商业机理研判，最后输出 expression）：\n"
            f"{{\n"
            f'  "dataset_field_study": {{\n'
            f'    "dataset_essence": "对该单数据集底层商业生成过程与核心未充分定价摩擦点的深度研判",\n'
            f'    "economic_clusters": [\n'
            f'      {{"cluster_name": "业务簇名称", "fields": ["字段名..."], "cluster_logic": "内在经济关联与去噪逻辑"}}\n'
            f"    ]\n"
            f"  }},\n"
            f'  "signals": [\n'
            f"    {{\n"
            f'      "id": "SEED_01",\n'
            f'      "cluster_ref": "所属业务簇名称",\n'
            f'      "fields_used": ["选用的1~3个具体字段名 (必须来自当前单数据集)"],\n'
            f'      "field_semantics_mapping": "逐一剖析字段商业实质、物理量纲及为何如此组合以剥离规模或基数噪音",\n'
            f'      "economic_mechanism": "完整因果传导链：底层异动 -> 市场参与者认知摩擦/交易约束 -> 价格修正方向与持续周期",\n'
            f'      "expected_polarity": 1,\n'
            f'      "expression": "<此处填入由上方因果机制推导出的 FastExpr 表达式，op<=6，严禁 + 和 *，日历窗口对齐>"\n'
            f"    }}\n"
            f"  ]\n"
            f"}}"
        )
        context = {
            "fields": sampled_names,
            "fields_meta": fields_meta_list,
            "pairing_candidates": pairing_candidates,
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

        # 直接使用毫秒级纯 Python ASTSandboxCorrector 与 DimensionAuditor 进行 ATOM Alpha 门禁审查
        signals = []
        for s in candidate_signals:
            expr = s["expression"]
            # 1. 自动日历网格吸附 (将 4->5, 17->20, 44->63 等)
            expr = ASTSandboxCorrector.snap_economic_calendar_windows(expr)
            s["expression"] = expr

            # 2. Stage 0 ATOM Alpha 专属门禁审查:
            # 严禁 +, *, add, multiply | op <= 6 | 1 <= fields <= 3 | 100% 同单数据集
            atom_ok, atom_issues, op_count, used_fields = ASTSandboxCorrector.audit_atom_stage0_expression(
                expr, valid_dataset_fields=set(all_field_names)
            )
            if not atom_ok:
                continue

            # 3. 量纲守恒与 PV 污染拦截 (上限 op <= 6)
            audit_res_ast = DimensionAuditor.audit_expression(
                expr,
                known_fields=fields_dict,
                category=self.category,
                allow_pv_cross=False,
                max_operators=6
            )
            if not audit_res_ast.get("is_valid", True):
                continue

            # 强制使用 Python AST 真实提取的数据集字段列表覆盖 LLM 自报字段
            s["fields_used"] = list(used_fields)
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

        if not signals:
            raise RuntimeError(
                f"❌ 【Stage 0 全员合规审查被拒】候选主信号原型全部未通过技术审查 / 铁律 A 冷热配对校验！\n"
                f"   系统拒绝违规死模板强行入池，请重新启动大模型推演合规种子！\n"
                f"   拒收详情: {json.dumps(pairing_report.get('rejected_detail', [])[:3], ensure_ascii=False)}"
            )

        # 若因同质化或语法违规导致存活种子不足 50%，打回重造，绝不接受缩水种子池
        min_required = max(1, int(count * 0.5))
        if len(signals) < min_required:
            raise RuntimeError(
                f"❌ 【Stage 0 存活种子不足】要求生成 {count} 个，经 AST 骨架多样性与量纲门禁审查后仅存活 {len(signals)} 个 (低于最低阈值 {min_required})！\n"
                f"   系统拒绝缩水种子池，请重新启动大模型推演高多样性合规种子！"
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

        print(f"✅ 阶段 0 生成并通过技术审查完毕，共 {len(signals)} 个 ATOM Alpha 双/三字段主信号原型写入 {self.signals_pool_file}")
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
                "domain": meta.get("domain", "unbounded"),
                "is_sparse": meta.get("is_sparse", False),
                "alpha_count": meta.get("alpha_count", meta.get("alphaCount", 0)),
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
            self.last_step_verdict = None
            self.last_step_qa_prescriptions = []
            stage_guidance = (
                "【阶段科研使命: Step #1 假说多维实证检验 (Clean Empirical Validation)】:\n"
                "- 当前假说尚未经过回测检验，不存在母本 (parent_alpha 为空)，因此本轮 100% 为假说实证探索 (type 统一填 'empirical_probe')！\n"
                "- 【基础清洗与周期高原】：允许使用 ts_backfill 与 winsorize(..., std=4) 进行基础清洗，并在 (5, 20)、(20, 63)、(63, 126)、(63, 252) 自然日历周期对上检验信号的参数高原稳健性！\n"
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
                yearly_stats=p_metrics.get("yearly_stats", []) or (parent_alpha.get("yearly_stats", []) if parent_alpha else []),
                operator_count=parent_op_count,
                prod_corr=(Gatekeeper.extract_prod_corr(parent_alpha) if parent_alpha else None) or (parent_alpha.get("prod_corr") if parent_alpha else None),
                max_operator_limit=getattr(self, "max_ast_operators", 8),
                parent_alpha=parent_alpha
            )
            # 处方凭据落盘，供 Gate 4 Pre-Flight 审计核验
            rx_path = os.path.join(self.campaign_dir, "authorized_mutations.json")
            try:
                with open(rx_path, 'w', encoding='utf-8') as rf:
                    json.dump({
                        "symptoms": verdict["symptoms"],
                        "forensic_clues": verdict.get("forensic_clues", []),
                        "allowed_mutations": []
                    }, rf, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"⚠️ [Gatekeeper] 处方锁凭据落盘异常: {e}")

            symptoms_str = ", ".join(verdict["symptoms"]) if verdict["symptoms"] else "无严重结构性病灶"
            forensic_clues_str = "\n".join(f"- {c}" for c in verdict.get("forensic_clues", [])) if verdict.get("forensic_clues") else "- 各项微观结构与统计属性稳健"
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
                    f"- 🩺 【场景路由 = 老兵精修 (1+9+10 分仓制)】母本 |Sharpe|={_parent_sharpe:.2f} 已是局部极值，本轮目标不是全绿，"
                    f"而是按母本病灶选一条轴做单点相对改进 (Margin 升 >= 20% / Turnover 降 >= 20%『仅当母本换手 > 30%』/ ProdCorr 降 >= 0.05)，"
                    f"且 |Sharpe| 不得低于母本。\n"
                    f"- ⚖️ 分仓配额: Slot 1 逐字复现母本控制槽；Slot 2~10 (45%) 锁定母本主锚特征做单变量微调；Slot 11~20 (50%) 彻底重构全新数学拓扑；\n"
                )
            else:
                mission_line = (
                    "- 🎯 【全绿冲刺使命】: 必须对症下药将 Fails 与 Warnings 一并彻底清零（实现 0 FAIL + 0 WARNING 的 ALL PASS 状态）！\n"
                )

            self.last_step_verdict = verdict
            self.last_step_qa_prescriptions = verdict.get("qa_prescriptions", [])
            stage_guidance = (
                f"【阶段科研使命: Step #{step} 基于回测病灶的靶向因子工程 (Diagnostic-Driven Engineering)】:\n"
                f"- 核心母本已证实存在显著信号！母本实测体检指标：Sharpe={p_sharpe:.2f}, Fitness={p_fit:.2f}, Turnover={p_turn:.2%}, Margin={p_margin:.2f}bps | Fails={p_fails} | Warnings={p_warnings}。\n"
                f"{golden_profile_str}\n"
                f"{mission_line}"
                f"- 🩺 【法医确诊病灶】: {symptoms_str}\n"
                f"- 🔬 【Gate 4 反事实法医病理线索 (Forensic Clues)】:\n{forensic_clues_str}\n"
                f"- 📋 【靶向 Tier-2 处方指引】:\n{rag_prescriptions_str}\n"
                + (f"\n{qa_insights_str}\n" if qa_insights_str else "")
                + f"{polarity_warning}"
                f"- 请严格根据反事实病理线索自主推演 DGP，结合第一性原理选配平台算子，绝不盲目堆叠非线性算子！\n"
            )
            output_schema_instruction = (
                f"【输出格式契约】必须返回严格的 JSON 数组，共 {self.parallelism} 个变体对象（1+9+10 三分天下分仓制）。\n"
                f"每个对象必须包含以下 6 个键：slot, optimize_reason, expression, neutralization, type, original_alpha（先写 optimize_reason 诊断依据，再写 expression！）。\n"
            )

        # ---------------- V3.1 极简瘦身 Prompt 构建 (< 1,000 Token) ----------------
        # 1. 字段铁律约束
        if step <= 2 and not parent_alpha:
            field_rule_str = "【字段铁律 (Step 1~2 初筛阶段)】: 严格 100% 锁定种子初始的 2 个字段，严禁增减任何字段！严禁使用外部量价 (PV) 字段！\n"
            alt_candidates_list = []
        else:
            field_rule_str = "【字段铁律 (Step 3~10 / 母本靶向优化)】: 允许从同数据集引入至多 1 个同源辅助特征做交互 (全表达式唯一字段总数严格 <= 3)！严禁跨数据集或引入外部量价字段！\n"
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
            alt_candidates_list = [
                {
                    "name": fn,
                    "type": fields_dict[fn].get("type", "MATRIX"),
                    "description": fields_dict[fn].get("description", "无描述"),
                    "coverage": round(fields_dict[fn].get("coverage", 1.0), 3),
                    "alpha_count": fields_dict[fn].get("alpha_count", 0),
                    "update_frequency": fields_dict[fn].get("update_frequency", "daily"),
                    "domain": fields_dict[fn].get("domain", "unbounded"),
                    "skewness": fields_dict[fn].get("skewness", "medium"),
                    "is_sparse": fields_dict[fn].get("is_sparse", False),
                }
                for fn in valid_candidates[:10]
            ]

        # 2. 30% RAG Dropout 脱敏 (30% 概率完全不召回，强迫 AI 从第一性原理发散)
        rag_dropout = (random.random() < 0.30)
        qa_prompt_section = ""
        if not rag_dropout and parent_alpha:
            try:
                from core.qa_rag_tool import format_qa_for_prompt
                qa_prompt_section = format_qa_for_prompt(verdict.get("qa_prescriptions", [])[:2])
            except Exception:
                qa_prompt_section = ""

        prompt_parts = [
            f"【量化变体生成使命】基于核心 '{core_expr}' 生成 {self.parallelism} 条群体变体。\n",
            f"轮次: Step #{step} | 区域: {self.region} | 股票池: {self.universe} | 延迟: Delay {self.delay} | 类别: {self.category}\n",
            f"假说内涵: {seed_mech}\n\n",
            f"【核心字段全量物理画像 (请基于以下商业实质与分布属性推演 DGP)】:\n"
        ]
        for cm in core_fields_meta:
            prompt_parts.append(
                f"- {cm['name']} ({cm.get('type', 'MATRIX')}): 业务释义=\"{cm.get('description', '无')}\" | "
                f"更新频率={cm.get('update_frequency', 'daily')} | 覆盖率={cm.get('coverage', 1.0)} | "
                f"定义域={cm.get('domain', 'unbounded')} | 偏态={cm.get('skewness', 'medium')} | "
                f"稀疏零值={cm.get('is_sparse', False)}\n"
            )
        prompt_parts.append(field_rule_str)

        if pairing_note:
            prompt_parts.append(f"\n{pairing_note}\n")
        if frequency_guidance:
            prompt_parts.append(f"\n{frequency_guidance}\n")

        if alt_candidates_list:
            prompt_parts.append(f"同源备选特征参考 (最多增选1个): {json.dumps(alt_candidates_list, ensure_ascii=False)}\n")

        # 核心指令注入：病灶法医确诊与处方 + 铁律硬指令 (Bug 1 关键修复)
        prompt_parts.append(f"\n{stage_guidance}\n")
        prompt_parts.append(f"\n{ironlaw_directive}\n")

        # 反模式防坑双轨记忆注入
        failed_digests = getattr(self, "failed_hypotheses_digest", [])
        if failed_digests:
            prompt_parts.append("\n【前车之鉴·被证伪机制防坑警示 (Anti-Pattern)】:\n")
            for fh in failed_digests[-3:]:
                prompt_parts.append(f"- ❌ {fh}\n")

        if parent_alpha:
            prompt_parts.append(f"{golden_profile_str}\n")
            if qa_prompt_section:
                prompt_parts.append(f"【因果问答启发】:\n{qa_prompt_section}\n")

        if top5:
            prompt_parts.append("【高分拓扑标杆 (Top 5)】:\n")
            for t in top5[:5]:
                expr_str = t.get("expression") or t.get("code") or ""
                sh_str = f"Sharpe={t.get('sharpe', 0.0):.2f}" if "sharpe" in t else ""
                prompt_parts.append(f"- {expr_str} ({sh_str})\n")

        if random20:
            prompt_parts.append("【破坏性灵感采样 (Random 20)】:\n")
            for r in random20[:15]:
                expr_str = r.get("expression") if isinstance(r, dict) else str(r)
                prompt_parts.append(f"- {expr_str}\n")

        if pyramid_kb:
            prompt_parts.append(f"【金字塔经验参考】:\n{pyramid_kb}\n")
        if inspiration:
            prompt_parts.append(f"【跨界启发】:\n{inspiration}\n")

        # 提取历史已测表达式集合，避免跨轮次重复生成被 AST Sandbox 拦截
        tested_exprs = set()
        if hasattr(self, "corrector") and self.corrector:
            try:
                conn = self.corrector._get_connection()
                c = conn.cursor()
                c.execute("SELECT expression FROM alpha_fingerprints WHERE region=? AND universe=? AND delay=?", (self.region, self.universe, self.delay))
                for r in c.fetchall():
                    if r[0]:
                        tested_exprs.add(r[0].strip())
                conn.close()
            except Exception:
                pass

        if tested_exprs and step >= 2:
            sampled_tested = list(tested_exprs)[:50]
            tested_str = "\n".join(f"- {e}" for e in sampled_tested)
            prompt_parts.append(
                f"\n🚫 【严禁重复的历史已测表达式黑名单 (Duplicate Forbidden)】:\n"
                f"以下表达式在历史轮次中已全部测过，除 Slot 1 对照槽允许保留母本外，其余卡槽绝对严禁重复生成下列公式！必须进行结构性或字段级创新：\n"
                f"{tested_str}\n"
            )

        if surgery_mode:
            format_spec = (
                f"\n【输出格式硬契约 (老兵精修模式)】\n"
                f"必须返回严格的 JSON 数组，共 {self.parallelism} 个变体对象。\n"
                f"⚠️ 【必须严格遵守的 4 大门禁硬契约，不合规直接整批打回】:\n"
                f"1. 严格键序: 必须先写 \"slot\" 和 \"optimize_reason\"，再写 \"expression\"！\n"
                f"2. 假设充分性: 每个对象的 \"optimize_reason\" 必须不少于 25 字，且必须显式包含至少一个可验收的度量指标词 (如 'Sharpe', 'Margin', 'Turnover', 'ProdCorr', 'Cluster')！\n"
                f"3. 控制槽基准: Slot 1 必须作为对照控制槽，逐字复制母本表达式 '{_parent_expr}'！\n"
                f"4. 1+9+10 分仓保护: Slot 2~10 (9槽) 必须锚定母本主锚字段 ({used_field_names}) 针对法医线索做单变量微创；Slot 11~{self.parallelism} (10槽) 彻底解除母本骨架限制，结合 DGP 与同源冷字段重构全新数学拓扑；严禁超过 2 个槽位做纯数字窗口微调！\n"
                f"对象结构示例: {{\"slot\": 1, \"optimize_reason\": \"保留母本核心骨架作为对照控制槽，严格比对基准 Sharpe 和 Margin 表现\", \"expression\": \"{_parent_expr}\", \"neutralization\": \"SUBINDUSTRY\", \"type\": \"exploit\"}}"
            )
        else:
            format_spec = (
                f"\n【输出格式硬契约 (假说开拓模式)】\n"
                f"必须返回严格的 JSON 数组，共 {self.parallelism} 个变体对象。\n"
                f"⚠️ 【必须严格遵守的 3 大门禁硬契约，不合规直接整批打回】:\n"
                f"1. 严格键序: 必须先写 \"slot\" 和 \"optimize_reason\"，再写 \"expression\"！\n"
                f"2. 假设充分性: 每个对象的 \"optimize_reason\" 必须不少于 25 字，且必须显式包含至少一个可验收的度量指标词 (如 'Sharpe', 'Margin', 'Turnover', 'ProdCorr')！\n"
                f"3. 拓扑多样性: 至少 40% 槽位外层不使用 group_rank (使用 group_neutralize/group_zscore)，并按 (N, 2N) 双窗口成对探针设计！\n"
                f"对象结构示例: {{\"slot\": 1, \"optimize_reason\": \"基于时序动量假说平滑日频噪声，预期提升夏普 Sharpe 并压制日间换手 Turnover\", \"expression\": \"FastExpr公式\", \"neutralization\": \"SUBINDUSTRY\", \"type\": \"explore\"}}"
            )
        prompt_parts.append(format_spec)
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
            "task_tag": f"{seed['id']}_s{step}",
            "pyramid_kb": pyramid_kb,
            "inspiration": inspiration
        }

        variants = session.send_message_sync(prompt, json_mode=True, context=context)
        if not (isinstance(variants, list) and len(variants) > 0):
            raise RuntimeError(
                "❌ 【严禁死模板】大模型未返回有效变体，系统已严禁回退至死模板！"
                "请检查智能体连接或切换为有效后端 (内置 SubAgent / LLM API)！"
            )

        # ---------------- Pre-Flight 批内自闭环校验与局部重写 (最多重试 2 次，杜绝 Python 替考与未捕获崩溃) ----------------
        max_local_retries = 2
        for retry_idx in range(max_local_retries + 1):
            slot_errors = []
            seen_in_batch = set()
            _p_clean = self.corrector.correct_expression(_parent_expr) if (hasattr(self, "corrector") and self.corrector and _parent_expr) else (_parent_expr.strip() if _parent_expr else "")

            for idx, v in enumerate(variants):
                if not isinstance(v, dict):
                    continue
                slot_no = int(v.get("slot", idx + 1))
                raw_e = v.get("expression", "").strip()
                corr_e = self.corrector.correct_expression(raw_e) if (hasattr(self, "corrector") and self.corrector) else raw_e
                v["expression"] = corr_e

                # (a) 校验 AST 语法与量纲守恒
                audit_known_fields = dict(fields_dict)
                for cf in used_field_names:
                    if cf not in audit_known_fields:
                        audit_known_fields[cf] = {"type": "MATRIX", "coverage": 1.0, "description": "母本核心特征"}
                ast_audit = DimensionAuditor.audit_expression(
                    corr_e, audit_known_fields, category=self.category,
                    max_operators=self.max_ast_operators, step=(2 if surgery_mode else step)
                )
                if not ast_audit["is_valid"]:
                    slot_errors.append(f"Slot {slot_no} AST/量纲违规: {'; '.join(ast_audit['issues'])}")
                    continue

                # (b) 校验历史库重复与批内重复 (豁免 Slot 1 控制槽)
                is_ctrl = (slot_no == 1 and _p_clean and corr_e == _p_clean)
                if not is_ctrl:
                    if (tested_exprs and (corr_e in tested_exprs or raw_e in tested_exprs)) or corr_e in seen_in_batch:
                        slot_errors.append(f"Slot {slot_no} 表达式 '{corr_e}' 与历史已测或本批其他槽位重复")
                        continue
                seen_in_batch.add(corr_e)

            if not slot_errors or retry_idx == max_local_retries:
                if slot_errors:
                    print(f"⚠️ [Pre-Flight 达到最大重试次数] 仍有 {len(slot_errors)} 个槽位存疑，交付门禁系统兜底。")
                break

            # 构造局部返工 Prompt，仅要求重写违规槽位并按 slot 编号热合并
            print(f"⚠️ [Pre-Flight 局部返工 #{retry_idx+1}] 检测到 {len(slot_errors)} 个槽位不合规，打回大模型重思...")
            retry_prompt = (
                prompt + "\n\n🚨 【Pre-Flight 本地编译器驳回通知】\n"
                "你刚才生成的变体中，以下槽位未能通过物理门禁审查：\n"
                + "\n".join(f"- {err}" for err in slot_errors)
                + "\n请从字段底层物理意义出发，重新构思上述违规槽位，并返回完整的 20 槽 JSON 数组（或仅返回修正后的违规槽位 JSON 数组）！"
            )
            try:
                patch_res = session.send_message_sync(retry_prompt, json_mode=True, context=context)
                if isinstance(patch_res, list) and len(patch_res) > 0:
                    by_slot = {int(item.get("slot", i + 1)): item for i, item in enumerate(variants) if isinstance(item, dict)}
                    for new_item in patch_res:
                        if isinstance(new_item, dict) and "slot" in new_item and "expression" in new_item:
                            try:
                                s_idx = int(new_item["slot"])
                                by_slot[s_idx] = new_item
                            except (ValueError, TypeError):
                                pass
                    variants = [by_slot[k] for k in sorted(by_slot.keys())]
            except Exception as e:
                print(f"⚠️ [Pre-Flight 重试捕获异常]: {e}，跳过本次重试。")
                break

        # ---------------- 铁律 B 物理核验: 非 rank 外壳占比 + 成对双窗口矩阵 ----------------
        mock_env = (self.client.mock_only or self.mock_only or os.environ.get("AEGIS_MOCK_MODE") == "1")
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

        warning_cnt = alpha.get("warning_count")
        fail_cnt = alpha.get("fail_count")
        if warning_cnt is None or fail_cnt is None:
            chk_parsed = Gatekeeper.parse_brain_checks(alpha)
            if warning_cnt is None:
                warning_cnt = len(chk_parsed.get("warnings", []))
            if fail_cnt is None:
                fail_cnt = chk_parsed.get("fail_count", 0)
        zero_warnings = (int(warning_cnt or 0) == 0 and int(fail_cnt or 0) == 0)

        op_count = self._operator_count_of(alpha)
        is_near = Gatekeeper.is_near_miss_champion(alpha, self.region)
        is_quasi_or_perfect = (
            bool(getattr(self, "targeted_alpha_id", None))
            or getattr(self, "is_quasi_champion_optimization", False)
        )
        max_ops = 10 if is_quasi_or_perfect else getattr(self, "max_champion_operators", 6)
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

        # 仅当命中严重共线 (>= 0.70) 或算子复杂度超标时硬性否决
        hard_rejected = any(">= 0.70" in r or "算子数" in r for r in reasons)
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
    # 单批次定向回测执行器 (Direct Single Batch Runner)
    # -------------------------------------------------------------
    async def run_single_batch(self, batch_file_path: str) -> dict:
        """
        单批次变体极速仿真执行器 (Single Batch Direct Runner)
        允许宿主 Agent 或外部脚本直接传入 20 槽变体 JSON，执行 AST 门禁、静默并发回测与 ALL PASS 准入核验
        """
        print("\n" + "=" * 65)
        print("⚡ 【AEGIS GrandMaster 单批次定向回测执行器启动】")
        print(f"📍 批次文件: {batch_file_path}")
        print(f"📍 回测环境: {self.region} / {self.universe} / Delay {self.delay} / {self.category}")
        print("=" * 65)

        if not os.path.exists(batch_file_path):
            raise FileNotFoundError(f"未找到指定的批次文件: {batch_file_path}")

        with open(batch_file_path, "r", encoding="utf-8") as bf:
            batch_data = json.load(bf)

        variants = batch_data.get("items") if isinstance(batch_data, dict) else batch_data
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"批次文件 {batch_file_path} 中未包含合法的变体列表 (list)")

        # 执行静默并发回测 (内置 Gate 2 AST 维度审计与 Gate 3 沙箱排重门禁)
        campaign_ledger = os.path.join(self.campaign_dir, "exploration_ledger.json")
        from core.sim_runner import SimBatchRunner
        if self.mock_only:
            os.environ["AEGIS_MOCK_MODE"] = "1"
        sim_res = await SimBatchRunner.run_batch_silently(
            batch_file_path=batch_file_path,
            region=self.region,
            universe=self.universe,
            delay=self.delay,
            category=self.category,
            neutralization=None,
            ledger_path=campaign_ledger
        )

        step1 = sim_res.get("step1", {})
        qualified = step1.get("qualified_seeds", [])
        final_passed = sim_res.get("final_passed", [])

        print("\n" + "-" * 65)
        print(f"📊 回测完成！总测试: {len(variants)} 条 | 达标 (Sharpe >= 1.2): {len(qualified)} 条 | 生产级 (ALL PASS): {len(final_passed)} 条")
        for idx, q in enumerate(qualified, 1):
            is_pass = "🏆 [ALL PASS]" if q in final_passed else "📈 [QUALIFIED]"
            print(f"  #{idx} {is_pass} Sharpe={q.get('sharpe', 0.0):.2f} | Margin={q.get('margin_bps', 0.0):.1f}bps | Turnover={q.get('turnover', 0.0)*100:.1f}% | ProdCorr={q.get('prod_corr', 'N/A')} | Expr: {q.get('expression')}")

        if final_passed:
            champions_file = os.path.join(self.campaign_dir, "campaign_champions.json")
            champions_list = []
            if os.path.exists(champions_file):
                try:
                    with open(champions_file, "r", encoding="utf-8") as cf:
                        champions_list = json.load(cf)
                except Exception:
                    champions_list = []
            for fp in final_passed:
                if not any(c.get("expression") == fp.get("expression") for c in champions_list):
                    champions_list.append(fp)
            with open(champions_file, "w", encoding="utf-8") as cf:
                json.dump(champions_list, cf, ensure_ascii=False, indent=2)
            print(f"\n🌟 生产级冠军已追加至待审库: {champions_file}")

        return sim_res

    # -------------------------------------------------------------
    # 主状态机循环 (Pure Python State Machine Loop)
    # -------------------------------------------------------------
    async def run_pipeline_loop(self, max_seeds_to_explore: int = 50, max_steps_per_seed: int = 10):
        print("\n" + "=" * 65)
        print("🚀 【AEGIS GrandMaster 纯 Python 状态机总控启动】")
        print(f"📍 目标: {self.region} / {self.universe} / Delay {self.delay} / {self.category} / {self.dataset_id}")
        print(f"⚙️ 并发容量: {self.parallelism} 条 | 模型: {self.model}")
        print("=" * 65)

        # 0. 启动时执行实战经验库指数半衰期衰减 (Spec 2.6)
        try:
            from core.qa_rag_tool import apply_experience_decay
            decayed_cnt = apply_experience_decay(half_life_days=14.0)
            if decayed_cnt > 0:
                print(f"📚 [LanceDB RAG] 成功执行实战经验半衰期衰减 (14天)，活跃经验更新: {decayed_cnt} 条")
        except Exception as rag_err:
            print(f"⚠️ [LanceDB RAG] 经验半衰期衰减未触发: {rag_err}")

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

            # 跨种子循环重置当前种子的算子预算，杜绝前一个种子的准冠军/加时赛状态泄漏到下一个全新种子
            self.is_quasi_champion_optimization = bool(self.targeted_alpha_id)
            if getattr(self, "initial_max_operator_count", None) is not None:
                self.max_champion_operators = int(self.initial_max_operator_count)
            else:
                self.max_champion_operators = 10 if self.is_quasi_champion_optimization else 6
            self.max_ast_operators = 10 if (self.is_quasi_champion_optimization or (getattr(self, "initial_max_operator_count", None) and self.initial_max_operator_count > 8)) else 8

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
                # 依据 Spec 2.5 Master Good Flag: 优先选取满足收益单调性与时效性的优质母本 (good_flag == True)
                def _parent_sort_key(alpha_dict):
                    try:
                        mgf = Gatekeeper.compute_master_good_flag(alpha_dict)
                        is_good = 1 if mgf.get("good_flag", False) else 0
                    except Exception:
                        is_good = 0
                    champ_score = self.compute_champion_score(alpha_dict)
                    sharpe = abs(alpha_dict.get("sharpe", 0.0))
                    return (is_good, champ_score, sharpe)

                seed_best_parent = (
                    sorted(seed_good_alphas, key=_parent_sort_key, reverse=True)[0]
                    if seed_good_alphas else (
                        sorted(seed_qualified_alphas, key=_parent_sort_key, reverse=True)[0]
                        if seed_qualified_alphas else None
                    )
                )

                # 动态升阶准冠军与加时赛算子预算: 挖掘阶段严格 <=6，准冠军/加时赛动态放宽至 <=10
                is_near_parent = bool(seed_best_parent and Gatekeeper.is_near_miss_champion(seed_best_parent, self.region))
                if overtime_granted or is_near_parent or bool(getattr(self, "targeted_alpha_id", None)):
                    self.is_quasi_champion_optimization = True
                    self.max_champion_operators = 10
                    self.max_ast_operators = 10

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
                            "parent_expression": seed_best_parent.get("expression") if seed_best_parent else None,
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
                        if os.path.exists(batch_path):
                            try:
                                os.remove(batch_path)
                            except Exception:
                                pass
                        raise e

                    with open(sim_cache_path, 'w', encoding='utf-8') as sf:
                        json.dump(sim_res, sf, ensure_ascii=False, indent=2)

                # ---------------------------------------------------------
                # 阶梯漏斗早停核心 (Funnel Pruning - 0.05秒极速断舍离)
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
                    # 反馈 LanceDB 经验库: 该处方未能孵化成功，施加 -10 惩罚 (Spec 2.6)
                    if getattr(self, "last_step_qa_prescriptions", None):
                        try:
                            from core.qa_rag_tool import feedback_experience_outcome
                            for q in self.last_step_qa_prescriptions:
                                qid = q.get("id")
                                if qid:
                                    feedback_experience_outcome(qid, success=False)
                        except Exception:
                            pass

                    # 记录被证伪的假说与特征组合，让反模式双轨记忆真正通电生效
                    self.failed_hypotheses_digest.append(
                        f"[{seed_id} Step 1 证伪] 原型 {core_expr} "
                        f"最高 |Sharpe|={step1_status.get('max_abs_sharpe', 0.0):.2f} < 1.2，"
                        f"该字段组合与周期未能产生有效边际利润"
                    )
                    self.save_campaign_memory()

                    # Step 1 冷酷熔断：Python 直接置 times = 1，秒级切换下一个主信号，严禁调用 LLM 写总结！
                    seed["times"] = seed.get("times", 0) + 1
                    self.save_signals_pool(pool)
                    print(f"⚡ [0 Token 极速早停] {seed_id} Step 1 未达到高起点门槛 (|Sharpe| >= 1.2 且 Margin >= 5.0 bps)。")
                    print(f"⏩ 立即置 times=1，0.05 秒内无缝切入下一个主信号，0 Token 浪费，拒绝无效内耗！")
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
                        spike_msg = (
                            f"[{seed_id} 尖峰过拟合] 公式 {q.get('expression', '')[:70]} "
                            f"在 N/2N 双窗口测试中表现急剧崩塌，判定为单点参数过拟合假信号"
                        )
                        if spike_msg not in self.failed_hypotheses_digest:
                            self.failed_hypotheses_digest.append(spike_msg)
                            self.save_campaign_memory()
                        continue
                    if abs(q.get("sharpe", 0.0)) >= 1.2:
                        seed_good_alphas.append(q)
                        self.good_alphas.append(q)

                # 🏛️ 准生产突破池 (Near-Miss Hall of Fame) 物理入库与基因强制沉淀
                for q in qualified:
                    if Gatekeeper.is_near_miss_champion(q, self.region):
                        q["status"] = "NEAR_CHAMPION"
                        q["near_champion"] = True
                        self.is_quasi_champion_optimization = True
                        self.max_champion_operators = 10
                        self.max_ast_operators = 10
                        if not hasattr(self, "near_miss_hall_of_fame"):
                            self.near_miss_hall_of_fame = []
                        if not any(nm.get("expression") == q.get("expression") for nm in self.near_miss_hall_of_fame):
                            self.near_miss_hall_of_fame.append(q)
                            print(f"\n🏛️ 【入选准生产突破池 (Near-Miss Hall of Fame)】{q['expression'][:55]}...")
                            print(f"   Sharpe={q['sharpe']:.2f} (离1.58仅差{1.58-q['sharpe']:.2f}) | ProdCorr={q.get('prod_corr', 0.0):.4f} | Margin={q['margin_bps']:.1f}bps")
                            print(f"   🚀 【算子预算动态升阶】捕获准冠军候选，算子预算自动升阶为 max_ops=10 (AST<=10)！")
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
                                if distill_res and str(distill_res).strip():
                                    abstract_rule = str(distill_res).strip()
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

                # 终极生产准入门禁核对 (ALL PASS 铁律与第一时间汇报研究员)
                final_passed = sim_res.get("final_passed", [])
                if final_passed:
                    # 反馈 LanceDB 经验库: 成功孵化生产级 Alpha，施加 +15 奖励并重置活跃时间 (Spec 2.6)
                    if getattr(self, "last_step_qa_prescriptions", None):
                        try:
                            from core.qa_rag_tool import feedback_experience_outcome
                            for q in self.last_step_qa_prescriptions:
                                qid = q.get("id")
                                if qid:
                                    feedback_experience_outcome(qid, success=True)
                        except Exception:
                            pass

                    print("\n" + "=" * 70)
                    print(f"🚨 【生产级 ALL PASS Alpha 诞生 - 立即汇报研究员！】")
                    print(f"📍 主信号: {seed_id} | 轮次: Step #{step} | 共诞生 {len(final_passed)} 条全维度达标因子")
                    print("-" * 70)
                    for i, f_alpha in enumerate(final_passed):
                        expr_str = f_alpha.get('expression', '')
                        alpha_id_str = f_alpha.get('id') or f_alpha.get('alpha_id') or 'N/A'
                        sh_val = f_alpha.get('sharpe', 0.0)
                        fit_val = f_alpha.get('fitness', 0.0)
                        m_bps = f_alpha.get('margin_bps', 0.0)
                        turn_pct = f_alpha.get('turnover', 0.0) * 100.0 if f_alpha.get('turnover', 0.0) <= 1.0 else f_alpha.get('turnover', 0.0)
                        pc_val = f_alpha.get('prod_corr', f_alpha.get('pcorr', 'N/A'))
                        sc_val = f_alpha.get('sc', 'N/A')

                        golden_res = SimBatchRunner.extract_golden_alpha_result(f_alpha)
                        yearly_str = " | ".join(f"{y}:{s}" for y, s in golden_res.get("yearly_sharpe", []))
                        monthly_str = " | ".join(f"{m}:{s}" for m, s in golden_res.get("last_24_monthly_sharpe", [])[-12:])

                        print(f"🏆 [生产级达标 Alpha #{i+1}] ID: {alpha_id_str}")
                        print(f"   表达式 (Code): {expr_str}")
                        print(f"   核心指标: Sharpe={sh_val:.2f} | Fitness={fit_val:.2f} | Margin={m_bps:.1f}bps | Turnover={turn_pct:.2f}%")
                        print(f"   相关性: ProdCorr={pc_val} (< 0.65) | SelfCorr={sc_val} (<= 0.60)")
                        print(f"   10年逐年夏普: {yearly_str or '见体检档案'}")
                        print(f"   最近12月夏普: {monthly_str or '见体检档案'}")
                        print(f"   平台审查: 0 FAIL + 0 WARNING (ALL PASS)")
                        print(f"   经济学机制: {seed.get('economic_mechanism', '因果假说驱动')}")
                        print(f"   ⚠️ 【绝对红线遵从】严禁系统私自提交平台池子！已安全归档至 campaign_champions.json，待研究员肉眼复核确认！")
                        print("-" * 70)

                        # 保存至待审冠军库 campaign_champions.json
                        champions_file = os.path.join(self.campaign_dir, "campaign_champions.json")
                        champions_list = []
                        if os.path.exists(champions_file):
                            try:
                                with open(champions_file, 'r', encoding='utf-8') as cf:
                                    champions_list = json.load(cf)
                            except Exception:
                                champions_list = []
                        if not any(c.get("expression") == expr_str for c in champions_list):
                            champions_list.append(f_alpha)
                            with open(champions_file, 'w', encoding='utf-8') as cf:
                                json.dump(champions_list, cf, ensure_ascii=False, indent=2)

                        # 触发经验提炼: 纯算子、去字段化抽象沉淀 (Plan 1 隔离会话)
                        distill_session = self.client.create_session(role="aegis-knowledge-distiller", model=self.model)
                        distill_prompt = (
                            f"达标 Alpha: {f_alpha['expression']} (Sharpe={f_alpha['sharpe']:.2f}, Fitness={f_alpha['fitness']:.2f})。\n"
                            f"请提炼纯算子抽象经验。严格遵循原则：只总结纯算子结构规律与风控拓扑，严禁出现任何具体数据字段名！"
                        )
                        try:
                            distill_res = await distill_session.send_message(
                                distill_prompt,
                                json_mode=False,
                                context={"alpha": f_alpha, "task_tag": f"{seed_id}_s{step}_distill_{i+1}"}
                            )
                            if distill_res and str(distill_res).strip():
                                abstract_rule = str(distill_res).strip()
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
                        except Exception as _de:
                            print(f"⚠️ [经验提炼] 达标 Alpha 经验沉淀异常: {_de}")

                    self.save_campaign_memory()
                    print("=" * 70 + "\n")

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
                        func2_sim_res = {}
                        if isinstance(refined_variants, list) and len(refined_variants) > 0:
                            SwarmAuditor.enforce(
                                refined_variants,
                                step=5,
                                parallelism=self.parallelism,
                                strict=False
                            )

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
                        if func2_sim_res:
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
                                        self.is_quasi_champion_optimization = True
                                        self.max_champion_operators = 10
                                        self.max_ast_operators = 10
                                        if not hasattr(self, "near_miss_hall_of_fame"):
                                            self.near_miss_hall_of_fame = []
                                        if not any(nm.get("expression") == q.get("expression") for nm in self.near_miss_hall_of_fame):
                                            self.near_miss_hall_of_fame.append(q)
                                            print(f"\n🏛️ 【func2 入选准生产突破池 (Near-Miss Hall of Fame)】{q['expression'][:55]}...")
                                            print(f"   Sharpe={q['sharpe']:.2f} (离1.58仅差{1.58-q['sharpe']:.2f}) | ProdCorr={q.get('prod_corr', 0.0):.4f} | Margin={q['margin_bps']:.1f}bps")
                                            print(f"   🚀 【算子预算动态升阶】捕获准冠军候选，算子预算自动升阶为 max_ops=10 (AST<=10)！")
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
                                                    if distill_res and str(distill_res).strip():
                                                        abstract_rule = str(distill_res).strip()
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
                                    if distill_res and str(distill_res).strip():
                                        func2_distill_done_flag = os.path.join(self.campaign_dir, f".distilled_{seed_id}_s{step}_func2_{j+1}.flag")
                                        if not os.path.exists(func2_distill_done_flag):
                                            RAGMemoryEngine.append_pure_operator_experience(
                                                region=self.region,
                                                delay=self.delay,
                                                category=self.category,
                                                abstract_insight=str(distill_res).strip(),
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
    parser.add_argument("--max-seeds", type=int, default=10, help="最多探索主信号数量")
    parser.add_argument("--max-steps", type=int, default=10, help="单主信号最大演进轮次")
    parser.add_argument("--max-operator-count", type=int, default=None, help="最大算子数约束 (默认研究挖掘阶段 <=6, 准冠军优化阶段 <=10)")
    parser.add_argument("--run-batch", default=None, help="直接执行外部给定的批次变体 JSON 文件并进行静默回测与门禁核验")
    
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

    if getattr(args, "run_batch", None):
        asyncio.run(controller.run_single_batch(args.run_batch))
        sys.exit(0)

    if args.generate_seeds or getattr(args, "seeds_only", False):
        controller.synthesize_stage0_seeds(count=20)
        if getattr(args, "seeds_only", False):
            print("✅ 阶段 0 种子生成完毕 (--seeds-only)，平稳停机。")
            sys.exit(0)

    asyncio.run(controller.run_pipeline_loop(
        max_seeds_to_explore=args.max_seeds,
        max_steps_per_seed=args.max_steps
    ))
