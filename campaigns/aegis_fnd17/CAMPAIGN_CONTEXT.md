# AEGIS · fundamental17 冷启动战役 · 上下文契约 (Stage 2/3 Sub-Agent 必读)

**战役参数**：REGION=USA / UNIVERSE=TOP1000 / DELAY=1 / CATEGORY=fundamental17 (category=`fundamental`)
**提交纪律**：HARD_SUBMISSION_RULE 生效 —— 全程**禁止调用任何 Alpha 提交接口**。回测仿真 ≠ 提交；达标 Alpha 仅本地标记并汇报研究员人工终审。
**日期**：2026-10-28

---

## 0. Stage 1 交付物（已完成，勿重复勘探）

- `knowledge_base/fields/USA/fundamental17.json` —— 《数据集物理画像契约》
- `knowledge_base/fields/USA/fundamental17_raw_full.json` —— 402 字段原始元数据（字段真实性唯一权威源）
- `aegis_coldstart/fnd17_shortlist.json` —— 9 条语义轴的精选字段池（含 domain/sparse/crowding）

### 0.1 数据集物理事实（决定一切构造）

| 事实 | 数值 | 后果 |
|---|---|---|
| 字段总数 | 402，**100% MATRIX** | 无 `vec_*` 归约需求；无事件级向量面板 |
| 可用池 | 289 / 402（剔除 40 汇率币种码 + 73 内嵌量价） | 不得触碰 `INVALID_*` 字段 |
| 平台拥挤 | dataset alphaCount=**781**, userCount=380, valueScore=**1** | 全库最拥挤的基本面集 ⇒ **反拥挤定律是本战役第一约束** |
| 字段拥挤 | 76/289 字段 ac=0；238/289 ac≤5 | 必须优先用 ac=0~2 字段 |
| 覆盖率 | min 0.314 / median 0.896 / max 0.965 | cov<0.80 ⇒ 稀疏，须防 CONCENTRATED_WEIGHT |
| **更新频率** | **季报/年报驱动**（`q`=最近季, `a`=最近财年, `ttm`=滚动12月, `mtt`=上年同期, `mtp`=prior TTM） | ① 换手天然低（TO 2~8% 区间）⇒ **LOW_TURNOVER 是真实威胁**；② 一阶裸水平值缺乏截面动态 ⇒ **必须构造「本期 vs 自身历史基线」的二阶预期差** |
| **结构资产** | **48 个字段自带「去年同期/上期/前财年」孪生口径** | 本数据集的皇冠明珠：天然满足「二阶预期差 + 零拥挤」双重要求 |
| 字段值域 | 每股金额/金额=unbounded；比率=[0,inf) 或 [-1,1] | **禁用 `subtract(x,0.5)`**（比率有天然正偏置） |

### 0.2 孪生字段对照表（Stage 2 首选材料）

| 本期 | 去年同期/上期 | ac(本期/孪生) | 经济含义 |
|---|---|---|---|
| `fnd17_tcpaormtt` | `fnd17_tcpaormtp` | 4 / **0** | TTM 资产回报率改善 |
| `fnd17_ngmpnmtt` | `fnd17_ngmpnmtp` | 3 / 8 | 净利率拐点 |
| `fnd17_qtotd2eq` | `fnd17_qtotd2eq2` | 1 / 2 | 杠杆去化 |
| `fnd17_qcurratio` | `fnd17_qcurratio2` | 2 / 1 | 流动性改善 |
| `fnd17_ttmintcov` | `fnd17_ptmintcov` | 1 / **0** | 利息保障能力改善 |
| `fnd17_shsoutbs` | `fnd17_shsoutbs2` | 3 / 6 | 股本缩减（回购） |
| `fnd17_ttmrev` | `fnd17_ptmrev` | **0** / 3 | TTM 收入增长 |
| `fnd17_qrev` | `fnd17_2rhsfcfq` 等 | **0** / 4 | 季度量能 |

### 0.3 已排除字段（物理不可用）

- **40 个名义码**：`*_currency_code_*`、`*_exrate`（汇率）—— 数值大小无经济学含义。
- **73 个内嵌量价**：`fnd17_nprice / mktcap / ev_cur / pr1dayprc / vol* / priceavg* / *price2bk* / *peexclxor* / *spfcr* / ebitda2ev* / awcappspr / qwcappspr / yield` 等 —— 违反零 PV 污染铁律（它们是 `close/returns/volume/cap` 的伪装形态）。

---

## 1. 四大公理（硬红线，违反即熔断）

