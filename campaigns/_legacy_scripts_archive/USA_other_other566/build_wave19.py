"""
build_wave19.py — wave 19: the joint (smoother x neutralization x decay) frontier.

WAVE 18 RESULT — two independent, complementary winners appeared:

  A) STATISTICAL neutralization + ts_target_tvr_decay:
       tvr 0.08 -> Sh 0.99, Mgn 4.67, TO 10.0%, 2Y 1.32
       tvr 0.10 -> Sh 1.17, Fit 0.55, Mgn 4.66, TO 11.9%, 2Y 1.68
       tvr 0.12 -> Sh 1.27, Fit 0.59, Mgn 4.37, TO 13.9%, 2Y 1.86, 0 fails
       tvr 0.15 -> Sh 1.31, Fit 0.56, Mgn 3.71, TO 17.0%, 2Y 1.86
       tvr 0.20 -> Sh 1.30, Fit 0.49, Mgn 2.84, TO 22.2%, 2Y 1.82
  B) STATISTICAL neutralization + ts_decay_exp_window(10, 0.5):
       -> Sh **1.59**, 2Y **2.37**, TO 53.5%, Mgn 1.43, 0 fails
     The first alpha in the whole campaign to clear the Sharpe>=1.58 gate.
     BUT turnover 53.5% breaches the 50% production cap and crushes Margin.

The two winners are the SAME two levers at different strengths:
  ts_target_tvr_decay  = explicit turnover target -> low turnover, moderate Sharpe
  ts_decay_exp_window  = geometric smoothing     -> high turnover, HIGH Sharpe
This is the opposite of what wave 12 (INDUSTRY) showed, where ts_decay_exp_window
underperformed ts_target_tvr_decay on Sharpe (1.00 vs 0.91 was comparable, but
Mgn was much worse). Under STATISTICAL neutralization the exp-decay smoother
retains far more of the signal (Sh 1.59 vs 1.27) — because STATISTICAL already
removed the common factors that were making the signal noisy, so a gentler
smoother no longer smears away real information.

=> THE MISSING POINT ON THE LADDER: an exp-decay smoother with a LONGER window
   or a HIGHER factor (stronger geometric smoothing), which is exactly the
   missing middle between ts_target_tvr_decay (TO 13.9%) and ts_decay_exp_window
   (TO 53.5%). Wave 19 sweeps that missing segment.

WAVE 19 also attacks the arithmetic directly. From the wave-18 ladder we can
read off the frontier in (TO, returns, Sharpe):
    STAT tvr 0.08: TO 10.0%, Mgn 4.67 => returns 2.33%, Sh 0.99
    STAT tvr 0.10: TO 11.9%, Mgn 4.66 => returns 2.77%, Sh 1.17
    STAT tvr 0.12: TO 13.9%, Mgn 4.37 => returns 3.04%, Sh 1.27
    STAT tvr 0.15: TO 17.0%, Mgn 3.71 => returns 3.15%, Sh 1.31
    STAT tvr 0.20: TO 22.2%, Mgn 2.84 => returns 3.15%, Sh 1.30
    STAT dexp10 : TO 53.5%, Mgn 1.43 => returns 3.83%, Sh 1.59
returns are FLAT (~2.3-3.8%) while Sharpe RISES with turnover. So under STATISTICAL
the alpha's gross return barely responds to smoothing, but its RISK does — the
smoother concentrates the PnL into fewer, larger moves. That is why Margin
(returns/turnover) falls linearly as turnover rises.

The gate needs returns >= 0.5*TO and Sharpe >= 1/sqrt(returns/max(TO,0.125)).
At TO=20%: returns >= 10% (!) and Sharpe >= 1.16. Our returns are ~3.2% at
TO 17-20%. So **Margin >= 10bps cannot be met at any turnover above ~7%**
unless returns roughly triple. That reframes the whole problem:

  THE ONLY WAY TO GET BOTH Sharpe>=1.58 AND Margin>=10bps IS TO RAISE RETURNS
  PER UNIT OF TURNOVER — i.e. improve the alpha's signal quality, not its
  turnover. A pure smoothing sweep cannot do it.

Wave 19 therefore tests the levers that can raise RETURNS per unit turnover:
  (a) a stronger-but-not-maximal exp-decay (the missing middle segment)
  (b) a SECOND, ORTHOGONAL signal leg added to the champion core — because the
      campaign's only working multi-field combination (w11_gz_l3r5, Sh 1.10 with
      0 fails) shows a second model leg can add Sharpe without adding turnover
      proportionally; the L3R5 leg is the cross-sectional complement to the
      R20MaRsi leg (technical indicators vs order-book depth)
  (c) a LOWER-COST direction leg: oth566_return (2-day forecast, 39 users) has
      a shorter horizon hence less stale information, at the same turnover
  (d) STATISTICAL + INDUSTRY-style outer mix

All slots keep 2 fields and <= 5 operators.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_P3 = "oth566_r20marsi_prob_3"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"

STAT = "STATISTICAL"
CORE = f"multiply({R_RET}, {R_P5})"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


W19 = {
 "batch": 19, "family": "missing_middle_segment_and_return_per_turnover_levers",
 "hypothesis": (
   "波次 19: 波次 18 同时浮现两个**互补**赢家: STATISTICAL + ts_target_tvr_decay (低换手, Sh 1.27/TO 13.9%) "
   "与 STATISTICAL + ts_decay_exp_window(10, 0.5) (高换手, Sh **1.59**/2Y **2.37**/TO 53.5%)。"
   "这是全战役首个越过 Sharpe>=1.58 门槛的 alpha, 但换手 53.5% 越过 50% 生产上限且 Margin 仅 1.43bps。"
   "两者用的是**同一对杠杆的不同强度** ⇒ 缺失的正是两者之间的中段 (更强几何平滑)。"
   "同时波次 18 的阶梯读数给出一个决定性事实: STATISTICAL 下 returns 几乎是常数 (~2.3%~3.8%), "
   "而 Sharpe 随换手单调上升 ⇒ 平滑只是把 PnL 集中成更大更少的交易, **单位换手的收益没有提高**。"
   "于是 gate 的代数 (Mgn>=10 ⇒ returns>=0.5*TO) 说明: 在 TO>7% 的任何工作点上, 要同时满足 "
   "Mgn 10bps 与 Sharpe 1.58, 必须把单位换手收益提高约三倍 ⇒ **靠继续拧平滑旋钮到不了终点**, "
   "必须提升信号本身的质量。本波 8 槽位因此分两组: (a) 补上指数平滑的中段 (window 15/20, factor 0.6/0.75) "
   "以定位高 Sharpe 端的最优换手; (b) 提升收益/换手比的真实杠杆 —— 加入**正交第二信号腿** "
   "(L3R5 订单簿深度模型 x 其置信腿; 波次 11 的 w11_gz_l3r5 以 0 fails 证明第二腿能加 Sharpe 而不同比例加换手)、"
   "以及换用**期限更短的方向腿** (oth566_return 2 日期预测, 信息更不陈旧)。"
 ),
 "items": [
  slot("w19_dexp15",
       f"group_zscore(ts_decay_exp_window({CORE}, 15, factor=0.6), industry)",
       3, [R_RET, R_P5],
       "(a) 中段补点: window 15 / factor 0.6。预期 TO 落在 35-45%, 即在 53.5% (Sh1.59) 与 13.9% (Sh1.27) 之间, 若 Sharpe 保持 >=1.5 而 TO 压到 45% 以下则同时解决换手上限与 Sharpe 门槛。"),
  slot("w19_dexp20",
       f"group_zscore(ts_decay_exp_window({CORE}, 20, factor=0.7), industry)",
       3, [R_RET, R_P5],
       "(a) 中段补点: window 20 / factor 0.7, 与上一槽配对做 window x factor 双维扫描。"),
  slot("w19_dexp20_d4",
       f"group_zscore(ts_decay_exp_window({CORE}, 20, factor=0.7), industry)",
       3, [R_RET, R_P5], "decay=4",
       "(a) 中段 + 平台端 decay=4: 平台端线性衰减与表达式端几何衰减叠加, 双平滑器能否把 TO 53.5% 压到 50% 以下而保住 Sh>=1.5。这是波次 13 建立的「两杠杆互补」在高 Sharpe 端的复测。"),
  slot("w19_l3_dexp20",
       f"group_zscore(ts_decay_exp_window(multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry)), 20, factor=0.7), industry)",
       5, [L3R5, L3R5P],
       "(b) 第二正交腿: Level3 订单簿 5 日模型 (标准化方向 x 行业内置信秩) 配指数平滑。R20MaRsi 是技术指标模型, L3R5 是订单簿深度模型, 信息集正交 ⇒ 期望在不线性增加换手的前提下抬 Sharpe。"),
  slot("w19_l3_tvr12",
       f"group_zscore(ts_target_tvr_decay(multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry)), target_tvr=0.12), industry)",
       5, [L3R5, L3R5P],
       "(b) 第二正交腿的低换手版: 与 w19_l3_dexp20 配对, 检验第二腿在不同平滑器下的收益。"),
  slot("w19_l3_dexp20_c",
       f"group_zscore(ts_decay_exp_window(multiply({R_RET}, {R_P5}), 20, factor=0.7), industry)",
       3, [R_RET, R_P5],
       "(b) 基准复现: w19_dexp20 的同设置第二次运行, 作为第二腿增量的归因基准 (平台同设置应逐位一致)。"),
  slot("w19_ret2_dexp20",
       f"group_zscore(ts_decay_exp_window(multiply({RET2}, group_rank({PROB_2}, industry)), 20, factor=0.7), industry)",
       4, [RET2, PROB_2],
       "(c) 更短期限的方向腿: oth566_return 是 2 日前向预测 (39 用户) 而非 20 日, 信息更不陈旧 ⇒ 预期更高的单位换手收益, 且其置信腿 prob_2 同样冷门 (1/1)。"),
  slot("w19_p3_dexp20",
       f"group_zscore(ts_decay_exp_window(multiply({R_RET}, {R_P3}), 20, factor=0.7), industry)",
       3, [R_RET, R_P3],
       "(c) 信念口径稳健性: 置信腿换 prob_3 (4 用户) 在高 Sharpe 工作点上重测, 确认结论不依赖 prob_5 的特定形态。"),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W19['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W19, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W19['items'])} items)")
