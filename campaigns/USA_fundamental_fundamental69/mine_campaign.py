# -*- coding: utf-8 -*-
"""
战役全量挖掘器 (Campaign Miner) —— 只读 GET，零配额消耗

用途：把本战役 (以及同账户同区域) 今日已创建的全部 IS alpha 拉下来，
在本地做**离线**门禁裁决与结构归纳，产出：
  1. 全量排名表 (按 Fitness)
  2. 按「字段组合」聚类，找出哪些信号族已被穷举
  3. 识别尚未被试过的构造 (供下一批设计)
  4. CONCENTRATED_WEIGHT 的跨表达式共性诊断

绝不调用任何仿真或提交接口 —— 只有 GET。
"""
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict

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

OUT = os.path.join(HERE, "campaign_mining.json")


async def main():
    rows = []
    offset = 0
    url = ("https://api.worldquantbrain.com/users/self/alphas"
           "?limit=100&offset=0&order=-dateCreated"
           "&settings.region=USA&stage=IS")
    pages = 0
    while url and pages < 12:
        resp = await bm.brain_client._request("GET", url)
        if resp.status_code != 200:
            print(f"[warn] GET {url} -> {resp.status_code}")
            break
        data = resp.json()
        for r in data.get("results", []):
            m = r.get("metrics") or {}
            ra = r.get("ra") or {}
            chk = r.get("checks") or {}
            code = r.get("code") or ""
            fails = sorted(set(
                [f.get("name") for f in (chk.get("fail") or []) if isinstance(f, dict)]
                + list(ra.get("ra_failed_checks") or [])))
            warns = sorted(set(
                [w.get("name") for w in (chk.get("warning") or []) if isinstance(w, dict)]
                + list(ra.get("ppa_failed_checks") or [])))
            rows.append({
                "id": r.get("id"), "code": code,
                "dateCreated": r.get("dateCreated"),
                "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
                "turnover": m.get("turnover"), "returns": m.get("returns"),
                "margin": m.get("margin"), "drawdown": m.get("drawdown"),
                "long_count": m.get("longCount"), "short_count": m.get("shortCount"),
                "sub_universe_sharpe": m.get("sub_universe_sharpe"),
                "two_year_sharpe": m.get("two_year_sharpe"),
                "investability_sharpe": m.get("investability_sharpe"),
                "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
                "self_correlation": m.get("selfCorrelation"),
                "prod_correlation": m.get("prodCorrelation"),
                "ra_failed": ra.get("ra_failed"),
                "authoritative_fail": fails,
                "warnings": warns,
                "settings": r.get("settings"),
                "fields": sorted(set(re.findall(r"fnd\d+_[a-z0-9_]+", code))),
                "groups": sorted(set(re.findall(
                    r"\b(market|sector|industry|subindustry|country)\b", code))),
                "ops": sorted(set(re.findall(r"([a-z_][a-z0-9_]*)\s*\(", code))),
            })
        url = data.get("next")
        offset += len(data.get("results", []))
        pages += 1
        print(f"[page {pages}] cumulative {len(rows)}")

    # ---- 字段族聚类 --------------------------------------------------
    fam = defaultdict(list)
    for r in rows:
        fam[tuple(r["fields"])].append(r)

    # ---- 骨架聚类 (去常数) ---------------------------------------------
    def skeleton(code):
        s = re.sub(r"\b\d+(\.\d+)?\b", "NUM", code)
        s = re.sub(r"\s+", "", s)
        return s

    skel = defaultdict(list)
    for r in rows:
        skel[skeleton(r["code"])].append(r)

    # ---- CONCENTRATED_WEIGHT 共性诊断 ----------------------------------
    cw = [r for r in rows if "CONCENTRATED_WEIGHT" in r["authoritative_fail"]]
    cw_no_cw = [r for r in rows if "CONCENTRATED_WEIGHT" not in r["authoritative_fail"]]

    def profile(rs):
        return {
            "n": len(rs),
            "mean_long": round(sum(r["long_count"] or 0 for r in rs) / max(len(rs), 1), 1),
            "mean_short": round(sum(r["short_count"] or 0 for r in rs) / max(len(rs), 1), 1),
            "mean_turnover": round(sum(r["turnover"] or 0 for r in rs) / max(len(rs), 1), 4),
            "ops_used": sorted(set(op for r in rs for op in r["ops"])),
            "groups_used": sorted(set(g for r in rs for g in r["groups"])),
        }

    summary = {
        "total_alphas": len(rows),
        "pages": pages,
        "n_with_cw_fail": len(cw),
        "n_without_cw_fail": len(cw_no_cw),
        "cw_profile": profile(cw),
        "no_cw_profile": profile(cw_no_cw),
        "field_families": {"|".join(k): {
            "n": len(v),
            "best_fitness": max((r["fitness"] or -9) for r in v),
            "best_sharpe": max((r["sharpe"] or -9) for r in v),
        } for k, v in sorted(fam.items(), key=lambda kv: -max((r["fitness"] or -9) for r in kv[1]))},
        "top_skeletons": {k[:150]: {
            "n": len(v),
            "best_fitness": max((r["fitness"] or -9) for r in v),
            "ids": [r["id"] for r in v][:6],
        } for k, v in sorted(skel.items(), key=lambda kv: -max((r["fitness"] or -9) for r in kv[1]))[:40]},
        "n_passing_all_gates": len([r for r in rows if not r["authoritative_fail"]]),
        "passing_ids": [r["id"] for r in rows if not r["authoritative_fail"]],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "alphas": rows}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:6000])
    print(f"\n[ok] wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
