# -*- coding: utf-8 -*-
"""Decay sweep on the champion power(subtract(group_rank(DIV),multiply(w,group_rank(B))),k) family."""
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

# family = power( subtract( group_rank(divide(..)) , multiply(w, group_rank(..)) ), k )
FAM = re.compile(r"power\(\s*subtract\(\s*group_rank\(\s*divide\(", re.S)
S = [a for a in H if a.get("region") == "USA" and a.get("universe") == "TOP1000" and a.get("delay") == 1
     and a.get("neutralization") == "STATISTICAL"]
fam = [a for a in S if FAM.search(a.get("code") or "")]
print(f"champion-family alphas (STATISTICAL USA/TOP1000/d1): n={len(fam)}")
print("\n  id          dec  Sh     Fit   sigma%   Ret      TO      2Y    nf")
for a in sorted(fam, key=lambda x: (x.get("decay") or 0)):
    s = sig(a) or 0
    print(f"  {a['id']:10s} {str(a.get('decay')):>4} {a.get('sharpe') or 0:5.2f} {(a.get('fitness') or 0):6.2f} {s*100:6.2f} {(a.get('returns') or 0):8.4f} {(a.get('turnover') or 0):.4f} {str(a.get('two_year_sharpe')):>6} {a.get('n_fail')}")

bd = collections.defaultdict(list)
for a in fam: bd[a.get("decay")].append(a)
print("\n  decay bucket | n | medSh | maxSh | medSigma% | medTO% | medFit | maxFit")
for d in sorted(bd, key=lambda x: (x is None, x)):
    v = bd[d]
    sg = [sig(a) or 0 for a in v]
    print(f"   dec{str(d):<6} n={len(v):2d}  medSh={statistics.median([a.get('sharpe') or 0 for a in v]):5.2f} "
          f"maxSh={max([a.get('sharpe') or 0 for a in v]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median([a.get('turnover') or 0 for a in v])*100:6.2f}% "
          f"medFit={statistics.median([a.get('fitness') or 0 for a in v]):5.2f} maxFit={max([a.get('fitness') or 0 for a in v]):5.2f}")

# Fit arithmetic for the best dec8 point
print("\n  dec<=8 bucket arithmetic:")
low = [a for a in fam if (a.get("decay") or 99) <= 8]
if low:
    for a in sorted(low, key=lambda x: -(x.get("sharpe") or 0)):
        s = sig(a) or 0; sh = a.get("sharpe") or 0; to = a.get("turnover") or 0
        fit = sh * (abs(a.get("returns") or 0)/max(to, 0.125))**0.5
        need = (1.0/(8*s)**0.5)**(2/3) if s > 0 else None
        print(f"   {a['id']} Sh {sh:5.2f} sig {s*100:5.2f}% TO {to:.4f} Fit(recomp) {fit:5.2f} | Sh needed at this sigma for Fit>=1: {need if need is None else round(need,3)}")

# Wider: all STAT alphas, sigma vs decay bucket, PV-free + group_rank cohort
print("\n=== all PV-free & inner-group_rank STATISTICAL: sigma/TO by decay ===")
PVTOK = re.compile(r"\b(close|open|high|low|vwap|volume|adv20|returns)\b", re.I)
b2 = collections.defaultdict(list)
for a in S:
    c = a.get("code") or ""
    o = ops(c)
    if "group_rank" in o and not PVTOK.search(c):
        b2[a.get("decay")].append(a)
for d in sorted(b2, key=lambda x: (x is None, x)):
    v = b2[d]; sg = [sig(a) or 0 for a in v]
    print(f"   dec{str(d):<5} n={len(v):4d} medSh={statistics.median([a.get('sharpe') or 0 for a in v]):5.2f} "
          f"maxSh={max([a.get('sharpe') or 0 for a in v]):5.2f} medSig={statistics.median(sg)*100:5.2f}% "
          f"medTO={statistics.median([a.get('turnover') or 0 for a in v])*100:6.2f}% "
          f"medFit={statistics.median([a.get('fitness') or 0 for a in v]):5.2f} maxFit={max([a.get('fitness') or 0 for a in v]):5.2f}")
