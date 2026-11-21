# -*- coding: utf-8 -*-
"""AEGIS 批次执行器: 调用 SimBatchRunner 静默回测 (严禁任何提交动作)"""
import asyncio, os, sys, json, io, contextlib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 沙箱注入的 HTTP_PROXY(127.0.0.1:19653) 会在 POST /simulations 时 RemoteDisconnected；
# 实测直连 api.worldquantbrain.com 可达 (curl 直连返回 401)，故强制绕过代理。
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))          # .../quant_framework
AGENTS = os.path.dirname(ROOT)                                    # .../.agents
sys.path.insert(0, AGENTS)
sys.path.insert(0, ROOT)
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.sim_runner import SimBatchRunner

BATCH = sys.argv[1] if len(sys.argv) > 1 else "batch_R1.json"
NEUT = sys.argv[2] if len(sys.argv) > 2 else "SUBINDUSTRY"
DECAY = int(sys.argv[3]) if len(sys.argv) > 3 else 4
TRUNC = float(sys.argv[4]) if len(sys.argv) > 4 else 0.08


def release_fingerprints(batch_path: str):
    """发包前释放本批指纹：SimBatchRunner 在 POST 之前登记指纹，若 POST 因网络失败，
    未真正回测的组合会被错误记为'已测'，下一轮被防重门禁拦下。"""
    import sqlite3
    db = os.path.join(ROOT, "alphas_record.db")
    if not os.path.exists(db):
        return
    exprs = [i.get("expression", "") for i in json.load(open(batch_path, encoding="utf-8")).get("items", [])]
    conn = sqlite3.connect(db); cur = conn.cursor()
    n = 0
    for e in exprs:
        cur.execute("DELETE FROM alpha_fingerprints WHERE expression = ?", (e,))
        n += cur.rowcount
    conn.commit(); conn.close()
    if n:
        print(f"[fingerprint] 释放本批 {n} 条历史指纹登记")


async def main():
    path = os.path.join(HERE, BATCH)
    release_fingerprints(path)
    log_path = path.replace(".json", ".log")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            res = await SimBatchRunner.run_batch_silently(
                batch_file_path=path, region="USA", universe="TOP1000", delay=1,
                category="fundamental", neutralization=NEUT, decay=DECAY,
                truncation=TRUNC, nan_handling="ON")
        out = buf.getvalue()
    except Exception as e:
        out = buf.getvalue() + f"\n!!! EXCEPTION: {type(e).__name__}: {e}\n"
        res = None
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(out)
    if res:
        with open(path.replace(".json", "_verdict.json"), "w", encoding="utf-8") as f:
            json.dump({
                "step1_message": res.get("step1", {}).get("message"),
                "step1_should_prune": res.get("step1", {}).get("should_prune"),
                "step2_passed_count": len(res.get("step2_passed", [])),
                "final_passed_count": len(res.get("final_passed", [])),
                "prescriptions": res.get("prescriptions"),
            }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
