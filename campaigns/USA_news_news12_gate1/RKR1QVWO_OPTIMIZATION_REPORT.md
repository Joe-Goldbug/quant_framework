# 种子 `rKR1qVWo` 定向优化终局研报（多 Agent 研究架构）

> 战役目录：`quant_framework/campaigns/USA_news_news12_gate1`
> 批次：`batch_rKR_waveR1~R4_result.json`（4 批 / 32 槽，全部真实回测，STRICT NON-SUBMISSION）
> 完成时间：2026-10-26

---

## 一、种子现状与目标

**种子 `rKR1qVWo`**（USA / TOP1000 / delay 1 / decay 22 / STATISTICAL / trunc 0.025）

```
power(subtract(group_rank(ts_decay_linear(multiply(power(mean_sentiment_score_transfer, 4),
  multiply(winsorize(prob_rank_bin1_10d_img_news, std=2.2), sqrt(news_relevance_score_2))), 10),
  subindustry), 0.5), 5)
```

| 指标 | 种子实测 | 阈值 | 判定 |
|---|---|---|---|
| IS Sharpe | 1.54 | ≥1.58 | ❌ LOW_SHARPE |
| Fitness | 0.78 | ≥1.00 | ❌ LOW_FITNESS |
| Turnover | 16.79% | 5%~50% | ✅ |
| Returns | 4.28% | — | — |
| Margin | 5.10 bps | (内部铁律 10 bps) | ⚠️ 未达标 |
| 2Y Sharpe | 2.10 | ≥1.58 | ✅ |
| Sub-universe Sharpe | 1.07 | — | ✅(未触发) |
| L/S | 439 / 596 | — | ✅ |
| **CLUSTER_TEST** | **1.24** | ≥1.58 | ⚠️ WARNING |
| **MATCHES_THEMES** | 警告 | — | ⚠️ WARNING |

目标：**0 fail + 0 warning**。

---

## 二、多 Agent 研究架构与独立判决

并行部署 4 个独立研究/审计 Agent，全部基于本地 **968 行真实回测实证**，互不通信：

| Agent | 职责 | 核心输出 |
|---|---|---|
| **A 线** 结构移植 | 冠军骨架 × 情绪核 | 偏离层应放在**慢腿**；整条复合高通已被 4 条历史行证伪（−0.22~−0.48 Sh） |
| **B 线** 换手/适应度前沿 | Ret-TO 前沿建模 | 786 行中**不存在** Sh≥1.55 且 TO≤14% 的行；时间平均型换手管理必挂 IS_LADDER |
| **C 线** 字段与拥挤度 | 868 字段全表筛查 | 拟合 `CLUSTER ≈ 0.039 + 0.839×Sharpe + 族/分组拥挤罚项`（R²=0.916） |
| **红队** 盲审 | 物理/数值/合规 | 砍掉主设计 4 槽；去 PV 锚判定为"覆盖度损耗而非信息增益" |

### 三方独立收敛的判决（这是本次研究最重要的结论）

1. **news84 情绪族 199 行实测：maxSharpe 1.56、maxFitness 0.82、maxCLUSTER 1.26，双达标 0/199。**
   种子的信号核（news84 情绪转移分）在 USA/TOP1000/d1 上存在**结构性天花板**，不是参数问题。
2. `CLUSTER_TEST` 零罚项需 `Sharpe ≥ 1.836`；叠加 news84 族拥挤罚项 −0.09 后需 **Sh ≥ 1.94**，
   而该族实测上限 1.56 → **只要表达式里出现 news84 情绪字段，CLUSTER 结构性不可达**。
3. `Fit = Sh × sqrt(Ret / max(TO, 0.125))`：Turnover 压到 12.5% 地板以下后**继续降换手不再加分**，
   唯一有效杠杆是 Returns 与 Sharpe；降换手路线在种子族上已被 4 条历史行（2Y 崩到 1.26~1.43）判死。
