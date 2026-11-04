"""
build_batches.py — USA/D1/TOP1000 other566 campaign: 10 batches x 8 expressions.

Design contract (user-specified + AEGIS doctrine):
  * 2 <= distinct dataset fields per expression <= 3
  * operator count <= 6 (AEGIS hard ceiling)
  * every expression has a stated economic hypothesis (see ideas.md)
  * >= 40% of outer layers are NON-rank (group_zscore / group_neutralize) — Iron Law B
  * each mechanism family is probed on a paired window (N and 2N) — dual-window plateau probe

SIGN-SAFETY NOTES (critical for other566):
  * `*_prob` fields described as "log-probabilities" are NEGATIVE in level:
      oth566_l2r20_prob, oth566_l5r20gasfculr_prob_3, oth566_l5r20gasfculr_prob_5
    -> never multiplied raw with a directional leg; only used via ts_zscore / ts_delta,
       or via group_rank(prob, group) which maps to a strictly positive weight.
  * all other `*_prob` fields are "confidence score" in [0,1] -> safe to multiply raw.
  * ordinal `*_label` fields are bucket codes on unknown scales -> always ts_zscore'd
    before any subtraction, and never compared raw across bucket schemes.
"""

import json
import os

# ---- field shorthands -------------------------------------------------------
R_RET      = "oth566_r20marsi_ret"          # continuous fwd return, R20MaRsi (71u/90a, crowded)
R_P5       = "oth566_r20marsi_prob_5"       # confidence score [0,1]  (1u/1a, cold)
R_P3       = "oth566_r20marsi_prob_3"       # confidence score [0,1]  (4u/4a)
R_L5       = "oth566_r20marsi_label_5"      # 5-bucket ordinal label (5u/8a)
R_L3       = "oth566_r20marsi_label_3"      # 3-bucket ordinal label (19u/24a)

L2R5       = "oth566_l2r5_label"            # Level2 5d label (29u/40a)
L2R5P      = "oth566_l2r5_prob"             # Level2 5d confidence (1u/1a)
L2R5RES    = "oth566_l2r5res_label"         # Level2 Res (residualized) 5d label (21u/25a)
L2R5RESP   = "oth566_l2r5res_prob"          # Level2 Res 5d confidence (1u/1a)
L2R20      = "oth566_l2r20_label"           # Level2 20d label (26u/36a)
L2R20P     = "oth566_l2r20_prob"            # Level2 20d LOG-PROB (negative) (11u/11a)

L3R5       = "oth566_l3r5_label"            # Level3 5d label (32u/40a)
L3R5P      = "oth566_l3r5_prob"             # Level3 5d confidence (1u/1a)
L3R20      = "oth566_l3r20_label"           # Level3 20d label (6u/9a)
L3R20P     = "oth566_l3r20_prob"            # Level3 20d confidence (6u/6a)
L3R20G     = "oth566_l3r20gasf_label"       # L3 Gasf 20d label (1u/4a)
L3R20GP    = "oth566_l3r20gasf_prob"        # L3 Gasf 20d confidence (1u/1a)
L3R20GM    = "oth566_l3r20gasfmulti_label"  # L3 GasfMulti 20d label (11u/14a)
L3R20GMP   = "oth566_l3r20gasfmulti_prob"   # L3 GasfMulti 20d confidence (0u/0a)
GM_PP      = "oth566_l3r20gasfmulti_prob_pattern"        # 0u/0a — coldest
GM_LP      = "oth566_l3r20gasfmulti_prob_last_pattern"   # 0u/0a — coldest

