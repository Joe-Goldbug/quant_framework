# -*- coding: utf-8 -*-
"""
Phase 4 driver: 种子因子定向优化 — ZYm1pn3n (news12 / USA / TOP1000 / delay1).

种子病灶 (batch1 swarm, alpha ZYm1pn3n):
  expr = divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))
  Sh -1.37 / Fit -0.31 / TO 129.9% / Mgn -1.01bp / DD 66.2% / 2Y -1.68 / InvSh -1.01 / rnSh -1.65
  -> 盈利方向 = reverse: Sh +1.37 / 2Y +1.68 / rnSh +1.65 (推断), TO 129.9% 为唯一致死因素.

MANDATE 事实核查: headline_positive_term_count_v2 在 news12 中不存在
  (实证: filter_sharpe=False 全量实时拉取, 875 字段, id/description 零匹配).
  替代字段 = news_vol_stddev (当日成交量相对 30 日均量的 z 分数, cov 0.967, 仅 19 个存量 alpha, 低拥挤).

架构 (平台约束: submit_multi_simulation 每次提交只应用一套 settings):
  Probe  (2 sims): ts_decay_exp_window 位置参数 vs 关键字参数 双变体探针, 防单条语法错误 CANCEL 整批
  Wave 1 (8 sims): 表达式级处方 @ INDUSTRY/decay=6/trunc=0.025 (与种子同设置, 保证归因纯净)
  Wave 2 (8 sims): 同 8 表达式 @ STATISTICAL/decay=6/trunc=0.025 (中性化下沉配对消融)
"""
import asyncio
import json
import os
import re
import sqlite3
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule
from quant_framework.core.sim_runner import SimBatchRunner
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.dimension_rules import DimensionAuditor

CAMPAIGN = os.path.join("quant_framework", "campaigns", "USA_news_news12")

# ---- 种子与替代字段 ----
A = "divide(news_max_up_amt, add(news_max_up_amt, news_max_dn_amt))"  # 不对称度核心 (种子本体)
V = "news_vol_stddev"  # 关注度强度替代字段 ( mandate 字段不存在, 最近似功能替代 )

BASE_SETTINGS = dict(region="USA", universe="TOP1000", delay=1, category="news",
                     neutralization="INDUSTRY", decay=6, truncation=0.025)
WAVE2_NEUTRALIZATION = "STATISTICAL"

