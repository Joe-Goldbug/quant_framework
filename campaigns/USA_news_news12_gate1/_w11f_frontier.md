# W11F 前沿分析报告：CLUSTER_TEST 缺口 / (Sh,TO) 前沿 / Turnover 机理 / 低 TO 天花板

- 战役：USA_news_news12_gate1（news12，USA/TOP1000/delay=1，truncation=0.025）
- 数据基座：56 个 `batch_*_result.json` → 442 条原始行 → 去重（表达式+settings）后 **417 条**，其中 **416 条**带 CLUSTER_TEST value 且 metrics 完整。本文所有统计基于该 416 行子集（下称"全库"）。
- 方法：只读分析，未运行任何回测/仿真，未修改任何已有文件。临时脚本：`_w11f_tmp_01_base.py`（合并）、`_w11f_tmp_02_analyze.py`（主分析）、`_w11f_tmp_03_v2.py`（平衡括号修正）、`_w11f_tmp_04_v3.py`（覆盖度）。
- 目标回顾：Sharpe ≥1.58 且 CLUSTER_TEST ≥1.58（零警告）；进阶目标 Sh ≥1.63 且 TO ≤25%。

---

## 1. CLUSTER_TEST 缺口驱动分析（gap = CL − Sh）

### 1.1 gap 总体分布

| 统计量 | 值 |
|---|---|
| mean | **−0.044** |
| median | −0.050 |
| min / max | −0.87 / +0.85 |
| gap ≥ 0（CL ≥ Sh）的行 | 158 / 416（38%） |

### 1.2 gap 与各量的相关度（n=416）

| 指标 | Pearson | Spearman | 方向解读 |
|---|---|---|---|
| **returns** | **−0.447** | −0.497 | 收益越高，gap 越负（最强驱动） |
| **risk_neutralized_sharpe** | **−0.444** | −0.491 | RN Sh 越高，gap 越负 |
| **sharpe** | −0.427 | −0.468 | Sh 越高，gap 越负 |
| fitness | −0.417 | −0.436 | |
| sub_universe_sharpe | −0.376 | −0.420 | |
| **turnover** | **−0.344** | −0.324 | TO 越高，gap 越负 |
| two_year_sharpe | −0.327 | −0.370 | |
| **longCount** | **+0.185** | +0.193 | 宽度越大，gap 越接近 0 |
| shortCount | +0.167 | +0.195 | |
| width（long+short） | +0.178 | +0.172 | |
| drawdown | +0.064 | +0.207 | |
| margin | −0.058 | −0.192 | |

**核心张力**：gap 与 Sh/Ret/RN 强负相关（≈−0.42~−0.45），与 turnover 负相关（−0.34），与持仓宽度正相关（+0.18）。即"越强的 alpha，CL 落后 Sh 越多；越宽的书，gap 越小"。分 TO 带看更清楚：

| TO 带 | n | gap mean | Sh mean | Sh max |
|---|---|---|---|---|
| [0, 0.25) | 78 | **+0.038** | 0.17 | 0.89 |
| [0.25, 0.50) | 87 | −0.003 | 0.71 | 1.19 |
| [0.50, 0.75) | 36 | +0.027 | 0.75 | 1.45 |
| [0.75, 1.00) | 25 | −0.077 | 1.01 | 1.49 |
| [1.00, 1.15) | 52 | −0.076 | 0.92 | 1.59 |
| [1.15, 1.35) | 106 | **−0.130** | 1.03 | 1.69 |

低 TO 区 gap≈0 但 Sh 上不去；高 TO 高 Sh 区 gap 最负。**CL≥1.58 的零警告目标 = 需要 gap≈0 的 Sh≥1.58，历史上从未同时出现**（CL 历史最高 1.56 @ Sh=1.57）。

### 1.3 gap 最小的结构特征（分组统计）

**按字段族（gap mean，全库）**：

| 字段族 | n | gap mean | 备注 |
|---|---|---|---|
| **amplitude**（max_up_amt/max_dn_amt） | 108 | **−0.014** | 最小 |
| none/纯 vec | 35 | −0.007 | |
| vol | 3 | −0.033 | |
| excursion_stddev | 224 | −0.055 | |
| atr | 12 | −0.060 | |
| intraday | 13 | −0.069 | |
| **vwap_close**（eod_close/ton_last 等） | 231 | **−0.082** | 最大（但这是高 Sh 引擎所在族） |

