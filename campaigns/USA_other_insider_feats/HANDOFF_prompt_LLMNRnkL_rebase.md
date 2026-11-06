# 交接任务书：USA / insider_feats 战役基座回退与根因重构

> 本文件是一份**可直接整体复制给下一个 Agent 执行的 prompt**（从「## 一、你的任务」开始到文末）。
> 生成时间：2026-11-05 00:00 GMT+8。基于 Wave 1~49（约 350 条表达式、21+ 次 PC 核验）的实证归档。
> 本窗口只做分析与撰写，**未执行任何新回测**。

---

## 一、你的任务

接手 WorldQuant BRAIN 的 `USA / D1 / TOP1000` alpha 挖掘战役。上一轮 Agent 已跑完 49 波并把 `N1NVqZYg` 登记为 grand champion，但经 Champion_Score 复核发现该"新王"实际上**劣于原始种子 `LLMNRnkL`**。你的任务不是继续沿 `N1NVqZYg` 爬山，而是：

1. **先做口径校准**（Step 0，强制），
2. **以 `LLMNRnkL` 骨架为主基座重新出发**，
3. 主攻一个 49 波从未真正触碰过的根因：**belief 腿的稀疏零值结块**，
4. 每一步都必须用统一目标函数判定"真进步 vs 伪进步"。

### 硬约束（违反即作废）
- **严禁修改任何 `.py` 源码**（brain-mcp 的 `main.py` 等）；只在上下文中手工构造 FASTEXPR 表达式。
- **严禁脚本循环 / 模板批量拼凑公式**。每条表达式必须由你逐条手写，并在批次 JSON 的 `note` 里写明其经济学假设与可证伪判据。
- 数据字段数 **2 ≤ n ≤ 3**；最多跨 **1 个**外部数据集；op 数不设硬上限，但必须逐条报告。
- 提交前**必须**完成两道前置核验：① 用 `get_datafields` 确认每个字段 ID 真实存在（历史出现过幻觉字段 `top20_..._volume_ratio_...`）；② 对照 104 算子白名单 `D:/brain_cli/wqb_cli/brain-kb/operators/ALL_OPERATORS.md` 确认每个算子合法。历史四次整批 CANCEL 连坐的元凶依次是 `vec_last`、`negate`（合法替代 `reverse`）、`ts_ir`（用 `ts_mean/ts_std_dev` 改写）、`ts_min|ts_max`。
- 回测一律走 `create_multi_simulation`，每批 8 条（或 ≥2 条）；单表达式会被服务端拒绝。
- 所有表达式在 `INDUSTRY` 中性化、`decay=8`、`truncation=0.025`、`universe=TOP1000`、`delay=1`、`pasteurization=ON`、`nan_handling=ON` 基线下测试（设置轴变更需显式记录并单独成组）。
- 禁止使用中性化强度做去相关（用户禁令：`SLOW/STATISTICAL/CROWDING` 一律禁用）。

---

## 二、为什么回退到 LLMNRnkL（已算清的账，不要重算，但可复核）

Champion_Score 定义（战役最初约定，后 9 波被错误弃用）：

```
CS = Fitness × ln(Margin_bps) × (1 − PC²) × (1 − 0.04 × OpCount)
```

| alpha | 世代 | Fit | Mgn | PC | Op | **CS** | **PC 余量 (0.70−PC)** |
|---|---|---|---|---|---|---|---|
| **LLMNRnkL** | 种子 W32 | 0.60 | 11.13 | 0.6316 | 6 | **0.6605** | **0.0684** |
| YP1bEqmM | W39 尾部幂次 | 0.66 | 12.1 | 0.6848 | 10 | 0.5243 | 0.0152 |
| A1Vv1xxg | W46 nc_w18 | 0.68 | 11.8 | 0.6936 | 10 | 0.5225 | 0.0064 |
| omEW12Qk | W45 nc_w15 | 0.63 | 10.7 | 0.6987 | 10 | 0.4586 | 0.0013 |
| **N1NVqZYg** | W47 最终王 | 0.69 | 12.1 | 0.6957 | 11 | **0.4971** | **0.0043** |
| QPvKlRGp | W48 d12 | 0.71 | 12.7 | 0.7091 | 10 | 0.5383 | −0.0091 |
| gJeZ1G5l | W49 d16 | 0.72 | 14.1 | ~0.72 | 11 | 0.5138 | −0.0200 |

**结论：CS 从 0.6605 单调劣化到 0.4971（−24.7%），后 5 代"新王"全部低于种子。** 用复杂度换来的核心收益是噪声级的：

