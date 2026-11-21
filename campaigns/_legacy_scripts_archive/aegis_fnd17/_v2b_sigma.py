# -*- coding: utf-8 -*-
"""What actually produces sigma >= 3.2% under STATISTICAL in this account? (local only)"""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))

def sig(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9:
        return None
    return abs(ret) / abs(sh)

def ops(code):
    try:
        t = ast.parse(code, mode="eval")
    except Exception:
        return []
    return [getattr(n.func, "id", "") or getattr(n.func, "attr", "") for n in ast.walk(t) if isinstance(n, ast.Call)]

S = [a for a in H if a.get("region") == "USA" and a.get("universe") == "TOP1000" and a.get("delay") == 1
     and a.get("neutralization") == "STATISTICAL"]
print("STATISTICAL USA/TOP1000/d1:", len(S))

# --- correlation of sigma with turnover / n_fields / n_ops / decay ---
def corr(xs, ys):
    n = len(xs)
    if n < 5: return None
    mx, my = sum(xs)/n, sum(ys)/n
    sx = (sum((x-mx)**2 for x in xs))**.5
    sy = (sum((y-my)**2 for y in ys))**.5
    if sx == 0 or sy == 0: return None
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(sx*sy)

rows = [(a, sig(a)) for a in S]
rows = [(a, s) for a, s in rows if s is not None]
sg = [s for _, s in rows]
print("\ncorr(sigma, turnover)  =", round(corr(sg, [a.get('turnover') or 0 for a,_ in rows]), 3))
print("corr(sigma, sharpe)    =", round(corr(sg, [a.get('sharpe') or 0 for a,_ in rows]), 3))
print("corr(sigma, decay)     =", round(corr(sg, [a.get('decay') or 0 for a,_ in rows]), 3))
print("corr(sigma, n_ops)     =", round(corr(sg, [len(ops(a.get('code') or '')) for a,_ in rows]), 3))
print("corr(sigma, n_fields)  =", round(corr(sg, [len(set(re.findall(r'\b[a-z0-9]+_[a-z0-9_]+\b', a.get('code') or ''))) for a,_ in rows]), 3))
print("corr(sigma, retention) =", round(corr(sg, [(a.get('returns') or 0) for a,_ in rows]), 3))

# --- HIGH-SIGMA STAT cohort: what's their shape? ---
hi = [(a, s) for a, s in rows if s >= 0.0317]
lo = [(a, s) for a, s in rows if s < 0.02]
print(f"\nHIGH-sigma (>=3.17%) n={len(hi)}   LOW-sigma (<2%) n={len(lo)}")
def summ(name, rs):
    if not rs: return
    to = [a.get('turnover') or 0 for a,_ in rs]
    sh = [a.get('sharpe') or 0 for a,_ in rs]
    nop = [len(ops(a.get('code') or '')) for a,_ in rs]
    nfl = [len(set(re.findall(r'\b[a-z0-9]+_[a-z0-9_]+\b', a.get('code') or ''))) for a,_ in rs]
    ds = collections.Counter()
    for a,_ in rs:
        for d in (a.get('datasets') or []): ds[d]+=1
    print(f"  {name}: medTO={statistics.median(to)*100:.2f}% medSh={statistics.median(sh):.2f} maxSh={max(sh):.2f} "
          f"medOps={statistics.median(nop):.0f} medFields={statistics.median(nfl):.0f} topDS={ds.most_common(4)}")
summ("HI-sig", hi)
summ("LO-sig", lo)

print("\n--- HIGH-sigma STATISTICAL alphas with Sh>=1.20 (actionable analogues) ---")
for a, s in sorted([x for x in hi if (x[0].get('sharpe') or 0) >= 1.2], key=lambda x: -(x[0].get('sharpe') or 0))[:14]:
    print(f"  {a['id']} dec{a.get('decay'):<3} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {s*100:5.2f}% "
          f"Ret {a.get('returns'):7.4f} TO {a.get('turnover'):.4f} 2Y {a.get('two_year_sharpe')} subU {a.get('sub_universe_sharpe')} robU {a.get('robust_universe_sharpe')} nf {a.get('n_fail')}")
    print(f"     {(a.get('code') or '')[:250]}")

# --- op-presence lift on sigma within STATISTICAL (median sigma when op present vs absent) ---
print("\n--- sigma lift by op (STATISTICAL) ---")
allops = collections.Counter(o for a,_ in rows for o in set(ops(a.get('code') or '')))
pres = collections.defaultdict(list); absent = collections.defaultdict(list)
for a, s in rows:
    o = set(ops(a.get('code') or ''))
    for op in allops:
        (pres if op in o else absent)[op].append(s)
for op, n in allops.most_common():
    if n < 20: continue
    p, ab = pres[op], absent[op]
    print(f"  {op:20s} n={n:4d} present medSig={statistics.median(p)*100:5.2f}% (n={len(p)}) | absent medSig={statistics.median(ab)*100:5.2f}%  delta={ (statistics.median(p)-statistics.median(ab))*100:+5.2f}pp")

# --- 2Y and SubU behaviour ---
print("\n--- SubU/Sharpe ratio distribution (STATISTICAL) ---")
rs = [(a.get('sub_universe_sharpe') or 0, a.get('sharpe') or 0) for a in S if a.get('sharpe')]
ok = [su/sh for su, sh in rs if sh > 0]
print("  n=", len(ok), "med=", round(statistics.median(ok),3), "p10=", round(sorted(ok)[int(.1*len(ok))],3), "p25=", round(sorted(ok)[int(.25*len(ok))],3))
print("  SubU >= 0.53*Sh pass-rate:", round(sum(1 for su,sh in rs if sh>0 and su >= 0.53*sh)/len(rs),3))
print("\n--- 2Y Sharpe: what fraction of Sh>=1.58 have 2Y>=1.58? ---")
s2 = [(a.get('sharpe') or 0, a.get('two_year_sharpe')) for a in S if (a.get('sharpe') or 0) >= 1.58]
have = [(s,t) for s,t in s2 if t is not None]
print("  Sh>=1.58:", len(s2), " with 2Y value:", len(have), " 2Y>=1.58:", sum(1 for _,t in have if t>=1.58), "/", len(have))
