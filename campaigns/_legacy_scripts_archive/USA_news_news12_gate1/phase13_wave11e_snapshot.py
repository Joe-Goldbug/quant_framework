# -*- coding: utf-8 -*-
"""Gate1 Wave11-E · 事件快照族探索 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== 立项依据: 最后一个未探索的大维度, 且是 R/TO 的唯一希望 ===

**战绩盘点 (本轮 Gate1 至今)**:
  Wave11-A 基本面首攻: 8 槽全败 (PEAD 数学不可实现: 无 estimate 字段 + z-score 吞幅值)
  Wave11-C pooled IC 提升: 8 槽全败 (Sh 天花板 0.63; 窗口/口径/归一/稳健/提纯/输出层/门控 7 类机制全证伪)
  Wave11-D 双压力分子: **槽5 突破** Sh 1.56 / 2Y 2.23 / rn 2.00 / CW ok / Ret 8.47%
                      (ts_rank250 层在 DUALP 上同时抬 Sh 与 2Y, 打破 ts_rank 只对 pooled 有效的旧结论)

**双约束联立的战略定位**:
    Fit>=1 需 Ret>=TO/Sh^2 ; Mgn>=10bps 需 Ret>=0.5*TO
    ==> **R/TO>=0.5 是与 Sh 无关的硬约束**
    DUALP (Ret 8.47%) 对应 Mgn 达标的 TO 上限 16.9%; 而日更内核上所有降 TO 手段
    (backfill/累积/门控/组内化) 都被实证会同比例降 Ret 或崩 Sh/2Y.
    ==> **唯一希望是找到一个 R/TO 天然高 (>=0.4) 且 Sh 能到 1.4+ 的新低频内核**.

**为什么是事件快照族 (nws12_mainz_* / prez_* / afterhsz_*)**:
  1. 315 基线中这些字段**零使用** (pre_news 极值历来只作反应内核的归一化分母);
  2. 它们是**事件行数据集**: 非事件日为 NaN, 配 ts_backfill 后持仓冻结, TO 结构性崩塌;
  3. Agent-RV 字段族清点把「盘前状态族」评为 12/15 分最高价值轴
     (新鲜度 4 x 慢变量 3 x 正交性 5);
  4. 战役内证据: backfill 化内核把 TO 从 120% 压到 69-84% 且 Sh 守住 1.20-1.43
     (MP0E7qxL 等), 说明事件稀疏内核 + backfill 是有效的低 TO 机制.

=== 本批 8 条 = 4 条新轴 + 4 条变体/对照 ===
  槽1  盘前会话位置反转      (tonlast 在 [tonlow,tonhigh] 的相对位置, reverse)
  槽2  盘前累计漂移 ATR 归一  (tonlast-prevclose)/41rta, reverse
  槽3  盘后漂移延续          (eodclose-dayopen)/41rta, **不取 reverse** (唯一延续假说)
  槽4  隔夜跳空 x 规模反转    (opengap 反转) x (mktcap 反转) 乘性交互
  槽5  散户拆单注意力        (tick_count / 30日均量) 反转
  槽6  忽视度慢倾斜          (30日量 x 昨收) / mktcap 反转 (纯慢变量)
  槽7  事件前量能 x 跳空延续  (prev_vol/mov_vol) x sign(opengap) (第二延续假说)
  槽8  槽1 的 ts_rank250 输出层变体 (与槽1 构成输出层 A-B)

=== 经济学 (逐条见 optimize_reason) ===
  共同逻辑: news12 是事件行数据集, mainz/prez/afterhsz 三族分别对应主板块/盘前/盘后
  三个交易时段的快照. 这些快照在事件日跳变, 事件间 stale, 天然低频.
  若其中含独立于 eod/ton 价格族的预测信息, 则 R/TO 结构性高于日更内核.

=== 平台纪律 ===
  winsorize 须命名参数; news_eod_open 已下线禁用; 一律显式 reverse (除延续假说条).
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

# ---- 事件快照族构件 (VECTOR, 须 vec_avg 归约) ----
TL = "vec_avg(nws12_mainz_tonlast)"        # 新闻时刻价格 (主板块)
TLO = "vec_avg(nws12_mainz_tonlow)"        # 新闻前时段最低价
THI = "vec_avg(nws12_mainz_tonhigh)"       # 新闻前时段最高价
PC = "vec_avg(nws12_mainz_prevclose)"      # 前收盘
RTA = "vec_avg(nws12_mainz_41rta)"         # 14 日 ATR (慢波动基准)
GAP = "vec_avg(nws12_mainz_opengap)"       # 隔夜跳空
MC = "vec_avg(nws12_mainz_mktcap)"         # 市值 (事件日快照)
MV = "vec_avg(nws12_mainz_mov_vol)"        # 30 日移动均量
PV = "vec_avg(nws12_mainz_prev_vol)"       # 前一日成交量
TICK = "vec_avg(total_tick_count)"         # 当日 tick 总数
MAVOL = "vec_avg(thirty_day_moving_average_volume)"
AE = "vec_avg(nws12_afterhsz_eodclose)"    # 盘后收盘
AD = "vec_avg(nws12_afterhsz_dayopen)"     # 盘后开盘
ARTA = "vec_avg(nws12_afterhsz_41rta)"


def gate3(field):
    """事件快照族标准壳: 新鲜度门 (3 日) + backfill(3) 冻结"""
    return f"less(days_from_last_change(vec_count({field})), 3)"


# 槽1 内核: TON 时刻价格在盘前 [最低, 最高] 区间中的相对位置
POS = (f"divide(subtract({TL}, {TLO}), "
       f"add(subtract({THI}, {TLO}), {TL}))")

SLOTS = [
    {
        "id": 1, "type": "PREPOS_REVERSAL", "role": "NEW_AXIS",
        "baseline": "无 (nws12_mainz_ton* 三字段在 315 基线零使用)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_tonlast')}, "
            f"ts_backfill(reverse(rank({POS})), 3), 0)"),
        "optimize_reason": (
            "【全新轴 · 盘前会话位置反转】内核 = TON 时刻价格在盘前 [最低, 最高] 区间中的相对位置 "
            "(0=贴近盘前低点, 1=贴近盘前高点), 取 reverse. 三个字段同属 nws12_mainz 报表族, "
            "cov 均 0.9733, 同缺失模式即同一事件行产出; 新闻前时段极值在新闻发布时已完全可知, "
            "无前瞻泄露. 经济学: 事件前买入压力把价格推向盘前高点的吸筹型资金, 在期望上持续为"
            "过度反应 —— 新闻落地后缺乏新增买盘接力, 价格向会话中位回落 (均值回复). "
            "反向假说同样可辩护 (盘前强 = 知情买入, 应延续), 故符号需双向验证: "
            "若本槽为显著负值, 立刻补 reverse 双子. 结构: 事件快照内核 + backfill(3) 冻结 + "
            "dflc<3 新鲜度门, 是内核去日更化的标准形态. 315 基线中 pre_news 极值历来只作"
            "反应内核的分母出现, 从未独立作预测子, 本槽是全库首次. "
            "信息增益为全批最高: 同时检验 mainz 快照族是否含独立于 eod/ton 价格族的信息."),
    },
    {
        "id": 2, "type": "PREDRIFT_ATR_REV", "role": "NEW_AXIS",
        "baseline": "omokbbKl divide(subtract(U,D),news_atr14) Sh0.70@TO125% (无快照版)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_tonlast')}, "
            f"ts_backfill(reverse(rank(divide(subtract({TL}, {PC}), add({RTA}, 0.01)))), 3), 0)"),
        "optimize_reason": (
            "【盘前累计漂移 ATR 归一反转】内核 = (TON 时刻价 - 前收盘) / 14 日 ATR, 即事件前"
            "累计漂移折合多少个 ATR, 取 reverse. 与槽1 同轴不同窗: 槽1 用会话内 [低,高] 位置, "
            "本槽用跨夜 + 会话的全程位移 (prevclose -> tonlast). ATR 归一把位移变成个股波动率"
            "调整后的强度, 使高波动股与低波动股的同等美元位移被区分开. "
            "经济学: 事件前累计漂移超过 1 个 ATR 的部分由流动性冲击与趋势资金造成而非新信息, "
            "这类拉伸在期望上持续为不可持续, 新闻日在期望上持续为回吐. "
            "此前 ATR 归一只在无累积版测过 (omokbbKl Sh 0.70 @ TO 125%), 失败源于无快照的高 TO; "
            "本槽用事件快照 + backfill(3) 把 TO 结构性压低, 检验 ATR 归一的信号质量是否"
            "在低 TO 框架下才显现. 若本槽与槽1 双双 Sh<1.0, 则盘前状态轴整体证伪."),
    },
    {
        "id": 3, "type": "AFTERDRIFT_CONT", "role": "NEW_AXIS",
        "baseline": "无 (afterhsz 族在 315 基线零使用)",
        "expression": (
            f"trade_when({gate3('nws12_afterhsz_eodclose')}, "
            f"ts_backfill(rank(divide(subtract({AE}, {AD}), add({ARTA}, 0.01))), 3), 0)"),
        "optimize_reason": (
            "【盘后漂移延续 · 全批唯一延续假说】内核 = (盘后收盘 - 盘后开盘) / 14 日 ATR, "
            "**不取 reverse** (延续方向). 经济学: 机构在盘后薄市场中以更大单手数重新定价 "
            "(延迟价格发现), 盘后超过 1 ATR 的方向性漂移在期望上持续为未完成调整, "
            "次日开盘在期望上持续为同向延续. 这与家族全部反转基调相反, 是刻意的方向对照: "
            "若本槽显著为正 (延续), 说明盘后时段存在独立的定价延迟效应, 且该效应与日内反转"
            "机制不冲突 (不同时段); 若显著为负, 则盘后漂移同样是过度反应, 应改 reverse. "
            "风险: afterhsz 族 cov 仅 0.707 (盘后事件子集), 日截面可能只有 30-80 只, "
            "CONCENTRATED_WEIGHT 风险显著高于其他 7 条 —— 本槽同时是 CW 风险探针. "
            "若 CW fail, 下一波该族需配 group_rank 或提高 backfill 以分散."),
    },
    {
        "id": 4, "type": "GAPxSIZE_REV", "role": "NEW_AXIS",
        "baseline": "无 (opengap x mktcap 交互零使用)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_opengap')}, "
            f"ts_backfill(multiply(reverse(rank({GAP})), reverse(rank({MC}))), 3), 0)"),
        "optimize_reason": (
            "【隔夜跳空 x 规模反转 · 乘性交互】两个 rank 型相乘: 跳空的反转信号 x 市值规模的反转"
            "信号 (reverse(rank(mktcap)) 即给小市值高权重). 经济学: 小市值股票做市商更薄、"
            "散户隔夜情绪单占比更高, 其跳空在期望上持续为流动性冲击而非信息, 事件日在期望上"
            "持续为均值回复; 大市值股票的跳空更可能是真实信息 (有分析师与机构持续覆盖), "
            "反转弱. 故规模是跳空反转强度的调节变量, 乘性交互比单独任一维度更纯. "
            "先例: 纯跳空反转 Sh 0.35 @ TO 138%; 跳空 x 反应修饰 Sh 0.18-1.03 —— "
            "本构念的增量在 x 规模且内核无反应字段 (去日更化). "
            "⚠️ 乘性交互的两个 rank 都取 reverse, 若真实机制是延续则乘积会双重放大错误方向, "
            "本槽的负值读数同样有信息量 (分离跳空与规模各自的符号)."),
    },
    {
        "id": 5, "type": "TICK_ATTENTION_REV", "role": "NEW_AXIS",
        "baseline": "无 (tick 计数独立构念零使用; news_tot_ticks 仅作分母)",
        "expression": (
            f"trade_when({gate3('total_tick_count')}, "
            f"ts_backfill(reverse(rank(divide({TICK}, add({MAVOL}, 1)))), 3), 0)"),
        "optimize_reason": (
            "【散户拆单注意力 · tick 微观结构】内核 = 当日 tick 总数 / 30 日移动均量, "
            "即平均单手规模的代理 (高 = 散户拆单主导, 低 = 机构大单主导), 取 reverse. "
            "经济学: 零售与算法以小单拆单执行而机构以大单执行, 事件日 tick 相对月度量基准的"
            "异常放大在期望上持续为散户注意力主导, 其价格反应在期望上持续为过度反应并次日反转. "
            "这与 vol_ratio (份额量注意力) 是不同的透镜: 份额量度量资金体量, tick 数度量"
            "交易笔数, 二者的比值才是单手规模. 基线中 news_tot_ticks 仅作反应内核的分母出现 "
            "(Sh 0.58-1.28 但全高 TO), 独立构念零先例. "
            "两个字段 cov 均高 (1.0 / 0.958), breadth 应充足. "
            "若散户注意力假说在本宇宙不成立, 本槽可能接近噪声 (Sh ~0), 这是低成本判决实验."),
    },
    {
        "id": 6, "type": "NEGLECT_TILT", "role": "NEW_AXIS",
        "baseline": "reverse(group_rank(news_atr14/news_eod_close,industry)) Sh-0.82@TO22% (负面先例)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_mktcap')}, "
            f"ts_backfill(reverse(rank(divide(multiply({MV}, {PC}), add({MC}, 1)))), 3), 0)"),
        "optimize_reason": (
            "【忽视度慢倾斜 · 30 日换手率】内核 = (30 日移动均量 x 前收盘) / 市值 = 30 日换手率, "
            "取 reverse (低换手组占优). 全慢变量构造: 三个字段 (mov_vol/prevclose/mktcap) "
            "全是事件日读取的慢基准, 无任何当日反应成分, 是本批 TO 最低候选. "
            "经济学: 低覆盖度股票缺乏持续跟踪的资金, 其新闻在期望上持续为定价不足 (欠反应), "
            "事件后在期望上持续为漂移修正, 故低换手组在期望上持续为占优 (忽视度效应, "
            "Merton 1987 投资者认知假说). ⚠️ 诚实附注: 基线有负面先例 —— "
            "reverse(group_rank(news_atr14/news_eod_close, industry)) 纯慢变量倾斜仅 Sh -0.82 @ TO 22%, "
            "说明本数据集上无事件信息的纯特征倾斜可能整体无效. 本槽定位为忽视度假说的低成本探针, "
            "若 Sh<0.5 则该轴关闭, 不再投入. 若显著为正, 则它是唯一能进 TO<=11% 区的构造, "
            "后续全部预算压向慢变量内核."),
    },
    {
        "id": 7, "type": "PREVOLxGAP_CONT", "role": "NEW_AXIS",
        "baseline": "无 (prev_vol/mov_vol 比值与方向交互零使用)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_prev_vol')}, "
            f"ts_backfill(multiply(sign({GAP}), "
            f"rank(divide({PV}, add({MV}, 1)))), 3), 0)"),
        "optimize_reason": (
            "【事件前量能积累 x 跳空方向延续 · 第二延续假说】内核 = sign(隔夜跳空) x "
            "rank(前一日量 / 30 日均量). 经济学: 知情交易者为规避冲击成本在事件前一日放量吸筹, "
            "前日量相对月度基准的抬升叠加隔夜定向跳空, 在期望上持续为知情仓位确认, "
            "事件日在期望上持续为同向延续 (与反转族对立的第二延续假说). "
            "关键设计: prev_vol 是**滞后一日**的量, 完全不含事件当日反应成分, 是本批最干净的"
            "事前信息变量; mov_vol 是 30 日慢基准. 若跳空已完全吸收积累信息, 则增量有限 "
            "(本槽会接近噪声); 若积累信息领先于跳空, 则乘积项显著. "
            "与槽3 同属延续假说但机制不同 (盘后延迟定价 vs 事前吸筹), 可互相验证: "
            "两者同号则延续效应在多个时段独立存在, 是强证据."),
    },
    {
        "id": 8, "type": "PREPOS_TSRANK250", "role": "VARIANT",
        "baseline": "槽1 的 ts_rank250 输出层变体 (Wave11-D 槽5 证明 ts_rank 在 DUALP 上 +0.12 Sh/+0.59 2Y)",
        "expression": (
            f"trade_when({gate3('nws12_mainz_tonlast')}, "
            f"ts_backfill(reverse(ts_rank({POS}, 250)), 3), 0)"),
        "optimize_reason": (
            "【槽1 的 ts_rank250 输出层变体】与槽1 唯一差别是外层 rank 换成 ts_rank(250). "
            "Wave11-D 槽5 实证 ts_rank250 层在 DUALP 内核上同时抬 Sh (1.44->1.56) 与 "
            "2Y (1.64->2.23), 打破了此前 ts_rank 只对 pooled 有效的旧结论 —— "
            "该层的真实作用是**把输出压成 250 日窗口内的相对分位**, 对任何有持续性的内核都能"
            "削峰填谷. 事件快照内核 (POS) 有天然持续性 (事件间 stale), 预期 ts_rank 层同样有效. "
            "本槽与槽1 构成干净的输出层 A-B, 是判定 ts_rank 层是否为家族通用增益算子的"
            "第三个数据点 (pooled: +27%, DUALP: +8%, PREPOS: ?). "
            "若三点一致为正, 则 ts_rank250 应升级为家族标准输出层, 后续所有构造预置."),
    },
]

DIRECTIONS = {
    "E": {"name": "事件快照族探索: 4 条新轴 + 输出层/延续假说变体",
          "hypothesis": (
              "双约束联立显示 R/TO>=0.5 是与 Sh 无关的硬约束, 而日更内核 (eod/ton 价格族) 上"
              "所有降 TO 手段都被实证会同比例降 Ret 或崩 Sh/2Y. 唯一希望是 R/TO 天然高的新低频内核. "
              "事件快照族 (nws12_mainz_*/prez_*/afterhsz_*) 在 315 基线零使用, 是事件行数据集"
              "(非事件日 NaN, 配 backfill 后持仓冻结, TO 结构性崩塌), 且 Agent-RV 清点评为"
              "最高价值轴 (新鲜度4 x 慢变量3 x 正交性5). 本批 8 条覆盖 4 条新轴 (盘前位置/盘前漂移/"
              "盘后漂移/跳空x规模) + 散户注意力 + 忽视度 + 事前吸筹 + 输出层变体."),
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
    d = DIRECTIONS["E"]
    print(f"[Wave11-E] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11E_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-E] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11E", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11e_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-E] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-E] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-E] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-E] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11e_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-E ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-E] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
