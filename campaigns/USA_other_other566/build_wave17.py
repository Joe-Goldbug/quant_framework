"""
build_wave17.py — wave 17: the neutralization sweep (biggest untested lever so far).

WAVE 16 RESULT: the confidence-leg variations did NOT help.
    ts_zscore(prob, 60) as the weight: Sh 0.50-0.68 (much WORSE than raw prob)
    group_rank(prob, industry) as the weight: Sh 0.92 (slightly worse than raw
        prob's 1.00, but with Mgn 7.27 vs 7.39 — essentially a wash)
  => RAW confidence is the best confidence-leg usage; the leg is exhausted.

WAVE 15/16 RESULT: along the single `tvr` knob the three metrics move in
OPPOSING directions and no setting satisfies all three:
    tvr 0.05 -> Sh 0.66, Fit 0.31, Mgn 10.39  (margin passes)
    tvr 0.08 -> Sh 0.91, Fit 0.51, Mgn  9.51
    tvr 0.12 -> Sh 1.00, Fit 0.61, Mgn  7.39  (fitness best, ZERO platform fails)
    tvr 0.15 -> Sh 1.00, Fit 0.55, Mgn  6.00
    tvr 0.20 -> Sh 0.98, Fit 0.46, Mgn  4.48

THE LEVER NEVER SWEPT IN 16 WAVES: **the platform's `neutralization` setting.**
Every single alpha so far used neutralization=INDUSTRY (the AEGIS default). The
platform offers, for USA/D1/TOP1000:
    NONE | REVERSION_AND_MOMENTUM | STATISTICAL | CROWDING | FAST | SLOW |
    MARKET | SECTOR | INDUSTRY | SUBINDUSTRY | SLOW_AND_FAST

This matters mechanically, not just cosmetically. Neutralization is how the
platform removes market/sector/industry beta from the alpha BEFORE the
long-short book is formed. Because:
  * returns are computed on the NEUTRALIZED portfolio, a different neutralization
    changes the realised returns, the Sharpe, the turnover AND the margin;
  * our alpha is a machine-learning forecast whose raw output carries a large
    market/sector beta component (a model that predicts "up" for everything
    contributes no cross-sectional dispersion but does contribute beta);
  * SUBINDUSTRY / STATISTICAL / NONE remove very different amounts of that beta.
    In particular NONE keeps the beta, which can RAISE Sharpe if the forecast
    has genuine market-timing skill, but usually LOWERS dispersion.

Concretely, the current best (tvr 0.12) has returns 4.60% at TO 12.5%. The
algebra says we need returns >= 6.25% at that turnover for Mgn 10. A less
aggressive neutralization (NONE / MARKET) could raise returns by keeping the
directional component, while SUBINDUSTRY could raise Sharpe by removing more
idiosyncratic sector noise.

Wave 17 sweeps the full neutralization menu at the two operating points that
matter (tvr 0.12 = fitness peak, tvr 0.08 = margin peak), plus two truncation
probes. Every slot keeps the champion expression (2 fields, 3 operators) and
changes ONLY the platform setting.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

R_RET = "oth566_r20marsi_ret"
R_P5 = "oth566_r20marsi_prob_5"
CORE = f"multiply({R_RET}, {R_P5})"


def slot(sid, tvr, neutralization, truncation=0.08, note=""):
    return {
        "id": sid,
        "expr": f"group_zscore(ts_target_tvr_decay({CORE}, target_tvr={tvr}), industry)",
        "ops": 3, "fields": [R_RET, R_P5], "decay": 0,
        "neutralization": neutralization, "truncation": truncation,
        "why": note,
    }


W17 = {
 "batch": 17, "family": "neutralization_sweep_on_champion_core",
 "hypothesis": (
   "波次 17: 扫描**平台 neutralization 设置** —— 这是 16 个波次里从未动过的最大杠杆, 全部 alpha 都用了 "
   "AEGIS 默认的 INDUSTRY。平台对 USA/D1/TOP1000 提供 NONE / MARKET / SECTOR / INDUSTRY / SUBINDUSTRY / "
   "STATISTICAL / CROWDING / FAST / SLOW / REVERSION_AND_MOMENTUM / SLOW_AND_FAST。"
   "这不是装饰性参数: 中性化是在**形成多空组合之前**剥离市场/行业 beta, 因此它同时改变 realized returns、"
   "Sharpe、换手与 Margin。我们的 alpha 是机器学习预测, 其原始输出天然带有很大的市场/行业 beta 成分 —— "
   "一个对所有股票都预测「涨」的模型不提供横截面区分度却贡献 beta; 而本数据集的预测模型极可能是行业条件性的 "
   "(订单簿形态与行业流动性结构强相关), 这使 INDUSTRY 中性化可能**误杀了真实的行业内信息**。"
   "SUBINDUSTRY 或 STATISTICAL 剥得更干净 ⇒ 横截面区分度更纯 ⇒ Sharpe 上升; NONE / MARKET 保留方向性 beta ⇒ "
   "若模型有真实择时能力则 returns 上升 ⇒ Margin 上升 (margin_bps = returns/turnover*20)。"
   "本波在两个关键工作点各扫一半菜单 (tvr=0.12 Fitness 峰 / tvr=0.08 Margin 峰), 外加两个 truncation 探针。"
 ),
 "items": [
  slot("w17_neu_none_t12", 0.12, "NONE",
       note="完全不做 beta 中性化: 保留模型的市场择时与行业方向成分。若模型有真实择时能力, returns 上升 → Margin 上升; 若没有, Sharpe 崩塌即为判据。"),
  slot("w17_neu_market_t12", 0.12, "MARKET",
       note="只剥离市场 beta, 保留行业结构: 检验行业条件性预测是否是真信息。"),
  slot("w17_neu_subind_t12", 0.12, "SUBINDUSTRY",
       note="剥离到细分行业: 横截面区分度最纯, 预期 Sharpe 上升 (若信号确实是选股而非选行业)。"),
  slot("w17_neu_stat_t12", 0.12, "STATISTICAL",
       note="统计中性化 (本仓库 proven_templates 的分析师模板最佳设置): 用统计方法而非固定分组剥离共同因子, 预期更贴合模型的真实因子结构。"),
  slot("w17_neu_none_t08", 0.08, "NONE",
       note="NONE @ tvr=0.08 (Margin 峰工作点): 若 NONE 能把 returns 抬上去, Margin 有望突破 10bps。"),
  slot("w17_neu_subind_t08", 0.08, "SUBINDUSTRY",
       note="SUBINDUSTRY @ tvr=0.08 (Margin 峰工作点): 更纯的横截面 + 更低换手, 与 NONE 对照以确定收益来源。"),
  slot("w17_neu_none_t12_tr004", 0.12, "NONE", truncation=0.04,
       note="truncation 探针: 截尾收紧到 0.04, 检验集中持仓是否是 NONE 下收益的拖累项。"),
  slot("w17_neu_market_t08", 0.08, "MARKET",
       note="MARKET @ tvr=0.08: 第三个中性化口径在 Margin 工作点上的读数, 与 NONE/SUBINDUSTRY 构成三点对照。"),
 ]}

if __name__ == "__main__":
    p = os.path.join(HERE, f"batch_{W17['batch']:02d}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(W17, f, indent=2, ensure_ascii=False)
    print("wrote", p, f"({len(W17['items'])} items)")
