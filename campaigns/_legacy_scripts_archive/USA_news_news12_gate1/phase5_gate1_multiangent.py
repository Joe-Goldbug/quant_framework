# -*- coding: utf-8 -*-
"""
Phase 5 / Gate 1 战役: 多方向并行定向优化 — USA / news12 / TOP1000 / delay1
基于最佳候选 reverse(A) (Sh 1.37 / TO 129.9% / DD 8.4% / 2Y 1.68 / rnSh 1.65) 的经济学延伸.

用户 mandate (2026-10-24):
  - 2 <= 数据字段数 <= 3; 不限 op (审计上限已放宽至 10); 每批 8 条 multi_create_simulate;
  - 严格基于严谨的经济学意义假设; 目标 = 通过所有指标阈值 (无 fail 无 warning);
  - 最终 alpha **严禁提交**.

四个并行研究方向 (每个方向一个独立后台 agent 流, 8 槽满批):
  A 异常度归一化   — 过度反应由超出自身波动尺度的异常冲测承载
  B 收益空间与反应速度解剖 — 过度反应是收益率现象; 分钟级反应剖面披露信息扩散结构
  C 累积订单流不平衡 — 振幅加权多日累积度量持续价格压力 (天然低换手)
  D 收盘位置与回吐解剖 — 收盘回吐程度披露买盘性质 (注意力驱动 vs 信息驱动)

每批槽1 = 对照锚 reverse(A) (与种子同设置 INDUSTRY/decay=6/trunc=0.025, 归因基准).
"""
import asyncio
import json
import os
import sqlite3
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule
from quant_framework.core.sim_runner import SimBatchRunner
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.gatekeeper import Gatekeeper

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))  # .agents 根目录
CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12", "news12_fields_UNFILTERED.json")
os.makedirs(CAMPAIGN, exist_ok=True)

REGION, UNIVERSE, DELAY, CATEGORY = "USA", "TOP1000", 1, "news"
NEUTRALIZATION, DECAY, TRUNCATION, NAN_HANDLING = "INDUSTRY", 6, 0.025, "ON"

# ---- 字段别名 (全部经 news12_fields_UNFILTERED.json 875 字段核实存在) ----
UP = "news_max_up_amt"      # 新闻后最高价 - 新闻时刻价 (美元冲测)
DN = "news_max_dn_amt"      # 新闻时刻价 - 新闻后最低价 (美元冲测)
UR = "news_max_up_ret"      # 上行冲测 (百分比)
DR = "news_max_dn_ret"      # 下行冲测 (百分比)
ATR14 = "news_atr14"        # 14 日平均真实波幅
ATRR = "news_atr_ratio"     # 当日量程 / 20 日 ATR (量程异常度, 恒正)
TICKS = "news_tot_ticks"    # 当日成交笔数
EOH = "news_eod_high"       # 新闻后至收盘的最高价
EOL = "news_eod_low"        # 新闻后至收盘的最低价
EOC = "news_eod_close"      # 收盘价
EOV = "news_eod_vwap"       # 新闻后至收盘的 VWAP
HEX = "news_high_exc_stddev"  # (收盘前最高价-最后价) 标准化
LEX = "news_low_exc_stddev"   # (新闻时刻价-收盘前最低价) 标准化
TONH = "news_ton_high"      # 新闻前当日最高价
TONL = "news_ton_last"      # 新闻时刻价
P1M = "news_pct_1min"       # 首分钟反应
P30S = "news_pct_30sec"     # 30 秒反应
P5M = "news_pct_5_min"      # 5 分钟反应
P30M = "news_pct_30min"     # 30 分钟反应
P60M = "news_pct_60min"     # 60 分钟反应
P120M = "news_pct_120min"   # 120 分钟反应
PDR = "news_prev_day_ret"   # 昨日全天涨跌

CTRL = f"reverse(divide({UP}, add({UP}, {DN})))"  # 对照锚 = 最佳候选盈利方向

R_CTRL = (
    "对照锚（归因基准）：最佳候选盈利方向 reverse(A)，Sh 1.37 / TO 129.9% / DD 8.4% / 2Y 1.68 / rnSh 1.65。"
    "本槽与种子同设置重测，用于校准批次环境漂移——若本槽复现 1.37 且 TO≈130%，证明本批与历史完全同构，"
    "其余 7 槽的读数差异才可全部归因于表达式结构本身。"
)

