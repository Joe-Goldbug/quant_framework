# -*- coding: utf-8 -*-
"""诊断 Gate2-F 批 7 个 ERROR 子模拟: 逐 child 拉取 message, 定位无效字段/算子。"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule  # noqa: E402

CHILDREN = [
    ("F1_CTRL(cancelled)", "https://api.worldquantbrain.com/simulations/jIUZq5MP4Xo9DjVqAR0AE6"),
    ("F2_SPEED_1PCT", "https://api.worldquantbrain.com/simulations/2GHpbs3rD57Haul1aZP5RVjl"),
    ("F3_SPEED_2PCT", "https://api.worldquantbrain.com/simulations/3SAvARcB54GMbiZlI9YIjtf"),
    ("F4_SPEED_20D", "https://api.worldquantbrain.com/simulations/1Ia5dH1zk4xsbbnFppeq24d"),
    ("F5_EXCESS_2DAY", "https://api.worldquantbrain.com/simulations/3Skg6heZy4onbGdGMuss1We"),
    ("F6_GAP_SPIKE", "https://api.worldquantbrain.com/simulations/2dtgql6J24QMa1r8yvzzkRd"),
    ("F7_PRENEWS_RANGE", "https://api.worldquantbrain.com/simulations/Cq4wE4li4VFbLOPKCoB8eS"),
    ("F8_TREND_ASYM", "https://api.worldquantbrain.com/simulations/4aLy6cdbo59z8WC13ZRyAPDD"),
]


async def main():
    for name, loc in CHILDREN:
        try:
            r = await BrainModule.check_simulation(loc)
            print(f"{name}: status={r.get('status')} msg={str(r.get('message'))[:220]}")
        except Exception as e:
            print(f"{name}: ERR {str(e)[:150]}")


if __name__ == "__main__":
    asyncio.run(main())
