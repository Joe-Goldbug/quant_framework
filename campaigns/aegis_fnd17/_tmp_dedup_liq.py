# -*- coding: utf-8 -*-
import os, sys, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import _paths; sys.path.insert(0, _paths.ROOT)
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)

MINE = {
 "S4_L_01": "power(subtract(group_rank(divide(fnd17_qcash, fnd17_atq), sector), 0.5), 5)",
 "S4_L_02": "power(subtract(group_rank(divide(fnd17_qcash, ts_backfill(fnd17_qcurliab,120)), sector), 0.5), 5)",
 "S4_L_03": "power(subtract(group_rank(divide(ts_backfill(fnd17_ttmebit,120), ts_backfill(fnd17_ttmintexp,120)), sector), 0.5), 5)",
 "S4_L_04": "power(subtract(group_rank(subtract(ts_backfill(fnd17_aquickrati,120), ts_backfill(fnd17_acurratio,120)), sector), 0.5), 5)",
}
tested = []
for f in ("batch_S1.json","batch_S2.json","batch_S3_EUR_ORIG.json","batch_S3_CAMPAIGN.json","batch_S4A_STAT_D0.json","batch_S4B_MKT_D0.json"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p): continue
    d = json.load(open(p, encoding="utf-8"))
    for it in d.get("items", []):
        tested.append((f, it.get("seed_id"), CORR.get_canonical_skeleton(it["expression"])))
tsk = {}
for f,sid,s in tested: tsk.setdefault(s,[]).append(f"{f}:{sid}")
print("tested skeletons:", len(tsk))

for cid, e in MINE.items():
    s = CORR.get_canonical_skeleton(e)
    print(f"\n{cid}\n  {s}")
    print("  dup_in_tested:", tsk.get(s, "NONE"))
    h = CORR.compute_skeleton_hash(s)
    con = sqlite3.connect(_paths.ALPHAS_DB); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash=? AND region=? AND universe=?", (h,"USA","TOP1000"))
    print("  db_history USA/TOP1000:", cur.fetchone()[0], "(fuse at >=4)")
    con.close()
    # cross-check vs the 8 S4_selected
for c in json.load(open(os.path.join(HERE,"S4_selected.json"),encoding="utf-8")):
    print("S4sel:", c.get("id"), CORR.get_canonical_skeleton(c["expression"]))
