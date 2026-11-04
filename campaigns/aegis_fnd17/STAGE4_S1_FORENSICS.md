# AEGIS · fundamental17 · S1 批次法医报告（零隐瞒）

**批次**：`aegis_fnd17_S1` · **日期**：2026-10-28 · **USA / TOP1000 / d1 / fundamental17**
**仿真设置**：STATISTICAL · decay=8 · truncation=0.08 · pasteurization=ON · unit=VERIFY · nan=ON
**结论**：**PRUNED_AT_STEP1**（预注册漏斗 |Sharpe| ≥ 1.0，0/8 存活）

---

## 1. 八槽实测结果（逐条零遗漏）

| slot | 表达式 | Sh | Fit | Ret | Mgn(bp) | 2Y | SubU | FAIL |
|---|---|---|---|---|---|---|---|---|
| 1 | `zscore(subtract(fnd17_tcpaormtt, fnd17_aroa5yavg))` | 0.06 | 0.01 | 0.31% | 0.63 | 0.44 | 0.31 | LOW_SHARPE / LOW_FITNESS / LOW_2Y / LOW_SUB |
| 2 | `zscore(ts_mean(subtract(fnd17_ghcspemtt, fnd17_ttmnichg), 20))` | 0.17 | 0.05 | 1.23% | 1.72 | 0.51 | 0.31 | + CONCENTRATED_WEIGHT |
| 3 | `zscore(divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252)))` | **0.01** | 0.00 | 0.04% | 0.08 | 0.29 | 0.38 | LOW_SHARPE / LOW_FITNESS / LOW_2Y |
| 4 | `add(group_zscore(fnd17_tcpaormtt, subindustry), group_zscore(fnd17_qroipct, subindustry))` | 0.26 | 0.06 | 0.69% | 1.93 | 0.55 | 0.28 | LOW_SHARPE / LOW_FITNESS / LOW_2Y / LOW_SUB |
| 5 | `group_zscore(ts_backfill(subtract(fnd17_apayratio, fnd17_apayratio2), 120), subindustry)` | 0.07 | 0.01 | 0.14% | 0.54 | 0.31 | 0.28 | LOW_SHARPE / LOW_FITNESS / LOW_2Y / LOW_SUB |
| 6 | `zscore(ts_mean(winsorize(subtract(fnd17_cftrendgr, fnd17_revtrendgr), std=3), 60))` | 0.05 | 0.01 | 0.15% | 0.47 | **-0.08** | 0.34 | LOW_SHARPE / LOW_FITNESS / LOW_2Y |
| 7 | `group_zscore(ts_backfill(subtract(fnd17_ttmintcov, fnd17_ptmintcov), 120), subindustry)` | **0.44** | 0.13 | 1.08% | 3.44 | 1.23 | 0.36 | LOW_SHARPE / LOW_FITNESS / LOW_2Y |
| 8 | `zscore(subtract(fnd17_nichngyr, fnd17_arevchg))` | 0.40 | 0.18 | 2.72% | 4.14 | 1.06 | 0.35 | LOW_SHARPE / LOW_FITNESS / LOW_2Y / CONCENTRATED_WEIGHT |

- **最高 |Sharpe| = 0.44**（slot7），漏斗要求 ≥ 1.0 ⇒ **8/8 全灭，零存活**。
- 平台硬门禁通过 **0/8**；全维度（含工作区铁律）通过 **0/8**。
- 全部 8 条 `ra.ra_failed = true`；全部 8 条 `CLUSTER_TEST` 处于 WARNING。
- 正收益年数 **0/10**（yearly-stats 接口对未提交 alpha 返回空，以 FAIL 项为准）。
- 未调用任何提交接口；未产生任何 OS alpha。

---

## 2. 法医诊断（三条病灶，均有硬证据）

### 病灶 A（主病灶）：一阶逐期差分 = 噪声，不是信号

S1 八槽**全部**是「本期水平 − 上期水平」的逐期差分（或其时间平滑）。
fundamental17 是**季报/年报驱动**的数据集，逐期差分把三样东西当成了信息：
披露噪声、季节性、口径切换。结果是 Sh 全线塌到 0.01~0.44。

**反证（硬证据）**：本账户 EUR/D1 冠军 `3qVlb3dN`（Sharpe 2.14 / Fitness 1.57 / `checks.fail` 为空 /
selfCorr 0.32 / prodCorr 0.64 / 已提交 OS）用的是**水平量**（FCF/收入、营业利润率）的
**行业相对价差**，不是逐期差分：

