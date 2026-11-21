# -*- coding: utf-8 -*-
"""Gate1 Wave10-C · ts_rank 层向"活着的高 Sh 低 TO 分支"迁移 (decay=25).

=== 前两批的结算 ===

[Wave10-A 证伪] decay 对日频快结构无降 TO 作用
  同表达式配对 decay 6->25, TO 比值 0.974 / 0.984 / 1.050 => 关闭该维度(对快结构).

[Wave10-A→B 交叉配对 修正] decay 对"已慢"结构有效
  同一 pooled 表达式: decay=6 TO 8.8% -> decay=25 TO 5.2% (×0.59, 降 41%).
  ==> decay 的有效性取决于信号自相关尺度: 对已慢的信号(持仓期~11天)有进一步平滑作用,
      对日频重排的信号(持仓期<1天)跟不上. 本批目标区是"中慢"结构, 故沿用 decay=25.

[Wave10-B 五维展开] 关键定量结论
  N=池化窗口 20/60/120 -> Sh 0.30 / 0.48 / 0.42, R-TO 0.072 / 0.190 / 0.202
    * N=120 未翻负(裸结构 N=120 为 -0.16) => ts_rank 层使邻域稳定, 反证 "data-mined 孤峰"
    * N=120 的 R/TO 0.202 高于 N=60 的 0.190, 长池化在这个 bundle 里是正贡献
  金额口径 vs 百分比口径 -> Sh 0.48 vs 0.48 => 不存在价格量纲污染
  ts_rank 层的边际贡献: 纯 rank 对照 Sh 0.14 -> ts_rank Sh 0.48 (×3.4)
  CTN / CVW 分子迁移 -> Sh 0.06 / -0.28 => U/D 是该结构的必要成分, 不可替换

[红队 conjunction: 接受的部分] ★本批的设计前提
  红队判 Wave10-A 槽6 为 INCOMPLETE_SIGNAL, 其中一条核心指控成立且必须接受:
    "Ret/TO 是 1/TO 型比率, TO 下降时该比值机械发散, 历史上唯一更高的样本
     e76Po6eM (R/TO 4.373) 是 L/S=0/0 的病态回测;
     而本样本 Sharpe 0.61 在家族仅第 51 百分位, Calmar 0.34 vs 家族最优 1.59"
  ==> **Sharpe 是不可协商的硬门槛 (LOW_SHARPE>=1.58). Ret/TO 只能作为结构线索,
      不能作为主排序指标.** 本批放弃继续在低 Sh 的 pooled 线上做局部微调,
      改为把"已被 Wave10-B 定量证明能抬 Sharpe ×3.4 的 ts_rank 同方差输出层"
      迁移到当前**唯一同时具备较高 Sh 与较低 TO** 的存活分支上.

=== 存活分支清单 (Sh>=1.0 且 TO<=70%, 全部无 CW fail) ===
  S2-槽7  trade_when(vec_count>0, reverse(rank(divide(U, add(U,D)))), 0)
          Sh 1.17 / TO 58.6% / Ret 4.06% / 2Y 1.18 / L-S 430/430
  6XAQKZgK reverse(rank(ts_backfill(divide(CTO, add(vec_count+1)), 60)))
          Sh 1.07 / TO 40.6% / Ret 4.63% / 2Y 0.99 / R-TO 0.114 (家族 R/TO 第二高)
  YPxOGboo reverse(group_rank(ts_backfill(divide(U, add(U,D)), 60), industry))
          Sh 1.17 / TO 37.8% / Ret 3.70% / 2Y 0.68
  这三条是目前全族唯一处在 "Sh 接近可行 + TO 已过门槛" 交集的资产, 本批围绕它们做输出层升级.

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
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY, REGION, DELAY = "news", "USA", 1
DECAY = 25  # 对已慢结构可再降 TO (已配对实证 ×0.59)
TRUNCATION = 0.025
NAN_HANDLING = "ON"

U, D = "news_max_up_amt", "news_max_dn_amt"
UR, DR = "news_max_up_ret", "news_max_dn_ret"
EOC, TON = "news_eod_close", "news_ton_last"
VHEX = "high_price_excursion_stddev"
CNT1 = f"add(vec_count({VHEX}), 1)"

UD = f"divide({U}, add({U}, {D}))"
POOL60 = f"divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60)))"
POOL180 = f"divide(ts_sum({U}, 180), add(ts_sum({U}, 180), ts_sum({D}, 180)))"
POOLRET120 = f"divide(ts_sum({UR}, 120), add(ts_sum({UR}, 120), ts_sum({DR}, 120)))"

SLOTS = [
    # ---- A 组: 存活分支 Sh 1.07-1.17 的输出层升级 (本批核心赌注) ----
    {
        "id": 1, "type": "S2G7_PLUS_TSRANK", "role": "UPGRADE", "baseline": "S2-槽7 Sh1.17/TO58.6",
        "expression": f"trade_when(greater(vec_count({VHEX}), 0), reverse(ts_rank({UD}, 250)), 0)",
        "optimize_reason": (
            "【存活分支 #1 + ts_rank 输出层】S2-槽7 = trade_when 硬事件门 + reverse(rank(U/(U+D))) "
            "是全族唯一 Sh>=1.15 且 TO<=60% 且无 CW 的样本 (Sh1.17/TO58.6%/Ret4.06%/2Y1.18/L-S 430/430). "
            "本槽唯一改动: 把输出层 rank 换成 ts_rank(250) —— 该替换已被 Wave10-B 槽1 vs 槽8 定量证明"
            "能抬 Sharpe ×3.4 (0.14 -> 0.48). 机制差异: rank 是纯横截面排序, 输出分布随每日截面形状漂移;"
            "ts_rank 是'该股当前值在自身 250 日历史分布中的分位', 同时完成①消去个股水平异质性"
            "(有的股长期偏 down-heavy) ②把输出压成 [0,1] 均匀分布实现横截面同方差. 保留 trade_when 硬事件门"
            "与第三参 0 (硬平仓) —— S2 实证这是消除 CW 的关键算子. 若本槽 Sh>=1.58 且 TO<=58.6% 保持, "
            "则 Fit = 1.58*sqrt(0.0406/0.586) = 0.42, 仍需 Ret 提升; 但这是全族最接近的一支."),
    },
    {
        "id": 2, "type": "S2G7_PLUS_TSRANK100", "role": "UPGRADE", "baseline": "S2-槽7 Sh1.17/TO58.6",
        "expression": f"trade_when(greater(vec_count({VHEX}), 0), reverse(ts_rank({UD}, 100)), 0)",
        "optimize_reason": (
            "【同一结构, ts_rank 窗口下探】与槽1 唯一差别 ts_rank 窗口 250 -> 100. "
            "必要性: ts_rank(x,M) 在 x 处于自身历史分布**尾部**时对输入敏感度趋于 0 (分布密度 f(z)->0), "
            "而 pooled ratio 的尾部恰恰是'刚经历最大不对称冲击'的股票 —— 红队据此判 INCOMPLETE_SIGNAL, "
            "指控该结构'在最该交易的时刻结构性不交易'. 缩短 M 可抬高 f(z) 均值、缓解死区. "
            "与槽1 构成 M 的响应标定: 若 M=100 优于 M=250 则确认死区假说成立且可修复, "
            "若更差则 250 已饱和."),
    },
    {
        "id": 3, "type": "6XAQKZGK_PLUS_TSRANK", "role": "UPGRADE", "baseline": "6XAQKZgK Sh1.07/TO40.6/R-TO0.114",
        "expression": f"reverse(ts_rank(ts_backfill(divide(subtract({EOC}, {TON}), {CNT1}), 60), 250))",
        "optimize_reason": (
            "【存活分支 #2 + ts_rank 输出层】6XAQKZgK = reverse(rank(ts_backfill(CTO/(vec_count+1), 60))) "
            "是家族 R/TO 第二高样本 (0.114) 且 Sh 1.07 / TO 40.6% / Ret 4.63% / 2Y 0.99 / 无 CW. "
            "它已经同时做到 'TO 过门槛 + Ret 接近门槛 + Sh 存活'. 本槽把输出层换成 ts_rank(250). "
            "机制加分项: 该结构是稀缺的**稀疏**(ts_backfill 60 携带), 祖先 redteam 指出'家族一直在工程"
            "修复 NaN 太多, 而稀疏本身就是低 TO 的来源' —— 本槽保留该稀疏性不受破坏. "
            "若 ts_rank 的 ×3.4 Sharpe 效应在此复现 (1.07 -> ~1.5+), 且 TO 维持 40% 上下, "
            "则 Fit = Sh*sqrt(Ret/TO) 有望进入 0.6-0.9 区间, 是全族前所未有的位置."),
    },
    {
        "id": 4, "type": "YOXOGBOO_PLUS_TSRANK", "role": "UPGRADE", "baseline": "YPxOGboo Sh1.17/TO37.8",
        "expression": f"reverse(ts_rank(group_rank(ts_backfill({UD}, 60), industry), 250))",
        "optimize_reason": (
            "【存活分支 #3 + ts_rank 输出层】YPxOGboo = reverse(group_rank(ts_backfill(U/(U+D),60), industry)) "
            "Sh 1.17 / TO 37.8% / Ret 3.70%. 本槽在其外层追加 ts_rank(250): 保留 group_rank 的行业内去水平"
            "作用, 再用 ts_rank 消去个股自身的历史水平差异. 双层去均值 (横截面行业 + 时序自身) 是本次"
            "未测过的组合: group_rank 处理'行业间不可比', ts_rank 处理'个股自身水平漂移', "
            "理论上把信号净化为纯粹的'相对自身历史 + 相对同行的双重异常度'. 与槽1/槽3 构成三条不同"
            "存活分支的输出层升级对照."),
    },

    # ---- B 组: pooled 线上的剩余高价值结构 ----
    {
        "id": 5, "type": "GROUPMEAN_X_TSRANK", "role": "NEW", "baseline": "omoX8edl Ret7.11% / QPYAZbEp Ret0.95%",
        "expression": f"reverse(ts_rank(group_mean({POOL60}, 1, industry), 250))",
        "optimize_reason": (
            "【Ret 放大器 x 同方差器: 首次叠加】家族唯一的 Ret>7% (在低 TO 区) 来源已被识别且量化: "
            "omoX8edl = group_mean(pooled60, 1, industry) 得到 Ret 7.11%, 而同一核心裸版 QPYAZbEp 只有 "
            "Ret 0.95% —— group_mean(industry) 带来 7.5x 的 Ret 放大 (代价是 TO 抬到 56.7%、Sh 仅 0.57). "
            "同时 Wave10-B 定量证明 ts_rank 层能把同一核心的 Sharpe 从 0.14 抬到 0.48 (×3.4) 并压 TO. "
            "本槽把两者叠加: 先用 group_mean 提取行业共同新闻因子的小噪声估计并保留幅度 (攻 Ret), "
            "再用 ts_rank 做同方差化与去异方差 (攻 Sharpe / TO). 机制上这是把'估计精度'与'横截面可比性'"
            "这两个此前互相打架的目标分别交给两个专门算子处理. 本批中理论与 Book 值最高的一槽."),
    },
    {
        "id": 6, "type": "TSRANK_THEN_GROUPRANK", "role": "NEW", "baseline": None,
        "expression": f"reverse(group_rank(ts_rank({POOL60}, 250), industry))",
        "optimize_reason": (
            "【与槽5 的算子顺序对照】同为 group_mean/group_rank 与 ts_rank 的双层组合, 但把 industry 层放在"
            "**外层**且用 group_rank (非 group_mean). 目的: 分离'内层/外层的次序'与'保幅度/去幅度'两项贡献. "
            "group_rank 在外层会把内层 ts_rank 的 [0,1] 输出再压成行业内的均匀秩 —— 最彻底的双重去尺度化, "
            "但会牺牲 omoX8edl 那种 Ret 放大 (背包幅度). 与槽5 (group_mean 在内+保幅度) 构成干净对照, "
            "答案决定后续应追求 'Ret 优先' 还是 'Sharpe 优先'."),
    },
    {
        "id": 7, "type": "POOLED_N180_M250", "role": "NEW", "baseline": "W10B 槽3 N=120 Sh0.42/R-TO0.202",
        "expression": f"reverse(ts_rank({POOL180}, 250))",
        "optimize_reason": (
            "【延长 N 到 180】Wave10-B 测得 N=120 的 R/TO (0.202) 已略高于 N=60 (0.190) 且 Sh 未翻负, "
            "说明在该 ts_rank bundle 下长池化仍是正贡献, 与'裸结构 N=120 翻负'完全不同. "
            "本槽把 N 推到 180 探 'N 的收益是否仍在上升'. 若为正则 N 的最优值可能远大于此前假定的 60, "
            "这将改变整个 pooled 线的搜索中心 (意味着 theta 的真实漂移尺度比家族假定的慢得多)."),
    },
    {
        "id": 8, "type": "POLLED_RET120_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank({POOLRET120}, 250))",
        "optimize_reason": (
            "【百分比口径 x 长池化】Wave10-B 槽4 已证明在 N=60 下金额口径与百分比口径 Sharpe 完全相同 "
            "(0.48 vs 0.48) => 该结构不存在价格量纲污染 (x = sum(P*u%)/sum(P*u%+P*d%) 中价格水平精确抵消). "
            "本槽在 N=120 下复验该结论是否稳健, 并同时提供 'N=120 百分比口径' 这一新的 nm record. "
            "若出现显著差异, 则说明 scale 效应在长池化下重新出现 (因为 ret 口径的覆盖率 0.8458 < "
            "amt 的 0.9692, 池化窗口越长, 缺失观测的累积效应越大), 该信息对 N 的选取有直接指导意义."),
    },
]

DIRECTIONS = {
    "C": {"name": "ts_rank 输出层向存活分支迁移 (decay=25)", "hypothesis": (
        "接受红队指控: Sharpe 是不可协商的硬门槛, Ret/TO 因是 1/TO 型比率会随 TO 下降机械发散, "
        "不能作为主排序指标. 但 'ts_rank 自历史分位输出层可把 Sharpe 抬 ×3.4' 这一效应已被 Wave10-B "
        "槽1 vs 槽8 干净地定量证明 (0.14 -> 0.48). 因此本批不再在低 Sh 的 pooled 线上做局部微调, "
        "而把该输出层迁移到当前唯一同时具备 'Sh 接近可行 + TO 已过门槛 + 无 CW' 的三条存活分支 "
        "(S2-槽7 Sh1.17/TO58.6, 6XAQKZgK Sh1.07/TO40.6/R-TO0.114, YPxOGboo Sh1.17/TO37.8) 上, "
        "并叠加 group_mean 的 Ret 放大效应."),
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
        print(f"  [pre-audit] slot{it['id']} role={it['role']:<7} ops={audit['operator_count']:>2} "
              f"fields={nf} len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:76]}", flush=True)
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
    print(f"[Wave10-C] 字段字典 {len(known_fields)} | decay={DECAY}", flush=True)

    direction = "C"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "role": s["role"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10C_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-C] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": f"GATE1W10C_{direction}", "region": REGION, "universe": d["universe"],
               "delay": DELAY, "decay": DECAY, "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10c_{direction}_{ts}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    exprs = [it["expression"] for it in items]
    loc = None
    for attempt in range(1, 6):
        try:
            sub = await BrainModule.submit_multi_simulation(
                alpha_expressions=exprs, region=REGION, universe=d["universe"], delay=DELAY,
                decay=DECAY, neutralization=d["neutralization"], truncation=TRUNCATION,
                pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                language="FASTEXPR", visualization=False)
            if "error" in sub:
                raise RuntimeError(str(sub)[:160])
            loc = sub["location"]
            print(f"[submit-C] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-C] attempt {attempt} failed: {str(e)[:200]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        print("[Wave10-C] 无 location, 退出", flush=True)
        return

    print("[Wave10-C] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-C] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10c_{direction}_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-C {d['name']} (decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'角色':<8} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} "
          f"{'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>10} {'DD%':>6}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        print(f"{it['id']:>2} {it['role']:<8} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} "
              f"{to * 100:>7.1f} {ret * 100:>7.2f} {(ret / to) if to else 0:>7.3f} "
              f"{(m.get('margin') or 0) * 1e4:>7.2f} {m.get('two_year_sharpe') or 0:>6.2f} "
              f"{m.get('sub_universe_sharpe') or 0:>5.2f} {m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave10-C] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
