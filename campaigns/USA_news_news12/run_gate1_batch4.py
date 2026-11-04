"""
run_gate1_batch4.py
Gate 1: AEGIS 多 Agent 研发攻坚多重回测 (批次 4)
数据集: USA / news12 / delay 1 / TOP1000
核心创新与突破设计:
复刻并强化 Batch 1 S3 的超低换手架构 (Turnover 12.4%, Margin 5.41 bps)!
在保持组内 Z-score 截面多空对称性的同时，利用真实高弹性门控 (>2% 冲测) 过滤噪音，
测试正确因果反转方向与不同阈值剪裁 (2%, 3%, 1.5%)，
全力冲击 Returns 6%~8% 与 Margin >= 10.0 bps，实现全指标合规！
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

PRESCRIPTIONS_GATE1_B4 = [
    {
        "slot": 1,
        "seed_id": "GATE1_B4_S1",
        "question_type": "Q1_SHOOTING_STAR_CORRECT",
        "name": "冲顶回落力竭阴影线 (正向因果)",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.02), subtract(news_max_up_ret, divide(subtract(news_eod_close, news_ton_last), news_ton_last)), -1), 12), subindustry)",
        "optimize_reason": "【纠正回撤剪刀差反转方向】在 Batch 1 S3 中，该架构成功实现了 12.4% 的超低换手与 5.41 bps 的高 Margin。然而前期错误使用了 reverse 算子，导致做多了未回落股票（做空了力竭股票），方向反噬引发夏普偏低。本处方去除 reverse，直接使用 positive 剪刀差：日内冲高逾 2% 且收盘大幅回落者（max_up_ret - net_ret > 0），多头彻底力竭，直接做空回落股票。由于方向修正为正向力竭做空，预期夏普与收益率将大幅修复，同时保持 12% 超低换手与高 Margin。"
    },
    {
        "slot": 2,
        "seed_id": "GATE1_B4_S2",
        "question_type": "Q2_2PCT_POP_DIRECT_REVERSE",
        "name": "2% 盘中大涨高门槛直接反转",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.02), reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), -1), 12), subindustry)",
        "optimize_reason": "【高弹性脉冲直接均值回归】将母本 mLYNEWjW 经过验证的有效反转信号 reverse((P_close - P_ton) / P_ton) 直接嵌入 S3 的高门槛框架中。只有当盘中最高涨幅突破 2% 时才启动更新，非冲刺日严格维持历史持仓 (exit=-1)。通过舍弃 80% 平庸波动的微小新闻，使交易高度集中在最亢奋的多头冲刺个股上，既保留了母本 Sharpe 1.6 的优质反转内核，又借助 12% 的低换手将 Margin 直接撬升至 10.0 bps 以上。"
    },
    {
        "slot": 3,
        "seed_id": "GATE1_B4_S3",
        "question_type": "Q3_MAX_UP_SCALED_2PCT_REVERSE",
        "name": "最大上冲归一化 + 2% 门控反转",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.02), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(news_max_up_ret, 0.01))), -1), 12), subindustry)",
        "optimize_reason": "【最大上冲幅度归一化阻尼反转】在 2% 盘中暴涨门控的基础上，以 news_max_up_ret 作为分母阻尼因子对相对涨幅进行自适应归一化。经济学假设：如果一只股票盘中冲高 10% 收盘涨 8%，其收盘涨幅受极强动量支撑；而冲高 3% 收盘涨 1% 的股票回撤比例更大。归一化使得不同冲高高度的个股在相对力竭程度上标准化可比，结合 12 日线性平滑与子行业 Z-score，兼顾低换手与高信息比率。"
    },
    {
        "slot": 4,
        "seed_id": "GATE1_B4_S4",
        "question_type": "Q4_3PCT_POP_HIGH_MARGIN",
        "name": "3% 极高冲击门控 (强化单笔 Margin)",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.03), reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), -1), 15), subindustry)",
        "optimize_reason": "【3% 极高门槛压榨极限 Margin】将盘中冲测阈值从 2% 进一步抬高至 3%，同时平滑窗口延展至 15 日。经济学因果非常直接：盘中拉升超 3% 的新闻事件在 TOP1000 中属于极显著的异动事件，其过度反应后的均值修正空间平均达 50~100 bps。更稀疏的交易频次使年化换手率进一步降至 8%~10% 区间，依据 Margin 与换手率的严格物理反比关系，单笔净利润率将爆发式增长，直击 12~15 bps。"
    },
    {
        "slot": 5,
        "seed_id": "GATE1_B4_S5",
        "question_type": "Q5_2PCT_NET_DRIFT_COUNT_NORM",
        "name": "2% 净漂移门控 + 频次归一化反转",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(divide(subtract(news_eod_close, news_ton_last), news_ton_last), 0.02), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 12), subindustry)",
        "optimize_reason": "【净收益率 2% 门控与事件频次稀释】不同于盘中峰值门控，本处方以收盘实际净漂移 > 2% 作为触发条件。只有当新闻发布到收盘的实打实价格涨幅超过 2% 时才启动做空，并结合 vec_count 稀释多重新闻冲击。该逻辑确保了做空标的具有实实在在的收盘高估值溢价，而非日内已提前被套牢的冲高回落股，反向建仓点位极其扎实，提供更高的夏普稳定性。"
    },
    {
        "slot": 6,
        "seed_id": "GATE1_B4_S6",
        "question_type": "Q6_1_5PCT_NET_DRIFT_15D_DECAY",
        "name": "1.5% 净漂移温和门控 + 15日深度平滑",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(divide(subtract(news_eod_close, news_ton_last), news_ton_last), 0.015), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 15), subindustry)",
        "optimize_reason": "【1.5% 温和门控与更长衰减周期的黄金平衡】寻找交易样本量与单笔反转力度的黄金分割点。将门槛放宽至 1.5%，捕获更广泛的过度反应样本池，防止有效持仓过薄；同时将线性平滑窗口拉长至 15 日，拉平多日持仓，在确保换手率控制在 15% 以内的同时，维持多头与空头组合的充分分散化，降低个股非系统性风险。"
    },
    {
        "slot": 7,
        "seed_id": "GATE1_B4_S7",
        "question_type": "Q7_BILATERAL_EXTREME_DRIFT",
        "name": "双边 1.5% 极端异动反转 (涨跌双向捕捉)",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(abs(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), 0.015), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 12), subindustry)",
        "optimize_reason": "【双向极端偏离对称反转】不仅对暴涨 1.5% 做空，也对恐慌暴跌 1.5% 做多抄底。微观机制在于：恐慌盘砸盘导致的极度超跌往往在次日伴随强烈的流动性反抽。双边触发使投资组合在多头端与空头端均由最高弹性的异动事件驱动，提升组合长短双边的预测对称度，进一步增厚年化收益率至 7%~9%，支撑 Margin 稳健跨越 10 bps。"
    },
    {
        "slot": 8,
        "seed_id": "GATE1_B4_S8",
        "question_type": "Q8_CONCAVE_LOG_2PCT_REVERSE",
        "name": "凹函数压缩 + 2% 脉冲门控反转",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.02), s_log_1p(reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last))), -1), 12), subindustry)",
        "optimize_reason": "【凹函数压缩削平暴拉风险与 2% 门控联合】在 2% 盘中暴涨门控之上，施加 s_log_1p 对数凹压缩变换。该结构既利用 2% 门控锁定了 12% 的超低换手率与深厚 Margin，又通过对数变换抑制了个别突发连续暴涨个股对空头权重的吞噬，彻底防范最大回撤（DD）恶化，全面稳定全周期各年份夏普比率，冲击无任何警告项的终审准入标准。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_gate1_b4.json")

    payload = {
        "seed_id": "GATE1_CAMPAIGN_BATCH4",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close", "news_ton_last", "high_price_excursion_stddev", "news_max_up_ret"
        ],
        "items": PRESCRIPTIONS_GATE1_B4
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Gate 1 Batch 4 配置文件生成完毕: {batch_file}")
    print("🚀 启动 SimBatchRunner 后台静默执行批次 (decay=12, neutralization=INDUSTRY)...")

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_file,
        region="USA",
        universe="TOP1000",
        delay=1,
        category="news",
        neutralization="INDUSTRY",
        decay=12,
        truncation=0.025,
        nan_handling="ON"
    )

    print("\n🏁 Gate 1 Batch 4 回测与门禁终审完成!")
    output_summary = batch_file.replace(".json", "_summary.json")
    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
