# -*- coding: utf-8 -*-
"""Task B: expression mining - operators x fields co-occurrence, unexplored cross cells."""
import json, os, re
from collections import Counter, defaultdict

D = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(D, '_w11h_master.json'), encoding='utf-8'))
catalog = json.load(open(os.path.join(D, 'news12_fields_full.json'), encoding='utf-8'))
cat_ids = {f['id'] for f in catalog}

OPS = set('''rank add subtract multiply divide ts_zscore ts_backfill ts_mean ts_std_dev ts_rank ts_delta
ts_delay ts_sum ts_std_dev ts_regression ts_corr ts_covariance ts_decay_linear ts_returns ts_av_diff
vec_avg vec_sum vec_max vec_min vec_count vec_range vec_stddev vec_norm vec_ir winsorize reverse
group_rank group_neutralize group_zscore trade_when less greater days_from_last_change hump
regression residual signed_power ts_min ts_max ts_arg_max ts_arg_min ts_scale ts_product
ts_moment ts_skewness ts_kurtosis ts_median ts_mode ts_quantile ts_theilsen ts_returns'''.split())

def parse(expr):
    toks = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\d+\.?\d*', expr)
    ops, fields, consts = set(), set(), set()
    for t in toks:
        if t in OPS:
            ops.add(t)
        elif re.fullmatch(r'\d+\.?\d*', t):
            consts.add(t)
        else:
            fields.add(t)
    return ops, fields, consts

field_cnt = Counter()
op_cnt = Counter()
field_ops = defaultdict(Counter)   # field -> Counter(op)
expr_ops = defaultdict(set)        # field -> set of exprs
pair_cnt = Counter()
n_expr = 0
unknown_fields = Counter()

for r in rows:
    e = r.get('expr') or ''
    if not e:
        continue
    n_expr += 1
    ops, fields, consts = parse(e)
    for o in ops:
        op_cnt[o] += 1
    for f in fields:
        field_cnt[f] += 1
        if f not in cat_ids:
            unknown_fields[f] += 1
        for o in ops:
            field_ops[f][o] += 1
            pair_cnt[(f, o)] += 1

out = []
P = out.append
P(f"# Task B 表达式挖掘 (n_expr={n_expr})")
P(f"\n## B0 总览")
P(f"使用算子 {len(op_cnt)} 种: {dict(op_cnt.most_common())}")
P(f"使用字段 {len(field_cnt)} 种 (catalog 共 {len(cat_ids)})")
P(f"未知(不在 catalog)字段: {dict(unknown_fields.most_common(10))}")

# fields never used
unused_cat = cat_ids - set(field_cnt)
P(f"\ncatalog 中从未使用的字段: {len(unused_cat)} 个")
for f in sorted(unused_cat)[:40]:
    meta = next(x for x in catalog if x['id'] == f)
    P(f"  {f} (cov={meta.get('coverage')}, type={meta.get('type')})")

# field usage frequency
P(f"\n## B1 字段使用频次 Top30")
for f, c in field_cnt.most_common(30):
    P(f"  {c:3d}  {f}")

# family grouping of fields
def family(f):
    for p in ['nws12_', 'news12_', 'news_']:
        if f.startswith(p):
            return f[len(p):].split('_')[0]
    return f.split('_')[0]

fam = Counter()
for f, c in field_cnt.items():
    fam[family(f)] += c
P(f"\n## B2 字段族使用: {dict(fam.most_common(15))}")

# field x operator matrix for top fields
top_fields = [f for f, _ in field_cnt.most_common(25)]
top_ops = [o for o, _ in op_cnt.most_common(15)]
P(f"\n## B3 字段×算子共现矩阵 (行=字段Top25, 列=算子Top15, .=0)")
P("field\\op      " + " ".join(f"{o[:8]:>8s}" for o in top_ops))
for f in top_fields:
    line = f"{f[:14]:14s}"
    for o in top_ops:
        c = field_ops[f].get(o, 0)
        line += f"{c:8d}" if c else f"{'.':>8s}"
    P(line)

# unexplored cross cells: (field used, op used) but pair never
P(f"\n## B4 一维已测、交叉未测的格 (字段已用>=5次, 算子已用>=20次, 但组合 0 次)")
cands = []
for f, fc in field_cnt.items():
    if fc < 5:
        continue
    for o, oc in op_cnt.items():
        if oc < 20:
            continue
        if field_ops[f].get(o, 0) == 0:
            cands.append((fc * oc, f, o, fc, oc))
cands.sort(reverse=True)
for score, f, o, fc, oc in cands[:25]:
    P(f"  {f} (x{fc}) × {o} (x{oc})   -> 从未组合")

txt = "\n".join(out)
open(os.path.join(D, '_w11h_B_out.txt'), 'w', encoding='utf-8').write(txt)
print(txt)
