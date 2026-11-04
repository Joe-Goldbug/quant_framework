# AEGIS 战役 · R10 离线多 Agent 合成简报

## 0. 战役底座（只读）
- 路径：`D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_fund_f90_USA_T1000_d1/`
- 战役参数：REGION=USA / UNIVERSE=TOP1000 / DELAY=1 / CATEGORY=fundamental90
- 放宽约束：**允许跨 1 个数据集**，alpha 表达式中最多出现来自**两个不同数据集**的字段（当前选定的搭档数据集 = `other466`）。
- **铁律 HARD_SUBMISSION_RULE：严禁调用任何提交接口！** 只允许创建回测仿真（IS），状态一律 UNSUBMITTED，等研究员人工终审。
- **频率限制**：BRAIN API 当前被限流，重置时间 **2026-10-29 23:00:00 UTC+8**。本简报驱动的离线合成阶段**严禁调用任何 BRAIN API / 回测**。所有工作只读写本地文件。

## 1. 演化轨迹（已测批次最优 Sharpe）
| 批 | 最优 alpha | Sharpe | Fitness | Margin(bps) | 换手 | SubU | 备注 |
|----|-----------|--------|---------|-------------|------|------|------|
| R6 | leAXlk5e  | 0.54 | 0.27 | 13.63 | 4.6% | 0.19 | 跨数据集首破 2.5% 年化线 |
| R7 | 6XdO96k5  | 0.73 | 0.42 | 22.13 | 3.7% | 0.23 | rank 映射增益 |
| R8 | npvV82Ra  | 0.76 | 0.51 | 24.55 | 4.6% | 0.91 | 年化 5.63% |
| R9 | **9qx0pbJ9** | **0.84** | **0.59** | **21.88** | **5.63%** | **0.90** | **L:S=94:95 对称**，当前全局最优 |

## 2. 收敛出的获胜算子范式（WINNING PARADIGM）
```
ts_mean(
  subtract(
    subtract( ts_zscore(vec_avg(fnd90_X), 252),
              ts_zscore(vec_avg(fnd90_Y), 252) ),
    ts_zscore(oth466_Z, 252)
  ),
  10
)
```
- 经济学语义：**「模型估计(fnd90) vs 真实报表(other466)」的二阶预期差**。两路 fnd90 先相减得到模型内部的相对结构，再减去一份真实报表基准，残差即「模型与现实背离度」；`ts_zscore(,252)` 做年度截面标准化，`ts_mean(,10)` 外层平滑压低事件跳变噪音。
- 物理实证：把 `ts_mean` 放错层（逐腿平滑）会让 Margin 从 +10bps 反转为 -0.13bps、换手从 4% 飙到 42%（稀疏事件序列死重病灶）。**平滑必须置于最外层**。

## 3. 四公理红线（任何合成/审计都不得违反）
1. **符号与零点守恒**：取值范围 [0,1] 或正偏置字段，乘方/相乘前必须先去中枢化（subtract(x,ts_mean(x,20)) / ts_zscore）。禁止双有符号变量直接 multiply；双有符号合成必须用 add(group_zscore(A),group_zscore(B))；multiply(Signal,Weight) 的 Weight 必须恒正。
2. **持仓对称与死重清除**：稀疏事件数据必须检查 Long:Short≈1:1；单边偏离 >15% 须 ts_backfill / trade_when / 外层时序衰减消除。
3. **奥卡姆与禁调参**：字段数 2≤n≤3；终态算子数 ≤6；时间窗口只允许 {3,5,10,20,60,120,252}；**严禁网格调参（如 decay 16→14、std 2.5→2.2）凑夏普**。
4. **反同簇拥挤**：优先 Alphas 使用数 ≤5 的低拥挤字段；热门字段必须构造相对于自身基线的二阶预期差，禁对静态截面水平值一阶裸乘。

## 4. 已用字段（R6–R9，避免重复）
- fnd90: `fnd90_us_game_cash_flow_coverage`, `fnd90_us_game_short_term_debt`, `fnd90_us_game_eff_interest_rate`
- oth466: `oth466_a_tnix`, `oth466_a_ttld`, `oth466_cf_cash_from_oper`, `oth466_cf_cash_int_pay`, `oth466_rt_cf_sales_q`