**按结构特征（gap mean，ON vs OFF）**：

| 特征 | ON n | ON mean | OFF mean | diff |
|---|---|---|---|---|
| group_neutralize/group_rank | 39 | **−0.003** | −0.048 | +0.045 |
| vec_avg 聚合 | 67 | **−0.008** | −0.051 | +0.044 |
| ts_rank（非250窗口） | 79 | −0.017 | −0.051 | +0.034 |
| ts_zscore | 6 | +0.030 | −0.045 | +0.075（样本小） |
| ts_mean | 42 | −0.031 | −0.046 | +0.015 |
| ts_backfill | 151 | −0.063 | −0.033 | −0.030 |
| plain rank | 214 | −0.066 | −0.021 | −0.044 |
| winsorize | 9 | −0.084 | −0.043 | −0.041 |
| **ts_decay_linear** | 20 | **−0.110** | −0.041 | −0.069 |

**按 settings（gap mean）**：

| 设置 | n | gap mean |
|---|---|---|
| decay=20 | 8 | **−0.003** |
| STATISTICAL 中性化 | 8 | −0.024 |
| decay=25 | 16 | −0.028 |
| **INDUSTRY 中性化** | 376 | −0.032 |
| decay=6 | 392 | −0.046 |
| MARKET 中性化 | 24 | −0.110 |
| TOP500 | 8 | −0.121 |
| TOP3000 | 8 | −0.171 |
| **SUBINDUSTRY 中性化** | 8 | **−0.445** |

**按输出层**：rank（最外层）−0.041~+0.041（n=13）；reverse 包裹 −0.045（n=284）；raw −0.051（n=119）。

### 1.4 条件分析：只看 Sh≥1.3 的可行 alpha（n=78）

gap 整体均值恶化到 −0.162（高 Sh 必然吃 gap），但**相对排序仍稳定**：

- 字段族：**amplitude −0.067（最小）** ≪ excursion −0.170 < vwap_close −0.177。amplitude 是唯一在低 gap 与高 Sh 之间没付出惨烈代价的族。
- 特征：**winsorize ON 的 gap 比 OFF 高 +0.049**（高 Sh 行里唯一改善 gap 的特征）；ts_decay/ts_backfill/rank 均使 gap 更负。
- settings：INDUSTRY −0.151 仍最优；decay=6 −0.160 vs decay=25 −0.213。
- CL≥1.5 的 6 行共同点：**全部带 trade_when(days_from_last_change(vec_count(excursion))≤2) 门控**，全部 excursion+vwap_close 族，全部 INDUSTRY。最强零警告候选：CL=1.56 @ Sh=1.57 @ TO=1.127（batch_gate1_b9，门控阈值=1，gap 仅 −0.01）。

### 1.5 gap 最小的 10 行（原始排序）

