# -*- coding: utf-8 -*-
"""W14 · mLYNEWjW 定向优化第二波 (2026-10-25) — 单文件预检+发射.

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

=== W14 战略 (最后一搏: Fit 下限保护区 + 纯慢信号 + 未开采字段) ===
W13 战果: B1xB2 复合 Sh 1.69 创家族记录 (3 fail); 豁免规律 10-25 当日失效
(平台规则可变, fail=[] 策略不可依赖). Fit 门完整数学 (450 行实证):
Fit = Sh x sqrt(Ret/max(TO,0.11)); 前沿 Sh^2 x R/TO ~= 0.18 (需 1.0, 缺口 5.6x);
(Sh, R/TO) 双轴结构性负相关. 唯一理论残口 = TO<11% 下限保护区 (Ret>=4.41% 即可,
e76Po6eM TO 2.2%/Ret 9.84% 但 Sh 0.22). 本波 8 条: 4 条纯慢信号 (注意力/覆盖族,
天然低 TO, 从未以纯逻辑测过) + 4 条池化族复合 (R/TO 0.19-0.40 区 x 正向杠杆).
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
    # ---------- W14: Fit 下限保护区冲刺 (纯慢信号 4 + 池化复合 4) ----------
    # Fit = Sh x sqrt(Ret/max(TO,0.11)): TO<11% 时下限激活, 只需 Ret>=4.41% (Sh=1.58).
    # 纯慢信号天然低 TO; 池化族 (up/(up+dn) N=60) 是族内 R/TO 最高区 (0.19-0.40).
    {"id": 1, "type": "ATTN_ATR_SLOW", "role": "SLOW",
     "expression": f"reverse(rank(ts_mean(divide(vec_count({VHEX}), add(vec_avg(average_true_range_14d), 0.01)), 20)))",
     "reason": "【W14-1 · 单位波动的新闻关注 · 纯慢信号】20 日平均 (新闻事件数 / 当日平均 ATR14): ATR 是慢变的波动尺度, 覆盖度是慢变的关注尺度, 比率 = '单位波动承受的新闻关注'. 经济学 (Barber-Odean 注意力 + 波动反馈): 高关注/波动比的股票被散户过度交易, 价格偏离基本面, 随后跑输 (reverse 做空). 纯慢信号: 无事件门/无快变量, TO 预期 15-25% —— 直击 Fit 下限保护区 (TO<11% 时 Ret>=4.41% 即过). 判据: TO<=25% 且 Sh>=0.8 = 慢信号路线成立; Ret>=4% 且 TO<=12% = Fit 数学达成 (配 Sh>=1.5); Sh<0.3 = 关注/波动比率无预测力."},
    {"id": 2, "type": "ATTN_VOL_SLOW", "role": "SLOW",
     "expression": f"reverse(rank(ts_mean(divide(vec_count({VHEX}), add(vec_avg(current_day_volume), 0.01)), 20)))",
     "reason": "【W14-2 · 单位成交量的新闻关注 · 与槽1 构成分母对照】新闻事件数 / 当日成交量 (20 日均): 成交量分母 vs ATR 分母的机制对照 —— 成交量 = 实际交易活动强度 (换手), ATR = 价格波动强度. 若两者都有效, 说明'关注/活动比'是稳健维度; 若仅一个有效, 分辨分母该用交易量还是价格波动. 经济学同槽1 (关注过剩 -> 过度反应 -> 回落). 判据: Sh 与槽1 同号且量级相近 = 关注比率的维度选择不敏感; 显著分化 = 分母语义关键."},
    {"id": 3, "type": "FLOW_TOTAL", "role": "SLOW",
     "expression": f"reverse(rank(ts_mean(add(vec_count({VHEX}), vec_count(current_trading_volume_count)), 20)))",
     "reason": "【W14-3 · 双事件流总覆盖 · 纯注意力水平】20 日平均 (新闻事件数 + 交易量事件数): 总信息流强度. 反向 = 做多冷门股 (信息关注度低), Barber-Odean 注意力假设的最纯粹形式 (无比率/无归一, 纯覆盖水平). 与槽1/2 (比率型) 构成水平 vs 比率对照. 判据: Sh>=0.8 = 纯注意力水平有效 (最简形式); Sh<0.3 = 必须比率化 (归一是关键)."},
    {"id": 4, "type": "IDX_PERF_SLOW", "role": "SLOW",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_mean(news_indx_perf, 20))), 0)",
     "reason": "【W14-4 · 事件窗口的指数表现慢信号】新闻时刻的指数表现 (news_indx_perf) 20 日均值 + 新鲜事件门. 机制: 新闻发布时点的市场环境 (指数涨跌) 是信息被'吸收还是被淹没'的调节变量 —— 牛市中的新闻被系统性买入 (反应不足), 熊市中的新闻被恐慌放大. 20 日平滑给出每只股票'新闻市场环境'的慢变量画像. w11a 的 0mjVaJ61 (indx_perf/事件数 x short_interest 门) 有 R/TO 0.215/Sh 0.51 的正面读数. 判据: Sh>=1.0 = 指数环境调节有效; R/TO>0.15 = 该轴同时改善 Fit 数学."},
    # ---------- 池化族复合 (R/TO 0.19-0.40 区 x 正向杠杆) ----------
    {"id": 5, "type": "POOLED_ATTN", "role": "POOL",
     "expression": f"reverse(ts_rank(divide(divide(ts_sum(news_max_up_amt, 60), add(ts_sum(news_max_up_amt, 60), ts_sum(news_max_dn_amt, 60))), {COUNT20}), 250))",
     "reason": "【W14-5 · 池化上涨占比 x 覆盖度折扣】w10a 的 GrgN9OAZ (池化 U/(U+D) N=60 x ts_rank250: R/TO 0.403 族内最高, Sh 0.61/TO 5.2%/Ret 2.09%) 除以 20 日覆盖度. 机制: 池化比率测'60 日新闻冲击的上涨偏向' (慢变量), 覆盖度折扣提取净信息含量 (W12 B1 在快信号上 +0.04 Sh, 在慢信号上增益或更大 —— 池化估计的精度与事件数正相关). 若 Sh 0.61->1.0+ 且 R/TO 保 0.3+: Fit = 1.0×sqrt(0.3) = 0.55, 若 Sh 1.3 -> 0.71. 判据: Sh>=1.0 且 R/TO>=0.25 = 池化族 Sh 天花板打破 (0.63 -> 1.0); Sh<=0.7 = 覆盖折扣在池化族无效."},
    {"id": 6, "type": "POOLED_N30", "role": "POOL",
     "expression": f"reverse(ts_rank(divide(ts_sum(news_max_up_amt, 30), add(ts_sum(news_max_up_amt, 30), ts_sum(news_max_dn_amt, 30))), 250))",
     "reason": "【W14-6 · 池化 N=30 窗口扫描点】w10b/w10c/w11c 已扫 N=20/40/60/120/180/500 (Sh 顶 0.63), N=30 未测 (N=40 与 w11c bl8wYXGR 精确重复已避让). 更短窗口 = 更快反映近期上涨偏向 (TO 略升, Sh 或升). 与 N=60 (GrgN9OAZ Sh 0.61) / N=40 (w11c 实测) / N=120 (xA1oEdwW Sh 0.42) 构成四点窗口响应. 判据: Sh>0.63 = N=30 是更优窗口; Sh<=0.55 = 窗口效应确认 60 附近为最优, 池化族窗口轴关闭."},
    {"id": 7, "type": "POOLED_EXP", "role": "POOL",
     "expression": f"reverse(ts_rank(ts_decay_exp_window(divide(ts_sum(news_max_up_amt, 60), add(ts_sum(news_max_up_amt, 60), ts_sum(news_max_dn_amt, 60))), 20, factor=0.9), 250))",
     "reason": "【W14-7 · 池化 x 指数衰减复合】池化比率再经 f=0.9/d20 指数衰减 (ESS~15 天): 池化已是慢变量, 指数衰减进一步平滑其残余噪声. 与槽6 (纯 N=40) 构成'缩短池化窗口 vs 后置衰减'的等效性对照 (两者都压缩估计的时间集中度). 若指数版 Sh 高于 N=40 版, 说明后置平滑优于前置窗口调整. 判据: Sh>=0.70 = 复合平滑突破池化族天花板; 双低 = 池化族对任何额外平滑免疫 (估计量已最优)."},
    {"id": 8, "type": "CTO_ATR_NOGATE", "role": "SLOW",
     "expression": f"reverse(rank(divide({CTO}, add(vec_avg(average_true_range_14d), 0.01))))",
     "reason": "【W14-8 · 事件冲击的 ATR 标准化 · 无门版】CTO / 当日事件平均 ATR14 (无门, 3 字段): 与 W12 B2 (CTO/vec_stddev(VHEX) 带门: Sh 1.59/Ret 7.89%) 构成双重配对 —— ①门效应 (带门 vs 无门); ②分母语义 (事件内 stddev vs 14 日 ATR). ATR 是更宽尺度的波动度量 (含非事件日, 更稳), 若 ATR 版 Sh/Ret 不低于 stddev 版, 说明波动标准化对分母选择稳健且 ATR 更通用 (可用于无事件信号). 判据: Sh>=1.55 = ATR 分母等效或更优; Sh<=1.40 = stddev 分母有独特信息 (事件内波动才是真尺度)."},
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
    state_path = os.path.join(CAMPAIGN, f"state_w14_{tag}.json")
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
    res_path = os.path.join(CAMPAIGN, f"batch_w14_{tag}_{ts}_result.json")
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
    sum_path = os.path.join(CAMPAIGN, f"summary_w14_{tag}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n===== W14-{tag} ({NEUT}/d{DECAY}) =====", flush=True)
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
    print(f"[W14] 字段字典 {len(known_fields)} 装载; 8 处方 (线A 4 攻豁免边界 + 线B 4 新经济逻辑) @INDUSTRY/d6", flush=True)
    items = [{"id": s["id"], "role": s["role"], "type": s["type"], "expression": s["expression"],
              "reason": s["reason"], "seed_id": f"GATE1W14_{s['id']}"} for s in SLOTS]
    preaudit_and_check(items, known_fields, "W14")
    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w14_MAIN_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": "GATE1W14_MAIN", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "decay": DECAY, "neutralization": NEUT, "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[W14] 批次文件: {batch_path}", flush=True)
    results, res_path = await submit_and_collect(items, "MAIN")
    if not results:
        print("[W14] fetch 空, 退出", flush=True)
        return
    print(f"[W14] 结果已存: {res_path}", flush=True)
    summarize(items, results, "MAIN", res_path)
    print("\n[W14] 批次回收完毕。严禁提交任何 alpha。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
