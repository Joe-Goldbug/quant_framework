"""AEGIS Stage 1 (part 2): fundamental90 字段级物理画像勘探
Neutralization: NONE, Decay: 0 条件下拉取字段元数据（含 alphaCount 拥挤度）
"""
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
    print("[1] 拉取 fundamental90 / USA / TOP1000 / delay=1 全字段 (含弱 Sharpe 字段) ...")
    res = await call(bm.get_datafields, region="USA", dataset_id="fundamental90",
                     universe="TOP1000", delay=1, filter_sharpe=False)
    if isinstance(res, dict) and "error" in res:
        print("ERROR:", res["error"])
        return
    rows = res.get("results", [])
    with open(os.path.join(HERE, "f90_fields_raw.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"    字段总数: {len(rows)} -> f90_fields_raw.json")

    if rows:
        print("\n[2] 字段样本结构:")
        print(json.dumps(rows[0], ensure_ascii=False, indent=2))

    print("\n[3] 按 alphaCount(拥挤度) 升序 Top40 冷门字段:")
    keyed = [r for r in rows if r.get("alphaCount") is not None]
    keyed.sort(key=lambda r: (r.get("alphaCount", 0), r.get("id", "")))
    for r in keyed[:40]:
        print(f"    {r.get('id',''):<46} alphas={r.get('alphaCount',0):<5} "
              f"cov={r.get('coverage',0):.3f} type={r.get('dataType','') or r.get('type','')}")
        print(f"        {str(r.get('description',''))[:150]}")


if __name__ == "__main__":
    asyncio.run(main())
