"""
run_gate1_batch8.py
Gate 1: AEGIS 多 Agent 研发攻坚多重回测 (批次 8)
数据集: USA / news12 / delay 1 / TOP1000
核心机制革命: 从单日微观噪音跨越至 20~30 日累积新闻漂移大周期 (PEAD vs Multi-Week Reversal)!
经济学机理：
单日新闻脉冲在 delay 1 下被隔夜抢跑压制在 1~5 bps；
但在 20~30 日滚动时间窗口内，持续遭遇负面或正面新闻冲击的个股，将经历机构资本数周的持续资金再配置！
累积漂移幅度达 300~500 bps，持仓周期拉长使换手率自然压至 10%~15%，
单笔交易净收益 Margin 预期爆发式跃升至 10.0~20.0 bps，从物理底层彻底攻克生产门禁！
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

PRESCRIPTIONS_GATE1_B8 = [
    {
        "slot": 1,
        "seed_id": "GATE1_B8_S1",
        "question_type": "Q1_20D_CUMULATIVE_DRIFT_MOMENTUM",
        "name": "20日累积新闻漂移延续假说 (PEAD 动量)",
        "expression": "group_zscore(ts_mean(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20), subindustry)",
        "optimize_reason": "【盈余公告后漂移 (PEAD) 20 日动量假说】经典金融学现象：在更长的时间尺度上，重大新闻信息在机构间扩散具有渐进性与不充分反应（Underreaction）。过去 20 日持续呈现正向新闻价格漂移的个股，在未来数周将获得持续的资金流入。以 20 日滚动均值作为信号，持仓时间自然拉长至一个月，换手率降至 10%~15%，累积收益空间达数个百分点，从根本上将 Margin 推高至 10.0 bps 以上。"
    },
    {
        "slot": 2,
        "seed_id": "GATE1_B8_S2",
        "question_type": "Q2_20D_CUMULATIVE_DRIFT_REVERSAL",
        "name": "20日累积新闻漂移反转假说 (多周中期反转)",
        "expression": "group_zscore(reverse(ts_mean(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20)), subindustry)",
        "optimize_reason": "【中期过度反应均值回归假说】与动量相对立的中期反转假说：过去 20 日持续被新闻炒作推高的股票，其估值溢价已透支未来数季度的盈利，机构筹码开始派发。反向做空 20 日累积炒作标的，捕捉大级别泡沫破灭利润。20 日平滑从底层消灭日内摩擦，实现低换手与高单笔净收益的双重突破。"
    },
    {
        "slot": 3,
        "seed_id": "GATE1_B8_S3",
        "question_type": "Q3_30D_CUMULATIVE_SUM_MOMENTUM",
        "name": "30日累积事件压力总和 (动量方向)",
        "expression": "group_zscore(ts_sum(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 30), subindustry)",
        "optimize_reason": "【30日信息累积压力总和动量】以 ts_sum 聚合过去 30 日所有新闻事件的净冲击强度。频繁遭遇利好事件且每次均收涨的个股累积得分极高，体现基本面长期反转拐点。30 日跨度使组合呈现高度稳定的月度轮动特征，换手率锁定在 8%~12% 极限水平，为达成 Margin >= 10 bps 提供最坚实的持仓周期支撑。"
    },
    {
        "slot": 4,
        "seed_id": "GATE1_B8_S4",
        "question_type": "Q4_30D_CUMULATIVE_SUM_REVERSAL",
        "name": "30日累积事件压力总和 (反转方向)",
        "expression": "group_zscore(reverse(ts_sum(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 30)), subindustry)",
        "optimize_reason": "【30日极端过热疲劳反转】过去 30 日累计承受最强新闻买压的股票已进入情绪衰竭期。反向做空此类极度拥挤标的，吃满漫长的阴跌补跌收益。与槽 3 共同完成对 30 日周期多空方向的对称判决。"
    },
    {
        "slot": 5,
        "seed_id": "GATE1_B8_S5",
        "question_type": "Q5_20D_LINEAR_WEIGHTED_MOMENTUM",
        "name": "20日线性时间加权新闻漂移 (近期优先动量)",
        "expression": "group_zscore(ts_decay_linear(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20), subindustry)",
        "optimize_reason": "【三角形时间加权信息传递假说】简单均值等权看待 20 天前的事件，而线性加权对近期事件赋予更高权重（信息新鲜度更高）。通过三角形时间衰减捕捉正在加速发酵的新闻动量，保持持仓粘性的同时提高对拐点的敏感度。"
    },
    {
        "slot": 6,
        "seed_id": "GATE1_B8_S6",
        "question_type": "Q6_20D_LINEAR_WEIGHTED_REVERSAL",
        "name": "20日线性时间加权新闻漂移 (近期优先反转)",
        "expression": "group_zscore(reverse(ts_decay_linear(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20)), subindustry)",
        "optimize_reason": "【三角形时间加权近期过激反转】对近期新闻冲击赋予更大反转权重的 20 日中期衰减模型。检验反转信号在赋予近期事件权重倾斜时的表现，全维度对比检验动量与反转的边际有效性。"
    },
    {
        "slot": 7,
        "seed_id": "GATE1_B8_S7",
        "question_type": "Q7_20D_GROUP_RANK_MOMENTUM",
        "name": "20日子行业组内排序 (动量方向)",
        "expression": "group_rank(ts_mean(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20), subindustry)",
        "optimize_reason": "【子行业组内分位数动量】采用 group_rank 替代 group_zscore，消灭极端长尾离群值导致的权重畸变，确保每个子行业内部资金均匀配置。在 20 日慢速动量下提供极其平滑的资金曲线与更低的最大回撤。"
    },
    {
        "slot": 8,
        "seed_id": "GATE1_B8_S8",
        "question_type": "Q8_20D_GROUP_RANK_REVERSAL",
        "name": "20日子行业组内排序 (反转方向)",
        "expression": "group_rank(reverse(ts_mean(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 20)), subindustry)",
        "optimize_reason": "【子行业组内分位数反转】对 20 日均值实施 group_rank 逆向排序。以最稳健的有界分位数结构防范集中度与回撤违规，探索在长周期反转下达成全指标通过的最佳路径。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_gate1_b8.json")

    payload = {
        "seed_id": "GATE1_CAMPAIGN_BATCH8",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close", "news_ton_last", "high_price_excursion_stddev"
        ],
        "items": PRESCRIPTIONS_GATE1_B8
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Gate 1 Batch 8 配置文件生成完毕: {batch_file}")
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

    print("\n🏁 Gate 1 Batch 8 回测与门禁终审完成!")
    output_summary = batch_file.replace(".json", "_summary.json")
    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
