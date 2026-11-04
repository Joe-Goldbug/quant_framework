# AEGIS · fundamental17 · S4 换核设计简报（子 Agent 必读）

**战役参数**：USA / TOP1000 / delay=1 / dataset=fundamental17 / category=`fundamental`
**提交纪律**：HARD_SUBMISSION_RULE —— **全程禁止调用任何 Alpha 提交接口**。回测 ≠ 提交；达标 alpha 仅本地标记，交研究员人工终审。
**日期**：2026-10-28

---

## 0. 你要交付什么

你是 S4 换核批次的设计者之一。交付 **3~4 条候选表达式**，每条含：
表达式 / 字段 / 经济机制 / 对手盘 / 因果归因 / 自检表。

**只交付设计，不要写代码、不要跑回测、不要提交任何东西。**
输出写成 JSON 文件（路径见派发指令），UTF-8 无 BOM。

---

## 1. 前情：S1/S2/S3 已全部失败（**这些结构严禁重提**）

| 批次 | 结构 | 最高 Sh | 结论 |
|---|---|---|---|
| S1（8 槽） | 一阶逐期差分（本期水平 − 上期水平）及其平滑 | **0.44** | PRUNED |
| S2（8 槽） | 水平量行业相对价差（EUR 冠军移植式） | **0.89** | PRUNED（方向对，量级差） |
| S3（16 次，8 式×2 档） | 同 S2 骨架，8 条第二腿轮换 | **1.11** | PRUNED |

**S1 法医结论**：一阶逐期差分 = 噪声。季报驱动数据做逐期差分，把披露噪声/季节性/口径切换当成了信息。

**S3 结论**：EUR 冠军骨架移植到 USA 后天花板 Sh≈1.11，**不是设置档的问题**（设置档只贡献 +0.29）。

---

## 2. ★ 核心约束：门禁算术指出瓶颈在 **年化收益 Ret**，不在 Sharpe

平台门禁：Sh ≥ 1.58、Fit ≥ 1.00、Margin ≥ 10bp、TO ∈ [1%, 70%]、2Y ≥ 1.58。

```
Mgn_bps = 20 × Ret / TO ≥ 10          ⇒  Ret / TO ≥ 0.5
Fit     = Sh × √( Ret / max(TO, 0.125) ) ≥ 1
```

在 TO ∈ [2%, 12.5%] 区间联立两式（取 Sh = 1.58）：

| TO | Fit≥1 要求的 Ret | Margin≥10bp 要求的 Ret | **同时满足** |
|---|---|---|---|
| 2% | 4.0% | 5.0% | **Ret ≥ 5.0%** |
| 6% | 4.6% | 3.0% | **Ret ≥ 4.6%** |
| 12.5% | 6.3% | 6.3% | **Ret ≥ 6.3%** |

⇒ **年化收益必须做到 ~5%**（EUR 冠军做到 6.76%；USA 移植式只有 2.4~3.8%）。
⇒ **你设计结构的唯一首要目标：把年化收益从 ~3% 抬到 ~5%。**
⇒ 调设置档只能贡献 +0.3 Sharpe / +25bp Margin，**不能替代结构挣 Ret**。

### 2.1 怎么抬 Ret
Ret ≈ 截面预测力 × 信号离散度 × 持仓期。三个抓手：
1. **更细的截面分位化**：`group_rank` 把连续比值压成分位，损失了尾部信息。
   `winsorize(x, std=3)` 保留连续幅度又切掉离群，通常比 group_rank 保留更多幅度信息。
2. **比值 vs 差值**：比值自带尺度归一；差值在跨行业比较时会被规模污染。
3. **更长的持仓期**（decay=0 已在用）：换手已压到 2%，Ret 靠累积。

---

## 3. 硬红线（违反即熔断）

1. **最外层必须零均值**：`zscore` / `ts_zscore` / `group_zscore` / `ts_delta` / `ts_av_diff` / `ts_decay_linear` / `ts_mean`。
   **最外层禁用** `group_rank` / `rank`（输出恒 [0,1] ⇒ 组合单边 ⇒ Ret 是 Beta 幻觉）。
2. **字段数 2 ≤ n ≤ 3；算子数 ≤ 4**（Phase 0 硬上限；引擎上限 11，但本战役守简约律）。
3. **时间窗口只用** {3, 5, 10, 20, 60, 120, 252}；`ts_backfill` 额外允许 250。
4. **零外部量价字段**：禁 `close / open / high / low / vwap / volume / cap / returns / adv20 / sharesout`。
5. **零内嵌量价字段**：禁 `fnd17_nprice / mktcap / ev_cur / pr1dayprc / priceavg* / price2bk* / peexclxor / spfcr / ebitda2ev* / awcappspr / qwcappspr / yield / vol*`。
6. **禁用算子**：`group_neutralize`（引擎黑名单）· `bucket` · `trade_when` · `hump` · `signed_power` · `quantile` · `ts_arg_max` · `ts_arg_min` · `reverse` · `neg` · `ts_neutralize`。
7. **禁用** `add(rank(A), rank(B))`（引擎物理拦截）· `subtract(x, 0.5)`（比率字段天然正偏置）。
8. **双有符号裸乘禁止**：`multiply` 的权重腿必须严格恒正（如 `rank(x)`、`add(rank(x), 0.01)`）。
9. **反拥挤**：数据集平台 alphaCount=781、userCount=380（全库最拥挤的基本面集）。
   优先 ac=0~2 字段；**严禁**用 ac≥5 的热门字段做裸水平值。