| 面板 | LLMNRnkL | N1NVqZYg | Δ |
|---|---|---|---|
| Sharpe | 1.12 | 1.16 | +0.04（噪声） |
| 2Y Sharpe | 0.91 | 0.92 | +0.01（噪声） |
| Fitness | 0.60 | 0.69 | +0.09（几乎全部来自 Ret 3.56→4.38%，非信号质量） |
| Cluster Sharpe | 0.51 | 0.73 | +0.22（唯一实质增益，但距 1.58 门仍差 0.85） |
| ProdCorr | 0.6316 | 0.6957 | **+0.064 恶化，余量被吃掉 16 倍** |
| Long/Short | 549/465 | 601/417 | **失衡差 84 → 184，根因反而恶化** |
| 算子数 | 6 | 11 | +83% |

### 主基座（唯一出发点）

```
group_rank(ts_mean(multiply(subtract(vec_avg(buy_sell_tx_count_ratio_all_20d_filled),
  vec_avg(buy_sell_tx_count_ratio_all_60d_filled)),
  vec_avg(top20_buy_to_sell_txn_ratio_lookback_60_filled)), 20), subindustry)
```
@USA/TOP1000/D1 / INDUSTRY / decay 8 / truncation 0.025 / pasteurization ON / nan_handling ON
实测：Sh 1.12 / 2Y 0.91 / Fit 0.60 / Ret 3.56% / TO 6.41% / Mgn 11.13bps / DD 5.82% / Sub 0.98 / RN 0.82 / CLST 0.51 / PC 0.6316。三个字段全部 `alpha_count=0`、coverage 0.8833，均属 `insider_feats`，**未使用跨数据集配额**。

`N1NVqZYg` 不要作为优化起点；只作为"外部新闻腿有效但吃 PC 余量"的证据存档。若未来出现能**主动压低 PC** 的新机制，可再激活该分支。

---

## 三、Step 0（强制前置）：校准 checks 口径，否则"全绿"判据不成立

实测发现同一指标在不同快照里 FAIL/WARNING 分级不一致，**我们落盘的 `fail_count` 不可跨代比较**：

| alpha | Sh | 落盘 FAIL | 落盘 WARNING |
|---|---|---|---|
| LLMNRnkL (W32/W37) | 1.12 | `[]` | LOW_SHARPE / LOW_FITNESS / CLUSTER_TEST / **LOW_2Y_SHARPE** |
| akKbQvM9 (W39) | 1.06 | `[]` | 同上 |
| YP1bEqmM (W39) | 1.15 | LOW_SHARPE / LOW_FITNESS / **LOW_2Y_SHARPE** | CLUSTER_TEST / MATCHES_THEMES |
| 2rAw6erx (W40) | 1.16 | 3 项 | CLUSTER_TEST / MATCHES_THEMES |
| N1NVqZYg (W47) | 1.16 | LOW_SHARPE / LOW_FITNESS / **IS_LADDER_SHARPE** | CLUSTER_TEST / MATCHES_THEMES |

数值更好却判得更严，且检查项名同步由 `LOW_2Y_SHARPE` 变为 `IS_LADDER_SHARPE`、`MATCHES_THEMES` 由 pass 变 warning。强烈提示 **preliminary simulation checks 与 submission-level checks 被混用**（疑似被 `check_correlation` 查询过的 alpha 返回更严分级，或来自不同 API 端点/不同落盘脚本）。

**你必须先做**：用**同一个端点**统一重拉以下候选的完整 checks + PC，建立可比基线后再启动优化：
`LLMNRnkL`、`YP1bEqmM`、`A1Vv1xxg`、`N1NVqZYg`、`QPvKlRGp`、`gJeZ1G5l`、`bl6bQ0Jp`。
输出一张表：每个 alpha 的 `fail[]` / `warning[]` / `pending[]` / `max_correlation` / `passes_check`，并明确记录所用端点与拉取时间。若确认口径漂移，请**修正** `campaign_champions.json` 中的 `gates` 记账。

用户最终目标始终是 **0 FAIL + 0 WARNING 全绿**（Sh≥1.58 / Fit≥1.0 / 2Y≥1.58 / CLUSTER≥1.58 / PC<0.70 / Margin≥10bps）。在口径校准完成前，任何"差几门"的说法都要标注数据来源。

---

## 四、根因诊断（五层，按优先级）

### R1 目标函数漂移（方法论，最致命）
战役前 37 波用 CS 排序，Wave 38 之后偷换成"双达标 + 面板逐项占优"的字典序比较，**等于删除了 `(1−0.04×Op)` 复杂度惩罚和 `(1−PC²)` 相关性惩罚**。于是局部爬山持续选择"用 PC 余量换 +0.01~0.04 Sharpe"的伪进步。这是典型的 Goodhart 定律。
→ **修复**：此后每一波必须报告 CS；`CS ≤ 0.6605` 的候选一律不得登记为新王，除非能证明其 CS 下降来自口径校准而非质量劣化。op 不设硬上限，但若 op 增加而 Sharpe/2Y 增益 < 0.05，判为伪进步。

