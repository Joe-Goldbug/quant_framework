# -*- coding: utf-8 -*-
"""S4 accrual_quality seed candidate local pre-flight (ZERO-QUOTA static analysis only)."""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import stage3_preflight as P

CANDIDATES = [
    {
        "id": "S4_AQ_01",
        "question_type": "Q4",
        "expression": (
            "power(subtract(group_rank(divide(fnd17_fcfq, fnd17_atmtt), sector), 0.5), 5)"
        ),
        "fields_used": ["fnd17_fcfq", "fnd17_atmtt"],
        "economic_mechanism": "季度自由现金流 / TTM 总资产 = 现金流强度的规模无关度量；"
                              "组内秩锐化后持有现金流强度显著高于同业的公司，"
                              "捕捉『盈利现金转化优于资产规模』的超额收益。",
        "counterparty": "忽略现金流强度、仅盯账面资产回报率的传统基本面资金",
    },
    {
        "id": "S4_AQ_02",
        "question_type": "Q8",
        "expression": (
            "power(subtract(group_rank(fnd17_aniacnorm, sector), group_rank(fnd17_aniac, sector)), 5)"
        ),
        "fields_used": ["fnd17_aniacnorm", "fnd17_aniac"],
        "economic_mechanism": "归母正常化净利与归母报告净利的组内秩差 = 一次性项目对盈利的扭曲幅度；"
                              "被一次性损失压低盈利的公司未来盈利可回补，被一次性收益抬高盈利的公司将均值回归。"
                              "奇数次幂保持零均值且放大极端扭曲信号。",
        "counterparty": "追逐一次性利好的业绩追逐型买方 / 做空被一次性损失压低盈利的价值陷阱",
    },
    {
        "id": "S4_AQ_03",
        "question_type": "Q1",
        "expression": (
            "power(subtract(group_rank(divide(fnd17_fcf1a, fnd17_atotce), sector), 0.5), 5)"
        ),
        "fields_used": ["fnd17_fcf1a", "fnd17_atotce"],
        "economic_mechanism": "财年自由现金流 / 财年账面权益 = 规模无关的现金回报基准（现金 ROE）；"
                              "组内秩锐化后持有现金回报显著高于同业的公司，规避杠杆扭曲的会计 ROE。",
        "counterparty": "偏好低现金回报、重资产低效率标的的资金",
    },
    {
        "id": "S4_AQ_04",
        "question_type": "Q5",
        "expression": (
            "power(subtract(group_rank(divide(fnd17_fcf1a, add(abs(fnd17_aniacnorm), 1)), sector), 0.5), 5)"
        ),
        "fields_used": ["fnd17_fcf1a", "fnd17_aniacnorm"],
        "economic_mechanism": "财年自由现金流 / |财年正常化净利| = 现金对盈利的支撑倍数；"
                              "分母取绝对值 + 1 后符号完全由现金流决定，亏损公司不会被符号翻转污染。",
        "counterparty": "以账面利润为唯一锚、忽略现金流验证的估值锚定型资金",
    },
]


def main():
    meta = P.load_meta()
    print("meta fields:", len(meta))
    out = []
    exprs = []
    for c in CANDIDATES:
        exprs.append(c["expression"])
        r = P.preflight(c["expression"], c["economic_mechanism"], c["counterparty"],
                        meta, meta, phase0=False, op_cap_override=P.ENGINE_MAX_OPS)
        out.append("=" * 78)
        out.append("%s  %s" % (c["id"], c["question_type"]))
        out.append("EXPR: " + c["expression"])
        out.append("ok=%s" % r["ok"])
        for iss in r["issues"]:
            out.append("  ISSUE: " + iss)
        ch = r["checks"]
        out.append("  ops=%s (engine cap %s) fields=%s top=%s zero_mean=%s window_ok=%s field_truth=%s pv_clean=%s"
                   % (ch.get("operator_count"), P.ENGINE_MAX_OPS, ch.get("field_count"),
                      ch.get("top_level"), ch.get("top_level_zero_mean_ok"),
                      ch.get("window_ok"), ch.get("field_truth_ok"), ch.get("pv_clean")))
        out.append("  windows=%s  banned=%s  mult_legs_ok=%s  unit_consistent=%s"
                   % (ch.get("windows"), ch.get("banned_ops"), ch.get("multiply_legs_ok"),
                      ch.get("unit_consistent")))
        out.append("  dimension_audit=%s" % json.dumps(ch.get("dimension_audit"), ensure_ascii=False))
        out.append("  redteam=%s" % json.dumps(ch.get("engine_redteam"), ensure_ascii=False))

    # G6 skeleton uniqueness + cross-batch history
    try:
        sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
        out.append("=" * 78)
        out.append("G6 skeletons:")
        for e, s, h in zip(exprs, sk["skeletons"], [sk["history"].get(s, 0) for s in sk["skeletons"]]):
            out.append("  hist=%s :: %s" % (h, s))
        out.append("  violations=%s" % sk["violations"])
    except Exception as e:
        out.append("=" * 78)
        out.append("G6 skeleton check unavailable: %r" % (e,))

    # also compare against every expression already measured in this campaign
    try:
        seen = set()
        for f in ("batch_S1.json", "batch_S2.json", "batch_S3_CAMPAIGN.json"):
            p = os.path.join(HERE, f)
            if not os.path.exists(p):
                continue
            d = json.load(open(p, encoding="utf-8"))
            for it in d.get("candidates", d if isinstance(d, list) else []):
                e = (it or {}).get("expression")
                if e:
                    seen.add(P.ASTSandboxCorrector.get_canonical_skeleton(e)
                             if hasattr(P, "ASTSandboxCorrector") else e)
        out.append("=" * 78)
        out.append("prior-batch skeleton count: %d" % len(seen))
        sk_res = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
        for e, s in zip(exprs, sk_res["skeletons"]):
            out.append("  collides_with_prior=%s :: %s" % (s in seen, s))
    except Exception as e:
        out.append("prior-batch skeleton compare unavailable: %r" % (e,))

    with open(os.path.join(HERE, "_tmp_preflight.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("done -> _tmp_preflight.txt")


if __name__ == "__main__":
    main()