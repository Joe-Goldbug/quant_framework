"""读取探针 alpha 的完整 IS/OS 物理指标 (更新频次/覆盖/多空对称)"""
import asyncio, json, os, sys

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"; os.environ["no_proxy"] = "*"

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

AIDS = sys.argv[1:] or ["ZYQGwX9n"]


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    for aid in AIDS:
        d = await call(bm.get_alpha_details, alpha_id=aid)
        print("=" * 70)
        print("ALPHA", aid)
        print(json.dumps(d, ensure_ascii=False, indent=2)[:4000])
        try:
            y = await call(bm.get_alpha_pnl, alpha_id=aid)
            print("-- pnl keys --", list(y.keys()) if isinstance(y, dict) else type(y))
        except Exception as e:
            print("pnl err", e)


if __name__ == "__main__":
    asyncio.run(main())
