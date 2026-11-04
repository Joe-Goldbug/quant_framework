# -*- coding: utf-8 -*-
"""Gate1 Wave11-A · 基本面维度首攻 (USA/TOP1000/delay1/INDUSTRY/decay=6).

=== ★ 本批的立项依据: 一项覆盖地图侦察揭示的全新维度 ===

对全战役 315 个 (表达式 x settings) 样本做字段覆盖清点, 发现 867 个字段中
已测表达式只触及约 94 个 token, 而**整个基本面维度从未被测过**:

    news_eps_actual        MATRIX cov=0.9646   实际 EPS        (季度更新 -> 原生慢变量)
    news_short_interest    MATRIX cov=0.8720   空头兴趣比      (双周更新 -> 原生慢变量)
    news_pe_ratio          MATRIX cov=0.9662   市盈率          (日更价格派生)
    news_dividend_yield    MATRIX cov=0.8534   股息率          (日更价格派生)
    news_indx_perf         MATRIX cov=0.9713   个股相对SPY超额收益 (事件窗口)
    nws12_{mainz,prez,afterhsz}_epsactual  VECTOR cov=0.87/0.76/0.38

**为什么这是对的方向 (而非又一次参数微调)**:
家族 315 样本的结构性困境已被定量锁定 —— 全部 Sh>=1.58 的样本 TO 全部 >=116.9%,
全部 TO<=70% 的样本 Sh 全部 <=1.19, 两集合交集为 0. 根因是家族信号源全部为
「事件当日价格反应」字段 (news_eod_close / news_max_up_amt / excursion 等), 日更
=> rank 后日更 => 换手结构性锁死 110-140%.

而 Fit = Sh x sqrt(|Ret| / max(TO, 0.11)) 的 turnover 下限保护意味着:
    Sh=1.58 时 TO<=11% 只需 Ret>=4.40%; TO=20% 需 8.01%; TO=30% 需 12.0%.
**TO<=11% 是一个门槛跳变台阶, 而要落到这个台阶, 信号源本身必须是慢变量** ——
这在算子层无解 (已实证: ts_backfill 平滑使 Sh 崩, ts_decay_linear 只提 Sh 不降 TO,
decay settings 对快结构无效), 唯一出路是换信号源.

基本面字段正是本数据集里仅有的慢变量信号源: EPS 季度更新 (每季仅跳变 4 次),
空头兴趣双周更新 (FINRA 申报周期). 其经济学支撑为金融学最坚实的异象之一:
    PEAD  (Ball & Brown 1968; Bernard & Thomas 1989) 盈余公告后漂移持续约 60 个交易日
    空头约束 (Diamond & Verrecchia 1987) 卖空约束使坏消息吸收缓慢

=== 本批 8 槽的两条路线 ===
  A 组 (槽1-4) PEAD 盈余域 [Agent-EPS 交付]:
    用 ts_zscore(EPS, 63) 构造标准化意外盈余 (SUE) 代理. 因 867 字段中无任何
    estimate/consensus/analyst 字段, 惊喜只能用自身历史标准化 —— 这恰好规避了
    「日更流量字段减自身 ts_mean 放大噪声」的证伪结论, 因为 EPS 是季度更新,
    subtract(EPS, ts_mean(EPS,63)) 约等于最新公告 EPS 减上一期 EPS, 是干净的
    盈利改善度量. 方向为动量 (PEAD 是反应不足, 与家族的日内反转机制相反).
  B 组 (槽5-8) 慢变量基本面域 [Agent-SV 交付]:
    直接用 MATRIX 慢字段做信号主体 (S1/S2) 或做门控条件化 (G1/G4).
    Agent-SV 的字段频率判断: EPS/空头兴趣 = 原生慢变量 (可入 TO<=11% 区);
    PE/股息率 = 日更价格派生 (裸用必高 TO, 只能作序数门控).

=== 判读 ===
本批是**方向判决批**而非达标批: 若 A 组任一槽拿到 Sh>=1.0 且 TO<=20%, 则
「换信号源解 TO」的路线被首次实证, 后续全部预算压向该结构;
若 A 组 Sh 全部 <0.5, 则 PEAD 在本数据集 (新闻而非公告数据) 中不成立,
B 组的慢字段门控结果决定是否升级为门控字段复用.

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

# ---------- 公共构件 ----------
VHEX = "high_price_excursion_stddev"
CN = f"vec_count({VHEX})"
CNT1 = f"add({CN}, 1)"                       # CW 已解分母 (16/16 实证, 禁 ts_backfill 版)
EPSM = "nws12_mainz_epsactual"
EPSA = "actual_earnings_per_share_value"
EPSP = "nws12_prez_epsactual"
# 季度更新 EPS 的时序 zscore (SUE 代理); backfill 250 为无害兜底
Z63 = lambda f: f"ts_zscore(ts_backfill(vec_avg({f}), 250), 63)"
DFLC2 = f"less(days_from_last_change({CN}), 2)"

SLOTS = [
    # ================= A 组: PEAD 盈余域 =================
    {
        "id": 1, "type": "PEAD_SUE63_DUAL", "role": "PEAD",
        "baseline": "无 (EPS 字段全库 0 样本)",
        "expression": f"rank(add({Z63(EPSM)}, {Z63(EPSA)}))",
        "optimize_reason": (
            "【基本面维度首攻 · TO<=11% 主攻槽】双源一致惊喜: 两个独立新闻源的 EPS 各自做 "
            "63 日时序 zscore 后相加. 机制 = PEAD (Ball & Brown 1968; Bernard & Thomas 1989): "
            "机构受注意力约束与保守主义偏误影响, 对盈余公告只能缓慢定价, 超预期股票未来 60 "
            "个交易日收益期望持续为正. 双源相加抑制单源提取噪声. 关键在换手结构: EPS 是季度 "
            "更新 (每季仅跳变 4 次), ts_zscore 输出形状天然就是 PEAD 衰减曲线, 信号以月度尺度 "
            "变化 —— 这是 315 样本中唯一有机会落入 Fit 的 turnover 下限保护区 (TO<=11%) 的信号源. "
            "按标定公式, 若 TO 落到 8% 而 Sh 达到 1.2, 则 Fit 自动达标 (1.2*sqrt(Ret/0.08)). "
            "方向为动量 (不取 reverse), 因 PEAD 是反应不足而非过度反应, reverse 会使期望收益变负."),
    },
    {
        "id": 2, "type": "PEAD_SUE63_CNT", "role": "PEAD",
        "baseline": "CONFLUENCE-1 的 CW 安全骨架",
        "expression": f"rank(divide({Z63(EPSM)}, {CNT1}))",
        "optimize_reason": (
            "【CW 安全骨架 x 盈余信号】与槽1 同信号源, 但换上家族已验证 16/16 CW ok 的 "
            "add(vec_count,1) 裸计数分母. 机制 = 盈余惊喜的市场传导依赖新闻关注度作为注意力 "
            "通道: 当日 excursion 计数越多, 信息被消化越快, 剩余漂移越少, 故按关注度归一化等价于 "
            "按注意力折扣缩放漂移强度. 本槽目的有二: (a) 检验 PEAD 强度是否依赖新闻关注度 "
            "(若 Sh 显著高于槽1, 则条件化有效, 该骨架值得承载后续全部盈余构造); "
            "(b) 给 A 组提供一个 CW 确定安全的对照点 —— 槽1 是纯 rank 型, 若触发 CW 则本槽是退路. "
            "预期 TO 略高于槽1 (计数日更会抬换手), 落在 20-35% 区间, 这是它换取 Sh 的代价."),
    },
    {
        "id": 3, "type": "PEAD_UNDERREACT", "role": "PEAD",
        "baseline": "无 (EPS x excursion 交互全库首测)",
        "expression": (
            f"rank(multiply({Z63(EPSM)}, "
            f"subtract(1, rank(ts_mean(vec_avg({VHEX}), 5)))))"),
        "optimize_reason": (
            "【反应不足交互 · 方向性判决实验】构造「盈余惊喜大 但 公告期价格反应小」的显式交互项: "
            " subtract(1, rank(ts_mean(excursion,5))) 是反应不足度 (价格反应分位越低值越大), "
            "与 SUE 相乘后放大 PEAD 最核心的成分. 机制 = 盈余惊喜大而价格反应小的股票是反应不足 "
            "最严重的样本, 受关注度约束的投资者尚未定价, 后续漂移期望最强. 本槽是方向判决实验: "
            "若显著正向而槽2 一般, 说明反应不足成分主导, 支持 A 组不取 reverse 的核心论证; "
            "若为负而槽2 正, 说明漂移由趋势成分主导, 机制叙事需修正为混合型. "
            "乘积极端值可能稀释信号, 但两个 rank 型相乘分布均匀, CW 风险低. "
            "TO 预期 30-50% (excursion 组件日更), 不主打低换手, 主打机制分离."),
    },
    {
        "id": 4, "type": "PEAD_PREGAP", "role": "PEAD",
        "baseline": "无 (跨 EPS 源相减全库首测)",
        "expression": f"rank(ts_zscore(subtract(ts_backfill(vec_avg({EPSP}), 250), ts_backfill(vec_avg({EPSM}), 250)), 63))",
        "optimize_reason": (
            "【盘前 vs 主板块报道差 · 信息扩散时差】两个 EPS 源分别对应盘前时段与主板块时段的 "
            "新闻报道. 当公司盘前发财报时, prez 源已更新而 mainz 源仍是旧值, 二者之差约等于惊喜 "
            "本身; 差不为零是「盈余信息在不同交易时段扩散不同步」的标记. 机制 = 日内交易者受时段 "
            "约束无法立即套平, 差值大的股票后续修正漂移期望持续同向 (信息扩散不完整, Hong-Stein "
            "1999 渐进信息扩散). 本槽与 A 组其他条的区别在于惊喜构造方式: 不是绝对水平而是跨源 "
            "时差, 信噪比特征不同. 两个源均季度更新, TO 预期 8-15%, 落进 Fit 可行区. "
            "风险: prez cov 0.7585 低于 mainz 0.8742, 共同覆盖会拉低持仓面至 220-240, "
            "但仍应远高于 CW 门槛. 若本槽 Sh 明显高于槽1, 说明时差信息比水平信息更干净."),
    },
    # ================= B 组: 慢变量基本面域 =================
    {
        "id": 5, "type": "SV_EPS_MINUS_SI", "role": "SLOWVAR",
        "baseline": "无 (news_eps_actual 与 news_short_interest 全库 0 样本)",
        "expression": (
            "rank(subtract(rank(subtract(news_eps_actual, ts_mean(news_eps_actual, 60))), "
            "rank(subtract(news_short_interest, ts_mean(news_short_interest, 60)))))"),
        "optimize_reason": (
            "【原生慢变量组合 · TO<=11% 唯一结构候选】两个字段均为 Agent-SV 判定的原生慢变量: "
            "EPS 季度更新 (cov 0.9646, 非公告日仍 populated 说明向前填充), 空头兴趣双周更新 "
            "(FINRA 申报周期, cov 0.872 的 13% 缺失正是监管数据的群体性结构缺失特征). "
            "机制 = 知情交易者通过卖空表达对盈利恶化股票的私有信息, 而卖空约束 (借券成本与召回 "
            "风险) 使该负面信息无法被即时完全定价; 盈余相对自身基线改善且空头兴趣未升高的股票, "
            "价格调整期望持续向上. 构造上先减自身 60 日均值 (时序归一, 对季度字段这是干净的改善 "
            "度量而非噪声放大), 再各自截面 rank 到 [0,1] 消除 EPS 绝对值与空头比的截面不可比性, "
            "最后相减. 无除法故无 CW 风险. 这是全批唯一有机会落入 TO<=11% 的构造, 但慢基本面 "
            "alpha 密度低, 诚实预期 Sh 0.4-1.2 —— 它的价值在于判决「TO<=11% 只能靠原生慢字段」"
            "这一结构性结论. 若 Sh>=1.3 则打开唯一低换手通路."),
    },
    {
        "id": 6, "type": "SV_PEGATE_INDXPERF", "role": "SLOWVAR",
        "baseline": "样本53-59 门控稀释先例 (0.8门 Sh0.24 / 0.9门 Sh0.44)",
        "expression": (
            f"trade_when({DFLC2}, trade_when(greater(rank(news_pe_ratio), 0.88), "
            f"reverse(rank(divide(news_indx_perf, {CNT1}))), 0), 0)"),
        "optimize_reason": (
            "【全批最现实通路 · 高 PE 门 x 市场调整引擎 x 新鲜度门 三重叠加】引擎 news_indx_perf "
            "= 个股相对 SPY 的事件窗口超额收益 (cov 0.9713, 全库 0 样本), 比家族现有 CTO 分子 "
            "更干净 (已剔除市场 beta). 除以 add(vec_count,1) 裸计数分母 = 按事件强度归一的超额 "
            "反应, 该骨架 16/16 CW ok. 外层 rank(news_pe_ratio)>0.88 门 = 只在最高 12% 估值 "
            "分组内交易. 机制 = 噪声交易者对高估值成长股的新闻更容易产生过度反应 (注意力与情绪 "
            "驱动, De Long et al. 1990), 而基本面套利资金受风格漂移约束不愿做空高 PE 股票, 事件日 "
            "超额收益的负向自相关在期望上只在高 PE 分组中持续为负 (反转获利). 三层设计各有依据: "
            "0.88 门参照已测门控样本 (0.8 门 TO 21.5% / 0.9 门 TO 17.1%) 预期把 TO 压到 12-17%; "
            "dflc 新鲜度门被证明是免费增益 (Sh 1.61->1.65) 且几乎不增 TO. 若引擎 Sh 保持 1.4-1.6 "
            "且门控保留 70-90% alpha, 则 Sh 1.0-1.4 @ TO 12-17% => Fit 0.7-1.1, 是边缘可过的形态. "
            "若复刻样本 53-59 的稀释幅度 (Sh 1.37->0.44) 则门控路线整体证伪."),
    },
    {
        "id": 7, "type": "SV_SIGATE_INDXPERF", "role": "SLOWVAR",
        "baseline": "样本55 (SI>0.8 门 + amt 引擎) Sh 0.51 弱正向先例",
        "expression": (
            f"trade_when({DFLC2}, trade_when(greater(rank(news_short_interest), 0.88), "
            f"reverse(rank(divide(news_indx_perf, {CNT1}))), 0), 0)"),
        "optimize_reason": (
            "【H-SI 假说判决实验 · 高空头兴趣门 x 同一引擎】与槽6 构成单变量对照: 引擎、分母、"
            "新鲜度门、门限分位全部相同, 唯一差别是门控字段 (PE vs 空头兴趣). 机制 = 高空头兴趣 "
            "股票的边际交易者是已建仓的知情空头, 公开新闻到达时信息成分已被提前定价, 残余价格变动 "
            "为噪声交易者过度反应, 该过度反应在期望上持续被修正. 但 Diamond-Verrecchia (1987) 的 "
            "约束假说给出相反预测: 卖空约束使坏消息吸收变慢, 则高空头组应表现出延续而非反转. "
            "本槽是两种假说的判决性对比: 若本槽显著弱于槽6, 说明约束假说相反成立 (空头约束使吸收 "
            "变慢), 高空头组不应做反转; 若本槽强于槽6, 说明知情空头提前定价假说成立, "
            "空头兴趣可升级为后续全部反转 alpha 的增益门控字段. 样本 55 已提供弱正向先例 (Sh 0.51). "
            "空头兴趣双周更新, 门本身变化慢, 对 TO 影响小."),
    },
    {
        "id": 8, "type": "SV_EPSFLOW_MINUS_SIFLOW", "role": "SLOWVAR",
        "baseline": "无 (同字段对的流量版, 与槽5 构成水平/流量 A-B)",
        "expression": (
            "rank(subtract(rank(ts_delta(news_eps_actual, 60)), "
            "rank(ts_delta(news_short_interest, 20))))"),
        "optimize_reason": (
            "【盈余流量减空头压力流量 · 与槽5 构成水平/流量 A-B 对照】同一字段对 (EPS + 空头兴趣), "
            "但把水平偏离换成流量: ts_delta(EPS,60) 是脉冲式 (公告后 60 天非零, 之间归零中性), "
            "ts_delta(SI,20) 近连续 (双周申报). 机制 = 盈余公告后投资者受注意力与处理成本约束而"
            "反应不足 (公告后漂移), 且空头兴趣上升代表知情做空压力在增加, 「盈余变化减去做空压力"
            "变化」衡量的基本面净改善在期望上预示持续的收益漂移. 与槽5 的对照价值在于: 若两槽"
            "同向显著, 则 H-SI 获双重确认 (水平与流量信息一致); 若分歧, 则水平与流量信息可分离, "
            "后续应分开使用. 构造上同样先 rank 后组合, 无原始单位截面运算, 无 CW 风险. "
            "TO 预期 3-10%, 是全批最低换手候选之一. 若本槽或槽5 的 Sh 达到 1.2 以上, "
            "则基本面慢变量路线首次被实证, 下一批全部预算压向该方向."),
    },
]

DIRECTIONS = {
    "A": {"name": "基本面维度首攻: PEAD 盈余域 (A组) + 原生慢变量域 (B组)",
          "hypothesis": (
              "315 样本的字段覆盖清点显示整个基本面维度从未被测 (867 字段中已测仅触及约 94 个 token). "
              "家族结构性困境 (Sh>=1.58 与 TO<=70% 交集为 0) 的根因是信号源全部为事件当日价格反应字段. "
              "Fit 公式的 turnover 下限保护 (max(TO,0.11)) 使 TO<=11% 成为门槛跳变台阶, "
              "而落到该台阶要求信号源本身是慢变量 —— 算子层已实证无解, 唯一出路是换信号源. "
              "基本面字段是本数据集仅有的慢变量源: EPS 季度更新, 空头兴趣双周更新. "
              "经济学支撑: PEAD (Ball-Brown 1968 / Bernard-Thomas 1989, 盈余公告后漂移约 60 交易日) "
              "与空头约束 (Diamond-Verrecchia 1987)."),
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
    d = DIRECTIONS["A"]
    print(f"[Wave11-A] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11A_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-A] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11A", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11a_{ts}.json"), "w", encoding="utf-8"),
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
            print(f"[submit-A] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-A] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-A] 静默轮询中 (前 60s 不输出)...", flush=True)
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
        print("[Wave11-A] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11a_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-A ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
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
    print("\n[Wave11-A] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