# ============================================================
# 方向 A: 异常度归一化 (Abnormality Normalization)
# 假说: 过度反应由超出个股自身波动尺度的异常冲测承载。同一美元净冲测, 对 ATR=$1 的股票是数倍
#       标准差的冲击, 对 ATR=$5 的股票是日常噪声。把净冲测除以个股波动尺度后, 信号从"冲测大小"
#       变为"冲测异常度"——只有异常冲测才触发流动性提供者的逆向定价, 信噪比与次日预测力同步提升。
# ============================================================
DIR_A = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL, "optimize_reason": R_CTRL},
    {"id": 2, "type": "NET_EXC_ATR14", "expression": f"reverse(divide(subtract({UP}, {DN}), {ATR14}))",
     "optimize_reason": (
        "净冲测/14日ATR：把(上行冲测-下行冲测)的美元净额除以个股14日平均真实波幅，得到以自身波动尺度计量的"
        "净冲测异常度。机制：流动性提供者只对超出常规波动幅度的单边冲测收取逆向定价溢价（库存成本+逆向选择），"
        "日常尺度内的冲测不改变其做市报价，因而不产生可交易的次日回归。ATR14 是平台原生波动尺度字段（覆盖率0.89），"
        "分母恒正、无量纲冲突。若 |Sh| 显著高于对照锚 1.37，证明边缘确实寄存于异常冲测而非全部冲测。")},
    {"id": 3, "type": "NET_EXC_ATR_RATIO", "expression": f"reverse(divide(subtract({UP}, {DN}), {ATRR}))",
     "optimize_reason": (
        "净冲测/当日量程异常度：分母改用当日量程相对20日ATR的比值——把异常度定义从'个股长期波动尺度'换成"
        "'当日量程的即时异常性'。机制：事件日的量程扩张本身就是注意力冲击的指纹（Barber-Odean 注意力假说），"
        "以当日量程为尺度衡量净冲测，等价于问'当日的单边压强有多大比例是异常放大的'。与槽2构成尺度选择"
        "配对消融：长期波动尺度（ATR14）vs 当日异常尺度（atr_ratio），判决过度反应 Edge 究竟由哪个尺度承载。")},
    {"id": 4, "type": "NET_EXC_SELF_STD", "expression": f"reverse(divide(subtract({UP}, {DN}), ts_std_dev(add({UP}, {DN}), 60)))",
     "optimize_reason": (
        "净冲测/自身60日总冲测标准差：完全自归一化（仅用 UP/DN 两个字段），分母为该股过去60日'上行+下行'总冲测的"
        "标准差。机制：同一美元净冲测，对事件冲测常年剧烈的股票是常态，对事件冲测常年平静的股票才是异常——"
        "个股自身的事件冲测分布才是最合适的异常度基准（静态价值因子在 TOP1000 已死，但事件尺度的个股校准仍有效）。"
        "本槽同时检验'不依赖外部波动字段'的纯两字段归一化能否复现槽2/3 的效果。")},
    {"id": 5, "type": "NET_EXC_SELF_MEAN", "expression": f"reverse(divide(subtract({UP}, {DN}), ts_mean(add({UP}, {DN}), 60)))",
     "optimize_reason": (
        "净冲测/自身60日总冲测均值：槽4的均值版基准。均值对离群事件日更稳健（标准差会被历史极端事件抬高，"
        "导致分母膨胀、信号被压缩）。机制相同：把净冲测翻译成'相对自身事件压力基准的倍数'。两槽配对可分离"
        "异常度估计量（均值vs标准差）对边缘的影响——若均值版显著更优，说明历史极端事件污染了标准差基准。")},
    {"id": 6, "type": "ASYM_X_ATR_RATIO", "expression": f"reverse(multiply(divide({UP}, add({UP}, {DN})), {ATRR}))",
     "optimize_reason": (
        "不对称度×当日量程异常度（书面交互）：把最佳候选的不对称度（有界[0,1]）乘以当日量程异常度。交互假说："
        "注意力冲击日的单边冲测才是可交易的过度反应，平静日的不对称是常态噪声——乘法让宽幅量程日的不对称获得"
        "更高权重、平静日的不对称被压向零。与方向A其余'除法归一化' slots 构成乘法vs除法的方向配对："
        "若乘法翻负（乘性交互引入波动率暴露致信号翻转，参考关注度缩放 -0.44 的教训），则确认该族只能用除法尺度化。")},
    {"id": 7, "type": "NET_EXC_SELF_Z", "expression": f"reverse(ts_zscore(subtract({UP}, {DN}), 120))",
     "optimize_reason": (
        "净冲测的自身120日标准分：用平台原生时序标准化把净冲测映射到自身一年分布的标准分。与槽4的区别在于"
        "窗口长度（120 vs 60）与标准化形式（zscore vs 比值）。机制：一年的自身历史足以覆盖个股的事件节奏"
        "（季报周期/并购窗口），标准分>2 的冲测在统计上就是异常事件。本槽检验异常度假说对窗口长度的敏感性。")},
    {"id": 8, "type": "NET_EXC_PER_TICK", "expression": f"reverse(divide(subtract({UP}, {DN}), {TICKS}))",
     "optimize_reason": (
        "净冲测/当日成交笔数（Kyle λ 事件版）：每笔交易承载的净冲测美元额=事件价格冲击系数。微观结构机制："
        "单位笔数的冲测越大，说明吃掉对手价的流动性越薄（高冲击、低弹性），此类冲击的次日回归是流动性溢价"
        "而非信息重定价；冲击小的单边冲测更多是信息驱动，不回归。这是本批次唯一直接来源于市场微观结构"
        "（Kyle 1985 价格冲击模型）而非行为金融的归一化假说，与全部行为假说形成机制对照。")},
]

