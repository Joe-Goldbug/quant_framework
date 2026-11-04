# -*- coding: utf-8 -*-
"""V2_B candidate draft: build + preflight + skeleton check."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _v2b_preflight as V

CANDS = [
 dict(id="V2_B_01", q="Q5_Structure", decay=8, pow=3, grp="sector",
      expr="power(subtract(group_rank(divide(oth466_bs_bv_tang,oth466_q_q_qta_sb),sector),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,sector))),3)",
      mech="有形账面价值占总资产比重（Berkshire 式硬资产占比）与权益乘数（总资产/普通股权益）之间的行业内相对错配。",
      cp="只看净资产收益率与每股账面、从不核对资产里有多少是商誉与无形、也从不追问这些资产是自有资金买的还是杠杆撬动的价值风格买方",
      why="结构论证"),
 dict(id="V2_B_02", q="Q8_Essence", decay=8, pow=3, grp="industry",
      expr="power(subtract(group_rank(divide(fnd23_intfvm_eltq,fnd23_intfvm_tota),industry),multiply(0.5,group_rank(oth466_rt_roce,industry))),3)",
      mech="合并口径权益占总资产比重与股东权益回报率的行业相对错配，度量净资产缓冲未被定价的幅度。",
      cp="以净资产收益率单一口径给公司贴价值标签、把厚权益缓冲当作不赚钱的累赘而给予折价的成长风格资金",
      why="结构论证"),
 dict(id="V2_B_03", q="Q1_Invariance", decay=8, pow=5, grp="subindustry",
      expr="power(subtract(group_rank(divide(fnd23_intfvm_dttl,fnd23_intfvm_dlts),subindustry),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,subindustry))),5)",
      mech="长期债务占总债务比重与权益乘数的子行业内相对错配，度量再融资墙与杠杆负担的双重脆弱。",
      cp="只看利息保障倍数与账面杠杆、忽略债务到期期限结构、并在短债续作窗口被迫抛售的高收益信用配置资金",
      why="结构论证"),
 dict(id="V2_B_04", q="Q3_Anomaly", decay=4, pow=3, grp="sector",
      expr="power(subtract(group_rank(divide(fnd23_intfvm_vbts,fnd23_intfvm_eltq),sector),multiply(0.5,group_rank(oth466_rt_cash_roce,sector))),3)",
      mech="有形账面价值占股东权益比重与现金收益回报率的行业相对错配，度量并购商誉对权益的稀释未被定价的幅度。",
      cp="把靠并购堆出来的现金利润当作内生盈利能力、直到商誉减值公告才重估利润质量的并购型成长资金",
      why="结构论证"),
 dict(id="V2_B_05", q="Q7_Relative", decay=8, pow=3, grp="subindustry",
      expr="power(subtract(group_rank(oth466_bs_bps_tang_q,subindustry),multiply(0.5,group_rank(oth466_rt_assets_com_eq_q,subindustry))),3)",
      mech="每股有形账面价值与权益乘数的子行业相对错配，度量每股硬资产支撑在压力情景下的可信度。",
      cp="按每股账面价值高低排序买入账面、却不追问账面背后的股本杠杆倍数、在减记中才发现每股净值经不起压力的价值陷阱资金",
      why="结构论证"),
]

if __name__ == "__main__":
    exprs = [c["expr"] for c in CANDS]
    allok = True
    for c in CANDS:
        r = V.preflight_v2(c["expr"], c["mech"], c["cp"])
        print(f"\n### {c['id']} [{c['q']}] group={c['grp']} decay={c['decay']} power={c['pow']}")
        print("  expr:", c["expr"])
        print("  ok =", r["ok"], "| issues:", r["issues"])
        ck = r["checks"]
        print(f"  ops={ck['operator_count']} fields={ck['field_count']} ds={ck['datasets_used']} top={ck['top_level']} zm={ck['top_level_zero_mean']}")
        for f, m in ck.get("field_meta", {}).items():
            print(f"    - {f:38s} {m['ds']:13s} cov={m['cov']} ac={m['ac']} | {m['desc'][:70]}")
        allok = allok and r["ok"]
    print("\n=== ALL OK:", allok, "===")
    skels, hist = V.skeleton_history(exprs)
    print("\n=== skeleton uniqueness / cross-batch history ===")
    for c, s, h in zip(CANDS, skels, [hist[s] for s in skels]):
        print(f"  {c['id']}: hist={h}  skel={s[:130]}")
    print("  distinct skeletons:", len(set(skels)), "/", len(skels))
