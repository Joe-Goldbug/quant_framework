"""
prescription_g3.py — Gate 1 · Batch 3：双线并进
Batch 1/2 结论:
  - PASS_ALL: vROQVzlA (max PT dev6 + sector) Sh 1.86 / Fit 1.09 / 0 fail / 0 warn；但 PROD corr 0.8554 -> 提交口径不过
  - CLUSTER_TEST 警告 = 均值/分歧/覆盖加权的共同代价；sector 分组 + max PT 是唯一零警告骨架
  - 20/60/120 日慢窗全部触发 REVERSION_COMPONENT 警告 -> 慢窗路线封死
  - 纯分析师零价格信号 (分歧趋势/乐观溢价) Sharpe 0.14~0.96 -> 单靠分析师字段不足以立身
本批: A线(1-4) 在零警告骨架上做正交加权去相关; B线(5-8) 换盈利预测修正机制(EPS revision, 独立数据库经济学)
"""
FX = "max_bias_adjusted_price_target"
MN = "min_bias_adjusted_price_target"
SD = "stddev_bias_adjusted_price_target"
CNT = "count_bias_adjusted_price_target_estimates"
FV = "median_bias_adjusted_fundamental_estimate"
SDF = "stddev_bias_adjusted_fundamental_estimate"
UPF = "num_upward_biasfree_fundamental_revisions"
DNF = "num_downward_biasfree_fundamental_revisions"


def irr_max():
    return f"divide({FX}, close)"


