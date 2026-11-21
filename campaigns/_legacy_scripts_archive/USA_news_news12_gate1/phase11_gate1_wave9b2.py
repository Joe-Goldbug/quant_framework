# -*- coding: utf-8 -*-
"""Gate1 Wave9-B2 振幅族拯救批 (2026-10-24 深夜).

Wave9-B1 判决 (8/8 负 Sharpe, 红队 alternative_slots 全无 reverse) 后的条件分化批.

B1 科学结论:
  1. 符号约定确认: reverse 必需 (本家族 232 槽全 reverse; B1 无 reverse 版全负 -> reverse
     是精确符号翻转, 等效读数 = B1 表取负, 无需重烧)
  2. vec_avg/vec_max 分母假说证伪: TO 不降反升 (123-128% 全场最高) + DD 78% 灾难——
     分母逐日变化驱动 TO, 红队'天然稀疏降 TO'落空; 但 VECMAX_DEN_CVW 的 reverse 等效
     Sh +1.68 是全场新记录 (冠军 1.61), 只是 TO128.5%/2Y1.19/DD78% 不可交易
  3. 门控机械有效但杀 Sh: 硬事件门 TO 113%->39.7% 但 Sh 0.93; 慢门 TO 21.4% 但 Sh 0.25
  4. P 增量通式机理判死 (TO 仍 123.5%) —— 红队裁决确认
  5. 🔴 前沿恒等式全景: 沿 (Sh,R/TO) 前沿 (0.57,0.125)...(1.61,0.064) 的 Fit 全部平坦于
     0.2-0.41 —— 家族每笔 IC 上限结构化, 换手管理曲线上无逃逸点

B2 三子方向 (每子方向攻一个尚未关闭的假设):
  A 振幅族 x 极端度: 振幅族 (U/(U+D)) 是唯一 TO 天然低 (37%) 的分子族, 但其 2Y 0.68-0.79
     是仅存短板; ts_rank250 极端度是已验证 2Y 修复器 (price 族 2Y 0.58->1.30-1.45) 但
     从未应用于振幅族 (ts_rank(A,20)=1.16 已测, 250 未测). 若 2Y 修复到 >=1.58 且 Sh
     拉到 1.4+, 振幅族将剩 Fit 单墙.
  B 新 Sh 记录基座 x 极端度: VECMAX_DEN_CVW (reverse 等效 Sh1.68 全场新记录) 的 2Y 仅 1.19,
     配 ts_rank250 攻 2Y; VECAVG_DEN_CTN 同构.
  C SUBINDUSTRY settings 探针 (红队预留 1 槽): 更细中性化分散持仓喂 CLUSTER_TEST (全场
     最高 1.47 < 1.58, 零警告的最后未测杠杆) —— 压在距达标最近的 COPEN 基座上.
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
EOH, EOL, OPEN, TH = "news_eod_high", "news_eod_low", "news_open", "news_ton_high"
U, D = "news_max_up_amt", "news_max_dn_amt"
HEX, LEX = "news_high_exc_stddev", "news_low_exc_stddev"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"
CNT = f"add(vec_count({VHEX}), 1)"                       # 防除零的事件计数分母
AMP = f"divide({U}, add({U}, {D}))"                      # 振幅族基座 (事件稀疏, TO 天然低)

# ================================================================ 方向 S2: 振幅族拯救 + 新记录基座 + SUBINDUSTRY 探针
DIR_S2 = [
    {"id": 1, "type": "AMP_BF60_TSRANK250", "expression":
        f"reverse(ts_rank(ts_backfill({AMP}, 60), 250))",
     "optimize_reason": (
        "振幅族 bf60 x ts_rank250 合成 (本批最关键未测组合)。机制: 前役实测两条腿从未结合——"
        "LL5wOMgv 原始振幅 x ts_rank250: Sh1.35/2Y**1.65**✓/但 TO129%✗; YPxOGboo 振幅 x "
        "bf60 x group_rank: TO37%✓/但 2Y0.68-0.79✗。bf60 砍 TO (回填只在无事件日补陈旧值, "
        "不伤事件日信号) + ts_rank250 修 2Y (自身极端度过滤政权变化)。若合成版 2Y>=1.58 且 "
        "TO<=50%, 振幅族只剩 Sh 与 Fit 两墙且都是已知可攻方向; 若 bf60 像杀 price 族一样杀 "
        "振幅极端度 (Sh 塌), 则回填墙通杀全家族, 振幅族路线关闭。")},
    {"id": 2, "type": "AMP_BF60_RANK", "expression":
        f"reverse(rank(ts_backfill({AMP}, 60)))",
     "optimize_reason": (
        "振幅 bf60 x plain rank (隔离组内化效应)。机制: YPxOGboo 是 bf60 x group_rank(industry) "
        "(Sh?/TO37.8%/2Y0.68-0.79), plain rank 版从未测试——与 YPxOGboo 构成包装 A/B, 分离 "
        "group_rank 对低 TO 振幅基座的边际效应 (price 族 group_rank 杀 Sh, 振幅族待测); 同时"
        "与槽1 分离 ts_rank250 对 bf60 基座的边际 (2Y 修复器是否必需)。")},
    {"id": 3, "type": "AMP_PER_CNT_TSRANK250", "expression":
        f"reverse(ts_rank(divide({AMP}, {CNT}), 250))",
     "optimize_reason": (
        "每关注度振幅 x 极端度。机制: 单位关注度的上偏强度取 250 日自身分位——'相对该股历史"
        "异常的关注度稀缺度'; Y 批只测了 bf60 包装版 (全灭), 无回填的极端度版未测。与槽1 "
        "分离计数归一化的边际贡献 (归一在 price 族是 Sh 提升器, 对振幅族待测)。")},
    {"id": 4, "type": "VECMAX_CVW_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {VWAP}), vec_max({VHEX})), 250))",
     "optimize_reason": (
        "新 Sh 记录基座 x 极端度 (B 子方向主攻)。机制: B1 槽4 VECMAX_DEN_CVW 的 reverse 等效 "
        "Sh +1.68 是全场新记录 (冠军 d5K6wxlx 1.61), 但 2Y 仅 1.19/TO128.5%/DD78%。配 "
        "ts_rank250 攻 2Y——若 2Y 修复到 >=1.58, 得 Sh1.68+2Y 双优基座, 剩 TO+Fit 两墙且 TO "
        "是唯一未在新结构上测过管理算子的轴。若 ts_rank 后 Sh 保持 1.5+, 这是迄今最强的"
        "单点改进方向。")},
    {"id": 5, "type": "VECAVG_CTN_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {TON}), vec_avg({VHEX})), 250))",
     "optimize_reason": (
        "vec_avg 分母 x CTN x 极端度。机制: 与槽4 构成 vec_max vs vec_avg 的口径对照 (B1 两者"
        "reverse 等效 Sh 1.68/1.44); CTN 分子的 2Y 持续性 (2.07-2.35) 配 vec_avg 分母的跨股"
        "可比性, 极端度去政权。若 2Y 与 Sh 同时高于槽4, vec_avg 口径胜出。")},
    {"id": 6, "type": "AMP_PER_CNT_RANK", "expression":
        f"reverse(rank(divide({AMP}, {CNT})))",
     "optimize_reason": (
        "每关注度振幅 plain rank (无回填无极端度, 对照臂)。机制: Y 批只测了 bf60+group_rank "
        "包装 (全灭), 分离'每关注度归一'与'回填包装'的边际——若 plain 版显著强于 bf60 版, "
        "则 Y 批全灭是回填之罪而非归一之罪 (归一名声需平反); 若 plain 也死, 每关注度口径在"
        "振幅族彻底出局。")},
    {"id": 7, "type": "HARDGATE_GE1_AMP_REV", "expression":
        f"trade_when(greater(vec_count({VHEX}), 0), reverse(rank({AMP})), 0)",
     "optimize_reason": (
        "硬事件门 x 振幅 (门控成本曲线的振幅族点)。机制: B1 槽1 硬门 x CTN 的 reverse 等效 "
        "Sh +0.93/TO39.7%——门控机械砍 TO 但信号强度减半; 振幅族本身稀疏 (非事件日 NaN), "
        "硬门对它是近空转 (门只砍本就没仓位的日子), 因此若门后 Sh 保持 ~1.2 而 TO 仍 37%, "
        "证明门控成本只在全日填充族上发生——这是'门控 x 稀疏分子'的免费 TO 红利假说。")},
    {"id": 8, "type": "HARDGATE_GE1_CVW_REV", "expression":
        f"trade_when(greater(vec_count({VHEX}), 0), reverse(rank(divide(subtract({EOC}, {VWAP}), {CNT}))), 0)",
     "optimize_reason": (
        "硬事件门 x CVW 冠军分子 (门控成本曲线的第二点)。机制: B1 槽1 硬门 x CTN 的 reverse "
        "等效 Sh +0.93/TO39.7% (门控机械砍 TO 但信号减半); 本槽把同一硬门应用到冠军分子族 "
        "(close-vwap, 锚 Sh1.63) —— 若 CVW 门后 Sh 保持 >=1.4 而 TO<=50%, 门控成本是分子依赖"
        "的且冠军分子可挽救; 若同样腰折, 则门控成本曲线与分子无关 (结构性常数), 门控路线"
        "正式关闭。与槽7 (硬门 x 振幅, 稀疏族免费红利假说) 构成门控 x 三分子族的完整成本"
        "矩阵 (CTN 已测 / CVW 本槽 / 振幅槽7)。")},
]

DIRECTIONS = {
    "S2": {"name": "振幅族拯救 + 新记录基座 + 门控成本矩阵 (B1 条件分化批)", "hypothesis":
           "振幅族 (TO 天然低 37%) x ts_rank250 极端度 (已验证 2Y 修复器) 的首次结合攻其仅存"
           "短板 2Y 0.68-0.79; B1 新 Sh 记录基座 (VECMAX reverse 等效 1.68) 配极端度攻 2Y; "
           "硬事件门 x 三分子族 (CTN/CVW/振幅) 的完整成本矩阵判定门控路线生死",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_S2},
}

STAGGER_SECONDS = {"S2": 0}


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


async def submit_one(it: dict, state_path: str, universe: str, default_neut: str, tag: str):
    """单条提交 (支持 per-item neutralization override)."""
    neut = it.get("neutralization", default_neut)
    location = None
    for attempt in range(1, 6):
        try:
            sub = await BrainModule.submit_multi_simulation(
                alpha_expressions=[it["expression"]], region=REGION, universe=universe, delay=DELAY,
                decay=DECAY, neutralization=neut, truncation=TRUNCATION,
                pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                language="FASTEXPR", visualization=False)
            if "error" in sub:
                raise RuntimeError(f"submit error: {sub}")
            location = sub["location"]
            with open(state_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"slot": it["id"], "neut": neut, "location": location,
                                    "submitted_at": int(time.time())}) + "\n")
            print(f"[submit-{tag}-slot{it['id']}] OK neut={neut} location={location}", flush=True)
            break
        except Exception as e:
            print(f"[submit-{tag}-slot{it['id']}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    return location


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


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave9-B2] 字段字典 {len(known_fields)} 个装载", flush=True)

    direction = "S2"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W9_{direction}_{s['id']}", "question_type": s["type"],
              **({"neutralization": s["neutralization"]} if "neutralization" in s else {})}
             for s in d["slots"]]
    assert len(items) == 8, f"{direction} 批必须 8 槽"
    print(f"\n[Wave9-B2-{direction}] {d['name']}", flush=True)
    print(f"[Wave9-B2-{direction}] 假说: {d['hypothesis']}", flush=True)
    preaudit(items, known_fields)
    check_dup_fingerprints(items, d["neutralization"], d["universe"])

    ts = int(time.time())
    # 分批提交: 同 neutralization 的槽合批 multi_create_simulate ( mandate: 一次一批 8 条;
    # slot8 为 SUBINDUSTRY settings 探针, 单独成批——settings 不同的 expression 不能混批)
    groups = {}
    for it in items:
        neut = it.get("neutralization", d["neutralization"])
        groups.setdefault(neut, []).append(it)
    locations = {}
    for neut, grp in groups.items():
        state_path = os.path.join(CAMPAIGN, f"state_gate9_{direction}_{neut}.json")
        batch_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{neut}_{ts}.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields,
                       "neutralization": neut, "items": grp}, f, ensure_ascii=False, indent=1)
        corrected = SimBatchRunner.validate_and_pack_batch(grp, known_fields, CATEGORY, REGION,
                                                           d["universe"], DELAY, neut)
        for it, ce in zip(grp, corrected):
            it["expression"] = ce
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields,
                       "neutralization": neut, "items": grp}, f, ensure_ascii=False, indent=1)
        print(f"[Wave9-B2-{direction}] 批次文件 ({neut}, {len(grp)} 条): {batch_path}", flush=True)
        try:
            loc = await submit_batch_group(grp, state_path, neut, d["universe"], f"{direction}_{neut}")
            locations[neut] = loc
        except Exception as e:
            purge_fingerprints([it["expression"] for it in grp], neut, d["universe"])
            print(f"[Wave9-B2-{direction}] FATAL submit ({neut}): {e}", flush=True)
            raise
        await asyncio.sleep(15)

    # 轮询各批
    done = {}
    while len(done) < len(locations):
        for neut, loc in list(locations.items()):
            if neut in done:
                continue
            try:
                chk = await BrainModule.check_multi_simulation(loc)
                st = chk.get("status")
                print(f"  [poll-{neut}] {st} progress={chk.get('progress', 0)}", flush=True)
                if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                    done[neut] = st
            except Exception as e:
                print(f"  [poll-{neut}] error: {str(e)[:150]}", flush=True)
            await asyncio.sleep(5)
        await asyncio.sleep(20)

    all_results = []
    for neut, loc in locations.items():
        fetch = await BrainModule.fetch_multi_simulation_result(loc)
        results = fetch.get("alpha_results", [])
        if not results:
            print(f"[Wave9-B2-{neut}] fetch 空! {str(fetch)[:300]}", flush=True)
            continue
        batch_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{neut}_{ts}_result.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
        print(f"[Wave9-B2-{neut}] 结果已存: {batch_path}", flush=True)
        all_results.extend(results)

    # 按 items 顺序对齐 (结果顺序应与提交顺序一致; slot8 的 SUBINDUSTRY 批单独)
    by_code = {}
    for r in all_results:
        by_code[r.get("code", "")] = r
    ordered = []
    for it in items:
        r = by_code.get(it["expression"])
        if r is None:
            # 纠偏后的表达式可能被 corrector 改写, 退化为按顺序
            ordered.append({"alpha_id": None, "code": it["expression"], "metrics": {}, "ra": {}, "checks": {}})
        else:
            ordered.append(r)
    if len(ordered) != len(items):
        print(f"[Wave9-B2] 警告: 结果对齐异常 {len(ordered)} vs {len(items)}", flush=True)
    summary = build_summary(items, ordered, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate9_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave9-B2-{direction}] 汇总已存: {sum_path}", flush=True)
    print("\n[Wave9-B2] 批次回收完毕。", flush=True)


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


if __name__ == "__main__":
    asyncio.run(main())
