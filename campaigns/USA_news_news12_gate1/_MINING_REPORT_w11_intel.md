# USA_news_news12_gate1 战役全史边界样本情报报告（为 W11 种子优化处方供数）

> 数据源：`campaigns/USA_news_news12_gate1/` 下 45 个 `batch_*_result.json`（360 条目）+ 29 个 `summary_gate*.json` + `corr_recheck_final.json` + `_baseline_final.json`（315 行快照）+ `FINAL_REPORT_v2.md`。
> 挖掘脚本：`_mining_aggregate.py`（聚合）、`_mining_t1t2.py`、`_mining_t3t4.py`、`_mining_t5.py`；中间产物 `_mining_all_rows.json`。全部数字由脚本直读 JSON 得出，未编造。

---

## 0. 口径对账（先读这一节，后面所有计数以此为准）

| 口径 | 行数 | 说明 |
|---|---|---|
| result JSON 总条目 | 360 | 45 文件 × 8 槽 |
| 幻影行（无 alpha_id、无任何指标） | 16 | = `batch_gate1_C` + `batch_gate2_F` 两批连坐取消（研报 §"336 行中 16 行幻影"的实证） |
| 有指标条目 | 344 | 其中 npAXmlmq 重复提交 5 次、ZYm9ebv0 重复 2 次 |
| **去重后唯一有效 alpha** | **339** | 本报告统计口径 |
| 研报口径（42 批×8−16 幻影） | 320 | = 339 − 24（b9/b10/b11 三个补充批，研报与 `_baseline_final.json` 均未收录） |

对账等式：**339 = 320（研报）+ 24（gate1_b9/b10/b11）− 5（跨批重复提交）**。下文每个统计均标注"研报口径内"数量，两类口径不混用。

**CLUSTER_TEST 数值可得性：result JSON 的 `checks.warning[].value` 记录了全部 339 行的 cluster 数值（`summary_*.json` 只有警告名无数值）。研报"仅有记载最高 1.54"不成立——全史最高实为 1.56。**

---

## T1: CLUSTER_TEST 全史分布

### 分布总览（n=339，全部有数值）
- 区间：**−1.52 ~ +1.56**（limit 恒为 1.58，warning 级）
- **CLUSTER ≥ 1.45 共 11 行**（其中研报口径内 7 行，b9 补充批 4 行）
- 分桶：1.5~1.6 档 11 行；1.4~1.5 档 15 行；1.3~1.4 档 27 行；1.2~1.3 档 25 行；1.1~1.2 档 34 行；≤1.0 共 165 行；负值 31 行
- **339/339 行全部带 CLUSTER_TEST 警告**（与研报"320/320 全带"一致，零例外）

### CLUSTER ≥ 1.45 全部 11 行（按 cluster 降序）

