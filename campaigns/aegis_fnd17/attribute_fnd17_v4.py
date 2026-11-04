# -*- coding: utf-8 -*-
"""fnd17 家族设置档归因（基于 v4 权威数据）—— 决定下一波回测的唯一依据。

关键待解问题（由 S3 诊断暴露）：
  S3 只测了两格：{decay=0, MARKET, nan=OFF} 与 {decay=8, STATISTICAL, nan=ON}
  ⇒ **STATISTICAL + decay=0 这一格从未测过**，而它恰是唯一可能同时拿到
     高 Sharpe（STATISTICAL）+ 高 Margin（decay=0 低换手）的组合。
"""
import json
import os
import sys
import re
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

recs = json.load(open(os.path.join(HERE, "fnd17_history_v4.json"), encoding="utf-8"))
print(f"精确 fnd17 共 {len(recs)} 条\n")


def skel(code):
    return re.sub(r"\s+", "", re.sub(r"\bfnd17_[a-z0-9_]+\b", "F", code or ""))


# ---------- ① 全局：门禁全过的 alpha ----------
print("=" * 112)
print("① fnd17 全史 · 通过全部门禁的 alpha（fail 空 + Sh>=1.58 + ra_failed=False）")
print("=" * 112)
full = [r for r in recs if not r["checks_fail"] and (r["sharpe"] or 0) >= 1.58
        and r["ra_failed"] is False]
full.sort(key=lambda r: -(r["sharpe"] or 0))
print(f"共 {len(full)} 条 / {len(recs)} 条 fnd17\n")
print(f"{'id':<10}{'reg':<5}{'univ':<11}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}{'Mgn':>8}"
      f"{'2Y':>6}{'Sub':>6}{'dec':>4}{'neut':<22}{'PC':>7}{'SC':>7}")
for r in full:
    print(f"{r['id']:<10}{r['region'] or '':<5}{r['universe'] or '':<11}"
          f"{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}{(r['turnover'] or 0)*100:>7.2f}"
          f"{(r['returns'] or 0)*100:>8.2f}{(r['margin'] or 0)*10000:>8.2f}"
          f"{(r['two_year_sharpe'] or 0):>6.2f}{(r['sub_universe_sharpe'] or 0):>6.2f}"
          f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization'] or '':<22}"
          f"{(r['prod_corr'] or 0):>7.3f}{(r['self_corr'] or 0):>7.3f}")

# ---------- ② 设置档归因：全局（仅统计有真实 Sharpe 的） ----------
print("\n" + "=" * 112)
print("② 设置档归因 · 全局")
print("=" * 112)
alive = [r for r in recs if (r["sharpe"] or 0) > 0]
print(f"（有非零 Sharpe 的 {len(alive)} 条）")
for key in ("decay", "neutralization", "nanHandling", "truncation"):
    agg = collections.defaultdict(list)
    for r in alive:
        agg[r[key]].append(r["sharpe"])
    print(f"\n  -- {key} --")
    for k, v in sorted(agg.items(), key=lambda kv: -max(kv[1])):
        v2 = sorted(v, reverse=True)
        print(f"     {str(k):<24} n={len(v):<4} max={max(v):>6.2f} mean={sum(v)/len(v):>6.2f} "
              f"top3={[round(x,2) for x in v2[:3]]}")

# ---------- ③ decay 与 Sharpe/Margin 的关系（decay 才是关键杠杆？） ----------
print("\n" + "=" * 112)
print("③ decay 对 Sharpe / Turnover / Margin 的影响（fnd17 全史）")
print("=" * 112)
agg = collections.defaultdict(list)
for r in alive:
    agg[r["decay"]].append(r)
print(f"{'decay':>6}{'n':>5}{'Sh_max':>8}{'Sh_mean':>9}{'TO%mean':>10}{'Ret%mean':>10}{'Mgn_mean':>10}")
for k in sorted(agg, key=lambda z: (z is None, z)):
    g = agg[k]
    sh = [x["sharpe"] or 0 for x in g]
    to = [(x["turnover"] or 0) * 100 for x in g]
    rt = [(x["returns"] or 0) * 100 for x in g]
    mg = [(x["margin"] or 0) * 10000 for x in g]
    print(f"{str(k):>6}{len(g):>5}{max(sh):>8.2f}{sum(sh)/len(sh):>9.2f}"
          f"{sum(to)/len(to):>10.2f}{sum(rt)/len(rt):>10.2f}{sum(mg)/len(mg):>10.2f}")

# ---------- ④ USA/TOP1000/d1 专项 ----------
print("\n" + "=" * 112)
print("④ USA / TOP1000 / d1 专项（本战役口径）")
print("=" * 112)
usa = [r for r in recs if r["region"] == "USA" and r["universe"] == "TOP1000"
       and r["delay"] == 1]
usa.sort(key=lambda r: -(r["sharpe"] or 0))
print(f"共 {len(usa)} 条")
print(f"{'id':<10}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}{'Mgn':>8}{'2Y':>6}{'Sub':>6}"
      f"{'dec':>4}{'neut':<12}{'nan':<4}")
for r in usa[:24]:
    print(f"{r['id']:<10}{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}"
          f"{(r['turnover'] or 0)*100:>7.2f}{(r['returns'] or 0)*100:>8.2f}"
          f"{(r['margin'] or 0)*10000:>8.2f}{(r['two_year_sharpe'] or 0):>6.2f}"
          f"{(r['sub_universe_sharpe'] or 0):>6.2f}"
          f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization'] or '':<12}"
          f"{r['nanHandling'] or '':<4}")

print("\n  -- USA/TOP1000/d1 按 decay 分档 --")
agg2 = collections.defaultdict(list)
for r in usa:
    agg2[(r["decay"], r["neutralization"])].append(r)
print(f"{'dec/neut':<28}{'n':>4}{'Sh_max':>8}{'Sh_mean':>9}{'TO%':>8}{'Ret%':>8}{'Mgn':>8}")
for k in sorted(agg2, key=lambda z: (-max((x["sharpe"] or 0) for x in agg2[z]),)):
    g = agg2[k]
    sh = [x["sharpe"] or 0 for x in g]
    print(f"{str(k):<28}{len(g):>4}{max(sh):>8.2f}{sum(sh)/len(sh):>9.2f}"
          f"{sum((x['turnover'] or 0)*100 for x in g)/len(g):>8.2f}"
          f"{sum((x['returns'] or 0)*100 for x in g)/len(g):>8.2f}"
          f"{sum((x['margin'] or 0)*10000 for x in g)/len(g):>8.2f}")

# ---------- ⑤ 骨架族（结构归因） ----------
print("\n" + "=" * 112)
print("⑤ 结构骨架族（fnd17 全史，按族内最高 Sharpe 排序，前 12 族）")
print("=" * 112)
grp = collections.defaultdict(list)
for r in recs:
    grp[skel(r.get("code"))].append(r)
ranked = sorted(grp.items(), key=lambda kv: -max((x["sharpe"] or 0) for x in kv[1]))
for s, g in ranked[:12]:
    b = max(g, key=lambda x: (x["sharpe"] or 0))
    print(f"  n={len(g):<3} bestSh={b['sharpe']:>5.2f} [{b['id']}] {b['region']}/{b['universe']} "
          f"dec={b['decay']} {b['neutralization']}")
    print(f"      {s[:135]}")
print(f"\n骨架族总数: {len(grp)}")
