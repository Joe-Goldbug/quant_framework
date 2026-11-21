# -*- coding: utf-8 -*-
"""零成本：设置档 × 数据集族 的零 fail 率与 σ 杠杆分析。

两个问题：
  Q1 哪个 neutralization 对基本面 alpha 最容易拿到零 fail？（平台 checks 的升级规则与 neutralization 强耦合）
  Q2 σ（年化收益/Sharpe）到底由哪个设置档决定？—— 决定 Ret 能否过 Fit 门槛
"""
import json, os, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter, defaultdict

recs = json.load(open("account_alpha_history_v2.json", encoding="utf-8"))
full = json.load(open("account_alpha_history_full.json", encoding="utf-8"))
code_of = {r["id"]: (r.get("code") or "") for r in full}
for r in recs:
    r["n_fail"] = len(r["fails"]); r["n_warn"] = len(r["warns"])
u = [r for r in recs if r["universe"] == "TOP1000" and r["delay"] == 1]


def ds_of(code):
    return sorted(set(re.findall(r"\b([a-z]+\d+)_[a-z0-9_]+", code or "")))


def is_fund(r):
    return any(d.startswith(("fnd", "oth")) for d in ds_of(code_of.get(r["id"], "")))


fu = [r for r in u if is_fund(r)]

print("=" * 116)
print("★ Q1：基本面 alpha 的零 fail 率 × neutralization")
print("=" * 116)
tab = defaultdict(Counter)
for r in fu:
    g = tab[r["neutralization"] or "?"]
    g["n"] += 1
    g["zero"] += (r["n_fail"] == 0)
    g["sh158"] += ((r["n_fail"] == 0) and (r["sharpe"] or 0) >= 1.58)
print(f"  {'neut':<14}{'n':>5}{'零fail':>8}{'零fail率':>10}{'零fail且Sh>=1.58':>18}")
for k in sorted(tab, key=lambda k: -tab[k]["zero"]):
    g = tab[k]
    print(f"  {k:<14}{g['n']:>5}{g['zero']:>8}{(g['zero']/g['n'] if g['n'] else 0):>10.3f}{g['sh158']:>18}")

print()
print("=" * 116)
print("★ Q2：σ 杠杆 —— 年化收益/Sharpe，按 neutralization（基本面 vs 全体）")
print("=" * 116)
print("  σ = returns / sharpe  （平台口径：Ret = Sh × σ）")
print(f"  {'neut':<14}{'基本面n':>9}{'σ中位':>9}{'σ最大':>9}{'全体n':>8}{'σ中位':>9}{'零fail率':>10}")
for k in sorted(tab, key=lambda k: -tab[k]["n"]):
    sub = [r for r in fu if r["neutralization"] == k and (r["sharpe"] or 0) > 0.2]
    alls = [r for r in u if r["neutralization"] == k and (r["sharpe"] or 0) > 0.2]
    if not sub:
        continue
    s = sorted(r["returns"] / r["sharpe"] for r in sub)
    a = sorted(r["returns"] / r["sharpe"] for r in alls) if alls else [0]
    g = tab[k]
    print(f"  {k:<14}{len(sub):>9}{s[len(s)//2]:>9.4f}{max(s):>9.4f}{len(alls):>8}{a[len(a)//2]:>9.4f}"
          f"{(g['zero']/g['n'] if g['n'] else 0):>10.3f}")

print()
print("=" * 116)
print("★ Q3：设置档组合（neut × decay × nan）× 零 fail 率（基本面，n>=6）")
print("=" * 116)
tab2 = defaultdict(Counter)
for r in fu:
    k = (r["neutralization"], r["decay"], r["nanHandling"])
    g = tab2[k]
    g["n"] += 1
    g["zero"] += (r["n_fail"] == 0)
rows = [(k, g) for k, g in tab2.items() if g["n"] >= 6]
rows.sort(key=lambda x: (-x[1]["zero"] / x[1]["n"], -x[1]["n"]))
print(f"  {'neut':<14}{'dec':>4}{'nan':>5}{'n':>5}{'零fail':>8}{'率':>8}{'Sh中位':>8}{'Ret中位%':>10}{'σ中位%':>9}")
for (n, d, na), g in rows[:18]:
    sub = [r for r in fu if (r["neutralization"], r["decay"], r["nanHandling"]) == (n, d, na)]
    sh = sorted((r["sharpe"] or 0) for r in sub)
    rt = sorted((r["returns"] or 0) for r in sub)
    sg = sorted((r["returns"] / r["sharpe"]) for r in sub if (r["sharpe"] or 0) > 0.2)
    print(f"  {n:<14}{d:>4}{na:>5}{g['n']:>5}{g['zero']:>8}{g['zero']/g['n']:>8.3f}"
          f"{sh[len(sh)//2]:>8.2f}{rt[len(rt)//2]*100:>10.2f}"
          f"{(sg[len(sg)//2]*100 if sg else 0):>9.2f}")

print()
print("=" * 116)
print("★ Q4：基本面零 fail 行的 σ 分布 —— 现有最优基础")
print("=" * 116)
z = [r for r in fu if r["n_fail"] == 0]
for r in sorted(z, key=lambda x: -(x["sharpe"] or 0)):
    sg = (r["returns"] / r["sharpe"]) if (r["sharpe"] or 0) > 0.2 else 0
    print(f"  {r['id']:<10} Sh={r['sharpe']:>5.2f} Fit={r['fitness']:>5.2f} σ={sg*100:>6.2f}% "
          f"TO={(r['turnover'] or 0)*100:>6.2f}% Ret={(r['returns'] or 0)*100:>6.2f}% "
          f"Mgn={(r['margin'] or 0)*10000:>6.2f} neut={r['neutralization']:<12} d{r['decay']} nan{r['nanHandling']}")
