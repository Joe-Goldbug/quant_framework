# -*- coding: utf-8 -*-
"""暴力搜索 FAIL↔WARNING 的判别规则（只用已挖掘的免费历史）。"""
import json, os, sys, io, itertools
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
for r in recs:
    r["n_fail"] = len(r["fails"]); r["n_warn"] = len(r["warns"])
u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]

# 构造标签：LOW_SHARPE 短项行，FAIL(1) vs WARN(0)
lab = []
for r in u:
    if "LOW_SHARPE" in r["fails"]:
        lab.append((r, 1))
    elif "LOW_SHARPE" in r["warns"]:
        lab.append((r, 0))
print(f"样本 n={len(lab)}  FAIL={sum(y for _,y in lab)}")

FEATS = {
    "fit_ge_1":   lambda r: 1 if (r["fitness"] or 0) >= 1.0 else 0,
    "fit_ge_0.9": lambda r: 1 if (r["fitness"] or 0) >= 0.9 else 0,
    "fit_ge_0.8": lambda r: 1 if (r["fitness"] or 0) >= 0.8 else 0,
    "fit_ge_0.75":lambda r: 1 if (r["fitness"] or 0) >= 0.75 else 0,
    "sh_ge_1.5":  lambda r: 1 if (r["sharpe"] or 0) >= 1.5 else 0,
    "sh_ge_1.2":  lambda r: 1 if (r["sharpe"] or 0) >= 1.2 else 0,
    "to_lt_0.125":lambda r: 1 if (r["turnover"] or 0) < 0.125 else 0,
    "to_lt_0.15": lambda r: 1 if (r["turnover"] or 0) < 0.15 else 0,
    "to_lt_0.2":  lambda r: 1 if (r["turnover"] or 0) < 0.2 else 0,
    "to_lt_0.4":  lambda r: 1 if (r["turnover"] or 0) < 0.4 else 0,
    "ret_ge_0.05":lambda r: 1 if (r["returns"] or 0) >= 0.05 else 0,
    "ret_ge_0.03":lambda r: 1 if (r["returns"] or 0) >= 0.03 else 0,
    "mgn_ge_0.001":lambda r: 1 if (r["margin"] or 0) >= 0.001 else 0,
    "ladder_ge_1.58":lambda r: 1 if (r["two_year_sharpe"] or 0) >= 1.58 else 0,
    "sub_ge_0.6": lambda r: 1 if (r["sub_universe_sharpe"] or 0) >= 0.6 else 0,
    "trunc_0.08": lambda r: 1 if r["truncation"] == 0.08 else 0,
    "decay_0":    lambda r: 1 if r["decay"] == 0 else 0,
    "nshort_le_2":lambda r: 1 if len(r["short"]) <= 2 else 0,
    "nshort_le_3":lambda r: 1 if len(r["short"]) <= 3 else 0,
    "nshort_le_4":lambda r: 1 if len(r["short"]) <= 4 else 0,
    "neut_stat":  lambda r: 1 if r["neutralization"] == "STATISTICAL" else 0,
    "neut_none":  lambda r: 1 if r["neutralization"] == "NONE" else 0,
    "neut_mkt":   lambda r: 1 if r["neutralization"] == "MARKET" else 0,
    "nlong_ge_400":lambda r: 1 if (r["longCount"] or 0) >= 400 else 0,
    "nshortpos_ge_400":lambda r: 1 if (r["shortCount"] or 0) >= 400 else 0,
}

def acc(rule):
    c = 0
    for r, y in lab:
        p = rule(r)
        if p == y:
            c += 1
    return c / len(lab)

print("\n=== 单特征最佳切点 ===")
best_single = []
for name, fn in FEATS.items():
    a = acc(fn)
    ainv = acc(lambda r, fn=fn: 1 - fn(r))
    b, bi = max((a, name), (ainv, "~" + name))
    best_single.append((b, bi))
    print(f"  {name:<20} acc={b:.4f}  (规则: {bi})")
best_single.sort(reverse=True)
print("\n  Top5:", best_single[:5])

print("\n=== 两特征组合（AND / OR / XOR）暴力搜索 ===")
res = []
names = list(FEATS)
for n1, n2 in itertools.combinations(names, 2):
    f1, f2 = FEATS[n1], FEATS[n2]
    for op, fn in (("AND", lambda r: f1(r) & f2(r)),
                   ("OR",  lambda r: f1(r) | f2(r)),
                   ("XOR", lambda r: f1(r) ^ f2(r))):
        a = acc(fn)
        if a > 0.93:
            res.append((a, f"{n1} {op} {n2}"))
res.sort(reverse=True)
for a, rule in res[:15]:
    print(f"  acc={a:.4f}  {rule}")

print("\n=== 三特征组合（限定在 top 单特征内）===")
top = [bi.lstrip("~") for _, bi in best_single[:8]]
res3 = []
for combo in itertools.combinations(top, 3):
    fs = [FEATS[c] for c in combo]
    for bits in range(1, 8):
        rule = lambda r, fs=fs, bits=bits: ((fs[0](r) >> (bits & 1) & 1) |
                                            (fs[1](r) >> (bits >> 1) & 1) |
                                            (fs[2](r) >> (bits >> 2) & 1))
        a = acc(rule)
        if a > 0.95:
            res3.append((a, combo, bits))
res3.sort(reverse=True)
seen = set()
for a, combo, bits in res3[:25]:
    key = (combo, bits)
    if key in seen: continue
    seen.add(key)
    print(f"  acc={a:.4f}  {'+'.join(combo)}  mask={bits:03b}")
