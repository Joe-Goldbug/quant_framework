# -*- coding: utf-8 -*-
"""Gate1 Wave9-B6' 终扫闭合批 (2026-10-25, 红队两轮终审版).

战役位置: ~272 槽后, B6 原始设计被红队终审砍掉 5/8 槽:
  槽1 PAN  —— 语义孪生 TON (EOC-PAN == CTN, 已测 20+ 变体, 预期完全落 CTN 包络)
  槽2 PHI  —— == news_ton_high 已测 4 变体 (最佳 Sh 0.99), 提案方字段描述错误
  槽4/5/8 SPYADJ —— 数学恒等死重: SPY_RET = 横截面常数, rank(X-c) == rank(X),
             剥掉后 = reverse(rank(vec_avg(P_N))), P10 Sh0.44 / P120 Sh0.95 已测
  槽7 RANGE_NORM_CTN —— CTN/TON 双分母自归一化, 被槽6 支配
B6' = 红队 3 个终结槽 (PLO 族) + 5 个家族补全单元格, mandate 每批 8 槽.

红队聚焦复审 (第二轮): 8/8 GO 无砍单. 新增性实证:
  PLO 全库 0 记录; U x TON 共现 0 条; D x TON 共现 0 条;
  RANGE 作分母 0 记录 (作分子的 rangeATR 轴 S5 已封闭, 不同格);
  BREAKOUT_RATIO 的 PAN 先例出自 gate2_F 连坐取消批 (7 取消+1 ERROR, 零有效读数).
机制深核 (红队): UXCTN 非振幅平方 -- "冲高回落" (U 大而 CTN<=0) 使 U 与 |CTN|
  机械独立; 与 UXCVW 差交叉项 U x (TON-VWAP), 是"交互轴上 TON/VWAP 可否互换"
  的判决性 A/B (UXCVW Sh1.44/2Y1.62 为家族第二佳).
ts_rank250 壳实证 (红队): 不毁 2Y (毁 2Y 的是 bf60: 冠军 2Y 2.09->0.45),
  TO 仅 -2pp (120.1->118.1), 作用是 2Y 增强而非 TO 解法.

判读规则 (发射前定好):
  R1. 任何槽 Sh>1.58 且 TO<=70% -> 推翻 Sh x sqrt(TO) 标度律, 重启战略评估;
  R2. 槽2 (PLO x 冠军骨架) Sh>1.61 -> PLO 优于 TON, 参照点轴未封顶, 触发下一轮;
  R3. 8/8 无 Sh>=1.5 -> price-context 几何实证穷尽 (280 槽完备), 转战役总结:
      三重独立证据 (实证前沿/恒等式/矩阵闭合) + bl8Wd2Nq 替代路径记录在案.
"""
import asyncio
import json
import os
import sqlite3
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule  # noqa: E402
from quant_framework.core.sim_runner import SimBatchRunner  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY = "news"
REGION = "USA"
DELAY = 1
DECAY = 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

# ---------------------------------------------------------------- 字段速记 (全部经 867 字段清单核对)
EOC, VWAP, TON = "news_eod_close", "news_eod_vwap", "news_ton_last"
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"
PHI, PLO = "highest_price_pre_news", "lowest_price_pre_news"  # 均为 TON 窗口高/低 (字段定义实读)
RANGE = "main_session_price_range"
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"

