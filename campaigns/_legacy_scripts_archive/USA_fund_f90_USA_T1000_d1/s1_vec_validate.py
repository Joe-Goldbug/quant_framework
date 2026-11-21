"""验证 vec_* 包裹后 ts_zscore 是否合法 (单点极速验证)"""
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


async def call(fn, **kw):
    f = getattr(fn, "fn", fn)
    return await f(**kw)


async def main():
    await call(bm.authenticate)
    expr = "ts_zscore(vec_avg(fnd90_game_noa), 252)"
    res = await call(bm.create_simulation, region="USA", universe="TOP1000", delay=1,
                     decay=0, neutralization="NONE", truncation=0.025, test_period="P0Y0M",
                     language="FASTEXPR", unit_handling="VERIFY", nan_handling="ON",
                     pasteurization="ON", alpha_expression=expr)
    print("submit:", json.dumps(res, ensure_ascii=False)[:400])
    loc = res.get("location")
    if not loc:
        return
    for i in range(45):
        await asyncio.sleep(8)
        chk = await call(bm.check_simulation, location=loc)
        st = chk.get("status")
        print(f"poll#{i+1} {st}")
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED", "FAIL"):
            print(json.dumps(chk, ensure_ascii=False, indent=2)[:2500])
            return


if __name__ == "__main__":
    asyncio.run(main())
