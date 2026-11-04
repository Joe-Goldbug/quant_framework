# -*- coding: utf-8 -*-
"""Stage 5 · 拉取跨数据集伙伴集的字段元数据（USA / TOP1000 / delay=1）

★ 新授权（2026-10-29）：允许跨**一个**数据集，表达式内最多来自两个不同数据集的字段。
  主数据集 = fundamental17（战役主体，冷启动面，fnd17_ 在本人 USA/d1 已提交 alpha 中使用数=0）。
  候选伙伴集（按 platform valueScore / alphaCount 排序取冷门）：
    fundamental89  Accrual based Earnings Model  (444 MATRIX, alphaCount=75,  valueScore=4)
    fundamental45  Earnings-call NLP            (12  MATRIX, alphaCount=36,  valueScore=2)
    fundamental110 Press Release / Revision      (26  VECTOR, alphaCount=103, valueScore=2)

只读端点（get_datafields），零仿真、零提交。
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

TARGETS = ["fundamental89", "fundamental45", "fundamental110"]


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(B.authenticate)
    out = {}
    for ds in TARGETS:
        try:
            res = await call(B.get_datafields, region="USA", dataset_id=ds,
                             universe="TOP1000", delay=1, filter_sharpe=False)
        except Exception as ex:
            print(f"  ❌ {ds}: {type(ex).__name__}: {ex}")
            continue
        rows = res.get("results", []) if isinstance(res, dict) else []
        out[ds] = rows
        types = {}
        for r in rows:
            t = r.get("type") or r.get("dataType") or "?"
            types[t] = types.get(t, 0) + 1
        acs = sorted(r.get("alphaCount", 0) for r in rows) if rows else []
        print(f"  {ds:<16} n={len(rows):<5} types={types} "
              f"ac: min={acs[0] if acs else '-'} med={acs[len(acs)//2] if acs else '-'} max={acs[-1] if acs else '-'}")

    path = os.path.join(HERE, "partner_fields.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {path}")


if __name__ == "__main__":
    asyncio.run(main())
