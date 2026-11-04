# -*- coding: utf-8 -*-
"""Gate1 Wave3 多 agent 优化驱动 (2026-10-24).

Wave2 判决 (32 槽, 已全量回收):
  E 降换手总攻 -> 累积订单流证伪 (cum20/60/120 = 0.07/0.06/-0.16, TO 15/8/6%)
                 末次事件回填保边 80% (bf5 Sh1.10/TO53%, bf20 Sh1.06/TO37.7%, bf60 Sh1.10/TO37.2%)
                 行业级累积 Ret 最高 7.11% 但 Sh0.57/DD34% (行业轮动假说证伪)
  G MARKET 中性化 -> 证伪 (CTRL 1.13 < INDUSTRY 1.37; 8 槽全 0.58-1.13)
  H TOP500 universe -> 证伪 (CTRL 1.10 < TOP1000 1.37; TO 未结构性下降 121%)
  F VECTOR 字段直接算子 -> 操作错误 (7 ERROR+1 CANCELLED, 已取证回滚)

🔴 本轮重大发现 (24 行精确吻合): Mgn_bps = 20 x Ret%/TO%  (USA, d1, 全 neut/universe)
   => Margin>=10bps 死线 <=> Ret >= 0.5*TO; 又 Fit = Sh*sqrt(Ret/max(TO,0.125))
   => 沿 margin 边界 Fit = 0.707*Sh, Sh>=1.58 主导 => 一致解集:
      {Sh>=1.58, Ret>=0.5*TO, TO in [5,50], 2Y>=1.58, Sub>=1.58}
   家族实测 Ret/TO: 锚 0.0506 / bf20 0.0926 / bf60 0.0965 / cum-industry 0.1254
   => 距 margin 死线 4-10 倍差距; 每个槽必须同时读出 Ret/TO 与边际缺口。

Wave3 四路 (每路 8 槽):
  I 速度不对称族: 同一过度反应机制的正交度量维度 (锚度量'冲多高', 本族度量'冲多快')
     分钟到阈值耗时比 (3/4/5/20% 阈值扫描) + 回填版 + 日内快窗/慢窗对比
  J 条件化过度反应: trade_when 门控把书库集中到过度反应假说预测最强的股票子集
     (高PE/高SI/小市值/高关注度高波动), 退出分支 0(平仓) vs -1(粘性持有) 对照
  K 解耦与秩包装: 事件振幅/事件日收盘价 vs 自身近期常态 (biasfree/news102 跨族复用模板)
     + rank/group_rank 包装 + 回填 120/250 长窗 + 行业广播
  L VECTOR 探针: vec_* 归约管道 (修正 F 批直接算子错误) 测 800 个 VECTOR 字段中的
     高覆盖族 (excursion stddev / 分钟到阈值 / 会话路径 / 量比)
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
EOC = "news_eod_close"
ATRR, ATR14 = "news_atr_ratio", "news_atr14"
PE, SI, CAP, DY, RV = "news_pe_ratio", "news_short_interest", "news_cap", "news_dividend_yield", "news_ratio_vol"
M3U, M3D = "news_mins_3_pct_up", "news_mins_3_pct_dn"
M4U, M4D = "news_mins_4_pct_up", "news_mins_4_pct_dn"
M5U, M5D = "news_mins_5_pct_up", "news_mins_5_pct_dn"
M20U, M20D = "news_mins_20_pct_up", "news_mins_20_pct_dn"
P30S, P1M, P120M = "news_pct_30sec", "news_pct_1min", "news_pct_120min"
V4U, V4D = "minutes_to_4pct_increase", "minutes_to_4pct_decline"
V2U, V2D = "minutes_to_2pct_increase", "minutes_to_2pct_decline"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"
VHD1555, VLD1555 = "high_price_deviation_std_1555", "low_price_deviation_std_1555"
VSR, VATR = "main_session_price_range", "average_true_range_14d"
VVWAP, VCLOSE = "end_of_day_vwap_2", "end_of_session_close_price"
VCVR = "current_to_average_volume_ratio_2"

CTRL = f"reverse(divide({U}, add({U}, {D})))"
ARAW = f"divide({U}, add({U}, {D}))"
S4 = f"divide({M4U}, add({M4U}, {M4D}))"
S20 = f"divide({M20U}, add({M20U}, {M20D}))"
S3 = f"divide({M3U}, add({M3U}, {M3D}))"
S5 = f"divide({M5U}, add({M5U}, {M5D}))"
RU = f"ts_backfill(divide({U}, {EOC}), 60)"
RD = f"ts_backfill(divide({D}, {EOC}), 60)"
BF = f"ts_backfill({ARAW}, 60)"

# ---------------------------------------------------------------- 方向 I: 速度不对称族
DIR_I = [
    {"id": 1, "type": "SPEED_ASYM_4PCT", "expression": f"reverse({S4})",
     "optimize_reason": (
        "速度不对称 (4% 阈值): 上涨到 4% 耗时占 (涨耗时+跌耗时) 比例, 反向。"
        "机制: 注意力驱动的过度反应在时间维度留下与振幅正交的指纹——若价格以脉冲式速度冲高"
        "(涨耗时极短) 而回落缓慢, 买盘是注意力冲击而非渐进信息定价, 次日回归确定性最高; "
        "与锚 '冲了多高' 构成同一机制的两个度量维度 (振幅 vs 速度), 这是本战役第一个"
        "真正新的测量轴。分钟耗时比无量纲跨股可比。")},
    {"id": 2, "type": "SPEED_ASYM_20PCT", "expression": f"reverse({S20})",
     "optimize_reason": (
        "速度不对称 (20% 阈值): 同槽1 但阈值提高到 20%, 只度量最极端注意力冲击的时间指纹。"
        "阈值扫描的经济含义: 4% 捕捉普通事件反应, 20% 只保留'暴力冲测'事件——"
        "若边缘随阈值上升而增强, 说明过度反应是极端事件的专属现象; 若衰减, 说明是普遍现象。")},
    {"id": 3, "type": "SPEED_ASYM_3PCT", "expression": f"reverse({S3})",
     "optimize_reason": (
        "速度不对称 (3% 阈值): 阈值扫描下端点。3%/4%/5%/20% 四点定出速度不对称的阈值响应曲线,"
        "与锚的振幅不对称形成 (阈值 x 维度) 二维度量网格。")},
    {"id": 4, "type": "SPEED_ASYM_5PCT", "expression": f"reverse({S5})",
     "optimize_reason": (
        "速度不对称 (5% 阈值): 阈值扫描中点。机制同槽1/3, 补齐四点扫描。"
        "注意 5% 阈值覆盖率为 0.921/0.847 (涨/跌不对称), 若信号强度异常需归因于覆盖率差异。")},
    {"id": 5, "type": "SPEED_ASYM_4PCT_BF60", "expression": f"reverse(ts_backfill({S4}, 60))",
     "optimize_reason": (
        "4% 速度不对称 + 60 日末次事件回填。机制: E 批已证 '末次事件先验' 是家族唯一保边结构"
        "(Sh 保留 80%, TO 从 130% 降到 37%); 本槽把该结构移植到速度维度——若速度不对称本身有边缘, "
        "回填版给出它的低换手形态, 直接读出 Ret/TO 与 margin 死线的距离。")},
    {"id": 6, "type": "SPEED_ASYM_20PCT_BF60", "expression": f"reverse(ts_backfill({S20}, 60))",
     "optimize_reason": (
        "20% 速度不对称 + 60 日回填: 暴力冲测事件的持续先验。机制同槽5, 阈值取最极端档。"
        "若暴力事件的速度指纹在回填后仍保留, 它是'高信念持仓'的天然候选 (边缘集中、换手低)。")},
    {"id": 7, "type": "DRIFT_MINUS_SPIKE", "expression": f"reverse(subtract({P120M}, {P30S}))",
     "optimize_reason": (
        "持续漂移减开盘尖峰: 2 小时累计涨跌减前 30 秒涨跌, 反向。"
        "机制: 注意力冲击的形态学指纹——若 30 秒尖峰大于 2 小时漂移, 买盘集中在新闻瞬间"
        "(脉冲式注意力, 无持续信息内容), 随后回落; 反向做空该类。反之漂移大于尖峰 = "
        "渐进信息定价 (有内容), 买入。本槽把'快慢对比'从耗时切换到涨跌幅空间, "
        "与槽1-6 的时间轴度量互补。减法保号, 无除零风险。")},
    {"id": 8, "type": "IMMEDIATE_POP_SUM", "expression": f"reverse(add({P30S}, {P1M}))",
     "optimize_reason": (
        "即时弹升合计: 前 30 秒 + 前 1 分钟涨跌之和, 反向。"
        "机制: 两个相邻快窗的同经济量变体求和 (白名单 add 用法), 构造最纯净的'新闻瞬间"
        "注意力脉冲'度量——若该合计预示次日回落, 是注意力过度反应假说最直接的证据; "
        "且快窗度量天然比全天度量更早出清, 换手结构可能优于锚。")},
]

# ---------------------------------------------------------------- 方向 J: 条件化过度反应门控
DIR_J = [
    {"id": 1, "type": "CONTROL_ANCHOR", "expression": CTRL,
     "optimize_reason": (
        "对照锚 (Wave1/Wave2 稳定 Sh1.37/TO129.9%/Ret6.57%/2Y1.68/Sub1.0)。"
        "本批一切门控结构都以它为基准: 门控的 Sh 变化 = 条件化假说的净增量, "
        "TO 下降 = 集中度红利, 两个读数必须同时解释。")},
    {"id": 2, "type": "PE_GATE_FLAT", "expression": f"trade_when(greater(rank({PE}), 0.8), {CTRL}, 0)",
     "optimize_reason": (
        "高市盈率门控 (平仓退出): 仅当股票 PE 处于当日横截面前 20% 时持有锚定反向仓位, 否则空仓。"
        "机制 (条件化过度反应): 高 PE = 高估值/高关注度/高散户参与——过度反应理论预测反转"
        "强度随'关注度 x 估值'上升; 若假说成立, 门控后 Sh 应显著高于 1.37 且持仓数从 ~148 降到 ~30, "
        "TO 同步下降。平仓退出 (第三参 0) 是基线版, 与槽3 的粘性退出构成退出语义对照。")},
    {"id": 3, "type": "PE_GATE_STICKY", "expression": f"trade_when(greater(rank({PE}), 0.8), {CTRL}, -1)",
     "optimize_reason": (
        "高市盈率门控 (粘性退出): 同槽2 但条件不满足时保持昨日仓位而非清空。"
        "机制: 第三参 -1 把'事件日判决'变成持续持仓——非事件日条件为假, 仓位自动延续, "
        "等价于内建回填; 这是同时攻 TO (预期降到 20-40%) 与 Ret/TO (margin 死线) 的结构。"
        "本槽是 margin 数学墙的核心攻击点: 若 Sh 保留 >70% 且 TO<40%, Ret/TO 将首次接近 0.2+。")},
    {"id": 4, "type": "SI_GATE_STICKY", "expression": f"trade_when(greater(rank({SI}), 0.8), {CTRL}, -1)",
     "optimize_reason": (
        "高空头兴趣门控 (粘性): 仅高 SI (卖空/流通股) 股票持有反向仓位。"
        "机制: 高 SI 股票的事件后上行更可能触发空头回补 (挤压) 而非注意力买入——"
        "若过度反应假说对高 SI 股票失效 (Sh 塌) 而对低 SI 成立, 则槽4 与槽2 的差值"
        "直接分离'注意力过度反应'与'空头挤压'两种机制, 是本次门控族最重要的机制判别槽。")},
    {"id": 5, "type": "SMALLCAP_GATE_STICKY", "expression": f"trade_when(less(rank({CAP}), 0.2), {CTRL}, -1)",
     "optimize_reason": (
        "小市值门控 (粘性): 仅市值后 20% 的股票持有反向仓位。"
        "机制: 小市值股机构关注低、散户定价占比高, 注意力冲击的价格影响更大更慢出清"
        "(Barber-Odean 注意力假说的横截面预测); 若 Sh 显著高于锚, 过度反应被证明是"
        "小盘专属现象, 后续全部结构都应加小盘条件。")},
    {"id": 6, "type": "VOLSURGE_GATE_STICKY", "expression": f"trade_when(greater(rank({RV}), 0.8), {CTRL}, -1)",
     "optimize_reason": (
        "成交量激增门控 (粘性): 仅当日量/30 日均量前 20% 的股票持有反向仓位。"
        "机制: 量比是注意力最直接的代理变量 (news_vol_stddev 门控在种子战役中 Sh0.13 证伪, "
        "但那是 zscore 形式且平仓退出); 本槽换用量比字段 + 粘性退出重测——若仍然塌陷, "
        "注意力条件化假说将被双重证伪, 可永久关闭该方向。")},
    {"id": 7, "type": "HIGHYIELD_GATE_STICKY", "expression": f"trade_when(greater(rank({DY}), 0.8), {CTRL}, -1)",
     "optimize_reason": (
        "高股息率门控 (粘性): 仅股息率前 20% 的股票持有反向仓位。"
        "机制: 高股息 = 成熟价值型投资者结构, 事件冲击后的定价错误修复更快 (机构纠错); "
        "与槽5 小盘门控构成'投资者结构'轴的两端对照——若两端都增强, 说明边缘来自"
        "投资者结构而非规模本身, 需重新解释机制。")},
    {"id": 8, "type": "PE_GATE_TOP10", "expression": f"trade_when(greater(rank({PE}), 0.9), {CTRL}, -1)",
     "optimize_reason": (
        "高市盈率门控 10% 极端档 (粘性): 同槽3 但阈值 0.8->0.9, 持仓数再砍半。"
        "机制: 阈值扫描定出'集中度-边缘'权衡曲线——若 0.9 档 Sh 继续上升, 说明边缘集中在"
        "最极端估值股票, 应进一步收窄; 若塌陷, 0.8 档即为最优集中度。两槽联合定参, "
        "避免单点过拟合。")},
]

# ---------------------------------------------------------------- 方向 K: 解耦与秩包装
DIR_K = [
    {"id": 1, "type": "DECOUPLE_UP_VS_OWN", "expression": f"reverse(group_rank(subtract({RU}, ts_mean({RU}, 5)), industry))",
     "optimize_reason": (
        "解耦模板 (上行振幅/事件日收盘价 vs 自身 5 日常态, 行业内排序, 反向)。"
        "机制 (biasfree/news102 跨族复用): 事件振幅除以当日收盘价 = 价格归一化的冲击强度; "
        "减去其近 5 日回填均值 = 相对该股自身近期事件的异常程度; 行业内排序剔除行业事件潮; "
        "反向 = 相对自身常态的异常冲测预示回落。这是把'绝对不对称'升级为'相对自身历史与同行'的"
        "三层归一化, 直接攻击 Sub/Sh 天花板 (家族实测 0.73)。")},
    {"id": 2, "type": "DECOUPLE_DN_VS_OWN", "expression": f"reverse(group_rank(subtract({RD}, ts_mean({RD}, 5)), industry))",
     "optimize_reason": (
        "解耦模板 (下行振幅版): 同槽1 但分子换成下行振幅。"
        "机制: 上行冲测的回落是'注意力买入耗尽', 下行砸盘的回升是'恐慌抛售耗尽'——"
        "两个方向的不对称应有同等量级的反向边缘 (E 批 DN_GIVEBACK 家族 0.61-0.74 已有弱证据); "
        "本槽在解耦归一化框架下重测下行方向, 与槽1 互为对照。")},
    {"id": 3, "type": "BACKFILL60_RANKED", "expression": f"reverse(rank({BF}))",
     "optimize_reason": (
        "回填 60 日 + 全横截面秩化。机制: E 批 bf60 (Sh1.10/TO37.2%) 保留 80% 边缘; "
        "rank 化把回填值转成均匀分布, 消除重尾权重对集中度 (CW) 的拉动, "
        "同时可能改变换手结构 (秩比原值变化更快还是更慢需实测)。"
        "本槽测量秩化对 Ret/TO 的净影响——若秩化后 TO 不升而 Sh 保留, 是免费的 margin 改善。")},
    {"id": 4, "type": "BACKFILL60_INDUSTRY_RANKED", "expression": f"reverse(group_rank({BF}, industry))",
     "optimize_reason": (
        "回填 60 日 + 行业内秩化。机制: 与槽3 的差别是排序空间从全市场缩到行业——"
        "行业内排序剔除行业级事件潮 (新闻事件的行业聚集性), 若 Sub/Sh 从 0.71 上升, "
        "证明子universe 疲弱源于行业聚集而非个股稀疏。这是攻 LOW_SUB_UNIVERSE_SHARPE 的专用结构。")},
    {"id": 5, "type": "BACKFILL_120", "expression": f"reverse(ts_backfill({ARAW}, 120))",
     "optimize_reason": (
        "末次事件回填 120 日 (半年持仓先验)。机制: E 批 5/20/60 日三点显示 Sh 平台 1.06-1.10 "
        "而 TO 在 20-60 日区间已饱和在 37-53%; 本槽探测 120 日长窗能否把 TO 压到 25% 以下"
        "(Ret/TO 若达 0.15+ 则 margin 首次可见), 同时测量陈旧先验的稀释终点。")},
    {"id": 6, "type": "BACKFILL_250", "expression": f"reverse(ts_backfill({ARAW}, 250))",
     "optimize_reason": (
        "末次事件回填 250 日 (一年持仓先验): 回填族窗口扫描的极端长端。"
        "机制: 若事件稀疏到'一年只交易少数几次', TO 将逼近 5-10% 区间 (margin 甜蜜区); "
        "风险是信号完全陈旧。本槽与槽5 联合定出回填族的经济寿命上限——即使 Sh 塌陷, "
        "其读数也是家族物理边界的关键数据点。")},
    {"id": 7, "type": "INDUSTRY_BROADCAST_BF60", "expression": f"reverse(group_mean({BF}, 1, industry))",
     "optimize_reason": (
        "行业广播版回填: 把个股末次事件不对称度聚合到行业均值再广播给全行业成员。"
        "机制: E 批行业级累积 (Ret7.11%/Sh0.57) 证明行业层有高毛收益但无风险调整边缘; "
        "本槽换成'末次事件先验'的行业广播——个股事件驱动整个行业的持续先验, "
        "广度从 148 只扩到全行业 (攻 CW 与 Sub), 若行业层边缘存在, 这是唯一能同时"
        "提高广度与保持事件纯度的结构。")},
    {"id": 8, "type": "BACKFILL60_ATR_SCALED", "expression": f"reverse(divide({BF}, {ATRR}))",
     "optimize_reason": (
        "回填 60 日 + ATR 比率归一化: 持续先验除以当日价格区间/20 日均幅。"
        "机制: 不对称度是绝对金额概念, 高波动股天然有更大冲测——除以 ATR 比率把先验转成"
        "'经波动率调整的过度反应' (Wave1 A 批证伪的是事件日即时 ATR 缩放, 本槽是回填后缩放, "
        "作用对象不同); 若 Sh 高于未缩放 bf60 的 1.10, 说明波动归一化对持续先验有效。")},
]

# ---------------------------------------------------------------- 方向 L: VECTOR 探针
DIR_L = [
    {"id": 1, "type": "VEC_SPEED_ASYM_4PCT", "expression": f"reverse(divide(vec_avg({V4U}), add(vec_avg({V4U}), vec_avg({V4D}))))",
     "optimize_reason": (
        "VECTOR 速度不对称 (4% 阈值, vec_avg 归约)。机制: F 批证伪的是'标准算子直接作用于事件型 "
        "VECTOR'; 本批改用 vec_* 归约管道。该字段族覆盖率 0.648/0.622 且为多事件聚合版, "
        "与 MATRIX 版 (news_mins_4_pct_up/dn) 构成材质对照——若 VECTOR 聚合版显著优于 MATRIX, "
        "说明多事件平均比单事件快照更稳健。")},
    {"id": 2, "type": "VEC_SPEED_ASYM_2PCT", "expression": f"reverse(divide(vec_avg({V2U}), add(vec_avg({V2U}), vec_avg({V2D}))))",
     "optimize_reason": (
        "VECTOR 速度不对称 (2% 阈值): 该族覆盖率最高 (0.889/0.875), 是最可能承载统计功效的档位。"
        "机制同槽1; 若 2% 档有边缘而 4% 档无, 说明速度不对称只在'几乎必有'的阈值上可测。")},
    {"id": 3, "type": "VEC_EXC_DIFF", "expression": f"reverse(subtract(vec_avg({VHEX}), vec_avg({VLEX})))",
     "optimize_reason": (
        "VECTOR 冲测标准差差 (上行 excursion stddev 减下行, 反向)。机制: D 批 MATRIX 版 "
        "(reverse(subtract(high_exc, low_exc))) 是全家族非锚最佳 (Sh0.74-0.86); VECTOR 版为"
        "多事件聚合 (覆盖率 1.000), 若聚合版优于单事件版, 该族可升级为主结构候选。")},
    {"id": 4, "type": "VEC_EXC_RATIO", "expression": f"reverse(divide(vec_avg({VHEX}), add(vec_avg({VHEX}), vec_avg({VLEX}))))",
     "optimize_reason": (
        "VECTOR 冲测标准差比 (归一化形式)。机制: 与槽3 的差是自归一化 (除以和) vs 差值——"
        "比值形式跨股可比且不受个股波动率量纲影响; 两槽联合定出该族的最优数学形式, "
        "与锚的比值形式 (up/(up+dn)) 保持同构, 便于跨族比较。")},
    {"id": 5, "type": "VEC_EXC_DIFF_1555", "expression": f"reverse(subtract(vec_avg({VHD1555}), vec_avg({VLD1555})))",
     "optimize_reason": (
        "VECTOR 冲测标准差差 (1555 收盘聚合变体, 覆盖率 1.000)。机制: 同一经济量的第三种聚合"
        "口径 (EOD 收盘视角 vs excursion 视角)。三槽 (3/4/5) 构成'聚合口径 x 数学形式' 消融, "
        "若三种口径结论一致, 该边缘稳健; 若分歧, 需归因到聚合差异而非信号本身。")},
    {"id": 6, "type": "VEC_RANGE_OVER_ATR", "expression": f"reverse(divide(vec_avg({VSR}), vec_avg({VATR})))",
     "optimize_reason": (
        "当日会话区间 / 14 日 ATR (VECTOR, 双字段覆盖率 1.000)。机制: 区间扩张倍数 = "
        "事件日波动放大程度; 反向做多扩张最大的股票——注意力冲击导致波动聚集, "
        "而波动聚集后的均值回归 (GARCH 类效应) 预示回落。这是'波动率通道'假说, "
        "与振幅/速度不对称是第三个正交维度。")},
    {"id": 7, "type": "VEC_VWAP_CLOSE_GAP", "expression": f"reverse(subtract(vec_avg({VVWAP}), vec_avg({VCLOSE})))",
     "optimize_reason": (
        "VWAP 减收盘价 (VECTOR, 日内路径末端压力)。机制: 收盘价低于当日 VWAP = 尾盘抛压"
        "(机构收盘定价权); 反向 = 尾盘抛压预示次日反弹 (短期供求失衡修复)。"
        "注: 两字段均为 news12 数据集内部价格上下文字段 (非外部 PV 污染), "
        "红队需复核该结构是否退化为纯日内反转 (与库内因子共线性风险)。")},
    {"id": 8, "type": "VEC_VOLSURGE_OVER_ATR", "expression": f"reverse(divide(vec_avg({VCVR}), vec_avg({VATR})))",
     "optimize_reason": (
        "量比 / ATR (VECTOR, 单位波动率的成交激增)。机制: 纯粹的'注意力密度'度量——"
        "成交量激增经波动率归一后, 剔除了'高波动股天然高成交量'的混杂; 剩余部分即"
        "异常关注度。若该比值预示次日回落, 是 Barber-Odean 注意力假说最干净的证据。"
        "与 J 批槽6 的门控法互为补充 (门控是条件化, 本槽是连续度量)。")},
]

DIRECTIONS = {
    "I": {"name": "速度不对称族 (正交度量维度)", "hypothesis": "过度反应的注意力机制在时间维度留下'涨快跌慢'指纹, 与振幅不对称正交",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_I},
    "J": {"name": "条件化过度反应门控", "hypothesis": "过度反应强度随关注度/估值/投资者结构上升, 门控集中书库可同时提Sh降TO",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_J},
    "K": {"name": "解耦模板与秩包装", "hypothesis": "事件冲击相对自身历史与同行的异常度 (三层归一化) 优于绝对不对称度",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_K},
    "L": {"name": "VECTOR 字段探针 (vec_* 归约)", "hypothesis": "800 个 VECTOR 字段的聚合口径携带 MATRIX 单事件快照不具备的稳健边缘",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_L},
}

STAGGER_SECONDS = {"I": 0, "J": 25, "K": 50, "L": 75}


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
        # 未知标识符检测: 非算子/非分组/非数字常量的 token 必须全部是已知字段
        ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_mean",
               "ts_backfill", "ts_mean", "ts_sum", "trade_when", "greater", "less", "vec_avg",
               "vec_sum", "vec_count", "industry", "subindustry", "sector", "market"}
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
    print(f"\n===== Gate1-Wave3 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
    print(f"假说: {summary['hypothesis']}", flush=True)
    print(f"设置: universe={s['universe']} neut={s['neutralization']} decay={s['decay']} trunc={s['truncation']}", flush=True)
    print(f"{'槽':>2} {'类型':<24} {'Sh':>6} {'Fit':>6} {'TO%':>7} {'Ret%':>7} {'R/TO':>6} {'Mgn':>6} {'DD%':>6} {'2Y':>6} {'sub':>5} {'rnSh':>5} {'L/S':>9} {'fail':<26} {'warn'}", flush=True)
    for r in summary["rows"]:
        to = (r["turnover"] or 0) * 100
        ret = (r["returns"] or 0) * 100
        dd = (r["drawdown"] or 0) * 100
        rto = r["ret_over_to"] or 0
        ls = f"{r['longCount']}/{r['shortCount']}"
        print(f"{r['slot']:>2} {str(r['type'])[:24]:<24} {r['sharpe'] or 0:>6.2f} {r['fitness'] or 0:>6.2f} {to:>7.1f} {ret:>7.2f} {rto:>6.3f} {r['margin_bps'] or 0:>6.2f} {dd:>6.1f} {r['two_year_sharpe'] or 0:>6.2f} {r['sub_sharpe'] or 0:>5.2f} {r['rn_sharpe'] or 0:>5.2f} {ls:>9} {','.join(map(str, r['fail_checks']))[:26]:<26} {','.join(map(str, r['warning_checks']))}", flush=True)
    g = summary["gate"]
    print(f"Step1: {g['step1']['message']}", flush=True)
    print(f"Step2 通过: {g['step2_count']}/8 | 终极准入: {g['final_count']}/8", flush=True)
    best = max(summary["rows"], key=lambda r: r["sharpe"] or -99)
    if best["ret_over_to"]:
        print(f"[margin 前沿] 最佳 Sh 槽{best['slot']} {best['type']}: Ret/TO={best['ret_over_to']:.4f} "
              f"(margin 死线需 0.5, 差距 {0.5/best['ret_over_to']:.1f}x)", flush=True)


async def main():
    direction = sys.argv[1].strip().upper()
    if direction not in DIRECTIONS:
        print(f"用法: python phase7_gate1_wave3.py <I|J|K|L>"); sys.exit(1)
    d = DIRECTIONS[direction]
    universe, neutralization = d["universe"], d["neutralization"]
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Wave3-{direction}] {d['name']} | 假说: {d['hypothesis']}", flush=True)
    print(f"[Wave3-{direction}] 设置: universe={universe} neut={neutralization} decay={DECAY} trunc={TRUNCATION}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave3-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W3_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, neutralization, universe)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate3_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate3_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W3_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave3-{direction}] 批次文件: {batch_path}", flush=True)

    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, universe, DELAY, neutralization)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W3_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path, neutralization, universe)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], neutralization, universe)
        print(f"[Wave3-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave3-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate3_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave3-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
