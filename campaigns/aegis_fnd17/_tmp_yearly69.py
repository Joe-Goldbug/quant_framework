import os,sys,json,asyncio
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform=="win32": sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}
IDS=[("fnd69 xAr0rmLJ","xAr0rmLJ"),("fnd69 d5WAWlGJ","d5WAWlGJ"),("fnd69 d5WAWlNw","d5WAWlNw"),("fnd17 LLMJq3Xa","LLMJq3Xa")]
async def main():
    await B.brain_client.ensure_authenticated()
    for lbl,aid in IDS:
        r=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}/recordsets/yearly-stats", timeout=60)
        print("="*100); print(lbl, aid, "HTTP", r.status_code)
        if r.status_code!=200: print(r.text[:200]); continue
        j=r.json()
        rows=j if isinstance(j,list) else (j.get("yearly-stats") or j.get("results") or [])
        pos=0
        for y in rows:
            if not isinstance(y,dict): continue
            yr=y.get("year") or y.get("date") or "?"
            sh=y.get("sharpe"); rt=y.get("returns"); dd=y.get("drawdown"); to=y.get("turnover")
            if rt is not None and rt>0: pos+=1
            print(f"   {str(yr):<8} Sh={(sh if isinstance(sh,(int,float)) else 0):>6.2f} Ret={(rt*100 if isinstance(rt,(int,float)) else 0):>7.2f}% DD={(dd*100 if isinstance(dd,(int,float)) else 0):>6.2f}% TO={(to*100 if isinstance(to,(int,float)) else 0):>6.2f}%")
        print(f"   ⇒ 正收益年份 {pos}/{len(rows)}  (房规要求 ≥8/10)")
        await asyncio.sleep(0.4)
asyncio.run(main())
