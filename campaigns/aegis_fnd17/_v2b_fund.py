# -*- coding: utf-8 -*-
"""Find fundamental-domain analogues: high Sh + adequate sigma under STATISTICAL."""
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
    b = t.body
    root = b if isinstance(b, ast.Call) else (b.value if isinstance(b, ast.Expression) and isinstance(b.value, ast.Call) else None)
    return getattr(root.func, "id", "") if root is not None else None

FUND = re.compile(r"(fnd|oth466|anl|nws|snt|mdl|img|prob|rsk|imbalance)", re.I)
PVONLY = re.compile(r"(close|open|high|low|vwap|volume|adv20|returns|risk)", re.I)

S = [a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1
     and a.get("neutralization")=="STATISTICAL"]
# "fundamental-ish": alphas whose datasets are predominantly fundamental datasets
FDS = {"fnd17","fnd69","fnd89","oth466","fnd13","fnd23","fnd3","fnd90","fnd25","fnd94","fnd1","fnd6",
       "fnd31","fnd65","fnd72","fnd77","fnd86","fnd19","fnd11","fnd2","fnd27","fnd37","fnd47","fnd54"}
fund = [a for a in S if set(a.get("datasets") or []) & FDS]
print(f"STATISTICAL USA/TOP1000/d1 total={len(S)}  fundamental-touching={len(fund)}")

print("\n=== ALL fundamental-touching STATISTICAL alphas, sorted by (Sh, sigma) ===")
rows = []
for a in fund:
    s = sig(a)
    if s is None: continue
    rows.append((a, s))
rows.sort(key=lambda r: -(r[0].get("sharpe") or 0))
for a, s in rows:
    sh = a.get("sharpe") or 0
    if sh < 1.2: continue
    print(f"  {a['id']} Sh {sh:5.2f} Fit {a.get('fitness') or 0:5.2f} sig {s*100:5.2f}% Ret {(a.get('returns') or 0):7.4f} "
          f"TO {(a.get('turnover') or 0):.4f} 2Y {a.get('two_year_sharpe')} subU {a.get('sub_universe_sharpe')} "
          f"robU {a.get('robust_universe_sharpe')} nf {a.get('n_fail')} dec{a.get('decay')} top={top(a.get('code') or '')}")
    print(f"     ds={a.get('datasets')} :: {(a.get('code') or '')[:210]}")

print("\n=== sigma distribution, fundamental-touching STATISTICAL ===")
sg = sorted(s for _, s in rows)
if sg:
    print(f"  n={len(sg)} med={statistics.median(sg)*100:.2f}% p75={sg[int(.75*len(sg))]*100:.2f}% p90={sg[int(.9*len(sg))]*100:.2f}% max={max(sg)*100:.2f}%")
    print(f"  n(sig>=3.17%)={sum(1 for s in sg if s>=0.0317)}  n(sig>=3.0%)={sum(1 for s in sg if s>=0.030)}")

print("\n=== TOP-level op among fundamental-touching STATISTICAL (Sh>=0.8) ===")
bt = collections.defaultdict(list)
for a, s in rows:
    t = top(a.get("code") or "")
    if t: bt[t].append((a, s))
for t, v in sorted(bt.items(), key=lambda kv: -max((x[0].get('sharpe') or 0) for x in kv[1])):
    shs = [a.get("sharpe") or 0 for a, _ in v]; sgs = [s for _, s in v]
    hi = [x for x in v if x[1] >= 0.0317]
    print(f"  {t:16s} n={len(v):4d} medSh={statistics.median(shs):5.2f} maxSh={max(shs):5.2f} medSig={statistics.median(sgs)*100:5.2f}% "
          f"n(sig>=3.17)={len(hi):3d} maxSh_with_sig>=3.17={max([a.get('sharpe') or 0 for a,_ in hi], default=0):5.2f}")

print("\n=== all alphas in account using fnd3/fnd13/fnd23/oth466 (any region) ===")
for a in H:
    ds = set(a.get("datasets") or [])
    if ds & {"fnd3","fnd13","fnd23","oth466","fundamental3","fundamental13","fundamental23","other466"}:
        print(f"  {a['id']} {a.get('region')}/{a.get('universe')} d{a.get('delay')} {a.get('neutralization')} dec{a.get('decay')} "
              f"Sh {a.get('sharpe')} Fit {a.get('fitness')} TO {a.get('turnover')} nf {a.get('n_fail')} ds={a.get('datasets')}")
