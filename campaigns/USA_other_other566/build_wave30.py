"""build_wave30.py — slow-leg horizontal scan across other685's 72 fields.

WAVE 29 READINGS:
  Outer ts_target_tvr_decay WORKS (TO 10.83% -> 8.43%/7.54%/6.70% at tvr
  0.05/0.04/0.03; Margin 5.07 -> 5.64/5.79/5.95bps) but Sharpe falls with it
  (1.07 -> 0.94/0.86/0.80). Also:
    * slow-leg weight x2.0 (xAr1x7YW) is BIT-IDENTICAL to x1.0 (88RvzW3m):
      after the outer group_zscore + tvr, a linear rescale of one leg is
      absorbed. Weight levers on ADDITIVE forms are inert. Do not retry.
    * outer group industry vs subindustry: negligible (Sh 0.94 both).
    * three-layer tvr (E56Vwnvm) is worse (Sh 0.74) — smoothing the slow leg
      destroys it, so the slow leg's ~11% turnover is its NATURAL repricing
      rate, not noise.

THE ARITHMETIC THAT MATTERS:
  x28_add_negpe = add(tvr_decay(r20marsi_ret, 0.08), group_zscore(reverse(pe_vs_hist)))
    portfolio: R 2.74%, TO 10.83%, Mgn 5.07bps
    slow leg alone (reverse of x27_base_pehist): Sh +1.09, R 2.80%, TO 10.87%
  => the SLOW LEG CONTRIBUTES ESSENTIALLY ALL OF THE PORTFOLIO'S RETURN
     (2.80% of the 2.74%) and the fast leg contributes ~0.
  => The "cross-dataset alpha" is really a slow valuation-reversion alpha
     with a fast leg bolted on. The lever that matters is therefore the
     QUALITY OF THE SLOW LEG, not the combination geometry.

  Target Mgn >= 15bps => R/TO >= 0.75. With the slow leg's natural TO ~11%,
  that needs R >= 8.2%. With outer tvr locking TO to 6%, it needs R >= 4.5%.
  A slow leg with Sh ~1.5 and R ~4% would satisfy both, and the fast leg
  would then add the decorrelation needed for Sh 1.65.

  other685 has 72 fields; the campaign has only probed 5. This wave scans 8
  more with the wave-28 geometry held CONSTANT (same fast leg, same tvr, same
  neutralization), so each slot is directly comparable to x28_add_negpe and the
  slow-leg ranking is clean.

SIGN CONVENTION (economics, per field):
  Reverse the "expensive is bad" fields (positive = rich vs own history / high
  absolute multiple). Do NOT reverse the quality/growth fields (positive =
  better fundamentals). If a slot comes back negative, its sign was wrong and
  the next wave flips it — this is the cheap way to test both orientations.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"

# (field_id, sign, economic reading)
SLOW_LEGS = [
 ("diff_current_vs_hist_price_ratio_earnings", "reverse",
  "P/E (current minus median historical forward 12m P/E), earnings-based twin of the proven pe_vs_hist leg"),
 ("forward_pe_ratio_mean_fy1", "reverse",
  "absolute forward P/E on mean analyst FY1 estimates; high multiple = expensive"),
 ("oth685_91v", "plain",
  "operating cash flow yield on enterprise value (CFO/EV); high = cash-generative = cheap"),
 ("oth685_cfroitrn", "plain",
  "trend/change in cash-flow return on investment; high = improving cash efficiency"),
 ("blended_growth_rate_smartest", "plain",
  "SmartEstimate earnings growth blended across last->this->next->LT; high = growth"),
 ("smartest_growth_this_vs_last_year_earnings", "plain",
  "SmartEstimate growth this year vs last year; high = upward revision"),
 ("oth685_81v", "plain",
  "free cash flow yield on EV (FCF/EV); high = cash-generative and less accrual-manipulated"),
 ("median_forward_12m_pe_ratio_hist", "plain",
  "the stock's OWN historical median forward P/E level; high = historically premium franchise (kept unreversed as the sign-riskiest probe)"),
]

W30 = {
 "batch": 30, "family": "slow_leg_horizontal_scan_other685",
 "hypothesis": (
   "波次 30: 波次 29 的算术揭示了真正的杠杆在哪 —— x28_add_negpe 的组合 R 2.74%, 而慢腿 "
   "reverse(diff_current_vs_hist_pe_ratio) 单独就有 R 2.80% (Sh +1.09, TO 10.87%), "
   "即**慢腿贡献了组合几乎全部的收益, 快腿贡献约 0**。所以「跨数据集」这个 alpha 的本体其实是"
   "一个慢速估值回归 alpha, 快腿只是搭上去的。要把 R/TO 从 0.25 推到 0.75, 必须换更好的慢腿。"
   "other685 有 72 个字段, 战役只测过 5 个。本波在**完全固定几何** (同快腿 r20marsi_ret + tvr0.08, "
   "同 add 结构, 同 STATISTICAL/decay0/trunc0.08) 下横向扫描 8 条新慢腿, 每个槽位与 x28_add_negpe "
   "逐位可比, 从而得到干净的慢腿排名。"
   "符号约定: 「贵就是坏」的字段取 reverse (当前 P/E 减历史中位、高绝对倍数), 「质量/成长」字段不取反 "
   "(高 = 更好)。若某槽回测为负, 说明符号判反, 下一波翻符号即可 —— 用一次回测同时测两个方向。"
   "经济学: 订单簿预测 (20 日微观结构) 与估值相对自身历史 (季度级再定价) 时间尺度不同; 慢腿的换手 "
   "(~11%) 是它自然的重定价节奏, 波次 29 已证平滑慢腿会杀它 (三层 tvr Sh 0.74)。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [],
}

for i, (fid, sign, reading) in enumerate(SLOW_LEGS, start=1):
    leg = f"reverse({fid})" if sign == "reverse" else fid
    W30["items"].append({
        "id": f"x30_slow{i}_{fid[:22]}",
        "expr": (f"group_zscore(add(ts_target_tvr_decay({R_RET}, target_tvr=0.08), "
                 f"group_zscore({leg}, subindustry)), subindustry)"),
        "ops": 5,
        "fields": [f"other566:r20marsi_ret", f"other685:{fid}"],
        "why": (f"慢腿扫描 {i}/8: {reading}. 符号 = {sign}. "
                f"与 x28_add_negpe 同几何 ⇒ 直接比较该慢腿相对 pe_vs_hist 的增量价值。"
                f"判据: 若本槽 Sh > 1.07 且 Mgn > 5.07bps, 该慢腿优于已知最好慢腿, 下一波即以它为主体"
                f"叠加外层 tvr + quantile 冲 15bps 死线。"),
    })

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W30['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W30, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W30['items'])} items)")
    for it in W30["items"]:
        print(f"  {it['id']:<36} fields={len(it['fields'])} {it['expr'][:92]}")
