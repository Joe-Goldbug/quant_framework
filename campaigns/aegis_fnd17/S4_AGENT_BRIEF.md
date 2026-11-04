# AEGIS · fundamental17 · S4 新机制设计简报（多智能体 Sub-Agent 必读）

**战役参数**：REGION=USA / UNIVERSE=TOP1000 / DELAY=1 / dataset=fundamental17 (category=fundamental)
**提交纪律**：HARD_SUBMISSION_RULE —— **禁止调用任何 Alpha 提交接口**。
**⚠️ 配额纪律**：本轮是 **Stage 2 零配额设计阶段** —— **禁止调用任何 BRAIN 仿真接口**
（`create_simulation` / `submit_multi_simulation` / `create_multi_simulation` / `check_simulation` /
`check_multi_simulation` / `fetch_multi_simulation_result`）。
**严禁调用任何 brain-mcp 工具**。你只需要做「字段 → 机制 → 表达式」的设计推理。
仿真由编排官统一执行。

**日期**：2026-10-28

---

## 1. 你要交付什么

**4 条候选表达式**（不是 1 条），每条对应一个**不同的机制假设**。4 条必须是**结构互不相同**
的（不同字段组合 + 不同算子骨架），以便编排官做骨架去重。

对每条给出：

| 字段 | 内容要求 |
|---|---|
| `id` | 形如 `S4_<你的轴字母>_01` 的唯一 ID |
| `question_type` | Q1..Q8 之一（见 §4） |
| `expression` | FASTEXPR 表达式，**逐字可粘贴** |
| `fields_used` | 用到的全部 fnd17 字段 id |
| `economic_mechanism` | 经济机理（中文，2-3 句，讲清「谁在买、谁在卖、为什么能持续」） |
| `counterparty` | 对手方画像（中文，一句话） |
| `optimize_reason` | 为何这个构造在本数据集的物理约束下合理（中文） |
| `treatment_tag` | `none` 或一个简短机制标签 |
| `self_check` | 对象：`{"sign_symmetry":"...","zero_mean_top":"...","anti_crowding":"..."}` |

---

## 2. 字段宇宙（唯一权威）

读 `agent_field_ref.json`（同目录，289 个字段）。每条：

```json
"fnd17_fcfmtt": {"d":"Free cash flow - trailing 12 months","ac":10,"cov":0.9102,
                 "dom":"unbounded","sp":false,"ax":["accrual_quality"]}
```

- `ac` = 平台上已有 alpha 使用该字段的数量（**反拥挤指标：越低越好，ac=0 是 virgin**）
- `cov` = 覆盖率（**cov<0.80 视为稀疏，须防 CONCENTRATED_WEIGHT**）
- `dom` = 值域：`unbounded` / `[0, inf)` / `[-1, 1]`
- `sp` = 是否稀疏
- `ax` = 语义轴（accrual_quality / profitability_roa_roe / efficiency_dupont /
  leverage_solvency / liquidity_coverage / growth_surprise / share_count_dilution /
  cost_intensity_rd / uncertainty_scale）

**字段硬约束**：
- 只用 `fnd17_` 前缀字段；**禁止** `*_currency_code_*` / `*_exrate`（汇率名义码）；
- **禁止**任何内嵌量价字段：`fnd17_nprice / mktcap / ev_cur / pr1dayprc / vol* / priceavg* /
  *price2bk* / *peexclxor* / *spfcr* / ebitda2ev* / awcappspr / qwcappspr / yield`（零 PV 污染铁律）；
- **优先 ac ≤ 5 的字段**；**强烈优先 ac = 0 的 76 个 virgin 字段**；
- 2~3 个字段（奥卡姆剃刀）；算子数 ≤ 4（Phase 0 上限，`op_cap_override` 可放宽但请自行控制）。

---

## 3. 已证伪清单（**严禁重烧**，这些都实测过）

