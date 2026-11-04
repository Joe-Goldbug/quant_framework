# Wave11-H 前沿与闭合性分析报告

**战役**: USA_news_news12_gate1 · news12 · TOP1000 · delay=1 · INDUSTRY · decay=6
**数据口径**: 440 个唯一 alpha（全部 54 个 batch result 文件 + 4 个 baseline 合并，按 aid 去重；含 Wave11-H 已回收的 8 行；另有 16 次 ERROR/CANCELLED 空回测不计入）。字段 sh/fit/to/ret/y2/sub/rn/lc/sc/dd 取自 metrics，fails = checks.fail ∪ ra.ra_failed_checks，warns = checks.warning。

---

## 任务 A：前沿精算

### A0 结构定律复核（全部相容，无矛盾）

| 定律 | 复核值（n=440） | 判定 |
|---|---|---|
| Fit = Sh·sqrt(|Ret|/max(TO,0.11)) | mean\|err\|=0.0029, max=0.0246 | 成立 |
| c=Sh²·(Ret/TO) 守恒 | mean=0.0563, median=0.0444, max=**0.2117**, p95=0.1636, p99=0.1812 | 成立，无一行 >0.30 |
| (Sh,TO) 阶梯前沿 | ≤10%→0.78; 10–25%→0.89; 25–38%→1.19; 38–50%→1.17; 50–70%→1.20; 70–90%→1.49; 90–130%→**1.69**; >130%→1.49 | 成立 |
| CLUSTER_TEST ≈ Sh−0.047 | n=450, mean diff=0.0469, **max CL=1.560** | 成立，从未达标 |
| MATCHES_THEMES ≡ hard fail | 423/423 带 MT 警告的行全部含 hard fail | 成立 |

### A1 按 wave 批次的前沿最优点（每批取 Sh 最大行）

| wave | 批次最优点 (Sh, TO, Fit, Ret, Y2) |
|---|---|
| gate1–9 (30 批) | 最优 1.69 未现；峰值 1.63 @116.9% (N1eGk79E, gate5)；最低 TO 前沿 0.89@22.0% (d5KMbRY2) |
| w10a–w10i (9 批) | 峰值 **1.65 @119.8%** (leMYnJZn, w10d, Y2=2.10, Fit=0.42) |
| w11a | 0.51@13.2%（epsactual 系，全批低 Sh） |
| w11b | 1.56@115.1% (RRAOON51) |
| w11c/w11e | 0.49@9.0% / 0.76@69.1%（pooled-ic / snapshot 系，低 Sh） |
| w11d/w11f | 1.56@119.8% (KPm1Kz8k / mLYv9WvE, Y2=2.16–2.23) |
| w11g | 1.14@123.7% (divergence 系) |
| **w11h** | **1.55@125.4%** (xA1Z9zab, Y2=1.27)——anchor 系未突破前沿 |
| w12 | 1.63@115.9% (9qEeNN3K, 仅 2 fail) |
| w13 | **1.69@125.3%** (d5KG231g, 全场最高 Sh) |
| w14 | 1.16@110.8% |

**Pareto 前沿（Sh↓ / TO↓，21 点）**: 1.69@125.3% → 1.65@119.8% → 1.63@115.9% → 1.59@114.6% → 1.57@112.7% → 1.49@83.7% → **1.45@71.8% (vROEWWob, Fit=0.44 全场最高)** → 1.20@68.8% → 1.19@37.5% → 1.15@37.0% → 1.13@36.6% → 0.89@22.0% → 0.78@8.6% → … → 0.22@2.2%。
结论：Sh 与 TO 强正相关，**不存在同时满足 Sh≥1.58 且 TO≤70% 的点**（详见任务 C）。

### A2 c=Sh²·(Ret/TO) 分布（守恒律例外搜索）

- mean=0.0563, median=0.0444, p90=0.1439, p95=0.1636, p99=0.1812, **max=0.2117**
- **>0.30 的行数 = 0**。Top6：0.2117 (e76Po6eM), 0.1902 (vROEWWob), 0.1867 (88vw5eJm), 0.1839 (wp9ddbAY), 0.1812 (omod1Jol), 0.1788 (ZYmJRdbn)
- Fit 分布：median=0.21, p95=0.40, **max=0.44**（vROEWWob）

