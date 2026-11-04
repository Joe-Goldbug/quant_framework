# AEGIS · 战役 V2 简报 · USA/TOP1000/d1 · 全基本面数据集（≤2 数据集/表达式）

> **范围变更（2026-10-29，用户指令）**：不再是 fnd17 单数据集，改为
> **专注 USA TOP1000 基本面数据集，允许跨一个数据集，但 alpha 表达式中最多出现来自两个不同数据集的字段。**
> 目标：**预期回测出高质量无 fail 项的 alpha**。
>
> **纪律不变**：全程禁止调用 Alpha 提交接口；回测 ≠ 提交；达标 alpha 仅本地标记交研究员人工终审。

---

## 0. 本简报基于的免费证据（零回测配额，全部 GET）

| 证据文件 | 内容 |
|---|---|
| `account_alpha_history_full.json` | 本账户全部 1111 条 alpha（OS+IS），含 `is.checks` 扁平数组 |
| `account_alpha_history_v2.json` | 同上 + 设置档 + 日期 + 短项集合 |
| `multids_cold_pool.json` | 10 个基本面数据集的冷字段池（3313 个 MATRIX 字段） |
| `gate_profile.py` / `tier_decision.py` | 门禁可达性与设置档决策表 |

---

## 1. ★★★ 门禁真相（本战役最重要的发现，必须先理解再设计）

### 1.1 「零 fail」的真实含义（988 条 USA/TOP1000/d1 实测反推）

平台 `checks` 在 `alpha['is']['checks']`，是**扁平数组** `[{name,result,value,limit}]`。
同一个不达标指标，有时报 `FAIL`、有时报 `WARNING`。**判别变量不是指标本身，
而是同时有几项硬门禁不达标。**

硬门禁集合：
`LOW_SHARPE / LOW_FITNESS / LOW_2Y_SHARPE / IS_LADDER_SHARPE / LOW_SUB_UNIVERSE_SHARPE /
LOW_ROBUST_UNIVERSE_SHARPE / HIGH_TURNOVER / LOW_TURNOVER / CONCENTRATED_WEIGHT / UNITS`

| 短项数 | n_fail=0 | n_fail>0 |
|---|---|---|
| 0 | 11 | 0 |
| 1 | 15 | 86 |
| 2 | 77 | 133 |
| 3 | 123 | 328 |
| **4** | 6 | **204** |
| 5 | 0 | 111 |
| 6 | 0 | 17 |

**精确规则（两条，零违例）：**
- **R1：`LOW_SHARPE < 1.00` ⇒ 必 FAIL**（782 个 FAIL 样本中 536 个 Sh<1.0，
  206 个 WARN 样本中 Sh 最小值恰为 1.000，**违例 0 个**）。
- **R2：`LOW_FITNESS < 1.00` ⇒ 必 FAIL**（唯一 FAIL=LOW_FITNESS 的 86 行，Fit 范围 0.73~0.98）。

⇒ **「零 fail」不是宽恕，是硬门槛。** 历史上 232 条零 fail 行里，
Sh 最小值 1.000、Fit 最小值 0.310；但**没有任何一条 Sh<1.0 或 Fit<1.0 却零 fail**。

**⚠️ 纠正一处旧记忆**：平台在 `checks.fail` 非空时，`LOW_SHARPE` 与 `LOW_FITNESS`
是**成对出现**的（119/133 个两短项组合是 `('LOW_FITNESS','LOW_SHARPE')`），
且只要 Sh 和 Fit 同时不达标，**两者都是 FAIL**（不是「Sh 降级成 warning」）。

### 1.2 实操门禁表（本战役的验收标准，比"零 fail"更严）

| # | 检查项 | 平台 limit | 要求 |
|---|---|---|---|
| G1 | `LOW_SHARPE` | ≥ 1.58 | **PASS**（不是 WARNING） |
| G2 | `LOW_FITNESS` | ≥ 1.00 | **PASS** |
| G3 | `LOW_2Y_SHARPE` / `IS_LADDER_SHARPE` | ≥ 1.58 **每一年** | **PASS** |
| G4 | `CONCENTRATED_WEIGHT` | ≤ 0.1 | **PASS**（虽然只报 WARNING，但 WARNING 态提交会被拒） |
| G5 | `UNITS` | — | **不得出现** |
| G6 | `LOW_SUB_UNIVERSE_SHARPE` | 平台动态限 | PASS |
| G7 | `LOW_ROBUST_UNIVERSE_SHARPE` | 平台动态限 | PASS |
| G8 | `checks.fail` | 空 | 空 |
| G9 | `CLUSTER_TEST` | — | WARNING 可接受（历史 19 条满门禁样本全是 WARNING） |

