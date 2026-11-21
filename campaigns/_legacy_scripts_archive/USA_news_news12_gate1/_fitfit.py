# -*- coding: utf-8 -*-
"""Fit the BRAIN Fitness identity against all evaluated runs in the 3qo campaign."""
import json, sys, glob, os, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

base = os.path.dirname(os.path.abspath(__file__))
pts = []
for f in glob.glob(os.path.join(base, 'batch_3qo_*_details.json')):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    for aid, v in d.items():
        if not isinstance(v, dict):
            continue
        m = (v.get('details') or {}).get('metrics') or {}
        sh, to, ret, fit = m.get('sharpe'), m.get('turnover'), m.get('returns'), m.get('fitness')
        if not all(isinstance(x, (int, float)) for x in (sh, to, ret, fit)):
            continue
        pts.append((sh, to, ret, fit, aid))

print(f'evaluated runs: {len(pts)}')

best = None
for c in [0.0, 0.05, 0.08, 0.10, 0.11, 0.115, 0.12, 0.125, 0.13, 0.135, 0.14, 0.15]:
    errs = []
    for sh, to, ret, fit, _ in pts:
        pred = sh * math.sqrt(abs(ret) / max(to, c)) if max(to, c) > 0 else 0
        errs.append(abs(pred - fit))
    mae = sum(errs) / len(errs)
    mx = max(errs)
    print(f'  floor={c:<6} MAE={mae:.4f}  MAX_ERR={mx:.4f}')
    if best is None or mae < best[1]:
        best = (c, mae, mx)

c = best[0]
print(f'\nBEST FLOOR = {c}  (MAE {best[1]:.4f}, max err {best[2]:.4f})')
print(f'IDENTITY:  Fitness = Sharpe * sqrt( |Returns| / max(Turnover, {c}) )')

print('\n--- structural ceiling: what if turnover were driven to zero? ---')
sh_max = max(p[0] for p in pts)
for sh, to, ret, fit, aid in sorted(pts, key=lambda x: -x[0])[:1]:
    ceil = sh * math.sqrt(abs(ret) / c)
    print(f'  best Sharpe run {aid}: Sh {sh}  Ret {ret*100:.2f}%  -> ceiling Fit {ceil:.4f}')
rets = sorted(pts, key=lambda x: -x[2])[:1]
for sh, to, ret, fit, aid in rets:
    print(f'  best Return run {aid}: Ret {ret*100:.2f}%  Sh {sh}  -> ceiling Fit {sh*math.sqrt(abs(ret)/c):.4f}')

print('\n--- requirement for Fit = 1.00 (turnover already at/below the floor) ---')
for sh in (1.58, 1.64, 1.66, 1.70, 1.75, 1.80, 1.90):
    print(f'  Sh {sh:.2f} -> needs Returns >= {c/sh**2*100:.2f}%')

print('\n--- observed Pareto frontier (does any run satisfy Sh^2 * Ret >= floor?) ---')
ok = [p for p in pts if p[0] ** 2 * abs(p[2]) >= c]
print(f'  runs satisfying Sh^2*|Ret| >= {c}: {len(ok)} / {len(pts)}')
for p in sorted(ok, key=lambda x: -(x[0] ** 2 * abs(x[2])))[:8]:
    print(f'    {p[4]:<9} Sh{p[0]:.2f} Ret{p[2]*100:.2f}%  Sh^2*Ret={p[0]**2*abs(p[2]):.4f}  Fit{p[3]:.2f}')
