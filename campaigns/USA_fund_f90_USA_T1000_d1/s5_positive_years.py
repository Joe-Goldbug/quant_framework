"""AEGIS Stage 5: 由 PnL 序列计算逐年盈亏与正收益年数"""
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
AIDS = sys.argv[1:] or ["ZYQGlpXQ", "mLo9AnO1", "RREWapl1", "leAXzVG2", "MPYm8pdr", "xArgzxVN"]


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    out = {}
    for aid in AIDS:
        d = await call(bm.get_alpha_pnl, alpha_id=aid)
        recs = (d or {}).get("records", [])
        if not recs:
            print(aid, "no pnl"); continue
        by_year = OrderedDict()
        for date, pnl, *_ in recs:
            y = date[:4]
            by_year.setdefault(y, []).append(pnl)
        # 累计 PnL 序列: 年内增量 = 年末 - 年初(用上一年末)
        yearly = OrderedDict()
        prev_end = 0.0
        for y, vals in by_year.items():
            end = vals[-1]
            yearly[y] = end - prev_end
            prev_end = end
        pos = sum(1 for v in yearly.values() if v > 0)
        out[aid] = {"yearly": yearly, "positive": pos, "total": len(yearly)}
        print(f"{aid}  正收益年数 {pos}/{len(yearly)}   " +
              " ".join(f"{y}:{v/1e6:+.2f}M" for y, v in yearly.items()))
    json.dump(out, open(os.path.join(HERE, "positive_years.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
