# -*- coding: utf-8 -*-
"""Gate1 Wave11-G · 多尺度背离 + 修正门 + 第三锚点 (USA/TOP1000/d1/INDUSTRY/decay=6).

=== 立项依据 (Wave11-F 回收 + 红队三审收敛) ===
Wave11-F 八个判决:
  A1 窗口120 = 250 窗平顶 (1.56=1.56) -> 窗口轴关闭
  R2 dflc(TON) 恒真退化 (与无门基线逐位相同) -> dflc 只对 vec_count(VHEX) 有效
  M1a 组层 -0.85 Sh 换 -35pp TO -> 机制1证伪
  CTRL 裸CVW核 Sh1.54 ≈ 双腿DUALP 1.56 -> VWAP腿是核心, TON腿仅+0.02Sh
  D1/D2 旧式门 L/S 578->732 + Sh 崩塌 -> 根因确诊: reverse(ts_rank) 值域[-1,0],
      trade_when else 分支 0 是值域极大值 -> 门外股票成统一伪腿
  D3 PE×SI 无边缘 (Sh-0.27/CW fail/DD35.6%) -> 慢引擎该构造证伪

=== 本批 8 条 = 三个新机制的首攻 ===
G1-G4  多尺度背离 DIV = ts_rank(快窗) - ts_rank(慢窗): 在同一 2-3 字段内提取二阶信息
        (新鲜度). DIV<0 = 新出现的弱势 (流动性冲击, 应反转); DIV>0 = 长期弱势
        (结构性抛售, 不赌反转). 这是「选择高 IC 子集」而非「平滑」的降噪路线,
        全库 417 行零先例 (subtract(ts_rank( 模式 0 次).
G5'    ts_rank(CVW_R,5) 短窗语义保险单: 快窗无历史事件时平台 ts_rank 的返回值
        语义未验证 (k=1 原子问题), 本槽直接分辨, 保护 G1-G4 的解释权.
G6/G7  修正门: subtract(0.5, ts_rank(...)) 中心化到 [-0.5,0.5] (0.5 = ts_rank
        结构中点, 非调参系数), 使 trade_when 的 else 分支 0 成为截面中性 ->
        门外股票真正平仓. 第一次干净读出 D 线 (便宜支撑/无知情空方) 的经济学问题.
G8     第三锚点: (EOC-VWAP)+(EOC-pre_vwap) 双基准偏离, 分离「新闻前价格发现」
        与「新闻后压力」. pre_vwap 全史零使用.

=== 红队三审预注册 ===
DIV 族预期 Sh 0.3-1.3 (去均值家族先例 1.14-1.30 < 水平版 1.44-1.56), 主判 G3;
守恒律打破claim已被定量驳回 (TO120% 需 Sh1.5 且 Ret9.2% > 家族天花板 9.07%),
本批是判决性实验非通关候选. G6/G7 的 TO 不会降 (105-125%), 买的是 IC 干净读数;
L/S 分支预登记: 每侧 130-170=门生效 / ~289=门空转 / >250=仍未修好;
关键观测量 = Sh 恢复度 (>=1.30 门架构成立 / <=0.60 且门生效则 D 线死亡).
"""
import asyncio
import json
import os
import sqlite3
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as BrainModule  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402

CAMPAIGN = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1")
FIELDS_FILE = os.path.join(CAMPAIGN, "news12_fields_full.json")
CATEGORY, REGION, DELAY = "news", "USA", 1
UNIVERSE, NEUT, DECAY = "TOP1000", "INDUSTRY", 6
TRUNCATION = 0.025
NAN_HANDLING = "ON"

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
PVWAP = "news_pre_vwap"
PE, SI = "news_pe_ratio", "news_short_interest"

CVW_R = f"divide(subtract({EOC}, {VWAP}), {VWAP})"
DUAL_R = f"divide(add(subtract({EOC}, {TON}), subtract({EOC}, {VWAP})), {VWAP})"
C250 = f"subtract(0.5, ts_rank({CVW_R}, 250))"   # 中心化的裸核信号 (else 分支中性)


def div(base, f, s):
    return f"subtract(ts_rank({base}, {f}), ts_rank({base}, {s}))"


