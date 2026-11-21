# -*- coding: utf-8 -*-
"""V2_B FINAL candidate set — sign discipline: A leg = quality (long high),
B leg = fragility (long low). Composite = group_rank(A) - 0.5*group_rank(B), power(odd) on top."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _v2b_preflight as V

CANDS = [
 dict(id="V2_B_01", q="Q5_Structure", decay=8, grp="sector",
      expr="power(subtract(group_rank(divide(oth466_bs_bv_tang,oth466_bs_assets_tot),sector),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,sector))),3)",
      ds=["other466"],
      mech="有形账面价值占总资产比重（Berkshire 式硬资产覆盖率）与权益乘数（总资产/普通股权益）之间的行业内相对错配。",
      cp="按 P/B 深度价值买入、从不核对资产里有多少是商誉与无形、也从不追问这层资产是自有资金买来的还是杠杆撬出来的价值风格买方"),
 dict(id="V2_B_02", q="Q8_Essence", decay=8, grp="industry",
      expr="power(subtract(group_rank(oth466_rt_cash_roce,industry),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,industry))),3)",
      ds=["other466"],
      mech="现金收益股东权益回报率与权益乘数之间的行业相对错配：赚的是不是真现金，撑起这些回报的杠杆有多重。",
      cp="只认会计净利润口径的权益回报率、把杠杆撬出来的回报当成经营能力、在利率上行时被迫平仓的业绩追逐型买方"),
 dict(id="V2_B_03", q="Q7_Relative", decay=8, grp="subindustry",
      expr="power(subtract(group_rank(divide(fnd23_intfvm_dttl,fnd23_intfvm_dlts),subindustry),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,subindustry))),5)",
      ds=["fundamental23","other466"],
      mech="长期有息债务占总有息债务比重（债务期限阶梯）与权益乘数之间的子行业相对错配。",
      cp="只看总杠杆率与利息保障倍数、从不看债务到期阶梯、在短债续作窗口被迫贱卖自己组合的高收益信用配置资金"),
 dict(id="V2_B_04", q="Q3_Anomaly", decay=8, grp="industry",
      expr="power(subtract(group_rank(divide(fnd23_intfvm_vbts,fnd23_intfvm_eltq),industry),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,industry))),3)",
      ds=["fundamental23","other466"],
      mech="有形账面价值占股东权益比重（并购商誉与无形资产对权益的稀释）与权益乘数之间的行业相对错配。",
      cp="把并购换来的利润当作内生盈利能力、照成长倍数给估值、直到商誉减值公告才重估利润质量的并购型成长资金"),
 dict(id="V2_B_05", q="Q6_Accumulation", decay=4, grp="sector",
      expr="power(subtract(group_rank(divide(fnd3_qacctadj_currentassets_fast_d1,fnd3_q_currentliabilities),sector),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,sector))),3)",
      ds=["fundamental3","other466"],
      mech="流动比率（流动资产对流动负债的覆盖）与权益乘数之间的行业相对错配，度量资产负债表能否自己撑过一轮收缩。",
      cp="只看账面资产折价买入、从不核对资产能不能变现去还到期债务、在第一轮信用收缩里被同一批同行一起清空的深度价值抄底资金"),
]

if __name__ == "__main__":
    exprs = [c["expr"] for c in CANDS]
    allok = True
    for c in CANDS:
        r = V.preflight_v2(c["expr"], c["mech"], c["cp"])
        ck = r["checks"]
        print(f"### {c['id']} [{c['q']}] grp={c['grp']} decay={c['decay']}  ok={r['ok']}  issues={r['issues']}")
        print(f"    ops={ck['operator_count']} fields={ck['field_count']} ds={ck['datasets_used']} top={ck['top_level']} zm={ck['top_level_zero_mean']} pv={ck['pv_clean']}")
        for f, m in ck.get("field_meta", {}).items():
            print(f"      - {f:38s} {m['ds']:13s} cov={m['cov']} ac={m['ac']} | {m['desc'][:62]}")
        allok = allok and r["ok"]
        print()
    print("=== ALL PREFLIGHT OK:", allok, "===")
    skels, hist = V.skeleton_history(exprs)
    print("=== skeleton distinctness ===")
    for c, s in zip(CANDS, skels):
        print(f"  {c['id']}: hist={hist[s]}  {s[:120]}")
    print("  distinct:", len(set(skels)), "/", len(skels))
