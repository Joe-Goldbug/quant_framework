# -*- coding: utf-8 -*-
"""检查 NONE 档基本面 alpha 的 σ 是否真实（排除 fnd69 冻结 PnL 伪影）。"""
import json, os, sys, io, re, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\brain-mcp"); sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"]=r"D:\brain-mcp\user_config.json"
import main as B
B.brain_client.session.trust_env=False; B.brain_client.session.proxies={}

recs=json.load(open("account_alpha_history_v2.json",encoding="utf-8"))
full=json.load(open("account_alpha_history_full.json",encoding="utf-8"))
code_of={r["id"]:(r.get("code") or "") for r in full}
for r in recs: r["n_fail"]=len(r["fails"])

def ds_of(c): return sorted(set(re.findall(r"\b([a-z]+\d+)_[a-z0-9_]+", c or "")))
def fund(r): return any(d.startswith(("fnd","oth")) for d in ds_of(code_of.get(r["id"],"")))

u=[r for r in recs if r["universe"]=="TOP1000" and r["delay"]==1 and fund(r)]
NONE=[r for r in u if r["neutralization"]=="NONE"]
NONE.sort(key=lambda r:-(r["sharpe"] or 0))
print("NONE 档基本面 alpha, Sh>=0.8, 按 Sh 降序（前 12）:")
cands=[]
for r in NONE:
    if (r["sharpe"] or 0) >= 0.8:
        cands.append(r)
for r in cands[:12]:
    sg=(r["returns"]/r["sharpe"]) if (r["sharpe"] or 0)>0.2 else 0
    print(f"  {r['id']:<10} Sh={r['sharpe']:>5.2f} Fit={r['fitness']:>5.2f} σ={sg*100:>6.2f}% TO={(r['turnover'] or 0)*100:>6.2f}% Ret={(r['returns'] or 0)*100:>7.2f}% fail={r['n_fail']} {ds_of(code_of.get(r['id'],''))}")
    print(f"      {code_of.get(r['id'],'')[:140]}")

async def main():
    await B.brain_client.ensure_authenticated()
    print("\n=== 抽查 NONE 档高 Sharpe 基本面 alpha 的年度剖面（识别冻结伪影）===")
    for r in cands[:6]:
        aid=r["id"]
        resp=await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}/recordsets/yearly-stats", timeout=60)
        try: j=resp.json()
        except Exception: print(f"  {aid}: 无 yearly-stats"); continue
        rows=j.get("records") or []
        pos=sum(1 for y in rows if (y.get("returns") or 0)>0)
        dead=sum(1 for y in rows if (y.get("longCount") or 0)+(y.get("shortCount") or 0)==0)
        rets=[(y.get("year"), (y.get("returns") or 0)*100, y.get("longCount"), y.get("shortCount")) for y in rows]
        print(f"  {aid} 正收益年 {pos}/{len(rows)}  零持仓年 {dead}/{len(rows)}  Sh={r['sharpe']:.2f}")
        for yr,rt,lc,sc in rets:
            flag=" <<< 零持仓" if (lc or 0)+(sc or 0)==0 else (" <<< 极端" if abs(rt)>25 else "")
            print(f"      {yr} Ret={rt:>8.2f}%  long={lc:<5} short={sc:<5}{flag}")
        await asyncio.sleep(0.35)
asyncio.run(main())
