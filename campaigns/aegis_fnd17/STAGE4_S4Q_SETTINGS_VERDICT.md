# AEGIS · fundamental17 · S4Q 设置档全交叉裁决（零隐瞒）

**批次**：`aegis_fnd17_S4Q_SETTINGS_CROSS` · 8 格 = {MARKET, STATISTICAL} × {decay 0, 8} × {nan OFF, ON}
**载体**：GRP/ASSET/营业利润率（8 槽表达式**完全相同** ⇒ 指标差异 100% 归因于设置档）
**纪律**：只回测，未触碰任何提交接口。
**注**：slot8（STAT/d8/ON）与 S4P slot2 配置完全相同，平台去重后未新建 alpha，复用 `QPvLv6V5` 的实测值。

---

## 1. 全交叉实测表

| 中性化 | decay | nan | alpha id | Sh | Fit | TO% | Ret% | Mgn(bp) | 2Y | SubU | fail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MARKET | 0 | OFF | QPvXdRn5 | 0.85 | 0.49 | 2.06 | 4.22 | 40.97 | 1.24 | 0.86 | LOW_SHARPE / LOW_FITNESS / LOW_2Y |
| **MARKET** | **0** | **ON** | **ZYQGLgQd** | **0.99** | **0.66** | **1.96** | **5.55** | **56.63** | **1.25** | **1.17** | LOW_SHARPE / LOW_FITNESS / LOW_2Y |
| MARKET | 8 | OFF | 0mYvWp1v | 0.82 | 0.47 | 1.52 | 4.06 | 53.25 | 1.28 | 0.83 | 同上 |
| **MARKET** | **8** | **ON** | **e75RJabp** | **0.95** | **0.62** | **1.48** | **5.38** | **72.70** | **1.28** | **1.15** | 同上 |
| STATISTICAL | 0 | OFF | LLMJAVre | 1.07 | 0.50 | 6.65 | 2.69 | 8.09 | 1.71 | 0.65 | — |
| **STATISTICAL** | **0** | **ON** | **VkxJo7R0** | **1.17** | **0.57** | **6.53** | **3.01** | **9.20** | **1.54** | **0.87** | — |
| STATISTICAL | 8 | OFF | xArgarYw | 1.00 | 0.45 | 6.04 | 2.52 | 8.34 | 1.68 | 0.60 | — |
| STATISTICAL | 8 | ON | QPvLv6V5 | 1.11 | 0.53 | 5.95 | 2.85 | 9.59 | 1.49 | 0.84 | — |

---

## 2. 三因子主效应（各自在其余两因子上的边际平均）

| 因子 | 档 | n | Sh 均值 | Sh 最高 | Fit 均值 | TO% | Ret% | Mgn(bp) |
|---|---|---|---|---|---|---|---|---|
| **neut** | MARKET | 4 | 0.90 | **0.99** | **0.56** | **1.75** | **4.80** | **56.00** |
| | STATISTICAL | 4 | **1.08** | 1.17 | 0.51 | 6.41 | 2.74 | 8.53 |
| **decay** | 0 | 4 | **1.02** | 1.17 | 0.55 | 4.30 | 3.87 | 28.79 |
| | 8 | 4 | 0.92 | 1.00 | 0.51 | **3.01** | **3.99** | **44.81** |
| **nan** | OFF | 4 | 0.94 | 1.07 | 0.48 | 4.07 | 3.37 | 27.68 |
| | **ON** | 4 | **1.04** | **1.17** | **0.62** | **3.32** | **4.65** | **46.28** |

### 2.1 ★ 最重要发现：**nanHandling=ON 严格支配 OFF（4/4 格全胜）**

| 中性化 | decay | OFF → ON 的 ΔSh | ΔRet | ΔMgn | ΔTO |
|---|---|---|---|---|---|
| MARKET | 0 | +0.14 | **+1.33pp** | +15.7bp | −0.10pp |
| MARKET | 8 | +0.13 | **+1.32pp** | +19.5bp | −0.04pp |
| STATISTICAL | 0 | +0.10 | +0.32pp | +1.1bp | −0.12pp |
| STATISTICAL | 8 | +0.17 | +0.33pp | +1.3bp | −0.09pp |

**4/4 格中 ON 在 Sharpe、Ret、Margin 三项上同时优于 OFF，且换手更低** ——
这不是噪声，是一致方向的主导效应。

⇒ **这推翻了本账户 1410 条历史统计给出的建议**：fnd17 全史里 nan=OFF 档均值 Sh 1.37 > nan=ON 档 0.45
（EUR 冠军 3qVlb3dN 正是 OFF）。但那是**跨区域混杂**的统计；
在本战役口径 USA/TOP1000/d1 的**受控同表达式对照**下，ON 全面占优。
⇒ **历史上"OFF 更好"是区域效应，不是 nan 本身的效应。**
⇒ 今后本战役一律 **nan=ON**。

### 2.2 中性化：Sharpe 与 收益/换手 的取舍
- **STATISTICAL**：Sharpe 更高（1.08 vs 0.90），但 TO 3.7×、Ret 仅一半、Margin 只有 1/6.5。
- **MARKET**：Sharpe 略低，但 Ret 4.80% / TO 1.75% ⇒ **Ret/TO = 2.74**（STAT 仅 0.43）。

---

## 3. ★ 门禁达标画像反解（若把该结构的 Sharpe 抬到 1.58，各格还差什么）

```
Fit = Sh·√(Ret / max(TO, 0.125)) ≥ 1        （平台硬门禁）
Mgn = 20·Ret/TO ≥ 10 bp                       （本账户房规，非平台门禁）
2Y  ≥ 1.58                                    （平台硬门禁，绝对值）
SubU ≥ 平台动态限 ≈ 0.53×Sh                   （本账户实测动态限）
```

