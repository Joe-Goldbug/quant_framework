# -*- coding: utf-8 -*-
"""S4 处方：候选池去重 + 六重预检 + 8 槽选取 + 设置档 A/B 成包。

═══════════════════════════════════════════════════════════════════════════
S4 的两个新杠杆（都由 fnd17 全史挖掘 + S3 配对实验逼出来）
───────────────────────────────────────────────────────────────────────────
杠杆 1 —— **未测设置格：decay=0 + STATISTICAL + nan=OFF**
  S3 只测了两格：{decay0, MARKET, nanOFF} 与 {decay8, STATISTICAL, nanON}。
  配对结果（同 8 条表达式）：
      EUR 档   (decay0/MARKET/nanOFF)     Sh 均值 0.59 | TO 2.06% | Ret 3.66% | Mgn 33.3bp
      战役档   (decay8/STATISTICAL/nanON) Sh 均值 0.88 | TO 6.02% | Ret 2.25% | Mgn  7.8bp
  ⇒ STATISTICAL 带来 +0.29 Sharpe，但 decay8/nanON 把 Ret 砍掉 39% ⇒ Margin 塌到 7.8bp（<10bp 底线）
  ⇒ **decay=0 + STATISTICAL + nan=OFF 这一格从未测过**：若 STAT 的 Sharpe 增益能与 decay0 的
    低换手/高 Ret 共存，就是唯一能同时抬 Sharpe 与 Margin 的组合。

杠杆 2 —— **门禁算术的真实瓶颈是 Ret，不是 Sharpe**
  Mgn_bps = 20·Ret/TO ≥ 10  ⇒  Ret/TO ≥ 0.5
  Fit = Sh·√(Ret/max(TO,0.125)) ≥ 1
  在 TO∈[2%,12.5%] 区间内联立两式：
      TO=2%:  Ret ≥ 5.0%(Sh=1.58)  |  TO=6%:  Ret ≥ 5.0%  |  TO=12.5%: Ret ≥ 5.0%
  ⇒ **要过 Fit≥1.0 且 Margin≥10bp，年化收益必须 ≈5%（Sharpe 1.58 时），与换手基本无关**
  ⇒ EUR 冠军 Ret=6.76% 过；USA 同结构 decay0 仅 Ret=3.77%、战役档 Ret=2.38% ⇒ 都不够
  ⇒ **Ret 是结构属性，必须靠新结构挣，不能靠调设置**
  ⇒ 设置档只作二级优化器（+0.3 Sh / +25bp Mgn），不承担主攻

杠杆 3 —— **两档都固定 decay=0 / nan=OFF**，只让 neutralization 变（单变量对照），
  这样 A/B 结果可干净归因到中性化一项，不与 decay/nan 纠缠。
  （依据：fnd17 全史 51 条中，nan=OFF 档 n=16 均值 Sh 1.37 vs nan=ON 档 n=31 均值 0.45；
    decay=0 档 n=14 均值 1.29 vs decay=8 档 n=30 均值 0.41 —— 本数据集 decay/nan 都偏好 OFF 档）
═══════════════════════════════════════════════════════════════════════════
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

CORR = ASTSandboxCorrector(db_path=_paths.ALPHAS_DB)


def skel(e):
    return CORR.get_canonical_skeleton(e)


def load_pool():
    """汇总所有设计切片 + 编排官自建候选。"""
    pool = []
    slice_files = [
        (os.path.join(HERE, "slices", f), HERE)
        for f in ("slice_A.json", "slice_B.json", "slice_C.json", "slice_D.json",
                  "slice_Q5Q8.json")
    ]
    # Q3/Q4 切片落在 _legacy 目录（housekeeping 后唯一活副本）
    legacy = os.path.join(_paths.ROOT, "_legacy", "aegis_coldstart", "campaign_fnd17",
                          "slices", "slice_B.json")
    slice_files.append((legacy, os.path.join(os.path.dirname(legacy), "..")))
    for path, base in slice_files:
        if not os.path.exists(path):
            print(f"  [缺] {path}")
            continue
        d = json.load(open(path, encoding="utf-8"))
        cs = d.get("candidates") if isinstance(d, dict) else d
        for c in cs:
            if not c.get("expression"):
                continue
            c["_src"] = os.path.basename(path)
            pool.append(c)
    return pool


def tested_skeletons():
    out = []
    for f in ("batch_S1.json", "batch_S2.json", "batch_S3_EUR_ORIG.json",
              "batch_S3_CAMPAIGN.json"):
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for it in d["items"]:
            out.append((f, it.get("seed_id"), it["expression"]))
    return out


def main():
    meta = P.load_meta()
    pool = load_pool()
    tested = tested_skeletons()
    tsk = {}
    for f, sid, e in tested:
        tsk.setdefault(skel(e), []).append(f"{f}:{sid}")
    print(f"候选池 {len(pool)} 条；已测骨架 {len(tsk)} 个")

    # ---- ① 去重：已测骨架 + 池内互相重复 ----
    uniq, seen = [], {}
    dropped = []
    for c in pool:
        e = c["expression"]
        try:
            s = skel(e)
        except Exception as ex:
            dropped.append((c.get("id"), f"骨架解析失败 {ex}"))
            continue
        if s in tsk:
            dropped.append((c.get("id"), f"已测骨架 {tsk[s][0]}"))
            continue
        if s in seen:
            dropped.append((c.get("id"), f"池内重复 {seen[s]}"))
            continue
        seen[s] = c.get("id")
        c["_skel"] = s
        uniq.append(c)
    print(f"\n去重后 {len(uniq)} 条（剔除 {len(dropped)} 条）")
    for cid, why in dropped:
        print(f"  ✗ {cid}: {why}")

    # ---- ② 六重预检 ----
    MECH = "现金创造效率与账面盈利口径在行业内的相对错配：现金叙事显著优于盈利叙事的公司随后跑赢"
    CP = "以账面利润率给公司贴标签、只在会计口径内比较盈利能力的主动基本面基金"
    ok, rej = [], []
    for c in uniq:
        r = P.preflight(c["expression"], c.get("optimize_reason") or MECH,
                        c.get("counterparty") or CP, meta, meta,
                        phase0=False, op_cap_override=6)
        if r["ok"]:
            c["_preflight"] = r["checks"]
            c["_ac"] = sum(meta[f]["alphaCount"] for f in P.field_ids(c["expression"]))
            ok.append(c)
        else:
            rej.append((c.get("id"), r["issues"]))
    print(f"\n预检通过 {len(ok)} / {len(uniq)}")
    for cid, iss in rej:
        print(f"  ✗ {cid}: {iss[:3]}")

    # ---- ③ 选 8 槽：先按 ac 升序（反拥挤），再保证算子族多样性 ----
    def op_family(e):
        cs, _, _ = P.ast_calls(e)
        inner = [c for c in cs if c not in ("ts_backfill", "zscore", "group_zscore")]
        return inner[0] if inner else (cs[0] if cs else "?")

    ok.sort(key=lambda c: (c["_ac"], c.get("id") or ""))
    picked, fam_seen = [], {}
    for pass_no in (0, 1):
        for c in ok:
            if c in picked:
                continue
            fam = op_family(c["expression"])
            cap = 1 if pass_no == 0 else 2
            if fam_seen.get(fam, 0) >= cap:
                continue
            picked.append(c)
            fam_seen[fam] = fam_seen.get(fam, 0) + 1
            if len(picked) == 8:
                break
        if len(picked) == 8:
            break
    # 若多样性约束下不足 8，用 ac 最低的补齐
    for c in ok:
        if len(picked) >= 8:
            break
        if c not in picked:
            picked.append(c)

    print(f"\n=== 选出的 8 槽 ===")
    for i, c in enumerate(picked, 1):
        e = c["expression"]
        print(f"  slot{i} {c.get('id'):<16} [{c.get('question_type')}] ac={c['_ac']} "
              f"ops={c['_preflight']['operator_count']} fields={c['_preflight']['field_count']}")
        print(f"        {e}")

    # ---- ④ 出两个设置档的批次文件 ----
    TIERS = {
        "S4A_STAT_D0": {"neutralization": "STATISTICAL", "decay": 0, "nan_handling": "OFF"},
        "S4B_MKT_D0": {"neutralization": "MARKET", "decay": 0, "nan_handling": "OFF"},
    }
    REASON = (
        "①本批次是 S3 诊断后的换核批次：S3 用 EUR 冠军骨架的 8 条移植式在 USA/TOP1000/d1 只拿到"
        "最高 Sh=1.11，且门禁算术显示瓶颈在年化收益（需 ≈5%，实测 2.4~3.8%），故本批彻底换结构。"
        "②全部字段优先取 alphaCount=0~2 的冷字段（数据集平台 alphaCount=781、userCount=380，"
        "76/289 字段 ac=0），以规避拥挤导致的 ProdCorr 抬升。"
        "③设置档固定 decay=0 / nan=OFF：fnd17 全史 51 条中 decay=0 档均值 Sh 1.29 vs decay=8 档 0.41，"
        "nan=OFF 档 1.37 vs nan=ON 档 0.45；且 decay=0 档 TO≈2%，是唯一能让 Ret/TO≥0.5（Margin≥10bp）"
        "落地的档位。两档只差 neutralization（STATISTICAL vs MARKET），构成单变量对照。"
        "④零外部量价字段，无 fnd17 内嵌量价字段（priceavg*/ev_cur*/ebitda2ev*/nprice* 等），"
        "杜绝跨数据集 PV 污染。全部表达式最外层为零均值构造（zscore / group_zscore / ts_decay_linear），"
        "不产生 [0,1] 单边幻觉。"
    )
    items = []
    for i, c in enumerate(picked, 1):
        fs = P.field_ids(c["expression"])
        items.append({
            "slot": i, "expression": c["expression"], "q": "PROVEN_PORT",
            "seed_id": c.get("id") or f"S4_{i}", "fields": fs,
            "mechanism": c.get("mechanism") or MECH,
            "counterparty": c.get("counterparty") or CP,
            "optimize_reason": REASON,
            "treatment_tag": c.get("treatment_tag") or "none",
            "sum_alphaCount": c["_ac"],
            "field_acs": [meta[f]["alphaCount"] for f in fs],
            "field_covs": [meta[f]["coverage"] for f in fs],
            "operator_count": c["_preflight"]["operator_count"],
            "skeleton": c["_skel"],
            "preflight_ok": True,
        })

    for tname, ts in TIERS.items():
        batch = {
            "batch_name": f"aegis_fnd17_{tname}", "dataset": "fundamental17",
            "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
            "stage": f"Stage4_prescribe_{tname}", "date": "2026-10-28",
            "settings": {"instrumentType": "EQUITY",
                         "neutralization": ts["neutralization"], "decay": ts["decay"],
                         "truncation": 0.08, "pasteurization": "ON",
                         "unit_handling": "VERIFY", "nan_handling": ts["nan_handling"],
                         "max_trade": "OFF", "language": "FASTEXPR", "simulation_mode": "FULL"},
            "slot_count": len(items),
            "known_fields": list(meta.keys()),
            "items": items,
            "preregistered_target": {
                "primary": "S4 换核 + 设置档单变量对照（STATISTICAL vs MARKET，均 decay=0/nan=OFF）",
                "step1_funnel": "诊断批次不剪枝；全 8 条回测留档",
            },
            "preregistered_notes": [
                f"本档设置: {ts}",
                "A/B 两档表达式完全相同 ⇒ 中性化单变量归因。",
                "严禁调用任何提交接口。",
            ],
        }
        out = os.path.join(HERE, f"batch_{tname}.json")
        json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[SAVED] {out}  ({len(items)} 槽)")

    json.dump([{k: v for k, v in c.items() if not k.startswith("_preflight")}
               for c in picked],
              open(os.path.join(HERE, "S4_selected.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
