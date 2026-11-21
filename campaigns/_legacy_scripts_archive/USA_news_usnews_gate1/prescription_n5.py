"""
prescription_n5.py — Gate 1 · Batch 5：在 news12 族内冲 Sharpe（归一化层级 × 三字段复合 × 外层算子）

【本轮的硬约束（研究员逐条给定）】
  1) 主信号必须是 **news 分类**数据集字段，且带 theme
     （news12 = USA/D1/NEWS 1.2×；已核验 A1QoKbMY 的 MATCHES_THEMES 位列 pass）
  2) 2 ≤ 字段数 ≤ 3   3) 严格经济学假设   4) 零 fail + 零警告   5) PROD_CORR < 0.70
  E5V905m0 的教训（全绿但 PROD 0.8915）说明：必须换到 news 主信号，才可能同时避开 prod 与 theme 两项。

【为什么这一批的唯一出路是把 Sharpe 从 1.3x 推过 1.58】
  族内已被钉死的事实（FALS_NEWS12_001/002/006/008、FALS_MARGIN_001）：
    · 换手与 Margin：原始字段 TO 结构性 110-130%，单笔收益 ≈2bps，延长视界无效；
    · 平滑：Ret 衰减快于 TO，Margin 反而降；
    · bucket：平台不产出数值。
  唯一未耗尽的自由度是**信息的组合方式**：本账户该族已知最强单口径为 |Sh| 1.37（原始、TO 129.9%），
  而 TOP1000/delay1 的阈值是 Sh 1.58 / Fit 1.0 / 2Y 1.58。缺口 ≈15%。
  补这 15% 的三条正交路径，各占若干槽：
    (a) 归一化层级：不归一 vs 当日区间倍数 vs 30日标准差 vs 30日量能 z —— 同一口径换分母；
    (b) 三字段复合：把「方向纯度」与「当日异常度」放进同一个比值（2 字段表达式无法承载此信息）；
    (c) 外层算子：rank 压缩尾部、zscore 保留尾部 —— 截面分布形状对 Sharpe 的直接影响。

【统一包裹与 settings】
  reverse(rank|zscore( ts_decay_linear( ts_backfill(x, 3), 6 ) ))
  —— 顺序严格对齐母本 WjL5Wlxx（先回填、后衰减、最外层横截面变换），是本账户已跑通的算子链。
  settings 冻结在已验证的组合（TOP1000 / delay1 / decay 6 / INDUSTRY / trunc 0.025 / nan ON），
  该组合下 WjL5Wlxx 与 A1QoKbMY 均未触发 HIGH_TURNOVER / CONCENTRATED_WEIGHT 类警告，
  因此任何新警告都可归因到表达式本身。

【经济学总纲】
  新闻触发的一次性价格位移 = 信息定价（永久）+ 流动性冲击（数日）+ 收盘拍卖机械压力（数日）。
  本批全部 8 槽都只做一件事：用「方向的纯度」除以「当日的异常度」，
  即把「这场单边行情相对它自己这一天有多反常」量出来。经济直觉是 Ball-Brown 的标准化意外
  （standardized unexpected move）：反常度越高、方向越纯，说明市场越可能把一次性事件外推成趋势，
  随后的回归幅度越大。归一化层的选择决定了「异常度」用什么当标尺 —— 这正是本批要测的。
"""

UPA = "news_max_up_amt"        # 新闻后最大上冲（价格单位）
DNA = "news_max_dn_amt"        # 新闻后最大下冲（价格单位）
UPR = "news_max_up_ret"        # 新闻后最大上冲（%）
DNR = "news_max_dn_ret"        # 新闻后最大下冲（%）
EODC = "news_eod_close"
EODV = "news_eod_vwap"
EODH = "news_eod_high"
EODL = "news_eod_low"
ATR14 = "news_atr14"           # 14 日 ATR（价格单位）
ATRR = "news_atr_ratio"        # 当日区间 / 20 日 ATR
INDX = "news_indx_perf"        # 相对 SPY 同期超额位移
VOLZ = "news_vol_stddev"       # 当日量能相对 30 日均值的 z 值
TON = "news_ton_last"          # 新闻到达瞬间价
OPEN = "news_open"             # 当日开盘价
HIEX = "news_high_exc_stddev"  # (EODHigh − TONLast)/30日收盘标准差
LOEX = "news_low_exc_stddev"   # (TONLast − EODLow)/30日收盘标准差


