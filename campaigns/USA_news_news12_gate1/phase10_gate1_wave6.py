# -*- coding: utf-8 -*-
"""Gate1 Wave6 多 agent 优化驱动 (2026-10-24).

Wave5 判决 (24 槽):
  P 自身极端度族 -> MOVE_EXTREMITY_250 Sh1.57/2Y2.16/sub1.12 (第二强者, 差 0.01 过 Sh 线);
     组内秩化证伪 (0.46); 所有原始形态 TO 仍 118-129% (NaN 流失如预期)
  Q 冠军形态空间 -> 计数口径稳健 (换下行计数/250 日窗口 = 冠军同值 1.61/2Y09);
     价格归一版 Sh1.43/2Y1.98/rnSh2.05 (全场最高风险中性)/Ret7.82%;
     🔴 bf60 对注意力族致死 (1.61->0.87, 2Y 2.09->0.45): 该边缘只在事件当日有效
     -> 两大族优势互斥: 振幅族可回填但 2Y 死 (0.78), 注意力族有 Sh+2Y 但瞬态
  R @STATISTICAL -> 彻底证伪: bf 族 Sh 0.32-0.79 且 2Y 转负 (与种子战役 8/8 净负互证);
     内生信念门控证伪 (前10% Sh -0.05, 前20% 0.27): 边缘是不可集中的宽横截面现象
     (与 J 批外生门控形成双重证据); bonus: CLOSE_VWAP_PER_COUNT Sh1.63 (微观结构新轴)

🔴 结构性结论 (五波 144 槽): Margin 恒等式 Mgn=20xRet/TO 需 R/TO>=0.5, 家族实测最高 0.098 (5.1x 缺口);
   每条降换手路径都被封死: 平滑 (瞬态墙) / 回填 (注意力族致死) / 门控 (毁边) / MARKET (TO 不降)
   / STATISTICAL (毁边) / 长短窗 (TO 37% 饱和)

Wave6 三路 (每路 8 槽) — 最后未测经济假说:
  V main_* 注意力归一族: news12 内一整套未测的 main_* VECTOR 会话字段 (45 个, 覆盖 1.0):
    相对基准表现/成交量激扰/多视野反应, 全部以'每单位成交量惊异'归一 (成交量稀缺假说,
    与事件计数归一化互补的第二个注意力代理)
  W 衰退 (fade) 结构族: 10/30/60/90/120 分钟涨跌幅的两两差 = 初始反应相对最终变化的衰退幅度
    — 教科书级过度反应签名 (大衰退=当日回吐), 从未测试; 含 10v120/30v120/60v120/90v120
    视野扫描与成交量惊异归一版
  X 注意力构成 + 低换手最后 Cell: Barber-Odean 注意力构成假说 (上涨事件占比作为慢信号,
    天然低换手 -> margin 友好) + 振幅族回填最后未测格 (excursion 比值 bf60+组内/MAX bf60)
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
FIELDS_FILE = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12",
                           "news12_fields_UNFILTERED.json")
CATEGORY = "news"
REGION = "USA"
DELAY = 1
DECAY = 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

# ---------------------------------------------------------------- 字段速记 (全部经字段清单核对存在, main_* 均 VECTOR)
BENCH = "main_session_performance_vs_benchmark"   # 相对 S&P500 会话表现
VOLR = "main_session_volume_ratio"                # 当前量/30 日均量
VOLS = "main_session_volume_stddev"               # 成交量 30 日标准分
P10 = "main_pct_change_ten_minute_post_news"      # 新闻后 10 分钟涨跌幅
P30 = "main_pct_change_thirty_minute_post_news"
P60 = "main_pct_change_sixty_minute_post_news"
P90 = "main_session_ninety_minute_change_pct"
P120 = "main_pct_change_one_twenty_minute_post_news"  # 新闻后 120 分钟涨跌幅
MCLOSE = "main_session_closing_price"
MVWAP = "main_session_volume_weighted_average_price"
MVWAPN = "main_session_vwap_from_news"
GAPP = "main_opening_gap_percent"
MRANGE = "main_session_price_range"
MRANGEZ = "main_price_range_deviation_std"

U, D = "news_max_up_amt", "news_max_dn_amt"
EOC, VWAP, TON = "news_eod_close", "news_eod_vwap", "news_ton_last"
HEX, LEX = "news_high_exc_stddev", "news_low_exc_stddev"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"
MEXCR = f"divide(subtract({HEX}, {LEX}), add({HEX}, {LEX}))"                    # MATRIX excursion 比值
VEXCMAX = f"divide(vec_max({VHEX}), add(vec_max({VHEX}), vec_max({VLEX})))"     # MAX 事件口径 (2Y 2.16)
EVCNT = f"ts_backfill(vec_count({VHEX}), 120)"
MOVECNT = f"divide(subtract({EOC}, {TON}), {EVCNT})"
# 注意力构成 (Barber-Odean): 上涨 excursion 事件占全部事件的比例
ATTMIX = f"divide(vec_count({VHEX}), add(vec_count({VHEX}), vec_count({VLEX})))"

def va(x):
    return f"vec_avg({x})"

# ---------------------------------------------------------------- 方向 V: main_* 注意力归一族
DIR_V = [
    {"id": 1, "type": "BENCH_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(BENCH)}, {va(VOLR)})))",
     "optimize_reason": (
        "相对基准表现 / 成交量激扰。机制 (成交量稀缺假说): 与已实证的事件计数归一化 (冠军 Sh1.61) "
        "互补的第二个注意力代理——单位成交量惊异下的相对基准移动才是定价不充分的异常; "
        "高成交量确认的大移动 = 充分定价 = 无回归。BENCH 剔除市场贝塔, 隔离个股事件反应。"
        "这是 main_* 族 (45 字段覆盖 1.0) 首次进入战役, 该族从未测试。")},
    {"id": 2, "type": "P10_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(P10)}, {va(VOLR)})))",
     "optimize_reason": (
        "新闻后 10 分钟涨跌幅 / 成交量激扰。机制: 10 分钟是最纯粹的价格发现窗口 (无缓冲), "
        "单位成交量惊异下的 10 分钟反应强度 = 注意力冲击的即时定价效率; 过度反应在最短窗口最强, "
        "随后衰退 (W 批直接检验衰退)。若该形态显著, 说明边缘在即时反应而非全日。")},
    {"id": 3, "type": "CLOSE_VWAP_PER_VOLSURGE", "expression": f"reverse(rank(divide(subtract({va(MCLOSE)}, {va(MVWAP)}), {va(VOLR)})))",
     "optimize_reason": (
        "收盘-VWAP 偏离 / 成交量激扰 (main_* 版收盘压力)。机制: R 批槽8 的 news_eod 版在 "
        "STATISTICAL 下 Sh1.63 (边缘非风格暴露); 本槽换 main_* 稠密口径并用成交量激扰替代事件计数, "
        "检验'尾盘抛压/关注度'假说对字段口径的稳健性。三字段全为 news12 内部 (合规)。")},
    {"id": 4, "type": "GAP_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(GAPP)}, {va(VOLR)})))",
     "optimize_reason": (
        "隔夜跳空 / 成交量激扰。机制: 跳空是盘前注意力累积的定价 (无连续交易缓冲), "
        "单位成交量惊异下的跳空 = 盘前定价效率。Q 批槽4 (跳空/事件数) 证伪 (0.52), "
        "本槽换成交量口径——若成交量版显著强于事件数版, 归因关注度代理的选择。")},
    {"id": 5, "type": "P120_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(P120)}, {va(VOLR)})))",
     "optimize_reason": (
        "新闻后 120 分钟涨跌幅 / 成交量激扰。机制: 与槽2 (10 分钟) 构成视野扫描的两端——"
        "10 分钟版测即时冲击, 120 分钟版测全日最终定价; 若两者都强且 10 分钟更强, "
        "过度反应在更短窗口; 若 120 分钟版更强, 边缘在全日尺度 (与 TO 130% 的 2 日视野互证)。")},
    {"id": 6, "type": "RANGE_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(MRANGE)}, {va(VOLR)})))",
     "optimize_reason": (
        "会话振幅 / 成交量激扰。机制: 方向中性的总活动量 (N 批槽7 振幅/事件数证伪 0.29), "
        "换成交量口径复测——振幅本身不预测方向, 但'低成交量确认的大振幅'=流动性冲击, "
        "应有均值回归。若仍证伪, 振幅族在该数据集彻底死亡。")},
    {"id": 7, "type": "CLOSE_VWAPN_PER_VOLSURGE", "expression": f"reverse(rank(divide(subtract({va(MCLOSE)}, {va(MVWAPN)}), {va(VOLR)})))",
     "optimize_reason": (
        "收盘 - 新闻时刻VWAP / 成交量激扰。机制: 与槽3 的差别是 VWAP 基准从全日 VWAP 换成"
        "新闻时刻起算的 VWAP——后者隔离'新闻后时段'的抛压, 剔除盘前既有趋势。"
        "若新闻后 VWAP 版显著强于全日 VWAP 版, 抛压是新闻驱动的 (与经济假说一致)。")},
    {"id": 8, "type": "RANGEZ_PER_VOLSURGE", "expression": f"reverse(rank(divide({va(MRANGEZ)}, {va(VOLR)})))",
     "optimize_reason": (
        "价格区间 30 日 z 分数 / 成交量激扰。机制: 异常振幅 (相对自身 30 日历史) x 成交量惊异 "
        "= '不寻常的高活动低确认'状态——两个标准化量的比值, 跨股可比性最好。"
        "若该形态是 V 批最强, 归一化层级 (原始 vs z-score) 的答案即定。")},
]

# ---------------------------------------------------------------- 方向 W: 衰退 (fade) 结构族
DIR_W = [
    {"id": 1, "type": "FADE_10V120", "expression": f"reverse(rank(subtract({va(P10)}, {va(P120)})))",
     "optimize_reason": (
        "衰退幅度 = 10 分钟涨跌幅 - 120 分钟涨跌幅, 反向。机制 (教科书级过度反应签名): "
        "若初始 10 分钟反应远超全日最终变化, 差额即当日回吐——价格发现过冲后修正。"
        "该度量自包含 (无需价格字段), 是过度反应假说最纯粹的形态; 且天然有界 (回吐 ≤ 初始反应)。"
        "若显著强于家族锚 (1.37), 说明'反应的时间结构'比'反应的不对称度'承载更强边缘。")},
    {"id": 2, "type": "FADE_RATIO_10V120", "expression": f"reverse(rank(divide({va(P10)}, {va(P120)})))",
     "optimize_reason": (
        "衰退比率 = 10 分钟 / 120 分钟涨跌幅, 反向。机制: 与槽1 的差别是比率形式 (尺度不变) vs "
        "差值形式 (保幅值)。比率 >1 = 初始反应大于全日 (回吐); 接近 1 = 无回吐; "
        "风险: 分母近零时爆表——rank 化应能抑制。两槽联合定出衰退的最优数学形式。")},
    {"id": 3, "type": "FADE_30V120", "expression": f"reverse(rank(subtract({va(P30)}, {va(P120)})))",
     "optimize_reason": (
        "30 分钟 vs 120 分钟衰退。机制: 视野扫描中段——10 分钟可能是微观结构噪声 (买卖价差反弹), "
        "30 分钟过滤掉瞬时噪声; 若 30 分钟版显著强于 10 分钟版, 回吐是真实的定价修正而非噪声。")},
    {"id": 4, "type": "FADE_60V120", "expression": f"reverse(rank(subtract({va(P60)}, {va(P120)})))",
     "optimize_reason": (
        "60 分钟 vs 120 分钟衰退。机制: 视野扫描长端——60 分钟已过主要价格发现期, "
        "若衰退在此尺度仍可测, 说明修正持续一小时以上 (与冠军 2 日视野相容)。")},
    {"id": 5, "type": "FADE_90V120", "expression": f"reverse(rank(subtract({va(P90)}, {va(P120)})))",
     "optimize_reason": (
        "90 分钟 vs 120 分钟衰退 (最短视野对照)。机制: 理论上应最弱 (90 与 120 分钟接近); "
        "本槽是扫描的对照端——若它异常地强, 说明衰退结构不是时间视野驱动的, 需重解机制。")},
    {"id": 6, "type": "FADE_10V120_PER_VOLSURGE", "expression": f"reverse(rank(divide(subtract({va(P10)}, {va(P120)}), {va(VOLR)})))",
     "optimize_reason": (
        "衰退幅度 / 成交量激扰。机制: 单位成交量惊异下的回吐 = 注意力稀缺假说在衰退结构上的应用——"
        "低成交量确认的回吐 = 流动性冲击的自我修正; 高成交量确认的回吐 = 真实信息反转 (不应回归)。"
        "若该版强于无归一版 (槽1), 两个注意力代理 (事件数/成交量) 在衰退结构上汇合。")},
    {"id": 7, "type": "FADE_10V60", "expression": f"reverse(rank(subtract({va(P10)}, {va(P60)})))",
     "optimize_reason": (
        "10 分钟 vs 60 分钟衰退 (基准窗口替换)。机制: 120 分钟窗口含收盘效应 (尾盘机构调仓), "
        "60 分钟窗口剔除之; 若 10v60 显著强于 10v120, 收盘效应污染了衰退度量, 最优窗口取 60。")},
    {"id": 8, "type": "P10_MINUS_GAP", "expression": f"reverse(rank(subtract({va(P10)}, {va(GAPP)})))",
     "optimize_reason": (
        "10 分钟反应 - 隔夜跳空。机制: 把即时反应拆成'跳空已定价部分'与'盘中新增反应部分'——"
        "后者才是新闻时刻后的新信息冲击。若该形态强于 P10 单独 (V 批槽2), "
        "说明边缘在剔除盘前定价后的净盘中反应 (更纯的事件冲击度量)。")},
]

# ---------------------------------------------------------------- 方向 X: 注意力构成 + 低换手最后 Cell
DIR_X = [
    {"id": 1, "type": "ATTMIX_RANKED", "expression": f"reverse(rank({ATTMIX}))",
     "optimize_reason": (
        "注意力构成: 上涨 excursion 事件占全部事件的比例, 反向。机制 (Barber-Odean 注意力假说): "
        "上涨事件占比高的股票吸引更多关注与买盘 -> 随后跑输; 这是注意力的'构成'而非'强度'"
        "(J 批证伪的是强度条件化)。计数类信号天然慢 (事件计数日间变化小) -> TO 可能显著低于 "
        "价格类 (margin 友好)。两字段 VHEX/VLEX 同源向量 (合规)。")},
    {"id": 2, "type": "ATTMIX_TSMEAN20", "expression": f"reverse(rank(ts_mean({ATTMIX}, 20)))",
     "optimize_reason": (
        "注意力构成 20 日平滑。机制: 单日事件占比噪声大 (可能全天仅 1-2 个事件), "
        "20 日平滑 = '过去一个月的新闻情绪构成'——更符合注意力缓慢积累的经济过程。"
        "若平滑版显著强, 注意力的时间尺度是月而非日 (TO 应同步大降, 直攻 margin 死线)。")},
    {"id": 3, "type": "ATTMIX_BF60", "expression": f"reverse(rank(ts_backfill({ATTMIX}, 60)))",
     "optimize_reason": (
        "注意力构成 60 日回填。机制: 与槽2 的差别是回填 (piecewise constant, 只在有新事件时更新) "
        "vs 平滑 (每日渐变)——回填保最新事件纯度, 平滑增样本量。两槽定出构成信号的最优时间结构。"
        "注意 ATTMIX 内层 vec_count 无 ts_ 层, 外层 backfill 作用复合量 (每字段 ≤1 层合规)。")},
    {"id": 4, "type": "ATTMIX_EXTREMITY", "expression": f"reverse(ts_rank({ATTMIX}, 250))",
     "optimize_reason": (
        "注意力构成的自身历史极端度 (250 日百分位)。机制: P 批证实异构基线对价格族有效 "
        "(MOVE_EXTREMITY Sh1.57); 本槽把同一结构应用到注意力构成——'本月新闻构成相对该股"
        "自身历史异常看多'才是注意力冲击。百分位有界持续 -> 位置仅在百分位移动时变化 (TO 友好)。")},
    {"id": 5, "type": "EXCMIX_SUM", "expression": f"reverse(rank(divide(vec_sum({VHEX}), add(vec_sum({VHEX}), vec_sum({VLEX})))))",
     "optimize_reason": (
        "excursion 幅度构成 (vec_sum 替代 vec_count)。机制: 与槽1 的差别是权重从'事件个数'换成"
        "'excursion 标准差之和'——大 excursion 事件权重更高。若 sum 版强于 count 版, "
        "注意力的构成应按幅度而非计数度量 (峰度偏好, 与 M 批 MAX 口径 2Y2.16 互证)。")},
    {"id": 6, "type": "MEXCR_BF60_IND_RANKED", "expression": f"reverse(group_rank(ts_backfill({MEXCR}, 60), industry))",
     "optimize_reason": (
        "excursion 比值 + 60 日回填 + 行业内秩化。机制: K 批冠军结构 (bf60+industry_rank, "
        "振幅族 Sh1.17) 移植到更强的 excursion 测量 (原始 Sh1.33/2Y1.67 vs 振幅 1.37/1.68 相当, "
        "但 excursion 是标准差单位更干净)。这是振幅族低换手路线的最后未测格——"
        "若 2Y 保住 1.58 且 Sh>=1.2, 即是 fail=0 家族中 2Y 达标的第一员。")},
    {"id": 7, "type": "VEXCMAX_BF60", "expression": f"reverse(ts_backfill({VEXCMAX}, 60))",
     "optimize_reason": (
        "MAX 事件口径 excursion 不对称 + 60 日回填。机制: M 批槽8 原始形态 2Y2.16 (全场第二), "
        "本槽攻其低换手形态——MAX 口径的边缘若在回填后存活 (振幅族保边 80%), "
        "则获得'2Y>=1.58 + TO<=40% + 无 CW'的组合, 是 Fit 门 (TO 地板 12.5%) 的真实候选。")},
    {"id": 8, "type": "CLOSEVWAP_CHAMP_BF60", "expression": f"reverse(ts_backfill(divide(subtract({EOC}, {VWAP}), {EVCNT}), 60))",
     "optimize_reason": (
        "收盘-VWAP 冠军 + 60 日回填。机制: R 批槽8 (Sh1.63, STATISTICAL 稳健) 的低换手形态——"
        "Q 批证明 MOVE 冠军回填后致死 (1.61->0.87), 但收盘-VWAP 压力的经济持续时间可能不同 "
        "(分布压力跨日延续 vs 瞬时移动)。本槽是两大假说 (压力持续 vs 瞬时) 的判别实验。")},
]

DIRECTIONS = {
    "V": {"name": "main_* 注意力归一族 (成交量稀缺)", "hypothesis": "单位成交量惊异 (而非事件计数) 下的相对基准移动/多视野反应才是定价不充分异常——与已实证的事件计数归一化互补的第二个注意力代理",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_V},
    "W": {"name": "衰退 (fade) 结构族", "hypothesis": "初始 10 分钟反应相对全日 (120 分钟) 最终变化的衰退幅度是教科书级过度反应签名, 承载比不对称度更强的边缘",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_W},
    "X": {"name": "注意力构成 + 低换手最后 Cell", "hypothesis": "Barber-Odean 注意力构成 (上涨事件占比, 慢信号低换手) 与振幅族回填最后未测格 (excursion 比值/MAX 口径 bf60+组内)",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_X},
}

STAGGER_SECONDS = {"V": 0, "W": 25, "X": 50}


def purge_fingerprints(exprs: list, neutralization: str, universe: str):
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
    print(f"[fingerprint purge] removed {n} records (neut={neutralization}, universe={universe})", flush=True)


def preaudit(items: list, known_fields: list):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        used = tokens & known_set
        ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_mean",
               "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore", "ts_delta",
               "trade_when", "greater", "less", "vec_avg",
               "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "industry", "subindustry",
               "sector", "market"}
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        n_fields = len(used)
        status = "OK" if audit["is_valid"] else "FAIL"
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']} fields={n_fields} {status} | {it['expression'][:80]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符 (字段名拼写错误?): {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")


def check_dup_fingerprints(items: list, neutralization: str, universe: str):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    dups = []
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        h = corrector.compute_fingerprint(fixed, REGION, universe, DELAY, neutralization)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        row = cur.fetchone()
        if row:
            dups.append((it["id"], it["expression"][:60]))
    conn.close()
    if dups:
        print(f"  [dup-check] 历史已测 {len(dups)} 条 (<=2/批合法): {dups}", flush=True)
    if len(dups) > 2:
        raise ValueError(f"批次内历史重复 {len(dups)} 条 > 2, 防摸鱼门禁将拒: {dups}")


async def submit_with_retry(batch_path: str, items: list, state_path: str, neutralization: str, universe: str):
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
                    json.dump({"location": location, "submitted_at": int(time.time()),
                               "universe": universe, "neutralization": neutralization}, f)
                print(f"[submit] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    await asyncio.sleep(60)
    poll = 0
    while True:
        poll += 1
        chk = await BrainModule.check_multi_simulation(location)
        st = chk.get("status")
        print(f"  [poll #{poll}] {st} progress={chk.get('progress', 0)}", flush=True)
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            break
        wait = 20
        if st == "RATE_LIMITED":
            wait = 60
        await asyncio.sleep(wait)
    fetch = await BrainModule.fetch_multi_simulation_result(location)
    results = fetch.get("alpha_results", [])
    if not results:
        raise RuntimeError(f"fetch 返回空 alpha_results: {str(fetch)[:300]}")
    return results


def build_summary(items: list, results: list, direction: str):
    rows = []
    for idx, (it, r) in enumerate(zip(items, results)):
        m = r.get("metrics") or r.get("is") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret = m.get("returns") or 0
        to = m.get("turnover") or 0
        row = {
            "slot": it["id"], "type": it["question_type"], "expression": it["expression"],
            "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": to, "returns": ret,
            "ret_over_to": (ret / to) if to else None,
            "drawdown": m.get("drawdown"), "margin_bps": (m.get("margin") or 0) * 10000,
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "sub_sharpe": m.get("sub_universe_sharpe"), "two_year_sharpe": m.get("two_year_sharpe"),
            "inv_sharpe": m.get("investability_sharpe"), "rn_sharpe": m.get("risk_neutralized_sharpe"),
            "ra_failed": ra.get("ra_failed"), "ra_failed_checks": ra.get("ra_failed_checks"),
            "fail_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("fail") or [])],
            "warning_checks": [c.get("name") if isinstance(c, dict) else c for c in (checks.get("warning") or [])],
        }
        rows.append(row)
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    d = DIRECTIONS[direction]
    summary = {
        "direction": direction, "direction_name": d["name"],
        "hypothesis": d["hypothesis"],
        "settings": {"neutralization": d["neutralization"], "universe": d["universe"],
                     "decay": DECAY, "truncation": TRUNCATION,
                     "region": REGION, "delay": DELAY, "nan_handling": NAN_HANDLING},
        "rows": rows,
        "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                 "step2": step2, "final": final},
    }
    return summary


def print_table(summary: dict):
    s = summary["settings"]
    print(f"\n===== Gate1-Wave6 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
    print(f"{'槽':>2} {'类型':<26} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'Mgn':>6} {'DD%':>6} {'2Y':>6} {'sub':>5} {'rnSh':>5} {'L/S':>9} {'fail':<24} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:26]:<26} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:24]:<24} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)
    valid = [r for r in summary["rows"] if (r["longCount"] or 0) > 20 and r["ret_over_to"]]
    if valid:
        best = max(valid, key=lambda r: r["sharpe"] or -99)
        print(f"[margin 前沿] 最佳 Sh 槽{best['slot']} {best['type']}: Ret/TO={best['ret_over_to']:.4f} "
              f"(margin 死线需 0.5, 差距 {0.5/best['ret_over_to']:.1f}x)", flush=True)


async def main():
    direction = sys.argv[1].strip().upper()
    if direction not in DIRECTIONS:
        print(f"用法: python phase10_gate1_wave6.py <V|W|X>"); sys.exit(1)
    d = DIRECTIONS[direction]
    universe, neutralization = d["universe"], d["neutralization"]
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Wave6-{direction}] {d['name']} | 假说: {d['hypothesis']}", flush=True)
    print(f"[Wave6-{direction}] 设置: universe={universe} neut={neutralization} decay={DECAY} trunc={TRUNCATION}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave6-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W6_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, neutralization, universe)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate6_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate6_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W6_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave6-{direction}] 批次文件: {batch_path}", flush=True)

    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, universe, DELAY, neutralization)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W6_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path, neutralization, universe)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], neutralization, universe)
        print(f"[Wave6-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave6-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate6_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave6-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
