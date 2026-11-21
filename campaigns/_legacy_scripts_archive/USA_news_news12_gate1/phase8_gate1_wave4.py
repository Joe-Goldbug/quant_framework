# -*- coding: utf-8 -*-
"""Gate1 Wave4 多 agent 优化驱动 (2026-10-24).

Wave3 判决 (32 槽):
  I 速度不对称 -> 证伪 (Step1 熔断: 最高 |Sh| 0.22; mins_* 字段日持仓仅 3-14 只, 结构稀疏不可交易)
  J 条件化门控 -> 证伪 (7 门控全塌: Sh 1.37->0.20-0.54; TO 虽降 4-6 倍但边缘塌更快;
     扁平/粘性退出完全同值 -> 门控条件近似静态; 注意力条件化双重证伪)
  K 解耦模板 -> 证伪 (DECOUPLE 0.71/-0.75 < 1.37; 行业广播 0.14; ATR 缩放 0.16)
     但回填族精炼: bf60+industry_rank Sh1.17/sub0.90/DD2.9% 且 **消除 MATCHES_THEMES** (只剩 CLUSTER_TEST);
     bf120/250 证实 TO 在 37% 饱和 (排名随他股事件日 shuffle, 与回填长度无关)
  L VECTOR 探针 -> 族证伪但两大发现:
     🔴 VEC_EXC_RATIO ( excursion stddev 上行/总和 ) Sh1.13/2Y**1.86** (全场 2Y 最强) /sub0.76/DD7.4%
     VEC 聚合口径优于 MATRIX 单事件 (1.13 vs 0.86) -> 聚合即稳健

家族前沿 (Sh, Ret/TO, 2Y, sub): 锚 (1.37, 0.051, 1.68, 1.00) / bf60_ind_rank (1.17, 0.098, 0.68, 0.90)
                                / VEC_EXC_RATIO (1.13, 0.040, 1.86, 0.76)
门禁一致解集: {Sh>=1.58, Ret>=0.5*TO, TO in [5,50], 2Y>=1.58, Sub>=1.58}

Wave4 三路 (每路 8 槽):
  M Excursion 族深化: 唯一 2Y 强者 (1.86) 的全形态扫描 (回填/秩化/组内/MAX 事件/ATR 归一/1555 口径)
  N 价格路径不对称 + 计数归一化: MATRIX excursion 比值形式 (未测) + 日内路径上下行份额
     + news102 跨族计数归一化模板 (价格移动/事件数, 注意力稀缺假说) + 不对称x跳空交互
  O MARKET 中性化 TO 力学攻击: 中性化是唯一合法 settings 消融轴; MARKET 剔除行业均值日度 shuffle
     -> 若权重仅在个股自身信号变化时变动, TO 应结构性下降 (攻 margin 死线的最后合法杠杆)
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

# ---------------------------------------------------------------- 字段速记 (全部经字段清单核对存在)
U, D = "news_max_up_amt", "news_max_dn_amt"
EOC, EODH, EODL, TON = "news_eod_close", "news_eod_high", "news_eod_low", "news_ton_last"
GAP = "news_open_gap"
HEX, LEX = "news_high_exc_stddev", "news_low_exc_stddev"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"
VHD1555, VLD1555 = "high_price_deviation_std_1555", "low_price_deviation_std_1555"
VATR = "average_true_range_14d"

CTRL = f"reverse(divide({U}, add({U}, {D})))"
ARAW = f"divide({U}, add({U}, {D}))"
BF = f"ts_backfill({ARAW}, 60)"
VEXCR = f"divide(vec_avg({VHEX}), add(vec_avg({VHEX}), vec_avg({VLEX})))"       # VECTOR excursion 比值 (2Y 1.86)
MEXCR = f"divide(subtract({HEX}, {LEX}), add({HEX}, {LEX}))"                    # MATRIX excursion 比值 (未测形式)
PATH_UP = f"subtract({EODH}, {TON})"
PATH_DN = f"subtract({TON}, {EODL})"
MOVE = f"subtract({EOC}, {TON})"                                                # 新闻时刻->收盘的价格移动
EVCNT = f"ts_backfill(vec_count({VHEX}), 120)"                                  # 120 日回填的事件计数

# ---------------------------------------------------------------- 方向 M: Excursion 族深化
DIR_M = [
    {"id": 1, "type": "VEC_EXC_RATIO_BF60", "expression": f"reverse(ts_backfill({VEXCR}, 60))",
     "optimize_reason": (
        "VECTOR excursion 比值 + 60 日回填。机制: L 批槽4 该族 2Y=1.86 为全场最强 (时间稳定性远超"
        "振幅族的 1.68), 但 TO 118.7% 且 Sh1.13; E/K 批已证回填是家族唯一保边降换手结构"
        "(保边 80%, TO 130%->37%)。本槽是 2Y 最强测量 x 唯一有效降换手结构的交汇——"
        "若 2Y 在回填后仍 >=1.58 (振幅族回填后 2Y 塌到 0.6, 但 excursion 族时间稳定性可能不同), "
        "同时 Sh 保留 >=0.9, 则家族首次出现 2Y/Sh/sub 三项同时接近门禁的结构。")},
    {"id": 2, "type": "VEC_EXC_RATIO_RANKED", "expression": f"reverse(rank({VEXCR}))",
     "optimize_reason": (
        "VECTOR excursion 比值 + 全横截面秩化。机制: K 批槽3/4 证实 rank/group_rank 包装可消除 "
        "MATCHES_THEMES 警告 (零警告目标的必要条件); 本槽把同一包装应用到 excursion 族, "
        "测量秩化对 Sh/TO 的净影响 (若 Sh 不降而警告消除, 是免费的合规改善)。")},
    {"id": 3, "type": "VEC_EXC_RATIO_IND_RANKED", "expression": f"reverse(group_rank({VEXCR}, industry))",
     "optimize_reason": (
        "VECTOR excursion 比值 + 行业内秩化。机制: 同槽2 的组内版; K 批槽4 (bf60+industry_rank) "
        "是全家族新最优 (Sh1.17/sub0.90/DD2.9%/无 MATCHES_THEMES), 行业内排序同时攻 sub-sharpe "
        "(剔除行业事件潮) 与警告项。本槽把该结构移植到 2Y 更强的 excursion 测量。")},
    {"id": 4, "type": "VEC_EXC_RATIO_ATR_SCALED", "expression": f"reverse(divide({VEXCR}, vec_avg({VATR})))",
     "optimize_reason": (
        "VECTOR excursion 比值 / 14 日 ATR。机制: 不对称度经波动率归一后 = '经波动调整的过度反应'。"
        "K 批槽8 对回填振幅族做过 ATR 缩放 (0.16 证伪), 但 excursion 族本身已是标准差单位, "
        "再除 ATR 是双重归一——本槽检验该族是否需要波动调整, 与 K8 形成'族 x 归一' 2x2 消融的一角。")},
    {"id": 5, "type": "VEC_EXC_1555_BF60", "expression": f"reverse(ts_backfill(divide(vec_avg({VHD1555}), add(vec_avg({VHD1555}), vec_avg({VLD1555}))), 60))",
     "optimize_reason": (
        "1555 收盘聚合口径 excursion 比值 + 回填。机制: L 批三种聚合口径 (excursion 1.13 / deviation1555 0.83) "
        "中 excursion 口径最强; 本槽把 1555 口径也回填化, 与槽1 构成口径 x 回填消融——"
        "若两口径回填后都保 2Y, 该边缘对聚合口径稳健; 若分歧, 归因到口径差异。")},
    {"id": 6, "type": "VEC_EXC_PURE_OVER_ATR", "expression": f"reverse(divide(divide(vec_avg({VHEX}), vec_avg({VLEX})), vec_avg({VATR})))",
     "optimize_reason": (
        "纯上行/下行 excursion 比 (无 add 归一) / ATR。机制: 与槽1 的差别是数学形式——"
        "纯比值 U/D 对分母零值敏感但保幅值信息 (add 归一把比值压到 [0,1] 损失极端值); "
        "ATR 归一处理跨股波动率量纲。三槽 (1/4/6) 定出该族的最优数学形式。")},
    {"id": 7, "type": "VEC_EXC_RATIO_BF20", "expression": f"reverse(ts_backfill(divide(subtract(vec_avg({VHEX}), vec_avg({VLEX})), add(vec_avg({VHEX}), vec_avg({VLEX}))), 20))",
     "optimize_reason": (
        " excursion 差值归一化 + 20 日回填 (窗口扫描短端)。机制: 与槽1 (60 日) 构成回填窗口扫描; "
        "E 批显示振幅族边缘在 5-60 日平台期, excursion 族的边缘寿命需独立测量——"
        "若 20 日版 Sh 高于 60 日版, 该族边缘出清更快, 最优窗口取 20。")},
    {"id": 8, "type": "VEC_EXC_MAX_EVENT", "expression": f"reverse(divide(vec_max({VHEX}), add(vec_max({VHEX}), vec_max({VLEX}))))",
     "optimize_reason": (
        "MAX 事件口径 excursion 不对称 (取向量最大值而非平均)。机制: 注意力由最极端事件驱动而非平均事件"
        "(峰度偏好)——若一日内多次 excursion, 最极端那次的不对称度才是注意力指纹; "
        "vec_max 与 vec_avg 的对照直接检验'平均事件 vs 极端事件'哪个承载边缘, 是该族最有信息量的单槽。")},
]

# ---------------------------------------------------------------- 方向 N: 价格路径不对称 + 计数归一化
DIR_N = [
    {"id": 1, "type": "MATRIX_EXC_RATIO", "expression": f"reverse({MEXCR})",
     "optimize_reason": (
        "MATRIX excursion 标准差比值形式 (上行减下行除和, 反向)。机制: D 批测过差值形式 "
        "reverse(subtract(HEX,LEX))=0.74, L 批 VECTOR 比值形式=1.13 (2Y1.86)——比值形式在两个口径都更强, "
        "但 MATRIX 单事件口径的比值形式从未测试。本槽补齐 (MATRIX x 比值) 单元格, "
        "若它复现 VECTOR 的 1.13 量级, 说明比值化本身是边缘来源而非聚合口径。")},
    {"id": 2, "type": "MATRIX_EXC_RATIO_BF60", "expression": f"reverse(ts_backfill({MEXCR}, 60))",
     "optimize_reason": (
        "MATRIX excursion 比值 + 60 日回填。机制: 同槽1 的低换手形态; 与 M 批槽1 (VECTOR 版回填) "
        "构成材质对照——若 MATRIX 回填后 2Y 保持而 VECTOR 不保持 (或反之), 边缘的时间稳定性"
        "来源被定死到某一口径。")},
    {"id": 3, "type": "PATH_ASYM_UP_SHARE", "expression": f"reverse(divide({PATH_UP}, add({PATH_UP}, {PATH_DN})))",
     "optimize_reason": (
        "日内价格路径上下行份额: (日高-新闻价)/((日高-新闻价)+(新闻价-日低)), 反向。"
        "机制: 这是 excursion 家族的原始价格版 (exc_stddev 是它的标准化版)——用原始美元行程直接度量"
        "新闻后上行占全程的比例, 不经任何标准化; 若它与 exc_stddev 族结论一致, 边缘稳健; "
        "若显著更强, 说明标准化过程有损。三字段全为 news12 内部价格上下文字段 (合规)。")},
    {"id": 4, "type": "PATH_ASYM_CLOSE_SHARE", "expression": f"reverse(divide({MOVE}, add({MOVE}, {PATH_DN})))",
     "optimize_reason": (
        "收盘路径份额: (收盘-新闻价)/((收盘-新闻价)+(新闻价-日低)), 反向。机制: 与槽3 的差别是度量终点"
        "从日高换成收盘——日高只捕捉盘中瞬时脉冲, 收盘价捕捉'事件日定价的最终裁决'。"
        "若收盘版显著强于日高版, 说明可持有的边缘在收盘相对位置而非盘中极值; 两槽联合定出"
        "该家族的最优度量终点, 直接服务'边缘能持多久'的核心问题。")},
    {"id": 5, "type": "MOVE_PER_EVENT_COUNT", "expression": f"reverse(divide({MOVE}, {EVCNT}))",
     "optimize_reason": (
        "计数归一化模板 (news102 跨族复用): 新闻时刻到收盘的价格移动 / 120 日回填的事件数, 反向。"
        "机制: news102 冠军结构即'价格移动/新闻覆盖数'——单位新闻关注度对应的价格移动才是异常"
        "(注意力稀缺假说: 低覆盖事件的大移动 = 定价不充分 = 随后回归); 高覆盖事件的大移动 = "
        "信息充分定价 = 无回归。vec_count(excursion 向量) 提供日内事件数代理。"
        "这是本战役对'注意力稀缺'假说的最直接检验, 也是与已证伪的'注意力强度'条件化 (J 批) "
        "互补的连续度量版本。")},
    {"id": 6, "type": "MOVE_PER_COUNT_RANKED", "expression": f"reverse(rank(divide({MOVE}, {EVCNT})))",
     "optimize_reason": (
        "计数归一化 + 秩化。机制: 同槽5 的秩化版——news102 冠军即 rank 化形态; 秩化同时服务两个目的: "
        "① 消除移动/计数比值的重尾 (单事件日计数=1 时比值=原始移动, 分布极偏) ② 消除 "
        "MATCHES_THEMES 警告 (K 批已验证)。本槽是 news102 模板在 news12 上的最高保真复现。")},
    {"id": 7, "type": "RANGE_PER_EVENT_COUNT", "expression": f"reverse(divide(subtract({EODH}, {EODL}), {EVCNT}))",
     "optimize_reason": (
        "当日振幅 / 事件数 (归一化改幅度版)。机制: 与槽5/6 的差别是分子从'新闻到收盘的净移动'换成"
        "'全日振幅'——净移动有方向偏差 (漂移), 振幅是方向中性的总活动量; 若振幅版有边缘而净移动版无, "
        "说明该机制是波动/活动度驱动的而非方向驱动的, 需重解经济含义。")},
    {"id": 8, "type": "ASYM_X_GAP_INTERACTION", "expression": f"reverse(multiply(rank({ARAW}), rank({GAP})))",
     "optimize_reason": (
        "不对称度 x 跳空交互 (书面交互, 白名单 multiply 用法)。机制: 跳空 = 盘前注意力累积, "
        "日内不对称 = 盘中注意力冲击——两者的乘积 = '全周期注意力脉冲' (隔夜+盘中); "
        "若交互项显著强于单一不对称 (1.37), 说明过度反应需要全周期注意力共振而非单一维度。"
        "与已证伪的乘性缩放 (乘 vol_stddev=-0.44) 的本质区别: 那是乘波动率放大器, "
        "这是两个同类排名量的条件交互 (rank x rank 有界 [-1,1] 量级)。")},
]

# ---------------------------------------------------------------- 方向 O: MARKET 中性化 TO 力学攻击
DIR_O = [
    {"id": 1, "type": "BF60_MARKET", "expression": f"reverse({BF})",
     "optimize_reason": (
        "回填 60 日 @MARKET 中性化。机制 (TO 力学假说): K 批证实回填族 TO 在 37% 饱和——"
        "信号值在事件间恒定, 但 INDUSTRY 中性化下'行业均值随他股事件日 shuffle'导致个股权重每日变动; "
        "MARKET 剔除行业均值这一 shuffle 源, 若权重仅在个股自身信号更新时变动, TO 应结构性跌破 37%。"
        "中性化是框架唯一合法 settings 消融轴, 本批是攻 margin 死线 (Ret>=0.5*TO) 的最后合法杠杆。"
        "代价风险: G 批证明 MARKET 对原始锚有害 (1.13<1.37), 本槽测量该代价在回填族是否可接受。")},
    {"id": 2, "type": "BF20_MARKET", "expression": f"reverse(ts_backfill({ARAW}, 20))",
     "optimize_reason": (
        "回填 20 日 @MARKET。机制同槽1, 窗口取中段; 与槽1 构成 MARKET 下的回填窗口扫描。"
        "若 20 日版 TO 显著低于 37% 且 Sh 保留, 取最短有效窗口 (边缘寿命最短=换手最低)。")},
    {"id": 3, "type": "BF60_RANKED_MARKET", "expression": f"reverse(rank({BF}))",
     "optimize_reason": (
        "回填 60 日 + 秩化 @MARKET。机制: 三重叠加——回填保边 + 秩化消警告 + MARKET 降 shuffle。"
        "本槽是家族全部合规杠杆 (零警告目标) 与 TO 杠杆的合并测试, 若 Sh>=1.0 且 TO<=25%, "
        "Ret/TO 将首次突破 0.15, 距 margin 死线缩到 3.3 倍以内。")},
    {"id": 4, "type": "VEC_EXC_RATIO_MARKET", "expression": f"reverse({VEXCR})",
     "optimize_reason": (
        "VECTOR excursion 比值 @MARKET (不回流填, 先测中性化本身对 2Y 最强族的影响)。"
        "机制: 该族 2Y=1.86 但 TO 118.7%; MARKET 若能把 TO 压到 60% 以下而 2Y 保持, "
        "Ret/TO 从 0.040 升到 0.08+; 与槽1 的振幅回填族形成'原始强 2Y x 低 TO'的两种路径对照。")},
    {"id": 5, "type": "VEC_EXC_RATIO_BF60_MARKET", "expression": f"reverse(ts_backfill({VEXCR}, 60))",
     "optimize_reason": (
        "VECTOR excursion 比值 + 回填 60 @MARKET。机制: 2Y 最强测量 x 回填 x MARKET 三重叠加——"
        "本槽若 2Y>=1.58 且 Sh>=0.9 且 TO<=25%, 即是整个战役最接近门禁的结构 (仍差 Sh)。"
        "即使不达标, 其 (Sh, 2Y, TO) 三元组也是家族前沿的关键坐标点。")},
    {"id": 6, "type": "MATRIX_EXC_RATIO_BF60_MARKET", "expression": f"reverse(ts_backfill({MEXCR}, 60))",
     "optimize_reason": (
        "MATRIX excursion 比值 + 回填 @MARKET。机制: N 批槽2 的 MARKET 版——MATRIX 口径在 MARKET "
        "下的 TO 响应可能与 VECTOR 不同 (单事件 vs 聚合的事件到达率不同); 与槽5 构成口径对照。")},
    {"id": 7, "type": "BF120_MARKET", "expression": f"reverse(ts_backfill({ARAW}, 120))",
     "optimize_reason": (
        "回填 120 日 @MARKET (长窗极端)。机制: K 批证明 TO 在 37% 饱和与回填长度无关 (排名 shuffle 主导); "
        "若 MARKET 下该饱和被打破 (TO 随回填长度继续下降), 证明 shuffle 确来自行业均值——"
        "这是对 TO 力学假说的直接证伪/证实实验, 比单纯追求低 TO 更有科学价值。")},
    {"id": 8, "type": "BF60_IND_RANK_MARKET", "expression": f"reverse(group_rank({BF}, industry))",
     "optimize_reason": (
        "回填 60 + 行业内秩化 @MARKET。机制: K 批槽4 的 MARKET 版 (家族新最优 Sh1.17/sub0.90 的对照实验)。"
        "注意 group_rank(·,industry) 与 neutralization=MARKET 是两个独立机制 (组内排序 vs 中性化约束), "
        "可叠加; 本槽测量'组内排序的边缘增益'在 MARKET 下是否依然存在。")},
]

DIRECTIONS = {
    "M": {"name": "Excursion 族深化 (2Y 最强者全形态扫描)", "hypothesis": "excursion 标准差不对称的 2Y 优势 (1.86) 可经回填/秩化保留, 与振幅族的时间稳定性不同",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_M},
    "N": {"name": "价格路径不对称与计数归一化", "hypothesis": "单位新闻关注度的价格移动 (注意力稀缺) 与原始路径上下行份额承载比标准化度量更强的边缘",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_N},
    "O": {"name": "MARKET 中性化 TO 力学攻击", "hypothesis": "行业均值日度 shuffle 是回填族 TO 37% 饱和的成因, MARKET 可结构性降 TO",
          "universe": "TOP1000", "neutralization": "MARKET", "slots": DIR_O},
}

STAGGER_SECONDS = {"M": 0, "N": 25, "O": 50}


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
               "ts_backfill", "ts_mean", "ts_sum", "trade_when", "greater", "less", "vec_avg",
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
    print(f"\n===== Gate1-Wave4 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
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
        print(f"用法: python phase8_gate1_wave4.py <M|N|O>"); sys.exit(1)
    d = DIRECTIONS[direction]
    universe, neutralization = d["universe"], d["neutralization"]
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Wave4-{direction}] {d['name']} | 假说: {d['hypothesis']}", flush=True)
    print(f"[Wave4-{direction}] 设置: universe={universe} neut={neutralization} decay={DECAY} trunc={TRUNCATION}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave4-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W4_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, neutralization, universe)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate4_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate4_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W4_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave4-{direction}] 批次文件: {batch_path}", flush=True)

    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, universe, DELAY, neutralization)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W4_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path, neutralization, universe)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], neutralization, universe)
        print(f"[Wave4-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave4-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate4_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave4-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
