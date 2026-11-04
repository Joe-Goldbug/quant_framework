# AEGIS · fundamental17 · Stage 3 白盒立项研报（铁律 5 · 仿真前公示）

**批次**：`aegis_fnd17_S1` · **日期**：2026-10-28 · **数据集**：fundamental17 (402 字段 / 289 可用)
**区域**：USA / TOP1000 / delay=1 / category=fundamental
**仿真设置（固定，不得更改）**：`neutralization=STATISTICAL, decay=8, truncation=0.08, pasteurization=ON, unit_handling=VERIFY, nan_handling=ON, language=FASTEXPR`
**纪律**：全程禁止调用任何 Alpha 提交接口。回测 ≠ 提交。达标 Alpha 仅本地标记，交研究员人工终审。

---

## 0. 门禁可行性算术（先算，再回测）

用今日 52 条实测 alpha 反查确认（52/52 全部吻合，无一例外）：

```
Fit   = Sh × √(|Ret| / max(TO, 0.125))      ← 平台 Fitness 公式
Mgn_bps = 20 × Ret / TO                    ← 平台 Margin（bps）
```

**推论（决定本批设计取向）**：

- 换手低于 12.5% 时 Fitness 分母被地板锁在 0.125 ⇒ **年化收益 Ret 成为硬约束**：
  - `Ret ≥ 0.125 / Sh²`（Fitness ≥ 1.0）
  - `Ret ≥ 0.5 × TO`（Margin ≥ 10bps）
- 在 Sh=1.58 处需 `Ret ≥ 5.01%`；今日实测组合口径下年化波动仅约 2.6%，
  ⇒ **实际可过的 Sharpe 门槛被推高到 ~1.75~1.85**，单看 Sharpe=1.58 是不够的。
- 因此 Stage 3 漏斗把存活线设在 **|Sharpe| ≥ 1.0** 而非 1.58 —— 先过漏斗，再攻精度。

**同时**：低换手基本面在 Fitness 上天然占优（TO<12.5% 不被惩罚），
**绝不需要为抬换手而引入外部量价字段**（那会直接触发 PV 污染 ⇒ ProdCorr 越线）。

---

## 1. 8 问特征认知画像

| 问 | 认知维度 | 因果微假设 |
|---|---|---|
| Q1 | Invariance 不变性 | 盈利中枢的**漂移方向**比盈利**水平**更值钱 |
| Q2 | Dynamics 动态变化 | EPS 增速与净利润增速的裂口 = 股本动作（回购/稀释） |
| Q3 | Anomaly 异常冲击 | 现金产出率（FCF/资产）比规模杠杆更接近真实价值 |
| Q4 | Interaction 交互 | 存量资本回报 + 增量资本回报**同时**居前 = 真实经营 |
| Q5 | Structure 结构占比 | 派息率的政策**转向**（本期 vs 上一财年）被当作外生事实定价 |
| Q6 | Accumulation 累积记忆 | 增长是否**含金量足**（现金流增速 vs 收入增速） |
| Q7 | Relative 截面相对 | 信用质量的**边际改善**比绝对水平更少与市值纠缠 |
| Q8 | Essence 预期差 | 市场只为营收超预期定价，**经营杠杆/利润率扩张**无人交易 |

---

## 2. 8 条装满的表达式清单