| # | alpha_id | CLUSTER | Sh | Fit | TO | Ret | 2Y | sub | rnSh | 表达式（结构缩写） | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3qjKl3Ag | **1.56** | 1.57 | 0.40 | 112.7 | 7.36% | 2.07 | 1.30 | 1.74 | `trade_when(dflc(VHEX)<1, reverse(rank((close−ton_last)/(VHEX+1))), dflc>5)` | gate1_b9 |
| 2 | gJWljwxK | 1.55 | 1.56 | 0.40 | 113.1 | 7.35% | 2.11 | 1.28 | 1.76 | 同上，退出门 `dflc>2` | gate1_b9 |
| 3 | A1QplYkX | 1.55 | 1.57 | 0.40 | 112.7 | 7.35% | 2.08 | 1.29 | 1.74 | 同上，退出门 `dflc>4` | gate1_b9 |
| 4 | npAj7Y3a | 1.54 | 1.53 | 0.39 | 112.8 | 7.19% | 2.09 | 1.25 | 1.71 | 同上，退出门 `dflc>3` | gate1_b9 |
| 5 | mLYNEWjW | 1.54 | 1.59 | 0.41 | 114.6 | 7.52% | 2.03 | 1.39 | 1.86 | `trade_when(dflc<2, reverse(rank((close−ton_last)/(VHEX+1))), 0)` | w10h |
| 6 | 3qjONb3O | 1.48 | 1.62 | 0.41 | 117.8 | 7.67% | 2.11 | 1.28 | 1.85 | `trade_when(dflc<1, reverse(rank((close−ton_last)/bf120(VHEX))), 0)` | w10e |
| 7 | d5K6wxlx | 1.47 | 1.61 | 0.41 | 120.1 | 7.70% | 2.09 | 1.27 | 1.91 | `reverse(rank((close−ton_last)/bf120(VHEX)))` | gate4_N |
| 8 | 9qE3g3WV | 1.47 | 1.61 | 0.41 | 120.1 | 7.70% | 2.09 | 1.27 | 1.91 | 同 7，分母换 `bf120(vec_count(low_price_excursion_stddev))` | gate5_Q |
| 9 | xA1oXobW | 1.47 | 1.61 | 0.41 | 120.1 | 7.70% | 2.09 | 1.27 | 1.91 | 同 7，回填窗口 120→250 | gate5_Q |
| 10 | leMYnJZn（=SH165） | 1.47 | **1.65** | 0.42 | 119.9 | **7.86%** | 2.10 | 1.30 | 1.95 | `trade_when(dflc<2, reverse(rank((close−ton_last)/bf120(VHEX))), 0)` | w10d |
| 11 | 3qjOGPzz | 1.46 | 1.58 | 0.36 | 127.6 | 6.78% | 1.27 | 0.96 | 1.85 | `reverse(ts_rank((close−eod_vwap)/vec_max(VHEX), 250))` | gate9_S2 |

### CLUSTER top5 的共同结构特征（3qjKl3Ag / gJWljwxK / A1QplYkX / npAj7Y3a / mLYNEWjW）

1. **内核完全同一**：`divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1))` —— 注意力稀缺反转的标准内核（close−ton_last 除以 VHEX 事件计数+1）。
2. **壳同一**：`reverse(rank(...))`，算子数 ≤10，字段恰 3 个（news_eod_close / news_ton_last / high_price_excursion_stddev）。
3. **门同一**：`trade_when(less(days_from_last_change(vec_count(VHEX)), 1 或 2), ·, 0)` —— 事件新鲜度门。
4. **前 4 名带"退出门"第三参**：`greater(days_from_last_change(vec_count(VHEX)), 2/3/4/5)`，即"新鲜窗口双门"（进入门 <1 天 + 退出门 >N 天），是全史 cluster 最高的结构；mLYNEWjW 为单门版（<2，第三参 0）。
5. **全部来自 gate1_b9 与 w10h 两个批次**，指标高度同质（Sh 1.53~1.59、TO 112.7~114.6%、Ret 7.19~7.52%、2Y 2.03~2.11）。

### 结构→cluster 的因果读数（对 W11 的直接意义）
- 换分母（bf120 回填）或换窗口（250）**不降 cluster**（1.47 不变）。
- 换壳 `rank→ts_rank(·,250)` 降 cluster 约 −0.15~−0.22（mLYNEWjW 1.54 → 2rjx3ow8 1.32）。
- 换分子 `ton_last→eod_vwap` 降约 −0.10（d5K6wxlx 1.47 → N1eGk79E 1.37）。
- **换字段/换壳最多降到 1.32，距 1.58 限仍有 0.26 缺口；而内核本身把 cluster 钉在 1.47~1.56。cluster 墙是内核级属性，非参数级。**

---

## T2: 无 MATCHES_THEMES 警告的行（重要否定发现）

### warning 组成分布（n=339）
| warning 名称 | 行数 | 占比 |
|---|---|---|
| CLUSTER_TEST | **339** | 100% |
| MATCHES_THEMES | **314** | 92.6% |
| LOW_SHARPE | 25 | 7.4% |
| LOW_FITNESS | 25 | 7.4% |
| LOW_2Y_SHARPE | 24 | 7.1% |
| UNITS | 10 | 2.9% |