L5R20      = "oth566_l5r20_label"           # Level5 20d label (3u/7a)
L5R20P     = "oth566_l5r20_prob"            # Level5 20d confidence (1u/1a)
L5C_RET    = "oth566_l5r20gasfculr_ret"     # L5 GasfCulr continuous 20d return (13u/17a)
L5C_L3     = "oth566_l5r20gasfculr_label_3" # L5 GasfCulr 3-bucket label (6u/11a)
L5C_L5     = "oth566_l5r20gasfculr_label_5" # L5 GasfCulr 5-bucket label (5u/8a)
L5C_P3     = "oth566_l5r20gasfculr_prob_3"  # L5 GasfCulr 3-bucket LOG-PROB (1u/1a)
L5C_P5     = "oth566_l5r20gasfculr_prob_5"  # L5 GasfCulr 5-bucket LOG-PROB (0u/0a)
L5C_PATP   = "oth566_l5r20gasfculr_prob_pattern"  # pattern confidence (0u/0a)

ML2        = "oth566_multil2_label"         # multi-horizon L2 label (4u/9a)
ML2P       = "oth566_multil2_prob"          # multi-horizon L2 confidence (3u/3a)
ML3        = "oth566_multil3_label"         # multi-horizon L3 label (2u/6a)
ML3P       = "oth566_multil3_prob"          # multi-horizon L3 confidence (9u/9a)
ML3_PP     = "oth566_multil3_prob_pattern"  # 2u/2a
ML3_PLP    = "oth566_multil3_prob_last_pattern"  # 0u/0a

LAB2       = "oth566_label2"                # multi-horizon 2d label (8u/12a)
LAB_2      = "oth566_label_2"               # R20MaRsi 2d label (9u/12a)
PROB_2     = "oth566_prob_2"                # R20MaRsi 2d confidence (1u/1a)
PROBL2     = "oth566_probl2"                # multi-horizon 2d confidence (1u/1a)
RET2       = "oth566_return"                # continuous 2d fwd return (39u/55a)

FB_L3      = "five_bucket_return_rank_label_l3"      # 5-bucket 3d rank label (21u/26a)
FB_C_L3    = "five_bucket_return_rank_confidence_l3" # 5-bucket 3d confidence (0u/0a)
TB_L3      = "twenty_bucket_return_rank_label_l3"    # 20-bucket 3d rank label (6u/9a)
TB_C_L3    = "twenty_bucket_return_rank_confidence_l3"  # 20-bucket 3d confidence (4u/4a)
TB_L5      = "twenty_bucket_return_rank_label_l5"    # 20-bucket 5d rank label (2u/5a)
TB_C_L5    = "twenty_bucket_return_rank_confidence_l5"  # 20-bucket 5d confidence (2u/2a)

# ---- building blocks --------------------------------------------------------
def zw(x, d=60):   return f"ts_zscore({x}, {d})"
def dl(x, d):       return f"ts_delta({x}, {d})"
def tm(x, d=26):   return f"ts_mean({x}, {d})"
def gr(x, g="subindustry"): return f"group_rank({x}, {g})"
def gz(x, g="industry"):    return f"group_zscore({x}, {g})"
def gn(x, g="subindustry"): return f"group_neutralize({x}, {g})"
def cw(x, g="industry"):    return f"group_rank({x}, {g})"   # positive confidence weight

# ---- the 10 batches ---------------------------------------------------------
BATCHES = []

BATCHES.append({
 "batch": 1, "family": "confidence_weighted_point_forecast",
 "hypothesis": "信念加权的点预测: 把「模型预测了多少」转为「模型有多确定」。R20MaRsi 的连续预测水平是全数据集最拥挤用法(71u/90a), 乘以冷门置信腿(1u/1a)既保留预测力又大幅去拥挤, 并自动收缩低信念个股上的死重仓位。5 个模型家族各测一次以检验跨信息集的可迁移性; 26/52 双窗口 + group_neutralize/group_zscore 非秩外层构成参数高原与幅度保留探针。",
 "items": [
  {"id": "b1_m1", "expr": f"{gr(tm(f'multiply({R_RET}, {R_P5})'))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b1_m2", "expr": f"{gr(tm(f'multiply({R_RET}, {R_P5})', 52))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b1_m3", "expr": f"{gn(tm(f'multiply({R_RET}, {R_P5})'))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b1_m4", "expr": f"{gz(tm(f'multiply({R_RET}, {R_P5})'))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b1_m5", "expr": f"{gr(tm(f'multiply({L5C_RET}, {cw(L5C_PATP)})'))}", "ops": 4, "fields": [L5C_RET, L5C_PATP]},
  {"id": "b1_m6", "expr": f"{gr(tm(f'multiply({zw(ML3)}, {cw(ML3P)})'))}", "ops": 4, "fields": [ML3, ML3P]},
  {"id": "b1_m7", "expr": f"{gr(tm(f'multiply({zw(L3R5)}, {cw(L3R5P)})'))}", "ops": 4, "fields": [L3R5, L3R5P]},
  {"id": "b1_m8", "expr": f"{gr(tm(f'multiply({zw(TB_L5)}, {cw(TB_C_L5)})'))}", "ops": 4, "fields": [TB_L5, TB_C_L5]},
 ]})

