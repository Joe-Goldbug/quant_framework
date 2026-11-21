"""build_wave33.py — scale-matched two-leg book: centered-rank slow leg + centered
fast-leg tilt, all under ONE outer turnover target.

THE GAP THIS WAVE ATTACKS (and why waves 28-30 could not):
  Wave 28's x28_add_negpe = add(ts_target_tvr_decay(r20marsi_ret, 0.08),
                                group_zscore(reverse(pe_vs_hist), subindustry))
  The two legs are on INCOMPATIBLE SCALES:
    fast leg (ts_target_tvr_decay of a raw forecast in [-0.04,+0.06]) ~ 0.005
    slow leg (group_zscore of a valuation field)                  ~ 1.0
  => the fast leg is diluted ~200x and contributes ~0 to the book. Proof:
    the slow leg ALONE has R +2.80% (reverse of x27_base_pehist's -2.80%);
    the whole portfolio's R is 2.74%. The fast leg adds nothing.
  Wave 30 repeated this scale error on 8 different slow legs, so its ranking is
  about the slow legs only (still valid for ranking, but it never tested a
  genuine blend).

  Wave 32 (earlier, same campaign) used `subtract(0.5, rank(x))` for the slow
  leg and got R/TO 0.655 (Mgn 13.12bps) vs my group_zscore leg's 0.253 --
  the BOUNDED centered rank is a much better book. But its fast leg was
  `multiply(0.3, rank(r20marsi_ret))`: rank is in [0,1] so it is ALWAYS
  POSITIVE and never expresses a directional fast view -- it only adds a
  constant-ish offset that group_zscore mostly absorbs.

WAVE 31 DESIGN:
  Both legs expressed as CENTERED RANKS (subtract(rank(x), 0.5), range
  [-0.5, +0.5]) so they are directly additive and neither can swamp the other:
    SLOW = subtract(0.5, rank(diff_current_vs_hist_pe_ratio))
           [cheap-vs-own-history is positive; centering is what B32 proved
            gives the high R/TO book]
    FAST = subtract(rank(oth566_r20marsi_ret), 0.5)
           [directional: the fast forecast's cross-sectional view, now
            two-sided instead of a positive offset]
  Weight the fast leg by c and search c. Under ONE outer ts_target_tvr_decay
  the portfolio turnover is locked, so c is a free allocation knob between
  "high-Sharpe fast leg" and "high R/TO slow leg" -- the exact trade-off the
  five hard gates demand.
  Also test whether the fast leg needs its own inner tvr (it does in the seed:
  a raw daily forecast has ~90% turnover and would otherwise dominate the
  book's turnover budget).

SIGN CONVENTION (economics):
  "expensive relative to own history is bad" -> subtract(0.5, rank(x)):
     high P/E-vs-history (rank 1) -> -0.5 (short). Matches the standalone
     reading of the field (Sh -1.09 un-reversed).
  "cheap within industry is good" -> subtract(rank(x), 0.5):
     high E/P percentile (rank 1) -> +0.5 (long).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
PE_HIST = "diff_current_vs_hist_pe_ratio"          # cov 0.9961, 7u/10a
PE_HIST_E = "diff_current_vs_hist_price_ratio_earnings"  # cov 0.9961, 4u/5a
EY_IND_PCTL = "earnings_yield_industry_percentile_fy1"    # cov 0.9947, 0u/0a

# centered slow leg: cheap-vs-own-history positive
SLOW_PE = f"subtract(0.5, rank({PE_HIST}))"
SLOW_PE_E = f"subtract(0.5, rank({PE_HIST_E}))"
# centered slow leg: cheap-within-industry positive (sign flipped vs the PE legs)
SLOW_EY = f"subtract(rank({EY_IND_PCTL}), 0.5)"
# centered fast leg: directional cross-sectional view
FAST_RAW = f"subtract(rank({R_RET}), 0.5)"
FAST_TVR = f"subtract(rank(ts_target_tvr_decay({R_RET}, target_tvr=0.08)), 0.5)"


def book(slow, fast, c, tvr):
    return (f"group_zscore(ts_target_tvr_decay(add({slow}, multiply({c}, {fast})), "
            f"target_tvr={tvr}), subindustry)")


W31 = {
 "batch": 33, "family": "scale_matched_centered_two_leg_book",
 "hypothesis": (
   "波次 33: 波次 28-30 的结构性缺陷是**两条腿尺度不匹配** —— 快腿 (ts_target_tvr_decay 后的原始预测, "
   "幅度 ~0.005) 与慢腿 (group_zscore 后的估值场, 幅度 ~1.0) 相差约 200 倍, 快腿被完全淹没。"
   "算术证据: 慢腿单独 R=+2.80%, 而整个组合 R=2.74% ⇒ 快腿净贡献约 0。"
   "波次 30 沿用了同一尺度错误 (只测慢腿排名, 从未真正混合)。"
   "波次 32 (本会话早前) 证明**中心化有界秩 `subtract(0.5, rank(x))` 的 R/TO 是 group_zscore 的 2 倍** "
   "(0.655 vs 0.253, Mgn 13.12bps), 但它的快腿用的是 `multiply(0.3, rank(ret))` —— rank ∈ [0,1] 恒正, "
   "只能表达「加权」而不能表达「方向」, 外层 group_zscore 后基本被吸收。"
   "本波把两条腿都写成**中心化有界秩** (subtract(rank(x),0.5), 均为 [-0.5,+0.5]), 从而可直接相加、"
   "互不淹没; 快腿乘权重 c 后在**单一外层 ts_target_tvr_decay** 下搜索 c。"
   "经济学: c 就是「快腿(20 日微观结构, 高 IR 高换手)」与「慢腿(估值自锚, 低换手高 R/TO)」之间的"
   "风险预算分配; 外层锁换手 ⇒ c 变成纯的自由分配旋钮, 直接瞄准五门联合所要求的 "
   "(Sharpe>=1.65 ∧ Mgn>=15bps ⇒ R/TO>=0.75 ∧ TO<=7.33%) 的前沿。"
   "本波同时测: 快腿是否需要自己的内层 tvr (原始预测换手 ~90%, 否则会吃掉换手预算); "
   "以及换用 earnings 口径的 P/E-vs-历史腿 与行业内 E/P 分位腿。"
 ),
 "settings": {"neutralization": "STATISTICAL", "decay": 0, "truncation": 0.08},
 "items": [
  {"id": "x33_slow_only_t03",
   "expr": f"group_zscore(ts_target_tvr_decay({SLOW_PE}, target_tvr=0.03), subindustry)",
   "ops": 4, "fields": ["other685:diff_current_vs_hist_pe_ratio"],
   "why": "基线: 中心化秩慢腿 + 外层 tvr0.03, 不含快腿。直接对照波次 32 的 A1VQkrdd (Mgn 13.12bps / Sh 0.53) "
          "验证本几何在 STATISTICAL 中性化下的表现 (波次 32 用 SUBINDUSTRY 且触发了 CONCENTRATED_WEIGHT)。"},

  {"id": "x33_c05_t03",
   "expr": book(SLOW_PE, FAST_RAW, 0.5, 0.03),
   "ops": 8, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "c=0.5: 快腿以半权重进入。中心化后两腿量级相当, 快腿的方向性观点 (订单簿 20 日预测) "
          "不再被稀释。若 Sharpe 从 0.53 升向 0.9+ 而 R/TO 仍 >0.5, 则 c 搜索方向正确。"},

  {"id": "x33_c10_t03",
   "expr": book(SLOW_PE, FAST_RAW, 1.0, 0.03),
   "ops": 8, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "c=1.0: 两腿等权。与 c=0.5 配对, 检验 Sharpe 对 c 的斜率。"},

  {"id": "x33_c20_t03",
   "expr": book(SLOW_PE, FAST_RAW, 2.0, 0.03),
   "ops": 8, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "c=2.0: 快腿主导。用于定位前沿另一端 (Sharpe 高但 R/TO 低), 与 c=0 端一起给出完整的 "
          "Sharpe-vs-R/TO 曲线, 从而确定是否存在同时满足两者的中间 c。"},

  {"id": "x33_c10_tvrfast_t03",
   "expr": book(SLOW_PE, FAST_TVR, 1.0, 0.03),
   "ops": 9, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "快腿自带内层 tvr0.08 版: 原始预测换手 ~90%, 不做内层平滑会吃掉外层换手预算。"
          "与 x33_c10_t03 配对, 隔离「快腿平滑」的影响。"},

  {"id": "x33_c10_tvrfast_t05",
   "expr": book(SLOW_PE, FAST_TVR, 1.0, 0.05),
   "ops": 9, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_pe_ratio"],
   "why": "同结构外层 tvr0.05: 换手放宽一档, 看 Sharpe/R/TO 的移动方向。"},

  {"id": "x33_pee_c10_t03",
   "expr": book(SLOW_PE_E, FAST_TVR, 1.0, 0.03),
   "ops": 9, "fields": ["other566:r20marsi_ret", "other685:diff_current_vs_hist_price_ratio_earnings"],
   "why": "换用 earnings 口径的 P/E-vs-历史腿 (波次 30 中 akKVno8W: Sh 1.05 / 0 FAIL / 2Y 1.30, "
          "是波次 30 最好的慢腿) + 中心化秩 + 快腿等权。"},

  {"id": "x33_ey_c10_t03",
   "expr": book(SLOW_EY, FAST_TVR, 1.0, 0.03),
   "ops": 9, "fields": ["other566:r20marsi_ret", "other685:earnings_yield_industry_percentile_fy1"],
   "why": "换用行业内 E/P 分位腿 (符号取反: 高 E/P 分位 = 便宜 = 做多)。经济含义: 相对自身历史便宜 "
          "(跨行业可比) vs 相对同行便宜 (行业内可比) 两种再定价锚的对照。"},
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W31['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W31, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W31['items'])} items)")
    for it in W31["items"]:
        print(f"  {it['id']:<24} fields={len(it.get('fields') or [])} {it['expr'][:110]}")
