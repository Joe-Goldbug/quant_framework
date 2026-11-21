"""
build_wave15.py — wave 15: the combined-lever wave (the two best axes at once).

WHAT WAVE 13 ESTABLISHED (real decay sweep, 8 slots, 4 decay groups):

  slot                 decay  Sh     Fit    Mgn     TO      2Y    fails
  w13_d0_plain           0    1.15   0.27   1.09    89.7%   1.52  4
  w13_d0_tvr15           0    1.00   0.55   6.00    15.6%   1.16  0   <== BEST
  w13_d8_tvr15           8    0.88   0.50   7.83    10.5%   1.03  3
  w13_d8_dexp            8    0.97   0.38   3.10    30.4%   1.00  3
  w13_d8_plain           8    0.89   0.38   3.73    23.2%   0.85  3
  w13_d12_tvr15         12    0.91   0.39   3.74    24.2%   0.78  3
  w13_d12_dexp         12    0.86   0.41   4.51    18.9%   0.78  3
  w13_d20_plain         20    (single-submit 400 -> re-run in wave 15)

THE STRUCTURAL FINDING: the two levers are NOT substitutes, they are COMPLEMENTARY.
  * decay is the PLATFORM-side position smoother: it decays the alpha value itself
    across days, so it directly attacks turnover.
  * ts_target_tvr_decay is the EXPRESSION-side smoother: it optimises a decay
    parameter so the resulting signal hits a turnover target.
  * Stacking them (decay=0 + tvr target) beat either alone:
      decay=4 + tvr15 : Sh 0.91 Fit 0.53 Mgn 6.95 TO 12.2%  (w12_tvr15)
      decay=0 + tvr15 : Sh 1.00 Fit 0.55 Mgn 6.00 TO 15.6%  (w13_d0_tvr15)  <-- Sharpe up, Fit up
    because ts_target_tvr_decay needs room: at decay=4 the platform has already
    smoothed the series, so the tvr optimiser's inner decay has less signal left
    to work with and lands on a worse joint solution.

  The best single alpha so far is `decay=0 + ts_target_tvr_decay(target_tvr=0.15)`
  at Sh 1.00 / Fit 0.55 / Mgn 6.00 / TO 15.6% / 2Y 1.16 / **0 platform fails**.
  It is the only alpha in the campaign that clears the platform's RA check
  (ra_failed=false) while also having a respectable Sharpe.

THE REMAINING GAP vs the production gate:
  need Sh>=1.58, Fit>=1.00, Mgn>=10.0bps, TO in [5%,50%], 0 fails.
  have Sh 1.00, Fit 0.55, Mgn 6.00, TO 15.6%, 0 fails.
  Recall the algebra:
      fitness = sharpe * sqrt(returns / max(turnover, 0.125))
      margin  = returns / turnover * 20
  From the winner: returns = 4.68%, turnover = 15.6%.
  For Fit>=1.00 at TO=15.6%: need Sh >= 1.00 / sqrt(0.0468/0.156) = 1.00/0.548 = 1.83.
  So we need Sharpe ~1.83 at the same turnover, OR Sharpe ~1.58 at a turnover
  where returns can be much larger.
  Since w13_d0_plain shows the SAME core reaches Sh 1.15 at decay=0 with TO 89.7%,
  the raw signal has more Sharpe available at high turnover than the smoothed
  version keeps. Wave 15 therefore explores the JOINT surface: which (tvr target,
  decay) pair maximises Sharpe*sqrt(returns/max(TO,0.125)) — i.e. Fitness — while
  keeping returns/turnover >= 0.5 for Margin.

WAVE 15 SLOTS (all 2 fields, <=6 operators, all on the champion core):
  * tvr target ladder 0.05/0.08/0.12/0.15/0.20 at decay=0 (the best regime)
  * decay ladder 0/2/6 at the best tvr target
  * outer-layer check: group_rank vs group_zscore at the best (decay, tvr) point
    (rank gave the best Sharpe 1.18 in wave 11; zscore the best Margin)
  * a cross-model replication of the winning structure on the L5 GasfCulr model
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
L5C_RET = "oth566_l5r20gasfculr_ret"
L5C_PATP = "oth566_l5r20gasfculr_prob_pattern"

CORE = f"multiply({R_RET}, {R_P5})"


def gz_tvr(tvr, decay=0):
    return {
        "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr={tvr}), industry)",
        "ops": 3, "fields": [R_RET, R_P5], "decay": decay,
    }


W15 = {
 "batch": 15, "family": "joint_lever_surface_decay_x_tvr_target",
 "hypothesis": (
   "波次 15: 联合杠杆面 (decay x tvr target)。波次 13 的真实 decay 扫描证明两个杠杆是**互补**而非替代: "
   "decay=0 + ts_target_tvr_decay(target_tvr=0.15) 给出 Sh 1.00 / Fit 0.55 / Mgn 6.00 / TO 15.6% / "
   "2Y 1.16 / **0 平台 FAIL** —— 是全战役唯一 ra_failed=false 的 alpha; 而 decay=4 同样的 tvr 只有 "
   "Sh 0.91 / Fit 0.53。原因是 ts_target_tvr_decay 内部本身就是一个 decay 优化器: 若平台端已先做过 "
   "decay=4 平滑, 留给它优化的信号空间被压缩, 联合解变差。代数上仍有缺口: 由冠军 (returns 4.68%, TO 15.6%) "
   "反推, 要 Fit>=1.00 需 Sh>=1.83 (同换手), 要 Mgn>=10bps 需 returns>=7.8%。"
   "本波 8 槽位在 (decay, tvr_target) 联合面上细扫: tvr 0.05/0.08/0.12/0.20 四档 @decay=0, "
   "decay 2/6 两档 @tvr=0.15, 外层 group_rank 对照 (波次 11 中 rank 给最高 Sharpe 1.18 而 zscore 给最高 "
   "Margin 7.46), 以及把胜出结构复制到 L5 深订单簿模型做跨模型稳健性检验。"
 ),
 "items": [
  {"id": "w15_tvr05_d0", **gz_tvr(0.05), "why": "最激进换手目标: 若 TO 压到 5-7% 而收益保持, Margin 可直接过 10bps 线。"},
  {"id": "w15_tvr08_d0", **gz_tvr(0.08), "why": "换手目标 8%: 与 tvr10 的 9.56bps 对照, 定位 Margin 峰值。"},
  {"id": "w15_tvr12_d0", **gz_tvr(0.12), "why": "换手目标 12%: 波次 13 冠军 (tvr15) 的邻域, 确认最优点。"},
  {"id": "w15_tvr20_d0", **gz_tvr(0.20), "why": "换手目标 20%: 宽松档, 检验「更多收益、更少 Margin」的一侧。"},
  {"id": "w15_tvr15_d2", **gz_tvr(0.15, 2), "why": "decay=2 @tvr15: 平台端轻度平滑 + 表达式端目标换手, 测试最小量的互补。"},
  {"id": "w15_tvr15_d6", **gz_tvr(0.15, 6), "why": "decay=6 @tvr15: 中度平台平滑, 定位互补性的拐点 (decay 0 最优? 还是 2~6 更优?)。"},
  {"id": "w15_tvr15_d0_rank",
   "expr": f"group_rank(ts_target_tvr_decay({CORE}, target_tvr=0.15), subindustry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "外层对照: 波次 11 中 group_rank 给最高 Sharpe (1.18 vs zscore 1.08), 本槽在胜出杠杆组合下复测该排序是否保持。"},
  {"id": "w15_l5_d0_tvr15",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({L5C_RET}, group_rank({L5C_PATP}, industry)), target_tvr=0.15), industry)",
   "ops": 4, "fields": [L5C_RET, L5C_PATP], "decay": 0,
   "why": "跨模型稳健性: 把胜出结构 (tvr 目标换手 + 信念加权 + 幅度外层) 复制到 L5 GasfCulr 深订单簿模型 (与 R20MaRsi 信息集正交)。若两者都出信号, 机制是数据集层面的, 而非单模型偶然。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W15['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W15, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W15['items'])} items)")