# ================================================================ 方向 S6: PLO 参照点族补全 + 交互轴 x 冠军核末梢 (闭合批)
DIR_S6 = [
    {"id": 1, "type": "CLOSE_VS_PRLOW",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({VHEX}))))",
     "optimize_reason": (
        "PLO 族基础格 (红队保留=唯一真新参照点)。机制: 收盘相对事件窗口最低点的偏离 per "
        "事件波动——收盘被推离窗口底部越远=追高过度->反转。PLO=TON 窗口最低价, 全库 0 记录; "
        "与 TON 有真实信息差 (PLO<=TON 恒成立, 非 PAN 式语义孪生)。预期落 CTN 包络 "
        "Sh~1.44/2Y~1.3/TO~124%——买参照点轴最后一格的实证闭合性。")},
    {"id": 2, "type": "CLOSE_VS_PLO_ANCHOR",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), {ANCHOR_DEN})))",
     "optimize_reason": (
        "PLO x 冠军骨架 (本批最高信息量槽)。机制: d5K6wxlx 骨架 (Sh1.61/2Y2.09/TO120.1%) "
        "的 TON->PLO 单变量隔离——一次读数终审'PLO 是否优于 TON': Sh>1.61 则参照点轴未封顶"
        "(触发 PHI 分子版等残余格), 落 1.3-1.4 则参照点轴在冠军骨架处实证封顶。PLO<=TON 使 "
        "EOC-PLO>=CTN, 横截面方差结构改变, 净效应不确定——这正是要测的原因。")},
    {"id": 3, "type": "CLOSE_VS_PLO_TSRANK250",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({VHEX})), 250))",
     "optimize_reason": (
        "PLO x ts_rank250 壳 (红队建议的 TO 壳, 补齐 PLO x 壳矩阵)。先例实证: ts_rank250 "
        "不毁 2Y (毁 2Y 的是 bf60: 冠军 2Y 2.09->0.45/CPV 2.08->0.99), TO 仅 -2pp "
        "(120.1->118.1), 2Y 反升 (+0.07)。预期 Sh~1.33/2Y~1.62/TO~124% (CTN 孪生先例 "
        "S2 slot5)。若本槽 2Y 显著高于槽1, ts_rank 壳的 2Y 增强在 PLO 族复现。")},
    {"id": 4, "type": "BREAKOUT_RATIO",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), subtract(vec_avg({PHI}), vec_avg({PLO})))))",
     "optimize_reason": (
        "无量纲窗口位置几何 (红队替换项=唯一未测的 price-context 无量纲格)。机制: "
        "(EOC-PLO)/(PHI-PLO) = 收盘在事件窗口 [低,高] 中的相对位置, 超越一切振幅/波动缩放"
        "的最干净过度反应读数; 可 <0 或 >1 (收盘走出窗口)。PAN 先例出自 gate2_F 连坐取消批 "
        "(7 取消+1 ERROR, 零有效读数); 8ea58526 无 rank。EOC 版确未测。")},
    {"id": 5, "type": "BREAKOUT_RATIO_TSRANK250",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, vec_avg({PLO})), subtract(vec_avg({PHI}), vec_avg({PLO}))), 250))",
     "optimize_reason": (
        "BREAKOUT x ts_rank250 壳 (闭合 BREAKOUT x 壳 2x2 矩阵)。双重自身归一无先例。"
        "预期 Sh 1.3-1.5/TO~120% (TO 由 rank 横截面换手决定, 与量纲无关)。科学价值=壳"
        "不变性验证: 若与槽4 读数接近, 证明无量纲化 + 慢壳对该几何是中性的。")},
    {"id": 6, "type": "RANGE_NORM_PLO",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({RANGE}))))",
     "optimize_reason": (
        "PLO x 全日波幅归一 (红队槽6 升级的 3 字段适配版——原三重归一超字段上限)。机制: "
        "窗口低点偏离 per 当日 (H-L)/L 波幅 = 单位全日运动的价格冲击强度。RANGE 作分母全库 "
        "0 记录 (作分子的 rangeATR 轴 S5 已封闭 Sh1.21-1.28, 不同格); 量纲风险被 rank 外层"
        "中和 (rank 对单调变换不变)。")},
    {"id": 7, "type": "UXCTN",
     "expression": f"reverse(rank(multiply({U}, subtract({EOC}, {TON}))))",
     "optimize_reason": (
        "交互轴 x 冠军核 (家族从未测过的交互单元格)。机制: 大幅上行事件 x 收盘高于新闻时价"
        "= 过度反应最强签名->反转; reverse 符号与冠军 reverse(rank(CTN/骨架)) 逐字一致, "
        "权重差异仅在按 U 加权。新增性三重实证: DB U x TON 共现 0 条, 本地 JSON 唯一 hit 是"
        "除法非交互。非振幅平方: '冲高回落' (U 大而 CTN<=0) 使 U 与 |CTN| 机械独立。与 "
        "UXCVW (Sh1.44/2Y1.62 家族第二佳) 差交叉项 U x (TON-VWAP)——落在 UXCVW +-0.05 内 "
        "= 交互轴上 TON/VWAP 可互换; 显著偏离 = VWAP 特有路径重心信息。判决性读数。")},
    {"id": 8, "type": "DXCTN",
     "expression": f"rank(multiply({D}, subtract({TON}, {EOC})))",
     "optimize_reason": (
        "交互轴下行镜像 (与槽7 构成配对实验)。机制: 大幅下行事件 x 收盘低于新闻时价 = 超卖"
        "反转做多, 不 reverse——与 B4 先例 DXCPV_FIXED (Sh1.23/2Y1.67) 同构。DB D x TON "
        "共现 0 条。与槽7 做多条件相同 (CTN<0) 而加权正交 (U vs D), 隔离上/下幅度调制的"
        "非对称性: UX 族已知上行不对称 (D 事件 U=0 不置仓), 本对补全下行侧。")},
]

