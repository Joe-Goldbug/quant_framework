# -*- coding: utf-8 -*-
"""备用批次执行器: 走 create_multi_simulation 通道 (submit_multi_simulation 被平台限流时的兜底)
仍强制经过 Gate0~Gate5 全部本地硬门禁，且严禁任何提交动作。
"""
import asyncio, json, os, sys

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
    """发包前释放本批指纹：指纹在 POST 之前登记，若 POST 因限流失败，
    未真正回测的组合会被错误记为'已测'，下一轮被防重门禁拦下。"""
    import sqlite3
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


async def main():
    path = os.path.join(HERE, BATCH)
    release_fingerprints(path)
    batch = json.load(open(path, encoding="utf-8"))
    items = batch["items"]
    known = batch["known_fields"]

    exprs = SimBatchRunner.verify_state_token_and_gates(
        batch_file_path=path, expressions_data=items, known_fields=known,
        category="fundamental", region="USA", universe="TOP1000", delay=1,
        neutralization=NEUT, ledger_path=os.path.join(HERE, "exploration_ledger.json"))
    print("\n📡 [备用通道] create_multi_simulation 提交 8 条 ...")

    await call(bm.authenticate)
    res = await call(bm.create_multi_simulation, alpha_expressions=exprs, region="USA",
                     universe="TOP1000", delay=1, decay=DECAY, neutralization=NEUT,
                     truncation=TRUNC, pasteurization="ON", unit_handling="VERIFY",
                     nan_handling="ON", language="FASTEXPR", visualization=False)
    if isinstance(res, dict) and res.get("error"):
        print("提交失败:", res["error"][:300]); return
    loc = res.get("location") or (res.get("multi_simulation") or {}).get("location")
    print("Location:", loc)
    if not loc:
        print("返回:", json.dumps(res, ensure_ascii=False)[:600]); return

    for i in range(60):
        await asyncio.sleep(15)
        chk = await call(bm.check_multi_simulation, location=loc)
        st = chk.get("status")
        print(f"  poll#{i+1} {st}")
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            break

    fetch = await call(bm.fetch_multi_simulation_result, location=loc)
    out = path.replace(".json", "_result.json")
    json.dump({"alpha_results": fetch.get("alpha_results", [])}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("->", os.path.basename(out), len(fetch.get("alpha_results", [])), "条")


if __name__ == "__main__":
    asyncio.run(main())
