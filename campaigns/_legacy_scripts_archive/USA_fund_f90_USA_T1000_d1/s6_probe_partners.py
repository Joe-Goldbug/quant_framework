# -*- coding: utf-8 -*-
"""Stage 1b: 跨数据集伙伴勘探 (USA/TOP1000/d1, fundamental 家族)"""
import asyncio, json, os, sys
from collections import Counter

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"; os.environ["no_proxy"] = "*"

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = sys.argv[1:] or ["fundamental72", "fundamental89", "other466", "fundamental17",
                              "fundamental3", "fundamental6", "fundamental28"]


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    summary = {}
    for ds in CANDIDATES:
        try:
            r = await call(bm.get_datafields, region="USA", dataset_id=ds, universe="TOP1000",
                           delay=1, filter_sharpe=False)
        except Exception as e:
            print(ds, "ERR", e); continue
        rows = r.get("results", []) if isinstance(r, dict) else []
        if not rows:
            print(f"{ds}: 0 fields"); continue
        types = Counter(x.get("type") for x in rows)
        covs = [x.get("coverage", 0) for x in rows]
        hi = sorted(rows, key=lambda x: -x.get("coverage", 0))[:6]
        summary[ds] = {"n": len(rows), "types": dict(types),
                       "cov_mean": round(sum(covs) / len(covs), 3),
                       "cov_max": round(max(covs), 3),
                       "sample_top_coverage": [{"id": x["id"], "cov": x["coverage"],
                                                "A": x.get("alphaCount"),
                                                "desc": (x.get("description") or "")[:80]} for x in hi]}
        print(f"\n=== {ds} === n={len(rows)} types={dict(types)} cov_mean={summary[ds]['cov_mean']} cov_max={summary[ds]['cov_max']}")
        for x in hi:
            print(f"    {x['id']:<40} cov={x['coverage']:.3f} A={x.get('alphaCount')}  {(x.get('description') or '')[:70]}")
        json.dump(rows, open(os.path.join(HERE, f"fields_{ds}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    json.dump(summary, open(os.path.join(HERE, "partner_probe.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n-> partner_probe.json")


if __name__ == "__main__":
    asyncio.run(main())
