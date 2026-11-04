"""AEGIS diagnostic: confirm which OUTER OPERATOR retains signal with the
UNFLIPPED core (subtract(max, median_3)) under COUNTRY neutralization.

Expressions are HARD-CODED by hand (no loop/template formula generation).
This script only submits pre-written tests and writes results to disk.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import importlib.util
_spec = importlib.util.spec_from_file_location("brain_mcp_main", r"D:\brain-mcp\main.py")
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)

REGION = "GLB"
UNIVERSE = "MINVOL1M"
DELAY = 1
NEUT = "COUNTRY"
DECAY = 0
TRUNCATION = 0.025
NAN_HANDLING = "ON"

CORE = "divide(subtract(negative_score_maximum_value, negative_score_median_value_3), add(negative_score_average_value, 1))"

# Hard-coded tests (each submitted as a 2-copy batch to satisfy >=2 exprs rule)
TESTS = [
    ("T1_rank_w20_sub",  "group_rank(ts_scale(" + CORE + ", 20), subindustry)"),
    ("T2_rank_w10_sub",  "group_rank(ts_scale(" + CORE + ", 10), subindustry)"),
    ("T3_rank_w20_ind",  "group_rank(ts_scale(" + CORE + ", 20), industry)"),
    ("T4_zscore_w20_sub","group_zscore(ts_scale(" + CORE + ", 20), subindustry)"),
    ("T5_zscore_w20_ind","group_zscore(ts_scale(" + CORE + ", 20), industry)"),
    ("T6_neut_w20_sub",  "group_neutralize(ts_scale(" + CORE + ", 20), subindustry)"),
    ("T7_neut_w20_ind",  "group_neutralize(ts_scale(" + CORE + ", 20), industry)"),
]

RESULTS = {}
RESULT_PATH = os.path.join(os.path.dirname(__file__), "diag_unflip2.json")

def _is_proxy_err(e):
    s = str(e).lower()
    return ("502" in s) or ("proxy" in s) or ("remote end closed" in s) or ("max retries" in s)

async def submit_with_retry(expr):
    batch = [expr, expr]
    for attempt in range(6):
        try:
            res = await bm.submit_multi_simulation(
                alpha_expressions=batch,
                region=REGION, universe=UNIVERSE, delay=DELAY,
                decay=DECAY, neutralization=NEUT, truncation=TRUNCATION,
                pasteurization="ON", unit_handling="VERIFY",
                nan_handling=NAN_HANDLING, language="FASTEXPR",
                visualization=False,
            )
            if "error" in res:
                print(f"  submit error: {res['error']}; retry {attempt}")
                await asyncio.sleep(20)
                continue
            return res.get("location")
        except Exception as e:
            print(f"  submit exception: {e}; retry {attempt}")
            await asyncio.sleep(20)
    return None

async def check_fetch_with_retry(loc):
    for attempt in range(8):
        try:
            chk = await bm.check_multi_simulation(loc)
            status = chk.get("status")
            if status in ("COMPLETE", "COMPLETED", "DONE"):
                fetch = await bm.fetch_multi_simulation_result(loc)
                return fetch.get("alpha_results", [])
            if status in ("ERROR", "CANCELLED"):
                return [{"status": status}]
            await asyncio.sleep(20)
        except Exception as e:
            print(f"  poll exception: {e}; retry {attempt}")
            await asyncio.sleep(15)
    return None

async def run_one(name, expr):
    print(f"\n=== {name}: {expr}")
    loc = await submit_with_retry(expr)
    if not loc:
        RESULTS[name] = {"expr": expr, "status": "SUBMIT_FAILED"}
        _dump()
        return
    print(f"  loc={loc}")
    res = await check_fetch_with_retry(loc)
    if res is None:
        RESULTS[name] = {"expr": expr, "status": "POLL_TIMEOUT"}
    else:
        # de-dup 2-copy batch; take first with metrics
        best = None
        for r in res:
            m = r.get("metrics") or {}
            if m.get("sharpe") is not None:
                best = {"status": r.get("status"), "sharpe": m.get("sharpe"),
                        "fitness": m.get("fitness"), "turnover": m.get("turnover")}
                break
        if best is None:
            best = {"status": (res[0].get("status") if res else "NONE")}
        RESULTS[name] = {"expr": expr, **best}
    _dump()
    print(f"  -> {RESULTS[name]}")

def _dump():
    with open(RESULT_PATH, "w") as f:
        json.dump(RESULTS, f, indent=2)

async def main():
    _dump()
    for name, expr in TESTS:
        await run_one(name, expr)
    print("\nDONE. Results written to", RESULT_PATH)

if __name__ == "__main__":
    asyncio.run(main())
