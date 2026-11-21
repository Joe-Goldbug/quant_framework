# -*- coding: utf-8 -*-
"""Stage 7: 候选搭档数据集扫描（只读 GET）。

目标：为 fundamental69 找一个互补的基本面搭档。fnd69 只有现金流量表科目 + 总资产 + 财年标签，
缺的是损益表（净利/营收）、股东权益、股本、负债、现金余额。

筛选口径：
  - 必须命中关键概念（净利/营收/权益/股本/负债/现金）
  - 优先低平台使用度（userCount / alphaCount 低 => PROD 相关性与多样性风险小）
"""
import asyncio
import json
import os
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm  # noqa: E402

CANDIDATES = ["fundamental17", "fundamental89", "fundamental77",
              "fundamental23", "fundamental13", "other466"]
KEYS = {
    "净利": r"net[_ ]?income|netincome|profit|earnings|net[_ ]?earn",
    "营收": r"revenue|sales|turnover",
    "权益": r"equity|stockholder|shareholder[_ ]?eq|book[_ ]?value",
    "股本": r"share[s]?[_ ]?(out|outstanding)|sharesout|common[_ ]?shares",
    "负债": r"liabilit|debt|borrow",
    "现金": r"\bcash\b|cash[_ ]?and|cash[_ ]?equiv",
    "总资产": r"total[_ ]?assets|assets[_ ]?total",
    "EBIT": r"ebit|operating[_ ]?income|oper[_ ]?profit",
    "营业成本": r"cogs|cost[_ ]?of[_ ]?revenue|cost[_ ]?of[_ ]?sales",
    "折旧": r"deprec|amortiz",
}


async def main():
    out = {}
    for ds in CANDIDATES:
        try:
            r = await bm.get_datafields(region="USA", dataset_id=ds, universe="TOP1000",
                                        delay=1, data_type="", search=None, filter_sharpe=False)
        except Exception as e:
            out[ds] = {"error": repr(e)[:200]}
            continue
        res = (r or {}).get("results", []) or []
        hits = {}
        for f in res:
            desc = (f.get("description") or "") + " " + (f.get("id") or "")
            low = desc.lower()
            for kname, pat in KEYS.items():
                if re.search(pat, low):
                    hits.setdefault(kname, []).append({
                        "id": f.get("id"), "cov": f.get("coverage"),
                        "ac": f.get("alphaCount"), "uc": f.get("userCount"),
                        "desc": (f.get("description") or "")[:70]})
        out[ds] = {"n_fields": len(res), "hits": {k: len(v) for k, v in hits.items()},
                   "detail": {k: v[:6] for k, v in hits.items()}}

    p = os.path.join(HERE, "stage7_partner_scan.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("[ok] wrote", p)
    for ds, d in out.items():
        if "error" in d:
            print(f"\n{ds}: ERROR {d['error']}")
            continue
        print(f"\n=== {ds} | 字段数 {d['n_fields']} | 概念命中 {d['hits']}")
        for k, v in d["detail"].items():
            for x in v[:3]:
                print(f"   [{k}] {x['id']} cov={x['cov']} ac={x['ac']} | {x['desc']}")


if __name__ == "__main__":
    asyncio.run(main())
