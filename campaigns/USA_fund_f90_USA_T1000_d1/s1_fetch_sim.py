"""AEGIS Stage 1: 拉取指定 simulation 结果 (物理探针)"""
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

LOC = sys.argv[1] if len(sys.argv) > 1 else None


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    loc = LOC or "https://api.worldquantbrain.com/simulations/2MpLfU8pE4wG9n71eVmHIkUQ"
    for i in range(60):
        chk = await call(bm.check_simulation, location=loc)
        st = chk.get("status")
        print(f"poll#{i+1} status={st}")
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            print(json.dumps(chk, ensure_ascii=False, indent=2)[:3000])
            return
        await asyncio.sleep(10)
    print("still running")


if __name__ == "__main__":
    asyncio.run(main())
