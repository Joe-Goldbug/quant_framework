# -*- coding: utf-8 -*-
"""S3 第二腿归因 + 换核方向量化（零新增仿真，纯数据分析）。

用 S3 的 16 次配对仿真回答三个问题：
  Q1 哪条第二腿最有信息量？（8 条结构 × 2 档）
  Q2 第一腿（FCF/资产 vs FCF/收入）哪个更好？
  Q3 「现金创造 vs 账面盈利」这个价差方向本身有没有效？
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# S3 实测（S3_settings_ab.json 是权威落盘）
rows = json.load(open(os.path.join(HERE, "S3_settings_ab.json"), encoding="utf-8"))

LEG_LABEL = {
    "S3_01_EUR_DIRECT": "营业利润率 ×0.5 (EUR冠军第二腿)",
    "S3_02_EUR_NOMULT": "营业利润率 (无×0.5)",
    "S3_03_FCF_ASSET": "营业利润率 ×0.5 + 分母换资产",
    "S3_04_FCF_VS_GROSS5Y": "五年毛利率中枢",
    "S3_05_FCF_VS_ROA": "TTM 资产回报率",
    "S3_06_FCF_ONLY": "无第二腿 (单腿)",
    "S3_07_ROA_VS_OPMGN": "ROA vs 营业利润率 (无FCF腿)",
    "S3_08_FCF_VS_MARGIN5Y": "五年净利率中枢",
}


def g(r, tier, k):
    v = r[tier].get(k)
    return v if isinstance(v, (int, float)) else 0


print("=" * 112)
print("Q1 第二腿信息量排名（战役档 decay8/STATISTICAL/nanON）")
print("=" * 112)
rank = sorted(rows, key=lambda r: -g(r, "CAMPAIGN", "sharpe"))
print(f"{'结构':<20}{'腿说明':<34}{'Sh':>7}{'2Y':>7}{'Sub':>7}{'Ret%':>8}{'Mgn':>8}{'TO%':>7}")
for r in rank:
    t = "CAMPAIGN"
    mgn = g(r, t, "returns") / g(r, t, "turnover") * 20 * 100 if g(r, t, "turnover") else 0
    print(f"{r['structure']:<20}{LEG_LABEL.get(r['structure'],''):<34}"
          f"{g(r,t,'sharpe'):>7.2f}{g(r,t,'two_year_sharpe'):>7.2f}"
          f"{g(r,t,'sub_universe_sharpe'):>7.2f}{g(r,t,'returns')*100:>8.2f}"
          f"{mgn:>8.2f}{g(r,t,'turnover')*100:>7.2f}")

print("\n" + "=" * 112)
print("Q2 第一腿：FCF/资产 vs FCF/收入（同样第二腿=营业利润率×0.5，两档各比）")
print("=" * 112)
pair = [r for r in rows if r["structure"] in ("S3_01_EUR_DIRECT", "S3_03_FCF_ASSET")]
for tier in ("EUR_ORIG", "CAMPAIGN"):
    a = next(r for r in pair if r["structure"] == "S3_01_EUR_DIRECT")   # FCF/Rev
    b = next(r for r in pair if r["structure"] == "S3_03_FCF_ASSET")    # FCF/Asset
    print(f"  {tier:<10} FCF/Rev  Sh={g(a,tier,'sharpe'):>5.2f} TO={g(a,tier,'turnover')*100:>5.2f}% "
          f"Ret={g(a,tier,'returns')*100:>5.2f}% 2Y={g(a,tier,'two_year_sharpe'):>5.2f}")
    print(f"  {tier:<10} FCF/Asset Sh={g(b,tier,'sharpe'):>5.2f} TO={g(b,tier,'turnover')*100:>5.2f}% "
          f"Ret={g(b,tier,'returns')*100:>5.2f}% 2Y={g(b,tier,'two_year_sharpe'):>5.2f}")
    print(f"  ⇒ ΔSh(Asset−Rev) = {g(b,tier,'sharpe')-g(a,tier,'sharpe'):+.2f}, "
          f"ΔRet = {(g(b,tier,'returns')-g(a,tier,'returns'))*100:+.2f}pp")

print("\n" + "=" * 112)
print("Q3 「现金创造 vs 账面盈利」价差方向是否有效？")
print("=" * 112)
s3_07 = next(r for r in rows if r["structure"] == "S3_07_ROA_VS_OPMGN")
print("  S3_07 = ROA vs 营业利润率（无 FCF 腿，纯账面口径内部价差）")
for tier in ("EUR_ORIG", "CAMPAIGN"):
    print(f"    {tier:<10} Sh={g(s3_07,tier,'sharpe'):>6.2f} "
          f"Ret={g(s3_07,tier,'returns')*100:>6.2f}% 2Y={g(s3_07,tier,'two_year_sharpe'):>6.2f}")
print("  ⇒ 对比 S3_05（FCF/Rev vs ROA）:")
s3_05 = next(r for r in rows if r["structure"] == "S3_05_FCF_VS_ROA")
for tier in ("EUR_ORIG", "CAMPAIGN"):
    print(f"    {tier:<10} Sh={g(s3_05,tier,'sharpe'):>6.2f} "
          f"Ret={g(s3_05,tier,'returns')*100:>6.2f}% 2Y={g(s3_05,tier,'two_year_sharpe'):>6.2f}")
print("  ⇒ 对比 S3_06（FCF 单腿，无价差）:")
s3_06 = next(r for r in rows if r["structure"] == "S3_06_FCF_ONLY")
for tier in ("EUR_ORIG", "CAMPAIGN"):
    print(f"    {tier:<10} Sh={g(s3_06,tier,'sharpe'):>6.2f} "
          f"Ret={g(s3_06,tier,'returns')*100:>6.2f}% 2Y={g(s3_06,tier,'two_year_sharpe'):>6.2f}")

print("\n" + "=" * 112)
print("Q4 换核方向量化：把 S3 全部 8 条按「是否含 FCF 现金腿」分组")
print("=" * 112)
with_fcf = [r for r in rows if r["structure"] not in ("S3_07_ROA_VS_OPMGN",)]
without_fcf = [r for r in rows if r["structure"] == "S3_07_ROA_VS_OPMGN"]
for tier in ("EUR_ORIG", "CAMPAIGN"):
    a = [g(r, tier, "sharpe") for r in with_fcf]
    b = [g(r, tier, "sharpe") for r in without_fcf]
    print(f"  {tier:<10} 含 FCF 腿 n={len(a)} Sh_mean={sum(a)/len(a):>6.2f} "
          f"Sh_max={max(a):>6.2f} | 无 FCF 腿 n={len(b)} Sh_mean={sum(b)/len(b):>6.2f}")

print("\n" + "=" * 112)
print("Q5 S3 冠军（GRP/ASSET/营业利润率）在 MARKET 档的达标画像反解")
print("=" * 112)
best = max(rows, key=lambda r: g(r, "CAMPAIGN", "sharpe"))
e = best["EUR_ORIG"]
print(f"  结构: {best['structure']}  战役档 Sh={g(best,'CAMPAIGN','sharpe'):.2f}")
print(f"  MARKET 档 (decay0/nanOFF) 实测: Sh={g(best,'EUR_ORIG','sharpe'):.2f} "
      f"TO={g(best,'EUR_ORIG','turnover')*100:.2f}% Ret={g(best,'EUR_ORIG','returns')*100:.2f}% "
      f"2Y={g(best,'EUR_ORIG','two_year_sharpe'):.2f}")
to = g(best, "EUR_ORIG", "turnover")
ret = g(best, "EUR_ORIG", "returns")
print(f"  Fit(Sh=1.58) = 1.58×√({ret:.4f}/max({to:.4f},0.125)) = "
      f"{1.58*(ret/max(to,0.125))**0.5:.3f}  ⇒ 需 Ret ≥ "
      f"{max(0.01, 1.0**2*max(to,0.125)/(1.58**2))*100:.2f}% 才能在 Sh=1.58 时 Fit=1.0")
mgn_needed_ret = 0.5 * to
print(f"  Margin≥10bp 需 Ret ≥ {mgn_needed_ret*100:.2f}%（当前 {ret*100:.2f}%，"
      f"{'✅' if ret >= mgn_needed_ret else '❌'}）")
print(f"  ⇒ 若把该结构在 MARKET 档的 Sharpe 从 {g(best,'EUR_ORIG','sharpe'):.2f} 抬到 1.58，")
print(f"    需要 Ret ≥ {max(mgn_needed_ret, 1.0**2*max(to,0.125)/(1.58**2))*100:.2f}%（EUR 冠军 6.76%）")
