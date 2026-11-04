import json

with open('quant_framework/campaigns/USA_news_news12/news12_fields_UNFILTERED.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = data.get('results', [])
print(f"Total fields: {len(fields)}")

matrix_fields = [f for f in fields if f.get('type') == 'MATRIX' and f.get('coverage', 0) > 0.5]
print(f"High coverage MATRIX fields: {len(matrix_fields)}")
for f in sorted(matrix_fields, key=lambda x: x.get('alphaCount', 0), reverse=True)[:35]:
    desc = f.get('description', '') or ''
    print(f"{f['id']:35} | cov: {f.get('coverage', 0):.2f} | alphas: {f.get('alphaCount', 0):3} | {desc[:60]}")

print("\n--- High coverage VECTOR fields ---")
vector_fields = [f for f in fields if f.get('type') == 'VECTOR' and f.get('coverage', 0) > 0.5]
print(f"High coverage VECTOR fields: {len(vector_fields)}")
for f in sorted(vector_fields, key=lambda x: x.get('alphaCount', 0), reverse=True)[:35]:
    desc = f.get('description', '') or ''
    print(f"{f['id']:35} | cov: {f.get('coverage', 0):.2f} | alphas: {f.get('alphaCount', 0):3} | {desc[:60]}")
