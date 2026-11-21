"""
evaluate_gate1.py — 平台口径终审（唯一判据 = BRAIN 官方 checks）
通过条件: ra.ra_failed == False 且 checks.fail == [] 且 checks.warning == []
辅助阈值: Sharpe>=1.58 / Fitness>=1.0 / 2Y>=1.58 / TO∈[5%,70%] / CW / Sub / IS_LADDER / CLUSTER
"""
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(__file__)
files = sys.argv[1:] or sorted(
    f for f in os.listdir(HERE) if f.endswith("_result.json"))

for fn in files:
    path = os.path.join(HERE, fn) if not os.path.isabs(fn) else fn
    if not os.path.exists(path):
        print(f"[skip] {fn}")
        continue
    batch_fn = os.path.basename(path).replace("_result.json", ".json")
    types = {}
    bp = os.path.join(HERE, batch_fn)
    if os.path.exists(bp):
        for it in json.load(open(bp, encoding="utf-8"))["items"]:
            types[it["expression"]] = (it["type"], it["id"])

    rs = json.load(open(path, encoding="utf-8"))["alpha_results"]
    print(f"\n===== {batch_fn} : {len(rs)} 条 =====")
    print(f"{'#':<3}{'TYPE':<30}{'Sharpe':>7}{'Fit':>6}{'2Y':>6}{'Sub':>6}{'TO%':>7}{'Ret%':>7}"
          f"{'Mgnbp':>7}{'fail':>5}{'warn':>5}  判读")
    for r in rs:
        m = r.get("metrics") or {}
        t, idx = types.get(r.get("code"), ("?", "?"))
        ra = r.get("ra") or {}
        chk = r.get("checks") or {}
        fails = [c["name"] for c in chk.get("fail", [])]
        warns = [c["name"] for c in chk.get("warning", [])]
        ra_failed = ra.get("ra_failed")
        ra_cnt = ra.get("failed_ra_count", len(fails))
        ok = (ra_failed is False) and not fails and not warns and ra_cnt == 0
        verdict = "PASS_ALL(0 fail / 0 warn)" if ok else (
            "FAIL " + ",".join(fails + warns)[:70] if (fails or warns) else f"FAIL ra_failed={ra_failed}")
        print(f"{idx:<3}{t:<30}{m.get('sharpe',0):>7.2f}{m.get('fitness',0):>6.2f}"
              f"{m.get('two_year_sharpe',0):>6.2f}{m.get('sub_universe_sharpe',0):>6.2f}"
              f"{m.get('turnover',0)*100:>7.1f}{m.get('returns',0)*100:>7.2f}"
              f"{m.get('margin',0)*10000:>7.2f}{len(fails):>5}{len(warns):>5}  "
              f"alpha={r.get('id')}  {verdict}")
