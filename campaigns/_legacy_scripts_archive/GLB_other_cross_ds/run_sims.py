"""
run_sims.py  —  AEGIS 跨数据集战役回测驱动器
读取 batch json (items=[{slot,expression,decay,neutralization,truncation,nan}])，按设置分组提交
multi-sim，静默轮询，落盘 sim_res + yearly stats，并打印紧凑对比表。
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as bm

REGION = "GLB"
UNIVERSE = "MINVOL1M"
DELAY = 1


async def submit_and_wait(exprs, decay, neut, trunc, nan, tag):
    loc = None
    for attempt in range(3):
        r = await bm.submit_multi_simulation(
            alpha_expressions=exprs, region=REGION, universe=UNIVERSE, delay=DELAY,
            decay=decay, neutralization=neut, truncation=trunc, test_period="P0Y0M",
            unit_handling="VERIFY", nan_handling=nan, pasteurization="ON", max_trade="OFF",
        )
        if r.get("error") == "RATE_LIMITED" or not r.get("location"):
            wait_s = r.get("retry_after") or 60
            print(f"[{tag}] RATE_LIMITED / no slot, sleep {wait_s}")
            await asyncio.sleep(float(wait_s) + 5)
            continue
        loc = r.get("location")
        if loc:
            break
        print(f"[{tag}] submit retry: {json.dumps(r)[:300]}")
        await asyncio.sleep(20)
    if not loc:
        return {"error": "SUBMIT_FAILED"}

    await asyncio.sleep(60)
    while True:
        s = await bm.check_multi_simulation(loc)
        st = s.get("status")
        if st in ("COMPLETE", "ERROR"):
            print(f"[{tag}] {st}")
            if st == "ERROR":
                print(json.dumps(s)[:800])
                return {"error": "SIM_ERROR", "raw": s}
            break
        if st == "RATE_LIMITED":
            await asyncio.sleep(45)
            continue
        await asyncio.sleep(max(20, int(s.get("retry_after") or 20)))
    return await bm.fetch_multi_simulation_result(loc)


def score(a):
    """从 alpha_results 单条记录提取核心指标"""
    m = a.get("metrics") or a.get("is") or {}
    checks = a.get("checks") or {}
    fails = [c.get("name") for c in checks.get("fail", []) if isinstance(c, dict)]
    warns = [c.get("name") for c in checks.get("warning", []) if isinstance(c, dict)]
    return {
        "id": a.get("id") or a.get("alpha_id"),
        "expression": a.get("expression") or (a.get("regular") or {}).get("code"),
        "sharpe": m.get("sharpe"),
        "fitness": m.get("fitness"),
        "returns": m.get("returns"),
        "turnover": m.get("turnover"),
        "margin_bps": (m.get("margin") or 0) * 10000 if m.get("margin") is not None else None,
        "drawdown": m.get("drawdown"),
        "fails": fails,
        "warnings": warns,
    }


async def yearly(alpha_id):
    try:
        y = await bm.get_alpha_yearly_stats(alpha_id)
        return {r["year"]: {"sharpe": r.get("sharpe"), "returns": r.get("returns"),
                            "margin": r.get("margin"), "turnover": r.get("turnover")}
                for r in y.get("records", [])}
    except Exception as e:
        return {"error": str(e)}


async def main():
    batch_file = sys.argv[1]
    with open(batch_file, encoding="utf-8") as f:
        meta = json.load(f)
    items = meta["items"]
    tag = meta.get("task_tag", os.path.basename(batch_file).replace(".json", ""))

    groups = {}
    for it in items:
        key = (it.get("decay", 0), it.get("neutralization", "COUNTRY"),
               it.get("truncation", 0.025), it.get("nan", "ON"))
        groups.setdefault(key, []).append(it)

    all_rows = []
    for (decay, neut, trunc, nan), its in groups.items():
        for i in range(0, len(its), 10):
            chunk = its[i:i + 10]
            exprs = [c["expression"] for c in chunk]
            print(f"\n=== {tag} | decay={decay} neut={neut} trunc={trunc} nan={nan} | {len(exprs)} exprs ===")
            for j, e in enumerate(exprs):
                print(f"  [{chunk[j]['slot']}] {e}")
            res = await submit_and_wait(exprs, decay, neut, trunc, nan, tag)
            rows = []
            if res.get("error"):
                print("!!", res.get("error"))
                all_rows.append({"error": res.get("error"), "exprs": exprs})
                continue
            for a in res.get("alpha_results", []):
                sc = score(a)
                sc["slot"] = chunk[len(rows)]["slot"] if len(rows) < len(chunk) else None
                if sc["id"]:
                    sc["yearly"] = await yearly(sc["id"])
                rows.append(sc)
            all_rows.extend(rows)
            for r in rows:
                print(f"  → [{r.get('slot')}] {r.get('id')} Sh={r.get('sharpe')} Fit={r.get('fitness')} "
                      f"Ret={r.get('returns')} TO={r.get('turnover')} Mgn={r.get('margin_bps')} "
                      f"fail={r.get('fails')} warn={r.get('warnings')}")
                y = r.get("yearly", {})
                if isinstance(y, dict) and "2014" in y:
                    print("     yearly:", {k: y[k]["sharpe"] for k in ["2014", "2015", "2016", "2017", "2019", "2021", "2023"] if k in y})

    out = os.path.join(os.path.dirname(os.path.abspath(batch_file)),
                       os.path.basename(batch_file).replace(".json", "_result.json"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"batch": tag, "rows": all_rows}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
