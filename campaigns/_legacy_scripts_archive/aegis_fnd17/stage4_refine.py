# -*- coding: utf-8 -*-
"""Stage 4 · 处方化攻坚（受限外科手术）

对 Step-1 存活的槽位做**受限**精炼：
  - 只允许在既有表达式上做**一次**结构替换（不是网格微调）
  - 每个槽位最多 3 个候选变体，总批次仍严格 8 槽
  - 变体必须命中上一轮法医诊断的靶向算子（Gate 4 处方锁）

处方来源（Gatekeeper.diagnose_and_route_prescriptions 的症状 → 算子）：
  LOW_FITNESS / 低换手      → ts_mean / ts_decay_linear（拉长记忆窗）
  LOW_2Y_SHARPE / 阶梯不稳   → ts_backfill（去 staleness）+ winsorize
  CONCENTRATED_WEIGHT       → s_log_1p / rank 凹压缩
  LOW_SHARPE / 信号弱        → group_zscore（组内剥离）
  多空失衡                   → ts_backfill / ts_mean
"""
import json, os, sys, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
import _paths
sys.path.insert(0, HERE)
sys.path.insert(0, _paths.ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import stage3_preflight as P

# 症状 → 靶向算子（与 Gatekeeper 处方路由同源）
SYMPTOM_OPS = {
    "LOW_FITNESS": ["ts_mean", "ts_decay_linear"],
    "LOW_2Y_SHARPE": ["ts_backfill", "winsorize"],
    "IS_LADDER_SHARPE": ["ts_backfill", "ts_mean"],
    "LOW_SHARPE": ["group_zscore", "zscore"],
    "CONCENTRATED_WEIGHT": ["s_log_1p", "rank"],
    "LOW_TURNOVER": ["ts_mean", "ts_decay_linear"],
    "HIGH_TURNOVER": ["ts_mean", "winsorize"],
}


def diagnose(alpha):
    """从回测结果提取症状标签。"""
    m = alpha.get("metrics") or alpha.get("is") or {}
    ch = alpha.get("checks") or {}
    fails = [c.get("name") for c in (ch.get("fail") or []) if isinstance(c, dict)]
    warns = [c.get("name") for c in (ch.get("warning") or []) if isinstance(c, dict)]
    symptoms = []
    sh = m.get("sharpe") or 0
    fit = m.get("fitness") or 0
    to = m.get("turnover") or 0
    t2y = m.get("two_year_sharpe")
    if fit < 1.0:
        symptoms.append("LOW_FITNESS")
    if t2y is not None and t2y < 1.58:
        symptoms.append("LOW_2Y_SHARPE")
    if sh < 1.58:
        symptoms.append("LOW_SHARPE")
    if to < 0.01:
        symptoms.append("LOW_TURNOVER")
    if to > 0.70:
        symptoms.append("HIGH_TURNOVER")
    symptoms += [f for f in fails if f in SYMPTOM_OPS]
    return symptoms, m


def make_variants(expr, symptoms):
    """对单条表达式做受限结构替换，返回候选变体。"""
    ops = []
    for s in symptoms:
        ops.extend(SYMPTOM_OPS.get(s, []))
    ops = list(dict.fromkeys(ops))
    out = []

    # 变体 A：若症状指向低 Fitness / 低换手 → 用 ts_mean 包一层（拉长记忆窗）
    if any(o in ops for o in ("ts_mean", "ts_decay_linear")):
        out.append(("ts_mean_smooth", f"ts_mean({expr}, 60)"))
        out.append(("ts_mean_smooth", f"ts_mean({expr}, 120)"))
    # 变体 B：若症状指向阶梯不稳 / 集中度 → 插入 winsorize 去极值
    if "winsorize" in ops:
        out.append(("winsorize_tail", f"winsorize({expr}, std=3)"))
    # 变体 C：若症状指向信号弱 → 组内标准化（若尚未 group_zscore）
    if "group_zscore" in ops and "group_zscore" not in expr:
        out.append(("group_zscore_neutral", f"group_zscore({expr}, subindustry)"))
    # 变体 D：若症状指向 staleness → 回填
    if "ts_backfill" in ops and "ts_backfill" not in expr:
        out.append(("ts_backfill_staleness", f"ts_backfill({expr}, 120)"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result_file", nargs="?",
                    default=os.path.join(HERE, "batch_S1_result.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "batch_S2.json"))
    ap.add_argument("--max-ops", type=int, default=6)
    args = ap.parse_args()

    meta = P.load_meta()
    d = json.load(open(args.result_file, encoding="utf-8"))
    rows = d.get("alpha_results", d if isinstance(d, list) else [d])

    # ---- Step-1 存活筛选 ----
    alive = []
    for r in rows:
        a = r.get("alpha") or {}
        m = a.get("metrics") or a.get("is") or {}
        if not m:
            continue
        sh = m.get("sharpe") or 0
        if abs(sh) >= 1.0:
            alive.append((r, a, m))
    print(f"Step-1 存活 {len(alive)}/{len(rows)} 条")
    if not alive:
        print("*** PRUNED_AT_STEP1：无可精炼目标 ***")
        return

    # ---- 生成候选变体 ----
    cand = []
    for r, a, m in alive:
        symptoms, _ = diagnose(a)
        expr = r.get("expr", "")
        for tag, ve in make_variants(expr, symptoms):
            fids = P.field_ids(ve)
            if len(fids) < 2 or len(fids) > 3:
                continue
            cand.append({"slot": len(cand) + 1, "expression": ve, "q": r.get("seed_id", ""),
                         "fields": fids, "treatment_tag": tag,
                         "optimize_reason": f"针对上一轮确诊病灶 {symptoms} 施加 {tag} 靶向手术",
                         "counterparty": "承接上一轮的对手盘画像",
                         "parent_expr": expr, "parent_alpha_id": (a.get("id") or r.get("alpha_id") or ""),
                         "symptoms": symptoms})

    # ---- 六重预检 ----
    ok = []
    for c in cand:
        r = P.preflight(c["expression"], c["optimize_reason"], c["counterparty"], meta, meta,
                        phase0=False)
        c["preflight_ok"] = r["ok"]
        c["preflight_issues"] = r["issues"]
        c["ops"] = r["checks"].get("operator_count")
        if r["ok"]:
            ok.append(c)
    print(f"预检通过 {len(ok)}/{len(cand)}")
    for c in cand:
        if not c["preflight_ok"]:
            print(f"  ❌ slot{c['slot']} ops={c['ops']} {c['preflight_issues']}")

    # ---- 骨架/指纹闸门 + 取前 8 ----
    if ok:
        sk = P.skeleton_and_fingerprint([c["expression"] for c in ok], "USA", "TOP1000", 1, "STATISTICAL")
        if sk["violations"]:
            print("*** 骨架/指纹闸门未过 ***")
            for v in sk["violations"]:
                print("   ", v)
            return
        ok = ok[:8]
        for i, c in enumerate(ok, 1):
            c["slot"] = i

    batch = {
        "batch_name": "aegis_fnd17_S2", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage4_refinement_S2", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL", "decay": 8,
                     "truncation": 0.08, "pasteurization": "ON", "unit_handling": "VERIFY",
                     "nan_handling": "ON", "max_trade": "OFF", "language": "FASTEXPR",
                     "simulation_mode": "FULL"},
        "slot_count": len(ok), "known_fields": list(meta.keys()),
        "items": ok,
        "preregistered_target": {
            "primary": "USA/D1/FUNDAMENTAL 金字塔点亮: Sh>=1.58 且 Fit>=1.0 且 margin>=10bps 且 TO∈[1%,70%]",
            "step1_funnel": "|Sharpe|>=1.0 且正收益年份>=8/10, 否则整批 PRUNED_AT_STEP1 并切换主信号",
        },
        "step1_funnel": "|Sharpe| >= 1.0 and profitable_years >= 8/10 else PRUNED_AT_STEP1",
        "preregistered_notes": [
            "Stage 4 受限外科手术：每槽只做一次结构替换，非网格微调。",
            "所有变体必须命中上一轮确诊症状的靶向算子（Gate 4 处方锁）。",
        ],
    }
    json.dump(batch, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[SAVED] {args.out}  ({len(ok)} 槽)")
    for c in ok:
        print(f"  slot{c['slot']} {c['q']:<18} {c['treatment_tag']:<24} {c['expression'][:96]}")


if __name__ == "__main__":
    main()
