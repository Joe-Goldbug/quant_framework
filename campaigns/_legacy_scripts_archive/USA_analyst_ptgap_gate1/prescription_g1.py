"""
prescription_g1.py — Gate 1 · Batch 1：分析师目标价隐含预期差（Analyst Target-Price Expectation Gap）
母本: bl8Wd2Nq (ACTIVE, checks.fail=[] & warning=[] , Sh 2.05 / Fit 1.12 / TO 22.9% / 2Y 2.39)
经济学假设:
  分析师共识目标价 PT 锚定公司基本面价值; 隐含上涨空间 IRR = PT/close 是一个"预期收益率"。
  股价短期被砸 → IRR 相对自身常态骤升, 而分析师目标价调整滞后于价格 (粘性),
  市场对目标价信息反应不足 → 该折价在随后 1-3 周被修复。
  截面 rank 剥掉行业整体估值漂移, STATISTICAL 中性化剥掉风格暴露, 剩下个股层面的折价修复。
字段数: 每条 2~3 个 (PT 族 + close 作为每股标度 + 可选分歧度/覆盖度/基本面估值)
"""
F = "median_bias_adjusted_price_target"
FM = "mean_bias_adjusted_price_target"
FX = "max_bias_adjusted_price_target"
FV = "median_bias_adjusted_fundamental_estimate"
SD = "stddev_bias_adjusted_price_target"
CNT = "count_bias_adjusted_price_target_estimates"
UP = "num_upward_biasfree_price_target_revisions"
DN = "num_downward_biasfree_price_target_revisions"


def irr(f):
    return f"divide({f}, close)"


