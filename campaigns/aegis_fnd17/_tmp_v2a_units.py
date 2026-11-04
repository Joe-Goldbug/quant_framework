# -*- coding: utf-8 -*-
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P
import stage3_preflight_v2 as V2

META = V2.load_multids_meta(["fundamental89", "other395"])
rows = []
for f, m in META.items():
    d = m.get("description") or ""
    rows.append((P.unit_family(d), f, m.get("coverage") or 0, m.get("alphaCount") or 0, d))
from collections import Counter
print(Counter(r[0] for r in rows))
print()
for fam in ("ratio", "percent", "total", "per_share", "unbounded"):
    sel = sorted([r for r in rows if r[0] == fam and r[2] >= 0.60 and r[3] <= 5],
                  key=lambda x: -x[2])
    print("=== family=%s  n=%d ===" % (fam, len(sel)))
    for u, f, c, a, d in sel[:26]:
        print("   %-44s cov=%.4f ac=%d | %s" % (f, c, a, d.replace(chr(10),' ')[:118]))
    print()
