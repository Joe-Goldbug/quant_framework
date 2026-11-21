# -*- coding: utf-8 -*-
"""Stage 4 · S2 换核批次（基于 S1 法医诊断，非网格微调）

═══════════════════════════════════════════════════════════════════════════
S1 法医诊断（batch_S1_audit.json，8/8 全死）
───────────────────────────────────────────────────────────────────────────
  slot | Sh   | Fit | Ret   | Mgn   | 2Y   | FAIL
  -----+------+-----+-------+-------+------+-------------------------------
   1   | 0.06 | 0.01| 0.31% | 0.63bp| 0.44 | LOW_SHARPE/LOW_FITNESS/LOW_2Y/SUB
   2   | 0.17 | 0.05| 1.23% | 1.72bp| 0.51 | +CONCENTRATED_WEIGHT
   3   | 0.01 | 0.00| 0.04% | 0.08bp| 0.29 | LOW_SHARPE/LOW_FITNESS/LOW_2Y
   4   | 0.26 | 0.06| 0.69% | 1.93bp| 0.55 | LOW_SHARPE/LOW_FITNESS/LOW_2Y/SUB
   5   | 0.07 | 0.01| 0.14% | 0.54bp| 0.31 | LOW_SHARPE/LOW_FITNESS/LOW_2Y/SUB
   6   | 0.05 | 0.01| 0.15% | 0.47bp|-0.08 | LOW_SHARPE/LOW_FITNESS/LOW_2Y
   7   | 0.44 | 0.13| 1.08% | 3.44bp| 1.23 | LOW_SHARPE/LOW_FITNESS/LOW_2Y
   8   | 0.40 | 0.18| 2.72% | 4.14bp| 1.06 | LOW_SHARPE/LOW_FITNESS/LOW_2Y/CW

  最高 |Sharpe| = 0.44 ⇒ **PRUNED_AT_STEP1**（预注册漏斗 |Sh|>=1.0，0/8 存活）

★ 病灶定位（三条，均有硬证据，非猜测）：
  (A) **主病灶：一阶变化量（差分）是噪声，不是信号。**
      S1 八槽全部是「本期水平 − 上期水平」的**逐期差分**。基本面字段是**季报/年报驱动**，
      逐期差分把「披露噪声 + 季节性 + 口径切换」当成信息，于是 Sh 全部塌到 0.01~0.44。
      证据对照：本账户 EUR champion 3qVlb3dN（Sh 2.14 / Fit 1.57 / fail=[]）用的是
      **水平量**（FCF/收入、营业利润率）的**行业相对价差**，不是差分。
  (B) **次病灶：subindustry 内生中性化在 USA/TOP1000 上过度削信息。**
      S1 的 4 条 subindustry 槽（slot4/5/7）与 3 条 sector 槽（slot1/2/8）表现无差异，
      但 EUR 侧证据明确：**sector 最优，industry/subindustry 会把 robust 打到 0.35~0.46**。
      ⇒ S2 统一改用 **sector**。
  (C) **第三病灶：raw 比值做 zscore 被极端值主导。**
      slot3 (FCF/资产 zscore) Sh=0.01 —— 现金收益率是重尾分布，少数极端值把 zscore 拉爆。
      ⇒ 改用 **group_rank 先做行业相对化**（天然截尾、天然抗离群）。

★ S2 结构通式（照搬 EUR champion 的骨架，但换成零均值顶层以满足本战役契约）：
      subtract(group_rank(<现金/盈利水平量>, sector), group_rank(<账面盈利量>, sector))
    外层 subtract ⇒ 差值零均值（不是 [0,1] 单边）⇒ 满足「最外层零均值」铁律，
    同时保留 group_rank 的抗离群 + 行业相对化双重优点。

  本战役 **禁止裸 group_rank 在最外层**（单边 ⇒ Ret/Margin 是 Beta 幻觉），
  故 EUR champion 原式若直接照抄在 USA 不可信；本 S2 用 **subtract 两个 group_rank**
  或 **zscore(group_rank(...))** 两种零均值封装。
═══════════════════════════════════════════════════════════════════════════
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

# ---------------------------------------------------------------- S2 八槽
SLOTS = [
    # ---------- 骨架族 1：EUR champion 直系移植（现金收益率 vs 账面利润率 价差）----------
    (
        "Q3_Anomaly",
        "subtract(group_rank(divide(fnd17_fcfmtt, fnd17_arev), sector), group_rank(fnd17_ttmopmgn, sector))",
        ["fnd17_fcfmtt", "fnd17_arev", "fnd17_ttmopmgn"],
        "现金收益率与账面营业利润率的行业相对价差：现金创造相对盈利叙事的偏离度",
        "按账面利润率高低给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金",
        "①**这正是 EUR/D1 通关冠军 3qVlb3dN 的骨架直系移植**：该 alpha 在 EUR/TOPCS1600 上 "
        "Sharpe 2.14 / Fitness 1.57 / checks.fail 为空 / selfCorr 0.32 / prodCorr 0.64，"
        "是本账户 fundamental17 家族唯一的硬证据。②针对 S1 病灶(A)(C)：S1 全批用逐期差分，"
        "把季报披露噪声当信息，导致 Sh 塌到 0.01~0.44；本槽改用**水平量**的**行业相对价差** —— "
        "divide 得到现金收益率（无��纲），group_rank 做行业内相对化（天然截尾、抗极端值，"
        "直接修复 S1 slot3 的 Sh=0.01），再与账面营业利润率做 subtract，"
        "衡量的是「现金创造相对盈利叙事」的偏离：现金收益率显著高于同行业利润率水平者，"
        "是盈利质量被低估的标的。③外层 subtract 的两个 group_rank 之差**天然零均值**"
        "（不是 [0,1] 单边），满足本战役「最外层必须零均值」铁律，同时保留 group_rank 的抗离群性；"
        "三字段均无外部量价，零 PV 污染。",
        "none",
    ),
    (
        "Q3_Anomaly_B",
        "zscore(group_rank(divide(fnd17_fcfmtt, fnd17_arev), sector))",
        ["fnd17_fcfmtt", "fnd17_arev"],
        "自由现金流对收入的行业相对水平：行业内现金转化效率的排序",
        "以收入和账面利润为唯一依据筛选公司、把会计利润直接等同现金流的成长风格配置资金",
        "①针对 S1 病灶(C)：S1 slot3 用 `zscore(divide(FCF,资产))` 得到 Sh=0.01 —— 现金收益率"
        "重尾，极少数极端值主导了截面 zscore。本槽把标准化**前置到 group_rank**："
        "group_rank 是分位映射，天然把重尾压成均匀分布，任何单点异常都无法主导信号；"
        "再外包一层 zscore 恢复零均值（group_rank 本身输出 [0,1] 单边，违反铁律）。"
        "②字段选择沿用 EUR 已验证的 FCF/收入 分母（EUR 社区口径 Sharpe 2.29 为该族最高），"
        "而非 S1 用的 FCF/资产（EUR 口径下 Sharpe 2.23 略低，且资产口径受规模干扰更大）；"
        "arev（收入，年度、cov 0.937、ac=2）比 atmtt（资产，TTM）更稳定地反映经营规模。"
        "③结构上零均值、无 multiply、无裸 group_rank 顶层；两字段量纲相除后无量纲，"
        "不涉及任何单位不一致风险；零 PV 污染。",
        "none",
    ),
    # ---------- 骨架族 2：盈利质量 spread（ROA vs 利润率） ----------
    (
        "Q4_Interaction",
        "subtract(group_rank(fnd17_tcpaormtt, sector), group_rank(fnd17_ttmopmgn, sector))",
        ["fnd17_tcpaormtt", "fnd17_ttmopmgn"],
        "资产回报率与营业利润率在行业内的相对差：杠杆与经营效率的错配",
        "只用单一盈利比率给公司排名、从不比较资产效率与经营效率差异的风格轮动资金",
        "①针对 S1 病灶(A)：S1 slot4 用 `add(group_zscore(ROA), group_zscore(ROI))` 得到 Sh=0.26，"
        "本质是**两个同类盈利比率的冗余相加**——ROA 与 ROI 在会计上高度共线，相加不产生新信息，"
        "只是在重复同一个因子。本槽改为**价差而非加总**：ROA = 净利/资产，营业利润率 = 营业利润/收入，"
        "两者的缺口来自**资产周转率**（杜邦分解：ROE = 净利率 × 资产周转率 × 权益乘数）。"
        "ROA 相对行业偏高而营业利润率相对行业偏低 ⇒ 高周转、低毛利的商业模式（零售/分销），"
        "市场却因为利润率低而给它低估值 —— 这是**真实且可交易的认知错配**。"
        "②group_rank(sector) 做行业内相对化后取差，既抗离群又剥离行业 Beta；"
        "两个字段 alphaCount 分别为 4 与 3，拥挤度中等但骨架全新（fnd17/USA/TOP1000 指纹库命中 0）。"
        "③外层 subtract 两 group_rank 之差天然零均值，不产生 [0,1] 单边幻觉；"
        "两腿同为百分比口径（unbounded 实为百分数），量纲可比；无 multiply，无 PV 污染。",
        "none",
    ),
    (
        "Q1_Invariance",
        "subtract(group_rank(fnd17_tcpaormtt, sector), group_rank(fnd17_aroa5yavg, sector))",
        ["fnd17_tcpaormtt", "fnd17_aroa5yavg"],
        "当期资产回报率相对公司自身五年中枢的行业内位置：盈利中枢的漂移",
        "以五年历史盈利中枢作为估值锚、按盈利水平稳定性筛选持仓的价值锚定资金",
        "①针对 S1 病灶(A)：S1 slot1 用 `zscore(TCMROA − 五年均值ROA)` 得到 Sh=0.06 —— "
        "**逐期差分直接相减两个不同尺度的水平**（当期百分数 vs 五年平均百分数）"
        "在截面上被公司规模与行业结构淹没，差值噪声远大于信号。本槽不直接相减，"
        "而是**各自在行业内做分位排名后再取差**：这样测的是「当前盈利水平在同业中排第几」"
        "减去「历史中枢在同业中排第几」，尺度问题被消除，剩下的才是真正的中枢漂移。"
        "②aroa5yavg 是数据集自带五年均值口径（ac=0，天然零拥挤），cov 0.78；"
        "tcpaormtt（ac=4）cov 0.907；两者皆为百分比，量纲完全可比。"
        "③外层 subtract 零均值，不违反最外层铁律；无 multiply、无裸 group_rank 顶层；"
        "两字段均无外部量价污染。",
        "none",
    ),
    # ---------- 骨架族 3：应计质量 / 增长含金量（改水平差 → 行业相对差） ----------
    (
        "Q6_Accumulation",
        "subtract(group_rank(fnd17_cftrendgr, sector), group_rank(fnd17_revtrendgr, sector))",
        ["fnd17_cftrendgr", "fnd17_revtrendgr"],
        "现金流复合增速与收入复合增速的行业相对差：增长的现金含金量",
        "只按收入复合增速排序成长股、把会计利润增长直接等同价值创造的趋势型成长配置资金",
        "①针对 S1 病灶(A)：S1 slot6 用 `zscore(ts_mean(winsorize(cftrendgr − revtrendgr, 3), 60))` "
        "得到 Sh=0.05 —— 同样是**逐期口径的直接差分**外加时间平滑，噪声被抹平但信号也一起被抹掉。"
        "本槽保留 S1 的核心经济假设（增长含金量 = 现金流增速 vs 收入增速），"
        "但**改变数学承载方式**：各自在行业内做分位排名再取差，而不是对差值做时间平滑。"
        "②这样做的物理理由：cftrendgr 的 cov 仅 0.61（极稀疏）、revtrendgr 的 cov 0.78，"
        "两者的**缺失模式不同** ⇒ 逐期差值在缺失处产生系统性偏差（NaN 传播偏置），"
        "而分位排名在各自的有效样本内计算，缺失只影响该公司的排名位置，不污染其他公司的差值；"
        "这正是 S1 slot6 的 Sh=0.05 与本槽结构的分野。group_rank 同时提供抗离群（五年 CAGR 重尾）。"
        "③外层 subtract 两 group_rank 之差天然零均值；两腿同为 [-1,1] 复合增速百分比，量纲一致；"
        "无 multiply，无 PV 污染。",
        "none",
    ),
    (
        "Q2_Dynamics",
        "subtract(group_rank(fnd17_ghcspemtt, sector), group_rank(fnd17_ttmnichg, sector))",
        ["fnd17_ghcspemtt", "fnd17_ttmnichg"],
        "每股盈利增速与净利润增速在行业内的相对差：股本层面的价值创造或稀释",
        "按净利润增速选股、完全不区分股本变化与经营变化的价值风格资金",
        "①针对 S1 病灶(A)：S1 slot2 用 `zscore(ts_mean(EPS增速 − 净利增速, 20))` 得到 Sh=0.17 —— "
        "同样是逐期差分 + 时间平滑。EPS 增速与净利润增速各自已是**同比变化率**（本身就是一阶差分），"
        "再对它们做差并平滑，等于对噪声做二阶差分，信息被彻底摧毁。本槽改为**行业内分位排名之差**："
        "两个同比增速分别与全市场/全行业比较后取差，衡量「这家公司的每股口径相对其利润口径有多突出」，"
        "这在会计上等价于股本收缩（回购）或稀释的方向。②两字段 alphaCount 均为 0（零拥挤），"
        "cov 均 0.906，更新频率一致（TTM 口径），缺失模式相同 ⇒ 差值无缺失偏置；"
        "group_rank 进一步消除重尾。③外层 subtract 天然零均值；两腿同为 [-1,1] 同比百分比，量纲一致；"
        "无 multiply、无 PV 污染；与 slot3 的骨架和字段均不重叠。",
        "none",
    ),
    # ---------- 骨架族 4：信用质量 / 财务健康（行业相对水平，非差分） ----------
    (
        "Q7_Relative",
        "subtract(group_rank(fnd17_ttmintcov, sector), group_rank(fnd17_qe2dtlq, sector))",
        ["fnd17_ttmintcov", "fnd17_qe2dtlq"],
        "利息保障能力与长期负债权益比在行业内的相对差：偿债安全边际",
        "以固定历史信用评分与静态杠杆阈值为准入标准、忽略偿债能力行业内差异的高收益信用配置资金",
        "①针对 S1 病灶(A)(B)：S1 slot7 用 `group_zscore(ts_backfill(覆盖倍数 − 上期覆盖倍数,120), subindustry)` "
        "得到 Sh=0.44 —— 是全批最好的一条，但仍远低于漏斗线；且它同时踩了「逐期差分」与「subindustry 过度中性化」"
        "两个坑。本槽改用**两个独立财务健康水平量的行业内价差**："
        "利息保障倍数（偿债能力）减去长期负债权益比（杠杆水平），两者都是「越高越健康」的同向指标，"
        "取相对排名之差后，衡量的是**在同业中「偿债能力强但杠杆不激进」的公司** —— "
        "这是信用质量中市场最少定价的维度（通常只看杠杆或只看覆盖）。"
        "②改用 sector 而非 subindustry，依据是 EUR 侧已验证的 in-expression 中性化强度排序"
        "（sector 最优；industry/subindustry 会把 robust 打到 0.35~0.46），"
        "与病灶(B)一致；两字段 ac 分别为 1 与 1，拥挤度低；"
        "qe2dtlq 的 cov 0.898 高于 ttmintcov 的 0.649，**两腿缺失率差异显著**，"
        "故取行业内排名（各自有效样本内）而非直接差值。③外层 subtract 天然零均值；"
        "两腿同为财务比率无量纲，量纲一致；无 multiply、无 PV 污染。",
        "none",
    ),
    (
        "Q5_Structure",
        "subtract(group_rank(fnd17_ttmopmgn, sector), group_rank(fnd17_grosmgn5yr, sector))",
        ["fnd17_ttmopmgn", "fnd17_grosmgn5yr"],
        "当期营业利润率与公司自身五年毛利中枢的行业相对差：经营效率的漂移",
        "以公司自身历史利润率中枢为锚做估值、忽略中枢漂移方向的均值回归型价值资金",
        "①针对 S1 病灶(A)：S1 slot5 用 `group_zscore(ts_backfill(派息率 − 上期派息率,120), subindustry)` "
        "得到 Sh=0.07 —— 逐期差分 + subindustry 双重踩坑（派息率 cov 仅 0.635，稀疏令差分噪声更重）。"
        "本槽放弃派息率（政策变量、离散跳变、天然低频），改用**盈利能力中枢漂移**："
        "当期营业利润率 vs 公司自身五年毛利率中枢，各自行业内排名后取差，"
        "刻画「这家公司的经营效率相对自己的历史中枢在改善还是在退化」。"
        "②tcmopmgn（TTM 营业利润率，ac=3，cov 0.899）与 grosmgn5yr（五年毛利率均值，ac=0，cov 见 dossier）"
        "都是数据集自带口径，一期为当期、一期为自身长期中枢，**天然的二阶预期差结构**；"
        "两个字段 alphaCount 极低（3 与 0），零拥挤；group_rank 提供行业相对化与抗重尾。"
        "③外层 subtract 两 group_rank 之差天然零均值；两腿同为百分比（[-1,1]），量纲一致；"
        "无 multiply、无裸 group_rank 顶层、无 PV 污染；与 slot1/slot3 骨架不重复。",
        "none",
    ),
]


def main():
    meta = P.load_meta()

    items = []
    for i, (q, expr, fields, mech, cp, reason, tag) in enumerate(SLOTS, 1):
        r = P.preflight(expr, reason, cp, meta, meta, phase0=True)
        if not r["ok"]:
            print(f"❌ slot{i} 预检未过: {r['issues']}")
            return
        acs = [meta[f]["alphaCount"] for f in P.field_ids(expr)]
        covs = [meta[f]["coverage"] for f in P.field_ids(expr)]
        items.append({
            "slot": i, "expression": expr, "q": q,
            "seed_id": f"S2_{q.split('_')[0]}_{i:02d}",
            "fields": P.field_ids(expr),
            "mechanism": mech, "counterparty": cp, "optimize_reason": reason,
            "treatment_tag": tag,
            "sum_alphaCount": sum(acs), "field_acs": acs, "field_covs": covs,
            "operator_count": r["checks"]["operator_count"],
            "preflight_ok": True,
        })

    exprs = [it["expression"] for it in items]
    sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
    print(f"骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    if sk["violations"]:
        for v in sk["violations"]:
            print("  ❌", v)
        return
    for it, s in zip(items, sk["skeletons"]):
        it["skeleton"] = s
        it["skeleton_history"] = sk["history"].get(s, 0)

    from quant_framework.core.red_team import DoubleBlindRedTeam
    rd = DoubleBlindRedTeam.sign_batch_verdicts(
        [{"expression": it["expression"], "counterparty": it["counterparty"],
          "optimize_reason": it["optimize_reason"]} for it in items],
        meta, os.path.join(HERE, "red_team_verdict_S2.json"))
    for i, it in enumerate(items):
        it["red_team_verdict"] = rd["verdicts"][i]["verdict"]
    print(f"红队通行证: all_passed={rd['all_passed']}")

    batch = {
        "batch_name": "aegis_fnd17_S2", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_refinement_S2", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL", "decay": 8,
                     "truncation": 0.08, "pasteurization": "ON", "unit_handling": "VERIFY",
                     "nan_handling": "ON", "max_trade": "OFF", "language": "FASTEXPR",
                     "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "USA/D1/FUNDAMENTAL 金字塔点亮: Sh>=1.58 且 Fit>=1.0 且 margin>=10bps 且 TO∈[1%,70%]",
            "step1_funnel": "|Sharpe|>=1.0 且正收益年份>=8/10, 否则整批 PRUNED_AT_STEP1 并切换主信号",
        },
        "step1_funnel": "|Sharpe| >= 1.0 and profitable_years >= 8/10 else PRUNED_AT_STEP1",
        "preregistered_notes": [
            "S2 换核批次，源自 S1 法医诊断（非网格微调）。",
            "病灶 A：一阶逐期差分 = 噪声（S1 八槽全用，Sh 0.01~0.44 全灭）→ S2 改用水平量的行业内相对价差。",
            "病灶 B：subindustry 过度中性化 → S2 统一 sector（EUR 侧已验证 sector > industry > subindustry）。",
            "病灶 C：raw 比值 zscore 被重尾极端值主导（slot3 Sh=0.01）→ 改 group_rank 前置抗离群。",
            "外层 subtract(group_rank, group_rank) 天然零均值，满足最外层零均值铁律。",
        ],
    }
    out = os.path.join(HERE, "batch_S2.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {out}")
    for it in items:
        print(f"  slot{it['slot']} {it['q']:<16} ac_sum={it['sum_alphaCount']:<3} "
              f"ops={it['operator_count']} {it['expression'][:96]}")


if __name__ == "__main__":
    main()
