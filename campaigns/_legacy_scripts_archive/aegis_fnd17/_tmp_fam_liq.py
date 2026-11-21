# -*- coding: utf-8 -*-
import os, sys, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import _paths; sys.path.insert(0, _paths.ROOT)
import stage3_preflight as P
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)

E = {
 "S4_L_01": "subtract(power(subtract(group_rank(divide(fnd17_qcash, fnd17_atq), sector), 0.5), 5), multiply(0.5, power(subtract(group_rank(ts_backfill(fnd17_ttmintcov, 120), sector), 0.5), 5)))",
 "S4_L_02": "power(subtract(group_rank(divide(fnd17_qcash, ts_backfill(fnd17_qcurliab, 120)), sector), 0.5), 5)",
 "S4_L_03": "power(subtract(group_rank(subtract(ts_backfill(fnd17_qquickrati, 120), ts_backfill(fnd17_qcurratio, 120)), sector), 0.5), 5)",
 "S4_L_04": "power(subtract(group_rank(ts_mean(divide(ts_backfill(fnd17_qebit, 120), ts_backfill(fnd17_zpxetniq, 120)), 60), sector), 0.5), 5)",
}
def op_family(e):
    cs,_,_ = P.ast_calls(e)
    inner = [c for c in cs if c not in ("ts_backfill","zscore","group_zscore")]
    return inner[0] if inner else (cs[0] if cs else "?")
meta = P.load_meta()
ref = json.load(open(os.path.join(HERE,"agent_field_ref.json"),encoding="utf-8"))
MECH="流动性与偿债覆盖轴：行业内相对结构 + power(.,5) 权重锐化抬升年化波动"
for cid,e in E.items():
    fs = P.field_ids(e)
    missing = [f for f in fs if f not in ref]
    r = P.preflight(e, MECH, "只按账面流动性指标被动再平衡的资金", meta, meta, phase0=False, op_cap_override=11)
    s = CORR.get_canonical_skeleton(e)
    h = CORR.compute_skeleton_hash(s)
    con = sqlite3.connect(_paths.ALPHAS_DB); cur=con.cursor()
    cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash=? AND region=? AND universe=?", (h,"USA","TOP1000"))
    dbn = cur.fetchone()[0]; con.close()
    print(f"{cid}: preflight_ok={r['ok']} ops={r['checks']['operator_count']} fam={op_family(e)} dbhist={dbn}")
    print(f"   fields={fs} missing={missing}")
    print(f"   acs={[(f, ref[f]['ac'], ref[f]['cov'], ref[f]['sp']) for f in fs]}")
    print(f"   skel={s}")
    if r["issues"]: print("   ISSUES:", r["issues"])
