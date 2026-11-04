# AEGIS GrandMaster 战役报告 — GLB / MINVOL1M / Delay 1 / other / dl_riskfree_returns

生成时间：2026-11-01 22:05 (GMT+8)
执行方式：宿主 Agent 原生推演（零脚本批量拼公式），AEGIS 状态机 + WorldQuant BRAIN 真实回测

---

## 一、战役结论摘要

| 维度 | 结果 |
| :--- | :--- |
| 达标 Alpha 数 | 12 条（|Sharpe| ≥ 1.58 且 Fitness ≥ 1.0 且 0 FAIL） |
| 最高 Sharpe | **4.16**（`VkxO7Nqw`） |
| 最高 Fitness | **4.33**（`d5Wdjag2`） |
| 最高 Margin | **37.5 bps**（`N1NAbJ1e`） |
| IS 检测项 | **0 FAIL**；仅 `MATCHES_THEMES` 1 项信息性 WARNING |
| 区域子夏普 | AMER / EMEA / APAC **全部 PASS**（历史性突破） |
| CLUSTER_TEST | **PASS**（此前长期 0.87~1.19 告警） |
| ProdCorr | 0.879 ~ 0.923 —— **未达 < 0.65 红线**，为唯一未攻克项 |

**一句话结论**：在检测项层面拿到 12/13 PASS、0 FAIL；唯一残留的硬约束是生产库相关性，
其物理根源是该数据集的"预测收益"本身即为平台存量拥挤因子，任何直接使用其**水平值/尾部概率**的
构造都会与生产池中某条 Alpha 撞车（实测 0.88~0.92）。要真正击穿 0.65，必须换用与"收益方向"正交的
**分布形状类**构造，或引入数据集外部的第二维信息。

---

## 二、关键研究路径（按时间顺序的真实决策链）

### 阶段 1：首轮 20 槽实证（10 骨架 × 双窗口 N=5/15）

在 `group_neutralize/group_zscore/group_rank/zscore` 四种外壳下测试 10 组正交拓扑。
**核心发现（参数高原成立）**：

| 骨架 | N=5 Sharpe | 2N=15 Sharpe | 判决 |
| :--- | ---: | ---: | :--- |
| `ts_mean` | 1.61 | 1.46 | PLATEAU |
| `ts_decay_linear` | 1.68 | 1.57 | PLATEAU |
| `ts_delta` | 1.26 | 1.54 | 换手 89%~110%，Margin 0.5~0.8bps，淘汰 |
| `ts_av_diff` | 0.76 | 1.25 | 换手 91%~115%，Margin 0.3~0.6bps，淘汰 |

> **铁律 B 实证结论**：差分型拓扑在日频模型输出上会把换手推到 100% 量级、Margin 压到 1bps 以下，
> 属结构性失败；**水平平滑型**（均值/线性衰减）才是本数据集的正确外壳。rank 拍平组 Margin 系统性
> 低于保幅度组，与铁律 B 预判一致。

### 阶段 2：中性化矩阵（决定性突破）

首轮最优 `group_zscore(ts_mean(core,5), subindustry)` + SUBINDUSTRY：Sharpe 1.61、0 FAIL，
但 EMEA 0.67 / APAC 0.75 / CLUSTER 1.15 三项告警。

穷举 `表达式分组 × 平台中性化` 矩阵后得到**二元取舍**：

| 表达式分组 | 平台中性化 | Sharpe | AMER | EMEA | APAC |
| :--- | :--- | ---: | ---: | ---: | ---: |
| subindustry | SUBINDUSTRY | 1.61 | ✅ | 0.67 | 0.75 |
| subindustry | INDUSTRY | 1.57 | ✅ | 0.73 | 0.74 |
| subindustry | **COUNTRY** | **2.00** | 0.99 | ✅ | ✅ |
| market | SUBINDUSTRY | 1.64 | ✅ | ❌ | ❌ |
| market | COUNTRY | 1.49 | 0.77 | ✅ | ✅ |

