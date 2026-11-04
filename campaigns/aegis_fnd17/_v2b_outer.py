# -*- coding: utf-8 -*-
"""Isolate outer-operator effect on sigma/Sharpe, conditional on inner group_rank."""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
def sig(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9: return None
    return abs(ret)/abs(sh)
def ops(code):
    try: t = ast.parse(code, mode="eval")
    except Exception: return []
    return [getattr(n.func,"id","") or getattr(n.func,"attr","") for n in ast.walk(t) if isinstance(n, ast.Call)]
def top(code):
    try: t = ast.parse(code, mode="eval")
    except Exception: return None
    b=t.body
    root = b if isinstance(b, ast.Call) else (b.value if isinstance(b, ast.Expression) and isinstance(b.value, ast.Call) else None)
    return getattr(root.func,"id","") if root is not None else None

S=[a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1 and a.get("neutralization")=="STATISTICAL"]
rows=[(a,sig(a)) for a in S]; rows=[(a,s) for a,s in rows if s is not None]

print("=== outer op effect, CONDITIONAL on inner group_rank present ===")
grp=[(a,s) for a,s in rows if "group_rank" in ops(a.get("code") or "")]
print(f"  base cohort (inner group_rank) n={len(grp)} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in grp]):.2f} "
      f"medSig={statistics.median([s for _,s in grp])*100:.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in grp])*100:.2f}%")
bytop=collections.defaultdict(list)
for a,s in grp:
    t=top(a.get("code") or "")
    if t: bytop[t].append((a,s))
for t,v in sorted(bytop.items(), key=lambda kv:-len(kv[1])):
    sh=[a.get("sharpe") or 0 for a,_ in v]; sg=[s for _,s in v]; to=[a.get("turnover") or 0 for a,_ in v]
    hi=[x for x in v if x[1]>=0.0317]
    print(f"   outer={t:16s} n={len(v):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median(to)*100:5.2f}% n(sig>=3.17)={len(hi):3d} maxSh@sig>=3.17={max([a.get('sharpe') or 0 for a,_ in hi],default=0):5.2f}")

print("\n=== champion skeleton variants (power(subtract(group_rank, multiply(0.5,group_rank)),k)) ===")
CH=re.compile(r"power\(subtract\(group_rank\(", re.S)
for k in [1,2,3,4,5]:
    sel=[(a,s) for a,s in rows if (a.get("code") or "") and CH.search(a.get("code") or "") and re.search(r"power\([^,]+,\s*"+str(k)+r"\)", a.get("code") or "")]
    if not sel: continue
    sh=[a.get("sharpe") or 0 for a,_ in sel]; sg=[s for _,s in sel]
    print(f"   k={k} n={len(sel):3d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% maxSig={max(sg)*100:5.2f}% "
          f"medTO={statistics.median([a.get('turnover') or 0 for a,_ in sel])*100:5.2f}% medFit={statistics.median([a.get('fitness') or 0 for a,_ in sel]):5.2f}")

print("\n=== s_log_1p at top: which inner structures? ===")
for a,s in sorted([x for x in rows if top(x[0].get("code") or "")=="s_log_1p"], key=lambda x:-(x[0].get('sharpe') or 0))[:10]:
    print(f"   {a['id']} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% TO {a.get('turnover'):.4f} inner={sorted(set(ops(a.get('code') or ''))-{'s_log_1p'})}")
    print(f"      {(a.get('code') or '')[:190]}")

print("\n=== winsorize OUTER (on top of a group_rank spread) ===")
sel=[(a,s) for a,s in rows if "winsorize" in ops(a.get("code") or "") and "group_rank" in ops(a.get("code") or "")]
print(f"   n={len(sel)} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in sel]):.2f} medSig={statistics.median([s for _,s in sel])*100:.2f}%")
for a,s in sorted(sel,key=lambda x:-(x[0].get('sharpe') or 0))[:5]:
    print(f"   {a['id']} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% TO {a.get('turnover'):.4f} :: {(a.get('code') or '')[:170]}")

print("\n=== how many STAT alphas use ts_backfill? sigma & Sh ===")
tb=[(a,s) for a,s in rows if "ts_backfill" in ops(a.get("code") or "")]
nb=[(a,s) for a,s in rows if "ts_backfill" not in ops(a.get("code") or "")]
print(f"   with ts_backfill n={len(tb)} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in tb]):.2f} medSig={statistics.median([s for _,s in tb])*100:.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in tb])*100:.2f}%")
print(f"   without         n={len(nb)} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in nb]):.2f} medSig={statistics.median([s for _,s in nb])*100:.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in nb])*100:.2f}%")

print("\n=== decay 0/4/8 vs sigma & TO, conditional inner group_rank + top power ===")
sel=[(a,s) for a,s in rows if "group_rank" in ops(a.get("code") or "") and top(a.get("code") or "")=="power"]
bd=collections.defaultdict(list)
for a,s in sel: bd[a.get("decay")].append((a,s))
for d in sorted(bd,key=lambda x:(x is None,x)):
    v=bd[d]
    print(f"   dec{str(d):<4} n={len(v):3d} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in v]):5.2f} medSig={statistics.median([s for _,s in v])*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in v])*100:5.2f}% medFit={statistics.median([a.get('fitness') or 0 for a,_ in v]):5.2f}")