# ============================================================
# 方向 B: 收益空间与反应速度解剖 (Return Space & Reaction-Speed Anatomy)
# 假说: ①过度反应本质是收益率现象（投资者以收益率体验事件），金额空间混杂股价水平效应——
#       高价股同一百分比冲测对应更大美元金额，金额不对称度对高价股存在系统性放大；
#       ②事件后分钟级反应剖面披露信息扩散结构：首分钟脉冲远大于后续漂移=注意力冲击型过度反应
#       （瞬时情绪成交、无持续信息注入），慢扩散型=信息渐进定价（延续）。反向结构只捕捉前者。
# ============================================================
DIR_B = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL, "optimize_reason": R_CTRL},
    {"id": 2, "type": "ASYM_RET_SPACE", "expression": f"reverse(divide({UR}, add({UR}, {DR})))",
     "optimize_reason": (
        "收益空间不对称度（金额空间的孪生）：把 UP/DN 金额换成 UP_RET/DN_RET 百分比冲测。机制：过度反应与"
        "次日回归是收益率现象（De Bondt-Thaler 以来的全部事件反转文献都以收益计量），金额空间的不对称度"
        "混杂了股价水平效应——同一 1% 冲测在 $1000 股票上是 $10、在 $20 股票上是 $0.2，金额比值虽为有界比值"
        "但其截面噪声结构被高价股主导。收益空间比值是投资者实际体验的不对称度。若其 |Sh| 高于金额空间 1.37，"
        "则证明冠军信号存在可修复的度量空间污染；若更低，则金额空间反而是更优度量（大单优先理论）。")},
    {"id": 3, "type": "NET_RET_EXC", "expression": f"reverse(subtract({UR}, {DR}))",
     "optimize_reason": (
        "净收益冲测：收益空间不对称度的差分版（不做比值归一）。比值版把'上行5%/下行1%'与'上行50%/下行10%'"
        "视为同等不对称，差分版保留幅度信息。机制假说：过度反应的力度同时取决于不对称方向与冲测规模——"
        "大幅度的单向冲测才值得做市商放大库存风险。与槽2配对分离'方向不对称'与'幅度'两个成分的预测力。")},
    {"id": 4, "type": "IMPULSE_VS_DRIFT_1M", "expression": f"reverse(subtract({P1M}, {P120M}))",
     "optimize_reason": (
        "首分钟脉冲减两小时漂移：反应剖面的'快-慢'分解。机制：若价格在首分钟即完成大部分反应而随后两小时无"
        "进一步漂移，说明推动力是注意力/情绪驱动的瞬时成交（无持续信息注入），此类脉冲的次日回归是经典过度"
        "反应；若反应在两个小时里持续扩散，说明信息在被渐进定价（underreaction-PEAD 机制），不应反向。"
        "本槽是整个速度解剖族的第一个探针，直接检验'脉冲型过度反应'假说。")},
    {"id": 5, "type": "IMPULSE_VS_DRIFT_30S", "expression": f"reverse(subtract({P30S}, {P30M}))",
     "optimize_reason": (
        "30秒脉冲减30分钟反应：更极端的时间尺度对比（30秒 vs 30分钟，相差60倍）。机制同槽4但把'瞬时'定义"
        "推到极限——30秒内的跳升若在半小时内回吐干净，是纯粹的注意力冲击（新闻标题的情绪冲击在秒级成交、"
        "分钟级消退）。两槽共同标定'快-慢差'假说的剂量效应：哪个时间尺度的脉冲差最承载边缘。")},
    {"id": 6, "type": "IMPULSE_VS_DRIFT_5M", "expression": f"reverse(subtract({P5M}, {P60M}))",
     "optimize_reason": (
        "5分钟反应减60分钟反应：中等时间尺度的快-慢对比，与槽4/5 构成三档扫描（秒级/分钟级/两小时级）。"
        "机制：不同时间尺度的'快-慢差'捕获不同频率的过度反应成分——若边缘集中在最短尺度（槽5），说明是纯情绪"
        "冲击；若集中在最长尺度（槽4），说明是当日内的信息定价节奏。三槽联合可定位边缘的时频谱峰。")},
    {"id": 7, "type": "ASYM_RET_X_ATR", "expression": f"reverse(multiply(divide({UR}, add({UR}, {DR})), {ATRR}))",
     "optimize_reason": (
        "收益空间不对称度×量程异常度：把槽2的收益空间不对称度与方向A的异常度假说合并——收益空间的不对称且"
        "发生在异常宽幅日，才是注意力冲击的完整指纹。书面交互假说：过度反应 = 不对称方向 × 事件异常度，"
        "两个条件必须同时成立（乘法交互而非加法拼凑）。本槽同时检验收益空间度量与异常度加权是否可叠加增益。")},
    {"id": 8, "type": "TREND_STACKING", "expression": f"reverse(multiply({PDR}, {P30M}))",
     "optimize_reason": (
        "趋势叠加度（昨日涨跌×当日30分钟反应）：书面交互假说——当事件反应叠加在已趋势运行的股票上（昨日大涨"
        "+今日事件后继续大涨），趋势耗尽+注意力叠加使次日回吐概率最高；逆于昨日趋势的事件反应更可能是新信息"
        "（延续）。乘积结构天然实现'两个条件同时极端才给极值'。风险提示：乘性交互可能引入波动率因子暴露"
        "（关注度缩放翻负 -0.44 的前车之鉴），本槽的读数同时是该风险的又一次性经验检验。")},
]

