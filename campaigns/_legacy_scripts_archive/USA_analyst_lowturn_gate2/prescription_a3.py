"""
prescription_a3.py — Gate 2 · Batch A3：用「分桶离散化」把换手打下来，而不是用平滑

【A1/A2 的裁决（实测）】
  A1（同一骨架，只把 ts_decay_linear 3→15/25/40）：
      TO 20.55%→14.09%→12.02%→10.39%，Ret 7.00%→3.97%→3.13%→2.75%，
      Margin 6.82→5.64→5.20→5.28bps，Sh 1.86→1.20→0.96→0.85。
      → 指数平滑把「信息的时效」一起磨掉了：收益衰减快于换手，Margin 反而下降。此路封死。
  A2（M&A 目标概率族 8 槽）：最高 Sh 0.39，但 CHEAP_TARGETS 槽拿到 TO 4.55% / Margin 13.08bps。
      → 证明「低换手 ⇒ 高 Margin」的物理成立（13bps 已达标），缺的只是 Sharpe。
      同时槽 3（概率×估值，+0.39）与槽 8（概率÷估值，−0.25）符号相反，
      **方向性被确认**：便宜的目标才是好交易，不是拟合噪声。

【本批的技术核心：bucket 离散化 vs 指数平滑的本质差别】
  平滑（ts_decay_linear）做的是「时间平均」：它把今天的新信息与过去 20 天的旧信息混合，
  于是信号每天都变一点点，但每天都只变一点点 —— 结果是**收益被摊薄、换手只降一半**。
  离散化（bucket）做的是「量化」：它保留今天的信号、只是把连续的排序压成 N 个台阶。
  关键差别在于：**台阶之间不交易**。信号在同一个台阶内小幅波动时，仓位完全不动；
  只有跨过台阶边界才换仓。于是：
    · 横截面排序（alpha 的全部来源）完整保留；
    · 噪声级波动（占日频信号变动的大头）被完全过滤；
    · 换手按「跨台阶频率」而非「信号变动幅度」计价。
  这正是做市/执行领域的「no-trade band」逻辑：最优再平衡策略从不连续调仓，
  而是在偏离超过阈值时才交易（Constantinides 1986, Davis-Norman 1990）。
  平滑是把信号做旧，离散化是给信号装一个**迟滞带**（hysteresis）—— 两者在数学上完全不同。

【经济学：为什么这个家族值得装迟滞带】
  分析师目标价是粘性报价，股价是快变量。二者之比（隐含收益率）的日频波动中，
  绝大部分是**股价噪声**而非分析师观点变化。投资者对目标价信息的反应不足需要数周兑现，
  因此「噪声级波动」既不带信息、又制造交易成本 —— 恰恰应该被迟滞带吸收。
  换句话说：本族的 alpha 是低频的（数周量级的定价修正），而它的换手是高频的（日频股价噪声）。
  用一个高频的调仓频率去交易一个低频的信号，是这一族 Margin 只有 6.8bps 的唯一结构性原因。
  离散化正是把调仓频率与信号频率对齐的手术。

settings: USA / TOP1000 / delay 1 / decay 0 / STATISTICAL / truncation 0.08 / nanHandling ON
  decay 0：迟滞带已经提供了粘性，再叠加设置层衰减会把台阶抹平，等于抵消本批的设计意图。
"""

MXP = "max_bias_adjusted_price_target"
MDP = "median_bias_adjusted_price_target"
MNP = "mean_bias_adjusted_price_target"
SDP = "stddev_bias_adjusted_price_target"
CNT = "count_bias_adjusted_price_target_estimates"
CLS = "close"


def gap(pt, w=6):
    return f"subtract(divide({pt}, {CLS}), ts_mean(divide({pt}, {CLS}), {w}))"


def bk(core, step):
    return f'bucket(group_rank({core}, sector), range="0,1,{step}")'


