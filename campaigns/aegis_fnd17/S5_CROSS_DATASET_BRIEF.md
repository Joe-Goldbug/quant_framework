# S5 · 跨数据集正交增锐 · 研究任务书（USA / TOP1000 / delay=1）

> **硬纪律**：HARD_SUBMISSION_RULE 生效 —— **禁止调用任何 Alpha 提交接口**；
> **本任务书下的设计 Agent 也禁止发起任何仿真**（零配额）。只做设计 + 本地零配额预检。
> 回测由总控统一执行。

---

## 0. 研究员新授权（2026-10-29）

> 「专注于 USA top1000 基本面数据集，允许跨一个数据集，但是 alpha 表达式中最多出现来自
> **两个不同数据集**的字段，预期回测出高质量无 fail 项的 alpha」

⇒ **G7 新闸门**：表达式内出现的数据集数 **≤ 2**；字段总数仍 **2~3**；算子数 ≤ 6（终态）。

---

## 1. 平台门禁（**实测标定**，不是猜测）

从本人 310 条已提交 alpha 的 `checks` 字段反推的真实阈值：

| 检查项 | FAIL | WARNING | PASS（真·合格） |
|---|---|---|---|
| `LOW_SHARPE` | ≤ 0.99 | 1.00 ~ 1.26 | **≥ 1.58**（实测 1.58 的 2rjRlvbZ PASS） |
| `LOW_FITNESS` | ≤ 0.66 | 0.67 ~ 0.70 | **≥ 1.00**（实测 fitness=1.00 的 6XdV13M5 / O0JNOMO1 均 PASS） |
| `LOW_2Y_SHARPE` | ≤ 1.51 | 1.52 ~ 1.54 | **≥ 1.58** |
| `LOW_SUB_UNIVERSE_SHARPE` | ≤ 0.32 | — | **动态阈值 ≈ 0.53 × Sharpe** |
| `LOW_TURNOVER` | < 0.01 | — | **≥ 0.01**（远低于本战役实际值，非约束） |
| `HIGH_TURNOVER` | > 0.70 | — | ≤ 0.70 |
| `CONCENTRATED_WEIGHT` | > 0.10 单票权重 | — | ≤ 0.10 |
| `CLUSTER_TEST` | — | value < 1.58 | value ≥ 1.58（**零警告需 Sh ≈ 1.95**） |

**⇒ 「无 fail 项」的正确判据 = `checks.fail == []`（平台把 FAIL/WARNING/PASS 分三档，
WARNING 不阻断提交，但 WARNING 会暴露「离合格还差多少」）。**

---

## 2. 本战役已实测的全部硬事实（**禁止重烧**）

### 2.1 门禁算术（决定一切）

```
Ret  = Sh × σ_annual                （平台恒等式）
Fit  = Sh × √(|Ret| / max(TO, 0.125))   ← TO < 12.5% 时分母被锁死 0.125
⇒ Fit = Sh^1.5 × √(8σ)
Mgn_bps = 20 × |Ret| / TO
```

fundamental17 是季报驱动 ⇒ **TO 天生 2~8% ⇒ 永远落在 0.125 锁死区**。

**全 PASS 的必要条件（联立求解）**：
```
Sh ≥ 1.58 且 Fit ≥ 1.00
⇒ σ ≥ 3.17%  且  Ret ≥ 5.01%
⇒ 在 TO=7% 时 Margin ≈ 14.3bp（自动过 10bp 铁律）
```

### 2.2 ★ 当前冠军（零 FAIL，已达标）

```
C03_DIFFPOW3_W50_FCFA   alpha=LLMJq3Xa
power(subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,120), ts_backfill(fnd17_atmtt,120)), sector),
               multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,120), sector))), 3)
Sh 1.26 | Fit 0.70 | σ 3.02% | Ret 3.81% | TO 7.22% | Mgn 10.56bp | SubU 0.81 | 2Y 1.33
FAIL=[]  WARN=[LOW_SHARPE, LOW_FITNESS, CLUSTER_TEST, LOW_2Y_SHARPE]
年度 Sharpe: 2.14 / 0.69 / 0.23 / 2.21 / 1.22 / -0.38 / 1.82 / 2.05 / 1.10 / 1.58  ⇒ 9/10 正
```

### 2.3 ★ σ 杠杆归因（S4-B 设置档 OFAT，8 槽逐字相同只改设置）

| 档位 | Sh | σ | Ret | TO | Margin |
|---|---|---|---|---|---|
| 基准 d8/STAT | 1.10 | 2.57% | 2.83% | 5.96% | 9.50bp |
| decay → 0 / 4 / 16 | 1.15 / 1.11 / 1.09 | 2.57~2.59% | — | — | ~9.4bp |
| nan → OFF | 0.97 | 2.52% | 2.44% | 6.05% | 8.07bp |
| trunc → 0.15 | 1.10 | 2.57% | 2.83% | 5.96% | 9.50bp |
| **neutralization → MARKET** | 0.97 | **5.66%** | 5.49% | **1.48%** | **73.97bp** |
| **neutralization → INDUSTRY** | 0.97 | **5.14%** | 4.99% | 1.94% | 51.53bp |