# ============================================================
# 方向 C: 累积订单流不平衡 (Cumulative Order-Flow Imbalance)
# 假说: 日频不对称度只是瞬态压力快照；振幅加权的多日累积不对称度（60日上行冲测金额占总冲测
#       金额的份额）度量'资金实际去向'的持续偏离——持续单边冲测积累未出清的价格压力，压力越大
#       回归越强。与已证伪的等权平滑 ts_mean(A,60)（Sh 0.11）本质不同：等权平滑把噪声日与信号日
#       等量混合，振幅加权让大事件主导累积量，更接近'压力'的经济定义；且累积量天然慢变→换手结构性下降。
# ============================================================
DIR_C = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL, "optimize_reason": R_CTRL},
    {"id": 2, "type": "CUM_IMBALANCE_60", "expression": f"reverse(divide(ts_sum({UP}, 60), add(ts_sum({UP}, 60), ts_sum({DN}, 60))))",
     "optimize_reason": (
        "60日累积不对称度（振幅加权）：过去60个交易日'上行冲测金额之和'占'上下行冲测总额之和'的份额。"
        "机制：持续单边的事件冲测=持续的单边订单流压力，做市商库存单向积累后必须通过逆向定价出清，"
        "形成多日尺度的均值回归。与 ts_mean(A,60) 的关键区别：等权平均让59个平静日与1个事件日等权，"
        "振幅加权让大事件主导——'钱实际去了哪边'而非'平均每天哪边大'。换手率预期结构性低于日频快照。")},
    {"id": 3, "type": "CUM_IMBALANCE_20", "expression": f"reverse(divide(ts_sum({UP}, 20), add(ts_sum({UP}, 20), ts_sum({DN}, 20))))",
     "optimize_reason": (
        "20日累积不对称度：窗口扫描的短端。机制：约一个月的订单流压力窗口，对应做市商库存的典型调整周期"
        "（风险限额通常按月考核）。与槽2/4 构成 20/60/120 日三档扫描，定位累积压力的最优记忆长度——"
        "若边缘随窗口缩短而增强，说明压力出清快（月内）；若随窗口拉长而增强，说明存在慢变错误定价。")},
    {"id": 4, "type": "CUM_IMBALANCE_120", "expression": f"reverse(divide(ts_sum({UP}, 120), add(ts_sum({UP}, 120), ts_sum({DN}, 120))))",
     "optimize_reason": (
        "120日累积不对称度：窗口扫描的长端（约两个季度）。机制：覆盖完整的事件节奏周期（季报窗口/行业事件），"
        "度量半年级的持续性单边压力。风险：长窗口把早期已出清的压力混入当前信号（这正是等权平滑失败的机制），"
        "但振幅加权缓解了该问题——早期大事件的权重仍然显著。三档联合标定累积族的边缘-换手前沿。")},
    {"id": 5, "type": "CUM_NET_60", "expression": f"reverse(divide(subtract(ts_sum({UP}, 60), ts_sum({DN}, 60)), add(ts_sum({UP}, 60), ts_sum({DN}, 60))))",
     "optimize_reason": (
        "60日净不平衡（标准化差分）：(60日上行总额-下行总额)/总额，取值[-1,1]且截面均值天然接近0。"
        "机制：与槽2的比值版数学等价类但数值行为不同——净版对'上行总额=下行总额'的股票给出精确0而非0.5，"
        "截面分布以零为中心，中性化后的多头/空头分组更对称。同时净版是两个 ts_sum 的差，权重结构与比值版"
        "完全一致，可作为比值版的稳健性对照（若两版读数接近，证明结论不依赖于单调变换形式）。")},
    {"id": 6, "type": "CUM_NET_ATR_SCALED", "expression": f"reverse(divide(subtract(ts_sum({UP}, 60), ts_sum({DN}, 60)), ts_mean({ATR14}, 60)))",
     "optimize_reason": (
        "60日净冲测/60日平均ATR：累积净压力除以同期平均波动尺度，得到'累积异常压力'（约等于60日净冲测"
        "相当于多少个日常波幅）。机制：把方向A的异常度假说应用到累积维度——$10 的60日净冲测对低波股票是"
        "巨大压力、对高波股票是噪声；只有相对自身波动尺度的累积压力才值得做市商出清库存。三字段"
        "(UP/DN/ATR14)，是方向A与方向C的交叉结构。")},
    {"id": 7, "type": "CUM_INDUSTRY_MEAN", "expression": f"reverse(group_mean(divide(ts_sum({UP}, 60), add(ts_sum({UP}, 60), ts_sum({DN}, 60))), industry))",
     "optimize_reason": (
        "行业级60日累积不对称度（广播）：把个股60日累积不对称度替换为所属行业的均值并广播给每个成员。"
        "机制：行业级订单流压力是系统性注意力/流动性冲击（整个板块被资金单边追逐），其出清通过板块级轮转"
        "完成，比个股级压力更慢、更持续，且分散个股特异性噪声。与已验证的 group_rank 包装（1.37→0.71，"
        "排序稀释边缘）本质不同：组内排序保留个股相对位置（信息被重排损坏），行业均值广播是信号本身的"
        "聚合（信息被平均保存）。本槽检验'聚合保存'能否同时保住边缘并压低换手。")},
    {"id": 8, "type": "CUM_DECAY_WEIGHTED", "expression": f"reverse(divide(ts_sum(ts_decay_linear({UP}, 10), 60), add(ts_sum(ts_decay_linear({UP}, 10), 60), ts_sum(ts_decay_linear({DN}, 10), 60))))",
     "optimize_reason": (
        "衰减加权60日累积不对称度：先对每日冲测金额做10日线性衰减（近端权重高）再按60日窗口累计。"
        "机制：纯等权60日累积把61天前与昨天的压力等权，而价格压力的确随时间衰减（做市商库存逐日出清）——"
        "衰减加权是'压力'更精确的动态形式。与槽2配对可分离时间加权结构（等权vs线性衰减）的边际贡献；"
        "若衰减版显著更优，说明压力记忆确实短于60日，可沿衰减窗口继续扫描。")},
]