4. `MATCHES_THEMES` 警告与"存在 hard fail"完全等价（426/426 行）→ 清掉 hard fail 后自动消失。
   真正的警告墙只有 CLUSTER_TEST。

---

## 三、红队否决记录（避免重复烧配额）

| 原提案 | 红队判决 | 依据 |
|---|---|---|
| 用 `vec_avg(end_of_session_close_price)` 替换 `close` 做"去拥挤锚" | ❌ NO-GO | 该 VECTOR 只覆盖当日有事件的票；数值≈close，不带来新信息，只带来覆盖度缺失 → TO 抬升、Ret 摊薄，正好打在 Fit 的两个变量上 |
| 4 条"情绪核 × 冠军骨架"调制槽 | ❌ NO-GO | news84 族拥挤罚使 CLUSTER 门槛升到 Sh≥1.94，族上限 1.56 |
| 锚拥挤度对照（slot1 vs slot8） | ❌ 冗余 | 两锚数值都≈close，真实变量是 coverage 1.0 vs 0.878，是"缺失值对照"不是"信息对照" |
| 完整 2×2 交互格 | ⚠️ 缺陷 | 缺 MAX×S 一格，且死因同源 |

**主设计因此从 decay 40 / 去 PV 锚 改为 decay 25 / 保留 `close` / 零拥挤分子。**

---

## 四、四批真实回测结果

### Wave R1（decay 25）→ 3/8 全清

| 槽 | 构型 | Sh | Fit | TO | Ret | Mgn | 判定 |
|---|---|---|---|---|---|---|---|
| 1 | MED w5 | **1.97** | 1.21 | 19.2% | 7.23% | 7.5b | 🏆 |
| 2 | MED w6 | 1.92 | 1.19 | 18.1% | 6.91% | 7.6b | 🏆 |
| 3 | MED w7 | 1.85 | 1.14 | 17.3% | 6.55% | 7.6b | 🏆 |
| 4 | MAX w8 | 1.68 | 1.04 | 16.4% | 6.25% | 7.6b | CLUSTER 1.56 |
| 5 | MAX w10 | 1.56 | 0.95 | 15.3% | 5.67% | 7.4b | 3 fail |
| 6 | 分歧腿 (MAX−MED)/close w5 | 1.40 | 0.72 | 18.4% | 4.84% | 5.3b | 3 fail |
| 7 | 分歧腿 w10 | 1.18 | 0.59 | 14.5% | 3.59% | 4.9b | 3 fail |
| **8** | **MED w5 × 种子情绪核** | **1.67** | **0.89** | 16.2% | 4.54% | 5.6b | **LOW_FITNESS + IS_LADDER + CLUSTER 1.54** |

> **Slot 8 是判决性实验**：种子情绪核接入 clean 骨架后 Sharpe −0.30（1.97→1.67）、Fit −0.32、CLUSTER 掉到 1.54。红队预断被证实。

### Wave R2（decay 25）→ 4/8 全清，刷新战役纪录

| 槽 | 构型 | Sh | Fit | TO | Ret | Mgn | 2Y | Sub | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | MED **w3** | **2.05** | 1.23 | 22.5% | **8.06%** | 7.2b | 2.10 | **1.65** | 🏆 |
| 2 | MED **w4** | **2.04** | **1.25** | 20.5% | 7.68% | 7.5b | **2.47** | 1.59 | 🏆 |
| 3 | MED w5 + winsorize | 1.98 | 1.22 | 19.2% | 7.24% | 7.5b | 2.37 | 1.48 | 🏆 |
| 4 | MED w5 @ **industry** | 2.01 | 1.18 | 19.9% | 6.83% | 6.9b | **2.48** | 1.50 | 🏆 |
| 5 | MIN 分子 w5 | 1.19 | 0.53 | 18.9% | 3.78% | 4.0b | 0.93 | 0.99 | 3 fail |
| 6 | 净上调次数腿 w5 | 1.24 | 0.59 | 16.3% | 3.66% | 4.5b | 1.27 | 1.44 | 3 fail |
| 7 | 上调占比腿 w5 | 0.93 | 0.43 | 12.5% | 2.65% | 4.2b | 0.79 | 0.82 | 3 fail |
| 8 | 种子情绪核（加权分子版） | 1.25 | 0.55 | 17.3% | 3.34% | 3.9b | 0.97 | 1.13 | 3 fail |

