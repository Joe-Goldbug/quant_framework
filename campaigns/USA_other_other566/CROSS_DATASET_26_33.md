# 波次 26–33 — 跨数据集放行后的最终判定

日期 2026-11-05 | USA / D1 / TOP1000 | 种子 `kqNgXQqd`
累计回测：**258 槽已解析**（本轮新增 32 槽）

种子基线：Sharpe 1.27 / Fitness 0.59 / TO 13.93% / Margin 4.37bps / Returns 3.04% / DD 4.89% / Cluster 0.95

---

## 一、数据集选型：绝大多数候选源不可用

| 数据集 | 判定 | 原因 |
|---|---|---|
| other546 / other635 / other699 / sustainable_profit / other545 | **弃用** | 字段全部为 VECTOR，横截面不可用（除 vec_avg 外无法做 group_zscore 之外的操作） |
| other580 (ETF 持仓) | 弃用 | 403 字段，但持仓变动是价格行为的派生量，与 other566 同源，非独立信息集 |
| **other685** (StarMine 盈利质量 + 分析师修正) | **采用** | MATRIX，覆盖 0.42–0.996，17 个 Sharpe>0 字段全部 0 用户/0 alpha（极冷），季度/分析师预期更新节奏 ⇒ 结构低换手，信息源与订单簿形态正交 |
| analyst_revision_horizons（波次 32 已用） | 采用 | `highest_estimate_change_quarterly_eps_30d_long`，但实测无预测力（见 §四） |

## 二、符号陷阱：`diff_current_vs_hist_pe_ratio` 是负 alpha

| 结构 | Sharpe | 说明 |
|---|---|---|
| `group_zscore(diff_current_vs_hist_pe_ratio, subindustry)` 单独 | **-1.09** | R -2.80%、DD 29.6% —— 当前 P/E 高于自身历史中位 = 相对自身历史偏贵 = **跑输** |
| 波次 26 `rank(+x)` 当权重 | 1.45 | **符号巧合**：rank 保号后变成「给贵股高权重」，与快腿亏损股重叠产生虚假收益 |
| 波次 27 加法槽 `add(fast, +x)` | **-1.07** | 符号错误直接毒化组合 |
| 波次 28 符号修正 `add(fast, reverse(x))` | **1.07，0 平台 FAIL** | 修正后成立 |

**教训**：`rank()` 抹平符号，会把错误方向伪装成有效权重。凡带「贵=坏」语义的字段，必须先 `reverse` 再用。

## 三、尺度 bug —— 本轮最重要的发现

波次 28 的加法结构：
```
add(ts_target_tvr_decay(oth566_r20marsi_ret, 0.08), group_zscore(reverse(pe_vs_hist), subindustry))
```
两条腿量级相差约 200 倍：

| 腿 | 幅度 | 换手 |
|---|---|---|
| 快腿（原始预测的 tvr_decay，值域 [-0.04,+0.06]） | ~0.005 | 90% |
| 慢腿（group_zscore 后的估值场） | ~1.0 | 10.87% |

**算术证据**：慢腿单独 R = +2.80%，而整个组合 R = 2.74% ⇒ 快腿净贡献约 **0**。
波次 30 在 8 条慢腿上重复了同一尺度错误，其结果只是慢腿排名，**从未真正测试过混合**。

**换手杠杆的正确位置**：内层 `target_tvr` 0.05 与 0.08 返回**逐位相同**的指标（组合换手由未平滑的慢腿主导）；只有加在**组合外层**才生效：

| 外层 tvr | Sharpe | TO | Margin |
|---|---|---|---|
| 0.05 | 0.94 | 8.43% | 5.64bps |
| 0.04 | 0.86 | 7.54% | 5.79bps |
| 0.03 | 0.80 | 6.70% | 5.95bps |

换手降了，Sharpe 同比降 ⇒ 前沿没有移动，只是沿着同一条线滑动。

## 四、中心化有界秩：R/TO 翻倍的唯一杠杆

波次 32（早前）用 `subtract(0.5, rank(x))` 替代 `group_zscore` 作慢腿：

| 慢腿写法 | R/TO | Margin | Sharpe |
|---|---|---|---|
| `group_zscore(reverse(pe_vs_hist), subindustry)` | 0.253 | 5.07bps | 1.07 |
| `subtract(0.5, rank(pe_vs_hist))` | **0.655** | **13.12bps** | 0.53 |

有界中心化秩把 R/TO 抬了 2.6 倍。波次 33 在此基础上搜索快腿权重 c：

| c（快腿权重） | 0 | 0.5 | 1.0 | 2.0 |
|---|---|---|---|---|
| Sharpe | **0.89** | 0.77 | 0.71 | 0.60 |
| Margin | 6.06bps | 5.21 | 4.85 | 4.14 |

