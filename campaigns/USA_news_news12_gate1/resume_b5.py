# -*- coding: utf-8 -*-
"""B5 恢复脚本: 从 state 文件续 poll + 回收 + 判决 (submit 已成功, 轮询进程被杀)."""
import asyncio
import glob
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule  # noqa: E402
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
REGION, DELAY = "USA", 1

# 找最新的 B5 批次文件与 state
batch_files = sorted(glob.glob(os.path.join(CAMPAIGN, "batch_gate9_S5_*.json")), key=os.path.getmtime)
batch_files = [f for f in batch_files if "_result" not in f]
assert batch_files, "未找到 B5 批次文件"
batch_path = batch_files[-1]
print(f"[resume] 批次文件: {batch_path}", flush=True)
batch = json.load(open(batch_path, encoding="utf-8"))
items = batch["items"]

state_path = os.path.join(CAMPAIGN, "state_gate9_S5.json")
lines = [json.loads(l) for l in open(state_path, encoding="utf-8") if l.strip()]
location = lines[-1]["location"]
print(f"[resume] location={location}", flush=True)


def build_summary(items, results, direction="S5"):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or r.get("is") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret = m.get("returns") or 0
        to = m.get("turnover") or 0
        rows.append({
            "slot": it["id"], "type": it["question_type"], "expression": it["expression"],
            "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": to, "returns": ret,
            "ret_over_to": (ret / to) if to else None,
            "drawdown": m.get("drawdown"), "margin_bps": (m.get("margin") or 0) * 10000,
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "sub_sharpe": m.get("sub_universe_sharpe"), "two_year_sharpe": m.get("two_year_sharpe"),
            "inv_sharpe": m.get("investability_sharpe"), "rn_sharpe": m.get("risk_neutralized_sharpe"),
            "ra_failed": ra.get("ra_failed"), "ra_failed_checks": ra.get("ra_failed_checks"),
            "fail_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("fail") or [])],
            "warning_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("warning") or [])],
        })
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    return {"direction": direction, "rows": rows,
            "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                     "step2": step2, "final": final}}


def print_table(summary):
    print(f"\n===== Gate1-Wave9 方向 {summary['direction']} (B5 归一器扫描, 恢复回收) =====", flush=True)
    print(f"{'槽':>2} {'类型':<28} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'Mgn':>6} {'DD%':>6} {'2Y':>6} {'sub':>5} {'rnSh':>5} {'L/S':>9} {'fail':<26} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:28]:<28} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:26]:<26} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)


async def main():
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(location)
            st = chk.get("status")
            print(f"  [poll-S5] {st} progress={chk.get('progress', 0)}", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                break
        except Exception as e:
            print(f"  [poll-S5] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)

    fetch = await BrainModule.fetch_multi_simulation_result(location)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[resume] fetch 空! {str(fetch)[:300]}", flush=True)
        return
    ts = int(time.time())
    result_path = os.path.join(CAMPAIGN, f"batch_gate9_S5_{ts}_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[resume] 结果已存: {result_path}", flush=True)

    by_code = {r.get("code", ""): r for r in results}
    ordered = []
    for it in items:
        r = by_code.get(it["expression"])
        ordered.append(r if r is not None else {"alpha_id": None, "code": it["expression"], "metrics": {}, "ra": {}, "checks": {}})
    summary = build_summary(items, ordered)
    sum_path = os.path.join(CAMPAIGN, "summary_gate9_S5.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[resume] 汇总已存: {sum_path}", flush=True)
    print("\n[B5] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