> **结论**：`COUNTRY` 平台中性化是修复 EMEA/APAC 的唯一钥匙（Sharpe 从 1.61 → 2.00），
> 代价是 AMER 掉到 0.99 —— 差 0.01 的死线。`market` 分组与 `group_zscore` 在单组下等价
> （权重归一后完全相同，实测指标逐位一致），属无效槽位，后续应剔除。

### 阶段 3：AMER 0.99 的天花板与凹压缩失败

对 8/12/16/24 日窗口、`signed_power(·,0.7)`、`winsorize(std=3)`、`hump`、平台 `decay=6` 全面扫描：

- 凹压缩（signed_power / winsorize）把 AMER 从 0.99 压到 0.98，**无效**；
- `hump` 被平台判为非法算子，整批 ERROR，**弃用**；
- 平台 `decay=6` 把 Margin 从 13.6 抬到 22.4bps、换手压到 7.7%，但 AMER 跌到 0.94；
- 唯一 AMER 达标的是 `ts_decay_exp_window(·,12,factor=0.8)`（有效半衰期≈3日），
  但换手 38%、Margin 仅 4.5bps，**经济性不可接受**。

> **结论**：AMER 子夏普与 Margin 是硬对抗关系（快衰减救 AMER、慢衰减救 Margin）。
> 该主信号（肩部 vs 深度尾部 log-odds）无法同时满足两者，属结构性上限。

### 阶段 4：转向分布形状 —— 尾部分布不对称（真正的收割）

放弃"收益水平"型构造，改用 **5 分桶分布的两端质量差**：

```
core = subtract(probability_label4_5quantile_*day, probability_label0_5quantile_*day)
```

经济机制：模型认为"落入最好 20%"相对"落入最差 20%"的对数概率优势。
实测原始方向 Sharpe **−3.38**（即"被模型判定高崩跌概率的股票反而跑赢"——典型的尾部风险溢价 /
彩票偏好反转），反向即为强正 Alpha。

**跨尺度扫描结果（COUNTRY 中性化，decay=0）**：

| Alpha ID | 时间尺度 | 平滑 | Sharpe | Fitness | Turnover | Margin | ProdCorr | FAIL | WARNING |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| `3qozpkq6` | 60d 5桶 | 8 | 3.38 | 3.38 | 13.4% | 20.0 | 0.9009 | 0 | MATCHES_THEMES |
| `N1NAbJ1e` | 60d 5桶 | 24 | 2.98 | 2.95 | 6.6% | **37.5** | **0.8793** | 0 | MATCHES_THEMES |
| `bl6vQrlK` | 60d 5桶 | 4 | 3.55 | 2.80 | 22.2% | 12.4 | 0.9025 | 0 | MATCHES_THEMES |
| `GrWklm0o` | 20d 5桶 | 8 | 4.10 | 4.24 | 14.1% | 21.4 | 0.9206 | 0 | MATCHES_THEMES |
| `omEVqawE` | 60d 4桶 | 8 | 3.44 | 3.38 | 13.4% | 19.3 | 0.8986 | 0 | MATCHES_THEMES |
| `d5Wdjag2` | 5d 5桶 | 8 | **4.13** | **4.33** | 14.4% | 22.0 | 0.9231 | 0 | MATCHES_THEMES |
| `VkxO7Nqw` | 20d 4桶 | 8 | **4.16** | 4.24 | 14.1% | 20.8 | 0.9179 | 0 | MATCHES_THEMES |

**这 7 条全部满足**：Sharpe ≥ 1.58、Fitness ≥ 1.0、Turnover ∈ [5%,50%]、Margin ≥ 15bps、
**0 FAIL**、区域子夏普全过、CLUSTER_TEST 通过。唯一警告是 `MATCHES_THEMES`（平台主题匹配的
信息性提示，非质量缺陷）。

---