DIRECTIONS = {
    "S6": {"name": "PLO 参照点族补全 + 交互轴 x 冠军核末梢 (B6' 闭合批)", "hypothesis":
           "红队两轮终审后的闭合批: B6 原始 8 槽被砍 5 槽 (PAN 语义孪生/PHI 重复/SPYADJ "
           "数学恒等死重/CTN 自归一), 仅 PLO (TON 窗口低点, 库中 0 记录) 是真新参照点。"
           "本批以 PLO 族 6 格 (x VHEX/锚分母/ts_rank250 壳/无量纲窗口位置/其 ts_rank 壳/"
           "全日波幅) + 交互轴 x 冠军核 2 格 (U/D x CTN, 全库 0 共现) 填满 8 槽。判读: "
           "R1 任何槽 Sh>1.58 且 TO<=70% 推翻标度律; R2 槽2 Sh>1.61 则 PLO 优于 TON; "
           "R3 8/8 无 Sh>=1.5 则 price-context 几何实证穷尽 (280 槽完备), 转战役总结",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_S6},
}

STAGGER_SECONDS = {"S6": 0}




def purge_fingerprints(exprs: list, neutralization: str, universe: str):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        fixed = corrector.correct_expression(e)
        h = corrector.compute_fingerprint(fixed, REGION, universe, DELAY, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n} records (neut={neutralization}, universe={universe})", flush=True)


def preaudit(items: list, known_fields: list):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        used = tokens & known_set
        ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
               "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
               "ts_delta", "ts_decay_linear", "trade_when", "greater", "less", "vec_avg",
               "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "days_from_last_change",
               "industry", "subindustry", "sector", "market"}
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        n_fields = len(used)
        status = "OK" if audit["is_valid"] else "FAIL"
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']} fields={n_fields} "
              f"len={len(it['expression'])} {status} | {it['expression'][:80]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符 (字段名拼写错误?): {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")
        if audit["operator_count"] > 10:
            raise ValueError(f"slot{it['id']} 算子数 {audit['operator_count']} > 10")
        if len(it["expression"]) > 857:
            raise ValueError(f"slot{it['id']} 表达式超长 {len(it['expression'])} > 857")


def check_dup_fingerprints(items: list, neutralization: str, universe: str):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    dups = []
    for it in items:
        neut = it.get("neutralization", neutralization)
        fixed = corrector.correct_expression(it["expression"])
        h = corrector.compute_fingerprint(fixed, REGION, universe, DELAY, neut)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        row = cur.fetchone()
        if row:
            dups.append((it["id"], it["expression"][:60]))
    conn.close()
    if dups:
        print(f"  [dup-check] 历史已测 {len(dups)} 条 (<=2/批合法): {dups}", flush=True)
    if len(dups) > 2:
        raise ValueError(f"批次内历史重复 {len(dups)} 条 > 2, 防摸鱼门禁将拒: {dups}")


def build_summary(items: list, results: list, direction: str):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or r.get("is") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret = m.get("returns") or 0
        to = m.get("turnover") or 0
        rows.append({
            "slot": it["id"], "type": it["question_type"], "expression": it["expression"],
            "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": to, "returns": ret,
            "ret_over_to": (ret / to) if to else None,
            "drawdown": m.get("drawdown"), "margin_bps": (m.get("margin") or 0) * 10000,
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "sub_sharpe": m.get("sub_universe_sharpe"), "two_year_sharpe": m.get("two_year_sharpe"),
            "inv_sharpe": m.get("investability_sharpe"), "rn_sharpe": m.get("risk_neutralized_sharpe"),
            "ra_failed": ra.get("ra_failed"), "ra_failed_checks": ra.get("ra_failed_checks"),
            "fail_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("fail") or [])],
            "warning_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("warning") or [])],
        })
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    d = DIRECTIONS[direction]
    return {
        "direction": direction, "direction_name": d["name"],
        "hypothesis": d["hypothesis"],
        "settings": {"neutralization": d["neutralization"], "universe": d["universe"],
                     "decay": DECAY, "truncation": TRUNCATION,
                     "region": REGION, "delay": DELAY, "nan_handling": NAN_HANDLING},
        "rows": rows,
        "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                 "step2": step2, "final": final},
    }


