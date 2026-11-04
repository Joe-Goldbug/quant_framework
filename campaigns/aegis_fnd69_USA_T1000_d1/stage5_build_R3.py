# -*- coding: utf-8 -*-
"""AEGIS Stage 5 -> Round 3: 针对 R2 结论的定向探测批。

R2 裁定（决定性）:
  R1 未去中枢 -> Sharpe 0.66~0.76 / shortCount=0 / returns ~26%  => 纯多头市场 beta
  R2 去中枢   -> Sharpe -0.47~+0.30 / long~460 short~540 / returns -3.6%~+3.0%
  结论：R1 的表观收益完全来自未去中枢造成的单边市场暴露；底层会计比率的真实横截面预测力≈0。
  另注：R1 risk_neutralized_sharpe=-0.37、investability_sharpe≈0.01，进一步佐证 beta 主导。

R3 探测三个尚未动过的杠杆:
  L1 批次级中性化 neutralization: NONE -> MARKET   (槽 1-4，与 R2 同表达式构成前后对照)
  L2 分母字段 fnd69_qta(密度1.00) -> fnd69_ta(密度0.511)  (槽 5-6)
  L3 回看窗口 252(同比) -> 60(单季环比)            (槽 7-8)
映射统一固定为 group_zscore(., industry)（R2 中 zscore 版普遍优于 rank-0.5 版）。
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

from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402
from quant_framework.core.red_team import DoubleBlindRedTeam  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

FIELDS = json.load(open(os.path.join(HERE, "batch_R1.json"), encoding="utf-8"))["known_fields"]
NEUT = "MARKET"          # L1
MAX_OPS = 11

Z = lambda x: f"group_zscore({x}, industry)"  # noqa: E731

SLOTS = [
    # ---- L1: 与 R2 同表达式、仅改批次级中性化 ----
    {"slot": 1, "role": "L1_S7_NETEQUITY_MARKET", "lever": "L1_neutralization",
     "expression": Z("reverse(divide(subtract(abs(ts_backfill(fnd69_q2yktss, 252)), abs(ts_backfill(fnd69_q2ycktsrp, 252))), fnd69_qta))"),
     "counterparty": "在高估值窗口配合增发、赚取承销费并把供给冲击延迟转嫁的一级市场与卖方",
     "mechanism": "股票净发行（增发减回购）除以总资产 = 净股权融资强度，做空净发行最高一档。本槽与 R2 槽2 表达式完全一致，唯一差别是批次级中性化由 NONE 改为 MARKET，用于读出市场 beta 剥离后的净增量。",
     "extra": "两腿密度 38.8%/39.0%，已 ts_backfill(252) 阶梯化；R2 同表达式在 NONE 下 Sharpe=0.30。"},
    {"slot": 2, "role": "L1_S2_FCF_MARKET", "lever": "L1_neutralization",
     "expression": Z("divide(subtract(ts_backfill(fnd69_q2yfcnao, 252), abs(ts_backfill(fnd69_capxy2q, 252))), fnd69_qta)"),
     "counterparty": "按营收/利润增速排序、系统忽视现金转化率的朴素成长配置盘",
     "mechanism": "自由现金流除以总资产 = 单位资产现金创造效率，做多高效率一档。本槽与 R2 槽4 同表达式，仅批次级中性化改为 MARKET。",
     "extra": "R2 同表达式在 NONE 下 Sharpe=0.18。"},
    {"slot": 3, "role": "L1_S5_CAPEX_MARKET", "lever": "L1_neutralization",
     "expression": Z("reverse(divide(abs(ts_backfill(fnd69_capxy2q, 252)), fnd69_qta))"),
     "counterparty": "为资本开支扩张故事提供增发与信贷供给的投行与银行",
     "mechanism": "资本开支除以总资产 = 投资强度，做空最高一档。本槽与 R2 槽6 同表达式，仅批次级中性化改为 MARKET。",
     "extra": "R2 同表达式在 NONE 下 Sharpe=-0.33。"},
    {"slot": 4, "role": "L1_S1_ASSETGROWTH_MARKET", "lever": "L1_neutralization",
     "expression": Z("reverse(divide(ts_delta(fnd69_qta, 252), ts_mean(fnd69_qta, 252)))"),
     "counterparty": "在并购扩表期有承销与佣金动机的卖方与投行",
     "mechanism": "总资产同比增量除以同期均值资产 = 资产扩张率，做空扩表最快一档。本槽与 R2 槽8 同表达式，仅批次级中性化改为 MARKET。",
     "extra": "R2 同表达式在 NONE 下 Sharpe=0.28；本槽是唯一 100% 密度字段，无需阶梯化。"},

    # ---- L2: 分母字段 qta -> ta ----
    {"slot": 5, "role": "L2_S7_NETEQUITY_DENOM_TA", "lever": "L2_denominator",
     "expression": Z("reverse(divide(subtract(abs(ts_backfill(fnd69_q2yktss, 252)), abs(ts_backfill(fnd69_q2ycktsrp, 252))), fnd69_ta))"),
     "counterparty": "在高估值窗口配合增发的一级市场与卖方",
     "mechanism": "净股权融资强度，但分母改用密度 0.511 的 fnd69_ta。若 fnd69_qta 的 1.00 密度来自过度前向填充导致分母失真，改用 ta 应能恢复真实截面区分度。",
     "extra": "分母密度由 1.00 降到 0.511，与分子的交集覆盖会进一步下降。"},
    {"slot": 6, "role": "L2_S2_FCF_DENOM_TA", "lever": "L2_denominator",
     "expression": Z("divide(subtract(ts_backfill(fnd69_q2yfcnao, 252), abs(ts_backfill(fnd69_capxy2q, 252))), fnd69_ta)"),
     "counterparty": "按营收/利润增速排序、系统忽视现金转化率的朴素成长配置盘",
     "mechanism": "自由现金流生产率，分母改用 fnd69_ta，用于裁定密度 1.00 的 qta 是否为失真分母。",
     "extra": "分母密度 0.511；若 qta 失真，本槽应显著优于槽 2。"},

    # ---- L3: 窗口 252 -> 60 ----
    {"slot": 7, "role": "L3_S1_ASSETGROWTH_W60", "lever": "L3_window",
     "expression": Z("reverse(divide(ts_delta(fnd69_qta, 60), ts_mean(fnd69_qta, 60)))"),
     "counterparty": "在扩表期给出溢价的卖方与投行",
     "mechanism": "资产扩张率，回看窗口由 252 日（同比）缩短到 60 日（约一个季度）。若 252 日窗口因季度数据滞后而失效，短窗口应更贴近最新一期报表。",
     "extra": "60 日窗口在季度数据上可能跨越 0~1 次报告，存在机械噪声上升的风险。"},
    {"slot": 8, "role": "L3_S6_OCFMOM_W60", "lever": "L3_window",
     "expression": Z("ts_delta(divide(ts_backfill(fnd69_q2yfcnao, 252), fnd69_qta), 60)"),
     "counterparty": "以历史均值定级、信息渐进扩散的基本面筛选盘",
     "mechanism": "经营现金流生产率的环比变动量（窗口 60 日），做多环比改善。窗口由 252 缩短到 60，检验及时性而非年度周期。",
     "extra": "季度密度 43.3%，ts_backfill 陈旧值在短窗口差分下同样会被放大。"},
]

for s in SLOTS:
    s["variation_source"] = f"{s['lever']} | {s['role']}"
    s["hypothesis_lines"] = [
        f"对手盘：{s['counterparty']}。",
        f"摩擦（诚实披露）：{s['extra']}",
        f"变动源：{s['lever']} 是本槽唯一被改变的维度，其余结构与 R2 保持一致。",
    ]


def main():
    report = {"round": 3, "neutralization": NEUT, "slots": [], "all_valid": True}

    for s in SLOTS:
        a = DimensionAuditor.audit_expression(
            s["expression"], FIELDS, category="fundamental", allow_pv_cross=False, max_operators=MAX_OPS
        )
        report["slots"].append({"slot": s["slot"], "role": s["role"],
                                "expression": s["expression"], "ast_audit": a})
        if not a["is_valid"]:
            report["all_valid"] = False

    corrector = ASTSandboxCorrector()
    raw = [s["expression"] for s in SLOTS]
    try:
        corrected = corrector.check_and_record_batch(raw, "USA", "TOP1000", 1, NEUT)
        report["skeleton_check"] = {"status": "PASS"}
        for s, cx in zip(SLOTS, corrected):
            s["expression"] = cx
    except Exception as e:
        report["skeleton_check"] = {"status": "FAIL", "error": repr(e)}
        report["all_valid"] = False

    items = [{"expression": s["expression"], "counterparty": s["counterparty"],
              "optimize_reason": s["mechanism"]} for s in SLOTS]
    vp = os.path.join(HERE, "batch_R3_red_team.json")
    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, vp)
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, "stage5_gate_report_R3.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "batch_R3.json"), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "dataset": "fundamental69", "category": "fundamental",
                   "neutralization": NEUT, "decay": 0, "truncation": 0.025,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": SLOTS}, f, ensure_ascii=False, indent=2)

    print("=" * 92)
    print(f"R3 AST 全通过: {report['all_valid']} | neutralization={NEUT}")
    for r in report["slots"]:
        a = r["ast_audit"]
        print(f"  S{r['slot']} {r['role']:<30} valid={a['is_valid']} ops={a['operator_count']} fields={len(a['used_fields'])}")
        if not a["is_valid"]:
            print(f"     ! {a['issues']}")
    print(f"骨架: {report['skeleton_check'].get('status')} | 红队: {report['red_team']['all_passed']}")
    for p in report["red_team"]["per_slot"]:
        if p["verdict"] != "PASS":
            print("   RT", p["slot"], p["issues"])
    print("=" * 92)


if __name__ == "__main__":
    main()
