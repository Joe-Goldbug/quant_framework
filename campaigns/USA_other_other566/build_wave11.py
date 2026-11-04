"""build_wave11.py — evidence-driven refinement wave after batches 01-09.

EMPIRICAL FINDINGS that drive this wave (from batches 01-09, USA/D1/TOP1000,
decay=4, neutralization=INDUSTRY, truncation=0.08):

  F1. `ts_mean(x, 26)` is the single biggest signal killer in this campaign.
      b1_m1 (ts_mean 26) -> Sharpe 0.66 | b1_m2 (ts_mean 52) -> 0.68
      b7_t1 (trade_when, NO ts_mean) -> Sharpe 1.18 with ZERO platform fails.
      The model output is already a daily-recomputed forecast; averaging it
      over 26 days destroys the very revision information that carries alpha.

  F2. The `trade_when` gate is always-true. b7_t1 (delta 1), b7_t2 (delta 5)
      and b7_t6 (delta on prob_5) returned IDENTICAL metrics
      (Sh 1.18 / TO 46.54% / Mgn 1.78bps / PnL 4128731 vs 4128689) => the model
      re-emits its forecast every single day, so "freshness gating" cannot
      fire. The real winner was the *absence of ts_mean*, not the gate.

  F3. Margin is the binding constraint, and it is an arithmetic identity:
      margin_bps = returns / turnover * 20
      => margin >= 10bps  <=>  returns >= 0.5 * turnover
      With turnover 46.5% we need returns >= 23% — unreachable.
      With turnover 10.5% we need returns >= 5.25% — reachable.
      => LOWER TURNOVER IS THE ONLY PATH TO THE MARGIN DEAD LINE.
      b1_m4 group_zscore had the best margin (7.46bps) precisely because it kept
      amplitude instead of flattening it (Iron Law B).

  F4. `group_zscore` > `group_rank` > `group_neutralize` on the SAME core
      (b1_m1/m3/m4): Sharpe 0.81 / 0.61 / 0.66, margin 7.46 / 5.08 / 4.16bps,
      risk_neutralized_sharpe 1.30 / 0.84 / 0.77.
      => Drop ts_mean, switch outer to group_zscore, add amplitude preservation.

  F5. `hump` is the platform's own turnover limiter (validOp: "Limits amount
      and magnitude of changes in input (thus reducing turnover)") and is the
      principled way to satisfy F3 without killing the signal via ts_mean.

  F6. Decay is already 4. Raising decay further trades Sharpe for turnover;
      hump + decay is the complementary lever (amplitude smoothing vs
      position smoothing).

So Wave 11 strips ts_mean from every slot, keeps group_zscore as the primary
outer, and adds hump / ts_decay_linear as turnover levers.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_P3 = "oth566_r20marsi_prob_3"
R_L5 = "oth566_r20marsi_label_5"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"
L2R20 = "oth566_l2r20_label"
L2R20P = "oth566_l2r20_prob"
L5C_RET = "oth566_l5r20gasfculr_ret"
L5C_PATP = "oth566_l5r20gasfculr_prob_pattern"
ML3 = "oth566_multil3_label"
ML3P = "oth566_multil3_prob"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"
TB_L5 = "twenty_bucket_return_rank_label_l5"
TB_C_L5 = "twenty_bucket_return_rank_confidence_l5"

W11 = {
 "batch": 11, "family": "no_tsm_mean_amplitude_preserving_turnover_levers",
 "hypothesis": (
   "波次 11: 依据 B01-B09 的实证诊断重写结构。F1: ts_mean(x,26) 是本战役最大的信号杀手 —— "
   "b1_m1(ts_mean26)=Sh0.66 vs b7_t1(无 ts_mean)=Sh1.18 且平台 0 FAIL, 因为本数据集是逐日重训的预测输出, "
   "26 日平均恰好抹掉了承载 alpha 的修正信息。F2: trade_when 门控恒真 (b7_t1/b7_t2/b7_t6 指标逐位相同), "
   "说明模型每日重发预测, 真正起作用的是「去掉 ts_mean」而非门控本身。F3: Margin 是硬约束且是算术恒等式 "
   "margin_bps = returns/turnover*20, 故 margin>=10bps 等价于 returns>=0.5*turnover —— 唯一出路是降换手。"
   "F4: 同一核心上 group_zscore(Sh0.81/Mgn7.46/RNS1.30) > group_rank > group_neutralize, 印证铁律 B 的幅度保留。"
   "F5: hump 是平台自带的换手限制器 ('Limits amount and magnitude of changes in input'), 是在不牺牲信号的前提下降换手的"
   "正路工具。本波 8 槽位全部剥离 ts_mean, 以 group_zscore 为主外层, 用 hump / ts_decay_linear 作为换手杠杆, "
   "并把置信腿从 group_rank(prob) 换成裸 prob (减少一个算子) 与 ts_zscore(prob) (保留连续幅度) 两路对照。"
 ),
 "items": [
  {"id": "w11_gz_plain", "expr": f"group_zscore(multiply({R_RET}, {R_P5}), industry)",
   "ops": 2, "fields": [R_RET, R_P5],
   "why": "F1+F4 核心: 剥离 ts_mean 的 group_zscore 版。预期在 b1_m4 (Sh0.81) 基础上因去掉 26 日平滑而显著提 Sharpe, 且保留幅度使 Margin 维持 7bps+ 水平。"},
  {"id": "w11_gz_rank", "expr": f"group_rank(multiply({R_RET}, {R_P5}), subindustry)",
   "ops": 2, "fields": [R_RET, R_P5],
   "why": "F1 最小对照: 完全去掉 ts_mean 的 group_rank 版, 与 w11_gz_plain 配对以隔离外层选择的影响 (同骨架、同字段、同置信腿)。"},
  {"id": "w11_gz_neutral", "expr": f"group_neutralize(multiply({R_RET}, {R_P5}), subindustry)",
   "ops": 2, "fields": [R_RET, R_P5],
   "why": "F4 第三点: 同一骨架的 group_neutralize 版, 验证幅度保留排序 (zscore > rank > neutralize) 在剥离 ts_mean 后是否依然成立。"},
  {"id": "w11_gz_hump", "expr": f"group_zscore(hump(multiply({R_RET}, {R_P5}), 0.01), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "F3+F5: hump 是平台自带换手限制器, 直接压 turnover 而非抹掉信号。预期 turnover 从 10.5% 降至 6-8%, 使 returns/turnover 比率上升, Margin 有望突破 10bps 死线。"},
  {"id": "w11_gz_decay_lin", "expr": f"group_zscore(ts_decay_linear(multiply({R_RET}, {R_P5}), 5), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "F5 替代杠杆: ts_decay_linear(5) 线性衰减比 ts_mean(26) 温和得多, 是「轻平滑 vs 强平滑」的中间档, 用于确认最优平滑强度在 1(不平滑)与 26 之间。"},
  {"id": "w11_gz_zret", "expr": f"group_zscore(multiply(ts_zscore({R_RET}, 60), {R_P5}), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "F1+F3: 对预测水平自身做 60 日标准化后再乘裸置信度。这在不抹掉水平信息的前提下剥离了模型的慢漂移 (宏观 regime), 同时保留截面幅度。"},
  {"id": "w11_gz_p3", "expr": f"group_zscore(multiply({R_RET}, {R_P3}), industry)",
   "ops": 2, "fields": [R_RET, R_P3],
   "why": "置信腿替换检验: 用 3 日桶的置信度 (4 用户/4 alpha) 替代 5 日桶 (1 用户/1 alpha), 检验信念加权结构对信念口径的敏感性, 同时略微提 ProdCorr 分母熵。"},
  {"id": "w11_gz_l3r5", "expr": f"group_zscore(multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry)), industry)",
   "ops": 4, "fields": [L3R5, L3R5P],
   "why": "跨模型复制检验: 把 B1 的胜出结构 (标准化方向 x 行业内置信秩) 搬到 Level3 5 日模型 (32 用户/40 alpha 但用的是置信腿 1 用户/1 alpha), 剥离 ts_mean 后验证该结构是否普适而非 R20MaRsi 个例。"},
 ]}

# ---- Wave 12: cross-dataset (other566 + insider_feats), same USA/D1/OTHER theme ----
I_BS20 = "vec_avg(buy_sell_ratio_all_20d_filled)"     # 0 users / 0 alphas
I_BS60 = "vec_avg(buy_sell_ratio_all_60d_filled)"     # 0 users / 0 alphas
I_BS20_TOP20 = "vec_avg(top20_buy_to_sell_txn_ratio_lookback_60_filled)"  # 0/0
I_TXR60 = "vec_avg(buy_sell_tx_count_ratio_all_60d_filled)"  # 0/0

W12 = {
 "batch": 10, "family": "cross_dataset_other566_plus_insider_feats",
 "hypothesis": (
   "波次 10 (跨数据集, 仍在 USA/D1/OTHER 金字塔内): insider_feats 的 category 为 other, 与 other566 同属 "
   "USA/D1/OTHER 金字塔 (乘数 1.4, 且该金字塔当前 0 alpha, 正需点塔), 因此满足 theme 要求。insider_feats 仅 "
   "9 用户/10 alpha, 且所选字段多在 0 用户/0 alpha —— 是全市场最冷的横截面源之一, 天然带来极低 ProdCorr。"
   "经济学机制: 内部人交易 (insider trading) 是信息优势最强、最难被套利的信号源之一 —— 内部人掌握公司基本面"
   "与内部人网络信息, 且交易受法律与声誉约束, 故买卖方向比金额更具信息含量。本波用 3 条机制与 other566 的"
   "订单簿形态预测正交组合: (a) 共识叠加 (两个独立信息集共同看多时信号更强, wisdom of crowds); "
   "(b) 相对价值分歧 (内部人信念 vs 模型预测的分歧, 押注哪一方信息更新); (c) 内部人信念加权的模型预测 "
   "(用内部人方向作为置信权重, 相当于提高模型信念的先验可信度)。每条机制的窗口 20/60 日配对, 外层以 "
   "group_zscore 保留幅度。"
 ),
 "items": [
  {"id": "x10_cons_20", "expr": f"group_zscore(ts_mean(add(ts_zscore({I_BS20}, 60), ts_zscore({R_RET}, 60)), 26), industry)",
   "ops": 4, "fields": ["insider_feats:buy_sell_ratio_all_20d_filled", "other566:r20marsi_ret"],
   "why": "共识叠加: 内部人 20 日买卖比 (标准化) + 模型点预测 (标准化)。两个正交信息集共同看多 = 内部人用真实现金投票 + 订单簿模型用微观结构投票, 双重确认。"},
  {"id": "x10_cons_60", "expr": f"group_zscore(ts_mean(add(ts_zscore({I_BS60}, 60), ts_zscore({L5C_RET}, 60)), 26), industry)",
   "ops": 4, "fields": ["insider_feats:buy_sell_ratio_all_60d_filled", "other566:l5r20gasfculr_ret"],
   "why": "共识叠加 (60 日内部人窗口 x 最深订单簿模型): 与 x10_cons_20 构成窗口配对, 检验内部人信号在 1 个月 vs 1 个季度尺度的一致性。"},
  {"id": "x10_relval_ins_minus", "expr": f"group_zscore(ts_mean(subtract(ts_zscore({R_RET}, 60), ts_zscore({I_BS60}, 60)), 26), industry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "insider_feats:buy_sell_ratio_all_60d_filled"],
   "why": "相对价值 (内部人 vs 模型): 模型看多而内部人看空 = 模型可能滞后于知情交易 (内部人有基本面信息优势); 押注内部人方向的修正。"},
  {"id": "x10_relval_ins_minus2", "expr": f"group_zscore(ts_mean(subtract(ts_zscore({L5C_RET}, 60), ts_zscore({I_BS60}, 60)), 26), industry)",
   "ops": 4, "fields": ["other566:l5r20gasfculr_ret", "insider_feats:buy_sell_ratio_all_60d_filled"],
   "why": "相对价值 (订单簿模型 vs 内部人): 与上一条配对, 但用 L5 深订单簿模型替代技术指标模型, 检验「内部人 vs 订单簿」是否比「内部人 vs 技术指标」更强 (订单簿更微观、更接近交易层面的实时信息)。"},
  {"id": "x10_weight_ins", "expr": f"group_zscore(ts_mean(multiply(ts_zscore({R_RET}, 60), group_rank({I_BS20}, industry)), 26), industry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "insider_feats:buy_sell_ratio_all_20d_filled"],
   "why": "内部人信念加权的模型预测: 把内部人买卖比作为模型预测的置信权重 (行业内秩, 恒正不翻转方向)。经济含义: 当内部人也在买入时, 模型的看多预测更可信, 加大权重; 反之自动收缩仓位。"},
  {"id": "x10_weight_ins2", "expr": f"group_zscore(ts_mean(multiply(ts_zscore({L5C_RET}, 60), group_rank({I_BS20_TOP20}, industry)), 26), industry)",
   "ops": 4, "fields": ["other566:l5r20gasfculr_ret", "insider_feats:top20_buy_to_sell_txn_ratio_lookback_60_filled"],
   "why": "权重加权的第二组: 用「前 20 名内部人」的成交笔数买卖比 (0/0 冷源) 替代全体内部人的金额买卖比, 检验「头部内部人信号质量更高」这一经典假设 (高管与大股东比中层员工更具信息含量)。"},
  {"id": "x10_cons_txr", "expr": f"group_zscore(ts_mean(add(ts_zscore({I_TXR60}, 60), ts_zscore({ML3}, 60)), 26), industry)",
   "ops": 4, "fields": ["insider_feats:buy_sell_tx_count_ratio_all_60d_filled", "other566:multil3_label"],
   "why": "共识叠加 (笔数口径): 用「买入笔数/卖出笔数」而非金额, 捕捉内部人行为的频率维度 (多次小额买入的累积意图), 与订单簿多期限模型共识。"},
  {"id": "x10_ins_only", "expr": f"group_zscore(ts_mean(ts_zscore({I_BS60}, 60), 26), industry)",
   "ops": 3, "fields": ["insider_feats:buy_sell_ratio_all_60d_filled"],
   "why": "纯内部人基线 (单字段, 供对照): 测量该冷源在 USA/D1/TOP1000 自身的 Sharpe/Margin 基线, 作为上述所有跨数据集组合的增量归因基准。这是本波唯一的单字段槽位 —— 它是基线对照而非候选 alpha。"},
 ]}

if __name__ == "__main__":
    for b in (W11, W12):
        p = os.path.join(HERE, f"batch_{b['batch']:02d}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f, indent=2, ensure_ascii=False)
        print("wrote", p, f"({len(b['items'])} items)")
