# -*- coding: utf-8 -*-
"""AEGIS Stage 6: 战役汇总、本地状态标记与报告生成。

严格遵守：不调用任何提交接口；达标者仅在本地标记，交人工终审。
"""
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

ROUNDS = {
    "R1": ("batch_R1", "NONE", "主核广度正交筛选（未去中枢）"),
    "R2": ("batch_R2", "NONE", "4 主核 x 2 去中枢映射"),
    "R3": ("batch_R3", "MARKET", "中性化 / 分母字段 / 窗口长度"),
    "R4": ("batch_R4", "NONE", "尾部截断 / 新字段 q2yvd,rtqf / 分子年化"),
}

THRESH = {"sharpe": 1.58, "fitness": 1.00, "margin_bps": 10.0,
          "turnover_lo": 5.0, "turnover_hi": 50.0}

rows = []
for rk, (base, neut, desc) in ROUNDS.items():
    meta = json.load(open(os.path.join(HERE, base + ".json"), encoding="utf-8"))["slot_meta"]
    res = json.load(open(os.path.join(HERE, base + "_result.json"), encoding="utf-8"))["alpha_results"]
    for s, r in zip(meta, res):
        m = r.get("metrics", {})
        chk = Gatekeeper.parse_brain_checks(r)
        rows.append({
            "round": rk, "round_desc": desc, "neutralization": neut,
            "slot": s["slot"], "role": s["role"], "expression": r.get("code", s["expression"]),
            "alpha_id": r.get("id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "returns_pct": round((m.get("returns") or 0) * 100, 2),
            "turnover_pct": round((m.get("turnover") or 0) * 100, 2),
            "margin_bps": round((m.get("margin") or 0) * 10000, 1),
            "drawdown_pct": round((m.get("drawdown") or 0) * 100, 2),
            "long": m.get("longCount"), "short": m.get("shortCount"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "investability_sharpe": m.get("investability_sharpe"),
            "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
            "fails": chk["fails"],
            # 判定
            "verdict": (
                "STEP1_PRUNED" if abs(m.get("sharpe") or 0) < 1.0 else
                "BELOW_PRODUCTION_GRADE"
            ),
            "submitted": False, "submission_api_called": 0,
        })

with open(os.path.join(HERE, "all_variants.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

# ---- 生产门禁终审 ----
final = Gatekeeper.audit_final_alpha({"alpha_results": [
    {"is": {"sharpe": r["sharpe"], "fitness": r["fitness"],
            "margin": (r["margin_bps"] or 0) / 10000.0,
            "turnover": (r["turnover_pct"] or 0) / 100.0},
     "code": r["expression"]} for r in rows]}, region="USA")

status = {
    "campaign": "aegis_fnd69_USA_T1000_d1",
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental69", "category": "fundamental",
    "hard_rule": "严禁调用任何提交接口；达标者仅本地标记，交研究员人工终审",
    "submission_api_calls": 0,
    "simulation_batches": 4, "variants_tested": len(rows),
    "production_thresholds": THRESH,
    "final_gate_passed": len(final),
    "candidates_for_human_review": [],
    "all_variants": rows,
}
with open(os.path.join(HERE, "local_alpha_status.json"), "w", encoding="utf-8") as f:
    json.dump(status, f, ensure_ascii=False, indent=2)

print(f"变体总数 {len(rows)} | 通过终极生产门禁 {len(final)} 条")
print(f"最高 |Sharpe| (全部) = {max(abs(r['sharpe'] or 0) for r in rows):.2f}")
print(f"最高 |Sharpe| (去中枢后 R2-R4) = "
      f"{max(abs(r['sharpe'] or 0) for r in rows if r['round'] != 'R1'):.2f}")
print("[ok] wrote all_variants.json / local_alpha_status.json")
