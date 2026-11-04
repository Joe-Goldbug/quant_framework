# AEGIS · R10 范式分析备忘录（aegis-analyst）

> 离线只读诊断。数据源：R6–R9 四个 `batch_*_result.json`（共 38 条 alpha，`alpha_results[].metrics`）。
> 物理设置固定：SUBINDUSTRY / decay=4 / truncation=0.08 / delay=1 / TOP1000（账户已验证，未改）。
> 铁律：本备忘录不触发任何提交/BRAIN API；仅供 R10 合成与红队接力。

---

## 一、物理诊断：为何 Sharpe 在 ~0.84 见顶

### 1.1 恒等式校验（margin 与 turnover 解耦 Sharpe）
对全局最优 `9qx0pbJ9`（R9）：returns=0.0616，turnover=0.0563，margin=0.002188。
```
margin_bps ≈ returns_bps / (504 × turnover)
          = 0.0616 / (504 × 0.0563) = 0.0616 / 28.375 = 0.00217  ≈ 0.002188  ✓
```
**结论**：margin 只是「年化收益 ÷ 换手频率」的再缩放。**Sharpe = returns / vol，与 turnover 无关**——换手只移动 margin（成本项），不移动 Sharpe。因此 "压低换手" 不是冲 1.0 的杠杆；它只改善 margin/成本，对 Sharpe 是中性。R9 已把换手压到 5.6%（接近稀疏事件序列的物理下限：信号按季跳变、按 ~18 天持有），再降换手无 Sharpe 增益。

### 1.2 振幅天花板（fnd90 是低频稀疏 VECTOR 事件序列）
- `fnd90` 字段为 **VECTOR 季度事件型**：仅在财报事件日跳变、事件间恒定。它与 `oth466`（报表标量）天然同频（均为季度节奏），两者的"模型 vs 现实"残差是一阶慢变、低振幅序列。
- 经 `ts_zscore(,252)` 标准化到单位方差后，残差的**前向可预测性（每次事件带来的超额收益）已经饱和**——市场已部分定价这些基本面关系。
- 实测：R9 年化 returns≈6.16%，Sharpe 0.84 ⇒ 年化 vol≈7.3%。这是事件残差在 SUBINDUSTRY 中性后的"信号自身波动"下限。要把 Sharpe 推到 1.0，需 returns 从 6.16%→7.3%（+18% 振幅），或 vol 同比例下降——而后者被振幅/广度锁死（见 1.4）。

### 1.3 平滑位置病灶（已实测，红线）
把 `ts_mean` 放到逐腿内层（对每条腿先平滑）会让 Margin 从 +10bps 反转为 -0.13bps、换手 4%→42%：稀疏事件序列被逐腿平滑后产生大量"死重"伪信号，迫使频繁调仓。**平滑必须置于最外层**（对最终残差做 `ts_mean(,10)`）。本备忘录所有推荐沿用外层平滑。

### 1.4 截面广度（breadth）约束
R6–R9 最优 alpha 的 `longCount≈shortCount≈94–95`（占 TOP1000 的 ~9.5%，CONCENTRATED_WEIGHT 临界通过）。**广度窄 → 特质波动无法被分散**，vol 被钉在 ~7.3%。广度的硬上限由字段覆盖度 `cov` 决定：
- `cov≥0.8` 的字段才能支撑足够多的命名覆盖，从而降低 vol、抬升 Sharpe；
- `cov<0.7`（如 `deferred_sal_chg` 0.59、`interest_investment_inc` 0.59）作主腿会进一步收窄广度 → vol↑ → Sharpe↓（这是 `P0o9G6Wp` cov 组合仅 0.20 且触发 CONCENTRATED_WEIGHT 的根因之一）。

**见顶综合诊断**：0.84 是「稀疏事件低振幅（信号项）× 窄广度高特质波动（噪声项）」的物理平衡。通往 1.0 的唯一杠杆是 **(a) 换用振幅更大/耦合更紧的字段三元组** 与 **(b) 用高 cov 字段拓宽广度压低 vol**，而非调换手或调参。

---

## 二、字段配对特征与高 Sharpe 的关联

