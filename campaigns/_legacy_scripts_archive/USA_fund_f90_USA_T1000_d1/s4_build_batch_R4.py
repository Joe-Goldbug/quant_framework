# -*- coding: utf-8 -*-
"""AEGIS Stage 4: R4 处方化攻坚批 —— 针对【稀疏事件序列死重病灶】

法医确诊 (R3 实测对照):
  * -rank(add(vec_avg(A), vec_avg(B)))            -> 换手 42.5%, Margin -0.18bps, CONCENTRATED_WEIGHT FAIL
  * -rank(add(ts_mean(vec_avg(A),20), ts_mean(vec_avg(B),20))) -> 换手 2.4%,  Margin  3.26bps, 无 CW FAIL
  诊断: fnd90 为稀疏事件型 VECTOR 序列，非事件日为 NaN。未做外层平滑时持仓在 NaN 进出间
  反复重排，制造 42% 的伪换手并吃光 Margin，同时使头部持仓权重抖动诱发 CONCENTRATED_WEIGHT。

处方 (Stage 4 授权): 【时序平滑移至事件合成最外层】—— 所有槽位在因果合成之后统一施加
  ts_mean(_, 20/60) 外层平滑，消除死重；保留内层 z-score 去中枢以保证符号守恒。
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

KB = json.load(open(os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental90.json"),
                    encoding="utf-8"))
ALL = KB["fields"]

FIELDS = [
    "fnd90_us_game_inventory_chg", "fnd90_us_game_receivable_chg",
    "fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt",
    "fnd90_us_game_total_debt_chg", "fnd90_us_game_other_asset_gr",
    "fnd90_us_game_optimism_sale", "fnd90_us_game_serial_special",
    "fnd90_us_game_receivable_days", "fnd90_us_game_inventory_days", "fnd90_us_game_payble_days",
    "fnd90_game_noa", "fnd90_game_accruals_vol",
]
KNOWN = {f: ALL[f] for f in FIELDS}

V = lambda x: "vec_avg(%s)" % x
Z = lambda x, w=252: "ts_zscore(%s, %d)" % (V(x), w)

SLOTS = [
    {
        "id": "R4_S1_WC_OUTER_SMOOTH_20",
        "expression": "-ts_mean(add(%s, %s), 20)" % (Z("fnd90_us_game_inventory_chg"),
                                                     Z("fnd90_us_game_receivable_chg")),
        "counterparty": "把存货与应收扩张解读为需求景气的成长型配置盘",
        "optimize_reason": (
            "R2 批中该母本以裸 z-score 形式取得 0.43 全批最高 Sharpe，却因 44.6% 伪换手使 Margin 仅 0.50bps。"
            "此处按处方把 20 日均值平滑移至事件合成最外层，抑制稀疏 NaN 造成的持仓重排，"
            "在不触碰内层因果结构的前提下抬升单位换手承载的收益。"),
    },
    {
        "id": "R4_S2_WC_OUTER_SMOOTH_60",
        "expression": "-ts_mean(add(%s, %s), 60)" % (Z("fnd90_us_game_inventory_chg"),
                                                     Z("fnd90_us_game_receivable_chg")),
        "counterparty": "以单季财报增量做决策、持仓随报告日跳变的短周期基本面盘",
        "optimize_reason": (
            "与 Slot1 完全同源，仅把外层平滑窗口由 20 日延长至 60 日，构成时序平滑拓扑消融："
            "用于判定该母本的收益究竟来自季报级的持续性信息，还是报告日附近的短脉冲，"
            "从而确定最优的持仓持久度而非盲目凑参数。"),
    },
    {
        "id": "R4_S3_WC_SMOOTH_THEN_RANK",
        "expression": "-rank(ts_mean(add(%s, %s), 20))" % (Z("fnd90_us_game_inventory_chg"),
                                                           Z("fnd90_us_game_receivable_chg")),
        "counterparty": "按因子原始量级加权、导致头部持仓过度集中的基本面量化盘",
        "optimize_reason": (
            "在 Slot1 外层平滑之上再施加均匀截面排序映射，针对 CONCENTRATED_WEIGHT 病灶："
            "z-score 相加后尾部极值仍会使少数标的占据过大账面份额，rank 映射把每只标的的持仓份额拉平，"
            "使收益由全截面广度贡献而非少数个股脉冲贡献。"),
    },
    {
        "id": "R4_S4_COVERAGE_VS_SHORTDEBT",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (Z("fnd90_us_game_cash_flow_coverage"),
                                                         Z("fnd90_us_game_short_term_debt")),
        "counterparty": "只看负债总额不看偿债覆盖能力与期限结构的信用筛选模型",
        "optimize_reason": (
            "经营现金流对总债务的覆盖度与短期债务占比构成偿债能力的二维刻画："
            "覆盖度高且短债压力小的公司再融资风险低，而市场在流动性宽松期对期限结构风险定价不足。"
            "以减法合成可避免双有符号变量相乘引发的符号反转，外层再平滑压制换手。"),
    },
    {
        "id": "R4_S5_DEBT_OTHERASSET_EXPANSION",
        "expression": "-ts_mean(add(%s, %s), 20)" % (Z("fnd90_us_game_total_debt_chg"),
                                                     Z("fnd90_us_game_other_asset_gr")),
        "counterparty": "以并购与扩表叙事配置仓位的成长资金，以及只看有息负债不看表外占用的人",
        "optimize_reason": (
            "总债务扩张与其他资产增长同步抬头，意味着资产端的膨胀并非由经营现金驱动，"
            "而是由融资与科目腾挪支撑，属于典型的低质量扩表。"
            "两个同向科目相加后取反做空，可把单项度量的口径噪声相互抵消。"),
    },
    {
        "id": "R4_S6_OPTIMISM_VS_SERIAL_SPECIAL",
        "expression": "ts_mean(subtract(group_zscore(%s, subindustry), group_zscore(%s, subindustry)), 20)" % (
            V("fnd90_us_game_optimism_sale"), V("fnd90_us_game_serial_special")),
        "counterparty": "依赖卖方一致预期、且不区分经常性损益与一次性损益的选股模型",
        "optimize_reason": (
            "卖方销售乐观度受承销关联偏误长期偏高；反复出现的'一次性'特殊项目则揭示公司持续借非经常科目调节利润。"
            "在子行业内做标准化后相减，剥离行业景气度，仅保留'乐观预期与利润质地'的背离，"
            "外层 20 日平滑消除稀疏事件日的持仓跳变。"),
    },
    {
        "id": "R4_S7_CCC_OUTER_SMOOTH",
        "expression": "-ts_mean(subtract(add(%s, %s), %s), 20)" % (
            V("fnd90_us_game_receivable_days"), V("fnd90_us_game_inventory_days"),
            V("fnd90_us_game_payble_days")),
        "counterparty": "以营收弹性配置、不考察营运资本占款效率的周期成长资金",
        "optimize_reason": (
            "现金转换周期 = 应收天数 + 存货天数 - 应付天数，度量现金被营运资本占用的净时长。"
            "R3 中该结构未做外层平滑时换手 42.7% 且 Margin 为负，此处补齐平滑处方，"
            "检验其失败究竟源于因果不成立还是源于换手磨损。"),
    },
    {
        "id": "R4_S8_NOA_ACCRUAL_GLOBAL",
        "expression": "-ts_mean(add(%s, %s), 20)" % (Z("fnd90_game_noa"), Z("fnd90_game_accruals_vol")),
        "counterparty": "把净经营资产增长解读为投资机会、并把应计波动当作经营波动的市场",
        "optimize_reason": (
            "净经营资产膨胀是 Sloan 应计异象的核心形态，应计波动率则度量账面利润的可兑现程度；"
            "两者同高意味着扩张部分难以转化为现金。此处刻意选用全球口径家族字段，"
            "以避开美国口径家族中两项指标方向不一致的口径冲突。"),
    },
]

# ---------------- 本地硬门禁 ----------------
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

with open(os.path.join(HERE, "stage4_gate_report_R4.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "PRESCRIPTION",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "Stage 4 处方: 时序平滑外移消除稀疏事件死重 + 母本纵深 + 新机制"},
}
with open(os.path.join(HERE, "batch_R4.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<32} mathOps={e['math_ops']}(+{e['vec_casts']}vec) G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton unique:", len(freq), "of", len(SLOTS), "| ALL GREEN:", report["all_green"])
