"""AEGIS Stage 1: VECTOR 类型安全实测探针 (单发，P0Y0M 极速)
目的: 确认 fnd90 字段是否必须 vec_* 包裹；同时取得 turnover(更新频次) / long-short count(零膨胀)
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


async def run_one(expr, tag):
    res = await call(bm.create_simulation, type="REGULAR", region="USA", universe="TOP1000",
                     delay=1, decay=0, neutralization="NONE", truncation=0.025,
                     test_period="P0Y0M", language="FASTEXPR", unit_handling="VERIFY",
                     nan_handling="ON", pasteurization="ON", alpha_expression=expr)
    if isinstance(res, dict) and res.get("error"):
        print(f"[{tag}] SUBMIT-ERROR: {str(res['error'])[:300]}")
        return None
    loc = res.get("location") or res.get("Location")
    print(f"[{tag}] accepted, loc={loc}")
    for i in range(40):
        await asyncio.sleep(10)
        chk = await call(bm.check_simulation, location=loc)
        st = chk.get("status")
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            print(f"[{tag}] status={st}")
            if st == "ERROR":
                print(f"[{tag}] err detail: {json.dumps(chk, ensure_ascii=False)[:600]}")
            return chk
    print(f"[{tag}] timeout")
    return None


async def main():
    await call(bm.authenticate)
    tests = [
        ("raw-naked", "fnd90_game_noa"),
        ("vec_avg", "vec_avg(fnd90_game_noa)"),
    ]
    out = {}
    for tag, expr in tests:
        r = await run_one(expr, tag)
        out[tag] = r
    with open(os.path.join(HERE, "vector_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("-> vector_check.json")


if __name__ == "__main__":
    asyncio.run(main())
