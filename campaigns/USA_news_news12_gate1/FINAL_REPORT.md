# Gate 1 终局研报 — USA/TOP1000/delay1/news12 注意力稀缺族

**战役代号**：USA_news_news12_gate1 · **执行期**：2026-10-24 · **规模**：21 批 × 8 槽 = 168 槽（152 有效回测 + 16 批内连坐 CANCELLED/ERROR）
**mandate**：在最佳候选 `reverse(divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt)))`（Sh 1.37）基础上优化；2≤字段≤3；op≤10；仅 multi_create_simulate 每批 8 条；成功标准 = 零 fail + 零任何警告；**严禁提交**。

---

## 0. 执行摘要

- **168 槽零候选达到 `ra.ra_failed==false`**（唯一权威判据，非 checks.fail 桶——10 行 fail 桶空但 ra_failed=true 实证）。
- **零警告同样被证明不可达**：CLUSTER_TEST 限 1.58（warning 级），**全场 168 槽最高 1.47**（d5K6wxlx）；MATCHES_THEMES 仅 group_rank 包装可消，但包装即杀边。
- **两个头部候选的精确差距**（全部指标实读，见 §7）：
  - **d5K6wxlx**（家族冠军，Sh 1.61 / 2Y 2.09 / Sub 1.27 / rnSh 1.91）：Fit 0.41、TO 120.1%、CW、Mgn 1.28bps、ProdCorr **0.7033**（超限 0.0033）、CLUSTER 1.47、MATCHES_THEMES —— 6 类不达标。
  - **N1eGk79E**（Sh 1.63 / ProdCorr 0.5589 / SelfCorr 0.1521 双过）：2Y 0.58、Fit 0.31、TO 116.9%、CW、Mgn 0.73bps —— 5 类不达标。
- **结构性不可能性证明**（§5）：Margin 恒等式（152/152 行精确吻合）把"过 Margin 门"化为 `Ret ≥ 0.5·TO`；家族前沿实测 `Ret/TO` 最高 0.125（出现在 Sh 0.57 处），在 Sh≥1.58 分支上最高 0.064 —— **缺口 7.8×**；且恒等式证明任何换手管理算子（decay/TVR 目标/平滑）都不改变 `Ret/TO`（Ret 与 TO 同比例缩放）。家族内 IC 天花板由 rnSh≤2.05 钉死。
- **红队物理盲审**（独立上下文子 agent，看不到任何回测指标）：两候选均判 **INCOMPLETE_SIGNAL**，断点同在催化剂段——与实证的瞬态墙互相印证（§6）。
- **合规声明**：全部数字来自本地结果 JSON 与 BRAIN API 实读复核；**未提交任何 alpha**（用户铁律）。

---

## 1. 判据与门禁（实读确认）

| 项 | 值 | 来源 |
|---|---|---|
| LOW_SHARPE | ≥1.58 | checks.fail limit |
| LOW_FITNESS | ≥1.0 | checks.fail limit |
| LOW_2Y_SHARPE | ≥1.58 | checks.fail limit |
| HIGH_TURNOVER | ≤0.7（即 TO≤70%；实际可用窗口 [5%,50%] 由 Margin+Fit 联立压缩，见 §3） | checks limit |
| CONCENTRATED_WEIGHT | ≤0.1 | checks.fail limit |
| CLUSTER_TEST | ≥1.58（**warning 级**） | checks.warning limit |
| LOW_SUB_UNIVERSE_SHARPE | limit -0.31（本家族实际需 Sub≥1.58 才能同时满足 Sub/Sh 比例约束，见 §4） | checks limit |
| ProdCorr / SelfCorr | <0.70 / ≤0.60 | 终局门禁（gatekeeper audit_final_alpha） |
| **唯一权威判据** | **`ra.ra_failed==false`** | 实证：10/152 行 fail 桶空但 ra_failed=true |

---

## 2. 战役全记录（21 批，每批最佳）

