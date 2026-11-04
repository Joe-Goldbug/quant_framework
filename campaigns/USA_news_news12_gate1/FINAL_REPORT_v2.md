# Gate 1 终局研报 v2 — USA/TOP1000/delay1/news12 注意力稀缺族（336 槽完备闭合）

**战役代号**：USA_news_news12_gate1 · **执行期**：2026-10-24 ~ 10-25 · **规模**：**42 批 × 8 槽 = 336 槽**（v1 为 21 批 168 槽；本版延伸 21 批 168 槽）
**mandate**：在最佳候选 N1eGk79E（close-vwap×回填分母，Sh 1.63）基础上修 4 FAIL（LOW_FITNESS/HIGH_TURNOVER/CONCENTRATED_WEIGHT/LOW_2Y_SHARPE）+ 零任何警告；2≤字段≤3；op≤10；仅 multi_create_simulate 每批 8 条；**严禁提交**。

---

## 0. 执行摘要

- **336 槽零候选达到 `ra.ra_failed==false`**（唯一权威判据；实读复核：336 行中 16 行为两批连坐取消的幻影行（无任何指标），320 个真实评估行 **0 个** ra_failed==false）。距达标最近者仅剩 2 类硬不达标 + 2 类警告（§8.1）。
- **fail 桶不可信判据的实证加强**：320 个真实行中 22 行 fail 桶为空但 ra_failed=true（v1 为 10/152）——判定必须读 `ra.ra_failed`，读 checks.fail 会虚报合格。
- **两条独立探索线全部实证闭合**：
  - **price-context 线**（gate7_W/Y/Z → B6'，12 批 96 槽）：参照点轴/归一器轴/壳轴/交互轴四大轴主要交叉格 100% 覆盖，R3 判读规则触发（§2.3）；
  - **Wave10 振幅+新杠杆线**（A-I，72 槽）：decay/ts_rank/Fit 下限/硬门/宇宙/中性化/合流七杠杆全部实测，零逃逸点（§6）。
- **settings 消融轴全闭合**：INDUSTRY（基线）/MARKET（无差异）/STATISTICAL（8/8 净负）/SUBINDUSTRY（冠军 Sh 1.61→1.48，CW 依旧）× TOP500（Sh 1.10）/TOP3000（Sh 1.49 且 TO 141%）——expression 轴 + settings 轴均无剩余合法格。
- **零警告仍不可达但缺口收窄**：CLUSTER_TEST 限 1.58（warning 级），全场 320 个评估行 **320/320 全部带 CLUSTER_TEST 警告**；族记录由 v1 的 1.47 抬至 **1.54**（mLYNEWjW，新鲜门族，缺口 0.04）。
- **两门半数学死局（§5）**：Fit 轴（Fit≥1 需 Sh≥2.83 vs 家族天花板 1.68）+ Margin 恒等式（Sh≥1.58 分支 R/TO≤0.066，缺口 7.6×）为硬墙；**Sub 轴经实证平反**（mLYNEWjW Sub 1.39 过门，全场 259/320 行过 Sub 门且 Sub-fail 行 Sh 全 ≤1.11——v1"Sub≥1.58 比例约束"系错误推断，§5.3）。
- **Sh-TO 标度律第八次应验**：全战役 |Sh|≥1.58 共 **9 行**（8 正 1 负），**TO 全部 ≥116.9%**（119.8/116.9/117.8/120.1×3/126.5/127.6/128.5）；TO≤70% 分支 Sh 上限 1.19（倒 U 峰在 TO 30-50%）。两个分支**不相交**。
- **记录在案的替代路径**：biasfree_analyst 族 `bl8Wd2Nq`（Sh 2.05 / Fit 1.12 / 2Y 2.39 / TO 22.9%，全门过+相关合规，**未提交**）——同一套 Gate 流程在持续型数据上已证明可过（§9）。
- **合规声明**：全部数字来自本地 336 行结果 JSON 与 BRAIN API 实读；**未提交任何 alpha**（用户铁律）。

---

## 1. 判据与门禁（实读确认，同 v1）