# ============================================================
# 方向 D: 收盘位置与回吐解剖 (Close-Location & Give-Back Anatomy)
# 假说: 事件冲测在收盘时的回吐程度直接披露买盘性质——收盘远离高点（大幅回吐）=注意力/流动性驱动
#       的过度反应（无持续买盘承接，次日延续回归）；收盘贴近高点（保住涨幅）=信息驱动（真实重定价，
#       不回归）。回吐比例是比冲测幅度更直接的'过度反应纯度'度量。另探两个正交攻击面：
#       新闻前趋势耗尽上下文、标准化回吐 excursion 差。
# ============================================================
DIR_D = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL, "optimize_reason": R_CTRL},
    {"id": 2, "type": "UP_GIVEBACK_CLOSE", "expression": f"reverse(divide(subtract({EOH}, {EOC}), {UP}))",
     "optimize_reason": (
        "上行冲测的收盘回吐比例：(新闻后最高价-收盘价)/上行冲测金额，度量'事件冲高有多少到收盘时已经回吐'。"
        "机制：回吐比例高=冲高缺乏持续买盘承接=注意力冲击型过度反应（流动性提供者被动接货后要求逆向溢价，"
        "次日延续回归）；回吐比例低=买盘持续到收盘=信息驱动的真实重定价。该结构直接度量过度反应的'纯度'，"
        "理论上比冲测幅度更贴近因果机制。三字段（EOH/EOC/UP），全部为事件日收盘后已知的合法字段。")},
    {"id": 3, "type": "DN_GIVEBACK_CLOSE", "expression": f"reverse(divide(subtract({EOC}, {EOL}), {DN}))",
     "optimize_reason": (
        "下行冲测的收盘回吐比例（下行孪生）：(收盘价-新闻后最低价)/下行冲测金额。机制：恐慌性下杀若在收盘前"
        "大幅收回了（收盘远离最低点），说明抛压是流动性/注意力驱动而非基本面恶化，次日反弹；反之收在最低点"
        "附近=真实坏消息定价。与槽2构成双向回吐解剖：若两侧都显示边缘，证明'收盘回吐'是通用的过度反应纯度"
        "度量；若只有单侧有效，说明多空两侧的过度反应机制不对称（融券约束使空侧更慢，符合预期）。")},
    {"id": 4, "type": "UP_GIVEBACK_VWAP", "expression": f"reverse(divide(subtract({EOH}, {EOV}), {UP}))",
     "optimize_reason": (
        "上行冲测相对VWAP的回吐：把槽2的收盘价基准换成新闻后VWAP。机制：收盘价是单点（易被尾盘特殊交易"
        "扰动），VWAP是全日成交量加权的平均成交价——'收盘相对VWAP的位置'比'收盘价单点'更稳健地度量"
        "持续买盘强度（VWAP之上收盘=尾盘买盘强势）。若两槽读数接近，证明结论对基准选择稳健；"
        "若VWAP版显著更优，说明应全面采用成交量加权基准。")},
    {"id": 5, "type": "DN_GIVEBACK_VWAP", "expression": f"reverse(divide(subtract({EOV}, {EOL}), {DN}))",
     "optimize_reason": (
        "下行冲测相对VWAP的回吐（下行孪生）：与槽4对称。机制同槽3但采用VWAP基准。四个回吐槽"
        "（2/3/4/5）构成完整的 2×2 设计：{上行,下行}×{收盘价,VWAP}，可完整分离方向与基准选择的主效应，"
        "是该假说族的判决性实验组合。")},
    {"id": 6, "type": "EXC_STDDEV_NET", "expression": f"reverse(subtract({HEX}, {LEX}))",
     "optimize_reason": (
        "标准化回吐净额：(高位回吐标准化值-低位回吐标准化值)。high_exc_stddev 度量最高价到收盘的回落、"
        "low_exc_stddev 度量新闻时刻价到最低点的下探，两者都是平台预标准化的 excursion 字段。净额大于0表示"
        "价格收在事件波动区间的偏上部位（买盘持续），净额小于0表示收在偏下部位（抛压持续）。作为对照组锚定"
        "已验证事实：反向单独 high_exc_stddev 的风险轮廓全场最优（Sh 0.86/DD 10.3%/rnSh 1.04），本槽检验"
        "加入低位项后能否把 0.86 推向 1.58 且保持干净的回撤轮廓。")},
    {"id": 7, "type": "PRENEWS_TREND_EXHAUST", "expression": f"reverse(divide(subtract({TONH}, {TONL}), {UP}))",
     "optimize_reason": (
        "新闻前趋势耗尽上下文：(新闻前当日最高价-新闻时刻价)/新闻后上行冲测，度量'新闻到来之前价格已经"
        "涨了多少（相对新闻后还能涨多少）'。机制：若股票在新闻前已大幅冲高、新闻后仅剩有限上行空间，"
        "说明买盘在新闻前已大量消耗（趋势耗尽），此时的事件冲测更容易是最后一批注意力资金推动的末端行情，"
        "次日回吐确定性最高；新闻前低位+新闻后大幅冲测=全新信息定价（延续）。这是把'事件反应'放回'当日"
        "价格路径上下文'的第一个探针，与全部'孤立看事件'的结构形成机制对照。")},
    {"id": 8, "type": "ABNORMAL_RANGE_GATE", "expression": f"trade_when(greater({ATRR}, 1.2), {CTRL}, 0)",
     "optimize_reason": (
        "量程异常门控（正交门控探针）：只在当日量程超过20日ATR的1.2倍（异常宽幅日）时持有对照锚的反向仓位，"
        "其余时间空仓。机制：注意力/流动性冲击在量程维度可直接识别——异常宽幅日的事件才可能触发做市商库存"
        "风险与逆向定价；平静日的不对称冲测是常态订单流，不构成可交易过度反应。与历史全部失败门控的本质区别："
        "batch3 的 A>0.75 门控与 news_vol_stddev 门控（cov 0.967，与不对称度近共线）实际上都是不对称度极端值"
        "门控，而本门控的条件变量是量程异常度——与信号本身近似正交。若本槽 |Sh|>=1.0 且 TO<=70%，"
        "将是该家族第一个同时通过 Step1 与 Step2 的形态（用极低换手换边缘损失的健康折中）。")},
]