### 3.1 结构黑名单
| 禁止 | 原因 |
|---|---|
| `group_rank(·, group)` 位于**表达式最外层** | 输出恒 [0,1] ⇒ 组合必然单边（shortCount=0）⇒ Ret/Margin 是市场 Beta 幻觉。**顶层必须零均值** |
| `group_neutralize(·, subindustry)` | 本账户证伪 + 引擎物理拦截 |
| `bucket(...)` | 本账户 8 槽全 Sharpe 0.00，整批作废 |
| `add(rank(A), rank(B))` | 无量纲加总，引擎物理拦截 |
| `trade_when` | 本账户实测有害（Sharpe 1.37→0.13） |
| `hump` / `signed_power` / `quantile` / `max_trade=ON` | 本账户有害算子 |
| `ts_decay_*` 放在 `ts_backfill` **内部** | 两层时间算子互相污染 ⇒ 换手爆炸。正确顺序：**降维 → ts_backfill → 标准化 → 最外层衰减** |
| `ts_zscore` 作信号内部归一化 | 摧毁信号（EUR fnd17 实测 Sharpe 0.15~0.56）。`zscore` 作**最外层**是必需的 |
| 一阶裸水平值相乘（如 `multiply(ROA, margin)`） | 违反公理 1：两个有正有负的同向变量直接相乘 ⇒ 熊市反向做多暴雷 |
| `subtract(x, 0.5)` | 比率字段天然正偏置，减常数会造出假中性化 |

### 3.2 **本战役三批实测的硬结论**（最重要的输入）
```
S1（一阶逐期差分：本期 − 上期）    最高 |Sharpe| = 0.44   ⇒ PRUNED
S2（水平量行业相对价差 group_rank 差） 最高 |Sharpe| = 0.89   ⇒ PRUNED
S3（EUR 冠军直系移植 + 设置档 A/B）    最高 |Sharpe| = 1.11   ⇒ 首次越过 Step-1(|Sh|≥1.0)
```
**⇒ 一阶逐期差分 = 噪声，不是信号。** 季报驱动数据做「本期 vs 上期」差分 = 披露噪声 + 季节性 + 口径切换。
**⇒ 必须用水平量的行业内相对结构。**

### 3.3 S3 的最佳结构（已实测有效，可作为你的起点或对照）
```
S3_03_FCF_ASSET  alpha=QPvLv6V5  (USA/TOP1000/d1, STATISTICAL/decay8/trunc0.08/nanON)
  subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_atmtt,250)), sector),
           multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))
  → Sh=1.11  Fit=0.53  TO=5.95%  Ret=2.85%  Margin=9.58bp  2Y=1.49  SubU=0.84
  → 算子数 11（已超 Phase0 上限，因移植 EUR 冠军故豁免）
```
外层 `subtract` 保证两个 group_rank 之差**天然零均值**（非 [0,1] 单边）——**这个技巧请沿用**。

---

## 4. 8 问维度（每条种子标一个 question_type）

| 编号 | 维度 | 拷问 | 本数据集材料 |
|---|---|---|---|
| Q1 | Invariance | 什么是规模无关的稳定基准？ | 规模无关比率：FCF/资产、ROA、每股口径 |
| Q2 | Dynamics | 变化速度/加速度/趋势 | 48 个自带「去年同期/上期」的**孪生字段** |
| Q3 | Anomaly | 历史极端偏离 | 比率的时序偏离（`ts_av_diff` / `ts_delta`） |
| Q4 | Interaction | 两字段结合产生新意义？ | 现金支撑度、杠杆×覆盖、增长×质量 |
| Q5 | Structure | 子项占总量的比例？ | 费用率、收入结构、利润率结构 |
| Q6 | Accumulation | 历史效应如何累积衰减？ | `ts_mean` / `ts_decay_linear` 记忆窗 |
| Q7 | Relative | 同行业/组内相对强弱？ | `group_zscore` / 组内秩（**不得置于最外层**） |
| Q8 | Essence | 超出预期的那部分？ | 水平量 vs 自身历史中枢 |

---

## 5. 门禁与算术约束（**这是你设计的真正边界**）

```
Fit     = Sharpe × √(|Ret| / max(TO, 0.125))
Margin_bps = 20 × |Ret| / TO
```
- **TO < 12.5% 时，Fit 的分母被锁死 0.125** ⇒ `Fit ≥ 1.0 ⟺ Sh² × |Ret| ≥ 0.125`
- 在 Sh=1.58 时：`Fit≥1.0 ⟺ |Ret| ≥ 5.0%`
- 在 Sh=1.11 时：`Fit≥1.0 ⟺ |Ret| ≥ 10.2%`（**不可能** ⇒ 必须先提 Sh）
- `Margin ≥ 10bps ⟺ |Ret| / TO ≥ 0.5`

**S3 最佳结构的账**：Sh=1.11、Ret=2.85%、TO=5.95% ⇒ Fit=0.53、Margin=9.58bp。
**⇒ 缺口在年化收益（Ret）**，不在 Sharpe。**你的设计必须在不牺牲 Sharpe 的前提下抬高 Ret。**