SLOTS = [
    {
        "id": 1, "type": "G1_DIV_5_60", "role": "DIVERGENCE",
        "baseline": "裸核 CTRL Sh1.54/TO120.4%/Ret6.91%/2Y1.73; 全库 subtract(ts_rank( 模式 0 次",
        "expression": f"reverse(rank({div(CVW_R, 5, 60)}))",
        "optimize_reason": (
            "【多尺度背离 (5,60) · 最粗剂量 + k=1 金丝雀】DIV = 5 日分位 - 60 日分位. "
            "经济含义: DIV<0 = 当前弱势在近 5 日而言是极端但在两个月的尺度上并不极端 = "
            "新出现的卖压 = 流动性冲击, 应反转买入; DIV>0 = 弱势已持续两个月 = 结构性抛售, "
            "不赌反转. 这是在同一 2 字段内提取二阶信息 (新鲜度) 的路线, 与所有已证伪的"
            "「平滑/冻结/门控」有本质区别: 那些丢信息, 这个选子集. 红队三审指出 5 日快窗在"
            "~0.578/名/日的事件率下仅约 2.9 个有效观测, 量化严重, 且快窗无历史事件时 ts_rank "
            "的返回值语义未验证 (k=1 原子) —— 本槽同时是该语义的金丝雀: 若 ts_rank(x,5) 病态, "
            "G1 会给出异常读数 (Sh<0 或极端 L/S), 提醒全批 DIV 解释需谨慎. "
            "成功标准: 建立 DIV 家族最粗剂量点 (预期 Sh 0.3-0.8); 金丝雀价值 > 经济学价值."),
    },
    {
        "id": 2, "type": "G2_DIV_10_120", "role": "DIVERGENCE",
        "baseline": "同 G1; 10 日窗约 5.8 个有效观测",
        "expression": f"reverse(rank({div(CVW_R, 10, 120)}))",
        "optimize_reason": (
            "【多尺度背离 (10,120) · 中档剂量】DIV = 10 日分位 - 120 日分位 (约两周 vs 半年). "
            "红队三审: 该剂量下快腿量化减半、k=1 原子可忽略, 是阶梯中的稳健点. "
            "经济含义同 G1: 只买入「近两周新出现、但半年尺度上并不极端」的卖压. "
            "120 日慢窗恰好是 A1 批实证的 Sh 峰窗口 (vwap-only 核 120 窗 1.56 > 250 窗 1.50), "
            "使慢腿本身处于信息最丰富的尺度. 成功标准: Sh >= 0.60 (中档可用); "
            "若 G1/G2/G3 呈单调剂量-反应, 取内部最优窗口作为后续精扫中心."),
    },
    {
        "id": 3, "type": "G3_DIV_20_250", "role": "DIVERGENCE",
        "baseline": "同 G1; 20 日窗约 11.6 个有效观测",
        "expression": f"reverse(rank({div(CVW_R, 20, 250)}))",
        "optimize_reason": (
            "【多尺度背离 (20,250) · 主判槽】DIV = 20 日分位 - 250 日分位 (约一个月 vs 一年). "
            "红队三审指定为全家族唯一量化最轻的干净测试: 快窗 11.6 个有效观测足以分辨分位, "
            "k=1 原子概率可忽略, 事件密度混淆最弱. 经济学: 新闻驱动的日内卖压若在一个月内"
            "是新鲜的、但放到一年尺度并不异常, 则它是可反转的流动性冲击; 若一年尺度同样极端, "
            "则是持续的知情抛售 (例如机构系统性减持), 反转假设不成立. 该条件化若成立, "
            "意味着家族 alpha 的适用边界可以被二阶信息收窄, 是 IC 密度的直接提升. "
            "成功标准: Sh >= 1.30 (机制成立, 值得精扫窗口与门控组合); "
            "证伪线: Sh <= 0.70 (二阶提取方向关闭, 与去均值家族先例 1.14-1.30 的下沿一致)."),
    },
    {
        "id": 4, "type": "G4_DUALP_DIV_20_250", "role": "DIVERGENCE",
        "baseline": "双腿 DUALP_TSRANK250 Sh1.56/2Y2.23 vs 裸CVW 1.54/2Y1.73",
        "expression": f"reverse(rank({div(DUAL_R, 20, 250)}))",
        "optimize_reason": (
            "【双腿核的多尺度背离 (20,250)】把 DIV 机制搬到双腿 DUALP 内核. Wave11-F 实证 "
            "TON 腿在水平版上贡献小 (+0.02 Sh) 但在 2Y 上贡献大 (+0.50: 2.23 vs 1.73), "
            "本槽检验该 2Y 优势在二阶 (背离) 版本下是否存活: 若 G4 的 2Y 显著高于 G3, "
            "说明 TON 腿 (新闻时刻价锚) 的价值在于时间稳定性而非即期收益, 后续全部背离构造"
            "都应预置双腿核. 合规注记: 13 ops, 援 9qEeNN3K (14 ops 正常运行) 先例, "
            "用户 mandate 不限 op. 成功标准: Sh >= G3 + 0.05 且 2Y >= 2.0."),
    },
    {
        "id": 5, "type": "G5_TSRANK5_PROBE", "role": "SEMANTIC_PROBE",
        "baseline": "全库 ts_rank(x,5) 零使用; CTRL (250窗) Sh1.54",
        "expression": f"reverse(rank(ts_rank({CVW_R}, 5)))",
        "optimize_reason": (
            "【短窗 ts_rank 语义保险单】reverse(rank(ts_rank(CVW_R,5))) —— 当前压力在近 5 日"
            "内的分位, 再过横截面 rank. 红队三审指定替换原 G5 (plain-rank 裸核被 CTRL 1.54 与 "
            "zqrxxbEG 1.44 夹死, 是已知量): 本槽是 G1-G4 整个 DIV 批的解释保险 —— DIV 的快腿"
            "全部依赖短窗 ts_rank, 而「快窗内有效观测不足时平台 ts_rank 返回什么」在全库 417 行"
            "从未被探测. 若本槽读数健康 (Sh 1.2-1.5, L/S ~289), 证明短窗 ts_rank 语义健全, "
            "G1-G4 的读数可放心解释; 若病态 (Sh<0.3 或 L/S 异常), 则 G1 (5 日快窗) 的读数须"
            "按语义污染折价. 附带价值: 5 日极端度本身是「最新鲜的极端」信号, 有独立经济含义. "
            "成功标准: 语义判决 (健康/病态) + Sh >= 1.20."),
    },
    {
        "id": 6, "type": "G6_PE_GATE_CENTERED", "role": "SLOW_FAST",
        "baseline": "旧式门 (未中心化) Sh0.48/L/S365-367 (伪腿污染); 裸核 CTRL Sh1.54/L/S289-289",
        "expression": f"trade_when(less(rank({PE}), 0.5), {C250}, 0)",
        "optimize_reason": (
            "【修正 PE 便宜门 · D 线第一次干净读数】只对横截面最便宜的一半股票执行 CVW 流动性"
            "反转. 与 Wave11-F 旧式门的唯一区别: 信号中心化 —— subtract(0.5, ts_rank) 把值域从"
            " [-1,0] 平移到 [-0.5,0.5], 使 trade_when 的 else 分支 0 成为截面中性 (ts_rank 输出"
            "近似均匀 -> 截面均值≈0), 门外股票真正平仓而非沦为统一伪腿 (旧式门 L/S 578->732 即"
            "伪腿症状). 经济学: 低估值 = 下行有基本面支撑, 被流动性冲击压低的收盘价反转更强; "
            "贵股票的抛售可能是重定价的开始. 红队三审确认修正正确, 但预期 TO 不降 (105-125%) —— "
            "本槽买的是 IC 干净读数不是 TO 豁免. L/S 预登记: 每侧 130-170=门生效; ~289=门空转; "
            ">250=仍未修好. 关键观测量 = Sh 恢复度: >=1.30 门架构成立; 门生效但 Sh<=0.60 则"
            "「便宜支撑」假说死亡. CW 风险 20-30% (半场书单名权重翻倍)."),
    },
    {
        "id": 7, "type": "G7_SI_GATE_CENTERED", "role": "SLOW_FAST",
        "baseline": "旧式门 Sh0.28/L/S349-344; 裸核 CTRL Sh1.54",
        "expression": f"trade_when(less(rank({SI}), 0.5), {C250}, 0)",
        "optimize_reason": (
            "【修正 SI 低空头门 · 信息与流动性的分离】只对空头兴趣最低的一半股票执行 CVW 流动性"
            "反转. 经济学: SI = 卖空股数/流通股数, 高空头意味着持续的知情空方; 高 SI 股票的"
            "新闻日走弱更可能是真实负面信息而非可反转的流动性冲击, 低 SI 股票的卖压则更接近"
            "无信息流动 —— 这是战役「提供流动性赚反转」主叙事最直接的边界条件检验. 与 G6 同为"
            "中心化修正门 (else 分支 0 = 截面中性), 共享 L/S 分支预登记与 Sh 恢复度判据. "
            "历史先例注意: SI 高档门曾把 sub-universe 打到 0.02 (LOW_SUB fail), 低档门零测试; "
            "本槽须同时监 sub. 成功标准: Sh >= 1.30 且 sub >= 0.50 (低 SI 侧既不崩 Sh 也不崩 sub)."),
    },
    {
        "id": 8, "type": "G8_PRE_VWAP_ANCHOR", "role": "ANCHOR",
        "baseline": "pre_vwap 全史零使用; CVW 单锚 Sh1.54; post_vwap 锚族 2Y 2.08-2.14",
        "expression": (
            f"reverse(rank(divide(add(subtract({EOC}, {VWAP}), subtract({EOC}, {PVWAP})), {VWAP})))"),
        "optimize_reason": (
            "【第三锚点 · 盘前 VWAP 双基准偏离】(收盘-新闻后VWAP) + (收盘-盘前VWAP), 以 VWAP 归一. "
            "经济含义: 把收盘价的偏离同时度量于两个均衡点 —— 新闻时刻到收盘的成交量加权均价"
            " (度量新闻后资金流的成本) 与盘前会话的成交量加权均价 (度量新闻前已存在的价格发现). "
            "二者之和 = 全日总位移中「可归因于新闻后压力」与「延续自盘前发现」的合成. 红队三审: "
            "该式约 70% 是跳空反转 (pre_vwap vs close 的隔夜部分) + 30% VWAP 反转, 跳空成分享"
            "零先例但 post_vwap 锚点族的 2Y 2.08-2.14 支撑「第三锚点抬时间稳定性」的假设. "
            "pre_vwap cov 0.8289 (四价格字段最低) 已登记: 若名数明显下降按稀疏分支解读. "
            "成功标准: Sh >= 1.50 (第三锚点不弱于单锚) 且 2Y >= 1.90 (稳定性增益); "
            "CW 风险 25-35% (双锚乘积放大极端名)."),
    },
]