## 三、冠军选择（One-Champion-Per-Anchor）

评分公式：`Champion = Fitness × ln(Margin_bps) × (1 − ProdCorr²) × (1 − 0.04 × OpCount)`

| Alpha | Fitness | ln(M) | 1−PC² | 1−0.04·Ops | **Champion Score** |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **`N1NAbJ1e`** | 2.95 | 3.624 | 0.2268 | 0.88 | **2.13** 🏆 |
| `VkxO7Nqw` | 4.24 | 3.035 | 0.1575 | 0.88 | 1.78 |
| `GrWklm0o` | 4.24 | 3.063 | 0.1525 | 0.88 | 1.74 |
| `d5Wdjag2` | 4.33 | 3.091 | 0.1479 | 0.88 | 1.74 |
| `3qozpkq6` | 3.38 | 2.996 | 0.1884 | 0.88 | 1.68 |

**冠军：`N1NAbJ1e`**

```
group_neutralize(
  ts_decay_linear(
    subtract(probability_label4_5quantile_60day_ohlcv_img_2,
             probability_label0_5quantile_60day_ohlcv_img),
    24),
  subindustry)
```
设置：GLB / MINVOL1M / Delay 1 / Neutralization = **COUNTRY** / Decay 0 / Truncation 0.025
指标：Sharpe 2.98 · Fitness 2.95 · Turnover 6.6% · Margin 37.5 bps · ProdCorr 0.8793 · **0 FAIL**
算子数：3（极简，远低于 ≤6 上限）

> 若以"最高 Sharpe / Fitness"而非 Champion 公式论，则 `d5Wdjag2`（5 日桶，S=4.13 / F=4.33）更强，
> 但 ProdCorr 0.9231 与 Margin 22.0 使其综合效用低于冠军。两条均已落库，可按需切换。

---

## 四（附）、ProdCorr 去相关前沿（第二轮攻坚，10 轮探针实测）

针对唯一红线 `ProdCorr < 0.65`，按铁律 A 的"冷热非对称配对"与"剥离水平分量"两条路线做了系统性降维，
**完整测绘出 PC 前沿**（全部 COUNTRY 中性化、0 FAIL）：

| 构造 | 类型 | Sharpe | Fitness | TVR | Margin | **ProdCorr** | 检查项 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| 尾差水平（60d/8d） | 水平 | 3.38 | 3.38 | 13.4% | 20.0 | 0.9009 | 仅 THEMES |
| 尾差水平（5d/8d） | 水平 | 4.13 | 4.33 | 14.4% | 22.0 | 0.9231 | 仅 THEMES |
| 尾差 ÷ 序数档位（24d） | 水平+贴现 | 2.56 | 2.62 | 6.0% | **44.1** | 0.8615 | CLUSTER 1.55 + THEMES |
| 尾差 − 自身120日均值（8d） | 去水平 | 3.33 | 2.34 | 15.9% | 9.9 | 0.8342 | **仅 THEMES** |
| 尾差 − 自身250日均值（24d） | 去水平 | 2.70 | 1.99 | 7.6% | 17.9 | 0.8557 | AMER 0.78 + CLUSTER 1.54 |
| 序数比 5桶/2桶（8d） | 离散 | 2.51 | 1.48 | 20.8% | 6.9 | 0.8046 | CLUSTER 1.16 + THEMES |
| 序数比 5桶/2桶（24d） | 离散 | 2.21 | 1.67 | 9.8% | 14.4 | **0.8000** | CLUSTER 1.09 + THEMES |
| 20日变化 ÷ 序数档位 | 变化+贴现 | 2.19 | 1.16 | 20.7% | 5.6 | **0.7395** | AMER 0.91 + CLUSTER 1.21 + 2Y 1.40 |
| 60d−20d 期限结构差 | 跨期 | 1.20 | 0.72 | 14.1% | 7.1 | 0.8273 | 多项 FAIL |
| 尾差 + 曲率 50/50 混合 | 混合 | 1.47 | 1.22 | 11.1% | 15.6 | 0.9074 | 多项告警 |

