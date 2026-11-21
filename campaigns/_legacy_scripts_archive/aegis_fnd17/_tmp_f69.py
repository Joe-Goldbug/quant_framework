import os,sys,json,asyncio
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform=="win32": sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}
IDS=["xAr0rmLJ","d5WAWlGJ","N1N9mweo","LLMJq3Xa","O0AOgQgR"]
async def main():
    await B.brain_client.ensure_authenticated()
    for aid in IDS:
        r=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}", timeout=60)
        if r.status_code!=200: print(aid,"HTTP",r.status_code); continue
        x=r.json(); isd=x.get("is") or {}
        print("="*100); print(aid, (x.get("regular") or {}).get("code"))
        st=x.get("settings") or {}
        print("  settings:", st.get("neutralization"), "d",st.get("decay"),"nan",st.get("nanHandling"),"trunc",st.get("truncation"),"univ",st.get("universe"),"reg",st.get("region"),"delay",st.get("delay"))
        print("  metrics:", json.dumps({k:v for k,v in isd.items() if k not in ("checks","pnl")},ensure_ascii=False)[:700])
        for c in (isd.get("checks") or []):
            print(f"    {c.get('name'):<28} {c.get('result'):<8} value={c.get('value')} limit={c.get('limit')} {c.get('year') or ''} {c.get('startDate') or ''}{c.get('endDate') or ''}")
        await asyncio.sleep(0.4)
asyncio.run(main())
