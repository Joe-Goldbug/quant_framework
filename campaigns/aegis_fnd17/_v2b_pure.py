# -*- coding: utf-8 -*-
"""PV-free fundamental cohort: topology stats + champion skeleton family breakdown."""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
PVTOK = re.compile(r"\b(close|open|high|low|vwap|volume|adv20|returns|risk_|_risk|ts_rank\([^)]*close)", re.I)
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
def flds(code):
    return set(re.findall(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", code))

S=[a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1 and a.get("neutralization")=="STATISTICAL"]
rows=[(a,sig(a)) for a in S]; rows=[(a,s) for a,s in rows if s is not None]
pure=[(a,s) for a,s in rows if not PVTOK.search(a.get("code") or "")]
print(f"STATISTICAL USA/TOP1000/d1: {len(rows)}  PV-free: {len(pure)}")

print("\n=== PV-free: outer-op cohort (inner group_rank) ===")
grp=[(a,s) for a,s in pure if "group_rank" in ops(a.get("code") or "")]
print(f"  PV-free & inner group_rank: n={len(grp)}")
if grp:
    sh=[a.get("sharpe") or 0 for a,_ in grp]; sg=[s for _,s in grp]
    print(f"   medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in grp])*100:6.2f}%")
    bt=collections.defaultdict(list)
    for a,s in grp:
        t=top(a.get("code") or "")
        if t: bt[t].append((a,s))
    for t,v in sorted(bt.items(), key=lambda kv:-len(kv[1])):
        print(f"    outer={t:16s} n={len(v):3d} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in v]):5.2f} maxSh={max([a.get('sharpe') or 0 for a,_ in v]):5.2f} "
              f"medSig={statistics.median([s for _,s in v])*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in v])*100:6.2f}% "
              f"medFit={statistics.median([a.get('fitness') or 0 for a,_ in v]):5.2f}")

print("\n=== PV-free: group granularity ===")
gb=collections.defaultdict(list)
for a,s in grp:
    m=re.findall(r"group_(?:rank|zscore)\([^()]*,\s*(\w+)\)", a.get("code") or "")
    if m: gb[m[0]].append((a,s))
for g,v in sorted(gb.items(), key=lambda kv:-len(kv[1])):
    print(f"  {g:12s} n={len(v):3d} medSh={statistics.median([a.get('sharpe') or 0 for a,_ in v]):5.2f} maxSh={max([a.get('sharpe') or 0 for a,_ in v]):5.2f} "
          f"medSig={statistics.median([s for _,s in v])*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in v])*100:6.2f}%")

print("\n=== PV-free: all, sorted by Sharpe (top 20) ===")
for a,s in sorted(pure, key=lambda x:-(x[0].get('sharpe') or 0))[:20]:
    print(f"  {a['id']} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% Ret {(a.get('returns') or 0):7.4f} "
          f"TO {(a.get('turnover') or 0):.4f} 2Y {a.get('two_year_sharpe')} subU {a.get('sub_universe_sharpe')} nf {a.get('n_fail')} dec{a.get('decay')}")
    print(f"     ops={len(ops(a.get('code') or ''))} top={top(a.get('code') or '')} :: {(a.get('code') or '')[:165]}")

print("\n=== champion family power(subtract(group_rank(DIV),multiply(w,group_rank(B)))) — weight & exponent ===")
fam=[(a,s) for a,s in rows if re.search(r"power\(subtract\(group_rank\(divide\(", a.get("code") or "")]
print("  n=",len(fam))
for a,s in sorted(fam, key=lambda x:-(x[0].get('sharpe') or 0)):
    w=re.search(r"multiply\(([\d.]+),", a.get("code") or "")
    k=re.search(r",\s*(\d+)\)\s*$", (a.get("code") or "").strip())
    g = re.findall(r"group_rank\([^()]*,\s*(\w+)\)", a.get("code") or "")[:1]
    print(f"  {a['id']} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% Ret {(a.get('returns') or 0):7.4f} TO {(a.get('turnover') or 0):.4f} "
          f"w={w.group(1) if w else '?'} k={k.group(1) if k else '?'} dec{a.get('decay')} grp={g}")

print("\n=== does 2Y track Sh? (PV-free, Sh>=1.0) ===")
v=[(a.get('sharpe'), a.get('two_year_sharpe')) for a,_ in pure if (a.get('sharpe') or 0)>=1.0 and a.get('two_year_sharpe') is not None]
print("  n=",len(v), " 2Y>=1.58:", sum(1 for s,t in v if t>=1.58), " 2Y>=1.40:", sum(1 for s,t in v if t>=1.40))
print("  Sh>=1.58 & 2Y>=1.58:", sum(1 for s,t in v if s>=1.58 and t>=1.58), "/", sum(1 for s,t in v if s>=1.58))
