"""
run_single.py — 并行单点仿真驱动器 (用于中性化/decay/截断设置扫描)
batch json: items=[{slot, expression, decay, neutralization, truncation, nan}]
每条独立提交 create_simulation, 并行轮询, 汇总核心指标。
"""
import asyncio, json, os, sys, time
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm

REGION, UNIVERSE, DELAY = "GLB", "MINVOL1M", 1


async def submit(it):
    r = await bm.create_simulation(
        alpha_expression=it["expression"], region=REGION, universe=UNIVERSE, delay=DELAY,
        decay=it.get("decay", 0), neutralization=it.get("neutralization", "COUNTRY"),
        truncation=it.get("truncation", 0.025), test_period="P0Y0M",
        unit_handling="VERIFY", nan_handling=it.get("nan", "ON"),
        pasteurization="ON", max_trade="OFF",
    )
    return it, r


async def poll(loc):
    while True:
        s = await bm.check_simulation(loc)
        st = s.get("status")
        if st == "COMPLETE":
            return s.get("alpha_id")
        if st in ("ERROR", "FAILED"):
            return None
        if st == "RATE_LIMITED":
            await asyncio.sleep(30)
            continue
        await asyncio.sleep(max(15, int(s.get("retry_after") or 15)))


async def main():
    bf = sys.argv[1]
    d = json.load(open(bf, encoding="utf-8"))
    print(f"submitting {len(d['items'])} single simulations")
    subs = []
    for it in d["items"]:
        it2, r = await submit(it)
        print(f"  [{it['slot']}] {r.get('submitted')} {r.get('location')} {r.get('error','')}")
        subs.append((it2, r.get("location")))
        await asyncio.sleep(2)

    rows = []
    for it, loc in subs:
        if not loc:
            rows.append({"slot": it["slot"], "error": "submit_failed"})
            continue
        aid = await poll(loc)
        row = {"slot": it["slot"], "id": aid, "expression": it["expression"],
               "neutralization": it.get("neutralization"), "decay": it.get("decay"),
               "truncation": it.get("truncation")}
        if aid:
            det = await bm.get_alpha_details(aid)
            isd = det.get("is") or {}
            checks = det.get("checks", {})
            row.update({
                "sharpe": isd.get("sharpe"), "fitness": isd.get("fitness"),
                "returns": isd.get("returns"), "turnover": isd.get("turnover"),
                "margin_bps": (isd.get("margin") or 0) * 1e4,
                "fails": [c.get("name") for c in checks.get("fail", []) if isinstance(c, dict)],
                "warns": [(c.get("name"), c.get("value")) for c in checks.get("warning", []) if isinstance(c, dict)],
            })
            reg = {}
            for c in checks.get("pass", []) + checks.get("fail", []) + checks.get("warning", []):
                if isinstance(c, dict) and c.get("name", "").startswith("LOW_GLB_"):
                    reg[c["name"].replace("LOW_GLB_", "").replace("_SHARPE", "")] = c.get("value")
            row["regions"] = reg
        rows.append(row)
        print(f"  → [{row['slot']}] {row.get('id')} Sh={row.get('sharpe')} Fit={row.get('fitness')} "
              f"Ret={row.get('returns')} TO={row.get('turnover')} Mgn={round(row.get('margin_bps') or 0,1)} "
              f"regions={row.get('regions')} fails={row.get('fails')}")

    out = bf.replace(".json", "_result.json")
    json.dump({"rows": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved", out)


asyncio.run(main())
