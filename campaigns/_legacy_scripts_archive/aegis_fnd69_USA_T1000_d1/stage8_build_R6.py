# -*- coding: utf-8 -*-
"""AEGIS Round 6: 修复 R5 的覆盖塌方（fnd89 阶梯化）。

R5 法医发现（决定性）:
  槽 1-7 只有 ~35-40 个持仓（TOP1000 宇宙里），换手却高达 41%；而槽 8（未用 fnd89）有 906 个持仓。
  结论：fnd89 字段虽然 API 报 coverage 0.8657 / 0.7583，但它是**财报日时点值、平台不做前向填充**，
  任一交易日只有约 35 只票有新鲜值，其余全为 NaN。这与 R1 在 fnd69 上踩过的坑完全同源。
  对照证据：R5 槽 8 的 fnd69 腿加了 ts_backfill(252) 后拿到 906 个持仓，说明 ts_backfill 有效。

R6 修复：所有 fnd89 腿加 ts_backfill(·, 252)。与 R5 的未阶梯化版本构成严格 A/B 对照。
oth466 腿（coverage 0.9578~1.0）经 R5 槽 8 验证是平台已填充的密集序列，不额外加 backfill。
槽 8 改为 TTM 平滑分子版本（与 R5 单季版对照，检验分子平滑）。
"""
import json
import os
import re
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

FIELDS = json.load(open(os.path.join(HERE, "batch_R5.json"), encoding="utf-8"))["known_fields"]

NEUT = "NONE"
MAX_OPS = 11
MAX_DATASETS = 2
Z = lambda x: f"group_zscore({x}, industry)"  # noqa: E731
B = lambda f: f"ts_backfill({f}, 252)"        # noqa: E731

SLOTS = [
    {"slot": 1, "role": "CTRL_FND89_ACCRUAL_LEVEL_BF",
     "expression": Z(f"reverse({B('fnd89_major_11_11')})"),
     "counterparty": "按报告净利排序、不区分应计与现金成分的行情与配置盘",
     "mechanism": "Sloan 应计异象标准测度：(净利 − 经营现金流)/总资产，做空最高一档。本槽是 R5 槽1 加 ts_backfill(252) 后的版本，用于直接读出阶梯化带来的增量。",
     "extra": "R5 同构造未阶梯化时只有 39 个持仓、Sharpe −0.23；阶梯化代价是最长约 250 日陈旧值。"},
    {"slot": 2, "role": "CTRL_FND89_NONCURRENT_ACCRUAL_BF",
     "expression": Z(f"reverse({B('fnd89_asset_51_11')})"),
     "counterparty": "把资本化支出与长期应计当作真实增长的成长配置盘",
     "mechanism": "非流动应计/总资产，做空最高一档。R5 槽2 的阶梯化版本。",
     "extra": "R5 未阶梯化时 35 个持仓、Sharpe −0.02；非流动应计在正常经营中本就为正，长边可能被重资产稳态公司占据。"},

    {"slot": 3, "role": "X_ACCRUAL_x_DEBT_ISSUE_BF",
     "expression": Z(f"reverse(add(zscore({B('fnd89_major_11_11')}), zscore(divide(abs({B('fnd69_q2ysitld')}), fnd69_qta))))"),
     "counterparty": "同时为账面利润与债务扩张定价过高的信用与股票配置盘",
     "mechanism": "应计水平与长期债务发行强度叠加，做空双高组合。两腿各自先 zscore 再相加，消除零膨胀尖峰腿淹没求和的问题。abs 使发行读数对符号约定免疫。",
     "extra": "fnd69 腿密度 0.3933，已阶梯化；交集覆盖取决于两腿的阶梯化后覆盖，R5 未阶梯化版本只有 37 个持仓。"},
    {"slot": 4, "role": "X_ACCRUAL_minus_BUYBACK_BF",
     "expression": Z(f"reverse(subtract(zscore({B('fnd89_major_11_11')}), zscore(divide(abs({B('fnd69_q2ycktsrp')}), fnd69_qta))))"),
     "counterparty": "只看报告利润、不看公司是否愿意用真金白银回购自身股票的配置盘",
     "mechanism": "利润含金量缺口：应计水平减去股票回购强度，多头是低应计且大额回购（盈余质量被现金背书）的公司。",
     "extra": "回购腿密度 0.3897，已阶梯化；abs 无法区分回购与增发混记的情形。"},

    {"slot": 5, "role": "X_ACCRUAL_x_REVENUE_GROWTH_BF",
     "expression": Z(f"reverse(add({B('fnd89_major_11_11')}, divide(ts_delta(oth466_is_revenue_q, 252), ts_delay(oth466_is_revenue_q, 252))))"),
     "counterparty": "按营收增速排序、把高增长等同于高质量的成长配置盘",
     "mechanism": "应计水平与营收同比增速叠加：高增长配合高应计是增长型盈余管理的典型特征，做空双高一档。",
     "extra": "营收腿覆盖 0.9578、平台使用数 1，R5 槽8 已验证其为已填充的密集序列；营收同比在并购或会计口径变更时会机械跳变。"},
    {"slot": 6, "role": "X_ACCRUAL_x_SHARE_DILUTION_BF",
     "expression": Z(f"reverse(add({B('fnd89_major_11_11')}, divide(ts_delta(oth466_de_cshoq_q, 252), ts_delay(oth466_de_cshoq_q, 252))))"),
     "counterparty": "承接增发的一级市场与在高估值窗口配合增发的卖方",
     "mechanism": "应计水平与股本同比扩张叠加：用股本口径度量净股权发行异象，比 fnd69 的现金流量表代理更直接，做空双高一档。",
     "extra": "股本腿覆盖 0.9963、平台使用数 0；股本变动也可能来自拆股、股权激励与可转债转股，未必都是稀释性增发。"},
    {"slot": 7, "role": "X_ACCRUAL_minus_CASH_BUFFER_BF",
     "expression": Z(f"reverse(subtract({B('fnd89_major_11_11')}, divide(oth466_bs_cash_equiv_q, oth466_bs_assets_tot_q)))"),
     "counterparty": "只看利润表不看资产负债表流动性的配置盘",
     "mechanism": "应计水平减去现金充裕度：高应计且现金缓冲薄弱的公司，是利润虚高叠加流动性紧绷，做空；多头是低应计且现金充裕的公司。",
     "extra": "两条 other466 腿覆盖均为 1.0；现金比率在金融行业语义不同（现金即存货），行业归一仅部分中和。"},

    {"slot": 8, "role": "X_TTM_FCF_OVER_REVENUE",
     "expression": Z("winsorize(divide(subtract(ts_mean(ts_backfill(fnd69_q2yfcnao, 252), 252), abs(ts_mean(ts_backfill(fnd69_capxy2q, 252), 252))), oth466_is_revenue_q), std=3)"),
     "counterparty": "按营收增速排序、忽视现金转化率的朴素成长配置盘",
     "mechanism": "TTM 平滑后的自由现金流除以季度营收：在 R5 槽8 单季版基础上把分子改成过去一年均值，检验\"流量/流量\"口径下分子平滑是否有增量。",
     "extra": "R5 单季版 Sharpe 0.25、906 个持仓、margin 10.6 bps（勉强过 USA 10 bps 线）但换手 4.53% 低于 5% 地板；TTM 平滑会进一步压低换手。"},
]