### 无 MATCHES_THEMES 的行：25 行（研报口径内 21 行 + b9/b10/b11 补充批 4 行）

**结构情报：这 25 行与"`checks.fail == []`（零硬 fail）"的 25 行是完全同一集合。** 共同画像：
- TO 全部 ≤ 70%（36.6%~69.9%）——全战役低换手簇
- Sh 全部 1.02~1.20（够不到 1.58）
- warning 组合固定为 `LOW_SHARPE + LOW_FITNESS + CLUSTER_TEST`（+LOW_2Y_SHARPE，仅 WjLZbEPN 无 2Y 警告）
- 即：**MATCHES_THEMES 警告的缺席与"零硬 fail"互为充要条件；带 MATCHES_THEMES 的 314 行全部有 ≥1 项硬 fail**

研报口径内 21 行清单（alpha_id | Sh | TO%）：
`LL5wVxv6` 1.10/53.1（E批）、`e76PkJYN` 1.06/37.7（E）、`zqrEKzV1` 1.10/37.2（E）、`ZYm9ebv0` 1.13/37.4（K）、`YPxOGboo` 1.17/37.8（K）、`akV8qbmv` 1.10/37.2（K）、`QPYALbRG` 1.10/37.1（K）、`gJW5z1Pg` 1.11/37.1（N）、`leMYZQJx` 1.15/37.8（O）、`O0Jjqbpq` 1.02/37.6（X）、`3qjOpPxg` 1.13/36.6（Z）、`2rjxp6R6` 1.15/37.0（Z）、`O0JjGzmY` 1.19/37.5（Z）、`0mjLpgQ8` 1.16/37.8（Z）、`6XAQKZgK` 1.07/40.6（T）、`leMYKEJN` 1.07/40.6（T）、`gJW5rGmv` 1.10/37.3（S2）、`6XAQG0Ep` 1.17/58.6（S2）、`GrgNzljG` 1.10/59.1（S3）、`zqrExXzX` 1.10/52.5（w10d）、`gJW5l7ze` 1.10/52.5（w10d）。

补充批 4 行：`Grg2bqlQ` 1.16/69.9（b10）、`WjLZbEPN` 1.09/68.7（b10）、`E5VjpeQm` 1.16/59.5（b11）、`MP0E7qxL` 1.20/68.8（b9）。

CLUSTER_TEST 警告分布：**339/339 全带，零例外**（研报"320/320 全带"在此口径下得到扩展确认）。

---

## T3: 边界样本扫描

### T3a: Ret ≥ 7% 共 53 行（研报口径内 44 行），top10 降序

