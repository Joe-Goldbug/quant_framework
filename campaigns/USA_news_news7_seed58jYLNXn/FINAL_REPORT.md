# 58jYLNXn 定向处方攻坚 — 终审报告（AEGIS 种子因子定向优化模式）

**种子**：`58jYLNXn` · USA / news7 / delay 1 / TOP1000 · 必用字段 `headline_positive_term_count_v2`

**母本表达式**：`hump(signed_power(group_zscore(ts_mean(s_log_1p(headline_positive_term_count_v2) * headline_positive_score_value_v2 / (ts_mean(headline_news_mention_count_v2, 30) + 0.1), 5), sector), 1.6), hump=0.003)`

**母本病灶**：Sharpe 1.03 < 1.58 · Fitness 0.60 < 1.00 · Margin 6.9bps < 10bps · 多头 111 / 空头 716（书严重偏斜）· Investability Sharpe 0.55


> 门禁：`quant_framework/core/gatekeeper.py`（Step1 |Sharpe|≥1.0 → Step2 合规 → Final Sharpe≥1.58 / Fitness≥1.00 / Margin≥10bps / TO∈[5%,50%] / fail_num=0）


## Wave 1 — 病灶直击处方（语调重构）

settings：decay=20 · neutralization=SECTOR · truncation=0.05 · nanHandling=OFF

| 变体 | Sharpe | Fitness | TO% | Margin(bp) | Ret% | L/S | 2Y Sharpe | 平台 fail |
|---|---|---|---|---|---|---|---|---|
| EXPLORATION_INTENSITY_PER_ARTICLE | 0.29 | 0.09 | 13.3 | 1.85 | 1.24 | 176/440 | 0.94 | 3 |
| EXPLORATION_NET_TONE_SPREAD | 0.03 | 0.00 | 64.2 | 0.05 | 0.17 | 170/133 | -0.32 | 5 |
| EXPLORATION_LOG_ODDS_TONE | -0.04 | -0.00 | 38.1 | -0.11 | -0.21 | 240/189 | -0.61 | 4 |
| EXPLORATION_SURPRISE_X_ATTENTION | -0.07 | -0.01 | 104.6 | -0.11 | -0.59 | 40/43 | 0.55 | 6 |
| EVOLUTION_MOTHER_HALFLIFE_DECAY | 0.34 | 0.11 | 11.5 | 2.47 | 1.43 | 383/584 | 1.21 | 3 |
| EVOLUTION_MOTHER_WINSOR_MEDIAN_BASE | 0.41 | 0.13 | 21.8 | 2.14 | 2.33 | 337/543 | 1.43 | 3 |
| EVOLUTION_TONE_PERSISTENCE_IR | 0.24 | 0.07 | 11.3 | 2.11 | 1.20 | 176/396 | 0.63 | 3 |
| EVOLUTION_EVENT_HOLD_TRADE_WHEN | 0.46 | 0.09 | 97.5 | 0.69 | 3.36 | 110/88 | -0.24 | 4 |

**本波最佳**：`EVOLUTION_EVENT_HOLD_TRADE_WHEN` → alpha `pwvLYOQo` · Sharpe 0.46 · Fitness 0.09 · TO 97.5% · Margin 0.69bps


## Wave 2 — 母本单因子消融网格

settings：decay=20 · neutralization=SECTOR · truncation=0.05 · nanHandling=OFF

| 变体 | Sharpe | Fitness | TO% | Margin(bp) | Ret% | L/S | 2Y Sharpe | 平台 fail |
|---|---|---|---|---|---|---|---|---|
| ABL_BASE_SECTOR_ZSCORE | 1.03 | 0.58 | 22.2 | 6.25 | 6.93 | 95/732 | 1.98 | 2 |
| ABL_WINSORIZE_NOT_POWER | 1.04 | 0.58 | 21.8 | 6.28 | 6.85 | 104/723 | 1.92 | 2 |
| HALFLIFE_EXP_DECAY10 | 0.79 | 0.49 | 12.4 | 7.66 | 4.74 | 124/832 | 1.80 | 2 |
| FRESHNESS_EXP_DECAY5 | 0.85 | 0.44 | 20.2 | 5.24 | 5.29 | 130/743 | 2.02 | 2 |
| SINK_SUBINDUSTRY | 0.48 | 0.14 | 42.2 | 1.61 | 3.39 | 56/206 | 0.80 | 4 |
| SINK_INDUSTRY | 0.65 | 0.24 | 33.8 | 2.65 | 4.47 | 78/461 | 1.13 | 4 |
| NET_BUZZ_PER_ATTENTION | 0.71 | 0.35 | 23.7 | 4.83 | 5.72 | 573/304 | 0.53 | 3 |
| EVENT_HOLD_MOTHER | 0.76 | 0.45 | 14.4 | 6.90 | 4.98 | 113/846 | 1.75 | 2 |

