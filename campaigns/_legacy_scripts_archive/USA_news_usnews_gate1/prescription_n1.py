"""
prescription_n1.py — Gate 1 · Batch 1：新闻语料的「精度加权语调 + 新息分解」

数据集: us_equity_news (US Equity Quantitative News Sentiment)
        coverage 0.9627 / 8 个 VECTOR 字段 / 每字段仅 ~20 条历史 alpha（生产库近乎空白 → PROD_CORR 天然低）

【为什么换到这一族（驱动源切换的实证依据）】
  · news7 族（headline_positive_term_count）已被 4 波 32 槽 + 前役 336 槽证明：|Sh|≥1.58 的行 TO 全部 ≥116.9%，
    TO≤70% 分支 Sh 上限 1.19 —— 「注意力折价」机制与换手/成本门禁物理不相容。
  · biasfree_analyst 族的 bl8Wd2Nq / vROQVzlA 已把「分析师粘性目标价」通道占满（族内 PnL 相关 0.82~0.95）。
  · 因此必须换『信息产生的第一现场』：新闻文本本身。且必须避开已被证伪的两个老路子
    （① 纯语调水平：news21 FALS_006/009 已证 1.17 天花板 + Margin 仅 2.8bps；② 关注度条数：FALS_010 已证零 alpha）。

【本批的经济学主线：精度加权 (precision weighting) 与 新息 (innovation) 分解】
  贝叶斯视角下，一条新闻对后验预期的边际影响 = 语调 × 该条新闻对该标的的信息精度。
  精度由三个可观测代理给出，且全部是数据集内自带的、无量纲的：
    (a) security_relevance_percentage  —— 文章与该公司真实相关的比例（伪提及 = 低精度噪声）
    (b) total_word_count_article      —— 报道深度（短讯 = 情绪脉冲，长文 = 事实与论证）
    (c) 文章内 (max − min) 情感跨度     —— 文章自身的观点一致性（跨度大 = 内部矛盾，语调不可信）
  同时必须把「存量语调水平」与「语调新息」严格分开：资产定价只对**新息**定价，存量语调只是风格暴露。
  8 个卡槽 = 3 个精度代理 × 2 个时间形态（水平/新息）× 1 个词典对照 × 1 个内部矛盾归一。
  每条都是 2~3 字段，零量价字段（数据集中无 close/returns），无 signed_power / hump / group_neutralize，
  无 add(rank, rank) 无量纲拼凑。

settings: USA / TOP1000 / delay 1 / decay 10 / STATISTICAL / truncation 0.08 / nanHandling ON
        （STATISTICAL 用于剥离规模/波动/动量风格暴露；news21 FALS_007 已证语调轴上统计中性化是 Sharpe 的唯一来源）
"""

SENT = "mean_sentiment_score_article"
MAXS = "maximum_sentiment_score"
MINS = "minimum_sentiment_score"
REL = "security_relevance_percentage"
WORDS = "total_word_count_article"
TAGGED = "sentiment_tagged_phrase_count"
POS = "count_positive_phrases"
NEG = "count_negative_phrases"

# 精度加权的当日语调（stock-day 标量）
A = f"multiply(vec_avg({SENT}), divide(vec_avg({REL}), 100))"
# 语调新息（相对自身 20 日常态）
A_DEV = f"subtract({A}, ts_mean({A}, 20))"
# 裸语调新息（不加精度权重，留给 3 字段槽做分歧归一）
S_DEV = f"subtract(vec_avg({SENT}), ts_mean(vec_avg({SENT}), 20))"


def z(x):
    return f"zscore({x})"


