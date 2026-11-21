# -*- coding: utf-8 -*-
"""
结果抓取器 (GET-only Result Fetcher)

用途：把已完成的 multisimulation 的 8 条子结果原样落盘到战役目录，
供 audit_normalize.py 做权威门禁裁决。

只读 GET，不发任何仿真 —— 零配额消耗。
"""
import asyncio
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as bm  # noqa: E402


async def main():
    sim_id = sys.argv[1]
    out_name = sys.argv[2]
    location = f"https://api.worldquantbrain.com/simulations/{sim_id}"

    chk = await bm.check_multi_simulation(location)
    print(f"[status] {chk.get('status')} children={chk.get('n_children')}")

    fetched = await bm.fetch_multi_simulation_result(location)
    results = fetched.get("alpha_results", [])
    print(f"[fetch] {len(results)} child results")

    out = os.path.join(HERE, out_name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "multisimulation_id": sim_id,
            "status": chk.get("status"),
            "total_requested": fetched.get("total_requested"),
            "total_created": fetched.get("total_created"),
            "simulation_only": True,
            "alpha_submission_calls": 0,
            "alpha_results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