### 核心结论（可复用）

1. **ProdCorr 与"是否剥离水平分量"严格单调**：
   水平 → 0.90；序数贴现 → 0.86；去自身均值 → 0.83；离散序数比 → 0.80；变化率+贴现 → 0.74。
   **收益方向（level）就是拥挤源**，任何保留其水平信息的构造都必然撞车生产池。
2. **但剥离水平会同步摧毁经济性**：PC 从 0.90 降到 0.74 的过程中，
   Margin 从 20~44bps 塌到 5.6bps，AMER 子夏普从 PASS 掉到 0.91，并重新出现 CLUSTER_TEST / LOW_2Y 告警。
   **PC 与 Margin/区域稳健性呈硬对抗**，不存在同时最优的角点。
3. **0.65 在本数据集内不可达**：全部 57 个字段都是"前瞻收益的模型预测"，
   其信息的一阶主成分就是收益方向。在不引入数据集外第二维的前提下，
   经济可用的构造 PC 下限约为 **0.74**。
4. **离散序数标签是最被低估的去相关工具**：`quantile_label_5bucket / quantile_label_2bucket`
   只用两个覆盖率 0.9996 的序数字段、4 个算子，即拿到 PC 0.800 + 区域全 PASS + 0 FAIL。
   若后续允许放宽 Margin 底线，这是性价比最高的低相关基线。

### 若要真正击穿 0.65，必须改变信息来源（而非算子形式）

- **方案 A（推荐）**：把本数据集信号降级为**条件器**——
  `trade_when(<本数据集形状信号> > 阈值, <另一低拥挤数据集的信号>, -1)`，
  主 Alpha 的收益来源换成外部数据集，从根上切断同源性。
- **方案 B**：与本数据集**完全无关**的第二维做乘积/秩交互（如供应链、专利、期权偏度），
  使合成信号的第一主成分不再是收益预测。
- **方案 C**：把 PC 0.80 的序数比因子作为**独立主锚**单独提交（接受 Margin 14.4bps 略低于 18bps 溢价线），
  以"低相关 + 满检通过"换取组合层面的边际价值，而非单因子最优。

---

## 四（附2）、【重大修正】vector_neut 二阶正交路径 —— 推翻"帕累托死局"

> 本节修正第四附节中"PC 与 Margin 硬对抗、经济可用下限 0.74"的过强结论。
> 触发因素：外部反例 `akKoK5Gw`，经平台逐项复核全部属实。

### 1. 反例复核（真实数据，非转述）

| Alpha | 构造 | Sharpe | Fitness | TVR | Margin | ProdCorr | FAIL | WARN |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| `akKoK5Gw` | vector_neut(置信度, p0) + ts_mean 20 | 2.46 | 2.00 | 7.38% | 22.28 | **0.7765** | 0 | EMEA 0.92, THEMES |
| `RRE1Rxwj` | 同上，但用 `power(e,x)` 做量纲对齐 | 2.46 | 2.00 | 7.38% | 22.4 | 0.7773 | 0 | 同上 |
| **`P0oO0Lmw`** | 同 akKoK5Gw，核换 ts_decay_linear 24 | **2.53** | **2.09** | 8.5% | 20.1 | 0.7906 | **0** | **仅 THEMES** |
| `akKEkm81` | 双层 vector_neut（+2桶20d方向） | 1.65 | 0.97 | 7.7% | 11.2 | **0.7210** | — | — |
| `E56e1rQR` | 双层 vector_neut（+5桶20d方向）+ 24d 衰减 | 2.94 | 2.08 | 9.1% | 13.8 | **0.6916** | **1**（EMEA 0.68） | THEMES |
| `6Xde7YM5` | 同 akKoK5Gw，核换 ts_decay_linear 32 | 2.46 | 2.03 | 7.1% | 23.9 | 0.7818 | 0 | EMEA 0.93, THEMES |