def sm(core, outer="rank"):
    """回填 3 日 → 线性衰减 6 日 → 横截面变换（对齐母本算子链）"""
    return f"reverse({outer}(ts_decay_linear(ts_backfill({core}, 3), 6)))"


BATCH = {
    "seed_id": "news12_sharpe_push_v1",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 6,
    "neutralization": "INDUSTRY",
    "truncation": 0.025,
    "nan_handling": "ON",
    "category": "news",
    "known_fields": [UPA, DNA, UPR, DNR, EODC, EODV, EODH, EODL, ATR14, ATRR,
                     INDX, VOLZ, TON, OPEN, HIEX, LOEX],
    "items": [
        {
            "id": 1,
            "type": "PURE_ASYMMETRY_AMT",
            "expression": sm(f"divide(subtract({UPA}, {DNA}), add(add({UPA}, {DNA}), 0.01))"),
            "optimize_reason": (
                "方向纯度（价格单位），3 字段：最大上冲、最大下冲、+0.01 除零保护。"
                "值域 (−1,1)、以 0 为对称锚：0 = 当日上下对称，+1 = 单边冲高，−1 = 单边杀跌。"
                "经济机制：单边行情里没有对手盘的均衡，所有持仓者处在同一侧的浮盈里，"
                "随后的获利因此更同步、更集中 —— 这是外推偏差（extrapolation bias）的可交易后果。"
                "与本族已知最强的『上冲占比』（|Sh|1.37）在数学上是仿射关系（占率 = (纯度+1)/2），"
                "放在最外层 rank 下二者等价 —— 因此本槽实际上是那条 1.37 锚的**复刻槽**，"
                "作用是标定：在**这一套 settings**（trunc 0.025 + decay 6 + 回填 3）与阈值表下，"
                "该锚能否接近 1.58。若它仍停在 1.3x，则后续槽必须靠归一化与复合来补缺口，"
                "而非再换口径 —— 这是整批的校准点，也是防止后面 7 槽无意义烧配额的前置判据。"
            ),
        },
        {
            "id": 2,
            "type": "ASYMMETRY_PER_RANGE_ANOMALY",
            "expression": sm(
                f"divide(subtract({UPR}, {DNR}), add({ATRR}, 1))", "zscore"
            ),
            "optimize_reason": (
                "方向纯度 / 当日区间异常度，3 字段：最大上冲%、最大下冲%、当日区间倍数。"
                "这是本批的**主攻槽**：分子是方向纯度，分母是『今天这根日线相对它自己的 20 日 ATR 有多反常』。"
                "经济机制直指 Ball-Brown 的标准化意外 —— 同样 6% 的单边上冲，"
                "若发生在一根平常的日线里只是普通波动；若发生在 2.5 倍 ATR 的异常日里，"
                "则是事件冲击被外推的标志。**方向纯度 × 异常度**是二者的信息乘积，"
                "比任何单一维度都更接近『市场把一次性事件当趋势的证据强度』。"
                "外层用 zscore 而非 rank：rank 把两端各 50% 的观测压成均匀分布，"
                "而这一族的可交易信息恰恰集中在极端日（反常日）；zscore 保留尾部权重，"
                "让截面分布里最有信息的那 1-2% 标的主导组合，truncation 0.025 负责封顶。"
                "分母 add(.,1) 把倍数偏移拉回 0 轴（ATRR=0 表示当日无波动）。"
            ),
        },
        {
            "id": 3,
            "type": "ASYMMETRY_PER_VOLUME_Z",
            "expression": sm(
                f"divide(subtract({UPR}, {DNR}), add({VOLZ}, 1))", "zscore"
            ),
            "optimize_reason": (
                "方向纯度 / 当日量能 z 值，3 字段：最大上冲%、最大下冲%、30 日量能 z 值。"
                "与槽 2 同构但换了标尺：槽 2 用波动当标尺（今天有多反常），本槽用量能当标尺（有多少人参与）。"
                "经济机制是 Amihud 的非流动性溢价逻辑：同样幅度的单边行情，若伴随极高的异常成交量，"
                "说明是信息驱动的真实重定价（价格发现完成、无需回归）；"
                "若成交量平平却出现大幅位移，说明是流动性稀缺下的临时冲击（少量订单推动价格），必然回归。"
                "用量能做分母等于只保留『无量单边行情』这一类，即最纯粹的流动性冲击。"
                "必须与 FALS_NEWS12_005 划清界限：那条证伪的是**乘性缩放**"
                "（把信号乘上量能因子，引入了高波动低收益的暴露，Sh 翻负 −0.44）；"
                "本槽是**除性归一**，把『每单位异常成交量的价格冲击』当信号，方向与含义完全相反。"
                "若本槽强于槽 2，说明该族的可交易性由流动性而非波动决定 —— 这会直接改写后续的归一化选择。"
            ),
        },
        {
            "id": 4,
            "type": "CLOSE_LOCATION_IN_RANGE",
            "expression": sm(
                f"divide(subtract({EODH}, {EODC}), add(subtract({EODH}, {EODL}), 0.01))"
            ),
            "optimize_reason": (
                "收盘价在新闻后区间中的位次，3 字段：新闻后最高、收盘、新闻后最低。"
                "(EODHigh − EODClose)/(EODHigh − EODLow) 值域 [0,1]、无量纲，0 = 收在最高、1 = 收在最低。"
                "它测的不是幅度，而是**尾盘还剩多少买盘**：收在最高说明尾盘仍有持续净买盘，收在最低则相反。"
                "经济机制是收盘拍卖的机械成分：被动基金按收盘价成交、做市商在收盘前调整库存、"
                "指数基金按收盘价再平衡 —— 与信息无关、随后必然逆转。"
                "它与槽 1-3 的根本差别：分子分母同源于同一天的区间量，"
                "因此完全不含价格水平、波动率与大盘信息，是整批**信息重叠度最低、量纲最干净**的构造，"
                "也是家族去相关（PROD_CORR）的主要候选。"
                "本账户历史证据显示该口径风险轮廓最优（rnSh 1.04 / InvSh 0.71 / DD 10.3%），"
                "在低换手与低回撤两项上是全批的保险槽。"
            ),
        },
        {
            "id": 5,
            "type": "CLOSE_VS_VWAP_ATR",
            "expression": sm(f"divide(subtract({EODC}, {EODV}), {ATR14})"),
            "optimize_reason": (
                "收盘相对新闻后 VWAP 的偏离 / 14 日 ATR，3 字段：收盘、新闻后 VWAP、ATR14。"
                "分母用新闻后 VWAP 而非新闻时刻价，测的是**最后一批进场资金的浮盈亏状态**："
                "收盘高于新闻后 VWAP ⇒ 新闻后进场者平均浮盈 ⇒ 处理效应（disposition effect）"
                "会在随后数日形成持续卖压；反之则形成补仓买盘。两种机制都发生在数日尺度上，"
                "与回填 3 日 + 衰减 6 日的时间常数自然匹配。"
                "除以 ATR14 把偏离换算成『多少个正常交易日的真实波幅』，"
                "使信号与股价水平、个股波动率彻底脱钩 —— 这是改善 investability Sharpe 的关键一步"
                "（母本用 DayOpen 归一，等于承认 2% 的位移在所有股票上意义相同，"
                "高波动股因此被系统性选入，拉低了子宇宙可投资性）。"
                "本槽与槽 4 是两个互补的『收盘强度』度量（区间位次 vs 成交量加权均价），"
                "两者差值可直接读出尾盘压力来自价格路径还是成交分布。"
            ),
        },
        {
            "id": 6,
            "type": "EXCESS_DRIFT_PER_RANGE_ANOMALY",
            "expression": sm(f"divide({INDX}, add({ATRR}, 1))"),
            "optimize_reason": (
                "市场调整异常漂移 / 当日区间倍数，2 字段：相对 SPY 超额位移、当日区间倍数。"
                "分子 news_indx_perf 已扣掉同期 SPY 变动，是纯个股特异位移 —— "
                "这一步剔除的是行业/市场共振，不剔除就会得到高 β 的伪 alpha（该族旧版本 investability 偏低的根因）。"
                "分母把位移换算成『多少个正常交易日的波动』，即标准化意外。"
                "取 reverse：标准化冲击越大 ⇒ 市场越可能过度外推 ⇒ 随后回吐。"
                "它与槽 2 的差别在**方向信息**：槽 2 的分子是『上冲与下冲的差』（路径形态），"
                "本槽的分子是『收盘相对新闻时刻的净位移』（结果）。"
                "形态与结果是两个不同的观察面 —— 若本槽强于槽 2，"
                "说明市场对「结果」而非「过程」外推，这对后续构造方向的选择是决定性的。"
            ),
        },
        {
            "id": 7,
            "type": "PURE_ASYMMETRY_RET",
            "expression": sm(f"divide({UPR}, add({UPR}, {DNR}))"),
            "optimize_reason": (
                "上冲占比（百分比口径），2 字段：最大上冲%、最大下冲%。"
                "这是本族已知最强的单一构造（|Sh| 1.37，价格单位版）在**百分比口径**下的版本。"
                "与槽 1 的唯一差别是量纲：价格单位的上冲在高股价股票上天然更大，"
                "百分比把它除回去，等价于按自身价格水平自归一，从而在跨股票比较时消掉规模暴露。"
                "与槽 1（纯度口径）构成三重对照：仿射等价性检验 + 量纲检验 —— "
                "若二者指标完全雷同，说明 FALS_NEWS21_002（仿射等价陷阱）确实适用于本族，"
                "后续只保留其一；若百分比版更强，则说明该族的边缘是**收益率性质**的过度反应，"
                "与股价水平无关。这条信息对后续构造的优先级排序价值很高。"
            ),
        },
        {
            "id": 8,
            "type": "STDEV_EXCITATION_SHARE",
            "expression": sm(f"divide({HIEX}, add({HIEX}, {LOEX}))"),
            "optimize_reason": (
                "波动标准化的上冲占比，2 字段：上冲/30 日收盘标准差、下冲/30 日收盘标准差。"
                "与槽 7 的口径完全平行，但两个分量**已经除以 30 日收盘标准差**，"
                "因此测的是『以个股自身波动为单位的路径不对称』，"
                "既不受股价水平影响、也与当日 ATR 倍数无关 —— 是槽 1/7 的最纯净版本。"
                "它与槽 1（不归一）、槽 2（当日 ATR 归一）在同一 settings 下并排，"
                "构成一次完整的**归一化层级消融**：不归一 / 当日区间 / 30 日标准差。"
                "胜出者会直接写进知识库，后续所有 news12 构造按它归一，"
                "不必再花配额在归一化维度上试错 —— 这是本批最可能沉淀成方法论的一条槽。"
                "经济上，用自身波动为单位的不对称度还自带风险控制效果："
                "高波动股票的 30 日标准差估计噪声大，标准化后权重反而被压低，"
                "对 DD 与 CONCENTRATED_WEIGHT 都是利好。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_n5.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']}, uni={BATCH['universe']})")
    assert len(BATCH["items"]) == 8
