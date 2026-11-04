# Gate 1 终审报告 — USA/TOP1000/delay1 · 分析师目标价隐含预期差（PT Expectation Gap）

**立项依据**：news7 语料族在 4 波 32 槽 + 前役 336 槽中被实证封顶（|Sh|≥1.58 的行 TO 全部 ≥116.9%，TO≤70% 分支 Sh 上限 1.19）。
**转向依据**：`bl8Wd2Nq` 是账户内唯一 `checks.fail=[] & warning=[]` 的实证通道（PT/close 隐含收益率折价修复）。
**mandate**：2≤字段≤3；不限算子；每批 8 条多重回测；目标 = 零 fail + 零警告；**严禁提交**。

---

## 0. 最终交付（PASS_ALL）

```
group_rank(subtract(divide(max_bias_adjusted_price_target, close),
                    ts_mean(divide(max_bias_adjusted_price_target, close), 6)), sector)
```

| 项 | 值 |
|---|---|
| **alpha ID** | **`vROQVzlA`**（UNSUBMITTED，未提交） |
| settings | USA / TOP1000 / delay 1 / decay **18** / **STATISTICAL** / truncation **0.08** / nanHandling **ON** |
| 字段数 | **2**（`max_bias_adjusted_price_target`, `close`） |
| Sharpe | **1.86**（门 ≥1.58） |
| Fitness | **1.09**（门 ≥1.00） |
| 2Y Sharpe | **2.19**（门 ≥1.58） |
| Sub-universe Sharpe | 1.45（门 ≈0.53×Sh） |
| Turnover | **20.55%**（门 ≤70%） |
| Returns | 7.00% |
| Drawdown | 4.00% |
| Margin | 6.82 bps |
| Long/Short | 555 / 481（多空均衡） |
| Investability | Sh 1.70 / Fit 0.97 |
| **ra_failed** | **false**，failed_ra_count = **0** |
| **checks.fail** | **[]** |
| **checks.warning** | **[]** |
| checks.pass | LOW_SHARPE / LOW_FITNESS / LOW_TURNOVER / HIGH_TURNOVER / CONCENTRATED_WEIGHT / LOW_SUB_UNIVERSE_SHARPE / **IS_LADDER_SHARPE** / **CLUSTER_TEST** / MATCHES_PYRAMID / MATCHES_THEMES |
| 金字塔 | **USA/D1/PV (×1.1) + USA/D1/ANALYST (×1.2)**（eff 2） |
| 逐年 Sharpe | 1.39 / 0.45 / 2.36 / 1.16 / 0.69 / 2.37 / 3.16 / 3.06 / 2.42 / 0.74 → **10/10 年为正，无负年** |
| ⚠ PROD_CORRELATION | **0.8554 ≥ 0.70（提交口径不过；按纪律未提交）** |

### 经济学机制
分析师共识目标价上限（最乐观者）换算成隐含收益率 `max_PT/close`，减去其自身 6 日常态 → 「最乐观分析师的估值上限相对股价的短期折价」。
股价一次性下挫会抬高该隐含收益，而分析师目标价调整滞后（粘性报价），市场对目标价信息反应不足 → 折价随后数周被修复。
`sector` 组内 rank 剥离行业估值中枢漂移；`STATISTICAL` 中性化剥离规模/价值/动量等风格；`decay 18` 把日频抖动抹平、换手压到 20%。
`max` 口径是最乐观分析师——它反映「最看好者愿意给的价格」，对正面催化最敏感且领先共识 1~2 周。

---

## 1. 三批 24 槽全记录

### Batch 1（8 槽）— 机制铺开

| # | 变体 | Sh | Fit | 2Y | TO% | fail | warn | 判读 |
|---|---|---|---|---|---|---|---|---|
| 1 | PGAP_MEDIAN_IND_DEV5（母本锚点） | 2.05 | 1.12 | 2.39 | 22.9 | 0 | 0 | PASS_ALL (=bl8Wd2Nq) |
| 2 | PGAP_MEAN_IND_DEV4 | 1.95 | 1.00 | 2.04 | 24.7 | 0 | 1 | CLUSTER_TEST |
| 3 | PGAP_DISPERSION_NORMALIZED | 1.98 | 1.04 | 2.02 | 23.1 | 0 | 1 | CLUSTER_TEST |
| 4 | PGAP_COVERAGE_WEIGHTED | 2.01 | 1.06 | 2.43 | 22.9 | 0 | 1 | CLUSTER_TEST |
| 5 | PT_OVER_FUNDAMENTAL_SPREAD | 0.43 | 0.10 | 1.09 | 22.7 | 3 | 3 | 死 |
| 6 | REVISION_DIFFUSION（PT 修正） | 0.30 | 0.08 | 0.98 | 8.5 | 3 | 2 | 死 |
| 7 | PGAP_IR_SUBINDUSTRY | 1.40 | 0.69 | 0.69 | 14.6 | 3 | 2 | 死 |
| 8 | **PGAP_MAX_SECTOR_DEV6** | **1.86** | **1.09** | **2.19** | **20.5** | **0** | **0** | **PASS_ALL → vROQVzlA** |

