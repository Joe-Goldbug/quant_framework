# GLB Delay 1 dl_riskfree_returns 数据集历史复盘归档 (Post-Mortem Archive)

> 注：本文件仅归档针对特定数据集 `GLB/MINVOL10M/dl_riskfree_returns` 的历史实证复盘结论，不作跨数据集默认先验，也不作为通用 RAG 探索启发注入其他数据集。任何「数据集穷尽/饱和」裁决仅能由 `AntiLazinessAuditor.evaluate_exhaustion_gate()` 结合实测有效秩 $C_{\text{eff}}$ 统一签发。

### 【复盘 A】单一 CNN 图像编码数据集的 ProdCorr 方差结构实测
- 57 个 MATRIX 字段若均源自同一 OHLCV 网络前向预测的单调编码，纯截面线性变换与期限斜率容易收敛至相近的主成分（实测 ProdCorr 落在 0.7229 ~ 0.8142 区间）。
- 原先曾记录：“若三轴各做 7 个单变量实验后 ProdCorr 最小值仍高于目标 0.07 以上，则该数据集在当前配置下趋于饱和。”（该判断仅限本特定数据集复盘，严禁外推到其他数据集）。

### 【复盘 B】`dl_riskfree_returns` 71 次回测拓扑轨迹与阈值权衡
- 实测轨迹：Δ10 微分 PC 0.694 / Margin 6.11bps；二阶曲率 PC 0.7707 / Margin 22.83bps；双轴确认 PC 0.7801 / Margin 21.14bps；短端斜率 PC 0.8029 / Margin 27.00bps；裸斜率 PC 0.8136 / Margin 27.20bps；rank 曲率 PC 0.9214。
- 物理结论：在本特定数据集与 `MINVOL10M` 宇宙下，ProdCorr 与 Margin 呈现强负权衡；任何将 Margin 抬至 >= 15bps 的慢速构造趋向共享低波/质量主成分，而高频微分使 Margin 低于 7bps。

### 【复盘 C】催化剂门控 (`trade_when`) 对该 CNN 数据集的实证结果
- 同向二桶信念修正 Δ20 配合同向催化剂门控可将 ProdCorr 由 0.6256 压降至 0.5453（S 1.77 / F 0.89 / 2Y 1.59 / 0 FAIL / Self 0.0），但受限于 `margin_bps ≈ 20 × returns / turnover` 结构，Margin 约为 5bps。
- 在 `GLB/MINVOL10M` 上该特定数据集呈现「ProdCorr 可通过门控解耦、但高 Margin 门槛受限」的特定形态。