## 5. 候选冷门字段池（预筛，覆盖度/拥挤度已标注）
### fnd90 候选（主题：现金/债务/利息/质量/应计，未用过）
```
fnd90_game_accruals_vol            cov=0.78 A=2   Accrual Volatility
fnd90_game_an_cov_chng             cov=0.85 A=0   Analyst Coverage Change Over Time
fnd90_game_debt_convertible        cov=0.69 A=0   Convertible Debt to Total Debt
fnd90_game_deferred_sal_chg        cov=0.59 A=1   Change in Deferred Revenue
fnd90_game_earning_smooth         cov=0.81 A=0   Earnings Smoothness
fnd90_game_eps_vol                cov=0.74 A=0   Earnings Volatility
fnd90_game_gma_chg                cov=0.85 A=1   Change in Gross Margin
fnd90_game_gross_margin_vol       cov=0.75 A=2   Gross Margin Volatility
fnd90_game_inc_cash_tax           cov=0.75 A=0   Income Statement Tax to Cash Tax
fnd90_game_interest_investment_inc cov=0.59 A=0  Interest and Investment Income
fnd90_game_inventory_chg          cov=0.84 A=0   Change in Inventory
fnd90_game_inventory_days         cov=0.84 A=1   Inventory Days
fnd90_game_optimism_gma           cov=0.70 A=0   Analyst Optimism Gross Margin
fnd90_game_pension_expense        cov=0.76 A=0   Pension Expense to EBITDA
fnd90_game_receivable_chg         cov=0.85 A=0   Change in Receivables
fnd90_game_receivable_days        cov=0.85 A=1   Receivable Days
```
### oth466 候选（MATRIX 标量，cov≥0.8，未用过，主题：现金/债务/利息/利润率/应计）
```
oth466_a_er                 cov=1.00 A=11  Restricted Cash - Long Term
oth466_a_pdaio              cov=1.00 A=0   Operating Income
oth466_bs_cash_equiv_q      cov=1.00 A=0   Cash and equivalents
oth466_bs_cash_only_q       cov=1.00 A=1   Net Cash
oth466_bs_cash_st_invest    cov=1.00 A=0   Cash & Short-Term Investments
oth466_bs_receiv_tot_q      cov=1.00 A=1   Total Accounts Receivable
oth466_cf_cash              cov=1.00 A=1   Cash
oth466_cf_cash_chg          cov=1.00 A=10  Net Change In Cash
oth466_cf_chg_cash_st_invest cov=1.00 A=8  Increase/Decrease In Cash And Short-Term Investments
oth466_cf_fin               cov=1.00 A=5   Cash From Financing Activities
oth466_des_net_debt_q       cov=1.00 A=7   Net Debt
oth466_is_ebit_bef_unusual  cov=1.00 A=4   Earnings Before Interest, Taxes & Unusual Expense
oth466_is_ebit_oper_q       cov=1.00 A=3   EBIT (Operating Income)
oth466_is_gross_prof        cov=1.00 A=0   Gross Profit
oth466_is_net_profit_12m_q  cov=1.00 A=0   Trailing 12 Months Net Profit
oth466_is_oper_exp_q        cov=1.00 A=0   Total Operating Expense
oth466_is_oper_inc_q        cov=1.00 A=1   Operating Income
```

## 6. R10 设计目标与子 Agent 分工
目标：把 Sharpe 从 0.84 推向 **≥1.0**（平台提交硬门槛），同时守住 Fitness≥1.0 / Margin≥10bps / 换手[5,50]% / SubU 不退化 / L:S 对称 / ProdCorr<0.7（提交后平台才计算，本地标 PENDING）。

### Agent A — 候选合成器 (aegis-seed-synthesizer)
- 基于获胜范式 + 第 5 节字段池，设计 **16 条** 候选表达式（供 R10 两批各 8 条使用）。
- 要求：机制正交（覆盖不同经济假设：现金充裕度背离、债务/利息压力背离、盈利质量/应计背离、运营资本背离、毛利动能背离…）；2~3 字段、来自 ≤2 数据集；算子数 ≤6；只用标准窗口；遵守四公理；禁止 PV 字段（pv*）。
- 每条附 `optimize_reason`（≥60 字，说明其提升信噪比的经济学机理，不得含「门控/过滤/放大/权重/交互/对冲」等触发红队否决的敏感词）。
- **输出文件**：`R10_candidates.json`，结构：
  `{"candidates":[{"id":"C01","expression":"...","family":"...","optimize_reason":"..."}, ...]}`

### Agent B — 范式分析师 (aegis-analyst)
- 读取 R6–R9 结果文件与字段目录，独立诊断：为何 Sharpe 在 ~0.84 见顶？字段配对的哪些特征（覆盖度/拥挤度/主题）与高 Sharpe 相关？给出 R10 最高期望值的字段三元组排序（≥12 组）及理由。
- **输出文件**：`R10_analysis_memo.md`（简明，含排序表与物理诊断）。

> A 与 B 互不依赖，可并行。完成后由 Agent C 接力。

### Agent C — 红队审计 (04_red_team_auditor)（A、B 完成后接力）
- 读取 `R10_candidates.json` 与 `R10_analysis_memo.md`，逐条审计：AST 合规性、四公理（尤其符号守恒与 PV 隔离）、机制-AST 忠实度、算子预算、与 R6–R9 表达式的去重（禁止重复）。
- **输出文件**：`R10_redteam_verdict.json`，结构：
  `{"verdicts":[{"id":"C01","pass":true/false,"issues":[...],"corrected_expression":"..."}, ...]}`
- 对未通过项给出修正表达式；对全部通过项标记 OK。
