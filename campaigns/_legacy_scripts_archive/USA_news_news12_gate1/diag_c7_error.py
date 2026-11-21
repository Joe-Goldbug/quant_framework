# -*- coding: utf-8 -*-
"""诊断 C 批 slot7 (group_mean) 的 BRAIN 侧 ERROR 明细 + 检查 group 算子在 news 类目的可用性。"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule


async def main():
    child = "https://api.worldquantbrain.com/simulations/2QCCc0g585c78DdhOtvSgv6"
    print("== fetch child detail ==")
    try:
        r = await BrainModule.fetch_multi_simulation_result(child)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
    except Exception as e:
        print("fetch err:", e)
    # 试 GET 单模拟
    for fn in ("check_simulation", "get_simulation"):
        f = getattr(BrainModule, fn, None)
        if f:
            try:
                r = await f(child)
                print(f"== {fn} ==")
                print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
            except Exception as e:
                print(f"{fn} err:", e)


if __name__ == "__main__":
    asyncio.run(main())
