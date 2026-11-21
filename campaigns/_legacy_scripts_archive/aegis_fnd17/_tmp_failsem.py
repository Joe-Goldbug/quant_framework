import os,sys,json,asyncio
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform=="win32": sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}
# one with real FAILs (MARKET tier ZYQGLgQd) vs fnd69 xAr0rmLJ vs STATISTICAL LLMJq3Xa
IDS=["ZYQGLgQd","xAr0rmLJ","LLMJq3Xa","d5WAWlGJ"]
async def main():
    await B.brain_client.ensure_authenticated()
    for aid in IDS:
        r=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}", timeout=60)
        x=r.json()
        print("="*90); print(aid, "stage",x.get("stage"),"status",x.get("status"))
        print("  ra:", json.dumps(x.get("ra"),ensure_ascii=False)[:400])
        print("  classifications:", json.dumps(x.get("classifications"),ensure_ascii=False)[:300])
        print("  pyramids:", json.dumps(x.get("pyramids"),ensure_ascii=False)[:300])
        isd=x.get("is") or {}
        for c in (isd.get("checks") or []):
            if c.get("result") in ("FAIL","WARNING"):
                print(f"    {c.get('result'):<8}{c.get('name'):<28} value={c.get('value')} limit={c.get('limit')}")
        await asyncio.sleep(0.4)
asyncio.run(main())
