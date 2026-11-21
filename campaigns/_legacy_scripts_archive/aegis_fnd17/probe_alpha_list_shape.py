# -*- coding: utf-8 -*-
"""探针：检查 /users/self/alphas 列表行到底带哪些字段（是否有 code / expression）。

v2 bug 实锤：1410 条抓下来但 fnd17 过滤出 0 条，而 3qVlb3dN 明明是 fnd17 且 OS/ACTIVE
⇒ 说明列表行的 `code` 字段为空/缺失 ⇒ 字符串过滤必然失效。
本探针只打 1 页，打印完整键集与 2 个样本行。
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


async def main():
    await B.brain_client.ensure_authenticated()
    url = (f"{B.brain_client.base_url}/users/self/alphas"
           f"?limit=5&offset=0&stage=OS")
    r = await B.brain_client._request("GET", url, timeout=90)
    print("HTTP", r.status_code)
    j = r.json()
    print("top keys:", list(j.keys()))
    rows = j.get("results") or []
    print("n rows:", len(rows))
    if rows:
        print("\n=== ROW KEYS ===")
        for k in sorted(rows[0].keys()):
            print(f"  {k}")
        print("\n=== ROW 0 (full) ===")
        print(json.dumps(rows[0], ensure_ascii=False, indent=1)[:2500])
        print("\n=== ROW 1 id/code ===")
        for i in range(min(3, len(rows))):
            print(" ", rows[i].get("id"), "|code=", repr(rows[i].get("code"))[:120],
                  "|name=", repr(rows[i].get("name"))[:80])

    # 试 name 过滤：fnd17 可能在 name 里
    for q in ("name=fnd17", "search=fnd17"):
        u = f"{B.brain_client.base_url}/users/self/alphas?limit=5&offset=0&stage=OS&{q}"
        rr = await B.brain_client._request("GET", u, timeout=90)
        try:
            jj = rr.json()
            n = len(jj.get("results") or []) if isinstance(jj, dict) else "n/a"
            cnt = jj.get("count") if isinstance(jj, dict) else None
            print(f"\n[{q}] HTTP {rr.status_code} count={cnt} rows={n}")
            if isinstance(jj, dict) and jj.get("results"):
                print("   ids:", [x.get("id") for x in jj["results"]])
                print("   names:", [x.get("name") for x in jj["results"]])
        except Exception as e:
            print(f"\n[{q}] HTTP {rr.status_code} parse err {e} {rr.text[:200]}")


asyncio.run(main())