BATCH = {
    "seed_id": "us_equity_news_v1",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 10,
    "neutralization": "STATISTICAL",
    "truncation": 0.08,
    "nan_handling": "ON",
    "category": "news",
    "known_fields": [SENT, MAXS, MINS, REL, WORDS, TAGGED, POS, NEG],
    "items": [
        {
            "id": 1,
            "type": "RELEVANCE_WEIGHTED_TONE_LEVEL",
            "expression": z(A),
            "optimize_reason": (
                "精度加权语调水平（2 字段：mean_sentiment_score_article + security_relevance_percentage）。"
                "经济机制：一条新闻对该公司后验估值的影响，等于语调乘以它究竟在讲这家公司的程度。"
                "security_relevance_percentage 是数据供应商对『文章与标的真实相关比例』的估计，"
                "在财经新闻里大量文章只是提及代码（行业综述、指数新闻、附带提名的财报汇总），"
                "这类文本的语调与该公司未来现金流无关，属于纯噪声；把它按相关度打折，"
                "等价于贝叶斯后验里按信息精度加权，能在不改变排序大体形状的前提下显著提升信噪比。"
                "取水平（不取新息）是刻意为之：本槽是整批的机制标定锚，"
                "用最朴素的『新闻说好话且真的关于你』来测这一族的经济学是否成立。"
                "如果连这条都跑不出 |Sharpe|≥1，说明该数据源的语调方向本身不可交易，后续 7 槽应整体改道；"
                "如果它合格而新息版不合格，则说明市场对语调水平定价充分、只对变化定价，"
                "这会把第二波的研究预算整体推向 ts_delta/新息方向。"
                "最外层 zscore 保证组合零均值、两侧建仓，避免 group_rank 外层导致单边持仓的虚假 Margin。"
            ),
        },
        {
            "id": 2,
            "type": "RELEVANCE_WEIGHTED_TONE_INNOVATION",
            "expression": z(A_DEV),
            "optimize_reason": (
                "精度加权语调的新息（2 字段）。与第 1 槽的唯一变化是减去自身 20 日常态。"
                "经济机制：资产价格已经吸收了此前的新闻存量（语调水平），"
                "真正驱动未来收益的是『本周新闻比过去一个月更好还是更差』——"
                "这正是 Ball-Brown 的盈余意外逻辑在文本层面的对应物："
                "不是好消息本身，而是好于预期的消息。20 日窗口对应机构调仓的一个自然周期"
                "（月度 rebalance 叠加约 4 周的信息扩散），既足够长以平滑单日噪声，"
                "又足够短以保留新息的可交易部分。"
                "第 2 槽与第 1 槽构成整批最关键的一对正交对照：两者共享同一分子的精度加权，"
                "差异只在『水平 vs 新息』，因此它们之间的表现差可以干净地归因为市场定价的是存量还是流量。"
                "这一对照在任何新闻 alpha 文献里都是首先要确认的前提，"
                "把它放在首批而不是后期，是为了避免像 news7 那样在错误的时间形态上烧掉 30+ 个配额。"
            ),
        },
        {
            "id": 3,
            "type": "INTRA_ARTICLE_AMBIGUITY_TSTAT",
            "expression": z(
                f"divide({S_DEV}, add(subtract(vec_avg({MAXS}), vec_avg({MINS})), 0.1))"
            ),
            "optimize_reason": (
                "以文章内情感跨度归一的语调新息（3 字段：mean + max + min）。"
                "本槽刻意不加相关度权重，让『内部矛盾归一』这一维度被纯净地隔离出来。"
                "经济机制：同一篇文章里最正面句子与最负面句子之间的情感跨度，"
                "刻画的是这篇文章自身观点的内部一致性——跨度小说明通篇一致（论据集中、信息可信），"
                "跨度大说明文章在同时陈述利好与风险（观点矛盾、方向不可交易）。"
                "把新息除以这个跨度，等于把它换算成『多少个文章内部情感单位』，"
                "是一个截面上的 t 统计量，直接给观点矛盾的股票降权、给观点一致的股票加权。"
                "这与资产定价里的不确定性折价一脉相承：信息精度低时投资者要求更高风险补偿，"
                "但我们的目标是横截面选股，所以需要的是精度高的信号而非高补偿的标的。"
                "分母加 0.1 是量纲保护（情感分数值域有限，跨度可能为 0，避免除零放大）。"
                "该槽同时是结构上的去相关主力：它把权重从『新息最大的股票』移向『新息显著且观点一致』的股票，"
                "与纯新息排序的截面相关性天然更低，且不像乘法加权那样引入波动率风格暴露。"
            ),
        },
        {
            "id": 4,
            "type": "EMOTIONAL_DENSITY_REVERSAL",
            "expression": (
                "reverse("
                + z(
                    f"ts_mean(divide(vec_sum({TAGGED}), add(vec_sum({WORDS}), 1)), 20)"
                )
                + ")"
            ),
            "optimize_reason": (
                "情感词密度的反向（2 字段：sentiment_tagged_phrase_count + total_word_count_article）。"
                "经济机制：情感词占全文词数的比例，衡量的是这篇报道『在讲事实还是在表态』。"
                "调查性/事件性报道 factual 内容占主体，情感词密度低；公关稿、快讯、观点评论"
                "情感词密度高但信息含量低。当一只股票的新闻流被高情感密度文本占据时，"
                "说明近期价格波动主要由情绪驱动而非现金流变化驱动 —— "
                "这正是 De Long 等 (1990) 噪声交易者模型里『情绪冲击』的可观测代理，"
                "其可交易推论是随后的均值回复。"
                "因此信号取反向：情感密度高 → 做空；密度低（冷静的事实报道）→ 做多。"
                "这里刻意用 vec_sum 的比值而非 vec_avg 的比值：密度本质是『词数加权的比例』，"
                "按文章合并计数才能得到真实的全文词频密度，逐篇平均会被大量短文主导。"
                "20 日平滑是把单日的公关稿脉冲摊平，得到『近一个月的信息质地』这一慢变量，"
                "这也让本槽的换手显著低于其余各槽，是专门为 Margin 门禁（≥10bps）预留的低频卡槽："
                "低换手 × 中等收益即可同时满足 Fitness 与 Margin，而不必去追 1.58 Sharpe 的高频端点。"
            ),
        },
        {
            "id": 5,
            "type": "DEPTH_WEIGHTED_TONE_INNOVATION",
            "expression": z(
                f"multiply({A_DEV}, rank(vec_avg({WORDS})))"
            ),
            "optimize_reason": (
                "报道深度加权的新息（3 字段：mean + relevance + word_count）。"
                "经济机制：报道长度是『信息量』最原始也最稳健的代理 —— "
                "一篇 600 词的调查报道包含具体数字、管理层表态、竞争对手对比，"
                "其语调变化对应真实的现金流预期修正；一篇 40 词的快讯只是复述标题，"
                "语调变化几乎全是措辞噪声。把新息乘以 rank(平均词数)（值域 [0,1] 的无量纲权重），"
                "等价于按信息量做精度加权，与第 1/2 槽按相关度加权是同一原理的两个独立代理："
                "相关度回答『是不是在讲你』，长度回答『讲得多深』，二者在实证上并不高度相关，"
                "因此这是两条独立的去相关路径。"
                "与第 3 槽（除法归一）相比，本槽用乘法加权：除法会放大大跨度股票的权重，"
                "乘法只会压低小权重，风险轮廓更保守、尾部更干净，"
                "在 CONCENTRATED_WEIGHT 与 DD 检查上更安全。"
                "该槽与第 2 槽（纯新息）的差值，恰好量化了『深度筛选』这一步本身的边际贡献，"
                "是把工程量化为收益的对照设计。"
            ),
        },
        {
            "id": 6,
            "type": "SLOW_TONE_MIGRATION_60_20",
            "expression": z(f"ts_delta(ts_mean({A}, 60), 20)"),
            "optimize_reason": (
                "慢迁移语调（2 字段）：60 日均线的 20 日变化。"
                "经济机制：这是本批频率最低的一条，捕捉的是『季度级的基本面叙事迁移』。"
                "60 日均线把日常新闻噪声彻底抹掉，只留下公司叙事的方向；"
                "再取 20 日差分（约一个月），得到『这个季度的新闻叙事比上个月好多少』。"
                "对应的经济学是分析师与机构的分批调仓：当一家公司的新闻基调在季度尺度上系统性改善时，"
                "覆盖它的买方会逐季提高目标仓位，这个过程的持续性远强于单条新闻的冲击。"
                "选择它作为低频卡槽还有一个纯工程上的理由：60+20 的窗口使日换手天然落在个位数百分比，"
                "而 Fitness 公式在 TO<12.5% 时以 0.125 为地板、Margin 又正比于 Ret/TO，"
                "因此低频信号只需 5~6% 的年化收益即可同时越过 Fitness 1.0 与 Margin 10bps 两道门，"
                "这是本批中唯一在算术上『低成本达标』的路径。"
                "如果它 Sharpe 合格，说明新闻数据在慢频上仍有未被套利的定价错误；"
                "若不合格，则证明新闻语调的 alpha 半衰期极短，必须回到事件窗口，"
                "后面的批次就应当全部转向 vec_max / 单日极端值而不是继续拉长窗口。"
            ),
        },
        {
            "id": 7,
            "type": "RELEVANCE_WEIGHTED_PEAK_TONE",
            "expression": z(f"multiply(vec_avg({MAXS}), divide(vec_avg({REL}), 100))"),
            "optimize_reason": (
                "精度加权的最强语调（2 字段：maximum_sentiment_score + relevance）。"
                "与第 1 槽用 mean 不同，max 是『当天覆盖该股的所有文章中最正面的那一篇』，"
                "即全天最乐观的表述强度。经济机制上，新闻定价存在明显的非对称性："
                "负面信息往往一次性打入价格（坏消息跑得快），"
                "而正面信息需要被反复确认才逐步计入（好消息慢慢涨），"
                "所以『最正面表述』在截面上比平均语调更能预测后续的确认性买盘。"
                "同时它天然过滤掉平淡无味的日常报道，只保留有实质利好的样本。"
                "该槽是口径对照（mean vs max）而非参数微调：两者考察的是情感分布在均值与尾部"
                "哪一个位置携带 alpha，这对后续是否该用 vec_max 做事件研究是决定性的判据。"
                "风险上，max 口径的横截面离散度更大、极端值更多，"
                "因此必须有 relevance 权重把『只是被提及却出现极端表述』的伪样本压下去，"
                "否则会直接触发 CONCENTRATED_WEIGHT。"
                "最外层 zscore + truncation 0.08 是双保险，把单票权重锁死在可提交区间内。"
            ),
        },
        {
            "id": 8,
            "type": "RAW_LEXICON_NET_TONE_SURPRISE",
            "expression": z(
                "ts_delta("
                f"divide(subtract(vec_sum({POS}), vec_sum({NEG})), "
                f"add(add(vec_sum({POS}), vec_sum({NEG})), 1)), 10)"
            ),
            "optimize_reason": (
                "原始词典净语调的新息（2 字段：count_positive_phrases + count_negative_phrases），"
                "整批唯一的『非模型打分』对照槽。"
                "经济机制：(正词数 − 负词数)/(正词数 + 负词数 + 1) 是 Loughran-McDonald 词典法最经典的语调度量，"
                "它不做任何语义理解，只看词频；取 10 日新息是为了与第 2 槽的模型语调新息直接对标。"
                "这一槽的研究价值不在它自身，而在它提供的**归因基准**："
                "如果模型打分（mean_sentiment）与词典净语调给出相近的 Sharpe，"
                "说明该数据集的 alpha 来自『措辞方向』这一最朴素的层，"
                "后续所有再加工（分歧归一、深度加权）都只是给同一个东西化妆；"
                "如果模型版显著更强，则证明语义模型确实提取了词典之外的信息"
                "（反讽、否定、条件句），预算应当押在模型字段上而不必再回头做词典工程。"
                "此外它是本批唯一完全等权、不加任何精度权重的基准，"
                "因此它也是衡量『加权到底值不值』的标尺。"
                "分母 +1 保证零新闻日不产生 0/0，量纲天生有界于 (−1,1)。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_n1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']}, uni={BATCH['universe']})")
    assert len(BATCH["items"]) == 8
