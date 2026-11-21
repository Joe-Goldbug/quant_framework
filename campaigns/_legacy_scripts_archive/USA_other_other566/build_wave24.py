"""
build_wave24.py — wave 24: the `factor` dimension of ts_decay_exp_window (last untested knob).

WAVE 23 FINDING — WHICH KNOB ACTUALLY CONTROLS TURNOVER:
    w23_dexp5_core   (window 5,  factor 0.5) -> TO 54.2%
    w23_dexp8_core   (window 8,  factor 0.5) -> TO 53.6%
    w23_dexp10_core  (window 10, factor 0.5) -> TO 53.5%   [wave 18, STATISTICAL]
    w12_dexp10       (window 10, factor 0.5) -> TO 31.7%   [wave 12, INDUSTRY]
  => The WINDOW length does NOT control turnover (5/8/10 all land at ~53% under
     STATISTICAL). The `factor` is the decay-rate knob and has never been swept.
     And neutralization moves the whole turnover level (53.5% STATISTICAL vs
     31.7% INDUSTRY at identical settings) — because a neutralization that keeps
     more beta produces a more volatile, higher-turnover alpha.

WAVE 23 also showed the ret2 leg under exp-decay reaching Sh 1.25 / CLUSTER 1.43
(w23_dexp5_ret2) — the best CLUSTER_TEST of the campaign, meaning that structure
is genuinely differentiated from the rest of the pool.

WAVE 24 therefore sweeps `factor` (the real turnover knob) at a fixed window,
under BOTH neutralizations, and pushes toward the cell the algebra demands:
T ~ 8-12%, R ~ 4-6%, Sharpe >= 1.58.

  Mgn >= 10  <=>  R/TO >= 0.50
  Fit >= 1.0 & Mgn >= 10  =>  Sharpe >= 1.414
  at T = 10%:  R >= 5.0% and Sharpe >= 1.58

The current best at LOW turnover is Sh ~1.01 (w21_q_ret2_tvr12_ind, T 12.6%,
R/TO 0.430) — short ~0.6 of Sharpe. The current best at HIGH Sharpe is 1.65 but
T is 67%. If `factor` slides turnover while holding the exp-decay family's Sharpe
advantage, there may be a factor value that lands both constraints at once.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"

STAT = "STATISTICAL"
IND = "INDUSTRY"
CORE = f"multiply({R_RET}, {R_P5})"
RET2_CORE = f"multiply({RET2}, group_rank({PROB_2}, industry))"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


W24 = {
 "batch": 24, "family": "exp_decay_factor_sweep_the_real_turnover_knob",
 "hypothesis": (
   "波次 24: 扫描 ts_decay_exp_window 的 **factor** 维度 —— 波次 23 已证明 window 长度**不控制换手** "
   "(window 5/8/10 在 STATISTICAL 下换手全是 ~53.5%), 真正的衰减速率旋钮是 factor, 而它从未被扫过。"
   "同时波次 23 发现中性化会整体平移换手水位 (同一表达式 STATISTICAL 53.5% vs INDUSTRY 31.7%), "
   "因为保留更多 beta 的中性化产生更易波动的 alpha ⇒ 两个中性化必须分别扫 factor。"
   "本波 8 槽位: factor 0.2/0.35/0.5/0.7 在 STATISTICAL 下的 r20marsi 核 (窗口固定 10), "
   "factor 0.2/0.35/0.7 在 INDUSTRY 下的同一核 (INDUSTRY 的换手水位低 20 个百分点, 更可能落在 "
   "T=8%~12% 的可行区), 以及 ret2 腿在 INDUSTRY + factor 0.35 下的两个形态 (group_zscore 与 quantile)。"
   "目标是找到 factor 使 T≈8%~12% 且 R/TO>=0.50 且 Sh>=1.58 的解 —— 这是唯一还没被系统搜索过的维度。"
 ),
 "items": [
  slot("w24_stat_f02", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.2), industry)",
       3, [R_RET, R_P5],
       "factor=0.2 @ STATISTICAL: 最慢衰减 ⇒ 换手最低档。检验 factor 与换手的单调方向, 并看 Sharpe 是否保留。",
       neutralization=STAT),
  slot("w24_stat_f035", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.35), industry)",
       3, [R_RET, R_P5],
       "factor=0.35 @ STATISTICAL: 中间档, 最可能落在 T=8%~12% 可行区。",
       neutralization=STAT),
  slot("w24_stat_f07", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.7), industry)",
       3, [R_RET, R_P5],
       "factor=0.7 @ STATISTICAL: 最快衰减档, 作为 factor 扫描的上界对照 (波次 19 的 dexp20/0.7 给出 TO 68.5%)。",
       neutralization=STAT),
  slot("w24_ind_f02", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.2), industry)",
       3, [R_RET, R_P5],
       "factor=0.2 @ INDUSTRY: INDUSTRY 的换手水位比 STATISTICAL 低 ~22 个百分点, 故 factor 0.2 在此可能直接落进 T=8%~12% 可行区。",
       neutralization=IND),
  slot("w24_ind_f035", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.35), industry)",
       3, [R_RET, R_P5],
       "factor=0.35 @ INDUSTRY: 最可能的可行解候选。",
       neutralization=IND),
  slot("w24_ind_f07", f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.7), industry)",
       3, [R_RET, R_P5],
       "factor=0.7 @ INDUSTRY: 上界对照, 检验 INDUSTRY 下 factor 的换手响应幅度是否与 STATISTICAL 相同。",
       neutralization=IND),
  slot("w24_ind_f035_q", f"quantile(ts_decay_exp_window({CORE}, 10, factor=0.35), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "INDUSTRY + factor 0.35 + quantile 账本形状: 波次 21 证明 quantile 抬 Fitness 与 R/TO (w21_q_tvr12 Fit 0.62 全战役最高), 在 factor 扫描的最优点上叠加。",
       neutralization=IND),
  slot("w24_ind_f035_ret2", f"group_zscore(ts_decay_exp_window({RET2_CORE}, 10, factor=0.35), industry)",
       4, [RET2, PROB_2],
       "ret2 腿 (R/TO 最高) + INDUSTRY + factor 0.35: 该腿在 exp-decay 下曾达 Sh 1.25 / CLUSTER 1.43 (w23_dexp5_ret2, 全战役最高 CLUSTER), 若 factor 0.35 同时压低换手则它最可能全格达标。",
       neutralization=IND),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W24['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W24, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W24['items'])} items)")