DIRECTIONS = {
    "G": {"name": "多尺度背离 + 修正门 + 第三锚点 (8 条)",
          "hypothesis": (
              "Wave11-F 八判决后的机制首攻: DIV 家族 (同字段二阶信息提取, 新鲜度条件化反转, "
              "全库零先例) 带短窗语义保险单; 中心化修正门第一次干净读出 D 线经济学; "
              "pre_vwap 第三锚点首测."),
          "universe": UNIVERSE, "neutralization": NEUT, "slots": SLOTS},
}


def purge_fingerprints(exprs, neutralization, universe):
    corrector = ASTSandboxCorrector()
    conn = sqlite3.connect(corrector.db_path)
    cur = conn.cursor()
    n = 0
    for e in exprs:
        h = corrector.compute_fingerprint(corrector.correct_expression(e), REGION, universe, DELAY, neutralization)
        cur.execute("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[fingerprint purge] removed {n}", flush=True)


def preaudit(items, known_fields):
    corrector = ASTSandboxCorrector()
    known_set = set(known_fields)
    ops = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
           "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
           "ts_delta", "ts_decay_linear", "ts_decay_exp_window", "trade_when", "greater", "less",
           "if_else", "vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev",
           "days_from_last_change", "industry", "subindustry", "sector", "market",
           "sign", "abs", "sqrt", "log", "power", "winsorize", "zscore",
           "std", "factor", "period", "window"}
    for it in items:
        fixed = corrector.correct_expression(it["expression"])
        it["expression"] = fixed
        audit = DimensionAuditor.audit_expression(fixed, known_fields, category=CATEGORY)
        tokens = set(audit["tokens_found"])
        nf = len(tokens & known_set)
        unknown = {t for t in tokens if t not in known_set and t not in ops and not t.isdigit()}
        print(f"  [pre-audit] slot{it['id']} ops={audit['operator_count']:>2} fields={nf} "
              f"len={len(fixed):>3} {'OK' if audit['is_valid'] else 'FAIL'} | {fixed[:70]}", flush=True)
        if unknown:
            raise ValueError(f"slot{it['id']} 未知标识符: {unknown}")
        if not audit["is_valid"]:
            raise ValueError(f"slot{it['id']} 本地审计失败: {audit['issues']}")
        if not (2 <= nf <= 3):
            raise ValueError(f"slot{it['id']} 字段数 {nf} 违反 mandate (2<=字段数<=3)")
        if len(fixed) > 900:
            raise ValueError(f"slot{it['id']} 超长 {len(fixed)} > 900")
        if len(it["optimize_reason"]) < 120:
            raise ValueError(f"slot{it['id']} optimize_reason 过短, 违反铁律5")


