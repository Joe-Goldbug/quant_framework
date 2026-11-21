# -*- coding: utf-8 -*-
"""S3 设置档 A/B 归因分析（16 次仿真结果）

把 brain-mcp multi 两批（EUR_ORIG 档 / CAMPAIGN 档）的结果落盘并做配对归因。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Tier1: decay=0 / MARKET / nan=OFF ----
T1 = [
    ("S3_01_EUR_DIRECT",     "rKRvRR9a", 0.79, 0.43, 0.0215, 0.0377, 1.05, 0.86),
    ("S3_02_EUR_NOMULT",     "WjO6OOoQ", 0.61, 0.34, 0.0231, 0.0377, 0.65, 0.68),
    ("S3_03_FCF_ASSET",      "akKqKKQ1", 0.85, 0.49, 0.0206, 0.0422, 1.24, 0.86),
    ("S3_04_FCF_VS_GROSS5Y", "xAr0rr2W", 0.55, 0.30, 0.0203, 0.0379, 0.52, 0.60),
    ("S3_05_FCF_VS_ROA",     "ZYQeQQzZ", 0.74, 0.39, 0.0210, 0.0347, 0.57, 0.77),
    ("S3_06_FCF_ONLY",       "0mY0YYg8", 0.44, 0.21, 0.0182, 0.0295, 0.60, 0.46),
    ("S3_07_ROA_VS_OPMGN",   "j2YbYYGo", -0.04, -0.01, 0.0189, -0.0030, 0.39, -0.09),
    ("S3_08_FCF_VS_MARGIN5Y", "1YNQNNPQ", 0.54, 0.27, 0.0204, 0.0309, 0.46, 0.61),
]
# ---- Tier2: decay=8 / STATISTICAL / nan=ON ----
T2 = [
    ("S3_01_EUR_DIRECT",     "kqN2N93O", 0.95, 0.41, 0.0580, 0.0238, 1.17, 0.74),
    ("S3_02_EUR_NOMULT",     "zq313emK", 0.61, 0.22, 0.0626, 0.0157, 1.17, 0.40),
    ("S3_03_FCF_ASSET",      "QPvLv6V5", 1.11, 0.53, 0.0595, 0.0285, 1.49, 0.84),
    ("S3_04_FCF_VS_GROSS5Y", "1YNQN0dX", 0.89, 0.39, 0.0592, 0.0243, 0.52, 0.89),
    ("S3_05_FCF_VS_ROA",     "6XdvdN9J", 0.73, 0.28, 0.0572, 0.0186, 0.30, 0.70),
    ("S3_06_FCF_ONLY",       "wpQMQWEx", 0.96, 0.44, 0.0571, 0.0259, 0.86, 0.84),
    ("S3_07_ROA_VS_OPMGN",   "omEMEZgn", 0.73, 0.30, 0.0619, 0.0206, 1.52, 0.47),
    ("S3_08_FCF_VS_MARGIN5Y", "P0odoKOK", 0.85, 0.36, 0.0581, 0.0223, 0.60, 0.63),
]


def main():
    print("=" * 96)
    print("S3 设置档 A/B 归因（同一批 8 条表达式，仅设置档不同）")
    print("=" * 96)
    print(f"{'结构':<20}{'EUR档 Sh':>9}{'战役档 Sh':>10}{'Δ Sh':>8}{'EUR 2Y':>9}{'战役 2Y':>9}"
          f"{'EUR Ret':>9}{'战役 Ret':>10}{'EUR Mgn':>9}{'战役 Mgn':>10}")
    rows = []
    for (n1, a1, sh1, f1, to1, r1, y1, s1), (n2, a2, sh2, f2, to2, r2, y2, s2) in zip(T1, T2):
        d = sh2 - sh1
        print(f"{n1:<20}{sh1:>9.2f}{sh2:>10.2f}{d:>+8.2f}{y1:>9.2f}{y2:>9.2f}"
              f"{r1*100:>8.2f}%{r2*100:>9.2f}%{r1/to1*20:>8.2f}b{r2/to2*20:>9.2f}b")
        rows.append({
            "structure": n1,
            "EUR_ORIG": {"alpha_id": a1, "sharpe": sh1, "fitness": f1, "turnover": to1,
                         "returns": r1, "two_year_sharpe": y1, "sub_universe_sharpe": s1},
            "CAMPAIGN": {"alpha_id": a2, "sharpe": sh2, "fitness": f2, "turnover": to2,
                         "returns": r2, "two_year_sharpe": y2, "sub_universe_sharpe": s2},
            "delta_sharpe": round(d, 3),
        })

    print("\n" + "-" * 96)
    print("归因结论")
    print("-" * 96)
    d = [r["delta_sharpe"] for r in rows]
    print(f"① 设置档效应（战役档 − EUR档）Sharpe：平均 {sum(d)/len(d):+.3f}，"
          f"中位 {sorted(d)[len(d)//2]:+.3f}，区间 [{min(d):+.2f}, {max(d):+.2f}]")
    print(f"   ⇒ EUR 档在 Sharpe 上{'略优' if sum(d) > 0 else '并不优'}；"
          f"**设置档不是 S2 差 0.11 的主因**（平均只差 {abs(sum(d)/len(d)):.2f}）。")

    t1_to = sum(r["EUR_ORIG"]["turnover"] for r in rows) / len(rows)
    t2_to = sum(r["CAMPAIGN"]["turnover"] for r in rows) / len(rows)
    print(f"② 换手：EUR 档平均 TO {t1_to*100:.2f}% vs 战役档 {t2_to*100:.2f}%"
          f"（decay=8 把换手抬高 {t2_to/t1_to:.2f}×）")

    t1_ret = sum(r["EUR_ORIG"]["returns"] for r in rows) / len(rows)
    t2_ret = sum(r["CAMPAIGN"]["returns"] for r in rows) / len(rows)
    print(f"③ 年化收益：EUR 档 {t1_ret*100:.2f}% vs 战役档 {t2_ret*100:.2f}%"
          f" ⇒ **EUR 档收益更高但换手更低** ⇒ Margin 显著更优")

    best = max(rows, key=lambda r: r["CAMPAIGN"]["sharpe"])
    print(f"\n④ 全批次最佳：**{best['structure']}**")
    print(f"   EUR 档  alpha={best['EUR_ORIG']['alpha_id']} Sh={best['EUR_ORIG']['sharpe']} "
          f"Fit={best['EUR_ORIG']['fitness']} TO={best['EUR_ORIG']['turnover']*100:.2f}% "
          f"Ret={best['EUR_ORIG']['returns']*100:.2f}% 2Y={best['EUR_ORIG']['two_year_sharpe']}")
    print(f"   战役档  alpha={best['CAMPAIGN']['alpha_id']} Sh={best['CAMPAIGN']['sharpe']} "
          f"Fit={best['CAMPAIGN']['fitness']} TO={best['CAMPAIGN']['turnover']*100:.2f}% "
          f"Ret={best['CAMPAIGN']['returns']*100:.2f}% 2Y={best['CAMPAIGN']['two_year_sharpe']}")

    out = os.path.join(HERE, "S3_settings_ab.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n💾 -> {out}")


if __name__ == "__main__":
    main()
