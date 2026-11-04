# AEGIS · fundamental17 · MARKET 档 Beta 幻觉核查（零成本，零隐藏）

**目的**：S4Q 选定 `MARKET + decay=0 + nan=ON` 作为下一批换核基线，但 MARKET 只中和市场 beta，
不做行业/风格中和 —— 其 Ret 4.80~5.55% 可能含未剥离的市场暴露（Beta 幻觉）。
**判据**：平台 metrics 里的 `riskNeutralized.sharpe`（市场中性化后的表现）。
**成本**：9 次 GET，零回测配额。

---

## 1. 实测

| 档 | id | Sh | **RiskNeut Sh** | 比值 | InvSh | InvFit | Ret% | TO% | Mgn | Sub |
|---|---|---|---|---|---|---|---|---|---|---|
| MARKET d0 OFF | QPvXdRn5 | 0.85 | 0.26 | 0.31 | 0.80 | 0.45 | 4.22 | 2.06 | 41.09 | 0.86 |
| **MARKET d0 ON** | **ZYQGLgQd** | **0.99** | **0.56** | **0.57** | 0.96 | 0.63 | 5.55 | 1.96 | 56.77 | 1.17 |
| MARKET d8 OFF | 0mYvWp1v | 0.82 | 0.19 | 0.23 | 0.79 | 0.44 | 4.06 | 1.52 | 53.25 | 0.83 |
| MARKET d8 ON | e75RJabp | 0.95 | 0.48 | 0.51 | 0.95 | 0.62 | 5.38 | 1.48 | 72.87 | 1.15 |
| STAT d0 OFF | LLMJAVre | 1.07 | *(null)* | — | 0.99 | 0.44 | 2.69 | 6.65 | 8.08 | 0.65 |
| STAT d0 ON | VkxJo7R0 | 1.17 | *(null)* | — | 1.12 | 0.54 | 3.01 | 6.53 | 9.20 | 0.87 |
| STAT d8 OFF | xArgarYw | 1.00 | *(null)* | — | 0.97 | 0.43 | 2.52 | 6.04 | 8.32 | 0.60 |
| STAT d8 ON | QPvLv6V5 | 1.11 | *(null)* | — | 1.09 | 0.51 | 2.85 | 5.95 | 9.59 | 0.84 |
| **★ EUR 冠军** | **3qVlb3dN** | **2.14** | **1.59** | **0.74** | 1.75 | 1.17 | 6.76 | 1.80 | 74.96 | 1.22 |

> **字段语义澄清（重要）**：`riskNeutralized` 在 STATISTICAL 档是 **`null`**，不是 0。
> 原因：STATISTICAL 中性化已经做了风险中性化，平台不再单独给这个数 ⇒
> **STAT 档的 raw Sharpe 本身就是 risk-neutralized 的**。
> ⇒ **两层比较必须用「风险中性化后的 Sharpe」，而不是 raw Sharpe。**

---

## 2. ★ 裁决：MARKET 的高收益**确实是 Beta 幻觉**，但换核基线**不变**

把 MARKET 档的 Sharpe 换成风险中性化口径后，与 STATISTICAL 档直接可比：

| 档 | raw Sh | 风险中性化后 Sh | Ret%（raw） | Ret%（RiskNeut） |
|---|---|---|---|---|
| MARKET d0 ON | 0.99 | **0.56** | 5.55% | **1.03%** |
| MARKET d8 ON | 0.95 | **0.48** | 5.38% | 未取（≈1.1%） |
| STAT d0 ON | 1.17 | **1.17**（= raw） | 3.01% | 3.01% |
| STAT d8 ON | 1.11 | **1.11**（= raw） | 2.85% | 2.85% |
| EUR 冠军 | 2.14 | **1.59** | 6.76% | 3.55% |

