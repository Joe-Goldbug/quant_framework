# -*- coding: utf-8 -*-
import json
raw = json.load(open('news12_fields_full.json', encoding='utf-8'))
fs = raw['results'] if isinstance(raw, dict) and 'results' in raw else raw


def show(pat, title, limit=40):
    print('=== %s ===' % title)
    n = 0
    for f in fs:
        if pat(f['id'].lower()):
            print('  %-50s type=%-7s cov=%-8s | %s' % (
                f['id'], str(f.get('type')), str(f.get('coverage')),
                str(f.get('description'))[:78]))
            n += 1
            if n >= limit:
                break
    print('  (共展示 %d)' % n)
    print()


pats = ['earnings', 'eps', 'pe_ratio', 'price_to', 'short', 'mkt_cap',
        'dividend', 'estimate', 'expected', 'surprise', 'consensus', 'forecast']
show(lambda x: any(p in x for p in pats), '基本面 / 盈余相关字段', 50)
show(lambda x: 'mins_chg' in x, 'news_mins_chg 族 (完全未测)', 10)
show(lambda x: 'z_min' in x, 'nws12_*_z_min VECTOR 族 (完全未测)', 25)
show(lambda x: 'mkt_cap' in x or 'sold_short' in x, 'mkt_cap / short 字段', 12)