| # | alpha_id | Ret | Sh | TO | Fit | 2Y | CLUSTER | 表达式 | fail/warn 摘要 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 9qE3b1o2 | **10.15%** | 1.29 | 141.1 | 0.35 | 0.90 | 1.22 | `reverse(rank(divide(vec_avg(main_session_performance_vs_benchmark), vec_avg(main_session_volume_ratio))))` | 5 fail（Sh/Fit/TO/CW/2Y） |
| 2 | e76Po6eM | 9.84% | 0.22 | 2.3 | 0.20 | 0.07 | 0.26 | `reverse(divide(news_mins_20_pct_up, add(news_mins_20_pct_up, news_mins_20_pct_dn)))` | 4 fail；LC/SC=0（信号恒空） |
| 3 | RRAObJVj | 8.93% | 1.26 | 82.9 | 0.41 | 1.72 | 1.21 | `reverse(rank(ts_backfill(divide(add(sub(close,ton_last),sub(close,open)), open), 2)))` | 3 fail |
| 4 | ZYm9NKN1 | 8.82% | 1.29 | 122.6 | 0.35 | 1.68 | 1.24 | `reverse(rank(multiply(news_max_up_ret, subtract(news_eod_close, news_post_vwap))))` | 4 fail |
| 5 | RRAoozwg | 8.67% | 1.25 | 138.0 | 0.31 | 1.48 | 1.26 | `reverse(rank(divide(subtract(close,post_vwap), vec_avg(main_session_volume_ratio))))` | 5 fail |
| 6 | 6XAQQ06P | 8.55% | 1.23 | 137.4 | 0.31 | 1.58 | 1.16 | `reverse(rank(divide(subtract(close,open), vec_avg(main_session_volume_ratio))))` | 5 fail |
| 7 | zqrEEG7G | 8.47% | 1.21 | 136.9 | 0.30 | 1.37 | 1.16 | `reverse(rank(divide(subtract(close,post_vwap), vec_avg(main_session_range_to_atr_ratio))))` | 5 fail |
| 8 | ZYm99z8j | 8.46% | 1.21 | 136.3 | 0.30 | 1.50 | 1.10 | `reverse(rank(divide(subtract(close,open), vec_avg(main_session_range_to_atr_ratio))))` | 5 fail |
| 9 | O0JLNxWg | 8.40% | 1.18 | 71.5 | 0.40 | 1.86 | 1.14 | `reverse(rank(ts_decay_linear(ts_backfill(divide(add(sub(close,ton_last),sub(close,open)),open),2),2)))` | 3 fail |
| 10 | A1Q5jJYe | 8.23% | 0.65 | 121.3 | 0.17 | 1.35 | 0.55 | `reverse(subtract(news_max_up_ret, news_max_dn_ret))` | 4 fail |

**读数**：高 Ret 与高 TO 强绑定（top10 中 7 行 TO>120%）；最高 Ret 的 9qE3b1o2 已实测 ProdCorr **0.742（超限 fail）**；唯一低 TO 高 Ret 样本 O0JLNxWg（TO71.5%/Ret8.40%/2Y1.86）仍未过 Sh。

### T3b: TO ≤ 85% 且 Sh ≥ 1.2 —— 共 5 行，**全部来自 b9/b10/b11 补充批**（研报 320 口径内 0 行）

| # | alpha_id | Sh | TO | Fit | Ret | 2Y | CLUSTER | 表达式 | fail | warn |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | QPYxb9vp | 1.43 | 84.1 | 0.40 | 6.66% | 1.41 | 1.37 | `reverse(rank(ts_backfill((close−ton_last)/(VHEX+1), 2)))` | 4 | 2 |
| 2 | XgR3b8al | 1.37 | 72.0 | 0.40 | 6.20% | 1.46 | 1.26 | `reverse(rank(ts_decay_linear(ts_backfill((close−ton_last)/(VHEX+1), 2), 2)))` | 4 | 2 |
| 3 | j2epA53o | 1.30 | 84.2 | 0.35 | 6.24% | 1.18 | 1.35 | `reverse(quantile(ts_backfill((close−ton_last)/(VHEX+1), 2)))` | 4 | 2 |
| 4 | RRAObJVj | 1.26 | 82.9 | 0.41 | 8.93% | 1.72 | 1.21 | `reverse(rank(ts_backfill((close−ton_last+close−open)/open, 2)))` | 3 | 2 |
| 5 | MP0E7qxL | 1.20 | **68.8** | 0.33 | 5.32% | 1.16 | 1.23 | `reverse(rank(ts_backfill((close−ton_last)/(VHEX+1), 3)))` | **0（空）** | 4 |

**读数**：研报"320 行内 TO≤85% 且 Sh≥1.2 为空"成立；真正的低换手高 Sharpe 边界样本只存在于研报未收录的 b9/b10/b11。共同手法是 `ts_backfill(内核, 2~3 天)` 平滑。MP0E7qxL 是**全战役唯一 checks.fail 为空的行**（TO 68.8%、margin 1.54bps 为全战役最高之一），但 Sh 1.20/2Y 1.16 仍三警告。

### T3c: 2Y ≥ 2.0 共 33 行（研报口径内 29 行），按 2Y 降序 top12

