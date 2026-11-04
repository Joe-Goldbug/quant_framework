# -*- coding: utf-8 -*-
"""Diagnostic sweep #2: 'other' category (where news12 actually lives)."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule

TARGET = "headline_positive_term_count_v2"


async def main():
    out = {"target": TARGET, "category": "other", "found_in": [], "fuzzy": {}, "checked": []}
    res = await BrainModule.get_datasets(category="other", region="USA", delay=1)
    ds = res.get("results", res) if isinstance(res, dict) else res
    if isinstance(ds, dict):
        ds = ds.get("results", [])
    names = [d.get("id") for d in ds if isinstance(d, dict) and d.get("id")]
    print(f"[other] {len(names)} datasets: {names}", flush=True)
    for name in names:
        try:
            fr = await BrainModule.get_datafields(
                region="USA", dataset_id=name, universe="TOP1000", delay=1, filter_sharpe=False)
            if isinstance(fr, dict) and fr.get("error"):
                continue
            flds = fr.get("results", fr) if isinstance(fr, dict) else fr
            ids = [f["id"] for f in flds if isinstance(f, dict) and "id" in f]
            out["checked"].append({"dataset": name, "n_fields": len(ids)})
            if TARGET in ids:
                out["found_in"].append(name)
                print(f"[FOUND] {TARGET} in {name}", flush=True)
            fuzzy = [i for i in ids if "positive_term" in i or "headline" in i]
            if fuzzy:
                out["fuzzy"][name] = fuzzy[:8]
                print(f"[FUZZY] {name}: {fuzzy[:8]}", flush=True)
        except Exception as e:
            out.setdefault("errors", []).append(f"{name}: {str(e)[:80]}")
    out["verdict"] = ("FOUND in " + ",".join(out["found_in"])) if out["found_in"] else "NOT FOUND in other category"
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "field_origin_diag_other.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("VERDICT:", out["verdict"], flush=True)


asyncio.run(main())
