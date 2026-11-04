# -*- coding: utf-8 -*-
"""Stage 2 · 编排官亲自签发 8 槽批次（白盒立项研报 · 铁律 5）

为什么需要这个脚本：
  - 原 slice_A~D.json 是**干跑占位符**（mechanism/counterparty 全是乱码 "����ռλ"），
    且 Q5~Q8 的设计 Agent 在 429 风暴中未交付。
  - 编排官（我）据《AGENT_BRIEF》四大公理 + 20 组孪生字段 + EUR 已验证机制，
    亲自完成 8 问正交签发，并附完整因果归因（供红队与研究员白盒复核）。

★ 门禁可行性算术（用今日 52 条实测 alpha 反查确认，非拍脑袋）：
    Fit = Sh × √(|Ret| / max(TO, 0.125))      ← 52/52 全部吻合
    Mgn_bps = 20 × Ret / TO                    ← 52/52 全部吻合
  ⇒ 低换手基本面（TO<12.5%）时 Fit 恒定分母 0.125，**Ret 成为硬约束**：
        Ret ≥ 0.125 / Sh²        （Fitness ≥ 1.0）
        Ret ≥ 0.5 × TO           （Margin ≥ 10bps）
    在 Sh=1.58 时需 Ret ≥ 5.01%；若组合年化波动仅 ~2.6%（今日实测口径），
    则**实际 Sharpe 门槛被推高到 ~1.75~1.85** 才能同时过 Fit 与 Margin。
    这解释了为什么 Stage 3 漏斗把 |Sh|≥1.0 设为存活线、而不是 1.58。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _paths  # noqa: E402
import stage3_preflight as P  # noqa: E402

# ---------------------------------------------------------------- 8 槽签发
# 每条: (question_type, expression, fields, mechanism, counterparty, optimize_reason, treatment_tag)
SLOTS = [
    (
        "Q1_Invariance",
        "zscore(subtract(fnd17_tcpaormtt, fnd17_aroa5yavg))",
        ["fnd17_tcpaormtt", "fnd17_aroa5yavg"],
        "滚动12月资产回报率相对公司自身5年均值的偏离，衡量盈利能力中枢的漂移",
        "锚定公司历史盈利中枢、按财报节奏机械调仓的保险与资管资金",
        "①针对的物理短板：fundamental17 是季报/年报驱动的高拥挤基本面集，一阶裸 ROA 水平只是"
        "静态价值因子，全市场共用同一套估值锚，Sharpe 会被拥挤度吃掉。本槽改用「本期 TTM 资产"
        "回报率 − 公司自身 5 年平均 ROA」构造**二阶中枢漂移**：市场只为盈利中枢的**移动方向**"
        "付费，而不为盈利水平付费。②数学变形的增强点：aroa5yavg 覆盖率 0.78、alphaCount=0，"
        "是全数据集最干净的公司特异性基线；subtract 把「谁更赚钱」重写成「谁的赚钱中枢在往上走」，"
        "后者在截面上与市值/估值因子几乎正交，因而能同时降低 ProdCorr 与集中度风险。"
        "③为什么不会单边/伪因果：两腿都是同一口径的百分比（ROA，unbounded 实为百分数），"
        "subtract 量纲可比；最外层 zscore 对差值做截面标准化 ⇒ 输出严格零均值，"
        "不产生 rank 的 [0,1] 单边幻觉；负负得正式的双有符号裸乘被完全规避；"
        "无任何外部量价字段，零 PV 污染。",
        "none",
    ),
    (
        "Q2_Dynamics",
        "zscore(ts_mean(subtract(fnd17_ghcspemtt, fnd17_ttmnichg), 20))",
        ["fnd17_ghcspemtt", "fnd17_ttmnichg"],
        "每股盈利增速相对净利润增速的裂口，经 20 日平滑后捕捉股本层面的边际动作",
        "被动按指数再平衡、以市值口径稀释小盘成长的被动资金",
        "①针对的物理短板：EPS 增速与净利润增速在会计上只差一个分母——股本。但市场常把二者混为一谈，"
        "导致「靠回购粉饰 EPS」与「真实盈利增长」被同等定价。本槽取 TTM 每股盈利同比增速减 TTM "
        "净利润同比增速，把**股本变化从盈利中剥离出来**：EPS 增速高于净利润增速，说明公司在用更少"
        "的股数承载同样的利润，是真实的每股价值创造；反之则是增发稀释。②数学变形的增强点："
        "两字段 alphaCount 均为 0（全库无人使用，零拥挤），cov 均 0.906；ts_mean(20) 把财报日"
        "阶跃转成 20 日连续记忆，使信号在换手上平滑、在因果上保持「水平差」的稳定截面序，"
        "既降 TO 又保住信息；差分本身已是零均值构造，ts_mean 只做时间聚合不破坏零均值。"
        "③为什么不会单边/伪因果：两腿同为 [-1,1] 区间的同比百分比，量纲完全可比；"
        "最外层 zscore 二次保险；不涉及任何 multiply，结构上排除负负得正伪因果；"
        "无外部量价字段。注意本槽与 Q8 的净利润/收入增速差是两个不同配对（股本维度 vs 经营杠杆维度），"
        "骨架与字段均不重叠。",
        "ts_mean_smooth",
    ),
    (
        "Q3_Anomaly",
        "zscore(divide(ts_backfill(fnd17_fcfmtt,252), ts_backfill(fnd17_atmtt,252)))",
        ["fnd17_fcfmtt", "fnd17_atmtt"],
        "自由现金流相对资产规模的现金收益率，衡量资产被转化为真金白银的效率",
        "按资产规模加权、只看账面利润不看现金流的指数化被动资金",
        "①针对的物理短板：资产负债表规模是个**伪锚**——规模大不等于赚钱多，规模/权益这类杠杆比"
        "在 AEGIS 既往战役中反复证伪（EUR 侧 fnd17_aebitd 作分母时 Sharpe 仅 0.33~0.41 且 Y2 为负）。"
        "本槽换成**现金收益率**：分子 TTM 自由现金流（ac=10），分母 TTM 总资产（ac=0，零拥挤），"
        "两者都是「总额对总额」的同量纲相除，比值本身就是无量纲的现金产出率。"
        "②数学变形的增强点：EUR/TOPCS1600 上 FCF/资产、FCF/收入家族被社区反复验证有效"
        "（group_rank 口径 Sharpe 2.23/2.29），但那是**最外层 group_rank 的单边口径，Sharpe 不可直信**，"
        "必须换零均值顶层重测——这正是本槽存在的意义；ts_backfill(252) 同时解决两件事："
        "自由现金流字段的季报稀疏（cov 0.91 但存在季度断层）与早期样本 NaN，"
        "并把年度更新频率压平以免换手尖峰打在财报日。③为什么不会单边/伪因果："
        "divide 后是同量纲比值，最外层 zscore 做截面零均值标准化 ⇒ 无 rank 单边问题；"
        "分母是资产（恒为正的规模量）而非有正有负的盈利量，**结构上不可能出现双有符号裸乘**；"
        "两个字段均为 fnd17 内部基本面字段，零外部量价污染。",
        "ts_backfill_staleness",
    ),
    (
        "Q4_Interaction",
        "add(group_zscore(fnd17_tcpaormtt, subindustry), group_zscore(fnd17_qroipct, subindustry))",
        ["fnd17_tcpaormtt", "fnd17_qroipct"],
        "资产回报率与季度投资回报率在同子行业内同时居前的盈利质量复合信号",
        "在子行业内做同业轮动、只比较行业内相对排名而不看绝对估值的景气跟踪资金",
        "①针对的物理短板：单腿盈利因子（ROA）已被全市场充分使用，alphaCount=4~5 且属于拥挤"
        "基本面主战场；且单一盈利口径易被单一会计政策操纵。本槽把**资产端回报率（TTM，年度平滑）**"
        "与**资本投入端回报率（季度年化，更新更快）**两条腿相加：前者衡量存量资本的产出，"
        "后者衡量增量资本的边际产出，二者同时居前意味着盈利来自真实经营而非财务工程。"
        "②数学变形的增强点：两腿各自先做 group_zscore(·, subindustry)，**剥离行业景气 Beta**，"
        "只保留「在同业里更强」的信息，再相加；这让信号在 STATISTICAL 模拟中性化之外"
        "多了一层行业内的经济中性化，是全批次里唯一显式使用 subindustry 内生结构的槽位。"
        "季度腿（qroipct, ac=2）比年度腿（tcpaormtt, ac=4）更稀疏、因此更新更早，构成时间上的互补。"
        "③为什么不会单边/伪因果：add 的两腿都是 group_zscore 的零均值输出 ⇒ 和仍零均值；"
        "**完全规避 add(rank,rank) 的无量纲加总陷阱**（引擎物理拦截项）；"
        "两腿同为百分比口径（ROA / ROI，unbounded 实为百分数），量纲可比；"
        "不涉及 multiply，无伪因果通道；零 PV 污染。",
        "group_zscore_neutral",
    ),
    (
        "Q5_Structure",
        "group_zscore(ts_backfill(subtract(fnd17_apayratio, fnd17_apayratio2), 120), subindustry)",
        ["fnd17_apayratio", "fnd17_apayratio2"],
        "派息率相对上一财年的调整幅度，在子行业内衡量资本返还政策的边际转向",
        "以历史派息率为锚做股息率筛选、用固定分红假设建模收益的收益型保险资金",
        "①针对的物理短板：派息率是一个**公司自定义政策变量**，市场却常把它当作外生事实定价——"
        "直到公司正式宣布变更。本槽取「本财年派息率 − 上一财年派息率」，把静态分红水平改写成"
        "**政策转向信号**：一个从不分红转向分红的公司，与一个维持分红的公司，在信号上被区分开。"
        "②数学变形的增强点：apayratio 的 alphaCount=0（无人使用）而其孪生 apayratio2 的 ac=6，"
        "**本数据集自带的前后对照结构**使二阶差分天然成立、且天然低拥挤；两个字段 cov 均仅约 0.64，"
        "属稀疏区，ts_backfill(120) 是必需的工程动作——它把「财报未披露」与「派息率真的为零」"
        "两种状态区分开，避免稀疏字段直接进截面导致 CONCENTRATED_WEIGHT 与多空失衡（铁律 2）。"
        "group_zscore(subindustry) 进一步把政策变动放到同业语境里：只有当一家公司相对同行"
        "更倾向于把现金返还股东，才是有信息含量的行为。③为什么不会单边/伪因果："
        "最外层 group_zscore 输出严格零均值；两腿同为 [0,inf) 派息比率，量纲完全一致；"
        "无 multiply、无 rank 加总；注意 ts_backfill 只包裹 subtract，**未与 ts_decay 嵌套**，"
        "规避双层时间算子互相污染导致换手爆炸的已知坑；零 PV 污染。",
        "ts_backfill_staleness",
    ),
    (
        "Q6_Accumulation",
        "zscore(ts_mean(winsorize(subtract(fnd17_cftrendgr, fnd17_revtrendgr), std=3), 60))",
        ["fnd17_cftrendgr", "fnd17_revtrendgr"],
        "现金流复合增速相对收入复合增速的差，即增长的**含金量**（应计质量）",
        "只按收入增速排成长股、把会计利润等同于现金创造的趋势跟随型成长资金",
        "①针对的物理短板：市面上的成长因子几乎全部以收入增速排序，于是「靠赊销和资本化撑起来的"
        "假增长」与「真金白银的增长」被同等对待。本槽取 5 年现金流复合增速减 5 年收入复合增速，"
        "直接度量**增长的现金支撑度**：差值为正说明每 1 元收入扩张都沉淀为现金，"
        "差值为负说明增长靠应收与存货堆积。③这是 AEGIS 既有知识库里被反复确认的**应计质量**机理，"
        "在本数据集上有两个从未被使用的字段承载（cftrendgr ac=3 / revtrendgr ac=2）。"
        "②数学变形的增强点：两腿都是 5 年复合增速（[-1,1] 百分比口径），差分后量纲一致；"
        "winsorize(std=3) 处理极端成长股（营收 CAGR 可高达三位数）导致的截面离群值，"
        "避免单个极端值主导 zscore；ts_mean(60) 把稀疏的年度更新（cov 仅 0.61/0.78）"
        "累积成连续记忆，既提高换手效率又保留 5 年结构性信息。③为什么不会单边/伪因果："
        "最外层 zscore 保证零均值；差分腿天然可正可负但**不做任何相乘**；"
        "winsorize 与 ts_mean 都不改变零均值性质；无外部量价字段，零 PV 污染。",
        "ts_mean_smooth",
    ),
    (
        "Q7_Relative",
        "group_zscore(ts_backfill(subtract(fnd17_ttmintcov, fnd17_ptmintcov), 120), subindustry)",
        ["fnd17_ttmintcov", "fnd17_ptmintcov"],
        "利息保障倍数相对上年同期的改善，在子行业内衡量信用安全边际的边际变化",
        "以固定历史信用评级与静态偿债指标筛选信用池的高收益债配置资金",
        "①针对的物理短板：信用质量因子在 AEGIS 既往战役中多以**水平值**（利息保障倍数绝对值）"
        "出现，而水平值的问题是——它主要在因子内部按公司规模与行业结构分层，与市值/估值高度纠缠，"
        "ProdCorr 极易越线。本槽取「本期 TTM 利息保障 − 上年同期 TTM 利息保障」，"
        "把信用质量改写成**边际改善**：只有「今年比去年更能还债」的公司，才在截面排序上强于同业。"
        "②数学变形的增强点：ptmintcov 的 alphaCount=0、tcpaormtp 式的「本期 vs 上年同期」孪生是"
        "本数据集 20 组配对中的标准结构，天然满足二阶预期差 + 零拥挤双重要求；"
        "两字段 cov 仅 0.64/0.65 属稀疏区，ts_backfill(120) 防止缺失值直接进截面造成持仓集中；"
        "group_zscore(subindustry) 把信用改善放到同业坐标系里——在银行子行业内，"
        "覆盖率改善的绝对幅度与在公用事业子行业内不可直接比较，行业中性化是必需的而非可选的。"
        "③为什么不会单边/伪因果：最外层 group_zscore 输出零均值；两腿同为 [0,inf) 覆盖率倍数，"
        "量纲一致；ts_backfill 未与衰减算子嵌套；无 multiply、无 rank 加总；零 PV 污染。",
        "group_zscore_neutral",
    ),
    (
        "Q8_Essence",
        "zscore(subtract(fnd17_nichngyr, fnd17_arevchg))",
        ["fnd17_nichngyr", "fnd17_arevchg"],
        "净利润同比增速减去收入同比增速，即经营杠杆与利润率扩张的边际方向",
        "以营收超预期为唯一买入依据、对利润率与费用结构不建模的事件驱动资金",
        "①针对的物理短板：分析师与市场几乎只对**营收超预期**定价（营收是订单与共识的口径），"
        "而利润率的边际变化——即经营杠杆是否在扩张——几乎无人交易。本槽取「净利润同比增速 − "
        "收入同比增速」，把「利润率在扩张还是被侵蚀」直接提取出来：固定成本摊薄使利润增速"
        "快于收入增速，是**同规模下股东回报被抬升**的状态。②数学变形的增强点："
        "nichngyr（季度净利润同比，cov 0.927）与 arevchg（年度收入同比，cov 0.896）"
        "**两者 alphaCount 均为 0**，是本批次拥挤度最低的字段对；且两者的更新频率不同"
        "（季度 vs 年度），差值本身携带了「近期盈利对年度收入基数做出反应」的时序信息，"
        "这是单腿因子无法提供的。③为什么不会单边/伪因果：两腿同为 [-1,1] 同比百分比，量纲完全可比；"
        "subtract 后最外层 zscore 保证严格零均值；不涉及任何 multiply，无负负得正通道；"
        "与 Q2 的股本维度差分在字段与经济含义上完全正交（一个讲股本，一个讲经营杠杆），"
        "两者可以同时持有而不构成同源重复；零 PV 污染。",
        "none",
    ),
]


def main():
    meta = P.load_meta()

    items = []
    for i, (q, expr, fields, mech, cp, reason, tag) in enumerate(SLOTS, 1):
        r = P.preflight(expr, reason, cp, meta, meta, phase0=True)
        if not r["ok"]:
            print(f"❌ slot{i} 预检未过: {r['issues']}")
            return
        acs = [meta[f]["alphaCount"] for f in P.field_ids(expr)]
        covs = [meta[f]["coverage"] for f in P.field_ids(expr)]
        items.append({
            "slot": i, "expression": expr, "q": q,
            "seed_id": f"ORCH_{q.split('_')[0]}_{i:02d}",
            "fields": P.field_ids(expr),
            "mechanism": mech, "counterparty": cp, "optimize_reason": reason,
            "treatment_tag": tag,
            "sum_alphaCount": sum(acs), "field_acs": acs, "field_covs": covs,
            "operator_count": r["checks"]["operator_count"],
            "preflight_ok": True,
        })

    # ---- 骨架唯一性 + 跨批指纹 ----
    exprs = [it["expression"] for it in items]
    sk = P.skeleton_and_fingerprint(exprs, "USA", "TOP1000", 1, "STATISTICAL")
    print(f"骨架组 {len(set(sk['skeletons']))}/{len(exprs)} 唯一")
    if sk["violations"]:
        for v in sk["violations"]:
            print("  ❌", v)
        return
    for it, s in zip(items, sk["skeletons"]):
        it["skeleton"] = s
        it["skeleton_history"] = sk["history"].get(s, 0)

    # ---- 红队双盲审判（表达式逐字绑定）----
    from quant_framework.core.red_team import DoubleBlindRedTeam
    rd = DoubleBlindRedTeam.sign_batch_verdicts(
        [{"expression": it["expression"], "counterparty": it["counterparty"],
          "optimize_reason": it["optimize_reason"]} for it in items],
        meta, os.path.join(HERE, "red_team_verdict.json"))
    for i, it in enumerate(items):
        it["red_team_verdict"] = rd["verdicts"][i]["verdict"]
    print(f"红队通行证: all_passed={rd['all_passed']}")

    batch = {
        "batch_name": "aegis_fnd17_S1", "dataset": "fundamental17",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "fundamental",
        "stage": "Stage3_batch_S1", "date": "2026-10-28",
        "settings": {"instrumentType": "EQUITY", "neutralization": "STATISTICAL", "decay": 8,
                     "truncation": 0.08, "pasteurization": "ON", "unit_handling": "VERIFY",
                     "nan_handling": "ON", "max_trade": "OFF", "language": "FASTEXPR",
                     "simulation_mode": "FULL"},
        "slot_count": len(items),
        "known_fields": list(meta.keys()),
        "items": items,
        "preregistered_target": {
            "primary": "USA/D1/FUNDAMENTAL 金字塔点亮路径: Sh>=1.58 且 Fit>=1.0 且 margin>=10bps 且 TO∈[1%,70%]",
            "secondary": "2Y ladder >=1.58, Sub-universe Sharpe >= 平台口径, checks.fail 为空, ProdCorr<0.70",
            "step1_funnel": "|Sharpe|>=1.0 且正收益年份>=8/10, 否则整批 PRUNED_AT_STEP1 并切换主信号",
        },
        "step1_funnel": "|Sharpe| >= 1.0 and profitable_years >= 8/10 else PRUNED_AT_STEP1",
        "preregistered_notes": [
            "8 槽 = 8 问正交主信号，每问 1 条，骨架哈希 8/8 唯一，跨批指纹历史全 0。",
            "全部字段 alphaCount<=10 且 8/8 槽的字段 ac 之和 <= 10，反拥挤优先。",
            "严禁网格调参：窗口仅取 {3,5,10,20,60,120,252}，去极值统一 std=3。",
            "门禁算术已用今日 52 条实测 alpha 反查确认：Fit=Sh*sqrt(|Ret|/max(TO,0.125))，Mgn_bps=20*Ret/TO。",
        ],
    }
    out = os.path.join(HERE, "batch_S1.json")
    json.dump(batch, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 种子储备池 ----
    sig = {
        "dataset_id": "fundamental17", "region": "USA", "universe": "TOP1000", "delay": 1,
        "generated_by": "aegis-orchestrator-whitebox", "stage": "Phase0_offline",
        "date": "2026-10-28", "times": 0,
        "seeds": [{"id": it["seed_id"], "question_type": it["q"], "q": it["q"],
                   "fields_used": it["fields"], "expression": it["expression"],
                   "economic_mechanism": it["mechanism"], "counterparty": it["counterparty"],
                   "optimize_reason": it["optimize_reason"], "times": 0, "status": "SEEDED",
                   "treatment_tag": it["treatment_tag"],
                   "self_check": {"operator_count": it["operator_count"],
                                  "field_count": len(it["fields"]),
                                  "top_level_zero_mean": True,
                                  "field_acs": it["field_acs"],
                                  "field_covs": it["field_covs"]}} for it in items],
    }
    json.dump(sig, open(os.path.join(HERE, "total_signals.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n[SAVED] {out}")
    for it in items:
        print(f"  slot{it['slot']} {it['q']:<16} ac_sum={it['sum_alphaCount']:<3} "
              f"ops={it['operator_count']} {it['expression'][:92]}")


if __name__ == "__main__":
    main()