| # | alpha_id | 2Y | Sh | TO | Ret | CLUSTER | 表达式摘要 |
|---|---|---|---|---|---|---|---|
| 1 | WjLRmpWx | **2.52** | 1.03 | 134.7 | 8.19% | 0.41 | `reverse(multiply(rank(max_up_amt/(up+dn)), rank(news_open_gap)))` |
| 2 | MP0n3vlM | 2.40 | 1.41 | 113.7 | 7.69% | 1.27 | `trade_when(dflc<5, reverse(rank((close−open)/(VHEX+1))), -1)` |
| 3 | xA1oN7pl | 2.35 | 1.42 | 113.8 | 7.78% | 1.30 | `reverse(rank((close−open)/(VHEX+1)))` |
| 4 | 9qE3k7mr | 2.35 | 1.40 | 114.6 | 7.60% | 1.33 | `reverse(rank((close−post_vwap)/(VHEX+1)))` |
| 5 | 9qE3NOV9 | 2.34 | 1.46 | 113.4 | 7.94% | 1.36 | `trade_when(dflc<2, reverse(rank((close−open)/(VHEX+1))), 0)` |
| 6 | bl8gOK7q | 2.24 | 1.45 | 118.8 | 8.09% | 1.27 | `reverse(rank((close−open)/bf120(VHEX)))` |
| 7 | j2eJOrxE | 2.24 | 1.46 | 119.7 | 8.14% | 1.32 | `reverse(rank((close−post_vwap)/bf120(VHEX)))` |
| 8 | rKdwenQa | 2.20 | 0.99 | 108.3 | 4.78% | 1.00 | `reverse(ts_rank((close−ton_high)/(VHEX+1), 250))` |
| 9 | zqrEb7wO | 2.19 | 1.46 | 112.4 | 6.97% | 1.32 | `trade_when(dflc<2, reverse(ts_rank((close−ton_last)/(VHEX+1),250)), -1)` |
| 10 | 2rjx3ow8 | 2.19 | 1.46 | 112.4 | 6.97% | 1.32 | 同 9，第三参 `0`（与 9 指标完全一致，实证 0≡−1） |
| 11 | KPmpWMON | 2.17 | 1.20 | 111.9 | 6.66% | 1.04 | `trade_when(dflc<2, reverse(ts_rank((close−open)/(VHEX+1),250)), 0)` |
| 12 | YPxOX1QA | 2.16 | 1.57 | 118.1 | 7.36% | 1.34 | `reverse(ts_rank((close−ton_last)/bf120(VHEX), 250))` |

**读数**：2Y 天花板 2.52（WjLRmpWx，双 rank 乘积但 Sh 仅 1.03）；2Y≥2.0 与 Sh≥1.46 可同时成立（9qE3NOV9/bl8gOK7q/j2eJOrxE/zqrEb7wO/2rjx3ow8），但无一例 TO<85%。**"2Y 已过线"的行共 33 个，全部卡在 Fit/TO。**

---

## T4: 5 条关键 alpha 全字段读数

全部为 USA/TOP1000/delay1/decay6/2014-01-01~2023-12-31/IS/UNSUBMITTED。

### 1) 2rjx3ow8（w10h，母本+ts_rank250 壳）
- 表达式：`trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(ts_rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 250)), 0)`
- sharpe 1.46 | fitness 0.36 | turnover 1.124 (112.4%) | returns 0.0697 (6.97%) | two_year_sharpe **2.19** | sub_universe_sharpe 1.18 | longCount 310 | shortCount 309 | margin 0.000124 | risk_neutralized_sharpe **1.89** | investability_sharpe 1.27 | drawdown 0.0446 | CLUSTER 1.32
- checks.fail: LOW_SHARPE, LOW_FITNESS, HIGH_TURNOVER；checks.warning: CLUSTER_TEST(1.32<1.58), MATCHES_THEMES；ra_failed=true
- 中性化 INDUSTRY。与 zqrEb7wO（gate8_G，第三参 −1）**逐字段完全一致**——trade_when 第三参 0≡−1 的又一实证。

