# -*- coding: utf-8 -*-
"""AEGIS Stage 4: R5 母本纵深攻坚批 (母本 = R4 Slot4 mLo9AnO1, Sharpe 0.62 / Margin 10.24bps)

病灶: Sharpe 0.62 << 1.58; Fitness 0.24 << 1.00; 换手 3.7% 低于 AEGIS 5.0% 下限。
处方:
  * 缩短外层平滑窗 (20 -> 10) 把换手推入 [5%, 50%] 合规区间；
  * 追加第三条同向腿 (股权稀释) 抬升单位换手所承载的收益；
  * 用 group_zscore(subindustry) / group_rank 替换时序标准化，检验截面口径是否更稳健；
  * 用 winsorize 抑制尾部脉冲对 Fitness 的拖累。
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
    "fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt",
    "fnd90_us_game_equity_dilution", "fnd90_us_qes_gamef_grossprofit_asset",
    "fnd90_us_game_accruals_vol", "fnd90_us_game_eff_interest_rate",
    "fnd90_us_game_capex_dep", "fnd90_us_game_total_debt_chg",
    "fnd90_us_game_inc_cash_tax", "contingent_liabilities_equity_ratio",
]
KNOWN = {f: ALL[f] for f in FIELDS}
V = lambda x: "vec_avg(%s)" % x
Z = lambda x, w=252: "ts_zscore(%s, %d)" % (V(x), w)

CFC, STD = "fnd90_us_game_cash_flow_coverage", "fnd90_us_game_short_term_debt"

SLOTS = [
    {
        "id": "R5_S1_PARENT_WINDOW_10",
        "expression": "ts_mean(subtract(%s, %s), 10)" % (Z(CFC), Z(STD)),
        "counterparty": "只看负债总额、不看偿债覆盖能力与期限结构的信用筛选模型",
        "optimize_reason": (
            "母本在 20 日平滑下取得 10.24bps Margin，但 3.7% 换手低于 5.0% 合规下限，"
            "相当于仓位几乎不动、收益未被充分周转。此处把外层均值窗缩短至 10 日，"
            "在不引入任何新因果变量的前提下把换手抬入合规区间，检验收益是否来自可周转的持续信息。"),
    },
    {
        "id": "R5_S2_PARENT_THIRD_LEG_DILUTION",
        "expression": "ts_mean(subtract(subtract(%s, %s), %s), 20)" % (
            Z(CFC), Z(STD), Z("fnd90_us_game_equity_dilution")),
        "counterparty": "以债务滚动能力为唯一安全边际、忽视股东摊薄的信用与高收益配置盘",
        "optimize_reason": (
            "在母本两条腿之外追加股权稀释：即便现金流覆盖充足且短债压力可控，"
            "若公司持续靠增发摊薄来维持覆盖度，则所谓安全边际是融资堆出来的而非经营创造的。"
            "以减法剔除这类伪安全，使剩余样本的安全边际更纯粹，从而抬升单位风险的收益。"),
    },
    {
        "id": "R5_S3_PARENT_CROSS_SECTIONAL",
        "expression": "ts_mean(subtract(group_zscore(%s, subindustry), group_zscore(%s, subindustry)), 20)" % (
            V(CFC), V(STD)),
        "counterparty": "跨行业统一比较杠杆与覆盖度、因而错杀资本密集行业的量化模型",
        "optimize_reason": (
            "把母本的时序自比标准化替换为子行业内截面标准化：公用事业与银行业的覆盖度中枢天然不同，"
            "时序自比会把行业固有的资本结构差异误判为安全边际差异。"
            "改为同业口径后，剩余横截面差异才是真正的相对安全边际。"),
    },
    {
        "id": "R5_S4_PARENT_RANK_MAP",
        "expression": "rank(ts_mean(subtract(%s, %s), 20))" % (Z(CFC), Z(STD)),
        "counterparty": "按因子原始量级加权、使少数极端标的决定组合损益的量化盘",
        "optimize_reason": (
            "母本保持时序自比结构，仅在最外层施加均匀截面排序映射。"
            "覆盖度与短债的 z-score 之差存在厚尾，少数极端标的会主导组合，"
            "排序映射把每只标的的持仓份额拉平，令收益由全截面广度而非个股脉冲贡献。"),
    },
    {
        "id": "R5_S5_GROSSPROFIT_VS_ACCRUAL_NOISE",
        "expression": "subtract(group_rank(ts_mean(%s, 20), subindustry), group_rank(ts_mean(%s, 20), subindustry))" % (
            V("fnd90_us_qes_gamef_grossprofit_asset"), V("fnd90_us_game_accruals_vol")),
        "counterparty": "按毛利率/资产比排序的质量因子与不看应计噪声的 ESG/质量指数编制方",
        "optimize_reason": (
            "毛利率/资产比度量结构性盈利能力，应计波动率度量账面利润的可兑现程度。"
            "此处把平滑施加在每条腿内部而非合成之后，构成平滑位置消融："
            "若逐腿平滑优于合成后平滑，说明两条腿的更新节奏不同，需分别处理各自的稀疏跳变。"),
    },
    {
        "id": "R5_S6_COVERAGE_VS_INTEREST_COST",
        "expression": "winsorize(ts_mean(subtract(%s, %s), 20), std=3)" % (
            Z(CFC), Z("fnd90_us_game_eff_interest_rate")),
        "counterparty": "只看债务规模、不看实际付息成本的杠杆筛选模型",
        "optimize_reason": (
            "有效利率是债权人对公司信用给出的市场化定价，比账面短债占比更前瞻："
            "覆盖度高但付息成本高，说明债权人已察觉财报未体现的风险。"
            "以外层 3 倍标准差截尾抑制极端脉冲对 Fitness 的拖累。"),
    },
    {
        "id": "R5_S7_REINVEST_VS_DEBT_EXPANSION",
        "expression": "ts_mean(subtract(%s, %s), 20)" % (
            Z("fnd90_us_game_capex_dep"), Z("fnd90_us_game_total_debt_chg")),
        "counterparty": "把资本开支解读为成长投入、同时忽视其融资来源的成长股配置盘",
        "optimize_reason": (
            "资本开支相对折旧的比率衡量再投资强度，总债务扩张衡量其融资来源。"
            "再投资由经营现金支撑时是真实扩张，由举债支撑时则是杠杆堆积；"
            "二者相减即为剔除融资修辞后的真实再投资强度。"),
    },
    {
        "id": "R5_S8_TAX_CONTINGENT_OFFBALANCE",
        "expression": "-ts_mean(add(%s, %s), 20)" % (
            Z("fnd90_us_game_inc_cash_tax"), Z("contingent_liabilities_equity_ratio")),
        "counterparty": "以表观有效税率与账面负债率建模、忽略表外或有索取权的估值模型",
        "optimize_reason": (
            "利润表税负相对现金税负的偏离揭示递延与激进入账，或有负债相对权益的比率则是表外索取权。"
            "两者同高意味着账面利润与账面权益同时被高估，属于尚未被定价的双重虚增，"
            "反向持有可捕获其回归真实价值的过程。"),
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
with open(os.path.join(HERE, "stage4_gate_report_R5.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

batch = {
    "region": "USA", "universe": "TOP1000", "delay": 1,
    "dataset": "fundamental90", "category": "fundamental",
    "neutralization": "SUBINDUSTRY", "decay": 4, "truncation": 0.08,
    "submission_forbidden": True,
    "known_fields": KNOWN,
    "items": [{"slot": i + 1, "seed_id": s["id"], "type": "DEEP_REFINEMENT",
               "expression": s["expression"], "counterparty": s["counterparty"],
               "optimize_reason": s["optimize_reason"]} for i, s in enumerate(SLOTS)],
    "slot_meta": {"purpose": "Stage 4 母本纵深: 换手区间修复 / 三腿纯化 / 截面口径 / 尾部截尾"},
}
with open(os.path.join(HERE, "batch_R5.json"), "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=2)

for e in report["slots"]:
    print(f"{e['id']:<34} ops={e['math_ops']} G2={'OK' if e['gate2']['ok'] else 'FAIL'} G1={e['gate1']['verdict']}")
    for k in (e["gate2"]["issues"], e["gate1"]["issues"]):
        if k:
            print("      !", k)
print("skeleton freq max:", max(freq.values()), "| ALL GREEN:", report["all_green"])