BATCH = {
    "seed_id": "vROQVzlA_bucket",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 0,
    "neutralization": "STATISTICAL",
    "truncation": 0.08,
    "nan_handling": "ON",
    "category": "pv",
    "known_fields": [MXP, MDP, MNP, SDP, CNT, CLS],
    "items": [
        {
            "id": 1,
            "type": "BUCKET10_MAXGAP",
            "expression": bk(gap(MXP), 0.1),
            "optimize_reason": (
                "最乐观目标价偏离 → 行业组内排序 → 10 档离散化（2 字段：目标价 + 收盘价）。"
                "10 档是最细的台阶（每档约 100 只），几乎保留了全部截面排序信息，"
                "但已足以吸收日频股价噪声：只有排序跨过 10% 分位边界时才换仓。"
                "这是本批的**保守端点**——若即使 10 档也能把 TO 从 20.5% 压到 15% 以下而不伤 Ret，"
                "说明迟滞带机制成立，后续可以放心加粗；若 10 档完全无效，说明信号本身每日都在大幅重排，"
                "迟滞带无从下手，本批其余槽也会同步失效，可立刻停止。"
                "经济上 10 档仍接近连续排序，等价于「只交易排序变动超过 10% 分位的那部分」，"
                "对应的正是 Constantinides 意义上的最小再平衡阈值。"
            ),
        },
        {
            "id": 2,
            "type": "BUCKET5_MAXGAP",
            "expression": bk(gap(MXP), 0.2),
            "optimize_reason": (
                "同上 → 5 档（每档约 200 只，20% 分位）。"
                "5 档是本批的**主攻档**：经验上股票池按 5 分位分组后，组内个体的定价差异仍然显著，"
                "而组间切换的频率远低于个体排序变动频率，因此换手通常能降 2-3 倍。"
                "按 Margin 恒等式，TO 20.5%→8% 且 Ret 只衰减 20%（7.00%→5.6%）时，"
                "Margin = 5.6%×10000/(504×0.08) = 13.9bps，Fitness = Sh×sqrt(5.6/12.5) ，"
                "配合 Sh 保持在 1.7 以上即可到 1.13 —— 四项指标同时逼近门槛。"
                "它同时保留了母本的全部经济含义（最乐观分析师的估值上限相对股价的短期折价），"
                "唯一改动是「多小的排序变化不值得我们付交易成本」。"
            ),
        },
        {
            "id": 3,
            "type": "BUCKET3_MAXGAP",
            "expression": bk(gap(MXP), 0.34),
            "optimize_reason": (
                "同上 → 3 档（约 33% 分位，多/空各 1 档 + 中间观察档）。"
                "这是本批的**激进端点**，用于测量迟滞带的安全边界：粗到 3 档时，"
                "组合实际只做多的部分是最乐观的 1/3、做空的是最悲观的 1/3，中间 1/3 空仓 —— "
                "这在结构上等价于「只在高信念标的上下注」，是低换手策略的经典形态。"
                "风险是排序信息损失过多（母本的边缘可能集中在极值端，而 3 档把极值摊平）。"
                "若 3 档 Ret 崩到 3% 以下，说明边缘确实集中在极值排序上；"
                "若 3 档 Ret 守住而 TO 降到 5% 以内，则 Margin 直接冲破 20bps —— 那就是解。"
                "这一槽存在的意义是把「迟滞带宽度」这条曲线的两端都钉住，"
                "使最优点可以在本批之内被定位，而不必再开一批做参数扫描。"
            ),
        },
        {
            "id": 4,
            "type": "BUCKET5_MEDGAP",
            "expression": bk(gap(MDP), 0.2),
            "optimize_reason": (
                "共识中位数口径 → 5 档（2 字段）。"
                "与槽 2 的唯一差别是统计量：max（最看好者）换成 median（共识中枢）。"
                "在连续排序下 max 版更强（母本 Sh 1.86），但离散化会改变这个结论 —— "
                "因为 max 是极值统计量，其排序在日频上更不稳定（某个分析师一改目标价，"
                "max 就可能跳变），因此 max 口径在迟滞带下的换手更高、台阶跨越更频繁；"
                "而 median 是稳健统计量，日频变动小，跨台阶频率天然低。"
                "所以「离散化 + max」与「离散化 + median」的对比不只是口径消融，"
                "而是**迟滞带与统计量稳健性的交互**：最优点很可能是 median 配粗台阶。"
                "这条是本批最可能给出「低换手 + 保住 Sharpe」组合的槽之一。"
            ),
        },
        {
            "id": 5,
            "type": "BUCKET5_MEANGAP",
            "expression": bk(gap(MNP), 0.2),
            "optimize_reason": (
                "算术均值口径 → 5 档（2 字段）。"
                "均值对少数极端乐观者更敏感（mean 与 median 之差即分析师分布偏度），"
                "因此它的日频波动比 median 大、比 max 小，在迟滞带下处于中间位置。"
                "保留这一槽是为了把「统计量稳健性 → 跨台阶频率 → 换手」这条链条测完整："
                "若三个统计量（max / mean / median）的 TO 单调递减且 Ret 保持，"
                "就得到一个可直接写进知识库的定量结论——"
                "「迟滞带策略应选稳健统计量」，而这条结论对所有未来的离散化改造都适用。"
                "经济学上 mean 版更接近「共识 + 偏度」的混合代理，"
                "在乐观者持续加码的阶段（叙事扩散期）会领先 median 上移，属于早期线索。"
            ),
        },
        {
            "id": 6,
            "type": "BUCKET5_MAXGAP_COVERAGE",
            "expression": bk(f"multiply({gap(MXP)}, rank({CNT}))", 0.2),
            "optimize_reason": (
                "max 偏离 × 覆盖广度 → 5 档（3 字段：目标价 + 收盘价 + 覆盖分析师数）。"
                "覆盖数是「信息生产强度」的度量：被 20 位分析师跟踪的股票，其 max 目标是 20 份独立研究的最大值，"
                "天然含极值偏差；被 3 位跟踪的，max 几乎等于唯一样本、噪声极大。"
                "用 rank(覆盖数) 加权等于按研究密度给信号打折，只保留信息生产充分的标的。"
                "这在迟滞带框架下有额外的好处：低覆盖股的 max 目标价噪声大、日频跳变大，"
                "正是造成频繁跨台阶、推高换手的元凶 —— 加权把它们挤出高信念档，"
                "等于同时降低换手与提高信号的信噪比，是本批少见的「一举两得」构造。"
                "经济上对应 Merton 的投资者认知假说：高覆盖 ⇒ 错价修正更快更确定，"
                "而确定的修正正是长持有期策略最需要的品质。"
            ),
        },
        {
            "id": 7,
            "type": "BUCKET5_MAXGAP_DISPERSION_NORM",
            "expression": bk(f"divide({gap(MXP)}, add(divide({SDP}, {CLS}), 0.01))", 0.2),
            "optimize_reason": (
                "max 偏离 / 分析师分歧度 → 5 档（3 字段：目标价 + 收盘价 + 目标价标准差）。"
                "除以分歧度把「乐观溢价」换算成「多少个分析师意见标准差」，即 t 统计量式的可信度。"
                "同样的 20% 溢价，在 ±5% 的低分歧股票上是共识结论，在 0.5~3 倍乱飞的高分歧股票上只是孤例。"
                "与迟滞带的交互特别关键：高分歧股的 t 值日频波动极大（分母在动），"
                "若不归一，这类股票会在台阶边界来回穿越、制造无效换手；归一之后排序稳定得多。"
                "同时它天然压制高分歧（通常高波动、高投机）小盘的权重，应同时改善 DD、"
                "sub_universe Sharpe 与 investability。注意与 g3 已证伪的『反向加权』"
                "（multiply 分歧，-0.46）方向相反，不可混淆。"
            ),
        },
        {
            "id": 8,
            "type": "BUCKET5_MAXGAP_SLOWBASELINE",
            "expression": bk(gap(MXP, 12), 0.2),
            "optimize_reason": (
                "max 偏离（基准窗 6→12 日）→ 5 档（2 字段）。"
                "前七槽固定 6 日基准窗、只动台阶；本槽反过来：固定台阶 5 档、只动基准窗。"
                "二者构成一张 2×2 的交叉设计，可直接分离「迟滞带」与「基准窗」两个旋钮的贡献。"
                "经济上 12 日基准把「短期折价」的定义从一周拉长到双周："
                "它过滤掉更短周期的股价噪声，使分子本身更慢，从而与迟滞带叠加后换手可能进一步降到 5% 以下。"
                "风险是基准窗太慢会触发平台的 REVERSION_COMPONENT 警告（分析师族历史上 20/60/120 日窗口均触发，"
                "5/6 日窗口不触发，12 日处于未测区间）—— 本槽的警告项读数会直接给出该边界，"
                "这对「零警告」这一硬要求是必须付的探测成本。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_a3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']})")
    assert len(BATCH["items"]) == 8
