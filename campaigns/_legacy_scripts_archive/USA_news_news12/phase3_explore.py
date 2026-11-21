# -*- coding: utf-8 -*-
"""
Phase 3 driver (final exploration batch): news12.
Batch-2 verdict: MA smoothing solves TO but kills the transient edge (Sh 1.37->0.25@MA20).
Fit math: TO must be <=12.5% for Fit>=1.0 at Sh>=1.58 -> smoothing route is closed.
Remaining levers that do NOT dilute the edge:
  (a) threshold stickiness via trade_when (positions persist while condition holds)
  (b) rank/group_rank wrappers (TO ~45%, uniform weights)
  (c) untested mechanism families: excursion give-back, reaction speed,
      short-interest-conditional reversal, trend/event divergence.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.sim_runner import SimBatchRunner

CAMPAIGN = os.path.join("quant_framework", "campaigns", "USA_news_news12")

A = "divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))"  # asymmetry core

VARIANTS = [
    {
        "id": 1,
        "type": "THRESHOLD_STICKINESS",
        "expression": f"trade_when(greater({A}, 0.75), reverse(news_max_up_ret), 0)",
        "optimize_reason": "阈值粘性上行侧：只在上行冲测占比超过 75% 的极端事件日做空（reverse 原始反向 Sharpe +1.37 的全部边缘保留在未被稀释的原始值里）。事件字段在事件间为前向填充，极端不对称一旦形成会持续到下一次事件，仓位具有天然粘性——若粘性假设成立，换手将从 130% 数量级下降而不触碰信号本身，这是唯一不稀释边缘的降换手机制。空头规模由最大上行幅度锚定。",
    },
    {
        "id": 2,
        "type": "THRESHOLD_STICKINESS",
        "expression": f"trade_when(less({A}, 0.25), reverse(news_max_dn_ret), 0)",
        "optimize_reason": "阈值粘性下行侧：只在下行压强占比超过 75%（A<0.25）的极端事件日做多，赚超卖反弹，多头规模由最大下行幅度锚定。与槽 1 构成双边阈值扫描，分别度量上/下两侧极端事件的回归强度是否对称——若两侧夏普接近，说明是对称的流动性回归；若一侧显著强，则是信息非对称（坏消息扩散更慢）。",
    },
    {
        "id": 3,
        "type": "RANK_WRAP",
        "expression": f"group_rank(reverse({A}), subindustry)",
        "optimize_reason": "排序包装旗舰：batch1 原始反向 +1.37 但 129.9% 换手；batch1 槽 7 显示 group_rank 可将换手压至 45%。组内排序把权重均匀化（消除极端值导致的权重集中与排名抖动），同时保留截面排序信息。若夏普保留 70% 以上且换手 ~45%，则得到该家族 TO 合规的基准形态，作为后续所有变体的对照锚。",
    },
    {
        "id": 4,
        "type": "EXCURSION_FAMILY",
        "expression": "reverse(news_high_exc_stddev)",
        "optimize_reason": "未测试族——收盘冲高回让度：news_high_exc_stddev 度量'收盘高点超出消息时刻价位多少个标准差'，是标准化的事件后派发指标。冲高越大说明追高盘在尾盘被派发得越彻底，属于流动性提供者被动出货后的价格虚高，次日回补概率高。反向即做空派发最彻底的股票。该字段仅有 40 个存量 alpha，拥挤度低，且标准差口径天然跨股可比。",
    },
    {
        "id": 5,
        "type": "DOWNSIDE_TWIN",
        "expression": "reverse(news_max_dn_ret)",
        "optimize_reason": "batch1 槽 3 只测试了上行冲高的 z-score  fade（+0.64），其下行孪生族未测：新闻后最大跌幅反向即'跌得越惨反弹越强'。若上行 fade 与下行 fade 强度接近，验证对称流动性回归机制；若下行更强，则符合坏消息扩散慢、超卖更极端的行為金融非对称性。原始值零平滑，边缘不稀释。",
    },
    {
        "id": 6,
        "type": "SPEED_FAMILY",
        "expression": "group_rank(reverse(news_mins_5_chg), subindustry)",
        "optimize_reason": "未测试族——反应速度：news_mins_5_chg 为价格出现 5% 移动所需分钟数（多空取快），是事件信息被市场消化的速度度量。反应越慢（分钟数越大）说明信息越复杂或关注度越低，定价不完整程度越高。反向+组内排序把'慢反应'映射为高信号，配合 group_rank 控换手。该族与幅度族（max_ret/pct）机制来源正交：幅度回答'动了多少'，速度回答'消化得多快'。",
    },
    {
        "id": 7,
        "type": "CONDITIONAL_REVERSAL",
        "expression": f"multiply(reverse({A}), news_short_interest)",
        "optimize_reason": "空头兴趣条件化的反转：裸反转对所有股票一视同仁，但高空头兴趣股票的向上冲高更可能是空头回补驱动的挤压——拥挤空头被逼平时买盘虚高，挤压结束后的回吐更剧烈。乘以空头兴趣比率让反转信号在'挤压脆弱'的股票上放大、在无空头压力的股票上衰减，把无条件反转升级为条件反转，属于对旗舰机制的信息增量而非重复。",
    },
    {
        "id": 8,
        "type": "DIVERGENCE",
        "expression": "subtract(news_prev_day_ret, news_pct_30min)",
        "optimize_reason": "趋势-事件背离：事件前一日收益与事件后 30 分钟反应之差。当既有上行趋势遭遇负面事件反应（差值为负）或下行趋势遭遇正面反应（差值为正）时，事件信息与趋势方向相反——此类背离要么是趋势的终结信号（延续），要么是事件的过度反应（回归），两种假说在此单槽对决。该结构只用两个字段、零平滑，是全批次最纯粹的二阶交互检验。",
    },
]


async def main():
    with open(os.path.join(CAMPAIGN, "news12_fields_raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]

    assert len(VARIANTS) == 8, "必须装满 8 槽"
    items = [{
        "expression": v["expression"],
        "optimize_reason": v["optimize_reason"],
        "seed_id": f"PHASE3_{v['id']}",
        "question_type": v["type"],
    } for v in VARIANTS]

    batch = {
        "seed_id": "SWARM_PHASE3_EXPLORE",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": known_fields,
        "items": items,
    }
    batch_path = os.path.join(CAMPAIGN, f"batch_phase3_explore_{int(time.time())}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"[Phase 3] 批次文件已写: {batch_path}")

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_path,
        region="USA",
        universe="TOP1000",
        delay=1,
        category="news",
        neutralization="INDUSTRY",
        decay=6,
        truncation=0.025,
    )

    with open(batch_path.replace(".json", "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"[Phase 3] 汇总已写: {batch_path.replace('.json', '_summary.json')}")


asyncio.run(main())
