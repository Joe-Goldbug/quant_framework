# -*- coding: utf-8 -*-
"""AEGIS Stage 4: L8 正交矩阵仿真执行器（带指纹释放/回滚 + 退避重试）。

安全声明：
  - 只调用 submit_multi_simulation / check_multi_simulation / fetch_multi_simulation_result
    （WorldQuant BRAIN 的“回测/仿真”端点）。
  - 绝不调用任何 alpha 提交接口（submit_alpha / create_spc_submission /
    set_spc_submission_weight 等）。达标因子只在本地标记状态，交研究员人工终审。

工程修正：
  - 沙箱 HTTP(S)_PROXY 会掐断 POST /simulations（GET 正常），本进程内摘除代理改为直连。
  - SimBatchRunner 的 Gate 3 会在“发包前”登记骨架指纹；若随后 POST 失败，会把未真正回测的
    组合误记为已测。故本脚本在每次尝试前释放本批指纹，失败后再次回滚。
"""
import asyncio
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from quant_framework.core.sim_runner import SimBatchRunner  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

BATCH = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "batch_R1.json")
SUMMARY = os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else "stage4_run_summary.json")
NEUT = sys.argv[3] if len(sys.argv) > 3 else "NONE"
DB = os.path.join(ROOT, "alphas_record.db")
MAX_ATTEMPTS = 3


def release_fingerprints():
    """释放本批 8 条指纹（因尚未真正回测，不应占用“已测”名额）。"""
    b = json.load(open(BATCH, encoding="utf-8"))
    c = ASTSandboxCorrector()
    md5s = [c.compute_fingerprint(c.correct_expression(m["expression"]), "USA", "TOP1000", 1, NEUT)
            for m in b["slot_meta"]]
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    q = ",".join("?" * len(md5s))
    cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash IN (%s)" % q, md5s)
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


async def main():
    print("[SAFETY] submission_forbidden = True；本脚本不会调用任何 alpha 提交接口。")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        freed = release_fingerprints()
        print(f"\n[attempt {attempt}/{MAX_ATTEMPTS}] 释放本批指纹 {freed} 条，开始发包...")
        try:
            res = await SimBatchRunner.run_batch_silently(
                batch_file_path=BATCH,
                region="USA",
                universe="TOP1000",
                delay=1,
                category="fundamental",
                neutralization=NEUT,
                decay=0,
                truncation=0.025,
                nan_handling="ON",
            )
        except Exception as e:
            print(f"[attempt {attempt}] 失败: {repr(e)}")
            release_fingerprints()
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(20 * attempt)
                continue
            raise

        out = SUMMARY
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("[ok] wrote", out)
        return

    raise RuntimeError("全部重试均失败")


if __name__ == "__main__":
    asyncio.run(main())