REASON_1 = (
    "反向对照锚：种子原始方向 Sh -1.37，符号翻转后理论推断 Sh +1.37 / 2Y +1.68 / rnSh +1.65 全部过线，唯 TO 129.9% 越红线。"
    "本槽把推断变为实测：夏普与换手率在符号翻转下严格奇对称（Sh(-x)=-Sh(x)、TO 不变），但回撤、子域夏普与相关性并非奇函数，"
    "只有直测才能得到盈利方向的真实风险轮廓。此槽同时是全部处方的归因基准——任何处方的读数差异都必须以本槽为参照，"
    "区分处方增益与批次环境漂移。若本槽复现 +1.37 且 TO≈130%，证明批次与种子完全同构，后续 7 槽读数全部有效。"
)
REASON_2 = (
    "半衰期指数平滑：ts_decay_exp_window 以 factor=0.5 的半衰期对过去 20 日不对称度指数加权——最近事件日权重 1、前一日 0.5、"
    "第三日 0.25，有效记忆约 2-3 个交易日。与 batch2 已证伪的 ts_mean 等权平滑（MA20 把 Sh 从 1.37 稀释到 0.25）有本质区别："
    "等权平均把 20 天等量混入，指数衰减把绝大部分权重压在最新事件日，理论上在压噪与保边之间取得严格更优的折中。"
    "本槽是对瞬态边缘假说的直接判决实验：若显著优于 MA20 且换手率大幅下降，平滑族复活；若同样死亡，则降换手必须转向门控与排序族。"
)
REASON_3 = (
    "时序自秩：把当日不对称度映射到自身过去 20 日的历史分位，输出天然有界。降换手机制在于分位序列只在相对位置穿越时跳变，"
    "而原始比值的日频抖动（中性化重排名导致）会被分位化吸收。同时分位化完成个股间校准：同样 0.75 的比值，对每日多事件的苹果是常态"
    "（低分位），对季度才有事件的小盘股是极值（高分位），分位化后二者可直接比大小。与槽 2 共同标定时间维度包装的稀释代价曲线："
    "若两者都保不住 1.0 而槽 4/5 能保住，则证明降换手正确方向是横截面条件化而非时间平滑。"
)
REASON_4 = (
    "关注度门控（核心新假说）：batch3 阈值粘性失败根因是门控条件取自信号自身极端值——只保留尾部事件、丢弃中部分布的大部分截面信息"
    "（Sh 跌至 0.30）。本槽把门控条件换为独立慢变量：当日成交量相对 30 日均量的 z 分数超过 0.5。机制假说：不对称度边缘由关注度驱动的"
    "过度反应承载——被异常放大的成交量背书的事件才是注意力冲击，无关注度背书的比值波动是流动性噪声。关注度是慢变变量，"
    "条件持续期间仓位不动，换手结构性下降而不触碰信号本身，且不改变活跃日的完整截面分布，与 batch3 尾部门控有本质区别。"
    "0.5 为温和探针（保留约三至四成交易日），成立后可沿 1.0/1.5 扫描剂量效应。"
)
REASON_5 = (
    "关注度连续缩放（门控假说的连续版对照）：不用开关而用乘性缩放，让反转强度与关注度成正比。若过度反应确由注意力承载，"
    "该乘积应在高关注度事件上放大边缘、在低关注度事件上把噪声压缩至零（z 分数为负时信号自动衰减）。乘性结构零参数、无量纲冲突，"
    "且保留全部交易日的截面信息——理论换手率接近原始 130%。因此本槽是纯边缘增强探针：若 Sh 显著高于对照锚而 TO 不变，"
    "证明关注度缩放就是边缘来源；若 Sh 不变，则槽 4/6/8 的整个条件化族被证伪。两槽共同完成对该假说的双向判决。"
)
REASON_6 = (
    "缩放+组内排序：把槽 5 的连续缩放再包一层组内排序。两层机制：缩放保留关注度强度信息；组内排序把权重均匀化——batch1 已证"
    "group_rank 单独可将 TO 从 129.9% 压到 49.9%（Sh 稀释至 0.71），其降换手来自消除极端值导致的权重集中与排名抖动。"
    "组内排序同时剔除行业层面对关注度分布的系统性差异（科技股天然高关注、公用事业天然低关注），保留同业内注意力反转的相对强弱。"
    "本槽检验两个已验证机制的可叠加性：若 Sh 显著高于纯排序且 TO 仍在 50% 区间，则得到该家族第一个 TO 合规且边缘增强的形态。"
)
REASON_7 = (
    "去极值修剪（直接靶向 Margin 与回撤病灶）：槽 5 乘积的尾部风险在于关注度 z 分数在极端事件日可达 5-10 倍标准差，"
    "与反转信号相乘后个别交易日信号值爆表，中性化后个别股权重过高——这正是种子 Margin 仅 1bp、DD 66% 的微观来源"
    "（权重被少数极端日主导）。winsorize 在 4 倍标准差处截尾，保留中部信息量同时削平权重尾部。与 event_return_model 战役中"
    "winsorize 有害的结论并不矛盾：那里修剪的是信号主体（整体分布变形），这里修剪的是乘性交互引入的尾部污染"
    "（主体分布在 [0,1] 比值上本已有界）。若 Margin 相对槽 5 显著抬升而 Sh 不塌，则去极值抬 Margin 处方成立。"
)
REASON_8 = (
    "门控+组排组合（剂量叠加）：把两个已验证的降换手机制叠加——关注度门控（槽 4，条件持续期间仓位不动，降换手主力）+ 组内排序"
    "（batch1，权重均匀化，降换手辅助），两者作用在不同环节理论上可乘。若 TO 降至 20% 以下且 Sh 保住 1.0 附近，则同时逼近"
    "Fit 数学要求的 12.5% 黄金区间，是全批次最接近可提交的形态。风险是双重过滤后有效截面变薄，需结合 longCount/shortCount 判读。"
    "本槽与槽 4 的差值单独隔离排序的边际贡献。"
)