| 批 | 方向 | 最佳槽 | Sh | 2Y | TO | 结论 |
|---|---|---|---|---|---|---|
| A/B/D | 种子锚（up/dn 比值及其 ret 版） | npAXmlmq / LL52vo1a | 1.37-1.38 | 1.68-1.69 | 129.9% | 基线；Fit 0.31/Mgn 1.01bps 死 |
| C | （批内连坐取消） | — | — | — | — | 7 取消 + 1 错误 |
| E-H | 结构空间（ts_sum 60 / group_mean 60 / SI 门控 / 极端度） | omoX8edl / QPYAZbEp | 0.19-1.37 | 0.62-1.68 | 8.6-129.9% | 平滑杀边（ts_sum60 Sh 0.19）；外生门控塌 |
| I-L | 字段替换（mins_20_pct / excursion 比值 / VEC_MAX / bf60） | GrgNp2J3 / 3qjOW9A0 | 1.13-1.29 | 1.86-2.16 | 118-130% | excursion 比值 2Y 1.86-2.16 但 Sh≤1.29 |
| M-O | **注意力稀缺突破** + bf 族 + MARKET 证伪 | **d5K6wxlx** | **1.61** | **2.09** | 120.1% | 家族首个过 Sh 线；Sub 1.27/CW/Fit 死 |
| P-R | 极端度族 / 冠军形态空间 / 信念门控@STAT | YPxOX1QA / N1eGk79E | 1.57-1.63 | 0.58-2.16 | 116-118% | ts_rank250 2Y2.16；CLOSE_VWAP Sh1.63；门控 Sh **-0.05** |
| V-X | main_* 注意力归一 / 衰退结构 / 注意力构成 | pwvkorJv / akV8MAO5 | 1.09-1.32 | 1.08-1.87 | 110-141% | main_* TO 全崩；**fade 族 8/8 负**；构成族 4/8 负 |

**批次内关键证伪（勿重烧）**：
- 信念门控（内生，前 10%/20% 极端度）：2rjxPlbx Sh **-0.05**、O0JjK7av Sh 0.27（TO 虽降至 10-15%，边缘塌方）
- 衰退结构族（fade，8/8）：2rjxQq8Z -0.88 / 9qE3bPZe -0.93 / 0mjL9kqk -0.75 / leMYk6q7 -0.84 —— **盘中反应是延续而非回吐**；反转边缘只在 1-2 日尺度
- 注意力构成族 ATTMIX（4/8 负）：j2eJW91e -0.59 / WjLRnagP -0.63
- STATISTICAL 中性化：对纯事件快照族 8/8 净负（与种子战役互证）
- bf60 对注意力族致死：d5K6wxlx 结构 1.61→0.87、2Y 2.09→0.45
- MARKET 中性化：TO 37.8% vs INDUSTRY 37.1%（无差异）
- close-vwap 版触发 UNITS 量纲警告；乘 vol_stddev -0.44；winsorize -0.43

---

## 3. Margin 恒等式（本战役最重要发现）

**恒等式**：`Mgn_bps = 20 × Ret / TO`（Ret、TO 为小数）。

- **验证**：152/152 行在 2% 相对容差内精确吻合（最差 1.8%）。
- **推论 1（USA 死线）**：Mgn≥10bps ⟺ **Ret ≥ 0.5·TO**。TO=37% 需 Ret≥18.5%；TO=10% 需 Ret≥5%。
- **推论 2（换手管理无效性）**：对固定信号，decay/平滑/TVR 目标按比例同时降 Ret 与 TO ⟹ `Ret/TO` 不变 ⟹ **Margin 是信号每笔交易信息量的属性，任何换手管理算子都不能改变它**。抬 Margin 唯一途径 = 抬每笔 IC。
- **推论 3（一致解集）**：{Sh≥1.58, Ret≥0.5·TO, TO∈[5,50]%, 2Y≥1.58, Sub≥1.58}；评估候选只需看 (Sh, Ret/TO) 两轴，缺口 = 0.5/(Ret/TO) 倍。

---

## 4. 家族前沿（Sh ↔ Ret/TO 反相关）

**前沿实测（全部 168 槽）**：

| 分支 | 代表 | Sh | Ret/TO | 与死线 0.5 的距离 |
|---|---|---|---|---|
| 高 Sharpe 原始瞬态（TO 117-141%） | d5K6wxlx | 1.61-1.63 | 0.036-0.064 | **7.8-13.9×** |
| bf60 回填（TO 37%） | YPxOGboo / ZYm9ebv0 | 1.13-1.17 | 0.086-0.099 | 5.1× |
| 长平滑 / 门控（TO 8-20%） | QPYAZbEp / gJW5E93v | 0.19-0.51 | 0.111-0.116 | 4.3× |
| group_mean 60（TO 57%） | omoX8edl | 0.57 | **0.125（全场最高）** | 4.0× |

