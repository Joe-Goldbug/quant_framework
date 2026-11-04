# -*- coding: utf-8 -*-
"""Gate1 Wave11-F · 三线并攻: 窗口轴 + 组层交叉 + 慢快混合架构 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== 立项依据 (三份 agent 报告收敛后的设计) ===
红队二审 + frontier 缺口分析 + 字段侦察的三重收敛:

1. frontier 实证: ts_rank 不是平滑器而是归一化器 —— TO 由输入信号的时间噪声决定
   (裸输入 ts_rank250 TO 中位 1.124 vs 预平滑输入 0.106, 10.6 倍差); 输出层算子对 TO
   无独立贡献. 降 TO 唯一有效路径 = 输入预平滑 (ts_backfill/ts_decay/ts_mean).
2. frontier 实证: gap(CL-Sh) 最小化配方 = amplitude 族 (-0.014) + group 输出层 (-0.003)
   + vec 聚合 (-0.008) + INDUSTRY + 宽书 + trade_when(<=2) 门控; 高 Sh 区 (>=1.4 的 60 行)
   从未出现过 group 输出层 —— 机制 1 是唯一同时攻 TO 与 CLUSTER 缺口的零测试交叉.
3. 红队二审: D 线 (慢信号x快催化剂) 必须有裸核对照, 否则门效应与裸核效应混淆;
   D1/D2 内壳从 rank 换 ts_rank250 (同核 +0.12 Sh / +0.59 2Y).
4. 字段侦察: 867 字段仅 104 被碰过; PE/SI/DY 等基本面水平值从未被系统挖掘
   (历史 6-10 次使用全是门或差分构造, 水平值引擎零测试).

=== 本批 8 条 = 四条假说的判决性实验 ===
A1   窗口轴 120      —— 合规空间内唯一可能补 LOW_SHARPE -0.02 缺口的杠杆
R2   dflc(TON) 新鲜门 —— dflc 首次作用于 MATRIX 价格字段 (全库 417 行 100% 作用于
                        vec_count(VHEX)); 三分支预登记: 恒真退化/门生效/书宽崩塌
M1a  组层全栈         —— 机制 1 判决性实验 (group_rank x TO 压缩栈)
CTRL 裸 CVW 核        —— D 线的归因基准 (全库 417 行零出现)
M2a  振幅x短窗x门     —— 低 TO 区唯一探针 (三个空白参数轴交叉点)
D1   便宜门           —— 低估值 = 下行有基本面支撑, 流动性冲击反转更强
D2   低空头门         —— 高空头 = 有知情空方, 走弱更可能是真实信息; 只对低 SI 股票提供流动性
D3   PE x SI 慢引擎   —— news12 基本面水平值的边缘探路 (高估值x高空 = 知情空方集中的过价股票)

=== 用户 mandate 合规 ===
2 <= 字段数 <= 3 (逐槽实算); 不限 op (用户原话); 不提交任何 alpha.
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
VHEX = "vec_count(high_price_excursion_stddev)"
UP, DN = "news_max_up_amt", "news_max_dn_amt"
PE, SI = "news_pe_ratio", "news_short_interest"

DUAL_R = f"divide(add(subtract({EOC}, {TON}), subtract({EOC}, {VWAP})), {VWAP})"
CVW_R = f"divide(subtract({EOC}, {VWAP}), {VWAP})"
AMP = f"divide({UP}, add({UP}, {DN}))"
S250 = f"reverse(ts_rank({DUAL_R}, 250))"

SLOTS = [
    {
        "id": 1, "type": "A1_WINDOW120", "role": "SHARPE_PUSH",
        "baseline": "同核 250 窗 Sh1.56/TO119.8%/Ret8.47%/2Y2.23/sub1.07/rn2.00/CW ok",
        "expression": f"reverse(ts_rank({DUAL_R}, 120))",
        "optimize_reason": (
            "【窗口轴 120 · 攻 LOW_SHARPE -0.02 缺口】把 DUALP_TSRANK250 的 ts_rank 窗口从 250 降到 120. "
            "依据: 红队实证 vwap-only 内核的窗口扫描 Sh 峰在 120 (250 窗 1.50 / 120 窗 1.56 / 500 窗 1.53), "
            "窗口轴是该内核唯一在合规空间内可能补上 LOW_SHARPE 缺口的杠杆; frontier 实证窗口长度本身不影响 TO "
            "(120 窗 n=5 TO 中位 1.224, 500 窗 n=4 TO 中位 1.227), 故本槽是纯 Sh 赌注不附带 TO 代价. "
            "经济学: 120 日窗口 = 约半年的事件压力历史, 比 250 窗更贴近当前的波动 regime, "
            "使「自身历史极端」的判定对 regime 迁移更敏感. 成功标准: Sh >= 1.58 (家族 fail 剖面从 3 项降到 2 项, "
            "追平战役最佳 9qEeNN3K); 证伪标准: Sh <= 1.50 (窗口轴平顶, 该轴关闭)."),
    },
    {
        "id": 2, "type": "R2_DFLC_TON", "role": "FRESHNESS_GATE",
        "baseline": "无门同核 Sh1.56/TO119.8%; dflc(VHEX)<=2 门在 CTO 核上 +0.04~0.13 Sh",
        "expression": (
            f"trade_when(less(days_from_last_change({TON}), 2), {S250}, 0)"),
        "optimize_reason": (
            "【dflc(TON) 新鲜门 · 全批信息密度最高的探针】用 days_from_last_change 直接作用于 MATRIX 价格字段 "
            "news_ton_last, 门控只交易「上次新闻发生在 2 天内」的股票. 三重价值: (a) 全库 417 行 dflc 100% 作用于 "
            "vec_count(VHEX), MATRIX 字段的 dflc 语义 (NaN 是否计为变化) 从未探测 —— 该语义决定今后所有门设计的写法; "
            "(b) 战役全部最强行都带 dflc(VHEX)<=2 门, 但 VHEX 门是「 excursion 事件新鲜度」, TON 门是「新闻新鲜度」, "
            "二者是不同的催化剂掩码; (c) 若门生效, 这是全批唯一不依赖组层的降 TO 杠杆. "
            "三分支预登记: 恒真退化 (dflc 恒 0, 复刻基线 Sh1.56) / 门生效 (TO 60-90%, Sh 1.2-1.5) / "
            "书宽崩塌 (TON 变化过频, 近空仓 UNITS 警告). 成功标准: TO <= 90% 且 Sh >= 1.30."),
    },
    {
        "id": 3, "type": "M1a_GROUP_STACK", "role": "GROUP_LAYER",
        "baseline": "同栈 plain-rank (Fit 全场#2) Sh1.49/TO83.7%/Ret6.93%/Fit0.43/2Y1.53/sub1.42",
        "expression": (
            f"trade_when(less(days_from_last_change({VHEX}), 2), "
            f"reverse(group_rank(ts_backfill(divide(winsorize(subtract({EOC}, {TON}), std=2), "
            f"add({VHEX}, 1)), 2), industry)), 0)"),
        "optimize_reason": (
            "【机制 1 判决性实验 · 组层 x TO 压缩栈】把 Fit 全场第 2 的降 TO 栈 (winsorize(EOC-TON) / VHEX 计数归一 / "
            "bf2 冻结 / dflc<=2 门) 的最外层 rank 换成 group_rank(industry). frontier 实证: group 输出层是 gap(CL-Sh) "
            "最小的结构 (-0.003 vs plain rank -0.066), TO 中位 0.398 天然低换手, 且 Sh>=1.4 的 60 行从未用过组层 —— "
            "这是唯一同时攻 TO 与 CLUSTER_TEST 两个缺口的零测试交叉. 与 wave11d 槽6 (group_rank 在 DUALP 核上 "
            "Sh 1.44->0.61 崩盘) 的关键差异: VHEX 分母已预先归一行业波动水平差, 组层要消除的东西内核自己消除了一半; "
            "winsorize 截断行业聚集的极端名; bf2 平滑组内排序; 内核强度更高. 行业内排序比全市场排序更粘 (同行业个股 "
            "相对位置日内稳定), 有直接压 TO 的机理. 成功标准: Sh >= 1.20 且 TO <= 0.65 (该 TO 桶新前沿点); "
            "证伪标准: Sh <= 0.90 (组层租金不可支付, 机制 1 关闭)."),
    },
    {
        "id": 4, "type": "CTRL_CVW_TSRANK250", "role": "CONTROL",
        "baseline": "全库 417 行零出现; 最近亲: DUALP 双腿版 Sh1.56, VHEX 分母版 (N1eGbEGo) Sh1.50",
        "expression": f"reverse(ts_rank({CVW_R}, 250))",
        "optimize_reason": (
            "【裸 CVW 核对照 · D 线的归因基准】只保留双压力中的 VWAP 腿 (EOC-VWAP)/VWAP 配 ts_rank250 输出层. "
            "红队二审强制项: D1/D2 两个门槽共享此内核, 若无裸核对照, 门效应与裸核效应混淆, D 线读数不可归因. "
            "正则实证该式在全部 824 条历史表达式中零出现 (VHEX 分母版与双腿版都测过, 裸版没有). "
            "经济学: 收盘价相对「新闻时刻到收盘的成交量加权均价」的偏离 = 全日买卖力量均衡点对收盘价的引力; "
            "反向 = 抄底被日内卖压压低的收盘. ts_rank250 只选自身历史极端. 成功标准: 建立裸核基线 "
            "(预期 Sh 1.35-1.50 / TO 115-125% / Ret 6-7%), 使 D1/D2 的门增益可被减出来."),
    },
    {
        "id": 5, "type": "M2a_AMP_BF20_TSRANK40", "role": "LOW_TO_PROBE",
        "baseline": "amplitude+bf60+group_rank+门 (低 TO 区最强) Sh1.19/TO37.5%/CL1.15/Fit0.38",
        "expression": (
            f"trade_when(less(days_from_last_change({VHEX}), 2), "
            f"reverse(ts_rank(ts_backfill({AMP}, 20), 40)), 0)"),
        "optimize_reason": (
            "【振幅 x 短窗 ts_rank x 新鲜门 · 低 TO 区唯一探针】振幅比率 = 新闻后上行 excursion 占上下行总 excursion "
            "的比例 (UP/(UP+DN)), 反向 = 买入以下行主导的新闻日股票 (与 DUALP 同源的流动性提供故事, 但用 excursion "
            "不对称度量而非收盘-锚点偏离). 结构坐在三个空白参数轴的交叉点: bf20 (amplitude 族 bf5/20/120/250 各只测过 "
            "1 次) x 短窗 ts_rank40 (amplitude 上短窗仅 1-2 行且 Sh<0.5) x dflc<=2 门 (CL top6 行共有). "
            "frontier 实证 amplitude+ts_rank250 的 TO 中位仅 0.121 (稀疏事件场 + 时序 rank 天然低换手), 且 amplitude 是 "
            "gap 最小的字段族 (-0.014). ts_rank40 的加入把「当前不对称性」与「该股票自身过去 40 天的不对称性」比较, "
            "只赌自身异常. 成功标准: Sh >= 0.90 且 TO <= 0.25 (低 TO 区新点); 该槽先验弱 (每轴独立先验都指向低 Sh), "
            "定位是测绘非通关."),
    },
    {
        "id": 6, "type": "D1_PE_GATE", "role": "SLOW_FAST",
        "baseline": "裸核对照 = 槽4; 历史 PE 门只测过 >0.8/0.9 高档位且都在 amplitude 核上 (Sh 0.24-0.44)",
        "expression": (
            f"trade_when(less(rank({PE}), 0.5), reverse(ts_rank({CVW_R}, 250)), 0)"),
        "optimize_reason": (
            "【便宜门 · 价值支撑条件化的流动性反转】只对横截面估值最便宜的一半股票 (rank(PE) < 0.5) 执行 CVW 流动性 "
            "反转. 经济学四段链: 机制 = 新闻日收盘价被日内卖压压低的程度包含流动性冲击与信息两种成分; 行为 = 流动性 "
            "冲击成分在未来数日回归, 信息成分不回归; 基础慢信号 = PE 估值水平 (下行有基本面支撑的股票, 其流动性 "
            "冲击更可能反转 —— 便宜股票的抛售有价值底, 贵股票的抛售可能是重定价的开始); 动态催化剂 = 新闻事件日的 "
            "双压力偏离. 历史 PE 门全部测在高档位 (>0.8/0.9) 且都挂在 amplitude 核上, 低档位 + 价格上下文核 + "
            "ts_rank250 壳的三重交叉零测试. 红队二审修正: 内壳从 rank 换 ts_rank250 (同核 +0.12 Sh / +0.59 2Y). "
            "宽度预登记: L/S 从 290/290 砍到 140-160/160, 单名权重翻倍, CW fail 概率 25-30%. "
            "成功标准: 门增益为正 (Sh 不低于裸核 -0.15) 且 TO <= 80%."),
    },
    {
        "id": 7, "type": "D2_SI_GATE", "role": "SLOW_FAST",
        "baseline": "裸核对照 = 槽4; 历史 SI 门只测过 >0.8/0.88 高档位 (sub 0.02 崩过, Sh 0.51)",
        "expression": (
            f"trade_when(less(rank({SI}), 0.5), reverse(ts_rank({CVW_R}, 250)), 0)"),
        "optimize_reason": (
            "【低空头门 · 信息与流动性的分离条件化】只对空头兴趣最低的一半股票 (rank(SI) < 0.5) 执行 CVW 流动性反转. "
            "经济学: 高空头的股票存在持续的知情空方 (SI = 卖空股数/流通股数), 其新闻日走弱更可能是真实负面信息 "
            "而非可反转的流动性冲击; 低 SI 股票的新闻日卖压则更接近无信息流动, 是流动性提供者应该吸收的对象. "
            "这是战役「信息 vs 流动性」主叙事最直接的判决性实验 —— 整个 DUALP/振幅家族的 alpha 都建立在"
            "「提供流动性赚反转」的机制上, 本槽直接检验该机制的边界条件. 历史 SI 门全部在高档位 (>0.8/0.88) "
            "且 sub-universe 崩过 (0.02), 低档位 + CVW 核 + ts_rank250 壳零测试. SI 为双周快照作门只是状态筛选, "
            "与上轮 SI 作分母的混合时间尺度交互有本质区别. 成功标准: 门增益为正且 sub >= 0.5 (SI 门不重演 sub 崩)."),
    },
    {
        "id": 8, "type": "D3_PE_SI", "role": "SLOW_ENGINE",
        "baseline": "零测试; PE 历史 8 次/SI 10 次使用全是门或差分构造, 水平值乘性交互从未出现",
        "expression": f"reverse(rank(multiply({PE}, {SI})))",
        "optimize_reason": (
            "【PE x SI 慢引擎 · news12 基本面水平值的边缘探路】做空「高估值且高空头」的股票. 经济学: 估值贵 "
            "(PE 高) 与知情空方集中 (SI 高) 同时出现, 是两类独立信息对同一判决的一致确认 —— 贵的股票被专业空头 "
            "持续做空, 其价格更可能向下修正; 乘性交互要求两个条件同时满足, 比任一单腿更纯. 这是全批唯一走 "
            "「Fit 的 TO 分母」路线的槽: 纯慢基本面信号, 预期 TO 5-15%, 若有任何边缘, Fit 公式中的 max(TO,0.11) "
            "下限保护会起作用 (TO<=11% 时 Sh1.58 仅需 Ret4.4%). 战略价值: news12 的 867 个字段中 763 个从未被碰, "
            "基本面水平值 (PE/EPS/DY/SI/cap) 只被用作门或差分; 本槽是慢引擎路径的探路针 —— 若 Sh 显著为正, "
            "开辟与事件反转完全平行的第二条战线; 若为零, 关闭该方向. 反向版预注册: 仅当 Sh <= -0.50 且 2Y >= 0.80 "
            "且 sub >= 0 才可考虑反向 (逼空故事), 否则先加 PE>0 门清负 PE 污染重测, 不擦鞋."),
    },
]

DIRECTIONS = {
    "F": {"name": "三线并攻: 窗口轴 + 组层交叉 + 慢快混合架构 (8 条)",
          "hypothesis": (
              " frontier 红队双重审计后的重设计. A1/R2 攻 LOW_SHARPE 缺口 (家族离通过最近的单项, -0.02); "
              "M1a 是 frontier 指出的唯一同时攻 TO 与 CLUSTER 缺口的零测试交叉 (组层 x 降 TO 栈); "
              "CTRL 是 D 线的归因基准 (红队二审强制); M2a 是低 TO 区唯一探针; D1/D2/D3 是全新的"
              "「慢信号 x 快催化剂」混合架构首攻 (用户四段链框架的直接实现), 其中 D3 同时是 news12 "
              "基本面水平值的边缘探路针."),
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
    d = DIRECTIONS["F"]
    print(f"[Wave11-F] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11F_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-F] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11F", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11f_{ts}.json"), "w", encoding="utf-8"),
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

    print("[Wave11-F] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-F] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11f_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-F ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-F] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
