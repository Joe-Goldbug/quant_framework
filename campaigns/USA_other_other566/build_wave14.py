"""
build_wave14.py — wave 14: the wave that closes the two remaining gaps.

STATE OF THE FRONTIER after waves 11-13 (USA/D1/TOP1000, decay=4, INDUSTRY, trunc=0.08):

  Slot                                   Sh     Fit    Mgn     TO      2Y    fails
  b11_gz_rank  (no ts_mean, rank)        1.18   0.35   1.78    46.5%   1.39  0
  b11_gz_plain (no ts_mean, zscore)      1.08   0.36   2.28    44.7%   1.41  0
  b12_dexp20   (exp decay 20/0.7)       1.05   0.38   2.68    37.1%   1.38  0
  b12_dexp10   (exp decay 10/0.5)       1.00   0.39   3.02    31.7%   1.22  0
  b12_ret2_tvr15                        0.91   0.57   8.03    12.0%   1.10  3
  b12_tvr10   (tvr target 0.10)         0.89   0.50   9.56     8.4%   1.42  3

The production gate needs: Sh>=1.58, Fit>=1.00, Mgn>=10.0bps, TO in [5%,50%], 0 fails.

THE CENTRAL TENSION, now quantified:
  * Sharpe and Margin trade off through turnover, and the trade-off is NOT smooth.
  * Every variant that reaches Mgn>=8bps has Sh<=0.91.
  * Every variant with Sh>=1.0 has Mgn<=3bps.
  * The reason is visible in the metric algebra:
        margin_bps = returns / turnover * 20
        fitness    = sharpe * sqrt(returns / max(turnover, 0.125))
    => to have BOTH Sh>=1.58 AND Mgn>=10 we need, at any turnover T:
        returns >= 0.5*T                (margin)
        returns >= (1.58/1.0)^2 * max(T,0.125)   (fitness, since fitness>=1)
    At T=0.125 (the fitness floor): returns >= 0.31 (31% annualised) AND >= 0.0625.
    The 31% requirement is unreachable for a 1000-name long-short book.
    => FITNESS >= 1.0 IS THE BINDING CONSTRAINT, NOT MARGIN.
    => The only way to fitness>=1.0 at a sane turnover is to raise RETURNS a lot,
       which is a SIGNAL problem, not a smoothing problem.

THE MISSING LEVER: we have only ever traded the LEVEL of the model forecast.
  The forecast REVISION (ts_delta) family was tested in wave 2 but every one of
  those 8 slots carried the ts_mean(26) wrapper that wave 11 proved fatal, so
  wave 2's verdict on ts_delta is INVALID and must be re-run without ts_mean.
  Wave 14 does exactly that, plus:
    * ts_delta at 1/3/5/10 day horizons on the champion core (revision is the
      classic information-shock channel and is the highest-variance, therefore
      highest-return-per-turnover signal available in this dataset);
    * ts_rank / ts_zscore on the revision so the revision is scale-free;
    * trade_when re-tested as a REVISION gate (trade only when the forecast was
      actually revised) — this is a DIFFERENT gate from wave 7's, which gated on
      the LEVEL changing; on the revision series it can actually fire.

Wave 13 (decay sweep) is left unrun because decay had NO measurable effect:
  b11_gz_plain / w13_d0_plain / w13_d8_plain / w13_d12_plain / w13_d20_plain all
  returned identical metrics (Sh 1.08 / TO 44.7% / Mgn 2.28). The platform's
  `decay` setting is evidently inert for these already-fast-turnover expressions,
  so spending quota on it is wasteful. It is folded into wave 14 as a single
  decay=0 control instead of 8 slots.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_L5 = "oth566_r20marsi_label_5"
L5C_RET = "oth566_l5r20gasfculr_ret"
L5C_PATP = "oth566_l5r20gasfculr_prob_pattern"
ML3 = "oth566_multil3_label"
ML3P = "oth566_multil3_prob"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"

W14 = {
 "batch": 14, "family": "revision_channel_without_tsm_mean",
 "hypothesis": (
   "波次 14: 重新检验「预测修正」通道 —— 波次 2 对该机制的否定结论无效, 因为那 8 个槽位全部裹了 ts_mean(26), "
   "而波次 11 已证明 ts_mean 在本数据集是信号杀手 (n=54 meanSh 0.292 vs n=8 meanSh 0.836)。"
   "更关键的是算术诊断: fitness = sharpe*sqrt(returns/max(turnover,0.125)), 要 fitness>=1.0 且 sharpe>=1.58, "
   "在 turnover=12.5% 时需要 returns>=31% (年化), 对 1000 成分股的多空组合不可达 ⇒ "
   "**真正的死线是 Fitness 而非 Margin**, 必须提升收益本身而非继续压换手。"
   "而在本数据集里唯一能大幅提升收益且降低换手的通道就是**预测修正 (ts_delta)**: 模型观点的意外变化是"
   "信息冲击的机器代理, 修正量的收益/换手比远高于水平值 (水平值每天重发, 修正量只在观点真正变动时非零)。"
   "本波 8 槽位: (a) ts_delta 在 1/3/5/10 日窗口上的原始修正 × 置信度; "
   "(b) ts_rank 尺度自由化的修正 (只保留修正的相对次序, 抑制极端修正值主导); "
   "(c) ts_zscore 尺度自由化的修正; (d) 以**修正量**为条件的 trade_when 门控 (与波次 7 对水平量门控不同, "
   "此处门控可以真正触发); (e) L5 深订单簿模型的修正复制 (跨模型稳健性); "
   "(f) 2 日期限模型 (oth566_return + prob_2) 的修正复制; (g) decay=0 对照。"
 ),
 "items": [
  {"id": "w14_rev1", "expr": f"group_zscore(multiply(ts_delta({R_RET}, 1), {R_P5}), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (a) 最快档: 1 日修正 × 5 日置信度, group_zscore 外层保留幅度。预期收益/换手比最高。"},
  {"id": "w14_rev3", "expr": f"group_zscore(multiply(ts_delta({R_RET}, 3), {R_P5}), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (a) 3 日档: 与 1 日/5 日配对, 定位信息冲击被市场吸收的速度。"},
  {"id": "w14_rev5", "expr": f"group_zscore(multiply(ts_delta({R_RET}, 5), {R_P5}), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (a) 5 日档: 波次 2 的 b2_r5 在 ts_mean(26) 包裹下只有 Sh 0.xx, 本槽剥离该包裹后重测。"},
  {"id": "w14_rev10", "expr": f"group_zscore(multiply(ts_delta({R_RET}, 10), {R_P5}), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (a) 10 日档: 最长修正窗口, 捕捉被市场缓慢吸收的持久观点变化。"},
  {"id": "w14_rev_rank", "expr": f"group_zscore(multiply(ts_rank(ts_delta({R_RET}, 5), 120), {R_P5}), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (b) 尺度自由化: ts_rank 把修正量转成 120 日内的相对次序, 抑制个别极端修正值主导, 同时保留方向信息。"},
  {"id": "w14_rev_z", "expr": f"group_zscore(multiply(ts_zscore(ts_delta({R_RET}, 5), 60), {R_P5}), industry)",
   "ops": 4, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (c) 尺度自由化: ts_zscore 定心定标修正量, 与 ts_rank 版配对 (次序 vs 标准分)。"},
  {"id": "w14_rev_l5", "expr": f"group_zscore(multiply(ts_delta({L5C_RET}, 5), group_rank({L5C_PATP}, industry)), industry)",
   "ops": 4, "fields": [L5C_RET, L5C_PATP], "decay": 0,
   "why": "修正通道 (e) 跨模型复制: 把同一机制搬到 Level5 深订单簿模型 (与 R20MaRsi 信息集完全正交)。若两者都出信号, 说明「修正即信息冲击」是数据集层面的普遍机制而非单模型偶然。"},
  {"id": "w14_rev_gate", "expr": f"group_zscore(trade_when(not_equal(ts_delta({R_RET}, 1), 0), multiply(ts_delta({R_RET}, 1), {R_P5}), -1), industry)",
   "ops": 5, "fields": [R_RET, R_P5], "decay": 0,
   "why": "修正通道 (d) 门控: 以修正量本身为条件 —— 预测未变动时冻结持仓。与波次 7 的水平门控不同, 此处条件可在修正序列上真正触发, 预期把换手压到 10-15% 且保住收益。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W14['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W14, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W14['items'])} items)")
