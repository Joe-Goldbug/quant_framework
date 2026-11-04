# AEGIS · fundamental17 冷启动 · 多智能体研究简报 (Sub-Agent 必读)

**战役参数**：REGION=USA / UNIVERSE=TOP1000 / DELAY=1 / DATASET=fundamental17 / category=`fundamental`
**提交纪律**：HARD_SUBMISSION_RULE —— 全程**禁止调用任何 Alpha 提交接口**。回测 ≠ 提交；达标 Alpha 仅本地标记，交研究员人工终审。
**日期**：2026-10-28

---

## 0. 你要交付什么

**你是 8 问种子池的某个切片的设计者。** 只交付 **4 条候选表达式**（你负责 2 个问题 × 每个问题 2 条候选），
每条含：表达式 / 字段 / 经济机制 / 对手盘 / 因果归因 / 自检表。**不要写代码、不要跑回测、不要提交任何东西。**
你的输出会被编排官（我）挑选、去重、并入 8 条种子池，再经本地三重预检（量纲/红队/骨架）后才发包。

---

## 1. 数据集物理事实（决定一切构造）

| 事实 | 数值 | 后果 |
|---|---|---|
| 字段总数 | 402，**100% MATRIX** | 无 `vec_*` 归约需求 |
| 可用池 | **289 / 402** | 40 个汇率币种码 + 73 个内嵌量价已物理剔除，**严禁触碰** |
| 平台拥挤 | dataset alphaCount=**781**, userCount=380, valueScore=**1** | 全库最拥挤的基本面集 ⇒ **反拥挤定律是第一约束** |
| 字段拥挤 | 76/289 字段 ac=0；238/289 ac≤5 | **优先用 ac=0~2 字段** |
| 覆盖率 | min 0.314 / median 0.896 / max 0.965 | cov<0.75 ⇒ 稀疏，须防 CONCENTRATED_WEIGHT 与多空失衡 |
| **更新频率** | **季报/年报驱动**（`q`=最近季, `a`=最近财年, `ttm`=滚动12月, `mtt`=上年同期, `mtp`=prior TTM） | ① 换手天然低（TO 2~8%）⇒ LOW_TURNOVER 风险低；② 一阶裸水平值缺乏截面动态 ⇒ **必须构造「本期 vs 自身历史基线」的二阶预期差** |
| **结构资产** | **56 个字段自带「去年同期/上期/前财年/5年均值」孪生口径** | 本数据集皇冠明珠：天然满足「二阶预期差 + 零拥挤」双重要求 |
| 字段值域 | 每股金额/金额=unbounded；比率=[0,inf) 或 [-1,1] | 比率字段天然正偏置或可正可负 ⇒ 乘方/相乘前必须去中枢 |

### 1.1 字段元数据权威源
- 完整画像：`aegis_coldstart/fnd17_field_dossier.json`（289 字段，含 desc / ac / cov / domain / sparse）
- **孪生字段对照表**：`aegis_coldstart/fnd17_lag_pairs.json`（20 组已配对，含 lag/current 双方描述与 ac）
- 原始全量：`knowledge_base/fields/USA/fundamental17_raw_full.json`
- **你必须实读 dossier 与 lag_pairs 选字段，不得凭记忆编造字段 id。**

### 1.2 已知 20 组孪生（部分摘录，全表见 lag_pairs.json）
| 本期 | 孪生（滞后） | ac(本期/孪生) | 经济含义 |
|---|---|---|---|
| `fnd17_tcpaormtt` | `fnd17_tcpaormtp` | 4 / **0** | TTM 资产回报率改善 |
| `fnd17_ngmtpmtt` | `fnd17_ngmpnmtp` | 1 / 8 | 净利率拐点 |
| `fnd17_qtotd2eq` | `fnd17_qtotd2eq2` | 1 / 2 | 杠杆去化 |
| `fnd17_qcurratio` | `fnd17_qcurratio2` | 2 / 1 | 流动性改善 |
| `fnd17_ttmintcov` | `fnd17_ptmintcov` | 1 / **0** | 利息保障能力改善 |
| `fnd17_shsoutbs` | `fnd17_shsoutbs2` | 3 / 6 | 股本缩减（回购） |
| `fnd17_apayratio` | `fnd17_apayratio2` | 0 / 6 | 派息率变化 |
| `fnd17_qtotce` | `fnd17_qtotce2` | 2 / 4 | 账面权益增长 |
| `fnd17_aptmgnpct` | `fnd17_aptmgnpct2` | 3 / 1 | 税前利润率改善 |
| `fnd17_tcpngmpoa` | `fnd17_2tcpngmpoa` | 1 / 3 | 营业利润率改善 |
| `fnd17_ataxrate` | `fnd17_ataxrate2` | 4 / 0 | 有效税率变化 |
| `fnd17_rhsfcq` | `fnd17_2rhsfcq` | 0 / 3 | 每股现金流同比 |
| `fnd17_rhsfcfq` | `fnd17_2rhsfcfq` | 5 / 4 | 每股自由现金流同比 |
| `fnd17_rhsfca` | `fnd17_2rhsfca` | 1 / 1 | 每股现金流年度同比 |
| `fnd17_agrosmgn` | `fnd17_agrosmgn2` | 1 / **0** | 毛利率年度变化 |