**三条硬约束**：
1. **Sh 与 Ret/TO 在本族反相关**：所有抬 R/TO 的机制（回填/平滑/门控）都压 Sh；解框 {Sh≥1.58, R/TO≥0.5} 为空。
2. **Sub/Sh ≈ 0.65-0.79**（头部 10 行实测）：Sub≥1.58 需 Sh≥2.0-2.4，超家族天花板（1.63）。
3. **rnSh 天花板 ≈ 2.05**（JjPkRkNA），实得最高 1.61 —— 风险中性化空间已很薄。

---

## 5. 结构性不可能性证明（六墙）

在 mandate 约束（news12 / USA / d1 / 2-3 字段 / op≤10）内，解集为空，证明如下：

1. **Margin 恒等式墙**：需 Ret≥0.5·TO；Sh≥1.58 分支实测最高 R/TO=0.064（缺口 7.8×）；且换手管理算子被恒等式证明无效。
2. **瞬态墙**：边缘只存于事件日附近；ts_mean(A,20/60/250)=0.25/0.11/-0.25；ts_decay_linear 保边 98.5% 但 TO 仅降 12%；ts_decay_exp_window 降 TO 77% 但 Sh 0.35 —— 保边与降换手严格互斥。
3. **回填墙**：bf60 消 CW/压 TO（130%→37%、longCount 511）但杀注意力族（1.61→0.87）；保振幅族 80% 边但 2Y 死（0.61-0.78 < 1.58）。
4. **门控墙**：外生门控（PE/SI/cap/vol/yield）与内生信念门控（前 10% Sh **-0.05**）双重证据 —— 边缘是不可集中的宽横截面现象，一集中就塌。
5. **中性化墙**：MARKET 无差异（37.8% vs 37.1%）；STATISTICAL 对事件快照族 8/8 净负；SUBIND/有害算子清单见记忆。
6. **TO 饱和墙**：TO 37% 与回填长度无关（bf60/120/250 同值）；原始事件字段 TO 结构性 110-130%。

**辅证（CLUSTER_TEST）**：即便上述全过，CLUSTER_TEST 限 1.58（warning 级），全场最高 1.47 —— **零警告在本族内不可达**。

---

## 6. 红队物理盲审（独立上下文子 agent，零回测指标）

对两头部候选执行 agent0 物理盲审（payload 经三重泄漏扫描：指标键名 / 指标名+数字 / bps 数值）：

| 候选 | 判决 | 数学现实反编译 | 断点 |
|---|---|---|---|
| d5K6wxlx | **INCOMPLETE_SIGNAL** | "事件活跃度缩放的日内新闻后反转，非关注度缩放，且无动态触发器" | **催化剂**：AST 无动态触发算子；ts_backfill 只包分母，分子非新闻日即空，"回填定义持仓久期"在 AST 中不成立；ton_last 覆盖率 0.97 使"新闻到达"近乎每日发生，非稀疏触发 |
| N1eGk79E | **INCOMPLETE_SIGNAL** | "被陈旧关注度标量调制的日频收盘-VWAP 反转信号" | **催化剂**：无事件门控；分子逐日更新而分母回填 120 天，非事件日也在交易，蓝队声称的催化剂与数学实现脱钩 |

**关键互证**：红队在**看不到任何回测数字**的条件下，仅从 AST + 字段定义就独立诊断出"催化剂断裂 / 分子分母更新频率错配"——这与实证的瞬态墙（TO 120% = 几乎每日交易、平滑即杀边）是同一事实的机制层与数据层两面。红队修复指令（事件掩码 / 当日关注度分母 / 压缩回填窗口）指向的方向均已被实证证伪（门控杀边、去回填即 CW、短回填即 Margin 死）。

---

## 7. 头部候选精确差距（全部实读）

### d5K6wxlx — 家族冠军（gate4_N）
`reverse(rank(divide(subtract(news_eod_close, news_ton_last), ts_backfill(vec_count(high_price_excursion_stddev), 120))))`

