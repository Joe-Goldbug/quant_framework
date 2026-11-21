"""
evaluate.py — 读取 batch_*_result.json，输出每条槽的白盒指标表
用法: python evaluate.py batch_n1_result.json
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
fn = sys.argv[1] if len(sys.argv) > 1 else "batch_n1_result.json"
data = json.load(open(os.path.join(HERE, fn), encoding="utf-8"))
rows = data.get("alpha_results", [])

hdr = (f"{'#':<3}{'alpha':<10}{'Sh':>6}{'Fit':>7}{'TO%':>7}{'Mgn':>7}{'Ret%':>7}{'DD%':>7}"
       f"{'2Y':>6}{'SubU':>6}{'L/S':>10}{'fail':>5} warn")
print(hdr)
print("-" * 95)
for i, r in enumerate(rows, 1):
    m = r.get("metrics") or r.get("is") or {}
    chk = r.get("checks") or {}
    fails = chk.get("fail") or []
    warns = [w.get("name") if isinstance(w, dict) else w for w in (chk.get("warning") or [])]

    def f(v, k=2):
        return f"{v:.{k}f}" if isinstance(v, (int, float)) else "   -"

    print(f"{i:<3}{r.get('alpha_id') or '--':<10}{f(m.get('sharpe')):>6}{f(m.get('fitness')):>7}"
          f"{f((m.get('turnover') or 0) * 100):>7}{f((m.get('margin') or 0) * 1e4):>7}"
          f"{f((m.get('returns') or 0) * 100):>7}{f((m.get('drawdown') or 0) * 100):>7}"
          f"{f(m.get('two_year_sharpe')):>6}{f(m.get('sub_universe_sharpe')):>6}"
          f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10}{len(fails):>5} {warns}")
    if fails:
        print("    FAIL:", [c.get('name') for c in fails])
    print("   ", (r.get('code') or '')[:160])
    print()
