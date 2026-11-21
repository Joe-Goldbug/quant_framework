# -*- coding: utf-8 -*-
"""AEGIS Stage 5: Gatekeeper 诚实裁决 + 知识沉淀 (严禁任何提交动作)"""
import json, os, sys, datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KB_DIR = os.path.join(ROOT, "knowledge_base")

# ---------- 1. 汇总全部批次的实测结果 ----------
BATCHES = ["batch_R1_result.json", "batch_R3_result.json", "batch_R4_result.json",
           "batch_R5_result.json"]
all_rows = []
for b in BATCHES:
    p = os.path.join(HERE, b)
    if not os.path.exists(p):
        continue
    for r in json.load(open(p, encoding="utf-8"))["alpha_results"]:
        m = r.get("metrics", {}) or {}
        ch = r.get("checks", {}) or {}
        all_rows.append({
            "batch": b.replace("_result.json", ""),
            "alpha_id": r.get("alpha_id") or r.get("id"),
            "expression": r.get("code"),
            "sharpe": m.get("sharpe"), "two_year": m.get("two_year_sharpe"),
            "fitness": m.get("fitness"), "margin_bps": round((m.get("margin") or 0) * 10000, 2),
            "turnover_pct": round((m.get("turnover") or 0) * 100, 2),
            "sub_universe": m.get("sub_universe_sharpe"),
            "cluster": next((c.get("value") for c in (ch.get("warning") or [])
                             if c.get("name") == "CLUSTER_TEST"), None),
            "long_short": f"{m.get('longCount')}:{m.get('shortCount')}",
            "returns_pct": round((m.get("returns") or 0) * 100, 2),
            "status": r.get("status"),
            "fails": [c.get("name") for c in (ch.get("fail") or [])],
            "warnings": [c.get("name") for c in (ch.get("warning") or [])],
        })

pos_years = {}
py_path = os.path.join(HERE, "positive_years.json")
if os.path.exists(py_path):
    py = json.load(open(py_path, encoding="utf-8"))
    pos_years = {k: f"{v['positive']}/{v['total']}" for k, v in py.items()}

for r in all_rows:
    r["positive_years"] = pos_years.get(r["alpha_id"], "未测")

# ---------- 2. Gatekeeper 终极裁决 ----------
def verdict(r):
    f = []
    if (r["sharpe"] or 0) < 1.58:
        f.append(f"Sharpe {r['sharpe']:.2f} < 1.58")
    if (r["fitness"] or 0) < 1.00:
        f.append(f"Fitness {r['fitness']:.2f} < 1.00")
    if (r["margin_bps"] or 0) < 10.0:
        f.append(f"Margin {r['margin_bps']:.2f} bps < 10.0")
    if (r["turnover_pct"] or 0) > 50.0:
        f.append(f"换手 {r['turnover_pct']:.1f}% > 50%")
    if (r["turnover_pct"] or 0) < 5.0:
        f.append(f"换手 {r['turnover_pct']:.1f}% < 5%")
    if r["fails"]:
        f.append("平台 fail: " + ",".join(r["fails"]))
    f.append("ProdCorr/SelfCorr: PENDING (需提交后方可计算，本战役严禁提交)")
    return f

for r in all_rows:
    r["gatekeeper_fails"] = verdict(r)
    r["submittable"] = False

