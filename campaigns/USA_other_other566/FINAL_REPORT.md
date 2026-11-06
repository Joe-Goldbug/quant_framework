# USA / Delay-1 / TOP1000 — other566 战役报告

> **⚠ 本文档已由后续波次扩展。** 波次 26–33（跨数据集放行后）新增 32 槽、平台门通过数 5→8，
> 并确立了符号陷阱 / 尺度 bug / 中心化有界秩三条工程规律。
> 最新结论见 **`CROSS_DATASET_26_33.md`**；本文件保留波次 1–25 的原始记录。

**数据集**: other566 — FinChart 多层级订单簿形态识别前向收益预测模型
**主题**: USA/D1 TOP1000 Theme (2X regular / 3X Python), 金字塔 `USA/D1/OTHER` (1.4x, 点塔目标)
**规模**: 24 批 × 8 槽位 = 192 个表达式, 189 个成功回测解析
**工具链**: Direct Alpha Miner (skill) + brain-mcp 多重回测

---

## 1. 数据集经济学分层 (全部 51 字段, 均 MATRIX, coverage ≥ 0.9999)

other566 是**纯预测层数据集** —— 全部字段都是机器学习模型对「未来 N 日收益」的**输出**, 而非原始行情特征。
这决定了整个战役的四条设计原则:

| 字段族 | 代表字段 | 拥挤度 | 角色 |
|---|---|---|---|
| 方向/水平 | `oth566_r20marsi_ret` (71u/90a) | 极拥挤 | 预测力来源, 但直接交易 = 撞生产库 |
| 信念 | `oth566_r20marsi_prob_5` (1u/1a) | 极冷 | 去拥挤主力 + 自动收缩低信念个股的死重仓位 |
| 形态 | `oth566_multil3_prob_pattern` (0u/0a) | 最冷 | 信念迁移, 接近信息到达的可观测量 |

**符号陷阱 (已在全部槽位规避)**: `oth566_l2r20_prob` / `oth566_l5r20gasfculr_prob_3` / `_prob_5`
的描述是「log-probabilities」, 水平为**负**。裸乘会翻转信号方向。这些字段只经
`ts_zscore` / `ts_delta` / `group_rank` 使用。

---

## 2. 战役的核心发现

### 2.1 `ts_mean` 是本数据集最大的信号杀手

| 结构 | Sharpe | 平台 FAIL |
|---|---|---|
| `group_rank(ts_mean(multiply(ret, prob5), 26), subindustry)` | 0.66 | 3 |
| `group_rank(multiply(ret, prob5), subindustry)` | **1.18** | **0** |

统计 (54 + 8 槽位): `ts_mean` 存在时 meanSharpe **0.292**; 不存在时 meanSharpe **0.836** (2.9x)。
机理: 模型**每日重训重估**, alpha 承载在「观点冲击」而非水平; 26 日平坦平均把脉冲式信号冲击洗掉了。

### 2.2 `trade_when` 新鲜度门控在此数据集**恒真**

b7_t1(对水平 delta 1) / b7_t2(delta 5) / b7_t6(对 prob_5 做 delta) 三个槽位返回**逐位相同**的指标
(Sh 1.18 / TO 46.54% / Mgn 1.78bps / PnL 4128731 vs 4128689) ⇒ 模型每天重发预测, 「预测未更新」事件不存在。
真正起作用的是「去掉 ts_mean」, 不是门控本身。

### 2.3 真正的死线是 Fitness, 不是 Margin

平台指标恒等式 (已在 4 个槽位上逐位验证):
```
margin_bps = returns / turnover × 20
fitness    = sharpe × sqrt(returns / max(turnover, 0.125))
```
联立 AEGIS 生产门 (Mgn ≥ 10bps, Fit ≥ 1.00):
```
Mgn ≥ 10  ⟺  returns/turnover ≥ 0.50
Mgn ≥ 10 且 Fit ≥ 1.0  ⟹  Sharpe ≥ 1.414   (必要条件)
在换手 T 处:  returns ≥ 0.5T,  且  T=10% 时 Sharpe ≥ 1.58
```
⇒ 唯一可行格是 **T ≈ 8-12%, returns ≈ 4-6%, Sharpe ≥ 1.58**。

### 2.4 平台 `neutralization` 是被严重低估的杠杆

| neutralization | Sharpe | Fitness | Margin | TO | 2Y Sharpe | FAILs |
|---|---|---|---|---|---|---|
| **STATISTICAL** | **1.27** | 0.59 | 4.37 | 13.9% | **1.86** | 0 |
| NONE / MARKET / INDUSTRY | 1.00 | 0.61 | 7.39 | 12.5% | 1.12 | 0 |
| SUBINDUSTRY | 0.83 | 0.42 | 5.14 | 12.8% | 0.57 | 3 |

