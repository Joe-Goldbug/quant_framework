# -*- coding: utf-8 -*-
"""
Phase 2 driver: news12 deep refinement batch #2.
Batch-1 diagnosis:
  - Direction consensus: event reactions OVERREACT -> next-day reversion
    (Q5 asym -1.37, Q6 momentum -0.72, Q2 drift -0.49 -> reversed = +1.37/+0.72/+0.49;
     Q3 pop-fade +0.64 forward already reversal-oriented)
  - Universal killer: TO 90-130% (platform HIGH_TURNOVER limit 0.70, AEGIS gate 50%)
  - Margin ~1bp, Fit ~0.3 -> TO-limited; Fit floor at TO<=12.5% is the lever
  - Q8 sparse (11 positions) -> drop; Q1/Q7 dead -> drop
Prescription: reverse() orientation + ts_mean input smoothing (window scan 20/60/250)
to crush TO into [5%,15%] while preserving the reversal edge.
Settings unchanged: INDUSTRY / decay=6 / truncation=0.025 (comparability).
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
        "type": "EVOLUTION",
        "expression": f"reverse(ts_mean({A}, 20))",
        "optimize_reason": "Q5 不对称度家族的短窗平滑（20日）：batch1 原始不对称度反向 Sharpe -1.37（反向即 +1.37，2Y +1.68 已过线），唯一死因是 129.9% 换手。20 日均值把事件冲击的特征成分从日频噪声中分离，预计 TO 降至 25% 附近，检验最短有效平滑窗。",
    },
    {
        "id": 2,
        "type": "EVOLUTION",
        "expression": f"reverse(ts_mean({A}, 60))",
        "optimize_reason": "Q5 不对称度家族的中窗平滑（60日）：在换手与信号稀释之间取中，预估 TO 12-17%，落入 Fit 地板受益区（max(TO,0.125)）。若原始 +1.37 的夏普被平滑保留 80% 以上即可同时满足 Sh>=1.3 与 TO<=15%，是本批次旗舰梭哈。",
    },
    {
        "id": 3,
        "type": "EVOLUTION",
        "expression": f"reverse(ts_mean({A}, 250))",
        "optimize_reason": "Q5 不对称度家族的长窗平滑（250日/年）：把事件不对称度压成稳定的个股特征（持续冲高型彩票股），TO 预计 6-9%，深度进入 Fit 地板区。检验过度平滑是否把边缘稀释到失效，与 20/60 日窗构成完整窗口扫描。",
    },
    {
        "id": 4,
        "type": "EVOLUTION",
        "expression": "reverse(ts_mean(news_indx_perf, 60))",
        "optimize_reason": "Q6 事件超额动量家族反向 + 60 日平滑：batch1 原始 decay_linear(20) 反向 +0.72、rnSh +0.90。超额收益口径已剔市场基准，反向即'事件动量宿命回吐'。60 日均值替代 decay_linear 以纯窗口控制换手，TO 预计 10-14%。",
    },
    {
        "id": 5,
        "type": "EVOLUTION",
        "expression": "reverse(ts_mean(divide(subtract(news_max_up_ret, ts_mean(news_max_up_ret, 60)), ts_std_dev(news_max_up_ret, 60)), 60))",
        "optimize_reason": "Q3 极端冲高 z-score 家族 + 外层 60 日平滑：batch1 该结构正向 +0.64 且 InvSh 0.70 / rnSh 0.98 为全批最优风险轮廓，但 116.7% 换手致死。z-score 保证跨股可比，外层均值进一步把'持续冲高倾向'从单次冲击中提炼，TO 预计 12-18%。",
    },
    {
        "id": 6,
        "type": "EVOLUTION",
        "expression": "ts_mean(multiply(news_pct_30min, news_vol_stddev), 60)",
        "optimize_reason": "Q4 量价共振家族保持原方向 + 60 日平滑：batch1 正向 +0.66 且 2Y +1.19 为全批最高（唯一 2Y 过 1.0 者）。成交量背书的反应代表真实信息注入、价格发现不完整，与反转家族形成科学对冲——若全批皆反，此槽验证'被确认的反应延续'这一对立假说。",
    },
    {
        "id": 7,
        "type": "EVOLUTION",
        "expression": "reverse(ts_mean(subtract(news_pct_120min, news_pct_30min), 60))",
        "optimize_reason": "Q2 当日慢扩散漂移家族反向 + 60 日平滑：batch1 原始 -0.49，反向即 +0.49。漂移度为负说明 120 分钟反应相对 30 分钟的延伸部分次日回吐——过度反应的日内延续比初始跳变更脆弱。60 日平滑后 TO 预计 12-18%。",
    },
    {
        "id": 8,
        "type": "EXPLORATION",
        "expression": "reverse(ts_mean(news_open_gap, 60))",
        "optimize_reason": "全新探索：隔夜跳空缺口 60 日平滑后反向。开盘跳空是盘前时段对新闻的第一定价，注意力驱动的追高开盘在次日系统性回补（隔夜缺口反转是行为金融最稳健的异象之一）。60 日均值把'跳空倾向'转为个股特征，与日内反应家族机制来源正交（盘前 vs 盘中），TO 预计 10-15%。",
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
        "seed_id": f"PHASE2_{v['id']}",
        "question_type": v["type"],
    } for v in VARIANTS]

    batch = {
        "seed_id": "SWARM_PHASE2_REFINE",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": known_fields,
        "items": items,
    }
    batch_path = os.path.join(CAMPAIGN, f"batch_phase2_refine_{int(time.time())}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"[Phase 2] 批次文件已写: {batch_path}")

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
    print(f"[Phase 2] 汇总已写: {batch_path.replace('.json', '_summary.json')}")


asyncio.run(main())
