# news12 字段侦察报告（_w11f_recon）

- 生成方式：只读分析，未运行任何回测/仿真，未调用任何 BRAIN API，未修改任何已有文件
- 字段源：`news12_fields_full.json`（867 个字段；MATRIX 75 / VECTOR 792）
- 历史表达式语料：`_baseline_final.json` 315 条 + `_baseline_w11.json` 57 条 + `batch_*.json` 提交文件 58 个共 452 条 = **824 条表达式**
- 匹配方法：对表达式做标识符分词（`[A-Za-z_][A-Za-z0-9_]*`）后精确匹配字段 id（token 法）；同时保留原始子串计数作对照。blue_*.json 中无可提取表达式（0 条），未计入。
- 全字段使用概况：104/867 个字段至少出现过 1 次；**763 个字段从未出现**（token=0 且 raw=0）
- 方法学校验：tok=0 但 raw>0 的「幻影匹配」字段 6 个（current_to_average_volume_ratio, performance_vs_benchmark, price_at_news_time, range_to_atr_ratio, session_closing_price, session_range_to_atr_ratio）——即字段 id 是其他更长标识符的子串，token 法已正确排除

---

## a. `news_short_interest` 详解

| 属性 | 值 |
|---|---|
| id | `news_short_interest` |
| 描述 | Ratio of total number of shares sold short to total shares outstanding |
| type | **MATRIX** |
| coverage | **0.872** |
| dateCoverage | 1.0 |
| userCount / alphaCount | 17 / 28（社区中等热度） |
| dateCreated | 2022-05-01 |
| 历史使用次数 | token=10，raw=10（_baseline_final×1, _baseline_w11×3, batch_gate3_J_1792843375.json×1, batch_w11a_1792941539.json×3） |

**定义解读**：卖空股数 / 总流通股数（total shares outstanding）之比，即**空头兴趣占流通股本比例**，无量纲比率，典型量级约 0.01–0.30（1%–30%）。

**更新频率线索**：元数据中无显式更新频率字段；描述本身不含频率信息。旁证：同族 VECTOR 字段 `shares_sold_short` 描述为 "Most recent short interest ratio for the stock on Day 1"，提示为**事件日快照语义**。真实世界中交易所空头兴趣通常为双周频率（FINRA 报送），BRAIN 内大概率按事件日对齐的最近一期快照——此为推断，非数据内证据。dateCoverage=1.0 表示回测区间内每日有值（可能含前向填充）。

**是否适合做分母**：**不适合直接做分母**。理由：
1. 量纲上它是纯比率（0–1），不是规模/尺度量；用 `divide(价格偏离, short_interest)` 会把低空头兴趣个股的偏离值放大 10–100 倍，数值不稳定且经济学含义混杂（偏离度与空头占比被强行相乘）。
2. 它更适合做**乘子/交互项**（如 `multiply(偏离, short_interest)` 度量「空头拥挤度加权的声音压力」）、**分组变量**或**门条件**。
3. 若要做 days-to-cover 类归一，正确分母是成交量而非 short_interest 本身——数据集中已有现成字段 `shares_sold_short_count_2`（"Number of shares sold short divided by average daily trading volume"，即 short/ADV，VECTOR cov 0.4598，**从未使用**）。

## b. 核心价格字段确认

| 字段 | 描述 | type | coverage | 历史使用 |
|---|---|---|---|---|
| `news_ton_last` | Price at the time of the news | MATRIX | 0.9717 | tok=295 |
| `news_eod_close` | Session closing price | MATRIX | 0.8778 | tok=466 |
| `news_eod_vwap` | VWAP from the time of news to the end of the session | MATRIX | 0.9673 | tok=120 |

**TON 确认**：`news_ton_last` = "Price at the time of the news"，即**新闻发布时刻的股价**（time-of-news last price），cov 0.9717，是最常用的基准价（295 次）。`news_eod_close` = 当日收盘价（cov 0.8778，466 次，全场最热）。`news_eod_vwap` = **从新闻时刻到收盘的 VWAP**（cov 0.9673，120 次）——即最佳 alpha 的分母度量的是「新闻后时段的成交均价」。