BATCH = {
    "seed_id": "bl8Wd2Nq",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "decay": 18,
    "neutralization": "STATISTICAL",
    "truncation": 0.08,
    "nan_handling": "ON",
    "category": "pv",
    "known_fields": [FX, MN, SD, CNT, FV, SDF, UPF, DNF, "close"],
    "items": [
        {
            "id": 1,
            "type": "MAXPT_SECTOR_X_CONSENSUS",
            "expression": (
                f"group_rank(multiply(subtract({irr_max()}, ts_mean({irr_max()}, 6)), "
                f"reverse(rank({SD}))), sector)"
            ),
            "optimize_reason": (
                "在唯一零警告骨架（max PT + 6 日偏离 + sector + decay18）上，把仓位权重换成『分析师共识紧密度』："
                "reverse(rank(stddev_PT)) 给目标价分歧最小的股票最高权重。经济含义是精度加权——"
                "最乐观目标价（max）本身噪声大，但当全体分析师的目标价高度集中时，"
                "这个最乐观值也是可靠的；当分歧极大时，max 很可能只是某个离群分析师的孤例，应当降权。"
                "相比 Batch 1 的直接缺口排序（与母本 0.855 相关，本质是价格反转），"
                "本条改变了截面的权重分布：不再只买『跌得最多』，而是买『分析师一致看好目标价 + 股价刚回撤』，"
                "权重的第二大变异源来自分歧度而非价格，预期能把 PROD 相关压下来，同时保留零警告。"
            ),
        },
        {
            "id": 2,
            "type": "MAXPT_SECTOR_X_COVERAGE",
            "expression": (
                f"group_rank(multiply(subtract({irr_max()}, ts_mean({irr_max()}, 6)), rank({CNT})), sector)"
            ),
            "optimize_reason": (
                "同骨架，权重换成覆盖广度 rank(覆盖分析师人数)。经济逻辑：一条目标价缺口的信息价值"
                "与跟踪人数正相关——20 位分析师共同覆盖的中位数目标价有真实共识含义，"
                "1 位分析师的孤立目标价更可能是数据滞后。Batch 1 第 4 槽在 industry + median 下用同一权重"
                "拿到了 Sh 2.01/Fit 1.06，但只剩 CLUSTER_TEST 警告；本条改为 sector + max 骨架，"
                "检验『零警告骨架 + 覆盖加权』能否同时成立。若成立，由于覆盖人数是一个独立于价格的信息轴，"
                "其在截面上重新分配权重的作用会显著降低与纯反转因子的相关。"
            ),
        },
        {
            "id": 3,
            "type": "MAXPT_SECTOR_DISPERSION_NORM",
            "expression": (
                f"group_rank(divide(subtract({irr_max()}, ts_mean({irr_max()}, 6)), "
                f"add(divide({SD}, close), 0.01)), sector)"
            ),
            "optimize_reason": (
                "同骨架，把缺口换算成『分析师分歧单位』：缺口 / (stddev_PT/close)。"
                "这是截面 t 统计量形式，同时完成两件事——(1) 精度加权，(2) 把信号从『幅度排序』"
                "改成『显著性排序』，使高波动、高分歧的名字不再被极端的 max 目标价绑架。"
                "Batch 1 第 3 槽用同一构造在 industry 分组下是 Sh 1.98 / Fit 1.04，仅剩 CLUSTER_TEST 警告；"
                "本条保留 sector 骨架（零警告的唯一载体）以验证分组是否才是 CLUSTER_TEST 的真正决定因素。"
                "经济上，分歧度归一后的缺口才是『市场错价 / 认知不确定性』的比值，叙事更严谨。"
            ),
        },
        {
            "id": 4,
            "type": "MINPT_SECTOR_DEV6",
            "expression": (
                f"group_rank(subtract(divide({MN}, close), ts_mean(divide({MN}, close), 6)), sector)"
            ),
            "optimize_reason": (
                "把统计量从 max 换成 min：最悲观分析师的目标价。这是一次符号层面的反向实验——"
                "若 max 口径的高分来自『最乐观者的乐观』，那么 min 口径应当给出反向或无效的收益；"
                "若 min 口径同样有效（甚至更强），说明真正驱动 alpha 的是『整个目标价分布相对股价的位移』，"
                "而不是乐观尾部，这会大幅简化机制解释。经济上，min 目标价代表『最悲观者的估值下限』，"
                "当这个下限相对股价快速抬升时，意味着连最保守的分析师都认为股价过低，是极强的安全边际信号，"
                "属于下行风险保护的 alpha，通常与价格反转的相关性更低（因为它锚定的是保守估值而非情绪）。"
            ),
        },
        {
            "id": 5,
            "type": "FV_REVISION_DIFFUSION",
            "expression": (
                f"group_rank(divide(subtract({UPF}, {DNF}), add(add({UPF}, {DNF}), 1)), industry)"
            ),
            "optimize_reason": (
                "换机制：盈利预测（基本面估计）修正扩散度。分析师体系里最稳健的异象不是目标价，而是"
                "EPS/盈利预测上修——修正漂移（revision drift）有数十年跨国实证支持："
                "盈利上修后市场需要数周至数月才完成定价，因为机构资金分批建仓、卖方报告逐步扩散。"
                "(上调家数 − 下调家数)/(上调 + 下调 + 1) 是标准的扩散指数，值域有界、0 为中性锚，"
                "且完全不使用价格与目标价（纯两字段）。它与 PT/close 缺口族的共同变异几乎为零——"
                "后者由股价驱动，前者由分析师对盈利前景的判断驱动，因此在 PROD 相关上有望显著低于 0.855。"
                "这是本批去相关潜力最大的一条，代价是需要承受纯分析师信号的强度通常较低。"
            ),
        },
        {
            "id": 6,
            "type": "FV_REVISION_PER_DISPERSION",
            "expression": (
                f"group_rank(divide(subtract({FV}, ts_delay({FV}, 20)), add({SDF}, 0.01)), industry)"
            ),
            "optimize_reason": (
                "盈利预测修正的精度加权版：分子是 20 日盈利预测变化绝对值（分析师把明年 EPS 上调了多少），"
                "分母是该预测本身的分歧度。当分析师集体上调且意见一致时，信号最强——"
                "这对应『共识已经形成且方向明确』，是机构最愿意跟进的状态；当上调幅度大但分歧也大时，"
                "说明只是部分分析师激进，可靠性低。用 ts_delay 而非 ts_mean 做参照，"
                "保留的是『净变化』而非『偏离度』，与目标价缺口的形态（偏离）在数学上正交，"
                "进一步降低与母本的共线。同时它不使用 close，量纲由 SDF 归一，是干净的分析师内部信号。"
            ),
        },
        {
            "id": 7,
            "type": "FV_REVISION_X_COVERAGE_SHOCK",
            "expression": (
                f"group_rank(multiply(subtract(divide({FV}, ts_mean({FV}, 30)), 1), "
                f"reverse(divide({SDF}, add({FV}, 0.01)))), industry)"
            ),
            "optimize_reason": (
                "盈利预测的『净上修 × 分歧收敛』双击：第一个因子是 30 日预测中枢的相对上修幅度"
                "（divide(FV, ts_mean(FV,30)) − 1），第二个因子是分歧度的倒数（SDF/FV 越小、共识越紧）。"
                "两者相乘 = 只有在分析师既上调预测、又收敛分歧时才产生强信号，这正是『共识上修』的完整定义。"
                "经济含义：分歧收敛本身就是不确定性折价消散的过程（Miller 1977），"
                "与上修叠加后是双重定价修正，理论上比单因子更强。"
                "由于两个分量都不含价格，这条与 PT/close 族的共同变异被压到很低，"
                "是 B 线里去相关最激进的一条，用来探测纯分析师信号的天花板。"
            ),
        },
        {
            "id": 8,
            "type": "FV_REVISION_IR_SUBINDUSTRY_60",
            "expression": (
                f"group_rank(divide(subtract({FV}, ts_delay({FV}, 60)), add({SDF}, 0.01)), subindustry)"
            ),
            "optimize_reason": (
                "把盈利预测修正的时间尺度拉到 60 日，并在 subindustry 内比较：季度级的预测上修"
                "对应一个完整财报周期的预期重置，比 20 日更能过滤掉单次路演/单份报告造成的噪声。"
                "细分组的意义在于盈利预期的修正幅度天然带行业属性——周期股全体上修并不构成个股信号，"
                "只有在本细分行业内上修最多者才有超额信息。这条同时检验两个独立维度"
                "（修正窗口 20→60、分组 industry→subindustry），是 B 线的稳健性收口；"
                "且因不含 close、不含目标价，与母本的 PROD 相关预期最低。"
            ),
        },
    ],
}

if __name__ == "__main__":
    import json
    import os

    out = os.path.join(os.path.dirname(__file__), "batch_g3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(BATCH, f, ensure_ascii=False, indent=2)
    print(f"batch written -> {out} ({len(BATCH['items'])} slots)")
    assert len(BATCH["items"]) == 8
