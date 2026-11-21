"""
BATCH08_GATE1_PROBE — 슬롯별 순차 단일 시뮬레이션 (single sim 파이프라인)
multi-sim이 ERROR로 빠지므로 슬롯별로 create_simulation → check → get_alpha_details 하여 결과 수집
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"]=r"D:\brain-mcp\user_config.json"

import main as bm
from core.gatekeeper import Gatekeeper

REGION="GLB"; UNIV="MINVOL1M"; DELAY=1

EXPRS=[
  "group_rank(ts_mean(negative_score_maximum_value, 250), industry)",
  "group_rank(ts_zscore(ts_mean(negative_score_maximum_value, 250), 250), industry)",
  "group_rank(subtract(ts_mean(negative_score_maximum_value, 250), ts_mean(oth424_divyld, 250)), industry)",
  "group_rank(multiply(ts_mean(negative_score_maximum_value, 250), ts_mean(oth424_divyld, 250)), industry)",
  "group_rank(ts_mean(max(negative_score_maximum_value, 0), 250), industry)",
  "group_rank(ts_mean(negative_coverage_pct, 250), industry)",
  "group_rank(ts_rank(ts_mean(negative_score_maximum_value, 250), 500), industry)",
]

async def run_one(slot, expr):
    print(f"\n=== SLOT {slot}: {expr}", flush=True)
    r=await bm.create_simulation(
        alpha_expression=expr, region=REGION, universe=UNIV, delay=DELAY,
        decay=0, neutralization="COUNTRY", truncation=0.025, test_period="P0Y0M",
        unit_handling="VERIFY", nan_handling="ON", pasteurization="ON", max_trade="OFF")
    loc=r.get("location")
    if not loc:
        print("  SUBMIT_ERR",r); return None
    print("  LOC:",loc[-20:], flush=True)
    for _ in range(35):
        await asyncio.sleep(16)
        s=await bm.check_simulation(loc)
        st=s.get("status")
        if st=="COMPLETE": break
        if st not in ("IN_PROGRESS","RATE_LIMITED"):
            print("  non-progress status:",st, s); return None
        if st=="RATE_LIMITED":
            print("  RATE_LIMITED, backoff"); await asyncio.sleep(40); continue
    if st!="COMPLETE":
        print("  TIMEOUT after polling"); return None
    aid=s.get("alpha_id")
    ad=await bm.get_alpha_details(aid)
    m=ad.get("metrics") or {}
    sc=Gatekeeper.parse_brain_checks(ad)
    row={
        "slot":slot,"expr":expr,
        "id":ad.get("id"),
        "sharpe":m.get("sharpe"),"fitness":m.get("fitness"),
        "returns":m.get("returns"),"turnover":m.get("turnover"),
        "margin_bps":round((m.get("margin") or 0)*10000,1),
        "fails":sc["fails"],"warnings":sc["warnings"],
        "pcorr":Gatekeeper.extract_prod_corr(ad)
    }
    print(f"  DONE -> id={row['id']} Sh={row['sharpe']} Fit={row['fitness']} Ret={row['returns']} TO={row['turnover']} Mgn={row['margin_bps']}bps")
    print(f"    fail={row['fails']} warn={row['warnings']} pcorr={row['pcorr']}")
    return row

async def main():
    results=[]
    for slot,expr in enumerate(EXPRS):
        row=await run_one(slot, expr)
        if row: results.append(row)
        await asyncio.sleep(8)
    out="quant_framework/campaigns/GLB_other_cross_ds/batch_BATCH08_GATE1_PROBE_result.json"
    with open(out,"w",encoding="utf-8") as f:
        json.dump({"batch":"BATCH08_GATE1","rows":results},f,ensure_ascii=False,indent=2)
    print("\n=== SAVED",out)
    for r in results:
        print(f"-> [{r['slot']}] {r['id']} | Sh={r['sharpe']} Fit={r['fitness']} Ret={r['returns']} TO={r['turnover']} Mgn={r['margin_bps']}bps fail={r['fails']} warn={r['warnings']} pcorr={r['pcorr']}")

if __name__=="__main__":
    asyncio.run(main())
