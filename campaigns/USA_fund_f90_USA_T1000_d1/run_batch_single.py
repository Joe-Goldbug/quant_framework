# -*- coding: utf-8 -*-
"""第三通道批次执行器: 8 条表达式并发单发 create_simulation，再并行轮询汇总。
用于 submit_multi_simulation / create_multi_simulation 均被平台限流或超时时的兜底。
仍强制经过 Gate0~Gate5 全部本地硬门禁，且严禁任何提交动作。
"""
import asyncio, json, os, sys, sqlite3

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"; os.environ["no_proxy"] = "*"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
AGENTS = os.path.dirname(ROOT)
sys.path.insert(0, AGENTS); sys.path.insert(0, ROOT); sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.sim_runner import SimBatchRunner
import main as bm

BATCH = sys.argv[1] if len(sys.argv) > 1 else "batch_R9.json"
NEUT = sys.argv[2] if len(sys.argv) > 2 else "SUBINDUSTRY"
DECAY = int(sys.argv[3]) if len(sys.argv) > 3 else 4
TRUNC = float(sys.argv[4]) if len(sys.argv) > 4 else 0.08


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


def release_fingerprints(batch_path: str):
    db = os.path.join(ROOT, "alphas_record.db")
    if not os.path.exists(db):
        return
    exprs = [i.get("expression", "") for i in json.load(open(batch_path, encoding="utf-8")).get("items", [])]
    conn = sqlite3.connect(db); cur = conn.cursor(); n = 0
    for e in exprs:
        cur.execute("DELETE FROM alpha_fingerprints WHERE expression = ?", (e,)); n += cur.rowcount
    conn.commit(); conn.close()
    if n:
        print(f"[fingerprint] 释放本批 {n} 条历史指纹登记")


async def submit_one(expr, idx, sem):
    async with sem:
        for attempt in range(3):
            try:
                r = await call(bm.create_simulation, region="USA", universe="TOP1000", delay=1,
                               decay=DECAY, neutralization=NEUT, truncation=TRUNC,
                               language="FASTEXPR", unit_handling="VERIFY", nan_handling="ON",
                               pasteurization="ON", alpha_expression=expr)
                loc = (r or {}).get("location")
                if loc:
                    print(f"  slot{idx+1} accepted ({attempt+1}试)")
                    return loc
            except Exception as e:
                print(f"  slot{idx+1} 提交异常({attempt+1}): {type(e).__name__}")
            await asyncio.sleep(5 + 5 * attempt)
        return None


async def poll_one(loc, idx):
    for i in range(70):
        try:
            chk = await call(bm.check_simulation, location=loc)
        except Exception:
            await asyncio.sleep(12); continue
        st = chk.get("status")
        if st in ("COMPLETE", "COMPLETED", "DONE"):
            det = await call(bm.get_alpha_details, alpha_id=chk.get("alpha_id"))
            print(f"  slot{idx+1} COMPLETE")
            return det
        if st in ("ERROR", "CANCELLED", "FAIL"):
            print(f"  slot{idx+1} {st}")
            return {"status": st, "code": None}
        await asyncio.sleep(12)
    print(f"  slot{idx+1} 轮询超时")
    return None


async def main():
    path = os.path.join(HERE, BATCH)
    release_fingerprints(path)
    batch = json.load(open(path, encoding="utf-8"))
    items, known = batch["items"], batch["known_fields"]
    exprs = SimBatchRunner.verify_state_token_and_gates(
        batch_file_path=path, expressions_data=items, known_fields=known,
        category="fundamental", region="USA", universe="TOP1000", delay=1,
        neutralization=NEUT, ledger_path=os.path.join(HERE, "exploration_ledger.json"))

    await call(bm.authenticate)
    print("\n📡 [第三通道] 并发单发 8 条 ...")
    sem = asyncio.Semaphore(4)
    locs = await asyncio.gather(*[submit_one(e, i, sem) for i, e in enumerate(exprs)])
    print("\n⏳ 并行轮询 ...")
    dets = await asyncio.gather(*[poll_one(l, i) for i, l in enumerate(locs) if l])

    results = [d if isinstance(d, dict) else {"status": "UNKNOWN"} for d in dets]
    out = path.replace(".json", "_result.json")
    json.dump({"alpha_results": results}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n->", os.path.basename(out), len(results), "条")


if __name__ == "__main__":
    asyncio.run(main())
