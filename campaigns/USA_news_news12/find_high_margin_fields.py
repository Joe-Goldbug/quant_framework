import json

with open('quant_framework/campaigns/USA_news_news12/news12_fields_UNFILTERED.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = data.get('results', [])
candidates = []
for f in fields:
    desc = (f.get('description') or '').lower()
    fid = f.get('id', '').lower()
    cov = f.get('coverage', 0)
    alphas = f.get('alphaCount', 0)
    if cov > 0.8:
        candidates.append((alphas, f['id'], f['type'], cov, f.get('description', '')))

candidates.sort(reverse=True)
print(f"Total fields with cov > 0.8: {len(candidates)}")
print(f"{'Field ID':35} | {'Type':6} | {'Cov':4} | {'Alphas':6} | {'Description'}")
print("-" * 90)
for a, fid, ftype, cov, desc in candidates[:50]:
    print(f"{fid:35} | {ftype:6} | {cov:.2f} | {a:6} | {desc[:40]}")
