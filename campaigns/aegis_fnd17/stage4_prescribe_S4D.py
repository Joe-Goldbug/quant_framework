# -*- coding: utf-8 -*-
"""Stage 4 · S4-D：σ 杠杆 × neutralization 杠杆的**正交叠加**（8 槽）

═══════════════════════════════════════════════════════════════════════════
两条已实测的独立杠杆
───────────────────────────────────────────────────────────────────────────
杠杆 1（结构）：power 锐化抬 σ
    S3_03 基线（两腿 group_rank 差）        Sh 1.10  σ 2.57%  Mgn  9.5bp
    S4-A P06 单腿 power3                    Sh 1.04  σ 3.19%  Mgn  9.9bp   (+24% σ)
    S4-A P02 单腿 power5                    Sh 0.90  σ 3.38%  Mgn  8.6bp   (+31% σ)
    ⚠ 两腿各自 power 后相减 → Sh 崩到 0.30（排序信息被摧毁）

杠杆 2（设置）：neutralization 抬 σ（**衰减/换手衰减才是小杠杆**）
    S4-B B01 基准 d8/STAT/nanON/tr0.08      Sh 1.10  σ 2.57%  Mgn  9.5bp  TO 5.96%
    S4-B B05 只改 neutralization→MARKET      Sh 0.97  σ 5.66%  Mgn 74.0bp  TO 1.48%
    S4-B B06 只改 neutralization→INDUSTRY    Sh 0.97  σ 5.14%  Mgn 51.5bp  TO 1.94%
    ⚠ decay∈{0,4,8,16} / nan / trunc 全部几乎无影响（σ 2.52~2.59%）

★ 本批研究问题：这两条杠杆**是否可叠加**？
  若叠加：Sh 1.04~1.15 × σ 5% ⇒ Ret 5.2~5.7% ⇒ Fit = Sh×√(Ret/0.125)
    Sh 1.10 时 Fit = 1.10×√(5.5/12.5) = 0.73
    Sh 1.15 时 Fit = 1.15×√(5.7/12.5) = 0.78
  ⇒ 仍差 Fit 1.0 一截 ⇒ **Sharpe 仍须从 1.1 抬到 1.4~1.58**。

★ 目标坐标（TO<12.5% 时 Fit = Sh^1.5 × √(8σ)）：
    Sh 1.58 需 σ ≥ 3.17%   ← 已被 neutralization 达成（5%+）
    Sh 1.30 需 σ ≥ 5.69%   ← MARKET 档接近（5.66%）
  ⇒ 本批同时测两个坐标：能否用 MARKET 档的 σ 换取更高的 Sh。

★ 纪律：只做回测，绝不触碰任何提交接口。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

FCFA_120 = "divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_atmtt,120))"
FCFA_252 = "divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252))"
OPM_120 = "ts_backfill(fnd17_ttmopmgn,120)"
OPM_252 = "ts_backfill(fnd17_ttmopmgn,252)"
GROSS_120 = "ts_backfill(fnd17_grosmgn5yr,120)"

# (id, expression, settings_probe)
EXPRS = [
    # 1. ★ 两腿差值后锐化(power3) @ MARKET —— 主力叠加假设
    ("D01_DIFFPOW3_MKT",
     f"power(subtract(group_rank({FCFA_120}, sector), group_rank({OPM_120}, sector)), 3)",
     {"neutralization": "MARKET", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 2. ★ 两腿差值后锐化(power3) @ STATISTICAL —— 与 D1 配对，隔离 neutralization
    ("D02_DIFFPOW3_STAT",
     f"power(subtract(group_rank({FCFA_120}, sector), group_rank({OPM_120}, sector)), 3)",
     {"neutralization": "STATISTICAL", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 3. ★ 单腿 power3 @ MARKET —— power × MARKET 的纯叠加
    ("D03_SINGLEPOW3_MKT",
     f"power(subtract(group_rank({FCFA_120}, sector), 0.5), 3)",
     {"neutralization": "MARKET", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 4. ★ 单腿 power3 @ INDUSTRY —— 第三个 neutralization 档
    ("D04_SINGLEPOW3_IND",
     f"power(subtract(group_rank({FCFA_120}, sector), 0.5), 3)",
     {"neutralization": "INDUSTRY", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 5. 两腿差值后锐化(power3) @ MARKET，backfill 252
    ("D05_DIFFPOW3_MKT_252",
     f"power(subtract(group_rank({FCFA_252}, sector), group_rank({OPM_252}, sector)), 3)",
     {"neutralization": "MARKET", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 6. 两腿差值后锐化(power5) @ MARKET —— 指数表征
    ("D06_DIFFPOW5_MKT",
     f"power(subtract(group_rank({FCFA_120}, sector), group_rank({OPM_120}, sector)), 5)",
     {"neutralization": "MARKET", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 7. 两腿差值后锐化(power3) @ MARKET，换第二腿为五年毛利率中枢
    ("D07_DIFFPOW3_MKT_GROSS5Y",
     f"power(subtract(group_rank({FCFA_120}, sector), group_rank({GROSS_120}, sector)), 3)",
     {"neutralization": "MARKET", "decay": 8, "truncation": 0.08, "nan_handling": "ON"}),

    # 8. ★ 两腿差值后锐化(power3) @ MARKET + decay=0（低衰减保 σ）
    ("D08_DIFFPOW3_MKT_D0",
     f"power(subtract(group_rank({FCFA_120}, sector), group_rank({OPM_120}, sector)), 3)",
     {"neutralization": "MARKET", "decay": 0, "truncation": 0.08, "nan_handling": "ON"}),
]

MECH = "现金创造效率与账面盈利口径在行业内的相对价差；在差值之后施加奇整数幂锐化，并配合低衰减中性化档抬升年化波动 σ"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批检验**两条已实测的独立 σ 杠杆是否可叠加**："
    "结构杠杆（power 锐化，S4-A 实测 σ 2.57%→3.19~3.38%）× "
    "设置杠杆（neutralization，S4-B 实测 σ 2.57%→5.14~5.66%，Margin 9.5bp→51~74bp）。"
    "②S4-B 的 OFAT 归因已证明 decay∈{0,4,8,16}、nan、truncation 三个维度对 σ 几乎无影响"
    "（σ 恒在 2.52~2.59%），**唯一的真设置变量是 neutralization**；"
    "本批据此把 MARKET/INDUSTRY/STATISTICAL 三档直接写进 settings_probe 做受控对照。"
    "③目标坐标：Fit = Sh^1.5 × √(8σ)（TO<12.5% 时）。Sh=1.58 需 σ≥3.17%（MARKET 档已超额达成）；"
    "Sh=1.30 需 σ≥5.69%（MARKET 档 5.66% 恰在边界）。"
    "⇒ 本批真正的问题是：**能否用 MARKET 档的 σ 换取 Sharpe 回到 1.30~1.58**。"
    "④D01/D02 配对隔离 neutralization；D03/D04 把单腿 power3 在三个 neutralization 档下对照；"
    "D05/D06/D07/D08 为窗口、指数、第二腿、decay 的表征维度。"
    "⑤全部零均值顶层、≤3 字段、纯 fundamental17、零 PV 污染、只做回测不提交。"
)


def main():
    meta = P.load_meta()
    items = []
    for i, (sid, expr, sp) in enumerate(EXPRS, 1):
        r = P.preflight(expr, "x", "y", meta, meta, phase0=False, op_cap_override=11)
        if not r["ok"]:
            print(f"❌ slot{i} {sid}: {r['issues']}")
            return
        fids = P.field_ids(expr)
        acs = [meta[f]["alphaCount"] for f in fids]
        items.append({
            "slot": i, "expression": expr, "q": "SIGMA_STACK",
            "seed_id": sid, "fields": fids,
            "mechanism": MECH, "counterparty": CP, "optimize_reason": REASON,
            "treatment_tag": "sigma_stack",
            "sum_alphaCount": sum(acs), "field_acs": acs,
            "field_covs": [meta[f]["coverage"] for f in fids],
            "operator_count": r["checks"]["operator_count"],
            "top_profile": r["checks"]["top_level_profile"],
            "settings_probe": sp,
            "preflight_ok": True,
        })

    batch = {
        "batch_name": "aegis_fnd17_S4D_SIGMA_STACK", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_S4D_sigma_stack", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL",
                     "decay": 8, "truncation": 0.08, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "σ 杠杆正交叠加：power 锐化 × neutralization 档",
            "step1_funnel": "诊断批次，不剪枝；全 8 条回测留档。",
            "readout": "σ = Ret/Sharpe；目标 Sh≥1.30 且 σ≥5.0% ⇒ Fit≥1.0 且 Margin≥10bp",
        },
        "preregistered_notes": [
            "结构杠杆 × 设置杠杆的受控叠加；每槽 neutralization 写在 settings_probe 内。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4D.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {out}  ({len(items)} 槽)")
    for it in items:
        sp = it["settings_probe"]
        print(f"  slot{it['slot']} {it['seed_id']:<24} ops={it['operator_count']:<3} "
              f"zm={it['top_profile']['zero_mean']} {sp['neutralization']:<11} d={sp['decay']:<3} "
              f"{it['expression'][:78]}")


if __name__ == "__main__":
    main()