- NONE / MARKET / INDUSTRY **逐位相同** —— 对美元中性多空组合, 「剥离市场 beta」与「保留 beta」构造同一本账。
- **STATISTICAL 最高**: 剥离市值/beta/波动率等共同统计因子, 保留行业条件性成分。
- **SUBINDUSTRY 明显更差** ⇒ 本 alpha 的边缘**部分来自行业层面**的订单簿流动性状态信号。
- **中性化偏好随腿而变**: r20marsi 腿偏爱 STATISTICAL (Sh 1.27 vs 1.00);
  2 日期腿 (`oth566_return`) 偏爱 INDUSTRY (R 4.84%/Mgn 8.03 vs STAT R 2.50%/Mgn 3.50)。

### 2.5 账本形状 (book shape) 才是「单位换手收益」的杠杆

`margin_bps = returns/turnover×20` 直接指向 R/TO。而提高 R/TO 的手段不是平滑, 是**权重集中度**:

| 结构 | Sharpe | Fitness | Margin | R/TO | TO |
|---|---|---|---|---|---|
| `quantile(x, driver="gaussian")` @ tvr0.12 | 1.28 | **0.62** | 4.65 | — | 14.0% |
| `quantile(...)` @ ret2 腿 tvr0.12 | 0.96 | 0.63 | **8.61** | 0.430 | 12.6% |
| `signed_power(subtract(group_rank(x),0.5), 2.25)` | 1.01 | 0.53 | 6.00 | 0.410 | 9.6% |
| `quantile(...)` @ dexp20 | **1.65** | 0.40 | 1.20 | — | 67.6% |

机理: `group_rank` 的 0.5 是横截面中位数; 减 0.5 中心化后 `signed_power(v, p>1)` 放大偏离中位数的幅度
⇒ 预测分布的中间区域 (模型说「没发生什么」) 仓位极小, 两端仓位大 ⇒ PnL/交易上升。

### 2.6 已证伪的机制 (全部 Sharpe < 0.95)

跨模型共识 (B03) / 跨模型分歧 (B04) / 期限结构 (B05) / 形态信念迁移 (B06) / 预测修正 (B02 重测 + B14) /
置信加权网格 (B09) / 置信腿历史标准分 `ts_zscore(prob)` (B16: Sh 0.50-0.68, 远差于原始 prob)。

**唯一站住的机制链**:
`信念加权 (原始 prob) × 幅度保留外层 (group_zscore 或 quantile) × 换手杠杆 (tvr / exp-decay) × 中性化 (随腿而变)`

### 2.7 跨数据集补位 (满足 theme)

`insider_feats` 的 category = **other** ⇒ 与 other566 **同属 USA/D1/OTHER 金字塔**, 满足 theme 要求。
仅 9 用户/10 alpha, 多个字段 0/0。但内部人冷源本身 Sharpe 为负 (-0.10), 组合最高只到 Sh 0.58 ——
**内部人信号在 USA/D1/TOP1000 单独不可用**, 仅作「信念权重」叠加时有正贡献。

---

## 3. 最终结果

### 3.1 平台门通过 (0 FAIL + 已核实相关性)

| alpha_id | 批次 | 槽位 | Sharpe | Fitness | Margin | TO | 2Y | CLUSTER | ProdCorr | SelfCorr |
|---|---|---|---|---|---|---|---|---|---|---|
| `58EgOP31` | B21 | w21_q_dexp20 | **1.65** | 0.40 | 1.20 | 67.6% | 2.30 | 1.05 | 0.6267 | 0.1877 |
| `kqNgXQqd` | B17 | w17_neu_stat_t12 | 1.27 | 0.59 | 4.37 | 13.9% | **1.86** | 0.95 | **0.5052** | **0.1492** |
| `1YNZEMrJ` | B13 | w13_d0_tvr15 | 1.00 | 0.55 | 6.00 | 15.6% | 1.16 | 1.10 | 0.6246 | 0.1835 |
| `mLo6OXLx` | B15 | w15_tvr12_d0 | 1.00 | **0.61** | 7.39 | 12.5% | 1.38 | 1.12 | 0.6477 | 0.1892 |
| `d5W1lzjx` | B19 | w19_ret2_dexp20 | **1.73** | 0.41 | 1.14 | 73.1% | 2.20 | **1.60** | 0.6466 | 0.2389 |

全部 ProdCorr < 0.70 且 SelfCorr < 0.70 ⇒ **相关性维度全面达标**。

### 3.2 AEGIS 内部门: 0 个通过

| 门槛 | 最好成绩 | 缺口 |
|---|---|---|
| Sharpe ≥ 1.58 | 1.73 (`d5W1lzjx`) | 达标但 TO 73.1% 越限 |
| Margin ≥ 10 bps | 10.39 (w15_tvr05_d0) | 达标但 Sharpe 仅 0.66 |
| Fitness ≥ 1.00 | 0.63 (w21_q_ret2_tvr12_ind) | **未达标** |
| Turnover ≤ 50% | 12.5% (w15_tvr12_d0) | 达标但 Sharpe 仅 1.00 |

**根因**: 在 STATISTICAL 中性化下, returns 几乎是常数 (~2.3%-4.6%), 因此任何降换手的平滑都**同比**降 Margin,
而保 Sharpe 的 exp-decay 家族必然高换手。R/TO 与 Sharpe 在本数据集上是**结构性互斥**的两端。