**抬高 Ret 的可用杠杆（按可靠性排序）**：
1. **信号更强 ⇒ 持仓更分散到「对的方向」**（提高命中率，而非只提高分散度）
2. **不要用 `ts_mean` 过度平滑**（平滑会削掉年化收益）；季报数据上短记忆窗（20~60）优于长窗
3. **避免把信号做成截面单边**（单边 ⇒ 多空数失衡 ⇒ 收益只是 Beta）
4. **`ts_backfill` 的窗口是换手与收益的直接调节旋钮**：250 太长（数据陈旧），试 120/60 更贴近披露节奏
   —— 窗口只允许 `{3,5,10,20,60,120,252}`，**注意 250 不在白名单**，请用 252 或 120

**年度收益上限的现实**：fundamental17 是季报驱动，TO 天生 2~8%，Ret 天生 1~4%。
**把 Ret 抬到 5% 需要信号的截面解释力真正强**，而不是靠调参。

---

## 6. 四大公理（硬红线）

1. **符号与零点守恒**：比率字段（margin/growth/turnover/coverage/ROA）天然正偏置或可正可负，
   乘方/相乘前必须去中枢；**双有符号合成必须 `add(group_zscore(A,…), group_zscore(B,…))`**；
   `multiply(Signal, Weight)` 的 Weight 必须**严格恒正**（如 `rank(x)` / `sqrt(abs(x))`）。
2. **持仓对称**：稀疏字段必须查 longCount vs shortCount 是否 ~1:1；单边偏离 >15% 即为污染
   ⇒ 顶层零均值是主要手段。
3. **奥卡姆剃刀**：2~3 字段、算子 ≤ 4（若你要突破请明确说明理由）、窗口 ∈ {3,5,10,20,60,120,252}、
   **严禁网格微调**。
4. **反同簇拥挤**：优先 ac ≤ 5、强烈优先 ac=0 字段；热门字段（如 fnd17_fcfmtt ac=10、
   fnd17_tcpaormtt ac=4）必须构造相对结构或换字段。

---

## 7. 顶层零均值 —— 三条已验证可行路径

```pascal
// 路径 A：两个组内秩相减（天然零均值，最外层不是 group_rank）★已实测最有效
subtract(group_rank(<量A>, sector), multiply(0.5, group_rank(<量B>, sector)))

// 路径 B：组内 zscore 相加（零均值，但两腿必须同号同向语义）
add(group_zscore(<量A>, sector), group_zscore(<量B>, sector))

// 路径 C：zscore 包裹组内秩（把 [0,1] 秩拉回零均值）
zscore(group_rank(<量>, sector))
```
`multiply(0.5, ...)` 的 0.5 是**固定权重**（不是调出来的），用于让 A 腿主导、B 腿做基线对照。

---

## 7.5 ★★★ 新增核心杠杆：**权重锐化以抬高 σ**（本轮最高优先级）

### 7.5.1 为什么这是关键（实测推导，非猜测）

平台口径：`Ret = Sh × σ_annual`（年化收益 = 夏普 × 年化波动）。
配合 `Fit = Sh × √(|Ret| / max(TO, 0.125))`，当 TO < 12.5%（本数据集常态）时：

```
Fit = Sh × √(8 × Ret) = Sh × √(8 × Sh × σ) = Sh^1.5 × √(8σ)
```

**⇒ Fit 同时由 Sharpe 和 σ 决定。** 且本账户今日两条实测 alpha 落在一条**等值线**上：

| 结构 / 设置档 | Sh | Ret | σ_annual | Margin | Fit |
|---|---|---|---|---|---|
| FCF/Asset vs 营业利润率 @ `d0/MKT/nanOFF` | 0.85 | 4.22% | **4.96%** | 41.1 bp | 0.49 |
| 同结构 @ `d8/STAT/nanON` | **1.11** | 2.85% | **2.57%** | 9.6 bp | 0.53 |

**⇒ 设置档只在这条等值线上滑动，Fix 不动（0.49 vs 0.53）。光调设置档永远过不了 Fitness。**
**⇒ 必须同时提高 σ 和 Sharpe。**

### 7.5.2 目标坐标

```
要 Fit ≥ 1.0 且 Sh ≥ 1.58  ⇒  Ret ≥ 5.0%  ⇒  σ_annual ≥ 3.17%
（Sh=1.58 时 Ret=Sh×σ ⇒ σ ≥ 5.0/1.58 = 3.17%）
```
σ 门槛 3.17% 介于今日两条实测（4.96% / 2.57%）之间 ⇒ **可达成，但需要「Sharpe 1.58 + σ 3.17%」同时成立**。

