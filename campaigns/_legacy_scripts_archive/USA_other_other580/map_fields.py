"""Parse other580 field ids into a structural map: (scope, sign, weighting, stat, window)."""
import json
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

SIGNS = ["negative_", "positive_"]
WEIGHTS = ["sqrt_weighted", "log_weighted", "weighted"]
STATS = ["average", "mean", "simple_sum", "sum", "count", "variance", "skewness",
         "squared_sum", "cubed_sum", "cusum", "sisum", "sqsum", "rav", "tnc", "alt"]


def parse(fid):
    s = fid
    scope = "percent" if s.startswith("percent_change") or "percent_change" in s else "raw"
    if "percent" in s:
        scope = "percent"
    sign = "both"
    for sg in SIGNS:
        if sg in s:
            sign = sg.rstrip("_")
            break
    weight = "equal"
    for w in ("sqrt_weighted", "log_weighted"):
        if w in s:
            weight = w
            break
    if weight == "equal" and re.search(r"\bweighted\b", s) and "sqrt_weighted" not in s and "log_weighted" not in s:
        weight = "shares_weighted"
    stat = "?"
    for st in STATS:
        if st in s:
            stat = st
            break
    win = "?"
    m = re.search(r"(?:_|^)(5d|20d|60d)(?:_|$)", s)
    if m:
        win = m.group(1)
    pred = "predicted" in s
    return dict(scope=scope, sign=sign, weight=weight, stat=stat, window=win, pred=pred)


def main():
    d = json.load(open(os.path.join(HERE, "fields_other580_USA_TOP1000_d1.json"), encoding="utf-8"))
    r = d["results"]
    recs = []
    for it in r:
        p = parse(it["id"])
        p["id"] = it["id"]
        p["userCount"] = it.get("userCount", 0)
        p["alphaCount"] = it.get("alphaCount", 0)
        p["coverage"] = it.get("coverage", 0)
        p["description"] = it.get("description", "")
        recs.append(p)

    json.dump(recs, open(os.path.join(HERE, "field_map.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    print("=" * 70)
    print(f"TOTAL {len(recs)} fields")
    for dim in ("scope", "sign", "weight", "stat", "window", "pred"):
        c = collections.Counter(x[dim] for x in recs)
        print(f"{dim:8s}: {dict(c.most_common())}")
    print("=" * 70)

    # coverage / crowding
    covs = sorted(x["coverage"] for x in recs)
    print(f"coverage: min={covs[0]:.4f} p25={covs[len(covs)//4]:.4f} "
          f"med={covs[len(covs)//2]:.4f} max={covs[-1]:.4f}")
    nz = [x for x in recs if x["userCount"] or x["alphaCount"]]
    print(f"non-zero crowding: {len(nz)}")
    for x in sorted(nz, key=lambda z: -(z["userCount"] + z["alphaCount"])):
        print(f"   {x['id']}  u={x['userCount']} a={x['alphaCount']} cov={x['coverage']}")

    print("=" * 70)
    # cross-tab: sign x stat x window (raw scope)
    for scope in ("raw", "percent"):
        print(f"--- scope={scope} ---")
        tab = collections.defaultdict(list)
        for x in recs:
            if x["scope"] == scope and not x["pred"]:
                tab[(x["sign"], x["weight"], x["stat"], x["window"])].append(x["id"])
        # print a condensed matrix over sign x stat for weight=equal
        st = collections.Counter((x["sign"], x["stat"]) for x in recs if x["scope"] == scope and not x["pred"])
        for k, v in sorted(st.items()):
            print(f"   {k}: {v}")
    print("=" * 70)
    print("PREDICTED / SPECIAL fields:")
    for x in recs:
        if x["pred"] or x["stat"] in ("cusum", "sisum", "sqsum", "rav", "tnc", "alt"):
            print(f"   {x['id']}  [{x['description'][:110]}]")


if __name__ == "__main__":
    main()
