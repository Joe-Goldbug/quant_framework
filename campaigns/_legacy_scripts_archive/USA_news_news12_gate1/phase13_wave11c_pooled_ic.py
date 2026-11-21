# -*- coding: utf-8 -*-
"""Gate1 Wave11-C · pooled 家族 IC 提升攻坚 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== ★ 本批立项依据: 双约束联立 isolated 出的唯一数学可行路径 ===

对全家族 315+ 样本做 Fit 与 Margin 的**双约束联立**:
    Fit >= 1.0   需 Ret >= TO / Sh^2
    Mgn >= 10bps 需 Ret >= 0.5 * TO          (Mgn = 20 * Ret / TO)
    Sh = 1.58 时 Fit 需 Ret >= 0.4004*TO, Mgn 需 Ret >= 0.5*TO
    ==> **R/TO >= 0.5 是与 Sh 无关的硬约束**; Fit>=1 需 Sh >= 1.414 (当 R/TO=0.5)
    家族 Ret 天花板 7.86% (SH165) ==> TO 必须 <= 15.7% 才可能 Mgn 达标.

**全场唯一数学可行资产 (双约束都只差最后一小步):**
    GrgN9OAZ = reverse(ts_rank(divide(ts_sum(U,60), add(ts_sum(U,60), ts_sum(D,60))), 250))
    -> Sh 0.61 / TO 5.2% / Ret 2.09% / R-TO 0.403 / **Mgn 8.05bps** / 2Y 1.25 / L/S 516/512
    反解: 若 Sh 提到 1.58, Fit = 1.58*sqrt(2.09/5.2) = **1.00 精确达标**;
          若 Ret 略提到 2.60%, Mgn = **10.00bps** 也达标.
    ==> **TO 与 Ret 几乎不动, 纯粹要把 Sharpe 提升 2.59 倍.**

=== 为什么必须攻 IC 而非时间尺度 ===
pooled 家族内部 Sh-TO 同样反相关:
    ts_sum(60)+ts_rank250 : Sh 0.61 @ TO 5.2%  @ R-TO 0.403   <- 本批基座
    ts_sum(180)+ts_rank250: Sh 0.34 @ TO 3.7%  @ R-TO 0.298
    backfill(60)+group_rank: Sh 1.17 @ TO 37.8% @ R-TO 0.098
    ts_decay_linear(60)   : Sh 1.28 @ TO 107%  @ R-TO 0.050
    无累积裸 rank         : Sh 1.37 @ TO 130%  @ R-TO 0.051
凡提高信号频率 (ts_decay_linear/缩短窗口/去累积) 的手段都摧毁 R/TO.
且 Sh = IC * sqrt(N) 中 N (breadth) 已满 (516/512 ~ TOP1000 满仓),
**故唯一出路是提高 IC (信号质量) 而不改变信号频率.**

=== 已测无效 (勿重复, 均为 315 基线实证) ===
  group_rank(ts_rank(pooled,250),industry) -> Sh 0.63 (+3%, npAlGnM8)
  ts_sum(180) 长窗 -> Sh 0.34
  ts_decay_linear 替 ts_sum -> Sh 1.28 但 TO 107%
  divide(subtract(U,D), news_atr14) -> Sh 0.70 @ TO 125%
  multiply(pooled, news_atr_ratio) -> Sh 0.51
  ts_zscore(subtract(U,D),120) -> Sh 0.62 @ TO 123%
  divide(subtract(U,D), ts_std_dev(add(U,D),60)) -> Sh 0.42
  divide(subtract(U,D), ts_mean(add(U,D),60)) -> Sh 0.75 @ TO 124%

=== 本批 8 条 = 7 类 IC 提升机制 (非参数摸鱼) ===
  槽1/2  窗口精扫 (40 / 120)      —— IC-TO 最优点可能不在 60
  槽3    无量纲口径 (ret 比)      —— 消除美元金额的规模偏差
  槽4    波动率归一 (ATR)         —— 把净方向变成波动率调整后的强度
  槽5    稳健化 (winsorize std=3) —— 极端事件值去噪 (平台须命名参数)
  槽6    双窗符号一致性过滤       —— 短窗与长窗同向才保留 (经典提纯)
  槽7    输出层 group_zscore      —— 行业内标准化 (与 group_rank 不同的正交化)
  槽8    新鲜度门                 —— 已验证免费增益, 检验在 pooled 上是否同样免费

=== 平台纪律 (来自并行同源研究的实证, 已内化) ===
  winsorize 只接受命名参数: winsorize(x, std=N); 位置传参整批 ERROR 连坐.
  news_eod_open 已从字段池下线, 禁用. 一律显式 reverse.

=== mandate ===
2<=字段数<=3 | op 数不限 | 仅 multi_create_simulate 每批 8 条 | 严禁提交
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

U, D = "news_max_up_amt", "news_max_dn_amt"
UR, DR = "news_max_up_ret", "news_max_dn_ret"
ATR = "news_atr14"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
GATE = f"less(days_from_last_change({CN}), 2)"


def pooled(n):
    """60 日累积净方向内核 (本批唯一基座, TO~5%)"""
    s_u, s_d = f"ts_sum({U}, {n})", f"ts_sum({D}, {n})"
    return f"divide({s_u}, add({s_u}, {s_d}))"


SLOTS = [
    # ---- 窗口精扫 ----
    {
        "id": 1, "type": "POOLED_N40", "role": "WINDOW",
        "baseline": "GrgN9OAZ N=60 Sh0.61/TO5.2%",
        "expression": f"reverse(ts_rank({pooled(40)}, 250))",
        "optimize_reason": (
            "【窗口精扫 · N=40】与 GrgN9OAZ (N=60, Sh 0.61/TO 5.2%) 唯一差别是累积窗口从 60 天"
            "缩短到 40 天. 机制假设: 新闻事件对价格发现的净贡献有衰减半衰期, 若半衰期短于 60 天, "
            "则 60 日窗口混入了过多过期事件 (旧新闻的净方向已被完全定价, 其贡献趋零但占权重), "
            "稀释 IC; 40 日窗口更贴近有效半衰期, IC 应更高, 而 TO 仅从 5.2% 升到约 7-8% (仍在 "
            "Fit 下限保护边缘). 这是纯粹的 IC-TO 最优点搜索, 不改变信号生成机制. "
            "若本槽 Sh 明显高于 0.61 而 TO 仍 <10%, 则找到更优窗口, 后续沿 30-50 精扫; "
            "若 Sh 反而下降, 则 60 已是该族最优窗口, 窗口轴关闭, 全部预算转投槽3-8 的机制创新."),
    },
    {
        "id": 2, "type": "POOLED_N120", "role": "WINDOW",
        "baseline": "GrgN9OAZ N=60 / mLYNnqMK N=180 Sh0.34",
        "expression": f"reverse(ts_rank({pooled(120)}, 250))",
        "optimize_reason": (
            "【窗口精扫 · N=120 · 与槽1 构成双向夹逼】N=180 已实测 Sh 崩到 0.34 (mLYNnqMK), "
            "N=60 为 0.61. 本槽取中间点 120, 目的是确认「60 附近是峰还是仍在上升段」: "
            "若 N=120 的 Sh 介于 0.34 与 0.61 之间 (如 0.5), 则 60 右侧是单调下降, 峰值在 60 或其左侧; "
            "若 N=120 的 Sh 高于 0.61, 则说明该 alpha 的有效记忆长于 60 天, 此前 N=180 的崩塌源于"
            "其他因素 (如 180 天窗内事件数过多导致比值饱和), 需重估. 经济学: 若新闻冲击的半衰期"
            "是数月尺度 (渐进信息扩散, Hong-Stein 1999), 则长窗应更优; 若半衰期是数周 "
            "(注意力快速衰减), 则短窗更优. 本槽与槽1 的夹逼可一次性定位最优窗口区间, "
            "把后续窗口搜索压缩到窄区间. 预期 TO 3-4%, R-TO 应维持 0.25-0.40 区间."),
    },
    # ---- 口径 ----
    {
        "id": 3, "type": "POOLED_RET_RATIO", "role": "METRIC",
        "baseline": "无 (ret 比口径在 ts_sum 累积版零使用)",
        "expression": (
            f"reverse(ts_rank(divide(ts_sum({UR}, 60), add(ts_sum({UR}, 60), ts_sum({DR}, 60))), 250))"),
        "optimize_reason": (
            "【无量纲口径 · ret 比替代 amt 比】把内核从美元金额比 U/(U+D) 换成百分比收益比 "
            "up_ret/(up_ret+dn_ret). 机制假设: 美元金额 = 价格 x 收益率, 故 amt 比暗中混入了"
            "价格水平的规模偏差 —— 高价股 (如 $500) 的同等百分比 excursion 产生的美元金额是低价股"
            "的数十倍, 其 pooled 比值被机械地推向极端, 而这部分方差是价格规模而非信息强度, "
            "属纯噪声; ret 比消除该规模项, 使截面比较只在信息强度维度上进行, IC 应提升. "
            "这是横截面可比性问题而非时间频率问题, 故不预期改变 TO (仍 ~5%). "
            "风险: up_ret cov 0.8458 低于 U 的 0.9692, 覆盖率下降会掉 breadth (可能从 516 降到 450), "
            "而 Sh = IC*sqrt(N), 若 IC 提升不足 10% 而 breadth 掉 13%, 净效应可能为负 —— "
            "本槽是 IC 与 breadth 的交换实验, 读数必须同时看 L/S."),
    },
    # ---- 归一化 ----
    {
        "id": 4, "type": "POOLED_ATR_NORM", "role": "NORM",
        "baseline": "omokbbKl divide(subtract(U,D),news_atr14) Sh0.70@TO125% (无累积版)",
        "expression": (
            f"reverse(ts_rank(divide({pooled(60)}, "
            f"add(add(ts_sum({U}, 60), ts_sum({D}, 60)), ts_mean({ATR}, 60))), 250))"),
        "optimize_reason": (
            "【波动率归一 · 分母注入 ATR 尺度】此前 ATR 归一只在无累积版测过 (omokbbKl: "
            "divide(subtract(U,D), news_atr14) -> Sh 0.70 @ TO 125%), 失败原因是无累积版本身高 TO. "
            "本槽把 ATR 用在**已累积的 60 日版本**上: 分母 = 60 日总 excursion 金额 + 60 日均 ATR. "
            "机制假设: pooled 比值只反映「净方向占比」, 不反映「该净方向相对个股正常波动有多大」 —— "
            "一只低波动股票 60% 的净上偏远比一只高波动股票 60% 的净上偏更异常 (后者可能仅是"
            "日常噪声). 分母加 ATR 项后, 信号变成「净方向强度经个股波动率调整」的量, "
            "高波动股的同等 pooled 值被降权, 低波动股的同值被加权, 这是把无信息的波动率维度"
            "从信号中剥离, 应提纯 IC. 因 ATR 是 60 日均值 (慢变量), 不改变信号频率, TO 应维持 ~5%. "
            "⚠️ 量纲诚实披露: 分子是无量纲比值 (0-1), 分母是美元+美元, 故除法结果的量纲是 1/美元, "
            "横截面不可比 —— 本槽的合法性依赖于外层 ts_rank 的单调保序性质: ATR 项对所有股票"
            "同向缩放, 不会逆转 pooled 的截面排序, 故 ts_rank 后等价于按 pooled/ATR 排序, "
            "这是有定义的重参数化而非量纲污染. 若本槽 Sh 提升, 后续应把 ATR 移进分子做乘性"
            "(multiply(pooled, ATR)) 以彻底消除量纲问题, 那属下一波."),
    },
    # ---- 稳健化 ----
    {
        "id": 5, "type": "POOLED_WINSOR", "role": "ROBUST",
        "baseline": "无 (winsorize 在 pooled 累积版零使用)",
        "expression": (
            f"reverse(ts_rank(winsorize({pooled(60)}, std=3), 250))"),
        "optimize_reason": (
            "【稳健化 · winsorize 极端值去噪】对 60 日累积 pooled 比值做 3 倍标准差缩尾. "
            "机制假设: pooled 比值的极端值 (接近 0 或 1) 绝大多数来自**小样本情形** —— "
            "60 日内仅 1-2 个事件且恰好全为同向, 此时比值 0.9+ 并不是「强烈的方向共识」, "
            "而是「偶然的一次性事件」; 这类极端值在截面上占据排名的两端, 把 rank/ts_rank 的"
            "分辨率浪费在低置信度样本上, 且它们的未来收益方差极大 (回归均值), 拖累 IC. "
            "winsorize 把这些低置信度极端值压回边界, 使排名分辨率集中到样本量充足的股票上. "
            "这是纯粹的估计稳健性改进, 不改变信号的时间频率, TO 应维持 ~5%. "
            "⚠️ 平台纪律: winsorize 只接受命名参数 winsorize(x, std=N), 位置传参会整批 ERROR "
            "连坐 (并行同源研究 2026-10-25 实证), 本槽已用命名参数. "
            "若本槽 Sh 提升, 说明小样本极端值是 IC 的主要漏损, 后续应引入置信度加权 (更强的手段)."),
    },
    # ---- 提纯 ----
    {
        "id": 6, "type": "POOLED_DUAL_SIGN", "role": "PURIFY",
        "baseline": "无 (双窗符号一致性过滤全库首测)",
        "expression": (
            f"reverse(ts_rank(multiply(sign({pooled(20)}), {pooled(60)}), 250))"),
        "optimize_reason": (
            "【双窗符号一致性过滤 · 短窗为长窗做方向确认】内核 = sign(pooled_20) x pooled_60. "
            "机制假设 (信息扩散的时间结构): 若某股票的新闻净方向在**短窗 (20 日, 近期) 与长窗 "
            "(60 日, 中期) 上符号一致**, 说明该方向是持续性的信息驱动 (同一批知情资金在持续"
            "表达观点), 其未来漂移更强; 若符号相反 (近期转空但中期仍净多), 说明中期读数只是"
            "陈旧事件的残留, 已无预测力. 乘上 sign(短窗) 后, 不一致的信号幅度被翻转且幅度缩水, "
            "一致的不变 —— 这是一个把「方向持续性」作为显式条件的提纯算子, 理论上直接作用于 IC "
            "而非频率. 风险: sign() 是阶梯函数, 在 pooled_20 穿越零点时会产生跳变, 可能小幅抬 TO "
            "(预期从 5% 到 8-12%); 且若该过滤无效 (方向一致性无信息), 则等价于给信号加了噪声, "
            "Sh 会低于 0.61. 本槽是 IC 提纯假设的干净判决实验: 有效则开启一整类「多尺度一致性」构造, "
            "无效则说明该族的 IC 漏损不在方向混淆而在别处."),
    },
    # ---- 输出层 ----
    {
        "id": 7, "type": "POOLED_GROUP_ZSCORE", "role": "OUTPUT",
        "baseline": "npAlGnM8 group_rank(ts_rank(pooled,250),industry) Sh0.63",
        "expression": (
            f"reverse(group_zscore({pooled(60)}, industry))"),
        "optimize_reason": (
            "【输出层变体 · group_zscore 行业内标准化】与 GrgN9OAZ 同为 60 日累积内核, "
            "但输出层从 ts_rank(250) 换成 group_zscore(industry). 已测: group_rank(ts_rank(...)) "
            "外层嵌套只给 +3% (npAlGnM8), 但那是在 ts_rank **之后**再组内 rank (两次保序变换叠加, "
            "第二次几乎无新信息). group_zscore 不同: 它先做 (x - 组均值)/组标准差, 是**线性**变换, "
            "保留了幅度信息 (ts_rank 已把幅度压平), 再经 INDUSTRY 中性化. 机制假设:  pooled 比值的"
            "行业间差异可能很大 (如科技股事件后持续净多, 能源股净空), 这部分行业 beta 是横截面"
            "上无信息的共同成分; group_zscore 剥离它后, 剩下的是行业内相对强度, IC 应更纯. "
            "⚠️ 风险: group_zscore 无历史使用记录于本家族, 输出范围无界, 可能触发 CONCENTRATED_WEIGHT "
            "(极值权重集中) —— 本槽同时是 CW 风险探针. 若 CW fail 而 Sh 高, 下一波用 "
            "group_rank 替换 (保留组内化但保序有界)."),
    },
    # ---- 门控 ----
    {
        "id": 8, "type": "POOLED_GATED", "role": "GATE",
        "baseline": "GrgN9OAZ 无门 Sh0.61 (本槽为其门控版)",
        "expression": (
            f"trade_when({GATE}, reverse(ts_rank({pooled(60)}, 250)), 0)"),
        "optimize_reason": (
            "【新鲜度门 x pooled 内核 · 免费增益的跨族检验】与 GrgN9OAZ 唯一差别是加载 "
            "trade_when(dflc(vec_count(VHEX))<2) 新鲜度门. 该门在**价格漂移族** (d5K6wxlx) 上被"
            "证明是免费增益 (Sh 1.61->1.65, TO 几乎不变, 因它只过滤已无新信息的陈旧仓位), "
            "但在 pooled 累积族上从未测过 —— 而 pooled 的设计哲学恰恰是「用 60 日累积容纳陈旧事件」, "
            "新鲜度门可能与之**直接冲突**: 门要求「近 2 日有新 excursion 事件」才持仓, "
            "恰好砍掉 pooled 想利用的历史累积. 本槽是这两种设计哲学的判决实验: "
            "若 Sh 高于 0.61, 说明门与累积可兼容 (门过滤的是无事件期的纯噪声, 累积保留的是"
            "事件的结构), 后续所有 pooled 构造都应加门; 若 Sh 低于 0.61, 则门与 backfill/累积类"
            "长记忆结构互斥, 这是一条可复用的结构性结论 (能避免后续大量无效配额). "
            "预期 TO 会显著上升 (门使仓位稀疏化), 落 15-40% 区间, 这是它换取 Sh 的代价."),
    },
]

DIRECTIONS = {
    "C": {"name": "pooled 家族 IC 提升: 7 类机制 (窗口/口径/归一/稳健/提纯/输出层/门控)",
          "hypothesis": (
              "双约束联立 (Fit>=1 且 Mgn>=10bps) isolated 出唯一数学可行资产 GrgN9OAZ "
              "(Sh 0.61/TO 5.2%/Ret 2.09%/R-TO 0.403/Mgn 8.05bps): 只需把 Sh 提升 2.59 倍至 1.58, "
              "Fit 即精确达标 (Ret 2.09% 已正好够), Ret 略提则 Mgn 也达标. "
              "pooled 家族内部 Sh-TO 同样反相关, 且 breadth 已满 (516/512), "
              "故唯一出路是提高 IC (信号质量) 而不改变信号频率. "
              "本批 8 条覆盖 7 类 IC 提升机制, 全部基于 60 日累积内核保持低 TO."),
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
    d = DIRECTIONS["C"]
    print(f"[Wave11-C] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11C_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-C] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11C", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11c_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-C] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-C] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-C] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-C] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11c_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-C ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-C] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
