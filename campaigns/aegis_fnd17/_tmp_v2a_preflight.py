# -*- coding: utf-8 -*-
"""轴A 候选本地零配额预检（修正 stage3_preflight_v2 的 fnd17-only field_ids 缺陷）。"""
import ast, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P
import stage3_preflight_v2 as V2

GENERIC = re.compile(r"\b(?:fnd|oth)[a-z0-9]*_[A-Za-z0-9_]+\b")
P.field_ids = lambda expr: sorted(set(GENERIC.findall(expr)))

META = V2.load_multids_meta(["fundamental89", "other395"])

def show(tag, expr, reason, cp):
    r = V2.preflight_v2(expr, reason, cp, META, op_cap=6, max_datasets=2,
                        max_fields=3, min_coverage=0.55, max_alpha_count=5)
    c = r["checks"]
    print("--- %s" % tag)
    print("    expr : %s" % expr)
    print("    ok=%s ops=%d fields=%s ds=%s zm=%s cov=%s crowd=%s pv=%s win=%s unit=%s rt=%s" % (
        r["ok"], c["operator_count"], c["fields_used"], c["datasets_used"],
        c["top_level_profile"], c["coverage_ok"], c["crowding_ok"], c["pv_clean"],
        c["window_ok"], c["unit_consistent"], c["engine_redteam"]["verdict"]))
    for i in r["issues"]:
        print("    ISSUE: %s" % i)
    print()
    return r
