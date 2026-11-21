# -*- coding: utf-8 -*-
"""AEGIS R6: 跨数据集批 (fundamental90 × other466) —— 双数据集上限内的二阶预期差

选伴理由 (零回测勘探):
  other466「Aggregated Fundamental Data」565 字段全部为 MATRIX(无需 vec_* 降维)，
  且 oth466_rt_cf_sales_q(0.98)/oth466_rt_ebit_oper_mgn_q(1.00)/oth466_cf_cash_from_oper(1.00)
  等覆盖度接近 1.0，可避免 fnd90 稀疏事件序列带来的换手扰动。

核心经济学: fnd90 是【模型输出】(集成学习对治理/会计/管理/平等维度的评分)，
other466 是【真实报表科目】。模型判定与现实科目的**背离**，才是真正未被定价的二阶信息：
  * 真实现金创造强 / 真实毛利高，但模型给出危险或低效判定 → 模型误判 → 做多(错杀反转)
  * 真实债务与利息负担重，同时模型短债压力高 → 双重印证 → 做空
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

P466 = {
    "oth466_rt_cf_sales_q":      ("Cash Flow/Sales 经营现金流占销售额比", 0.98, 5),
    "oth466_rt_gross_margin":    ("Gross Margin 毛利率", 0.89, 2),
    "oth466_rt_ebit_oper_mgn_q": ("Operating Margin 营业利润率", 1.00, 15),
    "oth466_a_ttld":             ("Long-Term Debt - Total 长期债务总额", 0.86, 1),
    "oth466_a_tnix":             ("Interest And Related Expense - Total 利息及相关费用净额", 0.88, 2),
    "oth466_cf_cash_from_oper":  ("Cash From Operating Activities 经营活动现金流", 1.00, 0),
}
F90 = [
    "fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt",
    "fnd90_us_game_optimism_sale", "fnd90_us_game_earning_smooth",
    "fnd90_us_qes_gamef_chs_default", "fnd90_us_game_sg_a_inefficiency",
]

KNOWN = {f: KB90[f] for f in F90}
for f, (desc, cov, a) in P466.items():
    KNOWN[f] = {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                "semantic_role": "Signal_Flow", "description": desc,
                "coverage": cov, "alpha_count": a}

V = lambda x: "vec_avg(%s)" % x
Z = lambda x, w=252: "ts_zscore(%s, %d)" % (x, w)
CFC = V("fnd90_us_game_cash_flow_coverage")
STD = V("fnd90_us_game_short_term_debt")

SLOTS = [
    {
        "id": "R6_S1_PARENT_PLUS_REAL_LTD",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z(CFC), Z(STD), Z("oth466_a_ttld")),
        "counterparty": "只按模型化偿债评分配置、不核对真实长期负债余额的量化信用盘",
        "optimize_reason": (
            "母本(覆盖度-短债)已取得 10/10 年正收益但振幅偏弱。此处追加真实报表长期债务总额作为第三条腿："
            "模型化的短债占比只刻画期限结构，真实长期债务余额才决定了到期的刚性偿付规模。"
            "两者同向剔除后，剩余样本的安全边际才同时通过模型与账实两道检验。"),
    },
    {
        "id": "R6_S2_PARENT_PLUS_REAL_INTEREST",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z(CFC), Z(STD), Z("oth466_a_tnix")),
        "counterparty": "以账面利率估算融资压力、不看实际已付利息规模的信用模型",
        "optimize_reason": (
            "把第三条腿由债务余额换成实际利息与相关费用净额：利息费用是融资压力已兑现的部分，"
            "比债务存量更直接地侵蚀自由现金流。与母本同向扣除后，可分离出'低息且短债轻且覆盖足'的真安全边际。"),
    },
    {
        "id": "R6_S3_REAL_MARGIN_VS_MODEL_OPTIMISM",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (
            Z("oth466_rt_gross_margin"), Z(V("fnd90_us_game_optimism_sale"))),
        "counterparty": "依赖卖方一致预期给成长溢价的资金，以及按预期而非按已实现毛利排序的选股模型",
        "optimize_reason": (
            "真实毛利率是已实现的定价能力，卖方销售乐观度只是对未来的预期。"
            "已实现毛利高而卖方预期冷淡的公司，其盈利质量尚未被预期定价；"
            "反之预期火热但毛利平平者，估值建立在未被验证的叙事上。跨数据集相减即为现实与预期之差。"),
    },
    {
        "id": "R6_S4_REAL_CASHFLOW_VS_MODEL_SMOOTHING",
        "expression": "ts_mean(subtract(group_zscore(oth466_rt_cf_sales_q, subindustry), group_zscore(%s, subindustry)), 20)" % (
            V("fnd90_us_game_earning_smooth")),
        "counterparty": "把盈余平滑读作经营稳定、并据此给低风险溢价的质量型配置盘",
        "optimize_reason": (
            "盈余平滑既可能来自真实经营稳定，也可能来自跨期调节；经营现金流占销售额比是判别标准。"
            "在子行业内同口径比较二者：现金转化强而平滑度低者是真实的稳定经营，"
            "现金转化弱而平滑度高者则是账面调节，市场往往只对后者给溢价。"),
    },
    {
        "id": "R6_S5_MISJUDGED_DISTRESS_REVERSAL",
        "expression": "rank(ts_mean(subtract(%s, %s), 20))" % (
            Z("oth466_rt_cf_sales_q"), Z(V("fnd90_us_qes_gamef_chs_default"))),
        "counterparty": "按历史会计特征训练的违约预测模型及其下游的困境剔除名单",
        "optimize_reason": (
            "CHS 违约概率由历史会计比率回归得出，对已实现转型的公司反应滞后；"
            "经营现金流占销售额比是当期的真实造血能力。二者背离即为模型的错杀样本，"
            "反向持有可捕获名单修正带来的重定价。外层排序映射用于拉平持仓集中度。"),
    },
    {
        "id": "R6_S6_REAL_OPMARGIN_VS_MODEL_SGA",
        "expression": "winsorize(ts_mean(subtract(%s, %s), 20), std=3)" % (
            Z("oth466_rt_ebit_oper_mgn_q"), Z(V("fnd90_us_game_sg_a_inefficiency"))),
        "counterparty": "按模型化费用效率评分剔除标的、却忽视已实现营业利润率的基本面筛选器",
        "optimize_reason": (
            "模型化的 SG&A 低效度是费用率的统计刻画，而已实现营业利润率是费用控制的最终结果。"
            "高实际营业利润率却被评为费用低效，说明模型口径与公司真实成本结构不匹配；"
            "以 3 倍标准差截尾抑制两个数据集量纲差异带来的尾部脉冲。"),
    },
    {
        "id": "R6_S7_DUAL_DEBT_PRESSURE",
        "expression": "-ts_mean(add(%s, %s), 20)" % (
            Z("oth466_a_ttld"), Z(STD)),
        "counterparty": "分头看待长期负债与短期负债、因而低估滚续叠加风险的信用筛选模型",
        "optimize_reason": (
            "真实长期债务余额与模型化短期债务占比分别刻画偿付规模的存量和到期压力的强度。"
            "二者同时居高意味着既要滚续又要扩表，属双重融资压力；"
            "两次独立度量同向叠加可相互抵消各自口径噪声，比任一单项更稳健。"),
    },
    {
        "id": "R6_S8_MODEL_COVERAGE_VS_REAL_INTEREST",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (
            Z(CFC), Z("oth466_a_tnix")),
        "counterparty": "以模型化覆盖度评分代替真实付息负担的杠杆筛选器",
        "optimize_reason": (
            "模型化的经营现金流覆盖度是对偿债能力的估计，实际已付利息是偿债负担的兑现值。"
            "估计乐观而实际付息沉重者，其覆盖度评分建立在偏松的假设之上；"
            "二者相减即为剔除假设松紧后的真实偿债余量。"),
    },
]

report = {"slots": [], "all_green": True}
WRAPPERS = {"vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min", "vec_std",
            "vec_norm", "vec_percentage", "vec_ir", "vec_choose"}
for s in SLOTS:
    e = {"id": s["id"], "expression": s["expression"],
         "datasets": sorted({("fundamental90" if "fnd90_" in s["expression"] else "other466"),
                             "other466" if "oth466_" in s["expression"] else "fundamental90"})}
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
with open(os.path.join(HERE, "stage4_gate_report_R6.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90+other466", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "CROSS_DATASET",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "跨数据集二阶预期差: fnd90 模型输出 × other466 真实报表 (双数据集上限)"},
}
with open(os.path.join(HERE, "batch_R6.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<36} ops={e['math_ops']} G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton distinct:", len(freq), "/", len(SLOTS), "| ALL GREEN:", report["all_green"])
