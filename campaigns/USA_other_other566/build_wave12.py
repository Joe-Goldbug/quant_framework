"""
build_wave12.py — wave 12: the turnover-lever wave that attacks the Margin dead line.

EVIDENCE LEDGER (USA/D1/TOP1000, decay=4, neutralization=INDUSTRY, truncation=0.08):

  E1. ts_mean is the signal killer.  ts_mean present: n=54 meanSh 0.292 maxSh 0.81.
      ts_mean absent : n=8  meanSh 0.836 maxSh 1.18.   => 2.9x Sharpe uplift.
  E2. Outer layer: group_zscore meanMgn 3.93 (max 7.46) > group_neutralize 2.69
      (max 5.08) > group_rank 1.49 (max 5.76).  group_zscore also has the best
      mean Sharpe 0.456.  => Iron Law B confirmed for this dataset.
  E3. Margin is arithmetic: margin_bps = returns/turnover*20, so
      margin >= 10bps  <=>  returns >= 0.5 * turnover.
      The b1_m4 core already returns 3.92% at 10.5% turnover (Mgn 7.46bps).
      If we can hold returns while halving turnover -> Mgn ~15bps, over the line.
      If we can push returns to 5.5% at 10.5% turnover -> Mgn ~10.5bps, over.
  E4. The platform's OWN turnover levers (validOp.json):
        ts_target_tvr_decay(x, lambda_min=0, lambda_max=1, target_tvr=0.1)
          "Tune 'ts_decay' to have a turnover equal to a certain target" — this
          is the platform's principled turnover target and is used in real
          submitted alphas in this repo (aegis_fnd17/account_alpha_history_full.json
          uses ts_target_tvr_decay(..., target_tvr=0.20)).
        ts_decay_exp_window(x, d, factor=f) — exponential decay; a much gentler
          smoother than ts_mean(x,26) because it keeps a geometric weight profile
          instead of a flat average.
        ts_decay_linear(x, d) — linear decay, the gentlest smoother.
  E5. hump(x, 0.01) is REJECTED by the platform ("Invalid number of inputs : 2,
      should be exactly 1 input(s)"). The single-arg hump(x) form is the safe one.
  E6. trade_when gating is always-true here (b7_t1/b7_t2/b7_t6 identical metrics)
      -> do NOT spend more quota on gating variants; spend it on smoothing levers.

Wave 12 therefore keeps the b1_m4 champion core (ret x prob_5) EXACTLY fixed and
varies ONLY the turnover lever + outer layer, so every slot is a controlled
experiment on the one remaining binding constraint.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
R_P3 = "oth566_r20marsi_prob_3"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"
L2R20 = "oth566_l2r20_label"
L2R20P = "oth566_l2r20_prob"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"

CORE = f"multiply({R_RET}, {R_P5})"

W12 = {
 "batch": 12, "family": "turnover_lever_attack_on_margin_deadline",
 "hypothesis": (
   "波次 12: 只攻 Margin 死线这一个约束。E3 的算术恒等式 margin_bps = returns/turnover*20 表明 "
   "margin>=10bps 等价于 returns>=0.5*turnover, 所以只要在保住收益的前提下把换手压下来, Margin 就能过线。"
   "E1/E2 已锁定冠军核心 = multiply(r20marsi_ret, r20marsi_prob_5) + group_zscore 外层 (Sh0.81/Mgn7.46bps/RNS1.30)。"
   "本波 8 槽位固定该核心, 只换唯一的换手杠杆, 构成受控实验: (a) ts_target_tvr_decay 显式目标换手 "
   "target_tvr=0.15/0.10 (平台自带的 'Tune ts_decay to have a turnover equal to a certain target', "
   "且本仓库已有生产 alpha 用 target_tvr=0.20); (b) ts_decay_exp_window 指数衰减 (几何权重而非平坦平均, "
   "比 ts_mean(26) 温和得多); (c) ts_decay_linear 线性衰减; (d) hump 单参数形式 (平台对 hump 只接受 1 个位置参数, "
   "hump(x,0.01) 会被拒); (e) 换置信腿 (prob_3) 与换方向腿 (oth566_return + prob_2) 的稳健性对照。"
   "预期: 若某杠杆在 Sharpe 保持 >=1.2 的前提下把 turnover 从 10.5% 压到 <=6%, Margin 即突破 10bps。"
 ),
 "items": [
  {"id": "w12_tvr15", "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr=0.15), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (a): 显式把换手目标设为 15%。若 Sharpe 保住而 returns/turnover 比值上升, Margin 过线。"},
  {"id": "w12_tvr10", "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr=0.10), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (a) 更激进档: target_tvr=10%, 与 15% 配对以定位最优点。"},
  {"id": "w12_dexp10", "expr": f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.5), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (b): 指数衰减 (10 日, factor 0.5)。几何权重保留了近期信号的相对优势, 而 ts_mean(26) 是平坦平均。"},
  {"id": "w12_dexp20", "expr": f"group_zscore(ts_decay_exp_window({CORE}, 20, factor=0.7), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (b) 长窗档: 20 日 factor 0.7, 与 10 日档配对做窗口/衰减强度双维扫描。"},
  {"id": "w12_dlin10", "expr": f"group_zscore(ts_decay_linear({CORE}, 10), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (c): 线性衰减 10 日, 作为指数衰减的对照 (几何 vs 线性权重)。"},
  {"id": "w12_hump1", "expr": f"group_zscore(hump({CORE}), industry)",
   "ops": 3, "fields": [R_RET, R_P5],
   "why": "换手杠杆 (d): hump 单参数形式。平台对 hump 只接受 1 个位置参数 —— 双参数形式已被平台以 'Invalid number of inputs : 2' 拒绝, 本槽改用单参数。"},
  {"id": "w12_p3_tvr15", "expr": f"group_zscore(ts_target_tvr_decay(multiply({R_RET}, {R_P3}), target_tvr=0.15), industry)",
   "ops": 3, "fields": [R_RET, R_P3],
   "why": "稳健性对照: 把置信腿从 prob_5 (1 用户) 换成 prob_3 (4 用户) 后再施加最优换手杠杆, 检验结果不依赖特定信念口径。"},
  {"id": "w12_ret2_tvr15", "expr": f"group_zscore(ts_target_tvr_decay(multiply({RET2}, group_rank({PROB_2}, industry)), target_tvr=0.15), industry)",
   "ops": 4, "fields": [RET2, PROB_2],
   "why": "跨模型稳健性对照: 换方向腿为 2 日期的 oth566_return (39 用户) + 2 日置信 (1 用户), 检验同一机制在另一预测期限上是否同样成立 —— 若成立则机制普适, 若不成立则 other566 的 alpha 高度依赖 20 日期限。"},
 ]}

# ---- Wave 13: decay sweep on the champion core (decay is currently 4) ----
W13 = {
 "batch": 13, "family": "decay_and_window_sweep_on_champion_core",
 "hypothesis": (
   "波次 13: 冠军核心的 decay 扫描。战役全程 decay=4, 但 decay 是平台对持仓做线性衰减的平滑参数, "
   "与 ts_mean 是同一类平滑器 —— 而 E1 已证明在本数据集上强平滑会杀死信号。因此 decay 很可能存在一个"
   "「低衰减保信号 / 高衰减压换手」的最优点。波次 13 用 8 个槽位扫描 decay(0/2/8/12/20) x 平滑档位"
   "(不平滑 / ts_decay_exp_window / ts_target_tvr_decay), 目标是在保住 Sharpe 的前提下把换手压到 Margin 死线之下。"
   "每个槽位仍是 2 字段、<=6 算子。"
 ),
 "items": [
  {"id": "w13_d0_plain", "expr": f"group_zscore({CORE}, industry)",
   "ops": 2, "fields": [R_RET, R_P5], "decay": 0,
   "why": "decay=0 完全不平滑: 与 decay=4 的 w11_gz_plain 配对, 单独测量 decay 参数本身的贡献。"},
  {"id": "w13_d8_plain", "expr": f"group_zscore({CORE}, industry)",
   "ops": 2, "fields": [R_RET, R_P5], "decay": 8,
   "why": "decay=8: 在不改变表达式的前提下提高平台端平滑, 观察 Sharpe/换手的权衡曲线。"},
  {"id": "w13_d12_plain", "expr": f"group_zscore({CORE}, industry)",
   "ops": 2, "fields": [R_RET, R_P5], "decay": 12,
   "why": "decay=12: 更强平滑档, 用于定位 Sharpe 崩塌的拐点。"},
  {"id": "w13_d20_plain", "expr": f"group_zscore({CORE}, industry)",
   "ops": 2, "fields": [R_RET, R_P5], "decay": 20,
   "why": "decay=20: 最强档, 预期换手最低但 Sharpe 可能崩塌 (E1 的延伸验证)。"},
  {"id": "w13_d0_tvr15", "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr=0.15), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
   "why": "双平滑器组合的对照: 表达式端 tvr 目标 + 平台端 decay=0, 隔离平台 decay 的边际作用。"},
  {"id": "w13_d8_tvr15", "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr=0.15), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 8,
   "why": "双平滑器组合: 表达式端目标换手 15% + 平台端 decay=8。两者叠加可能过度平滑, 此槽检验是否过头。"},
  {"id": "w13_d8_dexp", "expr": f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.5), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 8,
   "why": "指数衰减 + decay=8 的组合, 与 w13_d8_plain 配对以测双重平滑的边际贡献。"},
  {"id": "w13_d12_dexp", "expr": f"group_zscore(ts_decay_exp_window({CORE}, 10, factor=0.5), industry)",
   "ops": 3, "fields": [R_RET, R_P5], "decay": 12,
   "why": "指数衰减 + 更强 decay, 定位「双重平滑」下的 Sharpe 拐点。"},
 ]}

if __name__ == "__main__":
    for b in (W12, W13):
        p = os.path.join(HERE, f"batch_{b['batch']:02d}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f, indent=2, ensure_ascii=False)
        print("wrote", p, f"({len(b['items'])} items)")
