import asyncio, json, sys, time, os
sys.path.insert(0, "D:/brain-mcp")
os.chdir("D:/brain-mcp")
import main as bm

CAMP = "D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats"
BATCH = json.load(open(f"{CAMP}/gate1_wave38_batch.json", encoding="utf-8"))
EXPRS = [e["expr"] for e in BATCH["expressions"]]
TAGS = [e["tag"] for e in BATCH["expressions"]]

BASE = dict(instrument_type="EQUITY", region="USA", universe="TOP1000", delay=1,
            truncation=0.025, unit_handling="VERIFY", nan_handling="ON",
            pasteurization="ON", language="FASTEXPR", visualization=False)

async def main():
    ts = int(time.time())
    # submit (fire-and-forget, budget=0 -> instant location)
    for attempt in range(8):
        try:
            sub = await bm.create_multi_simulation(EXPRS, neutralization="INDUSTRY", decay=8, **BASE)
            break
        except Exception as e:
            print(f"[submit attempt {attempt}] {e}", flush=True)
            await asyncio.sleep(3 * (attempt + 1))
    print("SUBMIT:", json.dumps(sub, ensure_ascii=False)[:500], flush=True)
    loc = sub.get("location") or (sub.get("children") or [{}])[0].get("location")
    if not loc:
        json.dump({"error": "no location", "submit": sub}, open(f"{CAMP}/gate1_wave38_result_{ts}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return
    # poll
    for i in range(120):
        await asyncio.sleep(15)
        try:
            st = await bm.check_multi_simulation(loc)
        except Exception as e:
            print(f"[check {i}] {e}", flush=True); continue
        done = sum(1 for c in (st.get("children") or []) if c.get("status") in ("COMPLETE", "ERROR", "FAIL", "WARNING"))
        total = len(st.get("children") or [])
        print(f"[poll {i}] {done}/{total}", flush=True)
        if total and done == total:
            break
    res = await bm.fetch_multi_simulation_result(loc)
    out = {"tags": TAGS, "location": loc, "result": res}
    fp = f"{CAMP}/gate1_wave38_result_{ts}.json"
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("SAVED:", fp, flush=True)

asyncio.run(main())
