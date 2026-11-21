"""Dump other580 fields by economic family with full descriptions, to pin down semantics."""
import json
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "fields_other580_USA_TOP1000_d1.json"), encoding="utf-8"))
r = d["results"]
by_id = {x["id"]: x for x in r}

# window token inference from description (ids use _2 / no-suffix / _5d / _20d / _60d inconsistently)
def win_from_desc(s):
    s = (s or "").lower()
    m = re.search(r"(\d+)\s*[-‑–]?\s*day", s)
    if m:
        return m.group(1) + "d"
    return "?"


def show(fids, label):
    print(f"\n{'='*78}\n## {label}\n{'='*78}")
    for f in fids:
        x = by_id.get(f)
        if x is None:
            print(f"  {f}   ***MISSING***")
            continue
        print(f"  {f}   [win={win_from_desc(x.get('description'))} u={x.get('userCount')} a={x.get('alphaCount')}]")
        print(f"      {x.get('description')}")


# 1) EQUAL-weight, signed, all stats, default window (no suffix)
fams = collections.defaultdict(list)
for x in r:
    i = x["id"]
    if i.startswith("oth580") or i.startswith("average_predicted"):
        continue
    if re.search(r"_(5d|20d|60d)$", i) or i.endswith("_2"):
        continue
    sign = "neg" if i.startswith("negative_") else ("pos" if i.startswith("positive_") else "both")
    scope = "pct" if "percent_change" in i else "raw"
    weight = "log" if "log_weighted" in i else ("sqrt" if "sqrt_weighted" in i else "eq")
    m = re.search(r"(skewness|variance|average|mean|simple_sum|count|squared_sum|cubed_sum|sum)", i)
    stat = m.group(1) if m else "?"
    fams[(scope, sign, weight, stat)].append(i)

print("### FAMILY GRID (scope, sign, weight, stat) -> field ids")
for k in sorted(fams):
    print(f"{k}: {fams[k]}")

# 2) show key equal-weight default-window families in full
for key in [("raw", "both", "eq", "sum"), ("raw", "pos", "eq", "sum"), ("raw", "neg", "eq", "sum"),
            ("raw", "both", "eq", "average"), ("raw", "pos", "eq", "average"), ("raw", "neg", "eq", "average"),
            ("raw", "both", "eq", "count"), ("raw", "pos", "eq", "count"), ("raw", "neg", "eq", "count"),
            ("raw", "both", "eq", "variance"), ("raw", "both", "eq", "skewness"),
            ("raw", "both", "log", "sum"), ("raw", "both", "sqrt", "sum"),
            ("pct", "both", "eq", "sum"), ("pct", "pos", "eq", "sum"), ("pct", "neg", "eq", "sum"),
            ("pct", "both", "eq", "average"), ("pct", "pos", "eq", "average"), ("pct", "neg", "eq", "average"),
            ("pct", "both", "eq", "count"), ("pct", "pos", "eq", "count"), ("pct", "neg", "eq", "count"),
            ("pct", "both", "eq", "variance"), ("pct", "both", "eq", "skewness"),
            ("pct", "both", "log", "sum"), ("pct", "both", "sqrt", "sum")]:
    show(fams.get(key, []), f"{key}")

# 3) special / predicted
show([x["id"] for x in r if x["id"].startswith("oth580") or "predicted" in x["id"]], "SPECIAL + PREDICTED")

# 4) window variants for the equal/both/average+sum families
print(f"\n{'='*78}\n## WINDOW VARIANTS (all equal-weight 'both')\n{'='*78}")
for x in r:
    i = x["id"]
    if re.search(r"_(5d|20d|60d)$", i) and "sqrt_weighted" not in i and "log_weighted" not in i \
       and not i.startswith("negative_") and not i.startswith("positive_") \
       and ("average" in i or "sum" in i or "count" in i):
        print(f"  {i}  [win={win_from_desc(x.get('description'))}]")
        print(f"      {x.get('description')}")