| 项 | 值 | 备注 |
|---|---|---|
| LOW_SHARPE | ≥1.58 | |
| LOW_FITNESS | ≥1.0 | 公式见 §6.1（含 TO 下限保护） |
| LOW_2Y_SHARPE | ≥1.58 | |
| HIGH_TURNOVER | ≤0.7 | 实际可用窗口 [5%,50%] 由 Margin+Fit 联立压缩 |
| CONCENTRATED_WEIGHT | ≤0.1 | |
| CLUSTER_TEST | ≥1.58（**warning 级**） | 全场最高 1.54（mLYNEWjW）；320/320 行全带此警告 |
| LOW_SUB_UNIVERSE_SHARPE | **实证非绑定**（v1 推断错误，已平反，见 §5.3） | 259/320 行过；Sub-fail 行 Sh 全 ≤1.11，0 例单独因 Sub 失败 |
| ProdCorr / SelfCorr | <0.70 / ≤0.60 | 终局门禁 |
| **唯一权威判据** | **`ra.ra_failed==false`** | 实证：fail 桶空但 ra_failed=true 的行存在 |

---

## 2. 战役全记录（42 批，每批最佳 |Sh| 槽）

### 2.1 原始 21 批（168 槽，v1 已详载，摘要保留）

| 批 | 方向 | 最佳槽 | Sh | 2Y | TO | 结论 |
|---|---|---|---|---|---|---|
| A/B/D | 种子锚（up/dn 比值） | npAXmlmq / LL52vo1a | 1.37-1.38 | 1.68-1.69 | 129.9% | 基线；Fit 0.31 死 |
| C | 连坐取消 | — | — | — | — | 7 取消+1 错误 |
| E-H | 结构空间 | omoX8edl / QPYAZbEp | 0.19-1.37 | 0.62-1.68 | 8.6-129.9% | 平滑杀边；外生门控塌 |
| I-L | 字段替换 | GrgNp2J3 / 3qjOW9A0 | 1.13-1.29 | 1.86-2.16 | 118-130% | excursion 比值 2Y 高但 Sh≤1.29 |
| M-O | **注意力稀缺突破** + bf 族 | **d5K6wxlx** | **1.61** | **2.09** | 120.1% | 家族首个过 Sh 线 |
| P-R | 极端度/冠军形态/信念门 | YPxOX1QA / N1eGk79E | 1.57-1.63 | 0.58-2.16 | 116-118% | ts_rank250 2Y2.16；门控 Sh **-0.05** |
| V-X | main_* 归一/衰退/构成 | pwvkorJv / akV8MAO5 | 1.09-1.32 | 1.08-1.87 | 110-141% | main_* TO 全崩；**fade 8/8 负** |

### 2.2 延伸 21 批（168 槽，本版新增）