## c. 关键词字段清单 + MATRIX coverage>0.8 全清单

### c1. 关键词命中（id 或描述含 short_interest / borrow / utiliz / lending）

**严格关键词命中仅 3 个字段，全部是 short_interest；borrow / utiliz / lending 在本数据集零命中**（本数据集无借券费、利用率、融券供给类字段）：

| id | type | coverage | 历史使用 | 描述 |
|---|---|---|---|---|
| `news_short_interest` | MATRIX | 0.872 | tok=10 raw=10 | Ratio of total number of shares sold short to total shares outstanding |
| `nws12_mainz_short_interest` | VECTOR | 0.8632 | tok=0 raw=0 | Total number of shares sold short divided by total number of shares outstanding |
| `nws12_prez_short_interest` | VECTOR | 0.8116 | tok=0 raw=0 | Total number of shares sold short divided by total number of shares outstanding |

扩展：广义「做空相关」字段共 13 个（id/描述含 short_interest / sold_short / shorted / short_position）：

| id | type | coverage | 历史使用 | 描述 |
|---|---|---|---|---|
| `news_short_interest` | MATRIX | 0.872 | tok=10 raw=10 | Ratio of total number of shares sold short to total shares outstanding |
| `nws12_mainz_short_interest` | VECTOR | 0.8632 | tok=0 raw=0 | Total number of shares sold short divided by total number of shares outstanding |
| `nws12_prez_short_interest` | VECTOR | 0.8116 | tok=0 raw=0 | Total number of shares sold short divided by total number of shares outstanding |
| `shares_sold_short` | VECTOR | 0.4713 | tok=0 raw=0 | Most recent short interest ratio for the stock on Day 1 |
| `shorted_shares_count_all` | VECTOR | 0.4713 | tok=0 raw=0 | Short interest ratio (shares shorted relative to volume) for day 1 in 'All Filter' |
| `shares_sold_short_count_2` | VECTOR | 0.4598 | tok=0 raw=0 | Number of shares sold short divided by average daily trading volume (short interest ratio) |
| `shares_sold_short_count_6` | VECTOR | 0.4598 | tok=0 raw=0 | Short interest ratio for the stock during Day 1 |
| `shares_sold_short_count_5_1555` | VECTOR | 0.4597 | tok=0 raw=0 | Ratio of shares sold short to average daily trading volume |
| `shares_sold_short_count_3` | VECTOR | 0.4152 | tok=0 raw=0 | Short interest ratio or value as of After Hours Day 1 |
| `shares_sold_short_count_4` | VECTOR | 0.4152 | tok=0 raw=0 | Number of shares sold short for the security. |
| `shares_sold_short_count` | VECTOR | 0.4085 | tok=0 raw=0 | Short interest data, likely the ratio or number of shares shorted for the stock |
| `short_position_count` | VECTOR | 0.4085 | tok=0 raw=0 | Short interest ratio (number of shares shorted divided by average daily volume) for the st |

要点：MATRIX 版 `news_short_interest`（cov 0.872）已使用 10 次；而 VECTOR 三兄弟 `nws12_mainz_short_interest`（0.8632）/ `nws12_prez_short_interest`（0.8116）与全部 `shares_sold_short*` / `short_position_count` / `shorted_shares_count_all`（cov 0.41–0.47）**全部零使用**。

### c2. 全部 MATRIX 且 coverage>0.8 的字段（49 个，按 coverage 降序）

