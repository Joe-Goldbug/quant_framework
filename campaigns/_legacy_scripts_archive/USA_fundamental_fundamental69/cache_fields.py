# -*- coding: utf-8 -*-
"""
基本面数据集字段表缓存器 (GET-only)

把候选数据集的完整字段表落盘，供离线筛选（避免 MCP 返回塞爆上下文）。
只读，不消耗仿真配额。
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

OUTDIR = os.path.join(HERE, "field_cache")
os.makedirs(OUTDIR, exist_ok=True)

REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1

TARGETS = [
    "fundamental45", "fundamental89", "fundamental28", "fundamental23",
    "fundamental14", "fundamental110", "fundamental13", "fundamental3",
    "fundamental2", "fundamental6", "fundamental1", "fundamental22",
    "fundamental7", "fundamental72", "other466", "other401", "other395",
]


async def main():
    for ds in TARGETS:
        out = os.path.join(OUTDIR, f"{ds}.json")
        if os.path.exists(out):
            print(f"[skip] {ds} cached")
            continue
        try:
            data = await bm.brain_client.get_datafields(
                dataset_id=ds, region=REGION, universe=UNIVERSE, delay=DELAY,
                data_type="", filter_sharpe=False,
            )
            res = data.get("results", []) if isinstance(data, dict) else []
            with open(out, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            print(f"[ok] {ds}: {len(res)} fields")
        except Exception as e:
            print(f"[fail] {ds}: {str(e)[:160]}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
