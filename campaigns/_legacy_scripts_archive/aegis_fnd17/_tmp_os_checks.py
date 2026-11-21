# -*- coding: utf-8 -*-
"""查看已提交 OS alpha 的完整 checks 列表（含 DATA_DIVERSITY / MATCHES_PYRAMID 等），确认基本面数据集是否可提交。"""
import json, os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\brain-mcp"); sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"]=r"D:\brain-mcp\user_config.json"
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}
IDS=["3qVlb3dN","mLYX6n5x","d5Kb8zRw","2rjRlvbZ"]
async def main():
    await B.brain_client.ensure_authenticated()
    for aid in IDS:
        r=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}", timeout=60)
        if r.status_code!=200: print(aid,"HTTP",r.status_code); continue
        x=r.json(); isd=x.get("is") or {}
        print("="*104)
        print(aid, "stage",x.get("stage"),"status",x.get("status"))
        print("  code:", (x.get("regular") or {}).get("code","")[:130])
        print("  classifications:", json.dumps(x.get("classifications"),ensure_ascii=False)[:200])
        print("  pyramids:", json.dumps(x.get("pyramids"),ensure_ascii=False)[:300])
        print("  themes:", json.dumps(x.get("themes"),ensure_ascii=False)[:200])
        for c in (isd.get("checks") or []):
            print(f"    {str(c.get('result')):<8}{str(c.get('name')):<30} value={c.get('value')} limit={c.get('limit')} {c.get('year') or ''}")
        await asyncio.sleep(0.4)
asyncio.run(main())