| # | coverage | id | tok使用 | 状态 | 描述 |
|---|---|---|---|---|---|
| 1 | 0.9718 | `news_spy_last` | 0 | **从未使用** | SPY last price at the time of the news |
| 2 | 0.9717 | `news_pct_1min` | 4 |  | Percent change in price during the first minute following the news release |
| 3 | 0.9717 | `news_pct_30min` | 4 |  | Percent change in price during the first 30 minutes following the news rele |
| 4 | 0.9717 | `news_spy_close` | 0 | **从未使用** | SPY price at session close |
| 5 | 0.9717 | `news_ton_last` | 295 |  | Price at the time of the news |
| 6 | 0.9713 | `news_indx_perf` | 5 |  | Difference in percent return between the stock and the S&P 500 ETF over the |
| 7 | 0.9710 | `news_mins_4_pct_dn` | 4 |  | Number of minutes before the price decreased by at least 4 percent after th |
| 8 | 0.9707 | `news_eod_high` | 18 |  | Highest price from the time of news to end of session |
| 9 | 0.9707 | `news_eod_low` | 22 |  | Lowest price from the time of news to end of session |
| 10 | 0.9707 | `news_low_exc_stddev` | 24 |  | Standardized measure of price movement from last price in time-of-news wind |
| 11 | 0.9707 | `news_main_vwap` | 0 | **从未使用** | Main session volume-weighted average price |
| 12 | 0.9707 | `news_ton_high` | 8 |  | Highest price reached during the session before the time of news |
| 13 | 0.9707 | `news_ton_low` | 0 | **从未使用** | Lowest price reached during the session before the time of news |
| 14 | 0.9705 | `news_post_vwap` | 24 |  | Post-session volume-weighted average price |
| 15 | 0.9704 | `news_max_dn_amt` | 235 |  | Price at the time of the news minus the after-news low |
| 16 | 0.9704 | `news_max_dn_ret` | 19 |  | Percent change from price at time of news to lowest price after news |
| 17 | 0.9692 | `news_max_up_amt` | 427 |  | After-news high minus the price at the time of the news |
| 18 | 0.9692 | `news_pct_60min` | 2 |  | Percent change in price during the first 60 minutes following the news rele |
| 19 | 0.9692 | `news_pct_90min` | 0 | **从未使用** | Percent change in price during the first 90 minutes following the news rele |
| 20 | 0.9691 | `news_tot_ticks` | 4 |  | Total number of ticks during the trading day |
| 21 | 0.9678 | `news_mins_20_pct_dn` | 4 |  | Number of minutes that elapsed before price went down 20 percentage points |
| 22 | 0.9673 | `news_eod_vwap` | 120 |  | VWAP from the time of news to the end of the session |
| 23 | 0.9673 | `news_mins_20_pct_up` | 8 |  | Number of minutes that elapsed before price went up 20 percentage points |
| 24 | 0.9673 | `news_mins_4_pct_up` | 8 |  | Number of minutes before the price increased by at least 4 percent after th |
| 25 | 0.9673 | `news_pct_30sec` | 6 |  | Percent change in price in the 30 seconds after the news release |
| 26 | 0.9672 | `news_vol_stddev` | 0 | **从未使用** | Z-score of current volume compared to 30-day average volume, using 30-day v |
| 27 | 0.9671 | `news_mins_5_chg` | 0 | **从未使用** | Minimum value among L or S for each minute bucket, indicating the fastest r |
| 28 | 0.9662 | `news_pe_ratio` | 8 |  | Reported price-to-earnings ratio for the calendar day of the session |
| 29 | 0.9652 | `news_high_exc_stddev` | 26 |  | Standardized measure of price movement from end-of-day high to last price i |
| 30 | 0.9646 | `news_eps_actual` | 6 |  | Actual Earnings Per Share reported in the news release |
| 31 | 0.9214 | `news_mins_5_pct_up` | 4 |  | Number of minutes before the price increased by at least 5 percent after th |
| 32 | 0.9209 | `news_mins_3_pct_up` | 6 |  | Number of minutes before the price increased by at least 3 percent after th |
| 33 | 0.9209 | `news_mins_4_chg` | 0 | **从未使用** | Minimum value among L or S (minutes to reach positive/negative return thres |
| 34 | 0.9175 | `news_mins_1_chg` | 0 | **从未使用** | Minimum number of minutes taken for price to move (up or down) 1 percentage |
| 35 | 0.9174 | `news_mins_3_chg` | 0 | **从未使用** | Minimum number of minutes taken for price to move (up or down) 3 percentage |
| 36 | 0.9174 | `news_mins_3_pct_dn` | 4 |  | Number of minutes before the price decreased by at least 3 percent after th |
| 37 | 0.9142 | `news_mins_20_chg` | 0 | **从未使用** | The minimum of L or S above for 20-minute bucket |
| 38 | 0.9063 | `news_pct_120min` | 4 |  | Percent change in price during the first 120 minutes following the news rel |
| 39 | 0.8947 | `news_atr14` | 13 |  | 14-day Average True Range |
| 40 | 0.8817 | `news_mins_7_5_pct_dn` | 0 | **从未使用** | Number of minutes elapsed before price decreases by 7.5 percentage points a |
| 41 | 0.8778 | `news_eod_close` | 466 |  | Session closing price |
| 42 | 0.8720 | `news_short_interest` | 10 |  | Ratio of total number of shares sold short to total shares outstanding |
| 43 | 0.8534 | `news_dividend_yield` | 2 |  | Reported annual dividend yield percentage for the calendar day of the sessi |
| 44 | 0.8467 | `news_mins_5_pct_dn` | 2 |  | Number of minutes before the price decreased by at least 5 percent after th |
| 45 | 0.8458 | `news_max_up_ret` | 39 |  | Percent change from price at time of news to highest price after news |
| 46 | 0.8309 | `news_mins_1_pct_dn` | 0 | **从未使用** | Number of minutes before the price decreased by at least 1 percent after th |
| 47 | 0.8289 | `news_pre_vwap` | 0 | **从未使用** | Pre-session volume-weighted average price |
| 48 | 0.8272 | `news_cap` | 2 |  | Reported total market capitalization for the calendar day of the session |
| 49 | 0.8046 | `news_mov_vol` | 0 | **从未使用** | 30-day moving average of session volume |

其中 **15 个从未使用**：`news_spy_last`, `news_spy_close`, `news_main_vwap`, `news_ton_low`, `news_pct_90min`, `news_vol_stddev`, `news_mins_5_chg`, `news_mins_4_chg`, `news_mins_1_chg`, `news_mins_3_chg`, `news_mins_20_chg`, `news_mins_7_5_pct_dn`, `news_mins_1_pct_dn`, `news_pre_vwap`, `news_mov_vol`

## d. 交叉比对：上述字段的历史使用统计

语料：824 条表达式（baseline_final 315 + baseline_w11 57 + batch 提交 452）。「使用」= 字段 id 作为完整标识符出现 ≥1 次。

- 做空系：仅 `news_short_interest` 被用过（10 次）；其余 12 个做空相关字段全部未测。
- MATRIX>0.8 的 49 个字段中 34 个已测、15 个未测（见 c2 表）。
- 全数据集 867 个字段中 **763 个从未出现**（VECTOR 728 / MATRIX 35）。

## 3. 特别确认：三个「据说完全未测」字段——辟谣

**结论：说法不成立，三个字段均有历史使用记录**（但都只集中在少数几个文件里，测试深度很浅）：

| 字段 | type | coverage | 总使用次数 | 出现位置 |
|---|---|---|---|---|
| `news_eps_actual` | MATRIX | 0.9646 | **6** | _baseline_w11×2, batch_w11a_1792941539.json×2 |
| `news_pe_ratio` | MATRIX | 0.9662 | **8** | _baseline_final×3, _baseline_w11×1, batch_gate3_J_1792843375.json×3, batch_w11a_1792941539.json×1 |
| `news_dividend_yield` | MATRIX | 0.8534 | **2** | _baseline_final×1, batch_gate3_J_1792843375.json×1 |

解读：
- `news_eps_actual`（6 次）只在 w11a 基本面波被碰过（_baseline_w11 ×2 + batch_w11a ×2，另 _baseline_w11 中还有 `nws12_mainz_epsactual` VECTOR 变体），gate1–gate9 主战役从未使用。
- `news_pe_ratio`（8 次）分布在 _baseline_final ×3、batch_gate3_J ×3、_baseline_w11 ×1、batch_w11a ×1。
- `news_dividend_yield`（2 次）仅 _baseline_final ×1 + batch_gate3_J ×1，是三者中测试最浅的。
- 三者均为 MATRIX、coverage 0.85–0.97、dateCoverage=1.0，属于「被偶然碰过但从未被系统挖掘」的状态，仍是高价值空地。

## 4. 可做分母候选 top5（从未使用 + 规模/尺度类 + MATRIX，按推荐序）

| 排名 | 字段 | coverage | 描述 | 作为分母的经济学 |
|---|---|---|---|---|
| 1 | `news_main_vwap` | 0.9707 | Main session volume-weighted average price | 与现分母 `news_eod_vwap` 同族的平行替换：度量「TON→收盘」之外的**全日成交基准**，直接检验最佳 alpha 的分母是否只是 VWAP 的特例 |
| 2 | `news_vol_stddev` | 0.9672 | Z-score of current volume compared to 30-day average volume | 把价格偏离除以**量能异常度**=「单位异常成交量承载的价格压力」，与新闻驱动资金流的故事最贴合 |
| 3 | `news_mov_vol` | 0.8046 | 30-day moving average of session volume | 经典规模分母：可构造 `divide(偏离, news_mov_vol)` 类「每单位常态量的压力」，或与 short_interest 组合出 days-to-cover 思想 |
| 4 | `news_curr_vol` | 0.7769 | Current day's session volume | 当日绝对量：若分子换成分额偏离（amt 类），可归一为「单位成交量价格冲击」 |
| 5 | `news_pre_vwap` | 0.8289 | Pre-session volume-weighted average price | 盘前基准价：分离「新闻前已存在的价格发现」与「新闻后压力」，做双重偏离的第三重 |

备选：`news_ton_low`（0.9707，TON 前时段最低价，可换基准价）、`news_all_vwap`（0.7280，全场 VWAP）、`news_spy_last`/`news_spy_close`（0.9718/0.9717，市场基准，可做 relative 版分母）。

注意：另有 252 个从未使用的 VECTOR 规模类字段（cov 多为 1.0，如 `main_session_market_cap`、`main_current_trading_volume`、`main_end_of_day_vwap`、`fourteen_period_atr_all`），但 dateCoverage 为 null、且与当前最佳 alpha 的 MATRIX 体系不同族，引入前需先验证填充行为。

---

## 结论速览

1. `news_short_interest` = 卖空股数/总流通股数（无量纲比率，0.01–0.30 量级），MATRIX，cov 0.872，dateCoverage 1.0，事件日快照语义（频率无显式线索，推断双周）。已使用 10 次。**不适合做分母**（低 SI 名放大噪声、经济学混杂），宜作乘子/分组/门；要做借券压力归一请用 `shares_sold_short_count_2`（short/ADV，从未使用）或 `divide(news_short_interest, turnover)`。
2. borrow / utiliz / lending 类字段在本数据集**不存在**；做空系 13 个字段中 12 个从未测试（含两个高覆盖 VECTOR 变体 0.81–0.86）。
3. 「news_eps_actual / news_pe_ratio / news_dividend_yield 完全未测」**不实**：分别已用 6 / 8 / 2 次，但均局限于 gate3_J 与 w11a 少数文件，主战役未系统挖掘，仍是空地。
4. 分母候选 top5：`news_main_vwap` > `news_vol_stddev` > `news_mov_vol` > `news_curr_vol` > `news_pre_vwap`（全部从未使用、MATRIX、cov 0.78–0.97）。
5. 全数据集 867 字段中仅 104 个被碰过、763 个从未出现；MATRIX>0.8 的 49 个中 15 个未测（`news_spy_last`、`news_spy_close`、`news_main_vwap`、`news_ton_low`、`news_pct_90min`、`news_vol_stddev`、`news_mins_5_chg`、`news_mins_7_5_pct_dn`、`news_mins_4_chg`、`news_mins_1_chg`、`news_mins_3_chg`、`news_mins_20_chg`、`news_mins_1_pct_dn`、`news_pre_vwap`、`news_mov_vol`）。