### A3 Fit≥1.0 的数学要求 vs 实际分布（缺口定量）

由 Law1，Fit=√c，故 Fit≥1.0 ⟺ c≥1.0：
- 相对全场 max c=0.2117，需提升 **4.72×**；相对典型值 0.16 需 6.25×
- 等价地，TO=70% 时 Sh=1.58 需 Ret≥**0.280**；全场 Ret max=**0.1030**（median 0.0361, p95 0.0825）→ **2.7× 缺口**
- 在已实测的任何 TO 档位，Ret 天花板均 ≤0.10：TO≤25% 区 max Ret=0.0984（唯一异常点 e76Po6eM，Sh 仅 0.22），TO≤70% 区 max Ret=0.0532
- 即：**440/440 行 fail LOW_FITNESS，Fit 距门槛最差缺口 0.56，最优缺口仍 >2×**

### A4 「无 fail 无警告」豁免区

- **fails=[] 的行：0/440**。豁免区是空集——每一个有指标的回测都至少 2 个 hard fail。
- fail 数分布与各档最高 Sh：2 fail×6 行（最高 1.63, 9qEeNN3K, TO=115.9%, 仅 HIGH_TURNOVER+LOW_FITNESS）｜3 fail×198（最高 1.69）｜4 fail×134（1.63）｜5 fail×77（1.57）｜6 fail×25（0.75）
- fail 类型普查：LOW_FITNESS 440/440, LOW_SHARPE 427/440, LOW_2Y_SHARPE 348, HIGH_TURNOVER 239, CONCENTRATED_WEIGHT 146, LOW_SUB_UNIVERSE_SHARPE 77
- 结论：即使把门槛砍到「仅无 fail」，最高 Sh=1.63（TO=115.9%）；带 CLUSTER_TEST 警告的行 max CL=1.56 仍未达 1.58。**豁免区内无任何可用候选**。

---

## 任务 B：未探索维度清单（一维已测、交叉未测）

已测空间：26 种算子、103 个字段（catalog 867 个中仅 103 个露面，**773 个零使用**）；nws12_ 标准化家族 239 字段中仅 14 个被测（bestSh≤0.76）。按预期信息量排序的交叉格：

1. **news_ 原生家族 × nws12_ 标准化家族 = 0 次共现**（440 表达式中两家族从未同现）。前者承载全部 Sh≥1.5 的信号，后者提供 225 个未测维度。最大结构性空洞。
2. **low_price_excursion_stddev × trade_when = 0**。该字段 21 次使用即达 bestSh=1.61（二级载体），但从未被 trade_when 门控（trade_when 已用 126 次）。
3. **subindustry × group_rank = 1 次**（唯一一次 Sh=0.29）；**group_neutralize = 0 次**。组内中性化维度几乎未测。
4. **ts_zscore × news_eod_close / news_ton_last = 0**。ts_zscore 全场仅 6 次，只碰过 epsactual/max_up/dn 系；两大 1.69 载体从未被 z-score 归一化。
5. **vec_avg × news_max_up_amt / news_max_dn_amt / news_eod_vwap = 0**。vec_avg 已用 67 次但集中于 nws12/eps 与 excursion 字段，振幅与 vwap 家族未取向量均值。
6. **vec_max × news_max_up_amt / news_max_dn_amt = 0**（vec_max 已用 11 次，只作用于 excursion/eod_close/eod_vwap）。
7. **ts_decay_linear × nws12_* = 0**。ts_decay_linear 已用 20 次，全部作用于 news_ 原生字段。
8. **news_high_exc_stddev / news_low_exc_stddev × rank = 0**。excursion 家族的两个变体字段（各 8–9 次）从未 rank 归一化，而母字段 high_price_excursion_stddev×rank=138 次。
9. **news_eod_close × news_max_up_amt 直接交叉仅 7 次**（vs eod_close×excursion_stddev 170 次）——价格家族与振幅家族的耦合严重欠采样。
10. **长窗口 ts_rank（>180）× 载体字段**：ts_rank 已测窗口 {20,30,40,60,120,180}，250/500 窗仅在 ts_sum 比率骨架中出现过一次（11 次），未在载体字段上扫描。

