# -*- coding: utf-8 -*-
"""AEGIS Stage 3/4: R3 受控正交消融批 (Stage 4 处方化攻坚)

法医诊断依据 (R1/R2 实测):
  1. 回测物理条件配置错误: 账户 70 条已提交 alpha 中 34 条 SUBINDUSTRY / 25 条 decay=4 /
     40 条 truncation=0.08，而 R1 用 NONE/decay0/0.025 -> 已修正。
  2. ts_zscore / group_zscore 连续输出导致 43~52% 换手，Margin 被交易成本吃光 (<=0.76bps)。
     处方: 改用账户已验证的 rank / group_rank 整数型截面映射结构 (权重均匀、抑制 CONCENTRATED_WEIGHT)。
  3. 平台字段级 filter_sharpe 揭示方向性: cscore / chs_default / ohlson / icfroe_1y / icfroe_3y /
     short_term_debt / accruals_vol / eps_sur_vol / sg_a_inefficiency / pension_ev 均为负 Sharpe
     -> 反向持有 (做空该类暴露) 方为正收益方向。
"""
import json, os, sys, ast as _ast
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))

from quant_framework.core.dimension_rules import DimensionAuditor, ASTSymbolicVisitor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

KB = json.load(open(os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental90.json"),
                    encoding="utf-8"))
ALL = KB["fields"]

NEW_FIELDS = [
    "fnd90_us_game_pension_ev", "fnd90_us_game_pension_pbo",
    "fnd90_us_qes_gamef_chs_default", "fnd90_us_qes_gamef_ohlson", "fnd90_us_qes_gamef_cscore",
    "fnd90_us_game_receivable_days", "fnd90_us_game_inventory_days", "fnd90_us_game_payble_days",
    "fnd90_us_qes_gamef_grossprofit_asset", "fnd90_us_qes_gamef_icfroe_1y",
    "fnd90_game_accruals_vol", "fnd90_game_eps_sur_vol",
    "fnd90_game_sg_a_inefficiency", "fnd90_game_short_term_debt",
    "fnd90_us_game_inventory_chg", "fnd90_us_game_receivable_chg",
]
KNOWN = {f: ALL[f] for f in NEW_FIELDS}

