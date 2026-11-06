"""
build_wave22.py — wave 22: the signed_power book-shape lever (the last untried lever).

DISCOVERY THAT MOTIVATES THIS WAVE
----------------------------------
While listing the account's recent alphas (to check wave 21's progress) a SIBLING
campaign's alphas were visible with a striking profile:

    gJeZ1G5l  signed_power(subtract(group_rank(<core>), 0.5), 2.25)
              Sh 1.19  Fit 0.72  TO 6.45%  Mgn 14.09 bps   <- MARGIN 14bps!
    xArbRWQg  signed_power(subtract(group_rank(<core>), 0.5), 2.25)
              Sh 1.17  Fit 0.69  TO 7.01%  Mgn 12.57 bps
    P0ognabL  same shape, trunc 0.01
              Sh 1.11  Fit 0.64  TO 7.59%  Mgn 11.02 bps

Those alphas are NOT from this campaign (they use ai_news_scores + insider_feats
fields), but they expose the ONE book-shape construction this campaign never
tried: **signed_power on a CENTERED rank**.

Why it works, mechanically:
  group_rank(x) maps to [0,1] with 0.5 = the cross-sectional median. Subtracting
  0.5 centres it; signed_power(v, p) with p>1 then AMPLIFIES the magnitude of
  deviations from the median while preserving sign. The resulting weight profile
  is: tiny positions for the (uninformative) middle of the book, large positions
  for the tails. Since the middle of a forecast distribution is where the
  forecast says "nothing happens" — trading it is pure cost — this raises
  PnL per unit of turnover, which is EXACTLY margin_bps = returns/turnover*20.

This is a different path from `quantile(..., "gaussian")` (wave 21): quantile
reshapes the RANK into a distribution, signed_power sharpens the AMPLITUDE of a
centred rank. Wave 21's quantile results showed the ret2 leg's R/TO improving
to 0.43 (Mgn 8.61 bps at TO 12.55%) — so the amplitude-shaping hypothesis is
supported; signed_power is the stronger form of the same lever.

THE TARGET CELL (restated from the arithmetic):
    Mgn >= 10  <=>  returns/turnover >= 0.50
    Fit >= 1.0 with Mgn >= 10  =>  Sharpe >= 1.414 (necessarily)
    At turnover T: returns >= 0.5*T and Sharpe >= 1.58 at T=10%.
The sibling alphas show Margin 14bps is achievable at TO 6.5-7.6% — i.e. the
returns-per-turnover CAN be roughly doubled. Wave 22 therefore combines
signed_power book shape with this campaign's best legs and the tvr ladder.

All slots: 2 fields, <= 6 operators, and a stated economic hypothesis.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_P3 = "oth566_r20marsi_prob_3"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"

STAT = "STATISTICAL"
IND = "INDUSTRY"
CORE = f"multiply({R_RET}, {R_P5})"
RET2_CORE = f"multiply({RET2}, group_rank({PROB_2}, industry))"
L3_CORE = f"multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry))"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


def sp(sid, inner_core, tvr, p, neutralization, note, ops, fields):
    """signed_power(subtract(group_rank(<smoothed core>), 0.5), p)"""
    return slot(sid,
                f"signed_power(subtract(group_rank(ts_target_tvr_decay({inner_core}, target_tvr={tvr}), subindustry), 0.5), {p})",
                ops, fields, note, neutralization=neutralization)


W22 = {
 "batch": 22, "family": "signed_power_centered_rank_book_shape",
 "hypothesis": (
   "波次 22: 使用**本战役从未试过的账本形状杠杆** —— 对**中心化秩**做 signed_power。同事战役的 alpha 显示 "
   "signed_power(subtract(group_rank(<核>), 0.5), 2.25) 可达 **Margin 14.09bps** (TO 6.45%, Fit 0.72) —— "
   "那是全平台可见的、把单位换手收益翻倍的结构。机理: group_rank 映射到 [0,1], 0.5 即横截面中位数; "
   "减去 0.5 中心化后, signed_power(v, p>1) **放大偏离中位数的幅度并保留符号** ⇒ 权重剖面变成"
   "「中间区域仓位极小、两端仓位大」。预测分布的中间区域正是「模型说没发生什么」的地方, 在那里交易纯属成本, "
   "故 PnL/交易上升 ⇒ margin_bps = returns/turnover*20 上升。这与波次 21 的 quantile(gaussian) 是同一假设"
   "(尾部集中) 的更强形式: quantile 重排秩的分布, signed_power 锐化中心化秩的幅度。"
   "本波 8 槽位把该形状套到本战役三条已验证的腿上 (r20marsi 连续腿 / 2 日期腿 / L3 订单簿腿), "
   "并在 tvr 0.08~0.15 区间扫描, 目标是把 R/TO 从当前的 ~0.43 推到 0.50 以上, 同时守住 Sharpe >= 1.414 "
   "(Mgn>=10 与 Fit>=1.0 联立的必要条件)。"
 ),
 "items": [
  sp("w22_sp_core_t08_p225", CORE, 0.08, 2.25, IND,
     "r20marsi 核 x tvr=0.08 x p=2.25: 目标 R/TO >= 0.50 (Mgn>=10) 且 Sh>=1.58 (T=10% 处的必要条件)。"
     "用 INDUSTRY (r20marsi 腿在 INDUSTRY 下收益未被削)。", 5, [R_RET, R_P5]),
  sp("w22_sp_core_t10_p225", CORE, 0.10, 2.25, IND,
     "r20marsi 核 x tvr=0.10 x p=2.25: 换手略高一点换取 Sharpe, 与上一槽配对定位最优点。", 5, [R_RET, R_P5]),
  sp("w22_sp_core_t12_p225", CORE, 0.12, 2.25, STAT,
     "r20marsi 核 x tvr=0.12 x p=2.25 @ STATISTICAL: 该腿在 STATISTICAL 下 Sharpe 最高 (1.27), 检验"
     "「高 Sharpe 底座 + 幅度锐化」能否同时达标。", 5, [R_RET, R_P5]),
  sp("w22_sp_core_t10_p3", CORE, 0.10, 3.0, IND,
     "r20marsi 核 x tvr=0.10 x p=3.0: 更强的尾部集中。经济含义: 只在模型最有把握的两端建仓, "
     "中间区域完全不交易 ⇒ 换手与成本进一步下降。", 5, [R_RET, R_P5]),
  sp("w22_sp_ret2_t12_p225", RET2_CORE, 0.12, 2.25, IND,
     "2 日期腿 x tvr=0.12 x p=2.25 @ INDUSTRY: 该腿 R/TO 最高 (波次 21 的 quantile 版已达 Mgn 8.61), "
     "signed_power 应能把它推过 10bps。", 6, [RET2, PROB_2]),
  sp("w22_sp_ret2_t10_p225", RET2_CORE, 0.10, 2.25, IND,
     "2 日期腿 x tvr=0.10 x p=2.25: 更低换手的工作点, 检验 R/TO 是否继续上升。", 6, [RET2, PROB_2]),
  sp("w22_sp_l3_t12_p225", L3_CORE, 0.12, 2.25, STAT,
     "L3 订单簿腿 x tvr=0.12 x p=2.25: 该腿绝对收益最高 (R 6.22%), 若 R/TO 也高则最可能过 Mgn 线。", 7, [L3R5, L3R5P]),
  slot("w22_sp_p3_core_dexp20",
       f"signed_power(subtract(group_rank(ts_decay_exp_window({CORE}, 20, factor=0.7), subindustry), 0.5), 3.0)",
       5, [R_RET, R_P5],
       "高 Sharpe 底座 + 幅度锐化: 58Egq5l1 (dexp20 @STATISTICAL) 是全战役平台门 0-FAIL 的最高 Sharpe (1.63 / 2Y 2.43), "
       "但 Mgn 仅 1.12。若 signed_power 能把它的 R/TO 抬到 0.5 (即 R 需从 3.83% 升到 ~34% —— 极难), "
       "至少可测出该底座上幅度锐化的边际效应; 若 R 升到 6-8% 则 Mgn 可达 2-3bps, 仍是全战役最高。",
       neutralization=STAT),
 ]}

# The L3 slot would need 7 operators with group_rank(prob); drop the prob rank and
# use the raw confidence instead (2 fields, 6 operators).
W22["items"][6]["expr"] = (
    f"signed_power(subtract(group_rank(ts_target_tvr_decay(multiply(ts_zscore({L3R5}, 60), "
    f"{L3R5P}), target_tvr=0.12), subindustry), 0.5), 2.25)"
)
W22["items"][6]["ops"] = 6

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W22['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W22, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W22['items'])} items)")
