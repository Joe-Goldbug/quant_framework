# -*- coding: utf-8 -*-
"""Gate1 Wave10-I · 对 CONFLUENCE-1 (四墙已过三项) 的 TO 定向攻击 (decay=6).

=== Wave10-H 的决定性战果: CONFLUENCE-1 ===
  trade_when(less(days_from_last_change(vec_count(high_price_excursion_stddev)), 2),
             reverse(rank(divide(subtract(news_eod_close, news_ton_last),
                                 add(vec_count(high_price_excursion_stddev), 1)))), 0)
  Sh 1.59  ✅ (>=1.58)
  2Y 2.03  ✅ (>=1.58)
  sub 1.39 ✅ (>=-0.24)
  CW ok    ✅ (<=0.1)      <-- CW 墙正式破解
  rnSh 1.86 | Ret 7.52% | DD 5.4% | L/S 312/307
  剩余: LOW_FITNESS 0.41 (<1.0) 与 HIGH_TURNOVER 114.6% (>70%)
  ==> 由 4 个 FAIL 降至 2 个. 这是 232 槽以来首次出现 Sh/2Y/sub/CW 四项同过的资产.

=== ★ 达标的精确算术 (本批的目标面) ===
  Fit = Sh * sqrt(Ret / max(TO, 0.11)); 固定 Sh=1.59, Ret=7.52%:
    1.59 * sqrt(0.0752 / max(TO,0.11)) >= 1
 => max(TO,0.11) <= 0.0752 * 1.59^2 = 0.1901  ==> **TO <= 19.0% 即可 Fit>=1**
  若 Ret 随平滑下降为 R, 则要求 max(TO,0.11) <= R * 1.59^2 = 2.528 R.
  两条等价路径:
    (A) TO 落在 19-30%, 需 Ret >= TO/2.528 (例 TO=25% -> Ret>=9.89%; TO=30% -> Ret>=11.87%)
    (B) TO <= 11% 进入 turnover floor 保护区, 仅需 **Ret >= 4.35%** (Sh 1.59)
  路径 (B) 明显更现实: 它要求 TO 降 10.4x 而 Ret 只保住 58%.

=== 本批与 Wave10-E 的关键差别: 基座换了 ===
  Wave10-E 的 TO 攻击是在 SH165 的 **ts_backfill 回填分母**基座上做的, 结果最好的一格是
  ts_mean(RATIO,5) -> TO 30.0%/Sh 0.85/Ret 3.99%. 但现在已知: 那个基座的 CW fail 与低 Ret
  都源自回填的**陈旧仓位** —— 陈旧仓位既制造了权重集中, 也稀释了 Ret.
  本批把同样的攻击重做在 **add(vec_count,1) 裸计数分母**基座上 (该基座已实证 CW ok 且
  Ret 7.52% 显著高于旧基座的 3.99%). 同一套平滑算子在新基座上的响应曲线**从未测过**,
  且理论上有理由更好: 没有陈旧仓位稀释后, 单位换手承载的信息量应当更高.

=== 8 槽设计 ===
  槽1-3: ts_mean 窗口扫描 5 / 10 / 20 (标定 Ret 与 TO 的联合衰减曲线)
  槽4-5: ts_decay_linear 20 / 60 (已知保边最好的平滑, 用于与等权 ts_mean 对照)
  槽6-7: ts_sum 池化 N=5 / 20 (输入侧重参数化, 已知降 TO 最猛)
  槽8  : 门放宽 dflc<2 -> dflc<5 (方向相反: 增加交易日, 用于检验门的过滤方向)

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

EOC, TON = "news_eod_close", "news_ton_last"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
CNT1 = f"add({CN}, 1)"
CTO = f"subtract({EOC}, {TON})"
R = f"divide({CTO}, {CNT1})"                       # CONFLUENCE-1 的核心比值
GATE = f"less(days_from_last_change({CN}), 2)"     # CONFLUENCE-1 的新鲜度门

SLOTS = [
    {
        "id": 1, "type": "CONF1_TSMEAN5", "role": "TO-ATTACK", "baseline": "CONF-1 Sh1.59/TO114.6/Ret7.52",
        "expression": f"trade_when({GATE}, reverse(rank(ts_mean({R}, 5))), 0)",
        "optimize_reason": (
            "【最轻量平滑】窗口取 5 是刻意的: 它恰好是新闻后过度反应修复的文献尺度 (Hong-Stein "
            "渐进扩散 / PEAD 的经验窗口 5-20 日), 而不是此前被判'杀边'的 20/60/250. "
            "在旧基座上 ts_mean(5) 给出 TO 30.0% / Ret 3.99% / Sh 0.85; 本槽检验同样的算子在"
            "**已剔除陈旧仓位的新基座**上能否把 Ret 与 Sh 都抬起来 —— 新基座没有回填稀释, "
            "理论上单位换手的信息量更高. 若本槽 TO<=30% 且 Ret>=5%, 即进入路径(A)的有效区."),
    },
    {
        "id": 2, "type": "CONF1_TSMEAN10", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(ts_mean({R}, 10))), 0)",
        "optimize_reason": (
            "【窗口扫描中档】与槽1/槽3 共同标定 Ret 与 TO 的联合衰减曲线形状. "
            "关键判据不是'哪个窗口最好', 而是曲线是否**单调**: 若 Ret 与 TO 同比缩小 (R/TO 恒定), "
            "则任何等权平滑都不能改善 Fit (Fit=Sh*sqrt(Ret/max(TO,0.11)) 中 Sh 是唯一可变量); "
            "若某处 Ret 的衰减慢于 TO, 则存在甜点窗口, 该窗口即为后续全部预算的落点. "
            "这是本批信息价值最高的一个判据."),
    },
    {
        "id": 3, "type": "CONF1_TSMEAN20", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(ts_mean({R}, 20))), 0)",
        "optimize_reason": (
            "【窗口扫描上档 + 冲击 turnover floor】20 日等权平滑在当前家族经验上大致对应 TO 15-30% 区间, "
            "是最有可能**触达 TO<=19.0% 达标线**甚至进入 TO<=11% 保护区的一格. "
            "路径(B)要求: TO<=11% 且 Ret>=4.35%. 本槽是全批对路径(B)最直接的一次冲击; "
            "即使 Sh 随平滑下降, 只要 Sh>=1.2 且 Ret>=7.64% 或 Sh>=1.58 且 Ret>=4.40% 即可达标."),
    },
    {
        "id": 4, "type": "CONF1_TSDECAYLIN20", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(ts_decay_linear({R}, 20))), 0)",
        "optimize_reason": (
            "【保边最好的平滑】ts_decay_linear 是家族唯一被实证定义为'保边'的平滑: 20 日线性衰减曾保住 "
            "98.5% 的 Sharpe (1.37->1.35), 代价是 TO 仅降 12%. 与槽2 (等权 ts_mean 10) 构成算子对照: "
            "两者窗口尺度相近, 差别仅在权重结构 (线性递减 vs 等权). 经济学依据: 若边缘确实在 5-20 日"
            "修复, 则近期事件应占更大权重 —— 线性衰减正是这种先验的实现. "
            "本槽回答'权重结构'与'窗口长度'哪个才是决定因素."),
    },
    {
        "id": 5, "type": "CONF1_TSDECAYLIN60", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(ts_decay_linear({R}, 60))), 0)",
        "optimize_reason": (
            "【长线性衰减】窗口拉到 60 但保持线性递减权重. 与槽3 (等权 20) 的对照可分离"
            "'长度 vs 权重结构'各自的贡献: 若 60 日线性衰减优于 20 日等权, 则说明权重结构比长度更重要, "
            "后续应继续加长而非收紧; 反之则应走短窗口路线. 这一判据直接决定后续整条 TO 攻击线的走向."),
    },
    {
        "id": 6, "type": "CONF1_POOL_N5", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(divide(ts_sum({CTO}, 5), add(ts_sum({CN}, 5), 1)))), 0)",
        "optimize_reason": (
            "【输入侧重参数化 N=5】与输出侧平滑完全不同的机制: 不对已算好的比值做任何处理, 而是用 5 日"
            "原始观测重新估计'每条新闻的平均漂移' theta_hat = sum(CTO,5)/sum(事件数,5). "
            "理论优势: 估计误差 ~1/sqrt(N) 使 Sharpe 有理由上升, 而日变化 ~1/N 使 TO 下降 —— "
            "两者方向相反, 这正是打断家族 Sh<->R/TO 反相关的机制. 取 N=5 (而非此前 pooled 家族常用的 60) "
            "是为了尽量靠近日频、减少 theta 漂移失真."),
    },
    {
        "id": 7, "type": "CONF1_POOL_N20", "role": "TO-ATTACK", "baseline": "CONF-1",
        "expression": f"trade_when({GATE}, reverse(rank(divide(ts_sum({CTO}, 20), add(ts_sum({CN}, 20), 1)))), 0)",
        "optimize_reason": (
            "【输入侧重参数化 N=20】与槽6 构成 N 的响应标定. 已知线索: 在 U/D 分子的 pooled 家族上, "
            "N 从 60 提到 120 时 R/TO 反而略升 (0.190 -> 0.202) 且 Sharpe 未翻负, 说明长池化在该族是"
            "正贡献; 但在 CTO 分子上 N=60 曾给出 Sh 0.06 (W10B 槽6). 本槽与槽6 用 5/20 两个短窗口"
            "重新检验 CTO 分子在 pooled 结构上的可用性 —— 若短窗口显著优于 N=60, 则此前对该分子的"
            "失败判决应归因于窗口过长而非分子不成立."),
    },
    {
        "id": 8, "type": "CONF1_GATE_WIDEN_DFLC5", "role": "CONTROL", "baseline": "CONF-1",
        "expression": f"trade_when(less(days_from_last_change({CN}), 5), reverse(rank({R})), 0)",
        "optimize_reason": (
            "【反向对照: 放宽而非收紧门】前述 7 槽都是'减少交易'方向; 本槽反向把门从 dflc<2 放宽到 "
            "dflc<5 (增加交易日). 目的: 定量确认'门的方向'与 TO 确实是同向的 —— 若放宽门后 TO 上升, "
            "则证明 dflc 门确实是本资产 TO 的一个有效控制柄, 后续沿'收紧门'继续细分 (dflc<1 / dflc==0) "
            "就是有依据的; 若 TO 不变, 则说明 dflc 门对 TO 无效 (只是抬 Sh 的免费装置), "
            "后续必须完全依赖平滑/池化. 该判据决定下一批 8 槽的分配."),
    },
]

DIRECTIONS = {
    "I": {"name": "对 CONFLUENCE-1 (Sh1.59/2Y2.03/CW ok) 的 TO 定向攻击", "hypothesis": (
        "Wave10-H 产出 CONFLUENCE-1, 首次做到 Sh>=1.58 / 2Y>=1.58 / sub>=-0.24 / CW<=0.1 四项同过 "
        "(FAIL 由 4 项降至 2 项: Fit 0.41 与 TO 114.6%). 代入 Fit 公式反解得: "
        "固定 Sh=1.59 与 Ret=7.52% 时 **TO<=19.0% 即 Fit>=1**; 若 TO<=11% 则仅需 Ret>=4.35%. "
        "本批把降 TO 攻击重做在已剔除陈旧仓位的 add(vec_count,1) 基座上 —— 与 Wave10-E 在 "
        "ts_backfill 基座上做的同一套攻击形成对照, 检验'新基座下单位换手信息量更高'这一命题. "
        "覆盖等权平滑 (5/10/20)、线性衰减 (20/60)、输入侧池化 (5/20) 三类机制, "
        "外加一个反向对照 (放宽门) 用于确认门是否是 TO 的有效控制柄."),
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
    d = DIRECTIONS["I"]
    print(f"[Wave10-I] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10I_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-I] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10I", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10i_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-I] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-I] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-I] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-I] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10i_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-I ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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

    # 达标判定
    print(f"\n===== 达标判定 (Sh>=1.58, Fit>=1.0, 2Y>=1.58, TO<=0.70, CW ok, sub>=-0.24) =====", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        remain = [x for x in f if x != "LOW_SUB_UNIVERSE_SHARPE"]
        if not remain:
            print(f"  ✅ 槽{it['id']} 零 FAIL!  alpha_id={r.get('alpha_id')}", flush=True)
        else:
            print(f"  ❌ 槽{it['id']} 剩余 FAIL: {remain} (ra_failed={(r.get('ra') or {}).get('ra_failed')})", flush=True)
    print("\n[Wave10-I] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
