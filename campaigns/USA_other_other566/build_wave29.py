"""build_wave29.py — move the turnover lever to the COMBINATION layer.

WAVE 28 BREAKTHROUGH (first alpha in the campaign to clear AEGIS Step2 with 0
platform FAIL and Margin above the seed):
  x28_add_negpe  Sh 1.07 / Fit 0.50 / Mgn 5.07bps / TO 10.83% / R 2.74% /
                 DD 4.66% / 2Y 1.23 / CLUSTER 0.56 / 0 FAIL
  x28_mult_negpe_tvr12  Sh 1.22 / Fit 0.52 / Mgn 3.64bps / TO 15.51% / 0 FAIL
  x28_add_ey_grow       Sh 0.96 / Fit 0.42 / Mgn 3.86bps / TO 12.33% / DD 4.38%
  Seed kqNgXQqd         Sh 1.27 / Fit 0.59 / Mgn 4.37bps / TO 13.93% / R 3.04%

MECHANISM CONFIRMED (the campaign's first working cross-dataset mechanism):
  fast order-book forecast (20-day horizon) + slow valuation-vs-own-history
  reversion (quarterly-ish) enter as ADDITIVE streams. Different horizons =>
  partially uncorrelated return streams => the slow leg adds returns WITHOUT
  adding turnover, so R/TO rises: seed 0.218 -> x28_add_negpe 0.253, and Margin
  4.37 -> 5.07bps.

WAVE 28 ALSO EXPOSED THE BLOCKER:
  x28_add_negpe at target_tvr=0.05 and target_tvr=0.08 returned BIT-IDENTICAL
  metrics (Sh 1.07, TO 10.83%, Mgn 5.07bps). The inner lever is inert because
  ts_target_tvr_decay is applied ONLY to the fast leg; the SLOW leg is raw, so
  the portfolio's turnover (10.83%) is set by the slow leg's own turnover
  (baseline pe_vs_hist alone: TO 10.87%).
  => THE LEVER MUST GO ON THE COMBINATION.

WAVE 29 DESIGN:
  L1. Move ts_target_tvr_decay to the OUTER layer: tvr the whole sum. This
      lowers portfolio turnover to 4-8% while the slow leg's return stream is
      preserved (ts_target_tvr_decay is the campaign's only signal-preserving
      smoother; it adapts the decay to hit a turnover target instead of
      averaging the level away).
  L2. Three-layer tvr: inner fast leg + inner slow leg + outer combination.
      Rationale: the slow leg's own turnover (10.87%) is a quarterly-signal
      repricing rate; smoothing it separately at 5-6% lets each layer sit at
      its own natural horizon.
  L3. Book-shape levers on the combined book (quantile gaussian, signed_power):
      campaign-proven to raise R/TO (w21_q_tvr12 Fit 0.62, Mgn 8.61bps).
  L4. Neutralization sweep on the winning additive structure: the valuation leg
      is a valuation factor, so INDUSTRY vs STATISTICAL may differ (campaign:
      the 2-day leg preferred INDUSTRY, R 4.84% vs STAT 2.50%).

ALGEBRAIC TARGET (unchanged): Mgn >= 15bps => R/TO >= 0.75.
  If outer tvr=0.045 lands TO ~5% and R holds ~2.6%, R/TO = 0.52 => Mgn 10.4bps.
  With a book-shape lever lifting R to ~3.4% at the same TO => R/TO 0.68 =>
  Mgn 13.6bps, and Fit = 1.07*sqrt(0.034/0.125) = 0.55 ... still short.
  The binding constraint remains R itself: needs R >= 5.5% at TO <= 7.3%.
  This wave tests whether the slow leg can carry more return weight than 1:1.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
PE_VS_HIST = "diff_current_vs_hist_pe_ratio"
EY_SMARTTEST = "earnings_yield_smartest_fy1"
GROW_NEXT = "smartest_growth_next_vs_this_year_earnings"

NEG_PE = f"reverse({PE_VS_HIST})"
NEG_PE_ZS = f"group_zscore({NEG_PE}, subindustry)"

# the wave-28 winner's core, as a reusable fragment
CORE08 = f"add(ts_target_tvr_decay({R_RET}, target_tvr=0.08), {NEG_PE_ZS})"

W29 = {
 "batch": 29, "family": "outer_turnover_lever_on_additive_slow_stream",
 "hypothesis": (
   "波次 29: 波次 28 首个跨数据集 alpha 过了 AEGIS Step2 全条件 (x28_add_negpe: Sh 1.07 / Fit 0.50 / "
   "Mgn 5.07bps / TO 10.83% / DD 4.66% / 0 平台 FAIL / MATCHES_THEMES USA-D1-TOP1000 2.0x), "
   "且 Margin 首次超过种子 (5.07 vs 4.37bps)。"
   "但同时暴露阻塞点: **tvr=0.05 与 tvr=0.08 的指标逐位相同** ⇒ 内层换手杠杆完全失效, 因为 "
   "ts_target_tvr_decay 只作用在快腿上, 组合换手 (10.83%) 由未平滑的慢腿 (自身 TO 10.87%) 主导。"
   "本波把杠杆移到**组合外层**: 对整个加法和做 ts_target_tvr_decay —— 换手由组合整体的目标决定, "
   "而慢腿的收益流被保留 (ts_target_tvr_decay 是战役唯一不杀信号的平滑算子: 它自适应地调 decay 去命中换手目标, "
   "而不是把水平平均掉)。"
   "同时测: (a) 三层 tvr (内快腿 + 内慢腿 + 外组合) 让每个期限坐在自己的自然节奏; "
   "(b) 账本形状杠杆 (quantile gaussian / signed_power) 抬 R/TO; "
   "(c) 中性化扫描 (估值腿是估值因子, 可能偏爱 INDUSTRY); "
   "(d) 慢腿权重放大 (慢腿独立收益流, 加大权重可抬 R 而 TO 由外层锁定)。"
   "代数目标: Mgn>=15bps => R/TO>=0.75; 若外层 tvr 把 TO 锁到 5-7%, 则需 R 达 3.8-5.3%。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [
  {"id": "x29_outer_tvr05",
   "expr": f"group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.05), subindustry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L1 外层杠杆 tvr=0.05: 组合整体换手锁到 5-7%, 慢腿收益流保留。"
          "若 R 保持 2.5-2.8%, 则 R/TO 0.40-0.50 => Margin 8-10bps, 是战役首个进入 10bps 区间的组合。"},

  {"id": "x29_outer_tvr04",
   "expr": f"group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.04), subindustry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L1 变体 tvr=0.04: 换手再压一档 (TO 4-5.5%), R/TO 再抬 25%。"
          "若 R 守得住 2.5%, R/TO ~0.55 => Margin 11bps。"},

  {"id": "x29_outer_tvr03",
   "expr": f"group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.03), subindustry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L1 极限档 tvr=0.03: 探本结构的换手下界。若 R 塌陷 (说明快腿贡献被压死), 则说明 R/TO 存在内部最优点, "
          "该槽即拐点判定。"},

  {"id": "x29_outer_tvr05_quantile",
   "expr": f"quantile(group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.05), subindustry), driver=\"gaussian\")",
   "ops": 6, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L3 账本形状: quantile(gaussian) 把权重推向两端, 战役已证可抬 R/TO (w21_q_tvr12: Fit 0.62 全战役最高, Mgn 8.61bps)。"
          "与外层换手杠杆叠加, 是 Mgn>=15bps 的最强赌注。"},

  {"id": "x29_outer_tvr05_sp15",
   "expr": f"signed_power(group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.05), subindustry), 1.5)",
   "ops": 6, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L3 变体: signed_power(1.5) 放大双侧尾部 (Labs 图1: 有效 alpha 集中在 |value|>0.015 的双尾), "
          "中间区仓位极小 ⇒ 单位换手收益上升。"},

  {"id": "x29_three_layer",
   "expr": f"group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay({R_RET}, target_tvr=0.10), ts_target_tvr_decay({NEG_PE_ZS}, target_tvr=0.05)), target_tvr=0.05), subindustry)",
   "ops": 7, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L2 三层 tvr: 快腿 tvr0.10 (保住它的信息量)、慢腿 tvr0.05 (把它自己的季度调仓节奏平滑下来, "
          "慢腿平滑不杀信号 —— 季度值不像每日重训的快腿)、外层组合 tvr0.05 (统一锁定换手)。"
          "每个期限坐在自己的自然节奏上。"},

  {"id": "x29_outer_tvr05_weighted_slow",
   "expr": f"group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay({R_RET}, target_tvr=0.08), multiply({NEG_PE_ZS}, 2.0)), target_tvr=0.05), subindustry)",
   "ops": 6, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L4 慢腿权重放大 2x: 慢腿是独立收益流且换手低, 加大其权重可在**外层锁住换手**的前提下抬 R。"
          "经济含义: 订单簿预测 (20 日) 的信息半衰期短, 估值再定价 (季度) 的半衰期长, 二者按各自信息含量配权, "
          "而不是等权。"},

  {"id": "x29_outer_tvr05_ind",
   "expr": f"group_zscore(ts_target_tvr_decay({CORE08}, target_tvr=0.05), industry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "L4 中性化扫描 (外层 group=industry 而非 subindustry): 估值腿是估值因子, "
          "战役已证中性化偏好随腿而变 (2 日期腿偏爱 INDUSTRY: R 4.84% vs STAT 2.50%)。"
          "本槽与 x29_outer_tvr05 配对 (唯一差别是外层 group 参数), 隔离外层分组粒度的影响。平台 neutralization 保持 STATISTICAL。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W29['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W29, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W29['items'])} items)")
    for it in W29["items"]:
        print(f"  {it['id']:<26} fields={len(it.get('fields') or [])} neut={it.get('neutralization','STAT')} {it['expr'][:96]}")