### 2) mLYNEWjW（w10h 槽1，家族最优交付候选）
- 表达式：`trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0)`
- sharpe **1.59** | fitness 0.41 | turnover 1.1459 (114.6%) | returns 0.0752 (7.52%) | two_year_sharpe 2.03 | sub_universe_sharpe **1.39** | longCount 312 | shortCount 307 | margin 0.000131 | risk_neutralized_sharpe 1.86 | investability_sharpe 1.42 | drawdown 0.0544 | CLUSTER **1.54**
- checks.fail: **仅 LOW_FITNESS + HIGH_TURNOVER（2 项，全战役 fail 数最少的 4 行之一，且是唯一 Sharpe 过线的 2-fail 行）**；warning: CLUSTER_TEST(1.54), MATCHES_THEMES；ra_failed=true；SELF_CORRELATION/DATA_DIVERSITY/PROD_CORRELATION/REGULAR_SUBMISSION 均 pending（未提交未评）
- 中性化 INDUSTRY。与 2rjx3ow8 唯一差异：`ts_rank(·,250)` → `rank`——Sh +0.13、CLUSTER +0.22、2Y −0.16。

### 3) leMYnJZn（=SH165，w10d 槽5，v1 版最佳）
- 表达式：`trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120)))), 0)`
- sharpe **1.65（全战役最高）** | fitness 0.42 | turnover 1.1985 (119.9%) | returns **0.0786 (7.86%，全战役最高)** | two_year_sharpe **2.10** | sub_universe_sharpe 1.30 | longCount 299 | shortCount 294 | margin 0.000131 | risk_neutralized_sharpe **1.95** | investability_sharpe 1.39 | drawdown 0.0571 | CLUSTER 1.47
- checks.fail: LOW_FITNESS, HIGH_TURNOVER, CONCENTRATED_WEIGHT；warning: CLUSTER_TEST(1.47), MATCHES_THEMES；ra_failed=true；中性化 INDUSTRY
- 与母本 d5K6wxlx 唯一差异：加 `trade_when(dflc<2, ·, 0)` 新鲜门——Sh +0.04、Ret +0.16pp、2Y +0.01、TO −0.15pp（四项全面微升，CW 不变）。

### 4) d5K6wxlx（家族冠军）
- 表达式：`reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120))))`
- sharpe 1.61 | fitness 0.41 | turnover 1.2014 (120.1%) | returns 0.077 (7.70%) | two_year_sharpe 2.09 | sub_universe_sharpe 1.27 | longCount 299 | shortCount 294 | margin 0.000128 | risk_neutralized_sharpe 1.91 | investability_sharpe 1.38 | drawdown 0.0597 | CLUSTER 1.47
- checks.fail: LOW_FITNESS, HIGH_TURNOVER, CONCENTRATED_WEIGHT；warning: CLUSTER_TEST(1.47), MATCHES_THEMES；ra_failed=true；中性化 INDUSTRY
- **corr_recheck_final.json 实读：ProdCorr max=0.7033 vs 阈值 0.70——超限 0.0033（差 0.0033 即 fail）**；SelfCorr 未测。

### 5) N1eGk79E（锚，gate5_R）
- 表达式：`reverse(rank(divide(subtract(news_eod_close, news_eod_vwap), ts_backfill(vec_count(high_price_excursion_stddev), 120))))`
- sharpe 1.63 | fitness 0.31 | turnover 1.1688 (116.9%) | returns 0.0426 (4.26%) | two_year_sharpe **0.58** | sub_universe_sharpe 1.06 | longCount **519** | shortCount **516** | margin 7.3e-05 | risk_neutralized_sharpe **None（BRAIN 未返回该字段）** | investability_sharpe 1.33 | drawdown **0.0305** | CLUSTER 1.37
- checks.fail: LOW_FITNESS, HIGH_TURNOVER, CONCENTRATED_WEIGHT, LOW_2Y_SHARPE（4 项）；warning: CLUSTER_TEST(1.37), MATCHES_THEMES；ra_failed=true；**中性化 STATISTICAL（五条中唯一非 INDUSTRY）**
- **corr_recheck_final.json 实读：ProdCorr max=0.5589（pass）、SelfCorr max=0.1521（pass）——五条中唯一双 corr 全过的。** 代价是 Ret 仅 4.26%、2Y 0.58、持仓 519/516（接近全市场）。

