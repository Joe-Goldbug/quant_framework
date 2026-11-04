# AEGIS 战役审计报告 · fundamental90 / USA / TOP1000 / delay=1

> 总控：aegis-orchestrator　|　完成时间：2026-10-28
> **硬约束遵守声明：全战役提交接口调用次数 = 0。所有候选 Alpha 状态均为 `UNSUBMITTED`，仅本地标记，等待研究员人工终审。**

---

## 一、战役参数与最终裁决

| 项目 | 值 |
| :--- | :--- |
| REGION / UNIVERSE / DELAY | USA / TOP1000 / 1 |
| CATEGORY | fundamental90（平台分类 `fundamental`，全程未跨入 `pv`） |
| TARGET_DATASETS | fundamental 家族（锁定 fundamental90，133 字段） |
| 实测批次 | 5 批（R1 种子筛选 / R1 生产设置复测 / R3 / R4 / R5）+ 2 次单点物理探针 |
| 累计实测表达式 | 32 条（含复测） |
| **达标可提交 Alpha** | **0 条** |
| 提交接口调用 | **0 次** |

---

## 二、Stage 1 数据集物理画像（已落盘 `knowledge_base/fields/USA/fundamental90.json`）

**数据集体检**

| 指标 | 值 | 判读 |
| :--- | :--- | :--- |
| 字段数 | 133（全部 VECTOR） | 事件型，需 `vec_*` 降维 |
| 覆盖度 | 0.774 | 中高 |
| 平台 Alpha 使用数 | **135** | 极低拥挤度 |
| valueScore | **5.0**（最高档） | 平台给予最高价值评级 |
| 研究员存量使用 fnd90 的 Alpha | **0 / 470** | 完全未开垦，ProdCorr 撞车风险极低 |

**语义角色分布**：Signal_Flow 81 / Uncertainty_Scale 28 / Catalyst_Event 12 / Dimension_Anchor 12

**家族结构**（关键）
- `fnd90_game_*`（全球口径，覆盖度随字段变动 0.271~0.870）
- `fnd90_us_game_*`（美国口径，统一覆盖 0.828，描述带 `[Ascending]/[Descending]` 与 `[Quality.*]` 方向标签）
- `fnd90_*qes_gamef_*`（QES 法证综合分：Piotroski、Ohlson、Mohanram、C-Score、CHS 违约概率、icfroe）
- 3 个独立表外索取权比率（或有负债/权益、非流动资产占比、优先股占比）

**实测物理基准**（alpha `ZYQGwX9n = ts_zscore(vec_avg(fnd90_game_noa), 252)`，NONE/decay0）
`Sharpe 0.19 | turnover 46.29% | returns 1.46% | margin 0.63bps | Long:Short 373:337（多空比 1.107，无零膨胀死重）`

---

## 三、五阶段执行轨迹与关键判决

### Stage 2 · 8 问正交种子池（零回测）
8 条机制完全正交的种子（Q1 不变性 / Q2 动态 / Q3 异常 / Q4 协同 / Q5 结构 / Q6 累积 / Q7 相对 / Q8 预期差），
字段数 2、数学算子 ≤4，全部通过 AST 量纲编译器（Gate 2）与双盲红队审判（Gate 1），8 个拓扑骨架全唯一。

### Stage 3 · 阶梯漏斗回测
R1 全批熔断（最高 |Sharpe| 0.57）。法医诊断发现**回测物理条件配置错误**：

| 设置项 | R1 使用 | 账户 70 条已提交 Alpha 的实际分布 |
| :--- | :--- | :--- |
| Neutralization | NONE | SUBINDUSTRY 34 / INDUSTRY 20 / STATISTICAL 7 |
| Decay | 0 | 4 共 25 条，其次 8、5、10 |
| Truncation | 0.025 | 0.08 共 40 条 |

改为 `SUBINDUSTRY / decay=4 / trunc=0.08` 后，最优槽位 Sharpe 由 **-0.00 → 0.46**。

### Stage 4 · 处方化攻坚（三次迭代）

**处方一（R3）——改 `rank` 均匀映射**：失败。全批最高 0.21。但意外暴露真病灶：

| 构造 | 换手 | Margin | CONCENTRATED_WEIGHT |
| :--- | :--- | :--- | :--- |
| `-rank(add(vec_avg(A), vec_avg(B)))` | 42.5% | -0.18 bps | FAIL |
| `-rank(add(ts_mean(vec_avg(A),20), ts_mean(vec_avg(B),20)))` | **2.4%** | **+3.26 bps** | **PASS** |

**确诊**：fnd90 是稀疏事件序列，非事件日为 NaN；未平滑的持仓在 NaN 进出间反复重排，制造 42~52% 伪换手并吃光 Margin。

**处方二（R4）——时序平滑外移至最外层**：成功。
`ts_mean(subtract(ts_zscore(cash_flow_coverage,252), ts_zscore(short_term_debt,252)), 20)`
→ **Sharpe 0.62 | Margin 10.24bps（突破 USA 10bps 死线）| 换手 3.7% | SubU 0.73 | CW 消失**

**处方三（R5）——母本纵深**：触及天花板 0.65，10/10 年正收益。

---

## 四、Gatekeeper 全维度诚实审计表（Top 6，零隐瞒）

