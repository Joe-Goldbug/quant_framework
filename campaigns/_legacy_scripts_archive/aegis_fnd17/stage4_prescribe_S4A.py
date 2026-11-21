# -*- coding: utf-8 -*-
"""Stage 4 · S4-A：σ 锐化探针批（8 槽，纯机制表征）

═══════════════════════════════════════════════════════════════════════════
为什么做这一批
───────────────────────────────────────────────────────────────────────────
平台口径 Ret = Sh × σ_annual。本账户今日两条实测 alpha 落在同一条等值线上：

    FCF/Asset vs 营业利润率 @ d0/MKT/nanOFF : Sh 0.85  σ 4.96%  Ret 4.22%  Mgn 41.1bp  Fit 0.49
    同结构               @ d8/STAT/nanON : Sh 1.11  σ 2.57%  Ret 2.85%  Mgn  9.6bp  Fit 0.53

⇒ 设置档只在这条等值线上滑动，Fit 几乎不动。**光调设置档永远过不了 Fitness。**
⇒ Fit = Sh^1.5 × √(8σ) ⇒ 必须**同时**抬 Sh 和 σ。

σ 的抬升手段：power(·, 5) 权重锐化（本账户新闻冠军 Sh1.67/Fit0.95 已验证此结构可用）。
本批的**唯一研究问题**：power 锐化在本数据集上把 σ 抬高多少？Sharpe 损失多少？

★ 纪律
  - 只做回测，绝不触碰任何提交接口。
  - 槽位是**机制表征**（表征 σ(exponent) 与 σ(structure) 的响应曲线），不是网格凑夏普。
  - 最终种子若采用 power，指数固定为 5（与新闻冠军一致），不做微调。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

# --- 骨架片段 ---------------------------------------------------------------
FCFA_120 = ("divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_atmtt,120))")
FCFR_120 = ("divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_arev,120))")
FCFA_252 = ("divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252))")
FCFR_252 = ("divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_arev,252))")
OPM_120 = "ts_backfill(fnd17_ttmopmgn,120)"
OPM_252 = "ts_backfill(fnd17_ttmopmgn,252)"


def shp(inner, exp=5):
    """power(subtract(group_rank(inner, sector), 0.5), exp) —— 零均值锐化权重。"""
    return f"power(subtract(group_rank({inner}, sector), 0.5), {exp})"


# --- 8 槽 -------------------------------------------------------------------
EXPRS = [
    # 1. 基线：S3_03 结构，仅把 backfill 250 → 120（隔离窗口效应，无 power）
    ("P01_BASE_2LEG_BF120",
     f"subtract(group_rank({FCFA_120}, sector), multiply(0.5, group_rank({OPM_120}, sector)))"),

    # 2. 单腿锐化（FCF/资产）
    ("P02_POW5_SINGLE_FCFA_120", shp(FCFA_120)),

    # 3. 两腿锐化（FCF/资产 vs 营业利润率），等权 11 算子
    ("P03_POW5_2LEG_FCFA_120", f"subtract({shp(FCFA_120)}, {shp(OPM_120)})"),

    # 4. 单腿锐化，backfill 252
    ("P04_POW5_SINGLE_FCFA_252", shp(FCFA_252)),

    # 5. 两腿锐化，backfill 252
    ("P05_POW5_2LEG_FCFA_252", f"subtract({shp(FCFA_252)}, {shp(OPM_252)})"),

    # 6. ★ 指数表征槽：power 3（只用于刻画 σ 对指数的响应，不是调参凑夏普）
    ("P06_POW3_SINGLE_FCFA_120", shp(FCFA_120, 3)),

    # 7. 单腿锐化，换分母（FCF/收入）
    ("P07_POW5_SINGLE_FCFR_120", shp(FCFR_120)),

    # 8. 两腿锐化，换分母（FCF/收入 vs 营业利润率）
    ("P08_POW5_2LEG_FCFR_120", f"subtract({shp(FCFR_120)}, {shp(OPM_120)})"),
]

MECH = "现金创造效率与账面盈利口径在行业内的相对价差；power 锐化把零均值组内秩的权重分布拉向两端以抬升年化波动 σ"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批的唯一研究问题不是「哪条夏普最高」，而是**σ 对 power 锐化的响应**："
    "平台 Ret = Sh × σ_annual，而 Fit = Sh^1.5 × √(8σ)（TO<12.5% 时），"
    "本账户今日两条实测 alpha 落在同一条等值线上（Sh0.85/σ4.96%/Fit0.49 与 Sh1.11/σ2.57%/Fit0.53），"
    "证明设置档只能沿等值线滑动、无法独立抬高 Fit ⇒ 必须同时抬 Sh 与 σ。"
    "②power(subtract(group_rank(x,sector),0.5),5) 用奇整数幂把零均值组内秩的权重分布锐化："
    "中部压扁、两端放大 ⇒ 有效持仓集中 ⇒ σ 上升；排序不变 ⇒ Sharpe 理论上几乎不损。"
    "该结构已在本账户 USA/TOP1000/d1 新闻线上验证（Sh1.65~1.67 / Fit0.95~0.97 / 零 CONCENTRATED_WEIGHT），"
    "但**从未在 fundamental17 上验证过**。"
    "③槽位设计为机制表征：P01 无 power 为基线；P02/P04/P07 单腿；P03/P05/P08 两腿等权；"
    "P06 用指数 3 刻画 σ 对指数的响应斜率（仅表征，最终种子指数固定 5，不做网格微调）。"
    "④backfill 250 → 120/252：250 不在窗口白名单且长于披露节奏；120/252 为白名单内两端。"
    "⑤全部零均值顶层（外层 subtract 或 power 奇整数幂）、3 字段、无量价字段、零 PV 污染。"
)


def main():
    meta = P.load_meta()

    items = []
    for i, (sid, expr) in enumerate(EXPRS, 1):
        r = P.preflight(expr, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
        if not r["ok"]:
            print(f"❌ slot{i} {sid} 预检未过: {r['issues']}")
            return
        fids = P.field_ids(expr)
        acs = [meta[f]["alphaCount"] for f in fids]
        items.append({
            "slot": i, "expression": expr, "q": "SIGMA_PROBE",
            "seed_id": sid, "fields": fids,
            "mechanism": MECH, "counterparty": CP, "optimize_reason": REASON,
            "treatment_tag": "sigma_sharpen",
            "sum_alphaCount": sum(acs), "field_acs": acs,
            "field_covs": [meta[f]["coverage"] for f in fids],
            "operator_count": r["checks"]["operator_count"],
            "top_profile": r["checks"]["top_level_profile"],
            "preflight_ok": True,
        })

    exprs = [it["expression"] for it in items]
    sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
    print(f"骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    hist_v = [v for v in sk["violations"] if not v.startswith("同骨架")]
    for v in hist_v:
        print("  ❌", v)
    dup = [v for v in sk["violations"] if v.startswith("同骨架")]
    if dup:
        print("  ⚠️ 骨架重复:", dup)
    for it, s in zip(items, sk["skeletons"]):
        it["skeleton"] = s
        it["skeleton_history"] = sk["history"].get(s, 0)

    batch = {
        "batch_name": "aegis_fnd17_S4A_SIGMA_PROBE", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_S4A_sigma_probe", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY",
                     "neutralization": "STATISTICAL", "decay": 8,
                     "truncation": 0.08, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "σ 锐化机制表征：power(subtract(group_rank(x,sector),0.5),5) 对 σ/Sharpe/Fit 的净效应",
            "step1_funnel": "诊断批次，不剪枝；全 8 条回测留档。",
            "readout": "σ_annual = Ret / Sharpe；判定 power 是否值得采用（Δσ>0 且 ΔSh 不致命）",
        },
        "preregistered_notes": [
            "唯一研究问题 = σ 响应曲线，不是夏普网格搜索。",
            "最终种子若采用 power，指数固定 5（与本账户新闻冠军一致），不做微调。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4A.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {out}  ({len(items)} 槽)")

    for it in items:
        print(f"  slot{it['slot']} {it['seed_id']:<26} ops={it['operator_count']:<3} "
              f"zm={it['top_profile']['zero_mean']} ac={it['sum_alphaCount']:<3} "
              f"{it['expression'][:96]}")


if __name__ == "__main__":
    main()
