# -*- coding: utf-8 -*-
"""抓取 USA/TOP1000/d1 全基本面数据集的字段清单（只 GET，零回测配额）。

缓存到 knowledge_base/fields/USA/<ds>.json，供字段池构建与冷字段筛选。
"""
import json
import os
import sys
import asyncio

sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

KB = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\knowledge_base\fields\USA"

# 按"拥挤度×覆盖度"排序的候选：valueScore 高 / userCount 低 = 蓝海
TARGETS = [
    "fundamental90", "fundamental69", "other401", "fundamental25",
    "fundamental89", "other395", "fundamental77", "fundamental45",
    "fundamental22", "fundamental1", "fundamental110", "fundamental13",
    "fundamental3", "other466", "fundamental23", "fundamental17",
]


async def fetch(ds):
    out = []
    off = 0
    while True:
        url = (f"{B.brain_client.base_url}/data-fields?instrumentType=EQUITY&region=USA"
               f"&delay=1&universe=TOP1000&dataset.id={ds}&limit=50&offset={off}")
        r = await B.brain_client._request("GET", url, timeout=120)
        if r.status_code == 429:
            for attempt in range(6):
                wait = 8 * (attempt + 1)
                print(f"    429 backoff {wait}s (offset={off})", flush=True)
                await asyncio.sleep(wait)
                r = await B.brain_client._request("GET", url, timeout=120)
                if r.status_code != 429:
                    break
        if r.status_code != 200:
            return out, f"HTTP {r.status_code} {r.text[:150]}"
        j = r.json()
        rows = j.get("results") or []
        out.extend(rows)
        off += len(rows)
        if off >= (j.get("count") or 0) or not rows:
            break
    return out, None


async def main():
    await B.brain_client.ensure_authenticated()
    summary = {}
    for ds in TARGETS:
        rows, err = await fetch(ds)
        if err:
            print(f"  ! {ds}: {err}", flush=True)
            summary[ds] = {"error": err}
            continue
        # 冷字段 = alphaCount 低（未被挖过）
        cold = [x for x in rows if (x.get("alphaCount") or 0) <= 2]
        summary[ds] = {
            "n_fields": len(rows),
            "n_cold(ac<=2)": len(cold),
            "n_matrix": sum(1 for x in rows if x.get("type") == "MATRIX"),
            "n_vector": sum(1 for x in rows if x.get("type") == "VECTOR"),
            "n_group": sum(1 for x in rows if x.get("type") == "GROUP"),
            "cov_mean": round(sum(x.get("coverage") or 0 for x in rows) / max(len(rows), 1), 4),
        }
        json.dump(rows, open(os.path.join(KB, f"{ds}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"  {ds:<16} n={len(rows):<5} cold(ac<=2)={len(cold):<5} "
              f"M={summary[ds]['n_matrix']:<5} V={summary[ds]['n_vector']:<4} "
              f"G={summary[ds]['n_group']:<4} cov~{summary[ds]['cov_mean']}", flush=True)
        await asyncio.sleep(1.5)
    json.dump(summary, open("fund_ds_field_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n保存完成")


asyncio.run(main())
