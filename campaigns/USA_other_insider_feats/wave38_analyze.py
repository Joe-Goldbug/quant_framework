import json, glob, sys

CAMP = "D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats"
fp = sorted(glob.glob(f"{CAMP}/gate1_wave38_result_*.json"))[-1]
d = json.load(open(fp, encoding="utf-8"))
tags = d.get("tags")
ar = d.get("result", {}).get("alpha_results") if isinstance(d.get("result"), dict) else d.get("alpha_results")
if ar is None:
    ar = d.get("result") if isinstance(d.get("result"), list) else []
print("FILE:", fp, "| n =", len(ar))
hdr = f"{'tag':<18}{'alpha_id':<10}{'Sh':>5}{'2Y':>5}{'Sub':>5}{'Fit':>5}{'Ret%':>6}{'TO%':>6}{'Mgn':>6}{'DD%':>5}{'L/S':>11}{'RN':>5}  checks"
print(hdr); print("-" * len(hdr))
rows = []
for i, e in enumerate(ar):
    m = e.get("metrics", {})
    tag = (tags[i] if tags and i < len(tags) else f"#{i}")
    ls = f"{m.get('longCount')}/{m.get('shortCount')}"
    checks = e.get("checks", [])
    if isinstance(checks, list):
        fails = [c.get("name") for c in checks if c.get("result") == "FAIL"]
        warns = [c.get("name") for c in checks if c.get("result") == "WARNING"]
        cs = "FAIL:" + ",".join(fails) if fails else ("WARN:" + ",".join(warns) if warns else "CLEAN")
    else:
        cs = str(checks)[:40]
    row = dict(tag=tag, aid=e.get("alpha_id"), sh=m.get("sharpe"), y2=m.get("two_year_sharpe"),
               sub=m.get("sub_universe_sharpe"), fit=m.get("fitness"), ret=m.get("returns"),
               to=m.get("turnover"), mgn=m.get("margin"), dd=m.get("drawdown"), ls=ls,
               rn=m.get("risk_neutralized_sharpe"), status=e.get("status"), checks=cs, code=e.get("code"))
    rows.append(row)
    mgn_bps = f"{row['mgn']*10000:.1f}" if isinstance(row['mgn'], (int, float)) else str(row['mgn'])
    print(f"{tag:<18}{str(row['aid']):<10}{row['sh']!s:>5}{row['y2']!s:>5}{row['sub']!s:>5}{row['fit']!s:>5}"
          f"{(row['ret']*100 if isinstance(row['ret'],(int,float)) else 0):>6.2f}"
          f"{(row['to']*100 if isinstance(row['to'],(int,float)) else 0):>6.2f}"
          f"{mgn_bps:>6}{(row['dd']*100 if isinstance(row['dd'],(int,float)) else 0):>5.2f}{ls:>11}{row['rn']!s:>5}  {row['status']}|{cs[:60]}")
# all-green gate
print("\n=== ALL-GREEN GATE (Sh>=1.58, 2Y>=1.58, Sub>=1.58, Fit>=1.0, Mgn>=10bps, 0 FAIL 0 WARN) ===")
for r in rows:
    ok = (isinstance(r["sh"], (int, float)) and r["sh"] >= 1.58 and (r["y2"] or 0) >= 1.58
          and (r["sub"] or 0) >= 1.58 and (r["fit"] or 0) >= 1.0
          and isinstance(r["mgn"], (int, float)) and r["mgn"] * 10000 >= 10
          and r["checks"] == "CLEAN")
    if ok:
        print("PASS:", r["tag"], r["aid"])
print("(none)" if not any((isinstance(r["sh"], (int, float)) and r["sh"] >= 1.58) for r in rows) else "")
# dump PC-check shortlist: best by sharpe with margin>=10bps
short = [r for r in rows if isinstance(r["mgn"], (int, float)) and r["mgn"] * 10000 >= 10 and r["status"] == "UNSUBMITTED"]
short.sort(key=lambda r: -(r["sh"] or 0))
print("\nPC-CHECK SHORTLIST (Mgn>=10bps):", [r["aid"] for r in short[:4]])
json.dump(rows, open(fp.replace("_result_", "_rows_"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
