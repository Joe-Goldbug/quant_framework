# -*- coding: utf-8 -*-
"""免费证据采集：抓取本账户全部 alpha（IS+OS），筛出 fnd17 家族，按结构/设置归因。

不消耗任何回测配额（只 GET）。
目的：在再花配额之前，把"fundamental17 在本账户历史上到底什么结构能赢"摸清楚。
"""
import json
import os
import sys
import asyncio

ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}


async def fetch_all(stage):
    out = []
    url = f"{B.brain_client.base_url}/users/self/alphas?limit=100&offset=0&stage={stage}"
    while url:
        r = await B.brain_client._request("GET", url, timeout=90)
        if r.status_code != 200:
            print(f"  ! {stage} HTTP {r.status_code} {r.text[:120]}")
            break
        j = r.json()
        out.extend(j.get("results") or [])
        nxt = j.get("next")
        url = nxt if (nxt and str(nxt).startswith("http")) else None
        print(f"  {stage}: {len(out)}")
    return out


async def main():
    await B.brain_client.ensure_authenticated()
    allrows = []
    for stage in ("OS", "IS"):
        allrows.extend(await fetch_all(stage))

    f17 = [x for x in allrows if "fnd17" in (x.get("code") or "")]
    print(f"\n总计 {len(allrows)} 条 alpha，其中 fnd17 {len(f17)} 条")

    recs = []
    for x in f17:
        st = x.get("settings") or {}
        m = x.get("metrics") or (x.get("is") or {})
        recs.append({
            "id": x.get("id"), "code": x.get("code"), "stage": x.get("stage"),
            "status": x.get("status"), "region": st.get("region"), "universe": st.get("universe"),
            "delay": st.get("delay"), "decay": st.get("decay"), "neutralization": st.get("neutralization"),
            "truncation": st.get("truncation"), "nanHandling": st.get("nanHandling"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": m.get("turnover"),
            "returns": m.get("returns"), "margin": m.get("margin"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
            "checks_fail": [c.get("name") for c in ((x.get("checks") or {}).get("fail") or [])],
            "prod_corr": m.get("prodCorrelation"), "self_corr": m.get("selfCorrelation"),
        })

    recs.sort(key=lambda r: -(r["sharpe"] or 0))
    out_file = os.path.join(ROOT, "campaigns", "aegis_fnd17", "fnd17_history_mined.json")
    json.dump(recs, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n{'id':<11}{'reg':<5}{'univ':<10}{'stg':<4}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>7}"
          f"{'Mgn':>7}{'2Y':>6}{'dec':>5}{'neut':<12}{'nan':<4}{'fail'}")
    for r in recs:
        print(f"{r['id'] or '':<11}{r['region'] or '':<5}{r['universe'] or '':<10}{r['stage'] or '':<4}"
              f"{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}{(r['turnover'] or 0)*100:>7.2f}"
              f"{(r['returns'] or 0)*100:>7.2f}{(r['margin'] or 0)*10000:>7.2f}"
              f"{(r['two_year_sharpe'] or 0):>6.2f}{r['decay']:>5}{r['neutralization'] or '':<12}"
              f"{r['nanHandling'] or '':<4}{r['checks_fail']}")
    print(f"\n💾 -> {out_file}")


asyncio.run(main())
