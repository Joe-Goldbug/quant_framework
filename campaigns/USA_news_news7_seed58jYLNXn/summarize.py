"""summarize.py — 汇总各波次回测指标"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
waves = sys.argv[1:] or ["w1", "w2", "w3"]

for w in waves:
    p = os.path.join(HERE, f"batch_{w}_result.json")
    if not os.path.exists(p):
        print(f"[{w}] 无结果文件")
        continue
    rs = json.load(open(p, encoding="utf-8"))["alpha_results"]
    batch = json.load(open(os.path.join(HERE, f"batch_{w}.json"), encoding="utf-8"))
    types = {it["expression"]: it["type"] for it in batch["items"]}
    print(f"\n===== {w.upper()} =====")
    print(f"{'TYPE':<30}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Mgn(bp)':>9}{'Ret%':>7}{'L/S':>10}{'2Y':>6}{'fails':>6}")
    for r in rs:
        m = r.get("metrics") or {}
        t = types.get(r.get("code"), "?")
        fails = [c["name"] for c in r.get("checks", {}).get("fail", [])]
        print(f"{t:<30}{m.get('sharpe', 0):>6.2f}{m.get('fitness', 0):>6.2f}"
              f"{m.get('turnover', 0)*100:>7.1f}{m.get('margin', 0)*10000:>9.2f}"
              f"{m.get('returns', 0)*100:>7.2f}"
              f"{str(m.get('longCount'))+'/'+str(m.get('shortCount')):>10}"
              f"{m.get('two_year_sharpe', 0):>6.2f}{len(fails):>6}  {','.join(fails)}")