**⇒ decay / nanHandling / truncation 三个维度对 σ 几乎无影响；唯一真变量是 neutralization。
但 MARKET/INDUSTRY 档 2Y 崩塌（S4-D：D01 2Y=0.68 vs STAT 1.33）⇒ **MARKET 是 β 幻觉，不可用。**

### 2.4 ★ power 锐化的位置（S4-A / S4-C 实测）

| 构造 | Sh | σ | 结论 |
|---|---|---|---|
| 两腿 group_rank 差值（基线） | 1.10 | 2.57% | 基准 |
| **单腿 power3** | 1.04 | **3.19%** | σ +24%，SubU 1.02，零 FAIL |
| 单腿 power5 | 0.90 | 3.38% | 过度锐化削排序信息 |
| **两腿各自 power 后相减** | **0.30** | 3.33% | **排序信息被摧毁** |
| **差值后 power3** | 0.43 | 4.49% | σ 高但 Sh 崩 |
| **差值后 power3 + 第二腿 ×0.5** | **1.26** | 3.02% | ★ 冠军 |

**★ 关键洞察（比原简报更精确）**：
`A - 0.5B` 与 `A - B` 的差 = `+0.5B`。所以 C03 ≈ **(FCF/资产 − 营业利润率) + 0.5 × 营业利润率**。
⇒ **信号主要由 A 腿（FCF/资产质量）承载，B 腿（营业利润率）不是「配对」，而是权重可调的第二腿。**
⇒ 差值后锐化只有在**两腿权重不对称**时才保排序信息；对称差值 + power3 会崩。

### 2.5 已证伪（严禁重烧）

- 所有 `ts_av_diff` / `ts_delta` / `ts_mean(winsorize(...))` 的**时序偏离**构造（S1 最高 Sh 0.44）
- 一阶逐期差分「本期 − 上期」口径（S1 最高 Sh 0.44）
- 两增长口径的价差、成本率/比率的时序偏离
- `bucket` / `trade_when` / `hump` / `signed_power` / `quantile` / `group_neutralize`
- 顶层 `group_rank` / `rank`（输出恒 [0,1] ⇒ 组合单边）
- `add(rank, rank)`（引擎物理拦截）
- `ts_zscore` 作信号内部归一化（摧毁信号）；`zscore` 作最外层是必需的去单边手段
- `ts_decay_*` 放在 `ts_backfill` 内部（换手爆炸）

### 2.6 账户级黑名单

- 本人 USA/d1 已提交 alpha 中 **fnd17_ 字段使用数 = 0** ⇒ fnd17 是真实冷启动面
- 已烧字段（跨数据集时别碰）：`anl4`×11, `fnd6`×11, `nws12`×3, `nws29`×1, `anl39/10/52`,
  `mdl227/264`, `snt21` 各 1
- 跨区域已烧 22 个 fnd17 字段：`ev_cur`, `ebitda2ev*`, `revgrpct`, `qtotd2eq`, `atq`, `cainq`,
  `priceavg*`, `nprice` 等

---

## 3. 伙伴数据集物理画像（已拉取，见 `partner_fields.json`）

### fundamental89 · Accrual based Earnings Model（★ 首选伙伴）
- 444 字段，**100% MATRIX**，dataset alphaCount=75，valueScore=4，覆盖 0.698 均值
- **alphaCount 中位数 = 0**（极度冷门）⇒ 反拥挤满分
- 语义 = 应计质量（Sloan / Jones / Cross-sectional Jones 三个口径）
- 关键字段：
  | 字段 | 含义 | cov | ac |
  |---|---|---|---|
  | `fnd89_major_11_11` | (NI − CFO) / 总资产（**Sloan 应计**） | 0.866 | 0 |
  | `fnd89_fixed1313_d1_accum_4q` | 最近 4 季累计应计 | 0.869 | 0 |
  | `fnd89_fixed1313_d1_current_t` | 应计比率相对自身历史的 t 统计量 | 0.827 | 0 |
  | `fnd89_jones_accrual_r2_other_11` | 应计模型 **R²**（模型解释力） | 0.702 | 0 |
  | `fnd89_asset_d1_asset_change` | 资产变动 | 0.899 | 0 |
  | `fnd89_best11_d1_dts` | 应计比率历史标准差 | 0.881 | 0 |

### fundamental45 · Earnings-call NLP
- 12 字段全 MATRIX，dataset alphaCount=36，cov≈0.77
- `fnd45_us_sentiment_lm2_net_pr`（ac=4）/ `_vader_net_pr`(ac=8) / `fnd45_us_readability_executives`(ac=3)
  / `fnd45_us_numeric_perct_pr`(ac=2) / `fnd45_us_lda_bigram_pr`(ac=3) / `fnd45_us_score`(ac=2)
