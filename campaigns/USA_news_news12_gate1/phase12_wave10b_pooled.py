# -*- coding: utf-8 -*-
"""Gate1 Wave10-B · POOLED 突破结构的参数空间展开 (decay=6).

=== Wave10-A 的两项硬结论 (实读, 非推测) ===

[证伪] settings.decay 不是降换手杠杆
  3 条严格配对 (同表达式/同 universe/neut/delay, 唯一变量 decay 6->25):
    锚 N1eGk79E  TO 116.9% -> 122.8%  (比值 1.050)
    d5K6wxlx     TO 120.1% -> 117.0%  (比值 0.974)
    MP0n61ra     TO 128.5% -> 126.5%  (比值 0.984)
  ==> TO 变动 <5%, decay 对换手无实质作用. Sh 略降 6-9%. 该维度关闭.
  副产物: decay=25 使锚的 Ret 4.26%->5.92% (+39%) 与 2Y 0.58->1.23 (+112%),
  但因 Sh 同降, Fit 净变动仅 +3%.

[证实] 「输入侧池化重参数化 + ts_rank 输出」首次打破 Sh <-> R/TO 反相关
  Wave10-A 槽6 @decay=25:
    reverse(ts_rank(divide(ts_sum(news_max_up_amt,60), add(ts_sum(news_max_up_amt,60),
                                                          ts_sum(news_max_dn_amt,60))), 250))
    Sh 0.61 | Fit 0.25 | TO 5.2% | Ret 2.09% | R/TO 0.403 | Mgn 8.04bps
    2Y 1.25 | sub 0.52 | rn 0.84 | L/S 516/512 | DD 6.1%   | 无 CW fail
  对比家族历史包络:
    R/TO  最高 0.125 (omoX8edl, Sh 0.57)      -> 本槽 0.403  = 3.2x 跃升
    Margin 最高 ~1.3bps (d5K6wxlx 1.28bps)    -> 本槽 8.04bps = 6.3x 跃升
    TO 已进入 <=11% 的 Fit turnover-floor 保护区
    宽持仓 516/512 => 家族唯一不触发 CONCENTRATED_WEIGHT 的高 R/TO 结构
  这是 176 槽以来第一次出现"家族包络之外"的样本, 证明反相关不是物理定律.

=== 本批目标 ===
  槽6 距达标仍有 Gap (需 Sh^2 * Ret >= 0.11, 现为 0.0078).
  本批在该结构上做五维正交展开, 寻找 Sh 的提升路径:
    N  池化窗口   20 / 60(已知) / 120
    M  ts_rank窗口 250(已知) / 500 / 无输出层(纯 rank 对照)
    口径 金额 (max_up_amt/dn_amt) vs 百分比 (max_up_ret/dn_ret)
    分子 U/D  vs  CTN(close-ton_last)  vs  CVW(close-vwap)
    输出层 ts_rank vs rank (验证 ts_rank 层的边际贡献)
  全部 decay=6 (与历史 216 条同口径, 便于横向比较), 槽1 与 Wave10-A 槽6
  构成跨批 decay 配对.

=== 的铁律 ===
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
from quant_framework.core.sim_runner import SimBatchRunner  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402
from quant_framework.core.gatekeeper import Gatekeeper  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY, REGION, DELAY = "news", "USA", 1
DECAY = 6  # 回到历史口径 (已证实 decay 非换手杠杆)
TRUNCATION = 0.025
NAN_HANDLING = "ON"

U, D = "news_max_up_amt", "news_max_dn_amt"
UR, DR = "news_max_up_ret", "news_max_dn_ret"
EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
VHEX = "high_price_excursion_stddev"


def pooled(num_field, den_field, n):
    return f"divide(ts_sum({num_field}, {n}), add(ts_sum({num_field}, {n}), ts_sum({den_field}, {n})))"


SLOTS = [
    {
        "id": 1, "type": "POOLED_N60_M250_REPLICATE", "role": "PAIR", "baseline": "W10A-slot6@decay25",
        "expression": f"reverse(ts_rank({pooled(U, D, 60)}, 250))",
        "optimize_reason": (
            "【结构复现 + 跨批 decay 配对】Wave10-A 槽6 结构原样在 decay=6 下重跑, 目的有二: "
            "(a) 复现 R/TO 0.403 与 Mgn 8.04bps 这两个家族外数字是否为偶发; "
            "(b) 与 decay=25 构成第二个 decay 配对点, 检验 decay 效应对'输入侧池化'这类慢结构是否"
            "同样是中性的. 机制: 先在 60 日窗口上池化 News Max Up / Down Amt 的数量级得到该股潜在的"
            "新闻 aggregé per asymmetry parameter theta_hat (先池化分子分母再做比值 = 对 theta 的合并估计,"
            "而非先算日比值再平滑的衰减); 再取 theta_hat 自身 250 日历史分位. 池化使估计误差 ~1/sqrt(N) "
            "从而有可能抬 Sharpe, 日变化 ~1/N 从而压 Turnover, 两者方向相反故可打断家族反相关."),
    },
    {
        "id": 2, "type": "POOLED_N20_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank({pooled(U, D, 20)}, 250))",
        "optimize_reason": (
            "【池化窗口下界探针】N=20. 存在偏差-方差最优窗口: N 太小则池化估计方差大(SHARPE 低), "
            "N 太大则潜在参数 theta 本身漂移被抹平(实读警示: 裸池化 N=120 的 Sharpe 已翻负为 -0.16). "
            "本槽与槽3 共同标定 N 的响应曲线形状. 机制不变: 新闻 characteristiqué asymmetry 的局部估计."),
    },
    {
        "id": 3, "type": "POOLED_N120_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank({pooled(U, D, 120)}, 250))",
        "optimize_reason": (
            "【池化窗口上界探针】N=120. 若这里 Sharpe 反而高于槽1(N=60), 说明 ts_rank 输出层已吸收了"
            "慢漂移, 长池化反而更纯粹; 若低于槽1 则确认存在最优窗口. 已知裸池化 N=120 翻负(-0.16), "
            "若本槽(加 ts_rank 层后)转正则可结论: ts_rank 输出层本身就是使长池化可用的关键, "
            "该结论直接决定后续批次是继续加长还是收短."),
    },
    {
        "id": 4, "type": "POOLED_RET_N60_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank({pooled(UR, DR, 60)}, 250))",
        "optimize_reason": (
            "【口径对照: 金额 -> 百分比】改用 news_max_up_ret / news_max_dn_ret (新闻后相对新闻时刻价的"
            "百分比涨跌). 关键差别: 百分比口径自动完成价格尺度归一化, 使高价股与低价股在同一横截面上"
            "可比 —— 这是直接攻击 omoX8edl '最高 R/TO 却只有 Sh 0.57' 的尺度污染缺陷的第二条路线"
            "(第一条是 ts_rank 同方差化). 代价: max_up_ret 覆盖率 0.8458 低于 amt 的 0.9692, 广度略降."),
    },
    {
        "id": 5, "type": "POOLED_N60_M500", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank({pooled(U, D, 60)}, 500))",
        "optimize_reason": (
            "【自历史窗口上探】ts_rank 窗口 250 -> 500. ts_rank(x, M) 输出 x 在自身过去 M 日分布中的"
            "分位, M 越大则越接近'该股历史常态', 单个交易日的新息影响越小 => TO 进一步下降. "
            "若本槽 TO 显著低于 5.2% 而 Ret 不按比例下降, 则 R/TO 可继续抬升; 反之若 M 已饱和则 250 为最优. "
            "家族历史上 ts_rank 主窗口在 250 停住未向上探, 这是一个未测方向."),
    },
    {
        "id": 6, "type": "POOLED_CTN_N60_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank(divide(ts_sum(subtract({EOC}, {TON}), 60), add(ts_sum(vec_count({VHEX}), 60), 1)), 250))",
        "optimize_reason": (
            "【家族最强分子迁移到池化结构】把 CTN (close - ton_last, 即新闻时刻到收盘的漂移, "
            "decay=6 下 d5K6wxlx 用它拿到 Sh1.61/Ret7.70%/2Y2.09 —— 家族最高 Ret) 替换 U/D 分子, "
            "分母改为 60 日累积新闻事件条数 => 得到'每条新闻的平均漂移' theta_hat (以新闻关注度归一化的"
            "池化估计), 再取自身 250 日分位. 这是把 Family 内两个最强的已知成分 (CTN 分子的高 Ret, "
            "与 Wave10-A 槽6 结构的高 R/TO) 做首次组合. 若 Ret 显著抬升而 TO 仍低, 则直接逼近"
            "Fit>=1 所需区. 本槽是全批理论与 Book 值最高的一个."),
    },
    {
        "id": 7, "type": "POOLED_CVW_N60_M250", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank(divide(ts_sum(subtract({EOC}, {VWAP}), 60), add(ts_sum(vec_count({VHEX}), 60), 1)), 250))",
        "optimize_reason": (
            "【CVW 分子同构对照】与槽6 完全同构, 仅把分子换成 CVW (close - 新闻时刻至收盘的 VWAP). "
            "CVW 是不带在点 attention 的尾盘订单流压力净位移, CTN 则是相对新闻时刻价格的净位移. "
            "两者信息集互补: CTN 含隔夜/盘中成分, CVW 更纯粹地度量尾盘流动性冲击. 锚 N1eGk79E 用的正是"
            "CVW (家族最高 Sharpe 1.63). 与槽6 构成单变量对照, 直接读出'分子选择'对该结构的边际贡献."),
    },
    {
        "id": 8, "type": "POOLED_N60_PLAINRANK", "role": "NEW", "baseline": None,
        "expression": f"reverse(rank({pooled(U, D, 60)}))",
        "optimize_reason": (
            "【ts_rank 输出层的边际贡献 — 消融对照】与槽1 唯一差别是输出层由 ts_rank(x,250) 换成 "
            "横截面 rank(x). 目的: 定量分离'输入侧池化'与'ts_rank 自历史归一化'各自贡献多少. "
            "若本槽 R/TO 远低于槽1 的 0.403, 则证实 ts_rank 层是该结构的关键(因为 ts_rank 把"
            "输出压成 [0,1] 均匀分布 -> 横截面同方差且无尺度污染); 反之则池化本身即主因. "
            "该结论直接决定后续批次应在输出层还是输入层继续加码. 对照组: 历史上 QPYAZbEp "
            "(裸 ts_sum 60 比值, 无任何包装) Sh 0.19/Ret 0.95%/TO 8.56%/R-TO 0.110."),
    },
]

DIRECTIONS = {
    "B": {"name": "POOLED 突破结构五维展开 (decay=6)", "hypothesis": (
        "Wave10-A 槽6 首次给出家族包络之外的样本 (R/TO 0.403 = 3.2x 包络, Mgn 8.04bps = 6.3x 历史最高, "
        "TO 5.2% 进入 turnover floor 保护区, L/S 516/512 无 CW), 证明 Sh<->R/TO 反相关可被"
        "'输入侧池化重参数化 + ts_rank 同方差输出'打断. 本批在该结构上做五维正交展开 "
        "(池化窗口 N / 自历史窗口 M / 金额-百分比口径 / 分子 U-D vs CTN vs CVW / 输出层 ts_rank vs rank), "
        "目标找到 Sh 的提升路径. 达标区为 Sh^2 * Ret >= 0.11 (TO<=11%)."),
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
        n_fields = len(tokens & known_set)
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        print(f"  [pre-audit] slot{it['id']} role={it['role']:<4} ops={audit['operator_count']:>2} "
              f"fields={n_fields} len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:82]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符: {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")
        if len(fixed) > 900:
            raise ValueError(f"slot{it['id']} 超长 {len(fixed)} > 900")
        if len(it["optimize_reason"]) < 120:
            raise ValueError(f"slot{it['id']} optimize_reason 过短, 违反铁律5")


def check_dup(items, neutralization, universe):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    dups = []
    for it in items:
        h = corrector.compute_fingerprint(it["expression"], REGION, universe, DELAY, neutralization)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        if cur.fetchone():
            dups.append((it["id"], it["expression"][:70]))
    conn.close()
    print(f"  [dup-check] 历史已测 {len(dups)} 条: {dups}", flush=True)


async def submit_batch(items, state_path, neutralization, universe, tag):
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
                    json.dump({"location": location, "submitted_at": int(time.time()), "decay": DECAY}, f)
                print(f"[submit-{tag}] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt}: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    return location


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave10-B] 字段字典 {len(known_fields)} 个装载 | decay={DECAY}", flush=True)

    direction = "B"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "role": s["role"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10B_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave10-B] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
    check_dup(items, d["neutralization"], d["universe"])

    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w10b_{direction}_{ts}.json")
    json.dump({"seed_id": f"GATE1W10B_{direction}", "region": REGION, "universe": d["universe"],
               "delay": DELAY, "decay": DECAY, "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(batch_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[Wave10-B] 批次文件: {batch_path}", flush=True)

    state_path = os.path.join(CAMPAIGN, f"state_w10b_{direction}.json")
    loc = await submit_batch(items, state_path, d["neutralization"], d["universe"], direction)
    if not loc:
        print("[Wave10-B] 无 location, 退出", flush=True)
        return

    print("[Wave10-B] 静默轮询中 (前 60s 不输出)...", flush=True)
    waited = 0
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(loc)
            st = chk.get("status")
            if waited >= 60:
                print(f"  [poll] {st} progress={chk.get('progress', 0)} t={waited}s", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                print(f"  [poll] 终态 {st} (t={waited}s)", flush=True)
                break
        except Exception as e:
            print(f"  [poll] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)
        waited += 20

    fetch = await BrainModule.fetch_multi_simulation_result(loc)
    results = fetch.get("alpha_results", [])
    if not results:
        print(f"[Wave10-B] fetch 空! {str(fetch)[:500]}", flush=True)
        return
    res_path = os.path.join(CAMPAIGN, f"batch_w10b_{direction}_{ts}_result.json")
    json.dump({"alpha_results": results}, open(res_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[Wave10-B] 结果已存: {res_path}", flush=True)

    # 打印结果表
    print(f"\n===== Wave10-B {d['name']} (decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} "
          f"{'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>10} {'DD%':>6}", flush=True)
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
    print("\n[Wave10-B] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
