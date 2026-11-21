"""make_report.py — 生成四波次终审报告 FINAL_REPORT.md"""
import json
import os

HERE = os.path.dirname(__file__)
SEED = """hump(signed_power(group_zscore(ts_mean(s_log_1p(headline_positive_term_count_v2) * headline_positive_score_value_v2 / (ts_mean(headline_news_mention_count_v2, 30) + 0.1), 5), sector), 1.6), hump=0.003)"""
META = {
    "w1": ("Wave 1 — 病灶直击处方（语调重构）", 20),
    "w2": ("Wave 2 — 母本单因子消融网格", 20),
    "w3": ("Wave 3 — alpha 源头四条线索", 20),
    "w4": ("Wave 4 — decay 20→8 平滑度攻坚", 8),
}

lines = []
lines.append("# 58jYLNXn 定向处方攻坚 — 终审报告（AEGIS 种子因子定向优化模式）\n")
lines.append(f"**种子**：`58jYLNXn` · USA / news7 / delay 1 / TOP1000 · 必用字段 `headline_positive_term_count_v2`\n")
lines.append(f"**母本表达式**：`{SEED}`\n")
lines.append("**母本病灶**：Sharpe 1.03 < 1.58 · Fitness 0.60 < 1.00 · Margin 6.9bps < 10bps · "
             "多头 111 / 空头 716（书严重偏斜）· Investability Sharpe 0.55\n")
lines.append("\n> 门禁：`quant_framework/core/gatekeeper.py`（Step1 |Sharpe|≥1.0 → Step2 合规 → Final Sharpe≥1.58 / "
             "Fitness≥1.00 / Margin≥10bps / TO∈[5%,50%] / fail_num=0）\n")

