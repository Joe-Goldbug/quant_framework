# -*- coding: utf-8 -*-
"""S4Q 设置档全交叉探针：{MARKET, STATISTICAL} × {decay 0, 8} × {nan OFF, ON}

═══════════════════════════════════════════════════════════════════════════
为什么做（全部由 S3/S4P 实测逼出，不是网格微调）
───────────────────────────────────────────────────────────────────────────
★ 缺口 1：S4P 把 decay 与 nanHandling **捆绑**在两档里（D0=decay0/nanOFF, D8=decay8/nanON），
  所以只能得出"组合优劣"，无法归因到单个变量 ⇒ 本探针逐格拆开。
★ 缺口 2：S4P 的副产品显示 **中性化是换手/Margin 的总开关**：
      MARKET+decay0+nanOFF : TO 2.06% / Ret 4.22% / Mgn 41.09bp / Sh 0.85
      STAT  +decay0+nanOFF : TO 6.65% / Ret 2.69% / Mgn  8.08bp / Sh 1.07
      STAT  +decay8+nanON  : TO 5.95% / Ret 2.85% / Mgn  9.59bp / Sh 1.11
  ⇒ MARKET 档把 Fit 门槛从 Sh≥2.09 降到 Sh≥1.72 ⇒ 若能再抬 Sharpe，MARKET 是唯一可行区间。
★ 缺口 3：fnd17 全史 51 条中，decay=0 档（n=14）均值 Sh 1.29、nan=OFF（n=16）1.37，
  均显著优于 decay=8（0.41）、nan=ON（0.45）—— 但那些是**跨区域混杂**的统计，
  且冠军 EUR 的组合恰好是 decay0+nanOFF+MARKET。

★ 设计：2 中性化 × 2 decay × 2 nan = 8 格 × 1 条结构 = 8 槽（单变量全交叉）
  用**已验证最强结构**（GRP/ASSET，Sh 1.11）作载体 ⇒ 纯设置归因，零结构噪声。
  （另加 8 槽做第二条结构 REV ⇒ 16 槽会超单日配额风险，改为只测 ASSET 一条，
    因为 S4P 已证明 ASSET > REV，主效应不必重复测。）

★ 纪律：只回测，不触碰提交接口。诊断批次，不剪枝。
═══════════════════════════════════════════════════════════════════════════
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

STRUCT = ("subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), "
          "ts_backfill(fnd17_atmtt,250)), sector), "
          "multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))")

NEUTS = ("MARKET", "STATISTICAL")
DECAYS = (0, 8)
NANS = ("OFF", "ON")

MECH = "现金创造效率与账面盈利口径在行业内的相对错配：现金叙事显著优于盈利叙事的公司随后跑赢"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批次是**设置档全交叉诊断探针**，唯一研究问题：中性化 × decay × nanHandling 三个维度"
    "各自对 Sharpe / 换手 / 年化收益 / Margin 的边际贡献。"
    "②必要性来自 S4P 的诚实披露：S4P 把 decay 与 nanHandling 捆绑在两档里，"
    "只能得出组合优劣，无法归因到单个变量；本探针把两变量完全正交拆开。"
    "③必要性还来自 S4P 的副产品：**中性化是换手与 Margin 的总开关** —— "
    "MARKET 档（decay0/nanOFF）TO 2.06% / Ret 4.22% / Mgn 41.09bp，"
    "而 STATISTICAL 档（decay8/nanON）TO 5.95% / Ret 2.85% / Mgn 9.59bp；"
    "按门禁算术 Fit=Sh·√(Ret/max(TO,0.125))，MARKET 档的 Fit 门槛是 Sh≥1.72，"
    "STATISTICAL 战役档是 Sh≥2.09 ⇒ 若结构能把 Sharpe 抬到 1.6 以上，"
    "只有 MARKET 档可能同时过 Fit 与 Margin。"
    "④载体结构取已实测最强的 GRP/ASSET（S4P slot2 Sh 1.11 / Ret 2.85% / Mgn 9.59bp / 2Y 1.49），"
    "本批次 8 槽表达式完全相同 ⇒ 指标差异 100% 归因于设置档，零结构噪声。"
    "⑤所有字段为 fnd17 纯基本面字段（fcfmtt / atmtt / ttmopmgn），零外部量价、零内嵌量价字段；"
    "外层 subtract 天然零均值，不产生 [0,1] 单边幻觉。"
)


def main():
    meta = P.load_meta()
    r = P.preflight(STRUCT, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
    if not r["ok"]:
        print("❌ 预检未过:", r["issues"])
        return
    print(f"✅ 载体结构预检通过 ops={r['checks']['operator_count']} "
          f"fields={r['checks']['field_count']}")

    fs = P.field_ids(STRUCT)
    items = []
    slot = 0
    for neut in NEUTS:
        for dec in DECAYS:
            for nan in NANS:
                slot += 1
                items.append({
                    "slot": slot, "expression": STRUCT, "q": "PROVEN_PORT",
                    "seed_id": f"S4Q_{neut[:4]}_d{dec}_n{nan}",
                    "fields": fs, "mechanism": MECH, "counterparty": CP,
                    "optimize_reason": REASON, "treatment_tag": "none",
                    "sum_alphaCount": sum(meta[f]["alphaCount"] for f in fs),
                    "field_acs": [meta[f]["alphaCount"] for f in fs],
                    "field_covs": [meta[f]["coverage"] for f in fs],
                    "operator_count": r["checks"]["operator_count"],
                    "preflight_ok": True,
                    "settings_probe": {"neutralization": neut, "decay": dec,
                                       "nan_handling": nan, "truncation": 0.08},
                    "probe_factors": {"neut": neut, "decay": dec, "nan": nan},
                })

    batch = {
        "batch_name": "aegis_fnd17_S4Q_SETTINGS_CROSS",
        "dataset": "fundamental17", "region": "USA", "universe": "TOP1000",
        "delay": 1, "category": "fundamental",
        "stage": "Stage4_probe_S4Q_settings_cross", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL",
                     "decay": 8, "truncation": 0.08, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "设置档全交叉：{MARKET,STATISTICAL} × {decay0,8} × {nanOFF,ON}",
            "h3": "H3 干净拆开 decay 与 nanHandling 的独立贡献（S4P 捆绑变量）",
            "h4": "H4 找出能同时保住 Sharpe 与低换手/高 Margin 的设置格",
            "step1_funnel": "诊断批次不剪枝；全 8 条回测留档",
        },
        "preregistered_notes": [
            "8 槽表达式完全相同 ⇒ 纯设置归因。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4Q_SETTINGS_CROSS.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {out}  ({len(items)} 槽)")
    for it in items:
        pf = it["probe_factors"]
        print(f"  slot{it['slot']} {it['seed_id']:<24} neut={pf['neut']:<12} "
              f"decay={pf['decay']} nan={pf['nan']}")


if __name__ == "__main__":
    main()
