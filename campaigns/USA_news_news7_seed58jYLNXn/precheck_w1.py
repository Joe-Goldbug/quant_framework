"""
precheck_w1.py — 本地 AST 校验与量纲审计（只读，不写指纹库，避免与 sim_runner 冲突）
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

HERE = os.path.dirname(__file__)
BATCH_FILE = sys.argv[1] if len(sys.argv) > 1 else "batch_w1.json"
batch = json.load(open(os.path.join(HERE, BATCH_FILE), encoding="utf-8"))

corrector = ASTSandboxCorrector()
db = os.path.join(os.path.dirname(HERE), "..", "alphas_record.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

BANNED = {"signed_power", "hump", "group_neutralize"}
ok_all = True
rows = []
for it in batch["items"]:
    raw = it["expression"]
    fixed = corrector.correct_expression(raw)
    fp = corrector.compute_fingerprint(fixed, batch["region"], batch["universe"],
                                       batch["delay"], batch["neutralization"])
    cur.execute("SELECT 1 FROM alpha_fingerprints WHERE md5_hash = ?", (fp,))
    dup = cur.fetchone() is not None
    audit = DimensionAuditor.audit_expression(fixed, batch["known_fields"], category=batch["category"])
    banned_hit = [b for b in BANNED if b + "(" in fixed]
    must_use = "headline_positive_term_count_v2" in fixed
    ok = audit["is_valid"] and not banned_hit and must_use
    ok_all &= ok
    rows.append({
        "id": it["id"], "type": it["type"], "ops": audit["operator_count"],
        "len": len(fixed), "dup": dup, "banned": banned_hit,
        "must_use_field": must_use, "valid": audit["is_valid"],
        "issues": audit["issues"],
    })

conn.close()

print(f"{'#':<3}{'TYPE':<42}{'OPS':<5}{'LEN':<6}{'DUP':<6}{'BANNED':<10}{'FIELD':<7}{'VALID'}")
for r in rows:
    print(f"{r['id']:<3}{r['type']:<42}{r['ops']:<5}{r['len']:<6}"
          f"{str(r['dup']):<6}{str(r['banned'] or '-'):<10}{str(r['must_use_field']):<7}{r['valid']}")
    if r["issues"]:
        print("    issues:", r["issues"])

dup_count = sum(1 for r in rows if r["dup"])
print(f"\nMD5 重复数: {dup_count} (引擎容忍上限 2, 超过则熔断)")
ok_all = ok_all and dup_count <= 2
print("ALL_PASS =", ok_all)
sys.exit(0 if ok_all else 1)