| 批 | 线 | 方向 | 最佳槽 | Sh | 2Y | TO% | 结论 |
|---|---|---|---|---|---|---|---|
| gate7_W/Y/Z | PC | 2Y 墙突破/成分/新鲜度 | CVW_PER_CNT_TSRANK120 | 1.56 | 1.30 | 123.0 | CTN 2Y2.07/COPEN 2Y2.35；新鲜度路径证伪 |
| gate8_G/N/T | PC | 门控×锚分母/decay 扫描 | COPEN_ANCHORDEN_RANK | 1.45 | 2.24 | 118.8 | decay20+ts_rank TO 76.9% 但 Sh 1.11 |
| gate9_S | PC | 符号约定+vec 分母证伪 | VECMAX_DEN_CVW_RANK | **1.68**（负向） | -1.19 | 128.5 | 无 reverse 8/8 负；vec_avg/max 分母 TO 反升 |
| B1(S2) | PC | 门控成本矩阵+振幅合成 | VECMAX_CVW_TSRANK250 | **1.58** | 1.27 | 127.6 | 家族首个 Sh≥1.58；振幅 bf60×ts_rank 2Y 0.93 |
| B3'(S3) | PC | 分子矩阵收尾+CPV/UXCVW 双新 IC 轴 | UXCVW_RET_RANK | 1.44 | 1.62 | 126.8 | CPV 2Y 2.08-2.14 被支配；UXCVW×bf60 TO 40.3%/2Y 1.78 但 Sh 0.86 |
| B4(S4) | PC | CPV 骨架+交互轴收尾 | CPV_ANCHOR_DEN_RANK | 1.46 | 2.24 | 119.7 | CPV_CNT 2Y2.35；CPV×CVW Sh 0.17 退化；bf60 毁 CPV 2Y→0.99 |
| B5(S5) | PC | 归一器轴（volsurge/rangeATR/totticks） | CTN_PER_TOTTICKS | 1.28 | 1.60 | 112.8 | 归一器轴封闭（1.21-1.28） |
| B6'(S6) | PC | **PLO 参照点族补全+交互×冠军核** | UXCTN | 1.42 | 1.49 | 124.4 | **PLO×冠军骨架 1.13 ≪ TON 1.61（参照点轴封顶）**；UXCTN/DXCTN 1.42/1.40≈UXCVW 1.44（TON/VWAP 可互换） |
| w10a | AMP | decay=25 扫描 | （R/TO 0.403 槽） | 0.61 | — | 5.2 | **decay 非 TO 杠杆**（配对 0.97-1.05）；VECMAX_DEN 反向记录 1.68 |
| w10b | AMP | N/口径/ts_rank 研究 | N=120 ts_rank | 0.48 | — | — | **ts_rank 层 ×3.4**（0.14→0.48）；U/D 必要成分 |
| w10c | AMP | ts_rank 迁移三存活分支 | UPGRADE 槽1 | 0.98 | 0.50 | 52.0 | 高 R/TO（0.383）与高 Sh 不可兼得再现 |
| w10d | AMP | CW 门探索 | **BESTRET_FRESHGATE_0** | **1.65** | **2.10** | 119.8 | **SH165=冠军+新鲜事件门**（Ret 7.86%）但三 FAIL |
| w10e | AMP | SH165 的 TO 定向攻击 | FRESHGATE_1 | 1.62 | 2.11 | 117.8 | 低 TO 槽 Sh 塌 0.47-0.85（标度律第六次） |
| w10f | AMP | **TOP3000 宇宙轴** | 冠军×TOP3000 | 1.49 | 0.93 | 141.0 | 宇宙扩张同时降 Sh 升 TO，CW 非宽度问题 |
| w10g | AMP | **SUBINDUSTRY 中性化轴** | 冠军×SUBIND | 1.48 | 1.79 | 123.3 | Sh 1.61→1.48 且 CW 依旧——settings 消融轴全闭合 |
| w10h | AMP | **CW 已解×新鲜门合流矩阵** | **CONFLUENCE_CTO_RANK** | **1.59** | **2.03** | 114.6 | **mLYNEWjW：CW 已解+CLUSTER 1.54 族记录，仅剩 Fit/TO 两 fail（§8.1）** |
| w10i | AMP | mLYNEWjW 的 TO 定向攻击（final） | 保边变体 | 1.51 | 2.07 | 115.0 | 低 TO 变体 Sh 1.14@TO79.7%；标度律第八次应验 |

**批内关键证伪（勿重烧）**：PAN 参照点（≡TON 语义孪生）；PHI（≡ton_high，最佳 0.99）；SPY 市场调整全族（数学恒等死重，§6.5）；CTN/TON 双分母自归一；PLO 族（窗口低点非常态信号）；volsurge/rangeATR/totticks 归一器；group_mean×ts_rank 双算子；N=180 延拓；decay=25；TOP3000；days_from_last_change 硬门（TO 30% 时 Sh 0.85）。

---

## 3. Margin 恒等式（本战役最重要发现，320 槽全部复核）

**恒等式**：`Mgn_bps = 20 × Ret / TO`（Ret、TO 为小数）。

