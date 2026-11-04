"""AEGIS Stage 5: 拉取候选 alpha 的逐年收益，计算正收益年数 (10 年)"""
import asyncio, json, os, sys
from collections import OrderedDict

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
AIDS = sys.argv[1:] or ["ZYQGlpXQ", "RREWapl1", "leAXzVG2", "mLo9AnO1", "MPYm8pdr"]


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    out = {}
    for aid in AIDS:
        d = await call(bm.get_alpha_details, alpha_id=aid)
        if not isinstance(d, dict) or d.get("error"):
            print(aid, "ERR", str(d)[:200]); continue
        code = d.get("code")
        st = d.get("status")
        m = d.get("metrics", {}) or {}
        ys = d.get("yearlyStats") or d.get("yearly_stats") or d.get("yearlyPerformance") or []
        by_year = OrderedDict()
        if isinstance(ys, list):
            for item in ys:
                if isinstance(item, dict):
                    y = item.get("year") or item.get("date") or item.get("period")
                    r = item.get("returns") or item.get("return") or item.get("pnl")
                    if y is not None:
                        by_year[str(y)[:4]] = r
        pos = sum(1 for v in by_year.values() if isinstance(v, (int, float)) and v > 0)
        out[aid] = {"code": code, "status": st, "sharpe": m.get("sharpe"),
                    "yearly": by_year, "positive_years": pos, "n_years": len(by_year),
                    "raw_keys": list(d.keys())}
        print(f"\n=== {aid} | status={st} sharpe={m.get('sharpe')}")
        print(f"    {code}")
        print(f"    正收益年数 {pos}/{len(by_year)}  {dict(by_year)}")
    json.dump(out, open(os.path.join(HERE, "yearly_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