BATCHES.append({
 "batch": 2, "family": "forecast_revision_information_shock",
 "hypothesis": "预测修正即信息冲击: 分析师评级上调的横截面定价效应是稳健异象, 本数据集的 ts_delta 是机构观点修正的机器版本。修正量是增量信息而非水平, ProdCorr 显著更低。5/1/10 日三档差分窗口扫描最优冲击吸收速度; 对数概率字段一律走 ts_delta/ts_zscore 以规避符号陷阱。",
 "items": [
  {"id": "b2_r5",  "expr": f"{gr(tm(f'multiply({dl(R_RET, 5)}, {R_P5})'))}", "ops": 4, "fields": [R_RET, R_P5]},
  {"id": "b2_r5w", "expr": f"{gr(tm(f'multiply({dl(R_RET, 5)}, {R_P5})', 52))}", "ops": 4, "fields": [R_RET, R_P5]},
  {"id": "b2_r1",  "expr": f"{gr(tm(f'multiply({dl(R_RET, 1)}, {R_P5})'))}", "ops": 4, "fields": [R_RET, R_P5]},
  {"id": "b2_r10", "expr": f"{gr(tm(f'multiply({dl(R_RET, 10)}, {R_P5})'))}", "ops": 4, "fields": [R_RET, R_P5]},
  {"id": "b2_ret2","expr": f"{gr(tm(f'multiply({dl(RET2, 5)}, {cw(PROB_2)})'))}", "ops": 4, "fields": [RET2, PROB_2]},
  {"id": "b2_l5rev","expr": f"{gr(tm(f'multiply({dl(L5C_RET, 5)}, {cw(L5C_PATP)})'))}", "ops": 4, "fields": [L5C_RET, L5C_PATP]},
  {"id": "b2_lp5", "expr": f"{gr(tm(f'multiply({dl(L5C_P5, 20)}, {zw(L5C_RET)})'))}", "ops": 5, "fields": [L5C_P5, L5C_RET]},
  {"id": "b2_ml3", "expr": f"{gr(tm(f'multiply({dl(ML3P, 20)}, {zw(ML3)})'))}", "ops": 5, "fields": [ML3P, ML3]},
 ]})

