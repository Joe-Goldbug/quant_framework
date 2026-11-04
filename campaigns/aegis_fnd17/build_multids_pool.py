# -*- coding: utf-8 -*-
"""构建 USA/TOP1000/d1 全基本面冷字段池（跨数据集，≤2 数据集/表达式）。

筛选口径：
  - type == MATRIX（VECTOR 需 vec_* 前置，基础层先不碰）
  - coverage >= 0.50（TOP1000 覆盖率，避免标���塌陷）
  - alphaCount <= 5（冷字段：几乎没被挖过 ⇒ 拥挤度低）
  - 排除 PV/价量污染（close/returns/volume/cap 等）
"""
import glob
import json
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.abspath(os.path.join(HERE, "..", "..", "knowledge_base", "fields", "USA"))

FUND_DATASETS = {
    "fundamental17": "Direct Fundamental Data (FactSet)",
    "fundamental69": "Quarterly Fundamental Data",
    "fundamental89": "Accrual based Earnings Model",
    "other395": "Accrual based Earnings Model (aggregated)",
    "fundamental3": "Fundamentals Data for US Equities (10-K/10-Q)",
    "other466": "Aggregated Fundamental Data",
    "fundamental13": "Comprehensive Fundamentals Dataset",
    "fundamental77": "Filing Fundamental Data (XBRL)",
    "fundamental23": "Fundamental Point in Time Data",
    "fundamental45": "Systematic mining of earnings calls",
}

PV = re.compile(r"(^|_)(close|open|high|low|volume|vwap|returns?|cap|marketcap|"
                r"adv|turnover|px|price|shares_out|dividend_yield)(_|$)", re.I)

pool = {}
for ds, dname in FUND_DATASETS.items():
    f = os.path.join(KB, f"{ds}.json")
    if not os.path.exists(f):
        print(f"  ! missing {ds}")
        continue
    try:
        rows = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print(f"  ! {ds}: {e}")
        continue
    if isinstance(rows, dict):
        continue
    keep = []
    for x in rows:
        if x.get("type") != "MATRIX":
            continue
        cov = x.get("coverage") or 0
        ac = x.get("alphaCount") or 0
        fid = x.get("id") or ""
        if cov < 0.50 or ac > 5:
            continue
        if PV.search(fid):
            continue
        keep.append({"id": fid, "desc": (x.get("description") or "").strip(),
                     "cov": round(cov, 4), "ac": ac, "uc": x.get("userCount") or 0})
    pool[ds] = {"dataset": ds, "name": dname, "fields": keep}
    print(f"  {ds:<16} cold MATRIX pool = {len(keep):<5} (of {len(rows)} total)")

json.dump(pool, open(os.path.join(HERE, "multids_cold_pool.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n总池 = {sum(len(p['fields']) for p in pool.values())} 字段，{len(pool)} 个数据集")

# ---- 语义分组（关键词），便于设计 Agent 快速取材 ----
GROUPS = {
    "cashflow": r"cash|cash flow|free cash|fcf|operating activ|capital expend|capex",
    "accrual_earn": r"accrual|earnings quality|net income|net profit|ebit|income",
    "balance_sheet": r"asset|liabilit|debt|equity|book value|leverage|working capital",
    "margin": r"margin|profitab|gross|net margin|operating margin|return",
    "growth": r"growth|change|increase|decrease|revision|surprise|estimate",
    "shareholder": r"dividend|buyback|repurchase|payout|yield|issuance|shareholder",
    "efficiency": r"turnover|inventory|receivab|payable|days|ratio|per share|perunit",
    "valuation": r"price|book|book-to|valuation|multiple",
}
print("\n=== 语义分组预览 ===")
for g, pat in GROUPS.items():
    cnt = 0
    for ds, p in pool.items():
        c = sum(1 for f in p["fields"] if re.search(pat, f["desc"], re.I))
        cnt += c
    print(f"  {g:<16} {cnt}")
