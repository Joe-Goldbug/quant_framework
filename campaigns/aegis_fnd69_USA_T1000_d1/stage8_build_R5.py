# -*- coding: utf-8 -*-
"""AEGIS Round 5 (v2，红队整改后): 放开"最多两个数据集"后的首批。

约束：USA / TOP1000 / delay 1，基本面类数据集，单条表达式最多 2 个数据集、3 个字段、
算子 <= 11、无 PV、必须去中枢（平台不自动去中枢，这是上一阶段用回测证实的陷阱）。

红队 v1 驳回 5 槽，本版逐条落实：
  S3 零膨胀尖峰腿淹没 -> 两腿各自 zscore 后再 add
  S5 符号整体反向     -> 补 reverse（多头 = 低应计 + 高分红）
  S6 OCF 被重复计入（major_11_11 定义内已含 OCF）-> 换成回购腿
  S7 ts_delta 依赖未验证的更新频率 -> 删除，名额让给跨数据集构造
  S8 分母近零/负未设防 -> 补 winsorize，并去掉营收腿上多余的 ts_backfill（覆盖 0.9578）
  全局：fnd69 流量腿覆盖 0.39~0.43 会把任何交叉拉回 ~0.40；fnd89 x other466 交集 ≈0.83
        -> 新增 3 条 fnd89 x other466 高覆盖交叉
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
FIELDS.update({
    "fnd89_major_11_11": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                          "description": "(净利 - 经营现金流)/总资产，Sloan 应计比率",
                          "coverage": 0.8657, "alpha_count": 0},
    "fnd89_asset_51_11": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                          "description": "非流动应计/总资产", "coverage": 0.7583, "alpha_count": 0},
    "oth466_is_revenue_q": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                            "description": "季度总营收", "coverage": 0.9578, "alpha_count": 1},
    "oth466_de_cshoq_q": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                          "description": "季度末普通股股本", "coverage": 0.9963, "alpha_count": 0},
    "oth466_bs_cash_equiv_q": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                               "description": "现金及等价物", "coverage": 1.0, "alpha_count": 0},
    "oth466_bs_assets_tot_q": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                               "description": "总资产", "coverage": 1.0, "alpha_count": 3},
})

NEUT = "NONE"
MAX_OPS = 11
MAX_DATASETS = 2
Z = lambda x: f"group_zscore({x}, industry)"  # noqa: E731

SLOTS = [
    {"slot": 1, "role": "CTRL_FND89_ACCRUAL_LEVEL",
     "expression": Z("reverse(fnd89_major_11_11)"),
     "counterparty": "按报告净利排序、不区分应计与现金成分的行情与配置盘",
     "mechanism": "Sloan 应计异象的标准测度：(净利 − 经营现金流)/总资产。应计高的公司盈利含金量低、后续被市场逐步证伪，做空应计最高一档。纯 fundamental89 基准，用于衡量搭档自身信号强度。",
     "extra": "覆盖率 0.8657，平台使用数 0；比率已按总资产归一，无需额外分母。fnd89 的更新频率未经验证。"},
    {"slot": 2, "role": "CTRL_FND89_NONCURRENT_ACCRUAL",
     "expression": Z("reverse(fnd89_asset_51_11)"),
     "counterparty": "把资本化支出与长期应计当作真实增长的成长配置盘",
     "mechanism": "非流动应计/总资产：捕捉长期资产端的应计堆积（资本化、递延），相比流动应计更持久、更难反转，做空最高一档。",
     "extra": "覆盖率 0.7583，平台使用数 0；非流动应计在正常经营中本就为正，长边可能被重资产行业的稳态公司占据。"},

    {"slot": 3, "role": "X_ACCRUAL_x_DEBT_ISSUE",
     "expression": Z("reverse(add(zscore(fnd89_major_11_11), zscore(divide(abs(ts_backfill(fnd69_q2ysitld, 252)), fnd69_qta))))"),
     "counterparty": "同时为账面利润与债务扩张定价过高的信用与股票配置盘",
     "mechanism": "应计水平与长期债务发行强度叠加：既靠应计撑利润、又靠举债撑现金流的公司最脆弱，做空双高组合。两腿各自先 zscore 再相加，消除红队指出的\"零膨胀尖峰腿淹没求和\"问题。abs 使发行读数在任何符号约定下都代表发行规模。原计划的\"发行减偿还\"净额口径需要 4 个字段，超出 3 字段预算，故改为单腿发行强度。",
     "extra": "fnd69 腿密度 0.3933，已 ts_backfill(252) 阶梯化；交集覆盖会被 fnd69 腿拉到约 0.40，这是本槽最大的结构性弱点；单腿口径无法区分\"借新还旧\"与\"净加杠杆\"。"},
    {"slot": 4, "role": "X_ACCRUAL_minus_BUYBACK",
     "expression": Z("reverse(subtract(zscore(fnd89_major_11_11), zscore(divide(abs(ts_backfill(fnd69_q2ycktsrp, 252)), fnd69_qta))))"),
     "counterparty": "只看报告利润、不看公司是否愿意用真金白银回购自身股票的配置盘",
     "mechanism": "利润含金量缺口：应计水平减去股票回购强度。低应计且真金白银大额回购 = 盈余质量被管理层用现金背书，做多；高应计且不回购 = 账面富裕现金紧张，做空。取 abs 使回购读数在任何符号约定下都代表回购规模。",
     "extra": "回购腿密度 0.3897，已阶梯化；交集覆盖约 0.40；abs 无法区分回购与增发混记的情形。"},

    {"slot": 5, "role": "X_ACCRUAL_x_REVENUE_GROWTH",
     "expression": Z("reverse(add(fnd89_major_11_11, divide(ts_delta(oth466_is_revenue_q, 252), ts_delay(oth466_is_revenue_q, 252))))"),
     "counterparty": "按营收增速排序、把高增长等同于高质量的成长配置盘",
     "mechanism": "应计水平与营收同比增速叠加：高增长配合高应计，是增长型盈余管理最典型的特征（提前确认收入、放宽信用），做空双高一档。本槽是 fnd89 x other466 组合，交集覆盖约 0.83，远高于 fnd69 交叉的 0.40。",
     "extra": "营收腿覆盖 0.9578、平台使用数 1；营收同比在并购或会计口径变更时会机械跳变；两腿尺度未做标准化（红队对 S3 的同类意见在此按覆盖优先暂不采纳）。"},
    {"slot": 6, "role": "X_ACCRUAL_x_SHARE_DILUTION",
     "expression": Z("reverse(add(fnd89_major_11_11, divide(ts_delta(oth466_de_cshoq_q, 252), ts_delay(oth466_de_cshoq_q, 252))))"),
     "counterparty": "承接增发的一级市场与在高估值窗口配合增发的卖方",
     "mechanism": "应计水平与股本同比扩张叠加：这是用股本而非现金流口径度量的净股权发行异象（Loughran-Ritter），比 fnd69 的现金流量表代理更直接。高应计配合股本稀释是最脆弱的一档，做空。",
     "extra": "股本腿覆盖 0.9963、平台使用数 0；股本变动也可能来自拆股、股权激励与可转债转股，未必都是稀释性增发。"},
    {"slot": 7, "role": "X_ACCRUAL_minus_CASH_BUFFER",
     "expression": Z("reverse(subtract(fnd89_major_11_11, divide(oth466_bs_cash_equiv_q, oth466_bs_assets_tot_q)))"),
     "counterparty": "只看利润表不看资产负债表流动性的配置盘",
     "mechanism": "应计水平减去现金充裕度：高应计且现金缓冲薄弱的公司，是利润虚高叠加流动性紧绷的组合，一旦融资窗口收紧即被证伪，做空。多头端是低应计且现金充裕的公司。",
     "extra": "两条 other466 腿覆盖均为 1.0，平台使用数 0 与 3；现金比率在金融行业语义不同（现金即存货），group_zscore(industry) 仅部分中和。"},

    {"slot": 8, "role": "X_FCF_OVER_REVENUE",
     "expression": Z("winsorize(divide(subtract(ts_backfill(fnd69_q2yfcnao, 252), abs(ts_backfill(fnd69_capxy2q, 252))), oth466_is_revenue_q), std=3)"),
     "counterparty": "按营收增速排序、忽视现金转化率的朴素成长配置盘",
     "mechanism": "自由现金流除以季度营收：把此前\"单季流量 / 时点总资产\"的周期错配改成\"流量 / 流量\"，得到真正的现金利润率，做多最高一档。winsorize(std=3) 用于防住红队指出的\"营收接近 0 导致比值爆炸\"。",
     "extra": "两条 fnd69 腿密度 0.4333/0.4197 且需同时有值，交集覆盖约 0.18~0.40，是全批最低；营收腿覆盖 0.9578，已去掉多余的 ts_backfill；营收为负（冲回/重述）时符号解释会翻转。"},
]

for s in SLOTS:
    ds = sorted({("fundamental69" if f.startswith("fnd69_") else
                  "fundamental89" if f.startswith("fnd89_") else
                  "other466" if f.startswith("oth466_") else "?")
                 for f in __import__("re").findall(r"[a-zA-Z_][a-zA-Z0-9_]*", s["expression"])
                 if f.startswith(("fnd69_", "fnd89_", "oth466_"))})
    s["datasets"] = ds
    s["variation_source"] = f"{'+'.join(ds)} | {s['role']}"
    s["hypothesis_lines"] = [
        f"对手盘：{s['counterparty']}。",
        f"摩擦（诚实披露）：{s['extra']}",
        f"变动源：{' x '.join(ds)} 双数据集交叉，字段预算 3 个、数据集预算 2 个。",
    ]


def main():
    report = {"round": 5, "neutralization": NEUT, "max_datasets": MAX_DATASETS,
              "slots": [], "all_valid": True}

    for s in SLOTS:
        a = DimensionAuditor.audit_expression(
            s["expression"], FIELDS, category="fundamental", allow_pv_cross=False, max_operators=MAX_OPS)
        if len(s["datasets"]) > MAX_DATASETS:
            a["issues"].append(f"数据集超限: {s['datasets']} 共 {len(s['datasets'])} 个 > {MAX_DATASETS}")
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
    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, os.path.join(HERE, "batch_R5_red_team.json"))
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, "stage8_gate_report_R5.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "batch_R5.json"), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "datasets": ["fundamental69", "fundamental89", "other466"],
                   "category": "fundamental", "neutralization": NEUT,
                   "decay": 0, "truncation": 0.025,
                   "max_datasets_per_expression": MAX_DATASETS,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": SLOTS}, f, ensure_ascii=False, indent=2)

    print("=" * 100)
    print(f"R5 全通过: {report['all_valid']}")
    for r in report["slots"]:
        a = r["ast_audit"]
        print(f"  S{r['slot']} {r['role']:<30} valid={a['is_valid']} ops={a['operator_count']} "
              f"fields={len(a['used_fields'])} ds={len(r['datasets'])} {r['datasets']}")
        if not a["is_valid"]:
            print(f"     ! {a['issues']}")
    print(f"骨架: {report['skeleton_check'].get('status')} | 红队: {report['red_team']['all_passed']}")
    for p in report["red_team"]["per_slot"]:
        if p["verdict"] != "PASS":
            print("   RT", p["slot"], p["issues"])
    print("=" * 100)


if __name__ == "__main__":
    main()
