# -*- coding: utf-8 -*-
"""Fetch news12 datafields (USA / TOP1000 / delay 1) for Phase 0 field profile."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news12_fields_raw.json")


async def main():
    res = await BrainModule.get_datafields(
        region="USA",
        dataset_id="news12",
        universe="TOP1000",
        delay=1,
    )
    if isinstance(res, dict) and res.get("error"):
        print("ERROR:", res["error"])
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    # slim print
    fields = res.get("results", res) if isinstance(res, dict) else res
    count = res.get("count", len(fields)) if isinstance(res, dict) else len(fields)
    print(f"OK fields count = {count}")
    for it in (fields[:80] if isinstance(fields, list) else []):
        print(json.dumps(it, ensure_ascii=False)[:220])


asyncio.run(main())
