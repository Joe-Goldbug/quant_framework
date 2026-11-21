# -*- coding: utf-8 -*-
"""AEGIS Stage 5 -> Round 2: 法医归因后的受控对照批（4 主核 x 2 去中枢映射）。

R1 法医发现（决定性）:
  8/8 槽 shortCount = 0、Sharpe 高度雷同 0.66~0.76、换手仅 1.8~3.6%、回撤 52~67%、
  risk_neutralized_sharpe = -0.37、investability_sharpe ~ 0.01。
  诊断：无论底层信号如何变化，结果几乎完全一致 => PnL 由市场 beta 主导，信号贡献≈0。
  嫌疑根因：group_rank 输出恒为 [0,1] 正值，未去中枢 => 单边多头市场暴露。
  反证：平台存量 alpha bl8Wd2Nq 同样以 group_rank 收尾，却有 551 多 / 484 空。
  => 必须做受控实验裁定，禁止凭猜测改代码。

R2 设计（4x2 因子）:
  因子 A（主核，4 水平）: S7 净股权发行 / S2 FCF 生产率 / S5 资本开支强度 / S1 资产增长
  因子 B（去中枢映射，2 水平）: subtract(group_rank(.,industry), 0.5)  vs  group_zscore(.,industry)
  与 R1 的未去中枢同信号结果构成前后对照，可直接读出 ΔCentering。
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

MAX_OPS = 11  # 与 sim_runner Gate 2 一致 (Batch61 授权)；本批最高 9 个（含 1 个强制去中枢算子）

# 四个主核的"未映射原始量" X
CORES = {
    "S7_NET_EQUITY_ISSUANCE": {
        "core": "divide(subtract(abs(ts_backfill(fnd69_q2yktss, 252)), abs(ts_backfill(fnd69_q2ycktsrp, 252))), fnd69_qta)",
        "sign": "reverse",
        "counterparty": "在高估值窗口配合增发、赚取承销费并把供给冲击延迟转嫁的一级市场与卖方",
        "mechanism": "股票净发行（增发减回购）除以总资产 = 净股权融资强度。Loughran-Ritter / Pontiff-Woodgate 净股权发行异象：高净发行公司随后收益走低，做空净发行最高一档。abs 施加在两腿内部，净额符号完整保留且对符号约定免疫。",
        "extra": "两腿原始密度 38.8% / 39.0%，已 ts_backfill(252) 阶梯化，代价是最长约 250 日陈旧值；高回购与高增发并存的公司在净额口径下被抵消。",
    },
    "S2_FCF_PRODUCTIVITY": {
        "core": "divide(subtract(ts_backfill(fnd69_q2yfcnao, 252), abs(ts_backfill(fnd69_capxy2q, 252))), fnd69_qta)",
        "sign": None,
        "counterparty": "按营收/利润增速排序、系统忽视现金转化率的朴素成长配置盘",
        "mechanism": "自由现金流（经营性净现金流减资本开支）除以总资产 = 单位资产的现金创造效率。高生产率对应真实盈利能力，配置盘低估其持续性。",
        "extra": "两腿原始密度 43.3% / 42.0%，已阶梯化；abs 使本式对 capex 符号约定免疫。",
    },
    "S5_CAPEX_INTENSITY": {
        "core": "divide(abs(ts_backfill(fnd69_capxy2q, 252)), fnd69_qta)",
        "sign": "reverse",
        "counterparty": "为资本开支扩张故事提供增发与信贷供给的投行与银行，以及产能主题资金",
        "mechanism": "资本开支除以总资产 = 投资强度。Titman-Wei-Xie 投资异象：高强度资本开支后未来收益显著走低，做空投资强度最高一档。",
        "extra": "资本开支原始密度 42%，已阶梯化；长边为最低投资档，混入无能力投资的现金紧张公司。",
    },
    "S1_ASSET_GROWTH": {
        "core": "divide(ts_delta(fnd69_qta, 252), ts_mean(fnd69_qta, 252))",
        "sign": "reverse",
        "counterparty": "在并购扩表期有承销与佣金动机的卖方与投行",
        "mechanism": "总资产同比增量除以同期均值资产 = 资产扩张率。Cooper-Gulen-Schill 资产增长异象：激进扩表公司随后被证伪并杀估值，做空扩表最快一档。",
        "extra": "唯一 100% 密度字段，无需阶梯化；delay-1 下最长滞后约 15 个月。",
    },
}

MAPPINGS = [
    ("MAP_RANK_CENTERED", lambda s: f"subtract(group_rank({s}, industry), 0.5)",
     "group_rank 后减去 0.5 强制去中枢，把 [0,1] 序数平移为 [-0.5,+0.5] 对称双向暴露，使组合产生真实的空头腿。"),
    ("MAP_ZSCORE", lambda s: f"group_zscore({s}, industry)",
     "group_zscore 在行业内做标准化，天然零均值并保留尾部幅度信息，是另一种去中枢双向映射。"),
]

SLOTS = []
slot = 0
for core_name, c in CORES.items():
    base = c["core"] if c["sign"] is None else f"{c['sign']}({c['core']})"
    for map_name, fn, map_desc in MAPPINGS:
        slot += 1
        expr = fn(base)
        SLOTS.append({
            "slot": slot,
            "role": f"{core_name}__{map_name}",
            "expression": expr,
            "counterparty": c["counterparty"],
            "mechanism": c["mechanism"] + " 【本槽映射】" + map_desc,
            "variation_source": f"主核 {core_name} x 映射 {map_name}",
            "hypothesis_lines": [
                f"对手盘：{c['counterparty']}。",
                f"摩擦（诚实披露）：{c['extra']}",
                f"变动源：主核 {core_name} 的截面离散度；本槽仅用于裁定去中枢映射是否为 R1 短腿缺失的根因。",
            ],
        })


def main():
    report = {"round": 2, "design": "4 cores x 2 centering mappings", "slots": [], "all_valid": True}

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
        corrected = corrector.check_and_record_batch(raw, "USA", "TOP1000", 1, "NONE")
        report["skeleton_check"] = {"status": "PASS"}
        for s, cx in zip(SLOTS, corrected):
            s["expression"] = cx
    except Exception as e:
        report["skeleton_check"] = {"status": "FAIL", "error": repr(e)}
        report["all_valid"] = False

    items = [{"expression": s["expression"], "counterparty": s["counterparty"],
              "optimize_reason": s["mechanism"]} for s in SLOTS]
    vp = os.path.join(HERE, "batch_R2_red_team.json")
    v = DoubleBlindRedTeam.sign_batch_verdicts(items, FIELDS, vp)
    report["red_team"] = {"all_passed": v.get("all_passed"),
                          "per_slot": [{"slot": i + 1, "verdict": x["verdict"], "issues": x["issues"]}
                                       for i, x in enumerate(v.get("verdicts", []))]}
    if not v.get("all_passed"):
        report["all_valid"] = False

    with open(os.path.join(HERE, "stage5_gate_report_R2.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "batch_R2.json"), "w", encoding="utf-8") as f:
        json.dump({"region": "USA", "universe": "TOP1000", "delay": 1,
                   "dataset": "fundamental69", "category": "fundamental",
                   "neutralization": "NONE", "decay": 0, "truncation": 0.025,
                   "submission_forbidden": True, "known_fields": FIELDS,
                   "items": items, "slot_meta": SLOTS}, f, ensure_ascii=False, indent=2)

    print("=" * 90)
    print(f"R2 AST 全通过: {report['all_valid']}")
    for r in report["slots"]:
        a = r["ast_audit"]
        print(f"  S{r['slot']} {r['role']:<48} valid={a['is_valid']} ops={a['operator_count']} fields={len(a['used_fields'])}")
        print(f"       {r['expression']}")
        if not a["is_valid"]:
            print(f"     ! {a['issues']}")
    print(f"骨架: {report['skeleton_check'].get('status')} | 红队: {report['red_team']['all_passed']}")
    print("=" * 90)


if __name__ == "__main__":
    main()
