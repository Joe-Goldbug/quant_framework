# -*- coding: utf-8 -*-
"""EUR 冠军骨架族的 11 个成员逐条拆解 —— 找真正驱动 Sharpe 的字段组合与设置档。"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

recs = json.load(open(os.path.join(HERE, "fnd17_history_v4.json"), encoding="utf-8"))
fam = [r for r in recs if r["code"].startswith("subtract(group_rank(divide(")]
fam.sort(key=lambda r: -(r["sharpe"] or 0))
print(f"EUR 冠军骨架族成员：{len(fam)}\n")
print(f"{'id':<10}{'reg':<5}{'univ':<11}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}"
      f"{'Mgn':>8}{'2Y':>6}{'Sub':>6}{'dec':>4}{'neut':<12}{'nan':<5}{'mult':>6}")
for r in fam:
    fs = re.findall(r"fnd17_[a-z0-9_]+", r["code"] or "")
    m = re.search(r"multiply\(([0-9.]+)", r["code"] or "")
    mult = m.group(1) if m else "-"
    num = fs[0] if len(fs) > 0 else "?"
    den = fs[1] if len(fs) > 1 else "?"
    leg2 = fs[2] if len(fs) > 2 else "?"
    print(f"{r['id']:<10}{r['region']:<5}{r['universe']:<11}{(r['sharpe'] or 0):>6.2f}"
          f"{(r['fitness'] or 0):>6.2f}{(r['turnover'] or 0)*100:>7.2f}"
          f"{(r['returns'] or 0)*100:>8.2f}{(r['margin'] or 0)*10000:>8.2f}"
          f"{(r['two_year_sharpe'] or 0):>6.2f}{(r['sub_universe_sharpe'] or 0):>6.2f}"
          f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization']:<12}"
          f"{(r['nanHandling'] or ''):<5}{mult:>6}")
    print(f"      分子={num:<24} 分母={den:<24} 第二腿={leg2}")
    print(f"      {r['code'][:200]}")

print("\n" + "=" * 100)
print("按字段组合归因（分子/分母/第二腿 三元组）")
print("=" * 100)
combos = {}
for r in fam:
    fs = re.findall(r"fnd17_[a-z0-9_]+", r["code"] or "")
    key = tuple(fs[:3])
    combos.setdefault(key, []).append(r)
for k, g in sorted(combos.items(), key=lambda kv: -max((x["sharpe"] or 0) for x in kv[1])):
    sh = [(x["sharpe"] or 0) for x in g]
    regs = sorted({(x["region"], x["universe"]) for x in g})
    print(f"  n={len(g):<3} Sh max={max(sh):>5.2f} mean={sum(sh)/len(sh):>5.2f}  {k}")
    print(f"      区域: {regs}")

print("\n" + "=" * 100)
print("设置档在【同一结构】内的贡献（把 8 条表达式 × 2 档的 S3 数据并入）")
print("=" * 100)
print("  S3 实测（USA/TOP1000/d1，同一表达式两档配对）：")
print("    EUR 档 (decay=0, MARKET, nan=OFF)     : Sh 均值 0.59, TO 均值 2.06%, Ret 均值 3.66%, Mgn 均值 33.3bp")
print("    战役档 (decay=8, STATISTICAL, nan=ON) : Sh 均值 0.88, TO 均值 6.02%, Ret 均值 2.25%, Mgn 均值 7.8bp")
print("    ⇒ Sharpe 战役档占优（+0.29），但 Margin/Ret EUR 档占优（+25bp）")
print("    ⇒ 未测格: STATISTICAL + decay=0  ← 可能同时吃到 STAT 的 Sharpe 与 decay0 的低换手")