10. **单位一致性**：`subtract` 两腿必须同量纲族（金额↔金额、每股↔每股、%↔%、比率↔比率）。

---

## 4. ★ 取材池：37 个**冷字段**（ac=0 且未被 S1/S2/S3 触碰，覆盖率 ≥0.80）

**你只能从这个池子里取字段**（保证反拥挤 + 与已烧结构不撞）：

```
资产/资本   fnd17_cainmtt(净利润TTM,归母) ac=0 cov=.929   fnd17_qtachg(总资产同比%) ac=0 cov=.908
            fnd17_atotce(普通股权益,年) ac=1 cov=.937      fnd17_atotse(股东权益,年) ac=1 cov=.937
            fnd17_atq(总资产,季) ac=1 cov=.937             fnd17_qtotce(普通股权益,季) ac=2 cov=.937
            fnd17_atanbvdolr(有形账面价值$,年) ac=1 .937   fnd17_qtanbvdolr(有形账面价值$,季) ac=1 .937
            fnd17_qltd2cap(长债/总资本,季) ac=1 .864       fnd17_bvtrendgr(每股账面价值5年CAGR) ac=1 .728
负债/杠杆   fnd17_qtotd(总债务,季) ac=0 cov=.936           fnd17_spdtlq(长债/股,季) ac=0 .867
            fnd17_qcurliab(流动负债,季) ac=0 .745           fnd17_netdebt_a(净债务,年) ac=1 .937
            fnd17_lta(总负债,年) ac=1 .937                  fnd17_qtotd2eq(总债务/股东权益,季) ac=1 .898
            fnd17_debtcap_i(债务/资本化,中报) ac=1 .868      fnd17_atotd(总债务,年) ac=2 .937
            fnd17_atotltd(长期债务,年) ac=2 .937            fnd17_qtotd2eq2(总债务/权益,去年同季) ac=2 .872
            fnd17_2qe2dtlq(长债/权益,去年同季) ac=2 .872    fnd17_qltd2ast(长债/总资产,季) ac=2 .867
收入/销售   fnd17_qrev(季度收入) ac=0 .937                fnd17_qrevps(季度每股收入) ac=0 .937
            fnd17_ttmrev(TTM收入,百万) ac=0 .929           fnd17_ttmrevchg(TTM收入同比%) ac=0 .850
            fnd17_revchngyri(收入变动%YTD) ac=0 .964       fnd17_ttmrevpere(人均收入TTM) ac=0 .820
现金创造    fnd17_rhsfcq(季度每股现金流,年化) ac=0 .891   fnd17_anrhsfcq(季度每股现金流) ac=0 .891
            fnd17_acapspps(年度每股资本开支) ac=0 .896     fnd17_qcapspps(季度每股资本开支) ac=0 .873
利润率      fnd17_tcpngmtpq(季度税前利润率) ac=0 .902
回报率      fnd17_tcpaormtp(ROA,前TTM) ac=0 .864         fnd17_ptmroepct(ROE,前TTM) ac=0 .830
增长        fnd17_nichngin(净利润环比%) ac=0 .931          fnd17_nichngyri(净利润变动%YTD) ac=0 .965
折旧摊销    fnd17_adeprescfz(累计折旧,年) ac=0 .847
股本        fnd17_ttmdivshr(TTM每股股利) ac=0 .929         fnd17_spdq(季度股利) ac=0 .927
其他        fnd17_qebit(季度息税前利润) ac=0 .937          fnd17_tbeq(季度税前利润) ac=0 .937
            fnd17_aebitd(年EBITDA) ac=0 .937               fnd17_aebitd2(上年EBITDA) ac=0 .933
            fnd17_ttmebitd(TTM EBITDA) ac=0 .927           fnd17_inmtt(TTM税后净利) ac=0 .929
            fnd17_aniacnorm(年规范化归母净利) ac=0 .936    fnd17_abepsxclxo(年基本EPS除额外项) ac=0 .936
            fnd17_qepsinclxo(季度含额外项EPS) ac=0 .937   fnd17_ptmepsincx(EPS含额外项,前TTM) ac=0 .909
            fnd17_ttmastturn(资产周转率TTM) ac=0 .840      fnd17_ttmtaxpd(TTM实缴税) ac=0 .876
            fnd17_beta_down(下行beta) ac=0 .842            fnd17_public_float_shares(自由流通股,百万) ac=0 .937
            fnd17_shares_outstanding_current(在册股本,百万) ac=0 .939
```

