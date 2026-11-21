"""
build_wave23.py — wave 23: the final convergence wave (quantile + signed_power + tvr ladder).

THE FULL FRONTIER AFTER 22 WAVES (176 slots, USA/D1/TOP1000):

  TWO INDEPENDENT AXES, and no single alpha sits on both:
  ------------------------------------------------------------------------------------
  AXIS 1 — HIGH SHARPE (platform gate clean)      AXIS 2 — HIGH RETURNS/TURNOVER
  (Margin gate)                                   (Margin gate)
    w21_q_dexp20   Sh 1.65  Fit 0.40  Mgn  1.20      w15_tvr05_d0  R/TO 0.521 Mgn 10.39
    w19_dexp20     Sh 1.63  Fit 0.39  Mgn  1.12      w12_tvr10     R/TO 0.478 Mgn  9.56
    w19_dexp15     Sh 1.62  Fit 0.41  Mgn  1.26      w21_q_ret2_tvr12  R/TO 0.430 Mgn 8.61
    w21_q_dexp15   Sh 1.62  Fit 0.42  Mgn  1.35      w12_ret2_tvr15    R/TO 0.402 Mgn 8.03
    w18_stat_dexp10 Sh 1.59 Fit 0.43  Mgn  1.43      w13_d8_tvr15   R/TO 0.392 Mgn  7.83
    w20_dexp15_d4  Sh 1.38  Fit 0.43  Mgn  1.92      w15_tvr12_d0  R/TO 0.369 Mgn  7.39
       (TO 53-68%, 2Y Sharpe 2.26-2.45, 0 platform FAIL)   (TO 5-12%, but Sharpe only 0.66-1.00)
  ------------------------------------------------------------------------------------

  WHY THEY ARE DISJOINT, EXACTLY:  margin_bps = returns/turnover*20, and under
  STATISTICAL the returns are essentially CONSTANT (~2.3-4.6%) across every turnover
  level tested. A smoother that lowers turnover therefore lowers margin proportionally,
  and a smoother that preserves Sharpe (the exp-decay family) has to keep turnover
  high. The two ends of the tvr/dexp knob are two different alphas, not a continuum
  we can slide along.

  THE ALGEBRA OF THE TARGET, restated one final time:
      Mgn >= 10  <=>  R/TO >= 0.50
      Fit >= 1.0 & Mgn >= 10  =>  Sharpe >= 1.414   (since Fit = Sh*sqrt(0.5))
      and at turnover T:  R >= 0.5T,  Sh >= 1.58 at T = 10%
  So the only viable cell is T ~ 8-12% with R ~ 4-6% AND Sh >= 1.58.
  The best Sharpe observed AT that turnover is ~1.01 (w21_q_ret2_tvr12_ind at T 12.6%,
  Sh 0.96, R/TO 0.430). We are short roughly 0.6 of Sharpe at the right turnover.

WAVE 23 therefore tries to lift the Sharpe AT the low-turnover operating point using
the one ingredient proven to raise Sharpe at high turnover (the exp-decay family,
Sh 1.59-1.65) but applied to the LOW-turnover leg and at a length that keeps
turnover in the 8-14% band. Specifically:
  * ts_decay_exp_window with SHORT windows (3/5/8) and moderate factors: short
    geometric smoothing barely moves turnover but, unlike ts_mean, does not destroy
    the revision information (the wave-11 finding).
  * the same short exp-decay applied to the 2-day leg (best R/TO) under INDUSTRY.
  * quantile/signed_power book shape on top of the tvr ladder at the low-turnover end
    (wave 21/22 showed both raise R/TO; wave 22's signed_power at TO 9.6% gave
    R/TO 0.41 — close to the 0.50 threshold).
  * the ret2 leg under STATISTICAL with quantile + a shorter exp-decay.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"

STAT = "STATISTICAL"
IND = "INDUSTRY"
CORE = f"multiply({R_RET}, {R_P5})"
RET2_CORE = f"multiply({RET2}, group_rank({PROB_2}, industry))"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


W23 = {
 "batch": 23, "family": "short_exp_decay_at_low_turnover_to_lift_sharpe",
 "hypothesis": (
   "波次 23: 最终收敛波。22 个波次后前沿清晰地裂成两半且互不相交: 高 Sharpe 端 (dexp15/dexp20/quantile-dexp: "
   "Sh 1.59~1.65, 2Y 2.26~2.45, 0 平台 FAIL, 但 TO 53%~68% ⇒ Mgn 仅 1.1~1.4bps); "
   "高收益/换手端 (tvr05/tvr10/ret2: R/TO 0.43~0.52 ⇒ Mgn 8.6~10.4bps, 但 Sh 只有 0.66~1.00)。"
   "原因是代数: 在 STATISTICAL 下 returns 几乎是常数 (~2.3%~4.6%), 所以任何降换手的平滑都同比降 Margin, "
   "而保 Sharpe 的 exp-decay 家族必然高换手。唯一可行格是 T≈8%~12% 且 R≥4%~6% 且 **Sh≥1.58** —— "
   "现有该换手区间最好 Sharpe 仅 ~1.01, 缺口约 0.6。"
   "本波 8 槽位用**短窗几何衰减** (ts_decay_exp_window, window 3/5/8, 中等 factor) 攻击这个缺口: "
   "波次 11 已证明与 ts_mean 的关键区别是**短窗几何平滑不会抹掉修正信息** (ts_mean(26) 杀信号, 而 exp-decay "
   "保 Sharpe 1.62), 短窗 exp-decay 有望在不显著抬高换手的前提下保住高 Sharpe 端的信息优势。"
   "并把已在两侧都验证过的账本形状杠杆 (quantile / signed_power 中心化秩) 套到低换手端。"
 ),
 "items": [
  slot("w23_dexp5_core",
       f"group_zscore(ts_decay_exp_window({CORE}, 5, factor=0.5), industry)",
       3, [R_RET, R_P5],
       "短窗几何衰减 (5, 0.5) @ STATISTICAL: 目标是在 TO 8-14% 区间保住 Sh>=1.5。若成立, 叠加 quantile 即可逼近全格。",
       neutralization=STAT),
  slot("w23_dexp8_core",
       f"group_zscore(ts_decay_exp_window({CORE}, 8, factor=0.5), industry)",
       3, [R_RET, R_P5],
       "短窗几何衰减 (8, 0.5) @ STATISTICAL: 与 5 日档配对做窗口扫描。",
       neutralization=STAT),
  slot("w23_dexp8_core_ind",
       f"group_zscore(ts_decay_exp_window({CORE}, 8, factor=0.5), industry)",
       3, [R_RET, R_P5],
       "短窗 exp-decay (8, 0.5) @ INDUSTRY: 中性化对照 —— r20marsi 腿在两者的偏好不同 (STATISTICAL 抬 Sharpe, INDUSTRY 抬 returns)。",
       neutralization=IND),
  slot("w23_q_dexp8_core",
       f"quantile(ts_decay_exp_window({CORE}, 8, factor=0.5), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "短窗 exp-decay + quantile 账本形状: 波次 21 证明 quantile 抬 Fitness (0.62) 与 R/TO; 叠加短窗平滑检验两者是否可乘。",
       neutralization=STAT),
  slot("w23_sp_dexp8_core",
       f"signed_power(subtract(group_rank(ts_decay_exp_window({CORE}, 8, factor=0.5), subindustry), 0.5), 2.25)",
       5, [R_RET, R_P5],
       "短窗 exp-decay + signed_power 中心化秩: 波次 22 的 signed_power 把 R/TO 推到 0.41 (TO 9.6%), 距 0.50 只差一步。",
       neutralization=IND),
  slot("w23_dexp5_ret2",
       f"group_zscore(ts_decay_exp_window({RET2_CORE}, 5, factor=0.5), industry)",
       4, [RET2, PROB_2],
       "2 日期腿 (R/TO 最高) + 短窗 exp-decay @ INDUSTRY: 该腿是唯一 R/TO 接近 0.5 的结构, 若短窗平滑能把它 Sharpe 抬到 1.4 以上即可全格达标。",
       neutralization=IND),
  slot("w23_q_dexp5_ret2",
       f"quantile(ts_decay_exp_window({RET2_CORE}, 5, factor=0.5), driver=\"gaussian\")",
       4, [RET2, PROB_2],
       "2 日期腿 + 短窗 exp-decay + quantile: 把波次 21 的 R/TO 提升 (0.430) 与波次 19 的 Sharpe 提升 (dexp 家族) 在同一条腿上合并。",
       neutralization=IND),
  slot("w23_q_dexp3_core",
       f"quantile(ts_decay_exp_window({CORE}, 3, factor=0.5), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "最短窗 (3, 0.5) + quantile: 窗口的极端档, 换手应最低 (Mgn 侧), 检验 Sharpe 是否仍能保持。",
       neutralization=IND),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W23['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W23, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W23['items'])} items)")