| # | gap | Sh | CL | TO | Fit | 表达式 |
|---|---|---|---|---|---|---|
| 1 | −0.87 | 0.51 | −0.36 | 0.132 | 0.24 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), trade_when(greater(rank(news_short_interest), 0.88), reverse(rank(divide(news_indx_perf, add(vec_count(high_price_excursion_stddev), 1)))), 0), 0)` |
| 2 | −0.78 | 1.29 | 0.51 | 1.286 | 0.26 | `reverse(rank(divide(subtract(news_eod_close, news_eod_vwap), ts_backfill(vec_count(high_price_excursion_stddev), 120))))` |
| 3 | −0.65 | 1.15 | 0.50 | 1.313 | 0.22 | `reverse(rank(divide(subtract(news_eod_close, news_eod_vwap), vec_max(high_price_excursion_stddev))))` |
| 4 | −0.62 | 1.03 | 0.41 | 1.347 | 0.25 | `reverse(multiply(rank(divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))), rank(news_open_gap)))` |
| 5 | −0.55 | 0.85 | 0.30 | 0.312 | 0.32 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_mean(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120)), 5))), 0)` |
| 6 | −0.53 | 0.21 | −0.32 | 1.579 | 0.05 | `reverse(divide(news_mins_3_pct_up, add(news_mins_3_pct_up, news_mins_3_pct_dn)))` |
| 7 | −0.53 | 1.51 | 0.98 | 1.231 | 0.35 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120)))), 0)` |
| 8 | −0.52 | 1.48 | 0.96 | 1.233 | 0.34 | `reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120))))` |
| 9 | −0.47 | 1.50 | 1.03 | 1.228 | 0.33 | `reverse(ts_rank(divide(subtract(news_eod_close, news_eod_vwap), add(vec_count(high_price_excursion_stddev), 1)), 250))` |
| 10 | −0.46 | 1.53 | 1.07 | 1.227 | 0.34 | `reverse(ts_rank(divide(subtract(news_eod_close, news_eod_vwap), add(vec_count(high_price_excursion_stddev), 1)), 500))` |

注意：原始 gap 最小行多为弱 alpha（Sh 0.2~1.5）——gap 最小 ≠ 可用。**可操作的 gap 最小化配方**应取条件分析的结论：amplitude 族 + group 输出层 + vec 聚合 + INDUSTRY + decay=6/20 + 宽书 + trade_when(≤2) 门控；避免 SUBINDUSTRY/MARKET 中性化与 TOP500/3000。

---

## 2. (Sh, TO) 前沿分析

### 2.1 TO 10% 分桶前沿

| TO 桶 | n | max Sh | Fit@max | Ret@max | 桶内 Sh 中位 |
|---|---|---|---|---|---|
| [0.0,0.1) | 35 | 0.78 | 0.36 | 0.0263 | 0.14 |
| [0.1,0.2) | 24 | 0.70 | 0.24 | 0.0232 | 0.24 |
| [0.2,0.3) | 27 | 0.89 | 0.37 | 0.0382 | 0.40 |
| [0.3,0.4) | 48 | **1.19** | 0.38 | 0.0374 | 0.86 |
| [0.4,0.5) | 32 | 1.07 | 0.36 | 0.0463 | 0.79 |
| [0.5,0.6) | 19 | 1.17 | 0.31 | 0.0406 | 0.96 |
| [0.6,0.7) | 10 | 1.20 | 0.33 | 0.0532 | 0.71 |
| [0.7,0.8) | 12 | 1.45 | 0.44 | 0.0649 | 1.35 |
| [0.8,0.9) | 17 | 1.49 | 0.43 | 0.0693 | 1.15 |
| [0.9,1.0) | 2 | 1.10 | 0.24 | 0.0439 | 1.10 |
| [1.0,1.1) | 15 | 1.37 | 0.32 | 0.0571 | 0.69 |
| [1.1,1.2) | 69 | 1.65 | 0.42 | 0.0786 | 1.21 |
| [1.2,1.3) | 66 | **1.69** | 0.42 | 0.0777 | 1.29 |
| [1.3,1.4) | 20 | 1.29 | 0.30 | 0.0769 | 1.16 |
| [1.4,1.5) | 18 | 1.49 | 0.30 | 0.0579 | 0.09 |
| [1.5,1.6) | 2 | 0.41 | 0.09 | 0.0820 | 0.41 |

**前沿形状确认**：
- 全库 corr(TO, Sh) = +0.339。前沿呈**阶梯式上升**：TO 0.3→0.4 桶 max Sh 1.19，0.7→0.9 桶 1.45~1.49，1.15→1.3 桶达峰 1.65~1.69，之后样本稀疏回落。
- 关键断崖：**TO 从 0.4 到 0.7，max Sh 从 1.19 跳到 1.45（+0.26）；从 0.9 到 1.2，从 1.49 跳到 1.69（+0.20）**。Sh 对 TO 的边际收益在高 TO 区仍显著为正——降 TO 的每一分都在丢 Sh。
- **Sh≥1.5 的 30 行全部 TO≥1.127；TO≤25% 的 78 行 max Sh 仅 0.89；TO∈[25%,50%] 的 87 行 max Sh 1.19**。目标区（Sh≥1.63 & TO≤25%）目前 0 行，且距离最近的点（Sh 1.69 @ TO 1.25）差 5 倍 TO。

### 2.2 全史 Fit top10（不管 Sh）

| # | Fit | Sh | TO | Ret | 2Y | sub | CL | 表达式 |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.44 | 1.45 | 0.718 | 0.0649 | 1.61 | 1.27 | 1.33 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_decay_linear(ts_backfill(divide(winsorize(subtract(news_eod_close, news_ton_last), std=2), add(vec_count(high_price_excursion_stddev), 1)), 2), 2))), 0)` |
| 2 | 0.43 | 1.49 | 0.837 | 0.0693 | 1.53 | 1.42 | 1.43 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_backfill(divide(winsorize(subtract(news_eod_close, news_ton_last), std=2), add(vec_count(high_price_excursion_stddev), 1)), 2))), 0)` |
| 3 | 0.43 | 1.44 | 0.723 | 0.0632 | 1.46 | 1.27 | 1.21 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_decay_linear(ts_backfill(divide(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), add(ts_mean(vec_count(high_price_excursion_stddev), 20), 1)), 2), 2))), 0)` |
| 4 | 0.42 | 1.65 | 1.198 | 0.0786 | 2.10 | 1.30 | 1.47 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120)))), 0)` |
| 5 | 0.42 | 1.47 | 0.837 | 0.0681 | 1.49 | 1.41 | 1.41 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_backfill(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 2))), 0)` |
| 6 | 0.42 | 1.41 | 0.718 | 0.0636 | 1.55 | 1.26 | 1.31 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_decay_linear(ts_backfill(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), 2), 2))), 0)` |
| 7 | 0.42 | 1.63 | 1.159 | 0.0756 | 2.02 | 1.42 | 1.52 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), add(ts_mean(vec_count(high_price_excursion_stddev), 20), 1)))), 0)` |
| 8 | 0.42 | 1.49 | 0.842 | 0.0678 | 1.42 | 1.44 | 1.36 | `trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(ts_backfill(divide(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), add(ts_mean(vec_count(high_price_excursion_stddev), 20), 1)), 2))), 0)` |
| 9 | 0.42 | 1.69 | 1.253 | 0.0777 | 2.02 | 1.42 | 1.38 | `reverse(rank(divide(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)), multiply(add(ts_mean(vec_count(high_price_excursion_stddev), 20), 1), add(vec_stddev(high_price_excursion_stddev), 0.01)))))` |
| 10 | 0.41 | 1.26 | 0.829 | 0.0893 | 1.72 | 0.89 | 1.21 | `reverse(rank(ts_backfill(divide(add(subtract(news_eod_close, news_ton_last), subtract(news_eod_close, news_open)), news_open), 2)))` |