summary_rows = []
for w, (title, decay) in META.items():
    p = os.path.join(HERE, f"batch_{w}_result.json")
    if not os.path.exists(p):
        continue
    rs = json.load(open(p, encoding="utf-8"))["alpha_results"]
    batch = json.load(open(os.path.join(HERE, f"batch_{w}.json"), encoding="utf-8"))
    types = {it["expression"]: it["type"] for it in batch["items"]}
    lines.append(f"\n## {title}\n")
    lines.append(f"settings：decay={decay} · neutralization=SECTOR · truncation=0.05 · nanHandling=OFF\n")
    lines.append("| 变体 | Sharpe | Fitness | TO% | Margin(bp) | Ret% | L/S | 2Y Sharpe | 平台 fail |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    best = None
    for r in rs:
        m = r.get("metrics") or {}
        t = types.get(r.get("code"), "?")
        fails = [c["name"] for c in r.get("checks", {}).get("fail", [])]
        ra = r.get("ra") or {}
        nc = ra.get("fail_num", ra.get("failed_ra_count", len(fails)))
        lines.append(
            f"| {t} | {m.get('sharpe',0):.2f} | {m.get('fitness',0):.2f} | {m.get('turnover',0)*100:.1f} | "
            f"{m.get('margin',0)*10000:.2f} | {m.get('returns',0)*100:.2f} | "
            f"{m.get('longCount')}/{m.get('shortCount')} | {m.get('two_year_sharpe',0):.2f} | {nc} |")
        if best is None or (m.get("sharpe", -9), m.get("fitness", -9)) > (best[1].get("sharpe", -9), best[1].get("fitness", -9)):
            best = (t, m, r.get("id"))
    if best:
        m = best[1]
        lines.append(f"\n**本波最佳**：`{best[0]}` → alpha `{best[2]}` · Sharpe {m.get('sharpe'):.2f} · "
                     f"Fitness {m.get('fitness'):.2f} · TO {m.get('turnover')*100:.1f}% · "
                     f"Margin {m.get('margin')*10000:.2f}bps\n")
        summary_rows.append((title, best[0], best[2], m))

lines.append("\n## 四波次汇总（最佳变体）\n")
lines.append("| 波次 | 最佳变体 | alpha | Sharpe | Fitness | TO% | Margin(bp) |")
lines.append("|---|---|---|---|---|---|---|")
for title, t, aid, m in summary_rows:
    lines.append(f"| {title.split('—')[0].strip()} | {t} | {aid} | {m.get('sharpe'):.2f} | "
                 f"{m.get('fitness'):.2f} | {m.get('turnover')*100:.1f} | {m.get('margin')*10000:.2f} |")

lines.append("""
## 杠杆归因结论（32 条回测的净结论）

| 杠杆 | 效应 | 证据 |
|---|---|---|
| `hump` + `signed_power` 移除 | **≈ 0** | 消融基准 1.03 vs 母本 1.03（W2#1） |
| `winsorize(std=3/4)` 替尾巴 | **≈ 0（decay20）/ −0.03（decay8）** | 1.04 / 1.03 |
| 中性化下沉 subindustry | **−0.55（严重负）** | 0.48（W2#5）；industry 0.65 |
| 指数半衰期 / 缩短记忆窗 | **−0.24 ~ −0.28** | 0.79（exp10）/ 0.85（exp5） |
| 10 / 20 日均值窗 | **−0.26 ~ −0.32** | 0.80 / 0.74（W4#2、#7） |
| IR / ts_rank 重排（质量化） | **−0.4 ~ −0.6** | 0.39 / 0.60 |
| 语调比率家族（pos−neg、log-odds、pos-share） | **−0.6 ~ −1.1（全灭）** | 0.03 ~ 0.46（W1 全批） |
| 有符号语调 × 词量强度 | −0.11 | 0.92（W3#4） |
| 全市场 zscore（替代 group_zscore） | **+0.04 Sharpe，+1.8bps Margin，+1.1pt 收益** | 1.01 / 0.64 / 8.04bps（W3#1） |
| 关注度基线 30→60→90 日 | **+0.02 → +0.05** | 1.06 → 1.08 → 1.11（W4） |
| settings.decay 20→8 | **+0.05** | 1.01→1.06（market_z）；1.03→1.00（sector_z） |
| 事件门控 trade_when(NMC>0) | −0.27 Sharpe，但 Margin 6.9bps、TO 14.4% | 0.76（W2#8） |

**物理结论**：母本 alpha 的唯一有效载体是「关注度归一化的正向词量 **level** 信号 + 短均值窗（5日）+ 全市场 zscore + 长关注度基线」。
任何把信号改写为语调比率、时间序列重排、或下沉到细颗粒度中性化的处方，都会摧毁 alpha——
因为母本的收益本质来自「被正面新闻持续超额覆盖」的较宽倾斜，而非行业内精细选股。

## 生产门禁终审（Final Gate）

- Step 1（|Sharpe|≥1.0）：W1 **全批熔断**；W2/W3/W4 **通过**（最高 1.11）
- Step 2（fail_num=0 且 Margin≥5bps 且 TO≤70%）：**四波 0/32 通过**
- Final（Sharpe≥1.58 / Fitness≥1.00 / Margin≥10bps / TO∈[5%,50%]）：**0/32 通过**

**最佳候选**：`MARKET_Z_DECAY8_BASE90` = Sharpe 1.11 / Fitness 0.63 / TO 28.0% / Margin 6.54bps（alpha id 见上表）
——距 1.58 仍差 0.47，距 Fitness 1.00 差 0.37，距 Margin 10bps 差 3.5bps。**不可提交。**

## 建议下一步（不在本次授权范围，需另行立项）

1. **换锚**：母本空头端 795/880 是「无新闻股」，本质是注意力折价因子，与量价/规模因子高度共线，
   这是 Investability Sharpe 仅 0.55、Margin 卡在 6~8bps 的根因。继续在此表达家族内调参，天化板 ≈1.15。
2. **若坚持 58jYLNXn 血统**：唯一仍有正梯度的方向是「关注度基线继续拉长（120/250 日）+ decay 4~8 + 全市场 zscore」，
   预期上限 1.15~1.20，仍无法过 1.58。
3. **若目标是过门禁**：应改为多字段交互（news7 内 pos/neg/mention 三轴 + subindustry 风险剥离），
   或换金字塔（USA/D1/NEWS 乘数 1.2 已是最优，可考虑 OPTION/ANALYST 未点亮塔）。
""")

out = os.path.join(HERE, "FINAL_REPORT.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("written ->", out)
