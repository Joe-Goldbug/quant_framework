# -*- coding: utf-8 -*-
"""AEGIS Stage 5 -> Round 4: 尾部截断 + 两个未用字段的最后定向探测。

R1-R3 已收敛的事实:
  R1 未去中枢: Sharpe 0.66~0.76 / short=0 / ret~26%   -> 纯多头市场 beta 假象
  R2 去中枢(NONE): Sharpe -0.47~+0.30                 -> 真实信号≈0
  R3 去中枢(MARKET): 与 R2 逐位相同 (Δ=0.00)          -> 美元中性组合本就无市场暴露，中性化是空操作
  R3 L2 分母换 fnd69_ta: 覆盖塌到 ~171 个持仓，Sharpe 0.39 但账面过窄

R4 探测两个剩余杠杆 + 两个从未使用的字段:
  L4 尾部截断: group_zscore 前补 winsorize(std=2.5)。R2/R3 的 zscore 版本完全没有截断，
     而 divide(流量, 总资产) 在微型资产公司会产生 1e3 量级离群，zscore 会被极少数名字支配。
     槽 1-5 与 R2 的同表达式构成"加/不加截断"的严格对照。
  L5 新字段: fnd69_q2yvd(现金分红, alphaCount=1，全数据集最冷门) 与 fnd69_rtqf(财季,
     平台上被 12 个 alpha 使用，是本数据集使用度最高的字段)。
  L6 分子年化: 用 ts_mean(...,252) 平滑分子，修掉"单季流量 / 时点存量"的周期错配。
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
# 补入本轮新增使用的两个字段画像
FIELDS["fnd69_rtqf"] = {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                        "description": "Fiscal quarter 财季标签（平台使用度最高，alphaCount=12）",
                        "coverage": 1.0, "alpha_count": 12}
FIELDS["fnd69_fiscalquarter"] = {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                                 "description": "Fiscal quarter 财季", "coverage": 1.0, "alpha_count": 5}

NEUT = "NONE"
MAX_OPS = 11
Z = lambda x: f"group_zscore({x}, industry)"  # noqa: E731
W = lambda x: f"winsorize({x}, std=2.5)"      # noqa: E731

SLOTS = [
    {"slot": 1, "role": "L4_S7_NETEQUITY_WINS", "lever": "L4_winsorize",
     "expression": Z(W("reverse(divide(subtract(abs(ts_backfill(fnd69_q2yktss, 252)), abs(ts_backfill(fnd69_q2ycktsrp, 252))), fnd69_qta))")),
     "counterparty": "在高估值窗口配合增发、赚取承销费并把供给冲击延迟转嫁的一级市场与卖方",
     "mechanism": "股票净发行除以总资产 = 净股权融资强度，做空净发行最高一档。本槽与 R2 槽2 仅差一层 winsorize(std=2.5)，用于裁定 zscore 是否曾被极少数微型资产公司支配。",
     "extra": "R2 无截断版 Sharpe=0.30。若截断后显著改善，说明此前是尾部离群在主宰排序。"},
    {"slot": 2, "role": "L4_S2_FCF_WINS", "lever": "L4_winsorize",
     "expression": Z(W("divide(subtract(ts_backfill(fnd69_q2yfcnao, 252), abs(ts_backfill(fnd69_capxy2q, 252))), fnd69_qta)")),
     "counterparty": "按营收/利润增速排序、系统忽视现金转化率的朴素成长配置盘",
     "mechanism": "自由现金流除以总资产 = 单位资产现金创造效率，做多高效率一档。与 R2 槽4 仅差一层 winsorize。",
     "extra": "R2 无截断版 Sharpe=0.18。"},
    {"slot": 3, "role": "L4_S5_CAPEX_WINS", "lever": "L4_winsorize",
     "expression": Z(W("reverse(divide(abs(ts_backfill(fnd69_capxy2q, 252)), fnd69_qta))")),
     "counterparty": "为资本开支扩张故事提供增发与信贷供给的投行与银行",
     "mechanism": "资本开支除以总资产 = 投资强度，做空最高一档。与 R2 槽6 仅差一层 winsorize。",
     "extra": "R2 无截断版 Sharpe=-0.33。"},
    {"slot": 4, "role": "L4_S1_ASSETGROWTH_WINS", "lever": "L4_winsorize",
     "expression": Z(W("reverse(divide(ts_delta(fnd69_qta, 252), ts_mean(fnd69_qta, 252)))")),
     "counterparty": "在并购扩表期有承销与佣金动机的卖方与投行",
     "mechanism": "总资产同比增量除以同期均值资产 = 资产扩张率，做空扩表最快一档。与 R2 槽8 仅差一层 winsorize。",
     "extra": "R2 无截断版 Sharpe=0.28；本槽是唯一 100% 密度字段。"},
    {"slot": 5, "role": "L4_S4_NETDEBT_WINS", "lever": "L4_winsorize",
     "expression": Z(W("reverse(divide(subtract(abs(ts_backfill(fnd69_q2ysitld, 252)), abs(ts_backfill(fnd69_dltry2q, 252))), fnd69_qta))")),
     "counterparty": "在低利率窗口过度供给的一级信用市场与追逐杠杆的逐收益套利盘",
     "mechanism": "长期债务净发行除以总资产 = 净外部债权融资强度，做空净举债最高一档。补入截断后重测。",
     "extra": "R1 无去中枢版曾给出表观 0.69（已证明是 beta）；本槽是它第一次以双向账面出现。"},

    {"slot": 6, "role": "L5_DIVIDEND_INTENSITY", "lever": "L5_new_field_q2yvd",
     "expression": Z(W("divide(abs(ts_backfill(fnd69_q2yvd, 252)), fnd69_qta)")),
     "counterparty": "偏好高留存再投资叙事的成长偏好资金",
     "mechanism": "现金分红除以总资产 = 单位资产的股东现金回报强度，做多高强度一档。fnd69_q2yvd 是本数据集最冷门字段（alphaCount=1），此前从未在本战役中使用过。",
     "extra": "分红为事件性科目，密度 40.1%，已 ts_backfill 阶梯化；非派息公司读数恒为 0，会在长边形成大片并列。"},
    {"slot": 7, "role": "L5_RTQF_REPORT_GATE", "lever": "L5_new_field_rtqf",
     "expression": Z("trade_when(ts_delta(fnd69_rtqf, 1) != 0, divide(ts_backfill(fnd69_q2yfcnao, 252), fnd69_qta), 0)"),
     "counterparty": "在新报表落地日反应不足的做市与被动资金",
     "mechanism": "用 fnd69_rtqf 的财季标签变动检测新一期报表落地，并仅在该日建立经营现金流生产率头寸。信息刚落地时定价效率最低，随后被逐步消化。fnd69_rtqf 是本数据集平台使用度最高的字段（12 个 alpha），此前本战役从未使用。",
     "extra": "若 ts_delta(rtqf,1) 的符号在 Q4->Q1 回绕，!= 0 仍成立；但若该字段在日频上被前向填充成常量，门控会长期关闭导致空仓。行业归一在门控之外。"},
    {"slot": 8, "role": "L6_FCF_ANNUALIZED", "lever": "L6_numerator_annualized",
     "expression": Z(W("divide(subtract(ts_mean(ts_backfill(fnd69_q2yfcnao, 252), 252), abs(ts_mean(ts_backfill(fnd69_capxy2q, 252), 252))), fnd69_qta)")),
     "counterparty": "按营收/利润增速排序、系统忽视现金转化率的朴素成长配置盘",
     "mechanism": "分子改为过去一年均值（TTM 平滑）而非单季快照，修掉“单季流量 / 时点存量”的周期错配，与槽 2 的单季版构成对照。",
     "extra": "TTM 平滑会降低及时性，且进一步拉低换手（本批换手本就只有 3~4%）。"},
]

for s in SLOTS:
    s["variation_source"] = f"{s['lever']} | {s['role']}"
    s["hypothesis_lines"] = [
        f"对手盘：{s['counterparty']}。",
        f"摩擦（诚实披露）：{s['extra']}",
        f"变动源：{s['lever']} 是本槽唯一被改变的维度。",
    ]


def main():
    report = {"round": 4, "neutralization": NEUT, "slots": [], "all_valid": True}
    for s in SLOTS:
        a = DimensionAuditor.audit_expression(
            s["expression"], FIELDS, category="fundamental", allow_pv_cross=False, max_operators=MAX_OPS)
        report["slots"].append({"slot": s["slot"], "role": s["role"],
                                "expression": s["expression"], "ast_audit": a})
        if not a["is_valid"]:
            report["all_valid"] = False

    corrector = ASTSandboxCorrector()
    try:
        corrected = corrector.check_and_record_batch([s["expression"] for s in SLOTS],
                                                     "USA", "TOP1000", 1, NEUT)
        report["skeleton_check"] = {"status": "PASS"}
        for s, cx in zip(SLOTS, corrected):
            s["expression"] = cx
    except Exception as e:
        report["skeleton_check"] = {"status": "FAIL", "error": repr(e)}
        report["all_valid"] = False

    items = [{"expression": s["expression"], "counterparty": s["counterparty"],
              "optimize_reason": s["mechanism"]} for s in SLOTS]
    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, os.path.join(HERE, "batch_R4_red_team.json"))
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, "stage5_gate_report_R4.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "batch_R4.json"), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "dataset": "fundamental69", "category": "fundamental",
                   "neutralization": NEUT, "decay": 0, "truncation": 0.025,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": SLOTS}, f, ensure_ascii=False, indent=2)

    print("=" * 92)
    print(f"R4 AST 全通过: {report['all_valid']}")
    for r in report["slots"]:
        a = r["ast_audit"]
        print(f"  S{r['slot']} {r['role']:<26} valid={a['is_valid']} ops={a['operator_count']} fields={len(a['used_fields'])}")
        if not a["is_valid"]:
            print(f"     ! {a['issues']}")
    print(f"骨架: {report['skeleton_check'].get('status')} | 红队: {report['red_team']['all_passed']}")
    for p in report["red_team"]["per_slot"]:
        if p["verdict"] != "PASS":
            print("   RT", p["slot"], p["issues"])
    print("=" * 92)


if __name__ == "__main__":
    main()