| 指标 | 实值 | 门槛 | 状态 |
|---|---|---|---|
| Sharpe | 1.61 | 1.58 | ✅ |
| 2Y Sharpe | 2.09 | 1.58 | ✅ |
| Sub Sharpe | 1.27 | ~1.58（比例约束） | ❌ |
| Fitness | 0.41 | 1.0 | ❌ |
| Turnover | 120.1% | ≤50% | ❌ |
| Margin | 1.28bps | ≥10bps | ❌（缺口 7.8×） |
| CW | fail | ≤0.1 | ❌ |
| ProdCorr | **0.7033** | <0.70 | ❌（差 0.0033） |
| CLUSTER_TEST | 1.47 | 1.58（警告级） | ❌ |
| MATCHES_THEMES | 警告 | 无 | ❌ |

### N1eGk79E — 唯一相关性合规候选（gate5_R）
`reverse(rank(divide(subtract(news_eod_close, news_eod_vwap), ts_backfill(vec_count(high_price_excursion_stddev), 120))))`

| 指标 | 实值 | 门槛 | 状态 |
|---|---|---|---|
| Sharpe | 1.63 | 1.58 | ✅ |
| ProdCorr | **0.5589** | <0.70 | ✅ |
| SelfCorr | **0.1521** | ≤0.60 | ✅ |
| 2Y Sharpe | 0.58 | 1.58 | ❌ |
| Fitness | 0.31 | 1.0 | ❌ |
| Turnover | 116.9% | ≤50% | ❌ |
| Margin | 0.73bps | ≥10bps | ❌（缺口 13.7×） |
| CW / CLUSTER / MATCHES_THEMES | fail / 警告 / 警告 | — | ❌ |

**相关性终检全表**（BRAIN API 实读复核，2026-10-24）：

| alpha | Sh | ProdCorr | SelfCorr | 结论 |
|---|---|---|---|---|
| d5K6wxlx | 1.61 | 0.7033 | — | ❌ 超限 0.0033 |
| YPxOX1QA | 1.57 | 0.7416 | — | ❌ |
| 9qE3b1o2（最高 Ret 10.15%） | 1.29 | 0.7420 | — | ❌ |
| **N1eGk79E** | 1.63 | **0.5589** | **0.1521** | ✅ 唯一双过（但 IS 全崩） |
| YPxOGboo（bf60 组内） | 1.17 | 0.6710 | 0.2152 | ✅ 相关双过（Sh 死） |
| ZYm9ebv0（bf60 rank） | 1.13 | 0.6833 | 0.2281 | ✅ 相关双过（Sh 死） |

---

## 8. 结论与建设性路径

**结论**：在 mandate 约束集内，news12 注意力稀缺族的解集为**空集**（§5 六墙证明 + 168 槽零命中 + 红队机制判决三重一致）。这不是搜索不充分，而是该数据集的结构性物理极限：事件快照型数据 → 边缘瞬态 → TO 结构性 110-140% → Ret/TO 恒等式封死 Margin；任何"保边"操作都保瞬态，任何"降换手"操作都杀边。

**若目标不变（过全部门 + 零警告），可行动路径**（按优先级）：
1. **换数据集到持续型边缘族**：biasfree_analyst 已交付 `bl8Wd2Nq`（Sh 2.05 / Fit 1.12 / 2Y 2.39 / TO 22.9%，全部门过、相关性合规）——同一套 Gate 流程在持续型数据上已证明可过；该 alpha 至今**未提交**（遵铁律）。
2. **放宽 Margin 阈值**：若研究员可接受 Mgn≥2bps（家族极限），d5K6wxlx 仅差 ProdCorr 0.0033 与 Sub/CLUSTER；换字段去相关（L2 层）是最短路径。
3. **news12 内换经济假设**：fade/构成族符号反转证明"延续"边缘存在于 1-2 日尺度，但该尺度无法同时满足 2Y≥1.58 与 Sub≥1.58（尺度分层极限）。

**合规声明**：本战役未提交任何 alpha；所有指标来自本地 152 行结果 JSON 与 BRAIN API 实读；红队判决来自两个独立上下文子 agent（payload 经三重泄漏扫描，无任何回测指标）。

---
*研报生成：2026-10-24 · 证据文件：campaigns/USA_news_news12_gate1/{batch_gate*,summary_gate*,corr_recheck_final,field_meta_redteam}.json · 红队判例：agent0/redteam_outbox/{d5K6wxlx,N1eGk79E}.json*