**单调下降** ⇒ other566 快腿在中心化秩形态下是**负贡献**，稀释慢腿而非增强它。这解释了为什么 `R_w30_t05`（只含修正腿+快腿）Sharpe 仅 0.23。

## 五、本轮的平台门新增通过者（相关性已实测）

| alpha_id | 波次 | 表达式 | Sharpe | Fitness | Margin | TO | 2Y | Cluster | ProdCorr | SelfCorr |
|---|---|---|---|---|---|---|---|---|---|---|
| `vR1OLqgA` | 28 | `add(tvr_decay(ret,0.08), group_zscore(reverse(pe_vs_hist),sub))` | 1.07 | 0.50 | 5.07 | 10.83% | 1.23 | 0.56 | 0.5901 | 0.2696 |
| `akKVno8W` | 30 | 同上但用 earnings 口径 `diff_current_vs_hist_price_ratio_earnings` | 1.05 | 0.49 | 5.01 | 10.80% | **1.30** | 0.60 | 0.5643 | 0.2716 |
| `9qxEwv02` | 28 | `tvr_decay(ret × rank(reverse(pe_vs_hist)), 0.12)` | **1.22** | 0.52 | 3.64 | 15.51% | 1.33 | 0.70 | **0.5512** | **0.1754** |

三者全部 **0 平台 FAIL** + MATCHES_THEMES（USA/D1 TOP1000 Theme 2.0x + USA/D1/OTHER 1.4x）。平台门通过总数 5 → **8**。

跨数据集源 `oth685` 的 17 个 Sharpe>0 字段中，只有 P/E-vs-历史系有效；现金流质量系（`oth685_91v` CFO/EV、`oth685_81v` FCF/EV、`oth685_cfroitrn` CFROI 趋势、`oth685_cfroi_3`）单独 Sharpe 为 **-0.20 ~ -0.43**，成长系（`blended_growth_rate_smartest` 0.09、`smartest_growth_this_vs_last` 0.20、analyst 修正腿 0.23）接近零。**other685 里只有「估值相对自身历史」这一条腿可用。**

## 六、精确缺口

五门联立（Margin 与 Fitness 均为平台定义）：
```
Margin = 20·R/TO ≥ 15  且  R ≥ 5.5%   ⟹   TO ≤ 7.33%
TO < 12.5% 时  Fitness = Sharpe·√(R/0.125) ≥ 1.05  ⟹  Sharpe ≥ 1.583
```
唯一通关点：**Sharpe ≈ 1.6、R 5.5%、TO 7.3%、MaxDD ≤ 2.8%**。

| | Sharpe | R | TO | Margin | DD |
|---|---|---|---|---|---|
| 通关所需 | ≥1.58 | 5.5% | ≤7.33% | 15 | ≤2.8% |
| 种子 | 1.27 | 3.04% | 13.93% | 4.37 | 4.89% |
| 合规换手区（TO≤7.33%）全库最佳 | **0.66** | 2.76% | 5.30% | 10.39 | 8.62% |
| 本轮跨数据集最佳 `vR1OLqgA` | 1.07 | 2.74% | 10.83% | 5.07 | 4.66% |

**在合规换手区（TO≤7.33%）内，258 个槽位的最高 Sharpe 是 0.66，而通关需要约 1.6 —— 缺口 2.4 倍。**
换慢信息源（other685 / analyst_revision_horizons）**完全没有改变**这个上限。

## 七、判定

- 五门联合在 USA/D1/TOP1000 上**仍未达成**（258 槽 0 通过）。
- 但本轮有**实质增量**：跨数据集机制被验证可用（估值自锚慢腿 + 快腿倾斜 → 0 平台 FAIL + Margin 首次超过种子 + 平台门通过数 5→8），且确立了 §二/§三/§四三条可复用的工程规律。
- **瓶颈定位**：不是表达式几何，而是 **other566 族的物理属性** —— 它是 1~5 日高频图像预测，收益必须靠高换手兑现；任何满足 Margin≥15bps ⇒ TO≤7.33% 的组合里，它的贡献都被压死。要继续突破，必须**放弃 other566 作为方向腿**，改用「高 IR、低换手、低波」的慢速截面信号族作为 alpha 主体，other566 只能做极小权重的择时倾斜。

## 复现

```
python build_wave26.py / build_wave27.py / build_wave28.py
python build_wave29.py / build_wave30.py / build_wave33.py
python persist_wave_results.py / persist_wave_results_29_30_33.py
python collect_ledger.py     # 258 条
python score_and_select.py
```

产物：`batch_26..33.json` + `batch_26..33_result.json` + `correlations.json`（8 条）
