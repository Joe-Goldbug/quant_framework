"""零成本探针: 用平台内置 filter_sharpe 反查哪些 fnd90 字段具备正向 OS/IS Sharpe"""
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

HERE = os.path.dirname(os.path.abspath(__file__))


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    for ds, uni in (("fundamental90", "TOP1000"), ("fundamental90", "TOP3000")):
        pos = await call(bm.get_datafields, region="USA", dataset_id=ds, universe=uni,
                         delay=1, filter_sharpe=True)
        allf = await call(bm.get_datafields, region="USA", dataset_id=ds, universe=uni,
                          delay=1, filter_sharpe=False)
        ids_pos = {r["id"] for r in pos.get("results", [])}
        ids_all = {r["id"] for r in allf.get("results", [])}
        print(f"\n=== {ds} / {uni} ===  全字段 {len(ids_all)}, Sharpe>=0 字段 {len(ids_pos)}")
        surv = sorted(ids_pos)
        for i in surv:
            meta = next(r for r in allf["results"] if r["id"] == i)
            print(f"    {i:<46} cov={meta['coverage']:.3f} A={meta['alphaCount']}")
        print(f"  [被筛掉 {len(ids_all - ids_pos)} 个负 Sharpe 字段]")


if __name__ == "__main__":
    asyncio.run(main())
