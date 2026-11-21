"""build_wave27.py — cross-dataset wave 26 follow-up: restore the turnover lever
and measure the slow leg on its own.

WAVE 26 DIAGNOSIS (8/8 slots came back with turnover ~87-90%):
  I omitted ts_target_tvr_decay. That was the bug, not the cross-dataset idea.
  Wave 26 proved the other685 LEG carries signal:
    qMLEXov1 (r20marsi_ret x rank(diff_current_vs_hist_pe_ratio)): Sh 1.45,
      2Y 2.43 (campaign 2nd-highest), R 3.07%, DD 4.47%, 0 sub-universe FAIL.
    WjOLg6KO (r20marsi_ret x rank(smartest_growth...)): Sh 1.06, DD 3.30%.
  But every combo had TO ~90% (raw daily-changing order-book forecast, decay=0),
  so Margin collapsed to 0.03-0.07 bps despite R up to 3.07%.

  Campaign-proven fact (waves 15-24): ts_target_tvr_decay is the ONLY smoother
  that does NOT kill this dataset's signal (ts_mean / ts_zscore / ts_av_diff all
  destroy it). The seed kqNgXQqd = group_zscore(ts_target_tvr_decay(multiply(
  ret, prob_5), target_tvr=0.12), industry) -> TO 13.93%, R 3.04%, Sh 1.27.

  ⇒ Wave 27 = wave 26's winning leg, wrapped in the seed's turnover lever.

WAVE 27 ALSO ANSWERS THE DECISIVE QUESTION:
  Can a slow fundamental leg raise RETURNS without raising TURNOVER?
  Slots 1-3 are single-field other685 baselines. Their R/TO is the ceiling on
  what the slow leg can contribute. If a baseline is Sh>0.9 at TO<15%, the slow
  leg is genuinely additive (M1 consensus); if it is <=0 (like cfroi_3's -0.20),
  the slow leg can only work as a WEIGHT on the fast leg, not as an added stream.

ALGEBRAIC TARGET (unchanged, from the hard-gate directive):
  Margin >= 15bps => R/TO >= 0.75
  Fit >= 1.05 with TO<12.5% => Sh >= 1.05/sqrt(R/0.125)
  Feasible cell: TO 5-9%, R 4-7%, Sh >= 1.65.
  Seed R/TO = 0.218 (R 3.04% / TO 13.93%). Campaign best R/TO = 0.519 but with
  Sh only 0.66. Need a leg that lifts R at fixed TO.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
RET2 = "oth566_return"

EY_SMARTTEST = "earnings_yield_smartest_fy1"          # cov 0.9964, 9u/18a
EY_IND_PCTL = "earnings_yield_industry_percentile_fy1"  # cov 0.9947, 0u/0a
GROW_NEXT = "smartest_growth_next_vs_this_year_earnings"  # cov 0.9677, 1u/2a
PE_VS_HIST = "diff_current_vs_hist_pe_ratio"            # cov 0.9961, 7u/10a
CFO_EV = "oth685_91v"                                   # cov 0.6815, 0u/0a

W27 = {
 "batch": 27, "family": "cross_dataset_w26_leg_with_turnover_lever",
 "hypothesis": (
   "波次 27: 波次 26 的失败是**结构遗漏**而非跨数据集思路失败 —— 我漏掉了 ts_target_tvr_decay, "
   "导致 8 槽位换手冲到 87-90%, Margin 塌到 0.03-0.07bps。波次 26 同时证明了 other685 的腿有真信号: "
   "PE-vs-历史腿得 Sh 1.45 / 2Y 2.43 (战役次高)。"
   "本波做两件事: (a) 把波次 26 胜出腿套回种子的换手杠杆 (ts_target_tvr_decay, 战役已证是唯一不杀本数据集信号的平滑算子); "
   "(b) 用 3 个单字段 other685 基线槽**判定慢腿本身的价值上限** —— 若基线 Sh>0.9 且 TO<15%, 则慢腿可作为独立收益流"
   "叠加 (真正抬高 R 而不动 TO, 这正是 R/TO>=0.75 唯一可能的路径); 若基线<=0 (如 cfroi_3 的 -0.20), 则慢腿只能"
   "作为快腿的权重, 不能作为加法项。"
   "经济学: 分析师预期修正与现金流估值是慢速、基本面驱动、信息源与订单簿形态正交; 订单簿预测是快速、微观结构驱动。"
   "两者的**时间尺度互补**正是理论上前者能在不抬换手的前提下抬高组合期望收益的原因。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [
  {"id": "x27_base_ey",
   "expr": f"group_zscore({EY_SMARTTEST}, subindustry)",
   "ops": 2, "fields": ["other685:earnings_yield_smartest_fy1"],
   "is_baseline_control": True,
   "why": "纯慢腿基线 1: SmartEstimate 盈利收益率 (E/P, FY1)。价值因子在美股长期有效, 且季度更新 => 低换手。"
          "本槽测量: 慢腿的独立 Sharpe 与 R/TO。若 Sh>=0.9 且 R/TO>=0.15, 它就是 other566 缺的那条腿。"},

  {"id": "x27_base_pehist",
   "expr": f"group_zscore({PE_VS_HIST}, subindustry)",
   "ops": 2, "fields": ["other685:diff_current_vs_hist_pe_ratio"],
   "is_baseline_control": True,
   "why": "纯慢腿基线 2: 当前 P/E 减历史中位 P/E (正=相对历史变贵)。均值回复速度中等。"
          "本槽测量其独立 Sharpe/TO/2Y —— 波次 26 中它是权重形态下表现最好的腿 (Sh 1.45 / 2Y 2.43), 需确认其自身强度。"},

  {"id": "x27_base_grow",
   "expr": f"group_zscore({GROW_NEXT}, subindustry)",
   "ops": 2, "fields": ["other685:smartest_growth_next_vs_this_year_earnings"],
   "is_baseline_control": True,
   "why": "纯慢腿基线 3: SmartEstimate 下一财年 vs 本财年盈利增长 (分析师预期修正)。"
          "分析师上修是经典的信息含量事件且更新频率低 (季度), 是本波假设中最理想的「慢而强」腿。"},

  {"id": "x27_pehist_tvr08",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, rank({PE_VS_HIST})), target_tvr=0.08), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "波次 26 胜出腿 (qMLEXov1) + 换手杠杆 tvr=0.08: 与种子同构, 只把 prob_5 腿换成 PE-vs-历史腿。"
          "预期 TO 降到 8-10%; 检验 R 能否在 TO 下降时保持 (若 R 仍 2.5-3%, 则 R/TO 0.3+, Margin 6-7bps, 突破种子 4.37)。"},

  {"id": "x27_pehist_tvr12",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, rank({PE_VS_HIST})), target_tvr=0.12), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "同腿 tvr=0.12 (种子自身换手档): 与 x27_pehist_tvr08 构成换手配对, 分离「换手」与「腿替换」两个效应。"
          "本槽是种子的**最小差异对照** (只换腿), 因此任何指标变化都可干净归因于 other685 的 PE-vs-历史腿。"},

  {"id": "x27_pehist_inner_zs",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply(group_zscore({R_RET}, subindustry), rank({PE_VS_HIST})), target_tvr=0.08), subindustry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "内层加 subindustry zscore 版: 波次 26 的结构 (内层 group_zscore) 配换手杠杆, 检验子行业异方差处理"
          "(Labs 图6/图7: 高波子行业预测幅度远大于低波) 是否与换手杠杆叠加有效。"},

  {"id": "x27_add_pehist",
   "expr": f"group_zscore(add(ts_target_tvr_decay({R_RET}, target_tvr=0.08), group_zscore({PE_VS_HIST}, subindustry)), subindustry)",
   "ops": 4, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "加法机制 (关键槽): 慢腿作为**独立收益流**叠加, 而非权重。经济含义: 订单簿捕捉未来 20 日的微观结构"
          "定价, PE-vs-历史捕捉基本面估值的均值回复, 两者时间尺度不同 ⇒ 收益相关低 ⇒ 组合 Sharpe 可超各自分量而换手只由快腿决定。"
          "这是 R/TO>=0.75 的唯一理论路径 (慢腿抬 R 而几乎不抬 TO)。"},

  {"id": "x27_3f_value_rev",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply(multiply({R_RET}, rank({EY_SMARTTEST})), rank({PE_VS_HIST})), target_tvr=0.08), subindustry)",
   "ops": 5, "fields": ["other566:r20marsi_ret", "other685:earnings_yield_smartest_fy1", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "三字段双慢腿加权: 快腿 x 绝对估值 (E/P 水平) x 相对历史估值 (PE vs 历史中位)。"
          "经济含义: 订单簿信号只在「基本面便宜」且「估值未相对自身历史膨胀」时兑现 —— 前者筛质地, 后者筛均值回复空间。"
          "两腿均经 rank 保号, 不翻转快腿方向。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W27['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W27, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W27['items'])} items)")
    for it in W27["items"]:
        print(f"  {it['id']:<22} fields={len(it.get('fields') or [])} {it['expr'][:100]}")
