# -*- coding: utf-8 -*-
"""AEGIS R8: 跨数据集收敛批 (母本 = R7 Slot4 6XdO96k5)

R7 实测里程碑:
  6XdO96k5 rank(ts_mean(subtract(z(cfc_f90), z(tnix_466)), 20))
    Sharpe 0.73 | Fitness 0.42 | Margin 22.13bps | 换手 3.7% | 年化 4.14% | 2Y 0.76 | Cluster 0.43
  kqNl0pzk (实付现金利息口径): Sharpe 0.63 | Fitness 0.38 | Margin 22.09bps | 年化 4.66% | SubU 0.61
进展: 相比单数据集最优 (0.65/0.26/8.67bps/1.98%)，跨数据集腿把年化收益翻倍至 4.14%，
Fitness 0.26 -> 0.42，Margin 8.67 -> 22.13bps。
残留病灶: 换手 3.7% 仍低于 5.0% 下限；Sharpe 0.73 -> 1.58、Fitness 0.42 -> 1.00 未达标。

本批处方: 把 R7 证明有效的【rank 映射】与【窗 10 换手修复】合并，并正交测试
实付利息口径、三腿纯化、行业内排序、截尾与基线窗消融。
"""
import json, os, sys, ast as _ast
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

KB90 = json.load(open(os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental90.json"),
                      encoding="utf-8"))["fields"]
KB466 = json.load(open(os.path.join(ROOT, "knowledge_base", "fields", "USA", "other466.json"),
                       encoding="utf-8"))["fields"]

F90 = ["fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt"]
P466 = ["oth466_a_tnix", "oth466_cf_cash_int_pay", "oth466_a_ttld"]
KNOWN = {f: KB90[f] for f in F90}
KNOWN.update({f: KB466[f] for f in P466 if f in KB466})
for f, d in (("oth466_cf_cash_int_pay", "Cash Interest Paid 实付现金利息"),):
    KNOWN.setdefault(f, {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                         "semantic_role": "Signal_Flow", "description": d,
                         "coverage": 0.95, "alpha_count": 1})

V = lambda x: "vec_avg(%s)" % x
Z = lambda x, w=252: "ts_zscore(%s, %d)" % (x, w)
CFC, STD = V("fnd90_us_game_cash_flow_coverage"), V("fnd90_us_game_short_term_debt")

