# -*- coding: utf-8 -*-
"""Gate1 Wave2 多 agent 优化驱动 (2026-10-24).

Wave1 判决 (32 槽):
  A 异常度归一化 -> 证伪 (best 0.94, 对照 1.37)
  B 收益空间/反应速度 -> 证伪 (ret 版 1.38 等价锚; pct_* 速度差全死)
  C 累积订单流 -> 未测 (BRAIN 侧 group_mean 参数错误连坐取消, 指纹已回滚)
  D 收盘回吐 -> 证伪 (best 0.74; trade_when 门控杀死边缘)
锚: Sh1.37/Fit0.31/TO129.9%/Ret6.57%/2Y1.68/Sub1.0/rnSh1.65/DD8.4%
三重墙: Sh<1.58, Fit<1.0 (TO 地板公式), TO>70%.

Wave2 四路 (每路 8 槽, 槽1 均为对照锚):
  E 降换手结构总攻: 多日累积订单流 (20/60/120) + 末次事件回填 (5/20/60) + 行业级累积
    假说: 过度反应压力以"未出清的累积单边流"形式存在, 天然慢变低换手;
          回填版把"最近一次事件的不对称度"作为持续持仓先验 (与 ts_mean 混合平滑本质不同:
          回填不稀释事件日纯度)。
  F 新字段族: 速度不对称 (到 1%/2% 涨跌耗时比) + 20 日平滑速度不对称 + 基准相对超额 +
    跳空+冲测总过度反应 + 新闻前区间位置 + 事前趋势x不对称度交互
    假说: 过度反应的注意力机制表现为"涨快跌慢"的时间不对称; 基准相对运动剔除非特异性市场波动。
  G 中性化消融 (MARKET): 对 Wave1 已知最佳结构族放宽行业约束
    假说: INDUSTRY 约束剥掉了信号自带的行业轮动边缘 (AMR 战役 SUBIND->INDUSTRY->MARKET 单调提 Sh)。
  H Universe 消融 (TOP500): 大市值池的事件排名更持续 -> 结构性降换手
    假说: 大盘股的事件反应更慢消退, 排名持续性更强, TO 结构性下降。
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

# 字段速记
U, D = "news_max_up_amt", "news_max_dn_amt"
UR, DR = "news_max_up_ret", "news_max_dn_ret"
ATRR, ATR14 = "news_atr_ratio", "news_atr14"
EOH, EOV, EOL, EOC = "news_eod_high", "news_eod_vwap", "news_eod_low", "news_eod_close"
HEX, LEX = "news_high_exc_stddev", "news_low_exc_stddev"
M1U, M1D = "minutes_to_one_pct_up_move_1555", "minutes_to_one_pct_down_move_1555"
M2U, M2D = "minutes_to_two_pct_up_move_1555", "minutes_to_two_pct_down_move_1555"
RPB, PDC, GAP = "relative_performance_vs_benchmark_1555", "previous_day_percent_change", "opening_gap_percent"
PAT, LPB, HPN = "main_price_at_news_time", "lowest_price_before_event", "highest_price_pre_news"

CTRL = f"reverse(divide({U}, add({U}, {D})))"
ARAW = f"divide({U}, add({U}, {D}))"  # 未反向的原始不对称度比值 (供回填/交互结构正确复用)

# ---------------------------------------------------------------- 方向 E: 降换手结构总攻
DIR_E = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL,
     "optimize_reason": (
        "对照锚 (Wave1 三批实测稳定在 Sh1.37/TO129.9%/2Y1.68)。本批一切降换手结构都以它为基准校准: "
        "任何新结构的 TO 下降必须相对于本锚读数解释, Sh 保留率 = 新结构Sh/1.37。")},
    {"id": 2, "type": "CUM_IMBALANCE_20", "expression": f"reverse(divide(ts_sum({U}, 20), add(ts_sum({U}, 20), ts_sum({D}, 20))))",
     "optimize_reason": (
        "20 日振幅加权累积订单流不平衡度。机制: 把'最近一次事件的上行冲测占比'升级为'过去 20 个交易日内"
        "全部事件冲测中上行占比'——若过度反应压力以未出清的累积形式存在, 该比值应持续预测反向收益。"
        "累积求和天然慢变: 单日事件只占 1/20 权重, 预期 TO 从 130% 数量级下降。"
        "与 ts_mean(A,20) 的本质区别: 那是先取比值再平均 (混合不同事件的比值), 这是先累积振幅再取比值"
        "(保留振幅加权结构), 且分母同步累积自动归一化。")},
    {"id": 3, "type": "CUM_IMBALANCE_60", "expression": f"reverse(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))))",
     "optimize_reason": (
        "60 日版 (一个季度的订单流压力窗口)。机制同槽2, 窗口扫描的中点。"
        "若边缘存在于 20 日但不存在于 60 日, 说明压力出清周期约一个月; 若两窗口都存活, "
        "取保留率最高且 TO 最低的窗口作为主结构。")},
    {"id": 4, "type": "CUM_IMBALANCE_120", "expression": f"reverse(divide(ts_sum({U}, 120), add(ts_sum({U}, 120), ts_sum({D}, 120))))",
     "optimize_reason": (
        "120 日版 (半年订单流压力)。机制同槽2, 窗口扫描的长端。"
        "120 日窗口下 TO 预期降至 10-20% 区间 (正好落入 Fit 地板公式的甜蜜区 TO<=12.5%), "
        "是全部候选中唯一可能同时满足低换手与 Fit 地板的形态; 风险是边缘被长窗口稀释。")},
    {"id": 5, "type": "LASTEVENT_BACKFILL_5", "expression": f"reverse(ts_backfill({ARAW}, 5))",
     "optimize_reason": (
        "末次事件回填 5 日: 非事件日沿用最近一次事件的不对称度, 最多持续 5 个交易日。"
        "机制: 对照锚在非事件日为 NaN (被 nan_handling 剔除, 故每日仅约 500 只事件股可交易、TO 130%); "
        "回填把'最近一次事件的过度反应判决'变成持续 5 日的持仓先验——不混合多个事件 (与 ts_mean 的本质区别), "
        "只延用最近一次的纯度。预期 TO 降约 4-5 倍而事件日边缘完整保留。")},
    {"id": 6, "type": "LASTEVENT_BACKFILL_20", "expression": f"reverse(ts_backfill({ARAW}, 20))",
     "optimize_reason": (
        "末次事件回填 20 日 (一个月持仓先验)。机制同槽5, 回填窗口中点。"
        "20 日回填使每日可交易标的从约 500 只扩到'月内有事件'的全部股票 (预期 800+), "
        "集中度风险 (CW) 同步下降——这是同时攻 TO 与 CW 两个失败项的结构。"
        "关键判决: 若 Sh 保留率 >60% 且 TO<=25%, 回填族即为 Gate1 主攻方向。")},
    {"id": 7, "type": "LASTEVENT_BACKFILL_60", "expression": f"reverse(ts_backfill({ARAW}, 60))",
     "optimize_reason": (
        "末次事件回填 60 日 (一季度持仓先验)。机制同槽5, 回填窗口长端。"
        "60 日回填预期把 TO 压到 10% 以下 (Fit 地板全保护), 但陈旧信号的稀释也最重——"
        "本槽测量回填族的边缘-换手权衡曲线终点, 与槽5/6 三点定出最优回填窗口。")},
    {"id": 8, "type": "CUM_INDUSTRY_LEVEL", "expression": f"reverse(group_mean(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))), 1, industry))",
     "optimize_reason": (
        "行业级 60 日累积订单流不平衡 (3 参 group_mean(x, weight, group), 修正 Wave1-C 批的参数错误)。"
        "机制: 把个股累积压力聚合到行业层——若过度反应是行业级别的注意力轮动 (板块性事件潮), "
        "行业级信号的换手率天然低于个股级 (行业聚合平滑个股噪声), 且不受个股事件稀疏性影响。"
        "本槽同时检验'行业轮动'假说, 与槽3 的个股版形成层级对照。")},
]

# ---------------------------------------------------------------- 方向 F: 新字段族
DIR_F = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL,
     "optimize_reason": "对照锚, 同上。新字段族的任何发现都以本锚的 Sh1.37/TO129.9% 为基准解释。"},
    {"id": 2, "type": "SPEED_ASYM_1PCT", "expression": f"reverse(divide({M1D}, add({M1D}, {M1U})))",
     "optimize_reason": (
        "速度不对称 (1% 阈值): 下跌耗时占 (下跌耗时+上涨耗时) 的比例, 反向。"
        "机制: 注意力驱动的过度反应在时间维度留下指纹——上行 1% 耗时相对越短 (分母中上涨项越小、比值越大), "
        "说明买盘是脉冲式注意力冲击而非渐进信息定价, 次日回归确定性越高; 做空该类股票。"
        "分钟数比值是无量纲的, 跨股票可比; 与振幅不对称度 (锚) 是同一机制的两个正交度量维度: "
        "锚度量'冲了多高', 本槽度量'冲得多快'。")},
    {"id": 3, "type": "SPEED_ASYM_2PCT", "expression": f"reverse(divide({M2D}, add({M2D}, {M2U})))",
     "optimize_reason": (
        "速度不对称 (2% 阈值): 同槽2 但阈值提高到 2%, 度量更极端注意力冲击的速度指纹。"
        "机制: 2% 移动需要更强的注意力凝聚; 若 2% 版保留率显著高于 1% 版, 说明过度反应机制"
        "只在极端注意力水平激活 (支持'脉冲式冲击'假说); 若两版等价, 说明机制对阈值稳健。")},
    {"id": 4, "type": "SPEED_ASYM_20D", "expression": f"reverse(divide(ts_mean({M1D}, 20), add(ts_mean({M1D}, 20), ts_mean({M1U}, 20))))",
     "optimize_reason": (
        "20 日平滑速度不对称: 对槽2 的涨跌耗时做 20 日均值后再取比值。"
        "机制: 直接检验速度不对称边缘是瞬态 (仅事件日) 还是持续 (一个月内稳定)。"
        "这是本批最高信息量的一槽: 若 20 日平滑后 Sh 保留率 >50% 且 TO 大幅下降, "
        "速度族就是攻破 Fit 墙的主结构 (慢变+有边缘); 若保边率崩塌, 则证明速度边缘与锚同属瞬态, "
        "全部降换手希望转向累积/回填族 (E 批)。")},
    {"id": 5, "type": "EXCESS_2DAY_REVERSAL", "expression": f"reverse(add({RPB}, {PDC}))",
     "optimize_reason": (
        "两日累计基准相对超额的反转: (事件日相对 SPY 超额 + 前一日全日涨跌幅) 取反。"
        "机制: 把过度反应的度量从'事件日内上行冲测占比'换成'连续两日相对市场的累计超额位移'——"
        "基准相对字段剔除了市场整体涨跌带来的非特异性位移 (市场大跌日的所有股票都跌, 那不叫过度反应)。"
        "若该极简结构 (2 字段 2 算子) 就能达到锚的 Sh 量级, 说明过度反应的实质就是累计超额回归, "
        "且基准相对化可能同时压低 prod correlation (与纯事件快照族不同的风险暴露)。")},
    {"id": 6, "type": "GAP_PLUS_SPIKE", "expression": f"reverse(add({GAP}, {UR}))",
     "optimize_reason": (
        "跳空+盘中冲测的总过度反应幅度: 开盘跳空百分比 + 新闻后上行冲测百分比, 取反。"
        "机制: 隔夜跳空度量 overnight 注意力的第一波定价, 盘中冲测度量日内注意力的第二波, "
        "两者之和近似'从前收盘到事件后最高点的总上行压力'。做多日累计上行压力最大的股票次日回归。"
        "与锚的区别: 锚只看日内上行占比 (无量纲), 本槽看总上行幅度 (有量纲但跨日用 % 统一), "
        "且本槽对'跳空高开+回落'与'平开+冲高'两种过度反应形态都敏感。")},
    {"id": 7, "type": "PRENEWS_RANGE_POS", "expression": f"reverse(divide(subtract({PAT}, {LPB}), subtract({HPN}, {LPB})))",
     "optimize_reason": (
        "新闻到达时的事前区间位置: (新闻时刻价-事前最低)/(事前最高-事前最低), 取反。"
        "机制: 同样的利好, 到达在事前区间顶部 vs 底部经济含义相反——顶部=买盘在新闻前已大量消耗"
        "(趋势耗尽, 事件冲测更可能是末端注意力行情, 次日回吐确定性最高); 底部=全新信息定价起点 (延续)。"
        "这是把'事件反应'放回'当日价格路径上下文'的第二个探针 (Wave1-D 槽7 已测 ton 趋势耗尽版但被回吐族证伪背景污染), "
        "本槽用无量纲区间位置, 与振幅/速度/回吐全部正交。")},
    {"id": 8, "type": "TREND_x_ASYM_INTERACT", "expression": f"reverse(multiply(rank({ARAW}), rank({PDC})))",
     "optimize_reason": (
        "事前趋势 x 事件不对称度交互: 两个 rank 化后相乘再取反。"
        "机制: 书面交互假说——'事件日上行不对称'与'事前一日已上涨'同时成立时, 过度反应最强"
        "(趋势耗尽: 买盘存量已被消耗, 事件只是最后一批注意力资金)。单看任一条件都不足, "
        "乘积项只对两者同时极端的股票给出大权重。rank 化保证两侧无量纲可比、符号不互相污染。")},
]

# ---------------------------------------------------------------- 方向 G: 中性化消融 (MARKET)
DIR_G = [
    {"id": 1, "type": "CTRL_MARKET", "expression": CTRL,
     "optimize_reason": (
        "对照锚 @MARKET 中性化。机制: INDUSTRY 约束把行业均值剔掉, 若信号边缘部分来自行业层"
        "注意力轮动, MARKET 放宽后 Sh 应上升 (AMR 战役实测 SUBIND0.68->INDUSTRY0.74->MARKET0.81 单调)。"
        "风险: 放宽约束使行业集中赌注浮现, CW 可能反弹——本槽同时是 MARKET 的 CW 安全边际探测。")},
    {"id": 2, "type": "RET_ASYM_MARKET", "expression": f"reverse(divide({UR}, add({UR}, {DR})))",
     "optimize_reason": (
        "收益率版不对称度 @MARKET (Wave1-B 槽2, INDUSTRY 下与锚等价 Sh1.38)。"
        "机制: 金额版与收益率版在 INDUSTRY 下读数一致, 但在 MARKET 下可能分化——"
        "金额版隐含'波动大的股票权重大'的暴露, 收益率版是纯百分比。若 MARKET 下收益率版显著更优, "
        "说明应全面转向收益率度量 (去除规模暴露)。")},
    {"id": 3, "type": "RET_NET_MARKET", "expression": f"reverse(subtract({UR}, {DR}))",
     "optimize_reason": (
        "收益率净差额 @MARKET (Wave1-B 槽3, INDUSTRY 下 Sh0.78)。"
        "机制: 无分母归一化的原始差额版, 保留幅度信息。INDUSTRY 下它弱于比值版 (0.78 vs 1.38), "
        "但 MARKET 约束下行业间幅度差异被保留, 可能逆转排序——检验'归一化是否有行业依赖性'。")},
    {"id": 4, "type": "EXC_STDDEV_MARKET", "expression": f"reverse(subtract({HEX}, {LEX}))",
     "optimize_reason": (
        "标准化回吐净额 @MARKET (Wave1-D 槽6, INDUSTRY 下 Sh0.74/DD10.5%/2Y1.51, 全场最优非锚风险轮廓)。"
        "机制: 该结构的风险轮廓 (低回撤) 与锚互补, 若 MARKET 中性化能把它的 Sh 从 0.74 推向 1.0+, "
        "它可能比锚更适合作为 Gate1 主结构 (风险调整维度更干净)。")},
    {"id": 5, "type": "ATR_SCALED_MARKET", "expression": f"reverse(divide(subtract({U}, {D}), {ATRR}))",
     "optimize_reason": (
        "ATR 归一化不对称度 @MARKET (Wave1-A 槽3, INDUSTRY 下 Sh0.94/2Y0.05)。"
        "机制: 异常度归一化族在 INDUSTRY 下被证伪, 但归一化与中性化存在交互——MARKET 不控行业, "
        "行业间波动率差异可能正是该结构失效的原因; 换约束后重新检验可分离'归一化无效'与'行业暴露污染'两种解释。")},
    {"id": 6, "type": "ATR14_SCALED_MARKET", "expression": f"reverse(divide(subtract({U}, {D}), {ATR14}))",
     "optimize_reason": (
        "ATR14 绝对值归一化 @MARKET (Wave1-A 槽2, INDUSTRY 下 Sh0.70)。"
        "机制: 与槽5 构成归一化分母对照 (比率 vs 绝对值), 在 MARKET 下同时重测。"
        "两槽若在 MARKET 下都显著回升, 说明 A 族证伪结论依赖 INDUSTRY 设定, 需修正 falsified_vault。")},
    {"id": 7, "type": "DN_GIVEBACK_MARKET", "expression": f"reverse(divide(subtract({EOC}, {EOL}), {D}))",
     "optimize_reason": (
        "下行回吐纯度 @MARKET (Wave1-D 槽3, INDUSTRY 下 Sh0.61)。"
        "机制: 收盘相对当日低位的回升占下行冲测的比例——下行冲测后收回越多, 恐慌抛售越是被过度反应。"
        "MARKET 下重测: 该结构的边缘可能来自行业间恐慌修复的时间差 (行业层信号), 恰是 MARKET 保留的边缘。")},
    {"id": 8, "type": "TSMEAN_SCALED_MARKET", "expression": f"reverse(divide(subtract({U}, {D}), ts_mean(add({U}, {D}), 60)))",
     "optimize_reason": (
        "自身 60 日振幅均值归一化 @MARKET (Wave1-A 槽5, INDUSTRY 下 Sh0.75)。"
        "机制: 用个股自身 60 日平均冲测幅度做分母 (慢变归一化基准, 不同于 ATR 的市场化基准)。"
        "与槽5/6 共同构成归一化分母三材质 (市场ATR比率/自身ATR/自身历史均值) 在 MARKET 下的完整消融。")},
]

# ---------------------------------------------------------------- 方向 H: Universe TOP500
DIR_H = [
    {"id": 1, "type": "CTRL_TOP500", "expression": CTRL,
     "optimize_reason": (
        "对照锚 @TOP500。机制: 大盘股池的事件反应更慢消退 (流动性深度吸收冲击), 排名持续性更强, "
        "预期 TO 结构性下降; 同时大市值池的 margin 通常更高 (流动性溢价)。"
        "本槽测量换 universe 对锚的三维影响 (Sh/TO/Margin), 是 H 批全部结论的基准。")},
    {"id": 2, "type": "RET_ASYM_TOP500", "expression": f"reverse(divide({UR}, add({UR}, {DR})))",
     "optimize_reason": (
        "收益率版不对称度 @TOP500。机制: 金额版在大市值池被市值规模加权 (大股票冲测金额天然大), "
        "收益率版剔除规模效应——TOP500 内市值差异仍有一个数量级, 两版分化会比 TOP1000 更明显, "
        "本槽直接检验'收益率版在大池更优'的推断。")},
    {"id": 3, "type": "EXC_STDDEV_TOP500", "expression": f"reverse(subtract({HEX}, {LEX}))",
     "optimize_reason": (
        "标准化回吐净额 @TOP500 (全场最优非锚风险轮廓)。"
        "机制: 该结构的边缘可能集中于流动性较好的大股票 (回吐度量需要足够的日内价格路径细节), "
        "TOP500 池可能同时提升 Sh 与 DD; 若成立, 它与 TOP500 是天然配对。")},
    {"id": 4, "type": "ATR_SCALED_TOP500", "expression": f"reverse(divide(subtract({U}, {D}), {ATRR}))",
     "optimize_reason": (
        "ATR 归一化不对称度 @TOP500。机制: 归一化族在 TOP1000 证伪, 但 TOP500 的波动率分布更窄"
        "(大市值低波), 归一化的边际影响更小, 可能暴露被掩盖的边缘; 同时检验证伪结论的 universe 依赖性。")},
    {"id": 5, "type": "CUM60_TOP500", "expression": f"reverse(divide(ts_sum({U}, 60), add(ts_sum({U}, 60), ts_sum({D}, 60))))",
     "optimize_reason": (
        "60 日累积订单流 @TOP500 (与 E 批槽3 同结构, 跨 universe 联合探测)。"
        "机制: 累积族的换手下降 + TOP500 的排名持续性下降可能叠加, 把 TO 压到 12.5% 甜蜜区; "
        "若 E 批显示累积族有边缘而 TOP1000 下 TO 仍高, 本槽是'累积x大池'的联合解。")},
    {"id": 6, "type": "BACKFILL20_TOP500", "expression": f"reverse(ts_backfill({ARAW}, 20))",
     "optimize_reason": (
        "20 日末次事件回填 @TOP500 (与 E 批槽6 同结构, 跨 universe 联合探测)。"
        "机制: 回填扩池 + TOP500 高持续性双重作用下, 陈旧先验的稀释可能更慢; "
        "本槽测量回填族在大池的边缘保留率, 与 E 批槽6 联合定出 (结构, universe) 二维最优。")},
    {"id": 7, "type": "ATR14_SCALED_TOP500", "expression": f"reverse(divide(subtract({U}, {D}), {ATR14}))",
     "optimize_reason": (
        "ATR14 绝对值归一化 @TOP500。机制: 同槽4 的归一化分母材质对照 (绝对值 vs 比率), "
        "在大池重测。两槽共同完成'归一化族 x universe'的 2x2 消融设计。")},
    {"id": 8, "type": "DN_GIVEBACK_TOP500", "expression": f"reverse(divide(subtract({EOC}, {EOL}), {D}))",
     "optimize_reason": (
        "下行回吐纯度 @TOP500。机制: 大市值股的日内价格路径更连续 (跳空少), 回吐度量噪声更小; "
        "若该结构在 TOP500 显著优于 TOP1000 的 0.61, 说明回吐族需要大池的路径质量才能显现。")},
]

DIRECTIONS = {
    "E": {"name": "降换手结构总攻", "hypothesis": "过度反应压力以未出清的累积单边流/末次事件先验形式存在, 天然慢变低换手",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_E},
    "F": {"name": "新字段族: 速度不对称与基准相对", "hypothesis": "过度反应的注意力机制表现为涨快跌慢的时间不对称; 基准相对运动剔除非特异性波动",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_F},
    "G": {"name": "中性化消融 MARKET", "hypothesis": "INDUSTRY 约束剥掉信号自带行业轮动边缘, 放宽到 MARKET 应提 Sh",
          "universe": "TOP1000", "neutralization": "MARKET", "slots": DIR_G},
    "H": {"name": "Universe 消融 TOP500", "hypothesis": "大盘股池事件反应慢消退、排名持续性强, TO 结构性下降且 margin 更高",
          "universe": "TOP500", "neutralization": "INDUSTRY", "slots": DIR_H},
}

STAGGER_SECONDS = {"E": 0, "F": 25, "G": 50, "H": 75}


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
    print(f"\n===== Gate1-Wave2 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
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
        print(f"用法: python phase6_gate1_wave2.py <E|F|G|H>"); sys.exit(1)
    d = DIRECTIONS[direction]
    universe, neutralization = d["universe"], d["neutralization"]
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Wave2-{direction}] {d['name']} | 假说: {d['hypothesis']}", flush=True)
    print(f"[Wave2-{direction}] 设置: universe={universe} neut={neutralization} decay={DECAY} trunc={TRUNCATION}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave2-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W2_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, neutralization, universe)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate2_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate2_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W2_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave2-{direction}] 批次文件: {batch_path}", flush=True)

    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, universe, DELAY, neutralization)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W2_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path, neutralization, universe)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], neutralization, universe)
        print(f"[Wave2-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave2-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate2_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave2-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
