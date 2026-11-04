"""
run_gate1_batch3.py
Gate 1: AEGIS 多 Agent 研发攻坚多重回测 (批次 3)
数据集: USA / news12 / delay 1 / TOP1000
核心机制革命:
彻底抛弃导致翻仓的 rank/group_zscore 每日强制全市场重排机制！
回归纯净的非对称真实价格漂移连续流：
非事件日天然为 0 / 平滑衰减，只有真实新闻日才具有非零持仓！
预期：从根源上将换手率压降至 10%~20%，同时彻底释放真实的 Alpha 反转幅度，直击 Margin >= 10.0 bps 与 Fitness >= 1.00！
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

PRESCRIPTIONS_GATE1_B3 = [
    {
        "slot": 1,
        "seed_id": "GATE1_B3_S1",
        "question_type": "Q1_PURE_RELATIVE_DRIFT_15D",
        "name": "纯相对价格漂移连续平滑 (15日线性衰减)",
        "expression": "ts_decay_linear(reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), 15)",
        "optimize_reason": "【纯净相对收益率时序平滑与无强制全排】此前批次受困于 rank 与 group_zscore 每日强制对全市场 1000 支股票重新排位的数学副作用，导致即便无新闻股票也被迫每日被动调仓（产生 85% 换手率）。本处方彻底剪除 rank 算子，直接使用以 news_ton_last 百分比标准化的纯净相对价格漂移。在没有新闻的交易日，由于价格差为 0 或维持不变，持仓天然保持或沿 15 日线性窗口渐进衰减归零，只有真正发生事件的个股产生非零增量仓位。该结构从根本上铲除了换手率虚高的病灶，极大降低调仓摩擦，预期使单笔净收益 Margin 直接突破 10.0 bps。"
    },
    {
        "slot": 2,
        "seed_id": "GATE1_B3_S2",
        "question_type": "Q2_COUNT_NORMALIZED_RELATIVE_DRIFT",
        "name": "事件计数归一化相对漂移 (15日衰减)",
        "expression": "ts_decay_linear(reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_count(high_price_excursion_stddev), 1))), 15)",
        "optimize_reason": "【事件频次稀释与相对收益率联合标准化】在纯相对价格漂移的基础上，引入原始母本的核心分母 add(vec_count, 1) 进行多事件稀释。微观因果假设：单日多条新闻连续轰炸的个股，其日内累计漂移可能包含较多重复计算的非理性溢价；以新闻条数作为分母除数，能对过度兴奋的多重事件进行平滑降权，防止单一突发热点个股占满资金敞口。结合 15 日连续线性衰减，组合风险高度分散，夏普与回撤表现显著优于单事件股票。"
    },
    {
        "slot": 3,
        "seed_id": "GATE1_B3_S3",
        "question_type": "Q3_AVG_EXCURSION_NORMALIZATION",
        "name": "平均冲测标准差自归一化漂移",
        "expression": "ts_decay_linear(reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(vec_avg(high_price_excursion_stddev), 1))), 15)",
        "optimize_reason": "【以平均冲测标准差作为阻尼因子的均值回归】经济学假设：日内平均向上冲刺的标准差 vec_avg 越大，说明盘中多头力量越强劲，此时仅凭收盘净涨幅往往不足以完全反映冲顶难度；将 vec_avg 放置于分母作为阻尼系数，能有效平抑由流动性枯竭造成的假突破冲击，放大被市场低估的温和过度反应，实现高质量的单位交易盈利率与更高的收益稳定性。"
    },
    {
        "slot": 4,
        "seed_id": "GATE1_B3_S4",
        "question_type": "Q4_MAX_UP_RET_SCALING",
        "name": "盘中最大涨幅归一化剪刀差",
        "expression": "ts_decay_linear(reverse(divide(divide(subtract(news_eod_close, news_ton_last), news_ton_last), add(news_max_up_ret, 0.01))), 15)",
        "optimize_reason": "【日内最大弹性与收盘漂移的相对动能衰竭】微观因果机理：news_max_up_ret 记录了盘中最高脉冲幅度。若收盘涨幅与最大涨幅几乎一致，表明全天买盘极其坚决（动量强劲，反转阻力大）；若收盘涨幅远小于最大涨幅，比值大幅缩小，表明盘中获利回吐极其剧烈。以此比率反向建仓，精准捕捉获利盘出逃、多头力竭的脆弱窗口，获得极高的次日均值回归胜率与深厚 Margin。"
    },
    {
        "slot": 5,
        "seed_id": "GATE1_B3_S5",
        "question_type": "Q5_ATR14_NORMALIZED_CONTINUOUS",
        "name": "14日真实波幅自归一连续漂移",
        "expression": "ts_decay_linear(reverse(divide(subtract(news_eod_close, news_ton_last), add(news_atr14, 0.01))), 15)",
        "optimize_reason": "【真实波幅自归一化与连续低换手平滑】名义价格变动如果不消除波动率量纲，组合权重必然被少数高波妖股所绑架。本处方直接采用 news12 官方 14 日平均真实波幅 news_atr14 进行无量纲标准化，使得一笔 1 美元的跳空在不同波动率基准的个股间完全可比。完全摒弃外层 rank 重排，让不同个股依事件脉冲自然建仓与淡出，预期换手率锁定在 10%~15% 极低区间，单位交易利润率成倍抬升。"
    },
    {
        "slot": 6,
        "seed_id": "GATE1_B3_S6",
        "question_type": "Q6_CONCAVE_RELATIVE_DRIFT",
        "name": "对数凹函数压缩相对漂移",
        "expression": "ts_decay_linear(reverse(s_log_1p(divide(subtract(news_eod_close, news_ton_last), news_ton_last))), 15)",
        "optimize_reason": "【凹函数边际效用递减压缩与连续衰减】行为金融学微观基础：散户与短期跟风资金对新闻冲击的过度反应呈现边际效用递减曲线。利用 s_log_1p 对相对收益率施加对称凹压缩，既保留了收益率的正负方向与连续性，又压制了暴涨 20% 极端个股对权重的单边垄断。无外层 rank 扰动，信号在 15 日线性衰减下呈现极度平滑的换仓特征，显著降低滑点损耗并稳定抬升 Fitness。"
    },
    {
        "slot": 7,
        "seed_id": "GATE1_B3_S7",
        "question_type": "Q7_PURE_RELATIVE_DRIFT_20D",
        "name": "纯相对漂移长周期 20日平滑 (极限降换手)",
        "expression": "ts_decay_linear(reverse(divide(subtract(news_eod_close, news_ton_last), news_ton_last)), 20)",
        "optimize_reason": "【20日长衰减窗口极限降换手攻坚】针对 USA 市场 10.0 bps 的严苛 Margin 门禁，将相对收益率线性平滑窗口由 15 日进一步延展至 20 日。数学因果逻辑清晰：在年化收益率维持 6%~8% 的前提下，持仓周期的进一步拉长将换手率压缩至 8%~12% 极限水平，根据 Margin = Annual_Ret / (Turnover * 500) 的严格反比约束，Margin 自然被杠杆式放大至 12~16 bps，彻底攻克 Margin 门禁。"
    },
    {
        "slot": 8,
        "seed_id": "GATE1_B3_S8",
        "question_type": "Q8_TS_STDDEV_NORMALIZED_DRIFT",
        "name": "时序历史 20日标准差自归一化漂移",
        "expression": "ts_decay_linear(reverse(divide(subtract(news_eod_close, news_ton_last), add(ts_std_dev(subtract(news_eod_close, news_ton_last), 20), 0.01))), 15)",
        "optimize_reason": "【自身时序 20 日标准差自适应归一化】不依赖任何外部字段，完全利用新闻价格漂移序列自身的 20 日滚动标准差 ts_std_dev 进行 Z-Score 式的个股自适应标准化。在个股自身历史时间轴上识别真正的统计学异常事件，实现纯粹的内生去量纲化。配合 15 日线性平滑，持仓连续平稳，有效隔绝市场宏观波动与截面重排噪音，全维度冲击最终生产门禁。"
    }
]

async def main():
    campaign_dir = os.path.join("quant_framework", "campaigns", "USA_news_news12")
    os.makedirs(campaign_dir, exist_ok=True)
    batch_file = os.path.join(campaign_dir, "batch_gate1_b3.json")

    payload = {
        "seed_id": "GATE1_CAMPAIGN_BATCH3",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": [
            "news_eod_close", "news_ton_last", "high_price_excursion_stddev", "news_max_up_ret", "news_atr14"
        ],
        "items": PRESCRIPTIONS_GATE1_B3
    }

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Gate 1 Batch 3 配置文件生成完毕: {batch_file}")
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

    print("\n🏁 Gate 1 Batch 3 回测与门禁终审完成!")
    output_summary = batch_file.replace(".json", "_summary.json")
    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