**本波最佳**：`ABL_WINSORIZE_NOT_POWER` → alpha `rKdxp7dJ` · Sharpe 1.04 · Fitness 0.58 · TO 21.8% · Margin 6.28bps


## Wave 3 — alpha 源头四条线索

settings：decay=20 · neutralization=SECTOR · truncation=0.05 · nanHandling=OFF

| 变体 | Sharpe | Fitness | TO% | Margin(bp) | Ret% | L/S | 2Y Sharpe | 平台 fail |
|---|---|---|---|---|---|---|---|---|
| MARKET_ZSCORE_NO_GROUP | 1.01 | 0.64 | 20.0 | 8.04 | 8.03 | 104/778 | 1.77 | 2 |
| BASELINE_60D | 1.04 | 0.58 | 22.2 | 6.18 | 6.86 | 97/730 | 2.08 | 2 |
| BASELINE_120D | 1.02 | 0.56 | 22.2 | 6.10 | 6.77 | 98/729 | 2.06 | 2 |
| COUNT_X_SIGNED_TONE | 0.92 | 0.49 | 22.5 | 5.70 | 6.41 | 94/729 | 1.74 | 2 |
| LOG_PER_ARTICLE_RATIO | 0.83 | 0.40 | 21.5 | 4.67 | 5.01 | 135/691 | 1.82 | 2 |
| GROUP_RANK_SECTOR | 0.60 | 0.26 | 17.6 | 3.77 | 3.31 | 161/719 | 1.44 | 3 |
| IR_CORE_SECTOR | 0.39 | 0.17 | 8.1 | 5.72 | 2.33 | 148/831 | 0.69 | 3 |
| PSV_AS_OUTER_WEIGHT | -0.04 | -0.00 | 117.9 | -0.10 | -0.56 | 25/305 | 1.05 | 5 |

**本波最佳**：`BASELINE_60D` → alpha `vROQ8rRa` · Sharpe 1.04 · Fitness 0.58 · TO 22.2% · Margin 6.18bps


## Wave 4 — decay 20→8 平滑度攻坚

settings：decay=8 · neutralization=SECTOR · truncation=0.05 · nanHandling=OFF

| 变体 | Sharpe | Fitness | TO% | Margin(bp) | Ret% | L/S | 2Y Sharpe | 平台 fail |
|---|---|---|---|---|---|---|---|---|
| MARKET_Z_DECAY8_MEAN5 | 1.06 | 0.60 | 28.0 | 6.44 | 9.02 | 85/797 | 2.10 | 2 |
| MARKET_Z_DECAY8_MEAN10 | 0.80 | 0.54 | 16.9 | 9.14 | 7.75 | 94/874 | 1.39 | 3 |
| MARKET_Z_DECAY8_WINSOR | 1.03 | 0.54 | 27.8 | 5.48 | 7.62 | 91/788 | 2.30 | 2 |
| MARKET_Z_DECAY8_EXP10 | 1.00 | 0.56 | 25.9 | 6.19 | 8.01 | 81/887 | 1.89 | 2 |
| MARKET_Z_DECAY8_BASE60 | 1.08 | 0.61 | 27.9 | 6.37 | 8.90 | 86/795 | 2.16 | 2 |
| SECTOR_Z_DECAY8 | 1.00 | 0.50 | 28.4 | 5.04 | 7.16 | 69/758 | 2.02 | 2 |
| MARKET_Z_DECAY8_MEAN20 | 0.74 | 0.51 | 10.2 | 11.69 | 5.95 | 119/884 | 1.12 | 3 |
| MARKET_Z_DECAY8_BASE90 | 1.11 | 0.63 | 28.0 | 6.54 | 9.16 | 86/795 | 2.22 | 2 |

**本波最佳**：`MARKET_Z_DECAY8_BASE90` → alpha `omod5OXb` · Sharpe 1.11 · Fitness 0.63 · TO 28.0% · Margin 6.54bps


## 四波次汇总（最佳变体）

