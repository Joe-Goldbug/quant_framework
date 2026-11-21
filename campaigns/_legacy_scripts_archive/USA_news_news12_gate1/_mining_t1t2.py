#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1+T2: CLUSTER_TEST 分布 / warning 组成"""
import json, collections, os

BASE = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\USA_news_news12_gate1"
with open(os.path.join(BASE, '_mining_all_rows.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
rows = data['rows']
valid = [r for r in rows if r['sharpe'] is not None]
err = [r for r in rows if r['sharpe'] is None]
print('总唯一:', len(rows), ' 有效(有sharpe):', len(valid), ' 无效:', len(err))
for r in err:
    print('  ERR行:', r['alpha_id'], r['src'], r['status'], r['code'][:80])

# ---- T1 ----
print('\n===== T1: CLUSTER_TEST 分布 =====')
cvals = sorted([r['cluster'] for r in valid if r['cluster'] is not None], reverse=True)
print('有 cluster 数值行数:', len(cvals))
print('cluster >= 1.45 行数:', sum(1 for c in cvals if c >= 1.45))
print('top20 cluster:', cvals[:20])
# 分布直方
buckets = collections.Counter()
for c in cvals:
    buckets[round(c, 1)] += 1
print('分桶(0.1):', dict(sorted(buckets.items(), reverse=True)))

hi = [r for r in valid if r['cluster'] is not None and r['cluster'] >= 1.45]
hi.sort(key=lambda r: -r['cluster'])
print('\n--- CLUSTER >= 1.45 全部行（降序）---')
for r in hi:
    print(f"\n[{r['alpha_id']}] CLUSTER={r['cluster']} (limit {r['cluster_limit']})")
    print(f"  expr: {r['code']}")
    print(f"  Sh={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} Ret={r['returns']} 2Y={r['two_year_sharpe']} sub={r['sub_universe_sharpe']} rn={r['risk_neutralized_sharpe']} inv={r['investability_sharpe']} LC={r['longCount']} SC={r['shortCount']}")
    print(f"  fail={r['fail']} warn={r['warn']} ra_failed={r['ra_failed']} src={r['src']}")

# top5 结构特征
print('\n--- top5 共同结构特征 ---')
for r in hi[:5]:
    print(f"[{r['alpha_id']}] {r['code']}")

# ---- T2 ----
print('\n===== T2: warning 组成 =====')
warn_counter = collections.Counter()
for r in valid:
    for w in (r['warn'] or []):
        warn_counter[w] += 1
print('warning 名称分布（有效行 n=%d）:' % len(valid))
for k, v in warn_counter.most_common():
    print(f'  {k}: {v}')
no_theme = [r for r in valid if 'MATCHES_THEMES' not in (r['warn'] or [])]
print('\n无 MATCHES_THEMES 警告行数:', len(no_theme))
for r in no_theme[:20]:
    print('  ', r['alpha_id'], r['warn'], r['src'])
no_cl = [r for r in valid if 'CLUSTER_TEST' not in (r['warn'] or [])]
print('\n无 CLUSTER_TEST 警告行数:', len(no_cl))
for r in no_cl[:20]:
    print('  ', r['alpha_id'], r['warn'], r['cluster'], r['src'])
# fail 分布
fail_counter = collections.Counter()
for r in valid:
    for w in (r['fail'] or []):
        fail_counter[w] += 1
print('\nfail 名称分布:')
for k, v in fail_counter.most_common():
    print(f'  {k}: {v}')