- **验证**：152/152 行在 2% 相对容差内精确吻合（v1）；延伸期新增行继续吻合。
- **推论 1（USA 死线）**：Mgn≥10bps ⟺ **Ret ≥ 0.5·TO**。
- **推论 2（换手管理无效性）**：decay/平滑/TVR 目标按比例同降 Ret 与 TO ⟹ `Ret/TO` 不变 ⟹ **Margin 是每笔交易信息量的属性，任何换手管理算子都不能改变它**。w10a 的 decay 配对实验（TO 变动 <5%）与 B5 的门控实验（TO 降 3× 但 Sh 腰折）是该推论的两个独立实证。
- **推论 3（一致解集）**：{Sh≥1.58, Ret≥0.5·TO, TO∈[5,50]%, 2Y≥1.58}（~~Sub≥1.58~~ 已实证平反为非绑定，见 §5.3）；评估候选只看 (Sh, Ret/TO) 两轴。320 槽中 Sh≥1.58 分支的 R/TO 最高 **0.066**（SH165）——**缺口 7.6×**。

---

## 4. 家族前沿与 Sh-TO 可行域（221 条实测，倒 U 形）

| TO 区间 | n | 最高 Sh | 该槽 Ret |
|---|---|---|---|
| 0-15% | 20 | 0.61 | 2.09% |
| 15-30% | 19 | 0.57 | 2.71% |
| **30-50%** | 45 | **1.19** | 3.74% |
| 50-72% | 10 | 1.17 | 4.06% |
| 72-100% | 8 | 1.11 | 4.34% |
| 100%+ | 119 | **1.63**（v1）/ **1.68**（负向记录） | 4.26% |

- **倒 U 形**：TO 30-50% 是低换手区的 Sharpe 峰值（1.19）；Sh≥1.0 且 TO≤0.72 的样本仅 18 条。
- **两个分支不相交**：全战役 |Sh|≥1.58 仅 9 个历史点（TO 全≥116.9%），TO≤70% 点 Sh 全≤1.19。任何"降 TO 保 Sh"的算子都被实测证伪（bf60/门控/ts_rank/decay/宇宙扩张五杠杆全试）。
- **2Y 天花板 2.52 但不可用**：全场最高 2Y = 2.52（`reverse(multiply(rank(U/(U+D)), rank(news_open_gap)))`，gate4_N）出现在 Sh 1.03 / TO 134.7% 的点上——2Y 与 Sh 同样 trade-off，无"双高"点。
- **Fit 前沿平坦**：沿 (Sh, R/TO) 前沿 Fit 全在 0.2-0.42——家族每笔 IC 上限结构化，换手管理曲线上无逃逸点。（注：R/TO 全场名义最高 4.37 出现在 TO 2.2%/Sh 0.22 的退化行——Ret/TO 是 1/TO 型比率，TO→0 时机械发散，非可用信号；可用前沿最高 0.125 @ Sh 0.57。）

---

## 5. 结构性不可能性证明（六墙 + 两门数学死局 + 一门警告墙 + 一项平反）

在 mandate 约束（news12 / USA / d1 / 2-3 字段 / op≤10）内，解集为空。除 v1 六墙（Margin 恒等式墙/瞬态墙/回填墙/门控墙/中性化墙/TO 饱和墙）外，延伸期将其中两门量化为**数学死局**（Margin 恒等式量化：缺口 7.6×；Fit 轴：需 Sh 2.83）、补上一门**警告墙**（CLUSTER_TEST 320/320 全警告），并**实证平反**一项 v1 错误推断（Sub 轴）：