BATCHES.append({
 "batch": 3, "family": "cross_model_consensus_ensemble",
 "hypothesis": "跨模型共识与集成方差削减: 两个训练信息集正交的模型等权合成, 联合信噪比高于任一单腿 ('wisdom of crowds'), 且因拥挤度差异极大不易撞生产库。覆盖订单簿深度对 (L2/L3)、多期限对 (multiL2/multiL3)、技术vs订单簿、残差化 vs 原始 L2、Gasf vs GasfMulti、L5 模型 vs L5 GasfCulr 六组独立配对。",
 "items": [
  {"id": "b3_c1", "expr": f"{gr(tm(f'add({zw(R_RET)}, {zw(L5C_RET)})'))}", "ops": 5, "fields": [R_RET, L5C_RET]},
  {"id": "b3_c1w","expr": f"{gr(tm(f'add({zw(R_RET)}, {zw(L5C_RET)})', 52))}", "ops": 5, "fields": [R_RET, L5C_RET]},
  {"id": "b3_c2", "expr": f"{gr(tm(f'add({zw(L2R5)}, {zw(L3R5)})'))}", "ops": 5, "fields": [L2R5, L3R5]},
  {"id": "b3_c3", "expr": f"{gr(tm(f'add({zw(L2R20)}, {zw(L3R20)})'))}", "ops": 5, "fields": [L2R20, L3R20]},
  {"id": "b3_c4", "expr": f"{gr(tm(f'add({zw(ML2)}, {zw(ML3)})'))}", "ops": 5, "fields": [ML2, ML3]},
  {"id": "b3_c5", "expr": f"{gr(tm(f'add({zw(L2R5RES)}, {zw(L2R5)})'))}", "ops": 5, "fields": [L2R5RES, L2R5]},
  {"id": "b3_c6", "expr": f"{gr(tm(f'add({zw(L3R20G)}, {zw(L3R20GM)})'))}", "ops": 5, "fields": [L3R20G, L3R20GM]},
  {"id": "b3_c7", "expr": f"{gr(tm(f'add({zw(L5R20)}, {zw(L5C_RET)})'))}", "ops": 5, "fields": [L5R20, L5C_RET]},
 ]})

BATCHES.append({
 "batch": 4, "family": "cross_model_disagreement_relative_value",
 "hypothesis": "模型间分歧的相对价值: 当两个信息集结论相反时必有一方信息滞后。先验: 订单簿深度 (L5>L3>L2) 权威性高于技术指标模型。以深减浅交易「浅模型相对过度乐观」的修正, 对市场整体方向免疫并把权重集中在分歧最大的个股。组内跨五种分歧对以检验「信息深度单调性」是否成立 (若成立则机制可信, 若反转则说明收益来自久期差异)。",
 "items": [
  {"id": "b4_d1", "expr": f"{gr(tm(f'subtract({zw(L5C_RET)}, {zw(R_RET)})'))}", "ops": 5, "fields": [L5C_RET, R_RET]},
  {"id": "b4_d1w","expr": f"{gr(tm(f'subtract({zw(L5C_RET)}, {zw(R_RET)})', 52))}", "ops": 5, "fields": [L5C_RET, R_RET]},
  {"id": "b4_d2", "expr": f"{gr(tm(f'subtract({zw(L5R20)}, {zw(L3R20)})'))}", "ops": 5, "fields": [L5R20, L3R20]},
  {"id": "b4_d3", "expr": f"{gr(tm(f'subtract({zw(L3R20)}, {zw(L2R20)})'))}", "ops": 5, "fields": [L3R20, L2R20]},
  {"id": "b4_d4", "expr": f"{gr(tm(f'subtract({zw(ML3)}, {zw(ML2)})'))}", "ops": 5, "fields": [ML3, ML2]},
  {"id": "b4_d5", "expr": f"{gr(tm(f'subtract({zw(R_L5)}, {zw(L5C_L5)})'))}", "ops": 5, "fields": [R_L5, L5C_L5]},
  {"id": "b4_d6", "expr": f"{gr(tm(f'subtract({zw(L3R20GM)}, {zw(L3R20G)})'))}", "ops": 5, "fields": [L3R20GM, L3R20G]},
  {"id": "b4_d7", "expr": f"{gr(tm(f'subtract({zw(L2R5RES)}, {zw(L2R5)})'))}", "ops": 5, "fields": [L2R5RES, L2R5]},
 ]})

