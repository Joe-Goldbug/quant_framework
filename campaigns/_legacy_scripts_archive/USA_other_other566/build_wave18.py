"""
build_wave18.py — wave 18: STATISTICAL neutralization x tvr ladder (the winner combination).

WAVE 17 RESULT — the neutralization sweep was the right lever:

  slot                  neutralization   Sh     Fit    Mgn     TO      2Y    fails
  w17_neu_stat_t12      STATISTICAL      1.27   0.59   4.37    13.9%   1.86   0   <== WINNER
  w17_neu_none_t12      NONE             1.00   0.61   7.39    12.5%   1.12   0
  w17_neu_market_t12    MARKET           1.00   0.61   7.39    12.5%   1.12   0
  w17_neu_none_t08      NONE             0.91   0.51   9.51     8.3%   1.51   3
  w17_neu_market_t08    MARKET           0.91   0.51   9.51     8.3%   1.51   3
  w17_neu_subind_t12    SUBINDUSTRY      0.83   0.42   5.14    12.8%   0.57   3
  w17_neu_subind_t08    SUBINDUSTRY      0.82   0.41   7.30     8.6%   0.71   3

Three facts fall out:
  1. STATISTICAL beats INDUSTRY on Sharpe (1.27 vs 1.00) AND on 2Y Sharpe
     (1.86 vs 1.38) — the biggest single-metric jump of the whole campaign
     outside of removing ts_mean.
  2. NONE and MARKET are metrically IDENTICAL to each other (1.00/0.61/7.39/
     12.5% for both at tvr=0.12). That is not a coincidence: for a dollar-neutral
     long-short book, stripping market beta and keeping none of it produce the
     same cross-sectional book; the platform's MARKET neutralization already
     removes what NONE would have kept. So only STATISTICAL and SUBINDUSTRY
     (the two that peel a different FACTOR structure) move the numbers.
  3. SUBINDUSTRY is clearly WORSE (Sh 0.83 vs 1.00) — consistent with the
     hypothesis that this alpha's edge is partly a genuine industry-level
     (order-book liquidity regime) signal, and forcing sub-industry purity
     destroys it. STATISTICAL is better because it removes the *common
     statistical factors* (size, beta, volatility) while leaving the
     industry-conditional part of the forecast intact.

Now the operating point moves. Under STATISTICAL the champion (tvr 0.12) has
returns 4.37%*13.9/4.37*20... let us use the identity directly:
    margin_bps = returns/turnover*20  =>  4.37 = returns/0.139*20
    => returns = 4.37*0.139/20 = 3.04%
    fitness = sharpe*sqrt(returns/max(TO,0.125)) = 1.27*sqrt(0.0304/0.139) = 1.27*0.468 = 0.59  ✓
For the production gate at this operating point we need:
    Mgn >= 10  => returns >= 0.5*TO
    Fit >= 1.0 => sharpe >= 1/sqrt(returns/max(TO,0.125))
At TO = 10%: returns >= 5.0%, sharpe >= 1/sqrt(0.05/0.125) = 1.58.
So the target is a STATISTICAL + tvr that lands near TO ~10% with returns ~5%
and sharpe >= 1.58. The tvr ladder is the knob that trades TO against returns;
under STATISTICAL the ladder has never been swept.

WAVE 18 therefore sweeps tvr under STATISTICAL at the champion expression, and
adds the second dimension that STATISTICAL makes newly meaningful: since
STATISTICAL neutralization already removes common statistical factors, the
expression no longer needs to fight them, so the outer layer and the inner
smoother can be re-optimised.

Slots:
  * tvr 0.05/0.08/0.10/0.12/0.15/0.20 under STATISTICAL @ decay 0 (ladder)
  * tvr 0.10 under STATISTICAL with group_rank outer (rank gave the best Sharpe
    in wave 11; STATISTICAL + rank is the untested pairing)
  * tvr 0.10 under STATISTICAL with ts_decay_exp_window instead of the tvr
    optimiser (an independent smoother, to check the tvr optimum is not an
    artefact of one operator)
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
CORE = f"multiply({R_RET}, {R_P5})"
STAT = "STATISTICAL"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


def tvr(sid, t, note):
    return slot(sid,
                f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr={t}), industry)",
                3, [R_RET, R_P5], note)


W18 = {
 "batch": 18, "family": "statistical_neutralization_tvr_ladder",
 "hypothesis": (
   "波次 18: 把波次 17 的赢家 (STATISTICAL 中性化) 与 tvr 旋钮结合。波次 17 显示 STATISTICAL 相对 INDUSTRY "
   "把 Sharpe 从 1.00 抬到 **1.27**、2Y Sharpe 从 1.38 抬到 **1.86**, 且仍是 0 平台 FAIL —— 这是本战役"
   "除「去掉 ts_mean」之外最大的单点提升。机理: STATISTICAL 用统计方法剥离市值/beta/波动率等**共同统计因子**, "
   "而保留预测中真正与行业条件性相关的部分; 这与 SUBINDUSTRY 的结果一致地反证了本 alpha 的边缘**部分来自"
   "行业层面的订单簿流动性状态信号**, 强制细分行业纯度反而摧毁它 (Sh 0.83)。"
   "另外 NONE 与 MARKET 给出逐位相同的指标 (1.00/0.61/7.39/12.5%), 因为对美元中性多空组合而言"
   "「剥离市场 beta」与「完全保留 beta」最终构造出同一本账 —— 只有真正剥离不同**因子结构**的 STATISTICAL 与 "
   "SUBINDUSTRY 才改变数字。"
   "STATISTICAL 改变了工作点 (tvr=0.12 时 returns 3.04%, TO 13.9%), 因此必须在 STATISTICAL 下重扫 tvr 阶梯: "
   "要在 TO≈10% 处拿到 returns≥5% 且 Sharpe≥1.58, 才可能同时过 Mgn 10bps 与 Fit 1.00 两条线。"
 ),
 "items": [
  tvr("w18_stat_tvr05", 0.05,
      "STATISTICAL @ tvr=0.05: 最激进换手档。波次 17 在 INDUSTRY 下 tvr=0.05 曾给出唯一过 Margin 的槽位; "
      "在 STATISTICAL 下需重测 —— 统计因子剥离可能让低换手端的收益/换手比更优。"),
  tvr("w18_stat_tvr08", 0.08,
      "STATISTICAL @ tvr=0.08: INDUSTRY 下该点的 Mgn 9.51 (差 0.5bps), 在 STATISTICAL 下重测。"),
  tvr("w18_stat_tvr10", 0.10,
      "STATISTICAL @ tvr=0.10: 理论最优区间的探测点 (TO≈10% 时需 returns≥5% 且 Sharpe≥1.58)。"),
  tvr("w18_stat_tvr15", 0.15,
      "STATISTICAL @ tvr=0.15: INDUSTRY 下的 Sharpe 峰位 (1.00/0.55/6.00), STATISTICAL 下重测。"),
  tvr("w18_stat_tvr20", 0.20,
      "STATISTICAL @ tvr=0.20: 宽松换手端, 检验 STATISTICAL 是否把 Sharpe 峰推到更高换手 (Sharpe 换手率更高 ⇒ returns 更高 ⇒ Mgn 更高)。"),
  slot("w18_stat_tvr10_rank",
       f"group_rank(ts_target_tvr_decay({CORE}, target_tvr=0.10), subindustry)",
       3, [R_RET, R_P5],
       "外层对照: STATISTICAL + tvr=0.10 + group_rank。波次 11 中 rank 给最高 Sharpe (1.18 vs zscore 1.08), "
       "而 STATISTICAL 已剥离共同因子, 外层 rank 可能不再承担去因子职责 ⇒ Sharpe 可能进一步上升。"),
  slot("w18_stat_dexp10",
       f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.5), industry)",
       3, [R_RET, R_P5],
       "独立平滑器对照: 用 ts_decay_exp_window 替代 ts_target_tvr_decay, 检验 tvr 最优点是否为单一算子的产物。"),
  slot("w18_stat_tvr12",
       f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr=0.12), industry)",
       3, [R_RET, R_P5],
       "波次 17 冠军点复现 (STATISTICAL @ tvr=0.12 → Sh 1.27): 作为本波其余槽位的同组基准, "
       "确认结果可重复 (平台在同设置下应逐位一致)。"),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W18['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W18, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W18['items'])} items)")
