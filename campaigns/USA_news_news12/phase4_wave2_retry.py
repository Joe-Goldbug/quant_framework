# -*- coding: utf-8 -*-
"""Wave 2 retry v2: STATISTICAL neutralization paired ablation with backoff (proxy transients)."""
import asyncio
import glob
import json
import os
import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.sim_runner import SimBatchRunner
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

CAMPAIGN = os.path.join("quant_framework", "campaigns", "USA_news_news12")


def purge():
    batch_path = sorted(glob.glob(os.path.join(CAMPAIGN, "batch_wave2_neut_ablation_*.json")))[-1]
    with open(batch_path, encoding="utf-8") as f:
        items = json.load(f)["items"]
    c = ASTSandboxCorrector()
    conn = sqlite3.connect(c.db_path)
    cur = conn.cursor()
    n = 0
    for it in items:
        h = c.compute_fingerprint(c.correct_expression(it["expression"]), "USA", "TOP1000", 1, "STATISTICAL")
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[purge] removed {n} phantom STATISTICAL fingerprints", flush=True)


async def main():
    batch_path = sorted(glob.glob(os.path.join(CAMPAIGN, "batch_wave2_neut_ablation_*.json")))[-1]
    print(f"[Wave 2 retry] batch file: {batch_path}", flush=True)
    last_err = None
    for attempt in range(1, 6):
        try:
            print(f"[Wave 2 retry] attempt {attempt}/5 ...", flush=True)
            res = await SimBatchRunner.run_batch_silently(
                batch_file_path=batch_path, region="USA", universe="TOP1000", delay=1,
                category="news", neutralization="STATISTICAL", decay=6, truncation=0.025)
            with open(batch_path.replace(".json", "_summary.json"), "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=1, default=str)
            print("[Wave 2 retry] SUCCESS", flush=True)
            return
        except Exception as e:
            last_err = e
            print(f"[Wave 2 retry] attempt {attempt} failed: {str(e)[:150]}", flush=True)
            if attempt < 5:
                await asyncio.sleep(30)
    purge()
    raise RuntimeError(f"Wave 2 五次尝试全部失败: {last_err}")


asyncio.run(main())