> ⚠️ `fnd17_aebitd` **当分母是错误量纲**（规模因子≠信号，EUR 侧实测 Sh 0.33~0.41 且 2Y 为负）。可当**分子**用。

### 4.1 已烧字段对（**严禁重复**）
S1/S2/S3 共烧掉 24 个骨架，涉及这些字段对：
```
(fcfmtt,atmtt) (fcfmtt,arev) (fcfmtt,tcpaormtt) (fcfmtt,grosmgn5yr) (fcfmtt,margin5yr) (fcfmtt,ttmopmgn)
(tcpaormtt,aroa5yavg) (tcpaormtt,qroipct) (tcpaormtt,tcpaormtp) (ghcspemtt,ttmnichg)
(ttmnichg,nichngyr) (ttmnichg,nichngin) (ttmnichg,arevchg) (ttmnichg,ttmrevchg) (nichngyr,arevchg)
(nichngyr,revchngyr) (apayratio,apayratio2) (cftrendgr,revtrendgr) (ttmintcov,ptmintcov)
(qtotce,qtotce2) (qtotd2eq,qtotd2eq2) (ghcspemtt,ttmnichg) (ttmrev,atmtt) (qtotce,atmtt)
```
（成对判据：你的两个字段若同时出现在上面任一条 ⇒ 换组合）

---

## 5. 已验证有效的结构范式（可迁移，但 USA 须重测）

- **水平量的行业内相对价差**（唯一被 EUR 侧验证的路径）：
  ```
  subtract(group_rank(divide(ts_backfill(A,250), ts_backfill(B,250)), sector),
           multiply(0.5, group_rank(ts_backfill(C,250), sector)))
  ```
  外层 subtract 天然零均值。EUR 上 Sh 2.14 / Fit 1.57 / Ret 6.76% / TO 1.8% / 2Y 1.91 / SubU 1.22。
  **USA/TOP1000 上同一骨架只到 Sh 1.11** ⇒ 骨架没错，**腿错了**（分母换 atmtt 反而略优，第二腿换 ROA/毛利率/净利率中枢都更差）。
- **第二腿是「盈利质量基线」时最有效**：EUR 用营业利润率（ttmopmgn）最优；换 5 年毛利率中枢、5 年净利率中枢、ROA 都更差。
  ⇒ 你若做价差腿，第二腿优先找**当期盈利水平**而非**长期中枢**。

---

## 6. 交付格式

对每条候选交付一段 JSON：

```json
{
  "expression": "<你的表达式>",
  "fields": ["fnd17_xxx", "fnd17_yyy"],
  "mechanism": "一句话物理机制（≤60字）",
  "counterparty": "具体到行为模式的对手盘（≤50字），不得写'市场'",
  "optimize_reason": "≥200字深度因果归因：①针对什么物理短板（尤其：如何把年化收益从~3%抬到~5%）②数学变形如何增强对真实经济学现象的捕捉 ③为什么这个结构不会单边/不会伪因果",
  "treatment_tag": "one of: ts_mean_smooth | group_zscore_neutral | ts_backfill_staleness | winsorize_tail | rank_weight_interact | none",
  "self_check": {
    "operator_count": 3,
    "field_count": 2,
    "window_used": 60,
    "top_level_zero_mean": true,
    "unit_consistent": "说明：两个被减字段为何量纲可比",
    "no_double_signed_multiply": true,
    "no_pv_contamination": true,
    "fields_exist_in_dossier": true,
    "field_acs": [0, 4],
    "field_covs": [0.86, 0.91],
    "why_not_already_used": "反拥挤论证：为何这组字段+结构的 ac 组合在本账户 USA/d1 上未被使用"
  }
}
```

文件末尾附一行：`SLICES_SUMMARY: <交付几条>`。

---

## 7. 自检（**必须本地实跑，不得只靠目测**）

战役预检器在 `campaigns/aegis_fnd17/stage3_preflight.py`，用法：

```python
import sys; sys.path.insert(0, r"<战役目录>")
import stage3_preflight as P
meta = P.load_meta()
r = P.preflight(expr, optimize_reason, counterparty, meta, meta, phase0=False, op_cap_override=4)
assert r["ok"], r["issues"]
```

并用 `P.skeleton_and_fingerprint([...])` 确认：
- 同批骨架唯一（单批同骨架 ≤2）
- 跨批指纹库历史 < 4 次

**交付前必须 8/8 全部 `r["ok"]`**，任何 `issues` 非空都要改写到你满意为止。