### Batch 2（8 槽）— 去相关重构（全部失败）

| # | 变体 | Sh | Fit | warn | 结论 |
|---|---|---|---|---|---|
| 1 | PT_GROWTH_MINUS_PRICE_GROWTH | 1.46 | 0.80 | 5 | 新增 **REVERSION_COMPONENT** 警告 |
| 2 | LONG_HORIZON_GAP_120 | 0.68 | 0.27 | 3 | 慢窗杀边 |
| 3 | REVERSAL_NEUTRALIZED_GAP | 1.98 | 1.03 | 2 | 仍有 REVERSION_COMPONENT |
| 4 | DISAGREEMENT_TREND（纯分析师） | 0.96 | 0.40 | 3 | 弱 |
| 5 | FV_IMPLIED_VALUE_GAP | 0.44 | 0.10 | 3 | 死 |
| 6 | OPTIMISM_IN_DISAGREEMENT_UNITS | 0.14 | 0.02 | 5 | 死 + UNITS |
| 7 | DISPERSION_NORM_LONG_GAP_SUBIND | 0.80 | 0.32 | 3 | 死 |
| 8 | FIRST_ESTIMATE_GAP_20 | 1.34 | 0.75 | 5 | 死 |

### Batch 3（8 槽）— 骨架正交加权 + EPS 修正机制

| # | 变体 | Sh | Fit | warn | 结论 |
|---|---|---|---|---|---|
| 1 | MAXPT_SECTOR_X_CONSENSUS | **-0.46** | -0.13 | 2 | 共识加权方向是**反的**（分歧大利好） |
| 2 | MAXPT_SECTOR_X_COVERAGE | 1.81 | 1.01 | 2 | IS_LADDER + CLUSTER 警告 |
| 3 | MAXPT_SECTOR_DISPERSION_NORM | 1.79 | 0.99 | 3 | 同上 + Fit 跌破 1 |
| 4 | MINPT_SECTOR_DEV6 | 1.14 | 0.47 | 4 | 最悲观口径无效 |
| 5 | FV_REVISION_DIFFUSION | -0.15 | -0.02 | 2 | **EPS 修正扩散在此数据上无效** |
| 6 | FV_REVISION_PER_DISPERSION | 0.33 | 0.07 | 3 | 死 |
| 7 | FV_REVISION_X_COVERAGE_SHOCK | 0.17 | 0.02 | 3 | 死 + UNITS |
| 8 | FV_REVISION_IR_SUBINDUSTRY_60 | -0.07 | -0.01 | 3 | 死 + UNITS |

---

## 2. 本役新增的可复用结论（写回知识库）

1. **零警告骨架 = `sector` 分组 + `max` 口径 + 6 日偏离 + decay 18 + STATISTICAL**。同族把分组换成 industry 或把统计量换成 mean/分歧/覆盖加权，必然出现 `CLUSTER_TEST` 警告。
2. **`REVERSION_COMPONENT` 警告由慢窗触发**：20/60/120 日偏离类信号全部带此警告；5/6 日窗不触发。慢窗路线不可用于「零警告」目标。
3. **`UNITS` 警告**由量纲不守恒触发（除以 `stddev+0.01`、除以 `count` 等混合量纲），需保持分子分母同量纲。
4. **EPS 盈利预测修正族（4 槽）在本数据/本 settings 下全灭（−0.15 ~ 0.33）**，与 PT 目标价族的强度差一个数量级，勿再重烧。
5. **共识紧密度加权方向是反的**：`× reverse(rank(stddev_PT))` 得 −0.46 → 分析师分歧越大越有 alpha，说明该族赚的是「分歧 → 收敛」的不确定性折价，而非共识漂移。
6. **PT/close 族内部 PnL 相关 0.82~0.95，PROD 相关 0.855**：该族已被 `bl8Wd2Nq` 占据，任何新成员都要先解决相关性，去相关只能靠换驱动源（换价格↔换分析师判断），而后者在本数据上强度不足。

## 3. 合规声明

- 全部数字来自本地 24 行结果 JSON 与 BRAIN API 实读；每批严格 8 槽、经 AST/量纲/字段数(2~3)/MD5 本地审计后发往平台。
- **未提交任何 alpha**（vROQVzlA 仍为 UNSUBMITTED）。
- 提交前置门槛 PROD_CORRELATION 实测 0.8554 ≥ 0.70，因此该 alpha **不具备提交资格**；若后续要求可提交，必须先换驱动源去相关。