| # | Alpha ID | 表达式 | IS Sharpe | 2Y | Fit | Margin(bps) | TO% | SubU | Cluster | L:S | 正收益年 | 未达标根因 |
| :-- | :--- | :--- | --: | --: | --: | --: | --: | --: | --: | --: | --: | :--- |
| 1 | `ZYQGlpXQ` | `ts_mean(subtract(ts_zscore(vec_avg(cash_flow_coverage),252), ts_zscore(vec_avg(short_term_debt),252)), 10)` | **0.65** | 0.47 | 0.26 | 8.67 | 4.57 | 0.66 | 0.15 | 297:292 | **10/10** | Sharpe/Fit/Margin/换手下限/平台 LOW_SHARPE |
| 2 | `mLo9AnO1` | 同上，外层窗 20 | 0.62 | 0.35 | 0.24 | **10.24** | 3.72 | 0.73 | 0.17 | 297:292 | 9/10 | Sharpe/Fit/换手下限 |
| 3 | `RREWapl1` | `rank(...同上...)` | 0.60 | 0.51 | 0.22 | 10.26 | 3.41 | **0.76** | 0.15 | 295:295 | 9/10 | Sharpe/Fit/换手下限 |
| 4 | `leAXzVG2` | `winsorize(ts_mean(subtract(ts_zscore(coverage),ts_zscore(eff_interest_rate)),20),std=3)` | 0.58 | 0.18 | 0.22 | 10.97 | 3.29 | 0.64 | 0.21 | 281:281 | 9/10 | Sharpe/Fit/换手下限 |
| 5 | `A1VKYLPg` | `subtract(ts_zscore(coverage,252), ts_zscore(noa,252))` | 0.46 | -0.08 | 0.08 | 0.64 | 44.83 | 0.33 | 0.03 | 303:290 | 未测 | 未平滑 → 44.8% 换手 + CW |
| 6 | `VkxJqM3A` | `-add(ts_zscore(inventory_chg,252), ts_zscore(receivable_chg,252))` | 0.43 | 0.31 | 0.07 | 0.50 | 44.58 | 0.29 | 0.21 | 307:313 | 未测 | 同上 |

**全部 32 条实测候选的共同 WARNING（无一漏报）**：`CLUSTER_TEST`（0.03~0.29，限 1.58）、`MATCHES_THEMES`。
**ProdCorr / SelfCorr 状态：PENDING** —— 平台仅在提交后计算，本战役严禁提交，故无法给出数值（不编造）。

---

## 五、为何判定"不具备提交级可行性"（定量缺口证明）

平台 Margin 与换手存在实测恒等关系（两条独立 alpha 精确吻合）：

```
margin_bps = returns_bps / (504 × turnover_frac)
  校验: mLo9AnO1 → 191 / (504 × 0.0372) = 10.24 bps  ✓ 实测 10.24
        ZYQGlpXQ → 198 / (504 × 0.0457) = 8.59  bps  ✓ 实测 8.67
```

由此推导 AEGIS 双门槛的联立约束：

| 目标 | 要求 | 当前最优 | 缺口 |
| :--- | :--- | :--- | :--- |
| Margin ≥ 10bps 且 换手 ≥ 5% | 年化收益 ≥ **2.52%** | 1.98% | +27% |
| Sharpe ≥ 1.58（波动 3.05% 不变） | 年化收益 ≥ **4.82%** | 1.98% | **×2.4** |

即：**在不改变信号振幅的前提下，本数据集的 Margin 门槛与换手下限互相冲突，且 Sharpe 缺口达 2.4 倍。**
继续微调参数属无效搜索，故按阶梯早停规则停止发散。

---

## 六、被证伪的假设（已写入 `knowledge_base/falsified_vault.json`，FALS_F90_001~004）

1. **`fnd90` 是 MATRIX 标量** → 证伪。实为 VECTOR 事件型，`ts_*` 裸用被平台拒绝，必须 `vec_*` 降维。
2. **裸 z-score 合成即可** → 证伪。产生 44.6% 伪换手、Margin 0.5bps、CW FAIL。
3. **`rank` 均匀映射能救活弱信号** → 部分证伪。能修 CW 并抬 SubU（0.76），但对 Sharpe/Fitness 无实质提升。
4. **逐腿平滑等价于外层平滑** → 证伪。逐腿平滑（R5 Slot5）Sharpe **-0.13**，外层平滑 0.60，平滑位置必须外置。
5. **表外养老金 / 困境三重风险（C 分-O 分-CHS）/ 现金转换周期** → 均证伪（Sharpe -0.30 ~ -0.05）。

## 七、成功算子范式（已沉淀至 `knowledge_base/cards/fundamental90_operator_paradigm.json`）

| 范式 | 抽象模式 | 实测增益 |
| :--- | :--- | :--- |
| 类型降维前置 | `ts_*(vec_avg(字段), 窗口)` | 从"平台拒绝"到"可回测"的唯一入场券 |
| **外层时序平滑消死重** | `ts_mean(<因果合成>, 20)` | 换手 42.5%→3.7%，Margin -0.18→10.24bps，CW FAIL→PASS |
| 去中枢后减法（符号守恒） | `subtract(ts_zscore(A,252), ts_zscore(B,252))` | 全部正 Sharpe 候选均出自此结构 |
| 截面排序拉平持仓 | `rank(<外层平滑后的合成>)` | SubU 0.73→0.76，CW 消除 |

---

## 八、给研究员的下一步建议（非提交类）

1. **换宇宙而非换参数**：本账户 58/70 的达标 Alpha 在 TOP3000。fundamental90 在 TOP1000 的一阶/二阶构造天花板仅 0.65，
   建议同一批表达式改跑 TOP3000（大票基本面在大票池已被充分定价）。
2. **换时间维度构造**：本数据集更新频次极低（换手可压到 2~4%），适合做成**低换手长期持有型**因子，
   而非追求高 Sharpe；可考虑与 `anl*`/`mdl*` 类高频数据集做**跨数据集二阶残差**（需放开单数据集限制）。
3. **若要冲刺 Sharpe**：需引入与基本面正交的信息源（本战役受 `TARGET_DATASETS: fundamental` 约束，无法引入）。