### 2.1 主导腿（lead fnd90）必须是"现金充裕度/质量"主题
所有 Sharpe>0.6 的 alpha 都以 `fnd90_us_game_cash_flow_coverage` 为主腿（0.54→0.76→0.84 的演化主线）。它同时满足：高 cov、A 经"二阶预期差"范式规避拥挤、且主题直接对应"偿债/现金质量"——市场最持续错误定价的维度。

### 2.2 第二腿（second fnd90）做"模型内部相对结构"最有效
加入第二 fnd90 腿显著提升：`leAXlk5e`(cov−tnix, 0.54) → `npvV82Ra`(cov−std−intpay, 0.76) → `9qx0pbJ9`(cov−std−intpay, ts10, 0.84)。第二腿取 **debt/interest 风险主题**（short_term_debt、eff_interest_rate）使"模型 coverage vs 债务"形成内部价差，残差更锐利。纯单腿 (`kqNl0pzk` cov−intpay 0.63) 弱于双腿。

### 2.3 oth466 锚点 Z：真实现金/债务报表 > 静态存量水平
Z 字段的 Sharpe 排序与"和主题的耦合紧密度"正相关：
- `oth466_cf_cash_int_pay`（利息支出，A=1，现金流表真值）最优（配 cov 得 0.76/0.84）；
- `oth466_a_tnix`（长期投资，A=1）次之（0.44–0.73）；
- `oth466_a_ttld`（总资产，含现金存量水平）最差（0.2 / 组合 `58EWkOoJ` 窗口120 → -0.51）。
**机制**：利息支出是"现金充裕度主题"最贴近的报表真值，耦合最紧 → 残差信息量最大。

### 2.4 覆盖度 `cov` 与拥挤度 `A` 的影响（量化规律）
- **cov**：主腿 cov≥0.8 是 Sharpe>0.7 的必要条件（广度→降 vol）；cov<0.7 作主腿直接压垮 Sharpe。
- **A（平台使用数）**：`oth466` 端优先 A≤3（如 `bs_cash_only_q` A=1、`is_gross_prof` A=0、`is_oper_inc_q` A=1）；**A≥7 的字段（des_net_debt_q A=7、cf_cash_chg A=10、a_er A=11）属拥挤禁区**，仅作"高 EV 但需监控 ProdCorr"的例外，不优先。
- `fnd90` 冷门候选多 A=0（`an_cov_chng`、`debt_convertible`、`earning_smooth`、`inc_cash_tax`、`inventory_chg`、`receivable_chg` 等），经"二阶差"范式天然避开公理四红线，是 R10 主力。

### 2.5 算子包裹的边际效应
`rank()` 包裹对单腿有 +0.1~0.2 Sharpe 增益（0.54→0.73），但被"双腿+外层 ts_mean(10)"范式反超；`group_zscore`（88R1p73v）拿到最佳 2 年 Sharpe 1.53 却拉低全样本 IS（0.69）——因已 SUBINDUSTRY 中性，组内再中性属冗余且过拟合 2 年窗口，R10 不采用。

---

## 三、R10 最高期望值字段三元组排序（≥12 组）

范式（沿用获胜式，平滑最外）：
`ts_mean(subtract(subtract(ts_zscore(vec_avg(fnd90_X),252), ts_zscore(vec_avg(fnd90_Y),252)), ts_zscore(oth466_Z,252)), 10)`
约束：fnd90 须 `vec_avg()` 包裹；oth466 标量直喂；X=质量/现金主题(好)，Y=债务/风险主题(坏)，Z=真实报表锚(低 A)；优先 cov≥0.8、A≤3。

