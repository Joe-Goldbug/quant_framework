# -*- coding: utf-8 -*-
import json, os, sys, io, re, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\brain-mcp"); sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"]=r"D:\brain-mcp\user_config.json"
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}

def parse(j):
    """yearly-stats 返回 schema+records(数组) 或 records(dict)。"""
    if isinstance(j, dict):
        sch=j.get("schema") or {}
        props=[p.get("name") for p in (sch.get("properties") or [])]
        recs=j.get("records") or []
        if recs and isinstance(recs[0], list):
            return [dict(zip(props,r)) for r in recs]
        return recs
    return j

IDS=["xAr0rmLJ","d5WAWlGJ","N1N9mweo","winsorize", "wpQgJeld"]
IDS=["xAr0rmLJ","d5WAWlGJ","N1N9mweo","wpQgJeld","d5WAWlNw"]
async def main():
    await B.brain_client.ensure_authenticated()
    for aid in IDS:
        resp=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}/recordsets/yearly-stats", timeout=60)
        try: rows=parse(resp.json())
        except Exception as e: print(f"  {aid}: ERR {e}"); continue
        if not rows: print(f"  {aid}: empty"); continue
        pos=sum(1 for y in rows if (y.get("returns") or 0)>0)
        dead=sum(1 for y in rows if ((y.get("longCount") or 0)+(y.get("shortCount") or 0))==0)
        print("="*96); print(f"{aid}  正收益年 {pos}/{len(rows)}  零持仓年 {dead}/{len(rows)}")
        for y in rows:
            rt=(y.get("returns") or 0)*100; lc=y.get("longCount"); sc=y.get("shortCount")
            f=" <<< 零持仓" if (lc or 0)+(sc or 0)==0 else (" <<< 极端" if abs(rt)>25 else "")
            print(f"   {y.get('year')}  Ret={rt:>8.2f}%  Sh={y.get('sharpe'):>6.2f}  long={lc:<5} short={sc:<5}{f}")
        await asyncio.sleep(0.35)
asyncio.run(main())
