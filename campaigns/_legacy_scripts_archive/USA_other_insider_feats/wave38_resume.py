import asyncio, json, sys, time, os
sys.path.insert(0, "D:/brain-mcp")
os.chdir("D:/brain-mcp")
import main as bm

CAMP = "D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats"
BATCH = json.load(open(f"{CAMP}/gate1_wave38_batch.json", encoding="utf-8"))
TAGS = [e["tag"] for e in BATCH["expressions"]]
LOC = "https://api.worldquantbrain.com/simulations/1qW9Vt3jN5dcbNxKx343nRm"
TS = int(time.time())

def as_dict(x):
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return {}
    return x if isinstance(x, dict) else {}

async def main():
    for i in range(160):
        await asyncio.sleep(15)
        try:
            st = as_dict(await bm.check_multi_simulation(LOC))
        except Exception as e:
            print(f"[check {i}] {e}", flush=True); continue
        ch = st.get("children") or []
        ch = [as_dict(c) for c in ch]
        done = sum(1 for c in ch if c.get("status") in ("COMPLETE", "ERROR", "FAIL", "WARNING"))
        total = len(ch)
        print(f"[poll {i}] {done}/{total}", flush=True)
        if total and done == total:
            break
    res = await bm.fetch_multi_simulation_result(LOC)
    out = {"tags": TAGS, "location": LOC, "result": res}
    fp = f"{CAMP}/gate1_wave38_result_{TS}.json"
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("SAVED:", fp, flush=True)

asyncio.run(main())