DIRECTIONS = {
    "A": {"name": "异常度归一化", "hypothesis": "过度反应由超出个股自身波动尺度的异常冲测承载", "slots": DIR_A},
    "B": {"name": "收益空间与反应速度解剖", "hypothesis": "过度反应是收益率现象且脉冲型反应剖面披露注意力冲击", "slots": DIR_B},
    "C": {"name": "累积订单流不平衡", "hypothesis": "振幅加权多日累积单边压力未出清, 天然慢变低换手", "slots": DIR_C},
    "D": {"name": "收盘位置与回吐解剖", "hypothesis": "收盘回吐程度直接度量过度反应纯度", "slots": DIR_D},
}

STAGGER_SECONDS = {"A": 0, "B": 25, "C": 50, "D": 75}


def purge_fingerprints(exprs: list, neutralization: str):
    """回滚未真正送抵 Brain 的幻影指纹 (phase3/phase4 教训)."""
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        fixed = corrector.correct_expression(e)
        h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n} phantom records (neut={neutralization})", flush=True)


def preaudit(items: list, known_fields: list):
    corrector = ASTSandboxCorrector()
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        n_fields = len(set(t for t in audit["tokens_found"] if t in set(known_fields)))
        status = "OK" if audit["is_valid"] else "FAIL"
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']} fields={n_fields} {status} | {it['expression'][:90]}", flush=True)
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= n_fields <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {n_fields} 违反 mandate (2<=字段数<=3)")


