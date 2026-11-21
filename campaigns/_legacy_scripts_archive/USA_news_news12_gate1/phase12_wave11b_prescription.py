# -*- coding: utf-8 -*-
"""Gate1 Wave11b · mLYNEWjW 种子定向优化处方攻坚 (2026-10-25).

=== 战役定位 ===
news12 Gate1 战役已以 42 批 336 槽闭合 (解集为空, 六墙两门一警告+Sub 平反).
本波为 AEGIS 种子定向优化: 对全战役最佳近 miss mLYNEWjW 执行处方攻坚,
8 条处方 x 3 settings 消融 (W1 INDUSTRY/d6 主批; W2 MARKET/d6 中性化下沉;
W3 INDUSTRY/d20 decay 交互) + 前置 2 条新算子 smoke test.

=== v3 处方设计依据 (红队终审 NO-GO + 双研究 agent + 红队复审后的重构) ===
1. ts_rank250 壳删除: 2rjx3ow8 实读证伪 (本基座 Sh 1.59->1.46, CLUSTER 1.54->1.32);
   ts_rank(-x) 在零稀疏序列上并列破裂 (max 偏差 1.0).
2. 省 reverse 恒等式废止 (M2-1): 门控把常数 1 调制成门 flag g, 中性化残留
   g-mean(g) (std 0.497) 一阶大于信号 (0.29) —— 一律显式 reverse + RATIO_F.
3. 平台 checks 豁免规律 (352/352 零例外): |Sh|>=1 且 TO<=70% => Sh/Fit/2Y 检查
   降 warning; fail=[] 的 26 行全部无 MATCHES_THEMES.
4. b9/b10/b11 补充批情报 (24 槽, INDUSTRY/d6): bf2 无门 TO 84.1%/Sh 1.43;
   bf3 无门 TO 68.8% (过门); 双压力分子 bf2 无门 Ret 7.68%.
5. 门不是 TO 杠杆 (w10i); dflc<1 先证近中性 (Sh 1.65->1.62, CLUSTER +0.01).
6. news_eod_open 已从平台 875 字段池下线 (整批连坐风险), 弃用; 第二锚点改 vwap.
7. 新算子 (ts_decay_exp_window/winsorize) 本地零完成实证 -> smoke test 先行.
8. 平台实证 (2026-10-25 smoke test 首发): winsorize 只接受 1 个位置输入, std 必须
   命名参数 winsorize(x, std=N) —— 位置传参报 'Invalid number of inputs: 2, should be
   exactly 1 input(s)' 且同批全部 ERROR+CANCELLED 连坐 (红队 B.6 位置合法判断被推翻).

=== 发射纪律 (M3  mandate) ===
* 全部直调 BrainModule.submit_multi_simulation, 严禁流经 SimBatchRunner
  (validate_and_pack_batch 会写指纹; decay 不在指纹内 => W3 与 W1 指纹全同,
   走写入路径将使 W3 被 check_and_record_batch 以 8 重复 >2 熔断).
* phase 系直提不写指纹 => 无需 purge (预检的本地 JSON 精确匹配是防重主线).
* max_trade=OFF 显式; truncation=0.025; nan=ON; pasteurization=ON; unit=VERIFY.
* 严禁提交任何 alpha (铁律).
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
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY = "news"
REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
VHEX = "high_price_excursion_stddev"

GATE2 = f"days_from_last_change(vec_count({VHEX})), 2"
GATE1 = f"days_from_last_change(vec_count({VHEX})), 1"
RATIO_F = f"divide(subtract({EOC}, {TON}), add(vec_count({VHEX}), 1))"
DUAL_F = f"divide(add(subtract({EOC}, {TON}), subtract({EOC}, {VWAP})), {VWAP})"

# ================================================================ 8 条处方 (与 precheck_w11.py v3 逐字一致)
SLOTS = [
    {"id": 1, "type": "BF2_FRESHGATE", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill({RATIO_F}, 2))), 0)"},
    {"id": 2, "type": "BF3_FRESHGATE", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill({RATIO_F}, 3))), 0)"},
    {"id": 3, "type": "DFLC1_BF2", "role": "RX",
     "expression": f"trade_when(less({GATE1}), reverse(rank(ts_backfill({RATIO_F}, 2))), 0)"},
    {"id": 4, "type": "EXPDECAY20_F09", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_exp_window({RATIO_F}, 20, factor=0.9))), 0)"},
    {"id": 5, "type": "WINSORIZE_BF2", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill(divide(winsorize(subtract({EOC}, {TON}), std=2), add(vec_count({VHEX}), 1)), 2))), 0)"},
    {"id": 6, "type": "ANOMALY_D3", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(subtract({RATIO_F}, ts_mean({RATIO_F}, 20)))), 0)"},
    {"id": 7, "type": "DUAL_NATIVE", "role": "RX",
     "expression": f"reverse(rank({DUAL_F}))"},
    {"id": 8, "type": "POOLED_NETRATIO", "role": "RX",
     "expression": f"trade_when(less({GATE2}), reverse(rank(divide(ts_sum(subtract({EOC}, {TON}), 20), ts_sum(abs(subtract({EOC}, {TON})), 20)))), 0)"},
]
SEED_CONTROL = {"id": 8, "type": "SEED_CONTROL_MARKET", "role": "CTRL",
                "expression": f"trade_when(less({GATE2}), reverse(rank({RATIO_F})), 0)"}

# smoke test 探针 (2 条新算子变体; 与主批槽4/5 构成参数扫描点, 非浪费)
SMOKE = [
    {"id": 1, "type": "SMOKE_EXPDECAY10", "role": "PROBE",
     "expression": f"reverse(rank(ts_decay_exp_window({RATIO_F}, 10, factor=0.9)))"},
    {"id": 2, "type": "SMOKE_WINSORIZE_STD3", "role": "PROBE",
     "expression": f"reverse(rank(divide(winsorize(subtract({EOC}, {TON}), std=3), add(vec_count({VHEX}), 1))))"},
]

DIRECTIONS = {
    "W1": {"name": "主批 8 处方 (INDUSTRY/d6)", "universe": "TOP1000", "neutralization": "INDUSTRY",
           "decay": 6, "slots": SLOTS},
    "W2": {"name": "中性化下沉 (MARKET/d6): 槽1-7 + 母本对照", "universe": "TOP1000",
           "neutralization": "MARKET", "decay": 6, "slots": SLOTS[:7] + [SEED_CONTROL]},
    "W3": {"name": "decay 交互 (INDUSTRY/d20): 同 8 条", "universe": "TOP1000",
           "neutralization": "INDUSTRY", "decay": 20, "slots": SLOTS},
}

HYPOTHESIS = (
    "mLeneWjW 的缺口 = LOW_FITNESS(0.41) + HIGH_TURNOVER(114.6%) + CLUSTER(1.54<1.58) + MATCHES_THEMES. "
    "豁免规律 (|Sh|>=1 & TO<=70% => fail 降 warning; 26/26 fail=[] 行无 MATCHES_THEMES) 指明战略: "
    "先用 bf 短窗/池化把 TO 压过 70% 且保 Sh>=1.0 拿掉 fail, 再以 winsorize/异常分离/新鲜门攻 "
    "CLUSTER 1.58, 双压力分子保 Ret 攻 Fit. 8 处方覆盖: H1 (槽1/2/3/4/5/8), H2 (槽7/8), "
    "H3 (槽3/5/6), H4 (W2 母本对照).")


def preaudit(items: list, known_fields: list, tag: str):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
           "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
           "ts_delta", "ts_decay_linear", "ts_decay_exp_window", "ts_median", "trade_when",
           "greater", "less", "if_else", "vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min",
           "vec_stddev", "days_from_last_change", "winsorize", "abs", "power", "sqrt",
           "industry", "subindustry", "sector", "market", "sign", "factor", "std"}
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        it["expression"] = fixed
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        used = tokens & known_set
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        print(f"  [pre-audit-{tag}] slot{it['id']:<2} ops={audit['operator_count']:>2} "
              f"fields={len(used)} len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'}", flush=True)
        if unknown:
            raise ValueError(f"[{tag}] slot{it['id']} 未知标识符: {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"[{tag}] slot{it['id']} 审计失败: {audit['issues']}")
        if not (2 <= len(used) <= 3):
            raise ValueError(f"[{tag}] slot{it['id']} 字段数 {len(used)} 越界")
        if audit["operator_count"] > 16:
            raise ValueError(f"[{tag}] slot{it['id']} ops {audit['operator_count']} > 16")
        if len(fixed) > 857:
            raise ValueError(f"[{tag}] slot{it['id']} 超长")


async def submit_batch(items: list, state_path: str, neutralization: str, decay: int, tag: str):
    location = None
    if os.path.exists(state_path):
        try:
            location = json.load(open(state_path, encoding="utf-8")).get("location")
        except Exception:
            location = None
    exprs = [it["expression"] for it in items]
    if not location:
        for attempt in range(1, 6):
            try:
                sub = await BrainModule.submit_multi_simulation(
                    alpha_expressions=exprs, region=REGION, universe=UNIVERSE, delay=DELAY,
                    decay=decay, neutralization=neutralization, truncation=TRUNCATION,
                    pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                    language="FASTEXPR", visualization=False, max_trade="OFF")
                if "error" in sub:
                    raise RuntimeError(f"submit error: {sub}")
                location = sub["location"]
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump({"location": location, "submitted_at": int(time.time()),
                               "decay": decay, "neutralization": neutralization, "tag": tag}, f)
                print(f"[submit-{tag}] OK location={location} (n={len(exprs)})", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    return location


async def poll_until_done(location: str, tag: str):
    waited = 0
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(location)
            st = chk.get("status")
            if waited >= 60:
                print(f"  [poll-{tag}] {st} progress={chk.get('progress', 0)} t={waited}s", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                print(f"  [poll-{tag}] 终态 {st} (t={waited}s)", flush=True)
                return st
        except Exception as e:
            print(f"  [poll-{tag}] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)
        waited += 20


def build_summary(items: list, results: list, direction: str, decay: int, neutralization: str):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret, to = m.get("returns") or 0, m.get("turnover") or 0
        rows.append({
            "slot": it["id"], "role": it["role"], "type": it["type"],
            "expression": it["expression"], "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": to, "returns": ret,
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
    return {"direction": direction, "direction_name": DIRECTIONS[direction]["name"],
            "hypothesis": HYPOTHESIS,
            "settings": {"neutralization": neutralization, "universe": UNIVERSE, "decay": decay,
                         "truncation": TRUNCATION, "region": REGION, "delay": DELAY,
                         "nan_handling": NAN_HANDLING},
            "rows": rows,
            "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                     "step2": step2, "final": final}}


def print_table(summary: dict):
    s = summary["settings"]
    print(f"\n===== Wave11b {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
    print(f"{'槽':>2} {'角色':<5} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} "
          f"{'Mgn':>6} {'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>10} {'raFail':>6}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['role']):<5} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>5.2f} "
              f"{to:>7.1f} {ret:>7.2f} {r['ret_over_to'] or 0:>6.3f} {r['margin_bps'] or 0:>6.2f} "
              f"{r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} "
              f"{ls:>10} {str(r['ra_failed']):>6}", flush=True)
        if r["fail_checks"] or r["warning_checks"]:
            print(f"      fail: {r['fail_checks']}", flush=True)
            print(f"      warn: {r['warning_checks']}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)


async def run_direction(direction: str, known_fields: list):
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "role": s["role"], "type": s["type"], "expression": s["expression"],
              "optimize_reason": f"W11b {direction} slot{s['id']} ({s['type']}); 设计依据见 precheck_w11.py v3",
              "seed_id": f"GATE1W11B_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    print(f"\n[Wave11b-{direction}] {d['name']} (n={len(items)})", flush=True)
    preaudit(items, known_fields, direction)

    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w11b_{direction}_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W11B_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "decay": d["decay"], "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[Wave11b-{direction}] 批次文件: {batch_path}", flush=True)

    state_path = os.path.join(CAMPAIGN, f"state_w11b_{direction}.json")
    loc = await submit_batch(items, state_path, d["neutralization"], d["decay"], direction)
    if not loc:
        print(f"[Wave11b-{direction}] 无 location, 退出", flush=True)
        return None
    print(f"[Wave11b-{direction}] 静默轮询中 (前 60s 无输出)...", flush=True)
    st = await poll_until_done(loc, direction)

    fetch = await BrainModule.fetch_multi_simulation_result(loc)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[Wave11b-{direction}] fetch 空! {str(fetch)[:400]}", flush=True)
        return None
    res_path = os.path.join(CAMPAIGN, f"batch_w11b_{direction}_{ts}_result.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave11b-{direction}] 结果已存: {res_path} (n={len(results)})", flush=True)

    summary = build_summary(items, results, direction, d["decay"], d["neutralization"])
    sum_path = os.path.join(CAMPAIGN, f"summary_w11b_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave11b-{direction}] 汇总已存: {sum_path}", flush=True)
    return summary


async def run_smoke(known_fields: list):
    """新算子 smoke test: 2 条探针 @INDUSTRY/d6. CANCELLED/ERROR => 停止并报告."""
    items = [{"id": s["id"], "role": s["role"], "type": s["type"], "expression": s["expression"],
              "optimize_reason": f"W11b smoke probe: {s['type']}; 验证 ts_decay_exp_window/winsorize 签名后与主批槽4/5 构成参数扫描",
              "seed_id": f"GATE1W11B_SMOKE_{s['id']}", "question_type": s["type"]} for s in SMOKE]
    print("\n[Wave11b-SMOKE] 新算子探针批 (2 条: ts_decay_exp_window d10 + winsorize std3)", flush=True)
    preaudit(items, known_fields, "SMOKE")
    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w11b_SMOKE_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": "GATE1W11B_SMOKE", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "decay": 6, "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    state_path = os.path.join(CAMPAIGN, "state_w11b_SMOKE.json")
    loc = await submit_batch(items, state_path, "INDUSTRY", 6, "SMOKE")
    if not loc:
        return False
    print("[Wave11b-SMOKE] 静默轮询中...", flush=True)
    st = await poll_until_done(loc, "SMOKE")
    fetch = await BrainModule.fetch_multi_simulation_result(loc)
    results = fetch.get("alpha_results", [])
    ok = bool(results) and all(r.get("alpha_id") for r in results) and st in ("COMPLETE", "COMPLETED", "DONE")
    if ok:
        res_path = os.path.join(CAMPAIGN, f"batch_w11b_SMOKE_{ts}_result.json")
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
        print(f"[Wave11b-SMOKE] PASS: {len(results)} 条完成, 新算子签名验证通过 -> {res_path}", flush=True)
        for r in results:
            m = r.get("metrics") or {}
            print(f"    {r.get('alpha_id')} Sh={m.get('sharpe')} TO={m.get('turnover')}", flush=True)
    else:
        print(f"[Wave11b-SMOKE] FAIL: status={st}, results={len(results)} -> 主批中止, 需人工检查算子/语法", flush=True)
    return ok


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave11b] 字段字典 {len(known_fields)} 个装载", flush=True)
    print(f"[Wave11b] 假说: {HYPOTHESIS}", flush=True)

    # 0. smoke test (新算子签名验证; 例外授权的 2 条探针批, 规避整批连坐)
    smoke_ok = await run_smoke(known_fields)
    if not smoke_ok:
        print("[Wave11b] SMOKE 未通过, 主批 W1/W2/W3 全部中止", flush=True)
        return

    # 1-3. 三批串行 (一次一批, 每批 8 条)
    summaries = {}
    for direction in ("W1", "W2", "W3"):
        summaries[direction] = await run_direction(direction, known_fields)

    out = os.path.join(CAMPAIGN, f"summary_w11b_ALL_{int(time.time())}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[Wave11b] 三批汇总已存: {out}", flush=True)
    print("[Wave11b] 批次回收完毕。严禁提交任何 alpha。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
