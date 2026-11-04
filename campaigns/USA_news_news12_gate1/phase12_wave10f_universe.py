# -*- coding: utf-8 -*-
"""Gate1 Wave10-F · universe 维度首次扫描 (TOP3000) —— 定向攻击 CONCENTRATED_WEIGHT.

=== 为什么这是本轮唯一还没动过的 settings 维度 ===
  历史 settings 分布: universe={TOP1000: 208, TOP500: 8}; decay={6: 216}; neutralization=
  {INDUSTRY: 192, MARKET: 16, STATISTICAL: 8}. 即 universe 除 8 条 TOP500 探针外恒为 TOP1000.
  且 fingerprint = MD5(expr, region, universe, delay, neutralization) **含 universe**
  => 换 universe 不会与任何历史指纹冲突, 是一个干净的全新实验轴.

=== 核心命题: CW 是"集中度"约束, 而集中度是相对池子规模定义的 ===
  CONCENTRATED_WEIGHT 的 limit = 0.1, 衡量的是组合权重的集中程度.
  SH165 在 TOP1000 上 L/S = 299/294 (总持仓 593 / 1000), 这个偏窄的持仓面正是 CW fail 的直接来源;
  家族所有 Sh>=1.5 的资产 TO 分支持仓面都在 267-310 一侧 (300/300 量级), 无一例外伴 CW fail;
  而家族所有**不**触发 CW 的样本持仓面都在 430-530 一侧 (S2 槽7 430/430、S2 槽8 503/501、
  pooled 家族 515/515).
  ==> **CW 与"持仓面 / 池子规模"的比值强相关, 而不是与 Sharpe 强相关.**
  把 universe 从 TOP1000 扩到 TOP3000, 若策略的持仓绝对数同比放大 (例如 593 -> 1500+),
  则权重集中度应机械下降 —— 这是**不损失任何 Sharpe 或 Ret** 就能攻 CW 的唯一候选路径:
  它不改变信号, 只改变信号被部署的横截面宽度.

=== 本批设计 ===
  把家族 8 条最具代表性的资产原样搬到 TOP3000, 构成 universe 配对实验:
    - 三条 SH165 家族 (新纪录资产 / 其 ts_mean5 版 / 其 group_rank 版)
    - 家族历史三巨头 (锚 N1eGk79E / d5K6wxlx / MP0n61ra-reverse)
    - Wave10-E 槽8 (linear-decay U/D, Sh 1.28)
    - pooled 高 R/TO 资产 (R/TO 0.403)
  每条都能与它在 TOP1000 下的实读指标直接配对, 从而分离出 universe 的纯处理效应.

=== 风险与判读标准 ===
  风险: 更大的池子含更多小盘/低流动性标的, 可能引入流动性因子暴露, 也可能使 Sh 下降
        (alpha 在小盘上未必同构) 或 TO 上升.
  判读: (a) 若 SH165@TOP3000 的 L/S 显著放大且 CW 由 fail 转 pass, 则 CW 墙破解成功,
         后续应在 universe 轴上继续细分 (TOP2000/3000) 并与最低 TO 结构组合;
        (b) 若 CW 仍 fail 而 L/S 放大, 则说明 CW 判定与池子规模无关 (可能是行业内集中度),
         应转向 group_rank(subindustry) 等更细的中性化;
        (c) 若 Sh 大幅下降则记录该资产具有 TOP1000 特异性, 不得外推.

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
UNIVERSE = "TOP3000"  # ★ 本批唯一新变量 (历史 208 条恒为 TOP1000)
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
        "id": 1, "type": "SH165_AT_TOP3000", "role": "PAIR", "baseline": "Sh1.65/Ret7.86/2Y2.10/TO119.8/CW fail",
        "expression": f"trade_when({DFLC2}, reverse(rank({RATIO})), 0)",
        "optimize_reason": (
            "【本批头号槽】全族新纪录资产 SH165 原样搬到 TOP3000. 它在 TOP1000 上是唯一同时做到 "
            "Sh 1.65 (>=1.58 过线) + Ret 7.86% (全族最高) + 2Y 2.10 (>=1.58 过线) + sub 1.30 的资产, "
            "仅剩 Fit 0.42 / TO 119.8% / CW 三墙. 其持仓面 299/294 偏窄是 CW fail 的直接嫌疑. "
            "本槽检验: 池子从 1000 扩到 3000 后, 持仓绝对数是否同比放大、CW 是否由 fail 转 pass、"
            "以及 Sh/Ret/TO 三者各自变化多少. 这是纯 settings 改动, 信号本身一字未变, "
            "因此任何指标变化都可干净地归因于 universe."),
    },
    {
        "id": 2, "type": "SH165_TSMEAN5_AT_TOP3000", "role": "PAIR", "baseline": "W10E槽3 Sh0.85/TO30.0/CW ok",
        "expression": f"trade_when({DFLC2}, reverse(rank(ts_mean({RATIO}, 5))), 0)",
        "optimize_reason": (
            "【已 TO 达标版 x 大池】Wave10-E 槽3 是 SH165 家族中唯一把 TO 压到 30% (已过 <=70% 门) 的变体, "
            "代价是 Sh 掉到 0.85 且 2Y 崩到 0.16. 它在 TOP1000 上**不触发 CW** (L/S 364/359). "
            "搬到 TOP3000 的目的有二: (a) 检验大池能否把它持股面与 Sharpe 同时抬高 —— 若 CW 不再是约束, "
            "则可用更激进的平滑换取更低 TO 而不必担心集中度; (b) 观察 2Y 0.16 是否随池子改变 "
            "(若 2Y 是小盘/流动性效应而非信号属性, 大池下应显著不同)."),
    },
    {
        "id": 3, "type": "ANCHOR_N1EGK79E_AT_TOP3000", "role": "PAIR", "baseline": "Sh1.63/TO116.9/2Y0.58/CW fail",
        "expression": f"reverse(rank(divide({CVW}, {BF120})))",
        "optimize_reason": (
            "【本次战役的原始锚】用户指定的起点 N1eGk79E 原样搬到 TOP3000. 它是用户 mandate 明确要求优化"
            "的资产, 已有精确的 TOP1000 基线 (Sh1.63/Fit0.31/TO116.9%/Ret4.26%/2Y0.58/CW fail). "
            "本槽是本次战役对'锚在大池下会怎样'这一问题的直接回答, 也是用户最关心的对照点: "
            "若大池能救活锚的 CW 与 2Y, 则本次 mandate 在未改任何算子的前提下即取得实质进展."),
    },
    {
        "id": 4, "type": "D5K6WXLX_AT_TOP3000", "role": "PAIR", "baseline": "Sh1.61/Ret7.70/2Y2.09/CW fail",
        "expression": f"reverse(rank({RATIO}))",
        "optimize_reason": (
            "【家族历史最佳 Fitness 结构】d5K6wxlx (Fit 0.41 为家族最高) 原样搬到 TOP3000. "
            "它是 SH165 去掉新鲜度门后的裸版 —— 与槽1 构成'门的有无 x universe'的二乘二设计的一角, "
            "可用于分离 frescura 门效应是否依赖池子规模. 另外它 ProdCorr 0.7033 仅超限 0.0033, "
            "若大池改变了其持仓结构, 相关性也可能随之改变 —— 这是唯一能顺带检验相关性是否"
            "随 universe 变化的槽位."),
    },
    {
        "id": 5, "type": "MP0N61RA_REV_AT_TOP3000", "role": "PAIR", "baseline": "|Sh|1.68 天花板",
        "expression": f"reverse(rank(divide({CVW}, vec_max({VHEX}))))",
        "optimize_reason": (
            "【Sharpe 天花板资产】MP0n61ra 的 reverse 生产版 (|Sh| 1.68 为全族最高) 搬到 TOP3000. "
            "其分母 vec_max(VHEX) 是当日最大冲击振幅, 天然稀疏 (L/S 仅 268/268), 是 CW fail 的典型形态. "
            "本槽是检验'universe 扩大能否修复稀疏分母型 CW'的最佳样本 —— 若大池下它的持仓面放大到 "
            "800+ 且 CW 转 pass, 则证明 CW 确实是池子规模的函数, 而非信号结构的函数."),
    },
    {
        "id": 6, "type": "SH165_GROUPRANK_AT_TOP3000", "role": "PAIR", "baseline": "W10E槽7 Sh0.49/TO50.9/CW ok",
        "expression": f"trade_when({DFLC2}, reverse(group_rank({RATIO}, industry)), 0)",
        "optimize_reason": (
            "【组内化 x 大池】Wave10-E 槽7 在 TOP1000 上给出 TO 50.9% (过门) + CW 不触发 (L/S 530/498) "
            "但 Sh 仅 0.49. 它是 SH165 家族中第二个'TO 过门且无 CW'的成员. 搬到 TOP3000 检验大池能否"
            "在保持这两个优点的同时把 Sharpe 拉回. group_rank(industry) 在更大的池子里每个行业包含的"
            "标的更多, 行业秩的估计应当更稳 —— 这是本槽特有的、只在 TOP1000 上无法检验的机制假设."),
    },
    {
        "id": 7, "type": "DECAYLIN_UD_AT_TOP3000", "role": "PAIR", "baseline": "W10E槽8 Sh1.28/Ret5.42/2Y1.40",
        "expression": f"reverse(rank(divide(ts_decay_linear({U}, 60), add(ts_decay_linear({U}, 60), ts_decay_linear({D}, 60)))))",
        "optimize_reason": (
            "【Wave10-E 最大意外 x 大池】Wave10-E 槽8 用 ts_decay_linear 替代等权 boxcar 池化, "
            "把同一结构的 Sharpe 从 0.61 抬到 1.28 (+2.1x), 证实了红队'长记忆实现 vs 短记忆机制'的诊断"
            "是真问题且可修; 但它 TO 107.4% 且持仓面仅 247/247 (CW 高嫌疑). 搬到 TOP3000 是检验"
            "'该结构的高 Sharpe 是否能在更宽池子上保留、同时修复 CW'的直接实验. "
            "它是目前家族中信息含量最新鲜的一条线, 值得优先在大池下复现."),
    },
    {
        "id": 8, "type": "POOLED_HIGH_RTO_AT_TOP3000", "role": "PAIR", "baseline": "R/TO0.403/Mgn8.04/Sh0.61",
        "expression": f"reverse(ts_rank(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))), 250))",
        "optimize_reason": (
            "【家族 R/TO 最高资产 x 大池】Wave10-A 槽6 是家族唯一跳出 R/TO 包络的样本 "
            "(R/TO 0.403 / Mgn 8.04bps / TO 5.2% / L/S 516/512 无 CW), 唯一短板是 Sh 0.61. "
            "它在 TOP1000 上已天然宽持仓 (516/512). 搬到 TOP3000 后其持仓面若放大到 1500+, "
            "横截面分位估计 (ts_rank) 的分布应当更平滑, 可能抬 Sharpe. "
            "本槽是全批唯一同时具备 '最低 TO + 最高 R/TO + 已无 CW' 三条属性的资产, "
            "若 universe 能补上它缺的 Sharpe, 它是最接近达标区的形态."),
    },
]

DIRECTIONS = {
    "F": {"name": "universe 维度首次扫描 (TOP3000) — 定向攻 CONCENTRATED_WEIGHT", "hypothesis": (
        "历史 208 条 alpha 的 universe 恒为 TOP1000 (仅 8 条 TOP500 探针), universe 是完全未扫描的"
        "settings 轴, 且计入 fingerprint 故不与历史冲突. 核心命题: CW 是集中度约束, 而家族中"
        "所有不触发 CW 的样本持仓面都在 430-530 一侧, 所有触发 CW 的 Sh>=1.5 资产持仓面都在"
        "267-310 一侧 —— 即 CW 与'持仓面/池子规模'强相关而非与 Sharpe 强相关. "
        "把池子从 1000 扩到 3000 应能在**不改变信号一字**的前提下机械降低权重集中度, "
        "这是攻 CW 唯一不牺牲 Sharpe/Ret 的候选路径. 本批把 8 条最具代表性的家族资产原样搬到"
        "TOP3000 构成 universe 配对实验, 分离纯处理效应."),
        "universe": UNIVERSE, "neutralization": "INDUSTRY", "slots": SLOTS},
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
    print(f"[Wave10-F] 字段字典 {len(known_fields)} | universe={UNIVERSE} decay={DECAY}", flush=True)

    d = DIRECTIONS["F"]
    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10F_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-F] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W10F", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w10f_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-F] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-F] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave10-F] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave10-F] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w10f_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave10-F (universe={UNIVERSE}, decay={DECAY}) =====", flush=True)
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
    print("\n[Wave10-F] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
