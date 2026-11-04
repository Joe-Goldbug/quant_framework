# -*- coding: utf-8 -*-
"""Stage 4 · S4-B：设置档**单因子**正交消融（8 槽）

═══════════════════════════════════════════════════════════════════════════
为什么做这一批
───────────────────────────────────────────────────────────────────────────
S3 的设置档 A/B **一次动了三个变量**（decay 0→8、neutralization MARKET→STATISTICAL、
nanHandling OFF→ON），因此那组对照无法归因到任何单一维度：

    同结构 FCF/Assets vs 营业利润率
      d0/MKT/nanOFF : Sh 0.85  TO 2.06%  Ret 4.22%  Mgn 41.1bp  σ 4.96%
      d8/STAT/nanON : Sh 1.11  TO 5.95%  Ret 2.85%  Mgn  9.6bp  σ 2.57%

且两条落在同一条等值线上（Fit 0.49 vs 0.53）⇒ 三变量中至少有一个在抬 Sh、另一个在杀 σ。

★ 本批设计：**OFAT（one-factor-at-a-time）**，固定表达式、围绕战役基准档
  (decay=8 / STATISTICAL / nan=ON / trunc=0.08) 各改**一个**维度，
  每槽只相对基准变一个变量 ⇒ 每个维度的边际效应可被单独读出。

★ 纪律：只做回测，绝不触碰任何提交接口。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

# 固定表达式 = S3 最佳结构 QPvLv6V5（仅 backfill 250→120 以对齐窗口白名单，
# 120/252 均为白名单内；窗口本身是 S4-A 批的独立表征维度，不在本批混测）
EXPR = ("subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,120), "
        "ts_backfill(fnd17_atmtt,120)), sector), "
        "multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,120), sector)))")

BASE = {"neutralization": "STATISTICAL", "decay": 8, "nan_handling": "ON", "truncation": 0.08}

# (slot_id, 标签, 覆盖项)
SLOTS = [
    ("B01_BASE", "基准档 d8/STAT/nanON/tr0.08", {}),
    ("B02_DECAY0", "只改 decay→0", {"decay": 0}),
    ("B03_DECAY4", "只改 decay→4", {"decay": 4}),
    ("B04_DECAY16", "只改 decay→16", {"decay": 16}),
    ("B05_NEUT_MKT", "只改 neutralization→MARKET", {"neutralization": "MARKET"}),
    ("B06_NEUT_IND", "只改 neutralization→INDUSTRY", {"neutralization": "INDUSTRY"}),
    ("B07_NAN_OFF", "只改 nanHandling→OFF", {"nan_handling": "OFF"}),
    ("B08_TRUNC15", "只改 truncation→0.15", {"truncation": 0.15}),
]

MECH = "现金创造效率与账面盈利口径在行业内的相对价差（FCF/资产 vs 营业利润率，行业内零均值）"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批**唯一研究问题 = 仿真设置档的边际效应**，表达式 8 槽完全相同 ⇒ 纯设置效应。"
    "S3 的 A/B 一次动了 decay/neutralization/nanHandling 三个维度，无法归因；"
    "且两条实测落在同一条 Fit 等值线上（0.49 vs 0.53），证明至少一个维度在抬 Sh、另一个在杀 σ。"
    "②OFAT 设计围绕战役基准档 (d8/STAT/nanON/tr0.08) 每次只改一个维度："
    "decay∈{0,4,8,16}、neutralization∈{MARKET,STATISTICAL,INDUSTRY}、nan∈{ON,OFF}、trunc∈{0.08,0.15}。"
    "③读数口径：σ_annual = Ret/Sharpe（平台 Ret = Sh×σ）；"
    "判定标准是**找能把 σ 抬到 3.2% 以上且 Sharpe 不塌的档**，"
    "因为 Fit=1.0 门槛在 Sh=1.58 时要求 Ret≥5.0% ⇒ σ≥3.17%。"
    "④truncation 的动机：trunc=0.08 封顶单票权重 8%，"
    "会压制 weight 锐化带来的 σ 增益 ⇒ 需实测 0.15 是否解封。"
    "⑤表达式零均值顶层、3 字段、纯 fundamental17、零 PV 污染。"
)


def main():
    meta = P.load_meta()
    r = P.preflight(EXPR, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
    if not r["ok"]:
        print(f"❌ 表达式预检未过: {r['issues']}")
        return
    fids = P.field_ids(EXPR)
    acs = [meta[f]["alphaCount"] for f in fids]

    items = []
    for i, (sid, label, over) in enumerate(SLOTS, 1):
        st = dict(BASE)
        st.update(over)
        items.append({
            "slot": i, "expression": EXPR, "q": "SETTINGS_OFAT",
            "seed_id": sid, "fields": fids,
            "mechanism": MECH, "counterparty": CP, "optimize_reason": REASON,
            "treatment_tag": "settings_probe",
            "sum_alphaCount": sum(acs), "field_acs": acs,
            "field_covs": [meta[f]["coverage"] for f in fids],
            "operator_count": r["checks"]["operator_count"],
            "probe_label": label,
            "settings_probe": {
                "neutralization": st["neutralization"],
                "decay": st["decay"],
                "truncation": st["truncation"],
                "nan_handling": st["nan_handling"],
            },
            "preflight_ok": True,
        })

    batch = {
        "batch_name": "aegis_fnd17_S4B_SETTINGS_OFAT", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_S4B_settings_ofat", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY",
                     "neutralization": BASE["neutralization"], "decay": BASE["decay"],
                     "truncation": BASE["truncation"], "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": BASE["nan_handling"],
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "设置档 OFAT 归因：找出能把 σ_annual 抬到 ≥3.2% 且 Sharpe 不塌的档",
            "step1_funnel": "诊断批次，不剪枝；全 8 条回测留档。",
            "readout": "σ = Ret/Sharpe；比较每槽相对 B01 的 ΔSharpe / Δσ / ΔMargin",
        },
        "preregistered_notes": [
            "8 槽表达式逐字相同 ⇒ 纯设置效应；每槽相对基准只变一个维度。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4B.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {out}  ({len(items)} 槽)")
    for it in items:
        sp = it["settings_probe"]
        print(f"  slot{it['slot']} {it['seed_id']:<14} d={sp['decay']:<3} "
              f"{sp['neutralization']:<11} nan={sp['nan_handling']:<4} "
              f"tr={sp['truncation']:<5} | {it['probe_label']}")


if __name__ == "__main__":
    main()
