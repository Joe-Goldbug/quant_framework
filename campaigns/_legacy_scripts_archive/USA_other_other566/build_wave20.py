"""
build_wave20.py — wave 20: attack the binding constraint directly (returns/turnover).

WHERE THE CAMPAIGN STANDS AFTER 19 WAVES (152 slots, USA/D1/TOP1000):

  PLATFORM-LEVEL (the platform's own checks, limit HIGH_TURNOVER = 0.70):
    P0ogXzG7  dexp15 @STATISTICAL   Sh 1.62  TO 61.0%  Mgn 1.26  2Y 2.43  **0 FAIL**
    N1NV5zbL  dexp20 @STATISTICAL   Sh 1.63  TO 68.5%  Mgn 1.12  2Y 2.45  **0 FAIL**
    58Egq5l1  dexp20(prob_3)        Sh 1.63  TO 68.4%  Mgn 1.12  2Y 2.43  **0 FAIL**
    d5W1lzjx  ret2_dexp20           Sh 1.73  TO 73.1%  Mgn 1.14  2Y 2.20  CLUSTER 1.60
  => LOW_SHARPE PASSES, LOW_2Y_SHARPE PASSES, HIGH_TURNOVER PASSES for the first three.
     The only remaining platform item is LOW_FITNESS (a WARNING, not a FAIL, for the
     first three) plus CLUSTER_TEST (WARNING).

  AEGIS INTERNAL GATE (stricter: fitness>=1.00, margin>=10bps, turnover<=50%):
    NOTHING PASSES YET. The binding constraint is algebra, not luck:
        margin_bps = returns/turnover*20   => Mgn>=10  <=>  returns/turnover >= 0.50
        fitness    = sharpe*sqrt(returns/max(turnover,0.125))
    Combining Mgn>=10 (=> R/TO>=0.5) with Fit>=1.0 gives
        Fit = Sh*sqrt(0.5) = 0.707*Sh   =>  Sh >= 1.414 is NECESSARY.
    And at a given turnover T, Mgn>=10 needs returns = 0.5*T:
        T=8%  -> R>=4.0%, Sh>=1.77
        T=10% -> R>=5.0%, Sh>=1.58
        T=12.5%-> R>=6.25%, Sh>=1.41
    So the winning cell is around T=10-12.5% with R>=5-6.25% and Sh>=1.58.

  WHAT THE LEDGER SAYS ABOUT RETURNS (the scarce quantity):
    Highest R among all 150 resolved slots:
      w11_gz_l3r5  (L3R5 label leg)  R 6.22%  TO 46.7%  Sh 1.10
      w11_gz_plain (r20marsi leg)    R 5.09%  TO 44.7%  Sh 1.08
      w12_ret2_tvr15 (2-day leg)     R 4.84%  TO 12.0%  Sh 0.91  <-- R/TO = 0.403 !!
    Highest R/TO among all slots:
      w15_tvr05_d0 (INDUSTRY, tvr05) R/TO 0.520 (Mgn 10.39) but Sh only 0.66
      w12_ret2_tvr15                 R/TO 0.403 (Mgn  8.03) Sh 0.91
    => The **2-day forecast leg (oth566_return + oth566_prob_2)** has by far the best
       returns-per-turnover, and wave 19 already showed that same leg under
       ts_decay_exp_window reaches the campaign's highest Sharpe (1.73).
       It has NEVER been swept with a tvr ladder, and never under STATISTICAL.

WAVE 20 therefore sweeps the two highest-return structures at the two operating
points that the algebra says are viable (TO ~10% and TO ~12.5%), and tests
whether the platform's own HIGH_TURNOVER limit of 0.70 (not 0.50) lets the
exp-decay family satisfy the PLATFORM gate while a tvr variant satisfies the
AEGIS internal gate.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
L3R5 = "oth566_l3r5_label"
L3R5P = "oth566_l3r5_prob"
RET2 = "oth566_return"
PROB_2 = "oth566_prob_2"

STAT = "STATISTICAL"
CORE = f"multiply({R_RET}, {R_P5})"
RET2_CORE = f"multiply({RET2}, group_rank({PROB_2}, industry))"
L3_CORE = f"multiply(ts_zscore({L3R5}, 60), group_rank({L3R5P}, industry))"


def slot(sid, expr, ops, fields, note, neutralization=STAT, decay=0, truncation=0.08):
    return {"id": sid, "expr": expr, "ops": ops, "fields": fields,
            "decay": decay, "neutralization": neutralization, "truncation": truncation,
            "why": note}


def tvr_on(sid, core, t, neutralization, note, ops=4):
    return slot(sid,
                f"group_zscore(ts_target_tvr_decay({core}, target_tvr={t}), industry)",
                ops, [], note, neutralization=neutralization)


W20 = {
 "batch": 20, "family": "returns_per_turnover_attack_on_high_return_legs",
 "hypothesis": (
   "波次 20: 直接攻击唯一还缺的量 —— **单位换手收益**。代数定位: Mgn>=10bps 等价 returns/turnover>=0.50; "
   "与 Fit>=1.0 联立得 Sharpe>=1.414 是必要条件; 且在换手 T 处 Mgn>=10 要求 returns=0.5T "
   "(T=10% => R>=5% 且 Sh>=1.58; T=12.5% => R>=6.25% 且 Sh>=1.41)。"
   "台账显示两个结构的单位换手收益远高于其余: (i) **2 日期预测腿** oth566_return x oth566_prob_2 —— "
   "w12_ret2_tvr15 的 R/TO=0.403 (Mgn 8.03bps, TO 12.0%), 是全战役 R/TO 次高, 且波次 19 已证明同腿配 "
   "ts_decay_exp_window 达到全战役最高 Sharpe 1.73 —— 但它**从未被 tvr 阶梯扫描, 也从未在 STATISTICAL 下测过**; "
   "(ii) **Level3 订单簿 5 日腿** oth566_l3r5_label x oth566_l3r5_prob —— w11_gz_l3r5 的绝对收益最高 (R 6.22%), "
   "同样只测过单一工作点。本波 8 槽位: 2 日期腿在 STATISTICAL 下的 tvr 阶梯 (0.08/0.10/0.12/0.15, "
   "覆盖 T=8%~13% 的可行区), L3 腿在 STATISTICAL 下的 tvr 阶梯 (0.08/0.10), 以及两个高 Sharpe 端的换手压降探针 "
   "(dexp15 配 decay=4; dexp15 换 NONE 中性化) —— 因为平台自身的 HIGH_TURNOVER 上限是 0.70 而非 AEGIS 内部的 0.50, "
   "这些槽位可能直接满足**平台**提交门, 同时为 AEGIS 内部门提供低换手替代路径。"
 ),
 "items": [
  tvr_on("w20_ret2_tvr08", RET2_CORE, 0.08, STAT,
         "2 日期腿 x tvr=0.08 (T~8%): 代数可行区最优点。需 R>=4.0% 且 Sh>=1.77 —— 严格但这是唯一同时满足两条线的区间。", 4),
  tvr_on("w20_ret2_tvr10", RET2_CORE, 0.10, STAT,
         "2 日期腿 x tvr=0.10 (T~10%): 需 R>=5.0% 且 Sh>=1.58 —— 两个约束同时最宽松的工作点, 优先级最高。", 4),
  tvr_on("w20_ret2_tvr12", RET2_CORE, 0.12, STAT,
         "2 日期腿 x tvr=0.12 (T~12.5%): 需 R>=6.25% 且 Sh>=1.41 —— Sharpe 门槛最低的一档, 对 2 日期腿有利 (信息更新快)。", 4),
  tvr_on("w20_ret2_tvr15", RET2_CORE, 0.15, STAT,
         "2 日期腿 x tvr=0.15: 复现 w12_ret2_tvr15 (INDUSTRY 下 Sh0.91/Mgn8.03) 在 STATISTICAL 下的读数, 作为该腿的中性化对照。", 4),
  tvr_on("w20_l3_tvr08", L3_CORE, 0.08, STAT,
         "L3 订单簿腿 x tvr=0.08: 该腿绝对收益最高 (R 6.22%), 若能在 T~8-10% 保持高收益, 则 R/TO 可望破 0.5。", 5),
  tvr_on("w20_l3_tvr10", L3_CORE, 0.10, STAT,
         "L3 订单簿腿 x tvr=0.10: 与上一槽配对做 tvr 扫描, 定位该腿的 R/TO 峰值。", 5),
  slot("w20_dexp15_d4",
       f"group_zscore(ts_decay_exp_window({CORE}, 15, factor=0.6), industry)",
       3, [R_RET, R_P5],
       "高 Sharpe 端的换手压降: P0ogXzG7 (dexp15 @decay0) Sh 1.62 / TO 61.0% 是全战役 0-FAIL 的最高 Sharpe。平台端 decay=4 若能压低换手而不损 Sharpe, 即可同时满足平台门与 AEGIS 的 50% 换手上限。",
       decay=4),
  slot("w20_dexp15_none",
       f"group_zscore(ts_decay_exp_window({CORE}, 15, factor=0.6), industry)",
       3, [R_RET, R_P5],
       "高 Sharpe 端的换手压降 (换中性化): NONE 下波次 17 曾给出与 INDUSTRY 逐位相同的结果, 但在 dexp 强平滑下 alpha 残留更多 beta ⇒ 可能呈现不同的收益/换手比。",
       neutralization="NONE"),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W20['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W20, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W20['items'])} items)")
