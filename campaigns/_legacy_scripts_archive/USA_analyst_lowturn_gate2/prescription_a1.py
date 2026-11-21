"""
prescription_a1.py — Gate 2 · Batch A1：把已验证骨架上「换手」这一根轴单独解出来
（母本 vROQVzlA：Sh 1.86 / Fit 1.09 / TO 20.55% / Mgn 6.82bps / Ret 7.00% / DD 4.00%，零 fail 零 warn）

【为什么必须动平滑，而不是换字段】
  Margin(bps) = Ret × 10000 / (504 × TO)   → vROQVzlA 的 6.82bps 完全由 TO 决定
  Fitness     = Sh × sqrt(Ret / max(TO, 0.125))
  要让 Margin ≥ 15bps 且 Ret 大致守住 7%，必须 TO ≤ 9.3%（现在 20.55%）；
  同时 TO ≤ 12.5% 区间内 Fitness 的地板项才不吃亏。所以本轮唯一变量 = 平滑视界。
  三条硬证据把其它方向全部封死，不必再烧配额：
    · news 文本情感（us_equity_news / ai_news_scores / other635 headline）：峰值 Sh 0.37~0.62，三源一致，废弃。
    · news12 事件反应：Batch n4 实测视界 3→5→10→20 日 Sh 0.75→0.54→0.00→-0.01，
      且 Ret/TO 恒定在 0.095~0.118（每笔 2bps），延长视界对 Margin 完全无效，物理封死。
    · 分析师族 EPS 修正（g3 四槽）与共识紧密度加权（反向 -0.46）均已证伪。

【本批的三条设计铁律】
  (1) settings 完全冻结在母本（decay 18 / STATISTICAL / trunc 0.08 / TOP1000 / d1），
      平滑只通过表达式内部的 ts_decay_linear 视界实现 —— 这样 8 个槽共享同一套组合约束，
      TO 的差异 100% 来自表达式，可归因、可写进知识库。
  (2) 视界取 15 / 25 / 40 三档（母本是 3）。若 TO 与 Ret 同比例下滑，则 Margin 不动 —— 立刻停止；
      若 Ret 衰减慢于 TO（粘性预期假说成立），则 Margin 单调上升 —— 直接在本批内拿到解。
  (3) 其余 5 槽用「同一平滑视界 25 + 换统计口径」检验：低换手区的边缘究竟属于最乐观分析师
      （max，母本口径）还是共识中枢（median/mean）或保守端（min），避免把结果归因到单一字段。

经济学：分析师目标价是**粘性报价**（stickiness），股价的日常波动远快于目标价更新，
因此 max_PT/close 的偏离在 6 日尺度上是「最看好者的估值上限相对股价的短期折价」。
该折价由股价一次性下挫造成，市场对目标价信息的反应不足使其随后数周修复。
平滑视界的延长等价于只交易「折价持续存在」的那部分 —— 而持续存在的折价正是慢钱
（保险、养老金）尚未进场的证据，其修复期更长、每笔收益更大，故能抬高 Margin。
风险是过度平滑会把信号磨成风格暴露（这也是本批要测的）。
"""

MXP = "max_bias_adjusted_price_target"
MDP = "median_bias_adjusted_price_target"
MNP = "mean_bias_adjusted_price_target"
MIP = "min_bias_adjusted_price_target"
SDP = "stddev_bias_adjusted_price_target"
CNT = "count_bias_adjusted_price_target_estimates"
CLS = "close"


def gap(pt, w=6):
    """最看好/共识目标价隐含收益率相对其自身 w 日常态的偏离"""
    return f"subtract(divide({pt}, {CLS}), ts_mean(divide({pt}, {CLS}), {w}))"


def sig(core, decay):
    return f"group_rank(ts_decay_linear({core}, {decay}), sector)"


