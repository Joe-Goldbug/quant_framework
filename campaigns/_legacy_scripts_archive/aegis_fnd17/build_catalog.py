# -*- coding: utf-8 -*-
"""
Stage 2 辅助 · 精简字段目录生成器 (把 450KB 原始元数据压成 ~25KB 可嵌入提示词)
输出：fnd17_catalog.md（按 9 条语义轴分组，含 ac/uc/cov/domain/sparse/desc + 孪生标注）
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".."))

SHORTLIST = os.path.join(AGENTS, "aegis_coldstart", "fnd17_shortlist.json")
RAW = os.path.join(AGENTS, "knowledge_base", "fields", "USA", "fundamental17_raw_full.json")
OUT = os.path.join(HERE, "fnd17_catalog.md")

# ---- 孪生字段识别：本数据集自带"去年同期/上期"口径的字段族 ----
TWIN_MARKERS = [
    ("prior trailing", "PTM"), ("prior 12 month", "PTM"), ("prior twelve", "PTM"),
    ("prior trailing twelve", "PTM"), ("1 year ago", "Y1A"), ("one year ago", "Y1A"),
    ("prior fiscal year", "PFY"), ("prior quarter", "PQ"), ("prior period", "PP"),
    ("prior month", "PM"), ("prior 3", "P3"), ("prior 2", "P2"),
    ("year ago", "Y1A"), ("prior annual", "PA"),
]

AXIS_LABEL = {
    "accrual_quality": "Q-Quality / Accrual (earnings quality, cash vs accrual)",
    "profitability_roa_roe": "Q-Profitability (ROA / ROE / margin)",
    "efficiency_dupont": "Q-Efficiency (turnover / DuPont drivers)",
    "leverage_solvency": "Q-Leverage & Solvency",
    "liquidity_coverage": "Q-Liquidity & Coverage",
    "growth_surprise": "Q-Growth & Surprise",
    "share_count_dilution": "Q-Share Count & Dilution",
    "cost_intensity_rd": "Q-Cost Intensity & R&D",
    "uncertainty_scale": "Q-Uncertainty / Scale (weights & gates, NOT standalone direction)",
}


def twin_tag(desc: str) -> str:
    d = desc.lower()
    for marker, tag in TWIN_MARKERS:
        if marker in d:
            return tag
    return ""


def main():
    short = json.load(open(SHORTLIST, encoding="utf-8"))
    raw = json.load(open(RAW, encoding="utf-8"))
    by = {f["id"]: f for f in raw}

    lines = []
    lines.append("# fundamental17 (USA / TOP1000 / delay 1) — Field Catalog")
    lines.append("")
    lines.append("402 fields total; 289 usable (40 nominal FX/currency codes + 73 embedded price-volume "
                 "are BANNED). 100% MATRIX type. Updated on quarterly/annual report cadence => "
                 "naturally low turnover; a bare cross-sectional LEVEL on a static field is a value "
                 "factor, not a signal.")
    lines.append("")
    lines.append("Legend per field: `id | ac=<alphaCount> uc=<userCount> cov=<coverage> | "
                 "<domain> | <sparse?> | <twin tag> | description`")
    lines.append("")
    lines.append("- `ac` = platform alphaCount (how many platform alphas already use it). "
                 "**ac<=5 is the anti-crowding target; ac=0 is virgin.**")
    lines.append("- `cov` < 0.80 => sparse (many NaN) => needs `ts_backfill` or NaN handling.")
    lines.append("- Twin tags: PTM=prior trailing 12M, Y1A=one year ago, PFY=prior fiscal year, "
                 "PQ=prior quarter, PP=prior period, PM=prior month, P2/P3=prior 2nd/3rd period. "
                 "**A current-period field + its twin is the dataset's crown jewel: it is a genuine "
                 "second-order surprise vs the company's OWN history, and twins are usually ac=0~3.**")
    lines.append("- Domains: `unbounded` = absolute amounts (sign follows accounting), "
                 "`[-1,1]` = signed ratio (can be +/-), `[0,inf)` = non-negative ratio "
                 "(leverage/turnover/coverage), `[-1,1]R` = ratio that may be positive-biased.")
    lines.append("")

    total = 0
    for axis, entries in short["axes"].items():
        lines.append(f"## {axis}  —  {AXIS_LABEL.get(axis, axis)}")
        lines.append("")
        for e in sorted(entries, key=lambda x: (x["ac"], x["id"])):
            fid = e["id"]
            r = by.get(fid, {})
            desc = (r.get("description") or e.get("desc") or "").strip()
            tag = twin_tag(desc)
            sp = "SP" if e.get("is_sparse") else "-"
            cov = e.get("cov")
            cov_s = f"{cov:.3f}" if isinstance(cov, (int, float)) else "?"
            lines.append(
                f"- `{fid}` | ac={e.get('ac', '?')} uc={e.get('uc', '?')} cov={cov_s} | "
                f"{e.get('domain', '?')} | {sp} | {tag or '-'} | {desc}"
            )
            total += 1
        lines.append("")

    # ---- 孪生配对总表：把 current + twin 显式配对，方便直接做二阶预期差 ----
    lines.append("## TWIN PAIRS (current vs own-history baseline) — the anti-crowding core")
    lines.append("")
    lines.append("These are verified present in fundamental17_raw_full.json. Each pair is a "
                 "genuine second-order expectation gap (current reading vs the SAME company one "
                 "period earlier), which satisfies anti-crowding law without any price data.")
    lines.append("")
    pairs = [
        ("fnd17_tcpaormtt", "fnd17_tcpaormtp", "TTM return on average assets: now vs prior TTM"),
        ("fnd17_ngmpnmtt", "fnd17_ngmpnmtp", "TTM net profit margin: now vs prior TTM"),
        ("fnd17_qtotd2eq", "fnd17_qtotd2eq2", "Total debt/equity: now vs one year ago"),
        ("fnd17_qcurratio", "fnd17_qcurratio2", "Current ratio: now vs one year ago"),
        ("fnd17_ttmintcov", "fnd17_ptmintcov", "Interest coverage: now vs prior TTM"),
        ("fnd17_shsoutbs", "fnd17_shsoutbs2", "Balance-sheet shares outstanding: now vs 1yr ago"),
        ("fnd17_ttmrev", "fnd17_ptmrev", "TTM revenue: now vs prior TTM"),
    ]
    for cur, old, label in pairs:
        a = by.get(cur, {})
        b = by.get(old, {})
        lines.append(
            f"- `{cur}` (ac={a.get('alphaCount', '?')}) vs `{old}` (ac={b.get('alphaCount', '?')}) "
            f"— {label}"
        )
    lines.append("")

    # ---- 被禁字段清单（供 agent 自检）----
    lines.append("## BANNED FIELD CLASSES (never use)")
    lines.append("")
    lines.append("- Nominal FX / currency codes (40): any `*currency_code*`, `*exrate*`.")
    lines.append("- Embedded price-volume (73): `fnd17_nprice`, `fnd17_mktcap`, `fnd17_ev_cur`, "
                 "`fnd17_pr1dayprc`, `fnd17_vol*`, `fnd17_priceavg*`, `fnd17_*price2bk*`, "
                 "`fnd17_*peexclxor*`, `fnd17_*spfcr*`, `fnd17_ebitda2ev*`, `fnd17_awcappspr`, "
                 "`fnd17_qwcappspr`, `fnd17_yield`, `fnd17_*pr*2rev*`.")
    lines.append("- Any external PV field: close / open / high / low / vwap / returns / volume / "
                 "cap / adv20.")
    lines.append("")

    txt = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[SAVED] {OUT}  ({len(txt)} chars, {total} field lines)")


if __name__ == "__main__":
    main()
