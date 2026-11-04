# Gate 2 研究记录 — Margin / Fitness 攻坚（4 批 32 槽，全部实测）

母本：`WjL5Wlxx`（Sh 1.11 / Fit 0.38 / TO 65.48% / Mgn 2.36bps / Ret 7.74%，warn ×3，fail 0）

## 0. 把要求写成恒等式（后续所有判断的依据）

```
Fitness = Sh × sqrt(Ret / max(TO, 0.125))
Margin(bps) = Ret × 10000 / (504 × TO)
```

- Margin ≥ 15bps ⇔ `Ret/TO ≥ 0.756`（母本 0.118，差 6.4 倍）
- 若 TO = 8%、Ret = 6%：Margin 14.9bps、Fitness = Sh×0.693 → Sh ≥ 1.44 即可 Fit ≥ 1.0（而 Sh 硬门槛 1.58）
- 若 TO = 10.4%、Ret = 2.75%（实测 A1 最松档）：Margin 5.28bps —— 平滑方向错误

## 1. Batch n4 — news12 累积视界（8 槽，已证伪）

`reverse(rank(ts_sum(reaction, N)))`，N = 3/5/10/20 + 4 个正交压迫口径。

| N | Sh | TO | Margin | Ret |
|---|---|---|---|---|
| 3 | 0.75 | 42.97% | 1.89 | 4.07% |
| 5 | 0.54 | 33.46% | 1.74 | 2.91% |
| 10 | 0.00 | 21.16% | 0.01 | 0.01% |
| 20 | −0.01 | 13.89% | −0.09 | −0.06% |

**结论：`Ret/TO` 恒定 0.095~0.118 → news12 每笔收益结构性锁死 ≈2bps，延长视界对 Margin 无效。**
（VWAP 口径 0.08 / ATR 归一 0.05 / CLV 累积 −0.28 且触发 UNITS 警告）

## 2. Batch A1 — 分析师族平滑视界（8 槽）

冻结母本 settings（STATISTICAL / decay 18 / trunc 0.08），只改表达式内 `ts_decay_linear`：

| 视界 | Sh | TO | Margin | Ret | Fit |
|---|---|---|---|---|---|
| 3（母本 vROQVzlA） | 1.86 | 20.55% | 6.82 | 7.00% | 1.09 |
| 15 | 1.20 | 14.09% | 5.64 | 3.97% | 0.64 |
| 25 | 0.96 | 12.02% | 5.20 | 3.13% | 0.48 |
| 40 | 0.85 | 10.39% | 5.28 | 2.75% | 0.40 |

**结论：Ret 衰减快于 TO（Ret/TO 0.341→0.265），Margin 随平滑单调下降。**（8/8 出现 IS_LADDER_SHARPE fail）

## 3. Batch A2 — M&A 目标概率（news/NLP 派生，8 槽）

| 槽 | Sh | TO | Margin |
|---|---|---|---|
| 概率 × 估值（便宜的目标） | **0.39** | 4.55% | **13.08bps** |
| 概率 ÷ 信用质量 | 0.31 | 5.53% | 7.32 |
| 概率 ÷ 估值（镜像对照） | −0.25 | 7.92% | −4.77 |

**结论：Margin 物理可解（13bps 已达 15 的量级），但 Sharpe 上限 0.39；方向性被镜像对照确认。**

## 4. Batch A3 — bucket 迟滞带（8 槽，平台不支持）

`bucket(group_rank(...), range="0,1,0.2")` → **8/8 TO = 0.0%、Sh = 0.00**（持仓完全不动）。
bucket 在本平台不产出可交易数值。已写入 `FALS_OP_001`。

## 5. 已测前沿（本账户 60+ 槽）

| 家族 | 最高 Sh | 该点 Margin | Ret/TO |
|---|---|---|---|
| 分析师粘性目标价 | **1.86** | 6.82 | 0.341 |
| news12 事件反应 | 1.37 | 2.4 | 0.118 |
| M&A 目标概率 | 0.39 | 13.08 | 0.656 |
| 新闻文本情感（3 源） | ≤0.62 | — | — |

要求点（Sh ≥1.58 且 Margin ≥15bps 且 Fit ≥1.0 且零警告）落在该前沿之外：
Sharpe 最强的族 Margin 只有 6.8bps，Margin 达标的族 Sharpe 只有 0.39。

## 6. 仍未被验证的两条轴

1. **宇宙 / 中性化网格**：TOP500、TOP3000、trunc 0.05、INDUSTRY↔STATISTICAL —— 直接改 Ret/TO 的分母结构。
2. **软阈值挤压**（quote-free 迟滞带）：`divide(group_rank(x,sector)−0.5, |·|+b)`，b=0.1/0.2/0.3，
   只用 divide/subtract/add/abs，无平台风险，可近似 bucket 想做的事。

产物：`prescription_n4.py`(news 侧)、`prescription_a1~a3.py`、`batch_*_result.json`、`run_*.log`、
`falsified_vault.json` 新增 `FALS_NEWS12_008 / FALS_NEWS_TEXT_001 / FALS_MARGIN_001 / FALS_MARGIN_002 / FALS_OP_001`。
