"""AEGIS Stage 1: 数据集物理勘探 - 锁定 fundamental90 及 fundamental 家族"""
import asyncio, json, os, sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm

HERE = os.path.dirname(os.path.abspath(__file__))


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)

    print("[1] 拉取 USA / delay=1 全量数据集 ...")
    ds = await call(bm.get_datasets, region="USA", delay=1)
    results = ds.get("results", ds) if isinstance(ds, dict) else ds
    with open(os.path.join(HERE, "datasets_USA_d1.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"    总计 {len(results)} 个数据集 -> datasets_USA_d1.json")

    print("\n[2] fundamental 家族数据集 (含 fundamental90):")
    fund = [d for d in results if "fundamental" in d["id"].lower() or d.get("category") == "fundamental"]
    fund.sort(key=lambda d: d["id"])
    for d in fund:
        print(f"    {d['id']:<22} cat={d.get('category',''):<12} fields={d.get('fieldCount',0):<6} "
              f"alphas={d.get('alphaCount',0):<7} cov={d.get('coverage',0):.3f} "
              f"vs={d.get('valueScore')} pyr={d.get('pyramidMultiplier')}")
        print(f"        name: {d.get('name','')}")

    f90 = [d for d in results if d["id"] == "fundamental90"]
    print(f"\n[3] fundamental90 命中: {bool(f90)}")
    if f90:
        print(json.dumps(f90[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
