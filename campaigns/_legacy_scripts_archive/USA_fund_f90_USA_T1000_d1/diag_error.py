"""诊断 multisim 子任务的真实报错"""
import asyncio, json, os, sys

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
import main as bm

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    data = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "batch_R1_result.json"), encoding="utf-8"))
    locs = [r["location"] for r in data["alpha_results"]]
    res = await call(bm.lookINTO_SimError_message, locations=locs[:3])
    print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