def print_table(summary: dict):
    s = summary["settings"]
    print(f"\n===== Gate1-Wave9 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"{'槽':>2} {'类型':<28} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'Mgn':>6} {'DD%':>6} {'2Y':>6} {'sub':>5} {'rnSh':>5} {'L/S':>9} {'fail':<26} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:28]:<28} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:26]:<26} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)
    valid = [r for r in summary["rows"] if (r["longCount"] or 0) > 20 and r["ret_over_to"]]
    if valid:
        best = max(valid, key=lambda r: r["sharpe"] or -99)
        print(f"[margin 前沿] 最佳 Sh 槽{best['slot']} {best['type']}: Ret/TO={best['ret_over_to']:.4f} "
              f"(margin 死线需 0.5, 差距 {0.5/best['ret_over_to']:.1f}x)", flush=True)


async def submit_batch_group(items: list, state_path: str, neutralization: str, universe: str, tag: str):
    location = None
    if os.path.exists(state_path):
        try:
            lines = [json.loads(l) for l in open(state_path, encoding="utf-8") if l.strip()]
            if lines:
                location = lines[-1].get("location")
        except Exception:
            location = None
    exprs = [it["expression"] for it in items]
    if not location:
        for attempt in range(1, 6):
            try:
                sub = await BrainModule.submit_multi_simulation(
                    alpha_expressions=exprs, region=REGION, universe=universe, delay=DELAY,
                    decay=DECAY, neutralization=neutralization, truncation=TRUNCATION,
                    pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                    language="FASTEXPR", visualization=False)
                if "error" in sub:
                    raise RuntimeError(f"submit error: {sub}")
                location = sub["location"]
                with open(state_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps({"neut": neutralization, "location": location,
                                        "submitted_at": int(time.time())}) + "\n")
                print(f"[submit-{tag}] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    return location


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave9-B6'] 字段字典 {len(known_fields)} 个装载", flush=True)

    direction = "S6"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W9_{direction}_{s['id']}", "question_type": s["type"],
              **({"neutralization": s["neutralization"]} if "neutralization" in s else {})}
             for s in d["slots"]]
    assert len(items) == 8, f"{direction} 批必须 8 槽"
    print(f"\n[Wave9-B6'-{direction}] {d['name']}", flush=True)
    print(f"[Wave9-B6'-{direction}] 假说: {d['hypothesis']}", flush=True)
    preaudit(items, known_fields)
    check_dup_fingerprints(items, d["neutralization"], d["universe"])

    ts = int(time.time())
    state_path = os.path.join(CAMPAIGN, f"state_gate9_{direction}.json")
    batch_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields,
                   "neutralization": d["neutralization"], "items": items}, f, ensure_ascii=False, indent=1)
    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION,
                                                       d["universe"], DELAY, d["neutralization"])
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields,
                   "neutralization": d["neutralization"], "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[Wave9-B6'-{direction}] 批次文件: {batch_path}", flush=True)
    try:
        location = await submit_batch_group(items, state_path, d["neutralization"], d["universe"], direction)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
        print(f"[Wave9-B6'-{direction}] FATAL submit: {e}", flush=True)
        raise

    # 轮询
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(location)
            st = chk.get("status")
            print(f"  [poll-{direction}] {st} progress={chk.get('progress', 0)}", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                break
        except Exception as e:
            print(f"  [poll-{direction}] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)

    fetch = await BrainModule.fetch_multi_simulation_result(location)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[Wave9-B6'] fetch 空! {str(fetch)[:300]}", flush=True)
        return
    result_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{ts}_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave9-B6'] 结果已存: {result_path}", flush=True)

    by_code = {}
    for r in results:
        by_code[r.get("code", "")] = r
    ordered = []
    for it in items:
        r = by_code.get(it["expression"])
        if r is None:
            ordered.append({"alpha_id": None, "code": it["expression"], "metrics": {}, "ra": {}, "checks": {}})
        else:
            ordered.append(r)
    if len(ordered) != len(items):
        print(f"[Wave9-B6'] 警告: 结果对齐异常 {len(ordered)} vs {len(items)}", flush=True)
    summary = build_summary(items, ordered, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate9_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave9-B6'-{direction}] 汇总已存: {sum_path}", flush=True)
    print("\n[Wave9-B6'] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
