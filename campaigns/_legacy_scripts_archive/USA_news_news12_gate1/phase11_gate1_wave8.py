# -*- coding: utf-8 -*-
"""Gate1 Wave8 多 agent 优化驱动 (2026-10-24 深夜).

Wave7 判决 (24 槽) 后的继续战役 (用户 mandate: 锚 N1eGk79E, 攻 4 FAIL; 零 fail 零警告;
每批 8 条 multi_create_simulate; 未成功不许中断; 禁提交).

Wave7 判决要点:
  Y 全灭: 原始(未回填) count 分母 + 振幅族 -> Sh 0.43-0.81 (回填墙加强版: 分母也必须回填)
  W 突破: 新分子 close-ton_last / close-open x 极端度 -> 2Y 2.07/2.35 (锚仅 0.58, 2Y 墙破)
     CTN_PER_CNT_TSRANK250  Sh1.41/TO113%/2Y2.07/sub1.08/rnSh1.82  剩 LOW_FITNESS+HIGH_TURNOVER
     COPEN_PER_CNT_RANK     Sh1.42/TO113.8%/2Y2.35/R-TO0.068      剩 LOW_FITNESS+HIGH_TURNOVER
  Z 负结果: R/TO-新鲜度曲线平坦 (N=1/2/5/10 -> 0.097/0.098/0.100/0.096), 新鲜度路径证伪

Wave8 三路 (每路 8 槽, 蓝队三子 agent 并行设计 + 主编修正):
  T 换手管理 x 新分子: 核心可证伪假说——新分子 2Y 2.07-2.35 说明经济内容有日度以上持续性,
    平滑/回填对它们可能远比 close-vwap 温和; 若平滑后 Sh>=1.5 且 TO<=70% 且 R/TO 上升,
    则 Fit+TO 双 FAIL 同破. 覆盖 bf60/bf120/ts_mean10/20/ts_decay_linear/分子侧平滑.
  N 新分子扩展 x 锚式分母 x 极端度: 攻 Sharpe 缺口 (-0.16) 与 R/TO. 锚式低噪声分母
    (ts_backfill(count,120)) x 新分子; CTH 单层 ts_rank; ERANGE 极端度版; 窗口补点;
    COPEN 组内化; CTN 锚分母 x ts_rank250 主攻候选.
  G 门控 x 新分子合成: Z 批门控把振幅基座 TO 压到 37% 且 R/TO 保持 0.098 (平坦不伤 IC);
    若同门控作用于新分子 (无门控 TO 113%), 可能压 TO 到 50-60% 且保留 2Y 持续性 ->
    同时修 HIGH_TURNOVER 与保 2Y, 诞生战役首个三优候选. 另测门控化锚 (诊断锚 CW/TO 病因).

主编修正记录:
  1. N 批蓝队 type 名全为 "NEWS" -> 补正为可区分类型名
  2. G5 蓝队去掉 +1 防除零包装 (vec_count=0 除零污染整批) -> 修复; 修复后 ops=12 超限,
     故去掉外层 ts_rank250 保 ops=10 (与 T6  Ungated 版形成门控 A/B)
  3. G7 蓝队嵌套 trade_when (语法未经平台验证, 单条语法错误 CANCEL 整批) -> 替换为
     门控 x ERANGE 极端度版 (单层 trade_when, 安全)
  4. N1/N7 指纹命中前役两候选 (d5K6wxlx Sh1.61/TO120%/CW; YPxOX1QA Sh1.57/TO118%/CW),
     且实证锚分母对 CTN 不降反升 TO (120% vs 原始 CNT 113%) 但招 CW fail -> 原假说被数据
     推翻, 两槽替换为冠军基座 (d5K6wxlx, 全场最高 Sh1.61) 的平滑版与组内化版, 直接攻其
     残余 FAIL 集合 (TO/CW/Fit)
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
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"      # 锚式低噪声分母 (N1eGk79E 原样)
DFLC = f"days_from_last_change(vec_count({VHEX}))"       # 距上次事件计数变化的天数 (催化剂)

# ================================================================ 方向 T: 换手管理 x 新分子
DIR_T = [
    {"id": 1, "type": "COPEN_PER_CNT_BF60_RANK", "expression":
        f"reverse(rank(ts_backfill(divide(subtract({EOC}, {OPEN}), {CNT}), 60)))",
     "optimize_reason": (
        "COPEN 每关注度 + bf60 + plain rank。机制: 收盘相对开盘的日内买方压力经高波动日计数"
        "归一, 60 日回填只补空白不改变化率, 消除信号消失-重现造成的换手脉冲。Y5 已证 bf60 杀 "
        "close-vwap (Sh0.67), 本槽测回填致死效应是否分子依赖——若 COPEN 幸存 (Sh>=1.5 且 "
        "TO<=70%), 即打开 TO 113%->70% 的最短路径。")},
    {"id": 2, "type": "COPEN_PER_CNT_BF120_RANK", "expression":
        f"reverse(rank(ts_backfill(divide(subtract({EOC}, {OPEN}), {CNT}), 120)))",
     "optimize_reason": (
        "同槽1 回填加深至 120 日。机制: 与槽1 构成 bf 窗口长度单调曲线 (60/120)——检验 TO 降幅"
        "是否随回填深度继续下降、Sh 是否在 120 日处崩塌, 定位回填深度上限与最优区间。"
        "K 批证实 ASYM 族 TO 在 37% 饱和 (bf60/120/250 同值), 但每关注度口径计数分母每日可变,"
        "长回填可能进一步降 TO。")},
    {"id": 3, "type": "COPEN_PER_CNT_MEAN10_RANK", "expression":
        f"reverse(rank(ts_mean(divide(subtract({EOC}, {OPEN}), {CNT}), 10)))",
     "optimize_reason": (
        "COPEN 每关注度 + ts_mean10 + plain rank。机制: 10 日等权平均滤除单日跳动噪声而保留"
        "持续性日内动量暴露。核心判据: 若 Ret 降幅小于 TO 降幅 (R/TO 上升) 则 Fit 同步抬升——"
        "验证'平滑去噪提升单位换手收益'假说; 若 Ret/TO 同降 (旧族行为) 则 Fit 不变仅 TO 达标。")},
    {"id": 4, "type": "CTN_PER_CNT_MEAN20_TSRANK250", "expression":
        f"reverse(ts_rank(ts_mean(divide(subtract({EOC}, {TON}), {CNT}), 20), 250))",
     "optimize_reason": (
        "W4 基座唯一变体 (内层加 ts_mean20)。机制: 收盘相对盘后最新价的偏离 (价格发现滞后) 经"
        "计数归一后 20 日平滑再转 250 日时序秩。若 TO 大降且 Sh>=1.5, 证明 CTN 的 2Y=2.07 源于"
        "信号水平的真实持续性而非仅 ts_rank 的秩结构——Fit+TO 双破的主攻手。")},
    {"id": 5, "type": "CTN_PER_CNT_DECAY20_TSRANK250", "expression":
        f"reverse(ts_rank(ts_decay_linear(divide(subtract({EOC}, {TON}), {CNT}), 20), 250))",
     "optimize_reason": (
        "同槽4 但 20 日线性衰减加权替代等权平均。机制: 与槽4 配对分离衰减形状效应——近期滞后"
        "信息权重更高, 在去噪与保留新鲜度间取中。同时检验旧族证伪'decay 同比例降 Ret 与 TO'"
        "是否对新分子失效 (R/TO 上升则失效, 这是本批最重要的单点判据)。")},
    {"id": 6, "type": "CTN_PER_CNT_BF60_TSRANK250", "expression":
        f"reverse(ts_rank(ts_backfill(divide(subtract({EOC}, {TON}), {CNT}), 60), 250))",
     "optimize_reason": (
        "W4 直接变体 (唯一差异内层 bf60)。机制: 与槽1 配对可四槽分离 bf60 的分子依赖 (CTN vs "
        "COPEN) 与外层依赖 (ts_rank250 vs rank), 完整读出回填效应的全因子结构。若 CTN 对 bf60 "
        "的耐受显著优于 close-vwap, 回填墙是分子瞬态性而非算子固有属性。")},
    {"id": 7, "type": "CTN_PER_CNT_NUM_MEAN10_TSRANK250", "expression":
        f"reverse(ts_rank(divide(ts_mean(subtract({EOC}, {TON}), 10), {CNT}), 250))",
     "optimize_reason": (
        "只平滑分子 (收盘减盘后最新价的 10 日均), 分母保持原始日度调节。机制: 与槽4 配对分离"
        "平滑作用位置 (分子侧 vs 整体比值)——若本槽 R/TO 高于槽4, 说明分母的日度波动调节信息"
        "是 alpha 质量来源, 平滑应只作用于价格差而非整个比值。")},
    {"id": 8, "type": "COPEN_PER_CNT_MEAN20_RANK", "expression":
        f"reverse(rank(ts_mean(divide(subtract({EOC}, {OPEN}), {CNT}), 20)))",
     "optimize_reason": (
        "本批最有希望同时击穿 TO 与 Fit 的一条: COPEN 持续性全场最高 (2Y=2.35) 使 mean20 后 Sh "
        "幸存概率最大。机制: 日内买方压力的季度级经济持续性配 20 日深度平滑。若 TO<=70 且 "
        "Sh>=1.5 即成为下批基座; 若 Sh 塌则精确界定 COPEN 持续性窗口上限在 10-20 日之间。")},
]

# ================================================================ 方向 N: 新分子扩展 x 锚式分母 x 极端度
DIR_N = [
    {"id": 1, "type": "CHAMP_MEAN10_RANK", "expression":
        f"reverse(rank(ts_mean(divide(subtract({EOC}, {TON}), {ANCHOR_DEN}), 10)))",
     "optimize_reason": (
        "冠军基座平滑版 (主编修正: 原设计锚分母 x CTN plain rank 实为 d5K6wxlx 重测, 已实测 "
        "Sh1.61/TO120%/CW/Fit0.41)。机制: 全场最高 Sh (1.61, 唯一过 Sharpe 线) 基座的比值做 10 "
        "日等权平滑——若 TO 120%->70% 且 Sh>=1.58 且 2Y 2.09 保住, 冠军只剩 Fit+CW 两个 FAIL, "
        "且比 W 批基座 (Sh1.41-1.42) 高 0.2 的 Sharpe 头寸; 若 Sh 塌则冠军的高 Sh 依赖日度"
        "新鲜度 (与 T 批平滑假说互证/互斥)。")},
    {"id": 2, "type": "COPEN_ANCHORDEN_RANK", "expression":
        f"reverse(rank(divide(subtract({EOC}, {OPEN}), {ANCHOR_DEN})))",
     "optimize_reason": (
        "同槽1 换 COPEN 分子。机制: 与槽1 构成分子对照——W6 COPEN x 原始 CNT 分母 TO113.8%, "
        "换锚分母后若 TO 大降且 2Y=2.35 保住, 得双低噪候选 (锚分母已验证 + 最持续分子已验证)。")},
    {"id": 3, "type": "CTH_PER_CNT_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {TH}), {CNT}), 250))",
     "optimize_reason": (
        "close-ton_high 每关注度 + 单层 ts_rank250 (隔离变量)。机制: W8 双 rank 嵌套 "
        "group_rank(ts_rank) 仅 Sh0.48 但 2Y1.64——本槽去掉 group_rank 测单层能否救回 Sharpe; "
        "收盘相对新闻时刻高点的回撤深度 = 恐慌超卖签名, reverse 做多反弹。")},
    {"id": 4, "type": "ERANGE_PER_CNT_TSRANK250", "expression":
        f"reverse(ts_rank(divide(subtract({EOH}, {EOL}), {CNT}), 250))",
     "optimize_reason": (
        "全日高低价差每关注度 + 极端度版。机制: W 批 EODRANGE plain rank 全崩 (Sh0.37/2Y-0.08), "
        "本槽测 ts_rank250 极端度能否救回——单位关注度的全日振幅 = 彩票性过度反应签名; "
        "若仍崩则振幅族在 news12 无方向性内容 (与 Y 批合并定论)。")},
    {"id": 5, "type": "CTN_PER_CNT_TSRANK500", "expression":
        f"reverse(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 500))",
     "optimize_reason": (
        "CTN 极端度窗口补点 500 日。机制: CVW 网格 120/250/500 平坦 (Sh1.50-1.56), 测 CTN@500 "
        "是否维持 Sh 与 2Y——500 窗为最低 TO 直攻 R/TO 主墙; 若 CTN 窗口曲线不平坦 (长窗更优), "
        "说明价格发现滞后是慢过程, 与 2Y=2.07 的持续性互证。")},
    {"id": 6, "type": "COPEN_PER_CNT_GRPRANK", "expression":
        f"reverse(group_rank(divide(subtract({EOC}, {OPEN}), {CNT}), industry))",
     "optimize_reason": (
        "COPEN 每关注度 + 组内行业秩。机制: 组内化剔除行业间系统性漂移差异, 只交易行业内相对"
        "定价错位; group_zscore 已证伪 (Sh0.71/2Y-0.30) 但 group_rank(industry) 未测——测组内化"
        "对 R/TO 的净影响 (去行业共同因子可能提纯每笔 IC)。")},
    {"id": 7, "type": "CHAMP_GRPRANK", "expression":
        f"reverse(group_rank(divide(subtract({EOC}, {TON}), {ANCHOR_DEN}), industry))",
     "optimize_reason": (
        "冠军基座组内化版 (主编修正: 原设计锚分母 x CTN x ts_rank250 实为 YPxOX1QA 重测, 已实测 "
        "Sh1.57/2Y2.16/TO118%/CW)。机制: 直接攻冠军的 CONCENTRATED_WEIGHT fail——组内行业秩把"
        "头寸限制在行业相对排序内, 极端个股尖峰被压平 (与已证伪的 group_zscore Sh0.71 不同, "
        "group_rank 保留排序信息不引入连续幅度); 若 CW 消除且 Sh>=1.5, 冠军三 FAIL 去其一, "
        "且与 N1 (平滑攻 TO) 构成冠军修复的两条独立路径。")},
    {"id": 8, "type": "COPEN_PER_CNT_DECAY10_RANK", "expression":
        f"reverse(rank(ts_decay_linear(divide(subtract({EOC}, {OPEN}), {CNT}), 10)))",
     "optimize_reason": (
        "2Y 稳定性专测: 最持续分子 COPEN (2Y2.35) x 全战役未测的 ts_decay_linear 平滑 (直接砍 "
        "TO)。机制: 线性衰减加权在压换手同时比等权 mean 更新鲜; 若 TO 大降且 2Y 保持 1.58 以上"
        "则为 R/TO 突破路径; 若 Sh 崩则标定 COPEN 的平滑耐受上限 (与 T 批 mean10/20 构成三种"
        "平滑形状的完整对照)。")},
]

# ================================================================ 方向 G: 门控 x 新分子合成
DIR_G = [
    {"id": 1, "type": "EVT_GATE_5D_CTN_TSR250", "expression":
        f"trade_when(less({DFLC}, 5), reverse(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 250)), -1)",
     "optimize_reason": (
        "核心假说主检验: 事件后 5 日新鲜窗口内交易 CTN 极端度信号。Z 批门控把振幅基座 TO 压到 "
        "37% 且 R/TO 保持 0.098 (平坦曲线证明门控不伤每笔 IC); 若同门控把 CTN 的 TO 从 113% "
        "压到 50-60% 且保留 2Y~2.07, 则 Sh>=1.5/TO<=70%/2Y>=1.58 三优同时成立——战役首个"
        "全门候选。机制: 关注度稀缺错价只存在于事件后有限窗口, 门控显式化催化剂。")},
    {"id": 2, "type": "EVT_GATE_5D_COPEN_RANK", "expression":
        f"trade_when(less({DFLC}, 5), reverse(rank(divide(subtract({EOC}, {OPEN}), {CNT}))), -1)",
     "optimize_reason": (
        "同构对照换 COPEN 分子。机制: 与槽1 分离门控机制与分子选择的贡献——COPEN 无门控 2Y=2.35 "
        "为 W 批最高, 检验其持续性能否在门控下存活; 事件窗口内的日内过度反应均值回归是最干净的"
        "注意力稀缺假说载体。")},
    {"id": 3, "type": "EVT_GATE_2D_CTN_TSR250", "expression":
        f"trade_when(less({DFLC}, 2), reverse(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 250)), -1)",
     "optimize_reason": (
        "门控宽度对照 N=2 (事件日+次日)。机制: Z 批 N=1/2/5/10 在振幅基座上平坦, 但对 CTN 可能"
        "不同——若 N=2 与 N=5 接近则信号衰减慢、TO 可进一步压缩; 若 N=2 明显变差则最佳宽度在 5 "
        "附近, 且证明 CTN 边缘需要隔夜信息扩散时间。")},
    {"id": 4, "type": "EVT_GATE_5D_ANCHOR_CVW", "expression":
        f"trade_when(less({DFLC}, 5), reverse(rank(divide(subtract({EOC}, {VWAP}), {ANCHOR_DEN}))), -1)",
     "optimize_reason": (
        "门控化锚 N1eGk79E 整体复测 (诊断实验)。机制: 锚的 TO=116.88% 与 CW fail 是否源于非事件"
        "日持仓? 若门控后 TO 崩塌而 Sh 保持, 证实非事件日陈旧仓位是病因且门控可修复锚; 若整体"
        "塌方 (close-vwap 分子非事件日 NaN, 证伪清单第 1 条), 则确认锚的空转结构不可门控修复,"
        "新分子路线 (槽1/2) 是唯一出路。")},
    {"id": 5, "type": "EVT_GATE_5D_CTN_BF60", "expression":
        f"trade_when(less({DFLC}, 5), reverse(ts_backfill(divide(subtract({EOC}, {TON}), {CNT}), 60)), -1)",
     "optimize_reason": (
        "门控 x 回填双 TO 杠杆 (主编修正版: 蓝队原设计去掉 +1 防除零有除零污染风险, 且修复后 "
        "ops=12 超限, 故去外层 ts_rank 保 10)。机制: 冻结事件日快照 + 新鲜窗口双重压 TO; 与 T6 "
        "(无门控同构) 构成门控 A/B——若本槽 TO 显著低于 T6 而 Sh 不塌, 门控与回填可叠加; "
        "若 Sh 塌则回填冻结对 CTN 与对 close-vwap 一样致死 (回填墙通杀)。")},
    {"id": 6, "type": "COUNT_GE2_CTN_TSR250", "expression":
        f"trade_when(greater(vec_count({VHEX}), 1), reverse(ts_rank(divide(subtract({EOC}, {TON}), {CNT}), 250)), -1)",
     "optimize_reason": (
        "数据质量门控 x 新分子。机制: 仅当日 >=2 个新闻事件时持仓 (单事件日计数分母=1, 归一退化"
        "为裸位移且噪声最大); Z7 COUNT_GE2 x close-vwap 仅 Sh0.85-0.90, 换 CTN 分子后若门控转正"
        "说明质量过滤对持续分子有效; 若仍低则放弃计数门控轴 (与 G1 的新鲜度门控分离两轴)。")},
    {"id": 7, "type": "EVT_GATE_5D_ERANGE_TSR250", "expression":
        f"trade_when(less({DFLC}, 5), reverse(ts_rank(divide(subtract({EOH}, {EOL}), {CNT}), 250)), -1)",
     "optimize_reason": (
        "门控 x 全日振幅极端度 (主编修正版: 蓝队原设计嵌套 trade_when 语法未经平台验证, 单条语法"
        "错误会 CANCEL 整批, 替换为安全单层门控)。机制: 事件窗口内的单位关注度全日振幅 = 注意力"
        "稀缺型流动性冲击; 与 N4 (无门控) 构成门控 A/B, 同时与 G1/G2 分离'方向性分子'与'方向"
        "中性振幅'在门控下的存活差异。")},
    {"id": 8, "type": "EVT_GATE_5D_CTN_INDRANK", "expression":
        f"trade_when(less({DFLC}, 5), reverse(group_rank(divide(subtract({EOC}, {TON}), {CNT}), industry)), -1)",
     "optimize_reason": (
        "事件窗口内 CTN 行业分组反向排序。机制: 把 INDUSTRY 中性化前置到排序层——组内秩剔除行业"
        "共同漂移, 降低行业暴露与个股集中度 (攻 CW fail 与 MATCHES_THEMES 警告); 与 N6 (无门控 "
        "COPEN 组内化) 和 G1 (无组内化) 构成门控 x 组内化二维对照的一点。")},
]

DIRECTIONS = {
    "T": {"name": "换手管理 x 新分子 (攻 HIGH_TURNOVER 113%-><=70%)", "hypothesis":
           "新分子 (close-ton_last/open) 的 2Y 2.07-2.35 说明经济内容有日度以上持续性, "
           "平滑/回填对它们可能远比 close-vwap 温和; 若平滑后 Sh>=1.5 且 TO<=70% 且 Ret 降幅"
           "小于 TO 降幅 (R/TO 上升), Fit+TO 双 FAIL 同破",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_T},
    "N": {"name": "新分子扩展 x 锚式分母 x 极端度 (攻 Sharpe 缺口与 R/TO)", "hypothesis":
           "close-vwap 的 2Y 上限 (0.78) 对 ton_last/open 分子不适用; 新闻语境价格族其他参照点"
           "(ton_high/eod_range) 与锚式低噪声分母从未系统扫描; 堆叠三项已验证机制 (CTN 分子 x "
           "锚分母 x ts_rank250) 是最接近全门达标的结构",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_N},
    "G": {"name": "门控 x 新分子合成 (Z 批低 TO 门控机制驯服 W 批新分子的高 TO)", "hypothesis":
           "EVT_GATE 门控把振幅基座 TO 压到 37% 且 R/TO 保持 0.098 (平坦不伤 IC); 若同门控作用于"
           "新分子 (无门控 TO 113%), 可能压 TO 到 50-60% 且保留 2Y 持续性 -> 同时修 HIGH_TURNOVER "
           "与保 2Y, 诞生战役首个三优候选; 另含门控化锚的诊断实验",
           "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_G},
}

STAGGER_SECONDS = {"T": 0, "N": 25, "G": 50}


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
    print(f"\n===== Gate1-Wave8 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
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
    print(f"[Wave8] 字段字典 {len(known_fields)} 个装载", flush=True)

    plans = []
    for direction in ["T", "N", "G"]:
        d = DIRECTIONS[direction]
        items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
                  "seed_id": f"GATE1W8_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
        assert len(items) == 8, f"{direction} 批必须 8 槽"
        print(f"\n[Wave8-{direction}] {d['name']}", flush=True)
        print(f"[Wave8-{direction}] 假说: {d['hypothesis']}", flush=True)
        preaudit(items, known_fields)
        check_dup_fingerprints(items, d["neutralization"], d["universe"])
        plans.append((direction, d, items))

    ts = int(time.time())
    locations = {}
    for direction, d, items in plans:
        await asyncio.sleep(STAGGER_SECONDS[direction])
        batch_path = os.path.join(CAMPAIGN, f"batch_gate8_{direction}_{ts}.json")
        state_path = os.path.join(CAMPAIGN, f"state_gate8_{direction}.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W8_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                      f, ensure_ascii=False, indent=1)
        corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION,
                                                           d["universe"], DELAY, d["neutralization"])
        for it, ce in zip(items, corrected):
            it["expression"] = ce
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"seed_id": f"GATE1W8_{direction}", "region": REGION, "universe": d["universe"],
                       "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                      f, ensure_ascii=False, indent=1)
        print(f"[Wave8-{direction}] 批次文件: {batch_path}", flush=True)
        try:
            loc = await submit_batch(items, state_path, d["neutralization"], d["universe"], direction)
            locations[direction] = loc
        except Exception as e:
            purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])
            print(f"[Wave8-{direction}] FATAL submit: {e}", flush=True)
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
            print(f"[Wave8-{direction}] fetch 空! {str(fetch)[:300]}", flush=True)
            continue
        batch_path = os.path.join(CAMPAIGN, f"batch_gate8_{direction}_{ts}_result.json")
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
        print(f"[Wave8-{direction}] 结果已存: {batch_path}", flush=True)
        summary = build_summary(items, results, direction)
        sum_path = os.path.join(CAMPAIGN, f"summary_gate8_{direction}.json")
        with open(sum_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
        print_table(summary)
        print(f"[Wave8-{direction}] 汇总已存: {sum_path}", flush=True)

    print("\n[Wave8] 三批全部回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