BATCH = {
    "seed_id": "vROQVzlA_lowturn",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 18,
    "neutralization": "STATISTICAL",
    "truncation": 0.08,
    "nan_handling": "ON",
    "category": "pv",
    "known_fields": [MXP, MDP, MNP, MIP, SDP, CNT, CLS],
    "items": [
        {
            "id": 1,
            "type": "MAXGAP_DECAY15",
            "expression": sig(gap(MXP), 15),
            "optimize_reason": (
                "母本口径 + 平滑视界 3→15（2 字段：最乐观目标价 + 收盘价）。"
                "这一槽是**最低风险**的一档：ts_decay_linear 的线性权重把最近 15 日的偏离摊成一条平滑曲线，"
                "组合仓位不再逐日按 6 日偏离重排，而是按『半月至月度折价中枢』排序。"
                "经济上，粘性目标价造成的估值折价只有持续存在时才会被慢钱定价："
                "单日折价多为噪声与流动性冲击（正是 Margin 只有 6.8bps 的原因），"
                "而持续 15 日的折价意味着机构尚未完成建仓，属于真正的预期差。"
                "若本槽 TO 落到 12-14% 且 Ret 守住 6% 以上，Margin 就有 8.5-10bps；"
                "它是判定『平滑是否等比例杀死收益』的第一档读数，也是整条前沿的保守端点。"
            ),
        },
        {
            "id": 2,
            "type": "MAXGAP_DECAY25",
            "expression": sig(gap(MXP), 25),
            "optimize_reason": (
                "母本口径 + 平滑视界 25（2 字段，同槽 1）。"
                "25 日恰好覆盖分析师的月度修订周期：目标价的更新在月度尺度上几乎必然发生一次，"
                "因此 25 日平滑后的偏离近似于『过去一个月里最乐观分析师始终给出的估值上限』，"
                "它剔除了单次修订造成的跳跃，只保留水平差。"
                "按 Margin 恒等式，若 Ret 从 7.00% 只衰减到 5.5%、而 TO 从 20.5% 降到 9%，"
                "Margin 就是 5.5%×10000/(504×0.09) = 12.1bps，Fitness = Sh×sqrt(5.5/12.5) ，"
                "配合 Sh 抬升到 1.9 即可到 1.26 —— 三项同时逼近或越过门槛。"
                "这是本批的**主攻槽**：它最有可能一次同时清掉 LOW_TURNOVER 之外的三个警告。"
                "同时因为它把持仓周期从 5 天拉到 25 天，与已提交同源 alpha 的日频 PnL 相关性会同步下降，"
                "对后续 PROD_CORRELATION 也有直接好处。"
            ),
        },
        {
            "id": 3,
            "type": "MAXGAP_DECAY40",
            "expression": sig(gap(MXP), 40),
            "optimize_reason": (
                "母本口径 + 平滑视界 40（2 字段，同槽 1/2）。"
                "40 日（约两个月）是本批的**上界探针**：它检验『慢钱进场』这一机制是否真的存在于两个月尺度，"
                "还是只存在于月度尺度。若本槽 Ret 与槽 2 相当而 TO 继续下降，则 Margin 会直接冲上 20bps 以上，"
                "且持仓周期长达两个月，PnL 与任何日频/周频新闻、价量因子都天然脱钩，"
                "是本批最有价值的**去相关产出**；反之若 Ret 崩到 3% 以下，说明折价修复集中在 4 周内，"
                "最优解锁定在槽 2 附近，后续批次不必再在平滑轴上浪费配额。"
                "这一槽的另一个作用是诊断风格暴露：过度平滑会让信号逼近『目标价溢价率』的静态水平，"
                "而静态溢价率是一个价值型风格暴露，会同时拉高 DD 与 Investability 风险 —— "
                "本槽的 DD 与 investability_sharpe 读数将直接告诉我们平滑的安全边界在哪里。"
            ),
        },
        {
            "id": 4,
            "type": "MEDGAP_DECAY25",
            "expression": sig(gap(MDP), 25),
            "optimize_reason": (
                "共识中枢口径 + 平滑 25（2 字段：中位目标价 + 收盘价）。"
                "中位数是母本族最早使用的统计量（g1 槽 1），它对单一分析师的极端乐观值不敏感，"
                "因此在低换手区（平滑 25 日）更可能保留『共识缓慢上移』这一慢变量，"
                "而 max 口径在长平滑后可能被少数分析师的陈旧目标价拖住。"
                "经济上二者分工明确：max 捕捉『最看好者的独立判断』（领先信号、信息含量高但噪声大），"
                "median 捕捉『共识中枢』（滞后信号、噪声低、更接近慢钱定价的锚）。"
                "低换手组合需要的是后者：慢钱的仓位调整依据是共识而非极值。"
                "本槽与槽 2 构成同一平滑视界下的口径消融（唯一变量 = 统计量），"
                "可直接判定在 Margin ≥15bps 的目标下应押 max 还是 median。"
            ),
        },
        {
            "id": 5,
            "type": "MEANGAP_DECAY25",
            "expression": sig(gap(MNP), 25),
            "optimize_reason": (
                "算术均值口径 + 平滑 25（2 字段：均值目标价 + 收盘价）。"
                "均值与中位数的差（mean − median）是分析师分布的偏度：均值显著高于中位数说明存在少数"
                "极端乐观者把均值拉高。在平滑 25 日之后，偏度变成『过去一个月里乐观者是否在持续加码』的度量。"
                "本槽与槽 4 的对照因此不是重复，而是**偏度检验**：若 mean 版显著强于 median 版，"
                "说明可交易边缘来自乐观者的持续加码（叙事扩散）；若显著弱，说明边缘来自共识的稳健上移。"
                "统计上均值对单个极端值更敏感，因此在 truncation 0.08 的保护下它的尾部风险可控，"
                "但也更容易在低流动性小盘上产生虚假信号 —— TOP1000 的宇宙约束已部分对冲这一点。"
                "这条的诊断价值在于：它决定后续做「分析师分布形状」这一维度时该用哪个中心统计量。"
            ),
        },
        {
            "id": 6,
            "type": "MINGAP_DECAY25",
            "expression": sig(gap(MIP), 25),
            "optimize_reason": (
                "保守端口径 + 平滑 25（2 字段：最低目标价 + 收盘价）。"
                "min 是覆盖该股**最悲观**分析师给出的目标价，它衡量的是『看空者愿意承认的下限』。"
                "经济含义与 max 完全不同：最悲观目标价的抬升意味着空头阵营在投降（capitulation），"
                "这是文献中比多头乐观更可靠的拐点信号 —— 因为看空者改变观点的成本更高、需要更强的证据，"
                "其修订的信息含量天然更大（asymmetric revision informativeness）。"
                "此外 min 口径的截面分布更贴近股价（看空者目标价通常低于现价），"
                "因此 min/close 的分布左偏更少、rank 更均匀，组合的两侧会更均衡，"
                "这对 CONCENTRATED_WEIGHT 与 sub_universe_sharpe 都是结构性利好。"
                "在低换手区（25 日平滑）它可能反而优于 max —— 因为投降是一次性事件、修复期长，"
                "恰好匹配长持仓周期，是 Margin 提升的潜在来源。"
            ),
        },
        {
            "id": 7,
            "type": "MAXGAP_DISPERSION_NORM_DECAY25",
            "expression": sig(
                f"divide({gap(MXP)}, add(divide({SDP}, {CLS}), 0.01))", 25
            ),
            "optimize_reason": (
                "max 偏移 / 分析师分歧度 + 平滑 25（3 字段：最乐观目标价 + 收盘价 + 目标价标准差）。"
                "这是本批唯一把『分歧』放进分母的槽。经济逻辑：同样 20% 的最乐观溢价，"
                "若全体分析师目标价只在 ±5% 内高度一致（低分歧），说明 20% 是所有认真研究的共同结论，"
                "可信度极高；若目标价从 0.5 倍到 3 倍乱飞（高分歧），20% 只是极端乐观者的孤立观点，"
                "几乎没有定价力。除以分歧度就是把『乐观溢价』换算成『多少个分析师意见标准差』，"
                "即 t 统计量式的显著性，与第 2 槽的原始幅度形成互补：一个测幅度、一个测可信度。"
                "它同时天然抑制了高分歧股（通常是高波动、高投机的小盘）的权重，"
                "这应当同时改善 DD、Investability 与 sub_universe Sharpe 三项。"
                "注意：g3 曾验证过 multiply(·, reverse(rank(stddev))) 的反向加权版为 -0.46，"
                "那是因为反向加权把高分歧股的信号放大；本槽是除以分歧，加压方向相反，不可混为一谈。"
            ),
        },
        {
            "id": 8,
            "type": "MAXGAP_COVERAGE_WEIGHT_DECAY25",
            "expression": sig(f"multiply({gap(MXP)}, rank({CNT}))", 25),
            "optimize_reason": (
                "max 偏移 × 覆盖广度 + 平滑 25（3 字段：最乐观目标价 + 收盘价 + 覆盖分析师数）。"
                "覆盖分析师数量是『信息生产强度』的直接度量：被 20 位分析师跟踪的股票，"
                "其最乐观目标价背后是 20 份独立研究的最大值，天然存在极值偏差（max of many）；"
                "而被 3 位分析师跟踪的股票，max 几乎等于唯一样本，噪声极大。"
                "因此本槽用 rank(覆盖数) 给信号加权，等价于『按研究投入的密度给预测打折』，"
                "只保留信息生产充分的标的。经济上这对应 Merton 的投资者认知假说："
                "高覆盖 = 高可见度 = 错价被更快修正，因此高覆盖股上的折价修复更确定（但幅度更小），"
                "而低覆盖股的折价可能永远不修复（价值陷阱）。在长持仓周期（25 日）下，"
                "『修复的确定性』比『修复的幅度』更重要，所以这条在低换手区应当明显优于纯幅度版。"
                "它与槽 7 一起构成本批的两条『可信度加权』路线（一个按分歧、一个按覆盖），"
                "用于判定低换手区到底该押幅度还是押确定性。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_a1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']}, trunc={BATCH['truncation']})")
    assert len(BATCH["items"]) == 8
