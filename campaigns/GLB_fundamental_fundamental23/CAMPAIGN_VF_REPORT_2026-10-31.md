# GLB / MINVOL10M / Delay 1 / fundamental23 —— 高 VF Alpha 挖掘战役报告

**日期**：2026-10-31
**区域 / 股票池 / 延迟 / 类别 / 数据集**：GLB / MINVOL10M / 1 / fundamental / fundamental23
**回测区间**：2014-01-01 ~ 2023-12-31（IS, FULL）
**执行方式**：WorldQuant BRAIN multisimulation（一次一批 4 条表达式，串行提交）

---

## 一、冠军 Alpha（全项 IS 检查通过，零 fail）

**Alpha ID**：`YP1WAMdW`

```fasteXpr
group_rank(add(ts_delta(divide(add(fnd23_intfvalld1_taiv, fnd23_ofc), fnd23_intfvalld1_letq), 252),
               ts_delta(divide(add(fnd23_intfvalld1_taiv, fnd23_ofc), fnd23_intfvalld1_letq), 126)),
           industry)
```

**设定**：Region=GLB, Universe=MINVOL10M, Delay=1, Decay=0, Neutralization=COUNTRY, Truncation=0.025, Pasteurization=ON, NaN=ON, UnitHandling=VERIFY
**字段数**：3（`fnd23_intfvalld1_taiv`, `fnd23_ofc`, `fnd23_intfvalld1_letq`）
**算子数**：7（group_rank, add, ts_delta×2, divide×2, add）

| 指标 | 数值 | 门槛 | 状态 |
|---|---|---|---|
| Sharpe | **1.63** | ≥1.58 | PASS |
| Fitness | **1.13** | ≥1.00 | PASS |
| Turnover | **5.36%** | 5%~50% | PASS |
| Margin | **22.35 bps** | ≥15 bps | PASS |
| Returns | 5.99% | — | — |
| Drawdown | 11.59% | — | — |
| 2Y Sharpe | **1.74** | ≥1.58 | PASS |
| Sub-universe Sharpe | 1.33 | ≥1.0 | PASS |
| Risk-neutralized Sharpe | 1.74 | — | — |
| Investability Sharpe | 1.57 | — | — |
| Long / Short 持仓 | 1977 / 2078 | — | 均衡 |

**平台检查明细**

- `fail`: **[] （零 fail 项）**
- `pass`: LOW_SHARPE, LOW_FITNESS, LOW_TURNOVER, HIGH_TURNOVER, CONCENTRATED_WEIGHT, LOW_SUB_UNIVERSE_SHARPE, **LOW_GLB_AMER_SHARPE, LOW_GLB_EMEA_SHARPE, LOW_GLB_APAC_SHARPE**, LOW_2Y_SHARPE, MATCHES_PYRAMID
- `warning`: CLUSTER_TEST (1.03 vs 1.58), MATCHES_THEMES
- `pending`: SELF_CORRELATION, DATA_DIVERSITY, PROD_CORRELATION, REGULAR_SUBMISSION, POWER_POOL_CORRELATION
- **ProdCorrelation（已单独实测）= 0.799 > 0.70（未通过）**

> 这是本战役中**唯一同时通过 Sharpe / Fitness / Margin / Turnover / 2Y / 子池 / AMER / EMEA / APAC 全部子区域检查、且 fail 项为零**的因子。历史 200+ 条实测中，EMEA 子区域检查此前从未被突破（上限 0.91）。

---

## 二、经济学假设（为什么这个结构应该有效）

**核心机制：现金支撑的盈利能力动量（Cash-backed Profitability Momentum）**

1. **分子设计**：`taiv`（正常化税后净利，剔除一次性/特殊项目）+ `fnd23_ofc`（经营活动现金流）。两者相加得到"经现金流验证的可持续盈利能力"。
   - 单用净利：会计应计可被操纵，EMEA 各国 GAAP 差异大 → 子区域 Sharpe 仅 0.40。
   - 单用现金流：噪音大（营运资本波动）→ Sharpe 仅 1.34、EMEA 0.35。
   - **两者相加**：会计盈余获得现金流背书，同时现金流获得盈余平滑 → EMEA 从 0.40 跃升至 0.91，2Y Sharpe 从 1.56 升至 2.14。