TO < 12.5% 时 Fit 门槛统一为 **Ret ≥ 5.01%**（Sh=1.58 时）。

| 中性化 | decay | nan | Sh 现值 | Ret 现值 | Fit@1.58 | 需Ret(Fit) | 需Ret(Mgn) | **结论** |
|---|---|---|---|---|---|---|---|---|
| **MARKET** | **0** | **ON** | **0.99** | **5.55%** | **1.053** | 5.01% | 0.98% | ✅ **双门禁均可过，只差 Sharpe +0.59** |
| **MARKET** | **8** | **ON** | 0.95 | 5.38% | 1.037 | 5.01% | 0.74% | ✅ 双门禁均可过，只差 Sharpe +0.63 |
| MARKET | 0 | OFF | 0.85 | 4.22% | 0.918 | 5.01% | 1.03% | ❌ Ret 差 0.79pp |
| MARKET | 8 | OFF | 0.82 | 4.06% | 0.900 | 5.01% | 0.76% | ❌ Ret 差 0.95pp |
| STATISTICAL | 0 | ON | 1.17 | 3.01% | 0.775 | 5.01% | 3.26% | ❌ Ret 差 2.00pp |
| STATISTICAL | 0 | OFF | 1.07 | 2.69% | 0.733 | 5.01% | 3.33% | ❌ Ret 差 2.32pp |
| STATISTICAL | 8 | OFF | 1.00 | 2.52% | 0.709 | 5.01% | 3.02% | ❌ Ret 差 2.49pp |
| STATISTICAL | 8 | ON | 1.11 | 2.85% | 0.790 | 5.01% | 2.98% | ❌ Ret 差 2.16pp |

### 3.1 2Y 与 SubU 的比值检查（防止"Sharpe 达标但阶梯不过"）
| 中性化 | decay | nan | 2Y/Sh | Sub/Sh | 评价 |
|---|---|---|---|---|---|
| MARKET | 0 | ON | 1.26 | 1.18 | ✅ 双比值均 >1，Sh 到 1.58 时 2Y≈1.99 / Sub≈1.86 |
| MARKET | 8 | ON | 1.35 | 1.21 | ✅ 最健康 |
| STATISTICAL | 0 | OFF | 1.60 | 0.61 | 2Y 好但 Sub 逼近动态限 |
| STATISTICAL | 8 | OFF | 1.68 | 0.60 | 同上 |

### 3.2 ★★ 结论：**MARKET + decay=0 + nan=ON 是下一批换核结构的正确设置档基线**
理由：① 唯一在 Sh=1.58 时 Fit 与 Margin **双双可过**（Ret 5.55% > 5.01% 门槛）；② Sharpe 距门槛最近（+0.59）；③ Sub/Sh=1.18 最健康；④ TO 1.96% 远在 [1%,70%] 内。
（次选 MARKET + decay=8 + nan=ON：TO 更低 1.48%、Mgn 更高 72.7bp，但 Sharpe 门槛 +0.63。）

---

## 4. ⚠️ 诚实披露：MARKET 档高收益的来源存疑

MARKET 只中和市场 beta，不做行业/风格中和。对纯基本面信号，**其 Ret 4.80% 里含有未剥离的市场与规模暴露**，
而 STATISTICAL 会把这些剥离掉 —— 这正是 STATISTICAL 下 Ret 掉一半、Sharpe 反高的原因。
⇒ 因此「MARKET 档 Ret 高」**部分可能是 Beta 幻觉**，不能直接当成"更优"。

**但有三条证据支持它在本战役的合法性**：
1. **平台判据**：`e75RJabp` / `ZYQGLgQd` 的 `checks.fail` 只有 LOW_SHARPE / LOW_FITNESS / LOW_2Y，
   **CONCENTRATED_WEIGHT、LOW_SUB_UNIVERSE_SHARPE、LOW_TURNOVER 均 PASS** ——
   平台不要求行业中性。
2. **先例**：本账户唯一通关的 fnd17 alpha `3qVlb3dN`（EUR，OS 已提交）正是
   **decay=0 / MARKET / nan=OFF**，`checks.fail` 全空、prodCorr 0.64、selfCorr 0.32。
3. **Sub-universe 不塌**：MARKET 档 SubU 1.15~1.17 反而是全表最高
   （STATISTICAL 档 0.60~0.87）⇒ 收益不是只靠大市值票堆出来的。

⇒ 仍须在最终候选上**实测 prodCorr < 0.70**，若 MARKET 档候选的 prodCorr 越线，
则退回 STATISTICAL 档并改攻 Ret（那时需 Ret ≥ 5.01% 而非当前的 3%）。

---

## 5. 本批最佳（不达标，不提交）

- **最高 Sharpe**：`VkxJo7R0`（STATISTICAL/decay0/nanON）
  Sh **1.17** / Fit 0.57 / TO 6.53% / Ret 3.01% / Mgn 9.20bp / 2Y **1.54** / Sub 0.87 / `fail` 空
  —— **刷新 USA/TOP1000/d1 的 fnd17 天花板（原 1.11）**，但 Ret/Margin 不够。
- **最接近门禁**：`ZYQGLgQd`（MARKET/decay0/nanON）
  Sh 0.99 / Fit 0.66 / TO 1.96% / Ret 5.55% / Mgn 56.63bp / 2Y 1.25 / Sub 1.17
  —— 收益画像完全就位，**只差 Sharpe +0.59**。

**两批（S4P+S4Q）共 16 次仿真后，USA/TOP1000/d1 fnd17 最高 Sharpe = 1.17，仍未过 Step-1 漏斗（≥1.58）。**