for s in SLOTS:
    ds = sorted({("fundamental69" if f.startswith("fnd69_") else
                  "fundamental89" if f.startswith("fnd89_") else
                  "other466" if f.startswith("oth466_") else "?")
                 for f in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", s["expression"])
                 if f.startswith(("fnd69_", "fnd89_", "oth466_"))})
    s["datasets"] = ds
    s["variation_source"] = f"{'+'.join(ds)} | {s['role']}"
    s["hypothesis_lines"] = [
        f"对手盘：{s['counterparty']}。",
        f"摩擦（诚实披露）：{s['extra']}",
        f"变动源：{' x '.join(ds)} 双数据集交叉，字段预算 3 个、数据集预算 2 个。",
    ]


def main():
    report = {"round": 6, "fix": "fnd89 腿全域 ts_backfill(252) 阶梯化",
              "neutralization": NEUT, "slots": [], "all_valid": True}

    for s in SLOTS:
        a = DimensionAuditor.audit_expression(
            s["expression"], FIELDS, category="fundamental", allow_pv_cross=False, max_operators=MAX_OPS)
        if len(s["datasets"]) > MAX_DATASETS:
            a["issues"].append(f"数据集超限: {s['datasets']}")
            a["is_valid"] = False
        report["slots"].append({"slot": s["slot"], "role": s["role"], "datasets": s["datasets"],
                                "expression": s["expression"], "ast_audit": a})
        if not a["is_valid"]:
            report["all_valid"] = False

    try:
        corrected = ASTSandboxCorrector().check_and_record_batch(
            [s["expression"] for s in SLOTS], "USA", "TOP1000", 1, NEUT)
        report["skeleton_check"] = {"status": "PASS"}
        for s, cx in zip(SLOTS, corrected):
            s["expression"] = cx
    except Exception as e:
        report["skeleton_check"] = {"status": "FAIL", "error": repr(e)}
        report["all_valid"] = False

    items = [{"expression": s["expression"], "counterparty": s["counterparty"],
              "optimize_reason": s["mechanism"]} for s in SLOTS]
    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, os.path.join(HERE, "batch_R6_red_team.json"))
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, "stage8_gate_report_R6.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "batch_R6.json"), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "datasets": ["fundamental69", "fundamental89", "other466"],
                   "category": "fundamental", "neutralization": NEUT,
                   "decay": 0, "truncation": 0.025,
                   "max_datasets_per_expression": MAX_DATASETS,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": SLOTS}, f, ensure_ascii=False, indent=2)

    print("=" * 100)
    print(f"R6 全通过: {report['all_valid']}")
    for r in report["slots"]:
        a = r["ast_audit"]
        print(f"  S{r['slot']} {r['role']:<32} valid={a['is_valid']} ops={a['operator_count']} "
              f"fields={len(a['used_fields'])} ds={len(r['datasets'])}")
        if not a["is_valid"]:
            print(f"     ! {a['issues']}")
    print(f"骨架: {report['skeleton_check'].get('status')} | 红队: {report['red_team']['all_passed']}")
    for p in report["red_team"]["per_slot"]:
        if p["verdict"] != "PASS":
            print("   RT", p["slot"], p["issues"])
    print("=" * 100)


if __name__ == "__main__":
    main()
