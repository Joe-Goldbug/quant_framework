# -*- coding: utf-8 -*-
"""Gate1 Wave10-G · neutralization=SUBINDUSTRY 首次扫描 —— CW 墙的最后一击.

=== 为什么这是 CW 的最后一击 ===
  历史 neutralization 分布: INDUSTRY 192 / MARKET 16 / STATISTICAL 8, **SUBINDUSTRY 从未测过**
  (此前"SUBINDUSTRY 有害"的结论指的是**算子** group_neutralize(x, subindustry), 与 settings 层的
  neutralization 选项是完全不同的东西, 不能混为一谈).
  neutralization 计入 fingerprint, 故换 SUBINDUSTRY 不与任何历史冲突.

  CW (CONCENTRATED_WEIGHT <= 0.1) 是本次 mandate 四项 FAIL 中唯一尚未找到通用解法的墙:
    - Wave10-D/E 确认 trade_when 硬门只在**特定结构**上消除 CW (U/(U+D) 与 CVW/(cnt+1) 上有效,
      但在 SH165 的 CTO/bf120 上无效 —— 槽1/3/4/5 全部仍 CW FAIL)
    - Wave10-F 确认扩大 universe (TOP3000) 把持仓面翻倍 (299->658) 也**未能**消除 CW
      ==> CW 与"持仓面/池子规模"不是单调关系, 而是**权重分布的集中程度**,
          其最直接的控制手段就是中性化分组的粒度: 分组越细, 组内残差权重越分散.
  SUBINDUSTRY 把中性化从 行业级(~24 组) 细化到 子行业级(~100+ 组), 是 CW 的天然解药,
  且它**不改变信号一字, 不消耗任何 op 预算**.

=== 本批设计 ===
  8 条家族最具代表性的资产原样在 SUBINDUSTRY 下重跑, 每条都有精确的 INDUSTRY 基线可配对:
    1 SH165 新纪录 (Sh1.65/Ret7.86/2Y2.10/TO119.8/CW fail)
    2 锚 N1eGk79E (Sh1.63/CW fail) —— 用户 mandate 的起点
    3 d5K6wxlx (Sh1.61/Fit0.41/CW fail)
    4 MP0n61ra-reverse (|Sh|1.68 天花板/CW fail)
    5 Wave10-E 槽8 decay_linear U/D (Sh1.28/CW 未报)
    6 Wave10-E 槽2 SH165+ts_decay_linear20 (Sh1.14/TO86.4/CW fail)
    7 Wave10-E 槽3 SH165+ts_mean5 (Sh0.85/TO30.0/**CW ok**) —— 唯一的 TO 过门成员
    8 pooled 高 R/TO (R-TO0.403/TO5.2%/**CW ok**)
  配对可分离出"INDUSTRY -> SUBINDUSTRY"的纯处理效应 (Sh/Fit/TO/CW/2Y 各自的变化).

=== 判读标准 ===
  (a) 若某条的 CW 由 fail 转 pass 且 Sh 损失 <10% => CW 墙破解, 该条即进入"仅剩 Fit/TO"的状态;
  (b) 若 CW 仍 fail => CW 与中性化粒度无关, 应改攻权重分布本身 (本战役则需在报告中如实登记
      CW 为结构性墙);
  (c) 顺带记录 sub_universe_sharpe 在 SUBINDUSTRY 下的变化 (Wave10-F 已观察到更细/更大的
      横截面会显著抬 sub, SUBINDUSTRY 若同向则有利于 sub 门槛).

=== mandate ===
  2<=字段数<=3 | op 数不限 | 仅 multi_create_simulate 每批 8 条 | 严禁提交
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

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY, REGION, DELAY = "news", "USA", 1
UNIVERSE = "TOP1000"
NEUT = "SUBINDUSTRY"  # ★ 本批唯一新变量 (历史从未测过该 settings 选项)
DECAY = 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
BF120 = f"ts_backfill({CN}, 120)"
CTO = f"subtract({EOC}, {TON})"
CVW = f"subtract({EOC}, {VWAP})"
RATIO = f"divide({CTO}, {BF120})"
DFLC2 = f"less(days_from_last_change({CN}), 2)"

SLOTS = [
    {
        "id": 1, "type": "SH165_AT_SUBIND", "role": "PAIR", "baseline": "Sh1.65/Ret7.86/2Y2.10/TO119.8/CW fail",
        "expression": f"trade_when({DFLC2}, reverse(rank({RATIO})), 0)",
        "optimize_reason": (
            "【本批头号槽】全族新纪录资产 SH165 搬到 SUBINDUSTRY 中性化. 它是唯一同时做到 "
            "Sh 1.65 (>=1.58 过线) + Ret 7.86% (全族最高) + 2Y 2.10 (>=1.58 过线) + sub 1.30 的资产, "
            "仅剩 Fit 0.42 / TO 119.8% / CW 三墙. 已反解: 固定 Sh=1.65 与 Ret=7.86% 时, "
            "**只需 TO <= 21.4% 即 Fit>=1**. 其 CW fail 在 TOP1000 与 TOP3000 下都成立 "
            "(持仓面 299/294 与 658/647), 说明不是池子规模问题. 本槽检验更细的中性化粒度能否"
            "打散其权重集中度 —— 若 CW 转 pass, 则该资产仅剩 TO/Fit 两墙, 是本战役最接近达标的状态."),
    },
    {
        "id": 2, "type": "ANCHOR_AT_SUBIND", "role": "PAIR", "baseline": "N1eGk79E Sh1.63/TO116.9/2Y0.58/CW fail",
        "expression": f"reverse(rank(divide({CVW}, {BF120})))",
        "optimize_reason": (
            "【用户 mandate 的起点锚】N1eGk79E 原样搬到 SUBINDUSTRY. 用户明确要求在该 alpha 基础上"
            "继续优化, 四项 FAIL 为 Fit 0.31 / TO 116.9% / CW / 2Y 0.58. 本槽是对'锚在更细中性化下"
            "会怎样'的直接回答: 若 SUBINDUSTRY 能同时消 CW 与抬 2Y (锚的 2Y 0.58 是四项中最弱的一环), "
            "则本次 mandate 在未改任何算子的前提下即取得实质进展, 这对用户最重要."),
    },
    {
        "id": 3, "type": "D5K6WXLX_AT_SUBIND", "role": "PAIR", "baseline": "Sh1.61/Fit0.41/2Y2.09/CW fail",
        "expression": f"reverse(rank({RATIO}))",
        "optimize_reason": (
            "【家族历史最佳 Fitness】d5K6wxlx (Fit 0.41 家族最高) 搬到 SUBINDUSTRY. 它是 SH165 去掉"
            "新鲜度门后的裸版, 与槽1 构成'门的有无 x 中性化粒度'二乘二设计的一角, "
            "可用于分离 frescura 门效应是否依赖中性化粒度. 其 ProdCorr 0.7033 仅超限 0.0033 —— "
            "更细的中性化会改变持仓结构, 相关性也可能随之改变, 本槽顺带检验这一点."),
    },
    {
        "id": 4, "type": "MP0N61RA_AT_SUBIND", "role": "PAIR", "baseline": "|Sh|1.68 天花板/CW fail",
        "expression": f"reverse(rank(divide({CVW}, vec_max({VHEX}))))",
        "optimize_reason": (
            "【Sharpe 天花板资产】MP0n61ra 的 reverse 生产版搬到 SUBINDUSTRY. 其分母 vec_max(VHEX) "
            "是当日最大冲击振幅、天然稀疏 (L/S 268/268), 是 CW fail 的典型形态. 本槽检验: "
            "在把中性化细化到子行业后, 稀疏分母型资产的权重能否被打散. 这是 CW 是否可被"
            "'中性化粒度'这一纯 settings 手段解决的判别性样本."),
    },
    {
        "id": 5, "type": "DECAYLIN_UD_AT_SUBIND", "role": "PAIR", "baseline": "W10E槽8 Sh1.28/Ret5.42/2Y1.40",
        "expression": f"reverse(rank(divide(ts_decay_linear({U}, 60), add(ts_decay_linear({U}, 60), ts_decay_linear({D}, 60)))))",
        "optimize_reason": (
            "【Wave10-E 最大意外 x SUBINDUSTRY】用 ts_decay_linear 替代等权 boxcar 池化, 把同一结构的 "
            "Sharpe 从 0.61 抬到 1.28 (+2.1x), 证实了'长记忆实现 vs 短记忆机制'的矛盾是真问题且可修. "
            "它目前 TO 107.4%、持仓面 247/247. 本槽检验更细中性化对它是否既有分散作用又能保住"
            "这份来之不易的 1.28 Sharpe. 它是家族信息含量最新鲜的一条线, 值得优先在新 setting 下复现."),
    },
    {
        "id": 6, "type": "SH165_DECAYLIN20_AT_SUBIND", "role": "PAIR", "baseline": "W10E槽2 Sh1.14/TO86.4/CW fail",
        "expression": f"trade_when({DFLC2}, reverse(rank(ts_decay_linear({RATIO}, 20))), 0)",
        "optimize_reason": (
            "【当前最优 Sh/TO 权衡点】Wave10-E 槽2 是 SH165 家族中保留 Sharpe 最多的降 TO 变体 "
            "(Sh 1.14 / TO 86.4% / Ret 4.57% / 2Y 1.92 —— 2Y 已过线). 它是'渐进降 TO'路径上目前走得"
            "最远的一格. 搬到 SUBINDUSTRY 的目的: 若 CW 转 pass 且 Sharpe 保持在 1.1+, "
            "则它就是本战役'已过 2Y 与 CW 两墙、只差 TO 与 Fit'的最佳形态, 后续只需继续沿"
            "平滑强度细分 (decay_linear 40/60) 即可逼近 TO 70% 门."),
    },
    {
        "id": 7, "type": "SH165_TSMEAN5_AT_SUBIND", "role": "PAIR", "baseline": "W10E槽3 Sh0.85/TO30.0/CW ok",
        "expression": f"trade_when({DFLC2}, reverse(rank(ts_mean({RATIO}, 5))), 0)",
        "optimize_reason": (
            "【唯一 TO 已过门的成员】Wave10-E 槽3 是 SH165 家族中唯一把 TO 压到 30% (过 <=70% 门) 且 "
            "**不触发 CW** 的变体 (Sh 0.85 / Ret 3.99% / R-TO 0.133), 唯一短板是 Sh 0.85 与 2Y 0.16. "
            "搬到 SUBINDUSTRY 检验更细中性化能否补上它缺的 Sharpe —— 若 Sh 能抬到 1.0+ 而 TO 与无 CW "
            "两项优点保持, 则它成为家族唯一'TO 过门 + 无 CW'双达标资产, 后续只需攻 Sharpe 一项."),
    },
    {
        "id": 8, "type": "POOLED_HIGH_RTO_AT_SUBIND", "role": "PAIR", "baseline": "R-TO0.403/Mgn8.04/TO5.2/CW ok",
        "expression": f"reverse(ts_rank(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))), 250))",
        "optimize_reason": (
            "【家族 R/TO 最高资产】Wave10-A 槽6 是家族唯一跳出 R/TO 包络的样本 "
            "(R/TO 0.403 = 包络 0.125 的 3.2x; Mgn 8.04bps = 历史最高的 6.3x; TO 5.2% 已在 "
            "turnover floor 保护区内; L/S 516/512 天然无 CW), 唯一短板是 Sh 0.61. "
            "搬到 SUBINDUSTRY 后其横截面分位估计的组内分布应当更平滑, 可能抬 Sharpe. "
            "本槽是全批唯一同时具备 '最低 TO + 最高 R/TO + 已无 CW' 三条属性的资产, "
            "若更细中性化能补上它缺的 Sharpe, 它是最接近达标区的形态."),
    },
]

DIRECTIONS = {
    "G": {"name": "neutralization=SUBINDUSTRY 首次扫描 — CW 墙最后一击", "hypothesis": (
        "CW 是本次 mandate 四项 FAIL 中唯一未找到通用解法的墙: trade_when 硬门只在特定结构上有效 "
        "(在 SH165 上无效), 扩大 universe 到 TOP3000 把持仓面翻倍也未能消除 CW "
        "==> CW 不是持仓面/池子规模的函数, 而是权重分布集中度的函数, 其最直接的控制手段是 "
        "中性化分组粒度. 历史从未测过 settings 层的 SUBINDUSTRY 中性化 "
        "(INDUSTRY 192 / MARKET 16 / STATISTICAL 8; 此前所谓 SUBINDUSTRY 有害指的是算子 "
        "group_neutralize, 与 settings 选项不是同一事物). 本批把 8 条家族代表性资产原样搬到 "
        "SUBINDUSTRY, 构成纯 settings 配对实验分离处理效应."),
        "universe": UNIVERSE, "neutralization": NEUT, "slots": SLOTS},
}


def purge_fingerprints(exprs, neutralization, universe):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        h = corrector.compute_fingerprint(corrector.correct_expression(e), REGION, universe, DELAY, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n}", flush=True)


def preaudit(items, known_fields):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
           "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
           "ts_delta", "ts_decay_linear", "ts_decay_exp_window", "trade_when", "greater", "less",
           "if_else", "vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev",
           "days_from_last_change", "industry", "subindustry", "sector", "market",
           "sign", "abs", "sqrt", "log", "power"}
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        it["expression"] = fixed
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        nf = len(tokens & known_set)
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']:>2} fields={nf} "
              f"len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:70]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符: {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= nf <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {nf} 违反 mandate (2<=字段数<=3)")
        if len(fixed) > 900:
            raise ValueError(f"slot{it['id']} 超长 {len(fixed)} > 900")
        if len(it["optimize_reason"]) < 120:
            raise ValueError(f"slot{it['id']} optimize_reason 过短, 违反铁律5")


async def main():
    raw = json.load(open(FIELDS_FILE, encoding="utf-8"))
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    d = DIRECTIONS["G"]
    print(f"[Wave10-G] 字段字典 {len(known_fields)} | universe={UNIVERSE} neut={NEUT} decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10G_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-G] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10G", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10g_{ts}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    loc = None
    for attempt in range(1, 6):
        try:
            sub = await BrainModule.submit_multi_simulation(
                alpha_expressions=[it["expression"] for it in items], region=REGION,
                universe=d["universe"], delay=DELAY, decay=DECAY,
                neutralization=d["neutralization"], truncation=TRUNCATION,
                pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                language="FASTEXPR", visualization=False)
            if "error" in sub:
                raise RuntimeError(str(sub)[:160])
            loc = sub["location"]
            print(f"[submit-G] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-G] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-G] 静默轮询中 (前 60s 不输出)...", flush=True)
    waited = 0
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(loc)
            st = chk.get("status")
            if waited >= 60:
                print(f"  [poll] {st} t={waited}s", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                break
        except Exception as e:
            print(f"  [poll] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)
        waited += 20

    results = (await BrainModule.fetch_multi_simulation_result(loc)).get("alpha_results", [])
    if not results:
        print("[Wave10-G] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10g_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-G (universe={UNIVERSE}, neut={NEUT}, decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>12} {'DD%':>6} {'CW':>5}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        cw = "FAIL" if "CONCENTRATED_WEIGHT" in names else "ok"
        print(f"{it['id']:>2} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} {to * 100:>7.1f} "
              f"{ret * 100:>7.2f} {(ret / to) if to else 0:>7.3f} {(m.get('margin') or 0) * 1e4:>7.2f} "
              f"{m.get('two_year_sharpe') or 0:>6.2f} {m.get('sub_universe_sharpe') or 0:>5.2f} "
              f"{m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>12} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f} {cw:>5}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave10-G] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
