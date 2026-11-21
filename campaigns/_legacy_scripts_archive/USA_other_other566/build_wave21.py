"""
build_wave21.py — wave 21: raise RETURNS per unit turnover via book-shape levers.

WAVE 20 RESULT: STATISTICAL is NOT uniformly better — it is better for the
R20MaRsi leg (Sharpe 1.27 vs 1.00) but WORSE for the 2-day leg:
    w12_ret2_tvr15  INDUSTRY   R 4.84%  TO 12.0%  Mgn 8.03  Sh 0.91
    w20_ret2_tvr12  STATISTICAL R 2.50%  TO 14.3%  Mgn 3.50  Sh 0.99
  => the two legs want DIFFERENT neutralizations. The ret2 leg's edge survives
     only when the platform strips less (INDUSTRY keeps more of its returns).

THE REMAINING ARITHMETIC, restated:
    Mgn >= 10  <=>  returns/turnover >= 0.50
    Fit >= 1.0, combined with Mgn >= 10, forces  Sharpe >= 1.414
    and at turnover T:  returns >= 0.5*T,  Sharpe >= 1.58 at T=10%.
So the winning cell needs **returns of 5-6.25% at turnover of 10-12.5% with
Sharpe >= 1.58**. Best returns-per-turnover structures found so far:
    w15_tvr05_d0  R/TO 0.520 (Mgn 10.39)  but Sh 0.66, TO 5.3%
    w12_ret2_tvr15 R/TO 0.403 (Mgn 8.03)  but Sh 0.91, TO 12.0%
Neither has the Sharpe. The shortfall is not a smoothing problem — it is that
the book's PnL per trade is too small.

THE UNTESTED CLASS OF LEVERS: **book SHAPE**. Every alpha so far used one of
three outer layers (group_rank / group_zscore / group_neutralize), all of which
produce a roughly uniform weight profile across the book. The platform also
offers operators that change the weight CONCENTRATION without changing the
ordering, and concentration is precisely what raises returns per unit of
turnover:
  * `quantile(x, "gaussian")` — BRAIN's own documented operator for stretching
    the tails and compressing the middle: "Ranks and shifts a vector of Alpha
    values, then applies a chosen statistical distribution to reduce outliers."
    The tails carry the signal; compressing the middle (where the forecast is
    near-neutral and trading is pure cost) raises PnL per trade. It is the
    single most-used Sharpe lever in BRAIN practice and has NEVER been tried in
    this campaign.
  * `truncate` / higher `truncation` — allows a more concentrated book.
  * `group_scale` — within-group linear spread (different tail behaviour from
    group_rank's uniform spread).

Wave 21 therefore keeps the two best legs fixed and varies ONLY the book shape,
plus one lever sweep on the ret2 leg under its preferred INDUSTRY neutralization.
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


W21 = {
 "batch": 21, "family": "book_shape_operators_to_raise_returns_per_turnover",
 "hypothesis": (
   "波次 21: 攻击 **收益/换手比** —— 这是 Mgn>=10bps 的直接定义 (margin_bps = returns/turnover*20), "
   "也是全战役唯一还没被真正攻击的量。波次 18/19 已证明: 无论怎么平滑, returns 都被锁在 2.3%~6.2% 而 "
   "Sharpe 随换手上升 ⇒ **单位换手的收益不会靠平滑提高**。要提高它必须改变**账本的权重形状**。"
   "本战役 21 个波次只用过 group_rank / group_zscore / group_neutralize 三种外层, 它们产生的权重剖面"
   "都近似均匀 —— 而 PnL/交易 的大小正取决于权重**集中度**。BRAIN 自带的 `quantile(x, \"gaussian\")` "
   "正是为此设计 (把尾部拉长、中间压缩: 中间区域的预测接近中性, 在那里交易纯属成本), 它是 BRAIN 实践中"
   "最常用的 Sharpe 杠杆, 在本战役**从未用过**。本波 8 槽位: (a) 冠军核 (r20marsi 腿) 配 quantile "
   "外层, 在两个 tvr 工作点上; (b) 高 Sharpe 端 dexp20 核配 quantile (Sharpe 1.63 / 2Y 2.45 是全战役最高, "
   "若 quantile 能提 returns 则 Mgn 有望过线); (c) 2 日期腿在它偏好的 INDUSTRY 中性化下配 quantile "
   "(该腿 R/TO 最高); (d) truncation 放宽到 0.20 的集中度探针。"
 ),
 "items": [
  slot("w21_q_tvr12",
       f"quantile(ts_target_tvr_decay({CORE}, target_tvr=0.12), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "(a) quantile 外层 @ tvr=0.12 (STATISTICAL, 当前 Fitness 峰 Sh1.27/Fit0.59): 若尾部拉长能提高 PnL/交易, 则 returns 上升 ⇒ Mgn 与 Fit 同时改善。这是本波最核心的假设。",
       neutralization=STAT),
  slot("w21_q_tvr08",
       f"quantile(ts_target_tvr_decay({CORE}, target_tvr=0.08), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "(a) quantile 外层 @ tvr=0.08 (Margin 侧): 与上一槽配对定位 quantile 的收益。",
       neutralization=STAT),
  slot("w21_q_dexp20",
       f"quantile(ts_decay_exp_window({CORE}, 20, factor=0.7), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "(b) quantile 外层 @ dexp20 高 Sharpe 核 (Sh 1.63 / 2Y 2.45, 0 FAIL): 若 quantile 把收益集中到强信号上, 该核的 Mgn 有望从 1.12 跃升。",
       neutralization=STAT),
  slot("w21_q_dexp15",
       f"quantile(ts_decay_exp_window({CORE}, 15, factor=0.6), driver=\"gaussian\")",
       3, [R_RET, R_P5],
       "(b) quantile 外层 @ dexp15 核 (Sh 1.62, TO 61.0%): 与 dexp20 版配对。",
       neutralization=STAT),
  slot("w21_q_ret2_tvr15_ind",
       f"quantile(ts_target_tvr_decay({RET2_CORE}, target_tvr=0.15), driver=\"gaussian\")",
       4, [RET2, PROB_2],
       "(c) 2 日期腿 + quantile + INDUSTRY 中性化: 该腿在 INDUSTRY 下 R/TO 最高 (w12_ret2_tvr15: R 4.84% / TO 12.0% / Mgn 8.03), 且 STATISTICAL 会削掉它的收益 ⇒ 用它偏好的中性化。",
       neutralization=IND),
  slot("w21_q_ret2_tvr12_ind",
       f"quantile(ts_target_tvr_decay({RET2_CORE}, target_tvr=0.12), driver=\"gaussian\")",
       4, [RET2, PROB_2],
       "(c) 2 日期腿 + quantile + INDUSTRY @ tvr=0.12: 换手更低的工作点, 目标 R/TO >= 0.5。",
       neutralization=IND),
  slot("w21_q_l3_dexp20",
       f"quantile(ts_decay_exp_window(multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry)), 20, factor=0.7), driver=\"gaussian\")",
       5, [L3R5, L3R5P],
       "(d) L3 订单簿腿 + quantile: 该腿绝对收益最高 (R 6.22%), 若 quantile 能保住其高收益并改善 R/TO, 它是最可能过 Mgn 线的结构。",
       neutralization=STAT),
  slot("w21_dexp20_trunc20",
       f"group_zscore(ts_decay_exp_window({CORE}, 20, factor=0.7), industry)",
       3, [R_RET, R_P5],
       "(d) 集中度探针: truncation 从 0.08 放宽到 0.20, 允许更集中的账本 ⇒ 每笔交易的 PnL 更大 ⇒ 单位换手收益上升。与 quantile 是两条不同的集中度路径。",
       neutralization=STAT, truncation=0.20),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W21['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W21, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W21['items'])} items)")