BATCHES.append({
 "batch": 5, "family": "term_structure_of_model_expectations",
 "hypothesis": "模型预期的期限结构: 债券定价的预期假说是有百年实证基础的强机制, 本数据集天然提供 2/3/5/20 日前向预测, 可直接迁移到股票横截面。短端乐观而中端悲观 = 反趋势反弹的典型特征。5 组期限斜率对 + 1 组分桶粒度对 (5桶 vs 3桶) 检验「被压缩掉的分布形状信息」。所有标签先各自 ts_zscore 定心定标, 直接相减必是伪信号。",
 "items": [
  {"id": "b5_t1", "expr": f"{gr(tm(f'subtract({zw(R_L5)}, {zw(L5C_L5)})'))}", "ops": 5, "fields": [R_L5, L5C_L5]},
  {"id": "b5_t2", "expr": f"{gr(tm(f'subtract({zw(R_L3)}, {zw(R_L5)})'))}", "ops": 5, "fields": [R_L3, R_L5]},
  {"id": "b5_t3", "expr": f"{gr(tm(f'subtract({zw(R_L3)}, {zw(L5C_L3)})'))}", "ops": 5, "fields": [R_L3, L5C_L3]},
  {"id": "b5_t4", "expr": f"{gr(tm(f'subtract({zw(L5C_L5)}, {zw(L5C_L3)})'))}", "ops": 5, "fields": [L5C_L5, L5C_L3]},
  {"id": "b5_t5", "expr": f"{gr(tm(f'subtract({zw(LAB_2)}, {zw(R_L3)})'))}", "ops": 5, "fields": [LAB_2, R_L3]},
  {"id": "b5_t6", "expr": f"{gr(tm(f'subtract({zw(R_L3)}, {zw(L5R20)})'))}", "ops": 5, "fields": [R_L3, L5R20]},
  {"id": "b5_t7", "expr": f"{gr(tm(f'subtract({zw(TB_L5)}, {zw(TB_L3)})'))}", "ops": 5, "fields": [TB_L5, TB_L3]},
  {"id": "b5_t8", "expr": f"{gr(tm(f'subtract({zw(ML3)}, {zw(L3R20)})'))}", "ops": 5, "fields": [ML3, L3R20]},
 ]})

BATCHES.append({
 "batch": 6, "family": "conviction_migration_regime_break",
 "hypothesis": "形态信念迁移 = 格局突破代理: 本数据集最冷门的一对字段 (0 用户/0 alpha), 机制上最接近信息到达的可观测量。当前形态置信度与最近形态置信度之差刻画模型信念从旧形态迁移到新检测形态的速度。两个独立形态检测器 (multiL3 与 GasfMulti) 同时报告迁移 = 真实微观结构事件而非算法假象 (机制复现性检验)。",
 "items": [
  {"id": "b6_m1", "expr": f"{gr(tm(f'subtract({zw(ML3_PP)}, {zw(ML3_PLP)})'))}", "ops": 5, "fields": [ML3_PP, ML3_PLP]},
  {"id": "b6_m2", "expr": f"{gr(tm(f'subtract({zw(GM_PP)}, {zw(GM_LP)})'))}", "ops": 5, "fields": [GM_PP, GM_LP]},
  {"id": "b6_m3", "expr": f"{gr(tm(f'subtract({zw(ML3_PP)}, {zw(ML3_PLP)})', 52))}", "ops": 5, "fields": [ML3_PP, ML3_PLP]},
  {"id": "b6_m4", "expr": f"{gr(tm(f'multiply({zw(L5C_PATP)}, {zw(L5C_RET)})'))}", "ops": 5, "fields": [L5C_PATP, L5C_RET]},
  {"id": "b6_m5", "expr": f"{gr(tm(f'multiply({zw(ML3_PP)}, {zw(ML3)})'))}", "ops": 5, "fields": [ML3_PP, ML3]},
  {"id": "b6_m6", "expr": f"{gr(tm(f'multiply({zw(GM_PP)}, {zw(L3R20GM)})'))}", "ops": 5, "fields": [GM_PP, L3R20GM]},
  {"id": "b6_m7", "expr": f"{gr(tm(f'subtract({zw(GM_PP)}, {zw(GM_LP)})', 52))}", "ops": 5, "fields": [GM_PP, GM_LP]},
  {"id": "b6_m8", "expr": f"{gr(tm(f'multiply({dl(L3R20GMP, 20)}, {zw(L3R20GM)})'))}", "ops": 5, "fields": [L3R20GMP, L3R20GM]},
 ]})