def build_prescriptions(exp_syntax: str) -> list:
    """exp_syntax: 'keyword' (指数半衰期平滑) or 'linear' (线性衰减回退, 指数写法平台验证失败)."""
    if exp_syntax == "keyword":
        exp_call = f"ts_decay_exp_window({A}, 20, factor=0.5)"
        reason2 = REASON_2
        type2 = "HALF_LIFE_EXP_SMOOTH"
    else:
        exp_call = f"ts_decay_linear({A}, 20)"
        reason2 = (
            "线性衰减平滑（指数写法回退）：探针实证 ts_decay_exp_window 关键字写法在本配置同样报错，按预案回退到平台已验证的"
            "ts_decay_linear——以 20 日线性衰减加权（今日权重 20、昨日 19、…、第 20 日权重 1）平滑不对称度。与 batch2 证伪的"
            "ts_mean 等权平滑相比，线性衰减同样把权重压在近期但梯度更缓，稀释代价应介于等权与指数写法之间。官方文档明确标注"
            "衰减类算子 may help reduce turnover——本槽直接检验该承诺在 news12 瞬态边缘上是否成立，并与 batch2 的 MA20/60/250 "
            "读数共同标定时间维度包装的完整稀释曲线。"
        )
        type2 = "LINEAR_DECAY_SMOOTH"
    return [
        {"id": 1, "type": "CONTROL_REVERSE", "expression": f"reverse({A})", "optimize_reason": REASON_1},
        {"id": 2, "type": type2, "expression": f"reverse({exp_call})", "optimize_reason": reason2},
        {"id": 3, "type": "SELF_TS_RANK", "expression": f"reverse(ts_rank({A}, 20))", "optimize_reason": REASON_3},
        {"id": 4, "type": "ATTENTION_GATE", "expression": f"trade_when(greater({V}, 0.5), reverse({A}), 0)", "optimize_reason": REASON_4},
        {"id": 5, "type": "ATTENTION_SCALE", "expression": f"multiply(reverse({A}), {V})", "optimize_reason": REASON_5},
        {"id": 6, "type": "SCALE_GROUP_RANK", "expression": f"group_rank(multiply(reverse({A}), {V}), subindustry)", "optimize_reason": REASON_6},
        {"id": 7, "type": "WINSORIZE_TAIL", "expression": f"winsorize(multiply(reverse({A}), {V}), std=4)", "optimize_reason": REASON_7},
        {"id": 8, "type": "GATE_GROUP_RANK", "expression": f"trade_when(greater({V}, 0.5), group_rank(reverse({A}), subindustry), 0)", "optimize_reason": REASON_8},
    ]


def purge_fingerprints(exprs: list, neutralization: str):
    """回滚未真正送抵 Brain 的幻影指纹 (phase3 教训)."""
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        fixed = corrector.correct_expression(e)
        h = corrector.compute_fingerprint(fixed, "USA", "TOP1000", 1, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n} phantom records (neutralization={neutralization})")


