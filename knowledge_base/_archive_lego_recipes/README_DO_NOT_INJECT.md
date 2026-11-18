# ⚠️ 归档区：历史套壳配方（禁止注入 / 禁止照抄）

本目录存放 **已退役的配方型资料**，保留仅供研究复盘与历史溯源。

## 为什么被归档

AEGIS V3.1 反套积木复审确认：这些文件包含**完整可复制的算子套壳公式**，
会让 Agent 跳过「字段物理分布 → 所需数学变换」的推导，直接照抄算子积木，
是「套积木」行为的直接诱导源。它们不在任何运行时链路中（无 .py / role / agent prompt 引用），
但属于「磁盘上的惰性陷阱」——Agent 主动翻仓库时仍会照抄。

## 目录内容

| 文件 | 原路径 | 危害 |
|---|---|---|
| `sample_prompt.md` | `knowledge_base/references/` | 7 处 `enhanced_template` 完整套壳公式（`signed_power(group_zscore(winsorize(...)))` 等） |
| `operator_guidelines.md` | `knowledge_base/references/` | 「B 的安全用法模板」：`factor = 1 + k*b_clip`、`core = A * factor` 等可直接复制的交互范式 |
| `proven_templates.json` | `knowledge_base/` | 4 条冠军骨架（`group_rank(subtract(divide(F, close), ts_mean(...)))` + best_settings + proven_case），外壳全为 `group_rank`，直接违反铁律 B（幅度保留） |

## 使用禁令（硬性）

1. **禁止** 将本目录任何内容注入 System Prompt、任务卡、RAG 语料或批次上下文；
2. **禁止** 在生成变体时复制其中的表达式骨架或参数设置；
3. 如需参考其中的经济学直觉，必须**用自己的话重写为「物理问题 → 变换需求」的因果陈述**，
   再独立从算子签名表（`knowledge_base/operators/user_operators.json`）映射实现；
4. 这些 `proven_case` 的历史指标（Sharpe 2.05 / 2.41）是**过去战役的结果记录**，
   不构成当前生产库低相关性（ProdCorr < 0.65）的保证。

> 算子签名与定义域请查单一事实源：`knowledge_base/operators/user_operators.json`（由 `OperatorRegistry` 动态挂载）。
