"""
run_gate1_batch5.py
Gate 1: AEGIS 多 Agent 研发攻坚多重回测 (批次 5)
数据集: USA / news12 / delay 1 / TOP1000
核心机制革命:
保留母本 mLYNEWjW (Sharpe 1.59, 2Y 2.03, Returns 7.52%) 的完全盈利内核！
诊断并攻克其 114.59% 翻仓与 1.31 bps 贫血病灶：
在 trade_when(cond, alpha, 0) 的阶跃脉冲外部包裹 10~20 日线性平滑衰减，
将突发离散新闻脉冲转换为平缓的三角形渐进衰减退场曲线，
彻底杜绝 1 日断崖式全额清仓，直接实现平滑降换手与成倍抬升 Margin！
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.gatekeeper import Gatekeeper
from quant_framework.core.sim_runner import SimBatchRunner

PRESCRIPTIONS_GATE1_B5 = [
    {
        "slot": 1,
        "seed_id": "GATE1_B5_S1",
        "question_type": "Q1_PULSE_LINEAR_DECAY_10D",
        "name": "母本脉冲 + 10日线性平滑渐进退场",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0), 10)",
        "optimize_reason": "【脉冲清零转平滑退场核心假说】母本 mLYNEWjW 拥有极高的原始预测力 (Sharpe 1.59, 2Y 2.03, Ret 7.52%)，但因 trade_when 结尾设置 0 导致非事件日暴跌清仓，换手率高达 114.6%。本处方在脉冲外侧嵌套 10 日线性衰减 ts_decay_linear：在事件日开仓后，非事件日仓位不再断崖跌至 0，而是每天按 10% 线性匀速递减平滑退出。该结构完美保留了母本高夏普、高收益的完整因果多空分布，同时将单日翻仓摩擦降低数倍，预期将换手率压缩至 30% 以下，并成倍拉升 Margin 与 Fitness。"
    },
    {
        "slot": 2,
        "seed_id": "GATE1_B5_S2",
        "question_type": "Q2_PULSE_LINEAR_DECAY_15D",
        "name": "母本脉冲 + 15日深度线性平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0), 15)",
        "optimize_reason": "【15日渐进线性退场深度降换手】将渐进退场窗口由 10 日进一步拉长至 15 日。新闻过度反应后的均值回归在现实市场中往往需要 2~3 周由套利资金完成闭合。15 日三角形衰减赋予近期事件最高权重，每日仅按 6.7% 极微幅平仓，强力抑制高频买卖冲击，目标将换手率压制在 20% 黄金区间。结合母本 7.5% 的高年化回报，根据 Margin 物理反比公式，Margin 预期直接跳升至 7~10 bps。"
    },
    {
        "slot": 3,
        "seed_id": "GATE1_B5_S3",
        "question_type": "Q3_PULSE_LINEAR_DECAY_20D",
        "name": "母本脉冲 + 20日极限线性平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0), 20)",
        "optimize_reason": "【20日长周期线性退场冲击极限 Margin】针对 USA 市场 10.0 bps 的严苛死线，实施 20 日长周期线性平滑退场。每日调仓幅度仅为持仓的 5%，从物理结构上锁死极端低换手率 (10%~15%)。该处方是对母本原始信号在极限时间加权下的压力测试：若 20 日退场仍能保住 Sharpe 1.4+，则 Margin 必将突破 12 bps，直接达成生产准入！"
    },
    {
        "slot": 4,
        "seed_id": "GATE1_B5_S4",
        "question_type": "Q4_RELATIVE_RET_PULSE_15D",
        "name": "相对收益率脉冲 + 15日平滑退场",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0), 15)",
        "optimize_reason": "【百分比收益率标准化与 15 日平滑联合攻坚】在母本信号中引入除以 news_ton_last，将绝对美元差价转换为无量纲的百分比收益率，消除名义股价尺度的异方差扭曲；并在外层施加 15 日线性平滑退场。高价股与低价股在统一的百分比弹性下进行全市场排序，避免了少数高单价个股的极端扰动，提高收益率的时序平稳性与回撤控制能力。"
    },
    {
        "slot": 5,
        "seed_id": "GATE1_B5_S5",
        "question_type": "Q5_RELATIVE_RET_PULSE_20D",
        "name": "相对收益率脉冲 + 20日深度平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0), 20)",
        "optimize_reason": "【相对收益率 20 日长周期平滑极限形态】将百分比标准化的母本信号进一步推向 20 日长衰减窗口。此举旨在检验名义量纲消除与长期持有机制的协同效应。预期在大幅削减换手率的同时，完全覆盖长周期均值回归收益，直击 Margin >= 10.0 bps 与 Fitness >= 1.00。"
    },
    {
        "slot": 6,
        "seed_id": "GATE1_B5_S6",
        "question_type": "Q6_SUBINDUSTRY_PULSE_15D",
        "name": "子行业排序脉冲 + 15日平滑退场",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(group_rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), subindustry)), 0), 15)",
        "optimize_reason": "【子行业排序与 15 日平滑退场】将母本的全市场 rank 替换为细分子行业 group_rank(..., subindustry)，并在外部施加 15 日线性平滑。在细分赛道内部消除行业系统性 Beta，保留同行业内对新闻过度反应的纯净相对位次；通过 15 日平滑退场避免跳变，探索行业纯化能否在保住母本 Sharpe 的同时带来更高的单笔交易净溢价。"
    },
    {
        "slot": 7,
        "seed_id": "GATE1_B5_S7",
        "question_type": "Q7_SUBINDUSTRY_RELATIVE_PULSE_15D",
        "name": "相对收益 + 子行业排序脉冲 + 15日平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(group_rank(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), subindustry)), 0), 15)",
        "optimize_reason": "【双重纯化：相对收益 + 子行业组排 + 15日衰减】集大成组合：百分比相对收益率消除价格量纲，子行业组排消除行业系统性偏移，外层 15 日线性退场消除翻仓断崖。三维因果协同，全方位封堵母本的换手与滑点漏洞，预期达成全维度生产门禁。"
    },
    {
        "slot": 8,
        "seed_id": "GATE1_B5_S8",
        "question_type": "Q8_INDUSTRY_PULSE_15D",
        "name": "一级行业排序脉冲 + 15日平滑退场",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(group_rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), industry)), 0), 15)",
        "optimize_reason": "【一级行业排序与 15 日平滑对照】对比 subindustry（子行业样本过细可能引发的样本不足问题），本处方选用粒度适中的 industry（一级行业）进行组排，确保每个行业具有足够丰富的横截面股票样本，避免组排退化。配合 15 日平滑退场，测试最佳行业颗粒度与平滑周期的契合点。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_gate1_b5.json")

    payload = {
        "seed_id": "GATE1_CAMPAIGN_BATCH5",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close", "news_ton_last", "high_price_excursion_stddev"
        ],
        "items": PRESCRIPTIONS_GATE1_B5
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Gate 1 Batch 5 配置文件生成完毕: {batch_file}")
    print("🚀 启动 SimBatchRunner 后台静默执行批次 (decay=6, neutralization=INDUSTRY)...")

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_file,
        region="USA",
        universe="TOP1000",
        delay=1,
        category="news",
        neutralization="INDUSTRY",
        decay=6,
        truncation=0.025,
        nan_handling="ON"
    )

    print("\n🏁 Gate 1 Batch 5 回测与门禁终审完成!")
    output_summary = batch_file.replace(".json", "_summary.json")
    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