### 1.3 ★ 各 neutralization 的能力边界（本战役的设置档铁律）

| neutralization | n | Sh 最大 | 零 fail 率 | σ 中位 | 判定 |
|---|---|---|---|---|---|
| **STATISTICAL** | 788 | **2.40** | **17.8%（基本面）** | 2.60% | **唯一可行档** |
| SUBINDUSTRY | 68 | 1.95 | 0% | 3.12% | 零 fail 率 0 |
| INDUSTRY | 30 | 3.21 | 0% | 8.86% | n 太少 |
| NONE | 194 | 1.17 | 4.5%（全是 fnd69 伪影） | — | 无 Sh≥1.58 样本 |
| MARKET | 28 | 1.07 | 0% | 6.18% | **Sh 天花板 1.07 ⇒ 无 Sh≥1.58 样本** |

**⇒ MARKET 档在本战役被否决**：28 条样本 Sh 上限 1.07，`LOW_SHARPE` 无一 PASS。
这是对 S4Q 裁决（「MARKET+decay0+nanON 为下一批基线」）的**新证据推翻** ——
旧裁决基于零 fail 宽容度，没看到 Sh 硬天花板。

**⇒ 设置档基线 = `STATISTICAL + decay ∈ [0,8] + nan=ON + truncation=0.08`**

### 1.4 σ 门槛（Fit 的物理约束）

```
Fit = Sh·√(Ret / max(TO, 0.125)) ，Ret = Sh·σ
TO < 12.5% ⇒ Fit = Sh^1.5·√(8σ)
```

| Sh | 目标 | 需 Ret | 需 σ |
|---|---|---|---|
| 1.58 | Fit ≥ 1.0 | ≥ 5.01% | **≥ 3.17%** |
| 2.00 | Fit ≥ 1.0 | ≥ 3.12% | ≥ 1.56% |
| 2.20 | Fit ≥ 1.0 | ≥ 2.07% | ≥ 0.94% |

**fnd17 在 STATISTICAL 下的 σ 中位只有 2.60%，P75 3.38%，最大 6.80%。**
⇒ σ 是真实瓶颈：Sh 要抬到 1.58 同时 Fit≥1.0，需要 σ≥3.17%，在 fnd17 的分布里约 P70~P75 位。

**σ 的唯一大杠杆是 `neutralization`（不是 decay）**（已证，见 memory `usa-fnd17-sigma-lever`），
但 MARKET/NONE 的 Sh 天花板又太低。**⇒ 必须在 STATISTICAL 内把 σ 从 2.6% 抬到 3.2%+。**

### 1.5 ★ fnd69 的「高 σ 冠军」是数据伪影（必须知道，否则会走错路）

`xAr0rmLJ`（fnd69，Sh 1.17 / **Fit 1.23** / **Ret 13.83%** / σ 11.8%）看起来是全场最优。
**但年度剖面证明它是覆盖塌陷伪影：**

| 年 | Ret | long | short |
|---|---|---|---|
| 2020 | +2.63% | 436 | 447 |
| **2021** | **+68.04%** | 259 | 257 |
| **2022** | **+43.50%** | **0** | **0** |
| **2023** | 0.00% | **0** | **0** |

PnL 曲线从 2022-11 起完全冻结（`12168054` 一路不变到 2023-12）。
fnd69 字段覆盖率仅 0.39~0.43 ⇒ 覆盖率塌陷期（2021-2023）只剩少数标的，
组合塌缩成"只持有一只票" ⇒ 收益爆炸但零持仓年污染 IS 统计。

**⇒ fnd69 的 NONE 档高 σ 全部作废，不得作为 σ 杠杆的证据。**
**⇒ 任何候选若出现「某年 long=short=0」或「某年 Ret>25%」，一律判为伪影并剔除。**

---

## 2. 数据集优先级（免费证据排序）

