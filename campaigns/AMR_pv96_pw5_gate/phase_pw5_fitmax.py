# -*- coding: utf-8 -*-
"""
phase_pw5_fitmax.py — 种子 pw5GzEeX Fitness 前沿攻坚 · Phase 1 (Batch: PW5FITMAX)
================================================================================
【病灶】pw5GzEeX: Sh 13.92 / Fit 17.94 (全场最高) 但 CONCENTRATED_WEIGHT 0.50>0.10、
  LOW_2Y_SHARPE 0.00<1.58、sub_universe_sharpe ERROR —— "不可投资的 fitness 海市蜃楼"。
【根因】pv96_acquisition_status 覆盖率 0.5，120 日差分大多为 0 → 点状孤注集中在单票；
  2022-2023 并购枯竭 → 近两年信号昏迷。
【8 槽设计】4 演进 (S1 散点化 / S2 backfill 存活窗 / S3 事件×载体双腿融合 / S4 短窗新鲜度)
  + 4 探索 (S5 裸载体方向探针 / S6 备用事件腿 / S7 zscore 包裹 / S8 长记忆 rank 窗)。
承诺: STRICT NON-SUBMISSION — 只回测裁决，不提交。
【注意】本轮不做会写指纹库的 dry-run（后果见 rKR_MAXPRIM 波次教训: verify 阶段
  check_and_record_batch 先插入指纹导致正式发包被自碰撞驳回）；
  预审仅用 DimensionAuditor + 骨架计数（不落库）。
================================================================================
"""

import asyncio
import re
import json
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.sim_runner import SimBatchRunner

CAMPAIGN = os.path.dirname(os.path.abspath(__file__))
BATCH_FILE = os.path.join(CAMPAIGN, "batch_pw5_fitmax.json")

REGION = "AMR"
UNIVERSE = "TOP600"
DELAY = 1
DECAY = 4
NEUTRALIZATION = "SUBINDUSTRY"
TRUNCATION = 0.08
NAN_HANDLING = "ON"
CATEGORY = "pv"


def local_precise_audit():
    """预审 (不写指纹库): 逐条 DimensionAuditor + 批内骨架统计, 上限同拓扑 <= 2。"""
    with open(BATCH_FILE, encoding="utf-8") as f:
        batch = json.load(f)
    items = batch["items"]
    known = batch["known_fields"]
    corrector = ASTSandboxCorrector
    skeleton_count = {}
    ok = True
    print("\n[Step 1/5] Local non-inscribing audit...")
    for it in items:
        expr = it["expression"]
        res = DimensionAuditor.audit_expression(expr, known, category=CATEGORY)
        parens = expr.count("(")
        label = "OK" if res["is_valid"] and parens <= 8 else "VIOLATION: " + ";".join(res["issues"])
        if label != "OK":
            ok = False
        print(f"  Slot {it['id']:>2} ({it['type']:<22}): ops={res['operator_count']} parens={parens} fields={res['used_fields']} -> {label}")
        skel = corrector.get_canonical_skeleton(expr)
        skeleton_count.setdefault(skel, []).append(it["id"])
    for i, (sk, ids) in enumerate(skeleton_count.items(), 1):
        tag = "OK" if len(ids) <= 2 else "OVER-2 VIOLATION"
        if len(ids) > 2:
            ok = False
        print(f"  Skeleton {i}: {sk[:80]}{'...' if len(sk) > 80 else ''} slots={ids} -> {tag}")
    if not ok:
        raise ValueError("本地预审未通过, 严禁发包!")
    print("  ✅ 本地预审通过 (8 槽满载 / 算子-括号合规 / 骨架 <= 2 / 0 PV 污染)。")


def print_summary_table():
    result_path = BATCH_FILE.replace(".json", "_result.json")
    with open(BATCH_FILE, encoding="utf-8") as f:
        batch = json.load(f)
    items = batch["items"]
    if not os.path.exists(result_path):
        print("[无结果文件] 抽样: 门禁阶段被拦截, 见日志。")
        return
    with open(result_path, encoding="utf-8") as f:
        results = json.load(f).get("alpha_results", [])

    print("\n" + "=" * 134)
    print(f"{'Slot':<4}|{'AlphaID':<9}|{'Type':<22}|{'Sh':>6}|{'Fit':>6}|{'TO%':>7}|{'Ret%':>6}|"
          f"{'Mgn':>7}|{'2Y':>6}|{'Sub':>6}|{'L/S':>12}| 判定 (平台检查)")
    print("-" * 134)
    passed, best_fit = 0, (None, 0.0)
    for i, it in enumerate(items):
        r = results[i] if i < len(results) else {}
        m = r.get("metrics", {}) or {}
        ck = r.get("checks", {}) or {}
        fails = [x.get("name") if isinstance(x, dict) else x for x in (ck.get("fail") or [])]
        warns = [x.get("name") if isinstance(x, dict) else x for x in (ck.get("warning") or [])]
        if r and not fails and not warns:
            passed += 1
            tag = "🏆 0FAIL / 0WARN"
        elif not r:
            tag = "EMPTY"
        elif fails:
            tag = "FAIL:" + ",".join(fails)
        else:
            tag = "WARN:" + ",".join(warns)
        fid = m.get("fitness", 0.0)
        if fid > best_fit[1]:
            best_fit = (it["id"], fid)
        print(f"{it['id']:>4}|{str(r.get('alpha_id') or r.get('id') or '-'):<9}|{it['type']:<22}|"
              f"{m.get('sharpe', 0):>6.2f}|{fid:>6.2f}|{m.get('turnover', 0) * 100:>6.1f}%|"
              f"{m.get('returns', 0) * 100:>5.2f}%|{m.get('margin', 0) * 10000:>6.1f}b|"
              f"{m.get('two_year_sharpe', 0):>6.2f}|{m.get('sub_universe_sharpe', 0):>6.2f}|"
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>12}| {tag}")
    print("=" * 134)
    print(f"\n🏆 平台级 0 FAIL + 0 WARN: {passed} / {len(items)}  |  Fitness 最高: Slot {best_fit[0]} = {best_fit[1]:.2f}")


async def main():
    print("=" * 118)
    print("🚀 种子 pw5GzEeX Fitness 前沿攻坚 · Batch PW5FITMAX")
    print(f"   Region {REGION} | Universe {UNIVERSE} | Delay {DELAY} | Decay {DECAY} | "
          f"Neut {NEUTRALIZATION} | Trunc {TRUNCATION} | 承诺 STRICT NON-SUBMISSION")
    print("=" * 118)

    local_precise_audit()

    print("\n[Step 2/5] Submitting 8-Slot Multi-Simulation via SimBatchRunner (含 Gate 0-3 现场核验)...")
    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=BATCH_FILE,
        region=REGION,
        universe=UNIVERSE,
        delay=DELAY,
        category=CATEGORY,
        neutralization=NEUTRALIZATION,
        decay=DECAY,
        truncation=TRUNCATION,
        nan_handling=NAN_HANDLING,
    )

    print("\n[Step 3/5] AEGIS Gatekeeper 内核先行裁决:")
    if isinstance(res, dict):
        if res.get("step1"):
            print(f"  Step 1 (|Sh|>=1.0 熔断): {res['step1'].get('message', res['step1'])}")
        print(f"  Step 2 合规通过数: {len(res.get('step2_passed', []))}")
        print(f"  终极生产准入: {len(res.get('final_passed', []))}")

    print("\n[Step 4/5] 平台级全维度裁决表:")
    print_summary_table()


if __name__ == "__main__":
    asyncio.run(main())
