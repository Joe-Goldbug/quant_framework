# -*- coding: utf-8 -*-
"""Diagnostic: locate the true home dataset of headline_positive_term_count_v2 (or prove absence)."""
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
    out = {"target": TARGET, "found_in": [], "checked_datasets": [], "notes": []}
    # 1) list all USA datasets (news + sentiment categories)
    for cat in ["news", "sentiment", "socialmedia", "text"]:
        try:
            res = await BrainModule.get_datasets(category=cat, region="USA", delay=1)
            if isinstance(res, dict) and res.get("error"):
                out["notes"].append(f"cat={cat} error: {res['error']}")
                continue
            ds = res.get("results", res) if isinstance(res, dict) else res
            if isinstance(ds, dict):
                ds = ds.get("results", [])
            names = [d.get("id") for d in ds if isinstance(d, dict) and d.get("id")]
            out["notes"].append(f"cat={cat} datasets: {names}")
            print(f"[datasets] cat={cat}: {names}", flush=True)
            # 2) check each dataset's fields for the target
            for name in names:
                try:
                    fr = await BrainModule.get_datafields(
                        region="USA", dataset_id=name, universe="TOP1000", delay=1, filter_sharpe=False)
                    if isinstance(fr, dict) and fr.get("error"):
                        continue
                    flds = fr.get("results", fr) if isinstance(fr, dict) else fr
                    ids = [f["id"] for f in flds if isinstance(f, dict) and "id" in f]
                    out["checked_datasets"].append({"dataset": name, "n_fields": len(ids)})
                    if TARGET in ids:
                        out["found_in"].append(name)
                        print(f"[FOUND] {TARGET} lives in dataset: {name}", flush=True)
                    # also fuzzy: any field containing positive_term
                    fuzzy = [i for i in ids if "positive_term" in i]
                    if fuzzy:
                        out["notes"].append(f"dataset {name} fuzzy positive_term fields: {fuzzy[:10]}")
                        print(f"[FUZZY] {name}: {fuzzy[:10]}", flush=True)
                except Exception as e:
                    out["notes"].append(f"dataset {name} exc: {str(e)[:80]}")
        except Exception as e:
            out["notes"].append(f"cat={cat} exc: {str(e)[:80]}")
    out["verdict"] = ("FOUND in " + ",".join(out["found_in"])) if out["found_in"] else "NOT FOUND in any checked dataset"
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "field_origin_diag.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("VERDICT:", out["verdict"], flush=True)


asyncio.run(main())
