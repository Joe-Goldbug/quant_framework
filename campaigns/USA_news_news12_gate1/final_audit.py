# -*- coding: utf-8 -*-
"""Wave10 终局盘点: 生成最佳资产档案与权衡前沿."""
import glob
import json
from collections import Counter

rows = []
for fp in sorted(glob.glob('batch_*_result.json')):
    for r in json.load(open(fp, encoding='utf-8')).get('alpha_results', []):
        m = r.get('metrics') or {}
        if not m:
            continue
        s = r.get('settings') or {}
        ch = r.get('checks') or {}
        rows.append(dict(expr=r.get('code'), aid=r.get('alpha_id'), sh=m.get('sharpe'),
                         fit=m.get('fitness'), to=m.get('turnover'), ret=m.get('returns'),
                         y2=m.get('two_year_sharpe'), sub=m.get('sub_universe_sharpe'),
                         rn=m.get('risk_neutralized_sharpe'), lc=m.get('longCount'),
                         sc=m.get('shortCount'), dd=m.get('drawdown'),
                         decay=s.get('decay'), uni=s.get('universe'), neut=s.get('neutralization'),
                         fails=[c.get('name') if isinstance(c, dict) else c for c in (ch.get('fail') or [])]))

best = {}
for r in rows:
    k = (r['expr'], r['decay'], r['uni'], r['neut'])
    if r['expr'] and (k not in best or abs(r['sh'] or 0) > abs(best[k]['sh'] or 0)):
        best[k] = r
A = list(best.values())
print('总样本 (表达式 x settings):', len(A))


def nf(r):
    return len([x for x in r['fails'] if x != 'LOW_SUB_UNIVERSE_SHARPE'])


print()
print('=== 终局最佳 10: 按剩余 FAIL 项数升序 ===')
print(f"{'FAIL':>4} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>10} {'CW':>4}  id")
for r in sorted(A, key=lambda x: (nf(x), -(x['sh'] or 0)))[:10]:
    cw = 'FAIL' if 'CONCENTRATED_WEIGHT' in r['fails'] else 'ok'
    print(f"{nf(r):>4} {r['sh'] or 0:>6.2f} {r['fit'] or 0:>5.2f} {(r['to'] or 0)*100:>7.1f} "
          f"{(r['ret'] or 0)*100:>7.2f} {r['y2'] or 0:>6.2f} {r['sub'] or 0:>5.2f} {r['rn'] or 0:>5.2f} "
          f"{str(r['lc'])+'/'+str(r['sc']):>10} {cw:>4}  {r['aid']}")
    print(f"      剩余: {[x for x in r['fails'] if x != 'LOW_SUB_UNIVERSE_SHARPE']}")

print()
print('=== Sh vs TO 权衡前沿 (仅 CW-ok 样本) ===')
ok = [r for r in A if 'CONCENTRATED_WEIGHT' not in r['fails']]
print(f'CW-ok 样本数: {len(ok)}')
for lo, hi in [(0, 0.15), (0.15, 0.30), (0.30, 0.50), (0.50, 0.72), (0.72, 0.90), (0.90, 1.2), (1.2, 9)]:
    seg = [r for r in ok if lo <= (r['to'] or 9) < hi]
    if seg:
        mx = max(seg, key=lambda r: r['sh'] or -9)
        print(f'  TO[{lo*100:>3.0f}%-{hi*100:>3.0f}%): n={len(seg):>3}  最高Sh={mx["sh"] or 0:>5.2f}  '
              f'Ret={(mx["ret"] or 0)*100:>5.2f}%  2Y={mx["y2"] or 0:>5.2f}  Fit={mx["fit"] or 0:>5.2f}  {mx["aid"]}')

print()
print('=== 全样本剩余 FAIL 项数分布 ===')
print(dict(Counter(nf(r) for r in A)))

print()
b = sorted(A, key=lambda x: (nf(x), -(x['sh'] or 0)))[0]
print('=== 最佳 alpha 完整档案 ===')
print('表达式:', b['expr'])
print('alpha_id:', b['aid'])
print(f"Sh={b['sh']}  Fit={b['fit']}  TO={b['to']*100:.1f}%  Ret={b['ret']*100:.2f}%  "
      f"2Y={b['y2']}  sub={b['sub']}  rn={b['rn']}  DD={b['dd']*100:.1f}%  L/S={b['lc']}/{b['sc']}")
print('FAIL:', b['fails'])
print(f"Fit>=1 所需: TO <= {b['ret']*b['sh']**2*100:.2f}%  (固定 Sh={b['sh']}, Ret={b['ret']*100:.2f}%)")
print(f"或进入 TO<=11% 保护区时: 只需 Ret >= {0.11/b['sh']**2*100:.2f}%")
json.dump(b, open('_best_alpha.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(A, open('_baseline_final.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
