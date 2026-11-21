# -*- coding: utf-8 -*-
"""判定平台 fail↔warning 升级规则：手工决策树（不依赖 sklearn）。

目标：搞清"什么条件下 checks.fail 非空"，因为本战役验收标准是"零 fail"。
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

HARD = {"LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE", "IS_LADDER_SHARPE",
        "LOW_SUB_UNIVERSE_SHARPE", "LOW_ROBUST_UNIVERSE_SHARPE",
        "HIGH_TURNOVER", "LOW_TURNOVER", "CONCENTRATED_WEIGHT", "UNITS"}

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
for r in recs:
    r["n_fail"] = len(r["fails"]); r["n_warn"] = len(r["warns"])
u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]

print("=" * 104)
print("★ 特征可用性盘点")
print("=" * 104)
print("  字段:", sorted(u[0].keys()))

print()
print("=" * 104)
print("★ 假设 H：升级规则 = 「硬指标短了几项」")
print("=" * 104)
for r in u:
    r["n_short"] = len([c for c in set(r["fails"] + r["warns"]) if c in HARD])
tab = defaultdict(Counter)
for r in u:
    tab[r["n_short"]]["n_fail>0" if r["n_fail"] else "n_fail=0"] += 1
print(f"  {'短项数':<8}{'n_fail=0':>10}{'n_fail>0':>10}")
for k in sorted(tab):
    print(f"  {k:<8}{tab[k]['n_fail=0']:>10}{tab[k]['n_fail>0']:>10}")

print()
print("  ⇒ 若完全由「短项数」决定，则 n_fail=0 ↔ 短项数==1（且不是 LOW_FITNESS 单项）")

print()
print("=" * 104)
print("★ 逐候选判别变量：对 LOW_SHARPE 短项行，FAIL vs WARN")
print("=" * 104)
F = [r for r in u if "LOW_SHARPE" in r["fails"]]
W = [r for r in u if "LOW_SHARPE" in r["warns"]]
print(f"  n(FAIL)={len(F)}  n(WARN)={len(W)}")
for feat in ("fitness", "turnover", "returns", "margin", "two_year_sharpe",
             "sub_universe_sharpe"):
    fv = [r[feat] for r in F if r.get(feat) is not None]
    wv = [r[feat] for r in W if r.get(feat) is not None]
    if not fv or not wv:
        continue
    # 找最佳切点
    vals = sorted(set(fv) | set(wv))
    best = None
    for t in vals:
        a = sum(1 for x in fv if x <= t); b = sum(1 for x in wv if x <= t)
        # 纯度：被分到 <=t 的 FAIL 占比 vs WARN 占比
        acc = (a + (len(wv) - b)) / (len(fv) + len(wv))
        if best is None or acc > best[1]:
            best = (t, acc, a, b)
    t, acc, a, b = best
    print(f"  {feat:<20} FAIL范围[{min(fv):>8.3f},{max(fv):>8.3f}] "
          f"WARN范围[{min(wv):>8.3f},{max(wv):>8.3f}]  最佳切点={t:.3f} 准确率={acc:.3f} "
          f"(切点下 FAIL<=t: {a}, WARN>t: {len(wv)-b})")

print()
print("=" * 104)
print("★ 关键检验：LOW_SHARPE 短项行中，「是否同时 LOW_FITNESS 短」能否完全解释？")
print("=" * 104)
c = defaultdict(Counter)
for r in F + W:
    tag = "FAIL" if "LOW_SHARPE" in r["fails"] else "WARN"
    c["Fit短" if "LOW_FITNESS" in (r["fails"] + r["warns"]) else "Fit过"][tag] += 1
for k in sorted(c):
    print(f"  {k:<8} {dict(c[k])}")

print()
print("  ⇒ 若 (Fit短→FAIL, Fit过→WARN) 完全分离，规则就是：Sharpe 短 且 Fitness 也短 ⇒ FAIL")
print()
print("  检验 LOW_FITNESS 短项行同构：")
c2 = defaultdict(Counter)
for r in u:
    if "LOW_FITNESS" in (r["fails"] + r["warns"]):
        tag = "FAIL" if "LOW_FITNESS" in r["fails"] else "WARN"
        c2["Sh短" if "LOW_SHARPE" in (r["fails"] + r["warns"]) else "Sh过"][tag] += 1
for k in sorted(c2):
    print(f"  {k:<8} {dict(c2[k])}")
