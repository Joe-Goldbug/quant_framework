# -*- coding: utf-8 -*-
"""Gate1 Wave9-B1 结构发现批 (2026-10-24 深夜).

Wave8 判决 (24 槽) + 红队独立审查后的继续战役 ( mandate: 锚 N1eGk79E, 零 fail 零警告,
每批 8 条 multi_create_simulate; 未成功不许中断; 禁提交).

Wave8 判决: T ts_mean 平滑通杀 (冠军基座 mean10 -> 2Y -0.47, 完全依赖日度新鲜度);
  bf60 x COPEN rank 幸存但 2Y 塌 (Sh1.07/TO40.6%/R-TO0.114 新高/2Y0.99); N 组内化攻 CW
  全线证伪 (冠军组内化 Sh0.42); G 门控对慢变分子空转机理查明 (TON/OPEN 非事件日有值,
  TO 113%->112.8% —— 门控只砍 NaN 仓位) = 红队'分子分母频率错配'断点的直接实证.

红队独立审查核心裁决 (全盘接受):
  1. P 增量通式 (bl8Wd2Nq 迁移) 机理不可迁——形可迁机理不可迁: TON/OPEN 日更流量非稀疏
     水平量, 减自身 ts_mean = 二阶差分放大噪声; 无稀疏性 -> TO 必停 100%+. 份额 8->2.
  2. X settings 消融 8->1 (仅 SUBINDUSTRY x 幸存者留 B2; nan_handling/TOP500/MARKET cut).
  3. 🔴 关键 insight (主编盲区): CNT 的 +1 与 ANCHOR_DEN 的 ts_backfill 恰是杀死稀疏性、
     养出 TO116.9% 与 CW 的根因——家族一直在工程修复'NaN 太多', 而稀疏本身就是低 TO 的
     来源. vec_avg/vec_max 量级分母一个改动同时打 TO/CW/2Y 三靶: 无 +1 无 backfill ->
     无事件日分母 NaN -> 天然稀疏 (自带门控); 无陈旧值 -> 不招 CW; 连续分母消除 CNT
     整数剧变的频率错配.
  4. 门控的正确用法: 前两轮门控砍 NaN 所以空转; 门必须咬 vec_count 结构 (硬事件门 /
     慢注意力尖峰门), 慢门翻转少, flat 日零换手. trade_when 第三参用 0 (硬平仓) 替代 -1.

Wave9-B1 = 结构发现批 (红队 alternative_slots 全 8 槽): 三个结构杠杆 (咬计数结构的门控 /
vec_avg-vec_max 量级分母 / ts_rank 自历史归一化) + P 证伪槽 + CTH 新分子几何.
B2/B3 按 B1 结果条件分化 (红队预案: 门控咬住 -> 门控成本曲线; vec_avg 胜出 -> 分子/镜像
扩展; 1 槽 SUBINDUSTRY x 幸存者; 幸存者全因子扫描).

平台风险: A3/A4 无 +1 分母, vec_avg/vec_max 对空向量若返回 0 会除错 (单条 ERROR 不 CANCEL
兄弟槽); A1/A2 显式 trade_when 门控是不依赖 NaN 语义的平行主路径.
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
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"      # 锚式低噪声分母
DFLC = f"days_from_last_change(vec_count({VHEX}))"       # 距上次事件计数变化的天数
SLOWGATE = f"greater(vec_count({VHEX}), ts_mean(vec_count({VHEX}), 20))"  # 慢注意力尖峰门

# ================================================================ 方向 S: 结构发现 (红队 alternative_slots 全 8 槽)
DIR_S = [
    {"id": 1, "type": "HARDGATE_GE1_CTN_RANK", "expression":
        f"trade_when(greater(vec_count({VHEX}), 0), rank(divide(subtract({EOC}, {TON}), {CNT})), 0)",
     "optimize_reason": (
        "硬事件门 x CTN (红队 A1, 全场最高 EV 槽)。机制: 仅在有 >=1 次高波 excursion 事件的"
        "日子持仓, 其余硬平仓 (第三参 0)——前两轮门控砍 NaN 所以空转 (慢变分子非事件日有值), "
        "此门咬的是事件计数结构本身, 与全日填充分子真正互补; 关注度稀缺反转的收益应集中于"
        "事件日, 门控理论上不掉收益而机械砍 TO。最坏情况 (收益均匀分布) Sh/Fit 不变, 最好"
        "情况 R/TO 数量级改善——非对称盈亏。CNT 的 +1 在门内无害 (门保证 vec_count>=1 时分母>=2)。")},
    {"id": 2, "type": "SLOWGATE_ATTN_CTN_RANK", "expression":
        f"trade_when({SLOWGATE}, rank(divide(subtract({EOC}, {TON}), {CNT})), 0)",
     "optimize_reason": (
        "慢注意力尖峰门 x CTN (红队 A2)。机制: 只在新闻强度超过自身 20 日均值 (注意力尖峰) "
        "的日子持仓——尖峰日 = 定价错误最严重、反转收益最集中日; 慢门 (ts_mean20 基准) 翻转"
        "少, flat 日零换手, TO 有机械下降。与槽1 共同标定门控成本曲线 (硬门 vs 慢门); "
        "'门控空转'机理的反向利用: 门必须慢于信号才能真正咬合。")},
    {"id": 3, "type": "VECAVG_DEN_CTN_RANK", "expression":
        f"rank(divide(subtract({EOC}, {TON}), vec_avg({VHEX})))",
     "optimize_reason": (
        "vec_avg 量级分母 x CTN (红队 A3, 三靶齐击)。机制: 每单位平均冲击振幅对应的事件后"
        "漂移 = 标准化异常漂移, 跨股跨日可比, 直接攻 R/TO。vec_avg 无 +1 无 backfill: 无事件"
        "日分母 NaN -> 天然稀疏 (自带门控, 这是低 TO 的结构来源); 无陈旧值 -> 不招 CW; "
        "连续振幅分母消除 CNT 整数剧变的频率错配 (红队断点实证的直接修复)。风险: 空向量"
        "返回 0 则除错 (单条 ERROR 不 CANCEL 兄弟槽; 若 ERROR, B2 补 +1 版)。")},
    {"id": 4, "type": "VECMAX_DEN_CVW_RANK", "expression":
        f"rank(divide(subtract({EOC}, {VWAP}), vec_max({VHEX})))",
     "optimize_reason": (
        "vec_max 同源归一化 x CVW 冠军分子 (红队 A4)。机制: 家族 Sh 最高分子 (close-vwap, "
        "锚 Sh1.63) x 当日最大冲击振幅——同日同源归一化, 漂移以主导冲击为单位, 横截面意义最"
        "干净; vec_max 强调主导事件, 与槽3 均值版形成口径对照。给冠军分子换分母是边际收益"
        "最大的单点改动。")},
    {"id": 5, "type": "CTH_PER_CNT_RANK", "expression":
        f"rank(divide(subtract({EOC}, {TH}), {CNT}))",
     "optimize_reason": (
        "CTH 新分子几何 (红队 A5, R 批保留项)。机制: 新闻时高点 TH 到收盘 EOC 的回撤 = 高位"
        "派发/反转几何, 信息集与 TON/OPEN/VWAP 互补; 高波 excursion 事件制造事件时高点, 收盘"
        "深于该高点是最直接的反转证据。5 ops 极便宜且真正未测 (W8 双 rank 死/N3 ts_rank "
        "Sh0.99 但 2Y2.20); 若与 TON 版高度相关则证明家族几何已饱和——该信息本身有决策价值。")},
    {"id": 6, "type": "TSRANK_OUTER_CTN_RANK", "expression":
        f"rank(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 250))",
     "optimize_reason": (
        "ts_rank250 自历史归一化 x CTN (红队 A6, P 方向的最优替代)。机制: 当日每事件漂移在"
        "该股自身 250 日分布中的分位 = regime 自适应异常度, 直服 2Y>=1.58。对 P 的'减自身 5 "
        "日均值'是严格更优替代: 有界 [0,1]、单阶差分 (无二阶噪声放大)、无符号过零不稳定; "
        "外层 plain rank (组内化已证杀 Sh)。与 W4 (无外层 rank) 构成包装对照。")},
    {"id": 7, "type": "P_INCREMENT_CTN_N5_RANK", "expression":
        f"rank(subtract(divide(subtract({EOC}, {TON}), vec_count({VHEX})), "
        f"ts_mean(divide(subtract({EOC}, {TON}), vec_count({VHEX})), 5)))",
     "optimize_reason": (
        "P 方向证伪槽 (红队 A7 / 蓝队 P1 原式, 便宜的方向保险)。机制: bl8Wd2Nq 通式的最温和"
        "迁移 (N=5, TON 分子, plain rank 外层, 无 reverse; 分母用裸 vec_count——+1 版需 11 ops "
        "超 mandate, 若出 CW/除零问题 B2 再回退)。红队裁决 P 机理不可迁 (日更流量减自身均值 = "
        "二阶差分放大噪声; 无稀疏性 -> TO 必停 100%+), 但用 1 槽正式裁决: 若本槽 TO 仍 >90% "
        "则 P 全方向判死、B2 槽位释放; 若意外达标 (Sh>=1.5 且 TO<=70%) 则 P 升级主攻。")},
    {"id": 8, "type": "SLOWGATE_ATTN_CVW_RANK", "expression":
        f"trade_when({SLOWGATE}, rank(divide(subtract({EOC}, {VWAP}), {CNT})), 0)",
     "optimize_reason": (
        "慢注意力尖峰门 x CVW 冠军分子 (红队 A8)。机制: 若槽2 门控咬住 TO 但 Sh 塌陷 (CTN "
        "分子 Sh 仅 1.41), 此槽用冠军分子 (锚 Sh1.63) 保 Sharpe; 与槽2 共同给出门控下分子"
        "选择成本曲线, 是 B2 分叉的决策依据 (门控 x CTN vs 门控 x CVW 的 Sh/TO 交换率)。")},
]

DIRECTIONS = {
    "S": {"name": "结构发现 (红队 alternative_slots 全 8 槽)", "hypothesis":
           "CNT 的 +1 与 ANCHOR_DEN 的 ts_backfill 是杀死稀疏性/养出 TO 与 CW 的根因; 三个结构"
           "杠杆首次测试: 咬 vec_count 结构的门控 (硬事件门/慢注意力尖峰门, 第三参 0 硬平仓) / "
           "vec_avg-vec_max 量级分母 (天然稀疏+无陈旧+同源同频) / ts_rank 自历史归一化 (P 的"
           "严格更优替代); 外加 P 证伪槽与 CTH 新分子几何",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_S},
}

STAGGER_SECONDS = {"S": 0}


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
        fixed = corrector.correct_expression(it["expression"])
        h = corrector.compute_fingerprint(fixed, REGION, universe, DELAY, neutralization)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        row = cur.fetchone()
        if row:
            dups.append((it["id"], it["expression"][:60]))
    conn.close()
    if dups:
        print(f"  [dup-check] 历史已测 {len(dups)} 条 (<=2/批合法): {dups}", flush=True)
    if len(dups) > 2:
        raise ValueError(f"批次内历史重复 {len(dups)} 条 > 2, 防摸鱼门禁将拒: {dups}")


async def submit_batch(items: list, state_path: str, neutralization: str, universe: str, tag: str):
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
                    alpha_expressions=exprs, region=REGION, universe=universe, delay=DELAY,
                    decay=DECAY, neutralization=neutralization, truncation=TRUNCATION,
                    pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                    language="FASTEXPR", visualization=False)
                if "error" in sub:
                    raise RuntimeError(f"submit error: {sub}")
                location = sub["location"]
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump({"location": location, "submitted_at": int(time.time()),
                               "universe": universe, "neutralization": neutralization}, f)
                print(f"[submit-{tag}] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
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
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
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
    print(f"[Wave9-B1] 字段字典 {len(known_fields)} 个装载", flush=True)

    direction = "S"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W9_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8, f"{direction} 批必须 8 槽"
    print(f"\n[Wave9-B1-{direction}] {d['name']}", flush=True)
    print(f"[Wave9-B1-{direction}] 假说: {d['hypothesis']}", flush=True)
    preaudit(items, known_fields)
    check_dup_fingerprints(items, d["neutralization"], d["universe"])

    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{ts}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate9_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION,
                                                       d["universe"], DELAY, d["neutralization"])
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W9_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave9-B1-{direction}] 批次文件: {batch_path}", flush=True)

    loc = await submit_batch(items, state_path, d["neutralization"], d["universe"], direction)
    if not loc:
        print("[Wave9-B1] 无 location, 退出", flush=True)
        return

    # 轮询
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(loc)
            st = chk.get("status")
            print(f"  [poll-{direction}] {st} progress={chk.get('progress', 0)}", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                break
        except Exception as e:
            print(f"  [poll-{direction}] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)

    fetch = await BrainModule.fetch_multi_simulation_result(loc)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[Wave9-B1-{direction}] fetch 空! {str(fetch)[:300]}", flush=True)
        return
    batch_path = os.path.join(CAMPAIGN, f"batch_gate9_{direction}_{ts}_result.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave9-B1-{direction}] 结果已存: {batch_path}", flush=True)
    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate9_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave9-B1-{direction}] 汇总已存: {sum_path}", flush=True)
    print("\n[Wave9-B1] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