### Wave R3（decay 40）→ 4/8 全清，Margin 推到 9.0 bps

| 槽 | 构型 | Sh | Fit | TO | Ret | Mgn | 2Y | 判定 |
|---|---|---|---|---|---|---|---|---|
| 1 | MED w2 | 1.84 | 1.15 | 20.6% | 7.99% | 7.8b | 2.40 | 🏆 |
| 2 | MED w3 | 1.89 | 1.22 | 18.6% | 7.79% | 8.4b | 2.02 | CLUSTER 1.57 |
| 3 | MED w4 | **1.90** | **1.26** | 17.2% | 7.57% | **8.8b** | 2.42 | 🏆 |
| 4 | MED w6 | 1.82 | 1.22 | 15.4% | 6.92% | **9.0b** | 2.32 | 🏆 |
| 5 | MED w7 | 1.76 | 1.17 | 14.8% | 6.58% | 8.9b | 2.27 | CLUSTER 1.57 |
| 6 | MED w3 @ industry | 1.92 | 1.19 | 19.4% | 7.45% | 7.7b | 2.12 | CLUSTER 1.54 |
| 7 | MED w4 + winsorize | 1.90 | 1.26 | 17.2% | 7.57% | 8.8b | 2.42 | 🏆（与槽 3 逐位雷同） |
| 8 | MED w7 + winsorize | 1.76 | 1.17 | 14.8% | 6.58% | 8.9b | 2.27 | CLUSTER 1.57（与槽 5 雷同） |

### Wave R4（decay 60）→ 0/8（decay 轴上限确定）

Margin 最高到 9.7 bps（w5~w7），但 Sharpe 掉到 1.64~1.75，**全部触发 CLUSTER_TEST 警告**（1.25~1.44）。decay ≥ 60 路线关闭。

---

## 五、验收结论：11 条 0 FAIL + 0 WARNING

全部 USA / TOP1000 / delay 1 / STATISTICAL / truncation 0.08 / nanHandling ON / pasteurization ON，
`checks.fail = []`、`checks.warning = []`、`ra.ra_failed = false`。

### 🥇 主推交付：`qMLMo6LA`（综合最优）

```
group_rank(subtract(divide(median_bias_adjusted_price_target, close),
                    ts_mean(divide(median_bias_adjusted_price_target, close), 4)), sector)
```
settings：**decay 25** / STATISTICAL / truncation 0.08

| 指标 | 值 | 阈值 | 判定 |
|---|---|---|---|
| IS Sharpe | **2.04** | ≥1.58 | ✅ 超出 29% |
| Fitness | **1.25** | ≥1.00 | ✅ 超出 25% |
| Turnover | 20.5% | 5%~50% | ✅ |
| Returns | 7.68% | — | ✅ |
| Margin | 7.5 bps | (内部 10 bps) | ⚠️ 未达内部铁律 |
| Drawdown | 4.2% | — | ✅ |
| 2Y Sharpe | **2.47** | ≥1.58 | ✅ |
| Sub-universe Sharpe | **1.59** | ≥1.58 | ✅ |
| Long / Short | 576 / 459 | — | ✅ 双边、无 CW |
| CLUSTER_TEST | **无警告** | ≥1.58 | ✅ |
| MATCHES_THEMES | **无警告** | — | ✅ |

### 备选（按不同偏好）

