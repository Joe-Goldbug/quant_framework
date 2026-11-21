# -*- coding: utf-8 -*-
"""AEGIS Stage 5: 全维度诚实审计表生成器 (零隐瞒，含全部 WARNING)"""
import json, os, sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = sys.argv[1] if len(sys.argv) > 1 else "batch_R1_result.json"

d = json.load(open(os.path.join(HERE, RESULT), encoding="utf-8"))
rows = d["alpha_results"]


def g(r, *path, default=None):
    cur = r
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


hdr = (f"{'#':<3}{'AlphaID':<10}{'Sharpe':>7}{'2Y':>7}{'Fit':>7}{'Margin':>8}"
       f"{'TO%':>7}{'SubU':>7}{'Clust':>7}{'L:S':>11}{'Ret%':>7}  {'FAILS'}")
print(hdr)
print("-" * len(hdr) * 1)
for i, r in enumerate(rows, 1):
    m = r.get("metrics", {}) or {}
    ch = r.get("checks", {}) or {}
    fails = [c.get("name") for c in (ch.get("fail") or [])]
    warns = [c.get("name") for c in (ch.get("warning") or [])]
    lc, sc = m.get("longCount"), m.get("shortCount")
    ratio = f"{lc}:{sc}" if lc and sc else "NA"
    print(f"{i:<3}{str(r.get('alpha_id') or r.get('id')):<10}"
          f"{m.get('sharpe', 0):>7.2f}{m.get('two_year_sharpe', 0):>7.2f}"
          f"{m.get('fitness', 0):>7.2f}{m.get('margin', 0)*10000:>8.2f}"
          f"{m.get('turnover', 0)*100:>7.1f}{m.get('sub_universe_sharpe', 0):>7.2f}"
          f"{(next((c.get('value') for c in (ch.get('warning') or []) if c.get('name')=='CLUSTER_TEST'), None) or 0):>7.2f}"
          f"{ratio:>11}{m.get('returns', 0)*100:>7.2f}  {','.join(fails)}")
    if warns:
        print(f"{'':<3}{'  ⚠ WARN:':<12}{','.join(warns)}")

print()
print("=" * 110)
print("表达式明细:")
for i, r in enumerate(rows, 1):
    print(f"{i}. [{r.get('alpha_id')}] {r.get('code')}")
