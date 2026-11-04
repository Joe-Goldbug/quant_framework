# -*- coding: utf-8 -*-
"""AEGIS Stage 1: fundamental69 字段物理画像 + 存量已提交 alpha 雷同排查。

只读操作：
  - get_datafields(USA, fundamental69, TOP1000, delay=1)  -> 字段元数据
  - get_user_alphas(stage=OS) 分页                        -> 已提交 alpha 清单
不发任何仿真、不调用任何提交接口。
"""
import asyncio
import json
import os
import re
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as bm  # noqa: E402

REGION, UNIVERSE, DELAY, DATASET = "USA", "TOP1000", 1, "fundamental69"
MAX_PAGES = 24          # 24 * 50 = 1200 条已提交 alpha 上限
PAGE = 50


async def main():
    out = {"region": REGION, "universe": UNIVERSE, "delay": DELAY, "dataset": DATASET}

    # ---------- A. 字段元数据 ----------
    try:
        df = await bm.get_datafields(region=REGION, dataset_id=DATASET,
                                     universe=UNIVERSE, delay=DELAY,
                                     data_type="", search=None, filter_sharpe=False)
        out["datafields_raw"] = df
    except Exception as e:
        out["datafields_error"] = repr(e)

    # ---------- B. 已提交 alpha 清单（PROD 相关性避让基线） ----------
    collected = []
    meta = {}
    for p in range(MAX_PAGES):
        try:
            r = await bm.get_user_alphas(stage="OS", limit=PAGE, offset=p * PAGE,
                                         order="-dateSubmitted", region=REGION)
        except Exception as e:
            meta[f"page{p}_error"] = repr(e)
            break
        res = (r or {}).get("results", []) or []
        if p == 0:
            meta["os_count"] = (r or {}).get("count")
        collected.extend(res)
        if not (r or {}).get("next"):
            break
        if len(res) < PAGE:
            break
        time.sleep(0.4)

    out["os_scan"] = {
        "pages": MAX_PAGES,
        "page_size": PAGE,
        "fetched": len(collected),
        "total_count": meta.get("os_count"),
        "errors": {k: v for k, v in meta.items() if k.endswith("error")},
    }

    slim = []
    for a in collected:
        code = (a.get("regular") or {}).get("code") or a.get("code") or ""
        slim.append({
            "id": a.get("id"),
            "status": a.get("status"),
            "dateSubmitted": a.get("dateSubmitted"),
            "region": (a.get("settings") or {}).get("region"),
            "universe": (a.get("settings") or {}).get("universe"),
            "delay": (a.get("settings") or {}).get("delay"),
            "sharpe": (a.get("is") or {}).get("sharpe"),
            "fitness": (a.get("is") or {}).get("fitness"),
            "turnover": (a.get("is") or {}).get("turnover"),
            "code": code,
        })
    out["os_alphas"] = slim

    # ---------- C. 命中 fnd69 的历史构造（雷同避让清单） ----------
    hits = [a for a in slim if "fnd69" in (a.get("code") or "")]
    out["fnd69_hits"] = hits
    out["fnd69_hit_summary"] = {
        "count": len(hits),
        "field_usage": {},
    }
    for a in hits:
        for f in set(re.findall(r"fnd69_[a-z0-9_]+", a.get("code") or "")):
            out["fnd69_hit_summary"]["field_usage"][f] = \
                out["fnd69_hit_summary"]["field_usage"].get(f, 0) + 1

    p = os.path.join(HERE, "stage1_profile.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[ok] wrote {p}")
    print(f"[os_scan] {out['os_scan']}")
    print(f"[fnd69 hits] {len(hits)} / {len(slim)} scanned")
    for a in hits[:40]:
        print(f"  - {a['id']} | sub={a['dateSubmitted']} | sharpe={a['sharpe']} | {a['code'][:150]}")


if __name__ == "__main__":
    asyncio.run(main())