Fit top10 全部是同一引擎家族：**eod_close−ton_last（或 eod_close−open）对 vec_count(excursion) 的归一化 dislocation 比率 + reverse(rank) + trade_when 门控**，降 TO 手段为 ts_decay_linear/ts_backfill(2)/winsorize(std=2)。该栈把 TO 压到 0.72~0.84 时 Sh 保持 1.41~1.49——这是全库 TO-Sh 兑换效率最高的位置，但离 TO≤25% 仍差 3 倍。

---

## 3. Turnover 机理分析

### 3.1 三组 TO 分布对比

| 组 | n | TO mean | TO med | p10 | p25 | p75 | p90 | Sh mean | Sh max |
|---|---|---|---|---|---|---|---|---|---|
| **ts_rank(X,250)** | 68 | 0.570 | **0.403** | 0.081 | 0.103 | 1.124 | 1.228 | 0.64 | 1.58 |
| rank(X) only（无 ts_rank） | 212 | 0.810 | 0.842 | 0.202 | 0.397 | 1.206 | 1.369 | 0.82 | 1.69 |
| ts_backfill（任意窗口） | 151 | 0.578 | **0.406** | 0.228 | 0.371 | 0.816 | 1.197 | 0.82 | 1.65 |
| 既无 ts_rank 也无 ts_backfill | 199 | 0.945 | 1.150 | 0.153 | 0.498 | 1.265 | 1.401 | 0.63 | 1.69 |

ts_rank250 的 TO 中位（0.403）看起来低，但分布**严重双峰**（p25=0.103 vs p75=1.124）。按输入是否预平滑拆开：

| ts_rank250 子组 | n | TO mean | TO med | Sh mean | Sh max |
|---|---|---|---|---|---|
| **+ 预平滑输入**（首参含 ts_mean/ts_decay/ts_sum/ts_delta/ts_backfill/ts_std） | 36 | **0.245** | **0.106** | 0.50 | 1.57 |
| **+ 裸输入**（原始场直接进 ts_rank） | 32 | **0.935** | **1.124** | 0.81 | 1.58 |

对照 plain rank：裸输入 TO med **1.146**（n=100）vs 预平滑输入 0.715（n=112）。

### 3.2 假设验证：「ts_rank250 不平滑信号，极端日 rank 跳变导致高换手」

