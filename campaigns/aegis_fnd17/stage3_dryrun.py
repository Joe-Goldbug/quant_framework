# -*- coding: utf-8 -*-
"""
Stage 3 · 干跑自检 (dry-run of the full local gate chain, ZERO backtest quota)
目的：在真实种子到达之前，先证明 8 槽批次能通过 SimBatchRunner 的
Gate1(红队) / Gate2(量纲) / Gate3(骨架) / Gate5(Tabu) 全链，
并且 batch_S1.json 的字段结构与引擎期望完全一致。
用 8 条"已验证字段"的合成表达式做样例；它们不会发包。
"""
import json, os, sys, asyncio, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.sim_runner import SimBatchRunner

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "fundamental"
NEUTRALIZATION = "STATISTICAL"

# 8 条样例：全部使用已核实的孪生字段，拓扑刻意各不相同（Gate3 要求同骨架<=2）
SAMPLES = [
    ("Q2_twin_roa",
     "zscore(subtract(fnd17_tcpaormtt,fnd17_tcpaormtp))",
     "TTM 资产回报率相对上一滚动十二月的改善幅度：本期 ROA 减去自身前期 ROA，构成二阶预期差。"),
    ("Q1_scale_fcf",
     "zscore(divide(fnd17_fcfmtt,fnd17_atmtt))",
     "自由现金流对总资产的规模无关化产出率：绝对金额除以内生规模锚，跨行业可比。"),
    ("Q3_anomaly_mgn",
     "zscore(ts_av_diff(fnd17_ngmpnmtt,60))",
     "净利率相对自身 60 日滚动均值的异常偏离，赌机构对利润率跳变的反应过度。"),
    ("Q7_group_rel",
     "group_zscore(ts_delta(fnd17_qcurratio,60),sector)",
     "流动比率同比变化在行业组内的相对位置：截面相对性但顶层零均值。"),
    ("Q8_surprise_rev",
     "ts_zscore(subtract(fnd17_ttmrev,fnd17_ptmrev),252)",
     "TTM 收入相对上一滚动十二月的差额，再用 252 日时序标准化得到异常惊喜幅度。"),
    ("Q4_interaction",
     "zscore(multiply(ts_rank(fnd17_qrev,60),rank(fnd17_qcurratio)))",
     "季度收入动能与流动性水平的交互：权重项 rank 输出严格恒正，满足公理一。"),
    ("Q5_structure",
     "zscore(divide(subtract(fnd17_fcfmtt,fnd17_atmtt),divide(fnd17_ttmopmgn,100)))",
     "现金流产出率与经营利润率的结构差：两条无量纲比率相减，反映利润的现金含量。"),
    ("Q6_accumulation",
     "zscore(ts_mean(ts_av_diff(fnd17_tcpaorq,20),60))",
     "季度年化 ROA 偏离自身 20 日基线的程度，再用 60 日线性记忆累积衰减。"),
]


def build():
    profile = json.load(open(os.path.join(HERE, "..", "..", "knowledge_base",
                                          "fields", "USA", "fundamental17.json"),
                             encoding="utf-8"))["fields"]
    known = [f for f in profile if not profile[f]["semantic_role"].startswith("INVALID")]
    items = []
    for i, (name, expr, reason) in enumerate(SAMPLES):
        items.append({
            "expression": expr,
            "optimize_reason": reason,
            "seed_id": name,
            "question_type": name.split("_")[0],
            "counterparty": "流动性提供方与风格追逐型被动资金",
            "variant_type": "DRYRUN",
        })
    batch = {
        "batch_name": "aegis_fnd17_DRYRUN",
        "dataset": "fundamental17",
        "region": REGION, "universe": UNIVERSE, "delay": DELAY,
        "category": CATEGORY,
        "settings": {"neutralization": NEUTRALIZATION, "decay": 8, "truncation": 0.08,
                     "pasteurization": "ON", "unit_handling": "VERIFY", "nan_handling": "ON",
                     "max_trade": "OFF", "language": "FASTEXPR"},
        "slot_count": len(items),
        "known_fields": known,
        "items": items,
    }
    p = os.path.join(HERE, "batch_DRYRUN.json")
    json.dump(batch, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p, batch


def main():
    p, batch = build()
    print(f"[DRYRUN] built {p}")
    # Gate3 会把指纹写进共享库 alpha_fingerprints.db —— 干跑用的是**从未回测过的合成表达式**，
    # 留着会污染跨批次骨架熔断计数（>=4 次即熔断），所以干跑结束后必须清除。
    db_path = os.path.join(HERE, "..", "..", "quant_framework", "alphas_record.db")
    cleanup = []
    if os.path.exists(db_path):
        import sqlite3
        cc = sqlite3.connect(db_path)
        cur = cc.cursor()
        for it in batch["items"]:
            h = hashlib.md5(json.dumps({
                "expression": "".join(it["expression"].split()).lower(),
                "region": REGION, "universe": UNIVERSE, "delay": DELAY,
                "neutralization": NEUTRALIZATION}, sort_keys=True).encode()).hexdigest()
            cleanup.append(h)
        cc.close()

    try:
        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=p,
            expressions_data=batch["items"],
            known_fields=batch["known_fields"],
            category=CATEGORY,
            region=REGION, universe=UNIVERSE, delay=DELAY,
            neutralization=NEUTRALIZATION,
            ledger_path=os.path.join(HERE, "exploration_ledger.json"),
        )
        print("\n[DRYRUN] ✅ ALL GATES PASSED — batch format is engine-compatible")
        for i, e in enumerate(corrected):
            print(f"  slot {i+1}: {e}")
        rc = 0
    except Exception as e:
        print(f"\n[DRYRUN] ❌ GATE FAILURE: {type(e).__name__}")
        print(e)
        rc = 1

    # ---- 清理干跑污染的指纹（无论成败都要清）
    if cleanup:
        import sqlite3
        cc = sqlite3.connect(db_path)
        cur = cc.cursor()
        n = 0
        for h in cleanup:
            cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash=?", (h,))
            n += cur.rowcount
        cc.commit()
        cc.close()
        print(f"[DRYRUN] cleanup: removed {n} synthetic fingerprint rows from {db_path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
