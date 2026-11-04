# -*- coding: utf-8 -*-
"""Group granularity + inner group_zscore hedge, restricted to 2-leg group_rank-spread alphas."""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
def sig(a):
    s, r = a.get("sharpe"), a.get("returns")
    return abs(r)/abs(s) if s and r is not None and abs(s) > 1e-9 else None
def ops(c):
    try: t = ast.parse(c, mode="eval")
    except Exception: return []
    return [getattr(n.func, "id", "") or getattr(n.func, "attr", "") for n in ast.walk(t) if isinstance(n, ast.Call)]
def grps(c):
    return re.findall(r"group_(?:rank|zscore)\((?:[^()]|\([^()]*\))*?,\s*(\w+)\)", c)

S = [a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1
     and a.get("neutralization")=="STATISTICAL" and a.get("code")]

print("=== granularity: alphas whose code has >=1 group_rank with 2+ groups (all STATISTICAL) ===")
g = collections.defaultdict(list)
for a in S:
    c = a["code"]; o = ops(c)
    if "group_rank" not in o: continue
    gs = set(grps(c))
    if len(gs) == 1:
        g[next(iter(gs))].append(a)
for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
    sg = [sig(a) or 0 for a in v]
    print(f"  {k:12s} n={len(v):4d} medSh={statistics.median([a.get('sharpe') or 0 for a in v]):5.2f} "
          f"maxSh={max([a.get('sharpe') or 0 for a in v]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median([a.get('turnover') or 0 for a in v])*100:6.2f}% "
          f"medFit={statistics.median([a.get('fitness') or 0 for a in v]):5.2f} maxFit={max([a.get('fitness') or 0 for a in v]):5.2f}")

print("\n=== 2-leg group_rank spread (subtract(group_rank, group_rank)) granularity ===")
SPREAD = re.compile(r"subtract\(\s*group_rank\(", re.S)
v = [a for a in S if SPREAD.search(a["code"])]
g2 = collections.defaultdict(list)
for a in v:
    gs = grps(a["code"])
    if len(gs) >= 1: g2[gs[0]].append(a)
for k, vv in sorted(g2.items(), key=lambda kv: -len(kv[1])):
    sg = [sig(a) or 0 for a in vv]
    print(f"  {k:12s} n={len(vv):3d} medSh={statistics.median([a.get('sharpe') or 0 for a in vv]):5.2f} "
          f"maxSh={max([a.get('sharpe') or 0 for a in vv]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median([a.get('turnover') or 0 for a in vv])*100:6.2f}%")

print("\n=== inner group_zscore vs group_rank, 2-leg spread only, same outer ===")
for outer in ["power", "subtract", "ts_decay_linear"]:
    for inner in ["group_rank", "group_zscore"]:
        sel = []
        for a in S:
            c = a["code"]; o = ops(c)
            if outer not in o: continue
            if inner not in o: continue
            other = [x for x in ("group_rank","group_zscore") if x != inner]
            if any(x in o for x in other): continue   # pure inner type
            sel.append(a)
        if len(sel) < 3: continue
        sg = [sig(a) or 0 for a in sel]
        print(f"  outer={outer:16s} inner={inner:12s} n={len(sel):3d} medSh={statistics.median([a.get('sharpe') or 0 for a in sel]):5.2f} "
              f"maxSh={max([a.get('sharpe') or 0 for a in sel]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
              f"medTO={statistics.median([a.get('turnover') or 0 for a in sel])*100:6.2f}% "
              f"medFit={statistics.median([a.get('fitness') or 0 for a in sel]):5.2f}")

print("\n=== does 'multiply(w, group_rank(B))' with w<1 beat w=1 (asymmetry)? ===")
asym = collections.defaultdict(list)
for a in S:
    c = a["code"]
    m = re.search(r"power\(\s*subtract\(\s*group_rank\(divide\([^)]*\)[^)]*\)[^)]*\)\s*,\s*multiply\(\s*([\d.]+)\s*,", c)
    if m: asym[float(m.group(1))].append(a)
for w, vv in sorted(asym.items()):
    sg = [sig(a) or 0 for a in vv]
    print(f"  w={w} n={len(vv):3d} medSh={statistics.median([a.get('sharpe') or 0 for a in vv]):5.2f} "
          f"maxSh={max([a.get('sharpe') or 0 for a in vv]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medFit={statistics.median([a.get('fitness') or 0 for a in vv]):5.2f}")
