# -*- coding: utf-8 -*-
"""对撞组逐行 diff：找出 FAIL vs WARNING 的真实判别变量。"""
import json, os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\brain-mcp"); sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"]=r"D:\brain-mcp\user_config.json"
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}

recs=json.load(open("account_alpha_history_v2.json",encoding="utf-8"))
for r in recs: r["n_fail"]=len(r["fails"]); r["n_warn"]=len(r["warns"])
u=[r for r in recs if r["universe"]=="TOP1000" and r["delay"]==1 and r["neutralization"]=="STATISTICAL"]
F=[r for r in u if "LOW_SHARPE" in r["fails"] and 1.35<=(r["sharpe"] or -9)<=1.45]
W=[r for r in u if "LOW_SHARPE" in r["warns"] and 1.35<=(r["sharpe"] or -9)<=1.45]
print("FAIL组 n=%d, WARN组 n=%d"%(len(F),len(W)))
picks=[("FAIL",x) for x in F[:3]]+[("WARN",x) for x in W[:3]]

async def main():
    await B.brain_client.ensure_authenticated()
    for tag,r in picks:
        aid=r["id"]
        resp=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}", timeout=60)
        x=resp.json(); isd=x.get("is") or {}
        st=x.get("settings") or {}
        print("="*118)
        print(f"[{tag}] {aid}  date={r.get('dateCreated','')[:19]}")
        print(f"   code: {(x.get('regular') or {}).get('code','')[:130]}")
        print(f"   settings: neut={st.get('neutralization')} decay={st.get('decay')} trunc={st.get('truncation')} nan={st.get('nanHandling')} maxTrade={st.get('maxTrade')} pasteur={st.get('pasteurization')} unit={st.get('unitHandling')}")
        print(f"   metrics: Sh={isd.get('sharpe')} Fit={isd.get('fitness')} TO={isd.get('turnover')} Ret={isd.get('returns')} Mgn={isd.get('margin')} long={isd.get('longCount')} short={isd.get('shortCount')}")
        for c in (isd.get("checks") or []):
            if c.get("result") in ("FAIL","WARNING"):
                print(f"      {c.get('result'):<8}{c.get('name'):<28} value={c.get('value')} limit={c.get('limit')} year={c.get('year')} {c.get('startDate') or ''}{c.get('endDate') or ''}")
        await asyncio.sleep(0.4)
asyncio.run(main())