| Alpha | 表达式差异 | Sh | Fit | TO | Ret | Mgn | 2Y | Sub | 适用偏好 |
|---|---|---|---|---|---|---|---|---|---|
| `leAeb3Ax` | 窗口 4→**3** | **2.05** | 1.23 | 22.5% | **8.06%** | 7.2b | 2.10 | **1.65** | 要最高 Sharpe / 最高 Returns / 最高 Sub |
| `bl6l5wRN` | 同构型，**decay 40** | 1.90 | **1.26** | 17.2% | 7.57% | **8.8b** | 2.42 | 1.51 | 要最高 Fitness + 次高 Margin |
| `omEmMd66` | 窗口 6，**decay 40** | 1.82 | 1.22 | **15.4%** | 6.92% | **9.0b** | 2.32 | 1.41 | 要最低换手 + 最高 Margin |
| `e757oxap` | 窗口 5，分组 **industry** | 2.01 | 1.18 | 19.9% | 6.83% | 6.9b | **2.48** | 1.50 | 要最高 2Y 样本外 |

其余 6 条：`QPvPL9vg`(1.98) / `6XdXV0N5`(1.97) / `O0A0Pz2R`(1.92) / `rKRKvxO3`(1.90) / `npvpRqlz`(1.85) / `rKRKvxj8`(1.84)。

---

## 六、本次研究沉淀的结构性定律（可复用）

1. 🔴 **分子拥挤度决定成败**：`median_bias_adjusted_price_target`（alphaCount=0 / userCount=0）
   显著优于 `max`（ac=3）与 `min`（ac=0 但 Sh 仅 1.19）。**零拥挤分子同时给出更高 Sharpe 与零 CLUSTER 警告**——
   这是本次战役全部 11 条达标 alpha 的共同第一要素。
2. 🔴 **窗口轴单调递减**：MED 上 w3(2.05) > w4(2.04) > w5(1.97) > w6(1.92) > w7(1.85)。
   目标价偏离是**短基线更有效**的快变量（与"慢变量应取长基线"的直觉相反）；MAX 分子 w8/w10 已证伪。
3. **decay 是 Margin 与 Sharpe 的交换旋钮**：dec25 → Sh 最高；dec40 → Margin 最高（9.0 bps，仍在清警告区）；
   dec60 → Margin 9.7 bps 但 CLUSTER 系统性崩塌。**dec40 是交换前沿的最优折点。**
4. **winsorize(std=3) 在本构型上是恒等包装**（Wave R3 槽 7≡槽 3、槽 8≡槽 5 逐位雷同），该轴判死。
5. **Fit 地板 0.125 再次复核通过**（E5V905m0：1.87×√(0.0723/0.162)=1.249 ≈ 实测 1.25）。
6. **新增证伪清单（勿重烧）**：news84 情绪核的一切接入形式（乘差分 Sh1.67、乘分子 Sh1.25）；
   `min_bias_adjusted_price_target` 分子；修正次数腿（净额 1.24 / 占比 0.93）；
   分析师分歧腿 (MAX−MED)/close（1.40）；decay ≥ 60；`vec_avg(end_of_session_close_price)` 替代 `close`。
7. **Margin ≥ 10 bps 在本族未达成**：实测天花板 9.7 bps（dec60，但带 CLUSTER 警告），
   零警告区内最高 9.0 bps（omEmMd66）。该指标**不在平台 fail 检查项内**，仅属工作区内部铁律。

---

## 七、诚实声明

- 种子的**直系路线（保留 news84 情绪核）已被两次独立判决性实验证伪**，最终交付的 alpha 属于
  「保留研究起点、迁移经济骨架」的产物——这是实证给出的唯一可行路径，而非回避。
- 全部 32 槽均为平台真实回测，未提交（STRICT NON-SUBMISSION）。
- `PROD_CORRELATION` / `SELF_CORRELATION` 在平台侧恒为 pending，需提交后才出读数；
  提交前建议用 `check_correlation` 只读复核。
