# -*- coding: utf-8 -*-
"""Stage 4 · S4-C：σ 锐化的**正确施加位置**（8 槽）

═══════════════════════════════════════════════════════════════════════════
S4-A 的实测结论（USA/TOP1000/d1, STATISTICAL/decay8/trunc0.08/nanON）
───────────────────────────────────────────────────────────────────────────
  基准 S3_03 (QPvLv6V5)  两腿 group_rank 差值 : Sh 1.11  Ret 2.85%  σ 2.57%  Mgn  9.6bp
  P02  单腿 power5        : Sh 0.90  Ret 3.04%  σ 3.38%  Mgn  8.6bp  ← σ +31%
  P06  单腿 power3        : Sh 1.04  Ret 3.32%  σ 3.19%  Mgn  9.9bp  ← SubU 1.02 / 零 FAIL
  P03  两腿**各自**power5 后相减 : Sh 0.30  Ret 1.00%  σ 3.33%  Mgn 2.8bp  ← 信号崩塌

★ 关键规律：两条腿各自锐化 ⇒ 两条腿都变成稀疏尖峰 ⇒ 差值不再保留排序信息
  ⇒ **锐化必须在差值之后施加，不能在两条腿内部施加。**
  （σ 确实抬到了 3.33%，但 Sh 从 1.11 崩到 0.30 —— 是排序信息被摧毁，不是 σ 的问题）

★ 另一条规律：power 指数 3 比 5 好（Sh 1.04 vs 0.90），说明锐化过度会削排序信息。
  但新闻冠军用的是 5 —— 差异来自信号密度。**本批把指数作为表征维度再测一次，
  确认 fnd17 上的最优指数落在哪个位置，并据此固定最终指数（不做网格微调）。**

本批研究问题：power(subtract(legA, legB), k) 这个"差值后锐化"结构能否同时保住 Sh 与 σ？
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402


def leg(x):
    return f"group_rank({x}, sector)"


# 两腿原始素材（backfill 120 与 252 两个白名单窗口）
FCFA_120 = "divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_atmtt,120))"
FCFA_252 = "divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252))"
FCFR_120 = "divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_arev,120))"
OPM_120 = "ts_backfill(fnd17_ttmopmgn,120)"
OPM_252 = "ts_backfill(fnd17_ttmopmgn,252)"

EXPRS = [
    # 1. ★ 差值后锐化（k=3）—— 主假设：保住 Sh、抬 σ
    ("C01_DIFFPOW3_FCFA",
     f"power(subtract({leg(FCFA_120)}, {leg(OPM_120)}), 3)"),
    # 2. 差值后锐化（k=5）
    ("C02_DIFFPOW5_FCFA",
     f"power(subtract({leg(FCFA_120)}, {leg(OPM_120)}), 5)"),
    # 3. 差值后锐化（k=3），带 0.5 权重基线腿
    ("C03_DIFFPOW3_W50_FCFA",
     f"power(subtract({leg(FCFA_120)}, multiply(0.5, {leg(OPM_120)})), 3)"),
    # 4. 差值后锐化（k=3），backfill 252
    ("C04_DIFFPOW3_FCFA_252",
     f"power(subtract({leg(FCFA_252)}, {leg(OPM_252)}), 3)"),
    # 5. 差值后锐化（k=3），换分母 FCF/收入
    ("C05_DIFFPOW3_FCFR",
     f"power(subtract({leg(FCFR_120)}, {leg(OPM_120)}), 3)"),
    # 6. ★ 对照：单腿 power3（复现 S4-A 的 P06，验证批次可复现）
    ("C06_CTRL_SINGLE_POW3",
     f"power(subtract({leg(FCFA_120)}, 0.5), 3)"),
    # 7. 差值后锐化（k=3），换第二腿为五年毛利率中枢（不同对照口径）
    ("C07_DIFFPOW3_VS_GROSS5Y",
     f"power(subtract({leg(FCFA_120)}, {leg('ts_backfill(fnd17_grosmgn5yr,120)')}), 3)"),
    # 8. ★ zscore 包裹 + 差值后锐化（双保险：zscore 再标准化一次，可能进一步抬 σ）
    ("C08_ZSCORE_DIFFPOW3",
     f"zscore(power(subtract({leg(FCFA_120)}, {leg(OPM_120)}), 3))"),
]

MECH = "现金创造效率与账面盈利口径在行业内的相对价差；在**差值之后**施加奇整数幂锐化以抬升年化波动 σ"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①S4-A 实测证明：两条腿**各自** power 后相减会把 Sh 从 1.11 打到 0.30"
    "（σ 确实升到 3.33%，但排序信息被摧毁）；而单腿 power3/5 能把 σ 从 2.57% 抬到 3.19~3.38%、"
    "且 CONCENTRATED_WEIGHT 仍 PASS、SubU 1.02、checks.fail 为空。"
    "⇒ 本批检验「锐化施加在差值之后」这一结构：先做行业内零均值差值（保排序），再锐化（抬 σ）。"
    "②指数 2/3/5 作为**表征维度**出现，用于定位 fnd17 上的响应曲���拐点；"
    "最终种子指数固定为该拐点，不做网格微调（S4-A 已显示指数 5 在单腿上略劣于 3）。"
    "③backfill 120 vs 252、FCF/资产 vs FCF/收入 为第二、第三表征维度。"
    "④C08 额外加一层 zscore：若 power 已把分布拉尖，zscore 可把 σ 归一化到截面标准差 1，"
    "理论上进一步抬 σ 且不改变排序。"
    "⑤全部零均值顶层、≤3 字段、纯 fundamental17、零 PV 污染、只做回测不提交。"
)


def main():
    meta = P.load_meta()
    items = []
    for i, (sid, expr) in enumerate(EXPRS, 1):
        r = P.preflight(expr, "x", "y", meta, meta, phase0=False, op_cap_override=11)
        if not r["ok"]:
            print(f"❌ slot{i} {sid}: {r['issues']}")
            return
        fids = P.field_ids(expr)
        acs = [meta[f]["alphaCount"] for f in fids]
        items.append({
            "slot": i, "expression": expr, "q": "SIGMA_PLACEMENT",
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
    for v in sk["violations"]:
        print("  ⚠️/❌", v)
    for it, s in zip(items, sk["skeletons"]):
        it["skeleton"] = s
        it["skeleton_history"] = sk["history"].get(s, 0)

    batch = {
        "batch_name": "aegis_fnd17_S4C_SIGMA_PLACEMENT", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_S4C_sigma_placement", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL",
                     "decay": 8, "truncation": 0.08, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "σ 锐化施加位置：差值后锐化能否同时保住 Sh 与 σ",
            "step1_funnel": "诊断批次，不剪枝；全 8 条回测留档。",
            "readout": "σ = Ret/Sharpe；目标 σ≥3.17% 且 Sh≥1.58 ⇒ Fit≥1.0",
        },
        "preregistered_notes": [
            "8 槽互不相同；指数/窗口/分母为表征维度，不是夏普网格搜索。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4C.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {out}  ({len(items)} 槽)")
    for it in items:
        print(f"  slot{it['slot']} {it['seed_id']:<24} ops={it['operator_count']:<3} "
              f"zm={it['top_profile']['zero_mean']} ac={it['sum_alphaCount']:<3} "
              f"{it['expression'][:92]}")


if __name__ == "__main__":
    main()