**数据证据（假设成立，且比原表述更精确）**：

1. **ts_rank250 对裸输入的 TO 中位 1.124 ≈ plain rank 对裸输入的 1.146**。即给裸信号套一层 250 日时序 rank，几乎不产生任何平滑效果——ts_rank 只把当日值与自身过去 250 天比较后重新归一，不削减信号的时间方差。
2. **预平滑输入才是 TO 的真正来源**：同样的 ts_rank250，输入经 ts_mean/ts_backfill/ts_decay 预处理后 TO 中位从 1.124 塌到 0.106（10.6 倍差）。plain rank 同样呈现 1.146 → 0.715。
3. **窗口越长≠越平滑**：ts_rank(...,120) n=5 TO med 1.224；ts_rank(...,250) n=68 TO med 0.403（双峰混合）；ts_rank(...,500) n=4 TO med 1.227。窗口长度本身不解释 TO。
4. **同字段族内对照（控制字段后结论不变）**：
   - amplitude 族：ts_rank250 TO med **0.121**（n=31）vs rank 0.586（n=22）vs ts_backfill 0.374（n=29）；
   - excursion 族：ts_rank250 TO med **1.039**（n=34）vs rank 0.762（n=136）vs ts_backfill 0.418（n=100）；
   - vwap_close 族：ts_rank250 TO med **1.083**（n=34）vs rank 0.889（n=156）vs ts_backfill 0.608（n=97）。
5. **双峰成因**：news12 字段是稀疏事件场——amplitude（max_up_amt 等）只在有新闻的日子非零，事件间序列恒定，ts_rank 值不动 → TO 极低（0.121）；而 excursion/vwap_close 是连续含噪场，极端日的值在 250 日历史中 rank 跳变 → TO 高（1.04~1.08）。裸输入 + 连续含噪场 = 高换手的充分条件。
6. **佐证**：全库既无 ts_rank 也无 ts_backfill 的 199 行（裸 rank/裸信号）TO med 1.150 且 Sh mean 仅 0.63——最差的一组；ts_backfill 组 TO med 0.406 且 Sh mean 0.82，是唯一"降 TO 不掉 Sh"的机制（bf60 窗口：TO med 0.376，n=47）。

**结论**：原假设成立且可加固——**ts_rank250 不是平滑器，是归一化器**。降 TO 的唯一被验证路径是"先平滑输入（ts_backfill/ts_decay/ts_mean），后 rank"。turnover 由输入信号的时间噪声决定，输出层算子（rank vs ts_rank vs ts_zscore）对 TO 无独立贡献。

---

## 4. 低 TO 区 Sh 天花板（TO ∈ [10%, 40%]）

### 4.1 总量与分族天花板

低 TO 区共 **99 行**（全库 416 的 24%）。

| 字段族 | n | max Sh | @TO | @CL | 桶内 Sh 中位 |
|---|---|---|---|---|---|
| **amplitude** | 36 | **1.19** | 0.375 | 1.15 | 0.70 |
| excursion_stddev | 64 | **1.19**（同一行，多族） | 0.375 | 1.15 | 0.54 |
| vwap_close | 45 | 0.94 | 0.397 | 0.82 | 0.55 |
| other/纯 vec | 3 | 0.78 | 0.391 | 0.77 | 0.12 |
| ret | 3 | 0.51 | 0.132 | −0.36 | 0.26 |

低 TO 区最强行（也是 amplitude+excursion 共同的最强行）：

```
trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 5),
  reverse(group_rank(ts_backfill(divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt)), 60), industry)), -1)
Sh=1.19  TO=0.375  CL=1.15  Fit=0.38
```

结构特征：**amplitude 比率 + ts_backfill(60) + group_rank(industry) + trade_when 门控**——恰好是 gap 分析中"最小化 gap"的配方族（amplitude + group 层），但 Sh 天花板 1.19，离 1.63 差 0.44。

按结构特征看低 TO 区：ts_backfill n=59 maxSh 1.19；group_neutral n=16 maxSh 1.19；rank n=52 maxSh 1.13；ts_rank_other n=15 maxSh 1.10；ts_mean n=20 maxSh 0.85。**低 TO 区没有任何结构突破过 1.19**。

### 4.2 amplitude 族 backfill 参数轴覆盖度（提交文件 89 个去重表达式）