def check_dup_fingerprints(items: list, neutralization: str):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    dups = []
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, neutralization)
        cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        row = cur.fetchone()
        if row:
            dups.append((it["id"], it["expression"][:60]))
    conn.close()
    if dups:
        print(f"  [dup-check] 历史已测 {len(dups)} 条 (<=2/批合法): {dups}", flush=True)
    if len(dups) > 2:
        raise ValueError(f"批次内历史重复 {len(dups)} 条 > 2, 防摸鱼门禁将拒: {dups}")


async def submit_with_retry(batch_path: str, items: list, state_path: str):
    """带恢复的提交: 状态文件记录 location, 崩溃可重入; 提交失败才退避重试+清幻影指纹."""
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
                    decay=DECAY, neutralization=NEUTRALIZATION, truncation=TRUNCATION,
                    pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                    language="FASTEXPR", visualization=False)
                if "error" in sub:
                    raise RuntimeError(f"submit error: {sub}")
                location = sub["location"]
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump({"location": location, "submitted_at": int(time.time())}, f)
                print(f"[submit] OK location={location}", flush=True)
                break
            except Exception as e:
                print(f"[submit] attempt {attempt}/5 failed: {str(e)[:200]}", flush=True)
                purge_fingerprints(exprs, NEUTRALIZATION)
                if attempt == 5:
                    raise
                await asyncio.sleep(30)
    # 轮询 (前 60s 静默, 之后 20s 间隔; RATE_LIMITED 退避)
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
        row = {
            "slot": it["id"], "type": it["question_type"], "expression": it["expression"],
            "alpha_id": r.get("alpha_id"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": m.get("turnover"), "returns": m.get("returns"),
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
    summary = {
        "direction": direction, "direction_name": DIRECTIONS[direction]["name"],
        "hypothesis": DIRECTIONS[direction]["hypothesis"],
        "settings": {"neutralization": NEUTRALIZATION, "decay": DECAY, "truncation": TRUNCATION,
                      "region": REGION, "universe": UNIVERSE, "delay": DELAY, "nan_handling": NAN_HANDLING},
        "rows": rows,
        "gate": {"step1": step1, "step2_count": len(step2), "final_count": len(final),
                  "step2": step2, "final": final},
    }
    return summary


def print_table(summary: dict):
    print(f"\n===== Gate1 方向 {summary['direction']} ({summary['direction_name']}) 结果 =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"{'槽':>2} {'类型':<22} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'Mgn(bp)':>8} {'DD%':>6} {'2Y':>6} {'rnSh':>6} {'L/S':>9} {'fail':<28} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:22]:<22} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {r['margin_bps'] or 0:>8.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['rn_sharpe'] or 0:>6.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:28]:<28} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)


async def main():
    direction = sys.argv[1].strip().upper()
    if direction not in DIRECTIONS:
        print(f"用法: python phase5_gate1_multiangent.py <A|B|C|D>"); sys.exit(1)
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Gate1-{direction}] {DIRECTIONS[direction]['name']} | 假说: {DIRECTIONS[direction]['hypothesis']}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Gate1-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1_{direction}_{s['id']}", "question_type": s["type"]} for s in DIRECTIONS[direction]["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, NEUTRALIZATION)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate1_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate1_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1_{direction}", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Gate1-{direction}] 批次文件: {batch_path}", flush=True)

    # 本地审计 + 指纹 (与 SimBatchRunner 同序, 保证先审后录, 杜绝幻影指纹)
    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, UNIVERSE, DELAY, NEUTRALIZATION)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1_{direction}", "region": REGION, "universe": UNIVERSE,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], NEUTRALIZATION)
        print(f"[Gate1-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Gate1-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate1_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Gate1-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