1. **符号与零点守恒**：比率类字段（margin/growth/turnover/coverage/ROA…）天然正偏置或可正可负，**乘方/相乘前必须去中枢**（`subtract(x, ts_mean(x,20))` 或 `ts_zscore`）；**绝对禁止两个有正有负的同向变量直接 `multiply`**（熊市反向做多暴雷）。双有符号合成必须 `add(group_zscore(A,…), group_zscore(B,…))`；若用 `multiply(Signal, Weight)`，Weight 必须**严格恒正**（如 `rank(x)` / `sqrt(|x|)`）。
2. **持仓对称**：稀疏事件型数据必须查 `longCount` vs `shortCount` 是否 ~1:1；单边偏离 >15% 即为 tied-zeros 污染，须用 `ts_backfill` / 事件门控 / 时序衰减外移消除死重。
3. **奥卡姆剃刀**：字段数 `2 ≤ n ≤ 3`；**Phase 0 主信号算子数 ≤ 4**，Phase 1/2 终态 **≤ 6**；时间窗口只允许 `3, 5, 10, 20, 60, 120, 252`；**严禁网格微调**（decay 16→14、std 2.5→2.2 凑夏普）。
4. **反同簇拥挤**：优先 `Alphas 使用数 ≤ 5` 的低拥挤字段；热门字段必须构造**相对于自身历史基线的二阶预期差**，严禁对静态截面水平值做一阶裸乘。

---

## 2. 平台门禁（终态判据，零隐瞒）

| 指标 | 阈值 | 说明 |
|---|---|---|
| IS Sharpe | **≥ 1.58** | |
| Fitness | **≥ 1.00** | `Fit = Sh × sqrt(|Ret| / max(TO, 0.125))` ⇒ `Fit≥1 ⟺ Sh²×|Ret| ≥ 0.125` |
| Margin | **≥ 10 bps** | `Mgn_bps = 20 × Ret / TO` ⇒ 等价 `Ret/TO ≥ 0.5`（工作区内部铁律，非平台 fail 项） |
| Turnover | **∈ [5%, 50%]** | 低换手是本数据集最大风险（LOW_TURNOVER 硬 fail） |
| 2Y Ladder Sharpe | **≥ 1.58** | |
| Sub-universe Sharpe | 平台 fail 口径 | 实测非绑定（259/320 过） |
| `checks.fail` | **必须为空** | 唯一权威判据 = `ra.ra_failed == false` |
| ProdCorr | **< 0.70** | |
| 本地 SelfCorr | **≤ 0.60** | |
| CLUSTER_TEST / MATCHES_THEMES | warning 级 | CLUSTER ≈ 0.81×Sharpe ⇒ 零警告需 Sh≈1.95 |
| 正收益年数 | ≥ 8/10 | Step-1 漏斗硬条件 |

**Step-1 熔断**：单批 8 条若无任何一条满足 `|Sharpe| ≥ 1.0` **且** 正收益年数 ≥ 8/10 ⇒ 该主信号标记 `PRUNED_AT_STEP1`，立即切换，绝不恋战、不微调参数重发。

---

## 3. 仿真设置（P3 杠杆，勿偏离）

```
region=USA  universe=TOP1000  delay=1  instrumentType=EQUITY
neutralization=STATISTICAL   decay=8   truncation=0.08
pasteurization=ON  unit_handling=VERIFY  nan_handling=ON
max_trade=OFF  language=FASTEXPR  visualization=false
```

**为什么是 STATISTICAL + decay 6~12**：全库 12,272 条实测中，控 Sh≥1.58 后 STATISTICAL 通过率 73.0% vs INDUSTRY 19.3% vs SUBINDUSTRY 2.1%；decay∈[6,12] 74.5% vs decay=0 15.3%（**每数据集内、每窄 Sharpe 带内都成立**）。decay=0 是全库最差档。
**指纹 MD5(expr, region, universe, delay, neutralization) 不含 decay/truncation** ⇒ 二者是**免费消融轴**（首批用 8/0.08 即可）。

---

## 4. 本账户已证伪 / 已闭合（严禁重烧）

