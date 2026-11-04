# -*- coding: utf-8 -*-
import os, sys, json, asyncio
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32": sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import main as B
B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

async def main():
    await B.brain_client.ensure_authenticated()
    r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/users/self/alphas?limit=3&offset=0&stage=OS", timeout=90)
    print("HTTP", r.status_code)
    j = r.json()
    rows = j.get("results") or []
    print("n rows", len(rows), "count", j.get("count"))
    if rows:
        x = rows[0]
        print("TOP KEYS:", sorted(x.keys()))
        print("IS KEYS:", sorted((x.get("is") or {}).keys()) if isinstance(x.get("is"),dict) else type(x.get("is")))
        print("CHECKS type:", type(x.get("checks")))
        print(json.dumps(x.get("checks"), ensure_ascii=False)[:800])
        print("IS.CHECKS:", json.dumps((x.get("is") or {}).get("checks"), ensure_ascii=False)[:800] if isinstance(x.get("is"),dict) else None)
        print("CODE:", str(x.get("code"))[:200])
asyncio.run(main())