1. **Margin 恒等式死局（数学，§3）**：`Mgn_bps = 20×Ret/TO`，USA 死线 10bps ⟺ Ret≥0.5·TO。Sh≥1.58 分支 R/TO 最高 0.066 ⟹ Mgn≤1.31bps——**缺口 7.6×**；且 decay/平滑/门控等换手管理算子同比例降 Ret 与 TO，Ret/TO 不变，**Margin 只能靠抬每笔 IC，不能靠换手管理**。
2. **Fit 轴死局（数学）**：Fit 公式含 TO 下限保护（§6.1），但 Sh≥1.58 分支 R/TO≤0.066 ⟹ Fit≤1.68×sqrt(0.066)≈0.43。**Fit≥1 需 Sh≥2.83 = 家族天花板（1.68）的 1.69 倍——IC 包络问题，非组合覆盖问题。**
3. **CLUSTER_TEST 警告墙（实证）**：全场 320 个评估行 **320/320 全部带 CLUSTER_TEST 警告**，最高 **1.54**（mLYNEWjW，新鲜门族；v1 记录 1.47）< 1.58——**即使 Fit/TO 全过，"零警告"仍不可达**。这是 mandate「不能有任何指标的警告项」的直接不可能证明。
4. **Sub 轴平反（v1 错误推断的实证修正）**：v1 据「Sub/Sh≈0.65-0.79 比例约束」推断 Sub≥1.58 需 Sh≥2.0-2.4（"Sub 轴死局"）。**该推断被 w10h 直接推翻**：mLYNEWjW（Sh 1.59）Sub 1.39 明确位于 pass 桶（LOW_SUB_UNIVERSE_SHARPE 已过）；全场 259/320 行过 Sub 门，61 个 Sub-fail 行 **Sharpe 全部 ≤1.11**，无一例单独因 Sub 失败、无一例 Sh≥1.5 触 Sub。Sub 门对本家族高 Sharpe 候选**非绑定**。附注：Sub 边界在上报值口径下非单调（0.55 失败 / 0.56 通过、-0.13 通过 / -0.12 失败），疑检查用全精度或替代子宇宙定义——但无论如何不构成 1.58 级障碍。v1"三门死局"实为"两门死局 + 一平反"。

**辅证（Sh∝√TO×IC 标度律）**：UXCVW 1.44→0.86 @ TO 127%→40.3%（1.44/√3.2≈0.80，预测命中）；SH165 门控版 1.62→0.85 @ TO 118%→30%。**八次独立应验**（末次：w10i 对 mLYNEWjW 的 TO 定向攻击，低 TO 变体 Sh 1.14@TO79.7%）。

---

## 6. 延伸期新发现（七项可复用资产）

1. **Fit 公式含 TO 下限保护**：`Fit = Sh × sqrt(|Ret| / max(TO, ~0.11))`（174 行拟合，复现误差 ~0.003）。**TO≤11% 是门槛台阶**：Sh=1.58 时达标仅需 Ret 4.40%（TO=11%）、8.01%（20%）、16.0%（40%）。此前 21 批完全没注意到该临界点——但家族无任何低 TO 结构能达到 Sh 1.58，台阶无人能站上。
2. **ts_rank 层 ×3.4 抬 Sharpe**：纯 rank 0.14 → ts_rank 0.48（同结构）。仅在本结构族内有效（跨结构迁移失败 1.17→0.70-0.98）；且 ts_rank250 **不毁 2Y**（毁 2Y 的是 bf60：冠军 2Y 2.09→0.45），TO 仅 -2pp。
3. **CW 墙解法**：`trade_when(cond, X, 0)` 第三参 **0（硬平仓）**在振幅族双双消 CW（L/S 430/430）；但裸 rank 版全 CW fail，且硬门使 Sh 腰斩（§5 标度律）。**CW 与 Sh 在此族互斥**。
4. **新鲜事件门是唯一未杀边的催化剂掩码**：冠军+`trade_when(days_from_last_change(vec_count(VHEX))<2, ·, 0)` = SH165：Sh 1.61→**1.65**、Ret 7.70→**7.86%**、2Y 2.09→**2.10**、TO 120.1→119.8%（四项全面微升，CW 不变）。门 <1 天版 Sh 1.62/2Y 2.11。这是全战役对"催化剂断裂"红队指控的唯一建设性回应——但 TO 119.8%+CW+Fit 0.42 仍三 FAIL，且增益幅度（+0.04 Sh）远不足以补 7.6× Margin 缺口。
5. **SPY 市场调整恒等死重**：`rank(subtract(X, 横截面常数)) ≡ rank(X)`——spy_etf_closing_price 经 vec_avg+ts_delta 后 SPY_RET 为横截面常数，rank 封装下 100% 无效。此类构造（及任何"减市场收益"型）勿再烧；要生效必须裸加权，而裸加权必触 CW。
6. **宇宙轴闭合**：TOP3000 上冠军 Sh 1.49（<TOP1000 1.61）且 TO 141%、CW 依旧——**CW 非宇宙宽度问题**（L/S 621/619 仍 fail）。
7. **字段语义核验方法论**：B6 提案方的两处错误（PAN≡TON、PHI≡ton_high）全靠 `news12_fields_full.json` 字段定义实读揭穿。**查重不能只信指纹库**——指纹不含语义孪生检测，expression 级全史扫描（DB LIKE + 本地 JSON）是必要兜底。

