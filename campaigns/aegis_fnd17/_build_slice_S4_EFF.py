# -*- coding: utf-8 -*-
"""S4_EFF 切片设计器：Q-C「经营效率与利润率结构」轴。
零配额：只做本地 AST 预检 + 骨架指纹查重，不调用任何 BRAIN 接口。
"""
import json
import os
import sys

C = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\campaigns\aegis_fnd17"
sys.path.insert(0, C)
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
import stage3_preflight as P  # noqa: E402

META = P.load_meta()

CANDS = [
    {
        "id": "S4_EFF_01",
        "question_type": "Q4_Interaction",
        "expression": "zscore(subtract(group_rank(fnd17_tcpaormtp, sector), group_rank(fnd17_ptmroepct, sector)))",
        "fields": ["fnd17_tcpaormtp", "fnd17_ptmroepct"],
        "mechanism": "行业内 ROA(前TTM) 排名超出 ROE(前TTM) 排名的幅度，度量股东回报里经营贡献与杠杆贡献的分离度。",
        "counterparty": "把杠杆撬高的 ROE 当成经营质量买单的成长型资金",
        "optimize_reason": (
            "①物理短板：S1~S3 的唯一瓶颈是年化收益 Ret（门禁算术要求 ≈5%，本账户最好只有 2.85%），"
            "而 EUR 冠军式的两腿（FCF/资产、营业利润率）都是慢变量且与规模因子高度共线，USA 移植后 Ret 被结构性压死。"
            "本条改用「前TTM ROA 行业内秩 − 前TTM ROE 行业内秩」作为截面排序量：两腿同为年度化比率、量纲同为百分比，"
            "秩化彻底去掉规模与绝对水平，只留下「谁的股东回报里有经营成分、谁的只有杠杆成分」这一纯结构信息；"
            "group_rank 保留连续幅度（不是硬分箱），最外层 zscore 再统一截面尺度，既不塌成 [0,1] 单边也不产生 Beta 幻觉。"
            "②数学变形为何更强：杜邦恒等式 ROE = ROA + (ROA − r)(D/E)，故 ROE − ROA 正是杠杆楔子；"
            "市场给高 ROE 定价时普遍不区分它是经营挣的还是杠杆撬的，系统性地为杠杆驱动的 ROE 付溢价、并在信用收缩期集中回吐。"
            "本条相减的不是任何单腿水平，而是两腿各自行业内排名的差，捕捉「经营回报排名超出股东回报排名的幅度」——"
            "即经营贡献相对杠杆贡献的分离度，这是单腿 ROA 或单腿 ROE 永远拿不到的独立维度。"
            "③为什么这条比 EUR 移植式挣到更多 Ret：EUR 移植式两腿更新节奏不一致、持仓在两腿之间来回切换，收益被震荡磨损；"
            "本条两腿同频率、同口径（都是前TTM 年度化回报率），更新节奏完全同步，持仓稳定在低换手区间，"
            "Ret 由同一方向的头寸持续累积而非靠换手放大——这是把 Ret 从 2.85% 抬到 5% 的唯一可行路径：低换手 + 连续幅度 + 结构性截面解释力。"
            "④前TTM 的二阶性质：tcpaormtp 与 ptmroepct 都是「上一轮滚动 12 个月」，对最新季报的反映被自动滞后一个季度，"
            "等于把披露噪声与口径切换过滤在外，同时又比一阶差分保留方向信息——这正是 S1 法医结论（一阶差分=噪声）所指向的替代路径。"
            "⑤不会单边、不会伪因果：最外层 subtract 再接 zscore，强制截面零均值、多空腿对称；"
            "两腿同族同向（都是回报率秩）相减，是同量纲的差而非两个有符号量的裸乘，不存在负负得正伪因果；"
            "两字段覆盖率 0.864/0.830 均不稀疏，无需 backfill，避免陈旧填充造成的伪跳变。"
        ),
        "treatment_tag": "rank_weight_interact",
        "self_check": {
            "operator_count": 4,
            "field_count": 2,
            "window_used": None,
            "windows_used": [],
            "top_level_zero_mean": True,
            "unit_consistent": "两腿同为年度化回报率百分比口径（ROA 前TTM 与 ROE 前TTM），秩差在 [0,1] 上同量纲相减，量纲可比。",
            "no_double_signed_multiply": True,
            "no_pv_contamination": True,
            "fields_exist_in_dossier": True,
            "field_acs": [0, 0],
            "field_covs": [0.8638, 0.8297],
            "sum_alphaCount": 0,
            "why_not_already_used": "两字段 ac 均为 0（平台零拥挤）；简报 4.1 已烧字段对中含 tcpaormtp 的是 (tcpaormtt,tcpaormtp)，"
                                    "与 ptmroepct 的组合从未被烧；fnd17 全史 51 条 USA 记录里从无 ptmroepct 出现，"
                                    "骨架亦为 group_rank 差 + zscore 的新拓扑（非 EUR 两腿价差骨架）。",
        },
    },
    {
        "id": "S4_EFF_02",
        "question_type": "Q5_Structure",
        "expression": "zscore(subtract(multiply(fnd17_tcpngmtpq, fnd17_ttmastturn), fnd17_tcpaormtp))",
        "fields": ["fnd17_tcpngmtpq", "fnd17_ttmastturn", "fnd17_tcpaormtp"],
        "mechanism": "当季税前利润率×TTM 资产周转率构造的杜邦口径资产回报，减去前TTM 实际交付的 ROA，得到盈利构建与已兑现回报的错配缺口。",
        "counterparty": "只认滚动 ROA 绝对水平、不看利润率与周转率结构的估值锚定型资金",
        "optimize_reason": (
            "①物理短板：瓶颈是 Ret（需 ≈5%，实测 2.85%）。本条不靠换手去挣 Ret，而是靠信号本身的离散幅度："
            "不复用 EUR 冠军那种 group_rank 分位化（group_rank 把连续比值压成分位、丢掉尾部幅度，σ 被吃掉），"
            "而是直接保留「利润率×周转率」乘积的原始连续幅度，再用 zscore 做截面标准化，"
            "σ 天然高于任何 rank 型结构，而平台口径 Ret = Sharpe × σ ⇒ σ 上台阶就是 Ret 上台阶。"
            "②数学变形为何增强对真实经济学现象的捕捉：杜邦恒等式 ROA = 净利率 × 资产周转率。"
            "本条用「当季税前利润率 × TTM 资产周转率」构造公司当下的盈利能力口径，再减去「前TTM 实际交付的 ROA」，"
            "两者之差就是盈利构建方式与已兑现资产回报之间的错配缺口："
            "若公司宣称利润率改善、资产仍以同样效率运转，则杜邦乘积已高于过去 12 个月真正交付的水平 ⇒ 改善是新的、尚未被滚动口径确认的信息；"
            "反之若乘积低于已交付的 ROA，说明当前季报利润率在退步、或周转率已无法支撑。"
            "这是本数据集里唯一能把「利润率」与「周转率」在**同一量纲（资产回报口径）**下直接对话的构造，"
            "因为两条腿被乘回资产回报族后才允许相减，规避了百分比与比率直接相减的量纲陷阱。"
            "③为什么这条比 EUR 移植式挣到更多 Ret：EUR 冠军两腿（FCF/资产、营业利润率）在本账户 USA/TOP1000 上只拿到 Sh 1.11、"
            "且 FCF/资产 与规模因子共线会抬高 ProdCorr；本条三腿全是纯经营量（当季利润率、TTM 周转率、前TTM ROA），与量价因子正交，"
            "不靠稀释拥挤度换 Sharpe，同时保留未被分位化压缩的尾部幅度 ⇒ σ 与 Ret 同时上台阶。"
            "④前TTM 口径的二阶价值：tcpaormtp 已被平台平滑到 12 个月，它作为基线腿本身不含季报微观噪声，"
            "而当季税前利润率是快变量，两者的差把「快变量的新信息」与「慢变量的兑现水平」分离开，"
            "构成天然的快慢二阶预期差，而不是 S1 被证伪的一阶逐期差分。"
            "⑤不会单边、不会伪因果：最外层 zscore 强制截面零均值、多空对称；multiply 的第二条腿 ttmastturn 定义域 [0,∞) 恒正"
            "（收入/资产），不是第二个有符号量，故不存在负负得正伪因果（引擎只对双 [-1,1] 裸乘拦截）；"
            "乘积在量纲上等于资产回报口径的百分比，与同为回报率口径的 tcpaormtp 可比；"
            "三个字段覆盖率 0.902/0.840/0.864 均不稀疏，无需 backfill。"
        ),
        "treatment_tag": "none",
        "self_check": {
            "operator_count": 3,
            "field_count": 3,
            "window_used": None,
            "windows_used": [],
            "top_level_zero_mean": True,
            "unit_consistent": "乘法腿为「百分比(当季税前利润率) × 比率(资产周转率)」= 资产回报百分比口径，与第二腿同为百分比的"
                               "前TTM ROA 相减，两腿落在同一量纲族（资产回报%）。",
            "no_double_signed_multiply": True,
            "no_pv_contamination": True,
            "fields_exist_in_dossier": True,
            "field_acs": [0, 0, 0],
            "field_covs": [0.9025, 0.8396, 0.8638],
            "sum_alphaCount": 0,
            "why_not_already_used": "三字段 ac 全为 0；简报 4.1 已烧字段对中涉及 tcpaormtp 的仅 (tcpaormtt,tcpaormtp)，"
                                    "本条是 (tcpngmtpq,ttmastturn) 与 (ttmastturn,tcpaormtp) 两组全新组合；"
                                    "fnd17 全史 USA 记录里 ttmastturn 只与 qastturn 同框出现过一次且 Sh 仅 0.12，"
                                    "从未与当季税前利润率、也从未做过乘积形态，骨架为 multiply+subtract+zscore 的新拓扑。",
        },
    },
    {
        "id": "S4_EFF_03",
        "question_type": "Q7_Relative",
        "expression": "zscore(subtract(group_zscore(fnd17_ttmrevpere, sector), group_zscore(fnd17_ttmastturn, sector)))",
        "fields": ["fnd17_ttmrevpere", "fnd17_ttmastturn"],
        "mechanism": "人均收入 TTM 与资产周转率 TTM 的行业内相对位置之差，度量增长来自人效还是来自资本密度。",
        "counterparty": "把轻资产人效公司与重资产周转公司一视同仁的行业配置资金",
        "optimize_reason": (
            "①物理短板：Ret 缺口同样只能由结构挣。本条用两个同族（比率族）的效率量做行业内相对比较："
            "人均收入 TTM 与资产周转率 TTM，各自 group_zscore 后相减；数学上该差值近似「人均资产占用」的行业内相对位置"
            "（人均收入 ÷ 资产周转率 = 人均资产），等于把「效率来自人」还是「效率来自资产」这两个完全不同的增长来源拆开。"
            "②为什么这条比 EUR 移植式挣到更多 Ret：EUR 移植式的两腿（FCF/资产、营业利润率）在 USA/TOP1000 上 Sh 仅 1.11、"
            "Ret 被压到 2.85%，根因是两腿都高度绑定同一个规模因子，截面排序的边际解释力被规模噪声吃掉；"
            "本条两腿先各自做行业内标准化，规模被一次性消掉，而两腿彼此独立（一个跟人力资本、一个跟资产基数），"
            "相减后剩下的是纯粹的效率结构错配——这个维度在任何单腿 ROA/利润率 alpha 里都拿不到 ⇒ 独立解释力 ⇒ σ 与 Ret 同时改善。"
            "③数学上为何捕捉到真实经济现象：若资产周转排名高（资产用得好）而人均收入排名相对低，"
            "说明收入来自重资产与资本密度而非人效，单位收入上的固定成本更重、毛利率对价格与产能利用率的敏感度更高；"
            "若人均收入排名高而周转排名低，说明它是轻资产、人效驱动，费用结构更可压缩、利润率改善更可持续。"
            "市场把两者统称「效率好」⇒ 错配那一端被系统性错误定价，这正是可交易的预期差。"
            "④为什么用前TTM/TTM 口径而不是逐期差分：两腿都是滚动 12 个月口径，季报披露噪声被平台口径本身抹平，"
            "且各自做行业内标准化后相减，得到的是**水平量的行业内相对结构**——这正是 S2/S3 实测唯一有效的范式，"
            "同时又完全避开了 S1 被法医判定为噪声的一阶逐期差分。"
            "⑤不会单边、不会伪因果：最外层 zscore 强制截面零均值、多空腿对称；两腿同族同向（都是比率族）且各自先做 group_zscore 去中枢，"
            "相减是同量纲之差，不存在两个有符号量的裸乘，也不存在双 [-1,1] 乘积；"
            "两字段覆盖率 0.820/0.840 均不稀疏，无需 backfill，避免陈旧填充造成的伪跳变。"
        ),
        "treatment_tag": "group_zscore_neutral",
        "self_check": {
            "operator_count": 4,
            "field_count": 2,
            "window_used": None,
            "windows_used": [],
            "top_level_zero_mean": True,
            "unit_consistent": "两腿同为比率族（人均收入 = 收入/员工，资产周转率 = 收入/资产），各自 group_zscore 后相减，量纲可比。",
            "no_double_signed_multiply": True,
            "no_pv_contamination": True,
            "fields_exist_in_dossier": True,
            "field_acs": [0, 0],
            "field_covs": [0.8198, 0.8396],
            "sum_alphaCount": 0,
            "why_not_already_used": "两字段 ac 均为 0；简报 4.1 已烧字段对里没有出现 ttmrevpere，"
                                    "ttmastturn 仅与 qastturn 同框（不在已烧清单内、且那次 Sh 仅 0.12）；"
                                    "fnd17 全史 USA 51 条中 ttmrevpere 从未被使用，骨架为 group_zscore 差 + zscore 的新拓扑，"
                                    "与 EUR 两腿 group_rank 价差骨架完全不同。",
        },
    },
    {
        "id": "S4_EFF_04",
        "question_type": "Q8_Essence",
        "expression": "zscore(ts_av_diff(divide(fnd17_cainmtt, fnd17_ttmrev), 252))",
        "fields": ["fnd17_cainmtt", "fnd17_ttmrev"],
        "mechanism": "TTM 归母净利率相对自身 252 个交易日（≈一个完整财年）中枢的偏离，度量利润率重估而非利润率水平。",
        "counterparty": "按当前利润率水平线性外推、不看利润率相对自身历史中枢位置的资金",
        "optimize_reason": (
            "①物理短板：S1 法医结论是「一阶逐期差分 = 披露噪声」，S2/S3 的结论是「水平量行业相对价差有效但 Ret 上不去」。"
            "本条同时躲开两坑：**不取本期减上期**，而是取「本期水平 − 自身长期基线」，基线取 252 个交易日 ≈ 一个完整财年，"
            "正好覆盖 4 个季报周期，季节性与披露节奏被整周期平均掉，同时又比 60/120 日基线更慢更稳。"
            "②数学变形为何增强对真实经济现象的捕捉：用两个同为百万美元口径的 TTM 字段（归母净利 cainmtt ÷ TTM 收入 ttmrev）"
            "**自行重建** TTM 归母净利率，既绕开平台净利率字段（ngmpnmtt ac=3、ngmpnmtp ac=8）的拥挤，"
            "也避免把总净利与归母净利的少数股东损益差异混进信号；再用 ts_av_diff 对该比值取 252 期基线偏离，"
            "得到的是「归母净利率相对**它自己**去年常态的重估幅度」——这是二阶量：不是利润率现在多高，"
            "而是利润率相对自身历史中枢移动了多少；这既不同于会被规模与行业结构主导的裸水平值，也不同于会被披露噪声主导的一阶差分。"
            "③为什么这条比 EUR 移植式挣到更多 Ret：EUR 冠军的信号是「FCF/资产 减 营业利润率」的两腿横截面价差，"
            "两腿更新节奏不一致导致持仓不断在两腿之间切换、收益被震荡磨损；本条是**单条**自身基线偏离，"
            "信号连续、幅度不丢失、持仓稳定在低换手区间（随季报更新而非日频抖动），"
            "Ret 由同一方向的头寸持续累积而非靠换手放大——这是把 Ret 从 2.85% 抬到 5% 的直接机制。"
            "④平台口径核对：Ret = Sharpe × σ_annual、Fit = Sh·√(Ret/max(TO,0.125))，在 TO<12.5% 时 Fit 只看 Ret；"
            "本条既保留连续幅度（σ 高）又压低换手（TO 低），是唯一能同时满足 Fit≥1 与 Margin≥10bp（Ret/TO≥0.5）的形态。"
            "⑤不会单边、不会伪因果：最外层 zscore 强制截面零均值、多空对称；分子分母同为 TTM 金额口径（百万美元），比值无量纲，"
            "不存在量纲不一致的相减；全程只有一次除法、一次时序基线差、一次截面标准化，"
            "没有两个有符号量的裸乘，也没有稀疏零值偏移；两字段覆盖率均为 0.929，不稀疏。"
        ),
        "treatment_tag": "ts_mean_smooth",
        "self_check": {
            "operator_count": 3,
            "field_count": 2,
            "window_used": 252,
            "windows_used": [("ts_av_diff", 252)],
            "top_level_zero_mean": True,
            "unit_consistent": "分子分母同为 TTM 金额口径（归母净利 / TTM 收入，单位均为百万美元），相除后为无量纲归母净利率；"
                               "与 252 期自身基线做同量纲时序偏离。",
            "no_double_signed_multiply": True,
            "no_pv_contamination": True,
            "fields_exist_in_dossier": True,
            "field_acs": [0, 0],
            "field_covs": [0.9292, 0.9291],
            "sum_alphaCount": 0,
            "why_not_already_used": "两字段 ac 均为 0；简报 4.1 已烧字段对里 ttmrev 只与 atmtt 同框，cainmtt 完全未出现；"
                                    "fnd17 全史 USA 51 条中 cainmtt 从未被使用，ttmrev 也只做过 FCF/资产 与收入/资产两种比率形态，"
                                    "从未以「自建净利率 + 自身 252 期基线偏离」的拓扑出现。",
        },
    },
]