---

## T5: 算子使用史（n=339，按行去重计）

### 已使用算子 27 种（次数）
reverse 329 · divide 302 · subtract 220 · add 205 · rank 149 · vec_count 146 · ts_backfill 118 · trade_when 74 · ts_rank 69 · vec_avg 52 · less 43 · days_from_last_change 42 · group_rank 36 · greater 35 · ts_sum 25 · ts_mean 21 · multiply 15 · ts_decay_linear 15 · vec_max 11 · group_mean 4 · abs 3 · ts_zscore 2 · quantile 2 · ts_delta 2 · ts_std_dev 1 · vec_sum 1 · group_zscore 1

### 用户点名的白名单算子使用状态
| 算子 | 次数 | | 算子 | 次数 |
|---|---|---|---|---|
| rank | 149 | | winsorize | **0（从未用）** |
| reverse | 329 | | ts_median | **0** |
| ts_rank | 69 | | ts_decay_exp_window | **0** |
| ts_mean | 21 | | ts_sum | 25 |
| ts_decay_linear | 15 | | group_* | 41（rank36/mean4/zscore1） |
| ts_backfill | 118 | | trade_when | 74 |

### 从未使用的白名单算子（novelty 空间，共 66 个；标注确定性）
- **高确定性未用（BRAIN 标准算子）**：zscore, normalize, scale, winsorize, ts_median, ts_min, ts_max, ts_delay, ts_decay_exp_window, ts_scale, ts_av_diff, ts_returns, ts_covariance, ts_correlation, ts_regression, ts_theilsen, ts_kurtosis, ts_skewness, ts_moment, ts_entropy, ts_percentage, ts_step, ts_ir, group_sum, group_max, group_min, group_count, group_std_dev, group_backfill, if_else, filter, is_nan, power, log, sqrt, sign, exp, vec_min, vec_ir, vec_range, vec_norm, vec_choose, vec_stddev, ts_product, ts_arg_min, ts_arg_max
- **待向 BRAIN 验证存在性后可用**：sigmoid, tanh, inverse, floor, ceil, round, vec_prod, vec_skewness, vec_kurtosis, truncate, or, and, not
- **框架 FORBIDDEN 检查**：signed_power / hump / group_neutralize **全战役 0 次使用（clean）**

### 结构性观察
- 全战役表达式空间极度收敛：`reverse(rank((close−X)/(VHEX 或 bf120(VHEX) 或 VHEX+1)))` 一个骨架 + 少量分子/分母/壳替换，横跨 ~200 行。
- 分组算子仅 3 种（group_rank/mean/zscore，共 41 次）且集中在 S2_INDUSTRY 批次；其余 10 种 group_* 全未用。
- 非线性/数学算子（power/log/sqrt/sign/exp）与全部 ts_* 统计族（kurtosis/skewness/entropy/theilsen/regression/correlation/covariance）**零使用**——这是最大的 novelty 空间，但也意味着这些算子对本数据族完全无历史证据支撑。

---

## 对 W11 处方的 3 条最重要情报