| 优先级 | 数据集 | 名称 | 冷字段数 | 覆盖率 | 拥挤度 | 备注 |
|---|---|---|---|---|---|---|
| **P0** | `fundamental89` | Accrual based Earnings Model | 382 | 0.93 | **几乎全 ac=0** | ★ 蓝海，应计质量经典因子 |
| **P0** | `other395` | Accrual based Earnings Model (agg) | 312 | 0.83 | ac=0~1 | ★ 同源但不同前缀（跨集合适用） |
| **P1** | `fundamental3` | Fundamentals for US Equities (10-K/10-Q) | 533 | 0.85 | ac=0~3 | 原始财报科目 |
| **P1** | `other466` | Aggregated Fundamental Data | 385 | 1.00 | ac=0~3 | 覆盖率满分 |
| **P2** | `fundamental13` | Comprehensive Fundamentals | 32 | 0.97 | ac=1~3 | 字段少但覆盖好 |
| **P2** | `fundamental77` | Filing Fundamental (XBRL) | 30 | 0.42 | ac≤3 | 覆盖偏低 |
| **P2** | `fundamental23` | Fundamental Point in Time | 1319 | 0.77 | ac≤2 | 量大，需筛选 |
| **P3** | `fundamental17` | Direct Fundamental (FactSet) | 309 | 0.83 | ac≤2 | 已挖透，天花板 Sh 1.26 |
| **P3** | `fundamental69` | Quarterly Fundamental | 3 | 0.43 | — | ⚠ 覆盖率塌陷，仅 3 个合格冷字段 |
| — | `fundamental90` | Governance/Accounting/Equality | 0 (VECTOR) | 0.77 | — | **50 条历史 alpha，0 零 fail，Sh 上限 0.65 ⇒ 已证死** |

**★ 跨数据集配对建议**（都在 ≤2 数据集限制内，且经济机制互补）：
- `fundamental89`（应计质量） × `other466`（资产负债表科目）—— 质量 × 规模/杠杆
- `fundamental3`（原始科目） × `fundamental89`（应计质量）—— 原始量 × 加工质量
- `other466`（聚合） × `other395`（应计）—— 同源不同前缀，拥挤度低

---

## 3. 已证伪的构造（勿重提）

| 构造 | 证据 |
|---|---|
| 一阶逐期差分（ts_delta 本期−上期） | S1 批次 Sh 上限 0.44 |
| 水平量的行业相对价差（纯 group_rank 差） | S2 批次 Sh 上限 0.89 |
| EUR 冠军骨架直系移植 | S3 批次 Sh 上限 1.11 |
| 幅度保持归一化（winsorize+zscore）优于 group_rank | S4P 证伪：GRP Sh 0.98 vs AMP 0.24 |
| MARKET 档作为下一批基线 | **本次新证据推翻**：MARKET 档 Sh 天花板 1.07 |
| `power` 施加在两条腿内部 | S4A 证伪：两腿各自 power5 后相减 Sh 崩到 0.30 |
| `ts_av_diff` / `ts_mean(winsorize(...))` 时序偏离 | fnd17 全史证伪 |

**存活的结构**：水平量的行业内相对结构（group_rank 差值 / group_zscore）；
**差值之后**施加奇数幂锐化；`ts_backfill` 处理报告期错位。

---

## 4. 设计约束（每个候选必须满足）

1. **≤2 个数据集**（表达式中最多出现来自两个不同数据集的字段）
2. **字段数 ≤3**，算子数 ≤6
3. **零 PV 污染**：不得出现 `close/open/high/low/volume/vwap/returns/adv/cap` 等价量价字段
   （注：基本面字段名里含 `cap` 的要小心，如 `fnd17_capspps` 是每股资本支出，不是市值）
4. **STATISTICAL + decay∈[0,8] + nan=ON + truncation=0.08**
5. **零均值**：顶层必须是差值/秩/zscore 型，保证截面零均值
6. **覆盖护栏**：表达式涉及的所有字段 coverage ≥ 0.50
7. **伪影护栏**：若回测出现某年 long=short=0 或单年 Ret>25% ⇒ 直接判伪
8. **σ 目标**：σ ≥ 3.2%（Ret/Sharpe），否则 Fit 过不了
9. **不是平台门禁但本账户房规**：Margin ≥ 10bp（20·Ret/TO）
10. 产出必须附带：经济机制（counterparty 可证伪）、字段语义、单位量纲、σ 预估、预期换手

---

## 5. Stage 3 装配规则（8 槽批次）

- 8 槽里数据集覆盖要广（≥4 个不同数据集），不得全部押注一个族
- 骨架去重：同一批次内骨架哈希 ≤2 次重复
- 字段指纹跨批次 ≤3 次触碰
- 单一数据集 ≤5 槽（保留 ≥3 槽给跨集/其他族）
- 至少 1 槽做**受控对照**（同表达式不同设置档）或**负控**（预期无效的构造）

---

## 6. 引用

- `STAGE4_S4Q_SETTINGS_VERDICT.md`（S4Q 设置档全交叉）
- `STAGE4_BETA_HALLUCINATION_CHECK.md`（Beta 幻觉核查）
- `STAGE4_S1_FORENSICS.md`（S1 法医报告）
- memory `brain-fail-vs-warning-escalation`、`usa-fnd17-sigma-lever`、`usa-top1000-d1-real-gates`
