"""
run_gate1_batch1.py
Gate 1: AEGIS 多 Agent 量化攻坚多重回测脚本 (批次 1)
数据集: USA / news12 / delay 1 / TOP1000
要求:
1. 2 <= 字段数 <= 3
2. 8 槽装满，因果假设完备
3. 后台静默执行，0 轮询刷屏
4. 不得擅自提交
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

PRESCRIPTIONS_GATE1 = [
    {
        "slot": 1,
        "seed_id": "GATE1_B1_S1",
        "question_type": "Q1_STICKY_ZSCORE",
        "name": "深度持仓保持 + 子行业 Z-score 纯化 (decay 15)",
        "expression": "group_zscore(ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 15), subindustry)",
        "optimize_reason": "【深化持仓保持与子行业 Z-score 标准化】基于前期最佳候选 Rx6 (2Y Sharpe 2.07) 进行深度演进。将线性衰减窗口从 10 日延长至 15 日，同时在平台层将 decay 设置由 6 提升至 12，形成双重时间加权平滑。微观经济学机理在于：新闻过激反应发生后，机构投资者和套利资金需要 2~3 周时间逐步消化非理性流动性冲击，延长持有期能完整捕获均值回归全周期，消除日频无谓震荡，预期将换手率压缩至 20% 以内，进而成倍提升 Margin 并拉升 Fitness。"
    },
    {
        "slot": 2,
        "seed_id": "GATE1_B1_S2",
        "question_type": "Q2_EXTREME_FILTER",
        "name": "幅度门控过滤 + 极值均值回归",
        "expression": "group_zscore(ts_decay_linear(trade_when(and(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), greater(abs(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), 0.015)), reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), -1), 15), subindustry)",
        "optimize_reason": "【极端过度反应门控过滤提升单笔 Margin】经济学微观假设：日常微小的新闻价格漂移（如 < 1.5%）多为流动性摩擦噪音，其后续反转空间极薄，频繁交易此类噪音正是导致前期 Margin 只有 1.4 bps 的根本原因。本处方前置引入 1.5% 绝对涨跌幅门槛，只对发生显著非理性冲刺的异动个股开仓，并在非事件日严格维持持仓 (exit=-1)。通过减少 70% 的低效交易，将资本集中于胜率最高、反转幅度最大的极端事件，旨在从根本上将单笔交易净利润率 (Margin) 结构性推高至 10.0 bps 以上。"
    },
    {
        "slot": 3,
        "seed_id": "GATE1_B1_S3",
        "question_type": "Q3_EXHAUSTION_WICK",
        "name": "冲顶力竭反转 (Shooting Star 剪刀差)",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_max_up_ret, 0.02), reverse(subtract(news_max_up_ret, divide(subtract(news_eod_close, news_ton_last), news_ton_last))), -1), 12), subindustry)",
        "optimize_reason": "【冲高回落多头衰竭假说】经济学逻辑：日内最高涨幅 news_max_up_ret 与最终收盘涨幅的差值，构成了经典的技术分析多头力竭阴影线（Shooting Star）。当盘中资金亢奋将股价推高超过 2%，但收盘时无力维持并大幅回落，表明多头弹药耗尽，空头与机构抛压主导市场，次日具有极强惯性补跌效应。以此剪刀差作为反转做空依据，具有极高单笔反转深度，配合子行业 Z-score 纯化与持仓保持，预期获得更高的超额收益率与深厚 Margin。"
    },
    {
        "slot": 4,
        "seed_id": "GATE1_B1_S4",
        "question_type": "Q4_IDIOSYNCRATIC_ALPHA",
        "name": "剥离大盘 Beta 的特质性新闻超额反转",
        "expression": "group_zscore(ts_decay_linear(reverse(divide(news_indx_perf, add(abs(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), 0.01))), 15), subindustry)",
        "optimize_reason": "【大盘相对表现纯化特质性过度反应】经济学逻辑：若个股在新闻日上涨主要跟随标普500大盘普涨，则属于宏观系统性 Beta，次日不会发生针对性均值回归；相反，若个股相对大盘的超额表现 news_indx_perf 发生极端背离，则为纯粹由散户注意力驱动的个股特质性非理性定价。本处方以特质性超额收益作为核心信号，剥离大盘波动干扰，在 15 日线性平滑下实现低回撤、高纯度的纯 Alpha 溢价，直击 Margin 与 Fitness 核心门禁。"
    },
    {
        "slot": 5,
        "seed_id": "GATE1_B1_S5",
        "question_type": "Q5_STANDARDIZED_EXCURSION",
        "name": "标准差偏离度门控反转 (news_high_exc_stddev)",
        "expression": "group_zscore(ts_decay_linear(trade_when(greater(news_high_exc_stddev, 1.0), reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), -1), 15), subindustry)",
        "optimize_reason": "【波动率标准化偏离度触发反转】引入 news12 官方波动率标准化字段 news_high_exc_stddev（以历史标准差度量价格偏离）。微观机理在于：不同个股的天然波动率悬殊，绝对涨跌幅容易被高 Beta 股占据；以 1.0 倍标准差作为异常偏离触发条件，能跨资产、跨行业等权重捕获各领域的真正异常脉冲，结合相对收益率反向做空与持仓保持，消除异方差扭曲，稳定全周期收益率并抬升 Margin。"
    },
    {
        "slot": 6,
        "seed_id": "GATE1_B1_S6",
        "question_type": "Q6_ASYMMETRY_RATIO",
        "name": "日内多空压强不对称度反转",
        "expression": "group_zscore(ts_decay_linear(reverse(divide(subtract(news_max_up_ret, news_max_dn_ret), add(add(news_max_up_ret, news_max_dn_ret), 0.01))), 15), subindustry)",
        "optimize_reason": "【上下行极值不对称度均值回归】经济学逻辑：news_max_up_ret 与 news_max_dn_ret 分别记录了新闻发布后盘中的最高上冲与最低下探幅度。两者的相对差值反映了多空力量在事件初期的即时压强倾斜。当多头单边极端上冲而空头完全未作抵抗时，呈现极度拥挤的追高交易，情绪达到短期极值，随后必将经历深刻的均值修正。15 日连续线性衰减平滑消除了交易脉冲，为组合提供极低换手率与深厚单位交易边际。"
    },
    {
        "slot": 7,
        "seed_id": "GATE1_B1_S7",
        "question_type": "Q7_ATR_NORMALIZED_DRIFT",
        "name": "真实波幅 (ATR14) 自归一化价格漂移",
        "expression": "group_zscore(ts_decay_linear(trade_when(less(days_from_last_change(news_eod_close), 2), reverse(divide(subtract(news_eod_close, news_ton_last), add(news_atr14, 0.01))), -1), 15), subindustry)",
        "optimize_reason": "【14日真实波幅自归一化消除波动异方差】针对名义价格差直接相减造成的规模偏差，本处方利用 news12 官方计算的 14 日平均真实波幅 news_atr14 作为分母归一化。经济学假设：一次跳空 2 美元对于日均 ATR 为 10 美元的科技巨头是微幅波动，但对于 ATR 仅 0.5 美元的低波防守股则是特大地震。以 ATR 为尺子标准化价格漂移，能真正挖掘低波个股中被市场忽视的超额定价偏差，显著拓宽持仓广度，提升组合 Sharpe 并降低集中度风险。"
    },
    {
        "slot": 8,
        "seed_id": "GATE1_B1_S8",
        "question_type": "Q8_CONCAVE_ZSCORE_DEEP",
        "name": "对数凹压缩 + 深度 18日平滑降换手",
        "expression": "group_zscore(ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(s_log_1p(divide(subtract(news_eod_close, news_ton_last), news_ton_last))), -1), 18), subindustry)",
        "optimize_reason": "【凹函数边际递减压缩与极限降换手攻坚】微观机理：过度反应的心理学认知偏差存在显著边际递减，利用 s_log_1p 对相对收益率施加对称凹压缩，削平狂暴个股的极端权重，压实同质化中间分布。同时将线性平滑窗口拉长至 18 日，在平台 decay 12 的双重协同下，目标将换手率压缩至 10%~15% 的超低区间。根据 Margin = Returns / (Turnover * 500) 的数学约束，当换手率降至 12% 且收益率维持 6% 时，Margin 自然跃升至 10 bps 以上，同时 Fitness 大幅突破 1.0 门槛。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_gate1_b1.json")

    payload = {
        "seed_id": "GATE1_CAMPAIGN_BATCH1",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close", "news_ton_last", "high_price_excursion_stddev",
            "news_max_up_ret", "news_max_dn_ret", "news_indx_perf",
            "news_high_exc_stddev", "news_atr14"
        ],
        "items": PRESCRIPTIONS_GATE1
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Gate 1 Batch 1 配置文件生成完毕: {batch_file}")
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

    print("\n🏁 Gate 1 Batch 1 回测与门禁终审完成!")
    output_summary = batch_file.replace(".json", "_summary.json")
    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