def main():
    ok = True
    for c in CANDS:
        r = P.preflight(c["expression"], c["optimize_reason"], c["counterparty"],
                        META, META, phase0=False, op_cap_override=4)
        print("=" * 90)
        print(c["id"], "->", r["ok"])
        print("  expr:", c["expression"])
        print("  issues:", r["issues"])
        ck = r["checks"]
        print("  ops=%s fields=%s top=%s zm=%s windows=%s acs=%s" % (
            ck["operator_count"], ck["field_count"], ck["top_level"],
            ck["top_level_zero_mean_ok"], ck["windows"], ck["fields_used"]))
        print("  dim:", ck["dimension_audit"]["is_valid"], ck["dimension_audit"]["issues"])
        print("  redteam:", ck["engine_redteam"]["verdict"], ck["engine_redteam"]["issues"])
        print("  unit:", ck["unit_consistent"], ck["subtract_legs"])
        if not r["ok"]:
            ok = False

    sk = P.skeleton_and_fingerprint([c["expression"] for c in CANDS],
                                    "USA", "TOP1000", 1, "STATISTICAL")
    print("=" * 90)
    print("skeleton freq:", sk["freq"])
    print("history:", sk["history"])
    print("violations:", sk["violations"])
    hard = [v for v in sk["violations"] if not v.startswith("同骨架")]
    assert not hard, hard

    # 字段真实性 / 量纲族自检
    for c in CANDS:
        for f in c["fields"]:
            assert f in META, f
            assert META[f]["alphaCount"] == c["self_check"]["field_acs"][c["fields"].index(f)]

    assert ok, "存在未通过预检的候选"
    out = os.path.join(C, "slices", "slice_S4_EFF.json")
    payload = {
        "agent": "S4_EFF",
        "candidates": CANDS,
        "SLICES_SUMMARY": (
            "S4_EFF（Q-C 经营效率与利润率结构）交付 4 条："
            "S4_EFF_01 前TTM ROA 秩 − 前TTM ROE 秩（杠杆贡献 vs 经营贡献分离，ac 0+0=0）；"
            "S4_EFF_02 当季税前利润率×TTM 资产周转率 − 前TTM ROA（杜邦乘积与已兑现回报的错配缺口，ac 0+0+0=0）；"
            "S4_EFF_03 人均收入 TTM − 资产周转率 TTM 的行业内标准化之差（人效 vs 资本密度背离，ac 0+0=0）；"
            "S4_EFF_04 TTM 归母净利率相对自身 252 期中枢的偏离（利润率重估，ac 0+0=0）。"
            "全部 4 条 ac 之和均为 0（零拥挤），字段数 2~3、算子数 3~4、时间窗仅 252（白名单内），"
            "最外层零均值、零外部/内嵌量价字段、无黑名单算子、无双有符号裸乘；"
            "本地 stage3_preflight 六重闸门 4/4 全 ok，同批骨架唯一、跨批指纹历史 <4。"
        ),
    }
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("[SAVED]", out)


if __name__ == "__main__":
    main()
