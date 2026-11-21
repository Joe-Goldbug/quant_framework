"""
run_mLYNEWjW_opt.py
AEGIS 种子因子定向优化执行脚本 (alpha-id: mLYNEWjW)
严格遵循五大铁律：
1. 装满 8 条卡槽 (4 探索 + 4 演进)
2. Python 后台单次阻塞静默回测 (0 轮询刷屏，0 Token 浪费)
3. 纯 news12 内部字段，严禁 PV 污染
4. 全维度物理门禁 (Fitness>=1.0, USA Margin>=10bps, Turnover in [5%, 50%])
5. 白盒立项研报前置校验通过
"""

import asyncio
import json
import os
import sys

# 关键路径
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.gatekeeper import Gatekeeper
from quant_framework.core.sim_runner import SimBatchRunner

# 8 条定向处方变体
PRESCRIPTIONS = [
    {
        "slot": 1,
        "seed_id": "mLYNEWjW_Rx1",
        "question_type": "Q1_TEMPORAL_STICKINESS",
        "name": "持仓保持 + 10日线性平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), -1), 10)",
        "optimize_reason": "【处方1: 持仓保持与线性平滑降换手】原母本 mLYNEWjW 换手率高达 114.59% 的罪魁祸首在于 trade_when 结尾设置了 0：当股票在过去 2 天未触发新闻事件时，仓位被强制清空为零（硬平仓），而在新的新闻到来时又全额开仓，导致高频无谓震荡。本处方将第三参数置为 -1，使非事件日严格维持原有持仓，并引入 10 日线性衰减函数提供渐进平滑退场通道。线性衰减相比指数衰减赋予近期事件更高的平滑权重，避免了指数加权对新闻事件快速记忆的破坏。此举直击高换手病灶，预期将换手率从 115% 强力压降至 25%~35% 区间，同时减少交易滑点侵蚀，将 Margin 从 1.31 bps 翻倍抬升，并通过换手率降幅直接拉升 Fitness 跨越 1.0 门槛。"
    },
    {
        "slot": 2,
        "seed_id": "mLYNEWjW_Rx2",
        "question_type": "Q2_CROSS_SECTION_PURIFICATION",
        "name": "子行业下沉 + 15日线性衰减",
        "expression": "group_rank(ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 15), subindustry)",
        "optimize_reason": "【处方2: 子行业下沉剥离行业系统性风险抬升 Margin】针对母本 Margin 仅 1.31 bps 的严重贫血病灶，核心假说在于全市场统一排序混杂了大量细分行业层面的系统性事件漂移（例如生物医药在财报日的新闻振幅天然大于公用事业，全市场 rank 导致仓位被特定高波动行业主导，行业间系统性风险严重稀释了纯净 Alpha 溢价）。本处方将截面排序下沉至 subindustry（子行业层级），在最细颗粒度下剥离行业 Beta，保留同行业内对新闻过度反应的相对强弱；配合 15 日线性衰减进一步压实换手率至 20% 左右。该机制预期大幅提升每笔交易的纯 Alpha 边际（目标 Margin 突破 10.0 bps），从根本上消除行业共线性并解决 Margin 不足的问题。"
    },
    {
        "slot": 3,
        "seed_id": "mLYNEWjW_Rx3",
        "question_type": "Q3_SCALE_NORMALIZATION",
        "name": "相对收益率归一 + 10日线性平滑",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), -1), 10)",
        "optimize_reason": "【处方3: 相对百分比收益率标准化消除价格异方差】母本直接使用 subtract(news_eod_close, news_ton_last) 是绝对美元差价，这种未消除名义股价尺度的做法在 TOP1000 股票池中造成严重扭曲：高价股（如 500 美元股票变动 5 美元）的信号幅度天然是低价股（如 10 美元股票变动 0.5 美元）的 10 倍，导致投资组合权重被少数高单价个股绑架，引发极端离群值并拉低 Margin 与 Fitness。本处方通过除以事件发生时的基准价格 news_ton_last 实现百分比收益率标准化（(P_close - P_ton) / P_ton），使得所有个股的新闻过度反应在无量纲的百分比尺度上完全可比，消除价格异方差性，配合 10 日持仓衰减，预期全面提升收益稳定度与 Fitness。"
    },
    {
        "slot": 4,
        "seed_id": "mLYNEWjW_Rx4",
        "question_type": "Q4_OUTLIER_TRUNCATION",
        "name": "Winsorize 3倍标准差 + 8日指数平滑",
        "expression": "winsorize(ts_decay_exp_window(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), -1), 8, factor=0.8), std=3)",
        "optimize_reason": "【处方4: Winsorize 去极值平抑剧震拉升 Fitness】针对母本 Fitness 仅 0.41 的核心病灶，微观机制分析表明，个别重大突发新闻日（如极端业绩暴雷或超预期收购）会产生超过 5~10 倍标准差的狂暴价格脉冲，导致投资组合在单日被极少数头寸主导，造成非系统性的巨大收益跳跃与子时段夏普断崖（Sub-universe 剧震）。本处方在 8 日指数半衰期平滑（factor=0.8 确保近期记忆不被过度稀释）之后，前置注入 winsorize(std=3) 算子，强制修剪长尾离群值，保留分布主体 99.7% 的连续信息，压制极值引发的波动率膨胀，从数学上直接攻克 LOW_FITNESS 检查项，使因子在全历史区间表现平稳一致。"
    },
    {
        "slot": 5,
        "seed_id": "mLYNEWjW_Rx5",
        "question_type": "Q5_CONTINUOUS_STREAM",
        "name": "全时序连续平滑 (剥离 trade_when)",
        "expression": "ts_decay_linear(reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 12)",
        "optimize_reason": "【处方5: 连续时序流滤波与结构极简剪枝】本处方实施彻底的结构性剪枝：探究 trade_when 本身是否属于多余的阶跃伪结构。当没有新闻事件时，news_eod_close 与 news_ton_last 的差值在数据集中保持静态或 0，强行使用 trade_when 反而制造了非连续的人为边界断裂。本处方直接对全时序反转信号施加 12 日线性衰减 ts_decay_linear(..., 12)，让事件冲击自然形成平缓的三角形权重衰减曲线。该结构消除了任何外部门控逻辑，算子总数降至仅 7 个，极端纯净，利用纯数学时序滤波实现稳健的降换手（预期 TO 降至 35% 左右），检验连续流假设在新闻数据集上的因果有效性。"
    },
    {
        "slot": 6,
        "seed_id": "mLYNEWjW_Rx6",
        "question_type": "Q6_SUBINDUSTRY_ZSCORE",
        "name": "相对收益 + 子行业 Z-score 标准化",
        "expression": "group_zscore(ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), -1), 10), subindustry)",
        "optimize_reason": "【处方6: 相对收益率与子行业 Z-score 联合提纯】本处方为复合攻坚型王牌处方：同时针对 Margin、Turnover 与 Fitness 三重病灶展开全方位协同夹击。首先通过除以 news_ton_last 消除名义股价量纲，获得纯正百分比涨跌幅；其次通过 trade_when(..., -1) 配合 10 日线性衰减化解频繁开平仓，把换手率锁定在黄金区间；最后利用 group_zscore(..., subindustry) 代替普通分位数 rank，使同子行业内的多空权重具有严格的正态分布标准差度量，放大极端错误定价股票的置信度，压平同质化中间股票的权重。此举旨在最大化信息比率与单位换手收益，为冲击 Margin >= 10 bps 与 Fitness >= 1.20 建立双重保障。"
    },
    {
        "slot": 7,
        "seed_id": "mLYNEWjW_Rx7",
        "question_type": "Q7_CONCAVE_COMPRESSION",
        "name": "非线性凹压缩 (s_log_1p) 控制集中度",
        "expression": "s_log_1p(ts_decay_exp_window(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), -1), 10, factor=0.85))",
        "optimize_reason": "【处方7: 凹函数边际递减压缩控制持仓集中度】针对因子在极端行情下可能触发的 CONCENTRATED_WEIGHT 违规风险及尾部收益剧烈反噬问题，本处方引入凹函数变换 s_log_1p（有符号自然对数压缩: sign(x)*log(1+|x|)）。在心理学与行为金融学上，市场对新闻冲击的过度反应存在显著的边际递减效应——最初的冲击反应最强烈，越往后边际效应越弱。凹函数能够有效拉平头部巨头的过度暴露，将更多的边际权重分配给中间层有效定价差异的股票，从而提升投资组合的多样化持仓广度（Breadth），平滑 PnL 波动，降低最大回撤（DD），并协同 10 日指数平滑（factor=0.85）抑制高频翻仓。"
    },
    {
        "slot": 8,
        "seed_id": "mLYNEWjW_Rx8",
        "question_type": "Q8_MARGINAL_ACCELERATION",
        "name": "一阶时序差分 (ts_delta) 捕捉衰竭拐点",
        "expression": "ts_decay_linear(trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_delta(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 2))), -1), 8)",
        "optimize_reason": "【处方8: 时序动量一阶差分锁定过度反应衰竭拐点】原母本采用静态的价格差反应水平，但在真实新闻反转交易中，真正产生高夏普与高胜率的时间点并非价格偏离绝对值最大的时刻，而是漂移加速度开始减速停滞（边际动量耗竭）的关键拐点。本处方通过引入 ts_delta(..., 2) 对新闻漂移序列求一阶导数差分，精准锁定过度反应由冲顶转向力竭的动态瞬间；配合 8 日线性衰减锁定拐点发生后的反转持仓。该机制将因子属性由静态水平反转升级为动态加速度反转，探索与前 7 槽完全正交的时间动力学机制，若成立将提供更具韧性的多空收益曲线。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_mLYNEWjW_opt.json")

    payload = {
        "seed_id": "mLYNEWjW",
        "seed_alpha": "mLYNEWjW",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close",
            "news_ton_last",
            "high_price_excursion_stddev"
        ],
        "items": PRESCRIPTIONS
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ 批次文件生成完毕: {batch_file}")
    print("🚀 启动 SimBatchRunner 后台静默执行批次...")

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

    print("\n🏁 批次回测与门禁终审完成!")
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