### R2 PC 余量是唯一的"自由度货币"，被当成免费资源烧光
实测所有性能杠杆都**同向抬 PC**：窗口轴（w10 0.6914 → w25 0.7670）、幂次轴（p2 0.6848 → p3 0.7177）、decay 轴（d8 0.6957 → d10 0.7000 恰好 FAIL → d12 0.7091 → d16 更高）、新闻腿近端化（nleg10 CLST 0.84 但 PC 0.7521）、量比换血。到 W49 三轴全部贴墙，上一轮 Agent 称之为"帕累托前沿闭合 / 数据对穷尽"——**这是自锁，不是穷尽**：是主动走到 PC 墙角导致的。
→ **修复**：设硬安全边际 `PC ≤ 0.66`。任何新机制先问"它挣 PC 余量还是花 PC 余量"。正确顺序是**先挣余量（R3），再花余量（R4）**；上一轮做反了。

### R3 信号本体从未被动过（经济学根因，最深）
49 波全部在改：外壳（group_rank / 双层嵌套秩 / group_neutralize）、平滑（ts_mean / ts_decay_linear / ts_decay_exp_window）、权重（signed_power）、确认腿字段（top20 / top5 / 250d / 新闻 / 轧空 / 特质动量）。

**从未修改 belief 腿 `subtract(vec_avg(tx_20d), vec_avg(tx_60d))` 的稀疏结构。** 在多数标的过去 20/60 天均无内部人交易时该值恒为 0，乘以确认腿后仍为 0 → 截面上大面积并列零值 → `group_rank` ties 偏态 → 有效持仓宽度被浪费 → L/S 失衡（549/465 → 601/417）→ Sharpe 与 CLUSTER 同时封顶。PM 处方早就指出这一点，但 W38 把药下在"截面 rank 化"上，而 rank 化抹掉了事件脉冲幅度（铁律B），被实证证伪。

→ **主攻方向（以下只是经济学假设，不是可套用模板，表达式必须你手工构造）**：
1. **相对化而非差分**：把 20d/60d 的绝对差改为相对于长周期基准的比率/偏离度（6 大盲区之一 `divide` 结构从未真正攻过）。注意保持幅度，勿做截面 rank。
2. **逐标的时序标准化**：用 `ts_zscore` / `ts_std_dev` 等把"事件脉冲"转成"相对自身历史的异常度"。这与 W38 证伪的**截面** rank 化不同——时序标准化保留幅度信息，且能激活大量标的的非零值。
3. **改变向量聚合口径**：`vec_avg` 之外的合法向量算子（须先查白名单）可能改变零值传播方式；注意 W40 已证 `vec_max ≡ vec_avg`（group_rank 对组内单调变换输出逐位相同），别浪费配额。
4. **长周期连续基准**：`buy_sell_tx_count_ratio_all_250d_filled`（真实存在、coverage 0.8833）作为分母/锚点，而非第三字段的乘性确认腿。W47 的 `nc18_l250` 只是把 60d 换成 250d 做差分（Sh 0.98 弱），**相对化比率版本未测**。
5. **外部腿的正确用法**：W42 证明外部原始幅度直接相乘会被横截面尺度方差淹没（全灭 0.37~0.55）。若用外部数据集，让它做**基准/归一化分母**或**已中心化的有界调制项**，而非乘性幅度。

每条新表达式的验收：报告 `longCount/shortCount` 失衡度是否收窄到 < 50（这是零值结块被缓解的直接证据），以及 PC 是否 ≤ 0.66。

### R4 收益弹性瓶颈（Fitness 根因）
`Fitness = Sharpe × sqrt(|Returns| / max(Turnover, 0.125))`。全战役 TO 6.4~7.3% 全部低于 12.5% 免罚线，**分母从未被利用**；Fit 0.60→0.69 的增益 100% 来自 Ret 3.56→4.38%。要 Fit≥1.0，在 TO≤12.5% 区间需 Sh≈1.58 或 Ret≈8%。
→ **修复顺序**：先在 R3 上把 PC 挣到 ≤0.62（同时提升信号宽度→Sharpe），**再**用尾部幂次 p3~4 / decay 12~16 / 窗口 25~40 去换 Ret 与 Margin。上一轮反过来做，所以每换一点 Ret 就破门。

### R5 checks 口径不可比（验收根因）
见 Step 0。在完成校准前，"全绿还差几门"的结论不可信。