SLOTS = [
    {
        "id": "R3_S1_PENSION_OFFBALANCE",
        "expression": "-rank(add(vec_avg(fnd90_us_game_pension_ev), vec_avg(fnd90_us_game_pension_pbo)))",
        "counterparty": "只按表内有息负债建模的信用评级模型与质量/ESG 指数编制方",
        "optimize_reason": (
            "养老金义务(PBO)与其他福利义务相对企业价值(TEV)的双重负担构成表外固定索取权。"
            "权益定价普遍只贴现表内有息负债，精算假设披露滞后且 SFAS158 口径复杂，"
            "导致这类隐性杠杆被系统性低估；用 rank 做均匀截面映射可抑制极值集中。"),
    },
    {
        "id": "R3_S2_DISTRESS_TRIPLE",
        "expression": "-rank(add(add(vec_avg(fnd90_us_qes_gamef_chs_default), vec_avg(fnd90_us_qes_gamef_ohlson)), vec_avg(fnd90_us_qes_gamef_cscore)))",
        "counterparty": "追逐困境反转与高波动'翻身股'的彩票偏好资金；受 mandate 限制无法做空垃圾股的机构单边买盘",
        "optimize_reason": (
            "CHS 违约概率、Ohlson O 分与 Montier C 分三者分别度量破产风险、会计破产征兆与盈余操纵嫌疑，"
            "平台字段级检测三者均为负向 Sharpe，说明市场系统性高估高困境公司。"
            "三源同向叠加后做空，可把单一指标的度量噪声相互抵消，提升信噪比。"),
    },
    {
        "id": "R3_S3_CASH_CONVERSION",
        "expression": "-rank(subtract(add(vec_avg(fnd90_us_game_receivable_days), vec_avg(fnd90_us_game_inventory_days)), vec_avg(fnd90_us_game_payble_days)))",
        "counterparty": "以营收增速与毛利率排序选股、不考察营运资本占款效率的基本面动量盘",
        "optimize_reason": (
            "现金转换周期 = 应收天数 + 存货天数 - 应付天数。周期长的公司现金被营运资本长期占用，"
            "自由现金流被侵蚀且对利率上行更敏感，而会计利润在短期内不体现该损耗。"
            "用减法构造净占款后整体取截面排序，避免单独看某一项时的行业口径偏误。"),
    },
    {
        "id": "R3_S4_ACCRUAL_FORECAST_QUALITY",
        "expression": "-rank(add(vec_avg(fnd90_game_accruals_vol), vec_avg(fnd90_game_eps_sur_vol)))",
        "counterparty": "依赖卖方一致预期与表观 EPS 增速的量化选股模型",
        "optimize_reason": (
            "应计项目波动率与卖方 EPS 预测误差波动率共同度量'账面利润的可兑现程度'。"
            "两者同高意味着利润主要由应计与乐观偏差构成，后续现金兑现时估值会被下修。"
            "选用全球口径家族字段以避开美国口径家族的口径混入。"),
    },
    {
        "id": "R3_S5_WORKING_CAPITAL_EXPANSION",
        "expression": "-rank(add(vec_avg(fnd90_us_game_inventory_chg), vec_avg(fnd90_us_game_receivable_chg)))",
        "counterparty": "把存货与应收扩张解读为需求景气的成长型配置盘",
        "optimize_reason": (
            "R2 批次中该母本以连续 z-score 形式取得全批最高的 0.43 Sharpe，"
            "但 44.6% 换手使 Margin 仅 0.50bps。此处改以 rank 均匀截面映射重构同一因果，"
            "在保持方向性的同时压低头部持仓集中度与交易磨损。"),
    },
    {
        "id": "R3_S6_WORKING_CAPITAL_SMOOTHED",
        "expression": "-rank(add(ts_mean(vec_avg(fnd90_us_game_inventory_chg), 20), ts_mean(vec_avg(fnd90_us_game_receivable_chg), 20)))",
        "counterparty": "以单期财报增量作为决策输入的短周期量化盘",
        "optimize_reason": (
            "与 Slot5 同源但引入 20 日时序均值平滑：低频基本面字段在事件日之间存在跳变，"
            "平滑可把单期噪声转化为持续持仓，从而抬升单位换手所承载的收益，"
            "并直接针对 Step1 中 Margin 过薄的病灶。"),
    },
    {
        "id": "R3_S7_GROSSPROFIT_VS_ICFROE",
        "expression": "subtract(rank(vec_avg(fnd90_us_qes_gamef_grossprofit_asset)), rank(vec_avg(fnd90_us_qes_gamef_icfroe_1y)))",
        "counterparty": "追逐增量现金回报改善的成长股配置盘与卖方'现金流转机'叙事",
        "optimize_reason": (
            "毛利率/资产比度量可持续的结构性盈利能力，而一年期增量现金回报率属于高波动的短期改善指标，"
            "平台字段级检测后者为负向 Sharpe，说明市场对其改善的持续性定价过度。"
            "二者相减即为剔除短期现金修辞后的真实生产效率。"),
    },
    {
        "id": "R3_S8_SGA_SHORTDEBT_SQUEEZE",
        "expression": "-rank(add(vec_avg(fnd90_game_sg_a_inefficiency), vec_avg(fnd90_game_short_term_debt)))",
        "counterparty": "按营收弹性配置、忽略成本刚性与再融资风险的周期成长资金",
        "optimize_reason": (
            "SG&A 低效度衡量费用刚性，短期债务占比衡量再融资敞口；"
            "两者同高的公司在需求走弱时既无法压缩成本又面临滚续压力，亏损被非线性拉大，"
            "而市场在景气期对这两项风险定价不足。"),
    },
]

# ---------------- 本地硬门禁 ----------------
report = {"slots": [], "all_green": True}
for s in SLOTS:
    e = {"id": s["id"], "expression": s["expression"]}
    a = DimensionAuditor.audit_expression(s["expression"], KNOWN, category="fundamental",
                                          allow_pv_cross=False, max_operators=11)
    calls = [n for n in _ast.walk(_ast.parse(s["expression"], mode="eval")) if isinstance(n, _ast.Call)]
    vec = [n for n in calls if getattr(n.func, "id", "") in {"vec_avg","vec_sum","vec_count","vec_max","vec_min","vec_std","vec_norm","vec_percentage","vec_ir","vec_choose"}]
    e["math_ops"] = len(calls) - len(vec)
    e["vec_casts"] = len(vec)
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

with open(os.path.join(HERE, "stage4_gate_report_R3.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "ABLATION",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "Stage 4 处方化攻坚: rank 结构 + 平台字段级方向证据 + 母本纵深"},
}
with open(os.path.join(HERE, "batch_R3.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<34} mathOps={e['math_ops']}(+{e['vec_casts']}vec) G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton unique:", len(freq), "of", len(SLOTS))
print("ALL GREEN:", report["all_green"])
