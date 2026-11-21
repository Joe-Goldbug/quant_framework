# -*- coding: utf-8 -*-
import os, sys, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import _paths; sys.path.insert(0, _paths.ROOT)
import stage3_preflight as P
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)
meta = P.load_meta()
ref = json.load(open(os.path.join(HERE,"agent_field_ref.json"),encoding="utf-8"))

E = {
 "S4_L_01": "power(subtract(group_rank(divide(fnd17_qcash, fnd17_atq), sector), 0.5), 5)",
 "S4_L_02": "power(subtract(group_rank(subtract(ts_backfill(fnd17_aquickrati, 120), ts_backfill(fnd17_acurratio, 120)), sector), 0.5), 5)",
 "S4_L_03": "ts_av_diff(power(subtract(group_rank(divide(fnd17_qebit, fnd17_zpxetniq), sector), 0.5), 5), 120)",
 "S4_L_04": "ts_mean(power(subtract(group_rank(divide(fnd17_qcash, ts_backfill(fnd17_qcurliab, 120)), sector), 0.5), 5), 60)",
}
def fam(e):
    cs,_,_ = P.ast_calls(e)
    inner=[c for c in cs if c not in ("ts_backfill","zscore","group_zscore")]
    return inner[0] if inner else cs[0]
MECH="流动性与偿债覆盖轴：行业内相对水平结构 + power(subtract(group_rank(x,g),0.5),5) 权重锐化抬升年化波动"
for cid,e in E.items():
    fs=P.field_ids(e)
    r=P.preflight(e,MECH,"只按账面流动性指标被动再平衡的资金",meta,meta,phase0=False,op_cap_override=6)
    c=r["checks"]; s=CORR.get_canonical_skeleton(e); h=CORR.compute_skeleton_hash(s)
    con=sqlite3.connect(_paths.ALPHAS_DB);cur=con.cursor()
    cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash=? AND region=? AND universe=?",(h,"USA","TOP1000"))
    dbn=cur.fetchone()[0];con.close()
    print(f"{cid} OK={r['ok']} ops={c['operator_count']} fam={fam(e)} fields={c['field_count']} top={c['top_level']} zm={c['top_level_profile']['zero_mean']}")
    print(f"   wins={c['windows']} dim={c['dimension_audit']['is_valid']} rt={c['engine_redteam']['verdict']} pv={c['pv_clean']} mult={c['multiply_legs_ok']} unit={c['unit_consistent']} dbhist={dbn}")
    print(f"   missing_ref={[f for f in fs if f not in ref]} ac/cov={[(f,ref[f]['ac'],ref[f]['cov']) for f in fs]}")
    print(f"   skel={s}")
    if r["issues"]: print("   ISSUES:",r["issues"])
print("\nfamilies:", [fam(e) for e in E.values()])
print("unique skeletons:", len({CORR.get_canonical_skeleton(e) for e in E.values()}))
