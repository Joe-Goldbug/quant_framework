# -*- coding: utf-8 -*-
"""Gate1 Wave10-A · decay 维度首次突破批 (2026-10-24 深夜).

=== 本次战役的两项决定性发现 (全部来自本地 184 条实读数据, 非推测) ===

[发现 1] Fitness 公式带 turnover 下限保护 (174 条实读拟合, 复现误差 ~0.003)
    Fit = Sharpe * sqrt( |Ret| / max(TO, ~0.11) )
  ==> Fit >= 1.0  <=>  Ret >= max(TO, 0.11) / Sharpe^2
  在 Sh=1.58 处:
    TO<=11%  ->  只需 Ret >= 4.40%   <== turnover floor 保护区, 需求骤降
    TO=30%   ->  需   Ret >= 12.02%
    TO=50%   ->  需   Ret >= 20.03%
  即把 TO 压进 <=11% 区间存在巨大的门槛跳变. 之前 21 批的分析把 TO 目标设成
  "越低越好但没有区分 0.11 这个临界点", 抹掉了这个杠杆.

[发现 2] settings.decay 是完全未开发的自由维度
    历史 216 条 alpha 的 settings.decay 分布 = {6: 216}
    即 21 批全部用 decay=6, 从未扫描过.
    且 fingerprint = MD5(expr, region, universe, delay, neutralization) 不含 decay
    ==> 扫描 decay 是零重复成本的全新维度, 且不消耗 op 预算 (settings 层).

=== 两个子 agent 的矛盾裁决 (需本批实证) ===
  Agent-R 用 147 条跨结构回归得 d(log Fit)/d(log TO) = +0.058, 断言"降 TO 对 Fit 几乎中性";
  但该回归是 CROSS-SECTIONAL 的 — 它反映的是"历史上所有降 TO 的算子
  (ts_backfill / ts_mean / 门控) 都同时杀 Sh" 这一结构性共变, 而非"降 TO 物理上无效".
  decay 是平台层的纯输出侧衰减, 不引入 ts_backfill 的"陈旧值"(不招 CW),
  与上述任何算子机制都不同. 故 decay 的处理效应必须由实验测定, 不能靠跨结构回归外推.

=== 本批实验设计 (配对对照 + 新结构并行推进) ===
  槽 1/2/3 = 三条 decay=6 下已有精确实读的头部候选, 原样在 decay=25 下重跑.
    构成严格配对(paired)实验: 同表达式、同 universe/neut/delay, 唯一变量 = decay.
    由此可精确算出 decay=6->25 的 (Sh, Ret, TO, 2Y, CW) 变换因子,
    进而反推槽 4-8 新结构在 decay=6 下的等价表现 —— 一批同时拿到 decay 效应与新结构信息.
  槽 4/5/6/7/8 = 五条新机制结构 (在 decay=25 下首次测试).

=== 平台真实门槛 (实读 checks.limit) ===
  LOW_SHARPE>=1.58 | LOW_FITNESS>=1.0 | LOW_2Y_SHARPE>=1.58 | HIGH_TURNOVER<=0.70
  LOW_SUB_UNIVERSE_SHARPE>=-0.24 (极易过, 非墙) | CONCENTRATED_WEIGHT<=0.1
  CLUSTER_TEST>=1.58 (warning) | MATCHES_THEMES (warning)

=== mandate ===
  2<=字段数<=3 | op 数不限 | 仅 multi_create_simulate 每批 8 条 | 严禁提交任何 alpha
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
CATEGORY = "news"
REGION = "USA"
DELAY = 1
DECAY = 25  # ★ 本批唯一的新变量 (历史 216 条全部 decay=6)
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, VWAP, TON = "news_eod_close", "news_eod_vwap", "news_ton_last"
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"

SLOTS = [
    # ---------- A 组: 配对对照 (decay=6 下已有精确实读) ----------
    {
        "id": 1, "type": "PAIRCTRL_ANCHOR", "role": "PAIR", "baseline": "N1eGk79E",
        "expression": f"reverse(rank(divide(subtract({EOC}, {VWAP}), ts_backfill(vec_count({VHEX}), 120))))",
        "optimize_reason": (
            "配对对照槽 1 = 锚 N1eGk79E 原样在 decay=25 下重跑. decay=6 实读: Sh1.63/Fit0.31/"
            "TO116.9%/Ret4.26%/2Y0.58/CW fail/Mgn0.73bps. 锚的分子是 close-vwap 尾盘订单流压力,"
            "分母是回填 120 日的事件计数——它的问题是 TO 116.9% 导致 Fit 走到 sqrt(Ret/TO) 的极不"
            "利端. 本槽唯一变量是 decay: 若 decay 能把 TO 压到 <=11%, 按 Fit 公式只需 Ret>=4.40%,"
            "而锚已有 Ret 4.26% —— 理论上仅差 3%. 这是本批最直接的证伪/证实槽."),
    },
    {
        "id": 2, "type": "PAIRCTRL_BESTFIT", "role": "PAIR", "baseline": "d5K6wxlx",
        "expression": f"reverse(rank(divide(subtract({EOC}, {TON}), ts_backfill(vec_count({VHEX}), 120))))",
        "optimize_reason": (
            "配对对照槽 2 = 家族最佳 Fitness 结构 d5K6wxlx (CTO 分子) 在 decay=25 下重跑. "
            "decay=6 实读: Sh1.61/Fit0.41/TO120.1%/Ret7.70%/2Y2.09/sub1.27/rnSh1.91/ProdCorr0.7033."
            "它是家族唯一 2Y 已达 2.09 (>=1.58) 的高 Sharpe 槽, 也与 Worker: prod 相关超 0.0033 之外几乎"
            "合规. 其 Ret 7.70% 是全族最高之一 —— 若 decay 把 TO 压到 30% 而 Ret 保住 >6%, "
            "Fit 将达 1.6*sqrt(0.06/0.30)=0.72; 压到 11% 则 Fit=1.6*sqrt(0.045/0.11)=1.02 直接过线. "
            "本槽是 decay 处理效应的第二个独立标定 (与槽1 两个不同的 Ret 水平构成两点标定)."),
    },
    {
        "id": 3, "type": "PAIRCTRL_REV_MAXSH", "role": "PAIR", "baseline": "MP0n61ra(no reverse)",
        "expression": f"reverse(rank(divide(subtract({EOC}, {VWAP}), vec_max({VHEX}))))",
        "optimize_reason": (
            "配对对照槽 3 = 家族 Sharpe 绝对记录的生产性版本. Wave9-S 槽4 实测 "
            "rank(divide(subtract(close,vwap), vec_max(VHEX))) Sharpe = -1.68 (全族 |Sh| 最高, "
            "超过 d5K6wxlx 的 1.61), 但该槽未加 reverse 因而是负边缘. 本槽加 reverse 使其变为 "
            "+1.68 —— 这是将家族 Sharpe 天花板从 1.61 抬到 1.68 的第一个生产性形式, 此前从未测"
            "过. 同时它在 decay=25 下给出第三个标定点. 经济机制: 分子 '收盘价 - 新闻时刻至收盘"
            "VWAP' = 尾盘相对盘中成交均价的净订单流压力; 分母 '当日最大?' news High Price Excursion "
            "(标准差单位) = 当日主导事件的冲击强度. 比值 = 单位主导冲击所摊到的尾盘订单流位移,"
            "量纲为美元/标准差单位, 跨股可比. reverse 后做多'冲击大而尾盘被压制'的标的 = "
            "流动性冲击反转的标准化形式."),
    },

    # ---------- B 组: 新结构 (首次在 decay=25 下测试) ----------
    {
        "id": 4, "type": "SPEED_DOMAIN_GROUPRANK", "role": "NEW", "baseline": None,
        "expression": "reverse(group_rank(ts_backfill(subtract(news_mins_3_pct_dn, news_mins_3_pct_up), 120), industry))",
        "optimize_reason": (
            "【速度域首次截面归一化】子 agent-S 的诊断: mins 家族历史 6 条失败不是死于无 alpha, "
            "而是死于三个可修复的工程缺陷 —— ① up/(up+dn) 比值在分钟数据上退化为常数(两端同为哨兵值)"
            "② 184 条中 mins 家族的 rank/group_rank 归一化使用次数 = 0 ③ 宽度严重不足(lc/sc 仅 0/0,3/3,"
            "6/7, 而健康需 500/500). 本槽同时修 ①②③: 用 subtract 替代比值(免疫①), group_rank("
            "industry) 做组内归一化(修②), ts_backfill 120 抬宽度(修③). 机制: 同一批新闻中向下 3% 与"
            "向上 3% 被吸收所需时间之差 = 公司特定的'信息吸收偏斜', 是流动性深度与持有者结构的持久"
            "属性而非日频马尔可夫量. 实证依据: 速度域的 bf 降 TO 弹性 = 16.6x (143%->8.6%), 而幅度域"
            "仅 3.5x (129.9%->37.2%) —— 速度变量确实是慢变量."),
    },
    {
        "id": 5, "type": "VECTOR_MINUTES_COV10", "role": "NEW", "baseline": None,
        "expression": "reverse(group_rank(ts_backfill(subtract(vec_avg(minutes_to_one_pct_down_move_1555), vec_avg(minutes_to_one_pct_up_move_1555)), 120), industry))",
        "optimize_reason": (
            "【VECTOR 分钟族, cov=1.0 全覆盖 — 主攻 CW】与槽4 同一经济机制, 换成 VECTOR 表示. 关键区别:"
            "minutes_to_one_pct_{up,down}_move_1555 是 867 字段里唯一双侧覆盖率均为 1.0000 的分钟对. "
            "选择 1% 阈值是因为 TOP1000 日内几乎必然触及 ±1% => up/dn 都是真实观测而非哨兵值, "
            "这正是 ±20% 版本失效(比值恒 0.5 => lc=sc=0)的根因. 131 式中 margin GROUP: 与 mind the "
            "cross-sectional ~QESP; Zesign (residualized within industry) 直接打 CW. "
            "这是全批宽度先验最好的槽 —— CW<=0.1 是本批最可能修复的墙."),
    },
    {
        "id": 6, "type": "POOLED_TSRANK_BREAKER", "role": "NEW", "baseline": None,
        "expression": f"reverse(ts_rank(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))), 250))",
        "optimize_reason": (
            "【打破 Sh <-> R/TO 反相关的头号候选】子 agent-R 的根因诊断: 家族全部降换手尝试都在'输出侧'"
            "降频(先算日频信号再 ts_mean/backfill), 这是衰减(attenuation), 故 IC 与 TO 同比缩小, "
            "R/TO 恒定而 Sh 塌. 打断方式 = 把降频移到'输入侧'(重参数化): 先用 60 日原始观测重新估计"
            "潜在参数 theta = 累积上行占累积总News feeding): Ufd ratio, 再做自身 250 日时序分位. "
            "池化估计误差 ~1/sqrt(N) => Sh 有理由随 N 上升; 日变化 ~1/N => TO 下降. 两条曲线方向相反. "
            "采用 N=60 而非 250 是因为实读警示: 裸池化比值 N=120 已翻负(Sh -0.16), 存在偏差-方差最优窗口;"
            "而 N=60 的池化是全场唯一 Ret>7%@TO<62% 样本 omoX8edl 的窗口. ts_rank 输出把幅 compressing 为 "
            "[0,1] 均匀分布 => 横截面同方差, 直接消除 omoX8edl 有最高 R/TO(0.125) 却只有 Sh 0.57 的"
            "异方差缺陷. 全部 8 条历史 ts_rank 都作用在日频快信号上, '慢池化输入 + 时序分位输出'是首次."),
    },
    {
        "id": 7, "type": "GROUPMEAN_AMPLIFIER_X_CTN", "role": "NEW", "baseline": None,
        "expression": f"reverse(group_mean(divide(ts_sum(subtract({EOC}, {TON}), 60), add(ts_sum(vec_count({VHEX}), 60), 1)), 1, industry))",
        "optimize_reason": (
            "【Ret 放大器 x 家族最强分子】omoX8edl = reverse(group_mean(divide(ts_sum(U,60),"
            "add(ts_sum(U,60),ts_sum(D,60))), 1, industry)) 是全族唯一 TO<62% 且 Ret>7% 的样本 "
            "(TO56.7%/Ret7.11%/R-TO0.125). 与裸池化版 QPYAZbEp (Ret 0.95%) 对比, group_mean 带来 "
            "7.5x 的 Ret 放大 —— 这是家族已知的、最强的单一 Ret 放大机制, 但此前只在一个信号上"
            "验证过一次. 本槽把该放大器换到家族最强分子 CTN (close-ton_last, decay=6 下 Sh1.61/"
            "Ret7.70%) 上: 分子改为 '过去 60 日累积 CTN 漂移 / 过去 60 日累积新闻条数' = 每条新闻的"
            "平均漂移(池化估计), 再经行业组内均值化. 机制: 同行业共享新闻流与投资者结构, 组内均值把"
            "个股噪声估计替换为行业共同新闻因子的低噪估计, 同时 group_mean 不做秩压缩 => 保幅度攻 Ret. "
            "combined with decay=25 是本批最接近 '高 Ret + 中低 TO' 目标区的槽."),
    },
    {
        "id": 8, "type": "BL8WD2NQ_TEMPLATE_ATR", "role": "NEW", "baseline": None,
        "expression": "reverse(group_rank(subtract(divide(news_atr14, news_eod_close), ts_mean(divide(news_atr14, news_eod_close), 5)), industry))",
        "optimize_reason": (
            "【已验证可提交通式的迁移】外部 alpha bl8Wd2Nq (Sh2.05/Fit1.12/2Y2.39/TO22.9%, 全门过) 的"
            "结构解剖: D = F/close (F 慢 => D 慢但每日呼吸); D - ts_mean(D,5) = 归一化量的短周期偏离; "
            "再行业内排名. 数学上 ~= -D x (5日收益), 即'被慢水平量加权的锚定反转'. 上一轮红队判其"
            "不可迁移的理由是 'TON/OPEN 是日更流量非稀疏水平量, 减自身 ts_mean = 二阶差分放大噪声' —— "
            "该论证只在被减对象是日频快信号时成立 (实证确认: pwvkAReq 对快比值做 ts_mean5 => Sh0.71/"
            "R-TO 0.039). 本槽改用 news_atr14 (14 日滚动已皇 state 的 windowed statistic 且每日更新) 作为 F:"
            "它是 news12 内唯一落在'慢到能当锚、又日更到能呼吸'窗口的合格 F. D=ATR14/close 是无量纲的"
            "(USD/USD), 规避已知的 close-vwap UNITS 量纲警告. 机制: 做空行业内波动率刚异常抬升者 = "
            "Ang et al. 异质波动率异象的行业相对版."),
    },
]

DIRECTIONS = {
    "D25": {
        "name": "decay=25 突破批 (3 配对对照 + 5 新结构)",
        "hypothesis": (
            "Fit = Sh*sqrt(|Ret|/max(TO,0.11)) 存在 turnover 下限保护, TO<=11% 时 Sh=1.58 只需 Ret>=4.40%; "
            "settings.decay 在 21 批 216 条中恒为 6 从未扫描, 且不计入 fingerprint (零重复成本, 不占 op). "
            "decay 作为平台层纯输出侧衰减不引入 ts_backfill 的陈旧值(不招 CW), 有望同时改善 Fit/TO/CW/2Y. "
            "本批用 3 条 decay=6 已有精确实读的头部候选构成配对实验标定 decay 的处理效应, 其余 5 槽并行"
            "推进速度域/VECTOR分钟族/输入侧池化重参数化/group_mean放大/bl8Wd2Nq通式五个新机制."),
        "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": SLOTS},
}

STAGGER_SECONDS = {"D25": 0}


def purge_fingerprints(exprs: list, neutralization: str, universe: str):
    """decay 不在 fingerprint 内 => 重测旧表达式会被判重复, 需先 purge."""
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        fixed = corrector.correct_expression(e)
        h = corrector.compute_fingerprint(fixed, REGION, universe, DELAY, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n} records (decay 不在指纹内, 允许新 decay 重测)", flush=True)


def preaudit(items: list, known_fields: list):
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
        used = tokens & known_set
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        n_fields = len(used)
        print(f"  [pre-audit] slot{it['id']:<2} role={it['role']:<4} ops={audit['operator_count']:>2} "
              f"fields={n_fields} len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:78]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符 (字段名拼写错误?): {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")
        if len(fixed) > 900:
            raise ValueError(f"slot{it['id']} 表达式超长 {len(fixed)} > 900")
        if len(it["optimize_reason"]) < 120:
            raise ValueError(f"slot{it['id']} optimize_reason 过短, 违反铁律5 白盒立项要求")


def check_dup_fingerprints(items: list, neutralization: str, universe: str):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    dups = []
    for it in items:
        h = corrector.compute_fingerprint(it["expression"], REGION, universe, DELAY, neutralization)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        if cur.fetchone():
            dups.append((it["id"], it["expression"][:60]))
    conn.close()
    print(f"  [dup-check] 历史已测 {len(dups)} 条 (配对槽经 purge 后应为 0): {dups}", flush=True)


async def submit_batch(items: list, state_path: str, neutralization: str, universe: str, tag: str):
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
                    json.dump({"location": location, "submitted_at": int(time.time()), "decay": DECAY,
                               "universe": universe, "neutralization": neutralization}, f)
                print(f"[submit-{tag}] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    return location


def build_summary(items: list, results: list, direction: str):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret, to = m.get("returns") or 0, m.get("turnover") or 0
        rows.append({
            "slot": it["id"], "role": it["role"], "type": it["type"], "baseline": it["baseline"],
            "expression": it["expression"], "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": to, "returns": ret,
            "ret_over_to": (ret / to) if to else None,
            "drawdown": m.get("drawdown"), "margin_bps": (m.get("margin") or 0) * 10000,
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "sub_sharpe": m.get("sub_universe_sharpe"), "two_year_sharpe": m.get("two_year_sharpe"),
            "inv_sharpe": m.get("investability_sharpe"), "rn_sharpe": m.get("risk_neutralized_sharpe"),
            "ra_failed": ra.get("ra_failed"), "ra_failed_checks": ra.get("ra_failed_checks"),
            "fail_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("fail") or [])],
            "warning_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("warning") or [])],
        })
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    d = DIRECTIONS[direction]
    return {"direction": direction, "direction_name": d["name"], "hypothesis": d["hypothesis"],
            "settings": {"neutralization": d["neutralization"], "universe": d["universe"], "decay": DECAY,
                         "truncation": TRUNCATION, "region": REGION, "delay": DELAY,
                         "nan_handling": NAN_HANDLING},
            "rows": rows,
            "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                     "step2": step2, "final": final}}


def print_table(summary: dict):
    s = summary["settings"]
    print(f"\n===== Wave10-A 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} "
          f"decay={s['decay']} (历史全部为6) trunc={s['truncation']}", flush=True)
    print(f"{'槽':>2} {'角色':<5} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} "
          f"{'Mgn':>6} {'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>10} {'raFail':>6}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['role']):<5} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>5.2f} "
              f"{to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} "
              f"{r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} "
              f"{ls:>10} {str(r['ra_failed']):>6}", flush=True)
        if r["fail_checks"] or r["warning_checks"]:
            print(f"      fail: {r['fail_checks']}", flush=True)
            print(f"      warn: {r['warning_checks']}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave10-A] 字段字典 {len(known_fields)} 个装载", flush=True)

    direction = "D25"
    d = DIRECTIONS[direction]
    items = [{"id": s["id"], "role": s["role"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W10A_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8, f"批次必须 8 槽, 实为 {len(items)}"
    print(f"\n[Wave10-A-{direction}] {d['name']}", flush=True)
    print(f"[Wave10-A-{direction}] 假说: {d['hypothesis']}", flush=True)

    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
    check_dup_fingerprints(items, d["neutralization"], d["universe"])

    ts = int(time.time())
    batch_path = os.path.join(CAMPAIGN, f"batch_w10a_{direction}_{ts}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W10A_{direction}", "region": REGION, "universe": d["universe"],
                   "delay": DELAY, "decay": DECAY, "category": CATEGORY,
                   "known_fields": known_fields, "items": items}, f, ensure_ascii=False, indent=1)
    print(f"[Wave10-A] 批次文件: {batch_path}", flush=True)

    state_path = os.path.join(CAMPAIGN, f"state_w10a_{direction}.json")
    loc = await submit_batch(items, state_path, d["neutralization"], d["universe"], direction)
    if not loc:
        print("[Wave10-A] 无 location, 退出", flush=True)
        return

    print("[Wave10-A] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print(f"[Wave10-A] fetch 空! {str(fetch)[:500]}", flush=True)
        return
    res_path = os.path.join(CAMPAIGN, f"batch_w10a_{direction}_{ts}_result.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave10-A] 结果已存: {res_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_w10a_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave10-A] 汇总已存: {sum_path}", flush=True)
    print("\n[Wave10-A] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