### 3.3 冠军选优 (AEGIS 公式: Fitness × ln(Margin) × (1-ProdCorr²) × (1-0.04×OpCount))

| 排名 | alpha_id | CS | Sharpe | Fitness | Margin | ProdCorr | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | `mLo6OXLx` | **0.623** | 1.00 | 0.61 | 7.39 | 0.6477 | 综合最优; 低换手 + 最高 Fitness + 0 FAIL |
| 2 | `kqNgXQqd` | 0.570 | 1.27 | 0.59 | 4.37 | **0.5052** | 最低 ProdCorr; 2Y Sharpe 1.86 |
| 3 | `1YNZEMrJ` | 0.529 | 1.00 | 0.55 | 6.00 | 0.6246 | — |
| 4 | `58EgOP31` | 0.039 | **1.65** | 0.40 | 1.20 | 0.6267 | 最高 Sharpe + quantile 形状 |
| 5 | `d5W1lzjx` | 0.026 | **1.73** | 0.41 | 1.14 | 0.6466 | 最高 Sharpe + 最高 CLUSTER 1.60 |

### 3.4 推荐提交顺序 (依 AEGIS 铁律「一主锚一代表」)

1. **`kqNgXQqd`** — `group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), target_tvr=0.12), industry)`
   @ STATISTICAL / decay=0 / trunc=0.08。最低 ProdCorr (0.5052)、最低 SelfCorr (0.1492)、2Y Sharpe 1.86、
   0 平台 FAIL、CLUSTER 0.95。**相关性余量最大, 最适合点 USA/D1/OTHER 金字塔。**
2. **`58EgOP31`** — `quantile(ts_decay_exp_window(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 20, factor=0.7), driver="gaussian")`
   @ STATISTICAL。Sharpe 1.65 / 2Y 2.30 / 0 FAIL, 备选高 Sharpe 锚。
3. **`mLo6OXLx`** — 同结构但 tvr=0.12 @ INDUSTRY。综合分最高 (0.623), 若需更高 Fitness 则选它。

---

## 4. 战役统计

| 指标 | 值 |
|---|---|
| 批次 × 槽位 | 24 × 8 = 192 |
| 成功解析 | 189 |
| Step 1 (Sharpe ≥ 1.0) | 55 |
| 0 平台 FAIL | 50 |
| 平台门通过 (含已核实相关性) | **5** |
| AEGIS 内部门通过 | 0 |
| 已核实 ProdCorr / SelfCorr | 5 / 5, 全部通过 0.70 |
| 字段数 | 2 (全部槽位) |
| 算子数 | ≤ 6 (全部槽位) |

---

## 5. 产出文件

| 文件 | 内容 |
|---|---|
| `batch_01..24.json` | 每批 8 个表达式 + 经济学假设 + 每槽位理由 |
| `batch_01..24_result.json` | 平台原始回测结果 (逐 alpha 的 is/metrics/checks) |
| `exploration_ledger.json` | 192 槽位扁平台账 (指标 + 三级门禁 + 冠军分) |
| `campaign_champions.json` | 冠军 + 亚军 + 平台门通过名单 + 门禁阻塞原因 |
| `correlations.json` | 5 个已核实的 ProdCorr / SelfCorr |
| `ideas.md` | 18 个经济概念 (Direct Alpha Miner 格式, 在 `trailSomeAlphas/.../USA_delay1_other566_ideas.md`) |
| `final_expressions.json` | 20 条 AST 校验通过的表达式 |

## 6. 诚实的结论

**AEGIS 内部门 (Fitness ≥ 1.00 + Margin ≥ 10bps + TO ≤ 50%) 在本数据集上没有被突破。**
这不是配额或运气问题 —— 24 个波次、192 个槽位覆盖了 6 大类机制 (置信加权 / 修正 / 共识分歧 /
期限结构 / 形态迁移 / 账本形状) 与 4 个平台设置维度 (decay / neutralization / truncation / 平滑器)。

代数给出硬约束: 在 STATISTICAL 中性化下 returns 近似常数, 故
**Sharpe ≥ 1.58 与 Margin ≥ 10bps 在本数据集上互斥**; 唯一理论可行格 (T≈10%, R≈5%, Sh≈1.58)
要求把单位换手收益提高约 3 倍, 而 24 波次的全部杠杆 (平滑器 4 种 × 中性化 5 种 × 外层 5 种)
最多只把 R/TO 推到 0.521 (w15_tvr05_d0, 但 Sharpe 仅 0.66)。

若要继续突破, 应当换的**不是**参数, 而是**信息源**: 需要一个与 FinChart 订单簿预测正交、
且自身 Sharpe 更高的腿 (例如真正的基本面意外 / 盈利修正), 以便在**不增加换手**的前提下抬高 returns。
internal 门未过的事实已如实记录在 `campaign_champions.json` 的 `status: NO_PRODUCTION_PASS`。
