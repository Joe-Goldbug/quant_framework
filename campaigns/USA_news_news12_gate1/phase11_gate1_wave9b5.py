# -*- coding: utf-8 -*-
"""Gate1 Wave9-B5 新 IC 轴批 (2026-10-25 凌晨, 红队 B3' 裁决版).

B2 判决后的条件分化批. B2 关键读数:
  槽4 VECMAX_CVW_TSRANK250: Sh 1.58 (恰好压线, 家族首个) / 2Y 1.27 / TO 127.6% / Fit 0.36
  槽5 VECAVG_CTN_TSRANK250: 2Y 1.62 (CTN 族首个过线) / Sh 1.33 / TO 124%
  槽7 硬门 x 振幅: Sh 1.13->1.17 不降反升 (稀疏分子免费红利证实) / TO 58.6%
  振幅 bf60 x ts_rank250 合成: TO 37.3% 保住但 2Y 仅 0.93 (回填墙复现)

红队裁决 (2026-10-25, 全盘接受):
  砍 TOP3000 探针 (宇宙不回迁则读数不可迁移, mandate 交付宇宙是 TOP1000);
  砍 COPEN_VECMAX / CVW_VECAVG (可被 B2 两点线性插值的冗余置换);
  新开两个真新 IC 轴 (168 槽以来家族外唯一未测的经济内容):
    A. CPV 盘后参照点轴: close vs post_vwap (盘后是注意力最低时段, 收盘价被推离
       盘后共识 = 注意力稀缺的纯粹读数; 与 CVW 的盘中尾盘窗口不重叠; post_vwap
       全史 0 使用; cov 0.9705 与 EOC 对齐好; 价减价量纲干净)
    B. UXCVW 交互轴: 事件幅度 x 尾盘压力 (multiply(U, EOC-VWAP)), U 引入 CVW 没有的
       横截面幅度调制; 已知缺陷: 非稀疏 (cov 0.9692 -> TO 100-120%, 门控对其空转已证),
       使命是回答"交互有没有 IC"而非达标; RET 版量纲更干净 (UNITS 风险最低)
  判读规则 (发射前定好): CPV 裸版 Sh>1.4 或 UXCVW 裸版 Sh>1.3 = 新维度证据 -> B4 深挖;
  8/8 全灭 = news12 证伪地图完整.
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
OPEN, PVW = "news_open", "news_post_vwap"
U, D = "news_max_up_amt", "news_max_dn_amt"
UR = "news_max_up_ret"
VHEX = "high_price_excursion_stddev"
CNT = f"add(vec_count({VHEX}), 1)"
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"
AMP = f"divide({U}, add({U}, {D}))"
VOLSURGE, RANGEATR = "main_session_volume_ratio", "main_session_range_to_atr_ratio"
UPI, DPI = "max_pct_increase_post_news", "max_pct_decrease_post_news"

# ================================================================ 方向 S3: 分子矩阵收尾 + 两个真新 IC 轴 + 振幅冲刺
DIR_S5 = [
    {"id": 1, "type": "CTN_PER_VOLSURGE", "expression":
        f"reverse(rank(divide(subtract({EOC}, {TON}), vec_avg({VOLSURGE}))))",
     "optimize_reason": (
        "最佳 2Y 压力分子 x 量惊异归一 (红队保留=旗舰检验)。机制: CTN 是家族 2Y 之王 (x count "
        "2Y2.09/Sh1.61), volsurge (当日量/30日均量) 是参与强度归一——V 批只在 close-vwap 系"
        "分子上测过 (Sh1.29-1.32 < count 的 1.63), 但'分母效应分子依赖'已实证 (count 给 CTN "
        "2Y2.09 vs 给 CVW 0.58), 最佳分子上翻盘是合法期权。预期 Sh<=1.4/TO>=110%: 若 CTN 2Y "
        "保住 >=1.8 且 Sh 上头 1.5, volsurge 轴在最优分子上成立; 若双输, volsurge 封闭。")},
    {"id": 2, "type": "CPV_PER_VOLSURGE", "expression":
        f"reverse(rank(divide(subtract({EOC}, {PVW}), vec_avg({VOLSURGE}))))",
     "optimize_reason": (
        "CPV 分子 x 量惊异 (与槽1/3 构成受控实验)。机制: CPV x 锚分母 2Y2.24/Sh1.46 是 B4 "
        "新前沿点; volsurge 版本隔离归一器效应 (锚分母 vs 量惊异 on CPV)。若 2Y 保住且 Sh "
        "上头, 得第三个高 2Y 基座。")},
    {"id": 3, "type": "COPEN_PER_VOLSURGE", "expression":
        f"reverse(rank(divide(subtract({EOC}, {OPEN}), vec_avg({VOLSURGE}))))",
     "optimize_reason": (
        "COPEN 分子 x 量惊异 (2Y 家族之最 x 量惊异)。机制: COPEN x count 2Y2.35/Sh1.42/TO113.8% "
        "是距达标最近的既有候选; volsurge 版测归一器置换的边际。与槽1/2 固定分母扫三最佳分子, "
        "隔离分子效应, 是 volsurge 轴的完整受控网格。")},
    {"id": 4, "type": "CTN_PER_RANGEATR", "expression":
        f"reverse(rank(divide(subtract({EOC}, {TON}), vec_avg({RANGEATR}))))",
     "optimize_reason": (
        "CTN x 波幅惊异 (最后一个结构异质归一器)。机制: range/ATR = 当日价格运动 vs 14 日 ATR "
        "= 无量纲相对运动强度, 比 volsurge 更直接度量'事件日的异常运动'; 量纲分析与冠军 count "
        "分母同构 (美元差/无量纲)。红队提示先验风险: ATR 族分母 4 个历史点全弱 (0.35-1.05), "
        "但从未上最优分子——分子依赖律下值得一枪。")},
    {"id": 5, "type": "CPV_PER_RANGEATR", "expression":
        f"reverse(rank(divide(subtract({EOC}, {PVW}), vec_avg({RANGEATR}))))",
     "optimize_reason": (
        "CPV x 波幅惊异 (range/ATR 轴 x 家族并列最佳 2Y 分子)。机制: 与槽4/7 构成新归一器轴"
        "的最小受控网格 (CTN/CPV/COPEN), 若网格一致弱势则 range/ATR 轴封闭, 若 CPV 上 2Y 保 "
        "1.8+ 则新轴在最佳分子上成立。")},
    {"id": 6, "type": "CTN_PER_TOTTICKS", "expression":
        f"reverse(rank(divide(subtract({EOC}, {TON}), news_tot_ticks)))",
     "optimize_reason": (
        "CTN x 参与广度归一 (红队替换槽=全批最高 EV 新组合)。机制: tot_ticks = 全日成交笔数, "
        "压力 per 笔数 = 单位参与广度的价格冲击; 与 count (事件数) / volsurge (量) / range/ATR "
        "(波幅) 构成四种物理不同的参与归一。已验证 (U-D) 净振幅 x tot_ticks = LL52vvd2 Sh0.58 "
        "(弱), 但冠军分子 x tot_ticks 从未测——分子依赖律下 CTN 版是合法冲刺。")},
    {"id": 7, "type": "COPEN_PER_RANGEATR", "expression":
        f"reverse(rank(divide(subtract({EOC}, {OPEN}), vec_avg({RANGEATR}))))",
     "optimize_reason": (
        "COPEN x 波幅惊异 (range/ATR 网格第三点)。机制: 2Y 之王 x 新归一器——若 COPEN 在 "
        "range/ATR 上保住 2Y>=2.0, 得家族 2Y 新极值; 与槽4/5 共同判定 range/ATR 轴生死。")},
    {"id": 8, "type": "REACTION_ASYMMETRY", "expression":
        f"reverse(rank(subtract(vec_avg({UPI}), vec_avg({DPI}))))",
     "optimize_reason": (
        "反应不对称几何 (红队保留=唯一 0 用户反拥挤 2Y 候补)。机制: 事件后上行尖峰幅值 vs "
        "下行尖峰幅值之差 = 注意力驱动的上行偏好读数; 符号经字段定义验证 (UPI/DPI 均为绝对"
        "幅值, reverse=空上行偏好, 与种子锚 reverse(up/(up+dn)) 同向)。W 批'延续'证据只覆盖 "
        "10m-120m 衰减形态, 不覆盖极端幅值不对称, 非反证。")},
]

DIRECTIONS = {
    "S5": {"name": "归一器扫描: 最佳分子 x volsurge/range-ATR/tot_ticks + 不对称几何 (B5)", "hypothesis":
           "归一器轴是唯一未系统扫描完的轴: volsurge (V 批仅测 close-vwap 系) 上头三种最佳分子 "
           "(CTN/CPV/COPEN); range/ATR (从未作归一器, 0 用户) 上 CTN/CPV/COPEN; tot_ticks (参与"
           "广度, 仅测过净振幅) 上 CTN; 外加反应不对称几何。判读规则发射前定好: 若 8/8 无 "
           "Sh>=1.5 候选, 归一器轴经济实质穷尽 (形式上残余仅日频强度族)",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_S5},
}

STAGGER_SECONDS = {"S5": 0}




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
    print(f"[Wave9-B5] 字段字典 {len(known_fields)} 个装载", flush=True)

    direction = "S5"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W9_{direction}_{s['id']}", "question_type": s["type"],
              **({"neutralization": s["neutralization"]} if "neutralization" in s else {})}
             for s in d["slots"]]
    assert len(items) == 8, f"{direction} 批必须 8 槽"
    print(f"\n[Wave9-B5-{direction}] {d['name']}", flush=True)
    print(f"[Wave9-B5-{direction}] 假说: {d['hypothesis']}", flush=True)
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
    print(f"[Wave9-B5-{direction}] 批次文件: {batch_path}", flush=True)
    try:
        location = await submit_batch_group(items, state_path, d["neutralization"], d["universe"], direction)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
        print(f"[Wave9-B5-{direction}] FATAL submit: {e}", flush=True)
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
        print(f"[Wave9-B5] fetch 空! {str(fetch)[:300]}", flush=True)
        return
    result_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{ts}_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave9-B5] 结果已存: {result_path}", flush=True)

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
        print(f"[Wave9-B5] 警告: 结果对齐异常 {len(ordered)} vs {len(items)}", flush=True)
    summary = build_summary(items, ordered, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate9_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave9-B5-{direction}] 汇总已存: {sum_path}", flush=True)
    print("\n[Wave9-B5] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
