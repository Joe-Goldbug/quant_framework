# -*- coding: utf-8 -*-
"""Gate1 Wave10-H · CW 已解结构 x SH165 新鲜度门 的合流 (decay=6, INDUSTRY, TOP1000).

=== ★ 本批的立项依据: 一项修正了此前错误判据的发现 ===
  对全战役 299 个 (表达式 x settings) 样本重查 CW, 发现**存在 12 条 Sh>=1.4 且 CW=ok 的样本**.
  此前把 CW 当作"结构性墙"是错的. 根因由一对只差分母的对照直接锁定:
      N1eGk79E  divide(CVW, ts_backfill(vec_count,120))  -> Sh 1.63, L/S 519/516, **CW FAIL**
      N1eGbEGo  divide(CVW, add(vec_count, 1))           -> Sh 1.50, L/S 289/289, **CW ok**
      N1eGk79E 的 ts_backfill 回填值让**非事件日也保有陈旧非零值**, 组合因此长期持有
      一批"信息已过期"的仓位, 权重向这些陈旧仓位集中 -> CW.
      add(vec_count,1) 则天然稀疏: 无事件日分母 NaN -> 无持仓 -> 不集中.
  ==> **CONCENTRATED_WEIGHT 是"分母是否回填"的函数, 不是 Sharpe 的函数.**
      这与 Wave10-F(universe 扩大持仓面翻倍仍 CW fail) 与 Wave10-G(SUBINDUSTRY 仍 CW fail)
      的两次负面结果完全一致: 它们都没动到"陈旧值"这个真正的病根.

=== 于是四墙的真实状态被重新盘点为 ===
  ✅ CW    : 已解 —— 用 add(vec_count,1) 裸计数分母 (12 条实证)
  ✅ 2Y    : 已解 —— CTO/COPEN 分子 + ts_rank 给出 2Y 2.07~2.40 (xA1oN7pl 2.35 / MP0n3vlM 2.40)
  ✅ sub   : 已解 —— 门槛仅需 >= -0.24, 全部候选均在 0.87~1.30
  ⚠️ Sharpe: 已解但不可兼得 —— SH165 的 1.65 是过线的, 但它用的是 CW-fail 的回填分母
  🔴 TO    : **唯一真正的墙** —— 全部 Sh>=1.4 的样本 TO 均 >=112%, 无一例外

=== 本批的唯一命题 ===
  把两件已分别验证的事合流:
    (A) SH165 的新鲜度门 trade_when(less(days_from_last_change(vec_count),2), X, 0)
        —— 该门已被证明是"免费"的: 它把 d5K6wxlx 从 Sh1.61/Ret7.70% 抬到 **Sh1.65/Ret7.86%**
           (全族双料最高), 且几乎不增加 TO (120.1% -> 119.8%).
    (B) add(vec_count,1) 裸计数分母 —— 已证明消除 CW.
  **但 (A) 与 (B) 从未组合过**: SH165 用的是 ts_backfill 分母, 因而 CW fail;
    而所有 CW-ok 的高 Sharpe 样本 (2rjxpVxJ Sh1.56 / xA1oN7pl Sh1.42) 都没配新鲜度门.
  本批 8 槽即为 (A)x(B) 的合流矩阵, 覆盖三种分子 (CTO / COPEN / CVW) 与两种输出层
  (rank / ts_rank), 全部加载新鲜度门.

=== 判读 ===
  若某槽同时做到 Sh>=1.58 + CW ok + 2Y>=1.58, 则本战役首次达成"三墙已过、仅剩 TO/Fit"的状态,
  后续即可把全部预算压在单一变量 TO 上.

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
UNIVERSE, NEUT, DECAY = "TOP1000", "INDUSTRY", 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON, VWAP, OPEN = "news_eod_close", "news_ton_last", "news_eod_vwap", "news_open"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
CNT1 = f"add({CN}, 1)"                                   # ★ CW 已解分母 (天然稀疏)
CTO = f"subtract({EOC}, {TON})"
COPEN = f"subtract({EOC}, {OPEN})"
CVW = f"subtract({EOC}, {VWAP})"
GATE = f"less(days_from_last_change({CN}), 2)"           # ★ SH165 的免费新鲜度门


def gate_rank(num):
    return f"trade_when({GATE}, reverse(rank(divide({num}, {CNT1}))), 0)"


def gate_tsrank(num, m):
    return f"trade_when({GATE}, reverse(ts_rank(divide({num}, {CNT1}), {m})), 0)"


SLOTS = [
    {
        "id": 1, "type": "CONFLUENCE_CTO_RANK", "role": "CONFLUENCE", "baseline": "SH165 Sh1.65 (但 CW fail)",
        "expression": gate_rank(CTO),
        "optimize_reason": (
            "【本批头号槽 · 合流核心】SH165 的分子 (CTO = 新闻时刻至收盘的漂移, 是 d5K6wxlx/SH165 "
            "高 Ret 的来源) 换上 CW 已解分母 add(vec_count,1), 并保留 SH165 的新鲜度门. "
            "SH165 原版 Sh1.65/Ret7.86%/2Y2.10 是全族双料最高, 唯一的 CW fail 由 ts_backfill 回填分母"
            "造成; 本槽把分母换成裸计数后, 若 Sharpe 与 Ret 基本保持 (预期 Sh 1.5-1.65、Ret 7-8%) "
            "而 CW 转 ok, 则本战役首次出现 'Sh 过线 + CW 过线 + 2Y 过线' 三墙同过的资产, "
            "全部剩余预算即可压在单一变量 TO 上. 这是本战役迄今最接近达标的一槽."),
    },
    {
        "id": 2, "type": "CONFLUENCE_CTO_TSRANK120", "role": "CONFLUENCE", "baseline": "2rjxpVxJ Sh1.56/CW ok",
        "expression": gate_tsrank(CTO, 120),
        "optimize_reason": (
            "【CW-ok 最高 Sharpe 资产 + 新鲜度门】2rjxpVxJ = reverse(ts_rank(CTO/加1计数, 120)) 是全部 "
            "CW-ok 样本中 Sharpe 最高者 (Sh 1.56, 距 1.58 门槛仅 0.02), 但它从未配过新鲜度门. "
            "SH165 的经验表明该门能在几乎不增 TO 的前提下抬 Sh (d5K6wxlx 1.61 -> 1.65) 与抬 Ret. "
            "本槽若能把 1.56 推过 1.58, 即为家族首个 'Sh 过线 + CW ok' 的样本."),
    },
    {
        "id": 3, "type": "REPLICATE_2RJXPVXJ", "role": "REPLICATE", "baseline": "2rjxpVxJ Sh1.56/CW ok/TO123.0",
        "expression": f"reverse(ts_rank(divide({CTO}, {CNT1}), 120))",
        "optimize_reason": (
            "【复现 + 配对基准】2rjxpVxJ 原样重跑, 目的有二: (a) 复现 Sh 1.56 与 CW ok 这两个关键读数; "
            "(b) 与槽2 构成'新鲜度门有无'的干净配对, 直接读出该门在 CW-ok 结构上的边际贡献. "
            "没有这个基准, 槽2 的结果无法归因. 该槽不追求达标, 追求可解释性. "
            "另注: 该结构的 ts_rank 窗口 120 与 CVW 分子 (而非 250 与 CTO) 是它区别于同族其他样本的两点, "
            "本批槽7 会单独拆解这个差异."),
    },
    {
        "id": 4, "type": "CONFLUENCE_COPEN_RANK", "role": "CONFLUENCE", "baseline": "xA1oN7pl Sh1.42/2Y2.35/CW ok",
        "expression": gate_rank(COPEN),
        "optimize_reason": (
            "【2Y 冠军分子 x 合流】COPEN (收盘 - 当日开盘) 是家族 2Y 最高的分子: xA1oN7pl 裸版 2Y 2.35、"
            "MP0n3vlM 门版 2Y 2.40 (全族最高), 且两者 CW 均 ok. 本槽给它加载 SH165 的新鲜度门. "
            "若 2Y 保持 >=2.0 且 Sh 被门抬到 1.5+, 则本槽成为'2Y 与 CW 双过、Sh 接近'的形态 —— "
            "2Y 是最难抬的一项, 而它在这里已经不是约束, 这使本槽成为后续 TO 攻击的最佳承载基座."),
    },
    {
        "id": 5, "type": "CONFLUENCE_COPEN_TSRANK250", "role": "CONFLUENCE", "baseline": "MP0n3vlM 2Y2.40",
        "expression": gate_tsrank(COPEN, 250),
        "optimize_reason": (
            "【2Y 冠军 x ts_rank 输出层 x 门】三层叠加: COPEN 分子 (2Y 冠军) + ts_rank(250) "
            "(已知能显著抬 2Y: e76P3MZp 2.07 / zqrEbLw8 2.11) + 新鲜度门 (抬 Sh/Ret). "
            "MP0n3vlM 已用 COPEN + 门拿到 2Y 2.40, 但它的第三参是 -1 且输出层是 rank; "
            "本槽改为第三参 0 且输出层 ts_rank, 检验这两项改动能否在保住 2Y 的同时抬 Sh. "
            "这是本批对 '2Y 与 Sharpe 能否同时最大化' 这一问题的直接回答."),
    },
    {
        "id": 6, "type": "CONFLUENCE_CVW_RANK", "role": "CONFLUENCE", "baseline": "N1eGbEGo Sh1.50/CW ok",
        "expression": gate_rank(CVW),
        "optimize_reason": (
            "【锚的分子 x CW 已解分母 x 门】这是对用户 mandate 起点最直接的一次修复: "
            "锚 N1eGk79E 用 CVW 分子 + ts_backfill 分母, 得到 Sh1.63 但 CW fail 且 2Y 仅 0.58; "
            "而同一分子换 add(vec_count,1) 分母的 N1eGbEGo 是 CW ok (Sh 1.50). "
            "本槽 = 锚的分子 + CW 已解分母 + SH165 新鲜度门, 是对用户四项 FAIL "
            "(Fit/TO/CW/2Y) 中 CW 一项的最直接答复. 因 CVW 是用户 mandate 明确要求优化的起点分子, "
            "本槽即使不达标也具有最高的报告价值."),
    },
    {
        "id": 7, "type": "CONFLUENCE_CVW_TSRANK120", "role": "CONFLUENCE", "baseline": "2rjxpVxJ 的分子变体",
        "expression": gate_tsrank(CVW, 120),
        "optimize_reason": (
            "【拆解 2rjxpVxJ 的两点差异】2rjxpVxJ (Sh1.56, CW ok) 用的是 CVW 分子 + ts_rank(120); "
            "而同族其他 CW-ok 样本多用 CTO 分子 + ts_rank(250). 本槽把 2rjxpVxJ 的 CVW 分子与 "
            "ts_rank120 组合再加载新鲜度门, 与槽2 (CTO 分子 + ts_rank120 + 门) 构成单变量对照, "
            "定量分离'分子选择'对那个 1.56 的贡献. 若 CVW 更优, 则说明用户 mandate 的锚分子本身"
            "就是最优分子之一, 只是此前一直被错误的回填分母拖累."),
    },
    {
        "id": 8, "type": "CONFLUENCE_CTO_TSRANK250_GATE", "role": "CONFLUENCE", "baseline": "e76P3MZp Sh1.41/2Y2.07",
        "expression": gate_tsrank(CTO, 250),
        "optimize_reason": (
            "【三重已验证成分的最大叠加】CTO 分子 (高 Ret) + ts_rank250 (已验证抬 2Y: e76P3MZp 2.07) "
            "+ CW 已解分母 + 新鲜度门 (抬 Sh/Ret). 与槽2 (同一分子, ts_rank 窗口 120) 构成窗口对照, "
            "用于判定在 CW-ok 结构 + 门的条件下 ts_rank 最优窗口是 120 还是 250. "
            "本槽是本批四个'已验证成分'叠得最满的一槽, 若任何一槽能同时拿到 Sh>=1.58 与 2Y>=1.58 "
            "与 CW ok, 最可能出自槽1/槽8 这两槽."),
    },
]

DIRECTIONS = {
    "H": {"name": "CW 已解结构 x SH165 新鲜度门 合流矩阵", "hypothesis": (
        "修正此前错误判据: CW 不是结构性墙, 它是'分母是否回填'的函数 —— "
        "N1eGk79E (divide(CVW, ts_backfill(count,120))) CW FAIL 与 N1eGbEGo (divide(CVW, add(count,1))) "
        "CW ok 的对照直接锁定根因, 且全样本中存在 12 条 Sh>=1.4 且 CW=ok 的样本. "
        "于是四墙真实状态为: CW 已解 / 2Y 已解 (CTO-COPEN+ts_rank 给出 2.07-2.40) / sub 已解 / "
        "Sh 已解但由 SH165 的 1.65 承载 (而它 CW fail) / **TO 是唯一真墙** (全部 Sh>=1.4 样本 TO>=112%). "
        "本批把两件分别验证过的事首次合流: SH165 的新鲜度门 (免费抬 Sh 1.61->1.65 与 Ret) x "
        "add(vec_count,1) CW 已解分母, 覆盖三种分子与两种输出层."),
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
    d = DIRECTIONS["H"]
    print(f"[Wave10-H] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10H_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-H] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10H", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10h_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-H] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-H] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-H] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-H] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10h_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-H ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>11} {'DD%':>6} {'CW':>5}", flush=True)
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
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>11} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f} {cw:>5}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave10-H] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