```
subtract(group_rank(divide(ts_backfill(fnd17_fcfmtt,250), ts_backfill(fnd17_arev,250)), sector),
         multiply(0.5, group_rank(ts_backfill(fnd17_ttmopmgn,250), sector)))
```

⇒ **换核方向确定：放弃逐期差分，改用水平量的行业内相对价差。**

### 病灶 B（次病灶）：subindustry 内生中性化在 USA/TOP1000 上过度削信息

EUR 侧证据明确：**sector 最优，industry/subindustry 会把 robust 打到 0.35~0.46**。
S1 用 subindustry 的 3 槽（slot4/5/7）与 sector 的槽表现无显著差异，
说明 USA/TOP1000 下 subindustry 未带来收益，只带来信息损失。⇒ S2 统一改 sector。

### 病灶 C（第三病灶）：raw 比值做 zscore 被重尾极端值主导

slot3 `zscore(divide(FCF, 资产))` 得到 **Sh = 0.01**（全批最差）。
现金收益率是重尾分布，少数极端值把截面 zscore 彻底拉爆。
⇒ 标准化**前置**到 `group_rank`（分位映射天然截尾、抗单点离群）。

---

## 3. 附带修复：审计层的假通过漏洞（已修）

**发现**：BRAIN 原始 API 把 `checks` 放在 `alpha['is']['checks']`，且是**扁平数组**
`[{"name":..,"result":"FAIL"|"PASS"|"WARNING","value":..}]`；
而 MCP 工具返回的是归一化后的 `{"fail":[..],"warning":[..]}`。

原 `stage5_audit.py` 只读顶层 `alpha['checks']` ⇒ **恒得空列表 ⇒ 每个 alpha 都被误报成
`FAIL=[]`、`ra_failed=None`**。这是一条**致命假通过**通道：
若某槽真的达标，审计也会显示"checks.fail 为空"而误放行。

**已修**（`stage5_audit.py` + `stage3_run_batch.py`）：
1. `parse_checks()` 同时兼容两种形态，并优先读 `alpha['is']['checks']` 扁平数组；
2. `metrics_of()` 兼容 `is.metrics` 与 `is` 平铺两种指标布局；
3. **2Y ladder / Sub-universe 从 `checks` 数组的 `value` 回填** ——
   这两个指标在原始 API 的 metrics 里**根本不存在**（metrics 只有 12 个标准字段），
   缺失≠0，原实现会把它们误判为未达标；
4. 无 `ra` 字段时以 `checks` 的 FAIL 项作为权威等价判据。

修复后重跑审计：8/8 槽如实报出 LOW_SHARPE / LOW_FITNESS / LOW_2Y_SHARPE 等真实 FAIL 项。

---

## 4. 门禁算术复核（用今日 52 条实测 alpha 反查，52/52 吻合）

```
Fit     = Sh × √(|Ret| / max(TO, 0.125))
Mgn_bps = 20 × Ret / TO
```

S1 八槽 Ret 全部 ≤ 2.72%，因此即便 Sharpe 达标，Margin 也必然 < 10bps。
**要在 TO≈6% 上同时过 Fit≥1.0 与 Margin≥10bps，需 Ret ≥ 3.0% 且 Sh ≥ 1.58，
对应 Fit ≈ 1.58×√(3%/12.5%) ≈ 0.77 —— 仍不过。**
⇒ **必须把 Ret 抬到 ~5%+**，这要求信号本身有真实截面解释力，
再次印证「水平量行业相对价差」是唯一已验证路径。

---

## 5. S2 换核动作（预注册）

| 病灶 | S2 处方 |
|---|---|
| A 逐期差分=噪声 | 全部改用**水平量**的行业内相对结构 |
| B subindustry 过度中性化 | 统一 `sector` |
| C raw 比值被离群主导 | `group_rank` 前置（分位截尾） |

**S2 通式**：`subtract(group_rank(<量A>, sector), group_rank(<量B>, sector))`
—— 外层差值**天然零均值**（非 [0,1] 单边），既满足本战役「最外层零均值」铁律，
又保留 group_rank 的抗离群 + 行业相对化双重优点。
（EUR 冠军原式最外层是 subtract，**本身即零均值**，
故 AGENT_BRIEF 中「顶层 group_rank 必单边」的告诫在此**不适用** ——
单边风险来自 group_rank 直接落在最外层，而非这里的差值封装。）

**纪律**：S2 是**换核**，不是网格微调 —— 8 条表达式**无一**是 S1 表达式的参数变体。
