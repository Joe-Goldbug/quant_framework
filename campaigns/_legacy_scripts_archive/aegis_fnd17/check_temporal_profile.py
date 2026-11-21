# -*- coding: utf-8 -*-
"""零成本时间剖面诊断：年度收益 + 2Y ladder 逐窗。

要回答的问题（本战役从未直接查过）：
  ① 该信号的收益是否集中在个别年份？（若是 ⇒ 2Y ladder 与"8/10 正收益年"必然不过）
  ② 2Y ladder 每一窗的真实值 —— 平台的 LOW_2Y_SHARPE 检查到底卡在哪一窗？
  ③ 是否存在"近两年塌陷"（信号衰减）还是"全程偏弱"（信号本身弱）？
     ⇒ 前者要改结构（换更快的字段/缩短衰减），后者只能换核。

只 GET，零配额。
"""
import json
import os
import sys
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

CASES = [
    ("STAT d0 ON  (天花板)", "VkxJo7R0"),
    ("MKT  d0 ON  (最接近门禁)", "ZYQGLgQd"),
    ("MKT  d8 ON  (Mgn最高)", "e75RJabp"),
    ("EUR 冠军 3qVlb3dN", "3qVlb3dN"),
]


async def yearly(aid):
    r = await B.brain_client._request("GET",
                                       f"{B.brain_client.base_url}/alphas/{aid}/recordsets/yearly-stats",
                                       timeout=60)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:100]}"
    return r.json(), None


async def main():
    await B.brain_client.ensure_authenticated()
    for label, aid in CASES:
        print("=" * 118)
        print(f"{label}  ·  {aid}")
        print("=" * 118)
        j, err = await yearly(aid)
        if err:
            print(f"  yearly-stats 不可用: {err}")
        else:
            rows = j if isinstance(j, list) else (j.get("yearly-stats") or j.get("results") or [])
            print(f"  {'年份':<8}{'收益%':>10}{'Sharpe':>10}{'回撤%':>10}{'换手%':>9}")
            pos = 0
            for y in rows:
                if not isinstance(y, dict):
                    continue
                yr = y.get("year") or y.get("date") or "?"
                sh = y.get("sharpe")
                rt = y.get("returns")
                dd = y.get("drawdown")
                to = y.get("turnover")
                if rt is not None and rt > 0:
                    pos += 1
                print(f"  {str(yr):<8}"
                      f"{(rt*100 if isinstance(rt,(int,float)) else 0):>10.2f}"
                      f"{(sh if isinstance(sh,(int,float)) else 0):>10.2f}"
                      f"{(dd*100 if isinstance(dd,(int,float)) else 0):>10.2f}"
                      f"{(to*100 if isinstance(to,(int,float)) else 0):>9.2f}")
            print(f"  ⇒ 正收益年份 {pos}/{len(rows)}（门禁要求 ≥8/10）")

        # 2Y ladder：checks 数组里的 IS_LADDER_SHARPE 项
        r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}",
                                           timeout=60)
        x = r.json()
        isd = x.get("is") or {}
        m = isd.get("metrics") if isinstance(isd.get("metrics"), dict) else isd
        print(f"\n  raw: Sh={m.get('sharpe')} 2Y={m.get('two_year_sharpe')} "
              f"ladder_window={m.get('two_year_ladder_window')} "
              f"SubU={m.get('sub_universe_sharpe')} RobU={m.get('robust_universe_sharpe')}")
        lad = [c for c in (isd.get("checks") or [])
               if isinstance(c, dict) and "LADDER" in str(c.get("name", "")).upper()]
        if lad:
            print("  2Y ladder 逐窗（checks 中的 IS_LADDER_SHARPE）:")
            for c in lad:
                print(f"    name={c.get('name')} result={c.get('result')} "
                      f"value={c.get('value')} limit={c.get('limit')} "
                      f"year={c.get('year')} {c.get('startDate')}→{c.get('endDate')}")
        else:
            print("  （本 alpha 无 IS_LADDER_SHARPE 检查项）")
        await asyncio.sleep(0.3)


asyncio.run(main())