### R6 工程债（会重复踩，写进你的检查清单）
- `create_multi_simulation` 失败时返回 **error payload 而非抛异常** → 重试逻辑必须检测 payload 是否含 `location`。
- `check_multi_simulation` 的 `children` 是 **ID 字符串数组**，不是 dict；完成度必须靠 `fetch_multi_simulation_result` 判定。
- `check_correlation` 平台侧计算需 1~45 分钟，必须后台长等待 + 重试；`max_correlation = 0.7000` 整会 `passes_check=false`（严格小于）。
- 脚本文件方式运行时 `import main` 会解析到脚本所在目录 → 需 `sys.path.insert(0, 'D:/brain-mcp')`；`grep` 管道会缓冲吞输出 → 用 `-u`。
- `group_rank + signed_power((x−0.5),2)` 值域 [0, 0.25]，单股权重远低于 1% → **truncation 0.01/0.025/0.05 结果逐位相同，该轴不 bind**，勿再浪费配额。

---

## 五、已知证伪清单（不要重跑，直接引用证据）

| 已证伪 | 实证 |
|---|---|
| 截面 rank 化消零结块 | W38 全家 Sh 0.31~0.79，L/S 失衡恶化 592/427（铁律B：幅度即信息） |
| `group_neutralize` 外壳 | 第 5 次证毒，Sh 0.31 |
| `trade_when` 门控 / 等权双引擎混合 | W43 全灭（0.15 / 0.02） |
| 双层嵌套秩 × 尾部幂次 | 互斥，CLST 崩到 0.32~0.46 |
| `ts_decay_exp_window` 外层核 | Sh −0.26 毁灭 |
| `ts_decay_linear` | 2Y 1.00 全场最高但 Mgn 9.4 破门 |
| 量比信念换血（H6） | CLST 0.70 未超 0.73，L/S 591/427 恶化 |
| 双重平静（低水平×低波动） | Sh 0.68 |
| top5 置信腿 | 反而抬 PC（0.6848→0.7565） |
| 轧空族 / 特质动量 / 分析师确认 / 新闻正面确认 | W42~44 全灭；唯一幸存外部方向 = 新闻平静度 |
| 外部腿原始幅度直接乘积 | W42 全灭（尺度淹没） |
| 250d 直接替换 60d 差分 | Sh 0.98 弱 |
| decay > 8 / 窗口 > 18 / 幂次 > 2.25 | 全部抬 PC 破门 |

**已知有效部件（可继承）**：`group_rank` 幅度壳（不可替换）；尾部幂次 `signed_power(group_rank(core,subindustry)−0.5, p)` 在**幅度核**上有效（p2→2.25 免费午餐）；新闻平静度 `reverse(ts_mean(negative_score_average_value_3, 20))` 是唯一有效的外部经济假设（但吃 PC 余量）；decay 8；20d−60d 窗口旋转（曾把 2Y 0.68→1.60）；INDUSTRY 中性化。

---

## 六、执行与验收协议

1. **Step 0 校准**（见第三节），先出可比基线表，再动表达式。
2. 之后每波 8 条，全部围绕 **R3 稀疏 belief 腿**；每条 `note` 写明：经济学假设、预期改善的指标、可证伪判据、预判它是挣还是花 PC 余量。
3. 每波结果必须输出统一表格：`tag / alpha_id / Sh / 2Y / Fit / CLST / Ret% / TO% / Mgn / DD% / L/S / RN / PC / CS / OpCount / PC余量`。
4. **真进步判定（三者同时满足）**：`CS > 0.6605` 且 `PC ≤ 0.66` 且 `|L−S| < 50`。只满足 Sh/Fit 单项的，判为伪进步并归档，不得登记新王。
5. **One-Champion-Per-Anchor**：每个锚点只保留一个冠军，双窗口成对验证；不要在同一锚点上堆变体。
6. 每波落盘 `gate1_wave5x_batch.json` + `gate1_wave5x_result_*.json`，同步更新 `campaign_champions.json`（含 CS 字段）、`alpha_experience/USA_1_other.md`、`.workbuddy/memory/<date>.md`。
7. **停止条件**：出现 `CS > 0.6605` 且四门全绿（0 FAIL + 0 WARNING）；或连续 3 波无任何候选满足真进步判定 —— 此时输出书面的结构性结论与数据对迁移建议，不要无限爬山。

### 证据文件位置
- 全部波次处方与结果：`D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats/gate1_wave*_*.json`
- 冠军档案：`.../campaign_champions.json`
- 经验手册（含 11 条沉淀法则）：`D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/alpha_experience/USA_1_other.md`
- 算子白名单：`D:/brain_cli/wqb_cli/brain-kb/operators/ALL_OPERATORS.md`
- brain-mcp 入口：`D:/brain-mcp/main.py`（只读，禁改）
- 工作日志：`.../.workbuddy/memory/2026-11-04.md`

### 最后一句提醒
上一轮最大的教训不是某个表达式失败，而是**把"双达标"当成目标函数，把 PC 余量当免费午餐，然后在自己走到墙角后宣布数据对穷尽**。请从种子重新出发，先挣自由度，再花自由度，并始终用 CS 记账。
