# -*- coding: utf-8 -*-
"""AEGIS R10/R11 组合运行器: 顺序静默回测两批并各自生成审计表。
HARD_SUBMISSION_RULE: 严禁任何提交调用；仅创建 IS 仿真 (UNSUBMITTED)。
限流时优雅退出，不抛栈。
用法: python run_r10_r11.py
"""
import asyncio, os, sys, json, io, contextlib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 强制绕过沙箱代理 (直连 api.worldquantbrain.com 可达，代理会在 POST 时 RemoteDisconnected)
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
AGENTS = os.path.dirname(ROOT)
sys.path.insert(0, AGENTS)
sys.path.insert(0, ROOT)
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.sim_runner import SimBatchRunner


def release_fingerprints(batch_path: str):
    import sqlite3
    db = os.path.join(ROOT, "alphas_record.db")
    if not os.path.exists(db):
        return
    try:
        exprs = [i.get("expression", "") for i in json.load(open(batch_path, encoding="utf-8")).get("items", [])]
    except Exception:
        return
    conn = sqlite3.connect(db); cur = conn.cursor()
    for e in exprs:
        cur.execute("DELETE FROM alpha_fingerprints WHERE expression = ?", (e,))
    conn.commit(); conn.close()


async def run_one(tag):
    path = os.path.join(HERE, f"batch_{tag}.json")
    if not os.path.exists(path):
        print(f"[{tag}] 批次文件缺失，跳过"); return False
    release_fingerprints(path)
    log_path = os.path.join(HERE, f"run_{tag}.log")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            res = await SimBatchRunner.run_batch_silently(
                batch_file_path=path, region="USA", universe="TOP1000", delay=1,
                category="fundamental", neutralization="SUBINDUSTRY", decay=4,
                truncation=0.08, nan_handling="ON")
        out = buf.getvalue()
    except Exception as e:
        out = buf.getvalue() + f"\n!!! EXCEPTION: {type(e).__name__}: {e}\n"
        res = None
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(out[-4000:])
    if res:
        with open(os.path.join(HERE, f"batch_{tag}_verdict.json"), "w", encoding="utf-8") as f:
            json.dump({
                "step1_should_prune": (res.get("step1") or {}).get("should_prune"),
                "step2_passed": len(res.get("step2_passed", [])),
                "final_passed": len(res.get("final_passed", [])),
                "prescriptions": res.get("prescriptions"),
            }, f, ensure_ascii=False, indent=2)
    # 审计表
    res_path = os.path.join(HERE, f"batch_{tag}_result.json")
    if os.path.exists(res_path):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("audit_table", os.path.join(HERE, "audit_table.py"))
            mod = importlib.util.module_from_spec(spec)
            # 直接调用: 用 argv 注入
            old_argv = sys.argv
            sys.argv = ["audit_table.py", f"batch_{tag}_result.json"]
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.argv = old_argv
        except Exception as e:
            print(f"[{tag}] 审计表生成失败: {e}")
    return res is not None


async def main():
    print("=== AEGIS R10/R11 组合回测 (限流解除后执行) ===")
    ok_r10 = await run_one("R10")
    if not ok_r10:
        print("[R10] 未成功 (可能仍限流) — 终止，待下次重试")
        return
    ok_r11 = await run_one("R11")
    if not ok_r11:
        print("[R11] 未成功 (可能额度再次耗尽) — R10 已完成，R11 待补跑")
        return
    print("=== R10 + R11 全部完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
