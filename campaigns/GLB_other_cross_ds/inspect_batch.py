"""inspect_batch.py — 拉取某批次所有 alpha 的区域 Sharpe 与全量 checks"""
import asyncio, json, os, sys
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm


def region_map(checks):
    out = {}
    for c in checks.get("pass", []) + checks.get("fail", []) + checks.get("warning", []):
        if not isinstance(c, dict):
            continue
        n = c.get("name", "")
        if n.startswith("LOW_GLB_"):
            out[n.replace("LOW_GLB_", "").replace("_SHARPE", "")] = c.get("value")
    return out


async def main():
    res_file = sys.argv[1]
    d = json.load(open(res_file, encoding="utf-8"))
    for r in d["rows"]:
        aid = r.get("id")
        if not aid:
            continue
        det = await bm.get_alpha_details(aid)
        checks = det.get("checks", {})
        isd = det.get("is") or {}
        print(f"[{r.get('slot')}] {aid} Sh={isd.get('sharpe')} Fit={isd.get('fitness')} "
              f"Ret={isd.get('returns')} TO={isd.get('turnover')} Mgn={(isd.get('margin') or 0)*1e4:.1f}")
        print("   regions:", region_map(checks))
        print("   fails:", [c.get("name") for c in checks.get("fail", []) if isinstance(c, dict)])
        print("   warns:", [(c.get("name"), c.get("value")) for c in checks.get("warning", []) if isinstance(c, dict)])
    print(json.dumps({"inspected": res_file}))


asyncio.run(main())