| bf 参数 | 提交文件出现次数 | 结果行数 | TO med | Sh max |
|---|---|---|---|---|
| **bf60** | **18** | 22 | 0.375 | **1.19** |
| bf5 | 1 | 1 | 0.530 | 1.10 |
| bf20 | 1 | 3 | 0.377 | 1.06 |
| bf120 | 1 | 2 | 0.372 | 1.10 |
| bf250 | 1 | 1 | 0.371 | 1.10 |
| 无 backfill | 67 | 79 | 1.006 | 1.44 |

**结论：bf5 / bf20 / bf120 / bf250 四个参数点各只测过 1 次（1 个表达式），相对 bf60 的 18 次是近空白参数空间。** 但注意两点：(a) 所有 bf 窗口的 TO 中位都锚定在 0.37 附近——**bf 轴无法把 TO 压到 25% 以下**（bf 只解决"有新闻后持仓多久"，不解决事件间信号漂移）；(b) bf60 行的 Sh 中位 0.86~1.10，max 1.19——amplitude 低 TO 区的 Sh 瓶颈不在参数轴而在信号本身强度。真正未探索的是**参数轴 × 输出层 × 门控的三维交叉**（见第 5 节机制 2）。

补充：全库 bf 窗口总分布（提交文件 452 条）：bf120=49、bf60=52、bf2=27、bf3=20、bf250=9、bf20=4、bf5=4、无 bf=297。短窗（bf2/3/5）集中在 vwap_close 引擎，长窗（bf60/120/250）集中在 amplitude 与 vec_count 分母——**amplitude × 短窗 bf（2/3/5 中仅 bf5 有 1 次）与 amplitude × bf20/120/250 是明确的参数空白**。

---

## 5. 总结论：Sh ≥1.63 且 TO ≤25% 最值得尝试的 3 个未测机制

现状盘点（数据事实）：
- Sh≥1.63 需要 TO≥1.13（13 个 Sh≥1.58 行的最低 TO 为 1.127）；TO≤25% 的 78 行 Sh 上限 0.89。两者之间隔着整条 0.89→1.19→1.45→1.69 的前沿阶梯。
- 降 TO 已验证有效的手段只有"输入预平滑"（ts_backfill/ts_decay_linear/ts_mean），其极限位置是 TO 0.72~0.84 @ Sh 1.41~1.49（Fit top10 栈）。
- 全库零覆盖算子：hump、regression_neutral/beta/resi、ts_returns、vec_norm、scale、sigmoid、group_neutralize、ts_min/max/median、bucket、ts_corr、ts_regression（均 0 次）。
- 关键零测试交叉：ts_decay_linear×group_rank=0、ts_decay_linear×group_neutralize=0、winsorize×group_rank=0、ts_zscore×group_rank=0、ts_rank×group_neutralize=0、hump×ts_backfill=0。

### 机制 1（首选）：高 Sh 引擎 × group_rank(industry) 输出层——双赢未测交叉

- **做法**：把 Fit top10 的降 TO 栈（dislocation 比率 + ts_decay_linear/ts_backfill/winsorize + trade_when(≤2) 门控，TO 0.72~0.84 @ Sh 1.41~1.49）的最外层 rank 换成 `group_rank(..., industry)` 或 `group_neutralize(..., industry)`。
- **数据依据**：(a) group 输出层的 gap 全库最小（−0.003 vs plain rank −0.066），是唯一同时攻击 CLUSTER_TEST 缺口的输出层；(b) group_rank 的 37 行 TO 中位 0.398，天然工作在低 TO 区，低 TO 区最强行（Sh 1.19）正是 group_rank×ts_backfill(60)×amplitude；(c) 高 Sh 区（Sh≥1.4 的 60 行）**从未出现过 group 输出层**；(d) 行业内排序比全市场排序更"粘"（同行业个股相对位置日内稳定），有直接压 TO 的机理。
- **风险**：group_rank 单独使用 Sh 上限仅 1.19，必须靠强引擎信号承载 Sh。

### 机制 2：amplitude 双比率 × bf 参数轴补全（bf5/bf20/bf120/bf250）× 短窗 ts_rank × trade_when(≤2) 门控

