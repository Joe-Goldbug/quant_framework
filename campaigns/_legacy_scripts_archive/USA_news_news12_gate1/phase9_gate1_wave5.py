# -*- coding: utf-8 -*-
"""Gate1 Wave5 多 agent 优化驱动 (2026-10-24).

Wave4 判决 (24 槽, 全部回收):
  M Excursion 族深化 -> 族内证伪: 回填/ATR/1555/MAX 中仅 MAX 事件口径保 2Y (2.16), 但 Sh1.29 且 TO 121%;
     ATR 缩放二次证伪 (0.14); group_rank 行业版塌方 (0.19)
  N 价格路径+计数归一化 -> 🔴 重大突破:
     MOVE_PER_COUNT_RANKED = reverse(rank(divide(subtract(EOC,TON), ts_backfill(vec_count(VHEX),120))))
       Sh1.61 (家族首个过 1.58!) / 2Y2.09 / sub1.27 / rnSh1.91 / invSh1.38 / DD5.97%
       仅剩 Fit0.41 / TO120% / CW / CLUSTER_TEST1.47(限1.58, 极近)
     MATRIX_EXC_RATIO Sh1.33/2Y1.67; ASYM_X_GAP 2Y2.52 (全场最高) 但 sub0.21 集中度致死
     注意力稀缺假说 (单位新闻关注度的价格移动) 获实证: 计数归一化+秩化使 Sh 0.81->1.61
  O MARKET 中性化 -> 证伪: bf 族 TO 在 37% 饱和与中性化无关 (MARKET 37.8% vs INDUSTRY 37.1%),
     行业均值 shuffle 假说死亡; BF60_IND_RANK_MARKET fail=0 (Sh1.15/Fit0.36/2Y0.67/无 MATCHES_THEMES)

平台检查项实测语义 (原始 checks 对象):
  LOW_SHARPE limit=1.58 / LOW_FITNESS limit=1.0 / LOW_2Y_SHARPE limit=1.58
  HIGH_TURNOVER limit=0.7 / CLUSTER_TEST limit=1.58 (warning 级) / MATCHES_THEMES (无值)
  🔴 checks.fail=[] 不等于合格: N s2 fail 桶为空但 ra.ra_failed=true (LOW_SHARPE/FITNESS/2Y)
     -> 唯一权威判据 = ra.ra_failed==false (与历史结论互证)
  bf60 回填消 CW (longCount 511) 且削 TO 3.5x (130%->37%); group_rank(·,industry) 消 MATCHES_THEMES

Margin 恒等式 (24 行精确吻合): Mgn_bps = 20 x Ret/TO -> USA 死线 10bps <=> Ret>=0.5*TO
  家族实测 R/TO 最高 0.098 (bf60 族), 距死线 5.1x -> 需结构性提升每笔交易盈利

Wave5 三路 (每路 8 槽):
  P 自身极端度族: 同一不对称读数对不同股票含义不同; 相对该股自身历史 (ts_rank 250/120/500)
    的极端度才预测反转 (异构基线假说)。极端度秩天然有界且持续 -> 位置仅在百分位移动时变化,
    是同时攻 TO 与 CW 的结构。含 zscore/组内/双秩化形态
  Q 注意力稀缺族深化: 对 Sh1.61 冠军的形态空间扫描——回填60/120 (保边降换手),
    组内/子行业秩化 (攻 sub1.27->1.58 与 CLUSTER_TEST1.47->1.58), 价格归一 (移动%/关注度),
    隔夜跳空/关注度, 低行程事件计数对照, 250 日计数窗口
  R 信念门控+交互 @STATISTICAL: 只在自身历史极端度前 10%/20% 时入场 (粘性退出) 的
    信念集中门控——J 批证伪的是外生门控 (PE/cap/vol/yield), 本批测内生门控 (信号自身极端度),
    经济含义完全不同: 极端不对称才是过度反应假说预测最强的子集; 每笔交易盈利应上升 -> 攻 margin 死线
    STATISTICAL 是 TO 25-50% 甜区的合法中性化轴 (news29 战役结论); 另含 ASYM×GAP 行业修复版
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
EOC, EODH, EODL, TON, VWAP = "news_eod_close", "news_eod_high", "news_eod_low", "news_ton_last", "news_eod_vwap"
GAP = "news_open_gap"
VHEX, VLEX = "high_price_excursion_stddev", "low_price_excursion_stddev"

CTRL = f"reverse(divide({U}, add({U}, {D})))"
ARAW = f"divide({U}, add({U}, {D}))"
BF = f"ts_backfill({ARAW}, 60)"
# Wave4-N 冠军: 注意力稀缺 (新闻时刻->收盘移动 / 120 日回填事件数) + 秩化, Sh1.61/2Y2.09
MOVE = f"subtract({EOC}, {TON})"
EVCNT = f"ts_backfill(vec_count({VHEX}), 120)"
MOVECNT = f"divide({MOVE}, {EVCNT})"

# ---------------------------------------------------------------- 方向 P: 自身极端度族
DIR_P = [
    {"id": 1, "type": "EXTREMITY_250", "expression": f"reverse(ts_rank({ARAW}, 250))",
     "optimize_reason": (
        "自身历史极端度: 不对称度在该股 250 日事件历史中的百分位, 反向。机制 (异构基线假说): "
        "0.6 的不对称度对常年 0.5 波动的股票是强信号, 对常年 0.65 的股票是弱信号——"
        "绝对读数不可跨股比较, 相对自身历史的极端度才是过度反应的统一度量。"
        "百分位天然有界 [0,1] 且持续 (仅在百分位移动时换仓) -> 同时攻 TO 与 CW。"
        "这是 J 批外生门控证伪后, 门控思想在内生极端度上的重建。")},
    {"id": 2, "type": "EXTREMITY_120", "expression": f"reverse(ts_rank({ARAW}, 120))",
     "optimize_reason": (
        "极端度窗口 120 日。机制: 与槽1 构成窗口扫描——E 批显示振幅族边缘在 5-60 日平台期, "
        "极端度的参考窗口决定'多快的基线'：120 日约两个季度 (适应基本面变化), "
        "250 日约一年 (更稳但可能包含过期状态)。若 120 版显著强, 取短窗。")},
    {"id": 3, "type": "EXTREMITY_IND_RANKED", "expression": f"reverse(group_rank(ts_rank({ARAW}, 250), industry))",
     "optimize_reason": (
        "极端度 + 行业内秩化。机制: 双重归一 (时间维极端度 x 横截面行业维)。K/O 批证实 "
        "group_rank(·,industry) 可消除 MATCHES_THEMES (零警告目标必要条件) 且抬 sub-sharpe; "
        "本槽检验行业相对极端度是否比全市场极端度更强 (行业事件潮剔除)。")},
    {"id": 4, "type": "EXTREMITY_ZSCORE", "expression": f"reverse(ts_zscore({ARAW}, 250))",
     "optimize_reason": (
        "极端度 z-score 形式。机制: 与百分位的差别是保留幅度信息 (z-score 无界, 极端值更极端) "
        "vs 百分位有界 (抗单日异常)。两槽联合定出该族最优数学形式——若 z-score 版 Sh 更高, "
        "说明边缘在极端幅度; 若百分位版更稳 (DD 低), 取百分位。")},
    {"id": 5, "type": "MOVE_EXTREMITY_250", "expression": f"reverse(ts_rank({MOVECNT}, 250))",
     "optimize_reason": (
        "注意力移动的自身极端度: (移动/事件数) 在该股 250 日历史中的百分位, 反向。机制: "
        "Wave4 冠军 (移动/计数 秩化 Sh1.61) 的极端度版——把'今天注意力稀缺下的移动有多大'"
        "转成'相对该股自身历史有多异常'。事件计数字段仅 1 层 ts_* (回填), 合规。"
        "若该形态 Sh>=1.58 且 TO 显著低于 120%, 即是 margin 死线的首个真实候选。")},
    {"id": 6, "type": "MOVE_EXTREMITY_60", "expression": f"reverse(ts_rank({MOVECNT}, 60))",
     "optimize_reason": (
        "注意力移动极端度 60 日窗口。机制: 与槽5 构成窗口扫描; 60 日约一季, "
        "匹配事件驱动的边际信息半衰期 (E 批 5-60 日平台期)。")},
    {"id": 7, "type": "EXTREMITY_RANKED", "expression": f"reverse(rank(ts_rank({ARAW}, 250)))",
     "optimize_reason": (
        "极端度 + 全横截面秩化 (时间 x 横截面双重归一)。机制: 时间维百分位解决跨股基线差异, "
        "横截面秩化解决分布形状差异 (重尾/偏斜) 并消 MATCHES_THEMES (K 批)。"
        "若该形态同时消除警告且保 Sh, 是零警告路径的关键拼图。")},
    {"id": 8, "type": "EXTREMITY_500", "expression": f"reverse(ts_rank({ARAW}, 500))",
     "optimize_reason": (
        "极端度 500 日窗口 (约两年, 跨完整市场周期)。机制: 长窗口基线 = '相对该股整个"
        "可观测历史'——若 500 日版仍强, 说明边缘不依赖基线窗口选择 (稳健性); "
        "若塌方, 说明边缘只在近期状态有效 (250/120 更优)。三槽 (1/2/8) 定出窗口敏感性。")},
]

# ---------------------------------------------------------------- 方向 Q: 注意力稀缺族深化
DIR_Q = [
    {"id": 1, "type": "MOVECNT_BF60_IND_RANKED", "expression": f"reverse(group_rank(ts_backfill({MOVECNT}, 60), industry))",
     "optimize_reason": (
        "冠军 + 60 日回填 + 行业内秩化。机制: 三重叠加——回填保边降换手 (N 批: TO 130%->37%, "
        "longCount 511 消 CW), group_rank 消 MATCHES_THEMES 并攻 sub (1.27->1.58)。"
        "若该形态 Sh>=1.3 且 TO<=40% 且 2Y>=1.58, 即是家族首个同时逼近 Sh/2Y/sub/TO 四项的结构, "
        "距门禁只差 Fit (需 R/TO 从 0.064 升到 0.5, 或 Fit 公式的 TO 地板 12.5%)。")},
    {"id": 2, "type": "MOVECNT_BF60_RANKED", "expression": f"reverse(rank(ts_backfill({MOVECNT}, 60)))",
     "optimize_reason": (
        "冠军 + 60 日回填 + 全截面秩化。机制: 同槽1 的非组内版——对照'行业相对 vs 全市场相对'"
        "哪个更优; 同时是冠军 (已测原始形态) 的低换手孪生, 直接测量回填对 Sh/2Y 的代价。")},
    {"id": 3, "type": "MOVEPCT_PER_COUNT", "expression": f"reverse(rank(divide(divide({MOVE}, {TON}), {EVCNT})))",
     "optimize_reason": (
        "价格归一: (收盘-新闻价)/新闻价 / 事件数 = 百分比移动/关注度, 反向。机制: 原始冠军的分子是"
        "美元行程 (高股价股机械性更大); 除以新闻时刻价格后 = 收益率口径, 跨股可比。"
        "这是全场唯一未测的归一轴 (价格水平), 若显著强于冠军, 说明美元口径混入了价格水平因子。")},
    {"id": 4, "type": "GAP_PER_COUNT", "expression": f"reverse(rank(divide({GAP}, {EVCNT})))",
     "optimize_reason": (
        "隔夜跳空 / 事件数。机制: 跳空 = 盘前注意力累积的定价 (无连续交易, 最纯粹的注意力冲击), "
        "除以事件数 = 单位关注度的跳空。N 批槽8 证实跳空 x 不对称交互有全场最高 2Y (2.52), "
        "本槽单独检验跳空/关注度这一分量是否独立承载边缘。")},
    {"id": 5, "type": "MOVE_PER_LOWCOUNT", "expression": f"reverse(rank(divide({MOVE}, ts_backfill(vec_count({VLEX}), 120))))",
     "optimize_reason": (
        "低行程事件计数为分母 (对照实验)。机制: 冠军用上行 excursion 事件数; 本槽换下行 excursion "
        "事件数——若两者等效, 说明计数只是'新闻活跃度'代理 (与方向无关); 若上行版显著强, "
        "说明分子分母同向匹配有额外信息 (注意力结构性偏上行)。")},
    {"id": 6, "type": "MOVE_PER_COUNT_250", "expression": f"reverse(rank(divide({MOVE}, ts_backfill(vec_count({VHEX}), 250))))",
     "optimize_reason": (
        "250 日计数窗口。机制: 注意力基线的时间尺度——120 日约半年, 250 日约一年; "
        "长窗口 = 更稳的'该股正常关注度' (少受单月新闻潮影响), 但反应更慢。"
        "与 N 批 120 日冠军构成窗口对照。")},
    {"id": 7, "type": "MOVECNT_BF120_RANKED", "expression": f"reverse(rank(ts_backfill({MOVECNT}, 120)))",
     "optimize_reason": (
        "冠军 + 120 日回填。机制: K 批证明 TO 在 37% 饱和与回填长度无关 (排名 shuffle 主导), "
        "但保边率随回填长度变化——若 120 日版 Sh 与 60 日版持平, 回填长度不敏感 (稳健); "
        "若 120 日版更高, 说明该边缘寿命长于振幅族 (注意力信号比价格信号更持续)。")},
    {"id": 8, "type": "MOVECNT_SUBIND_RANKED", "expression": f"reverse(group_rank({MOVECNT}, subindustry))",
     "optimize_reason": (
        "冠军 + 子行业秩化 (更细分组)。机制: analyst52 战役结论'簇越细越好'——子行业剔除更窄的"
        "行业事件潮; 若 sub-sharpe 与 CLUSTER_TEST 值 (1.47, 限 1.58) 同步上升, "
        "即找到消除最后一个警告项的钥匙。风险: 子行业分组小 -> 组内排序噪声大 (analyst10 教训)。")},
]

# ---------------------------------------------------------------- 方向 R: 信念门控 + 交互 @STATISTICAL
DIR_R = [
    {"id": 1, "type": "MOVECNT_BF60_STAT", "expression": f"reverse(ts_backfill({MOVECNT}, 60))",
     "optimize_reason": (
        "冠军回填版 @STATISTICAL 中性化。机制: news29 战役结论'TO 25-50% -> STATISTICAL 唯一钥匙'——"
        "回填族恰在 TO 37% 甜区; 统计中性化剔除全部风格暴露 (动量/波动/规模), "
        "若 Sh 保持而 TO 再降, R/TO 首次突破 0.15。J/K 批证伪 STATISTICAL 仅针对纯事件快照族, "
        "回填族下未测——本槽补齐该关键单元格。")},
    {"id": 2, "type": "MOVECNT_BF60_IND_RANKED_STAT", "expression": f"reverse(group_rank(ts_backfill({MOVECNT}, 60), industry))",
     "optimize_reason": (
        "冠军回填 + 行业内秩 @STATISTICAL。机制: Q 批槽1 的中性化对照——"
        "group_rank 与 neutralization 是独立机制 (组内排序 vs 风格约束), 可叠加; "
        "本槽是家族全部合规杠杆 (消 MATCHES_THEMES/CW) x TO 杠杆 (回填) x 风格杠杆 (STATISTICAL) "
        "的合并测试, 若 Sh>=1.3/TO<=35%/无警告, 即为当前最优候选。")},
    {"id": 3, "type": "BF60_STAT", "expression": f"reverse({BF})",
     "optimize_reason": (
        "振幅不对称回填 @STATISTICAL。机制: N 批槽2 (fail=0 的唯一形态) 的中性化对照——"
        "该形态 Sh1.11/Fit0.35/2Y0.78/TO37%/R/TO0.097 (家族最高); STATISTICAL 若能把 2Y 从 0.78 "
        "拉回 1.58 (统计中性化通常稳定 2Y), 即使 Sh 略降, 也是首个 2Y 达标的低换手形态。")},
    {"id": 4, "type": "EXTREMITY_250_STAT", "expression": f"reverse(ts_rank({ARAW}, 250))",
     "optimize_reason": (
        "自身极端度 @STATISTICAL。机制: P 批槽1 的中性化对照。极端度百分位含个股时序信息, "
        "统计中性化剔除其风格暴露后, 若边缘保留 -> 该边缘是纯过度反应效应而非风格代理; "
        "若塌方 -> 归因风格。这是对极端度假说的最严格检验。")},
    {"id": 5, "type": "CONVICTION_GATE_90", "expression": f"trade_when(greater(ts_rank({ARAW}, 250), 0.9), reverse({BF}), -1)",
     "optimize_reason": (
        "信念门控 (前 10% 极端度, 粘性退出): 只在不平衡度处于该股自身历史前 10% 时持有反向仓位, "
        "跌出前十也不平仓 (-1), 等重新进入或自然消退。机制 (攻 margin 死线的核心实验): "
        "J 批证伪的是外生门控 (PE/cap/vol/yield——与过度反应机制无关的切分); 内生门控的经济含义"
        "完全不同: 极端不对称才是过度反应假说预测最强的子集 (非极端读数是噪声)。"
        "若每笔交易盈利上升 (R/TO -> 0.2+), margin 死线首次被逼近; 代价是持仓数下降 (CW 风险)。")},
    {"id": 6, "type": "CONVICTION_GATE_80", "expression": f"trade_when(greater(ts_rank({ARAW}, 250), 0.8), reverse({BF}), -1)",
     "optimize_reason": (
        "信念门控 (前 20% 极端度)。机制: 与槽5 构成阈值扫描——10% 太严 (持仓稀疏, CW 风险) "
        "vs 20% 更宽 (覆盖更多样本)。两槽联合定出门控严格度与每笔盈利的权衡曲线, "
        "这是 margin 恒等式下唯一可能提升 R/TO 的结构性手段 (选择性交易)。")},
    {"id": 7, "type": "ASYM_X_GAP_IND_RANKED", "expression": f"reverse(group_rank(multiply(rank({ARAW}), rank({GAP})), industry))",
     "optimize_reason": (
        "不对称 x 跳空交互 + 行业内秩化。机制: N 批槽8 的原始版有全场最高 2Y (2.52) 与最高 "
        "Ret (8.19%) 但 sub0.21 集中度致死 (longCount 97); 组内秩化把交互项限制在行业内比较, "
        "应同时修复 sub-sharpe 与持仓集中度。书面交互: 隔夜跳空 (盘前注意力) x 日内不对称 "
        "(盘中注意力冲击) = 全周期注意力共振——两者同向时过度反应最强。若 sub 修复到 1.0+, "
        "该形态以 2Y2.52/Ret8.19% 的底子成为门禁候选。")},
    {"id": 8, "type": "CLOSE_VWAP_PER_COUNT", "expression": f"reverse(rank(divide(subtract({EOC}, {VWAP}), {EVCNT})))",
     "optimize_reason": (
        "收盘 vs 当日 VWAP 的偏离 / 事件数。机制: 微观结构新信息 (VWAP 首入战役)——收盘低于 "
        "VWAP = 尾盘卖方压力 (事件日定价的最终裁决被抛压主导), 单位关注度越大越异常。"
        "与冠军 (新闻时刻->收盘) 的差别是基准从新闻时刻换成全日成交均价, "
        "剔除'新闻时刻定价效率'只留'尾盘压力'成分。三字段全为 news12 内部价格上下文字段 (合规)。")},
]

DIRECTIONS = {
    "P": {"name": "自身极端度族 (异构基线)", "hypothesis": "不对称度的绝对读数不可跨股比较; 相对该股自身历史 250 日的极端度 (ts_rank) 才是过度反应的统一度量, 且百分位有界持续 -> 同攻 TO/CW",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_P},
    "Q": {"name": "注意力稀缺族深化 (Sh1.61 冠军形态空间)", "hypothesis": "单位新闻关注度的价格移动承载家族最强边缘 (Sh1.61/2Y2.09); 其回填/组内/价格归一/跳空/计数窗口形态可同时逼近 Sh/2Y/sub/TO 四项门禁",
          "universe": "TOP1000", "neutralization": "INDUSTRY", "slots": DIR_Q},
    "R": {"name": "信念门控+交互 @STATISTICAL", "hypothesis": "内生极端度门控 (只交易自身历史前 10-20% 的不对称) 提升每笔交易盈利 -> 攻 margin 死线; STATISTICAL 是 TO 25-50% 甜区的合法中性化轴",
          "universe": "TOP1000", "neutralization": "STATISTICAL", "slots": DIR_R},
}

STAGGER_SECONDS = {"P": 0, "Q": 25, "R": 50}


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
    print(f"\n===== Gate1-Wave5 方向 {summary['direction']} ({summary['direction_name']}) =====", flush=True)
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
        print(f"用法: python phase9_gate1_wave5.py <P|Q|R>"); sys.exit(1)
    d = DIRECTIONS[direction]
    universe, neutralization = d["universe"], d["neutralization"]
    await asyncio.sleep(STAGGER_SECONDS[direction])
    print(f"[Wave5-{direction}] {d['name']} | 假说: {d['hypothesis']}", flush=True)
    print(f"[Wave5-{direction}] 设置: universe={universe} neut={neutralization} decay={DECAY} trunc={TRUNCATION}", flush=True)

    with open(FIELDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Wave5-{direction}] 字段字典 {len(known_fields)} 个装载", flush=True)

    items = [{"id": s["id"], "expression": s["expression"], "optimize_reason": s["optimize_reason"],
              "seed_id": f"GATE1W5_{direction}_{s['id']}", "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    preaudit(items, known_fields)
    check_dup_fingerprints(items, neutralization, universe)

    batch_path = os.path.join(CAMPAIGN, f"batch_gate5_{direction}_{int(time.time())}.json")
    state_path = os.path.join(CAMPAIGN, f"state_gate5_{direction}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W5_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"[Wave5-{direction}] 批次文件: {batch_path}", flush=True)

    corrected = SimBatchRunner.validate_and_pack_batch(items, known_fields, CATEGORY, REGION, universe, DELAY, neutralization)
    for it, ce in zip(items, corrected):
        it["expression"] = ce
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump({"seed_id": f"GATE1W5_{direction}", "region": REGION, "universe": universe,
                   "delay": DELAY, "category": CATEGORY, "known_fields": known_fields, "items": items},
                  f, ensure_ascii=False, indent=1)

    try:
        results = await submit_with_retry(batch_path, items, state_path, neutralization, universe)
    except Exception as e:
        purge_fingerprints([it["expression"] for it in items], neutralization, universe)
        print(f"[Wave5-{direction}] FATAL: {e}", flush=True)
        raise

    out_path = batch_path.replace(".json", "_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    print(f"[Wave5-{direction}] 结果已存: {out_path}", flush=True)

    summary = build_summary(items, results, direction)
    sum_path = os.path.join(CAMPAIGN, f"summary_gate5_{direction}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print_table(summary)
    print(f"[Wave5-{direction}] 汇总已存: {sum_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
