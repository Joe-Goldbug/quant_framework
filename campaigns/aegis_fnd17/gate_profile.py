# -*- coding: utf-8 -*-
"""从全账户历史提取"零 fail + Sh>=1.58 + Fit>=1.0"的可达画像，并按数据集族归因。"""
import json, os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
for r in recs:
    r["n_fail"] = len(r["fails"]); r["n_warn"] = len(r["warns"])
u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]

# 复用全量代码表
full = json.load(open("account_alpha_history_full.json", encoding="utf-8"))
code_of = {r["id"]: r.get("code") or "" for r in full}
ds_of = {}
for r in full:
    ds_of[r["id"]] = r.get("datasets") or []

def fund(r):
    ds = ds_of.get(r["id"]) or []
    return [d for d in ds if d.startswith(("fnd", "oth"))]

print("=" * 116)
print("★ 目标画像：n_fail==0 且 Sh>=1.58 且 Fit>=1.0")
print("=" * 116)
hits = [r for r in u if r["n_fail"] == 0 and (r["sharpe"] or 0) >= 1.58
        and (r["fitness"] or 0) >= 1.0]
print(f"命中 {len(hits)} 条（全部数据集族）")
for r in sorted(hits, key=lambda x: -(x["sharpe"] or 0)):
    code = code_of.get(r["id"], "")
    print(f"  {r['id']:<10} {r['stage']:<4} Sh={r['sharpe']:>5.2f} Fit={r['fitness']:>5.2f} "
          f"TO={(r['turnover'] or 0)*100:>6.2f}% Ret={(r['returns'] or 0)*100:>6.2f}% "
          f"Mgn={(r['margin'] or 0)*10000:>6.2f} neut={r['neutralization']:<12} ds={','.join(ds_of.get(r['id']) or ['?'])}")
    print(f"       {code[:150]}")

print()
print("=" * 116)
print("★ 基本面数据集族中，n_fail==0 的行按 (Sh>=1.58, Fit>=1.0) 分类")
print("=" * 116)
fu = [r for r in u if fund(r)]
print(f"基本面行总数 = {len(fu)}")
print(f"  n_fail==0                        : {sum(1 for r in fu if r['n_fail']==0)}")
print(f"  n_fail==0 且 Sh>=1.58            : {sum(1 for r in fu if r['n_fail']==0 and (r['sharpe'] or 0)>=1.58)}")
print(f"  n_fail==0 且 Fit>=1.0            : {sum(1 for r in fu if r['n_fail']==0 and (r['fitness'] or 0)>=1.0)}")
print(f"  n_fail==0 且 Sh>=1.58 且 Fit>=1.0: {sum(1 for r in fu if r['n_fail']==0 and (r['sharpe'] or 0)>=1.58 and (r['fitness'] or 0)>=1.0)}")

print()
print("  按数据集族分：")
tab = defaultdict(lambda: Counter())
for r in fu:
    ds = (ds_of.get(r["id"]) or ["?"])[0]
    g = tab[ds]
    g["n"] += 1
    if r["n_fail"] == 0:
        g["zero"] += 1
        if (r["sharpe"] or 0) >= 1.58: g["sh158"] += 1
        if (r["fitness"] or 0) >= 1.0: g["fit1"] += 1
        if (r["sharpe"] or 0) >= 1.58 and (r["fitness"] or 0) >= 1.0: g["both"] += 1
print(f"  {'族':<12}{'n':>5}{'零fail':>8}{'Sh>=1.58':>10}{'Fit>=1.0':>9}{'两者皆':>9}")
for ds in sorted(tab, key=lambda d: -tab[d]["both"]):
    g = tab[ds]
    print(f"  {ds:<12}{g['n']:>5}{g['zero']:>8}{g['sh158']:>10}{g['fit1']:>9}{g['both']:>9}")

print()
print("=" * 116)
print("★ 零 fail 行的短项构成（哪些项被降级为 WARNING）")
print("=" * 116)
z = [r for r in u if r["n_fail"] == 0]
print("  warn 项频次:", Counter(w for r in z for w in r["warns"]).most_common(14))
print()
print("  ★ 零 fail 行的关键指标分布：")
for f in ("sharpe", "fitness", "turnover", "returns", "margin"):
    v = [r[f] for r in z if r.get(f) is not None]
    if v:
        q = sorted(v)
        print(f"    {f:<10} min={min(v):>9.4f} p25={q[len(q)//4]:>9.4f} med={q[len(q)//2]:>9.4f} "
              f"p75={q[3*len(q)//4]:>9.4f} max={max(v):>9.4f}")
print()
print("  ★ 零 fail 且 Sh>=1.58 的行的指标分布（可达目标画像）：")
z2 = [r for r in z if (r["sharpe"] or 0) >= 1.58]
for f in ("sharpe", "fitness", "turnover", "returns", "margin"):
    v = [r[f] for r in z2 if r.get(f) is not None]
    if v:
        q = sorted(v)
        print(f"    {f:<10} min={min(v):>9.4f} p25={q[len(q)//4]:>9.4f} med={q[len(q)//2]:>9.4f} "
              f"p75={q[3*len(q)//4]:>9.4f} max={max(v):>9.4f}")