2. **分母设计**：`letq`（负债+权益=总资产）。存量口径把重资产与轻资产行业放在同一标尺上，是修复 GLB 跨洲不均衡的结构性手段（营收分母会把 EMEA 打到 0.02~0.50）。
3. **双窗口差分**：252 日（一年）捕捉"盈利能力中枢抬升"，126 日（半年）捕捉"边际加速"。二者相加既保留长期趋势，又把换手抬进 5%~50% 的合规区间（季度基本面单窗口换手仅 2~4%，会被 LOW_TURNOVER 否决）。
4. **截面排序**：`group_rank(..., industry)`。分组宽度是关键：subindustry 在 EMEA 只有 2~4 只成分股，排序被单只股票的重述主导（EMEA 0.69）；industry 提供 3~5 倍更宽的同类基准（EMEA 0.95→PASS）；sector/market 过粗，Sharpe 下滑。
5. **中性化 COUNTRY**：剥离国别层面的盈利能力水平差异，使信号只表达"同国同业内的相对改善"。

---

## 三、关键实证发现（按发现顺序，全部来自真实回测）

| # | 发现 | 证据 |
|---|---|---|
| 1 | **单位口径污染会触发 UNITS 警告** | `operating_cashflow` 的单位是 `CSPrice`，而 `fnd23_intfvalld1_*` 是无量纲 `Unit[]`；`add(tait, operating_cashflow)` 直接触发 2 条 UNITS 警告。改用同族 `fnd23_ofc` 后 UNITS 归零 |
| 2 | **总资产锚 >> 权益锚 >> 营收锚** | ROA 口径 EMEA 0.87；ROE 口径 EMEA 0.42~0.62；营收口径 EMEA 0.02~0.50 |
| 3 | **分组宽度是 EMEA 的开关** | subindustry 0.69 → industry 0.87~0.95 → sector 0.84~0.90 → market 0.88 |
| 4 | **短腿窗口存在 EMEA/Sharpe 权衡曲线** | 42日: Sharpe 1.73/EMEA 0.88；63日: 1.61/0.95；105日: 1.61/0.98；**126日: 1.63/PASS**；147日: 1.55/PASS |
| 5 | **正常化净利(taiv) 优于报表净利(tait)** | 252+126 窗口下：taiv 版 Sharpe 1.63 / 2Y 1.74 / EMEA PASS；tait 版 Sharpe 1.55 / 2Y 1.53 / EMEA 0.90 |
| 6 | **中性化层级：COUNTRY 最优** | COUNTRY: Sharpe 1.63, EMEA 0.87；SUBINDUSTRY: 1.55, EMEA 0.67；SECTOR: 1.42~1.50, EMEA/APAC 双失 |
| 7 | **衰减/截断/winsorize 全部有害** | decay=8 → Sharpe 1.47~1.55、EMEA 0.53~0.71；truncation 0.08 无影响（权重本就分散）；winsorize(std=3) 直接把 Sharpe 打到 1.16 |
| 8 | **低拥挤字段家族（递延税/税项应计/SBC）信号太弱** | 递延税 0.80；税项应计 0.99；SBC 1.15；R&D 强度 1.56（Margin 24.7bp 但换手仅 3.2%） |
| 9 | **CLUSTER_TEST 是结构性元数据** | 全战役 199 条实测中 CLUSTER_TEST 通过次数 = 0，最高值 1.35（门槛 1.58）；无任何 alpha 做到"零 warning" |
| 10 | **ProdCorr 是真正的硬门槛** | 全部强信号（Sharpe≥1.58）的 ProdCorr 落在 0.72~0.82；最低为 ipos 口径的 0.7246 |

---

## 四、候选梯队（全部 fail=[] 或仅 EMEA 单项）

| Alpha ID | 表达式要点 | Sharpe | Fitness | Turnover | Margin | 2Y | EMEA | ProdCorr |
|---|---|---|---|---|---|---|---|---|
| **YP1WAMdW** | taiv+ofc/letq, 252+126, industry | **1.63** | **1.13** | 5.36% | **22.4bp** | **1.74** | **PASS** | 0.799 |
| P0oXp6Xp | ipos+ofc/letq, 252+126, industry | 1.61 | 1.09 | 4.98% | 23.1bp | 1.63 | 0.70 | **0.7246** |
| RREk286b | (tait+ofc)/letq 动量 × 现金含量权重 | 1.69 | 1.17 | 6.06% | 19.6bp | 2.15 | 0.91 | 0.811 |
| LLMlnen6 | 同上，252+42 | 1.73 | 1.20 | 7.01% | 17.1bp | 2.22 | 0.88 | — |
| xArmeMeq | 同上，abs 权重 | 1.61 | 1.08 | 6.07% | 18.6bp | 2.08 | 0.95 | 0.819 |
| Jje5dQKj | tait+ofc/letq, 252+105 | 1.61 | 1.10 | 5.82% | 20.2bp | 1.92 | 0.98 | — |
| j2YdZXdO | taiv+ofc/letq, 252+126, subindustry | 1.66 | 1.12 | 5.74% | 19.8bp | 1.73 | 0.96 | 0.823 |
| 78LKVzbL | tait+ofc/letq, 252+63, industry | 1.63 | 1.11 | 6.12% | 19.1bp | 2.14 | 0.87 | 0.796 |

