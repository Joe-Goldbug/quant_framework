# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\campaigns\aegis_fnd17")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P

meta = P.load_meta()
print("meta fields:", len(meta))

CANDS = {
 "S4_SH_01": "subtract(power(subtract(group_rank(ts_backfill(fnd17_tcpaormtt,120), sector), 0.5), 5), power(subtract(group_rank(divide(ts_backfill(fnd17_mttshs,120), ts_backfill(fnd17_mtpshs,120)), sector), 0.5), 5))",
 "S4_SH_02": "subtract(power(subtract(group_rank(ts_backfill(fnd17_ttmopmgn,120), sector), 0.5), 5), power(subtract(group_rank(divide(ts_backfill(fnd17_shsoutavgq,120), ts_backfill(fnd17_shboutavgq,120)), sector), 0.5), 5))",
 "S4_SH_03": "subtract(power(subtract(group_rank(divide(ts_backfill(fnd17_float,120), ts_backfill(fnd17_shsout,120)), sector), 0.5), 5), power(subtract(group_rank(ts_backfill(fnd17_qtotd2eq,120), sector), 0.5), 5))",
 "S4_SH_04": "power(subtract(group_rank(divide(divide(ts_backfill(fnd17_ttmrev,120), ts_backfill(fnd17_ttmrevps,120)), ts_backfill(fnd17_shsout,120)), sector), 0.5), 5)",
}
REASON = "捕捉股本结构与盈利/融资状态的相对错配：管理层用真实资本行动（回购、减发、锁仓）投票，其信息含量高于账面盈利本身；对手方是按每股增长线性外推的卖方模型与被动再平衡资金。"
CP = "按每股盈利线性外推、忽视股本供给变化的卖方模型与被动指数再平衡资金"
allok=True
for k, e in CANDS.items():
    r = P.preflight(e, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
    c = r["checks"]
    print("="*72)
    print(k, "ok=", r["ok"], "| ops", c.get("operator_count"), "| fields", c.get("field_count"),
          "| top", c.get("top_level"), "| zm", c.get("top_level_profile"),
          "| windows", c.get("windows"))
    print("  fields_used:", c.get("fields_used"))
    print("  dim_audit:", json.dumps(c.get("dimension_audit"), ensure_ascii=False))
    print("  redteam:", json.dumps(c.get("engine_redteam"), ensure_ascii=False))
    print("  unit_legs:", c.get("subtract_legs"), "unit_ok:", c.get("unit_consistent"))
    print("  ISSUES:", r["issues"])
    allok = allok and r["ok"]

res = P.skeleton_and_fingerprint(list(CANDS.values()))
print("="*72)
print("freq:", json.dumps(res["freq"], ensure_ascii=False, indent=1))
print("violations:", res["violations"])
for k,s in zip(CANDS, res["skeletons"]):
    print(" ", k, "hist=", res["history"][s])
    print("     ", s)
print("ALL OK:", allok)
