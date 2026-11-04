# -*- coding: utf-8 -*-
"""V2 轴A 本地预检：修正 stage3_preflight_v2 的 fnd17-only field_ids 缺陷。"""
import ast, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P
import stage3_preflight_v2 as V2

# --- 修复：通用字段抽取（覆盖全部数据集前缀）---
GENERIC = re.compile(r"\b(?:fnd|oth)[a-z0-9]*_[A-Za-z0-9_]+\b")
def generic_field_ids(expr):
    return sorted(set(GENERIC.findall(expr)))
P.field_ids = generic_field_ids   # patch

meta = V2.load_multids_meta(["fundamental89", "other395"])
print("meta fields:", len(meta))

FIELDS = [
 "fnd89_jones_accrual_r2_other_11","fnd89_best11_d1_current_t",
 "oth395_other_12_11","oth395_other_11_11",
 "oth395_jones_accrual_r2_other_11","fnd89_best11_d1_max",
 "fnd89_jones_accrual_r2_major_11","fnd89_other_12_11","fnd89_other_11_11",
 "fnd89_other_14_11",
]
for f in FIELDS:
    m = meta.get(f, {})
    print("  %-40s cov=%.4f ac=%s unit=%-10s | %s" % (
        f, m.get("coverage") or 0, m.get("alphaCount"),
        P.unit_family(m.get("description","")),
        (m.get("description") or "")[:95]))
