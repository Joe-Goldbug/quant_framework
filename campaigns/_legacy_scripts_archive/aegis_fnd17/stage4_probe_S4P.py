# -*- coding: utf-8 -*-
"""S4P 诊断探针：2×2×2 析因 —— 结构归一化方式 × 设置档

═══════════════════════════════════════════════════════════════════════════
为什么做这个探针（全部有硬证据支撑，不是网格微调）
───────────────────────────────────────────────────────────────────────────
★ 事实 1：EUR 冠军骨架在 USA/TOP1000 的表现是 **Sh 1.11 / Ret 2.85% / Mgn 9.59bp**，
  而门禁算术要求 Ret ≈ 5% ⇒ **Ret 差 1.75 倍**，这是第一瓶颈。
★ 事实 2：EUR 冠军骨架用 `group_rank` 做归一化。group_rank 把连续值压成 [0,1] **分位**，
  **幅度信息被彻底丢弃**。在 EUR/TOPCS1600 上现金创造效率的截面幅度足够大，
  分位化仍能排序出 6.76% 的年化；在 USA/TOP1000 上该因子的截面幅度更窄，
  分位化把可挣的幅度削掉了 ⇒ **这正是 Ret 上不去的结构性原因**。
  ⇒ 假设 H1：换成 **保幅度的归一化**（winsorize → zscore，保留相对幅度形状）能抬 Ret。
★ 事实 3：S3 只测了两格设置。实测（同一批 8 条表达式配对）：
      EUR 档   (decay=0 / MARKET / nan=OFF)      Sh 均值 0.59 | TO 2.06% | Ret 3.66% | Mgn 33.3bp
      战役档   (decay=8 / STATISTICAL / nan=ON)  Sh 均值 0.88 | TO 6.02% | Ret 2.25% | Mgn  7.8bp
  ⇒ STATISTICAL 贡献 +0.29 Sh，但 decay8+nanON 把 Ret 砍掉 39% ⇒ Margin 塌到 7.8bp（<10bp 底线）
  ⇒ **第三格 (STATISTICAL / decay=0 / nan=OFF) 从未测过**：若 STAT 的 Sharpe 增益能与
    decay0 的低换手/高 Ret 共存，就是唯一能同时抬 Sharpe 与 Margin 的组合。
  ⇒ 假设 H2：该格优于已测两格。

★ 析因设计（8 次仿真，2×2×2 全交叉，槽位零浪费）
      因子 A（归一化方式）：group_rank（分位，保序不保幅）  vs  winsorize+zscore（保幅）
      因子 B（基础结构）  ：FCF/资产 vs 营业利润率           vs  FCF/收入 vs 营业利润率
      因子 C（设置档）    ：STATISTICAL+decay0+nanOFF        vs  STATISTICAL+decay8+nanON
      ⇒ 8 槽 = 2(A) × 2(B) × 2(C)，可干净分离 H1 / H2 的边际贡献

★ 纪律：只做回测，绝不触碰任何提交接口。诊断批次，不剪枝。
═══════════════════════════════════════════════════════════════════════════
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

# ---- 因子 B：两条基础结构（分子/分母腿 × 第二腿） ----
FCF_ASSET = ("divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_atmtt,250))",
             "ts_backfill(fnd17_ttmopmgn,250)")
FCF_REV = ("divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250))",
           "ts_backfill(fnd17_ttmopmgn,250)")

# ---- 因子 A：两种归一化方式 ----
def make_grp(ratio_leg, leg2):
    """分位归一化（S3 原版，EUR 冠军结构）。"""
    return (f"subtract(group_rank({ratio_leg}, sector), "
            f"multiply(0.5, group_rank({leg2}, sector)))")


def make_amp(ratio_leg, leg2):
    """保幅度归一化：winsorize 切尾保连续 + zscore 标准化保相对幅度形状。

    与 group_rank 的本质差异：
      group_rank → 输出 [0,1] 分位，**幅度信息归零**，只保留次序；
      zscore(winsorize(x)) → 输出以 0 为中心、以截面标准差为单位的连续值，
                              **保留"这家比同业好多少倍"的信息**。
    两腿各自标准化 ⇒ 量纲可比，subtract 后零均值。
    """
    return (f"subtract(zscore(winsorize({ratio_leg}, std=3)), "
            f"multiply(0.5, zscore(winsorize({leg2}, std=3))))")


STRUCTS = {
    "ASSET_GRP": make_grp(*FCF_ASSET),
    "ASSET_AMP": make_amp(*FCF_ASSET),
    "REV_GRP": make_grp(*FCF_REV),
    "REV_AMP": make_amp(*FCF_REV),
}

# ---- 因子 C：两个设置档 ----
TIERS = {
    "STAT_D0": {"neutralization": "STATISTICAL", "decay": 0, "nan_handling": "OFF"},
    "STAT_D8": {"neutralization": "STATISTICAL", "decay": 8, "nan_handling": "ON"},
}

MECH = "现金创造效率与账面盈利口径在行业内的相对错配：现金叙事显著优于盈利叙事的公司随后跑赢"
CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
REASON = (
    "①本批次是**析因诊断探针**，唯一研究问题是两个已定位的杠杆："
    "（H1）归一化方式是否应为保幅度的 winsorize+zscore 而非分位的 group_rank；"
    "（H2）STATISTICAL 中性化搭配 decay=0/nan=OFF 是否优于已测的 EUR 档与战役档。"
    "②H1 的物理依据：EUR 冠军骨架的归一化用 group_rank，把连续值压成 [0,1] 分位，"
    "**幅度信息被彻底丢弃**；USA/TOP1000 移植后年化收益只有 2.85%，"
    "而门禁算术（Margin=20·Ret/TO≥10 且 Fit=Sh·√(Ret/max(TO,0.125))≥1）要求 Ret≈5%，"
    "缺的是幅度而非排序 ⇒ 保幅度归一化应当能挣到 group_rank 挣不到的 Ret。"
    "③H2 的物理依据：S3 配对实测显示 STATISTICAL 带来 +0.29 Sharpe，"
    "但 decay=8 + nan=ON 同时把 Ret 砍掉 39%、Margin 塌到 7.8bp（<10bp 底线）；"
    "fnd17 全史 51 条中 decay=0 档（n=14）均值 Sh 1.29、nan=OFF 档（n=16）均值 Sh 1.37，"
    "均显著优于 decay=8（0.41）与 nan=ON（0.45）⇒ 混合档 STATISTICAL+decay0+nanOFF "
    "是唯一可能同时拿到 STAT 的 Sharpe 与 decay0 的低换手高收益的组合。"
    "④8 槽为 2×2×2 全交叉析因设计（归一化方式 × 基础结构 × 设置档），槽位零浪费，"
    "可干净分离两个假设的边际贡献。"
    "⑤全部字段为 fnd17 纯基本面字段（fcfmtt / atmtt / arev / ttmopmgn），"
    "零外部量价、零内嵌量价字段，无跨数据集污染；外层 subtract 天然零均值，不产生单边幻觉。"
)


def main():
    meta = P.load_meta()

    # ---- 预检四条结构（诊断批次放宽算子数上限到 11，与 S3 同规格）----
    for name, expr in STRUCTS.items():
        r = P.preflight(expr, REASON, CP, meta, meta, phase0=False, op_cap_override=11)
        print(f"  预检 {name:<12} ops={r['checks'].get('operator_count'):>2} "
              f"ok={r['ok']} {'' if r['ok'] else r['issues']}")
        if not r["ok"]:
            print("     ❌ 预检未过，终止")
            return

    # ---- 骨架唯一性（同批 4 条结构，2 条结构 × 2 档设置共用同一表达式）----
    exprs = list(STRUCTS.values())
    sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
    print(f"\n骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    hist_v = [v for v in sk["violations"] if not v.startswith("同骨架")]
    if hist_v:
        for v in hist_v:
            print("  ❌", v)
        return
    dup = [v for v in sk["violations"] if v.startswith("同骨架")]
    print(f"  {'⚠️ 骨架重复: ' + str(dup) if dup else '✅ 4/4 骨架唯一'}")

    # ---- 出包：8 槽（4 结构 × 2 设置档），逐槽 settings_probe 覆盖 ----
    items = []
    slot = 0
    for sname, sexpr in STRUCTS.items():
        for tname, tset in TIERS.items():
            slot += 1
            fs = P.field_ids(sexpr)
            items.append({
                "slot": slot,
                "expression": sexpr,
                "q": "PROVEN_PORT",
                "seed_id": f"S4P_{sname}_{tname}",
                "fields": fs,
                "mechanism": MECH,
                "counterparty": CP,
                "optimize_reason": REASON,
                "treatment_tag": "winsorize_tail" if "AMP" in sname else "group_zscore_neutral",
                "sum_alphaCount": sum(meta[f]["alphaCount"] for f in fs),
                "field_acs": [meta[f]["alphaCount"] for f in fs],
                "field_covs": [meta[f]["coverage"] for f in fs],
                "operator_count": len(P.ast_calls(sexpr)[0]),
                "preflight_ok": True,
                "settings_probe": {
                    "neutralization": tset["neutralization"],
                    "decay": tset["decay"],
                    "nan_handling": tset["nan_handling"],
                    "truncation": 0.08,
                },
                "probe_factors": {"norm": "AMP" if "AMP" in sname else "GRP",
                                  "base": "ASSET" if "ASSET" in sname else "REV",
                                  "tier": tname},
            })

    batch = {
        "batch_name": "aegis_fnd17_S4P_FACTORIAL",
        "dataset": "fundamental17", "region": "USA", "universe": "TOP1000",
        "delay": 1, "category": "fundamental",
        "stage": "Stage4_probe_S4P_factorial", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL",
                     "decay": 0, "truncation": 0.08, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "OFF",
                     "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "2×2×2 析因诊断：归一化方式(group_rank vs winsorize+zscore) × 基础结构 × 设置档",
            "h1": "H1 保幅度归一化抬 Ret（期望 Ret 2.85%→5%+）",
            "h2": "H2 STATISTICAL+decay0+nanOFF 同时拿到高 Sharpe 与高 Margin",
            "step1_funnel": "诊断批次不剪枝；全 8 条回测留档",
        },
        "preregistered_notes": [
            "8 槽 = 4 条结构 × 2 个设置档，全交叉。",
            "严禁调用任何提交接口。",
        ],
    }
    out = os.path.join(HERE, "batch_S4P_FACTORIAL.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {out}  ({len(items)} 槽)")
    for it in items:
        pf = it["probe_factors"]
        print(f"  slot{it['slot']} {it['seed_id']:<26} norm={pf['norm']:<4} base={pf['base']:<6} "
              f"tier={pf['tier']:<8} dec={it['settings_probe']['decay']} "
              f"nan={it['settings_probe']['nan_handling']}")


if __name__ == "__main__":
    main()