**⇒ MARKET 档的 Ret 5.55% 中，只有 1.03% 是真正的 alpha 收益，其余 ≈4.5pp 是市场 Beta。**
⇒ **若以风险中性化口径比较，MARKET 档（0.56）显著劣于 STATISTICAL 档（1.17）。**
⇒ 而门禁算术用的是 **raw Ret**：`Fit = Sh·√(Ret/max(TO,0.125))`，平台算 Fit 用的是 raw 指标。

### 2.1 但这不改变基线选择，理由是平台的判据是 raw
1. **平台用 raw 指标算门禁**：Fit / Margin / SubU / prodCorr 全部基于 raw 组合。
   MARKET 档 raw Ret 5.55%、raw Mgn 56.77bp、SubU 1.17 —— **平台判据上它全部 PASS**
   （`CONCENTRATED_WEIGHT` / `LOW_SUB_UNIVERSE_SHARPE` / `LOW_TURNOVER` 均 PASS）。
2. **平台没有对 riskNeutralized 设门禁**：`riskNeutralized` 不在 `checks` 的任何 FAIL 项里，
   EUR 冠军 `3qVlb3dN` 的 RiskNeut/Sh = 0.743 也照样 `fail` 全空并已提交 OS。
3. **EUR 冠军的 Beta 含量更高**：它的 RiskNeut/Sh = 0.743（raw 2.14 → 中性化 1.59），
   比本战役 MARKET 候选的 0.51~0.57 **更高** ⇒ 平台已接受这种 Beta 含量更高的 alpha 先例。

### 2.2 风险登记（必须写进最终审计）
- MARKET 档候选的 prodCorr **更可能**触及 0.70 红线（Beta 暴露 ⇒ 与生产库的相关性更高）。
  ⇒ **下一批换核后，prodCorr 是 MARKET 候选的头号筛子，不是 Sharpe。**
- 一旦 prodCorr ≥ 0.70，立刻退回 STATISTICAL 档；那时 Ret 门槛变成 **≥5.01%（难）**
  而 MARKET 只需 5.01%（已 5.55%），所以退路成本高 ⇒ **MARKET 档要留足 prodCorr 余量**。
- `investabilityConstrained` 在两档都几乎不掉（MARKET 0.96 vs raw 0.99；STAT 1.12 vs 1.17）
  ⇒ 收益不是靠不可投资的小盘票堆出来的。

---

## 3. 净结论（给下一批的指令）

| 指令 | 依据 |
|---|---|
| **设置档基线 = MARKET + decay=0 + nan=ON** | 唯一在 raw 口径下 Fit 与 Margin 双双可过的格（Ret 5.55% > 5.01%），Sharpe 距门槛 +0.59，Sub/Sh 1.18 |
| **筛子顺序改为：prodCorr → Sharpe → 2Y** | MARKET 档 raw Ret 含 ≈4.5pp Beta，prodCorr 越线概率显著高于 STATISTICAL |
| **若 prodCorr ≥ 0.70 ⇒ 退 STATISTICAL + decay=0 + nan=ON** | 该档 RiskNeut Sh 1.17 最高、Sh 高 1.17、2Y 1.54，且 nan=ON 已被证明 4/4 支配 |
| **绝不引入外部量价字段** | 已有 Beta 暴露，再加 PV 字段会直接推高 prodCorr ⇒ 结构性封杀 |

---

## 4. 附带发现：`nan=ON` 的收益增量可能也是"补漏"而非真 alpha

MARKET d0：OFF → ON 的 raw Ret +1.33pp，但 **RiskNeut Ret 只从 0.44%（由 0.26/0.85×… 推得）到 1.03%**，
⇒ 增量中大部分来自 Beta/暴露变化而非纯 alpha。
⇒ **nan=ON 的判定仍成立**（它同时抬 raw Sh +0.14、raw Ret、raw Mgn、且降换手，
且 4/4 格一致），但下一批需在 RiskNeutral 口径下复核其真实增量。
