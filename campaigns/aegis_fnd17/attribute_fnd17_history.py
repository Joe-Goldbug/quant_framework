# -*- coding: utf-8 -*-
"""fnd17 全史本地精确归因（基于已抓取的 1410 条 alpha 详情，零额外请求）。

v3 抓取时服务端 ?search=fnd17 是**模糊匹配**（返回了 news alpha），
但每条详情都带真实 code ⇒ 本地按 'fnd17_' 精确过滤即可得到权威子集。

输出：
  ① fnd17 家族全量（按区域 / 设置档 / 结构骨架聚类）
  ② 本战役口径 USA/TOP1000/d1 的 fnd17 历史（最高 Sharpe 榜）
  ③ 通过全部门禁的历史 alpha（checks.fail 空 + Sh>=1.58 + ra_failed false）
  ④ 设置档归因：decay / neutralization / nanHandling 各档的 Sharpe 分布
"""
import json
import os
import re
import collections
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fnd17_history_mined.json")
OUT = os.path.join(HERE, "fnd17_history_attribution.json")

recs = json.load(open(SRC, encoding="utf-8"))
f17 = [r for r in recs if "fnd17" in (r.get("code") or "")]
print(f"全量 {len(recs)} 条，其中 code 含 fnd17 的 {len(f17)} 条")

# ---------- 骨架聚类：把表达式抽象成结构签名 ----------
def skeleton(code):
    """把表达式抽象成结构骨架：字段名归一，保留算子结构。"""
    if not code:
        return "?"
    s = re.sub(r"\bfnd17_[a-z0-9_]+\b", "F", code)
    s = re.sub(r"\s+", "", s)
    return s

groups = collections.defaultdict(list)
for r in f17:
    groups[skeleton(r.get("code"))].append(r)

# ---------- 打印总览 ----------
print("\n" + "=" * 110)
print("① fnd17 家族 · 骨架族榜（按族内最高 Sharpe 排序，族内计数）")
print("=" * 110)
ranked = sorted(groups.items(),
                key=lambda kv: -(max((x["sharpe"] or 0) for x in kv[1])))
for sk, g in ranked[:22]:
    best = max(g, key=lambda x: (x["sharpe"] or 0))
    regs = collections.Counter((x["region"], x["universe"]) for x in g)
    print(f"  n={len(g):<4} bestSh={best['sharpe']:>5.2f} "
          f"[{best['id']}] {best['region']}/{best['universe']} "
          f"dec={best['decay']} {best['neutralization']}")
    print(f"        {sk[:150]}")
    print(f"        分布: {regs.most_common(4)}")

# ---------- ② USA/TOP1000/d1 ----------
print("\n" + "=" * 110)
print("② 本战役口径 USA / TOP1000 / d1 的 fnd17 历史")
print("=" * 110)
usa = [r for r in f17 if r["region"] == "USA" and r["universe"] == "TOP1000"
       and r["delay"] == 1]
usa.sort(key=lambda r: -(r["sharpe"] or 0))
print(f"共 {len(usa)} 条")
print(f"{'id':<10}{'stg':<4}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}{'Mgn':>8}{'2Y':>6}"
      f"{'Sub':>6}{'dec':>4}{'neut':<13}{'PC':>7}{'SC':>7}  fail")
for r in usa[:30]:
    print(f"{r['id']:<10}{(r['stage'] or '')[:3]:<4}{(r['sharpe'] or 0):>6.2f}"
          f"{(r['fitness'] or 0):>6.2f}{(r['turnover'] or 0)*100:>7.2f}"
          f"{(r['returns'] or 0)*100:>8.2f}{(r['margin'] or 0)*10000:>8.2f}"
          f"{(r['two_year_sharpe'] or 0):>6.2f}{(r['sub_universe_sharpe'] or 0):>6.2f}"
          f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization'] or '':<13}"
          f"{(r['prod_corr'] or 0):>7.3f}{(r['self_corr'] or 0):>7.3f}  "
          f"{(r['checks_fail'] or [])[:3]}")

# ---------- ③ 全门禁通过 ----------
print("\n" + "=" * 110)
print("③ 全部门禁通过的历史 alpha（fail 空 + Sh>=1.58 + ra_failed false）")
print("=" * 110)
def passes(r):
    return (not r["checks_fail"]) and (r["sharpe"] or 0) >= 1.58 \
        and r["ra_failed"] is False
full = [r for r in f17 if passes(r)]
full.sort(key=lambda r: -(r["sharpe"] or 0))
print(f"共 {len(full)} 条")
for r in full:
    print(f"  {r['id']} {r['region']}/{r['universe']} d{r['delay']} {r['stage']} "
          f"Sh={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']*100:.2f}% "
          f"Ret={r['returns']*100:.2f}% Mgn={r['margin']*10000:.2f}bp 2Y={r['two_year_sharpe']} "
          f"Sub={r['sub_universe_sharpe']} PC={r['prod_corr']} SC={r['self_corr']} "
          f"dec={r['decay']} {r['neutralization']} nan={r['nanHandling']}")
    print(f"     {r['code']}")

# ---------- ④ 设置档归因 ----------
print("\n" + "=" * 110)
print("④ 设置档归因（USA/TOP1000/d1 子集，n=%d）" % len(usa))
print("=" * 110)
for key in ("neutralization", "decay", "nanHandling"):
    agg = collections.defaultdict(list)
    for r in usa:
        agg[r[key]].append(r["sharpe"] or 0)
    print(f"\n  -- {key} --")
    for k, v in sorted(agg.items(), key=lambda kv: -max(kv[1])):
        v2 = sorted(v, reverse=True)
        print(f"     {str(k):<14} n={len(v):<4} max={max(v):>6.2f} "
              f"mean={sum(v)/len(v):>6.2f} top3={v2[:3]}")

json.dump({"fnd17_total": len(f17), "usa_top1000_d1": len(usa),
           "full_pass": [r["id"] for r in full],
           "skeleton_groups": {k: [x["id"] for x in v] for k, v in groups.items()}},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n💾 -> {OUT}")
