# -*- coding: utf-8 -*-
import json
A = json.load(open('_baseline_final.json', encoding='utf-8'))
print('=== 双约束联立 (Sh=1.58) ===')
print('Fit>=1.0   需 Ret >= TO/2.4964')
print('Mgn>=10bps 需 Ret >= 0.5*TO')
print('=> 更紧者 = 0.5*TO (因 0.5 > 0.4004)')
print()
print('TO%   需Ret%(Mgn)  需Ret%(Fit)  家族最高Ret7.86%  判定')
for to in (5, 8, 11, 15, 20, 30, 50, 70, 115):
    nm, nf = 0.5 * to, to / 2.4964
    ok = 'YES' if 7.86 >= nm else 'NO (缺%.1fx)' % (nm / 7.86)
    print('%5d %12.2f %12.2f %14s  %s' % (to, nm, nf, '7.86', ok))
print()
print('=== 关键: 家族 Ret 天花板 7.86% => TO 必须 <= 15.7% 才可能 Mgn 达标 ===')
print()
print('=== 宽持仓健康样本 (lc+sc>200) 的 R/TO 排行 (Mgn=20*Ret/TO) ===')
rows = [r for r in A if (r['to'] or 0) > 0 and (r['ret'] or 0) > 0 and (r['lc'] or 0) + (r['sc'] or 0) > 200]
rows.sort(key=lambda x: -(x['ret'] / x['to']))
print('%6s%7s%7s%7s%7s%6s%10s %s' % ('Sh', 'TO%', 'Ret%', 'R/TO', 'Mgn', '2Y', 'L/S', 'id'))
for r in rows[:14]:
    to, ret = r['to'] * 100, r['ret'] * 100
    print('%6.2f%7.1f%7.2f%7.3f%7.2f%6.2f%10s %s' % (
        r['sh'] or 0, to, ret, ret / to, 20 * ret / to, r['y2'] or 0,
        str(r['lc']) + '/' + str(r['sc']), r['aid']))
print()
print('=== Fit 反解: 若 Sh 提升, pooled 家族是否自动达标? ===')
for sh, to, ret in [(0.61, 5.2, 2.09), (1.0, 5.2, 2.09), (1.28, 5.2, 2.09),
                    (1.58, 5.2, 2.09), (1.58, 5.2, 2.6), (1.19, 37.5, 3.74)]:
    fit = sh * ((ret / max(to, 0.11)) ** 0.5)
    mgn = 20 * ret / to
    print('  Sh=%.2f TO=%.1f%% Ret=%.2f%% -> Fit=%.2f (需1.0) Mgn=%.2fbps (需10)' % (sh, to, ret, fit, mgn))
print()
print('=== pooled 家族全部样本 (ts_sum 或 backfill 内核) ===')
for r in A:
    e = r['expr'] or ''
    if 'max_up_amt' in e or 'max_dn_amt' in e or 'max_up_ret' in e:
        to, ret = (r['to'] or 0) * 100, (r['ret'] or 0) * 100
        print('  Sh=%5.2f Fit=%5.2f TO=%6.1f Ret=%5.2f R/TO=%6.3f Mgn=%5.2f 2Y=%5.2f L/S=%s %s' % (
            r['sh'] or 0, r['fit'] or 0, to, ret, ret / to if to else 0,
            20 * ret / to if to else 0, r['y2'] or 0, str(r['lc']) + '/' + str(r['sc']), r['aid']))
        print('     ', e[:120])