| 排名 | 组合 (fnd90_X, fnd90_Y, oth466_Z) | 主题 | 机制（一句话） | 交易对手盘是谁 |
|---|---|---|---|---|
| 1 | (gma_chg, pension_expense, is_gross_prof) | 毛利动能−养老金 | 模型毛利改善减养老金负担、锚定真实毛利，捕捉被慢变量养老金负债掩盖的盈利质量 | 外推毛利率的趋势动量盘 |
| 2 | (deferred_sal_chg*, debt_convertible, bs_cash_only_q) | 营收可见度−可转债 | 递延收入增量(未来现金可见度)减可转债稀释风险、锚定真实净现金，捕获表外/可转债未定价 | 做空高可转债密集股的信用卖空盘 |
| 3 | (interest_investment_inc, inventory_days, bs_cash_only_q) | 现金生成−营运资本 | 投资/现金生成估计减库存天数压力、锚定净现金，捕捉库存积压与现金生成的背离 | 押注库存周期反转的交易盘 |
| 4 | (an_cov_chng, receivable_days, bs_receiv_tot_q) | 信息改善−回款风险 | 分析师覆盖上升(信息改善)减应收天数恶化、锚定真实应收，捕捉信息不对称二阶差 | 被动持有低覆盖小盘的流动性提供盘 |
| 5 | (earning_smooth, eps_vol, is_net_profit_12m_q) | 盈利质量−波动 | 盈利平滑质量减 EPS 波动、锚真实滚动净利，捕捉应计/平滑反转 | 追涨杀跌的盈余惊喜动量盘 |
| 6 | (inc_cash_tax, debt_convertible, is_oper_inc_q) | 现金税−债务 | 现金税支付(真实盈利质量)减可转债风险、锚经营利润，捕捉避税/表外债务信号 | 高账面利润低现金税的套利对手 |
| 7 | (receivable_chg, inventory_chg, cf_cash) | 营运资本变动 | 应收与库存变动的模型差(渠道填充)锚经营现金，捕捉渠道填充反转 | 追营收增长的供应链动量盘 |
| 8 | (gma_chg, gross_margin_vol, is_gross_prof) | 毛利动能质量 | 毛利改善减毛利波动、锚真实毛利，稳定性加成避免外推陷阱 | 同上趋势动量盘 |
| 9 | (deferred_sal_chg*, receivable_days, bs_cash_only_q) | 营收可见度−回款 | 递延收入(好)减应收天数(坏)锚净现金，双现金质量维度 | 信用卖空盘 |
| 10 | (inventory_chg, debt_convertible, cf_fin) | 库存−再融资 | 库存变动(渠道)减可转债(再融资风险)锚真实融资现金流，再融资+渠道双击/双杀 | 高收益债/可转债套利盘 |
| 11 | (eps_vol, pension_expense, is_ebit_oper_q) | 盈利风险−经营 | EPS波动减养老金负担锚真实经营EBIT，经营确定性差的公司被高估 | 做多低波动的质量因子拥挤盘 |
| 12 | (accruals_vol, inventory_days, cf_cash) | 应计−营运 | 应计波动(激进会计)减库存天数锚经营现金，会计激进+库存积压双预警 | 账面盈利质量追逐盘 |
| 13 | (an_cov_chng, eps_vol, is_oper_inc_q) | 关注−波动 | 分析师覆盖改善减EPS波动锚经营利润，信息改善但盈利不稳的背离 | 低覆盖小盘流动性盘 |
| 14 | (inc_cash_tax, receivable_days, bs_receiv_tot_q) | 现金税−应收 | 现金税(质量)减应收天数锚真实应收，避税+回款恶化双信号 | 应收账款保理/信用盘 |

> 注：`deferred_sal_chg` 与 `interest_investment_inc` 的 cov 仅 0.59（广度偏薄），已在表中标 *——作为高 EV 但需监控广度的例外；若回测 vol 偏高，优先改用 cov≥0.8 的主腿（gma_chg 0.85 / an_cov_chng 0.85 / inventory_chg 0.84 / receivable_chg 0.85）。
> 等价组合备选（供 Agent A 扩充）：(a) 同三元组换 `ts_mean(,20)` 或 `ts_mean(,5)` 取稳健/灵敏两档；(b) 主腿单 fnd90+双 oth466 变体如 `(cash_flow_coverage, is_gross_prof, cf_cash)` 仅作去重对照，不优先。

---

## 四、一句话核心诊断
**Sharpe 在 0.84 见顶是"稀疏季度事件信号低振幅 × 窄截面广度高特质波动"的物理平衡——换手/调参不是杠杆，R10 唯一出路是用高 cov(≥0.8)、低 A(≤3) 的"现金质量主腿 − 债务风险次腿 − 真实报表锚"三元组换更大振幅并拓宽广度，把年化收益从 6.2% 推过 7.3%。**
