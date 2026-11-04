# 本战役回测最佳 Alpha（当前离线只读）

> 来源：`quant_framework/campaigns/USA_fund_f90_USA_T1000_d1/` 本地存储的回测结果文件。
> 状态：**离线只读复盘，不再调用 BRAIN API，不进行提交**。

---

## 战役参数
- REGION / UNIVERSE / DELAY: **USA / TOP1000 / 1**
- CATEGORY: **fundamental90**（平台分类 `fundamental`，全程未跨入 `pv`）
- 回测物理设置（后期固定）：SUBINDUSTRY / decay=4 / truncation=0.08 / pasteurization=ON / nanHandling=ON / unitHandling=VERIFY / maxTrade=OFF

---

## 全战役单一最佳（按 IS 夏普排序）
- **Alpha ID**: `9qx0pbJ9`
- **表达式**:
  ```
  ts_mean(
    subtract(
      subtract(
        ts_zscore(vec_avg(fnd90_us_game_cash_flow_coverage), 252),
        ts_zscore(vec_avg(fnd90_us_game_short_term_debt), 252)
      ),
      ts_zscore(oth466_cf_cash_int_pay, 252)
    ),
    10
  )
  ```
- **IS 夏普**: 0.84
- **Fitness**: 0.59
- **年化收益**: 6.16%
- **换手**: 5.63%
- **Margin**: 21.88 bps
- **子空间夏普（sub_universe_sharpe）**: 0.90
- **两年期夏普（two_year_sharpe）**: 0.64
- **Long:Short**: 94 : 95
- **状态**: UNSUBMITTED（从未提交）
- **平台检查结论（该结果文件）**
  - FAIL: LOW_SHARPE（0.84 < 1.58）、LOW_FITNESS（0.59 < 1.0）、IS_LADDER_SHARPE（0.64 < 1.58）
  - WARN: CLUSTER_TEST（0.47）、MATCHES_THEMES
  - PENDING: SELF_CORRELATION / DATA_DIVERSITY / PROD_CORRELATION / REGULAR_SUBMISSION

---

## 按批次最佳 IS 夏普一览（仅供上下文）
来源：本地 `batch_R*_result.json`，仅列各批内最高 IS Sharpe 的 alpha。

| 批 | Alpha ID | IS Sharpe | Fitness | Margin(bps) | 换手 | 子空间夏普 | 两年夏普 | 表达式片段 |
|---|---|---|---|---|---|---|---|---|
| R1 | A1VKYLPg | 0.46 | 0.08 | 1 | 44.83% | 0.33 | -0.08 | cash_flow_coverage vs noa（未平滑） |
| R3 | 6XdO1a25 | 0.09 | 0.02 | 3 | 2.41% | 0.07 | 0.54 | -rank(add(ts_mean(...))) |
| R4 | mLo9AnO1 | 0.62 | 0.24 | 10 | 3.72% | 0.73 | 0.35 | ts_mean( cov vs short_term_debt , 20) |
| R5 | ZYQGlpXQ | 0.65 | 0.26 | 9 | 4.57% | 0.66 | 0.47 | ts_mean( cov vs short_term_debt , 10) |
| R6 | leAXlk5e | 0.54 | 0.27 | 14 | 4.64% | 0.19 | 0.43 | ts_mean( cov vs oth466_a_tnix , 20) |
| R7 | 6XdO96k5 | 0.73 | 0.42 | 22 | 3.74% | 0.23 | 0.76 | rank(ts_mean( cov vs oth466_a_tnix , 20)) |
| R8 | npvV82Ra | 0.76 | 0.51 | 25 | 4.59% | 0.91 | 0.54 | ts_mean( cov - short_term_debt - oth466_cf_cash_int_pay , 20) |
| R9 | **9qx0pbJ9** | **0.84** | **0.59** | **22** | **5.63%** | **0.90** | **0.64** | ts_mean( cov - short_term_debt - oth466_cf_cash_int_pay , 10) |
| R10 | d5WLWNvg | 0.24 | 0.09 | 6 | 6.08% | 0.25 | 0.21 | interest_investment_inc - deferred_sal_chg - oth466_cf_cash |
| R11 | e75R1oRd | 0.73 | 0.41 | 14 | 5.77% | 0.64 | 1.37 | deferred_sal_chg - inventory_chg - oth466_cf_cash |

> 注：R11 中 `e75R1oRd` 的两年期夏普（1.37）是当前战役里单条最高的两年期夏普之一，但全样本 IS 夏普仍低于 R9 最优值；因此“整体最佳”仍是 `9qx0pbJ9`。

---

## 对应该最佳 Alpha 的关键元数据
- 字段构成：
  - `fnd90_us_game_cash_flow_coverage`（模型侧、现金覆债能力，vec_avg 包裹）
  - `fnd90_us_game_short_term_debt`（模型侧、短期债务，vec_avg 包裹）
  - `oth466_cf_cash_int_pay`（真实报表侧、利息现金支付，标量）
- 构造范式（该战役收敛出的获胜范式）：
  - 先对两个 fnd90 字段分别做 `vec_avg(…, 252)`，再分别 `ts_zscore(…, 252)`
  - 模型侧做“好现金覆债 − 坏短期债务”的去中枢后减法
  - 再减去真实报表侧锚点 `ts_zscore(oth466_cf_cash_int_pay, 252)`
  - 最外层 `ts_mean(…, 10)` 平滑稀疏事件跳变
- 该构造在本战役里同时满足：
  - 2~3 字段、≤2 个数据集（fnd90 + other466）
  - 长短持仓对称（94:95）
  - 换手进入合规下限附近（5.63%）
  - 子空间夏普 0.90，Margin 超过 20bps

---

## 审计结论（基于本地结果文件）
- 当前战役的**最高 IS 夏普候选**是 `9qx0pbJ9`，但它仍未通过平台提交门槛（IS 夏普 0.84 < 1.58，Fitness 0.59 < 1.0，且两年期梯级夏普 0.64 < 1.58）。
- 所有回测候选均为 **UNSUBMITTED**，未调用提交接口。
- 该最佳值是本地历史回测结果的统计最高值，不代表已证明样本外有效、平台可提交、或未来会盈利。

---

## 本次对话专属边界
- 本回答只读取了本地回测结果和摘要文件，未重新提交或重新回测任何表达式。
- 如需基于该最佳结构进一步构造变体、换 유니버스、或做交叉数据集组合，请明确说“是否允许重新回测 / 是否允许调用 BRAIN API”。