---

## 任务 C：闭合性判决

**判决：在 news12/TOP1000/d1/INDUSTRY/decay=6 与已扫构造空间内，用户全门槛（Sh≥1.58 ∧ Fit≥1.0 ∧ 2Y≥1.58 ∧ TO≤70% ∧ CL≥1.58 ∧ 无 MT）数学不可达。** 三条独立证据链：

**证据链 1 — Fit 守恒律（绝对瓶颈）**。Law1+Law2 给出 Fit=√c，全场 440 行 c max=0.2117（0 行 >0.30）→ Fit 硬上限 0.46。Fit≥1.0 需 c≥1.0，即守恒乘积提升 4.72×；等价于 TO=70%/Sh=1.58 时 Ret≥0.28，而全场 Ret max=0.1030（2.7× 缺口）。没有任何已测构造模式触碰过该量级。

**证据链 2 — CLUSTER 阶梯（不可同时满足）**。CL≈Sh−0.047（n=450），max CL=1.56<1.58。CL≥1.58 需 Sh≥1.627，全场仅 2 行达标（1.69/1.65），其 TO=125.3%/119.8% ≫70%。反向：TO≤70% 区（n=201）max Sh=1.20 → CL≈1.15，差 0.43。**CL≥1.58 与 TO≤70% 在数据中从未共存，且差距是结构性的（0.4 级），不是边际调参可弥合。**

**证据链 3 — 低 TO 区 Ret/Sh 双天花板**。阶梯前沿显示 Sh 帽由 TO 决定：TO≤25%→0.89，TO≤50%→1.19，TO≤70%→1.20。{Sh≥1.58} 的 13 行全部落在 TO∈[114.6%, 127.6%]，与 {TO≤70%} **交集为空**。且 TO≤70% 且 Y2≥1.58 的仅 4 行，max Sh=1.09。低 TO 区 Ret 天花板 0.0532（剔除异常点），配合 Sh≤1.20 → Fit≤0.38。用户门槛在低 TO 区同时要求 Sh=1.58（超帽 0.38）与 Fit=1.0（超实测 2.6×），双向不可能。

**反例线索（单独列出，供后续验证，均不构成反证）**：
- **vROEWWob**（Sh=1.45, TO=71.8%, Y2=1.61, Fit=0.44, c=0.1902）：全场 Fit 最高且唯一 Y2/TO 双近线（TO 仅超 1.8pp，Y2 已过线）。距全门槛差 Sh +0.13、Fit +0.56。是「最接近」的行，但其差距恰好落在守恒律的 4.7× 缺口内。
- **9qEeNN3K**（Sh=1.63, TO=115.9%, 仅 HIGH_TURNOVER+LOW_FITNESS 两个 fail）：证明「高 Sh 载体」可以干净到只差 TO 一项，但把 TO 从 116% 压到 70% 在同族构造中从未发生（ts_rank 归一化只改分布不改时间噪声，Law6）。
- **e76Po6eM**（Ret=0.0984 @ TO=2.2%，全场 Ret max，c=0.2117 也是全场 max）：极低 TO 下 Ret 可以很高，但 Sh=0.22、Y2=0.07。说明 Ret 与 Sh 在该数据集上由不同机制供给，简单组合会同时抬高 TO。

**结论性表述**：该数据集上 Sh 的唯一来源是高 TO 的价格/振幅噪声结构（TO≈115–125%），而用户门槛要求 Sh 来自低 TO 结构（TO≤70%）——两者被阶梯前沿（Law3）与 Fit 守恒律（Law2）双重锁死。继续在同构空间加 batch 只会复制 Pareto 前沿上的点；若要破局，只能来自任务 B 的交叉格（尤其是 news_×nws12_ 家族交叉与 subindustry 组内中性化），且需先有证据表明存在 c>0.30 的构造——历史上 440 行中一次也未出现。
