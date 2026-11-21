# -*- coding: utf-8 -*-
"""回滚 Gate1-C 批的幻影指纹: 该批 8 个 children 全部 CANCELLED/ERROR, 零数据产出。
C2-C8 共 7 条表达式从未被测过(被 slot7 group_mean 参数错误连坐取消), 其指纹记录属于
"已记录但未送达有效数据"状态。按框架 purge 机制回滚, 以便 Direction C 假说(累积订单流)
获得真正的首次测量机会。CTRL 锚不 purge(A/B/D 三批均已产出数据)。
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
REGION, UNIVERSE, DELAY, NEUT = "USA", "TOP1000", 1, "INDUSTRY"


def main():
    batch = json.load(open(os.path.join(CAMPAIGN, "batch_gate1_C_1792839409.json"), encoding="utf-8"))
    items = batch["items"]
    ctrl = items[0]["expression"]
    targets = [it["expression"] for it in items[1:]]  # slot2-8
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    print("== purge 前指纹库中匹配的目标 ==")
    n_purged = 0
    for e in targets:
        fixed = corrector.correct_expression(e)
        h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, NEUT)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
            n_purged += cur.rowcount
            print(f"  [purged] {e[:80]}")
        else:
            print(f"  [absent] {e[:80]}")
    conn.commit()
    # CTRL 必须保留(已测)
    h_ctrl = corrector.compute_fingerprint(corrector.correct_expression(ctrl), REGION, UNIVERSE, DELAY, NEUT)
    cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE md5_hash = ?", (h_ctrl,))
    print(f"== CTRL 锚指纹保留检查: count={cur.fetchone()[0]} (必须=1) ==")
    conn.close()
    print(f"purged total = {n_purged}")


if __name__ == "__main__":
    main()