**情报 1：CLUSTER_TEST 墙是内核级属性，且全史记录比研报高 0.02。**
339/339 行全带 CLUSTER_TEST 警告；≥1.45 的 11 行全部是同一注意力稀缺内核（`(close−ton_last)/(VHEX 计数或 bf120)` + `reverse(rank)` + dflc 新鲜门）的参数变体。最高 **1.56（3qjKl3Ag，gate1_b9，带退出门 dflc>5 的双门版）**——研报记载的 1.54 只是 w10h 单门版。换壳（ts_rank250）最多降到 1.32、换分子（eod_vwap）降到 1.37、换回填窗口无效（1.47 不动）。**若 W11  mandate 要求零警告，唯一出路是换数据内核（新字段组合），而不是继续在该骨架上调参——该骨架的 cluster 下界约 1.32，距 1.58 仍差 0.26。**

**情报 2：研报"解集为空"的结论在 320 口径内成立，但 b9/b10/b11 三个补充批藏着研报未分析的边界样本群——"零硬 fail"与"无 MATCHES_THEMES"是同一批 25 行，且全部是 TO≤70% 的低换手簇。**
- 全战役**唯一 checks.fail==[] 的行是 MP0E7qxL**（Sh 1.20/TO 68.8%/Ret 5.32%/margin 1.54bps，w10h 母本的 ts_backfill(·,3) 平滑版），只差 Sh 0.38。
- TO≤85% 且 Sh≥1.2 的 5 行**全部**来自 b9/b10/b11，共同手法是 `ts_backfill(内核, 2~3)`：最好者 QPYxb9vp（Sh 1.43/TO 84.1%/CLUSTER 1.37，全战役 Sh 与低 TO 的最佳折中）。
- **对 W11 的含义**：降 TO 不必付"Sh 崩到 0.8"的代价——ts_backfill 2~3 天平滑可在 Sh≥1.2 前提下把 TO 压到 70~85%；但 Sh 天花板（该平滑族 1.43）仍够不到 1.58。若要同时过 Sh/TO/2Y/Fit，需把平滑族与高 cluster 内核解耦（平滑族 CLUSTER 1.21~1.37，反而低于母本）。

**情报 3：五条关键 alpha 的相关性风险已实测分层——d5K6wxlx 的 ProdCorr 只超限 0.0033，N1eGk79E 是唯一双 corr 全过的锚。**
- d5K6wxlx ProdCorr **0.7033 vs 0.70**（超 0.0033），YPxOX1QA 0.7416、9qE3b1o2 0.742（后者同时是全史 Ret 冠军 10.15%）——高 TO 高 Ret 样本的 ProdCorr 系统性贴限/超限。
- N1eGk79E（STATISTICAL 中性化 + eod_vwap 分子 + 519/516 持仓）ProdCorr 0.5589 / SelfCorr 0.1521 双过，YPxOGboo 0.671/0.215、ZYm9ebv0 0.6833/0.228 也双过。
- **对 W11 的含义**：W11 若走"提交级"优化，ProdCorr 是比 Fit/TO 更近的墙（缺口 0.0033 vs Fit 缺口需 Sh 2.83）。换字段去相关（ton_last→eod_vwap、INDUSTRY→STATISTICAL）已被实证可将 ProdCorr 从 0.70+ 压到 0.56，且同时降 CLUSTER 0.10——这是唯一被实证的"一石二鸟"杠杆，应作为 W11 种子库的优先变异方向；同时 W11 必须把 PROD_CORRELATION 从 pending 转为实测（当前五条关键 alpha 中 4 条的 ProdCorr 状态未知）。

---

### 附：本报告数据完整性声明
- T1/T2/T3/T4/T5 全部基于 result JSON 实读数值；CLUSTER 数值来自 `checks.warning[].value`（339/339 行齐备）。
- 未找到的项如实报告：SH165 非 alpha_id，经 `phase12_wave10e_toattack.py` 与 `FINAL_REPORT_v2.md §8.2` 交叉确认 SH165 = leMYnJZn（w10d 槽5）；N1eGk79E 的 risk_neutralized_sharpe 在 BRAIN 返回中缺失（None，因其为 STATISTICAL 中性化）。
- 研报口径（320 行）与本报告口径（339 行）的差异 = gate1_b9/b10/b11 三批 24 行 − 跨批重复 5 行，已在每项统计中分别标注。
