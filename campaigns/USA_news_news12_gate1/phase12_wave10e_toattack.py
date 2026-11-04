# -*- coding: utf-8 -*-
"""Gate1 Wave10-E · 对 Sh1.65/Ret7.86%/2Y2.10 新纪录资产做 TO 攻击 (decay=6).

=== Wave10-D 的战果: 全族新纪录资产 SH165 ===
  trade_when(less(days_from_last_change(vec_count(VHEX)), 2),
             reverse(rank(divide(subtract(news_eod_close, news_ton_last),
                                 ts_backfill(vec_count(VHEX), 120)))), 0)
  Sh 1.65 (家族最高, 过 >=1.58) | Ret 7.86% (家族最高, 过 d5K6wxlx 的 7.70%)
  2Y 2.10 (过 >=1.58) | sub 1.30 (过 >=-0.24) | rnSh 1.95 | DD 5.7%
  剩余三墙: LOW_FITNESS 0.42<1.0 | HIGH_TURNOVER 119.8%>70% | CONCENTRATED_WEIGHT

=== ★ 本批的核心算术: 达标的重心已经从 "抬 Ret" 移到 "压 TO" ===
  由 Fit = Sh * sqrt(Ret / max(TO, 0.11)), 固定 Sh=1.65 / Ret=7.86%:
      1.65 * sqrt(0.0786 / max(TO,0.11)) >= 1
   =>  max(TO, 0.11) <= 0.0786 / (1/1.65)^2 = 0.0786 * 1.65^2 = 0.2140
   ==> **只要 TO <= 21.4%, Fit 即达标 (无需任何 Ret 提升).**
  对比旧局势: d5K6wxlx 在 TO=120% 下需 Ret=46.35% (缺口 6.0x);
             现在只需 Ret 保住 >= 21.4%/1.65^2 = 7.86% * (TO/21.4%) 的线性缩放.
  即 ROS требуется: **TO 降 5.6x 且 Ret 保住 >=55%** (此前是 Ret 抬 6x).
  另注 frescura 门 < 2 本身几乎不过滤 (TO 119.8% vs 裸版 120.1%), 它保留了全部 Sharpe
  与 Ret — 这说明 'less(days_from_last_change, 2)' 是与该资产兼容的"免费"门, 可作为
  后续所有 TO 攻击的承载基座.

=== 另两项 Wave10-D 副结论 ===
  - 第三参 0 与 -1 **完全等价** (槽1=槽2 Sh0.94/TO39.7%; 槽3=槽4 Sh1.10/TO52.5%)
    => 家族此前围绕 third-param 的设计争论结案, 后续不必再花槽位在此.
  - 慢注意力尖峰门彻底失败 (槽6 Sh 0.24) => 该门 route 关闭.

=== 已知的各降 TO 手段的"代价表"(家族实测, 决定本批选哪些) ===
  ts_sum 池化 N=60      TO 降 15.2x  -> Sh 0.19 (裸) / 0.48 (加 ts_rank)
  ts_backfill(ratio,60) TO 降  3.5x  -> Sh 1.10-1.19
  trade_when 硬门       TO 降  2.7x  -> Sh 0.88-1.17
  ts_decay_linear(20)   TO 降  1.14x -> Sh 保 98.5% (家族已知"保边最好"的平滑)
  => 目前 TO<=40% 区的最高 Sh 是 1.19; TO 15-30% 区的最高 Sh 只有 0.57-0.61.
     目标区 (TO<=21.4% 且 Sh>=1.58) 从未被观测到. 本批即为对该区的一次定向冲击.

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
DECAY = 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON = "news_eod_close", "news_ton_last"
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
BF120 = f"ts_backfill({CN}, 120)"
CTO = f"subtract({EOC}, {TON})"
RATIO = f"divide({CTO}, {BF120})"          # SH165 的核心比值
DFLC2 = f"less(days_from_last_change({CN}), 2)"

SLOTS = [
    {
        "id": 1, "type": "SH165_GATE_TIGHTEN_DFLC1", "role": "TO-ATTACK", "baseline": "SH165 Sh1.65/TO119.8",
        "expression": f"trade_when(less(days_from_last_change({CN}), 1), reverse(rank({RATIO})), 0)",
        "optimize_reason": (
            "【收紧新鲜度门 dflc<2 -> dflc<1】这是本批最保守也最直接的一步: SH165 的门 dflc<2 几乎不过滤 "
            "(TO 119.8% vs 裸版 120.1%), 收紧到 dflc<1 (仅剩'当日/次日'恰好发生计数变化的日子) 应能机械"
            "砍掉一批交易日. 家族先前证据显示该门{dyld}dflc<1 版本在另一结构上曾把 TO 压到 36.6% (Sh 1.13), "
            "说明新鲜度门的松紧刻度确实连续且可控. 本槽回答: 在 SH165 这个最高质量资产上, 门收紧一档能换到"
            "多少 TO、代价多少 Sh. 这是决定后续是否继续沿'门刻度'细分的依据."),
    },
    {
        "id": 2, "type": "SH165_TSDECAYLIN20", "role": "TO-ATTACK", "baseline": "SH165",
        "expression": f"trade_when({DFLC2}, reverse(rank(ts_decay_linear({RATIO}, 20))), 0)",
        "optimize_reason": (
            "【家族已知保边最好的平滑 + SH165】ts_decay_linear 是唯一被实证定义为'保边'的平滑算子: "
            "此前在另一结构上 20 日线性衰减保住了 98.5% 的 Sharpe (Sh 1.37->1.35), 代价是 TO 仅降 12%. "
            "本槽把它套到 SH165 基座上 (而非此前那个较低质量的基座). 关键命题: 若在同一个高质量资产上"
            "线性衰减仍能保住 ~98% 的 Sharpe, 则只需再叠加第二个 1.5-2x 的降 TO 手段即可接近 TO 21% 目标, "
            "这是一条比'一次性重平滑'更可能保留 quality 的渐进路径."),
    },
    {
        "id": 3, "type": "SH165_TSMEAN5", "role": "TO-ATTACK", "baseline": "SH165",
        "expression": f"trade_when({DFLC2}, reverse(rank(ts_mean({RATIO}, 5))), 0)",
        "optimize_reason": (
            "【最轻量平滑探针】ts_mean 窗口取 5 (家族先前只测过 10/20/60/250 的中长窗口并判'平滑杀边'). "
            "命题: 杀边的真正原因可能是窗口过长导致边缘过期, 而非平滑本身 —— N=5 是'事件后 5 日'这一"
            "文献中过度反应修复窗口 (Hong-Stein 渐进扩散 / PEAD) 的自然尺度. 若 N=5 能把 TO 压到 60-80% "
            "而 Sh 保持在 1.4+, 则说明存在'既在真实修复窗口内、又能降换手'的甜点, 后续应在 N=5-15 细分."),
    },
    {
        "id": 4, "type": "POOLED_CTN_N10_TSRANK", "role": "BRIDGE", "baseline": "W10B 槽6 (N=60 -> Sh0.06)",
        "expression": f"reverse(ts_rank(divide(ts_sum({CTO}, 10), add(ts_sum({CN}, 10), 1)), 250))",
        "optimize_reason": (
            "【短池化桥梁】把两个世界连起来: SH165 的信息内容 (CTO = 新闻时刻至收盘漂移) 用 pooled 方式表达. "
            "Wave10-B 槽6 用 N=60 得到 Sh 0.06 (判失败); 本槽把窗口缩到 N=10 —— 更接近日频, 更少稀释事件信息. "
            "命题: pooled 失败的原因可能同样是'窗口过长使 theta 漂移失真'而非'CTO 分子不成立'. "
            "若 N=10 显著优于 N=60, 则 N 的响应曲线在 CTO 版本上呈现 与 Wave10-B 的 U/D 版本相反的单调性, "
            "该信息本身就是两个 families 结构差异的直接读数."),
    },
    {
        "id": 5, "type": "POOLED_UD_TSRANK_GATE_DFLC2", "role": "BRIDGE", "baseline": "W10A槽6 R/TO0.403",
        "expression": f"trade_when({DFLC2}, reverse(ts_rank(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))), 250)), 0)",
        "optimize_reason": (
            "【双 Cruci 组合】把家族 R/TO 最高资产 (Wave10-A 槽6: R/TO 0.403 / Mgn 8.04bps / TO 5.2%, "
            "但 Sh 仅 0.61) 与 SH165 的'免费兼容门' (dflc<2, 该门已被证明不损伤 Sharpe) 组合. "
            "这只是 pooled  families 从未配过 frescura 门. 命题: 若 pooled 结构的低 Sharpe 部分来自"
            "'在非事件日也持有陈旧仓位', 则加载 event-freshness 门应能同时抬 Sh 与保低 TO —— "
            "这是把两个 families 的互补优势 (高 R/TO vs 高 Sh) 合并的唯一未测接口."),
    },
    {
        "id": 6, "type": "DECAYLIN_UD_TSRANK250", "role": "BRIDGE", "baseline": "W10A槽6 Sh0.61/R-TO0.403",
        "expression": f"reverse(ts_rank(divide(ts_decay_linear({U}, 60), add(ts_decay_linear({U}, 60), ts_decay_linear({D}, 60))), 250))",
        "optimize_reason": (
            "【用线性衰减替代 boxcar 池化】Wave10-A 槽6 用等权 ts_sum (boxcar, 第 1 天与第 60 天等权), "
            "这被红队正确指出与'新闻后过度反应在 5-20 日修复'的真实经济窗口不匹配. 本槽把 boxcar 换成 "
            "ts_decay_linear(60): 权重线性递减, 近期事件贡献更大. 这是对该结构最自然的一个 symplectic "
            "改进, 且不需要引入任何新字段或新算子族. 若本槽 Sharpe 显著高于槽5 所处的 0.61 水平, "
            "则确认'长记忆实现 vs 短记忆机制'的矛盾是 pooled 线低 Sharpe 的真实原因."),
    },
    {
        "id": 7, "type": "SH165_GROUPRANK_INDUSTRY", "role": "TO-ATTACK", "baseline": "SH165",
        "expression": f"trade_when({DFLC2}, reverse(group_rank({RATIO}, industry)), 0)",
        "optimize_reason": (
            "【组内化 — 唯一'降噪但不降频'的手段】与前几条不同, group_rank(industry) 不改变时间序列, "
            "只把个股值换成其在行业内的秩. 它的降 TO 来自剔除行业层面的共同漂移 (这部分漂移每日大幅变动"
            "却不产生个股间可分时的 alpha), 因此理论上能降 TO 而不损失个股特有的边缘. "
            "家族内 group_rank 此前只套过较低质量基座 (YPxOGboo Sh 1.17/TO 37.8%), 从未套过 SH165. "
            "本槽是全批唯一'不靠平滑降 TO'的路径, 若成功则为 decorator 提供一条全新菜单."),
    },
    {
        "id": 8, "type": "DECAYLIN_UD_PLAINRANK", "role": "BRIDGE", "baseline": None,
        "expression": f"reverse(rank(divide(ts_decay_linear({U}, 60), add(ts_decay_linear({U}, 60), ts_decay_linear({D}, 60)))))",
        "optimize_reason": (
            "【ts_rank 层在 linear-decay 输入的再验证】与槽6 唯一差别是无 ts_rank(250) 输出层. "
            "Wave10-B 已定量证明: 在 boxcar 池化输入上 ts_rank 贡献 ×3.4 Sharpe (0.14 -> 0.48); "
            "Wave10-C 又证明该贡献是结构特异的 (在 trade_when 分支上反而 -16% ~ -57%). "
            "本槽把它放到第三种输入 (linear decay) 上, 用于判定 ts_rank 的适用范围究竟是 'ts_sum 池化专属' "
            "还是更一般的 '慢化了的时间序列' —— 这个判据直接决定后续是否值得对每条慢信号都加 ts_rank."),
    },
]

DIRECTIONS = {
    "E": {"name": "对 Sh1.65/Ret7.86%/2Y2.10 新纪录资产 (SH165) 的 TO 定向攻击", "hypothesis": (
        "Wave10-D 产出全族新纪录资产 SH165 (Sh1.65/Ret7.86%/2Y2.10/sub1.30, Sh 与 2Y 已过线). "
        "代入 Fit = Sh*sqrt(Ret/max(TO,0.11)) 得: 固定 Sh=1.65 与 Ret=7.86% 时, "
        "**只需 TO <= 21.4% 即可 Fit>=1** —— 达标的重心已从'把 Ret 抬 6 倍'转变为"
        "'把 TO 压 5.6 倍同时 Ret 保住 55%'. 本批围绕该资产做三类攻击: "
        "(a) 门刻度收紧与轻量平滑 (槽1-3), (b) 与 pooled 高 R/TO 分支的桥接 (槽4-6), "
        "(c) 唯一不降频的去噪手段 group_rank 组内化 (槽7), 外加 ts_rank 适用范围的第三类输入验证 (槽8)."),
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
    print(f"[Wave10-E] 字段字典 {len(known_fields)} | decay={DECAY}", flush=True)

    d = DIRECTIONS["E"]
    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10E_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-E] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10E", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10e_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-E] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-E] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-E] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-E] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10e_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-E (decay={DECAY}) | 目标: TO<=21.4% 且 Ret>=4.4% 且 Sh>=1.58 =====", flush=True)
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
    print("\n[Wave10-E] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
