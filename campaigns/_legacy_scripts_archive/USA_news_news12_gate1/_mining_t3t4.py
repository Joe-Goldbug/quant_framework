#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3: 边界样本扫描 + 行数口径核实 + 关键 alpha 检索"""
import json, os

BASE = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\USA_news_news12_gate1"
with open(os.path.join(BASE, '_mining_all_rows.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
rows = [r for r in data['rows'] if r['sharpe'] is not None]

def show(r, extra=''):
    print(f"  [{r['alpha_id']}] Sh={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} Ret={r['returns']} 2Y={r['two_year_sharpe']} sub={r['sub_universe_sharpe']} rn={r['risk_neutralized_sharpe']} inv={r['investability_sharpe']} CL={r['cluster']} LC={r['longCount']} SC={r['shortCount']} DD={r['drawdown']} {extra}")
    print(f"    expr: {r['code']}")
    print(f"    fail={r['fail']}")
    print(f"    warn={r['warn']} ra_failed={r['ra_failed']} src={r['src']}")

# ---- 口径核实 ----
print('===== 口径核实 =====')
print('result 聚合唯一 alpha:', data['total_unique'], '（有效', len(rows), '+ ERROR 1）')
try:
    with open(os.path.join(BASE, '_baseline_final.json'), 'r', encoding='utf-8') as f:
        bl = json.load(f)
    bl_ids = {b['aid'] for b in bl}
    my_ids = {r['alpha_id'] for r in data['rows'] if r['alpha_id']}
    print('_baseline_final.json 行数:', len(bl), ' 其中不在聚合集:', len(bl_ids - my_ids), ' 聚合集多出:', len(my_ids - bl_ids))
    print('  多出的 id:', sorted(my_ids - bl_ids)[:30])
except Exception as e:
    print('baseline err', e)

# ---- T3 ----
print('\n===== T3a: Ret >= 7% top10（降序） =====')
hi_ret = sorted([r for r in rows if r['returns'] is not None and r['returns'] >= 0.07], key=lambda r: -r['returns'])
print('Ret>=7% 总数:', len(hi_ret))
for r in hi_ret[:10]:
    show(r)

print('\n===== T3b: TO <= 85% 且 Sh >= 1.2 =====')
lowto = sorted([r for r in rows if r['turnover'] is not None and r['turnover'] <= 0.85 and r['sharpe'] is not None and r['sharpe'] >= 1.2], key=lambda r: -r['sharpe'])
print('命中数:', len(lowto))
for r in lowto:
    show(r)

print('\n===== T3c: 2Y >= 2.0 =====')
hi2y = sorted([r for r in rows if r['two_year_sharpe'] is not None and r['two_year_sharpe'] >= 2.0], key=lambda r: -r['two_year_sharpe'])
print('命中数:', len(hi2y))
for r in hi2y:
    show(r)

# ---- T4 检索 ----
print('\n===== T4: 关键 alpha 检索 =====')
targets = ['2rjx3ow8', 'mLYNEWjW', 'leMYnJZn', 'SH165', 'd5K6wxlx', 'N1eGk79E']
for t in targets:
    hits = [r for r in data['rows'] if r['alpha_id'] == t]
    print(f'\n--- {t}: {len(hits)} hit ---')
    for r in hits:
        show(r)
# 模糊：id 以 SH165 开头
sh = [r for r in data['rows'] if r['alpha_id'] and r['alpha_id'].upper().startswith('SH165')]
print('\nSH165 前缀匹配:', [r['alpha_id'] for r in sh])
# 2rjx 前缀族
fam = [r for r in data['rows'] if r['alpha_id'] and r['alpha_id'].startswith('2rjx')]
print('2rjx 前缀族:', [(r['alpha_id'], r['sharpe'], r['cluster']) for r in fam])
