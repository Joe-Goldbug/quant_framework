# -*- coding: utf-8 -*-
"""AEGIS R7: 跨数据集母本纵深 (母本 = R6 Slot8 leAXlk5e)

R6 实测: ts_mean(subtract(ts_zscore(vec_avg(cash_flow_coverage),252), ts_zscore(oth466_a_tnix)),20)
  Sharpe 0.54 | Margin 13.63bps | 年化 3.16% | 换手 4.6% | L:S 128:126
关键进展: 年化收益由单数据集的 1.98% 抬升至 3.16%，已越过 Margin>=10bps 与 换手>=5%
联立约束所需的 2.52% 门槛 —— 即【Margin 与换手的数学冲突已被跨数据集腿解开】。
剩余缺口: Sharpe 0.54 -> 1.58 (波动 5.85% 偏高)，Fitness 0.27 -> 1.00。

本批处方: 三腿纯化 / 换手抬入合规区 / 尾部截尾压波动 / 排序映射 / 替换真实付息口径。
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
    "oth466_a_tnix":            ("Interest And Related Expense - Total 利息及相关费用净额", 0.88, 2),
    "oth466_a_ttld":            ("Long-Term Debt - Total 长期债务总额", 0.86, 1),
    "oth466_cf_cash_int_pay":   ("Cash Interest Paid 实付现金利息", 0.95, 1),
    "oth466_cf_cash_from_oper": ("Cash From Operating Activities 经营活动现金流", 1.00, 0),
    "oth466_rt_cf_sales_q":     ("Cash Flow/Sales 经营现金流占销售额比", 0.98, 5),
    "oth466_rt_ebit_oper_mgn_q": ("Operating Margin 营业利润率", 1.00, 15),
}
F90 = ["fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt",
       "fnd90_us_game_sg_a_inefficiency"]
KNOWN = {f: KB90[f] for f in F90}
for f, (desc, cov, a) in P466.items():
    KNOWN[f] = {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                "semantic_role": "Signal_Flow", "description": desc,
                "coverage": cov, "alpha_count": a}

# 落盘 other466 字段画像
kb466 = {"dataset_id": "other466", "dataset_name": "Aggregated Fundamental Data",
         "category": "fundamental", "region": "USA", "universe": "TOP1000", "delay": 1,
         "total_fields": len(P466), "dataset_coverage": 0.827, "dataset_alpha_count": 3825,
         "physical_probe_evidence": [
             "565 个字段全部为 MATRIX 类型，无需 vec_* 降维，与 fundamental90 的 VECTOR 事件型形成互补。",
             "核心字段覆盖度接近 1.0 (cf_cash_from_oper=1.00, rt_ebit_oper_mgn_q=1.00, rt_cf_sales_q=0.98)，"
             "可显著缓解 fnd90 稀疏事件序列造成的持仓重排。",
             "字段级 alphaCount 0~15，属低拥挤度；数据集整体 3825 个 alpha。",
         ],
         "fields": {f: {"type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                        "semantic_role": "Signal_Flow", "description": d,
                        "coverage": c, "alpha_count": a} for f, (d, c, a) in P466.items()}}
json.dump(kb466, open(os.path.join(ROOT, "knowledge_base", "fields", "USA", "other466.json"),
                      "w", encoding="utf-8"), ensure_ascii=False, indent=2)

V = lambda x: "vec_avg(%s)" % x
Z = lambda x, w=252: "ts_zscore(%s, %d)" % (x, w)
CFC, STD = V("fnd90_us_game_cash_flow_coverage"), V("fnd90_us_game_short_term_debt")
TNIX = "oth466_a_tnix"

SLOTS = [
    {
        "id": "R7_S1_PARENT_PLUS_SHORTDEBT",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (Z(CFC), Z(STD), Z(TNIX)),
        "counterparty": "把已付利息视作唯一融资成本、忽略到期滚续压力的信用筛选模型",
        "optimize_reason": (
            "母本(模型覆盖度 - 真实利息)已把年化收益抬到 3.16%。此处追加模型化短期债务占比作为第三条腿："
            "利息费用只度量已发生的付息，短债占比才刻画即将到期的滚续压力。"
            "三腿同向扣除后，剩余样本同时通过了模型覆盖、实际付息与期限结构三道检验。"),
    },
    {
        "id": "R7_S2_PARENT_WINDOW_10",
        "expression": "ts_mean(subtract(%s, %s), 10)" % (Z(CFC), Z(TNIX)),
        "counterparty": "以年度财报节奏调仓、错失季度间信息更新的长期持有盘",
        "optimize_reason": (
            "母本换手 4.6% 略低于 5.0% 合规下限。此处把外层均值窗由 20 日缩短到 10 日，"
            "在不引入任何新变量的前提下把换手抬入合规区间；若收益同步显著下滑，"
            "则可反证该母本的收益主要来自极低频的年度重定价而非季度信息。"),
    },
    {
        "id": "R7_S3_PARENT_WINSORIZE",
        "expression": "winsorize(ts_mean(subtract(%s, %s), 20), std=3)" % (Z(CFC), Z(TNIX)),
        "counterparty": "按因子原始量级加权、使少数极端利息负担标的决定组合波动的量化盘",
        "optimize_reason": (
            "母本年化收益已达 3.16%，但 5.85% 的波动把 Sharpe 压到 0.54。"
            "波动主要来自两个数据集量纲差异叠加出的尾部脉冲：fnd90 的覆盖度是比率估计，"
            "利息费用是绝对金额，二者 z-score 相减后尾部会被少数重资产公司主导。"
            "以 3 倍标准差截尾直接针对该波动源，而非对收益做任何修饰。"),
    },
    {
        "id": "R7_S4_PARENT_RANK_MAP",
        "expression": "rank(ts_mean(subtract(%s, %s), 20))" % (Z(CFC), Z(TNIX)),
        "counterparty": "按因子量级加权、使头部少数标的决定损益的量化盘",
        "optimize_reason": (
            "母本横截面有效标的仅约 254 只（两数据集覆盖度交集收窄），头部集中度天然偏高。"
            "在最外层施加均匀排序映射可把每只标的的持仓份额拉平，"
            "使组合波动由全截面共同决定，从波动端而非收益端改善 Sharpe。"),
    },
    {
        "id": "R7_S5_PARENT_PAID_INTEREST",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (Z(CFC), Z("oth466_cf_cash_int_pay")),
        "counterparty": "以应计利息估算融资成本、不看实际现金流出的信用模型",
        "optimize_reason": (
            "把母本的真实付息口径由应计利息费用换成现金流量表中的实付现金利息。"
            "应计利息包含资本化与摊销部分，实付利息才是真正流出企业的现金；"
            "这一替换检验母本的收益究竟来自会计口径还是现金口径的融资压力。"),
    },
    {
        "id": "R7_S6_TRIPLE_NET_CUSHION",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z("oth466_cf_cash_from_oper"), Z(TNIX), Z(STD)),
        "counterparty": "只看现金流总量、不扣减刚性付息与到期滚续的成长型配置盘",
        "optimize_reason": (
            "直接从真实报表构造净现金垫：经营活动现金流减去实付利息，再扣除模型化的短期债务压力。"
            "相比母本用模型估计的覆盖度，这里全部采用真实科目做分子分母，"
            "仅保留模型对期限结构的判断作为第三腿，是更纯粹的账实结合构造。"),
    },
    {
        "id": "R7_S7_OPMARGIN_THIRD_LEG",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z("oth466_rt_ebit_oper_mgn_q"), Z(V("fnd90_us_game_sg_a_inefficiency")), Z(STD)),
        "counterparty": "按模型化费用评分剔除标的、并忽视到期结构的选股器",
        "optimize_reason": (
            "R6 中该两腿结构取得全批最高的两年期 Sharpe 1.36，说明其近期有效性优于全样本均值。"
            "此处追加模型化短期债务占比作为第三条腿，检验其收益是否来自真实的成本优势，"
            "还是来自高杠杆公司在宽松周期里的费用摊薄效应。"),
    },
    {
        "id": "R7_S8_REAL_CASHFLOW_VS_MODEL_SHORTDEBT",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (Z("oth466_cf_cash_from_oper"), Z(STD)),
        "counterparty": "分别看待现金流与杠杆、不做交叉印证的信用与质量双因子模型",
        "optimize_reason": (
            "真实经营活动现金流与模型化短期债务压力构成最直接的账实交叉："
            "现金创造强且到期压力轻的公司，其安全性由真实科目而非模型评分支撑；"
            "而现金创造弱却被评为短债压力轻者，暴露了模型对期限结构的误判。"),
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
with open(os.path.join(HERE, "stage4_gate_report_R7.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90+other466", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "CROSS_DEEP_REFINEMENT",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "R7 跨数据集母本纵深: 压波动 / 抬换手 / 三腿纯化 / 口径替换"},
}
with open(os.path.join(HERE, "batch_R7.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<30} ops={e['math_ops']} G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton distinct:", len(freq), "/", len(SLOTS), "| ALL GREEN:", report["all_green"])
