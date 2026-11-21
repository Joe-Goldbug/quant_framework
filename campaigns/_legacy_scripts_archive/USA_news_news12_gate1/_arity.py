# -*- coding: utf-8 -*-
"""Detect top-level arity of a given operator inside FastExpr expressions."""
import sys, sqlite3, json, glob, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def args_of(expr, start):
    """start = index just after 'op('. Return list of top-level arg strings."""
    depth = 1
    i = start
    buf = []
    args = []
    while i < len(expr):
        ch = expr[i]
        if ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            if depth == 0:
                args.append(''.join(buf))
                return args, i + 1
            buf.append(ch)
        elif ch == ',' and depth == 1:
            args.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    return None, i


def max_arity(expr, op):
    best = 0
    pat = op + '('
    i = 0
    while True:
        j = expr.find(pat, i)
        if j < 0:
            break
        args, nxt = args_of(expr, j + len(pat))
        if args is not None:
            best = max(best, len(args))
        i = j + len(pat)
    return best


if __name__ == '__main__':
    op = sys.argv[1] if len(sys.argv) > 1 else 'multiply'
    # 1) fingerprint DB
    db = os.path.join(os.path.dirname(__file__), '..', '..', 'alphas_record.db')
    db = os.path.abspath(db)
    print('DB:', db, os.path.exists(db))
    if os.path.exists(db):
        c = sqlite3.connect(db)
        rows = c.execute('SELECT expression FROM alpha_fingerprints').fetchall()
        hits = [(e[0], max_arity(e[0], op)) for e in rows]
        hi = [h for h in hits if h[1] >= 3]
        print(f'  fingerprint rows={len(hits)}  arity>=3 -> {len(hi)}')
        for e, a in hi[:8]:
            print(f'    [{a}] {e[:150]}')
        c.close()

    # 2) all batch manifests + results in this campaign
    base = os.path.dirname(os.path.abspath(__file__))
    seen = {}
    for fn in glob.glob(os.path.join(base, '*.json')):
        try:
            d = json.load(open(fn, encoding='utf-8'))
        except Exception:
            continue
        exprs = []
        if isinstance(d, dict) and isinstance(d.get('items'), list):
            exprs = [(it.get('id'), it.get('expression', '')) for it in d['items']]
        elif isinstance(d, dict):
            for aid, v in d.items():
                if isinstance(v, dict):
                    for k in ('expression', 'code', 'regular'):
                        if isinstance(v.get(k), str):
                            exprs.append((aid, v[k]))
        for k, e in exprs:
            if e and max_arity(e, op) >= 3:
                seen.setdefault(e, []).append(os.path.basename(fn))
    print(f'\n  campaign files with arity>=3 {op}: {len(seen)}')
    for e, fs in list(seen.items())[:10]:
        print(f'    [{max_arity(e, op)}] {e[:160]}')
        print(f'       in: {fs[:3]}')
