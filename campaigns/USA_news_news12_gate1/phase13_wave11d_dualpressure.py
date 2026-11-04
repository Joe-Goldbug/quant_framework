# -*- coding: utf-8 -*-
"""Gate1 Wave11-D · 双压力分子家族全展开 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== 立项依据: 家族 Ret 新纪录资产, 从未系统展开 ===

并行同源研究 (phase12_wave11b_prescription, W1 批) 产出了家族 Ret 新纪录:

    DUALP = reverse(rank(divide(add(subtract(EOC,TON), subtract(EOC,VWAP)), VWAP)))
    其中 EOC=news_eod_close, TON=news_ton_last, VWAP=news_eod_vwap
    -> Sh 1.44 / TO 120.5% / **Ret 9.07%** (家族前纪录 7.86%) / 2Y 1.64
       / sub 0.94 / rnSh 1.98 / L/S 289-289 / **CW ok**

分子经济含义 = (收盘-新闻时刻价) + (收盘-当日VWAP) = 双重压力:
    收盘价同时偏离「新闻发布时的价格锚」与「当日成交量加权均价」.
    两个锚点分别度量 (a) 事件冲击的即时方向 (b) 全日买卖力量的均衡点.
    两者之和 = 新闻驱动买压/卖压的总额外度量, 且 VWAP 项自带成交量权重
    (VWAP 是成交量加权的, 故 subtract(EOC,VWAP) 隐含「收盘价相对全日主导资金的成本」).

=== 双约束联立的战略定位 ===
    Fit>=1 需 Ret>=TO/Sh^2 ; Mgn>=10bps 需 Ret>=0.5*TO
    ==> R/TO>=0.5 是硬约束; 家族 Ret 天花板决定 TO 必须 <=15.7%
    DUALP 的 Ret 9.07% 是全场最高, 对应 Mgn 达标的 TO 上限 = 9.07/0.5 = **18.1%**
    ==> 若能把 DUALP 的 TO 从 120.5% 压到 18.1% 且 Ret 不掉, Mgn 即达标;
        此时 Fit = 1.44*sqrt(9.07/18.1) = 1.02 也达标 (Sh 1.44 略低于 1.58 是唯一剩项).

=== 已测的 TO 压缩手段在 CTO 内核上的断崖 (并行研究实证) ===
    bf2 + 门 : Sh 1.47 / TO 83.7% / Ret 6.81%   <- 最优点
    bf3 + 门 : Sh 0.87 / TO 40.6% / Ret 3.36%   <- 断崖 (TO x0.49 但 Sh x0.59)
    bf20(exp): Sh 1.06 / TO 46.0% / Ret 4.33%
    ==> backfill 超过 2 天即断崖, 参数轴已关闭; 降 TO 必须换机制而非调参数.

=== 本批 8 条 = DUALP 家族的机制展开 (全部保持 3 字段) ===
    槽1  原样复现 (配对基准, 分离后续各槽的边际贡献)
    槽2  + backfill(2)          —— 已证最优点, 测其在 DUALP 上的迁移
    槽3  + 去均值 20 日         —— 并行实证该算子在 CTO 上把 2Y 从 1.49 抬到 2.37
    槽4  + winsorize(std=2)     —— 并行实证该算子在 CTO 上微正 (1.47->1.49)
    槽5  + ts_rank250 输出层    —— 输出层变体
    槽6  + group_rank(industry) —— 行业内排序
    槽7  60 日累积净方向占总活动 —— 把 DUALP 放进低 TO 框架 (攻 R/TO)
    槽8  + backfill(2) + winsorize 双重叠加 —— 两个已验证正收益算子的合流

=== 平台纪律 (并行同源研究实证, 已内化) ===
    winsorize 只接受命名参数 winsorize(x, std=N); 位置传参整批 ERROR 连坐.
    news_eod_open 已下线 (禁用). 一律显式 reverse.
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

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
CTO = f"subtract({EOC}, {TON})"                 # 压力一: 收盘 - 新闻时刻价
CVW = f"subtract({EOC}, {VWAP})"                # 压力二: 收盘 - 当日 VWAP
DUAL = f"add({CTO}, {CVW})"                     # 双压力分子
DUAL_R = f"divide({DUAL}, {VWAP})"              # 以 VWAP 归一 (家族 Ret 纪录内核)


SLOTS = [
    {
        "id": 1, "type": "DUALP_BASE", "role": "REPLICATE",
        "baseline": "并行 W1槽7 Sh1.44/TO120.5%/Ret9.07%/2Y1.64/rn1.98/CW ok",
        "expression": f"reverse(rank({DUAL_R}))",
        "optimize_reason": (
            "【配对基准 · 家族 Ret 纪录资产原样复现】DUALP = (收盘-新闻时刻价 + 收盘-当日VWAP)/VWAP, "
            "取 reverse 后横截面 rank. 该结构在并行同源研究的 W1 批拿到 Sh 1.44 / TO 120.5% / "
            "Ret 9.07% (家族前纪录 7.86%, 提升 15%) / 2Y 1.64 / sub 0.94 / rnSh 1.98 / L/S 289-289 / CW ok. "
            "本槽原样重跑的目的: (a) 复现这四个关键读数, 确认跨批稳定性 (跨设置复跑离散度可达 0.3-0.4 Sh); "
            "(b) 作为槽2-8 的唯一配对基准 —— 没有它, 后续 7 条的边际贡献无法归因. "
            "经济学: 双锚点偏离同时捕捉事件冲击的即时方向 (TON 锚) 与全日买卖力量均衡 (VWAP 锚, "
            "自带成交量权重), 两者之和比单一锚点更完整地度量新闻驱动资金流的净额. "
            "该槽不追求达标 (TO 120.5% 结构性过高), 追求可解释性."),
    },
    {
        "id": 2, "type": "DUALP_BF2", "role": "TO_COMPRESS",
        "baseline": "并行 W1槽1 bf2+门 CTO版 Sh1.47/TO83.7%/Ret6.81%",
        "expression": f"reverse(rank(ts_backfill({DUAL_R}, 2)))",
        "optimize_reason": (
            "【backfill(2) 迁移到 DUALP】并行研究在 CTO 内核上实证 backfill 参数轴的断崖: "
            "bf2 时 Sh 1.47 / TO 83.7% / Ret 6.81% 是最优点, bf3 立即崩到 Sh 0.87 / TO 40.6%. "
            "本槽把 bf2 迁移到 DUALP 内核, 检验该最优点是否内核无关 (若是, 则 bf2 是家族通用 TO 压缩器). "
            "预期: TO 从 120.5% 降到 80-90%, Ret 从 9.07% 降到 6.5-7.5%, Sh 保持 1.3-1.45. "
            "按 Mgn 反解, 该点 R/TO 约 0.08 -> Mgn 1.6bps, 仍差 6 倍; 但若 Sh 保持 1.4+ 且 2Y 保持 1.6+, "
            "它仍是家族综合最强资产之一, 值得作为后续所有构造的承载基座. "
            "机制: backfill(2) 让非事件日沿用 2 天前的信号, 持仓冻结 2 天, 换手降 30% 而 alpha 半衰期"
            " (新闻冲击的持续再定价期) 恰好约 2 天, 故信号损失小."),
    },
    {
        "id": 3, "type": "DUALP_DEMEAN20", "role": "TWOYEAR",
        "baseline": "并行 W1槽6 去均值CTO版 Sh1.37/TO105.9%/2Y2.37",
        "expression": (
            f"reverse(rank(subtract({DUAL_R}, ts_mean({DUAL_R}, 20))))"),
        "optimize_reason": (
            "【去均值 20 日 · 攻 2Y 短板】DUALP 减自身 20 日均值. 并行研究在 CTO 内核上实证该算子"
            "把 2Y 从 1.49 抬到 2.37 (+59%, W1槽6), 是全家族最强的 2Y 提升手段. 机制: "
            "原始 DUALP 含一个公司层面的慢变成分 (某些股票长期处于收盘强于/弱于 VWAP 的状态, "
            "如机构持续减持的股票), 该成分在样本前半段与后半段的符号可能反转, 拖累 2Y; "
            "减自身 20 日均值剥离这个慢变基线, 只保留相对近期状态的偏离, 使信号的时间稳定性上升. "
            "DUALP 的 2Y 已是 1.64 (不低), 但用户 mandate 要求 2Y>=1.58 且不能有任何警告项, "
            "更高的 2Y 是达成「无警告」的必要条件之一 (CLUSTER_TEST 与 2Y 常同向). "
            "预期: 2Y 抬到 1.8-2.2, Sh 维持 1.3-1.45, TO 维持 110-125%. 本槽不主打 Mgn, 主打 2Y 冗余."),
    },
    {
        "id": 4, "type": "DUALP_WINSOR2", "role": "ROBUST",
        "baseline": "并行 W1槽5 winsorize CTO版 Sh1.49 (vs 无winsorize 1.47)",
        "expression": (
            f"reverse(rank(divide(winsorize({DUAL}, std=2), {VWAP})))"),
        "optimize_reason": (
            "【winsorize(std=2) 稳健化】对双压力分子做 2 倍标准差缩尾后再除以 VWAP. "
            "并行研究在 CTO 内核上实证 winsorize(std=2) 微正 (Sh 1.47 -> 1.49), "
            "而同一算子在 pooled 内核上显著为负 (Wave11-C 槽5: Sh 0.61 -> 0.37) —— "
            "说明 winsorize 的效果取决于内核的极端值性质: CTO/DUALP 是价格差 (连续分布, 极端值多为"
            "真实大幅波动, 缩尾损失信息), pooled 是比值 (0-1 有界, 极端值多为小样本噪声, 缩尾有益). "
            "DUALP 属价格差类, 预期缩尾微正或中性. 平台纪律: winsorize 只接受命名参数 std=N, "
            "位置传参整批 ERROR 连坐 (并行实证), 本槽已用命名参数. "
            "本槽与槽1 构成 winsorize 有无的干净配对, 若 Sh 提升则确认该算子在价格差内核上的正收益, "
            "后续全部价格差类构造都应预置 winsorize."),
    },
    {
        "id": 5, "type": "DUALP_TSRANK250", "role": "OUTPUT",
        "baseline": "无 (DUALP x ts_rank250 零使用)",
        "expression": f"reverse(ts_rank({DUAL_R}, 250))",
        "optimize_reason": (
            "【ts_rank250 输出层】把外层 rank 换成 ts_rank(250). 家族实证: ts_rank 层在 pooled 内核上"
            "贡献 1.27 倍 Sh (0.48->0.61), 但在三条价格差存活分支上迁移失败 (Wave10-C: Sh 从 1.07-1.17 "
            "降到 0.46-0.98) —— 说明 ts_rank 不是通用增益算子, 其有效性取决于内核的时间自相关结构: "
            "对低频内核 (pooled) 有效, 对日更内核无效. DUALP 是日更内核, 预期 ts_rank 无效或微负, "
            "但本槽仍值得一测: DUALP 的 Ret (9.07%) 远高于 pooled (2.09%), 若 ts_rank 在其上能保持 Ret "
            "而降低排名噪声, 可能出现意想不到的组合. ts_rank 把输出压成 [0,1] 均匀分布, "
            "横截面同方差, 理论上有利组合构建. 本槽是输出层 A-B 的必要一环 (槽1=rank, 本槽=ts_rank)."),
    },
    {
        "id": 6, "type": "DUALP_GROUPRANK", "role": "OUTPUT",
        "baseline": "YPxOGboo group_rank(pooled,industry) Sh1.17/TO37.8%",
        "expression": f"reverse(group_rank({DUAL_R}, industry))",
        "optimize_reason": (
            "【group_rank(industry) 行业内排序】把输出层换成行业内 rank. 家族实证: "
            "group_rank 在 pooled 内核上把 Sh 从 0.61 抬到 1.17 (YPxOGboo, +92%), "
            "但在 ts_sum 版 pooled 上只给 +3% (npAlGnM8) —— 再次说明输出层效果依赖内核. "
            "对 DUALP 的预期: 行业内化剥离行业间的共同漂移 (如某行业整体事件后走强), "
            "保留行业内相对强度. 因 INDUSTRY 已是 settings 层中性化, group_rank 的增量在于"
            "中性化前的行业内竞争, 理论上能提纯 IC. 风险: group_rank 输出有界 [0,1], 若行业内"
            "股票数少则分辨率下降. 本槽与槽1 构成输出层 A-B (rank vs group_rank), "
            "若 Sh 明显提升则行业内化对价格差内核有效, 后续全部价格差构造应换输出层."),
    },
    {
        "id": 7, "type": "DUALP_POOLED60", "role": "LOW_TO",
        "baseline": "W1槽8 CTO累积版 Sh0.01 (失败先例) / GrgN9OAZ pooled Sh0.61",
        "expression": (
            f"reverse(ts_rank(divide(ts_sum({DUAL}, 60), "
            f"ts_sum(abs({DUAL}), 60)), 250))"),
        "optimize_reason": (
            "【60 日累积净方向占总活动 · 攻 R/TO 的唯一构造】把 DUALP 放进家族唯一 R/TO 达标区的"
            "框架: 分子 = 60 日双压力之和 (净方向存量), 分母 = 60 日双压力绝对值之和 (总活动). "
            "该比值的经济含义 = 过去两个月该股票新闻驱动资金流的「方向一致性」—— "
            "若持续同向 (净方向/总活动 接近 1), 说明有稳定的知情资金在持续表达观点; "
            "若正负抵消 (接近 0), 说明新闻影响是噪声. 家族实证: pooled 版的同类构造 (U/(U+D) 的 "
            "ts_sum 60 累积) 拿到 R/TO 0.403 (全场最高, GrgN9OAZ), 而 CTO 版的同类构造"
            " (W1槽8: ts_sum(CTO,20)/ts_sum(|CTO|,20)) 失败 (Sh 0.01). 本槽的赌注是: "
            "W1槽8 失败是因为 CTO 单压力的方向一致性弱, 而 DUALP 双压力 (含 VWAP 成交量权重) "
            "的方向一致性显著更强, 故在相同低 TO 框架下能保住 Sh. 这是本批唯一以 R/TO>=0.5 为"
            "直接目标的构造, 也是把「Ret 纪录内核」与「R/TO 纪录框架」合流的首次尝试. "
            "预期 TO 3-8%; 若 Sh >=1.0 则是全战役突破 (pooled 框架的 Sh 天花板是 0.63)."),
    },
    {
        "id": 8, "type": "DUALP_BF2_WINSOR", "role": "COMBO",
        "baseline": "槽2 (bf2) 与 槽4 (winsorize) 的合流, 两者均微正",
        "expression": (
            f"reverse(rank(ts_backfill(divide(winsorize({DUAL}, std=2), {VWAP}), 2)))"),
        "optimize_reason": (
            "【bf2 x winsorize 双重叠加】把两个在 CTO 内核上被并行实证为微正/最优的算子合流到 DUALP: "
            "backfill(2) (TO 压缩最优点, 无信号损失) x winsorize(std=2) (稳健化微正). "
            "家族纪律教训: 多个已验证正收益的算子叠加往往不是简单相加 (Wave10-C 的 ts_rank 迁移三连败), "
            "但 bf2 与 winsorize 作用在不同维度 (前者管时间冻结, 后者管截面稳健), 机制上不冲突, "
            "是最有可能正向合流的一对. 预期: TO 80-90%, Ret 6.5-7.5%, Sh 1.35-1.50. "
            "若本槽 Sh 高于槽2 与槽4 的任一, 说明两算子可叠加, 后续价格差族的标准构造应为"
            "「winsorize 内核 + bf2 冻结 + rank 输出」; 若低于两者, 则叠加收益为负, "
            "应回到单算子最优. 本槽是算子合流假设的判决实验."),
    },
]

DIRECTIONS = {
    "D": {"name": "双压力分子 (DUALP) 家族全展开: 8 条机制变体",
          "hypothesis": (
              "并行同源研究产出家族 Ret 新纪录 DUALP (Sh 1.44/TO 120.5%/Ret 9.07%/2Y 1.64/rn 1.98/CW ok), "
              "分子 = (收盘-新闻时刻价) + (收盘-当日VWAP), 双锚点同时捕捉事件冲击即时方向与全日"
              "买卖力量均衡 (VWAP 自带成交量权重). 双约束联立显示 Mgn 达标的 TO 上限 = Ret/0.5, "
              "DUALP 的 9.07% 对应 18.1% (全场最宽裕). 本批 8 条系统展开该家族: "
              "复现基准 + bf2 迁移 + 去均值(2Y) + winsorize 稳健化 + 两种输出层 + "
              "60 日累积低 TO 框架 (攻 R/TO) + 双算子合流."),
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
           # 命名参数 (平台实证: winsorize 只接受 winsorize(x, std=N), 位置传参整批连坐)
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
    d = DIRECTIONS["D"]
    print(f"[Wave11-D] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11D_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-D] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11D", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11d_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-D] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-D] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-D] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-D] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11d_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-D ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-D] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
