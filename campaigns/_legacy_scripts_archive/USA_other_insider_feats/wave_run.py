import asyncio, json, sys, time, os
sys.path.insert(0, "D:/brain-mcp")
os.chdir("D:/brain-mcp")
import main as bm

CAMP = "D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats"
BATCH = json.load(open(f"{CAMP}/gate1_wave{sys.argv[1]}_batch.json", encoding="utf-8"))
W = sys.argv[1]
EXPRS = [e["expr"] for e in BATCH["expressions"]]
TAGS = [e["tag"] for e in BATCH["expressions"]]

BASE = dict(instrument_type="EQUITY", region="USA", universe="TOP1000", delay=1,
            truncation=0.025, unit_handling="VERIFY", nan_handling="ON",
            pasteurization="ON", language="FASTEXPR", visualization=False)

async def main():
    ts = int(time.time())
    sub = None
    for attempt in range(8):
        try:
            sub = await bm.create_multi_simulation(EXPRS, neutralization="INDUSTRY", decay=8, **BASE)
            sub = json.loads(sub) if isinstance(sub, str) else sub
            break
        except Exception as e:
            print(f"[submit attempt {attempt}] {e}", flush=True)
            await asyncio.sleep(3 * (attempt + 1))
    if not sub or not sub.get("location"):
        json.dump({"error": "submit failed", "submit": sub}, open(f"{CAMP}/gate1_wave{W}_result_{ts}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return
    loc = sub["location"]
    print("SUBMITTED:", sub.get("multisimulation_id"), flush=True)
    # children are id strings; wait fixed period then try fetch with retries
    await asyncio.sleep(600)
    for i in range(40):
        try:
            res = await bm.fetch_multi_simulation_result(loc)
            res = json.loads(res) if isinstance(res, str) else res
            n = len(res.get("alpha_results") or [])
            print(f"[fetch {i}] {n} results", flush=True)
            if n >= len(EXPRS):
                fp = f"{CAMP}/gate1_wave{W}_result_{ts}.json"
                json.dump({"tags": TAGS, "location": loc, "result": res}, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print("SAVED:", fp, flush=True)
                return
        except Exception as e:
            print(f"[fetch {i}] {str(e)[:120]}", flush=True)
        await asyncio.sleep(30)
    print("FETCH_TIMEOUT", flush=True)

asyncio.run(main())
