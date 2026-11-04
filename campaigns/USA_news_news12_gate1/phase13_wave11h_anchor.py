# -*- coding: utf-8 -*-
"""Gate1 Wave11-H · 多锚点轴 + CW 修复 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== 立项依据 (Wave11-G 回收 + 红队四审收敛) ===
Wave11-G 判决: DIV 家族全军覆没 (四窗全负 Sh); 短窗语义健康; 门构造双重证伪;
pre_vwap 第三锚点首测 = 家族 Ret 第二高 (8.25%) 但 CW FAIL.

红队四审的 CW 定律 (432 行新实证): 扩展时段锚点自身即风险源 (post 10/12 fail,
pre 1/1 fail) —— 只有 bf2 改变名集构成 (修复先验 75-80%), winsorize/ts_rank/
VHEX 只改数值分布. VHEX+1 非万能 (9qE3k7mr post 锚+同分母直接反例).
预期下修: Sh1.58 无现实路径 (需 +0.44 vs 历史单构造最大 +0.13; G8 守恒乘积
0.087 远低于精英带 0.15-0.19). 本批定位 = CW 修复方法判决 + pre 轴强度隔离
+ 可能的 Ret 纪录; 最优可行剖面 = 把 G8 的 4 fails 压到 3 项 (CW 转绿).

=== 本批 8 条 = 锚点轴系统展开 ===
H1  pre 双锚 + winsorize(std=2)   —— CW 修复#1, 最保 Ret (孪生 winsorize 中性)
H2  pre 双锚 + ts_rank250 输出层   —— CW 修复#2 + Sh 抬升 + 唯一 2Y 上行候选
H3  pre 双锚 + bf2 冻结           —— CW 修复先验最高 (改名集构成) + 唯一 TO 故事
H4  pre 单锚隔离                  —— pre 轴归因基准
H5  pre 单锚 + VHEX 分母          —— 跨锚点推广判决 (先验最低)
H6  post 双锚 (盘后出清)          —— sum vs product 毒性判决 + post 2Y 引擎
H7  main 双锚 (全日均衡)          —— blend 轴 CW 安全对照 (锚点三角收尾)
H8  量能确认的压力                 —— 唯一处女字段 + 新机制 (abs 缺陷已预注册)
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

EOC, VWAP = "news_eod_close", "news_eod_vwap"
PVWAP, OVWAP, MVWAP = "news_pre_vwap", "news_post_vwap", "news_main_vwap"
VHEX = "vec_count(high_price_excursion_stddev)"
VOLZ = "news_vol_stddev"

DA_PRE = f"divide(add(subtract({EOC}, {VWAP}), subtract({EOC}, {PVWAP})), {VWAP})"
CVW = f"subtract({EOC}, {VWAP})"

SLOTS = [
    {
        "id": 1, "type": "H1_PRE_WINSOR", "role": "CW_FIX",
        "baseline": "G8 (无winsorize) Sh1.14/TO123.7%/Ret8.25%/2Y1.80/CW FAIL",
        "expression": f"reverse(rank(divide(winsorize(add({CVW}, subtract({EOC}, {PVWAP})), std=2), {VWAP})))",
        "optimize_reason": (
            "【pre 双锚 + winsorize(std=2) · CW 修复#1】对双锚分子做 2 倍标准差缩尾. "
            "红队四审 CW 定律: winsorize 只改数值分布不改名集构成, 修复先验中等 (~50%), "
            "但是全批最保 Ret 的槽 (孪生 xA1ZKGzg 实测 winsorize 中性 +0.02pp Ret, "
            "且是全批唯一有 Ret 纪录路径的槽, P(Ret>8.47%)≈25-30%). 机理: G8 的 CW fail 来自"
            "双锚乘积放大的极端名 (pre_vwap cov 0.8289 的低覆盖名), 缩尾直接削减这些极端值"
            "的权重贡献. 经济学不变: 收盘价同时偏离新闻后 VWAP 与盘前 VWAP = 全日总位移中"
            "可归因于新闻后压力的部分. 成功标准: CW 转绿且 Ret >= 7.5% (Ret 引擎成立); "
            "证伪: CW 仍 fail 且 Ret < 7% (缩尾无效)."),
    },
    {
        "id": 2, "type": "H2_PRE_TSRANK250", "role": "CW_FIX",
        "baseline": "G8 Sh1.14/Ret8.25%/2Y1.80/CW FAIL; DUALP 上 ts_rank250 壳 +0.12 Sh",
        "expression": f"reverse(ts_rank({DA_PRE}, 250))",
        "optimize_reason": (
            "【pre 双锚 + ts_rank250 输出层 · CW 修复#2 + Sh 抬升】把外层 rank 换成 ts_rank250. "
            "三重机理: (a) ts_rank 输出有界 [0,1] -> reverse 后 [-1,0] -> 权重天然有界, "
            "直接抑 CW (全库实证有界输出层的 CW 通过率显著高于无界比值); (b) 家族实证该壳在 "
            "DUALP 上 +0.12 Sh, 可能迁移; (c) 只选「该股票自身 250 日历史上极端」的双锚偏离, "
            "把横截面比较换成时序极端度, 与经济学的「异常位移」更贴合. 红队四审: 全批唯一 2Y "
            "上行候选 (2Y 2.1-2.4). 成功标准: CW 转绿且 (Sh >= 1.25 或 2Y >= 2.10); "
            "证伪: Sh <= 1.00 (壳不迁移)."),
    },
    {
        "id": 3, "type": "H3_PRE_BF2", "role": "CW_FIX",
        "baseline": "G8 Sh1.14/TO123.7%/CW FAIL; DUAL_R bf2 孪生 Ret-0.79pp/Sh-0.29",
        "expression": f"reverse(rank(ts_backfill({DA_PRE}, 2)))",
        "optimize_reason": (
            "【pre 双锚 + bf2 冻结 · CW 修复先验最高】红队四审 CW 定律: 只有 bf2 改变名集构成"
            " (冻结 2 天使低覆盖名的权重不再由单日极端值主导), 修复先验 75-80%, 是全批最可能"
            "CW 转绿的槽; 同时是唯一有 TO 故事的槽 (预期 TO 85-105%). 代价: bf 陈旧税 (孪生 "
            "DUAL_R bf2: Ret -0.79pp / Sh -0.29). 经济学: alpha 半衰期约 2 天 (新闻冲击的持续"
            "再定价期), 冻结 2 天信号损失小. 成功标准: CW 转绿且 Sh >= 0.95 (以最小 Sh 代价换 "
            "CW + TO); 若 CW 转绿且 TO <= 90%, 该构造进入 fail=[] 豁免区 (MT 自动清)."),
    },
    {
        "id": 4, "type": "H4_PRE_SINGLE", "role": "ISOLATION",
        "baseline": "全史零使用; CVW 单锚 (CTRL) Sh1.54/Ret6.91%",
        "expression": f"reverse(rank(divide({CVW}, {PVWAP})))",
        "optimize_reason": (
            "【pre 单锚隔离 · pre 轴归因基准】只用盘前 VWAP 一个锚: (收盘-盘前VWAP)/盘前VWAP. "
            "没有它, H1-H3 的双锚增益无法归因 (是 pre 腿独立有效, 还是与 VWAP 腿的交互有效). "
            "红队四审预测 Sh 1.05-1.35 / CW ~80% (单锚 + 扩展时段 = 高风险组合). 经济学: "
            "收盘价相对盘前会话均衡价的偏离 = 全日 (含盘前) 总位移, 其中跳空部分 (盘前发现) 与"
            "盘中部分混合. 成功标准: 建立 pre 腿独立基线; 若 Sh >= 1.35, pre 腿本身接近 CVW 腿"
            "强度, 双锚组合的合理性大幅上升; 若 Sh <= 0.9, pre 腿只是交互项无独立边缘."),
    },
    {
        "id": 5, "type": "H5_PRE_VHEX", "role": "CW_FIX",
        "baseline": "mLNEWjW (VWAP腿+VHEX分母) Sh1.59/CW pass; 9qE3k7mr (post锚+VHEX) CW fail 反例",
        "expression": f"reverse(rank(divide({CVW}, add({VHEX}, 1))))",
        "optimize_reason": (
            "【pre 单锚 + VHEX 分母 · 跨锚点推广判决】把战役验证过的 VHEX 计数归一搬到 pre 锚: "
            "(收盘-盘前VWAP) / (1+ excursion 事件数). 红队四审标注先验最低 (~55% CW) 但是唯一"
            "可能摸 2Y 2.40 的槽. 判决价值 > 通关价值: mLNEWjW 证明 VHEX 分母在 VWAP 腿上修 CW "
            "(Sh1.59/CW pass), 但 9qE3k7mr 证明同一分母在 post 锚上失败 —— 本槽判决该分母是"
            "「锚点无关的通用 CW 解」还是「只对特定锚有效」, 这决定今后所有 CW 修复的默认选择. "
            "经济学: 用 excursion 事件数归一 = 「单位事件强度承载的价格位移」, 与新闻驱动资金流"
            "的故事自洽. 成功标准: CW 转绿 (推广成立) 或 fail (推广有边界)."),
    },
    {
        "id": 6, "type": "H6_POST_DUAL", "role": "ANCHOR",
        "baseline": "post_vwap 单锚形式已测 (reverse(rank(subtract(EOC,OVWAP))) 等 12 次); sum 形式零先例",
        "expression": f"reverse(rank(divide(add({CVW}, subtract({EOC}, {OVWAP})), {VWAP})))",
        "optimize_reason": (
            "【post 双锚 · 盘后出清 + sum vs product 毒性判决】(收盘-新闻后VWAP) + (收盘-盘后VWAP), "
            "以 VWAP 归一. 红队四审: 唯一 post×vwap 组合是毒性 product (Sh 0.17), sum 形式零先例; "
            "post 锚是家族 2Y 引擎 (2.08-2.35), 本槽买 2Y; CW fail 先验 75-85% (全批最高). "
            "经济学: 盘后 VWAP = 全日交易全部出清后的均衡价, 收盘价同时偏离「新闻后时段均衡」与"
            "「全日出清均衡」= 双重未出清位移. 若本槽 2Y 显著高于 G8 (1.80), 说明盘后锚的时间"
            "稳定性优于盘前锚, 锚点选择应按 2Y 而非 Ret 排序. 成功标准: 2Y >= 2.00 (锚点排序结论); "
            "CW 预期 fail, 不作为证伪线."),
    },
    {
        "id": 7, "type": "H7_MAIN_DUAL", "role": "ANCHOR",
        "baseline": "main_vwap 全史零使用; G8 (pre 双锚) Sh1.14/Ret8.25%/CW FAIL",
        "expression": f"reverse(rank(divide(add({CVW}, subtract({EOC}, {MVWAP})), {VWAP})))",
        "optimize_reason": (
            "【main 双锚 · 全日均衡 + blend 轴 CW 安全对照】(收盘-新闻后VWAP) + (收盘-全日VWAP). "
            "红队四审: MVWAP 腿与 VWAP 腿信息包含度最高 (全日 VWAP 已含新闻后时段), 稀释最少, "
            "预期 Sh 1.20-1.45 且 CW ~30% (全批最安全的双锚) —— 是 blend 轴的 CW 安全对照. "
            "若本槽 CW 转绿而 H1/H2/H3 的 pre 版不全转绿, 说明「锚点相关性越低 CW 风险越高」, "
            "锚点选择存在 CW-Ret 权衡. 经济学: 全日 VWAP = 包含盘前的全日成交量加权均衡, "
            "与新闻后 VWAP 之差度量新闻对全日均衡价格的推动. 成功标准: CW 转绿 (对照组成立)."),
    },
    {
        "id": 8, "type": "H8_VOLZ_CONFIRM", "role": "VIRGIN_FIELD",
        "baseline": "news_vol_stddev 全史零使用; CVW 单锚 (CTRL) Sh1.54/Ret6.91%",
        "expression": f"reverse(rank(multiply({CVW}, add(abs({VOLZ}), 1))))",
        "optimize_reason": (
            "【量能确认的压力 · 唯一处女字段 + 新机制】压力 × (1 + |量能 z-score|): 把价格位移按"
            "「伴随的成交量异常幅度」加权. 经济学: 同样幅度的收盘-VWAP 偏离, 伴随异常成交量的是"
            "真实资金流冲击 (有反转价值), 伴随枯竭成交量的是报价噪声 (无信息) —— 量能是价格压力"
            "有效性的确认变量. 红队四审已确诊设计缺陷并预注册: abs() 把量能暴涨 (z>0) 与枯竭 "
            "(z<0) 混淆, 若本槽高 Sh 则确认机制成立 (缺陷可原谅), 若低 Sh 则结论不可用 (须换"
            "有符号版本重测), 不得据本槽单独否定该机制. vol_stddev 定义 = 当前量相对 30 日均量的"
            "z-score, cov 0.9672. 成功标准: Sh >= 1.30 (量能确认成立); 证伪线按预注册分支处理."),
    },
]

DIRECTIONS = {
    "H": {"name": "多锚点轴 + CW 修复 (8 条)",
          "hypothesis": (
              "G8 (pre_vwap 第三锚点) 拿下家族 Ret 第二 (8.25%) 但 CW fail. 本批系统展开锚点轴: "
              "三种 CW 修复 (winsorize/ts_rank250/bf2) + pre 轴归因 (单锚隔离 + VHEX 推广判决) + "
              "锚点三角收尾 (post/main) + 唯一处女字段 (量能确认)."),
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
           "sign", "abs", "sqrt", "log", "power", "winsorize", "zscore",
           "std", "factor", "period", "window"}
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
    print(f"[Wave11-H] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11H_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-H] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11H", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11h_{ts}.json"), "w", encoding="utf-8"),
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

    print("[Wave11-H] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-H] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11h_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-H ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>11} {'DD%':>6} {'CW':>5} {'CL':>5} {'MT':>4}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        cw = "FAIL" if "CONCENTRATED_WEIGHT" in names else "ok"
        cl = next((c.get("value") for c in (ch.get("warning") or [])
                   if isinstance(c, dict) and c.get("name") == "CLUSTER_TEST"), None)
        mt = "W" if "MATCHES_THEMES" in [c.get("name") if isinstance(c, dict) else c
                                          for c in (ch.get("warning") or [])] else "-"
        print(f"{it['id']:>2} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} {to * 100:>7.1f} "
              f"{ret * 100:>7.2f} {(ret / to) if to else 0:>7.3f} {(m.get('margin') or 0) * 1e4:>7.2f} "
              f"{m.get('two_year_sharpe') or 0:>6.2f} {m.get('sub_universe_sharpe') or 0:>5.2f} "
              f"{m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>11} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f} {cw:>5} "
              f"{('%.2f' % cl) if cl is not None else '  - ':>5} {mt:>4}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave11-H] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