- **做法**：以 `divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))` 为核，系统扫描 bf5/20/120/250（各只测过 1 次的空白点）与短窗 ts_rank（20/30/40，amplitude 上 n≤3）的组合，外套 trade_when(days_from_last_change(vec_count(excursion))≤2) 门控（CL top6 行共有的 gap≈−0.01 门控）。
- **数据依据**：(a) amplitude 是 gap 最小的族（全库 −0.014，Sh≥1.3 子集 −0.067，唯一"低 gap 不付代价"族）；(b) amplitude+ts_rank250 的 TO 中位仅 0.121（稀疏事件场 + 时序 rank 的组合天然低换手）；(c) bf60 已达 TO 0.375 @ Sh 1.19，参数轴补全是仅剩的低风险提升空间；(d) 短窗 ts_rank 在 amplitude 上几乎空白（ts_rank20/30/40 各 1~2 行且 Sh<0.5，但窗口×门控×bf 的交叉未测）。
- **风险**：amplitude 信号强度本身是瓶颈（族内 Sh 上限 1.44 @ TO 1.27），此机制更可能把 Sh 推到 1.3~1.4 @ TO≤0.25，作为机制 1 的候选分量而非单独达标。

### 机制 3：平滑化双族合成 + 零覆盖结构算子开图（regression_neutral / hump）

- **做法 A（平滑化双族合成）**：将 amplitude 比率与 dislocation 比率先各自 ts_backfill/ts_decay 平滑后再 multiply/add 合成。现有 14 个双族 multiply 行**全部是裸乘**（TO 1.23~1.27，Sh 1.23~1.44），平滑版仅 1 行（Sh 0.92 @ TO 0.379）。两个族单独最强（dislocation Sh 1.69 / amplitude Sh 1.44）且相关性未知——若相关性低，合成可同时提 Sh 与分散降 gap；平滑每一腿可保 TO。
- **做法 B（零覆盖算子）**：regression_neutral(信号, 市场或行业基准) / hump(信号, 阈值) 全库 0 次。机理上直接针对第 3 节验证的 TO 病根——去掉信号中的市场/行业系统性成分，剩下 idiosyncratic 新闻漂移，换手来源被结构性切除。
- **数据依据**：TO 由输入噪声驱动（第 3 节结论）；裸乘双族行 TO 全部 >1.2；零覆盖算子是唯一没开图的机制类别；amplitude 族小 gap + dislocation 族高 Sh 的组合有互补性。
- **风险**：无任何先验数据，纯探索，建议小批量（3~5 个表达式）验证后再加码。

**优先级建议**：机制 1 > 机制 2 > 机制 3。机制 1 是唯一同时被"降 TO 有效"（backfill/decay 栈）与"缩 gap 有效"（group 层）两面数据支持的未测交叉；若机制 1 能把 Sh≥1.4 的引擎在 TO 0.4~0.6 复现，再叠加机制 2 的 amplitude 分量与门控，是通向 Sh≥1.63 & TO≤25% 的唯一有数据支撑的路径。

---

## 附录：方法与限制

1. **表达式-元数据关联**：result 文件 `alpha_results[].code` 与同前缀提交文件 `items[].expression` 精确匹配，416/417 行匹配成功；仅 batch_gate1_C 有 1 行无提交记录。
2. **函数参数解析**：使用平衡括号解析（`_w11f_tmp_03_v2.py`），修正了初版正则 `[^,]+` 对嵌套参数漏配的问题（初版曾漏计全部 ts_rank250/bf 窗口）。
3. **去重**：按（表达式, settings 全量 JSON）去重，442 → 417 行。用户口径"426 个有效仿真"与 417 的差异可能来自失败/中止仿真或本目录外的记录文件。
4. **相关度**：Pearson + Spearman 双报，结论对秩相关稳健（排序一致）。
5. **CLUSTER_TEST 口径**：取 checks.warning 中 name=CLUSTER_TEST 的 value；416 行全部有值。
6. **局限**：分组统计中部分 cell 样本小（ts_zscore n=6、SUBINDUSTRY n=8、decay=20 n=8），结论已标注样本量；字段族按表达式所含字段集合划分，多族表达式在各族分别计数（导致各族 n 之和 > 总行数）。
7. **未运行任何回测/仿真，未调用 BRAIN API，未修改任何已有文件**；本报告与 4 个 `_w11f_tmp_*.py` 临时脚本、`_w11f_tmp_rows.json`、`_w11f_tmp_analysis.json`、`_w11f_tmp_analysis_out.txt`、`_w11f_tmp_v2_out.txt`、`_w11f_tmp_v3_out.txt` 为本次分析全部产出。