- ⚠ `fnd45_us_mktcap` = PV 污染，禁止使用

### fundamental77 · Filing Fundamental Data
- 211 字段，dataset alphaCount=**1**（几乎无人用），valueScore=5
- 语义 = 10-K/10-Q **分章节文本情绪**（AFINN / Loughran-McDonald）
- `fnd77_q_lm_positive_cnt` / `_negative_cnt`（cov 0.581，ac=0）、`fnd77_q_valid_tag_cnt`(0.581)、
  分章节情绪如 `fnd77_q_lm_financialinstrumentsdisclosuretextblock`(0.416)、
  `fnd77_q_lm_incometaxdisclosuretextblock`(0.477)

### fundamental110 · Press Release / Revision
- 26 字段全 **VECTOR**（需 `vec_avg` 降维），dataset alphaCount=103
- `fnd110_value` / `fnd110_original_value` / `fnd110_revision_number` / `fnd110_preliminary`
  / `fnd110_period_end` / `fnd110_metric`（VECTOR，cov 0.768~0.888）

---

## 4. 本任务的设计目标（按优先级）

1. **在 C03 的已验证骨架上做跨数据集正交增锐**，把 Sh 从 1.26 抬到 **≥ 1.58**、
   Fit 从 0.70 抬到 **≥ 1.00**、2Y 从 1.33 抬到 **≥ 1.58**。
2. **零 FAIL 是底线**（当前 C03 已达成），但用户要的是「**高质量**无 fail」⇒ 目标是全 PASS 或
   至少「零 FAIL + 只剩 CLUSTER_TEST 一个警告」。
3. **正交性是唯一出路**：fnd17 单数据集已实测封顶在 Sh≈1.26（S1~S4 共 60+ 条表达式的天花板），
   任何 fnd17 内部微调都已被证伪。跨数据集提供**新的信息维度** ⇒ 这是唯一尚未穷尽的搜索面。

### 4.1 门槛算术（设计时自检）

```
目标：Sh ≥ 1.58 且 Fit ≥ 1.00 ⇒ σ ≥ 3.17% 且 Ret ≥ 5.01%
C03 现状：Sh 1.26 / σ 3.02% / Ret 3.81%
⇒ 需要：σ 至少 +5%，且 Sh +25%（两者**必须同时**发生，缺一不可）
```

---

## 5. 结构约束（硬）

- 数据集数 ≤ 2；字段数 2~3；算子数 ≤ 6（终态）
- **顶层必须零均值**（`zscore` / `ts_zscore` / `group_zscore` / `ts_delta` / `ts_av_diff` /
  `subtract` / 奇整数幂 `power`）；顶层 `group_rank`/`rank` 禁止
- 窗口白名单：`{3,5,10,20,60,120,252}`；`ts_backfill` 额外允许 `250`
- 禁止：PV 字段（`close/open/high/low/vwap/volume/cap/returns/sharesout/...`）、
  fnd17 内嵌量价字段（`nprice/mktcap/ev_cur/priceavg/price2bk/peexclxor/spfcr/
  ebitda2ev/awcappspr/qwcappspr/yield/vol/pr1day*`）
- 黑名单算子：`bucket/trade_when/hump/signed_power/quantile/group_neutralize/ts_neutralize/
  reverse/neg/ts_arg_max/ts_arg_min`
- `add(rank, rank)` 物理拦截；`multiply` 的权重腿必须**恒正**
- fnd89/fnd45/fnd77 字段**不需要** `ts_backfill`（平台已日频补齐），fnd17 需要

---

## 6. 交付物（每个候选）

```json
{
  "id": "S5_<axis>_<nn>",
  "expression": "<完整 FASTEXPR>",
  "fields_used": ["...", "..."],
  "datasets_used": ["fundamental17", "fundamental89"],
  "economic_mechanism": "……（为什么这条价差对应可被套利的定价偏差）",
  "counterparty": "……（谁在错误定价这一侧）",
  "optimize_reason": "……（为什么用这两个字段、为什么这个权重、为什么锐化在这里）",
  "treatment_tag": "<机制标签>",
  "self_check": {
    "sign_symmetry": "两腿均可正可负 ⇒ 差值保号；power 奇整数幂保号",
    "zero_mean_top": "顶层算子 = X，profile.zero_mean = true",
    "anti_crowding": "字段 ac 合计 = N",
    "why_not_falsified": "……（逐条对照 §2.5 说明本设计避开了哪个已证伪模式）"
  }
}
```

**每个候选必须给出 4~6 个**（8 槽批次由总控从各 Agent 候选中择优装配，
按 §5 骨架唯一性 + 跨批指纹查重筛）。

---

## 7. 本地零配额预检（自检用，总控会复跑）

```bash
cd <campaign_dir>
python stage5_preflight_cross.py     # 看统一表 + 样例
```
总控装配时会调用 `stage5_preflight_cross.preflight_cross()`，
**你在本地不跑预检也可以**，但必须自己核对 §5 的每一条约束。