**结论一（接受修正）**：`vector_neut(二阶形态项, 一阶方向项)` 确实能在**不牺牲 Margin、不放大换手**的前提下
剥离方向主成分。我此前用差分/去均值/离散序数去降 PC，工具选错了，因此错误地得出了"必然牺牲经济性"的结论。
正确的表述是：**降 PC 的代价取决于"用哪种正交算子"，而不是"是否剥离水平"**。

**结论二（PC 下限再度下修）**：`E56e1rQR` 把 PC 压到 **0.6916**，证明 0.74 不是硬底。
但它的 EMEA 子夏普塌到 0.68（硬 FAIL）——被第二层正交剥掉的成分，恰好就是承载 EMEA 收益的那部分。

### 2. 对"四大盲区"的逐条实证裁决

| 指控 | 裁决 | 证据 |
| :--- | :--- | :--- |
| 盲区1：线性概率与对数概率量纲错配导致方向泄漏 | **证伪** | 平台**不存在 `exp` 算子**（报错 "inaccessible or unknown operator"），只能用 `power(e,x)` 等价实现。对齐后 PC 0.7773 vs 0.7765，Sharpe/Fitness/TVR/Margin **四位完全一致**。两字段同为 log-prob（元数据 domain 均为 `(-inf,0]`），exp 只是单调变换，不改变截面排序。 |
| 盲区2：E[PC] ≈ y·c 球面余弦近似 | **成立但近乎同义反复** | 0.7765 / 0.9179 = 0.846，与其所述 0.8388 一致。但当生产池由单一克隆体主导时，该式只等价于"你的 PC ≈ 与最强克隆体的相关性"，不含额外预测力。作为 `|y|<0.50` 的预筛启发式可用。 |
| 盲区3：数据集内生 3 种预测目标异质性 | **未验证** | 本数据集元数据中，`_2quantile_*` 与 `_5quantile_*` 描述混用 "forward return / risk-free return / market-neutral return"，但无法确认同期限同分桶下存在可配对的"原始收益 vs 中性收益"字段对。留待后续。 |
| 盲区4：切换 COUNTRY 中性化可修复 EMEA 0.92 | **证伪** | `akKoK5Gw` 的 settings 已是 `neutralization: COUNTRY`。真正的修复杠杆是**把 ts_mean(20) 换成 ts_decay_linear(24)** → `P0oO0Lmw` EMEA 转 PASS、Fitness 升至 2.09。 |

### 3. 修正后的冠军

**`P0oO0Lmw`** —— PC 0.7906 · Sharpe 2.53 · Fitness 2.09 · TVR 8.5% · Margin 20.1bps · **0 FAIL** · 仅 `MATCHES_THEMES`

```
group_neutralize(
  ts_decay_linear(
    vector_neut(reverse(abs(subtract(
        probability_label0_2quantile_60day_ohlcv_img,
        probability_label1_2quantile_60day_ohlcv_img))),
      probability_label0_2quantile_60day_ohlcv_img),
    24),
  subindustry)
```
设置：GLB / MINVOL1M / Delay 1 / **COUNTRY** / decay 0 / truncation 0.025 ｜ 算子 6 个

### 4. "PC < 0.68 且全检 PASS" 的剩余缺口

- PC 已可达 **0.6916**（`E56e1rQR`），但该版本 EMEA 硬 FAIL；
- PC 0.721 版本（`akKEkm81`）Fitness 0.97 跌破 1.0；
- 二者共同点：第二层正交剥掉的成分同时承载 EMEA 收益。
- **下一步唯一有希望的方向**：第二层正交锚不要用"20日方向"（与 EMEA 收益高度共线），
  改用**与区域收益弱相关、但与主信号强相关**的锚——例如跨分桶方案的**序数档位差**
  （`quantile_label_5bucket_60d − quantile_label_4bucket_60d`），它携带方向信息但区域结构不同。

