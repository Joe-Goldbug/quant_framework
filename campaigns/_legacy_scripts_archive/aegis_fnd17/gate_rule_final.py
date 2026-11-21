# -*- coding: utf-8 -*-
"""零成本：精确定位 FAIL↔WARNING 升级规则（对撞组逐行归因）。"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

HARD = {"LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE", "IS_LADDER_SHARPE",
        "LOW_SUB_UNIVERSE_SHARPE", "LOW_ROBUST_UNIVERSE_SHARPE",
        "HIGH_TURNOVER", "LOW_TURNOVER", "CONCENTRATED_WEIGHT", "UNITS"}
ALLNAMES = Counter()

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
for r in recs:
    r["n_fail"] = len(r["fails"])
    r["n_warn"] = len(r["warns"])
u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]

print("=" * 108)
print("★ 规则检验 1：n_fail==0 的行里，LOW_SHARPE 是否只在 warns？")
print("=" * 108)
z = [r for r in u if r["n_fail"] == 0]
print(f"  n_fail==0 行数 = {len(z)}")
print("  其中 LOW_SHARPE 在 fails 的:", sum(1 for r in z if "LOW_SHARPE" in r["fails"]))
print("  其中 LOW_SHARPE 在 warns 的:", sum(1 for r in z if "LOW_SHARPE" in r["warns"]))
print("  其中 LOW_FITNESS 在 fails 的:", sum(1 for r in z if "LOW_FITNESS" in r["fails"]))
print("  其中 LOW_FITNESS 在 warns 的:", sum(1 for r in z if "LOW_FITNESS" in r["warns"]))

print()
print("=" * 108)
print("★ 规则检验 2：单独不达标的项（其它短指标都 PASS）报 FAIL 还是 WARN？")
print("=" * 108)
solo = defaultdict(Counter)
for r in u:
    sh = set(r["short"])
    if len(sh) != 1:
        continue
    nm = list(sh)[0]
    solo[nm]["FAIL" if nm in r["fails"] else "WARN"] += 1
for nm in sorted(solo):
    print(f"  {nm:<28} {dict(solo[nm])}")

print()
print("=" * 108)
print("★ 规则检验 3：LOW_SHARPE 报 FAIL 时 n_fail 最小值 / 报 WARN 时 n_fail 分布")
print("=" * 108)
lf = [r for r in u if "LOW_SHARPE" in r["fails"]]
lw = [r for r in u if "LOW_SHARPE" in r["warns"]]
print("  LOW_SHARPE=FAIL : n_fail 分布", dict(Counter(r["n_fail"] for r in lf)))
print("  LOW_SHARPE=WARN : n_fail 分布", dict(Counter(r["n_fail"] for r in lw)))

print()
print("=" * 108)
print("★ 规则检验 4：时间轴 —— 平台是否在 2026-10-27/28 改过升级规则？")
print("=" * 108)
by_day = defaultdict(lambda: {"FAIL": 0, "WARN": 0, "n_fail0": 0, "tot": 0})
for r in u:
    d = (r.get("dateCreated") or "")[:10]
    if not d:
        continue
    g = by_day[d]
    g["tot"] += 1
    if "LOW_SHARPE" in r["fails"]:
        g["FAIL"] += 1
    elif "LOW_SHARPE" in r["warns"]:
        g["WARN"] += 1
    if r["n_fail"] == 0:
        g["n_fail0"] += 1
print(f"  {'日期':<12}{'总':>6}{'ShFAIL':>8}{'ShWARN':>8}{'n_fail=0':>10}")
for d in sorted(by_day):
    g = by_day[d]
    print(f"  {d:<12}{g['tot']:>6}{g['FAIL']:>8}{g['WARN']:>8}{g['n_fail0']:>10}")

print()
print("=" * 108)
print("★ 规则检验 5：真正『零 fail 且 Sh>=1.58 且 Fit>=1.0』的样本（全数据集族）")
print("=" * 108)
full = [r for r in u if r["n_fail"] == 0 and (r["sharpe"] or 0) >= 1.58
        and (r["fitness"] or 0) >= 1.0]
print(f"  n = {len(full)}")
for r in sorted(full, key=lambda x: -(x["sharpe"] or 0)):
    print(f"    {r['id']:<10} {r['stage']:<4} Sh={r['sharpe']:>5.2f} Fit={r['fitness']:>5.2f} "
          f"TO={(r['turnover'] or 0)*100:>6.2f}% Ret={(r['returns'] or 0)*100:>6.2f}% "
          f"Mgn={(r['margin'] or 0)*10000:>6.2f} 2Y={(r['two_year_sharpe'] or 0):>5.2f} "
          f"neut={r['neutralization']:<12} warn={','.join(r['warns'])[:40]}")
