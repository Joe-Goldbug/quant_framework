#!/usr/bin/env python3
"""
rep566_probe.py — BATCH A 种子探针 (诊断)

仅用 oth566_return / oth566_l2r20_label / oth566_l2r20_prob / oth566_r20marsi_ret / oth566_r20marsi_label_5
这 5 个「已知结构」字段做极简形式探针，看 raw predictor 自带的方向与强度，排除 data-free 噪音。
经济学动机写在表达式注释里。
"""

import json, os, sys, time, subprocess, platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from quant_framework.core.gatekeeper import Gatekeeper
except ImportError:
    from core.gatekeeper import Gatekeeper
try:
    from quant_framework.core.sim_runner import SIMRunner
except ImportError:
    from core.sim_runner import SIMRunner
try:
    from quant_framework.core.rag_memory import RAGMemoryEngine
except ImportError:
    from core.rag_memory import RAGMemoryEngine

OUT_DIR = PROJECT_ROOT / "campaigns" / "USA_other566_rep1_probe"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS = dict(
    region="USA", universe="TOP1000", delay=1, decay=4, truncation=0.0,
    test_period="P0Y0M", instrument_type="EQUITY",
    neutralization="SUBINDUSTRY", unit_handling="VERIFY",
    nan_handling="ON", pasteurization="ON", max_trade="OFF",
    language="FASTEXPR", visualization=False,
)

MEM = RAGMemoryEngine(prefix="rep566_probe")
EXPRS = [
    (
        "raw_return_core",
        "oth566_return",
        "回归式模型的原始 2 日预测值。价格信号而非图表形态，作为 direction 基石。",
    ),
    (
        "l2r20_label_bucket_direction",
        "rank(oth566_l2r20_label) + rank(oth566_return)",
        "FinChart 20 日分类预测（label）+ 回归预测共识，与价格动量同向加权（动量经济学）。",
    ),
    (
        "l2r20_prob_confidence",
        "oth566_l2r20_prob * rank(oth566_return)",
        "模型对 20 日预测的信心 × price 动量排名。自信的模型预测越强，买入信号越强（信心加权经济学）。",
    ),
    (
        "r20marsi_ret_raw",
        "oth566_r20marsi_ret",
        "最佳母本 R20MaRsi 预测的原始回归值。确认它在 USA/TOP1000/D1 下仍有独立信息。",
    ),
    (
        "r20marsi_label_5_bucket",
        "rank(oth566_r20marsi_label_5) + rank(oth566_return)",
        "R20MaRsi 5 分位标签（跨期限验证器）与价格动量共识。",
    ),
    (
        "label_prob_cross_valid",
        "rank(oth566_l2r20_label) * rank(oth566_l2r20_prob) + rank(oth566_return)",
        "模型分类预测 × 信心 与价格动量三轴合成（B5 结构的种子版）。",
    ),
    (
        "l2r20_quantile_minus_r20marsi",
        "rank(oth566_l2r20_label) - rank(oth566_r20marsi_label_5)",
        "两个模型（FinChart 20 日 vs R20MaRsi 5 日）的预测分歧。分歧大时捕捉过度反应机会（跨模型分歧经济学）。",
    ),
    (
        "prob_inverse_horizon_check",
        "rank(oth566_l2r20_prob) - rank(oth566_r20marsi_ret)",
        "短预测信心 与 长预测回归值的对比：若短预测信心高而长预测弱，警惕视觉显著性过度反应。",
    ),
]

def main():
    runner = SIMRunner(
        region=SETTINGS["region"], universe=SETTINGS["universe"], delay=SETTINGS["delay"],
        decay=SETTINGS["decay"], truncation=SETTINGS["truncation"],
        test_period=SETTINGS["test_period"], instrument_type=SETTINGS["instrument_type"],
        neutralization=SETTINGS["neutralization"], unit_handling=SETTINGS["unit_handling"],
        nan_handling=SETTINGS["nan_handling"], pasteurization=SETTINGS["pasteurization"],
        max_trade=SETTINGS["max_trade"], language=SETTINGS["language"],
        visualization=SETTINGS["visualization"], memory_engine=MEM,
        out_dir=OUT_DIR,
    )

    header = f"{'name':<26} {'expression':<52} | {'sharpe':>7} {'fitness':>7} {'turn':>6} {'margin_bps':>9} {'sub_sharpe':>10} {'2y_sharpe':>9} {'ra_fail':>7}  verdict"
    print(header); print("-"*len(header))

    for name, expr, motive in EXPRS:
        expr_disp = expr
        try:
            res = runner.run_regular_alpha(name, expr, motive=motive, **SETTINGS)
            is_data = res.get("is") or res
            m = (is_data.get("metrics") or is_data) if isinstance(is_data, dict) else {}
            nm = m.get("name") or m.get("alphaName")
            if nm:
                MEM.commit(name, nm, motive, res)
            gc = Gatekeeper()
            pc = gc.extract_prod_corr(res)
            sc = gc.extract_self_corr(res)
            metrics = (res.get("is") or res.get("metrics") or res) if isinstance(res, dict) else {}
            sh = metrics.get("sharpe")
            fi = metrics.get("fitness")
            to = metrics.get("turnover")
            mr = metrics.get("margin")
            sub = metrics.get("sub_universe_sharpe")
            t2 = metrics.get("two_year_sharpe") or metrics.get("investability_sharpe")
            ra_failed = (metrics.get("ra") or {}).get("ra_failed", None)
            verdict = ""
            if sh is None:
                verdict = "NO_RESULT"
            elif not Gatekeeper.audit_step1_batch(res, min_sharpe=1.0).get("survive", False):
                verdict = "drop"
            else:
                verdict = "candidate"
            margin_bps = round(float(mr)*1e4, 2) if mr is not None else float("nan")
            print(f"{name:<26} {expr_disp[:52]:<52} | {sh:>7.2f} {fi:>7.2f} {to:>6.2%} {margin_bps:>9.2f} {sub:>10.2f} {t2:>9.2f} {str(ra_failed):>7}  {verdict}")
            fname = f"{name}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(res, f, indent=2, default=str)
        except Exception as e:
            print(f"{name:<26} {expr_disp[:52]:<52} |  ERROR  {e}")

if __name__ == "__main__":
    main()
