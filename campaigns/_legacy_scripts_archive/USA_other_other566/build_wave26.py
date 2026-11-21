"""build_wave26.py — cross-dataset wave: other566 + other685.

USER CONSTRAINT (2026-11-05): cross one dataset allowed, MUST include theme fields,
2 <= n_fields <= 3, no op limit, must be based on rigorous economic hypothesis,
must backtest to alphas passing all metric thresholds.

SOURCE SELECTION RATIONALE:
  other566 = FinChart order-book-pattern forward-return forecasts. Fast leg:
  high turnover needed for Sharpe, hence R/TO is its structural weakness.
  The seed kqNgXQqd: R=3.04% / TO=13.93% => R/TO=0.218 => Margin 4.37bps.

  The hard gates need Margin >= 15bps => R/TO >= 0.75, plus Sharpe >= 1.65 and
  Fitness >= 1.05 => with TO<12.5% the Fitness denominator locks at 0.125, so
  Fit>=1.05 => Sharpe*sqrt(R/0.125)>=1.05. With R=5.5% and Sh=1.65 -> 1.15 OK.

  => The cross-dataset partner must RAISE RETURNS WITHOUT RAISING TURNOVER.
  A fast leg cannot do that (any smoothing of other566 lowers R and Sh together).
  A SLOW, slow-updating fundamental leg can: it adds a low-turnover return
  stream that is largely orthogonal to the order-book forecast.

  other685 "Enhanced Financial Indicators" = StarMine Earnings Quality + Analyst
  Revisions Model. Chosen because:
    * MATRIX type (cross-sectionally usable; other546/other635/other699/
      sustainable_profit/other545 are all VECTOR -> rejected).
    * 17 fields survive the platform's OS/IS Sharpe>0 filter, ALL at 0 users /
      0 alphas -> maximally cold, minimal ProdCorr.
    * Quarterly/analyst-estimate update cadence -> structurally low turnover.
    * Information source is ORTHOGONAL to FinChart: fundamental cash-flow
      quality + analyst revisions vs order-book chart patterns.

  Rejected alternative other580 (ETF holdings change): 403 fields, mechanism is
  a passive-flow proxy rather than an independent information source, and its
  holdings data is a derivative of the same price action other566 already prices.

ECONOMIC MECHANISMS (8 slots, each with a distinct hypothesis):
  M1. CONSENSUS STACKING: an order-book forecast AND an analyst-revision
      forecast both bullish => two independent information sets confirm.
  M2. VALUE-WEIGHTED FORECAST: the order-book forecast is only credible when
      the stock is not already richly priced vs SmartEstimate -> multiply by a
      value-rank that is always positive (rank in [0,1], so no sign flip).
  M3. REVISION-WEIGHTED FORECAST: the order-book forecast is a fast, noisy
      read on 20-day forward returns; analyst revisions (SmartEstimate growth
      next-vs-this-year) are the slow, sticky prior on the same quantity.
      Weight the fast signal by the slow prior's strength.
  M4. RELATIVE VALUE: when the analyst/valuation view disagrees with the
      order-book view, one of them is stale -> trade the divergence.
  M5. CASH-FLOW QUALITY: FCF/EV yield is a cash-based value measure that
      survives accounting manipulation; combine with the order-book forecast
      that measures near-term flow.
  M6. PASSIVE FLOW (other580): ETF holding changes measure institutional
      rebalancing pressure.
  M7. PURE other685 BASELINE (single-field control): measures the partner leg
      alone, so the cross-dataset combinations can be attributed.
  M8. OPERATING-PROFIT TREND: CFO/EV yield level x its trend = improving
      cash generation, a slow fundamental momentum orthogonal to flow.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- other566 (theme leg, fast order-book forecast) ----
R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
RET2 = "oth566_return"
P2 = "oth566_prob_2"

# ---- other685 (partner leg, slow StarMine fundamental/analyst) ----
# value: SmartEstimate earnings yield (E/P) for FY1  -- cov 0.9964, 9u/18a
EY_SMARTTEST = "earnings_yield_smartest_fy1"
# value percentile vs industry (0-100) -- cov 0.9947, 0u/0a
EY_IND_PCTL = "earnings_yield_industry_percentile_fy1"
# analyst revision: SmartEstimate growth next year vs this year -- cov 0.9677, 1u/2a
GROW_NEXT = "smartest_growth_next_vs_this_year_earnings"
# valuation vs history: current P/E minus median historical P/E -- cov 0.9961, 7u/10a
PE_VS_HIST = "diff_current_vs_hist_pe_ratio"
# cash-flow quality: FCF/EV yield -- cov 0.6923, 0u/0a
FCF_EV = "oth685_81v"
# cash-flow quality: CFO/EV yield -- cov 0.6815, 0u/0a
CFO_EV = "oth685_91v"
# operating cash-flow return on invested capital, 3y -- cov 0.5939, 0u/0a
CFROI3 = "oth685_cfroi_3"
# trend in cash-flow ROI -- cov 0.5695, 0u/0a
CFROI_TRN = "oth685_cfroitrn"
# EPS growth 5y -- cov 0.3608, 0u/0a
EPSGROW5 = "oth685_epsgrow5"

W26 = {
 "batch": 26, "family": "cross_dataset_other566_plus_other685_starmine",
 "hypothesis": (
   "波次 26 (跨数据集, 满足 USA/D1 TOP1000 Theme: other685 category=other => 同属 USA/D1/OTHER 金字塔, 乘数 1.4, "
   "且 MATCHES_THEMES 确认 USA/D1 TOP1000 Theme 2.0x)。"
   "核心代数诊断: 种子 kqNgXQqd R=3.04%/TO=13.93% => R/TO=0.218 => Margin 4.37bps; "
   "而五门联合 (Sh>=1.65 ∧ Fit>=1.05 ∧ Mgn>=15bps ∧ Cluster>=1.60 ∧ R>=5.5%>DD<=2.8%) 要求 R/TO>=0.75。"
   "战役已证: other566 快腿的任何平滑都同比压低 returns 与 sharpe (ts_mean/ts_zscore/ts_av_diff 三路全崩), "
   "故快腿单独无法把 R/TO 从 0.218 推到 0.75 —— **必须引入一个「不抬换手而抬 returns」的慢腿**。"
   "other685 (StarMine 盈利质量 + 分析师修正) 正是这样一个慢腿: 季度/分析师预期更新节奏 ⇒ 结构低换手; "
   "17 个 Sharpe>0 字段全部 0 用户 0 alpha ⇒ 极冷源; 信息源 (现金流质量 + 分析师预期修正) 与 FinChart "
   "订单簿形态在经济学上正交 (一个测公司质地与预期, 一个测交易层面的微观结构)。"
   "八条机制各自独立: 共识叠加 / 价值加权 / 修正加权 / 相对价值 / 现金流质量 / 被动资金流 / 纯慢腿基线 / 经营现金流趋势。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [
  {"id": "x26_cons_ey",
   "expr": f"group_zscore(multiply(group_zscore({R_RET}, subindustry), rank({EY_SMARTTEST})), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:earnings_yield_smartest_fy1"],
   "why": "M1 共识叠加 (最简版): 订单簿看多预测 x SmartEstimate 盈利收益率 (0-100 行业分位的绝对水平经 rank 保号)。"
          "经济含义: 两个正交信息集 (微观结构流向 vs 基本面估值) 同向时信号最强, 提升组合期望收益而不增加换手 —— "
          "盈利收益率是季度慢变量, 权重变化极慢 ⇒ 理论上可拉高 R 而几乎不动 TO。"},

  {"id": "x26_cons_ey_growth",
   "expr": f"group_zscore(multiply(group_zscore({R_RET}, subindustry), rank({GROW_NEXT})), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:smartest_growth_next_vs_this_year_earnings"],
   "why": "M1 变体 (增长侧共识): 用 SmartEstimate 下一财年 vs 本财年盈利增长修正 (分析师预期上修方向) 替代估值水平。"
          "经济含义: 分析师在**主动上修**盈利的公司, 其订单簿看多信号更可能是基本面驱动的真实需求而非噪声。"},

  {"id": "x26_value_weight_ey",
   "expr": f"group_zscore(multiply(group_zscore({R_RET}, subindustry), rank({EY_IND_PCTL})), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:earnings_yield_industry_percentile_fy1"],
   "why": "M2 价值加权: 行业分位 (0-100) 必正, rank 保号不翻转方向, 且天然规避 r20marsi_ret 与 prob_5 的负值符号陷阱。"
          "经济含义: 订单簿预测只有在股票**不昂贵**时才可信 —— 高估值股的看多预测更可能是拥挤交易。"},

  {"id": "x26_revision_weight",
   "expr": f"group_zscore(multiply(group_zscore({RET2}, subindustry), rank({GROW_NEXT})), subindustry)",
   "ops": 4, "fields": ["other566:return", "other685:smartest_growth_next_vs_this_year_earnings"],
   "why": "M3 修正加权: oth566_return (2 日期连续预测, 战役中偏爱 INDUSTRY 中性化) x 分析师增长修正秩。"
          "经济含义: 快信号 (订单簿) 用慢先验 (分析师预期) 加权, 是本战役唯一被证伪过的机制 (B09 置信加权网格 Sh<0.95) "
          "在**跨数据集**上的重试 —— 之前失败是因为同源冷腿, 现在换成正交的基本面腿。"},

  {"id": "x26_relval_divergence",
   "expr": f"group_zscore(subtract(group_zscore({R_RET}, subindustry), group_zscore({EY_IND_PCTL}, subindustry)), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:earnings_yield_industry_percentile_fy1"],
   "why": "M4 相对价值分歧: 订单簿看多但估值贵 (或反之) = 两个信息集冲突, 冲突本身携带信息。"
          "经济含义: 微观结构信号与估值信号的分歧幅度 ≈ 短期资金流对基本面定价的偏离度, 偏向均值回复。"},

  {"id": "x26_cashflow_quality",
   "expr": f"group_zscore(multiply(group_zscore({R_RET}, subindustry), rank({FCF_EV})), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:oth685_81v"],
   "why": "M5 现金流质量: FCF/EV 收益率是**抗盈余操纵**的价值度量 (现金流而非会计利润), 与 StarMine 盈利质量模型同源。"
          "经济含义: 只有现金流质地支撑的订单簿看多信号才值得下注, 权重恒正保号。覆盖率 0.69 限制有效样本, 但 "
          "在 TOP1000 内仍覆盖约 690 只大市值股。"},

  {"id": "x26_pe_history",
   "expr": f"group_zscore(multiply(group_zscore({R_RET}, subindustry), rank({PE_VS_HIST})), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "M2/M5 变体 (估值相对自身历史): 当前 P/E 减历史中位 P/E, 正=相对历史变贵。rank 保号 ⇒ 相对历史便宜的股票"
          "获得更高权重。经济含义: 订单簿预测的兑现概率与估值回归压力成反比 (均值回复风险)。"},

  {"id": "x26_baseline_slow",
   "expr": f"group_zscore({CFROI3}, subindustry)",
   "ops": 2, "fields": ["other685:oth685_cfroi_3"],
   "is_baseline_control": True,
   "why": "M7 纯慢腿基线 (单字段, **对照组而非候选 alpha**): 3 年现金回报投入资本 (CFROI), 纯基本面质量因子。"
          "测量 other685 在 USA/D1/TOP1000 自身的 Sharpe/Margin/换手基线 —— 这是判断跨数据集组合能否抬高 R/TO 的"
          "关键读数: 若该基线本身就低换手高 Sharpe, 则它正是 other566 缺的那条腿; 若 Sharpe 也很差, 说明本数据集"
          "在 TOP1000 同样不可用 (如 insider_feats 的 -0.10 先例)。用户要求的 2~3 字段约束适用于候选 alpha, 此槽按设计仅作基线。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W26['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W26, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W26['items'])} items)")
    for it in W26["items"]:
        n = len(it.get("fields") or [])
        print(f"  {it['id']:<22} fields={n} {it['expr'][:95]}")
