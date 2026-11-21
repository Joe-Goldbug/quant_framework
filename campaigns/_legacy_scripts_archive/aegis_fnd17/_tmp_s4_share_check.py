# -*- coding: utf-8 -*-
import sys, json, io
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\campaigns\aegis_fnd17")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P

meta = P.load_meta()
print("meta fields:", len(meta))

CANDS = {
 "S4_SH_01": "subtract(power(subtract(group_rank(divide(ts_backfill(fnd17_float,120), ts_backfill(fnd17_shsout,120)), sector), 0.5), 5), multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,120), sector)))",
 "S4_SH_02": "power(subtract(group_rank(divide(divide(ts_backfill(fnd17_ttmrev,120), ts_backfill(fnd17_ttmrevps,120)), ts_backfill(fnd17_shsout,120)), sector), 0.5), 5)",
 "S4_SH_03": "subtract(power(subtract(group_rank(ts_backfill(fnd17_ttmroepct,120), sector), 0.5), 5), power(subtract(group_rank(divide(ts_backfill(fnd17_shsoutavgq,120), ts_backfill(fnd17_shboutavgq,120)), sector), 0.5), 5))",
 "S4_SH_04": "subtract(power(subtract(group_rank(divide(ts_backfill(fnd17_mttshs,120), ts_backfill(fnd17_shsout,120)), sector), 0.5), 5), multiply(0.5, group_rank(ts_backfill(fnd17_tcpaormtt,120), sector)))",
}
for k, e in CANDS.items():
    r = P.preflight(e, "捕捉股本结构与盈利水平的相对错配", "以股权融资扩张与以股权替代薪酬的发行人", meta, meta, phase0=False, op_cap_override=11)
    c = r["checks"]
    print("="*70)
    print(k, "ok=", r["ok"])
    print("  ops", c.get("operator_count"), "fields", c.get("field_count"), "top", c.get("top_level"), "zm", c.get("top_level_profile"))
    print("  fields_used", c.get("fields_used"))
    print("  dim_audit", json.dumps(c.get("dimension_audit"), ensure_ascii=False))
    print("  redteam", json.dumps(c.get("engine_redteam"), ensure_ascii=False)[:400])
    print("  issues", r["issues"])

res = P.skeleton_and_fingerprint(list(CANDS.values()))
print("="*70)
print("skeletons:")
for k, s in zip(CANDS, res["skeletons"]):
    print(" ", k, s[:120])
print("freq", json.dumps(res["freq"], ensure_ascii=False)[:600])
print("violations", res["violations"])
print("history", json.dumps(res["history"], ensure_ascii=False)[:800])