### 7.5.3 ★ 锐化算子（本轮要你用的新武器）

本账户**已验证**的 USA/TOP1000/d1 新闻冠军（Sh 1.65~1.67 / Fit 0.95~0.97）用的正是这一招：

```
power(subtract(group_rank(<x>, <group>), 0.5), 5)
```

- `subtract(group_rank(x, group), 0.5)` 把 [0,1] 的组内秩拉回**零均值**（不是单边！合规）
- `power(·, 5)` 把权重分布**锐化**：中部压扁、两端放大 ⇒ 有效持仓集中 ⇒ **σ 上升**，
  而方向性（排序）不变 ⇒ Sharpe 几乎不损
- **指数 5 是固定常数（不是网格调出来的）**，严禁改成 3/4/6 去凑夏普

**用法**：把「零均值顶层」从 `subtract(group_rank(A), group_rank(B))` 升级为
```
subtract(power(subtract(group_rank(A, sector), 0.5), 5),
         multiply(0.5, power(subtract(group_rank(B, sector), 0.5), 5)))
```
或单腿版 `power(subtract(group_rank(A, sector), 0.5), 5)`。

⚠️ **风险**：权重过度集中可能触发平台 `CONCENTRATED_WEIGHT`（limit 0.1）。
truncation=0.08 会封顶单票权重；你无法在设计期验证，只能靠结构保守（保留两腿价差比单腿更稳）。

### 7.5.4 其他可抬 σ 的杠杆（按可用性排序）
1. **保留两腿价差**（subtract A−B）比单腿 zscore 更稳：价差天然零均值且抵消共同成分
2. **缩短 `ts_backfill` 窗口**（120 或 252，不要 250）⇒ 数据更贴近披露节奏 ⇒ 换手与信息同步更新
3. **不要过度 `ts_mean` 平滑**（季报数据上平滑只削收益）
4. **不要把信号做成截面单边**（单边 ⇒ 收益是 Beta 幻觉）
5. 避免 `winsorize`（它削尾 ⇒ 降 σ）；`power` 才是加尾

### 7.5.5 窗口白名单提醒
`ts_backfill` 窗口必须 ∈ **{3,5,10,20,60,120,252}**。
**250 不在白名单**（那是 S3 从 EUR 冠军原样移植留下的痕迹）—— 你设计新种子时用 **120** 或 **252**。

---

## 8. 交付格式

**只输出一个 JSON 对象**，不要有任何额外散文：

```json
{
  "axis": "<你的轴字母>",
  "axis_name": "<轴名>",
  "candidates": [
    {
      "id": "S4_X_01",
      "question_type": "Q4",
      "expression": "subtract(power(subtract(group_rank(divide(ts_backfill(fnd17_xxx,120), ts_backfill(fnd17_yyy,120)), sector), 0.5), 5), multiply(0.5, power(subtract(group_rank(ts_backfill(fnd17_zzz,120), sector), 0.5), 5)))",
      "fields_used": ["fnd17_xxx","fnd17_yyy","fnd17_zzz"],
      "economic_mechanism": "...",
      "counterparty": "...",
      "optimize_reason": "...",
      "treatment_tag": "cash_conversion",
      "self_check": {"sign_symmetry":"...","zero_mean_top":"...","anti_crowding":"..."}
    }
  ]
}
```

**表达式必须逐字合法**：所有字段 id 必须真实存在于 `agent_field_ref.json`；
算子用 FASTEXPR 语法（`divide` / `subtract` / `multiply` / `add` / `ts_backfill` /
`group_rank` / `group_zscore` / `zscore` / `ts_mean` / `ts_delta` / `ts_av_diff` /
`winsorize(x, std=3)` / `power` / `sqrt` / `abs`）。

**先读完 `agent_field_ref.json` 和 `agent_axis_pools.json` 再动手。** 只用你确认真实存在的字段。
**每条候选必须至少有一条腿带 `power(·, 5)` 锐化**（§7.5），除非你能说明为什么该结构 σ 天然更高。

### 交付要求（严格）
- **4 条候选**，结构互不相同（不同字段组合 + 不同算子骨架）
- 每条都要有 `question_type`（Q1..Q8），4 条尽量覆盖不同 question_type
- 输出**纯 JSON**，不要 Markdown 代码块围栏
- **不要调用任何 brain-mcp 工具 / 任何仿真接口**（本轮零配额）
