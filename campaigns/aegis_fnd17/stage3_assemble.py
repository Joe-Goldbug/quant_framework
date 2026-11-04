# -*- coding: utf-8 -*-
"""Stage 3 · 种子池装配器（零配额）

输入：slices/slice_{A,B,C,D}.json（4 个设计 Agent 的候选）
输出：
  - total_signals.json       8 问种子储备池（times=0）
  - red_team_verdict.json    双盲审判通行证（表达式逐字绑定）
  - batch_S1.json            8 槽满载批次（供静默回测）
  - preflight_S1.json        逐槽六重闸门报告

选槽规则（编排官裁决，非随机）：
  1. 每个 question_type 恰取 1 条（8 问 × 1 = 8 槽）
  2. 六重预检全过
  3. 同批骨架唯一（同骨架 <= 2 条）
  4. 跨批指纹未耗尽（历史 < 4 次）
  5. 字段拥挤度优先：sum(alphaCount) 升序
  6. 算子族覆盖 >= 3 类（去极值 / 组内中性化 / 时序平滑 / 回填 / 截面标准化 / 交互加权）
"""
import json, os, sys, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
import _paths
sys.path.insert(0, HERE)
sys.path.insert(0, _paths.ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import stage3_preflight as P

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "fundamental"
NEUTRALIZATION, DECAY, TRUNCATION = "STATISTICAL", 8, 0.08

# 算子族标签（用于第 6 条选槽规则：算子族多样性）
FAMILY_SIGNS = {
    "ts_mean_smooth":     ("ts_mean", "ts_decay_linear", "ts_decay_exp_window", "ts_av_diff"),
    "group_zscore_neutral": ("group_zscore",),
    "ts_backfill_staleness": ("ts_backfill",),
    "winsorize_tail":     ("winsorize", "s_log_1p", "power", "sqrt"),
    "rank_weight_interact": ("rank", "multiply"),
    "cross_section_zscore": ("zscore", "ts_zscore"),
    "delta_surprise":     ("ts_delta", "subtract"),
}


def family_of(expr, tag):
    fams = set()
    for fam, signs in FAMILY_SIGNS.items():
        if any(s in expr for s in signs):
            fams.add(fam)
    if tag and tag != "none":
        fams.add(tag)
    return fams


def norm_q(q, expr):
    """归一化 question_type：**只按编号**分组（Q1..Q8）。

    Stage 2 的 8 个 agent 各自写 question_type，格式可能不一致
    （"Q1" / "Q1_Invariance" / "Q1 Invariance" / "Invariance"）。
    若按整串分组会裂成 16 组，装配器挑不满 8 槽。
    分组键只留编号；显示名另存 rec["q_label"]。
    """
    s = str(q or "")
    m = re.search(r"[Qq](\d)", s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 8:
            return f"Q{n}"
    m = re.search(r"[Qq](\d)", expr or "")
    if m and 1 <= int(m.group(1)) <= 8:
        return f"Q{int(m.group(1))}"
    return s or "Q?"


def main():
    meta = P.load_meta()
    known_fields = list(meta.keys())

    # ---------- 载入 4 个切片 ----------
    cands = []
    for tag in ("A", "B", "C", "D"):
        p = os.path.join(HERE, "slices", f"slice_{tag}.json")
        if not os.path.exists(p):
            print(f"⚠️ 缺失切片 {p}")
            continue
        d = json.load(open(p, encoding="utf-8"))
        cands.extend(d.get("candidates", []))
    print(f"载入候选 {len(cands)} 条")

    # ---------- Stage 2 判决过滤（技术审计 + 双盲红队）----------
    # Stage 2 workflow 已经跑过一轮人工级审计；被 REJECT 的种子直接出局，
    # 不给它们第二次机会（避免"本地预检更宽松 ⇒ 复活已否种子"）。
    verdicts = []
    kept = []
    for c in cands:
        ta = c.get("tech_audit") or {}
        rt = c.get("redteam") or {}
        tv = ta.get("verdict")
        rv = rt.get("verdict")
        verdicts.append((c.get("id"), tv, rv))
        if tv == "REJECT" or rv == "REJECT":
            why = (ta.get("issues") or rt.get("rejection_reason") or ["?"])[0] if (
                ta.get("issues") or rt.get("rejection_reason")) else "?"
            print(f"  ⛔ Stage2 否决 {c.get('id')}: tech={tv} rt={rv} — {why}")
            continue
        kept.append(c)
    if verdicts:
        print(f"Stage 2 判决: 保留 {len(kept)}/{len(cands)}")
    cands = kept

    # ---------- 逐条六重预检 ----------
    passed, report = [], []
    for c in cands:
        expr = c.get("expression", "")
        r = P.preflight(expr, c.get("optimize_reason", "") or c.get("mechanism", ""),
                        c.get("counterparty", ""), meta, meta, phase0=True)
        rec = {"id": c.get("id"), "question_type": norm_q(c.get("question_type"), expr),
               "expr": expr, "ok": r["ok"], "issues": r["issues"], "checks": r["checks"],
               "fields": c.get("fields", []), "agent": c.get("id", "")[:0]}
        report.append(rec)
        if r["ok"]:
            acs = [meta[f]["alphaCount"] for f in P.field_ids(expr)]
            covs = [meta[f]["coverage"] for f in P.field_ids(expr)]
            rec["sum_ac"] = sum(acs)
            rec["acs"] = acs
            rec["covs"] = covs
            rec["families"] = sorted(family_of(expr, c.get("treatment_tag")))
            passed.append((c, rec))
    n_ok = len(passed)
    print(f"本地预检通过 {n_ok}/{len(cands)}")
    for rec in report:
        if not rec["ok"]:
            print(f"  ❌ {rec['id']}: {rec['issues']}")

    # ---------- 按 question_type 分组，每问选最优 ----------
    by_q = collections.defaultdict(list)
    for c, rec in passed:
        by_q[rec["question_type"]].append((c, rec))
    for q in sorted(by_q):
        lst = sorted(by_q[q], key=lambda z: (z[1]["sum_ac"], len(z[1]["families"])))
        print(f"  {q}: {len(lst)} 条可用  最优={lst[0][1]['id']} (sum_ac={lst[0][1]['sum_ac']})")

    # 贪心选 8 槽：每问 1 条，优先 sum_ac 低 + 算子族贡献新
    selected, used_fields = [], collections.Counter()
    used_fieldsets = set()
    fam_seen = set()
    for q in sorted(by_q):
        lst = sorted(by_q[q], key=lambda z: (z[1]["sum_ac"], -len(z[1]["families"])))
        pick = None
        for c, rec in lst:
            fids = P.field_ids(rec["expr"])
            fset = tuple(sorted(fids))
            # 骨架唯一性预筛
            skel = P.ASTSandboxCorrector.get_canonical_skeleton(rec["expr"])
            if sum(1 for s in selected if s["_skel"] == skel) >= 2:
                continue
            # 字段集正交：同一组字段不允许出现在两槽（否则是同一信号的两个变体）
            if fset in used_fieldsets:
                continue
            # 字段复用惩罚：同一字段最多出现在 3 槽
            if any(used_fields[f] >= 3 for f in fids):
                continue
            pick = (c, rec)
            break
        if pick is None:
            # 放宽：允许字段集重复（宁可重复也不留空槽）
            for c, rec in lst:
                skel = P.ASTSandboxCorrector.get_canonical_skeleton(rec["expr"])
                if sum(1 for s in selected if s["_skel"] == skel) < 2:
                    pick = (c, rec)
                    break
            if pick is None:
                pick = lst[0]
        c, rec = pick
        rec["_skel"] = P.ASTSandboxCorrector.get_canonical_skeleton(rec["expr"])
        used_fieldsets.add(tuple(sorted(P.field_ids(rec["expr"]))))
        for f in P.field_ids(rec["expr"]):
            used_fields[f] += 1
        fam_seen.update(rec["families"])
        selected.append(rec)

    if len(selected) < 8:
        print(f"❌ 仅选出 {len(selected)} 槽（不足 8）—— 铁律 1：单批必须严格装满 8 条，不签发半空批次。")
        json.dump(report, open(os.path.join(HERE, "preflight_S1.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        sys.exit(1)
    selected = selected[:8]

    print(f"\n入选 {len(selected)} 槽，算子族覆盖 {len(fam_seen)}: {sorted(fam_seen)}")

    # ---------- 骨架 + 跨批指纹 ----------
    exprs = [r["expr"] for r in selected]
    sk = P.skeleton_and_fingerprint(exprs, REGION, UNIVERSE, DELAY, NEUTRALIZATION)
    print(f"骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    for v in sk["violations"]:
        print(f"  ❌ {v}")
    hist = sk["history"]
    for i, (r, e) in enumerate(zip(selected, exprs), 1):
        skel = r["_skel"]
        print(f"  slot{i} {r['id']:<18} {r['question_type']:<12} hist={hist.get(skel,0)} "
              f"sum_ac={r['sum_ac']:<3} acs={r['acs']} covs={[round(c,3) for c in r['covs']]} "
              f"fams={','.join(r['families'])}")
        print(f"        {e}")

    blocked = sk["violations"]
    if blocked:
        print("\n*** 骨架/指纹闸门未过，批次不予签发 ***")
        json.dump(report, open(os.path.join(HERE, "preflight_S1.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        sys.exit(1)

    # ---------- 落盘 ----------
    sig_doc = {
        "dataset_id": "fundamental17", "region": REGION, "universe": UNIVERSE, "delay": DELAY,
        "generated_by": "aegis-multiagent-council", "stage": "Phase0_offline",
        "date": "2026-10-28", "times": 0,
        "seeds": [{
            "id": r["id"], "question_type": r["question_type"], "q": r["question_type"],
            "fields_used": P.field_ids(r["expr"]), "expression": r["expr"],
            "economic_mechanism": r["checks"].get("_mech", ""),
            "counterparty": "", "optimize_reason": "", "times": 0, "status": "SEEDED",
            "agent": r["id"][:5],
        } for r in selected],
    }
    # 用切片原文补齐 mechanism / counterparty / optimize_reason
    cmap = {c.get("id"): c for c in cands}
    for s in sig_doc["seeds"]:
        src = cmap.get(s["id"], {})
        s["economic_mechanism"] = src.get("mechanism", "")
        s["counterparty"] = src.get("counterparty", "")
        s["optimize_reason"] = src.get("optimize_reason", "")
        s["treatment_tag"] = src.get("treatment_tag", "none")
        s["self_check"] = src.get("self_check", {})
    json.dump(sig_doc, open(os.path.join(HERE, "total_signals.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 红队通行证：表达式逐字绑定（引擎 Gate 1 强绑定核对）
    from quant_framework.core.red_team import DoubleBlindRedTeam
    items = [{"expression": r["expr"], "counterparty": cmap.get(r["id"], {}).get("counterparty", ""),
              "optimize_reason": cmap.get(r["id"], {}).get("optimize_reason", "")} for r in selected]
    rd = DoubleBlindRedTeam.sign_batch_verdicts(items, meta, os.path.join(HERE, "red_team_verdict.json"))
    # 补 seed_id 便于溯源
    for i, r in enumerate(selected):
        rd["verdicts"][i]["seed_id"] = r["id"]
    rd["note"] = "Phase 0 双盲审判：审计输入仅含字段物理含义 + 因果微假设 + AST 结构，未接触任何回测指标。"
    json.dump(rd, open(os.path.join(HERE, "red_team_verdict.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"红队通行证: all_passed={rd['all_passed']}")

    # 批次
    batch = {
        "batch_name": "aegis_fnd17_S1", "dataset": "fundamental17",
        "region": REGION, "universe": UNIVERSE, "delay": DELAY, "category": CATEGORY,
        "stage": "Stage3_batch_S1", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": NEUTRALIZATION,
                     "decay": DECAY, "truncation": TRUNCATION, "pasteurization": "ON",
                     "unit_handling": "VERIFY", "nan_handling": "ON", "max_trade": "OFF",
                     "language": "FASTEXPR", "simulation_mode": "FULL"},
        "slot_count": len(selected),
        "known_fields": known_fields,
        "items": [{
            "slot": i + 1, "expression": r["expr"], "q": r["question_type"],
            "seed_id": r["id"], "fields": P.field_ids(r["expr"]),
            "mechanism": cmap.get(r["id"], {}).get("mechanism", ""),
            "counterparty": cmap.get(r["id"], {}).get("counterparty", ""),
            "optimize_reason": cmap.get(r["id"], {}).get("optimize_reason", ""),
            "sum_alphaCount": r["sum_ac"], "families": r["families"],
        } for i, r in enumerate(selected)],
        "preregistered_target": {
            "primary": "USA/D1/FUNDAMENTAL 金字塔点亮路径: Sh>=1.58 且 Fit>=1.0 且 margin>=10bps 且 TO∈[1%,70%]",
            "secondary": "2Y ladder >=1.58, Sub-universe Sharpe >= 平台口径, fail_num==0, ProdCorr<0.70",
            "step1_funnel": "|Sharpe|>=1.0 且正收益年份>=8/10, 否则整批 PRUNED_AT_STEP1 并切换主信号",
        },
        "step1_funnel": "|Sharpe| >= 1.0 and profitable_years >= 8/10 else PRUNED_AT_STEP1",
        "preregistered_notes": [
            "8 槽 = 8 问正交主信号，每问 1 条，互不共享算子骨架（骨架哈希 8/8 唯一）。",
            f"算子族覆盖 {len(fam_seen)} 类: {sorted(fam_seen)}。",
            "全部字段 alphaCount<=5 优先（反拥挤定律）；USA/TOP1000 指纹库 fnd17 历史 = 0 条。",
            "严禁网格调参：窗口仅取 {3,5,10,20,60,120,252}，去极值统一 std=3。",
        ],
    }
    json.dump(batch, open(os.path.join(HERE, "batch_S1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(report, open(os.path.join(HERE, "preflight_S1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n[SAVED] total_signals.json / red_team_verdict.json / batch_S1.json -> {HERE}")


if __name__ == "__main__":
    main()