| 波次 | 最佳变体 | alpha | Sharpe | Fitness | TO% | Margin(bp) |
|---|---|---|---|---|---|---|
| Wave 1 | EVOLUTION_EVENT_HOLD_TRADE_WHEN | pwvLYOQo | 0.46 | 0.09 | 97.5 | 0.69 |
| Wave 2 | ABL_WINSORIZE_NOT_POWER | rKdxp7dJ | 1.04 | 0.58 | 21.8 | 6.28 |
| Wave 3 | BASELINE_60D | vROQ8rRa | 1.04 | 0.58 | 22.2 | 6.18 |
| Wave 4 | MARKET_Z_DECAY8_BASE90 | omod5OXb | 1.11 | 0.63 | 28.0 | 6.54 |

## 杠杆归因结论（32 条回测的净结论）

| 杠杆 | 效应 | 证据 |
|---|---|---|
| `hump` + `signed_power` 移除 | **≈ 0** | 消融基准 1.03 vs 母本 1.03（W2#1） |
| `winsorize(std=3/4)` 替尾巴 | **≈ 0（decay20）/ −0.03（decay8）** | 1.04 / 1.03 |
| 中性化下沉 subindustry | **−0.55（严重负）** | 0.48（W2#5）；industry 0.65 |
| 指数半衰期 / 缩短记忆窗 | **−0.24 ~ −0.28** | 0.79（exp10）/ 0.85（exp5） |
| 10 / 20 日均值窗 | **−0.26 ~ −0.32** | 0.80 / 0.74（W4#2、#7） |
| IR / ts_rank 重排（质量化） | **−0.4 ~ −0.6** | 0.39 / 0.60 |
| 语调比率家族（pos−neg、log-odds、pos-share） | **−0.6 ~ −1.1（全灭）** | 0.03 ~ 0.46（W1 全批） |
| 有符号语调 × 词量强度 | −0.11 | 0.92（W3#4） |
| 全市场 zscore（替代 group_zscore） | **+0.04 Sharpe，+1.8bps Margin，+1.1pt 收益** | 1.01 / 0.64 / 8.04bps（W3#1） |
| 关注度基线 30→60→90 日 | **+0.02 → +0.05** | 1.06 → 1.08 → 1.11（W4） |
| settings.decay 20→8 | **+0.05** | 1.01→1.06（market_z）；1.03→1.00（sector_z） |
| 事件门控 trade_when(NMC>0) | −0.27 Sharpe，但 Margin 6.9bps、TO 14.4% | 0.76（W2#8） |

**物理结论**：母本 alpha 的唯一有效载体是「关注度归一化的正向词量 **level** 信号 + 短均值窗（5日）+ 全市场 zscore + 长关注度基线」。
任何把信号改写为语调比率、时间序列重排、或下沉到细颗粒度中性化的处方，都会摧毁 alpha——
因为母本的收益本质来自「被正面新闻持续超额覆盖」的较宽倾斜，而非行业内精细选股。

## 生产门禁终审（Final Gate）

- Step 1（|Sharpe|≥1.0）：W1 **全批熔断**；W2/W3/W4 **通过**（最高 1.11）
- Step 2（fail_num=0 且 Margin≥5bps 且 TO≤70%）：**四波 0/32 通过**
- Final（Sharpe≥1.58 / Fitness≥1.00 / Margin≥10bps / TO∈[5%,50%]）：**0/32 通过**

**最佳候选**：`MARKET_Z_DECAY8_BASE90` = Sharpe 1.11 / Fitness 0.63 / TO 28.0% / Margin 6.54bps（alpha id 见上表）
——距 1.58 仍差 0.47，距 Fitness 1.00 差 0.37，距 Margin 10bps 差 3.5bps。**不可提交。**

## 建议下一步（不在本次授权范围，需另行立项）

1. **换锚**：母本空头端 795/880 是「无新闻股」，本质是注意力折价因子，与量价/规模因子高度共线，
   这是 Investability Sharpe 仅 0.55、Margin 卡在 6~8bps 的根因。继续在此表达家族内调参，天化板 ≈1.15。
2. **若坚持 58jYLNXn 血统**：唯一仍有正梯度的方向是「关注度基线继续拉长（120/250 日）+ decay 4~8 + 全市场 zscore」，
   预期上限 1.15~1.20，仍无法过 1.58。
3. **若目标是过门禁**：应改为多字段交互（news7 内 pos/neg/mention 三轴 + subindustry 风险剥离），
   或换金字塔（USA/D1/NEWS 乘数 1.2 已是最优，可考虑 OPTION/ANALYST 未点亮塔）。
