# -*- coding: utf-8 -*-
"""冷字段分类清单 —— 为 S4 换核提供「结构 × 字段」的真实可选空间。

输出：按经济语义分组的 ac=0~2 字段清单（覆盖率 ≥0.75 者优先），
并标注每个字段在 S1/S2/S3 已测骨架里是否出现过（已测 ⇒ 该字段组合烧过）。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)
meta = P.load_meta()

# ---- 已测表达式 + 已测字段对 ----
tested_exprs, tested_pairs = [], set()
for f in ("batch_S1.json", "batch_S2.json", "batch_S3_EUR_ORIG.json", "batch_S3_CAMPAIGN.json"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    for it in d["items"]:
        e = it["expression"]
        tested_exprs.append(e)
        fs = sorted(P.field_ids(e))
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                tested_pairs.add((fs[i], fs[j]))

used_fields = set()
for e in tested_exprs:
    used_fields |= set(P.field_ids(e))
print(f"已测表达式 {len(tested_exprs)} 条；已测字段对 {len(tested_pairs)} 组；"
      f"已测字段 {len(used_fields)} 个\n")

# ---- 语义分组 ----
GROUPS = {
    "现金创造": r"free cash flow|cash flow|operating cash|capital expenditure",
    "资产/资本": r"total assets|total equity|book value|shareholders|tangible",
    "收入/销售": r"(^|\s)revenue|sales",
    "利润率": r"margin|operating income|gross profit",
    "回报率": r"return on|roa|roe|roic",
    "负债/杠杆": r"debt|leverage|liabilit|borrowing",
    "流动性": r"current ratio|quick ratio|cash and|working capital",
    "利息保障": r"interest cover|coverage",
    "折旧摊销": r"depreciat|amortiz",
    "股本": r"shares outstanding|share repurchase|buyback|dividend",
    "存货应收": r"inventor|receivab",
    "员工/人均": r"employee|per employee",
    "税率": r"tax rate|effective tax",
    "增长": r"growth|change in|percent change|yoy|year over year",
}
COMPILED = {k: re.compile(v, re.I) for k, v in GROUPS.items()}

rows = []
for f, v in meta.items():
    desc = v.get("description", "") or ""
    ac = v.get("alphaCount", 0)
    cov = v.get("coverage", 0)
    if ac > 2:
        continue
    grp = next((k for k, rx in COMPILED.items() if rx.search(desc)), "其他")
    rows.append((grp, f, desc, ac, cov, f in used_fields))

rows.sort(key=lambda r: (r[0], r[3], -r[4]))
cur = None
for grp, f, desc, ac, cov, used in rows:
    if grp != cur:
        cur = grp
        print(f"\n### {grp}")
    mark = "*" if used else " "
    print(f"  {mark}{f:<24} ac={ac} cov={cov:.3f}  {desc[:72]}")

print("\n(* = 该字段已在 S1/S2/S3 出现过)")

print("\n" + "=" * 100)
print("冷字段（ac=0，未被测过，覆盖率≥0.80）—— S4 换核的取材池")
print("=" * 100)
cold = [r for r in rows if r[3] == 0 and not r[5] and r[4] >= 0.80]
print(f"共 {len(cold)} 个")
for grp, f, desc, ac, cov, _ in cold:
    print(f"  {f:<24} {grp:<10} cov={cov:.3f}  {desc[:80]}")

json.dump([{"group": g, "field": f, "desc": d, "ac": a, "cov": c}
           for g, f, d, a, c, _ in cold],
          open(os.path.join(HERE, "cold_fields.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
