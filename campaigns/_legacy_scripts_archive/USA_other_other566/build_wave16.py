"""
build_wave16.py — wave 16: close the last gap with a compound-lever sweep.

THE FRONTIER AFTER WAVE 15 (decay=0 regime, USA/D1/TOP1000, INDUSTRY, trunc=0.08):

  slot                 Sh     Fit    Mgn     TO      2Y    fails
  w15_tvr12_d0        1.00   0.61   7.39    12.5%   1.38  0   <== best Fitness, Step2 PASS
  w15_tvr15_d0_rank   1.01   0.46   4.21    15.8%   1.21  0
  w13_d0_tvr15        1.00   0.55   6.00    15.6%   1.16  0   (ProdCorr 0.6246 PASS, SelfCorr 0.1835 PASS)
  w15_tvr08_d0        0.91   0.51   9.51     8.3%   1.51  0
  w15_tvr05_d0        0.66   0.31  10.39     5.3%   1.23  3   <== first Margin >= 10bps
  w13_d0_plain        1.15   0.27   1.09    89.7%   1.52  4

Production gate: Sh>=1.58, Fit>=1.00, Mgn>=10.0bps, TO in [5%,50%], 0 fails.

READING THE TABLE: tvr target is a single knob and the three metrics move in
OPPOSING directions along it:
    tvr 0.05 -> Sh 0.66, Fit 0.31, Mgn 10.39   (margin passes, sharpe/fitness fail)
    tvr 0.08 -> Sh 0.91, Fit 0.51, Mgn  9.51   (close on both)
    tvr 0.12 -> Sh 1.00, Fit 0.61, Mgn  7.39   (fitness best, margin 2.6bps short)
    tvr 0.15 -> Sh 1.00, Fit 0.55, Mgn  6.00
    tvr 0.20 -> Sh 0.98, Fit 0.46, Mgn  4.48
The Sharpe peak is at tvr 0.12-0.15; the Margin peak is at tvr 0.05. A SINGLE
tvr cannot satisfy both. To break this trade-off we must raise RETURNS at a
GIVEN turnover — the algebra says:
    margin  = returns/turnover*20  => Mgn 10 at TO 12.5% needs returns 6.25%
    fitness = sharpe*sqrt(returns/max(TO,0.125))
             => Fit 1.0 at TO 12.5% needs sharpe >= 1/sqrt(0.0625/0.125) = 1.41
So at TO=12.5% we need returns >= 6.25% AND Sharpe >= 1.41. Currently at
tvr 0.12 we have returns 4.60% and Sharpe 1.00.

THE COMPOUND LEVER NOT YET TRIED: **the confidence leg is the only free variable
left**. `oth566_r20marsi_prob_5` is currently used RAW (its level, a [0,1]
confidence). That makes the alpha's magnitude proportional to confidence, which
does NOT change the RANKING — so it contributes nothing to Sharpe beyond what the
direction leg provides, while still consuming an operator. Two better uses:
  (a) `ts_zscore(prob_5, 60)` — use confidence's own deviation from its history.
      This is a genuine new signal: "the model is more confident than it usually
      is for this stock" is a different proposition from "the model is confident",
      and it varies the alpha's cross-sectional weight in a time-varying way that
      can raise both Sharpe and Margin.
  (b) `group_rank(prob_5, industry)` — pure positive weight (already tested in
      wave 9's grid, but that grid was ts_mean-wrapped and therefore invalid).

WAVE 16 therefore varies the CONFIDENCE LEG (the one untested degree of freedom)
against the tvr target that maximises each metric, plus a couple of
amplitude-preserving outer variants and one third-model replication.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_P3 = "oth566_r20marsi_prob_3"
R_L5 = "oth566_r20marsi_label_5"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"

W16 = {
 "batch": 16, "family": "confidence_leg_variation_on_best_tvr_operating_point",
 "hypothesis": (
   "波次 16: 波次 15 的 tvr 单旋钮扫描显示三个指标沿该旋钮**反向移动** —— tvr=0.05 时 Margin 首次达 "
   "10.39bps 但 Sh 掉到 0.66; tvr=0.12 时 Fitness 达峰 0.61 但 Margin 只有 7.39; 单一旋钮无法同时满足。"
   "代数定位了缺口: 在 TO=12.5% 处要 Mgn>=10 需 returns>=6.25%, 要 Fit>=1.0 需 Sharpe>=1.41, "
   "而当前 tvr=0.12 只有 returns 4.60% / Sharpe 1.00 ⇒ **必须提升收益, 而不是继续拧旋钮**。"
   "唯一还没动过的自由度是**置信腿的用法**: 当前 oth566_r20marsi_prob_5 是以**原始水平**参与乘法的, "
   "这使 alpha 幅度正比于置信度 —— 而这**不改变横截面排序**, 因此对 Sharpe 毫无贡献却占用一个算子。"
   "本波 8 槽位改用置信腿的两种**真正有信息**的用法: (a) ts_zscore(prob,60) = 「模型对该股的信心比其"
   "历史常态高多少」, 这是与「模型有信心」完全不同的命题, 且让权重随时间变化, 有同时提升 Sharpe 与 Margin 的可能; "
   "(b) group_rank(prob, industry) 纯正权重 (波次 9 的网格全部裹了 ts_mean, 结论无效, 需重测)。"
   "槽位覆盖: 置信腿用法 x tvr 最优点 (0.08/0.12/0.15) 的组合, 外加 L3R5 模型的第三模型复制与 "
   "r20marsi_label_5 序数方向的复制, 以检验「置信腿是数据集层面的通用机制」而非单字段偶然。"
 ),
 "items": [
  {"id": "w16_zp_tvr12", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, ts_zscore({R_P5}, 60)), target_tvr=0.12), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "置信腿 (a) x tvr=0.12 (Fitness 峰): 置信度的 60 日历史标准分作为权重。这是本波最核心的假设 —— 若「信心相对自身常态的变化」携带独立信息, 则 Sharpe 与 Margin 可同时上移。"},
  {"id": "w16_zp_tvr08", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, ts_zscore({R_P5}, 60)), target_tvr=0.08), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "置信腿 (a) x tvr=0.08 (Margin 峰附近, Mgn 9.51): 与上一槽配对, 检验 (a) 是否能同时保住高 Margin。"},
  {"id": "w16_zp_tvr15", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, ts_zscore({R_P5}, 60)), target_tvr=0.15), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "置信腿 (a) x tvr=0.15 (Sharpe 峰): 第三个 tvr 点, 三点连线确认趋势。"},
  {"id": "w16_grp_tvr12", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, group_rank({R_P5}, industry)), target_tvr=0.12), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "置信腿 (b) x tvr=0.12: 行业内置信秩作为正权重。波次 9 的同类网格全部裹 ts_mean(26) 已证无效, 此处是干净重测。"},
  {"id": "w16_grp_tvr08", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, group_rank({R_P5}, industry)), target_tvr=0.08), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "置信腿 (b) x tvr=0.08: Margin 侧配对。"},
  {"id": "w16_l3_tvr12", "expr": f"group_zscore(ts_target_tvr_decay(multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry)), target_tvr=0.12), industry)",
   "ops": 5, "fields": [L3R5, L3R5P], "decay": 0,
   "why": "第三模型复制 (Level3 5 日): 把「标准化方向 x 置信权重 x tvr 目标」搬到 L3R5 模型 (32 用户/40 alpha, 但置信腿 1/1)。若它也过 Step 2, 说明该结构是数据集层面的通用机制。"},
  {"id": "w16_lbl_tvr12", "expr": f"group_zscore(ts_target_tvr_decay(multiply(ts_zscore({R_L5}, 60), {R_P5}), target_tvr=0.12), industry)",
   "ops": 5, "fields": [R_L5, R_P5], "decay": 0,
   "why": "序数方向复制: 用 R20MaRsi 的 5 桶序数标签 (标准化后) 替代连续预测, 配原始置信度。若序数方向也能过 Step 2, 说明「信念加权」机制不依赖连续回归输出, 稳健性更强。"},
  {"id": "w16_p3_zp_tvr12", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, ts_zscore({R_P3}, 60)), target_tvr=0.12), industry)",
   "ops": 4, "fields": [R_RET, R_P3], "decay": 0,
   "why": "信念口径稳健性: 把置信腿从 prob_5 (1 用户) 换成 prob_3 (4 用户) 再用历史标准分。若结论对信念口径不敏感, 机制可信; 若敏感, 说明只是在拟合 prob_5 的特定形态。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W16['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W16, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W16['items'])} items)")
