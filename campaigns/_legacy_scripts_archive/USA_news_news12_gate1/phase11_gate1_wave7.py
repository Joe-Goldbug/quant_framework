# -*- coding: utf-8 -*-
"""Gate1 Wave7 多 agent 优化驱动 (2026-10-24 深夜).

Wave6 判决 (24 槽) + 相关性终检 + 红队盲审后的继续战役 (用户新 mandate: 以 N1eGk79E 为锚,
攻其 4 FAIL: Fit0.31 / TO116.88% / CW / 2Y0.58; 零 fail 零警告; 每批 8 条; 禁提交).

N1eGk79E = reverse(rank(divide(subtract(news_eod_close,news_eod_vwap),
           ts_backfill(vec_count(high_price_excursion_stddev),120))))
  Sh1.63 / Fit0.31 / TO116.88% / CW / 2Y0.58 / PC0.5589 / SC0.1521 (唯一相关双过)
  红队判决 (双候选): INCOMPLETE_SIGNAL, 断点=催化剂 (AST 无动态触发/分子分母频率错配/回填分母陈旧)

Wave7 三路 (每路 8 槽, 蓝队三子 agent 并行设计 + 主编基于战役知识修正):
  Y 每关注度振幅 x 回填: 三个已验证成分的首次合成 —— 计数归一化 (Sh 提升器 0.81->1.61)
    x bf60 回填 (TO/CW 杀手 130%->37%) x 振幅/excursion 字段 (2Y 稳定 1.67-2.16).
    假说: 单位新闻关注度承载的振幅 = 关注度稀缺下的流动性冲击 -> 回归.
  W 2Y 修复与权重工程: N1eGk79E 的 2Y0.58 vs d5K6wxlx 的 2Y2.09 -> 尾盘压力可能是近半期
    政权依赖; ts_rank 极端度是已验证 2Y 修复器 (2Y 2.09->2.16); 新分子字段
    (eod_high/low, open, ton_high 从未测试); group_zscore 攻 CW.
  Z 事件新近性门控 (回应红队催化剂断点的判别实验): 已验证低换手基座 (YPxOGboo 结构,
    TO37.5%/R-TO0.098/fail 桶空/PC0.671) 加 days_from_last_change 新近门控 N=1/2/5/10
    —— R/TO 随信号新鲜度的曲线从未测绘; 若中间新鲜度抬 R/TO, 即攻 Margin 墙唯一未测路径.
    另含 ts_delta 动态催化剂 x2 + 数据质量门控 (count>=2/>=3) x2.
    注意: close-vwap 族 bf60 已实证致死 (Sh0.11/2Y-0.52, Wave6-X 槽8), 故门控基座选振幅族.
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
FIELDS_FILE = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1",
                           "news12_fields_full.json")
CATEGORY = "news"
REGION = "USA"
DELAY = 1
DECAY = 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

# ---------------------------------------------------------------- 字段速记 (全部经 867 字段清单核对)
EOC, VWAP, TON = "news_eod_close", "news_eod_vwap", "news_ton_last"
EOH, EOL, OPEN, TH = "news_eod_high", "news_eod_low", "news_open", "news_ton_high"
U, D = "news_max_up_amt", "news_max_dn_amt"
HEX, LEX = "news_high_exc_stddev", "news_low_exc_stddev"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"
CNT = f"add(vec_count({VHEX}), 1)"                       # 防除零的事件计数分母
CNTL = f"add(vec_count({VLEX}), 1)"
DFLC = f"days_from_last_change(vec_count({VHEX}))"       # 距上次事件计数变化的天数 (催化剂)

# 已验证低换手基座 (= YPxOGboo 原式, TO37.8%/R-TO0.098/fail桶空/PC0.671)
BASE_BF60_ASYM = (f"reverse(group_rank(ts_backfill(divide({U}, add({U}, {D})), 60), industry))")

DIR_Y = [
    {"id": 1, "type": "VECAVG_AMP_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide(vec_avg({VHEX}), {CNTL}), 60), industry))",
     "optimize_reason": (
        "vec_avg 口径 excursion 振幅 / 低侧事件计数 + bf60 + 行业内秩。机制 (关注度稀缺): "
        "单位新闻关注度承载的 excursion 振幅越大, 该移动越是关注度稀缺下的流动性冲击, 随后回归; "
        "关注度充足时同幅移动是信息有效定价。三个已验证成分的首次合成: 计数归一化 (Sh 0.81->1.61) "
        "x bf60 (TO 130%->37%, 消 CW) x 振幅字段 (2Y 1.67-2.16)。高低侧事件计数同源 (同一新闻"
        "产生两侧 excursion), 作分母近似总关注度。")},
    {"id": 2, "type": "MAXUP_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide({U}, {CNT}), 60), industry))",
     "optimize_reason": (
        "新闻后最大涨幅 / 事件计数 + bf60 + 组内秩。机制: 单位关注度下的最大向上 excursion = "
        "注意力稀缺型冲击的峰值度量 (比均值口径对极端事件更敏感, M 批 MAX 口径 2Y2.16 互证)。"
        "reverse = 做多'每单位关注度涨幅小'的股票。两字段 (U + VHEX) 合规。")},
    {"id": 3, "type": "VECMAX_AMP_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide(vec_max({VHEX}), {CNTL}), 60), industry))",
     "optimize_reason": (
        "vec_max 口径 excursion 振幅 / 低侧计数 + bf60。与槽1 构成 avg vs max 的干净 A/B: "
        "若 max 版显著强于 avg 版, 关注度稀缺性应由峰值而非均值度量 (峰度偏好); "
        "若 avg 更强, 稀缺性是全日平均属性。单变量对照, 直接定口径。")},
    {"id": 4, "type": "EXCDIFF_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide(subtract({HEX}, {LEX}), {CNT}), 60), industry))",
     "optimize_reason": (
        "高低 excursion 标准差差 / 事件计数 + bf60。机制: 上侧 excursion 相对下侧的强度, "
        "按关注度归一 = 单位注意力下的上行情景不充分定价; 上偏越大越可能回归 (与种子族 ASYM "
        "同向但用 excursion 度量, N 批原始 Sh1.33/2Y1.67 已验证该口径)。三字段合规。")},
    {"id": 5, "type": "CVW_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide(subtract({EOC}, {VWAP}), {CNT}), 60), industry))",
     "optimize_reason": (
        "收盘-VWAP 每关注度 + bf60 + 组内秩 (锚定候选的低换手形态)。Wave6-X 槽8 已证 bf60 杀 "
        "close-vwap 族 (Sh0.11/2Y-0.52), 本槽换 add(·,1) 分母 + 组内秩复测——若仍死, "
        "则确认尾盘压力边缘严格瞬态 (与 Q 批结论合并); 若活, 则组内秩+eps 分母救了它。"
        "对照实验, 两种结果都归档。")},
    {"id": 6, "type": "VECAVG_AMP_PER_CNT_BF250", "expression":
        f"reverse(group_rank(ts_backfill(divide(vec_avg({VHEX}), {CNTL}), 250), industry))",
     "optimize_reason": (
        "槽1 的长回填版 (bf60->bf250)。机制: 与槽1 构成回填长度 A/B。K 批证实 ASYM 族 TO 在 "
        "37% 饱和 (bf60/120/250 同值), 但每关注度口径的计数分母每日可变, 长回填可能进一步"
        "降 TO 且保 2Y。若 bf250 版 Sh/2Y 不塌而 TO 更低, 即 Margin 墙的最近接点。")},
    {"id": 7, "type": "EXC_PER_CNT_TSRANK250", "expression":
        f"reverse(group_rank(ts_rank(divide({HEX}, {CNT}), 250), industry))",
     "optimize_reason": (
        "MATRIX 上偏 excursion / 计数 的 250 日自身极端度 + 组内秩。机制: P 批证实 ts_rank "
        "极端度对价格族有效 (2Y 2.09->2.16 且 Sh 仅 -0.04); 本槽把极端度变换应用到每关注度"
        "口径——'相对该股自身历史异常的振幅稀缺度'才可交易, 过滤政权变化 (攻 2Y)。"
        "ts_rank 有界持续 -> 位置仅在百分位移动时变化 (TO 友好)。")},
    {"id": 8, "type": "EODRANGE_PER_CNT_BF60", "expression":
        f"reverse(group_rank(ts_backfill(divide(subtract({EOH}, {EOL}), {CNT}), 60), industry))",
     "optimize_reason": (
        "全日高低价差 / 事件计数 + bf60 (未测新分子 eod_high/eod_low)。机制: 方向中性的全日"
        "活动量按关注度归一 = 单位注意力下的流动性冲击总强度; 高冲击低关注 -> 随后波动率与"
        "收益回归 (Bali-Cakici-Whitelaw 特质波动异象的注意力稀缺版)。与 W 批槽5 (无回填"
        "plain rank) 构成包装 A/B。")},
]

DIR_W = [
    {"id": 1, "type": "CVW_PER_CNT_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {VWAP}), {CNT}), 250))",
     "optimize_reason": (
        "锚定候选的 250 日自身极端度版 (2Y 修复主假说)。机制: N1eGk79E 的 2Y0.58 说明尾盘压力"
        "边缘近半期崩塌, 而 ts_rank 极端度在家族另一支 (d5K6wxlx->YPxOX1QA) 把 2Y 从 2.09 "
        "修到 2.16——自身历史百分位过滤政权变化, 只交易'相对该股自身异常的尾盘压力'。"
        "若 2Y 回到 1.58 且 Sh 保持 1.5+, 即 4 FAIL 中 2Y 项的首解。")},
    {"id": 2, "type": "CVW_PER_CNT_TSRANK120", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {VWAP}), {CNT}), 120))",
     "optimize_reason": (
        "同槽1 但 120 日窗口。机制: 与 250/500 构成窗口扫描——极端度的回看窗口决定'自身历史"
        "异常'的尺度; 120 日对机制政权变化更敏感 (半年度适应), 500 日更钝。三槽定出 2Y 修复"
        "的最优时间尺度, 且 ts_rank 天然比原始日频信号慢 (TO 应下降, 攻 Fit)。")},
    {"id": 3, "type": "CVW_PER_CNT_TSRANK500", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {VWAP}), {CNT}), 500))",
     "optimize_reason": (
        "同槽1 但 500 日窗口 (约两年)。机制: 最长回看 = 最钝的自身基线, 对近半期政权变化最鲁棒;"
        "若 2Y 随窗口拉长单调改善, 证明尾盘压力边缘的衰减是快基线相对慢基子的伪信号; "
        "若 500 日版 Sh 崩塌, 说明边缘依赖中频自身历史。窗口扫描的第三点定曲线形状。")},
    {"id": 4, "type": "CTN_PER_CNT_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 250))",
     "optimize_reason": (
        "全日位移 (close-ton_last) 每关注度的 250 日极端度。机制: 家族两个最优成分的合成——"
        "全日位移口径 (d5K6wxlx, 2Y 2.09, 边缘稳定非政权依赖) x ts_rank250 极端度 (2Y 修复器)。"
        "若该槽 Sh>=1.5 且 2Y>=1.58 且 PC<0.70, 即是本战役最接近全门达标的候选: "
        "它同时绕开尾盘压力的政权依赖与原始口径的 TO 问题 (极端度降换手)。")},
    {"id": 5, "type": "EODRANGE_PER_CNT_RANK", "expression":
        f"reverse(rank(divide(subtract({EOH}, {EOL}), {CNT})))",
     "optimize_reason": (
        "全日高低价差每关注度, plain rank 无包装 (对照臂)。机制: 单位注意力下的全日流动性冲击"
        "总强度 (特质波动异象的注意力稀缺版); 与 Y 批槽8 (同分子 + bf60 + 组内秩) 构成包装"
        "A/B——定出该分子在原始/回填两形态的边缘留存, 分离分子效应与包装效应。"
        "新分子 eod_high/eod_low 从未测试。")},
    {"id": 6, "type": "COPEN_PER_CNT_RANK", "expression":
        f"reverse(rank(divide(subtract({EOC}, {OPEN}), {CNT})))",
     "optimize_reason": (
        "开收盘位移每关注度, plain rank。机制: 隔夜+日内的总位移按关注度归一 = 单位注意力下的"
        "全日重定价幅度; 大幅重定价低关注 -> 关注度稀缺型过度反应 -> 回归。与 close-vwap (尾盘)"
        "和 close-ton_last (新闻后) 构成三个时间视野的分子对照, 定位边缘的时间结构。"
        "news_open 字段从未测试。")},
    {"id": 7, "type": "CVW_PER_CNT_IND_ZSCORE", "expression":
        f"reverse(group_zscore(divide(subtract({EOC}, {VWAP}), {CNT}), industry))",
     "optimize_reason": (
        "收盘-VWAP 每关注度的组内 z 分数 (攻 CONCENTRATED_WEIGHT)。机制: rank 把信号压成均匀"
        "分位, 权重集中来自信号本身的截面尖峰; group_zscore 保留组内幅度信息并按行业标准化, "
        "极端值被压缩 -> 权重更分散。若 CW 消除且 Sh 保持, 即得'消 CW 不杀边'的包装; "
        "组内化同时攻 MATCHES_THEMES (行业均值 shuffle)。")},
    {"id": 8, "type": "CTH_PER_CNT_TSRANK250_IND", "expression":
        f"reverse(group_rank(ts_rank(divide(subtract({EOC}, {TH}), {CNT}), 250), industry))",
     "optimize_reason": (
        "收盘相对新闻时刻最高价的位移每关注度 + 250 日极端度 + 组内秩 (全栈合成)。机制: "
        "close-ton_high = 新闻后价格相对当日峰值的回撤 (收盘走弱签名); 按关注度归一后取自身"
        "极端度, 只交易'相对该股历史异常的峰值回撤稀缺度'; 组内秩消 MATCHES_THEMES 并分散权重。"
        "三个已验证杠杆 (极端度/组内/每关注度) 与未测分子 (ton_high) 的合成, 攻 2Y+CW+警告项。")},
]

DIR_Z = [
    {"id": 1, "type": "EVT_GATE_1D", "expression":
        f"trade_when(less({DFLC}, 1), {BASE_BF60_ASYM}, -1)",
     "optimize_reason": (
        "事件新近性门控 N=1 (仅事件当日持仓) x 已验证低换手基座 (TO37.8%/R-TO0.098/PC0.671)。"
        "机制 (催化剂显式化, 回应红队 INCOMPLETE_SIGNAL): 关注度稀缺错价只存在于事件当日, "
        "过期的事件信息已被套利——门控把 60 日回填的陈旧仓位砍到当日, 若每笔 IC 随新鲜度上升, "
        "R/TO 应显著高于 0.098 (攻 Margin 墙唯一未测路径); 若边缘塌方, 则证明边缘依赖陈旧"
        "回填的连续性 (宽横截面现象)。判别实验, 两种结果都定论。")},
    {"id": 2, "type": "EVT_GATE_2D", "expression":
        f"trade_when(less({DFLC}, 2), {BASE_BF60_ASYM}, -1)",
     "optimize_reason": (
        "事件新近性门控 N=2。机制: 与 N=1/5/10 构成半衰期扫描——若 R/TO 在 N=2-5 达峰后下降, "
        "即测得事件边缘的时间半衰期 (过度反应的消退速度), 这是注意力稀缺假说的核心参数; "
        "若 N=1 已杀边而 N=5 保边, 说明错价需要隔夜的信息扩散时间 (与慢信息扩散理论一致)。")},
    {"id": 3, "type": "EVT_GATE_5D", "expression":
        f"trade_when(less({DFLC}, 5), {BASE_BF60_ASYM}, -1)",
     "optimize_reason": (
        "事件新近性门控 N=5 (一周)。机制: 扫描中点——若边缘在 5 日窗口内存活且 R/TO 高于基座, "
        "得'事件后一周内可收割'的可交易事件策略 (TO 应低于原始 130% 而高于基座 37%, "
        "落在 Margin 友好区); 若与基座同值, 门控空转 (证明回填 60 日内无陈旧损益差)。")},
    {"id": 4, "type": "EVT_GATE_10D", "expression":
        f"trade_when(less({DFLC}, 10), {BASE_BF60_ASYM}, -1)",
     "optimize_reason": (
        "事件新近性门控 N=10 (两周)。机制: 扫描上端——若 N=10 与基座 (bf60) 几乎同值, 说明"
        "10 日后的陈旧仓位不贡献边际损益, 回填可安全缩短 (TO 不变而信号更纯); 若 N=10 显著"
        "弱于 N=5, 边缘半衰期约一周, 与注意力衰减的实证文献 (投资者关注半衰期 3-10 日) 互证。")},
    {"id": 5, "type": "ATTN_DRIFT_5D", "expression":
        f"reverse(rank(ts_delta(divide(subtract({EOC}, {VWAP}), {CNT}), 5)))",
     "optimize_reason": (
        "尾盘压力每关注度的 5 日变化 (动态催化剂)。机制 (回应红队'公式只是逐日排名, 无动态"
        "触发'): 边际事件冲击 = 今日相对 5 日前的位移稀缺度跳变; 跳变为正 = 新的关注度稀缺"
        "冲击正在发生 (催化剂), 而非陈旧水平的持续。ts_delta 提供显式时序动态, 若该形态"
        "Sh/2Y 达标, 即补上四段式逻辑链缺失的催化剂段。")},
    {"id": 6, "type": "TON_DRIFT_5D", "expression":
        f"reverse(rank(ts_delta(divide(subtract({EOC}, {TON}), {CNT}), 5)))",
     "optimize_reason": (
        "全日位移每关注度的 5 日变化 (槽5 的全日口径对照)。机制: 与槽5 分离'尾盘压力跳变'与"
        "'全日位移跳变'两个动态催化剂——全日口径的边缘更稳 (d5K6wxlx 2Y2.09), 若 drift 版"
        "在全日口径显著, 动态催化剂假说成立且找到了稳定载体; 若仅尾盘口径显著, 催化剂是"
        "尾盘特有的 (收盘拍卖流的变化)。")},
    {"id": 7, "type": "COUNT_GE2", "expression":
        f"trade_when(greater(vec_count({VHEX}), 1), reverse(rank(divide(subtract({EOC}, {VWAP}), {CNT}))), -1)",
     "optimize_reason": (
        "数据质量门控: 仅当日 >=2 个新闻事件时持仓。机制: 单事件日的计数分母=1, '每关注度'"
        "归一退化为裸位移且噪声最大; >=2 事件才有真实的关注度密度度量 (分母的边际信息量)。"
        "与既往证伪的内生门控 (信号自身极端度) 不同——这是字段驱动的数据存在性过滤, 若边缘"
        "存活且 TO/CW 下降, 即得干净的低噪声子样本策略。")},
    {"id": 8, "type": "COUNT_GE3", "expression":
        f"trade_when(greater(vec_count({VHEX}), 2), reverse(rank(divide(subtract({EOC}, {VWAP}), {CNT}))), -1)",
     "optimize_reason": (
        "数据质量门控 >=3 事件 (槽7 的收紧版)。机制: 与槽7 构成门槛扫描 (1/2/3)——若边缘随"
        "门槛提高而增强 (Sh 升/CW 降), 关注度稀缺假说在最稠密事件日最强 (分母度量最可靠); "
        "若杀边, 单事件日的裸位移已承载全部边缘 (归一的边际价值在稀疏日)。门槛扫描定出"
        "关注度密度的最优度量区间。")},
]

DIRECTIONS = {
    "Y": {"name": "每关注度振幅 x 回填 (三成分首合成)", "hypothesis":
           "单位新闻关注度承载的 excursion 振幅 = 关注度稀缺下的流动性冲击, 随后回归; "
           "计数归一化 (Sh 提升器) x bf60 (TO/CW 杀手) x 振幅字段 (2Y 稳定) 三成分首次合成",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_Y},
    "W": {"name": "2Y 修复与权重工程", "hypothesis":
           "尾盘压力边缘的近半期崩塌是政权依赖, ts_rank 自身极端度过滤政权变化修复 2Y; "
           "新分子字段 (eod_high/low/open/ton_high) 与组内 z 分数 (消 CW) 从未测试",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_W},
    "Z": {"name": "事件新近性门控 + 动态催化剂 (红队催化剂断点判别实验)", "hypothesis":
           "关注度稀缺错价只存在于事件后有限窗口; 新近门控扫描 (N=1/2/5/10) 测绘 R/TO 随信号"
           "新鲜度的曲线——若中间新鲜度抬 R/TO, 即攻 Margin 墙唯一未测路径; ts_delta 动态"
           "催化剂补四段式逻辑链缺失段; count>=2/3 数据质量门控降噪",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_Z},
}

STAGGER_SECONDS = {"Y": 0, "W": 25, "Z": 50}


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
        ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
               "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
               "ts_delta", "ts_decay_linear", "trade_when", "greater", "less", "vec_avg",
               "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "days_from_last_change",
               "industry", "subindustry", "sector", "market"}
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        n_fields = len(used)
        status = "OK" if audit["is_valid"] else "FAIL"
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']} fields={n_fields} "
              f"len={len(it['expression'])} {status} | {it['expression'][:80]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符 (字段名拼写错误?): {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")
        if audit["operator_count"] > 10:
            raise ValueError(f"slot{it['id']} 算子数 {audit['operator_count']} > 10")
        if len(it["expression"]) > 857:
            raise ValueError(f"slot{it['id']} 表达式超长 {len(it['expression'])} > 857")


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
                    json.dump({"location": location, "submitted_at": int(time.time()),
                               "universe": universe, "neutralization": neutralization}, f)
                print(f"[submit-{tag}] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit-{tag}] attempt {attempt} failed: {str(e)[:200]}", flush=True)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    return location


async def poll_one(location: str, tag: str):
    poll = 0
    while True:
        poll += 1
        chk = await BrainModule.check_multi_simulation(location)
        st = chk.get("status")
        print(f"  [poll-{tag} #{poll}] {st} progress={chk.get('progress', 0)}", flush=True)
        if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            return st
        wait = 60 if st == "RATE_LIMITED" else 20
        await asyncio.sleep(wait)


def build_summary(items: list, results: list, direction: str):
    rows = []
    for it, r in zip(items, results):
        m = r.get("metrics") or r.get("is") or {}
        ra = r.get("ra") or {}
        checks = r.get("checks") or {}
        ret = m.get("returns") or 0
        to = m.get("turnover") or 0
        rows.append({
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
        })
    step1 = Gatekeeper.audit_step1_batch({"alpha_results": results})
    step2 = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=REGION)
    final = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=REGION)
    d = DIRECTIONS[direction]
    return {
        "direction": direction, "direction_name": d["name"],
        "hypothesis": d["hypothesis"],
        "settings": {"neutralization": d["neutralization"], "universe": d["universe"],
                     "decay": DECAY, "truncation": TRUNCATION,
                     "region": REGION, "delay": DELAY, "nan_handling": NAN_HANDLING},
        "rows": rows,
        "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                 "step2": step2, "final": final},
    }


def print_table(summary: dict):
    s = summary["settings"]
    print(f"\n===== Gate1-Wave7 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
    print(f"{'槽':>2} {'类型':<28} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'Mgn':>6} {'DD%':>6} {'2Y':>6} {'sub':>5} {'rnSh':>5} {'L/S':>9} {'fail':<26} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:28]:<28} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:26]:<26} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)
    valid = [r for r in summary["rows"] if (r["longCount"] or 0) > 20 and r["ret_over_to"]]
    if valid:
        best = max(valid, key=lambda r: r["sharpe"] or -99)
        print(f"[margin 前沿] 最佳 Sh 槽{best['slot']} {best['type']}: Ret/TO={best['ret_over_to']:.4f} "
              f"(margin 死线需 0.5, 差距 {0.5/best['ret_over_to']:.1f}x)", flush=True)


async def main():
    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave7] 字段字典 {len(known_fields)} 个装载", flush=True)

    plans = []
    for direction in ["Y", "W", "Z"]:
        d = DIRECTIONS[direction]
        items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
                  "seed_id": f"GATE1W7_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
        assert len(items) == 8, f"{direction} 批必须 8 槽"
        print(f"\n[Wave7-{direction}] {d['name']}", flush=True)
        print(f"[Wave7-{direction}] 假说: {d['hypothesis']}", flush=True)
        preaudit(items, known_fields)
        check_dup_fingerprints(items, d["neutralization"], d["universe"])
        plans.append((direction, d, items))

    ts = int(time.time())
    locations = {}
    for direction, d, items in plans:
        await asyncio.sleep(STAGGER_SECONDS[direction])
        batch_path = os.path.join(CAMPAIGN, f"batch_gate7_{direction}_{ts}.json")
        state_path = os.path.join(CAMPAIGN, f"state_gate7_{direction}.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W7_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                      f, ensure_ascii=False, indent=1)
        corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION,
                                                           d["universe"], DELAY, d["neutralization"])
        for it, ce in zip(items, corrected):
            it["expression"] = ce
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W7_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                      f, ensure_ascii=False, indent=1)
        print(f"[Wave7-{direction}] 批次文件: {batch_path}", flush=True)
        try:
            loc = await submit_batch(items, state_path, d["neutralization"], d["universe"], direction)
            locations[direction] = loc
        except Exception as e:
            purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
            print(f"[Wave7-{direction}] FATAL submit: {e}", flush=True)
            raise

    # 轮询三批
    done = {}
    while len(done) < len(locations):
        for direction, loc in list(locations.items()):
            if direction in done:
                continue
            try:
                chk = await BrainModule.check_multi_simulation(loc)
                st = chk.get("status")
                print(f"  [poll-{direction}] {st} progress={chk.get('progress', 0)}", flush=True)
                if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                    done[direction] = st
            except Exception as e:
                print(f"  [poll-{direction}] error: {str(e)[:150]}", flush=True)
            await asyncio.sleep(5)
        await asyncio.sleep(20)

    for direction, d, items in plans:
        loc = locations[direction]
        fetch = await BrainModule.fetch_multi_simulation_result(loc)
        results = fetch.get("alpha_results", [])
        if not results:
            print(f"[Wave7-{direction}] fetch 空! {str(fetch)[:300]}", flush=True)
            continue
        batch_path = os.path.join(CAMPAIGN, f"batch_gate7_{direction}_{ts}_result.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
        print(f"[Wave7-{direction}] 结果已存: {batch_path}", flush=True)
        summary = build_summary(items, results, direction)
        sum_path = os.path.join(CAMPAIGN, f"summary_gate7_{direction}.json")
        with open(sum_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
        print_table(summary)
        print(f"[Wave7-{direction}] 汇总已存: {sum_path}", flush=True)

    print("\n[Wave7] 三批全部回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
