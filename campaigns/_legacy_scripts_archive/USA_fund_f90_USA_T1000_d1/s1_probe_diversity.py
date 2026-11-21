"""AEGIS Stage 1 (part 3): 研究员存量 Alpha 多样性基线勘查 (用于 ProdCorr 防撞车)"""
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
    all_rows = []
    for stage in ("OS", "IS"):
        off = 0
        while True:
            res = await call(bm.get_user_alphas, stage=stage, limit=50, offset=off,
                             region="USA", order="-dateCreated")
            if isinstance(res, dict) and "error" in res:
                print("ERR", stage, res["error"][:200]); break
            rows = res.get("results", [])
            if not rows:
                break
            for r in rows:
                r["_stage"] = stage
            all_rows.extend(rows)
            cnt = res.get("count")
            off += len(rows)
            if cnt is not None and off >= min(int(cnt), 400):
                break
            if len(rows) < 50:
                break
    with open(os.path.join(HERE, "user_alphas_baseline.json"), "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    print(f"存量 Alpha 总数: {len(all_rows)} -> user_alphas_baseline.json")

    # 统计 fnd90 相关使用
    hit = [r for r in all_rows if "fnd90" in (r.get("expression") or "")]
    print(f"\n已使用 fnd90 字段的存量 Alpha: {len(hit)}")
    for r in hit:
        print(f"   {r.get('id')} | {(r.get('expression') or '')[:110]}")

    print("\n[OS 已提交] 近期 25 条表达式:")
    osr = [r for r in all_rows if r.get("_stage") == "OS"][:25]
    for r in osr:
        st = r.get("settings", {}) or {}
        print(f"   {r.get('id')} | {st.get('region')}/{st.get('universe')}/d{st.get('delay')} | "
              f"sh={r.get('is',{}).get('sharpe') if isinstance(r.get('is'),dict) else None} | "
              f"{(r.get('expression') or '')[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
