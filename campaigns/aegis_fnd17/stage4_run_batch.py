# -*- coding: utf-8 -*-
"""
Stage 4 · 静默回测执行器 (AEGIS fundamental17 / USA TOP1000 d1)
零提交纪律：HARD_SUBMISSION_RULE —— 本脚本**只做回测仿真**，绝不调用提交接口。
设置固定：neutralization=STATISTICAL, decay=8, truncation=0.08,
          pasteurization=ON, unit_handling=VERIFY, nan_handling=ON, language=FASTEXPR

用法：python stage4_run_batch.py [batch_S1.json]
"""
import asyncio, json, os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.sim_runner import SimBatchRunner
from quant_framework.core.gatekeeper import Gatekeeper

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "fundamental"
NEUTRALIZATION = "STATISTICAL"
DECAY = 8
TRUNCATION = 0.08


def summarize(batch_path, res):
    """把 raw result 整理成一张人读的表（含 10 年正收益年数、checks、三大防骗指标）。"""
    out = {"batch": os.path.basename(batch_path), "step1": res.get("step1"), "slots": []}
    try:
        raw = json.load(open(batch_path.replace(".json", "_result.json"), encoding="utf-8"))
    except Exception:
        raw = {"alpha_results": []}
    results = raw.get("alpha_results", [])
    for i, r in enumerate(results):
        is_m = r.get("is") or r.get("metrics") or {}
        expr = r.get("regular", {}).get("code") or r.get("code") or ""
        parsed = Gatekeeper.parse_brain_checks(r)
        yearly = r.get("yearly_stats", []) or is_m.get("yearly_stats", []) or []
        pos_years = 0
        for y in yearly:
            try:
                if float(y.get("sharpe", 0)) > 0:
                    pos_years += 1
            except Exception:
                pass
        out["slots"].append({
            "slot": i + 1,
            "alpha_id": r.get("id"),
            "expr": expr,
            "sharpe": is_m.get("sharpe"),
            "fitness": is_m.get("fitness"),
            "margin_bps": (float(is_m.get("margin", 0)) * 10000) if is_m.get("margin") is not None else None,
            "turnover": is_m.get("turnover"),
            "returns": is_m.get("returns"),
            "long_count": is_m.get("longCount"),
            "short_count": is_m.get("shortCount"),
            "risk_neut_sharpe": is_m.get("riskNeutralizedSharpe"),
            "positive_years": pos_years,
            "yearly_count": len(yearly),
            "fails": parsed["fails"],
            "warnings": parsed["warnings"],
            "cluster_sharpe": parsed["cluster_sharpe"],
            "ladder_2y_sharpe": parsed["ladder_2y_sharpe"],
            "sub_universe_sharpe": parsed["sub_universe_sharpe"],
            "checks": is_m.get("checks"),
        })
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", nargs="?", default=os.path.join(HERE, "batch_S1.json"))
    args = ap.parse_args()
    batch_path = os.path.abspath(args.batch)

    print("=" * 70)
    print(f"STAGE 4 · SILENT BACKTEST · {os.path.basename(batch_path)}")
    print(f"region={REGION} universe={UNIVERSE} delay={DELAY} "
          f"neut={NEUTRALIZATION} decay={DECAY} trunc={TRUNCATION}")
    print("HARD_SUBMISSION_RULE: simulation only, NO submission API is called.")
    print("=" * 70)

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_path,
        region=REGION, universe=UNIVERSE, delay=DELAY,
        category=CATEGORY, neutralization=NEUTRALIZATION,
        decay=DECAY, truncation=TRUNCATION, nan_handling="ON",
    )

    summ = summarize(batch_path, res)
    sp = os.path.join(HERE, "stage4_summary.json")
    json.dump(summ, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n" + "=" * 70)
    print(f"{'SLOT':<5}{'ALPHA':<12}{'SHARPE':>8}{'FIT':>7}{'MGN':>8}{'TO':>8}"
          f"{'POSYR':>7}{'LONG':>7}{'SHORT':>7}  FAILS")
    print("-" * 70)
    for s in summ["slots"]:
        def f(v, d=2):
            try:
                return f"{float(v):.{d}f}"
            except Exception:
                return "n/a"
        print(f"{s['slot']:<5}{str(s['alpha_id']):<12}{f(s['sharpe']):>8}{f(s['fitness']):>7}"
              f"{f(s['margin_bps'],1):>8}{f(s['turnover'],3):>8}{s['positive_years']:>7}"
              f"{str(s['long_count']):>7}{str(s['short_count']):>7}  {s['fails']}")
    print("=" * 70)
    print(f"[SAVED] {sp}")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
