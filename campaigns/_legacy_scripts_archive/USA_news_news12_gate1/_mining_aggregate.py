#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""USA_news_news12_gate1 全史聚合：result JSON -> 统一数据集（按 alpha_id 去重）"""
import json, glob, os, re, collections

BASE = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\USA_news_news12_gate1"

def load(fn):
    with open(os.path.join(BASE, fn), 'r', encoding='utf-8') as f:
        return json.load(f)

def get_check(checks_list, name):
    for c in checks_list or []:
        if isinstance(c, dict) and c.get('name') == name:
            return c
        if isinstance(c, str) and c == name:
            return {'name': name}
    return None

def warn_names(checks):
    out = []
    for c in (checks.get('warning') or []):
        out.append(c['name'] if isinstance(c, dict) else c)
    return out

def fail_names(checks):
    out = []
    for c in (checks.get('fail') or []):
        out.append(c['name'] if isinstance(c, dict) else c)
    return out

rows = []
batch_files = sorted(glob.glob(os.path.join(BASE, 'batch_*_result.json')))
seen = {}
for fp in batch_files:
    fn = os.path.basename(fp)
    try:
        d = load(fn)
    except Exception as e:
        print('LOAD_ERR', fn, e); continue
    for r in d.get('alpha_results', []):
        aid = r.get('alpha_id') or r.get('id')
        m = r.get('metrics', {}) or {}
        ck = r.get('checks', {}) or {}
        ra = r.get('ra', {}) or {}
        ct = get_check(ck.get('warning'), 'CLUSTER_TEST')
        rec = {
            'alpha_id': aid,
            'code': r.get('code', ''),
            'status': r.get('status', ''),
            'sharpe': m.get('sharpe'),
            'fitness': m.get('fitness'),
            'turnover': m.get('turnover'),
            'returns': m.get('returns'),
            'drawdown': m.get('drawdown'),
            'margin': m.get('margin'),
            'longCount': m.get('longCount'),
            'shortCount': m.get('shortCount'),
            'two_year_sharpe': m.get('two_year_sharpe'),
            'sub_universe_sharpe': m.get('sub_universe_sharpe'),
            'investability_sharpe': m.get('investability_sharpe'),
            'risk_neutralized_sharpe': m.get('risk_neutralized_sharpe'),
            'cluster': (ct or {}).get('value'),
            'cluster_limit': (ct or {}).get('limit'),
            'fail': fail_names(ck),
            'warn': warn_names(ck),
            'ra_failed': ra.get('ra_failed'),
            'ra_failed_checks': ra.get('ra_failed_checks'),
            'universe': (r.get('settings') or {}).get('universe'),
            'neut': (r.get('settings') or {}).get('neutralization'),
            'decay': (r.get('settings') or {}).get('decay'),
            'src': [fn],
        }
        if aid in seen:
            seen[aid]['src'].append(fn)
            # 若后出现带 cluster 而前没有，补 cluster
            if seen[aid]['cluster'] is None and rec['cluster'] is not None:
                seen[aid]['cluster'] = rec['cluster']; seen[aid]['cluster_limit'] = rec['cluster_limit']
            # 若先出现 UNSUBMITTED 后有其他状态，保留更“新”状态（简单策略：后覆盖 status 若非 UNSUBMITTED）
            if rec['status'] and rec['status'] != 'UNSUBMITTED':
                for k in ('status','sharpe','fitness','turnover','returns','fail','warn','ra_failed','ra_failed_checks'):
                    seen[aid][k] = rec[k]
        else:
            seen[aid] = rec
            rows.append(rec)

# 从 summary_*.json 交叉补全（仅当 result 中没有该 alpha_id 时新增）
sum_files = sorted(glob.glob(os.path.join(BASE, 'summary_gate*.json')))
sum_added = 0
for fp in sum_files:
    fn = os.path.basename(fp)
    try:
        d = load(fn)
    except Exception:
        continue
    for r in d.get('rows', []):
        aid = r.get('alpha_id')
        if not aid or aid in seen:
            continue
        seen[aid] = {
            'alpha_id': aid, 'code': r.get('expression', ''),
            'sharpe': r.get('sharpe'), 'fitness': r.get('fitness'),
            'turnover': r.get('turnover'), 'returns': r.get('returns'),
            'drawdown': r.get('drawdown'), 'margin': r.get('margin_bps'),
            'longCount': r.get('longCount'), 'shortCount': r.get('shortCount'),
            'two_year_sharpe': r.get('two_year_sharpe'),
            'sub_universe_sharpe': r.get('sub_sharpe'),
            'investability_sharpe': r.get('inv_sharpe'),
            'risk_neutralized_sharpe': r.get('rn_sharpe'),
            'cluster': r.get('cluster'), 'cluster_limit': r.get('cluster_limit'),
            'fail': r.get('fail_checks'), 'warn': r.get('warning_checks'),
            'ra_failed': r.get('ra_failed'), 'ra_failed_checks': r.get('ra_failed_checks'),
            'universe': None, 'neut': None, 'decay': None, 'src': ['summary:' + fn],
        }
        rows.append(seen[aid]); sum_added += 1

out = {'total_unique': len(rows), 'batch_result_files': len(batch_files), 'summary_added': sum_added, 'rows': rows}
with open(os.path.join(BASE, '_mining_all_rows.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

# 简报
print('result files:', len(batch_files))
print('summary added:', sum_added)
print('unique alphas:', len(rows))
print('with cluster value:', sum(1 for r in rows if r['cluster'] is not None))
print('with sharpe:', sum(1 for r in rows if r['sharpe'] is not None))
print('statuses:', collections.Counter(r['status'] for r in rows))
print('cluster range:', min([r['cluster'] for r in rows if r['cluster'] is not None], default=None),
      max([r['cluster'] for r in rows if r['cluster'] is not None], default=None))
