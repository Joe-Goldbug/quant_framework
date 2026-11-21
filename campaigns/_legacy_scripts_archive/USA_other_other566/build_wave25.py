"""build_wave25.py — root-cause reconstruction of seed kqNgXQqd.

SEED: group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret,
      oth566_r20marsi_prob_5), target_tvr=0.12), industry)
      @ STATISTICAL / decay=0 / trunc=0.08
      Sh 1.27 / Fit 0.59 / Cluster 0.95 / Mgn 4.37bps / TO 13.93% / R 3.04% / DD 4.89%

HARD GATES: Sh>=1.65, Fit>=1.05, Cluster>=1.60, Mgn>=15bps, R>=5.5% > DD<=2.8%.

OPERATOR VERIFICATION (2026-11-05, get_operators):
  - ts_target_tvr_hump DOES NOT EXIST. Turnover lever = ts_target_tvr_decay
    (campaign-proven: tvr=0.10 -> TO 8.4%; tvr=0.12 -> TO 12.5-13.9%).
    Target TO 3.5-5.5% -> target_tvr in [0.04, 0.05].
  - ts_ir DOES NOT EXIST. Marginal-breakthrough via ts_zscore(x,d) and
    ts_av_diff(x,d) (= x - ts_mean(x,d), innovation without std-normalization).
  - hump(x, hump=0.01) has a NAMED param but positional 2-arg form was
    platform-rejected earlier; not risked this wave.

ROOT-CAUSE FIXES APPLIED (per directive):
  R1: prob/confidence legs wrapped in rank()/group_rank(...,subindustry) -> [0,1]
      sign-preserving; main signal winsorize(group_zscore(...,subindustry), std=3.0).
  R2: pipeline order = ts_zscore innovation -> cross-sectional denoise ->
      slow tvr smoothing -> subindustry neutralize (was: smooth then neutralize,
      which locked 2017/2019/2021 dispersion-collapse drift into the book).
  R3: target_tvr 0.04-0.05 (TO ~3.5-5.5%, Margin x3+); signed_power(z,1.5/2.0)
      on the FINAL centered book concentrates tails -> raise Returns without
      adding turnover (Fitness denominator locked at 0.125 when TO<12.5%).
  R4: cluster orthogonalization via (a) ts_zscore/ts_av_diff second-order
      dynamics instead of raw level, (b) replacing weak prob_5 leg (avg Sh 0.50)
      with higher-Sharpe low-crowding legs: r20marsi_label_5 (0.95, 8 alphas),
      label_2 (1.09, 12), multil3_prob_pattern (1.05, 2), l2r5res_prob (0.85, 1).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

RET = "oth566_r20marsi_ret"
P5 = "oth566_r20marsi_prob_5"
L5 = "oth566_r20marsi_label_5"
LB2 = "oth566_label_2"
MLPP = "oth566_multil3_prob_pattern"
L2RES = "oth566_l2r5res_prob"

# rule-compliant core: ts-innovation -> x-sectional denoise + winsorize
def core(win):
    return f"winsorize(group_zscore(ts_zscore({RET}, {win}), subindustry), std=3.0)"

W25 = {
 "batch": 25, "family": "rootcause_reconstruction_seed_kqNgXQqd",
 "hypothesis": (
   "波次 25: 种子 kqNgXQqd 四大根因修复。"
   "R1: prob 腿一律 rank()/group_rank(subindustry) 映射 [0,1] 保号, 主信号 winsorize(group_zscore(...,subindustry),std=3) 防爆尾。"
   "R2: 流水线反转为 先 ts_zscore 边际突破 -> 慢速 tvr 平滑 -> 后 subindustry 中性化, 修复 2017/2019/2021 离散度塌缩回撤。"
   "R3: target_tvr 0.04~0.05 (TO 3.5~5.5%, Margin 3x+); signed_power(z,1.5/2.0) 作用于最终零均值账本, 尾部聚焦抬 Returns 破 Fitness 0.125 分母瓶颈。"
   "R4: ts_zscore 二阶动态 + 正交腿 (label_5 / label_2 / multil3_prob_pattern / l2r5res_prob) 替换弱 prob_5, 破 386 个存量共线簇。"
   "代数设计点: R=6%/TO=4.5% -> Mgn=26.7bps, Fit=1.65*sqrt(0.06/0.125)=1.14, 需 R/TO=1.33 (战役前最佳 0.52), 赌注在边际突破+尾部聚焦。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [
  {"id": "w25_zs40_p5_t04",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({core(40)}, rank({P5})), target_tvr=0.04), subindustry)",
   "ops": 7, "fields": [RET, P5],
   "why": "全流水线基准: ts_zscore(40) 边际突破 x rank(prob_5) 保号信念, tvr0.04 压 TO~3.5%, subindustry 双中性化。R1+R2+R3 完全体。"},
  {"id": "w25_zs40_p5_t04_sp15",
   "expr": f"signed_power(group_zscore(ts_target_tvr_decay(multiply({core(40)}, rank({P5})), target_tvr=0.04), subindustry), 1.5)",
   "ops": 8, "fields": [RET, P5],
   "why": "R3 尾部聚焦: 对最终零均值账本 signed_power(1.5) 放大双侧高确信尾部仓位, 不加换手抬 Returns, 直攻 Fitness>=1.05 与 Mgn>=15bps。"},
  {"id": "w25_zs40_l5_t04",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({core(40)}, group_rank({L5}, subindustry)), target_tvr=0.04), subindustry)",
   "ops": 7, "fields": [RET, L5],
   "why": "R4 正交腿: r20marsi_label_5 (avg Sh 0.95, 仅 8 alpha) 替换 prob_5 (avg Sh 0.50)。同族 5 日标签信念, 语义一致但存量簇远小, 攻 Cluster>=1.60。"},
  {"id": "w25_zs40_mlpp_t045",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({core(40)}, rank({MLPP})), target_tvr=0.045), subindustry)",
   "ops": 7, "fields": [RET, MLPP],
   "why": "R4 最正交腿: multil3_prob_pattern (avg Sh 1.05, 仅 2 alpha, slow 主题) 是形态置信度, 与 R20MaRsi 技术指标路线信息源不同, 最大化簇脱敏。"},
  {"id": "w25_zs40_vol_t05",
   "expr": f"group_zscore(ts_target_tvr_decay(divide({core(40)}, ts_std_dev(returns, 20)), target_tvr=0.05), subindustry)",
   "ops": 8, "fields": [RET, "returns"],
   "why": "R2 风险平价: 以 20 日实现波动率缩放边际突破, 直接压制 2017/2019/2021 低波/逼空 regime 的回撤 (目标 DD<=2.8%); 去掉 prob_5 腿换取波动率自适应仓位。"},
  {"id": "w25_avdiff40_p5_t04",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply(ts_av_diff({RET}, 40), rank({P5})), target_tvr=0.04), subindustry)",
   "ops": 5, "fields": [RET, P5],
   "why": "R2 对照: ts_av_diff = x - ts_mean(x,40), 无 std 归一的边际突破, 保留幅度信息 (铁律B); 与 w25_zs40_p5_t04 配对隔离「std 归一 vs 裸差分」。"},
  {"id": "w25_zs20_lb2_t045",
   "expr": f"group_zscore(ts_target_tvr_decay(multiply({core(20)}, group_rank({LB2}, subindustry)), target_tvr=0.045), subindustry)",
   "ops": 7, "fields": [RET, LB2],
   "why": "R4 短窗腿: label_2 (2 日预测标签, avg Sh 1.09, 12 alpha) 提供最短 horizon 信念, 与 ts_zscore(20) 短窗边际突破同尺度共振; 检验窗口匹配假说。"},
  {"id": "w25_zs60_l2res_t05_sp2",
   "expr": f"signed_power(group_zscore(ts_target_tvr_decay(multiply({core(60)}, rank({L2RES})), target_tvr=0.05), subindustry), 2.0)",
   "ops": 8, "fields": [RET, L2RES],
   "why": "R3+R4 极限档: ts_zscore(60) 长窗突破 x l2r5res_prob (avg Sh 0.85, 仅 1 alpha) x signed_power(2.0) 强尾部聚焦, tvr0.05。探 R/TO 上限的边界槽位。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W25['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W25, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W25['items'])} items)")
    for it in W25["items"]:
        print(f"  {it['id']:<24} ops={it['ops']} {it['expr'][:100]}")