async def probe_exp_syntax(known_fields: list) -> str:
    """重设计探针: 每次提交只含 1 条高风险表达式 (batch 内单条错误会 CANCEL 兄弟槽).
    官方文档确认签名为 ts_decay_exp_window(x, d, factor = 1.0, nan = True), 示例用关键字 factor = 0.5.
    因此本探针测关键字写法; 伙伴槽 = 线性衰减回退候选 (若指数写法失败, 该读数直接复用为槽2).
    返回 'keyword' 或 'linear'."""
    probes = [
        f"ts_decay_exp_window({V}, 20, factor=0.5)",   # 高风险: 关键字写法 (官方示例形式)
        f"reverse(ts_decay_linear({A}, 20))",          # 回退候选 + 探针健康对照
    ]
    corrector = ASTSandboxCorrector()
    for e in probes:
        fixed = corrector.correct_expression(e)
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category="news")
        if not audit["is_valid"]:
            raise ValueError(f"探针本地审计失败: {e} -> {audit['issues']}")
    corrector.check_and_record_batch(probes, "USA", "TOP1000", 1, "INDUSTRY")
    print("[probe] 提交探针 (关键字指数衰减 + 线性衰减回退候选)...", flush=True)
    sub = await BrainModule.submit_multi_simulation(
        alpha_expressions=probes, region="USA", universe="TOP1000", delay=1,
        decay=6, neutralization="INDUSTRY", truncation=0.025,
        pasteurization="ON", unit_handling="VERIFY", nan_handling="ON",
        language="FASTEXPR", visualization=False)
    if "error" in sub:
        raise RuntimeError(f"探针提交失败: {sub}")
    print(f"[probe] location: {sub['location']}", flush=True)
    await asyncio.sleep(60)
    while True:
        chk = await BrainModule.check_multi_simulation(sub["location"])
        st = chk.get("status")
        print(f"[probe poll] status={st} progress={chk.get('progress', 0)}", flush=True)
        if st in ["COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"]:
            break
        await asyncio.sleep(20)
    fetch = await BrainModule.fetch_multi_simulation_result(sub["location"])
    results = fetch.get("alpha_results", [])
    out_path = os.path.join(CAMPAIGN, f"probe_exp_syntax_{int(time.time())}_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
    ok_exp = False
    for i, r in enumerate(results):
        m = r.get("metrics") or {}
        has_metrics = bool(m) and m.get("sharpe") is not None
        tag = "keyword_exp" if i == 0 else "linear_fallback"
        print(f"[probe] variant {i} ({tag}): metrics={'OK' if has_metrics else 'EMPTY'} status={r.get('status')} err={str(r.get('error'))[:80]}", flush=True)
        if i == 0 and has_metrics:
            ok_exp = True
    if ok_exp:
        print("[probe] 结论: ts_decay_exp_window 关键字写法可用 -> 槽2 用指数半衰期平滑", flush=True)
        return "keyword"
    print("[probe] 结论: 指数写法失败 -> 槽2 回退为 ts_decay_linear 线性衰减 (探针伙伴槽读数可直接复用)", flush=True)
    return "linear"


async def run_wave(prescriptions: list, wave_name: str, neutralization: str, known_fields: list):
    items = [{
        "expression": p["expression"],
        "optimize_reason": p["optimize_reason"],
        "seed_id": f"PHASE4_W{wave_name[-1]}_{p['id']}",
        "question_type": p["type"],
    } for p in prescriptions]
    batch = {
        "seed_id": f"SEED_OPT_{wave_name}",
        "seed_alpha": "ZYm1pn3n",
        "region": "USA", "universe": "TOP1000", "delay": 1, "category": "news",
        "known_fields": known_fields,
        "items": items,
    }
    batch_path = os.path.join(CAMPAIGN, f"batch_{wave_name}_{int(time.time())}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"[{wave_name}] 批次文件已写: {batch_path} (neutralization={neutralization})", flush=True)
    try:
        res = await SimBatchRunner.run_batch_silently(
            batch_file_path=batch_path, region="USA", universe="TOP1000", delay=1,
            category="news", neutralization=neutralization, decay=6, truncation=0.025)
        with open(batch_path.replace(".json", "_summary.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
        return res
    except Exception as e:
        purge_fingerprints([p["expression"] for p in prescriptions], neutralization)
        raise


async def main():
    with open(os.path.join(CAMPAIGN, "news12_fields_UNFILTERED.json"), encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    print(f"[Phase 4] 字段字典 {len(known_fields)} 个装载; 种子=ZYm1pn3n; 替代字段={V}", flush=True)

    # 0) mandate 事实核查复诵
    if "headline_positive_term_count_v2" in known_fields:
        print("[WARN] mandate 字段竟存在? 重新检查", flush=True)
    else:
        print("[FACT] headline_positive_term_count_v2 不在 news12 875 字段中 -> 采用替代字段 news_vol_stddev", flush=True)

    # 1) 探针
    syntax = await probe_exp_syntax(known_fields)
    prescriptions = build_prescriptions(syntax)
    assert len(prescriptions) == 8
    # 本地预演全部 8 条审计
    corrector = ASTSandboxCorrector()
    for p in prescriptions:
        fixed = corrector.correct_expression(p["expression"])
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category="news")
        print(f"  [pre-audit] slot{p['id']} ops={audit['operator_count']} valid={audit['is_valid']} {p['expression'][:80]}", flush=True)
        if not audit["is_valid"]:
            raise ValueError(f"slot{p['id']} 审计失败: {audit['issues']}")

    # 2) Wave 1: 表达式级处方 @ 种子同设置
    r1 = await run_wave(prescriptions, "wave1_expr_rx", "INDUSTRY", known_fields)
    print(f"[Wave 1] step1={r1.get('step1', {}).get('message') if isinstance(r1, dict) else r1}", flush=True)

    # 3) Wave 2: 中性化下沉配对消融
    r2 = await run_wave(prescriptions, "wave2_neut_ablation", WAVE2_NEUTRALIZATION, known_fields)
    print(f"[Wave 2] step1={r2.get('step1', {}).get('message') if isinstance(r2, dict) else r2}", flush=True)

    print("[Phase 4] 全部波次完成", flush=True)


asyncio.run(main())