async def main():
    raw = json.load(open(FIELDS_FILE, encoding="utf-8"))
    fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
    known_fields = [x["id"] for x in fields]
    d = DIRECTIONS["G"]
    print(f"[Wave11-G] 字段字典 {len(known_fields)} | {UNIVERSE}/{NEUT}/decay={DECAY}", flush=True)

    items = [{"id": s["id"], "baseline": s["baseline"], "expression": s["expression"],
              "optimize_reason": s["optimize_reason"], "seed_id": f"GATE1W11G_{s['id']}",
              "question_type": s["type"]} for s in d["slots"]]
    assert len(items) == 8
    print(f"\n[Wave11-G] {d['name']}", flush=True)
    preaudit(items, known_fields)
    purge_fingerprints([it["expression"] for it in items], d["neutralization"], d["universe"])

    ts = int(time.time())
    json.dump({"seed_id": "GATE1W11G", "region": REGION, "universe": d["universe"], "delay": DELAY,
               "decay": DECAY, "neutralization": d["neutralization"], "category": CATEGORY,
               "known_fields": known_fields, "items": items},
              open(os.path.join(CAMPAIGN, f"batch_w11g_{ts}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    loc = None
    for attempt in range(1, 6):
        try:
            sub = await BrainModule.submit_multi_simulation(
                alpha_expressions=[it["expression"] for it in items], region=REGION,
                universe=d["universe"], delay=DELAY, decay=DECAY,
                neutralization=d["neutralization"], truncation=TRUNCATION,
                pasteurization="ON", unit_handling="VERIFY", nan_handling=NAN_HANDLING,
                language="FASTEXPR", visualization=False)
            if "error" in sub:
                raise RuntimeError(str(sub)[:160])
            loc = sub["location"]
            print(f"[submit-G] OK attempt={attempt} location={loc}", flush=True)
            break
        except Exception as e:
            print(f"[submit-G] attempt {attempt}: {str(e)[:180]}", flush=True)
            if attempt == 5:
                raise
            await asyncio.sleep(30)
    if not loc:
        return

    print("[Wave11-G] 静默轮询中 (前 60s 不输出)...", flush=True)
    waited = 0
    while True:
        try:
            chk = await BrainModule.check_multi_simulation(loc)
            st = chk.get("status")
            if waited >= 60:
                print(f"  [poll] {st} t={waited}s", flush=True)
            if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                break
        except Exception as e:
            print(f"  [poll] error: {str(e)[:150]}", flush=True)
        await asyncio.sleep(20)
        waited += 20

    results = (await BrainModule.fetch_multi_simulation_result(loc)).get("alpha_results", [])
    if not results:
        print("[Wave11-G] fetch 空", flush=True)
        return
    json.dump({"alpha_results": results},
              open(os.path.join(CAMPAIGN, f"batch_w11g_{ts}_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n===== Wave11-G ({UNIVERSE}/{NEUT}/decay={DECAY}) =====", flush=True)
    print(f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} "
          f"{'sub':>5} {'rn':>5} {'L/S':>11} {'DD%':>6} {'CW':>5} {'CL':>5} {'MT':>4}", flush=True)
    for it, r in zip(items, results):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        cw = "FAIL" if "CONCENTRATED_WEIGHT" in names else "ok"
        cl = next((c.get("value") for c in (ch.get("warning") or [])
                   if isinstance(c, dict) and c.get("name") == "CLUSTER_TEST"), None)
        mt = "W" if "MATCHES_THEMES" in [c.get("name") if isinstance(c, dict) else c
                                          for c in (ch.get("warning") or [])] else "-"
        print(f"{it['id']:>2} {m.get('sharpe') or 0:>6.2f} {m.get('fitness') or 0:>5.2f} {to * 100:>7.1f} "
              f"{ret * 100:>7.2f} {(ret / to) if to else 0:>7.3f} {(m.get('margin') or 0) * 1e4:>7.2f} "
              f"{m.get('two_year_sharpe') or 0:>6.2f} {m.get('sub_universe_sharpe') or 0:>5.2f} "
              f"{m.get('risk_neutralized_sharpe') or 0:>5.2f} "
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>11} "
              f"{(m.get('drawdown') or 0) * 100:>6.1f} {cw:>5} "
              f"{('%.2f' % cl) if cl is not None else '  - ':>5} {mt:>4}", flush=True)
        f = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        if f:
            print(f"      FAIL: {f}", flush=True)
        if w:
            print(f"      WARN: {w}", flush=True)
    print("\n[Wave11-G] 批次回收完毕。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
