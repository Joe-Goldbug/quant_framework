# -*- coding: utf-8 -*-
"""Conditional sigma/Sharpe effect of outer ts_mean + sector/industry granularity, inner group_rank cohort."""
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

def grp_of(code):
    m=re.findall(r"group_(?:rank|zscore)\([^()]*,\s*(\w+)\)", code)
    return m[0] if m else None

print("=== inner group_rank cohort: outer ts_mean vs not (STATISTICAL USA/TOP1000/d1) ===")
base=[(a,s) for a,s in rows if "group_rank" in ops(a.get("code") or "")]
for label,pred in [("has ts_mean", lambda c: "ts_mean" in ops(c)),
                   ("has ts_decay_linear", lambda c: "ts_decay_linear" in ops(c)),
                   ("no ts_* at all", lambda c: not any(o.startswith("ts_") for o in ops(c)))]:
    v=[(a,s) for a,s in base if pred(a.get("code") or "")]
    if len(v)<5:
        print(f"  {label:20s} n={len(v)} (too few)"); continue
    sh=[a.get("sharpe") or 0 for a,_ in v]; sg=[s for _,s in v]; to=[a.get("turnover") or 0 for a,_ in v]
    fit=[a.get("fitness") or 0 for a,_ in v]
    print(f"  {label:20s} n={len(v):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median(to)*100:6.2f}% medFit={statistics.median(fit):5.2f} maxFit={max(fit):5.2f}")

print("\n=== group granularity in inner-group_rank cohort ===")
gb=collections.defaultdict(list)
for a,s in base:
    g=grp_of(a.get("code") or "")
    if g: gb[g].append((a,s))
for g,v in sorted(gb.items(), key=lambda kv:-len(kv[1])):
    sh=[a.get("sharpe") or 0 for a,_ in v]; sg=[s for _,s in v]; to=[a.get("turnover") or 0 for a,_ in v]
    print(f"  {g:12s} n={len(v):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% medTO={statistics.median(to)*100:6.2f}%")

print("\n=== Fit arithmetic: what Sh is needed at each sigma (TO<12.5%) ===")
for sg_pct in [2.6,3.0,3.2,3.6,4.0,4.5]:
    sg=sg_pct/100
    need = (1.0/( (8*sg)**0.5 ))**(2/3)
    print(f"  sigma={sg_pct:.1f}% -> need Sh >= {need:.3f} for Fit>=1.00")
print("\n=== inverse: sigma needed at each Sh ===")
for sh in [1.4,1.5,1.58,1.7,1.8,1.9,2.0]:
    need = (1.0/sh**1.5)**2/8
    print(f"  Sh={sh:.2f} -> need sigma >= {need*100:.2f}%")

print("\n=== how many STAT alphas meet BOTH Sh>=1.58 and sigma>=3.17 (any) and their ops ===")
good=[(a,s) for a,s in rows if (a.get("sharpe") or 0)>=1.58 and s>=0.0317]
print("  count:",len(good))
for a,s in sorted(good,key=lambda x:-(x[0].get('fitness') or 0))[:12]:
    print(f"   {a['id']} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% TO {a.get('turnover'):.4f} "
          f"ops={len(ops(a.get('code') or ''))} top={top(a.get('code') or '')} nfields={len(set(re.findall(r'[a-z0-9]+_[a-z0-9_]+',a.get('code') or '')))} ds={a.get('datasets')}")
