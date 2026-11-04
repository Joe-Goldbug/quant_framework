"""
prescription_w3.py — Wave 3：母本 alpha 源头的三条未开线索
Wave 2 结论: (1) hump/signed_power 贡献≈0 (1.03 vs 1.03); (2) 中性化下沉是反向杠杆
  (subindustry 0.48 < industry 0.65 < sector 1.03) → 母本 alpha 是 sector 级语调倾斜;
  (3) 半衰期/新鲜度改造均下滑 (0.79 / 0.85) → 5 日等权核已近局部最优。
本波转向: 关注度基线窗口、PSV 重复计数的剥离、截面口径 (market vs sector)、尾部口径 (rank vs zscore)、
以及『情绪强度 / 情绪波动』的信息比率化。
"""

SEED_ID = "58jYLNXn"
PTC = "headline_positive_term_count_v2"
PSV = "headline_positive_score_value_v2"
NMC = "headline_news_mention_count_v2"


def core(base_d=30):
    return f"divide(multiply(s_log_1p({PTC}), {PSV}), add(ts_mean({NMC}, {base_d}), 0.1))"


BATCH = {
    "seed_id": SEED_ID,
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 20,
    "neutralization": "SECTOR",
    "truncation": 0.05,
    "category": "news",
    "known_fields": [PTC, PSV, NMC, "headline_negative_term_count_v2", "headline_sentiment_value_v2"],
    "items": [
        {
            "id": 1,
            "type": "MARKET_ZSCORE_NO_GROUP",
            "expression": f"zscore(ts_mean({core()}, 5))",
            "optimize_reason": (
                "沿 Wave 2 的归因外推：既然 group_zscore 的颗粒度越细分数越差（sector 1.03 > industry 0.65 > "
                "subindustry 0.48），说明母本的 alpha 主要是『谁能在一段时间里被正面新闻持续覆盖』这一较宽的倾斜，"
                "而非子行业内的精细选股。本条把这个单调关系推到端点：干脆不做分组，直接全市场 zscore。"
                "若分数继续上升，则证明之前的 sector 分组本身就在削弱信号，最优口径是市场级；"
                "若分数回落，则说明 sector 分组恰好是那层『刚好合身』的中性化，可据此锁定母本结构不动，"
                "把优化预算全部转向信号内容而非截面处理。注意 settings 仍保留 SECTOR 中性化，"
                "本节只改表达式口径，两者之差即为『分组标准化』的净效应。"
            ),
        },
        {
            "id": 2,
            "type": "BASELINE_60D",
            "expression": f"group_zscore(ts_mean({core(60)}, 5), sector)",
            "optimize_reason": (
                "单因子替换（关注度基线长度）：母本用 30 日 ts_mean 作为『自身常态新闻量』基准，"
                "30 日约 1.5 个自然月，覆盖不了一次完整的财报季；一旦公司进入财报/路演密集期，"
                "分母被系统性抬高，此后把真实的高情绪日误判为『平淡』，造成信号在前瞻性最强的事件窗口里反而衰减。"
                "60 日窗口横跨一个完整财报周期，基线更接近『结构性关注度』而非『事件期关注度』，"
                "理论上能保留更多事件驱动的信号幅度。本条同时改变信号的持续性（分母更稳、比值更跳），"
                "因此会一并观察换手变化，是关注度基线这一维度上最关键的一次扫描。"
            ),
        },
        {
            "id": 3,
            "type": "BASELINE_120D",
            "expression": f"group_zscore(ts_mean({core(120)}, 5), sector)",
            "optimize_reason": (
                "单因子替换（基线长度上探）：与第 2 条构成 30/60/120 三点扫描，120 日≈半年，"
                "此时分母基本等于『这家公司被媒体关注的长期产能』，信号退化为『当期正向词量相对于长期媒体产能的利用率』。"
                "这一口径的优势是极度稳健——单次公关事件、一次性诉讼报道都不会污染基线，"
                "信号的多空两端更接近『谁在被超额报道且是正面报道』这一纯信息维度；"
                "代价是对关注度结构变化（如新晋热门股）反应滞后。三点扫描可确定母本最优的记忆尺度，"
                "并判断母本 1.03 的瓶颈是否来自基线太短导致的信号稀释。"
            ),
        },
        {
            "id": 4,
            "type": "COUNT_X_SIGNED_TONE",
            "expression": (
                f"group_zscore(ts_mean(divide(multiply(s_log_1p({PTC}), headline_sentiment_value_v2), "
                f"add(ts_mean({NMC}, 30), 0.1)), 5), sector)"
            ),
            "optimize_reason": (
                "结构改造（强度 × 有符号语调）：母本外层乘子 PSV 是『正向词占比』，值域 [0,1] 恒非负，"
                "因此无论负面新闻多么密集，信号都不会变成负数——这正是全簿 87% 空头、"
                "空头端退化为一堆无新闻股的物理原因。本条把乘子换成 headline_sentiment_value_v2"
                "（(正向词-负向词)/(正向词+负向词)，值域 [-1,1]，同为 news7 内部字段，零 PV 污染），"
                "于是信号变成『关注度归一化的新闻强度 × 有符号语调』：报道很多且整体正面 → 强多头；"
                "报道很多且整体负面 → 强空头；无新闻 → 自然接近 0。"
                "这保留了母本赖以取胜的词量量级（Wave 2 已证 level 结构才是 alpha 源），"
                "同时把多空两端都锚在真实新闻事件上，直接针对 Margin 与可投资性症状。"
            ),
        },
        {
            "id": 5,
            "type": "LOG_PER_ARTICLE_RATIO",
            "expression": (
                f"group_zscore(ts_mean(divide(s_log_1p({PTC}), add(s_log_1p({NMC}), 1)), 5), sector)"
            ),
            "optimize_reason": (
                "结构改造（对数口径自洽化）：母本分母用线性新闻条数、分子用对数词量，两者处于不同变换空间，"
                "导致『新闻量很大的公司』分母被过度放大、信号被系统性阉割——这是母本多头只有 111 只、"
                "仓位集中在中等关注度公司的物理原因。本条把分母也取 s_log_1p，使分子分母同为对数尺度，"
                "比值成为『每单位对数新闻量的对数正向词量』，即对数意义下的情绪密度，"
                "既保留了母本『关注度归一化』的因果核心，又消除了尺度不匹配带来的非线性偏斜，"
                "让高关注度与低关注度公司处在同一可比量纲上，从而拓宽有效多空两端。"
            ),
        },
        {
            "id": 6,
            "type": "GROUP_RANK_SECTOR",
            "expression": f"group_rank(ts_mean({core()}, 5), sector)",
            "optimize_reason": (
                "单因子替换（尾部口径）：Wave 2 已证明 winsorize 与基准同分（1.04 vs 1.03），说明母本的分数"
                "并非由个别极端值撑起，而是来自整个截面的排序信息。既然如此，z-score 的线性加权就属多余，"
                "改用 group_rank 的分位等权在统计上更稳健：它对分布形状不敏感、对异常值免疫、"
                "在 sector 内样本量波动时方差更小，并且天然把多空两端拉成对称（母本 111 长 / 716 空的不平衡将被抹平）。"
                "若本条 Sharpe 不低于基准而 Margin 明显上升，则可确定母本的收益来自排序而非幅度，"
                "后续所有处方都应建立在分位口径之上。"
            ),
        },
        {
            "id": 7,
            "type": "IR_CORE_SECTOR",
            "expression": (
                f"group_zscore(divide(ts_mean({core()}, 20), add(ts_std_dev({core()}, 20), 0.01)), sector)"
            ),
            "optimize_reason": (
                "结构改造（信号质量化）：Wave 2 显示单纯换平滑核只会掉分（0.79/0.85），说明问题不在平滑，"
                "而在『同一信号对不同标的的置信度被一视同仁』。本条把母本核心改造为信息比率结构："
                "分子是 20 日情绪强度均值，分母是同一序列的 20 日标准差，比值度量『每单位情绪波动换来多少情绪强度』。"
                "持续被正面覆盖且强度稳定的公司获得高权重，忽高忽低、被正负报道交替拉扯的公司权重被压制——"
                "这恰好针对母本 Investability Sharpe 仅 0.55、risk_neutralized 仅 0.65 的『仓位压在噪音股』症状。"
                "该结构不改任何字段与量纲，只重组时间维统计量，是 Sharpe 提升空间最大的一条。"
            ),
        },
        {
            "id": 8,
            "type": "PSV_AS_OUTER_WEIGHT",
            "expression": (
                f"group_zscore(multiply(ts_mean(divide(s_log_1p({PTC}), add(ts_mean({NMC}, 30), 0.1)), 5), {PSV}), sector)"
            ),
            "optimize_reason": (
                "结构改造（PSV 重新定位）：第 4 条验证 PSV 是否冗余，本条给出它的另一种用法做对照。"
                "母本把 PSV 与被取对数的 PTC 相乘，等于在『对数证据』之后再乘一个 [0,1] 强度系数，"
                "会把已经压缩过的尾部再抬一次，方向不可控。本条先把 PTC 除以关注度基线得到纯净的情绪强度，"
                "再用 PSV 作为『情绪纯度』的外层权重：只有当一个标的的新闻里正向词占比确实高时，"
                "它的词量强度才被完整计入；若词量多但正负混杂（PSV 低），强度被自动折价。"
                "这在因果上更自洽——『说得多』与『说得一致地正面』是两个独立维度，应当相乘而非嵌套，"
                "且外乘位置保证了量纲仍为一阶强度，不再出现 words²/articles。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_w3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots)")
    assert len(BATCH["items"]) == 8, "卡槽未装满 8 条"
