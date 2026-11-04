"""
BATCH08_GATE1_PROBE 실행기 — 8개 expr, 다중 multi-sim, 정적 폴링, 결과 저장
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

async def main():
    with open("quant_framework/campaigns/GLB_other_cross_ds/batch_BATCH08_GATE1_PROBE.json", encoding="utf-8") as f:
        meta=json.load(f)
    exprs=meta["exprs"]
    print(f"\n=== BATCH08 | {len(exprs)} expressions ===")
    for i,e in enumerate(exprs):
        print(f"  [{i}] {e}")

    r=await bm.submit_multi_simulation(
        alpha_expressions=exprs, region=REGION, universe=UNIV, delay=DELAY,
        decay=0, neutralization="COUNTRY", truncation=0.025, test_period="P0Y0M",
        unit_handling="VERIFY", nan_handling="ON", pasteurization="ON", max_trade="OFF")
    loc=r.get("location")
    err=r.get("error")
    print("SUBMIT:", "OK" if loc else f"ERR {err}")
    if not loc:
        print(json.dumps(r)[:500])
        return

    print("LOC:",loc)
    await asyncio.sleep(70)
    while True:
        s=await bm.check_multi_simulation(loc)
        st=s.get("status")
        print("STATUS:",st, "ID:",s.get("alpha_id"), flush=True)
        if st=="COMPLETE": break
        if st=="ERROR":
            print("ERR:",json.dumps(s)[:800]); return
        if st=="RATE_LIMITED":
            await asyncio.sleep(40); continue
        await asyncio.sleep(22)

    res=await bm.fetch_multi_simulation_result(loc)
    rows=[]
    for a in res.get("alpha_results",[]):
        if a.get("status") in ("CANCELLED","ERROR"): continue
        m=a.get("metrics") or {}
        sc=Gatekeeper.parse_brain_checks(a)
        rows.append({
            "id":a.get("id"),
            "expr":a.get("expression"),
            "sharpe":m.get("sharpe"),
            "fitness":m.get("fitness"),
            "returns":m.get("returns"),
            "turnover":m.get("turnover"),
            "margin_bps":round((m.get("margin") or 0)*10000,1),
            "fails":sc["fails"],
            "warnings":sc["warnings"],
            "pcorr":Gatekeeper.extract_prod_corr(a)
        })
    out="quant_framework/campaigns/GLB_other_cross_ds/batch_BATCH08_GATE1_PROBE_result.json"
    json.dump({"batch":"BATCH08_GATE1","rows":rows}, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nSaved -> {out}")
    print(f"\n{'='*80}")
    for r in rows:
        print(f"→ [{r['id']}] Sh={r['sharpe']} Fit={r['fitness']} Ret={r['returns']} TO={r['turnover']} Mgn={r['margin_bps']}bps")
        print(f"    fail={r['fails']}")
        print(f"    warn={r['warnings']}")
        print(f"    pcorr={r['pcorr']}")
        print(f"    expr={r['expr']}")
        print()
    print(f"{'='*80}")

if __name__=="__main__":
    asyncio.run(main())