BATCHES.append({
 "batch": 7, "family": "freshness_gating_trade_when",
 "hypothesis": "预测新鲜度门控: other566 模型每日重训重估, 但多数个股预测数日内不变。跟随未变化的预测是纯换手噪音。trade_when 只在信息真正到达 (预测发生变化) 时更新持仓, 事件之间冻结 = 信念持有, 与「分析师评级上调后持有 N 日」的事件驱动逻辑同构。8 个槽位分别对不同更新条件 (预测变 / 置信变) 与不同信号腿 (水平 / 修正) 交叉, 以确定最优门控对象。",
 "items": [
  {"id": "b7_t1", "expr": f"{gr(f'trade_when(not_equal({dl(R_RET, 1)}, 0), multiply({R_RET}, {R_P5}), -1)')}", "ops": 5, "fields": [R_RET, R_P5]},
  {"id": "b7_t2", "expr": f"{gr(f'trade_when(not_equal({dl(R_RET, 5)}, 0), multiply({R_RET}, {R_P5}), -1)')}", "ops": 5, "fields": [R_RET, R_P5]},
  {"id": "b7_t3", "expr": f"{gr(f'trade_when(not_equal({dl(L5C_RET, 1)}, 0), multiply({zw(L5C_RET)}, {cw(L5C_PATP)}), -1)')}", "ops": 6, "fields": [L5C_RET, L5C_PATP]},
  {"id": "b7_t4", "expr": f"{gr(f'trade_when(not_equal({dl(ML3, 1)}, 0), multiply({zw(ML3)}, {cw(ML3P)}), -1)')}", "ops": 6, "fields": [ML3, ML3P]},
  {"id": "b7_t5", "expr": f"{gr(f'trade_when(not_equal({dl(L3R5P, 1)}, 0), multiply({L3R5}, {cw(L3R5P)}), -1)')}", "ops": 6, "fields": [L3R5, L3R5P]},
  {"id": "b7_t6", "expr": f"{gr(f'trade_when(not_equal({dl(R_P5, 1)}, 0), multiply({R_RET}, {R_P5}), -1)')}", "ops": 5, "fields": [R_RET, R_P5]},
  {"id": "b7_t7", "expr": f"{gr(f'trade_when(not_equal({dl(L5C_RET, 1)}, 0), multiply({dl(L5C_RET, 5)}, {cw(L5C_PATP)}), -1)')}", "ops": 6, "fields": [L5C_RET, L5C_PATP]},
  {"id": "b7_t8", "expr": f"{gr(f'trade_when(not_equal({dl(RET2, 1)}, 0), multiply({dl(RET2, 5)}, {cw(PROB_2)}), -1)')}", "ops": 6, "fields": [RET2, PROB_2]},
 ]})

