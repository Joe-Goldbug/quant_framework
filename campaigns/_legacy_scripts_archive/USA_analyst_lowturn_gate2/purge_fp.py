"""
purge_fp.py — 清理指定批次误写入的 MD5 幻影指纹
（依据 FALS_NEWS21_008：提交在 HTTP 层失败、但 check_and_record_batch 已写指纹，
  会造成真实重试被误判为"偷懒微调"。仅在确认平台侧未产生任何仿真时使用。）
用法: python purge_fp.py batch_n2.json
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

HERE = os.path.dirname(__file__)
batch = json.load(open(os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "batch_n2.json"), encoding="utf-8"))

corrector = ASTSandboxCorrector()
db = os.path.join(os.path.dirname(HERE), "..", "alphas_record.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

removed = 0
for it in batch["items"]:
    fp = corrector.compute_fingerprint(
        corrector.correct_expression(it["expression"]),
        batch["region"], batch["universe"], batch["delay"], batch["neutralization"],
    )
    cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (fp,))
    removed += cur.rowcount
conn.commit()
conn.close()
print(f"purged {removed} phantom fingerprints for batch '{sys.argv[1] if len(sys.argv) > 1 else 'batch_n2.json'}'")