| 序号 | 表达式 | 8问维度 | 正交变动源 | 字段 ac | 算子数 |
|---|---|---|---|---|---|
| 1 | `zscore(subtract(fnd17_tcpaormtt, fnd17_aroa5yavg))` | Q1 Invariance | 盈利中枢漂移 | 4+0=**4** | 2 |
| 2 | `zscore(ts_mean(subtract(fnd17_ghcspemtt, fnd17_ttmnichg), 20))` | Q2 Dynamics | 股本动作裂口 | 0+0=**0** | 3 |
| 3 | `zscore(divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252)))` | Q3 Anomaly | 现金产出率 | 10+0=**10** | 4 |
| 4 | `add(group_zscore(fnd17_tcpaormtt, subindustry), group_zscore(fnd17_qroipct, subindustry))` | Q4 Interaction | 存量+增量资本回报 | 4+2=**6** | 3 |
| 5 | `group_zscore(ts_backfill(subtract(fnd17_apayratio, fnd17_apayratio2), 120), subindustry)` | Q5 Structure | 分红政策转向 | 0+6=**6** | 3 |
| 6 | `zscore(ts_mean(winsorize(subtract(fnd17_cftrendgr, fnd17_revtrendgr), std=3), 60))` | Q6 Accumulation | 增长含金量 | 3+2=**5** | 4 |
| 7 | `group_zscore(ts_backfill(subtract(fnd17_ttmintcov, fnd17_ptmintcov), 120), subindustry)` | Q7 Relative | 信用边际改善 | 1+0=**1** | 3 |
| 8 | `zscore(subtract(fnd17_nichngyr, fnd17_arevchg))` | Q8 Essence | 经营杠杆扩张 | 0+0=**0** | 2 |

> 逐条 300 字深度因果归因见 `batch_S1.json` 的 `optimize_reason` 字段（编排官亲签，非模板）。

---

## 3. 本地 AST 校验与量纲审计通过凭据

| 闸门 | 判据 | 结果 |
|---|---|---|
| G1 语法/AST | `ast.parse(mode='eval')` | **8/8 PASS** |
| G2 引擎量纲审计 | `DimensionAuditor.audit_expression(max_ops=11)` | **8/8 is_valid=True** |
| G3 战役结构契约 | 字段数 2~3 · 算子数 ≤4 · 顶层零均值 · 黑名单算子 0 · PV 污染 0 | **8/8 PASS** |
| G4 单位一致性 | `subtract` 两腿量纲族必须可比 | **8/8 PASS**（ROA↔ROA5Y均值 / EPS增速↔净利增速 / 派息率↔派息率 / 现金流增速↔收入增速 / 覆盖率↔覆盖率 / 净利增速↔收入增速） |
| G5 双盲红队 | 定义域对齐 + 假设-AST 保真 + 奥卡姆剃刀 | **all_passed=True** |
| G6 骨架/指纹 | 同批骨架唯一 ≤2 · 跨批历史 <4 | **8/8 骨架唯一** · **跨批历史全 = 0** |

**红队实战记录（零隐瞒）**：首轮编排官自签文本中有 2 条被红队 REJECT ——
机制描述里写了「放大」二字，但 AST 里没有任何乘积/条件门控算子。
红队判定正确（文不对题伪因果），已改写措辞使其与 AST 严格一致后复审通过。
**这证明红队闸门是活的，不是摆设。**

---

## 4. 反拥挤论证

- 字段 ac 之和：4 / 0 / 10 / 6 / 6 / 5 / 1 / 0 ⇒ **8/8 槽均 ≤ 10**，其中 3 槽为 0。
- 本账户 USA/d1 已提交 70 条 alpha 中 `fnd17_` 字段使用数 = **0** ⇒ 本数据集对本账户是真实冷启动面。
- 跨区域已烧 22 个 fnd17 字段 ⇒ 本批刻意避开 `nprice / mktcap / ev_cur / priceavg* / ebitda2ev* / yield` 等，
  优先用 **20 组孪生字段**与 **ac=0 的 5 年均值/上期基线字段**。
- 骨架哈希 8/8 唯一（无同源重复），跨批指纹库 `alphas_record.db` 中 fnd17/USA/TOP1000 历史命中 = **0 条**。

---

## 5. 预注册漏斗（回测前写死，不事后改）

- **Step-1 漏斗**：`|Sharpe| ≥ 1.0` 且 正收益年份 ≥ 8/10
  → 全批无一达标则 **PRUNED_AT_STEP1**，立即换主信号，**不做网格微调重发**。
- **Step-2 阶梯**：2Y ladder ≥ 1.58 · Sub-universe 平台口径 · `checks.fail` 为空 · `ra.ra_failed == false`
- **终态门禁**：Sharpe ≥ 1.58 · Fitness ≥ 1.0 · Margin ≥ 10bps · TO ∈ [1%,70%] · ProdCorr < 0.70 · SelfCorr ≤ 0.60