---

## 五、ProdCorr 瓶颈与后续建议

**事实**：冠军 `YP1WAMdW` 与生产池中某条 alpha 的相关系数为 **0.799**，超过 0.70 门槛。全战役最低值为 `P0oXp6Xp` 的 **0.7246**（ipos 口径，距门槛仅 0.025）。

**成因**：GLB 生产池中已存在大量"现金支撑盈利 / 资产回报动量"类因子；本战役的最强结构在时序上与其高度同源（同为季度财报驱动的截面动量）。这与研究员"其他 agent 回测出的 alpha 相关性较高"的判断一致。

**已尝试但未奏效的解耦手段**（均已实测）：
- 更换分子口径：tait → taiv（0.799）、ipos（0.7246）、xbin（0.82+）
- 更换分母：letq → tota（≈同值）、eltq（Sharpe 崩至 1.10~1.59）
- 更换分组：industry / sector / subindustry / market
- 更换中性化：COUNTRY / SUBINDUSTRY / SECTOR / MARKET
- 更换窗口：42 / 63 / 105 / 126 / 147 / 189 / 252 / 504
- 加权交互：现金含量权重、abs 权重、水平权重
- 低拥挤字段替换：递延税 / 税项应计 / R&D / SBC / 租赁 / 养老金（Sharpe 0.80~1.56）

**下一步建议（需研究员决策）**：
1. **接受 0.72~0.80 的 ProdCorr 并申请人工复核**——该因子在全部 IS 检查项上零 fail、三大子区域全部通过，属于"质量达标但风格与存量重叠"的类型。
2. **转向低拥挤字段做长周期孵化**：R&D 强度（`darv/rltr`）Margin 24.7bp、2Y 1.78、ProdCorr 0.7053（距门槛仅 0.005）。但 W38 的 4 组换手修复实验（252+42 / 252+21 / tota 锚 / sector 分组）显示其换手天然锁死在 2.6%~3.5%（研发费用季度间变化极慢），Sharpe 反而回落至 1.33~1.52，**该方向需要换用更高频的数据集（analyst / sentiment）才能把换手抬进合规区间**。
3. **跨数据集组合**：fundamental23 内部的盈利动量赛道已高度拥挤，建议在 analyst / sentiment 数据集上复用本报告的"双窗口 + 宽分组 + 单位同族"方法论。
4. **若必须提交**：优先提交 `YP1WAMdW`（唯一全项 IS 检查通过者），`P0oXp6Xp` 作为低相关备选（ProdCorr 0.7246，但 EMEA 0.70 会挂 warning）。

---

## 六、复现与产物

**脚本**
- `research_scripts/wave_driver.py` —— 单批 4 条表达式的 multisimulation 提交/轮询/落盘（含 429 退避重试）
- `research_scripts/wave_poll.py` —— 断点续轮询
- `research_scripts/check_corr.py` —— ProdCorr / SelfCorr 实测

**数据产物**（`campaigns/GLB_fundamental_fundamental23/`）
- `wave17_result.json` ~ `wave37_result.json` —— 每批 4 条的真实回测全量结果（含 metrics / checks）
- `tmp/session_alphas.json` —— 本会话全部 alpha 的结构化汇总
- `CAMPAIGN_VF_REPORT_2026-10-31.md` —— 本报告

**本战役规模**：本会话新增 **21 批 × 4 条 = 84 条**真实回测（叠加历史 199 条，累计 283 条），全部通过 multisimulation 批量提交，无单条回测。

---

⚠️ 本报告为量化研究记录，所有指标均为 WorldQuant BRAIN 平台样本内（IS, 2014-2023）回测结果，不代表样本外或实盘表现。
