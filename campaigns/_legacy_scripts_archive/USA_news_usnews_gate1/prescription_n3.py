"""
prescription_n3.py — Gate 1 · Batch 3：新闻事件后的「异常漂移」过度反应（news12 内部字段）

【前两批的裁决（白盒，全部来自实测）】
  · Batch 1 us_equity_news（8 个 VECTOR 情感字段）：最高 |Sh| 0.62，6/8 槽 TO 83~108% → 该源信噪比过低，废弃。
  · Batch 2 ai_news_scores（RavenPack 式事件情感 + 95% 置信区间）：最高 |Sh| 0.37，TO 79~126%，
    8 槽 2Y Sharpe 全负 → 方向性零边缘，废弃。
  · 账户既有证据（OS 池 news 金字塔）：news12 的「事件后价格位移」族 |Sh| 1.27~1.30、
    Margin 17~18bps、TO 65%，fitness 0.38 —— 是 news 分类里唯一强度足够的通道。
    其缺陷是 2Y Sharpe 1.39 与 CLUSTER_TEST 1.16 未达 1.58，且 TO 贴近 70% 上限。

【本批的经济学主线：新闻后的「异常」漂移 = 反应不足与过度反应的分离】
  news12 交付的是**事件时刻的价格快照**：TONLast（新闻到达瞬间价）、EODClose、EODVWAP、
  EODHigh/EODLow、最大上冲/下冲幅度、ATR14、30 日量能 z 值、以及相对 SPY 的同期超额变动。
  这与前两批的根本差别：前两批测量的是「文本说了什么」，本批测量的是「市场听到之后做了什么」。
  行为的可交易性远高于文本，因为价格位移是机构真金白银投票的结果，而文本需要被解读两次
  （模型解读文本、我们再解读模型）。这解释了 0.37 vs 1.30 的强度差。

  统一的因果命题：**新闻触发的一次性价格位移里，只有一部分是信息定价，其余是流动性冲击与情绪外推。**
  二者无法直接观测，但可以用「位移」除以不同的**尺度/条件变量**把它分离出来：
    (a) 除以 ATR / 区间宽度  → 单位正常波动的异常度（是否为「异常」位移）
    (b) 除以成交量 z 值      → 位移是否有量能支撑（有量=信息，无量=流动性冲击）
    (c) 除以空头比例        → 位移是否处于挤压敏感区
    (d) 上冲/下冲之差        → 位移的方向不对称度（情绪外推的标志）
    (e) 收盘在区间内的位置    → 尾盘买盘强度（收盘拍卖机制的机械压力）
  8 个卡槽 = 5 个尺度变量 × 2 个位移口径（超额收益 / 绝对价格) + 1 个纯不对称 + 1 个纯收盘位次。

settings: USA / TOP1000 / delay 1 / decay 6 / INDUSTRY / truncation 0.025 / nanHandling ON
        （与账户中 news12 族已实证的最优 settings 完全对齐，保证可归因；
          FALS_NEWS12_007 已证 STATISTICAL 对该族全面净负，故不重复试错）
"""

INDX = "news_indx_perf"          # ((EODClose-TONLast)/TONLast) - ((SPYClose-SPYLast)/SPYLast) 市场调整超额位移
ATRR = "news_atr_ratio"          # 当日区间 / 20 日 ATR
ATR14 = "news_atr14"             # 14 日 ATR（价格单位）
UP_R = "news_max_up_ret"         # 新闻后最大上冲（%）
DN_R = "news_max_dn_ret"         # 新闻后最大下冲（%）
EODC = "news_eod_close"
EODV = "news_eod_vwap"
EODH = "news_eod_high"
EODL = "news_eod_low"
VOLZ = "news_vol_stddev"         # 当日量能相对 30 日均值的 z 值
HI_EXC = "news_high_exc_stddev"  # (EODHigh-TONLast)/30日收盘标准差
LO_EXC = "news_low_exc_stddev"   # (TONLast-EODLow)/30日收盘标准差
SI = "news_short_interest"       # 空头比例


def rev(x):
    return f"reverse(zscore(ts_backfill({x}, 3)))"


