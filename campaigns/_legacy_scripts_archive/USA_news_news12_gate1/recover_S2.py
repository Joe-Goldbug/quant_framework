# -*- coding: utf-8 -*-
"""回收 Wave9-S2 批次 (未回收): location 4mfQWzVN5b59A1qJln3fV3, decay=6.

该批已于 2026-10-24 23:49 提交并完成回测, 但轮询进程被中断导致结果从未落盘.
本次仅做只读 fetch, 不消耗任何新回测配额.
"""
import asyncio
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule  # noqa: E402

LOCATION = "https://api.worldquantbrain.com/simulations/4mfQWzVN5b59A1qJln3fV3"
BATCH_FILE = os.path.join(BASE, "batch_gate9_S2_INDUSTRY_1792856973.json")


async def main():
    items = json.load(open(BATCH_FILE, encoding="utf-8"))["items"]
    chk = await BrainModule.check_multi_simulation(LOCATION)
    print(f"[status] {chk.get('status')} progress={chk.get('progress')}", flush=True)
    fetch = await BrainModule.fetch_multi_simulation_result(LOCATION)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[fetch] 空: {str(fetch)[:400]}", flush=True)
        return
    out = os.path.join(BASE, "batch_gate9_S2_INDUSTRY_1792856973_result.json")
    json.dump({"alpha_results": results}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[saved] {out}  ({len(results)} 条)", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>10} {'raFail':>6}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ra = r.get("ra") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        print(f"{it['id']:>2} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} "
              f"{to * 100:>7.1f} {ret * 100:>7.2f} {(ret / to) if to else 0:>6.3f} "
              f"{m.get('two_year_sharpe') or 0:>6.2f} {m.get('sub_universe_sharpe') or 0:>5.2f} "
              f"{m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10} "
              f"{str(ra.get('ra_failed')):>6}", flush=True)
        ch = r.get("checks") or {}
        f_names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w_names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f_names:
            print(f"     fail: {f_names}", flush=True)
        if w_names:
            print(f"     warn: {w_names}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
