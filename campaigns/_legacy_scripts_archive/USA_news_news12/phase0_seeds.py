# -*- coding: utf-8 -*-
"""
Phase 0 driver: news12 (USA / TOP1000 / delay 1) cold-start seed synthesis.
8-question methodology -> 8 orthogonal main signals -> Tech Auditor audit -> total_signals.json
Zero backtest quota consumed.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.orchestrator import AEGISOrchestrator
from quant_framework.core.dimension_rules import DimensionAuditor

CAMPAIGN = os.path.join("quant_framework", "campaigns", "USA_news_news12")

# ---- 8-question main signals (<=2 distinct dataset fields, basic ops, <=6 operators) ----
SEEDS = [
    {
        "id": "SEED_Q1_INVARIANCE",
        "question_type": "Q1_Invariance",
        "fields_used": ["news_ton_last"],
        "economic_mechanism": (
            "不变性：新闻事件时刻的股价相对自身过去120日事件时刻均价的拉伸度。事件天然聚簇，"
            "当本次事件价位显著高于该股自身事件价位稳态时，说明买盘由关注度/流动性脉冲而非新增信息驱动，"
            "此类拉伸无法被基本面解释，将在随后数日内向自身稳态回归。reverse 使高拉伸获得低信号（做空），"
            "捕捉事件驱动的价格均值回归。"
        ),
        "expression": "reverse(divide(news_ton_last, ts_mean(news_ton_last, 120)))",
    },
    {
        "id": "SEED_Q2_DYNAMICS",
        "question_type": "Q2_Dynamics",
        "fields_used": ["news_pct_120min", "news_pct_30min"],
        "economic_mechanism": (
            "动态变化：当日120分钟反应减去前30分钟反应，度量消息公布后慢扩散部分的漂移量。"
            "若市场对新闻存在初期反应不足（underreaction），信息在当日剩余时间持续被定价，"
            "该漂移具有惯性并将延续至次日，构成经典公告后漂移（PEAD）的事件版。"
            "漂移为正做多、为负做空，直接捕捉信息扩散的时间结构。"
        ),
        "expression": "subtract(news_pct_120min, news_pct_30min)",
    },
    {
        "id": "SEED_Q3_ANOMALY",
        "question_type": "Q3_Anomaly",
        "fields_used": ["news_max_up_ret"],
        "economic_mechanism": (
            "异常冲击：新闻后最大上行幅度相对自身60日历史的标准分（z-score）。当冲高幅度超过2倍标准差时，"
            "属于流动性冲击导致的过度反应——知情卖压被暂时吸收、做市商库存被动放大，"
            "此类极端冲高在次日出现部分回吐。reverse 使极端正分位获得做空信号，"
            "利用事件日的反应极端性预测次日均值回归。"
        ),
        "expression": "reverse(divide(subtract(news_max_up_ret, ts_mean(news_max_up_ret, 60)), ts_std_dev(news_max_up_ret, 60)))",
    },
    {
        "id": "SEED_Q4_INTERACTION",
        "question_type": "Q4_Interaction",
        "fields_used": ["news_pct_30min", "news_vol_stddev"],
        "economic_mechanism": (
            "跨字段协同：30分钟价格反应乘以当日成交流量的30日标准分。单独的价格反应混有噪声，"
            "乘以成交量确认项后，只有被异常放大的成交量背书的反应用于信号——高换手背书的大幅反应代表"
            "知情交易者的真实信息注入，其价格发现不完整，次日延续漂移；无量能背书的反应是流动性噪声，"
            "乘积结构天然实现对信息性反应与噪声反应的分离。"
        ),
        "expression": "multiply(news_pct_30min, news_vol_stddev)",
    },
    {
        "id": "SEED_Q5_STRUCTURE",
        "question_type": "Q5_Structure",
        "fields_used": ["news_max_up_amt", "news_max_dn_amt"],
        "economic_mechanism": (
            "结构占比：新闻后上行冲高金额占上行/下行双向冲高总金额的比例。双向冲测总量度量事件的信息总量，"
            "而其内部结构披露信息的不对称方向——当绝大部分冲测发生在买方一侧，说明利好信息正被主动性买单"
            "持续吸收，卖盘深度不足，次日起跳空延续；反之空头压强占比高则做空。该比值是无量纲的"
            "事件信息不对称度指标。"
        ),
        "expression": "divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))",
    },
    {
        "id": "SEED_Q6_ACCUMULATION",
        "question_type": "Q6_Accumulation",
        "fields_used": ["news_indx_perf"],
        "economic_mechanism": (
            "累积记忆：事件日相对标普500超额收益的20日线性衰减加权和。新闻事件对个股的影响并非一日出清，"
            "而是以指数衰减形成持续数周的重定价记忆；线性衰减加权让近期事件权重更高、远期事件平滑淡出，"
            "捕捉累积性特异事件动量。超额收益口径已剔除市场基准，避免把beta误认为事件alpha。"
        ),
        "expression": "ts_decay_linear(news_indx_perf, 20)",
    },
    {
        "id": "SEED_Q7_RELATIVE",
        "question_type": "Q7_Relative",
        "fields_used": ["news_pct_30min"],
        "economic_mechanism": (
            "截面相对性：30分钟反应强度在子行业内的分组排序。同一子行业的股票面对相似类型的新闻时，"
            "反应强度差异披露了信息扩散的先后次序——行业内反应最强者往往是信息传导的源头，"
            "其同业跟随者存在滞后定价空间（lead-lag）。组内排序剔除行业层面对新闻反应强度的系统性差异"
            "（如科技股天然高波动），保留纯粹的同业相对强弱。"
        ),
        "expression": "group_rank(news_pct_30min, subindustry)",
    },
    {
        "id": "SEED_Q8_ESSENCE",
        "question_type": "Q8_Essence",
        "fields_used": ["news_eps_actual"],
        "economic_mechanism": (
            "本质预期差：新闻披露的实际EPS相对自身250日（约四个季度）趋势基准的比值。市场只为超出预期的"
            "事实定价，而本数据集无一致预期字段，故以自身盈利趋势外推作为随机游走基准——实际EPS突破自身"
            "年度趋势即构成基本面意外度，触发盈余公告后漂移；反之低于趋势则做空。"
            "该比值把绝对盈利水平转化为可跨股票比较的意外度。"
        ),
        "expression": "divide(news_eps_actual, ts_mean(news_eps_actual, 250))",
    },
]


async def main():
    # load field dictionary (867 fields) for Tech Auditor fact-checking
    with open(os.path.join(CAMPAIGN, "news12_fields_raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [f["id"] for f in fields]
    field_type = {f["id"]: f.get("type") for f in fields}
    print(f"[Phase 0] 字段字典装载: {len(known_fields)} fields")

    orch = AEGISOrchestrator(region="USA", dataset_id="news12", category="news",
                             universe="TOP1000", delay=1)

    # pre-audit each seed locally (field existence + type + PV isolation + syntax)
    print("\n[Tech Auditor 预审] 逐条事实核查...")
    ok = True
    for s in SEEDS:
        expr = s["expression"]
        toks = set(__import__("re").findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr))
        groups = {"market", "sector", "industry", "subindustry"}
        used = [t for t in toks if t in known_fields]
        missing = [t for t in toks if t not in known_fields and t not in groups
                   and t not in {"reverse", "divide", "ts_mean", "subtract", "ts_std_dev",
                                 "multiply", "add", "ts_decay_linear", "group_rank"}]
        types = {field_type[u] for u in used}
        audit = DimensionAuditor.audit_expression(expr, known_fields, category="news")
        status = "PASS" if (audit["is_valid"] and not missing) else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  [{status}] {s['id']}: fields={used} types={types} ops={audit['operator_count']} "
              f"missing={missing} issues={audit['issues']}")

    if not ok:
        print("\n[熔断] 存在未通过预审的种子，终止。")
        sys.exit(1)

    # official Phase 0 pool init (AST correction + DimensionAuditor + pool write)
    accepted = orch.phase0_init_seed_pool(SEEDS, known_fields)
    print(f"\n[Phase 0] 入库 {len(accepted)}/8 条主信号 -> {orch.signals_pool_file}")


asyncio.run(main())