BATCH = {
    "seed_id": "news12_eventdrift_v1",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 6,
    "neutralization": "INDUSTRY",
    "truncation": 0.025,
    "nan_handling": "ON",
    "category": "news",
    "known_fields": [INDX, ATRR, ATR14, UP_R, DN_R, EODC, EODV, EODH, EODL,
                     VOLZ, HI_EXC, LO_EXC, SI],
    "items": [
        {
            "id": 1,
            "type": "ABNORMAL_DRIFT_PER_RANGE",
            "expression": rev(f"divide({INDX}, add({ATRR}, 1))"),
            "optimize_reason": (
                "市场调整后的异常漂移 / 当日区间倍数（2 字段：news_indx_perf + news_atr_ratio）。"
                "经济机制：news_indx_perf 已经剔除 SPY 同期变动，是纯粹的个股特异位移——"
                "这一步至关重要，因为新闻日的位移有相当部分是行业/市场共振，"
                "不剔除就会得到一个高 β 的伪 alpha（账户里 news12 旧族 2Y Sharpe 上不去、"
                "Investability 也偏低的根因就在这里）。"
                "但『位移 5%』在不同波动的股票上意义完全不同：对一只日波动 1% 的公用事业股是 5 个西格玛事件，"
                "对一只日波动 8% 的生物科技股只是平常的一天。除以当日区间/20 日 ATR 倍数，"
                "把位移换算成『多少个正常交易日的波动』，即标准化的事件冲击强度，"
                "对应 Ball-Brown 意义上的『标准化意外』。"
                "取 reverse：标准化冲击越大说明市场越可能过度外推，随后回吐。"
                "ts_backfill(3) 处理无新闻日的快照缺口（事件型数据的标准做法），"
                "避免非事件日出现 NaN 导致持仓塌缩。本槽是整批的机制标定锚。"
            ),
        },
        {
            "id": 2,
            "type": "EXCURSION_ASYMMETRY_REVERSAL",
            "expression": rev(
                f"divide(subtract({UP_R}, {DN_R}), add(add({UP_R}, {DN_R}), 0.01))"
            ),
            "optimize_reason": (
                "冲测不对称度的反转（2 字段：最大上冲% + 最大下冲%）。"
                "经济机制：(上冲 − 下冲)/(上冲 + 下冲) 是当日在新闻之后的**路径不对称度**，"
                "值域 (−1,1)、以 0 为对称锚，量纲在比值中完全相消。"
                "它测量的不是漂移的方向，而是『盘中曾经多强 / 曾经多弱』的相对幅度——"
                "在行为金融上这是外推偏差最直接的测量：投资者记住的是盘中摸到的高点，"
                "而不是收盘价，所以上冲远大于下冲的股票会被系统性地高估，随后回吐。"
                "账户既有证据支持这个方向：该比值在原始未平滑时的 |Sharpe| 达 1.37（本族最强单一构造），"
                "但原始换手 130% 不可用；本槽用 ts_backfill(3) + settings decay 6 把换手压回门禁内，"
                "并保留其方向信息，是本批最有希望在强度上突破的主攻槽。"
                "分母 +0.01 是除零保护（两极值可能同时为 0，即当日几乎无位移）。"
            ),
        },
        {
            "id": 3,
            "type": "CLOSE_PRESSURE_PER_ATR",
            "expression": rev(f"divide(subtract({EODC}, {EODV}), {ATR14})"),
            "optimize_reason": (
                "收盘订单流压力 / ATR（3 字段：收盘价 + 新闻后 VWAP + 14 日 ATR）。"
                "经济机制：news_eod_vwap 是『新闻时刻至收盘』的成交均价，"
                "收盘价高于该均价意味着新闻之后进场的人平均是浮亏的买入方——"
                "即尾盘存在净买入压力（可能是被动资金调仓、也可能是散户追高）。"
                "把它除以 ATR14 而不是除以事件条数，是相对既有实现的一处实质性改进："
                "旧写法 divide(…, vec_count(...)) 的量纲是『美元/条』，与个股价格水平强相关，"
                "本质上混入了规模因子；除以 ATR 后量纲化为『多少个正常波动单位』，"
                "信号与股价水平、市值彻底脱钩，这应当直接改善可投资性与子宇宙 Sharpe。"
                "取 reverse：尾盘净买入压力越大，越可能是流动性/情绪驱动的错价，随后回归。"
                "这是 Graham-Harvey 意义上『收盘拍卖机制约束下的临时价格压力』，"
                "与信息类信号在机制上完全正交。"
            ),
        },
        {
            "id": 4,
            "type": "DRIFT_PER_VOLUME_SUPPORT",
            "expression": rev(f"divide({INDX}, add({VOLZ}, 1))"),
            "optimize_reason": (
                "量能标准化的异常漂移（2 字段：市场调整位移 + 当日量能 z 值）。"
                "经济机制：同样幅度的新闻后位移，若伴随极高的异常成交量，说明是信息事件引发的"
                "真实重定价（大量资金在重新估值，价格发现完成度高）；若成交量平平却出现大幅位移，"
                "说明是流动性稀缺下的临时冲击（少数订单就能推动价格），随后必然回归。"
                "把位移除以 30 日量能 z 值，等价于按『成交量支撑度』给冲击打折："
                "有量支撑的位移被压低、无量位移被放大，从而只保留流动性冲击这一类。"
                "这在市场微观结构文献里是标准的 Amihud 逻辑：价格冲击与成交量成反比，"
                "单位成交量带来的冲击越大，随后的反转越强。"
                "这条与第 1 槽用区间 normalize 是两条独立路径（一个用波动、一个用量能），"
                "二者的差值可以直接读出『究竟是波动尺度还是流动性尺度决定可交易性』，"
                "为后续四批的归一化选择定调。"
            ),
        },
        {
            "id": 5,
            "type": "DRIFT_PER_UPSIDE_EXCURSION",
            "expression": rev(f"divide({INDX}, add({HI_EXC}, 0.01))"),
            "optimize_reason": (
                "位移 / 上冲幅度（2 字段：市场调整位移 + 标准化上冲）。"
                "经济机制：news_high_exc_stddev 是 (EODHigh − TONLast) 除以 30 日收盘标准差，"
                "即『盘中最多涨了多少个标准差的波动』。"
                "它和收盘位移的比值刻画的是**位移的持续性**："
                "比值接近 1 说明价格一路走高并收在高位（信息定价、趋势健康）；"
                "比值很小说明盘中冲高但收盘回落（典型的情绪脉冲 + 获利了结），"
                "这类股票随后往往继续走弱。因此该比值是『位移质量』而非『位移幅度』的度量，"
                "与第 1/4 槽的尺度归一在信息维度上正交。"
                "取 reverse 后，信号 = 做空『冲高但没守住』、做多『跌下去但没继续跌』的股票，"
                "经济叙事对应处置效应（disposition effect）："
                "投资者在浮盈时过早卖出，压抑了真正的利好漂移，之后才补涨。"
                "该槽是整批唯一把『盘中路径形态』与『收盘结果』放在同一个比值里的构造。"
            ),
        },
        {
            "id": 6,
            "type": "SHORT_SQUEEZE_CONDITIONED_DRIFT",
            "expression": rev(f"divide({INDX}, add({SI}, 0.01))"),
            "optimize_reason": (
                "空头比例条件化的异常漂移（2 字段：市场调整位移 + 空头比例）。"
                "经济机制：news_short_interest 是流通股中被卖空的比例，"
                "它是『被迫买盘』的存量池。新闻引发的上涨在空头比例高的股票上包含相当比例的"
                "挤空买盘——这部分买盘不是估值判断，而是风控驱动的强制平仓，"
                "一旦挤空完成就会消失，价格回落。因此『位移 / 空头比例』本质上是"
                "位移里『有多少被挤压机制放大』的度量：比值越大，越说明位移是被挤压而非信息驱动。"
                "取 reverse 即做空挤压放大的上涨、做多挤压放大的下跌。"
                "该槽在账户里是全新维度：既有的 news12 战役从未引入空头比例条件化，"
                "因此它的 PnL 与家族其它成员相关性最低，是去相关的主力候选。"
                "分母 +0.01 避免零空头股票除零（此时信号被放大，需靠 truncation 0.025 与 "
                "zscore 的双侧对称性控制尾部）。"
            ),
        },
        {
            "id": 7,
            "type": "STANDARDIZED_EXCURSION_SPREAD",
            "expression": rev(f"subtract({HI_EXC}, {LO_EXC})"),
            "optimize_reason": (
                "标准化上冲与下冲之差（2 字段：high excursion − low excursion）。"
                "与第 2 槽用百分比不同，本槽用的是**已经除以 30 日收盘标准差**的标准化幅度，"
                "因此它是『以个股自身波动为单位的路径宽幅』之差，"
                "天生不受股价水平与个股波动率影响，也与当日的 ATR 倍数无关。"
                "经济机制上这是最强的『外推偏差』度量：投资者对盘中能摸到的极端价位记得最牢，"
                "而上冲 3 个标准差 vs 下冲 0.5 个标准差，会让市场对这只股票形成"
                "『它有爆发力』的叙事，推高后续的追涨需求，随后被基本面修正。"
                "取 reverse 即做空这种『叙事被路径放大』的标的。"
                "与第 2 槽构成干净的对照：同一经济命题的两种标准化方式（自比 vs 波动标准化），"
                "哪一个给出更高的 Sharpe，就直接决定后续批次用哪个量纲。"
                "该槽不含任何漂移均值信息，只含路径信息，因此与第 1/3/4/5 槽天然低相关。"
            ),
        },
        {
            "id": 8,
            "type": "CLOSE_LOCATION_IN_RANGE",
            "expression": rev(
                f"divide(subtract({EODH}, {EODC}), add(subtract({EODH}, {EODL}), 0.01))"
            ),
            "optimize_reason": (
                "收盘在事件区间中的位次（3 字段：事件后最高 + 收盘 + 事件后最低）。"
                "经济机制：(EODHigh − EODClose)/(EODHigh − EODLow) 是收盘价距离当区间最高点的相对距离，"
                "值域 [0,1]、无量纲，0 表示收在最高、1 表示收在最低。"
                "它是收盘拍卖机制与尾盘订单流最纯粹的度量：收在最高点说明尾盘仍有持续的净买盘，"
                "收在最低点说明尾盘有持续的净卖盘。"
                "与第 3 槽（收盘 vs VWAP）相比，本槽不涉及成交量加权，只看区间位置，"
                "因此不受大单成交分布的影响，是更稳健的『收盘强度』代理。"
                "经济上，新闻日收盘的强弱包含明显的机械成分："
                "被动基金按收盘价成交、做市商在收盘前调整库存，这些行为与信息无关，"
                "会在次日被逆转。因此取 reverse，做空『收在最高』的强势股、做多『收在最低』的弱势股。"
                "这是本批唯一的纯区间位置构造，不含任何位移幅度信息，"
                "与其余 7 槽在信息集上几乎不重叠，是家族去相关的最后一块拼图。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_n3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']}, uni={BATCH['universe']})")
    assert len(BATCH["items"]) == 8