---

## 7. 红队终审记录（两轮，独立上下文子 agent）

| 轮次 | 对象 | 判决 |
|---|---|---|
| B6 终审 | 原始 8 槽 | **砍 5/8**：PAN 语义孪生 / PHI 字段描述错误导致的重复 / SPYADJ×3 数学恒等死重 / CTN 自归一被支配；保留 PLO（唯一真新参照点） |
| B6' 聚焦复审 | 修正后 8 槽 | **8/8 GO 无砍单**；机制深核：UXCTN 非振幅²（"冲高回落"事件使 U 与 \|CTN\| 机械独立）；ts_rank250 不毁 2Y；战略签署"price-context 几何实证穷尽（主要交叉格 100% 覆盖）" |

红队两轮的战略闭合性论证（Fit≤Sh×0.354；Sh≥1.58 与 TO≤70% 不相交）被后续 B6'/w10e/w10f 三批数据完全应验。

---

## 8. 头部候选精确差距（全部实读）

### 8.1 mLYNEWjW — 全战役最佳近 miss（w10h 槽1，CW 已解×新鲜门合流核心）
`trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), add(vec_count(high_price_excursion_stddev), 1)))), 0)`

与 SH165 的**唯一差异**：分母 `ts_backfill(vec_count(VHEX),120)` → `add(vec_count(VHEX),1)`——去回填后 **CW 入 pass**、CLUSTER 抬至族记录 1.54、Sh 仅 -0.06。

| 指标 | 实值 | 门槛 | 状态 |
|---|---|---|---|
| Sharpe | **1.59** | 1.58 | ✅ |
| Returns | 7.52% | — | 过门行中次高（SH165 7.86% 更高） |
| 2Y Sharpe | **2.03** | 1.58 | ✅ |
| Sub Sharpe | 1.39 | 实证非绑定（§5.3） | ✅（pass 桶） |
| Fitness | 0.41 | 1.0 | ❌（需 Sh 2.83，§5.1） |
| Turnover | 114.59% | ≤50% | ❌（Margin 缺口 7.6×） |
| Margin | 1.31bps | ≥10bps | ❌ |
| CW | **pass（L/S 312/307）** | ≤0.1 | ✅（家族唯一解） |
| CLUSTER_TEST | 1.54 | 1.58 | ⚠️ 警告（缺口 0.04，族记录） |
| MATCHES_THEMES | 警告 | — | ⚠️ |
| invSh / rnSh | 1.42 / 1.86 | — | 记录 |

**ra 判定**：ra_failed=true，仅 2 项硬 fail（LOW_FITNESS + HIGH_TURNOVER）+ 2 项警告（CLUSTER_TEST + MATCHES_THEMES）；SELF_CORRELATION / DATA_DIVERSITY / PROD_CORRELATION / REGULAR_SUBMISSION 为 pending（未提交故未评）。**全战役 fail 数最少的 4 行之一，且是唯一 Sharpe 已过线的 2-fail 行**（另 3 行 2-fail 均含 LOW_SHARPE，Sh≤0.86；其余 316 行 ≥3 项 fail）。

### 8.2 SH165（alpha_id=leMYnJZn，w10d 槽5）— v1 版最佳，让位于 mLYNEWjW
`trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2), reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120)))), 0)`

