# -*- coding: utf-8 -*-
"""零成本：剔除 fnd69 覆盖塌陷伪影后，重算设置档决策表。

背景：NONE 档的高 σ/高 Ret 全部来自 fnd69（覆盖率塌陷 ⇒ 2021 极端收益 + 2022-23 零持仓冻结）。
若不剔除，会把伪影当成 σ 杠杆。必须剔除后再决策。
"""
import json, os, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
full = json.load(open("account_alpha_history_full.json", encoding="utf-8"))
code_of = {r["id"]: (r.get("code") or "") for r in full}
for r in recs:
    r["n_fail"] = len(r["fails"]); r["n_warn"] = len(r["warns"])


def ds_of(c):
    return sorted(set(re.findall(r"\b([a-z]+\d+)_[a-z0-9_]+", c or "")))


u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]
for r in u:
    r["ds"] = ds_of(code_of.get(r["id"], ""))
    r["is_fund"] = any(d.startswith(("fnd", "oth")) for d in r["ds"])
fu = [r for r in u if r["is_fund"]]
fu_nof69 = [r for r in fu if "fnd69" not in r["ds"]]

print("=" * 118)
print("★ 剔除 fnd69 后，基本面 alpha 的设置档决策表")
print("=" * 118)
print(f"  基本面 n={len(fu)}   剔除 fnd69 后 n={len(fu_nof69)}")
print()
print(f"  {'neut':<14}{'n':>5}{'零fail':>8}{'率':>8}{'Sh中位':>9}{'Sh最高':>8}{'σ中位%':>9}"
      f"{'Ret中位%':>10}{'Mgn中位':>9}{'TO中位%':>9}")
for name, grp in (("全部基本面", fu), ("剔除fnd69", fu_nof69)):
    print(f"  --- {name} ---")
    tab = defaultdict(list)
    for r in grp:
        tab[r["neutralization"] or "?"].append(r)
    for k in sorted(tab, key=lambda k: -len(tab[k])):
        g = tab[k]
        sh = sorted((r["sharpe"] or 0) for r in g)
        sg = sorted(r["returns"] / r["sharpe"] for r in g if (r["sharpe"] or 0) > 0.3)
        rt = sorted((r["returns"] or 0) for r in g)
        mg = sorted((r["margin"] or 0) for r in g)
        to = sorted((r["turnover"] or 0) for r in g)
        z = sum(1 for r in g if r["n_fail"] == 0)
        print(f"  {k:<14}{len(g):>5}{z:>8}{(z/len(g)):>8.3f}{sh[len(sh)//2]:>9.2f}{max(sh):>8.2f}"
              f"{(sg[len(sg)//2]*100 if sg else 0):>9.2f}{rt[len(rt)//2]*100:>10.2f}"
              f"{(mg[len(mg)//2]*10000 if mg else 0):>9.2f}{to[len(to)//2]*100:>9.2f}")

print()
print("=" * 118)
print("★ 门禁可达性：各档要同时过 Sh>=1.58 & Fit>=1.0，需要什么 σ？")
print("=" * 118)
print("  Fit = Sh·√(Ret/max(TO,0.125)),  Ret = Sh·σ")
print("  ⇒ TO<12.5% 时 Fit = Sh^1.5·√(8σ) ⇒ σ_req = (1/1.58^1.5)²/8 = %.4f (%.2f%%)" %
      ((1 / (1.58 ** 1.5)) ** 2 / 8, (1 / (1.58 ** 1.5)) ** 2 / 8 * 100))
print("  ⇒ TO>=12.5% 时 Ret 需 >= 1.0²·TO/1.58² = %.4f·TO（TO=15%% ⇒ Ret>=%.2f%%）" %
      (1.0 / (1.58 ** 2), 1.0 / (1.58 ** 2) * 0.15))
print()
print("  各档实测 σ 与 Ret/TO 能力：")
for k in ("STATISTICAL", "MARKET", "NONE", "INDUSTRY", "SUBINDUSTRY"):
    g = [r for r in fu_nof69 if r["neutralization"] == k]
    if not g:
        continue
    sg = sorted(r["returns"] / r["sharpe"] for r in g if (r["sharpe"] or 0) > 0.3)
    to = sorted((r["turnover"] or 0) for r in g)
    sm = (sg[len(sg)//2] if sg else 0)
    tm = (to[len(to)//2] if to else 0)
    need = (1 / (1.58 ** 1.5)) ** 2 / 8 if tm < 0.125 else None
    ret_at = 1.58 * sm
    fit_at = 1.58 * (ret_at / max(tm, 0.125)) ** 0.5
    verdict = "✅可达" if (need is None or sm >= need) else ("❌σ不足" if need else "TO>=12.5%→Ret需≥%.2f%%" % (1.0/(1.58**2)*tm*100))
    print(f"    {k:<14} n={len(g):<4} σ中位={sm*100:>6.2f}%  TO中位={tm*100:>6.2f}%  "
          f"Sh=1.58 时 Ret={ret_at*100:>6.2f}%  Fit≈{fit_at:>5.2f}  {verdict}")

print()
print("=" * 118)
print("★ 零 fail 行的 Sh 上界（历史天花板）：基本面 vs 全体")
print("=" * 118)
for name, grp in (("基本面", fu), ("全体", u)):
    z = [r for r in grp if r["n_fail"] == 0]
    sh = sorted((r["sharpe"] or 0) for r in z)
    print(f"  {name:<8} 零fail n={len(z):<4} Sh: min={sh[0]:.2f} p50={sh[len(sh)//2]:.2f} "
          f"p90={sh[int(len(sh)*0.9)]:.2f} max={sh[-1]:.2f}  "
          f"n(Sh>=1.58)={sum(1 for s in sh if s>=1.58)}")