**另有 8 个 ac=0 的「5 年均值/自身基线」字段**（天然的一阶 vs 自身长期中枢，无需手动算基线）：
`fnd17_aroa5yavg`(ROA 5年均值) / `fnd17_aroe5yavg` / `fnd17_ry5ngmtp`(税前利润率5年均值) / `fnd17_ry5ngmpo` /
`fnd17_aebitd5yr`(EBITD利润率5年均值) / `fnd17_grosmgn5yr`(毛利率5年均值) / `fnd17_ataxrat5yr` / `fnd17_margin5yr`

**以及 8 个 ac=0 的「上期」字段**（本数据集最干净的二阶预期差源）：
`fnd17_nichngin`(净利润环比%) / `fnd17_ptmepsincx`(每股盈利 prior TTM) / `fnd17_ghcspemtt`(TTM EPS同比%) /
`fnd17_tcpaormtp`(ROA prior TTM) / `fnd17_ptmroepct`(ROE prior TTM) / `fnd17_ptmintcov`(利息保障 prior TTM) /
`fnd17_qtachg`(总资产同比%) / `fnd17_aebitd2`(EBITDA 上财年)

---

## 2. 四大公理（硬红线，违反即熔断）

1. **符号与零点守恒**：比率类字段（margin/growth/coverage/ROA…）天然正偏置或可正可负，**乘方/相乘前必须去中枢**；**绝对禁止两个有正有负的同向变量直接 `multiply`**（负负得正伪因果，引擎有物理拦截）。若用 `multiply(Signal, Weight)`，Weight 必须**严格恒正**（如 `rank(x)` 或 `sqrt(abs(x))` 或 `add(rank(x), 0.01)`）。双有符号合成必须 `add(group_zscore(A,…), group_zscore(B,…))`。
2. **持仓对称**：稀疏字段必须查 longCount vs shortCount；单边偏离 >15% 即为死重污染，须用 `ts_backfill` / 时序平滑消除。
3. **奥卡姆剃刀**：**字段数 2 ≤ n ≤ 3**；**算子数 ≤ 4**（Phase 0 主信号硬上限）；时间窗口只允许 **{3, 5, 10, 20, 60, 120, 252}**；**严禁网格微调**。
4. **反同簇拥挤**：优先 `alphaCount ≤ 5` 的低拥挤字段；热门字段必须构造**相对于自身历史基线的二阶预期差**，严禁对静态截面水平值做一阶裸乘。

### 2.1 算子白名单与黑名单（引擎会物理拦截）
**可用**：`add subtract divide multiply reverse neg abs sign power sqrt log s_log_1p exp max min rank group_rank scale group_scale zscore group_zscore ts_mean ts_sum ts_std_dev ts_min ts_max ts_rank ts_delta ts_delay ts_corr ts_decay_linear ts_decay_exp_window if_else winsorize ts_backfill ts_av_diff`

**禁用（战役已实测证伪 / 引擎拦截）**：
`group_neutralize`（引擎黑名单）· `bucket`（8槽全 0.00）· `trade_when`（实测有害）· `hump`（有害）· `signed_power`（有害）· `quantile`（有害）· `ts_arg_max` · `ts_arg_min` · `reverse`（本战役黑名单）
**最外层禁用** `group_rank` / `rank` —— 输出恒 [0,1] ⇒ 组合必然单边 ⇒ Ret/Margin 是市场 Beta 幻觉。**最外层必须是零均值构造**：`zscore` / `ts_zscore` / `group_zscore` / `ts_delta` / `ts_av_diff`。
**禁用** `add(rank(A), rank(B))`（无量纲加总，引擎物理拦截）。
**禁用** `subtract(x, 0.5)`（比率字段天然正偏置）。

---

## 3. 平台门禁（终态判据，零隐瞒）

| 指标 | 阈值 |
|---|---|
| IS Sharpe | **≥ 1.58** |
| Fitness | **≥ 1.00**，公式 **`Fit = Sh × √(|Ret| / max(TO, 0.125))`** |
| Margin | **≥ 10 bps**，`Mgn_bps = 20 × Ret / TO` |
| Turnover | **∈ [1%, 70%]**（平台 LOW_TURNOVER 实测阈值=1%，HIGH_TURNOVER=70%） |
| 2Y Ladder Sharpe | **≥ 1.58** |
| Sub-universe Sharpe | 平台 fail 口径 |
| `checks.fail` | **必须为空**（唯一权威判据 = `ra.ra_failed == false`） |
| ProdCorr | **< 0.70**；本地 SelfCorr **≤ 0.60** |
| 正收益年数 | ≥ 8/10 |