SLOTS = [
    {
        "id": "R8_S1_RANK_WINDOW_10",
        "expression": "rank(ts_mean(subtract(%s, %s), 10))" % (Z(CFC), Z("oth466_a_tnix")),
        "counterparty": "以年度财报节奏调仓、错失季度间融资成本更新的长期持有盘",
        "optimize_reason": (
            "R7 已分别验证 rank 映射 (Sharpe 0.73 / Fitness 0.42) 与 窗10 (换手 5.7%) 各自有效，"
            "但两者尚未合并。此处把二者叠加，目标是同时拿到 rank 带来的持仓均匀化增益"
            "与窗 10 带来的换手合规，是本批最直接的收敛点。"),
    },
    {
        "id": "R8_S2_RANK_PAID_INTEREST_W10",
        "expression": "rank(ts_mean(subtract(%s, %s), 10))" % (Z(CFC), Z("oth466_cf_cash_int_pay")),
        "counterparty": "以应计利息估算融资成本、不看实际现金流出的信用模型",
        "optimize_reason": (
            "R7 中实付现金利息口径取得全批最高年化 4.66% 与最高 Sub-universe 0.61，"
            "说明现金口径的付息比应计口径更贴近真实负担。此处与 rank 映射、窗 10 三者合并，"
            "检验收益与换手合规能否同时成立。"),
    },
    {
        "id": "R8_S3_RANK_WINSORIZE_PAID",
        "expression": "rank(winsorize(ts_mean(subtract(%s, %s), 20), std=3))" % (
            Z(CFC), Z("oth466_cf_cash_int_pay")),
        "counterparty": "使少数极端付息标的决定组合波动的按量级加权量化盘",
        "optimize_reason": (
            "R7 中截尾独立使用时把 Margin 由 13.63 抬到 15.50bps，说明尾部脉冲确实在侵蚀单位换手收益。"
            "此处把截尾前置到排序之前（而非之后，排序后再截尾是空操作），"
            "先削掉两个数据集量纲差异造成的尾部，再均匀映射持仓。"),
    },
    {
        "id": "R8_S4_RANK_TRIPLE_PAID",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z(CFC), Z(STD), Z("oth466_cf_cash_int_pay")),
        "counterparty": "把已付利息视作唯一融资成本、忽略到期滚续压力的信用筛选模型",
        "optimize_reason": (
            "在实付利息腿之上再扣除模型化短期债务占比，形成覆盖度、期限结构、实际付息三道检验。"
            "三条腿分别来自模型评分、模型评分与真实科目，任一腿失效都会被另外两腿证伪，"
            "从而降低单腿噪声进入组合的概率。"),
    },
    {
        "id": "R8_S5_GROUP_RANK_SUBINDUSTRY",
        "expression": "group_rank(ts_mean(subtract(%s, %s), 20), subindustry)" % (Z(CFC), Z("oth466_a_tnix")),
        "counterparty": "跨行业统一比较融资成本、因而错杀资本密集行业的量化模型",
        "optimize_reason": (
            "母本在全市场排序时会把公用事业、银行等天然高付息行业整体压到空头侧，"
            "这部分是行业敞口而非公司层面的融资效率差异。改为子行业内排序后，"
            "剩余的横截面差异才是同业内真实的相对融资优势。"),
    },
    {
        "id": "R8_S6_RANK_TRIPLE_ACCRUAL",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z(CFC), Z(STD), Z("oth466_a_tnix")),
        "counterparty": "把应付利息视作唯一融资成本、忽略到期滚续压力的信用筛选模型",
        "optimize_reason": (
            "与 Slot4 同为三腿结构，但把真实付息腿换回应计利息费用，构成口径消融："
            "若应计口径三腿优于现金口径三腿，说明市场更看重权责发生制下的负债确认；"
            "反之则印证现金口径才是有定价能力的负担度量。"),
    },
    {
        "id": "R8_S7_RANK_WINSORIZE_ACCRUAL",
        "expression": "rank(winsorize(ts_mean(subtract(%s, %s), 20), std=3))" % (Z(CFC), Z("oth466_a_tnix")),
        "counterparty": "使少数极端利息负担标的决定组合波动的按量级加权量化盘",
        "optimize_reason": (
            "与 Slot3 同构但换回应计利息口径，构成截尾处方的口径对照。"
            "截尾位置固定在排序之前，保证两次对照之间只有付息口径一个变量不同。"),
    },
    {
        "id": "R8_S8_RANK_LTD_SHORTBASE",
        "expression": "rank(ts_mean(subtract(%s, %s), 20))" % (
            Z(CFC, 120), Z("oth466_a_ttld", 120)),
        "counterparty": "按长期负债存量配置、不做自身历史基准比较的杠杆因子",
        "optimize_reason": (
            "把真实腿由利息费用换成长期债务余额，并把两腿的自身历史基准窗由 252 日缩短到 120 日，"
            "构成基线窗消融：短窗让最近一次财报对取值的影响更大，可检验该母本的收益"
            "究竟来自长期结构性差异还是来自最近一期报表的增量信息。"),
    },
]

report = {"slots": [], "all_green": True}
WRAPPERS = {"vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min", "vec_std",
            "vec_norm", "vec_percentage", "vec_ir", "vec_choose"}
for s in SLOTS:
    e = {"id": s["id"], "expression": s["expression"]}
    a = DimensionAuditor.audit_expression(s["expression"], KNOWN, category="fundamental",
                                          allow_pv_cross=False, max_operators=11)
    calls = [n for n in _ast.walk(_ast.parse(s["expression"], mode="eval")) if isinstance(n, _ast.Call)]
    vec = [n for n in calls if getattr(n.func, "id", "") in WRAPPERS]
    e["math_ops"] = len(calls) - len(vec)
    e["gate2"] = {"ok": a["is_valid"], "issues": a.get("issues", [])}
    if not a["is_valid"] or e["math_ops"] > 6:
        report["all_green"] = False
    v = DoubleBlindRedTeam.audit_candidate_blindly(DoubleBlindRedTeam.generate_blind_payload(
        s["expression"], {"counterparty": s["counterparty"], "mechanism": s["optimize_reason"]}, KNOWN))
    e["gate1"] = {"verdict": v["verdict"], "issues": v["issues"]}
    if v["verdict"] != "PASS":
        report["all_green"] = False
    report["slots"].append(e)

c = ASTSandboxCorrector(":memory:")
sk = [c.get_canonical_skeleton(s["expression"]) for s in SLOTS]
freq = Counter(sk)
report["skeleton_freq"] = dict(freq)
if any(n > 2 for n in freq.values()):
    report["all_green"] = False
with open(os.path.join(HERE, "stage4_gate_report_R8.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90+other466", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "CROSS_CONVERGENCE",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "R8 收敛: rank×窗10 合并 / 付息口径对照 / 三腿 / 行业内排序 / 基线窗消融"},
}
with open(os.path.join(HERE, "batch_R8.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<28} ops={e['math_ops']} G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton distinct:", len(freq), "/", len(SLOTS), "| ALL GREEN:", report["all_green"])
