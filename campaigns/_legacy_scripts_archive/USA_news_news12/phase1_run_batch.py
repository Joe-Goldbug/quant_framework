# -*- coding: utf-8 -*-
"""
Phase 1 driver: news12 (USA / TOP1000 / delay 1) first swarm batch.
8 slots = 8 orthogonal main signals (Q1-Q8). Silent background execution via SimBatchRunner.
Settings: neutralization=INDUSTRY, decay=6, truncation=0.025 (AEGIS batch-1 standard).
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
POOL = os.path.join(CAMPAIGN, "total_signals.json")

NEUTRALIZATION = "INDUSTRY"
DECAY = 6
TRUNCATION = 0.025


async def main():
    with open(POOL, encoding="utf-8") as f:
        pool = json.load(f)
    with open(os.path.join(CAMPAIGN, "news12_fields_raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]

    seeds = pool["signals"]
    assert len(seeds) == 8, f"种子池必须恰好 8 条, 当前 {len(seeds)}"

    items = [{
        "expression": s["expression"],
        "optimize_reason": s["economic_mechanism"],
        "seed_id": s["id"],
        "question_type": s["question_type"],
    } for s in seeds]

    batch = {
        "seed_id": "SWARM_Q1_Q8",
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "category": "news",
        "known_fields": known_fields,
        "items": items,
    }
    batch_path = os.path.join(CAMPAIGN, f"batch_swarm_q1q8_{int(time.time())}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"[Phase 1] 批次文件已写: {batch_path} (8 slots, neutralization={NEUTRALIZATION}, decay={DECAY})")

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_path,
        region="USA",
        universe="TOP1000",
        delay=1,
        category="news",
        neutralization=NEUTRALIZATION,
        decay=DECAY,
        truncation=TRUNCATION,
    )

    # writeback pool times
    for s in pool["signals"]:
        s["times"] = s.get("times", 0) + 1
        if isinstance(res, dict) and res.get("step1", {}).get("should_prune"):
            s["status"] = "PRUNED_AT_STEP1"
        else:
            s["status"] = "PROGRESSED"
    with open(POOL, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)

    with open(batch_path.replace(".json", "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"[Phase 1] 汇总已写: {batch_path.replace('.json', '_summary.json')}")


asyncio.run(main())