ranked = sorted(all_rows, key=lambda x: -(x["sharpe"] or -9))
json.dump(ranked, open(os.path.join(HERE, "stage5_full_audit.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print("=" * 100)
print("AEGIS 终极生产准入裁决：全部候选 0 条达标 (严禁提交，仅本地标记待研究员人工终审)")
print("=" * 100)
for r in ranked[:6]:
    print(f"[{r['alpha_id']}] Sharpe={r['sharpe']} Fit={r['fitness']} Margin={r['margin_bps']}bps "
          f"TO={r['turnover_pct']}% SubU={r['sub_universe']} L:S={r['long_short']} 正收益年={r['positive_years']}")
    print(f"    {r['expression']}")
    print(f"    未达标项: {'; '.join(r['gatekeeper_fails'][:5])}")
print(f"\n累计实测表达式: {len(all_rows)} 条 | 提交调用次数: 0")

# ---------- 3. 证伪知识沉淀 ----------
vault_path = os.path.join(KB_DIR, "falsified_vault.json")
vault = json.load(open(vault_path, encoding="utf-8")) if os.path.exists(vault_path) else []
existing = {v.get("id") for v in vault}
new_rules = [
    {
        "id": "FALS_F90_001",
        "target": "dataset:fundamental90 / type:VECTOR",
        "rule": "fundamental90 的 133 个字段物理类型是 VECTOR(event input)。ts_zscore / ts_delta "
                "等 ts_* 算子直接吃裸字段会被平台拒绝：'Operator ts_zscore does not support event inputs'。"
                "必须先用 vec_avg / vec_sum 等 vec_* 降维。平台 datafields 元数据 type 字段即可预判，无需试探。",
        "evidence": "2026-10-28 USA/TOP1000/d1 实测: ts_zscore(fnd90_game_noa,252) 全批 8 条 ERROR；"
                    "ts_zscore(vec_avg(fnd90_game_noa),252) 回测成功 (alpha ZYQGwX9n)。",
    },
    {
        "id": "FALS_F90_002",
        "target": "operator:外层时序平滑 (稀疏事件序列死重)",
        "rule": "在稀疏事件型 VECTOR 数据集中，若不在因果合成【最外层】施加 ts_mean / ts_backfill，"
                "持仓会在 NaN 进出之间反复重排，制造 42~52% 的伪换手并吃光 Margin，"
                "同时诱发 CONCENTRATED_WEIGHT。处方：平滑一律外移。",
        "evidence": "R3/R4 对照: -rank(add(vec_avg(A),vec_avg(B))) 换手 42.5% / Margin -0.18bps / CW FAIL；"
                    "-rank(add(ts_mean(vec_avg(A),20),ts_mean(vec_avg(B),20))) 换手 2.4% / Margin 3.26bps / 无 CW。",
    },
    {
        "id": "FALS_F90_003",
        "target": "backtest settings (USA/TOP1000/d1)",
        "rule": "回测物理条件必须先对齐账户已验证的生产设置再判信号生死。本账户 70 条已提交 alpha 中 "
                "SUBINDUSTRY 34 条、decay=4 共 25 条、truncation=0.08 共 40 条；"
                "用 NONE/decay0/0.025 会人为制造 43~52% 换手与 0.x bps Margin 的假死。",
        "evidence": "同一批表达式由 NONE/0/0.025 改 SUBINDUSTRY/4/0.08 后，最优槽位 Sharpe 由 -0.00 升至 0.46。",
    },
    {
        "id": "FALS_F90_004",
        "target": "dataset:fundamental90 信号上限",
        "rule": "fundamental90 在 USA/TOP1000/d1 的一阶与二阶构造实测天花板约 Sharpe 0.65 "
                "(10/10 年正收益但振幅仅 1.98%/年)。Margin 与换手存在数学耦合 "
                "margin_bps ≈ returns_bps / (504 × turnover_frac)，"
                "在 AEGIS 换手下限 5% 下要求年化收益 >= 2.52% 才能同时满足 Margin >= 10bps，"
                "而 Sharpe 1.58 要求 ~4.8%/年，故该数据集在此宇宙下不具备提交级可行性。",
        "evidence": "5 批 40 条实测 (R1/R3/R4/R5 + 种子筛选)，最高 Sharpe 0.65 (ZYQGlpXQ)，"
                    "最高 Margin 12.99bps (MPYm8pdr, Sharpe 仅 0.25)。",
    },
]
added = 0
for r in new_rules:
    if r["id"] not in existing:
        vault.append(r); added += 1
json.dump(vault, open(vault_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"证伪知识库新增 {added} 条 -> falsified_vault.json (共 {len(vault)} 条)")

# ---------- 4. 算子范式沉淀 (剔除字段名，抽象化) ----------
paradigm = {
    "region": "USA", "universe": "TOP1000", "delay": 1, "dataset_family": "fundamental (VECTOR 事件型)",
    "distilled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "paradigms": [
        {
            "name": "类型降维前置范式",
            "pattern": "ts_*(vec_avg(字段), 窗口)",
            "gain": "从'平台拒绝执行'到'回测可跑'，是该类数据集的唯一入场券",
            "note": "vec_* 属类型强制转换，不应计入数学算子预算。",
        },
        {
            "name": "外层时序平滑消死重范式",
            "pattern": "ts_mean(<因果合成>, 20)",
            "gain": "换手 42.5% -> 3.7%，Margin -0.18bps -> 10.24bps，CONCENTRATED_WEIGHT 由 FAIL 转为 PASS",
            "note": "必须置于最外层；置于内层(逐腿平滑)效果反转为负 (R5 Slot5 Sharpe -0.13)。",
        },
        {
            "name": "去中枢后做减法的符号守恒范式",
            "pattern": "subtract(ts_zscore(A, 252), ts_zscore(B, 252))",
            "gain": "避开双有符号变量相乘的伪因果；本战役全部正 Sharpe 候选均出自该结构",
            "note": "严禁裸乘；严禁对稀疏 [0,1] 字段减 0.5。",
        },
        {
            "name": "截面排序拉平持仓范式",
            "pattern": "rank(<外层平滑后的合成>)",
            "gain": "在保持 Sharpe 0.60 的同时把 Sub-universe Sharpe 抬到 0.76 (本批最高)",
            "note": "对 CONCENTRATED_WEIGHT 有效，但对 Fitness 提升有限。",
        },
    ],
    "counter_paradigms": [
        {"name": "rank 直接加总", "pattern": "add(rank(A), rank(B))",
         "verdict": "被 AST 量纲编译器物理封杀 (无量纲排序加总属数学拼凑)"},
        {"name": "裸 z-score 合成不加平滑", "pattern": "add(ts_zscore(A), ts_zscore(B))",
         "verdict": "换手 44.6%，Margin 0.50bps，CW FAIL"},
        {"name": "逐腿平滑替代外层平滑", "pattern": "subtract(group_rank(ts_mean(A,20)), group_rank(ts_mean(B,20)))",
         "verdict": "Sharpe -0.13，优于外层平滑方案的 0.60，证明平滑位置必须外置"},
    ],
}
card_path = os.path.join(KB_DIR, "cards", "fundamental90_operator_paradigm.json")
json.dump(paradigm, open(card_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("算子范式卡片 ->", os.path.relpath(card_path, ROOT))
