# -*- coding: utf-8 -*-
"""Wave11-H frontier analysis: build master dataset from all batch results + baselines."""
import json, glob, os, re
from collections import Counter, defaultdict

D = os.path.dirname(os.path.abspath(__file__))

def load_master():
    rows = {}  # aid -> normalized row
    # 1) raw batch results (most complete, includes w11h)
    for f in sorted(glob.glob(os.path.join(D, 'batch_*_result.json'))):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        for r in d.get('alpha_results', []):
            aid = r.get('alpha_id') or r.get('id')
            if not aid:
                continue
            m = r.get('metrics', {}) or {}
            ra = r.get('ra', {}) or {}
            ck = r.get('checks', {}) or {}
            fails = set(ra.get('ra_failed_checks', []) or [])
            for c in ck.get('fail', []) or []:
                fails.add(c.get('name'))
            warns = set(c.get('name') for c in ck.get('warning', []) or [] if c.get('name'))
            st = r.get('settings', {}) or {}
            row = dict(
                aid=aid, expr=r.get('code', ''),
                sh=m.get('sharpe'), fit=m.get('fitness'), to=m.get('turnover'),
                ret=m.get('returns'), y2=m.get('two_year_sharpe'),
                sub=m.get('sub_universe_sharpe'), rn=m.get('risk_neutralized_sharpe'),
                lc=m.get('longCount'), sc=m.get('shortCount'), dd=m.get('drawdown'),
                decay=st.get('decay'), uni=st.get('universe'), neut=st.get('neutralization'),
                fails=sorted(fails), warns=sorted(warns), src=os.path.basename(f),
            )
            prev = rows.get(aid)
            if prev is None or (len(row['fails']) + len(row['warns'])) >= (len(prev['fails']) + len(prev['warns'])):
                rows[aid] = row
    # 2) baseline files (may carry waves whose raw files were cleaned; enrich)
    for bf in ['_baseline_w11.json', '_baseline_final.json', '_baseline_unified.json', '_baseline_all.json']:
        p = os.path.join(D, bf)
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        for r in d:
            aid = r.get('aid')
            if not aid:
                continue
            prev = rows.get(aid)
            cand = dict(
                aid=aid, expr=r.get('expr', ''),
                sh=r.get('sh'), fit=r.get('fit'), to=r.get('to'), ret=r.get('ret'),
                y2=r.get('y2', r.get('2y')), sub=r.get('sub'), rn=r.get('rn'),
                lc=r.get('lc'), sc=r.get('sc'), dd=r.get('dd'), decay=r.get('decay'),
                uni=r.get('uni'), neut=r.get('neut'),
                fails=r.get('fails', []), warns=r.get('warns', []),
                src=r.get('file', bf),
            )
            if prev is None:
                rows[aid] = cand
            else:
                # enrich missing fields
                for k, v in cand.items():
                    if prev.get(k) in (None, '', []) and v not in (None, '', []):
                        prev[k] = v
    return list(rows.values())

if __name__ == '__main__':
    rows = load_master()
    print('master rows:', len(rows))
    src_c = Counter(r['src'] for r in rows)
    for k, v in sorted(src_c.items(), key=lambda x: -x[1])[:40]:
        print(f'{v:4d}  {k}')
    json.dump(rows, open(os.path.join(D, '_w11h_master.json'), 'w', encoding='utf-8'))
