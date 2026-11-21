"""AEGIS Stage-0 通道探针: 校验 brain-mcp 鉴权与网络链路"""
import asyncio, json, os, sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

brain_dir = os.environ.get("BRAIN_MCP_DIR")
if not brain_dir:
    for candidate in [
        "/home/kali/.gemini/antigravity/scratch/quant_research/brain-mcp",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../brain-mcp")),
        r"D:\brain-mcp"
    ]:
        if os.path.exists(candidate):
            brain_dir = candidate
            break

if brain_dir and brain_dir not in sys.path:
    sys.path.insert(0, brain_dir)
if brain_dir:
    os.environ.setdefault("BRAIN_MCP_CONFIG", os.path.join(brain_dir, "user_config.json"))

import main as bm


async def main():
    print("[1] authenticate ...")
    r = await bm.authenticate.fn() if hasattr(bm.authenticate, "fn") else await bm.authenticate()
    print(json.dumps(r, ensure_ascii=False)[:400])

    print("\n[2] get_datasets(region=USA, delay=1) ...")
    try:
        ds = await bm.get_datasets.fn(region="USA", delay=1) if hasattr(bm.get_datasets, "fn") else await bm.get_datasets(region="USA", delay=1)
    except TypeError:
        ds = await bm.get_datasets.fn() if hasattr(bm.get_datasets, "fn") else await bm.get_datasets()
    print(json.dumps(ds, ensure_ascii=False)[:1200])
    return ds


if __name__ == "__main__":
    asyncio.run(main())
