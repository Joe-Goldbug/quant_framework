# -*- coding: utf-8 -*-
"""Gate1 Wave11-B · 内核去日更化: backfill 参数轴扫描 + 配对对照 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== ★ 本批立项依据: Wave11-A 失败中挖出的战略资产 ===

Wave11-A (基本面首攻) 全批 Sh<=0.51 无一达标, 且红队先验审计 6/6 命中:
z-score 对 ffill 阶梯序列只剩 sign x recency (跳变幅值被 std 归一化完全吞噬),
且 867 字段中 estimate/consensus 字段数为 0 => 经典 PEAD 在本数据集数学不可实现.
A 组 (PEAD) 4 条关闭.

**但失败中挖出了本战役迄今最优的 TO-Sh 权衡资产**:
    MP0E7qxL = reverse(rank(ts_backfill(divide(CTO, add(vec_count(VHEX),1)), 3)))
    -> Sh 1.20 / TO 68.84% / Ret 5.32% / 2Y 1.16 / sub 1.18 / L/S 424/418 / fail=[]

对照无 backfill 的 CONFLUENCE-1 (Sh 1.59 / TO 114.6% / Ret 7.52%):
    TO x 0.60 而 Sh 仅 x 0.75 —— 远优于 pooled 结构 (Sh 0.61 @ TO 5.2%).
机制: 事件日稀疏内核 + ts_backfill(内核, N) = 非事件日持仓**冻结 N 天**.
这是"内核去日更化": 内核只在事件日重算, 其余日沿用旧值 => 换手随 N 反比下降.

**而 backfill 窗口参数轴 N in {5,10,20,40} 从未被测过** (N=3 与 N=60 之间是完整空白).

=== Fit 反解定标 (Fit = Sh x sqrt(|Ret| / max(TO, 0.11))) ===
  要 Fit>=1 且 Sh>=1.58, 必须 Ret >= max(TO,0.11)/1.58^2:
    TO=11% -> Ret>=4.41% | TO=20% -> 8.01% | TO=30% -> 12.0% | TO=50% -> 20.0%
  家族最高 Ret 为 SH165 的 7.86% (@TO 119.8%), 第二为 d5K6wxlx 7.70%.
  ==> **唯一数学可行的目标区是 TO<=11% 且 Ret 保住 4.4%+, 或 TO<=20% 且 Ret>=8%**.
  本批测绘 TO-Sh 权衡曲线, 直接检验"backfill 拉长持仓期"能否把家族拖进该区.

=== 红队对 Wave11-A 的批次级批评 (本批已内化) ===
  "8 条里 0 条对照实验 (无 reverse 双子/无无门引擎/无窗口探针), 该有的对照一个没有"
  ==> 本批 8 槽中 4 条为**配对对照**: 槽5 = 槽2 去门 (分离 dflc 门贡献),
      槽6 = 槽2 换 pooled 内核 (分离内核贡献), 槽1-4 互为窗口参数梯度.

=== 三象限设计 ===
  象限一 (槽1-4): CTO/count+1 内核 + dflc<2 门 + backfill N in {5,10,20,40}
      —— 直接测绘 TO-Sh 权衡曲线, 寻找 Fit 可行区的入口
  象限二 (槽5-6): 配对对照 —— 分离 dflc 门与内核选择的边际贡献
  象限三 (槽7-8): 新轴探索 —— Agent-RV 首选的"盘前状态反转"轴 (315 基线零使用)
      + SI 门 (Wave11-A 唯一正面信号, 强度为 PE 门 2 倍) x pooled x backfill(20)

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

EOC, TON = "news_eod_close", "news_ton_last"
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
CNT1 = f"add({CN}, 1)"                       # CW 已解分母 (16/16 实证)
CTO = f"subtract({EOC}, {TON})"              # 家族最高 Ret 分子 (7.86%)
RATIO = f"divide({CTO}, {CNT1})"             # 事件日稀疏内核
GATE = f"less(days_from_last_change({CN}), 2)"
U, D = "news_max_up_amt", "news_max_dn_amt"
POOLED = f"divide({U}, add({U}, {D}))"       # pooled 内核 (Wave10 证明低 TO 但 Sh 仅 0.61)


def bf_gate(n):
    """backfill 参数轴: 内核冻结 n 天 + 新鲜度门"""
    return f"trade_when({GATE}, reverse(rank(ts_backfill({RATIO}, {n}))), 0)"


SLOTS = [
    # ================= 象限一: backfill 参数梯度 =================
    {
        "id": 1, "type": "BF5_GATE", "role": "BF_AXIS",
        "baseline": "MP0E7qxL backfill(3) Sh1.20/TO68.8%",
        "expression": bf_gate(5),
        "optimize_reason": (
            "【backfill 参数轴 · N=5】内核 = CTO/count+1 (家族最高 Ret 分子 + CW 已解分母), "
            "外层 ts_backfill(内核,5) 使非事件日持仓冻结 5 天, 再包 SH165 的新鲜度门. "
            "已测锚点: N=3 时 Sh 1.20 / TO 68.84% / Ret 5.32%; 无 backfill 时 Sh 1.59 / TO 114.6%. "
            "本槽把冻结期从 3 天拉长到 5 天, 预期 TO 降到 45-55%, Sh 落到 1.05-1.20. "
            "按 Fit 反解, 该区间需 Ret>=20-25% 才达标 —— 本槽大概率不过 Fit, 其价值在于"
            "给 N=10/20/40 提供曲线的第二个点, 与槽2-4 共同构成完整的 TO-Sh 权衡梯度. "
            "经济学: 新闻事件对价格的冲击不是当日完全吸收, 而是有数日的持续再定价 "
            "(Hong-Stein 1999 渐进信息扩散), 冻结持仓是对该持续性的正确匹配."),
    },
    {
        "id": 2, "type": "BF10_GATE", "role": "BF_AXIS",
        "baseline": "本批核心扫描点, 槽5/6 的配对基准",
        "expression": bf_gate(10),
        "optimize_reason": (
            "【backfill 参数轴 · N=10 · 本批核心扫描点】冻结期 10 天, 预期 TO 落到 25-35% "
            "(约为无 backfill 版的 0.28 倍), Sh 预期 0.85-1.10, Ret 4-6%. 这个区间是关键: "
            "若 Sh 能守住 1.0 且 Ret 5%, 则 Fit = 1.0*sqrt(5/30) = 0.41, 仍差 2.4 倍; "
            "但如果曲线比预期平缓 (Sh 守住 1.2+), 则 Fit = 1.2*sqrt(5/30) = 0.49, "
            "说明需要继续拉长 N 而非本批能到达. 本槽同时是槽5 (无门对照) 与槽6 "
            "(pooled 内核对照) 的配对基准, 是全批归因的枢纽. 经济学同槽1: 10 个交易日的 "
            "冻结对应约两周的事件冲击持续期, 与新闻事件的半衰期量级一致."),
    },
    {
        "id": 3, "type": "BF20_GATE", "role": "BF_AXIS",
        "baseline": "无 (N=20 从未测)",
        "expression": bf_gate(20),
        "optimize_reason": (
            "【backfill 参数轴 · N=20 · Fit 保护区入口探测】冻结期 20 天, 预期 TO 落到 "
            "12-20% 区间 —— 这正是 Fit 公式 turnover 下限保护 max(TO,0.11) 开始生效的门槛! "
            "若 Sh 仍 >=0.9 且 Ret>=4%, 则 Fit = 0.9*sqrt(4/15) = 0.46; 若 TO 真的压到 11% "
            "以下, 则分母被 0.11 兜住, Fit = 0.9*sqrt(4/11) = 0.54. 本槽是全批最有机会"
            "进入 Fit 低换手可行区的一槽, 也是检验"TO 压到 11% 时 Sh 还剩多少"的唯一探针. "
            "风险: 冻结 20 天意味着信号严重过期, Sh 可能崩到 0.5 以下 —— 那将证明"
            "backfill 路线的极限在 N=10 附近, 后续应转投"慢变量内核"而非"快内核长冻结". "
            "经济学: 20 日对应一个月的冲击持续, 超过多数新闻事件的半衰期, 本槽实为路线极限测试."),
    },
    {
        "id": 4, "type": "BF40_GATE", "role": "BF_AXIS",
        "baseline": "YPxOGboo backfill(60) pooled 内核 Sh1.17/TO37.8%",
        "expression": bf_gate(40),
        "optimize_reason": (
            "【backfill 参数轴 · N=40 · 曲线上界封顶】冻结期 40 天, 预期 TO 落到 6-12%, "
            "深入 Fit 下限保护区. 但 40 天冻结的信号陈旧度极高, Sh 预期 0.4-0.8. "
            "本槽的判读价值大于达标价值: 若本槽 Sh 仍 >=0.8, 说明该内核的 alpha 有超长半衰期 "
            "(事件冲击持续两个月), 则 N=20-40 区间值得精扫; 若 Sh <0.4, 则 backfill 路线"
            "整体封顶于 N<=10, 家族必须换内核 (慢变量) 而非调参数. 与 YPxOGboo "
            "(pooled 内核 + backfill 60 + group_rank, Sh 1.17 / TO 37.8%) 构成跨内核对照: "
            "同窗口量级下 CTO 内核 vs pooled 内核的 Sh-TO 权衡差异. 本槽若 Sh 高于槽3, "
            "说明衰减比预期慢; 若低于槽3 且差距大, 说明 40 天已越过 alpha 半衰期拐点."),
    },
    # ================= 象限二: 配对对照 (红队要求) =================
    {
        "id": 5, "type": "BF10_NOGATE", "role": "CONTROL",
        "baseline": "槽2 的无门配对 (唯一变量 = dflc<2 新鲜度门)",
        "expression": f"reverse(rank(ts_backfill({RATIO}, 10)))",
        "optimize_reason": (
            "【配对对照 · 分离 dflc 新鲜度门的边际贡献】与槽2 完全同构, 唯一差别是去掉 "
            "trade_when(dflc<2) 外层门. 此前 SH165 与 CONFLUENCE-1 的对照证明该门在"
            "无 backfill 结构上是"免费增益" (Sh 1.61->1.65, TO 几乎不变), 但在 backfill(10) "
            "结构上从未检验过 —— 而 backfill 本身已把持仓期拉长到 10 天, 新鲜度门可能"
            "从"过滤过期信号的有用装置"退化为"无谓的仓位削减" (甚至有害, 因为它砍掉的正是"
            "backfill 想保留的冻结期). 本槽与槽2 的差直接读出该门在长持仓结构上的真实符号. "
            "若槽2 > 槽5, 门仍然有益; 若槽5 > 槽2, 则门与 backfill 机制冲突, 后续全部"
            "backfill 构造应去门. 这是本批最重要的单条归因实验."),
    },
    {
        "id": 6, "type": "BF10_POOLED", "role": "CONTROL",
        "baseline": "槽2 的内核配对 (唯一变量 = CTO vs pooled 内核)",
        "expression": (
            f"trade_when({GATE}, reverse(rank(ts_backfill({POOLED}, 10))), 0)"),
        "optimize_reason": (
            "【配对对照 · 分离内核选择的边际贡献】与槽2 唯一差别是内核从 CTO/count+1 换成 "
            "pooled = U/(U+D) (新闻后最高价涨幅占比). 此前证据: pooled 内核在无 backfill 时 "
            "Sh 0.48 / TO 8.8%, 在 backfill 60 时 Sh 1.17 / TO 37.8% (YPxOGboo); "
            "而 CTO 内核在 backfill 3 时 Sh 1.20 / TO 68.8%. 两者都优于各自的无 backfill 版, "
            "但在同一 backfill 窗口下从未正面对比过. 本槽回答: 在 N=10 这个中间窗口, "
            "哪种内核的 TO-Sh 权衡更优? pooled 的经济学 = 新闻后价格发现的净方向 (幅度域), "
            "CTO 的经济学 = 新闻时刻至收盘的漂移 (时点域). 若 pooled 明显更优, 则家族最优"
            "内核应从 CTO 切换到 pooled, 这是一个会改变后续所有批次基座的结论. "
            "CW 风险: pooled 内核在 YPxOGboo 上 CW ok, 本槽同结构, 预期安全."),
    },
    # ================= 象限三: 新轴探索 =================
    {
        "id": 7, "type": "PREPOS_REVERSAL", "role": "NEW_AXIS",
        "baseline": "无 (nws12_mainz_ton* 三字段在 315 基线零使用)",
        "expression": (
            f"trade_when(less(days_from_last_change(vec_count(nws12_mainz_tonlast)), 3), "
            f"ts_backfill(reverse(rank(divide(subtract(vec_avg(nws12_mainz_tonlast), vec_avg(nws12_mainz_tonlow)), "
            f"add(subtract(vec_avg(nws12_mainz_tonhigh), vec_avg(nws12_mainz_tonlow)), vec_avg(nws12_mainz_tonlast))))), 3), 0)"),
        "optimize_reason": (
            "【全新轴 · 盘前会话位置反转 (Agent-RV 首选轴)】内核 = TON 时刻价格在"
            "盘前 [最低, 最高] 区间中的相对位置, 取 reverse. 三个字段 (tonlast/tonlow/tonhigh) "
            "同属 nws12_mainz_* 报表族, cov 均 0.9733, 同缺失模式 = 同一事件行产出, "
            "**315 基线中 pre_news 极值历来只作反应内核的归一化分母出现, 从未独立作预测子**. "
            "经济学: 事件前买入压力把价格推向盘前高点的吸筹型资金, 在期望上持续为过度反应 —— "
            "新闻落地后缺乏新增买盘接力, 价格向会话中位回落 (均值回复). 反向假说同样可辩护"
            "(盘前强 = 知情买入, 应延续), 故本槽符号需双向验证, 若为显著负值则立刻补 reverse 双子. "
            "结构上: 事件快照内核 + backfill(3) 冻结 + dflc<3 新鲜度门, 是 Agent-RV 论证的"
            "「内核去日更化」标准形态. 本槽信息增益为全批最高: 它同时检验 (a) mainz 快照族"
            "是否含独立于 eod/ton 价格族的信息 (b) 盘前位置轴是否成立."),
    },
    {
        "id": 8, "type": "SIGATE_POOLED_BF20", "role": "NEW_AXIS",
        "baseline": "Wave11-A 槽7 SI门 Sh0.51@TO13.2% (本战役唯一正面)",
        "expression": (
            f"trade_when(greater(rank(news_short_interest), 0.88), "
            f"reverse(rank(ts_backfill({POOLED}, 20))), 0)"),
        "optimize_reason": (
            "【SI 门 x pooled 内核 x backfill(20) 三重合流】Wave11-A 槽7 是本战役基本面"
            "维度唯一正面信号: SI>0.88 门 + indx_perf 引擎 + dflc 门拿到 Sh 0.51 @ TO 13.2% "
            "/ R-TO 0.215 (超家族包络 0.125) / rnSh 0.38, 且 **SI 门强度是 PE 门的 2 倍"
            " (0.51 vs 0.26)** —— 判决"知情空头提前定价"假说成立方向. 本槽把该门的成功"
            "三要素换到更强的内核上: (a) 引擎从 indx_perf (当日超额收益, 家族内核克隆) "
            "换成 pooled (低 TO 已验证), (b) backfill 从无拉到 20 天, (c) 保留 SI>0.88 门. "
            "经济学: 高空头兴趣股票的边际交易者是已建仓的知情空头, 公开新闻到达时信息成分"
            "已被提前定价, 残余价格变动为噪声交易者过度反应, 而 pooled 内核度量的正是"
            "新闻后价格发现的净方向 —— 过度反应在期望上持续被修正 (反转), 且该修正发生在"
            "数十天的尺度上 (卖空约束使定价缓慢), 故 backfill(20) 的冻结与机制时间尺度匹配. "
            "⚠️ 红队警告: 门控 6/6 先例为逆选择, 本槽若 Sh<0.3 则确认门控路线整体证伪, "
            "SI 门的正面信号仅是 dflc 门的副产品. 字段数 = SI + U + D = 3, 合规."),
    },
]

DIRECTIONS = {
    "B": {"name": "内核去日更化: backfill 参数轴 (N=5/10/20/40) + 配对对照 + 新轴",
          "hypothesis": (
              "Wave11-A 失败中挖出战略资产 MP0E7qxL (backfill(3) 内核: Sh1.20/TO68.8%), "
              "证明「事件日稀疏内核 + ts_backfill(内核,N) = 非事件日持仓冻结 N 天」能以 "
              "TO x0.60 的代价换 Sh x0.75, 远优于 pooled 结构. 而 backfill 窗口参数轴 "
              "N in {5,10,20,40} 从未被测 (N=3 与 N=60 之间完整空白). Fit 反解表明唯一"
              "数学可行区为 TO<=11% 且 Ret>=4.41% (Sh=1.58), 本批测绘 TO-Sh 权衡曲线以定位"
              "该区入口. 同时内化红队批次级批评: 8 槽中 4 条为配对对照 (槽5 分离 dflc 门, "
              "槽6 分离内核选择), 杜绝「全是新结构无一对照」."),
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
           "sign", "abs", "sqrt", "log", "power"}
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
    d = DIRECTIONS["B"]
    print(f"[Wave11-B] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11B_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-B] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11B", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11b_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-B] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-B] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-B] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-B] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11b_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-B ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-B] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
