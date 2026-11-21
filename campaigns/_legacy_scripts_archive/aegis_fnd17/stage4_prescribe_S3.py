# -*- coding: utf-8 -*-
"""Stage 4 · S3 诊断批次 v2：8 条**互不相同**的表达式 × 2 个设置档（配对对照）

═══════════════════════════════════════════════════════════════════════════
为什么要重设计 S3
───────────────────────────────────────────────────────────────────────────
S1（一阶逐期差分）        最高 |Sh| = 0.44 → PRUNED
S2（水平量行业相对价差）  最高 |Sh| = 0.89 → PRUNED（方向对，量级差 0.11）

S2 相对 S1 的改善无法归因：因为 S2 的**表达式结构**和**仿真设置档**同时变了。
本账户唯一通关的 fnd17 alpha（EUR/D1，3qVlb3dN，Sh=2.14/Fit=1.57/fail=[]/已提交OS）
用的设置档是：

    decay=0  neutralization=MARKET  truncation=0.08  nanHandling=OFF

而 S1/S2 固定用：

    decay=8  neutralization=STATISTICAL  truncation=0.08  nanHandling=ON

**三个设置维度全部不同，且从未 A/B 验证过** ⇒ 这是 S2 差 0.11 的最大未测杠杆。

★ v2 设计（比 v1 更干净）：
  v1 = 2 结构 × 4 设置档 = 8 槽（其中 4 槽表达式重复，浪费一半槽位）
  v2 = **8 条互不相同的表达式**，每条在 **2 个设置档**下各跑一次
       ⇒ 2 次 multi 调用 × 8 条 = 16 次仿真，但得到 **8 组严格配对的设置档对照**，
         槽位零浪费，且能对每条结构单独归因设置档的边际贡献。

  Tier 1 = EUR 原档：decay=0 / MARKET / nan=OFF
  Tier 2 = 战役档：  decay=8 / STATISTICAL / nan=ON
  （两档之间只差设置，表达式完全相同 ⇒ 纯设置效应）

★ 八条结构覆盖（全部零均值顶层，骨架互不相同）：
  1  EUR 冠军直系（FCF/Rev vs 营业利润率 ×0.5）
  2  同上但去掉 multiply(0.5,·) ⇒ 两 rank 直接相减
  3  FCF/资产 vs 营业利润率（换分母：资产规模口径）
  4  FCF/Rev vs 五年毛利率中枢（换第二腿：盈利质量基线）
  5  FCF/Rev vs TTM 资产回报率（换第二腿：总资产产出效率）
  6  FCF/Rev 单腿 + 行业相对化（去掉价差腿，纯现金收益率排序）
  7  TTM ROA vs 营业利润率（杜邦口径的效率错配）
  8  FCF/Rev vs 五年净利率中枢（换第二腿：利润率自身长期中枢）

★ 纪律：只做回测，绝不触碰任何提交接口。
═══════════════════════════════════════════════════════════════════════════
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

EXPRS = [
    ("S3_01_EUR_DIRECT",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))"),
    ("S3_02_EUR_NOMULT",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector), "
     "group_rank(ts_backfill(fnd17_ttmopmgn,250), sector))"),
    ("S3_03_FCF_ASSET",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_atmtt,250)), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))"),
    ("S3_04_FCF_VS_GROSS5Y",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_grosmgn5yr,250), sector)))"),
    ("S3_05_FCF_VS_ROA",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_tcpaormtt,250), sector)))"),
    ("S3_06_FCF_ONLY",
     "zscore(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector))"),
    ("S3_07_ROA_VS_OPMGN",
     "subtract(group_rank(ts_backfill(fnd17_tcpaormtt,250), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))"),
    ("S3_08_FCF_VS_MARGIN5Y",
     "subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector), "
     "multiply(0.5, group_rank(ts_backfill(fnd17_margin5yr,250), sector)))"),
]

MECH = "现金创造效率与账面盈利口径在行业内的相对价差：盈利质量相对市场叙事的偏离"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批次全部移植自本账户**唯一通关**的 fundamental17 家族 alpha（EUR/D1，3qVlb3dN，"
    "Sharpe 2.14 / Fitness 1.57 / checks.fail 为空 / selfCorr 0.32 / prodCorr 0.64 / 已提交 OS），"
    "外层 subtract 保证两个 group_rank 之差零均值，不产生 [0,1] 单边幻觉。"
    "②本批次的**唯一研究问题**是仿真设置档：EUR 配方为 decay=0 / MARKET / nanHandling=OFF，"
    "而 S1、S2 两批固定为 decay=8 / STATISTICAL / nanHandling=ON，三项全不同且从未 A/B 验证；"
    "S2 相对 S1 的 Sharpe 改善（0.44→0.89）因此无法区分「结构贡献」与「设置档贡献」。"
    "本批用同一批 8 条表达式在两档设置下各跑一次，形成严格配对对照，把设置效应单独剥离。"
    "③经济机理：divide 得到无量纲现金收益率，group_rank(sector) 做行业内相对化"
    "（分位映射天然抗重尾离群，直接修复 S1 slot3 的 Sh=0.01 病灶），"
    "再减去账面盈利口径的行业排名，衡量「现金创造显著优于同行业盈利叙事」的公司；"
    "第二腿在 8 条中轮换为营业利润率 / 五年毛利率中枢 / 资产回报率 / 五年净利率中枢，"
    "以分离「哪条第二腿的对照最有信息量」；三字段均无外部量价字段，零 PV 污染。"
)

TIERS = {
    "EUR_ORIG": {"neutralization": "MARKET", "decay": 0, "nan_handling": "OFF", "truncation": 0.08},
    "CAMPAIGN": {"neutralization": "STATISTICAL", "decay": 8, "nan_handling": "ON", "truncation": 0.08},
}


def main():
    meta = P.load_meta()

    items = []
    for i, (sid, expr) in enumerate(EXPRS, 1):
        r = P.preflight(expr, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
        if not r["ok"]:
            print(f"❌ slot{i} {sid} 预检未过: {r['issues']}")
            return
        acs = [meta[f]["alphaCount"] for f in P.field_ids(expr)]
        items.append({
            "slot": i, "expression": expr, "q": "PROVEN_PORT",
            "seed_id": sid, "fields": P.field_ids(expr),
            "mechanism": MECH, "counterparty": CP, "optimize_reason": REASON,
            "treatment_tag": "none",
            "sum_alphaCount": sum(acs), "field_acs": acs,
            "field_covs": [meta[f]["coverage"] for f in P.field_ids(expr)],
            "operator_count": r["checks"]["operator_count"],
            "preflight_ok": True,
        })

    exprs = [it["expression"] for it in items]
    sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
    print(f"骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    hist_v = [v for v in sk["violations"] if not v.startswith("同骨架")]
    if hist_v:
        for v in hist_v:
            print("  ❌", v)
        return
    dup = [v for v in sk["violations"] if v.startswith("同骨架")]
    if dup:
        print(f"  ⚠️ 骨架重复: {dup}")
    else:
        print("  ✅ 8/8 骨架唯一，无需诊断豁免")
    for it, s in zip(items, sk["skeletons"]):
        it["skeleton"] = s
        it["skeleton_history"] = sk["history"].get(s, 0)

    # ---- 两个设置档各出一个批次文件 ----
    for tname, tset in TIERS.items():
        batch = {
            "batch_name": f"aegis_fnd17_S3_{tname}", "dataset": "fundamental17",
            "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
            "stage": f"Stage4_diagnostic_S3_{tname}", "date": "2026-10-28",
            "settings": {"instrumentType": "EQUITY",
                         "neutralization": tset["neutralization"], "decay": tset["decay"],
                         "truncation": tset["truncation"], "pasteurization": "ON",
                         "unit_handling": "VERIFY", "nan_handling": tset["nan_handling"],
                         "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
            "slot_count": len(items),
            "known_fields": list(meta.keys()),
            "items": items,
            "preregistered_target": {
                "primary": f"设置档诊断 · {tname}",
                "step1_funnel": "诊断批次，不剪枝；全 8 条回测留档",
            },
            "preregistered_notes": [
                f"本档设置: {tset}",
                "8 条表达式在 EUR_ORIG 与 CAMPAIGN 两档下完全相同 ⇒ 纯设置效应对照。",
                "严禁调用任何提交接口。",
            ],
        }
        out = os.path.join(HERE, f"batch_S3_{tname}.json")
        json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[SAVED] {out}  ({len(items)} 槽, {tset})")

    for it in items:
        print(f"  slot{it['slot']} {it['seed_id']:<20} ops={it['operator_count']} "
              f"ac={it['sum_alphaCount']:<3} {it['expression'][:88]}")


if __name__ == "__main__":
    main()