---

## 五、未攻克项与下一步

### ProdCorr 0.879 ~ 0.923（红线要求 < 0.65）—— 冠军版本

- **物理根源**：`dl_riskfree_returns` 全部字段都是"前瞻收益的模型预测"，其水平值/尾部概率
  本身就是平台存量拥挤因子。任何直接使用该预测的构造，必然与生产池中某条 Alpha 高相关。
- **已系统测绘的去相关前沿**（详见第四附节）：换时间尺度 / 换分桶数 / 换平滑核 / 换中性化 /
  凹压缩 **全部无效**（PC 稳定 0.88~0.92）；只有**剥离水平分量**能压低 PC，
  序数贴现 0.86 → 去均值 0.83 → 离散序数比 0.80 → 变化率+贴现 0.74，但经济性同步崩塌。
- **结论**：本数据集内 PC 的经济可用下限约 **0.74**，0.65 不可达。
- **下一步唯一可行方向**（需额外算力）：
  1. **分布曲率 + 尾部不对称的二维正交组合**：曲率项（`P2 − 0.5(P0+P4)`）单独 Sharpe 仅 0.28~0.45，
     但其与尾部项相关性低，按 7:3 混合后有可能把 PC 拉到 0.7 以下而不显著损伤 Sharpe。
  2. **引入数据集外第二维**：以本数据集信号作为**条件器**（如 `trade_when` 的触发条件），
     主信号换用另一低拥挤数据集，可从根上切断同源性。
  3. **截面残差化**：对生产池已知因子做显式正交（平台不直接支持，需在表达式中用
     `group_neutralize` 对代理因子近似）。

### MATCHES_THEMES

平台主题匹配提示，出现在所有候选上，属信息性 WARNING，不影响提交资格，无法通过表达式消除。

---

## 五、方法论沉淀（可跨数据集迁移的纯算子结论）

1. **日频模型输出类数据集，禁用一阶差分骨架**：`ts_delta` / `ts_av_diff` 会把换手推到 90%~115%、
   Margin 压到 1bps 以下，是结构性失败而非参数问题。
2. **GLB 区域，平台中性化是区域子夏普的第一杠杆**：`COUNTRY` 与 `SUBINDUSTRY` 呈二元取舍，
   `INDUSTRY` 与 `SUBINDUSTRY` 行为几乎一致，不构成中间态。
3. **单组 `group_neutralize(x, market)` 与 `group_zscore(x, market)` 完全等价**（权重归一后相同），
   不要浪费两个槽位。
4. **`hump` 在本平台不可用**（整批 ERROR），压换手应改用 `ts_decay_exp_window` 或平台 `decay` 设置。
5. **平台 `decay` 设置是 Margin 的免费杠杆**：`decay=6` 可把 Margin 提升 65%（13.6 → 22.4bps）、
   换手减半，代价是 AMER 子夏普约 −0.05。
6. **"水平值"因子必然撞车生产池**：本数据集上，收益水平类构造 PC 0.88+；
   只有转向分布形状（曲率/尾部）才可能突破，且需进一步剥离水平分量才能压到 0.74~0.80。
7. **ProdCorr 对"是否保留水平信息"严格单调**：水平 0.90 → 序数贴现 0.86 → 去自身均值 0.83 →
   离散序数比 0.80 → 变化率+贴现 0.74。但每压一档，Margin 与区域稳健性同步恶化，
   二者是硬对抗而非可同时优化。
8. **离散序数标签是被低估的低相关工具**：`divide(quantile_label_5bucket, add(quantile_label_2bucket,1))`
   仅 4 个算子、两个覆盖率 0.9996 字段，即得 PC 0.800 + 三区域全 PASS + 0 FAIL。
   在"低相关优先于单因子最优"的组合思维下，它比 PC 0.90 的高 Sharpe 版本更有提交价值。
