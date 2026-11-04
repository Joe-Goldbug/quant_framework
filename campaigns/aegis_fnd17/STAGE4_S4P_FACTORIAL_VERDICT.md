# AEGIS · fundamental17 · S4P 析因探针裁决（零隐瞒）

**批次**：`aegis_fnd17_S4P_FACTORIAL` · 8 槽 = 4 结构 × 2 设置档 · 2026-10-28
**纪律**：只回测，未触碰任何提交接口。

---

## 1. 预注册的两个假设 —— **双双被证伪**

### H1「保幅度归一化（winsorize+zscore）比 group_rank 分位化挣到更多 Ret」→ ❌ **证伪**

| 基础结构 | 设置档 | GRP（分位） | AMP（保幅度） | Δ |
|---|---|---|---|---|
| ASSET | STAT_D0 | Sh **1.07** / TO 6.65% / Ret 2.69% / Mgn 8.08bp | Sh 0.64 / TO 9.11% / Ret 2.80% / Mgn 6.14bp | ΔSh **−0.43** |
| ASSET | STAT_D8 | Sh **1.11** / TO 5.95% / Ret 2.85% / Mgn 9.59bp | Sh 0.60 / TO 8.53% / Ret 2.59% / Mgn 6.06bp | ΔSh **−0.51** |
| REV | STAT_D0 | Sh **0.80** / TO 6.64% / Ret 2.08% / Mgn 6.27bp | Sh **−0.17** / TO 16.30% / Ret −1.37% | ΔSh **−0.97** |
| REV | STAT_D8 | Sh **0.95** / TO 5.80% / Ret 2.38% / Mgn 8.20bp | Sh **−0.12** / TO 15.22% / Ret −1.01% | ΔSh **−1.07** |

主效应：**GRP 均值 Sh 0.98 / TO 6.26% / Ret 2.50% / Mgn 8.04bp**
vs **AMP 均值 Sh 0.24 / TO 12.29% / Ret 0.75% / Mgn 2.30bp**。

**为什么我的推理错了**：我以为 group_rank 丢掉「幅度信息」是 Ret 上不去的原因。
实测相反 —— 保幅度归一化让**换手翻倍（6.26%→12.29%）**，因为连续值里的噪声尾部天天换手，
而 group_rank 的分位化本身就是一种**天然的单调变换 + 抗噪截断**，
它丢掉的幅度被"换手纪律"补偿回来了。**EUR 冠军用 group_rank 不是缺陷，是优点。**

### H2「STATISTICAL + decay=0 + nan=OFF 是隐藏的第三格」→ ❌ **证伪**（且带一处诚实披露）

| 归一化 | 基础结构 | D0（decay0/nanOFF） | D8（decay8/nanON） | Δ |
|---|---|---|---|---|
| GRP | ASSET | Sh 1.07 / TO 6.65% / Mgn 8.08bp | Sh 1.11 / TO 5.95% / Mgn 9.59bp | ΔSh +0.04 / ΔMgn +1.51bp |
| GRP | REV | Sh 0.80 / TO 6.64% / Mgn 6.27bp | Sh 0.95 / TO 5.80% / Mgn 8.20bp | ΔSh +0.15 / ΔMgn +1.93bp |

主效应：STAT_D0 均值 Sh 0.58 / Mgn 4.70bp **vs** STAT_D8 均值 Sh 0.64 / Mgn 5.63bp
⇒ 战役档（decay8/nanON）**略优**，H2 不成立。

> ⚠️ **诚实披露**：本探针的 D0 与 D8 档**捆绑了两个变量**（decay 与 nanHandling 同时变），
> 因此 H2 的严格结论是「{decay0, nanOFF} 这个**组合**劣于 {decay8, nanON} 这个**组合**」，
> **不能**单独归因给 decay 或 nan 之一。要拆开必须逐格测（见 S4Q）。

---

## 2. ★ 探针的副产品比假设本身更有价值：**中性化才是换手与 Margin 的总开关**

把 S3（MARKET 档）与 S4P（STATISTICAL 档）并排：

