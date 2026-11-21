# -*- coding: utf-8 -*-
"""Mine account_alpha_history_full.json for structural evidence (local only, zero quota)."""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))

def sigma(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9:
        return None
    return abs(ret) / abs(sh)

def calls(code):
    try:
        t = ast.parse(code, mode="eval")
    except Exception:
        return None, None
    c = [getattr(n.func, "id", "") or getattr(n.func, "attr", "") for n in ast.walk(t) if isinstance(n, ast.Call)]
    body = t.body
    if isinstance(body, ast.Call):
        root = body
    elif isinstance(body, ast.Expression) and isinstance(body.value, ast.Call):
        root = body.value
    else:
        return c, None
    top = getattr(root.func, "id", "") or getattr(root.func, "attr", "")
    return c, top

sel = [a for a in H if a.get("region") == "USA" and a.get("universe") == "TOP1000" and a.get("delay") == 1]
print("USA/TOP1000/d1:", len(sel))

# --- 1. sigma distribution by neutralization ---
print("\n=== sigma (Ret/Sharpe) by neutralization, USA/TOP1000/d1 ===")
byn = collections.defaultdict(list)
for a in sel:
    s = sigma(a)
    if s is not None:
        byn[a.get("neutralization")].append(s)
for n, v in sorted(byn.items(), key=lambda kv: -len(kv[1])):
    v2 = sorted(v)
    print(f"  {str(n):14s} n={len(v):4d} med={statistics.median(v)*100:5.2f}%  p75={v2[int(.75*len(v2))]*100:5.2f}%  p90={v2[int(.90*len(v2))]*100:5.2f}%  max={max(v)*100:6.2f}%")

# --- 2. top-level operator vs sigma+sharpe ---
print("\n=== top-level op vs (Sh, sigma) for STATISTICAL only ===")
rows = []
for a in sel:
    if a.get("neutralization") != "STATISTICAL":
        continue
    s = sigma(a)
    c, top = calls(a.get("code") or "")
    if s is None or top is None:
        continue
    rows.append((top, a.get("sharpe") or 0, s, a.get("fitness") or 0, a.get("turnover") or 0, a))
bytop = collections.defaultdict(list)
for r in rows:
    bytop[r[0]].append(r)
for t, rs in sorted(bytop.items(), key=lambda kv: -len(kv[1])):
    shs = [r[1] for r in rs]; sgs = [r[2] for r in rs]
    hi = [r for r in rs if r[2] >= 0.0317]
    print(f"  {t:16s} n={len(rs):4d} medSh={statistics.median(shs):5.2f} maxSh={max(shs):5.2f} medSig={statistics.median(sgs)*100:5.2f}%  n(sig>=3.17%)={len(hi):4d}  maxSh&sig>=3.17={max([r[1] for r in hi], default=0):5.2f}")

# --- 3. inner operator presence vs sigma ---
print("\n=== inner operator presence vs median sigma (STATISTICAL) ===")
opstat = collections.defaultdict(list)
for r in rows:
    c, top = calls(r[5].get("code") or "")
    for op in set(c):
        opstat[op].append(r[2])
for op, v in sorted(opstat.items(), key=lambda kv: -statistics.median(kv[1])):
    if len(v) < 8:
        continue
    print(f"  {op:18s} n={len(v):4d} medSig={statistics.median(v)*100:5.2f}%  p90={sorted(v)[int(.9*len(v))]*100:5.2f}%")

# --- 4. the real question: alphas with sigma>=3.17 AND sharpe>=1.58 ---
print("\n=== USA/TOP1000/d1 alphas with sigma>=3.17% and Sh>=1.58 (any neutralization) ===")
good = [a for a in sel if (sigma(a) or 0) >= 0.0317 and (a.get("sharpe") or 0) >= 1.58]
print("count:", len(good))
for a in sorted(good, key=lambda x: -(x.get("fitness") or 0))[:20]:
    c, top = calls(a.get("code") or "")
    print(f"  {a['id']} {a.get('neutralization'):12s} dec{a.get('decay'):<3} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} sig {sigma(a)*100:5.2f}% Ret {a.get('returns'):7.4f} TO {a.get('turnover'):.4f} 2Y {a.get('two_year_sharpe')} nfail {a.get('n_fail')} top={top}")
    print(f"      {(a.get('code') or '')[:230]}")