**设计含义（务必读懂）**：
- 换手低于 12.5% 不会被 Fitness 惩罚（分母有 12.5% 地板）⇒ **低频基本面数据在 Fitness 上天然占优**，不必为抬换手而引入外部量价字段。
- 但 `Ret/TO ≥ 0.5` 是硬要求：若 TO=5%，则年化收益需 ≥2.5%；若 TO=2%，需 ≥1%。
- ⚠️ **绝对不得引入 `close` / `returns` / `volume` / `cap` / `vwap` 等外部量价字段**（跨数据集 PV 污染 ⇒ ProdCorr > 0.70 被物理封杀），也不得使用本数据集内嵌量价的 73 个字段（`fnd17_nprice / mktcap / ev_cur / pr1dayprc / vol* / priceavg* / *price2bk* / *peexclxor* / *spfcr* / ebitda2ev* / yield` 等）。

---

## 4. 已证伪 / 已闭合（严禁重烧）

- `group_rank(·, group)` 位于**最外层** ⇒ 组合必然单边 ⇒ 不可信其 Sharpe。
- `group_neutralize(·, subindustry)` —— 本账户证伪 + 引擎物理拦截。
- `bucket(...)` —— 8 槽全部 Sharpe 0.00 / TO 0.0%，整批作废。
- `add(rank(A), rank(B))` —— 无量纲加总，纯数学过拟合，引擎物理拦截。
- `trade_when` —— 本账户高频数据上实测有害（Sharpe 1.37→0.13），CW 亦未解。
- `hump` / `signed_power` / `quantile` / `max_trade=ON` —— 本账户有害算子。
- `ts_decay_*` **不得放在 `ts_backfill` 内部**（两层时间算子互相污染 ⇒ 换手爆炸）。正确顺序：**降维 → ts_backfill → 标准化 → 最外层再衰减**。
- `ts_zscore` 用作**信号内部归一化**会摧毁信号（EUR fnd17 实测 Sharpe 0.15~0.56）；`zscore` 作**最外层**是必需的去单边手段。两者不可混谈。
- 仿真设置固定：`neutralization=STATISTICAL, decay=8, truncation=0.08, pasteurization=ON, unit_handling=VERIFY, nan_handling=ON, language=FASTEXPR`。你**不得**建议改这些。

## 5. 本数据集已证有效机制（可迁移，但 USA 口径须重测）

- **FCF/资产、FCF/收入家族在本数据集真实有效**：EUR/TOPCS1600 上 `group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_atmtt,250)), sector)` Sharpe 2.23；`/fnd17_arev` 2.29；`/fnd17_fcfq` 1.99。**但最外层是 group_rank ⇒ 单边 ⇒ 其 Sharpe 不可直接信**，须换零均值顶层后重测 —— 这正是你要做的。
- `fnd17_tcpaorq`（季度年化 ROA）是最佳第二锚。
- **`qrev` 优于 `ttmrev`**（稳健性）。
- `fnd17_aebitd`（EBITDA 规模）当分母 → Sharpe 0.33~0.41 且 Y2 为负 ⇒ **EBITDA 规模是错误量纲**（规模因子≠信号）。
- EUR 侧 in-expression 中性化：**sector 最优**，industry/subindustry 使 robust 掉到 0.35~0.46（本战役改用 sim 层 STATISTICAL + 顶层零均值，规避此坑）。
- 本账户 USA/d1 已提交 70 条 alpha 中 `fnd17_` 字段使用数 = **0** ⇒ 本数据集对本账户 USA/d1 组合是**真实冷启动面**。跨区域已烧 22 个 fnd17 字段（`ev_cur, ebitda2ev*, revgrpct, qtotd2eq, atq, cainq, priceavg*, nprice…`）⇒ **跨区域 self-corr 风险集中在少数字段，优先用孪生字段与 ac=0 字段**。

---

## 6. 交付格式（严格遵守）

对每条候选交付一段 JSON：

```json
{
  "question_type": "Invariance",
  "expression": "zscore(<你的表达式>)",
  "fields": ["fnd17_xxx", "fnd17_yyy"],
  "mechanism": "一句话物理机制（≤60字）",
  "counterparty": "具体到行为模式的对手盘（≤50字），不得写'市场'",
  "optimize_reason": "≥200字深度因果归因：①针对什么物理短板 ②数学变形如何增强对真实经济学现象的捕捉 ③为什么这个结构不会单边/不会伪因果",
  "treatment_tag": "one of: ts_mean_smooth | group_zscore_neutral | ts_backfill_staleness | winsorize_tail | rank_weight_interact | none",
  "self_check": {
    "operator_count": 3,
    "field_count": 2,
    "window_used": 60,
    "top_level_zero_mean": true,
    "unit_consistent": "说明：两个被减字段为何量纲可比",
    "no_double_signed_multiply": true,
    "no_pv_contamination": true,
    "fields_exist_in_dossier": true,
    "field_acs": [0, 4],
    "field_covs": [0.86, 0.91],
    "why_not_already_used": "反拥挤论证：为何这组字段+结构的 ac 组合在本账户 USA/d1 上未被使用"
  }
}
```

**输出末尾附一行**：`SLICES_SUMMARY: <你交付了几条，各自 question_type>`。

---

## 7. 你的具体任务

（由编排官在派发时填写）

