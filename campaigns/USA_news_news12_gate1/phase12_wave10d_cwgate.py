# -*- coding: utf-8 -*-
"""Gate1 Wave10-D · CW 解法 x 家族最高质量资产 的首次交叉 (decay=6).

=== Wave10-A/B/C 三批的净结算 ===

[A] decay 维度: 对日频快结构无降 TO 作用 (配对比值 0.974/0.984/1.050); 对已慢结构仍有
    ×0.59 降 TO 作用, 但同比例杀 Sh. => 不是通往达标区的路径, 关闭.
[B] pooled 结构五维展开: N=120 未翻负 => 邻域稳定, 非孤峰; 金额/百分比口径等价 => 无量纲污染;
    ts_rank 层把 Sharpe 抬 ×3.4 (0.14->0.48); U/D 分子不可替代.
[C] ★ 关键负面: ts_rank 层向三条存活分支迁移全部失败 ——
      S2-槽7   Sh 1.17 -> 0.98
      6XAQKZgK Sh 1.07 -> 0.46
      YPxOGboo Sh 1.17 -> 0.70
    ==> **ts_rank 不是通用增益算子, 其收益是结构特异的 (只在 ts_sum 池化输入上成立).**
        这条结论本身价值很高: 它否定了"把某个算子当万能补丁到处贴"的搜索模式.

=== 因此本批的战略前提 ===
  既然"输出层升级"路线已破产, 回到唯一被实证的机械解法上做交叉:
  ✅ **trade_when(cond, X, 0) 第三参 0 (硬平仓) 是目前唯一敢素证实能消除 CONCENTRATED_WEIGHT 的算子**
     证据 (S2 批次免费回收):
       槽7 trade_when(vec_count>0, reverse(rank(U/(U+D))), 0)      -> L/S 430/430, 无 CW fail
       槽8 trade_when(vec_count>0, reverse(rank(CVW/(cnt+1))), 0)  -> L/S 503/501, 无 CW fail
     而全部裸 rank 版本均 CW fail.
  ✅ 该算子同时能机械压 TO: CVW 分子 116.9% -> 44.3% (-62%).

  但该算子此前只与"低质量分子"组合过 (得到 Sh 0.88), **从未与家族最高质量资产交叉**:
     d5K6wxlx     Sh 1.61 / Ret 7.70% (全族最高 Ret) / 2Y 2.09 (少数已达 2Y 门)
     MP0n61ra-rev Sh 1.59-1.68 (全族 Sharpe 天花板)
  本批 8 槽全部围绕这个交叉, 并同时标定"门的类型"与"第三参 0 vs -1"两个未决变量.

=== 未决变量的意义 ===
  trade_when 第三参: 0 = 不满足条件时硬平仓; -1 = 不满足条件时保持上一期持仓.
  红队曾主张用 0 替代 -1, 但从未在同一资产上做过 0/-1 配对.
  理论上 -1 应更利于保 Ret (不平仓 => 不放弃后续漂移) 且更利于降 TO (持仓不变),
  但也可能累积过期仓位. 本批槽1/2 与槽3/4 是两组干净的 0/-1 配对.

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
DECAY = 6  # 回到历史基线 (decay 已证实对快结构无降 TO 作用)
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
BF = f"ts_backfill({CN}, 120)"
CTO = f"subtract({EOC}, {TON})"
CVW = f"subtract({EOC}, {VWAP})"

# 家族最高质量的两条资产
BEST_RET = f"reverse(rank(divide({CTO}, {BF})))"            # d5K6wxlx  Ret 7.70% / 2Y 2.09
BEST_SH = f"reverse(rank(divide({CVW}, vec_max({VHEX}))))"  # MP0n61ra  |Sh| 1.68

GATE_EXIST = f"greater({CN}, 0)"
GATE_FRESH = f"less(days_from_last_change({CN}), 2)"
GATE_SPIKE = f"greater({CN}, ts_mean({CN}, 20))"

SLOTS = [
    {
        "id": 1, "type": "BESTRET_HARDGATE_0", "role": "CROSS", "baseline": "d5K6wxlx Sh1.61/Ret7.70/TO120.1",
        "expression": f"trade_when({GATE_EXIST}, {BEST_RET}, 0)",
        "optimize_reason": (
            "【本批头号槽】把唯一实证的 CW 解法 (trade_when 第三参 0 硬平仓) 首次套到家族最高质量资产 "
            "d5K6wxlx (Sh1.61/Ret7.70%/2Y2.09/rnSh1.91 —— 全族最高 Ret 且是少数 2Y 已达 2.09 过线者) 上. "
            "此前该算子只与低质量分子组合过 (CVW+硬门 => Sh0.88/TO44.3%; U/(U+D)+硬门 => Sh1.17/TO58.6%). "
            "机制: 只在当日存在 high-price-excursion 事件的日子建仓, 其余日子硬平仓 —— 把注意力稀缺反转"
            "这一'只在事件日成立'的边缘与其'非事件日无信息'的时段机械分离. 第三参 0 而非 -1 是为了真正"
            "清空非事件日仓位, 这也是 S2 实证能消 CW 的关键 (不解该.userName) . 若本槽能把 TO 从 120.1% "
            "压到 <=70% 且 Ret 保住 >4.4%, 则 Fit 有望进入 0.5-0.8."),
    },
    {
        "id": 2, "type": "BESTRET_SOFTGATE_NEG1", "role": "CROSS", "baseline": "d5K6wxlx",
        "expression": f"trade_when({GATE_EXIST}, {BEST_RET}, -1)",
        "optimize_reason": (
            "【0 vs -1 配对】与槽1 唯一差别是第三参 -1 (不满足条件时保持上一期持仓, 而非平仓). "
            "理论预期: -1 更利于保 Ret (不平仓 => 不中断尚未走完的新闻后漂移) 且更利于降 TO "
            "(持仓不变 => 当日换手为 0). 但风险是累积过期仓位与在非事件日承担无信息的陈旧暴露. "
            "槽1/槽2 的差值会给出 'bearing cost of flat' 的直接估计: "
            "若 -1 显著优于 0, 则家族此前的门控设计原则 (红队主张的第三参 0) 需要整体修订."),
    },
    {
        "id": 3, "type": "BESTSH_HARDGATE_0", "role": "CROSS", "baseline": "MP0n61ra |Sh|1.68",
        "expression": f"trade_when({GATE_EXIST}, {BEST_SH}, 0)",
        "optimize_reason": (
            "【Sharpe 天花板 x CW 解法】把同一个硬门套到家族 Sharpe 天花板资产 (MP0n61ra 的 reverse 版, "
            "|Sh| 1.68 为全族最高). 该资产此前从未以 trade_when 包装的形式测过. "
            "MP0n61ra 的构造是 divide(close-vwap, vec_max(VHEX)) —— 每单位'最大主导冲击振幅'所摊到的"
            "尾盘订单流位移, 是跨股可比的标准化异常漂移. 与槽1 的 d5K6wxlx 构成分子对照 "
            "(CVW vs CTO) x 分母对照 (vec_max vs ts_backfill-count) 的二乘二设计."),
    },
    {
        "id": 4, "type": "BESTSH_SOFTGATE_NEG1", "role": "CROSS", "baseline": "MP0n61ra |Sh|1.68",
        "expression": f"trade_when({GATE_EXIST}, {BEST_SH}, -1)",
        "optimize_reason": (
            "【第二组 0 vs -1 配对】与槽3 配对, 目的与槽2 相同但作用在 Sharpe 最高的资产上. "
            "交叉验证第三参效应是稳健的还是资产特异的 —— 这决定了后续批次是否应整体改用 -1. "
            "特别地, MP0n61ra 的分母 vec_max(VHEX) 是当日最大值、天然稀疏, 而 d5K6wxlx 的分母 "
            "ts_backfill 是携带值、几乎每日有值; 若 -1 的保持持仓行为在 sparse 与 dense 两种分母上"
            "给出相反的结论, 则可进一步反推第三参效应究竟作用于'换手'还是作用于'有效持仓天数'."),
    },
    {
        "id": 5, "type": "BESTRET_FRESHGATE_0", "role": "CROSS", "baseline": "d5K6wxlx",
        "expression": f"trade_when({GATE_FRESH}, {BEST_RET}, 0)",
        "optimize_reason": (
            "【新鲜度门】把硬事件门换成'距离上次事件计数变化 <=2 日' (days_from_last_change). "
            "已知该门在家族其他结构上曾给出最好的 Sh/TO 组合之一 (O0JjGzmY Sh1.19/TO37.5%, "
            "MP0n3vlM Sh1.41/TO113.7%), 但从未与 d5K6wxlx 组合. 机制: 注意力稀缺反转的边缘存于"
            "'事件刚发生后的窗口', 而非'事件当天' —— 若属实则新鲜度门应优于 existence 门(槽1). "
            "与槽1 构成门的类型对照."),
    },
    {
        "id": 6, "type": "BESTRET_SPIKEGATE_0", "role": "CROSS", "baseline": "d5K6wxlx",
        "expression": f"trade_when({GATE_SPIKE}, {BEST_RET}, 0)",
        "optimize_reason": (
            "【慢注意力尖峰门】条件 = 当日事件计数超过其自身 20 日均值. 与前两门的差别是它是**慢变**条件 "
            "(20 日基准本身漂移慢), 理论上翻转频率远低于日等的 existence 门 => 换手更低. "
            "此前该门只配过 CNT 分母 (得到 Sh -0.25 / -0.46, 当时被判失败), 但**从未配过 ts_backfill "
            "分母 + d5K6wxlx 的高质量组合**. 与槽1/槽5 构成三门的类型标定."),
    },
    {
        "id": 7, "type": "BESTRET_TSRANK_HARDGATE_0", "role": "CROSS", "baseline": "YPxOX1QA Sh1.57/2Y2.16",
        "expression": f"trade_when({GATE_EXIST}, reverse(ts_rank(divide({CTO}, {BF}), 250)), 0)",
        "optimize_reason": (
            "【硬门 x ts_rank】YPxOX1QA = reverse(ts_rank(CTO/bf120, 250)) 是家族 2Y 最高者 (2.16) 且 "
            "Sh 1.57, 但 TO 118.1%. 本槽给它加上已实证的 CW 解法(硬门). 虽然 Wave10-C 已证明 ts_rank "
            "不是通用增益算子, 但那是'替换原有输出层'; 本槽是'额外加一层旧的 Researcher 而保留 ts_rank', "
            "两者机制不同 (一个是输出层替换, 一个是显式平仓). 选择 YPxOX1QA 而非 d5K6wxlx 是因为它同时"
            "具备家族最高 2Y —— 若 A Cumulative 墙是最后一道墙, 这是最有准备的资产."),
    },
    {
        "id": 8, "type": "BESTRET_CNT_HARDGATE_0", "role": "CROSS", "baseline": "d5K6wxlx / xA1oN7pl Sh1.42",
        "expression": f"trade_when({GATE_EXIST}, reverse(rank(divide({CTO}, add({CN}, 1)))), 0)",
        "optimize_reason": (
            "【分母效应 x 硬门】d5K6wxlx 用 ts_backfill(count,120) 作分母; 本槽换成 add(count,1) —— "
            "去掉回填、恢复天然稀疏性 (无事件日分母 NaN => 自带门控). 已知裸版 xA1oN7pl (开系列 open 分子)"
            " Sh1.42/TO113.8%, 且家族一直怀疑 ts_backfill 的'陈旧值'正是招致 CW 的来源 —— "
            "本槽若能在加硬门的前提下同时保持宽持仓并进一步压 TO, 则可验证'去 +1 去 backfill 的裸计数分母'"
            "这一结构假设 (该假设此前只在 (a) 无硬门 or (b) 低质量分子两种条件下测过, 从未同时成立)."),
    },
]

DIRECTIONS = {
    "D": {"name": "CW 解法 (trade_when 硬平仓) x 家族最高质量资产 首次交叉", "hypothesis": (
        "Wave10-C 证明 ts_rank 等输出层算子不是通用增益 (迁移到三条存活分支全部把 Sh 从 1.07-1.17 "
        "压到 0.46-0.98). 因此转向唯一被实证的**机械**解法: trade_when(cond, X, 0) 硬平仓是家族唯一"
        "敢素证实能消除 CONCENTRATED_WEIGHT 并能把 TO 从 116.9% 压到 44.3% 的算子, "
        "但它此前只与低质量分子组合过. 本批把它首次交叉到家族最高质量资产 "
        "(d5K6wxlx Ret7.70%/2Y2.09 与 MP0n61ra |Sh|1.68) 上, "
        "并同时标定两个从未配对的未决变量: 第三参 0 vs -1、以及三种门的类型 "
        "(existence / 新鲜度 days_from_last_change / 慢注意力尖峰)."),
        "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": SLOTS},
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
              f"len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:74]}", flush=True)
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
    print(f"[Wave10-D] 字段字典 {len(known_fields)} | decay={DECAY}", flush=True)

    d = DIRECTIONS["D"]
    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10D_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-D] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10D", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10d_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-D] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-D] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-D] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-D] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10d_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-D (decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>10} {'DD%':>6}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        print(f"{it['id']:>2} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} {to * 100:>7.1f} "
              f"{ret * 100:>7.2f} {(ret / to) if to else 0:>7.3f} {(m.get('margin') or 0) * 1e4:>7.2f} "
              f"{m.get('two_year_sharpe') or 0:>6.2f} {m.get('sub_universe_sharpe') or 0:>5.2f} "
              f"{m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave10-D] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