BATCH = {
    "seed_id": "bl8Wd2Nq",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 18,
    "neutralization": "STATISTICAL",
    "truncation": 0.08,
    "nan_handling": "ON",
    # close 仅作"每股标度"分母(把目标价换算成无量纲的隐含收益率), 属因果白名单特批的交叉用法
    "category": "pv",
    "known_fields": [F, FM, FX, FV, SD, CNT, UP, DN, "close"],
    "items": [
        {
            "id": 1,
            "type": "PGAP_MEDIAN_IND_DEV5",
            "expression": f"group_rank(subtract({irr(F)}, ts_mean({irr(F)}, 5)), industry)",
            "optimize_reason": (
                "母本锚点（机制标定槽）：分析师共识目标价中位数换算成隐含收益率 PT/close 后，"
                "减去其自身 5 日常态，得到『股价相对分析师基准价值的短期折价』。"
                "经济学上，目标价由分析师对公司基本面的估值决定，调整远慢于价格；股价一次性下挫会把 IRR 顶上去，"
                "而分析师不会当天改目标价，于是这个缺口就是可交易的反应不足。行业组内 rank 消除行业估值中枢漂移，"
                "STATISTICAL 中性化剥离规模/价值/动量等风格暴露，decay 18 把 5 日窗口的抖动用指数平均抹平，"
                "从而把换手压到 20% 出头、把每笔交易的信息含量抬起来。本槽不追求新颖，它的作用是"
                "在本次 Settings（decay 18 / STATISTICAL / trunc 0.08）下标定整条家族的天花板与检查项状态，"
                "为其余 7 条的相对优劣提供唯一基准。"
            ),
        },
        {
            "id": 2,
            "type": "PGAP_MEAN_IND_DEV4",
            "expression": f"group_rank(subtract({irr(FM)}, ts_mean({irr(FM)}, 4)), industry)",
            "optimize_reason": (
                "均值口径的短窗口变体：中位数会牺牲一部分信息（当分析师意见右偏时中位数钝化），"
                "均值则完整保留共识的强度信息；代价是对极端离群目标价敏感。"
                "把参照窗从 5 日缩到 4 日，是为了补偿均值平滑带来的信号迟滞——经济上仍是同一个『折价修复』逻辑，"
                "但响应更快半拍，理论上能多吃一点事件初期的修复段。"
                "与第 1 槽构成『均值 vs 中位数 × 4日 vs 5日』的 2×2 对照，用来判断目标价分布的偏度是否在提供 alpha："
                "若均值明显更差，说明分析师目标价右偏、必须用中位数；若均值不差，说明取中位数是信息浪费。"
            ),
        },
        {
            "id": 3,
            "type": "PGAP_DISPERSION_NORMALIZED",
            "expression": (
                f"group_rank(divide(subtract({irr(F)}, ts_mean({irr(F)}, 5)), "
                f"add(divide({SD}, close), 0.01)), industry)"
            ),
            "optimize_reason": (
                "以分析师分歧度归一（三字段：中位数目标价 + 分歧度 + 股价）：同样的 IRR 折价，"
                "若分析师目标价的横截面标准差很小（高度共识），这笔折价更可信、修复概率更高；"
                "若分歧巨大（有人看多有人看空），折价只是观点噪声。除以 stddev/close 等于把缺口换算成"
                "『多少个分析师分歧单位』，是一个截面上的 t 统计量，直接提高信号的信噪比与尾部稳健性。"
                "这条同时是家族去相关的主力：它把权重从『缺口最大的股票』移向『共识最强且折价明显的股票』，"
                "与纯缺口排序的相关性天然更低，且经济叙事更完整（不确定性折价是资产定价的第一性原理）。"
            ),
        },
        {
            "id": 4,
            "type": "PGAP_COVERAGE_WEIGHTED",
            "expression": (
                f"group_rank(multiply(subtract({irr(F)}, ts_mean({irr(F)}, 5)), "
                f"rank({CNT})), industry)"
            ),
            "optimize_reason": (
                "以覆盖广度加权（三字段：中位数目标价 + 覆盖分析师人数 + 股价）：一条 IRR 缺口的信息价值取决于"
                "有多少分析师在持续跟踪——只有 1 位分析师给出的目标价，缺口再大也可能只是报价噪声或数据滞后；"
                "20 位分析师共同给出的中位数才有真实的共识含义。rank(覆盖人数) 作为 [0,1] 权重乘上缺口，"
                "等于按『共识的厚度』给仓位加权，这是信息经济学里经典的精度加权（precision weighting）。"
                "经济上它把仓位推向真正有机构关注度的标的，直接改善可投资性与 Margin，"
                "并在截面上与纯缺口排序错位，构成第二条去相关路径。"
            ),
        },
        {
            "id": 5,
            "type": "PT_OVER_FUNDAMENTAL_SPREAD",
            "expression": (
                f"group_rank(subtract({irr(F)}, divide({FV}, close)), industry)"
            ),
            "optimize_reason": (
                "目标价与基本面估值之差（三字段：中位数目标价 + 中位数基本面估值 + 股价）："
                "分析师给出的两个东西——价格目标（考虑情绪与催化剂的 12 个月目标）与基本面估值（DCF/倍数内在价值）——"
                "之间的差，刻画的是『分析师认为这只票值多少 vs 分析师认为市场会给多少』的乐观溢价。"
                "两者都以同一股价归一，close 在差分中被消掉一阶量纲，"
                "因此这条信号本质上完全不受价格水平影响，只反映分析师内部的分歧结构。"
                "经济假设：当乐观溢价异常高时，说明分析师目标价已被市场情绪绑架、后续下修风险大（反向）；"
                "反之溢价被压缩则存在正向修复。它是家族中唯一不依赖『股价历史窗口』的成员，"
                "因此与其余各槽的时序相关性最低，是结构上最强去相关的一个卡槽。"
            ),
        },
        {
            "id": 6,
            "type": "REVISION_DIFFUSION",
            "expression": (
                f"group_rank(divide(subtract({UP}, {DN}), add(add({UP}, {DN}), 1)), industry)"
            ),
            "optimize_reason": (
                "目标价修正扩散度（纯分析师两字段，完全不使用任何量价字段）："
                "(上调家数 − 下调家数)/(上调 + 下调 + 1) 是分析师修正的净扩散指数，"
                "值域 (-1,1)、天然有界、以 0 为中性锚。经济机制与 IRR 折价互补："
                "折价捕捉『水平偏离』，扩散捕捉『共识的迁移方向』——当分析师成批上调目标价时，"
                "机构资金会分批跟进（分析师修正漂移，revision drift），这个过程持续数周且不依赖价格。"
                "由于它既不使用 close 也不使用任何历史价格窗口，与母本的相关性在结构上最低，"
                "是本批唯一一条零量价污染（pure analyst）的样本，也是最有希望在 PROD_CORRELATION 上"
                "打开空间的一条。"
            ),
        },
        {
            "id": 7,
            "type": "PGAP_IR_SUBINDUSTRY",
            "expression": (
                f"group_rank(divide(subtract({irr(F)}, ts_mean({irr(F)}, 20)), "
                f"add(ts_std_dev({irr(F)}, 60), 0.01)), subindustry)"
            ),
            "optimize_reason": (
                "时序 t 统计量 + 细颗粒度中性化：把 20 日缺口除以该 IRR 序列 60 日的标准差，"
                "得到『这轮折价相对其自身历史波动有多极端』——这是一个自标准化的 z 值，"
                "天然给高波动标的降权、给稳定标的加权，等价于把信号从『幅度』升级为『显著性』。"
                "同时把分组从 industry 下沉到 subindustry：目标价溢价在细分行业内部才可比"
                "（半导体与公用事业的合理 IRR 中枢差一倍以上），industry 层会残留行业中枢噪声。"
                "这条同时检验两个独立假设（时序显著性 vs 截面幅度、subindustry vs industry），"
                "是家族里第一次把中性化颗粒度调到最细的尝试，也是去相关的第三条路径。"
            ),
        },
        {
            "id": 8,
            "type": "PGAP_MAX_SECTOR_DEV6",
            "expression": f"group_rank(subtract({irr(FX)}, ts_mean({irr(FX)}, 6)), sector)",
            "optimize_reason": (
                "最乐观分析师口径 + 粗颗粒度分组：max_bias_adjusted_price_target 是覆盖该股的最乐观目标价，"
                "它衡量的是『最看好的人愿意给多少』，对正面催化剂最敏感，通常领先中位数 1-2 周；"
                "用 sector 而不是 industry 分组，让信号保留更宽的行业相对强弱信息（在粗分组下 rank 的离散度更大），"
                "这是刻意与第 1 槽错开的一层。经济上，最乐观目标价的抬升往往先于共识上移，"
                "因此这条信号更像『早期线索』而非『共识确认』，与第 3/4 槽的保守化处理形成风格对立。"
                "它的存在也用于检验：家族 alpha 是否依赖于『取中位数』这一特定的稳健化选择。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_g1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots, decay={BATCH['decay']}, "
          f"neut={BATCH['neutralization']})")
    assert len(BATCH["items"]) == 8
