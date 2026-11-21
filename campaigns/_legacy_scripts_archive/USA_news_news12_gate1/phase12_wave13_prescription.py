# -*- coding: utf-8 -*-
"""W13 · mLYNEWjW 定向优化第二波 (2026-10-25) — 单文件预检+发射.

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

=== W13 战略 (承接 W12 战果) ===
W12 线 B (新经济逻辑) 全线激活: B1 注意力折扣 (RATIO/20日覆盖度) Sh 1.63 超母本 1.59,
fail 仅 2 项, CLUSTER 1.52≈母本 1.54, Ret 7.56%, 2Y 2.02, rn 1.97 —— 新的家族最佳近 miss;
B2 波动标准化 Sh 1.59/Ret 7.89% (Ret 族内合格线新高). 线 A (多重平滑复合) 全军覆没
(门 x bf x 衰减三重互斥普遍化). 本波 8 条全部以 B1 为基座: 三种降 TO 算子 (bf2/bf3+dl2/
指数) 与 B1 复合攻 fail=[] 豁免边界; B1xB2 双杠杆可加性; 无门版 B2 解 CW;
B1 x 多事件门攻 CLUSTER 1.58.
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
    # ---------------- W13: B1 (注意力折扣, Sh 1.63/CL 1.52/2 fail) 系处方 ----------------
    # W12 战果: B1 是新的家族最佳近 miss (Sh 1.63 > 母本 1.59, fail 仅 LOW_FITNESS+HIGH_TURNOVER,
    # CLUSTER 1.52 ≈ 母本 1.54, Ret 7.56%, 2Y 2.02, rn 1.97) —— 缺口只剩 TO 115.9%->70% 与
    # Fit (R/TO 0.065 -> 0.376). 本波 8 条全部以 B1 为基座: 用 W11b/W12 已验证的降 TO 杠杆
    # (bf/衰减) 与 B1 复合攻 fail=[] 豁免边界 (Sh>=1.10 & TO<=70%), 并检验 B1xB2 双杠杆可加性.
    {"id": 1, "type": "B1_BF3_DL2_NOGATE", "role": "A",
     "expression": f"reverse(rank(ts_decay_linear(ts_backfill(divide({RATIO_F}, {COUNT20}), 3), 2)))",
     "reason": "【W13-1 · B1 x E5VjpeQm 构造 · fail=[] 头号候选】B1 (RATIO/覆盖度) x bf3+dl2 (无门版是 26 行 fail=[] 俱乐部成员, Sh 1.16/TO 59.45%). 机制复合: 覆盖度折扣提取净信息含量 (B1 +0.04 Sh) + bf3+dl2 把 TO 压到 ~59% + 无门保留全部填充日 (K2: 门切填充日即死, 故本槽无门). 若 B1 的 +0.04 Sh 增益在低 TO 区保住 (Sh>=1.20) 且 TO<=70% -> fail=[] 达成且无 LOW_SHARPE 警告. 判据: fail=[] = 豁免边界+注意力轴双达成; Sh>=1.25 = B1 增益在低 TO 区完全保住."},
    {"id": 2, "type": "B1_BF2_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill(divide({RATIO_F}, {COUNT20}), 2))), 0)",
     "reason": "【W13-2 · B1 x bf2 x 门】B1 + W11b 家族最优降 TO 构造 (bf2+门: TO 83.7%/Sh 1.47 于 RATIO 基座). 预期 TO ~84%/Sh ~1.5: 若 TO 压不到 70%, 与槽1 (bf3+dl2) 构成'门 vs 无门'在 B1 基座上的对照 (K2 预言门版 Sh 更低); 若意外压过 70% (门 x bf x 折扣三重交互), 直接 fail=[]. 判据: fail=[] = 三重交互意外有利; Sh>=1.50 且 TO<=85% = B1xbf2 路线成立."},
    {"id": 3, "type": "B1_BF3_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill(divide({RATIO_F}, {COUNT20}), 3))), 0)",
     "reason": "【W13-3 · B1 x bf3 x 门 · K2 反证】K2 (门 x bf 强互斥) 在 B1 基座上的反向验证: bf3+门在 RATIO 基座 Sh 1.20->0.87. B1 的覆盖度折扣是否缓解互斥? (折扣放大低覆盖名的位移 = 部分抵消门造成的信号稀疏化). 若 Sh 明显高于 0.87 -> B1 与门控存在协同, 打开'B1 x 门族'新空间; 若同样崩 -> K2 是基座无关的普遍规律. 判据: Sh>=1.10 = B1 缓解门 x bf 互斥 (协同); Sh<=0.95 = K2 普遍化."},
    {"id": 4, "type": "B1_B2_COMBO", "role": "B",
     "expression": f"reverse(rank(divide({RATIO_F}, multiply({COUNT20}, add(vec_stddev({VHEX}), 0.01)))))",
     "reason": "【W13-4 · B1 x B2 双杠杆复合 (无门版, ops=13)】注意力折扣 (B1: Sh 1.63) x 波动标准化 (B2: Sh 1.59/Ret 7.89%): 位移 / (覆盖度 x 冲击std) = 单位'注意力-波动'维度的净位移. 两个杠杆经济学正交 (覆盖度 = 关注噪声, std = 波动尺度), 若可加则 Sh 应 >1.63 且 Ret 保 7.5%+. 去门处理: 门非本复合的核心变量 (B1/B2 均为无门也可读), 且省 4 ops 规避 16 上限. 风险: 乘法分母使小覆盖+小波动名的信号爆炸 (重尾), 需监控 L/S 与 CW. 判据: Sh>1.63 且无 CW fail = 双杠杆可加 (家族新前沿); Sh<1.55 = 复合反噬."},
    {"id": 5, "type": "B2_NOGATE", "role": "B",
     "expression": f"reverse(rank(divide({CTO}, add(vec_stddev({VHEX}), 0.01))))",
     "reason": "【W13-5 · B2 无门版】W12 B2 (带门) Sh 1.59/Ret 7.89%/CW fail. 去门检验: CW fail 是否由门造成的稀疏仓位集中引起? 无门版 L/S 更均衡 -> CW 或解. 同时给出 B2 的原生 TO (预期 ~120%) 与门效应配对. 判据: CW fail 消失 = 门是 CW 诱因 (无门路线); Sh>=1.60 = B2 原生质量确认."},
    {"id": 6, "type": "B1_MULTIEVENT", "role": "B",
     "expression": f"trade_when(greater(vec_count({VHEX}), 2), reverse(rank(divide({RATIO_F}, {COUNT20}))), 0)",
     "reason": "【W13-6 · B1 x 多事件日门 · 攻 CLUSTER】B1 (CLUSTER 1.52) x 系统性新闻日门 (count>2): W12 B3 单独测 count>2 门 Sh 0.86/CLUSTER 0.79 (死), 但与 B1 复合或不同 —— 多事件日的覆盖度折扣位移 = 系统性事件的净信息含量, 正面制造簇同向性. 这是 CLUSTER 1.52->1.58 的第二路径 (第一路径 winsorize 仅 +0.02). 判据: CLUSTER>1.54 = 多事件门 x 折扣是簇杠杆 (警告墙破口); Sh>=1.2 = 复合成立."},
    {"id": 7, "type": "B1_EXPDECAY20", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_exp_window(divide({RATIO_F}, {COUNT20}), 20, factor=0.9))), 0)",
     "reason": "【W13-7 · B1 x 指数衰减】B1 + f=0.9/d20 指数衰减 (K3: 门控基座上 -7.5pp TO, W1 槽4 Sh 1.06). 与槽1 (bf3+dl2) / 槽2 (bf2) 构成 B1 基座上的三种降 TO 算子对照 (线性衰减/回填/指数). 关注覆盖度折扣与衰减的交互: 折扣后的信号更慢 (覆盖度是 20 日均值), 衰减或更温和. 判据: TO<=100% 且 Sh>=1.40 = 指数路线在 B1 上最优; Sh<=1.20 = 衰减族在 B1 基座同样杀 Sh."},
    {"id": 8, "type": "B1_BF2_DL2_GATE", "role": "A",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_linear(ts_backfill(divide({RATIO_F}, {COUNT20}), 2), 2))), 0)",
     "reason": "【W13-8 · B1 x bf2 x dl2 x 门 · 四重网格角】B1 + W12-A2 构造 (bf2+dl2+门: Sh 1.41/TO 71.8% 于 RATIO 基座, 距豁免框 1.8pp). B1 的 +0.04~0.22 Sh 增益 (W12 B1 vs 母本 +0.04; 但 B2 vs B1 显示折扣轴在低 TO 区增益或更大) 若在四重构造上保住, 落点 (TO~72%, Sh~1.5) —— 差 2pp TO 与 0.31 Sh 到 fail=[]. 判据: fail=[] = 家族首次在 B1 基座击穿豁免框; Sh>=1.45 且 TO<=73% = 前沿最近点."},
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
    state_path = os.path.join(CAMPAIGN, f"state_w13_{tag}.json")
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
    res_path = os.path.join(CAMPAIGN, f"batch_w13_{tag}_{ts}_result.json")
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
    sum_path = os.path.join(CAMPAIGN, f"summary_w13_{tag}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n===== W13-{tag} ({NEUT}/d{DECAY}) =====", flush=True)
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
    print(f"[W13] 字段字典 {len(known_fields)} 装载; 8 处方 (线A 4 攻豁免边界 + 线B 4 新经济逻辑) @INDUSTRY/d6", flush=True)
    items = [{"id": s["id"], "role": s["role"], "type": s["type"], "expression": s["expression"],
              "reason": s["reason"], "seed_id": f"GATE1W13_{s['id']}"} for s in SLOTS]
    preaudit_and_check(items, known_fields, "W13")
    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w13_MAIN_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": "GATE1W13_MAIN", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "decay": DECAY, "neutralization": NEUT, "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[W13] 批次文件: {batch_path}", flush=True)
    results, res_path = await submit_and_collect(items, "MAIN")
    if not results:
        print("[W13] fetch 空, 退出", flush=True)
        return
    print(f"[W13] 结果已存: {res_path}", flush=True)
    summarize(items, results, "MAIN", res_path)
    print("\n[W13] 批次回收完毕。严禁提交任何 alpha。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
