# -*- coding: utf-8 -*-
import json, sys, os, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def fmt(x, scale=1, nd=2):
    if not isinstance(x, (int, float)):
        return '?'
    return f'{x*scale:.{nd}f}'

def show(fn):
    if not os.path.exists(fn):
        print('MISSING', fn); return
    try:
        d = json.load(open(fn, encoding='utf-8'))
    except Exception as e:
        print('ERR', fn, e); return
    print('=====', os.path.basename(fn), 'n=', len(d))
    rows = []
    for aid, v in d.items():
        if not isinstance(v, dict):
            continue
        det = v.get('details') or {}
        m = det.get('metrics') or {}
        rows.append((v.get('slot') if v.get('slot') is not None else 99, aid, m))
    rows.sort()
    for slot, aid, m in rows:
        if not m:
            print(f'  S{slot:>2} {aid:<9} NO-METRICS')
        else:
            print(f'  S{slot:>2} {aid:<9} Sh{fmt(m.get("sharpe"))} Fit{fmt(m.get("fitness"))} '
                  f'TO{fmt(m.get("turnover"),100,1)}% Ret{fmt(m.get("returns"),100,2)}% '
                  f'Mgn{fmt(m.get("margin"),10000,2)}bp')

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        show(fn)