| 设置档 | TO | Ret | Mgn | Sh |
|---|---|---|---|---|
| **MARKET** + decay=0 + nan=OFF | **2.06%** | **4.22%** | **41.09 bp** | 0.85 |
| **STATISTICAL** + decay=0 + nan=OFF | 6.65% | 2.69% | 8.08 bp | 1.07 |
| **STATISTICAL** + decay=8 + nan=ON | 5.95% | 2.85% | 9.59 bp | 1.11 |
| STATISTICAL + decay=8 + nan=ON（S3 EUR 档对照） | 6.02% | 2.25% | 7.8 bp（均值） | — |

⇒ **MARKET 中性化把换手从 6.65% 压到 2.06%（3.2×），把年化收益从 2.69% 抬到 4.22%（1.6×），
把 Margin 从 8.08bp 抬到 41.09bp（5.1×）** —— 而代价只有 Sharpe −0.22。

### 2.1 门禁算术重算：MARKET 档才是**更容易过门**的区间

```
Mgn_bps = 20·Ret/TO ≥ 10        （注意：这是本账户自设的房规，非平台门禁）
Fit     = Sh·√(Ret/max(TO,0.125)) ≥ 1        （平台硬门禁）
```

在 MARKET 档实测点（TO=2.06%, Ret=4.22%）反解所需 Sharpe：

| 设置档 | TO | Ret | Fit 公式 | Fit=1.0 所需 Sh | Margin 所需 Ret | 现状 Sh | 缺口 |
|---|---|---|---|---|---|---|---|
| MARKET decay0 | 2.06% | 4.22% | Sh×√(0.0422/0.125)=Sh×0.581 | **Sh ≥ 1.72** | Ret ≥ 1.03%（已 4.22% ✅） | 0.85 | **−0.87** |
| MARKET decay0（若 Ret 抬到 6.76%） | 2.06% | 6.76% | Sh×0.735 | Sh ≥ 1.36 | ✅ | 0.85 | −0.51 |
| STATISTICAL decay8 | 5.95% | 2.85% | Sh×0.478 | **Sh ≥ 2.09** | Ret ≥ 2.98%（差 0.13pp ❌） | 1.11 | **−0.98** |

⇒ **对本战役当前信号强度（Sh≈1.1）而言，MARKET 档是唯一有可能过的设置区间**：
它把 Fit 门槛从 Sh≥2.09 降到 Sh≥1.72，且 Margin 有 4 倍余量。
⇒ **下一步的正确方向：把结构做对 + 回到 MARKET 档，而不是继续在 STATISTICAL 里调参。**

### 2.2 目标画像（EUR 冠军口径）
**Sh ≥ 1.58 且 Ret ≥ 4.66% 且 TO ≤ 2.1%**（此时 Fit=1.00、Mgn≈45bp、TO 达标）
—— EUR 冠军 `3qVlb3dN` 正是这个画像（Sh 2.14 / Ret 6.76% / TO 1.80% / Mgn 74.96bp / 2Y 1.91 / SubU 1.22）。
⇒ **USA 移植失败不是设置档问题，是结构在美国截面上的解释力不足**（同骨架 USA 只到 Sh 0.85）。

---

## 3. 未测格清单（S4Q 立即补测，10 次仿真）

`{MARKET, STATISTICAL} × {decay 0, 8} × {nan OFF, ON}` 全交叉 16 格，
已测 6 格（S3 的 2 格 + S4P 的 4 格），**未测 10 格**：
MKT/d8/OFF、MKT/d0/ON、MKT/d8/ON、STAT/d0/ON、STAT/d8/OFF（× ASSET 与 REV 两条结构）。

**目的**：① 干净拆开 decay 与 nan 两个被捆绑的变量；
② 找到「让 Sharpe 增益与低换手/高收益共存」的真实格；
③ 为下一步换核结构选定设置档基线。

---

## 4. 本批最佳（不达标，不提交）

`gJepEE7g`（= `QPvLv6V5`，S4P slot2，GRP/ASSET/STAT_D8）
Sh **1.11** / Fit 0.53 / TO 5.95% / Ret 2.85% / Mgn 9.59bp / 2Y 1.49 / SubU 0.84 / `checks.fail` 空（4 项 warning）

仍是 **USA/TOP1000/d1 的 fnd17 天花板**，与 S3 最佳持平，**未过 Step-1 漏斗**（需 Sh≥1.58）。