Sh **1.65**（过门行最高）/ Fit 0.42 / TO 119.85% / Ret **7.86%**（过门行最高）/ 2Y **2.10** / Sub 1.30（过）/ Mgn 1.31bps / CW **fail** / CLUSTER 1.47；**3 FAIL**（LOW_FITNESS+HIGH_TURNOVER+CONCENTRATED_WEIGHT）+ 2 警告。Sh/Ret 略优于 mLYNEWjW 但 CW 未解、CLUSTER 低 0.07、fail 数多 1——综合距离达标更远。

### 8.3 d5K6wxlx — 家族冠军（v1 已详载）：Sh 1.61/2Y 2.09/TO 120.1%/Fit 0.41/CW/ProdCorr 0.7033（差 0.0033）/CLUSTER 1.47。
### 8.4 N1eGk79E — 唯一相关性双过（PC 0.5589/SC 0.1521）但 2Y 0.58/Fit 0.31/TO 116.9%/CW/Mgn 0.73bps。
### 8.5 对照：bl8Wd2Nq（biasfree_analyst 族，**未提交**）Sh 2.05/Fit 1.12/2Y 2.39/TO 22.9% 全门过——证明阈值组合本身可满足，不可满足的是 news12 事件快照族的 IC 结构。

---

## 9. 结论与建设性路径

**结论**：在 mandate 约束集内，news12 族的解集为**空集**。三重独立证据一致：①320 槽实证前沿（无任何候选同时满足 Sh/Ret-TO/2Y/零警告）；②Margin 恒等式+两门数学死局（Fit 需 Sh 2.83）+ CLUSTER 警告墙（320/320 全警告、最高 1.54）+ Sub 门实证平反（非绑定）；③红队两轮机制判决与战略闭合签署。**这不是搜索不充分**——四大轴主要交叉格 100% 覆盖、五类 TO 管理杠杆、宇宙轴、新鲜门全部实测——**而是事件快照型数据的结构性物理极限**：边缘瞬态 → TO 结构性 110-140% → Ret/TO 恒等式封死 Margin → 保边与降换手严格互斥。

**若目标不变（过全部门+零警告），可行动路径**（按优先级）：
1. **换持续型边缘族（唯一已验证路径）**：biasfree_analyst `bl8Wd2Nq` 已全门过（Sh 2.05/Fit 1.12/2Y 2.39/TO 22.9%），其通式「组内化：现价相对 F 的偏离 − 其近期均值」可直接作为新战役种子；同套 Gate 流程已证明可过。该 alpha 至今**未提交**（遵铁律）。
2. **news12 内仅剩的窄路径**：**mLYNEWjW 为家族最优交付候选**（Sh 1.59/2Y 2.03/CW 已解/CLUSTER 1.54，仅剩 Fit 0.41 + TO 114.6% 两项硬 fail）。剩余墙：Fit 需 Sh 2.83（§5.1，IC 包络问题）+ Margin 缺口 7.6×（§3）+ CLUSTER 缺口 0.04 + MATCHES_THEMES 警告——**零警告仍不可达**；若再攻 ProdCorr（pending 未评），可换字段走 L2 层去相关（N1eGk79E 已证 PC 0.56 可达）。
3. **放宽阈值**（需研究员批准）：若接受 Mgn≥2bps + 允许 CLUSTER 警告，mLYNEWjW/SH165/d5K6wxlx 是家族最优交付（Sh 1.59/1.65/1.61、2Y 2.03/2.10/2.09、Ret 7.52%/7.86%/4.26%；仅 mLYNEWjW 已解 CW）。

**合规声明**：本战役未提交任何 alpha；所有指标来自本地 320 行结果 JSON 与 BRAIN API 实读；红队判决来自独立上下文子 agent（payload 经三重泄漏扫描，无任何回测指标）。

---

*研报生成：2026-10-25 · 证据文件：campaigns/USA_news_news12_gate1/{batch_gate*,batch_w10*,summary_gate9_*,wave9b*,wave10*}.log/.json（42 批）+ FINAL_REPORT.md（v1，168 槽）· 红队判例：agent0/redteam_outbox/{d5K6wxlx,N1eGk79E}.json + 本轮两轮终审对话记录*
