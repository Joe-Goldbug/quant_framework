# -*- coding: utf-8 -*-
"""W12 · mLYNEWjW 定向优化第二波 (2026-10-25) — 单文件预检+发射.

=== W11b 终审读数 (24 槽 + 2 探针, INDUSTRY/d6, MARKET/d6, INDUSTRY/d20) ===
零行过生产门禁 (step2 0/8 x3, ra_failed=false 0/24). 母本 mLYNEWjW 仍全战役最佳.
十项新机制知识:
 K1 bf2+门 = TO-Sh 前沿最优降 TO: TO 83.7%/Sh 1.47 (无门配对 QPYxb9vp 84.1%/1.43,
    门 +0.04 Sh, TO -0.34pp; 门不是 TO 杠杆第三次验证)
 K2 门 x bf 强互斥: bf3+门 Sh 1.20->0.87, TO 68.8->40.6 —— bf 的价值在填充日,
    门切填充日; dflc<1 在 bf 基座同样灾难 (Sh 0.90)
 K3 decay=20 在门控+bf 基座首次成为 TO 杠杆 (槽1 -7.5pp/槽4 -19.5pp) 但 Sh 净损,
    R/TO 不变 —— 与 w10a (d25 无门基座 TO 反升) 结论互补: decay 效应依赖基座
 K4 winsorize 分子级全线微正: 无门std3 Sh 1.56/CL 1.48; bf2+std2 Sh 1.49 vs bf2 1.47;
    CLUSTER +0.02 —— 家族史上首次非负面 winsorize 读数
 K5 双压力分子原生 (无门无bf): Sh 1.44/Ret 9.07%/2Y 1.64 —— Ret 族内合格线新高;
    bf 对双压力是纯损伤 (WjLZbE7N bf2 版 1.27/7.68%)
 K6 异常分离 2Y 2.37-2.40 族内最高之一, 但 Sh 1.37/TO 106%/CLUSTER 1.15
 K7 中性化下沉纯互换: 母本@MARKET Sh 1.59->1.25 (-21%) 换 Ret +14.2%/Mgn +16%;
    8/8 结构 MARKET 版 Sh 全低于 INDUSTRY 版
 K8 池化净压力比率死 (Sh 0.01) —— N=20 比率构造在稀疏序列上退化为 0/0
 K9 豁免规律精确化 (370 行): |Sh|>=1.10 且 TO<=70% => Sh/Fit/2Y 检查降 warning;
    warn 组最低 Sh 1.10, fail 组 TO<=70% 的最高 Sh 1.06 (W1 槽4) —— 边界在
    1.06-1.10 之间; fail=[] 的 26 行 26/26 无 MATCHES_THEMES
 K10 CLUSTER 与 TO 正相关: 降 TO 必降 CLUSTER (bf2 1.41/指数 1.01/池化 0.31),
    族顶仍母本 1.54 —— 警告墙的结构性根源

=== W12 战略 (双线) ===
线A (4 槽): TO-Sh 前沿网格插值攻 fail=[] 豁免边界 (Sh>=1.10 & TO<=70%).
  已知点: (84,1.47)bf2门, (72,1.37)bf2dl2无门, (59.5,1.16)bf3dl2无门(fail=[]),
  (40.6,0.87)bf3门, (46,1.06)指数门, (83.7,1.49)bf2winsor门.
  A1-A4 用 dl2/指数/winsorize 与 bf2/bf3 的因子网格寻找落入边界框的组合.
线B (4 槽): 新经济逻辑探针 (K10 表明同族降 TO 必降 CLUSTER, Fit 数学不可达
  (R/TO 需 0.74 vs 族上限 0.075) —— 破局必须换估计量/逻辑):
  B1 Barber-Odean 注意力折扣: 单位长期新闻覆盖的价格位移 (覆盖低=散户关注少=
     价格发现更信息-laden); B2 scale-free 冲击 (CTO/事件stddev); B3 多事件日门
     (count>2 = 系统性新闻日, 正面攻 CLUSTER); B4 注意力折扣异常分离版.
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
CATEGORY = "news"
REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
TRUNCATION, NAN_HANDLING = 0.025, "ON"
DECAY, NEUT = 6, "INDUSTRY"

EOC, TON = "news_eod_close", "news_ton_last"
VHEX = "high_price_excursion_stddev"

GATE2 = f"days_from_last_change(vec_count({VHEX})), 2"
RATIO_F = f"divide(subtract({EOC}, {TON}), add(vec_count({VHEX}), 1))"
COUNT20 = f"add(ts_mean(vec_count({VHEX}), 20), 1)"
CTO = f"subtract({EOC}, {TON})"

SLOTS = [
    # ---------------- 线 A: TO-Sh 前沿网格插值 (攻 fail=[] 豁免边界) ----------------
    {"id": 1, "type": "BF3_DL2_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_linear(ts_backfill({RATIO_F}, 3), 2))), 0)",
     "reason": "【A1 · E5VjpeQm+门】bf3+dl2 无门版是 26 行 fail=[] 俱乐部成员 (Sh 1.16/TO 59.45%), 本槽加 mLYNEWjW 硬门: 门在无 bf 基座不改 TO, 但 bf3+dl2 的 TO 59% 中有多少来自'陈旧填充'待测量 —— 若门后 TO 仍 <=70% 且 Sh>=1.10, 即复制 fail=[] 且获得更纯的事件因果链. 判据: fail=[] = 豁免边界达成; Sh>=1.25 = 门修复 dl2 的 Sh 损失."},
    {"id": 2, "type": "BF2_DL2_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_linear(ts_backfill({RATIO_F}, 2), 2))), 0)",
     "reason": "【A2 · XgR3b8al+门】bf2+dl2 无门 Sh 1.37/TO 71.95% (b11), 距豁免边界仅 1.95pp TO; 加门 (K1: 门 +0.04 Sh 且几乎不动 TO) 后预期 TO ~71.5%/Sh ~1.40 —— 家族 TO-Sh 前沿上距 fail=[] 最近的点. 判据: fail=[] = 边界击穿; Sh>=1.45 = 前沿新记录."},
    {"id": 3, "type": "BF2_WINSOR_DL2_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_linear(ts_backfill(divide(winsorize({CTO}, std=2), add(vec_count({VHEX}), 1)), 2), 2))), 0)",
     "reason": "【A3 · W11b 最佳 + dl2】槽5 (bf2+winsorize+门) 是 W11b 家族内最佳 (Sh 1.49/TO 83.66%/CLUSTER 1.43), 本槽叠加 dl2 线性衰减压最后 13.7pp TO: winsorize (K4 全线 +0.02~0.04) x dl2 (b11: -13pp TO/-0.06 Sh) 若效应可加, 落点 (TO~70%, Sh~1.42) 直击豁免框. 判据: fail=[] = 双杠杆可加性成立; Sh>=1.40 且 TO<=72% = 家族前沿."},
    {"id": 4, "type": "BF2_EXP10_F07_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_exp_window(ts_backfill({RATIO_F}, 2), 10, factor=0.7))), 0)",
     "reason": "【A4 · bf2 x 指数衰减复合】双平滑复合 (表达式内 bf2 保持事件 + 平台侧指数 f=0.7/d10 ESS≈4.7 天): K3 证明 decay 在门控基座是温和 TO 杠杆 (-7.5pp@d20), 表达式内指数衰减同理但可与 bf 复合. 与 A2 (bf2+线性) 构成衰减形状对照 (指数 vs 线性). 判据: TO 65-75% 且 Sh>=1.20 = 复合平滑路线; Sh<1.0 = 双平滑过度 (与 K2 的互斥规律一致)."},
    # ---------------- 线 B: 新经济逻辑探针 (K10: 破局须换估计量) ----------------
    {"id": 5, "type": "ATTENTION_DISCOUNT", "role": "B",
     "expression": f"trade_when(less({GATE2}), reverse(rank(divide({RATIO_F}, {COUNT20}))), 0)",
     "reason": "【B1 · Barber-Odean 注意力折扣】单位事件位移 / 长期(20日)平均新闻覆盖: 散户注意力是有限资源 (Barber-Odean 2008), 高覆盖日的价格位移被过度反应主导 (噪声), 低覆盖日的位移更 information-laden (价格发现). 以覆盖度折扣位移 = 提取'净信息含量'. 与 K8 池化死的区别: 分母是覆盖度 (慢变量) 而非位移量, 不退化. 判据: Sh>0.8 且 R/TO>0.15 = 注意力轴成立 (族内 R/TO 上限 0.075, 翻倍即破局); Sh<0.3 = 覆盖度无信息."},
    {"id": 6, "type": "STDTSCALE", "role": "B",
     "expression": f"trade_when(less({GATE2}), reverse(rank(divide({CTO}, add(vec_stddev({VHEX}), 0.01)))), 0)",
     "reason": "【B2 · scale-free 冲击】尾盘位移 / 当日事件冲击的标准差 (vec_stddev(VHEX)): 把 CTO 从'美元位移'换成'标准差单位位移' —— 高波动股票需要更大位移才构成同等信号 (异质波动调整), 直接治'横截面被高波动名主导'的 IC 泄漏. 与已证伪的'归一化分母替换' (count 类) 不同: 分母是波动率类. 判据: Sh>=1.4 且 R/TO>0.08 = 波动标准化优于计数标准化 (母本 Sh 1.59/R/TO 0.066 基准); CLUSTER 升 = scale-free 增强簇可比性."},
    {"id": 7, "type": "MULTIEVENT_GATE", "role": "B",
     "expression": f"trade_when(greater(vec_count({VHEX}), 2), reverse(rank({RATIO_F})), 0)",
     "reason": "【B3 · 多事件日门 · 正面攻 CLUSTER】count>2 = 当日 >=3 条新闻的系统性新闻日. 机制: 单条新闻是个股轶事 (特异), 多条同日新闻 = 公司层面系统性事件 (财报/并购/监管) —— 簇内多家公司对同类系统性事件的反应模式相似, 正面制造 CLUSTER_TEST 要的'簇同向性'. b11 测过 count>0 门 (Sh 0.90/TO 39.5%), count>2 是收紧版未测. 判据: CLUSTER>1.54 = 多事件门是簇杠杆 (警告墙破口第一候选); Sh<1.0 但 CLUSTER 高 = 门路线的簇/整体分离读数."},
    {"id": 8, "type": "ATTENTION_WINSOR", "role": "B",
     "expression": f"trade_when(less({GATE2}), reverse(rank(divide(winsorize({CTO}, std=2), {COUNT20}))), 0)",
     "reason": "【B4 · 注意力折扣 x winsorize 加固】B1 的稳健化配对: 先对分子 CTO 横截面削极值 (std=2, K4 实证 winsorize 分子级全线微正 +0.02~0.04) 再除以长期覆盖度. 目的: ①分离 winsorize 在注意力轴上的边际作用 (与 B1 配对); ②覆盖度折扣放大低覆盖名的位移, 而这些名的位移恰好是极值高发区 (小盘股新闻少但波动大) —— winsorize 防'低覆盖+高波动'的伪信息名主导排序. 判据: Sh>B1+0.1 = winsorize 在折扣轴有效; 双槽同灭 = 覆盖度折扣族整体关闭."},
]


def preaudit_and_check(items: list, known_fields: list, tag: str):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
           "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
           "ts_delta", "ts_decay_linear", "ts_decay_exp_window", "ts_median", "trade_when",
           "greater", "less", "if_else", "vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min",
           "vec_stddev", "days_from_last_change", "winsorize", "abs", "power", "sqrt",
           "industry", "subindustry", "sector", "market", "sign", "factor", "std"}
    # 本地全历史精确匹配 (含 SMOKE 探针教训: 一切表达式都要过 novelty)
    import glob
    hist = {}
    for fp in sorted(glob.glob(os.path.join(CAMPAIGN, "batch_*_result.json"))):
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("alpha_results", []):
            code = r.get("code")
            if code:
                hist[corrector.correct_expression(code)] = (r.get("alpha_id"), os.path.basename(fp))
    print(f"  [novelty-{tag}] 历史表达式 {len(hist)} 条装载", flush=True)
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        it["expression"] = fixed
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        used = tokens & known_set
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        exact = hist.get(fixed)
        h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, NEUT)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        dbdup = cur.fetchone()
        print(f"  [pre-audit-{tag}] slot{it['id']:<2} [{it['type']:<22}] ops={audit['operator_count']:>2} "
              f"fields={len(used)} len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'}"
              f"{' EXACT:' + str(exact[0]) if exact else ''}{' DUP@IND' if dbdup else ''}", flush=True)
        if unknown:
            raise ValueError(f"[{tag}] slot{it['id']} 未知标识符: {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"[{tag}] slot{it['id']} 审计失败: {audit['issues']}")
        if not (2 <= len(used) <= 3):
            raise ValueError(f"[{tag}] slot{it['id']} 字段数 {len(used)} 越界")
        if audit["operator_count"] > 16:
            raise ValueError(f"[{tag}] slot{it['id']} ops > 16")
        if len(fixed) > 857:
            raise ValueError(f"[{tag}] slot{it['id']} 超长")
        if exact:
            raise ValueError(f"[{tag}] slot{it['id']} 本地历史精确重复: {exact}")
        if len(it["reason"]) < 120:
            raise ValueError(f"[{tag}] slot{it['id']} reason 过短")
    conn.close()


async def submit_and_collect(items: list, tag: str):
    state_path = os.path.join(CAMPAIGN, f"state_w12_{tag}.json")
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
                    alpha_expressions=exprs, region=REGION, universe=UNIVERSE, delay=DELAY,
                    decay=DECAY, neutralization=NEUT, truncation=TRUNCATION,
                    pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                    language="FASTEXPR", visualization=False, max_trade="OFF")
                if "error" in sub:
                    raise RuntimeError(f"submit error: {sub}")
                location = sub["location"]
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump({"location": location, "submitted_at": int(time.time()), "tag": tag}, f)
                print(f"[submit-{tag}] OK {location} (n={len(exprs)})", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    waited = 0
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(location)
            st = chk.get("status")
            if waited >= 60:
                print(f"  [poll-{tag}] {st} t={waited}s", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                print(f"  [poll-{tag}] 终态 {st} (t={waited}s)", flush=True)
                break
        except Exception as e:
            print(f"  [poll-{tag}] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)
        waited += 20
    fetch = await BrainModule.fetch_multi_simulation_result(location)
    results = fetch.get("alpha_results", [])
    ts = int(time.time())
    res_path = os.path.join(CAMPAIGN, f"batch_w12_{tag}_{ts}_result.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    return results, res_path


def summarize(items: list, results: list, tag: str, res_path: str):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret, to = m.get("returns") or 0, m.get("turnover") or 0
        rows.append({
            "slot": it["id"], "role": it["role"], "type": it["type"], "reason": it["reason"],
            "expression": it["expression"], "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": to, "returns": ret,
            "ret_over_to": (ret / to) if to else None, "margin_bps": (m.get("margin") or 0) * 10000,
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "sub_sharpe": m.get("sub_universe_sharpe"), "two_year_sharpe": m.get("two_year_sharpe"),
            "rn_sharpe": m.get("risk_neutralized_sharpe"),
            "ra_failed": ra.get("ra_failed"), "ra_failed_checks": ra.get("ra_failed_checks"),
            "fail_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("fail") or [])],
            "warning_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("warning") or [])]})
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    s = {"tag": tag, "settings": {"neutralization": NEUT, "decay": DECAY, "universe": UNIVERSE,
                                  "region": REGION, "delay": DELAY, "truncation": TRUNCATION},
         "result_file": res_path, "rows": rows,
         "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final), "step2": step2, "final": final}}
    sum_path = os.path.join(CAMPAIGN, f"summary_w12_{tag}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n===== W12-{tag} ({NEUT}/d{DECAY}) =====", flush=True)
    for r in rows:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        print(f"slot{r['slot']} [{r['type']:<22}] Sh={r['sharpe']} Fit={r['fitness']} TO={to:.1f}% "
              f"Ret={ret:.2f}% R/TO={r['ret_over_to'] or 0:.3f} 2Y={r['two_year_sharpe']} "
              f"sub={r['sub_sharpe']} rn={r['rn_sharpe']} Mgn={r['margin_bps']}bps L/S={r['longCount']}/{r['shortCount']}", flush=True)
        print(f"   fail={r['fail_checks']} warn={r['warning_checks']} ra={r['ra_failed']} id={r['alpha_id']}", flush=True)
    print(f"Step1: {step1['message']}", flush=True)
    print(f"Step2: {len(step2)}/8 | 终极准入: {len(final)}/8", flush=True)
    # 预注册判据
    print("\n--- 预注册判据检验 ---", flush=True)
    nofail = [r for r in rows if not r["fail_checks"]]
    print(f"  fail=[] 行 (豁免边界 Sh>=1.10 & TO<=70%): {len(nofail)}", flush=True)
    for r in nofail:
        print(f"    slot{r['slot']} [{r['type']}] Sh={r['sharpe']} TO={r['turnover']} warn={r['warning_checks']}", flush=True)
    b_rows = [r for r in rows if r["role"] == "B"]
    for r in b_rows:
        rto = r["ret_over_to"] or 0
        if (r["sharpe"] or 0) > 0.8 and rto > 0.15:
            print(f"  !! B 线活杠杆: slot{r['slot']} [{r['type']}] Sh={r['sharpe']} R/TO={rto:.3f}", flush=True)
    return s


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[W12] 字段字典 {len(known_fields)} 装载; 8 处方 (线A 4 攻豁免边界 + 线B 4 新经济逻辑) @INDUSTRY/d6", flush=True)
    items = [{"id": s["id"], "role": s["role"], "type": s["type"], "expression": s["expression"],
              "reason": s["reason"], "seed_id": f"GATE1W12_{s['id']}"} for s in SLOTS]
    preaudit_and_check(items, known_fields, "W12")
    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w12_MAIN_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": "GATE1W12_MAIN", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "decay": DECAY, "neutralization": NEUT, "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[W12] 批次文件: {batch_path}", flush=True)
    results, res_path = await submit_and_collect(items, "MAIN")
    if not results:
        print("[W12] fetch 空, 退出", flush=True)
        return
    print(f"[W12] 结果已存: {res_path}", flush=True)
    summarize(items, results, "MAIN", res_path)
    print("\n[W12] 批次回收完毕。严禁提交任何 alpha。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
