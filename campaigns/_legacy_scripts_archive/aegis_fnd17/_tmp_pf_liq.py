# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths
sys.path.insert(0, _paths.ROOT)
import stage3_preflight as P
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)

meta = P.load_meta()
EXPRS = {
 "S4_L_01": "power(subtract(group_rank(divide(fnd17_qcash, fnd17_atq), sector), 0.5), 5)",
 "S4_L_02": "power(subtract(group_rank(divide(fnd17_qcash, ts_backfill(fnd17_qcurliab,120)), sector), 0.5), 5)",
 "S4_L_03": "power(subtract(group_rank(divide(ts_backfill(fnd17_ttmebit,120), ts_backfill(fnd17_ttmintexp,120)), sector), 0.5), 5)",
 "S4_L_04": "power(subtract(group_rank(subtract(ts_backfill(fnd17_aquickrati,120), ts_backfill(fnd17_acurratio,120)), sector), 0.5), 5)",
}
MECH = "流动性与偿债覆盖轴：行业内相对结构 + power(.,5) 权重锐化抬升年化波动"
for cid, e in EXPRS.items():
    r = P.preflight(e, MECH, "只按账面流动性指标被动再平衡的资金", meta, meta, phase0=False, op_cap_override=6)
    c = r["checks"]
    print("="*72)
    print(cid, "OK=", r["ok"], "| ops=", c.get("operator_count"), "fields=", c.get("field_count"))
    print("  ", e)
    print("  top=", c.get("top_level"), "zm=", c.get("top_level_profile"), "wins=", c.get("windows"))
    print("  dim=", c.get("dimension_audit"), "rt=", c.get("engine_redteam"))
    print("  mult_ok=", c.get("multiply_legs_ok"), "pv=", c.get("pv_clean"), "units=", c.get("unit_consistent"))
    print("  acs=", [(f, meta[f]["alphaCount"], meta[f]["coverage"]) for f in c.get("fields_used")])
    if r["issues"]: print("  ISSUES:", r["issues"])
    print("  SKELETON:", CORR.get_canonical_skeleton(e))