### 4.1 算子与结构黑名单
- `group_rank(·, group)` **位于表达式最外层** ⇒ 输出恒 [0,1] ⇒ 组合必然单边（longCount≈持仓数, shortCount=0）⇒ Ret/Margin 全是市场 Beta 幻觉。**顶层必须换成零均值构造**：`zscore` / `ts_zscore` / `group_zscore` / `ts_delta`。
- `group_neutralize(·, subindustry)` —— 本账户证伪，且被引擎 `FORBIDDEN_OPERATORS` 物理拦截。
- `bucket(...)` —— 本账户 8 槽全部 Sharpe 0.00 / TO 0.0%，整批作废。
- `add(rank(A), rank(B))` —— 无量纲加总，纯数学拼凑过拟合，引擎物理拦截。
- `trade_when` —— 在本账户高频事件数据上实测有害（Sharpe 1.37→0.13），CW 亦未解。
- `hump` / `signed_power` / `quantile` / `max_trade=ON` —— 本账户有害算子列表。
- `ts_decay_*` **不得放在 `ts_backfill` 内部**（两层时间算子互相污染 ⇒ 换手爆炸）。正确顺序：**降维 → ts_backfill → 标准化 → 最外层再衰减**。
- `ts_zscore` 用作**信号内部归一化**会摧毁信号（EUR fnd17 实测 Sharpe 0.15~0.56）；`zscore` 作**最外层**是必需的去单边手段。两者不可混谈。

### 4.2 fundamental17 自身的既有实测（EUR/TOPCS1600 口径，勿当 USA 结论，但机制可迁移）
- **FCF/资产、FCF/收入 家族在本数据集真实有效**：`group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_atmtt,250)), sector)` EUR Sharpe 2.23；`/fnd17_arev` 2.29；`/fnd17_fcfq` 1.99。**但最外层是 group_rank ⇒ 单边 ⇒ 不可直接信其 Sharpe**（须换零均值顶层后重测）。
- `fnd17_tcpaorq`（季度年化 ROA）是最佳第二锚。
- **`qrev` 优于 `ttmrev`**（稳健性）。
- `fnd17_aebitd`（EBITDA 规模）当分母 → Sharpe 0.33~0.41 且 Y2 为负 ⇒ **EBITDA 规模是错误量纲**。
- `ts_av_diff(ratio, 60)` 是换手驱动器（3~4%）；accel 窗口 60 最优（30→robust 0.69，120→robust 降，250→Sharpe 0.95）。
- EUR 侧 in-expression 中性化：**sector 最优**，industry/subindustry 使 robust 掉到 0.35~0.46（本战役改用 sim 层 STATISTICAL + 顶层 zscore，规避此坑）。

### 4.3 自相关盘点（本人 310 条已提交 Alpha 全量实读）
- 本人 **USA/d1 的 70 条已提交 Alpha 中，fnd17_ 字段使用数 = 0** ⇒ 本数据集对本人 USA/d1 组合是**真实冷启动面**。
- 本人 USA/d1 已烧字段：`anl4`×11, `fnd6`×11, `nws12`×3, `nws29`×1, `anl39/anl10/anl52/mdl227/mdl264/snt21` 各 1 ⇒ **跨数据集时不要碰 fnd6**。
- 跨区域已烧 22 个 fnd17 字段（`ev_cur`, `ebitda2ev*`, `revgrpct`, `qtotd2eq`, `atq`, `cainq`, `priceavg*`, `nprice`…）—— 其中 `cainq`/`atq`/`qtotd2eq` 亦在本次候选池内 ⇒ **跨区域 self-corr 风险集中在少数几个字段，优先用孪生字段与 ac=0 字段**。

---

## 5. Stage 2 任务书（8 问种子池）

依据 `quant_framework/roles/02_main_signal_synthesizer.md` 的《8 问特征工程方法论》：

| 编号 | 8 问维度 | 金融学拷问 | 本数据集的对应物理材料 |
|---|---|---|---|
| Q1 | Invariance 不变性 | 什么是稳定基准？偏离稳态的比值？ | 规模无关比率：FCF/Assets、ROA/Assets、每股口径 |
| Q2 | Dynamics 动态变化 | 变化速度、加速度、趋势？ | 孪生字段差分（本期 vs 去年同期）、`ts_delta` |
| Q3 | Anomaly 异常冲击 | 历史极端偏离？ | 比率的时序 z-score / `ts_av_diff` |
| Q4 | Interaction 跨字段协同 | 两个字段结合产生新意义？ | 现金支撑度（FCF vs NI）、杠杆×覆盖 |
| Q5 | Structure 结构占比 | 子项占总量比例？ | 收入增速、利润率结构、费用率 |
| Q6 | Accumulation 累积记忆 | 历史效应如何累积衰减？ | `ts_decay_linear` / `ts_mean` 记忆窗 |
| Q7 | Relative 截面相对性 | 同行业/组内相对强弱？ | `group_zscore` / 组内秩（**不得置于最外层**） |
| Q8 | Essence 本质预期差 | 超出预期的那部分？ | 「本期 vs 自身历史基线」的二阶预期差 |

**硬约束**：每条种子 **2~3 字段、算子 ≤ 4、窗口 ∈ {3,5,10,20,60,120,252}、只用本数据集字段、字段 ac 优先 ≤ 5、顶层零均值**。