BATCHES.append({
 "batch": 8, "family": "magnitude_preservation_non_rank_outer",
 "hypothesis": "幅度保留 (铁律 B): group_rank 把极端幅度拍平, 使因子间相关性飙升且 Margin 受损; group_zscore/group_neutralize 保留连续形态, 同等 Sharpe 下 Margin (bps) 通常提升 50%~100%, 且保留的幅度使生产库共线性暴露更分散。本批 8 槽位把 B1/B3/B4/B6 的四个核心机制各做一次 group_zscore 与 group_neutralize 对照, 验证非秩外层是否真的换来更低 ProdCorr 与更高 Margin。",
 "items": [
  {"id": "b8_z1", "expr": f"{gz(tm(f'multiply({zw(ML3)}, {cw(ML3P)})'))}", "ops": 4, "fields": [ML3, ML3P]},
  {"id": "b8_n1", "expr": f"{gn(tm(f'multiply({zw(ML3)}, {cw(ML3P)})'))}", "ops": 4, "fields": [ML3, ML3P]},
  {"id": "b8_z2", "expr": f"{gz(tm(f'multiply({R_RET}, {R_P5})'))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b8_n2", "expr": f"{gn(tm(f'multiply({R_RET}, {R_P5})'))}", "ops": 3, "fields": [R_RET, R_P5]},
  {"id": "b8_z3", "expr": f"{gz(tm(f'add({zw(L2R5)}, {zw(L3R5)})'))}", "ops": 5, "fields": [L2R5, L3R5]},
  {"id": "b8_n3", "expr": f"{gn(tm(f'add({zw(R_RET)}, {zw(L5C_RET)})'))}", "ops": 5, "fields": [R_RET, L5C_RET]},
  {"id": "b8_z4", "expr": f"{gz(tm(f'subtract({zw(L5C_RET)}, {zw(R_RET)})'))}", "ops": 5, "fields": [L5C_RET, R_RET]},
  {"id": "b8_n4", "expr": f"{gn(tm(f'subtract({zw(ML3_PP)}, {zw(ML3_PLP)})'))}", "ops": 5, "fields": [ML3_PP, ML3_PLP]},
 ]})

BATCHES.append({
 "batch": 9, "family": "confidence_weighted_grid_horizon",
 "hypothesis": "置信加权网格探针: 把 B1 胜出的「标准化方向 x 行业内正信念权重」结构铺到 8 个不同字段对上, 每对都用 26/52 窗口配对, 以确认该机制是普适结构而非 R20MaRsi 个例。含 log-prob 字段 (L2R20P/L5C_P3) 的处理 — 因其水平为负, 必须经 ts_zscore 定心或 group_rank 化为正权重, 绝不可裸乘。",
 "items": [
  {"id": "b9_g1",  "expr": f"{gr(tm(f'multiply({zw(R_L5)}, {cw(R_P5)})'))}", "ops": 4, "fields": [R_L5, R_P5]},
  {"id": "b9_g2",  "expr": f"{gr(tm(f'multiply({zw(R_L5)}, {cw(R_P5)})', 52))}", "ops": 4, "fields": [R_L5, R_P5]},
  {"id": "b9_g3",  "expr": f"{gr(tm(f'multiply({zw(L3R5)}, {cw(L3R5P)})'))}", "ops": 4, "fields": [L3R5, L3R5P]},
  {"id": "b9_g4",  "expr": f"{gr(tm(f'multiply({zw(L3R5)}, {cw(L3R5P)})', 52))}", "ops": 4, "fields": [L3R5, L3R5P]},
  {"id": "b9_g5",  "expr": f"{gr(tm(f'multiply({zw(L2R20)}, {cw(L2R20P)})'))}", "ops": 4, "fields": [L2R20, L2R20P]},
  {"id": "b9_g6",  "expr": f"{gr(tm(f'multiply({zw(L5C_L3)}, {cw(L5C_P3)})'))}", "ops": 4, "fields": [L5C_L3, L5C_P3]},
  {"id": "b9_g7",  "expr": f"{gr(tm(f'multiply({zw(TB_L3)}, {cw(TB_C_L3)})'))}", "ops": 4, "fields": [TB_L3, TB_C_L3]},
  {"id": "b9_g8",  "expr": f"{gr(tm(f'multiply({zw(FB_L3)}, {cw(FB_C_L3)})'))}", "ops": 4, "fields": [FB_L3, FB_C_L3]},
 ]})

# Batch 10 is generated separately (cross-dataset) — see build_cross_batch.py
if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    meta = {
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "other",
        "dataset": "other566", "neutralization": "INDUSTRY", "decay": 4,
        "truncation": 0.08, "pasteurization": "ON", "nan_handling": "ON",
        "batches": [b for b in BATCHES],
    }
    for b in BATCHES:
        p = os.path.join(out_dir, f"batch_{b['batch']:02d}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "batches_01_09.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(BATCHES)} batches -> {out_dir}")
