# -*- coding: utf-8 -*-
"""
phase15_rKR_nws94.py — 种子 rKR1qVWo 换核工程 · Phase 1 (Batch: rKR_NWS94MIX)
================================================================================
【核心情报注入】2026-10-26 破除信息盲区:
  · mean_sentiment_score_transfer 单因子平台实测夏普仅 0.38 (种子败笔根源)；
  · 同族 max_primary_sentiment_score_transfer (第一信源峰值, 覆盖100%, alphaCount=1
    零拥挤) 单因子夏普高达 1.95, 100% 适配 STATISTICAL 中性化；
  · 辅助变动源: skew_primary 0.69 (ac=1), min_primary 0.52 (ac=1)。
【旧判决冲突】本地 RKR1QVWO_OPTIMIZATION_REPORT 曾判 news84 情绪族结构性天花板 1.56
  (只测过 mean/median 族)；本批以平台真实回测对 max_primary 一线裁决。
【裁决基准】种子 rKR1qVWo: Sh 1.54 / Fit 0.78, 2 hard FAIL (LOW_SHARPE, LOW_FITNESS)。
【8 槽设计】4 探索 (S2 复刻 / S3 裸字段 / S5 偏度门控 / S6 到达脉冲 / S8 zscore)
  + 4 演进 (S1 种子换核 / S4 偏离腿 / S7 floor 腿) — 见 batch_rKR_nws94.json。
承诺: STRICT NON-SUBMISSION — 只回测裁决，不提交。
用法:
  python phase15_rKR_nws94.py --dry   # 仅走 Gate 0-5 前置门禁, 不发包
  python phase15_rKR_nws94.py         # 全流程静默回测 (Gate 4/5 自动记账)
================================================================================
"""

import asyncio
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

from quant_framework.core.sim_runner import SimBatchRunner

CAMPAIGN = os.path.dirname(os.path.abspath(__file__))
BATCH_FILE = os.path.join(CAMPAIGN, "batch_rKR_nws94.json")

REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1
DECAY = 22
NEUTRALIZATION = "STATISTICAL"
TRUNCATION = 0.025
NAN_HANDLING = "ON"
CATEGORY = "news"


def print_summary_table():
    """Gatekeeper 之外的平台级全维度裁决表 (fail/warn + 8 项实测指标)。"""
    result_path = BATCH_FILE.replace(".json", "_result.json")
    with open(BATCH_FILE, encoding="utf-8") as f:
        batch = json.load(f)
    items = batch["items"]
    if not os.path.exists(result_path):
        print(f"[dry-run 模式] 无回测结果文件可打印: {result_path}")
        return
    with open(result_path, encoding="utf-8") as f:
        results = json.load(f).get("alpha_results", [])

    print("\n" + "=" * 132)
    print(f"{'Slot':<4}|{'AlphaID':<9}|{'Type':<26}|{'Sh':>6}|{'Fit':>6}|{'TO%':>7}|{'Ret%':>6}|"
          f"{'Mgn':>7}|{'2Y':>6}|{'Sub':>6}|{'L/S':>10}|{'CL':>5}| 判定 (平台检查)")
    print("-" * 132)
    passed = 0
    for i, it in enumerate(items):
        r = results[i] if i < len(results) else {}
        m = r.get("metrics", {}) or {}
        ck = r.get("checks", {}) or {}
        fails = [f.get("name") if isinstance(f, dict) else f for f in (ck.get("fail") or [])]
        warns = [w.get("name") if isinstance(w, dict) else w for w in (ck.get("warning") or [])]
        cl = next((w.get("value") for w in (ck.get("warning") or [])
                   if isinstance(w, dict) and w.get("name") == "CLUSTER_TEST"), None)
        if not fails and not warns and r:
            passed += 1
            tag = "🏆 0FAIL / 0WARN"
        elif not r:
            tag = "EMPTY:"
        elif fails:
            tag = "FAIL:" + ",".join(fails)
        else:
            tag = "WARN:" + ",".join(warns)
        print(f"{it['id']:>4}|{str(r.get('alpha_id') or r.get('id') or '-'):<9}|{it['type']:<26}|"
              f"{m.get('sharpe', 0):>6.2f}|{m.get('fitness', 0):>6.2f}|{m.get('turnover', 0) * 100:>6.1f}%|"
              f"{m.get('returns', 0) * 100:>5.2f}%|{m.get('margin', 0) * 10000:>6.1f}b|"
              f"{m.get('two_year_sharpe', 0):>6.2f}|{m.get('sub_universe_sharpe', 0):>6.2f}|"
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10}|"
              f"{(f'{cl:.2f}' if cl else '-'):>5}| {tag}")
    print("=" * 132)
    print(f"\n🏆 平台级 0 FAIL + 0 WARN: {passed} / {len(items)}")


async def main():
    dry = "--dry" in sys.argv
    print("=" * 118)
    print("🚀 种子 rKR1qVWo 换核工程 · Phase 1 Batch rKR_NWS94MIX" + (" 【DRY-RUN 仅门禁核验】" if dry else ""))
    print(f"   Region {REGION} | Universe {UNIVERSE} | Delay {DELAY} | Decay {DECAY} | "
          f"Neut {NEUTRALIZATION} | Trunc {TRUNCATION} | 承诺 STRICT NON-SUBMISSION")
    print("=" * 118)

    if dry:
        with open(BATCH_FILE, encoding="utf-8") as f:
            batch = json.load(f)
        items = batch["items"]
        known_fields = batch["known_fields"]
        # 验证红队通行证是否可以现场签发 (写入 batch_rKR_maxprim_red_team.json)
        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=BATCH_FILE,
            expressions_data=items,
            known_fields=known_fields,
            category=CATEGORY,
            region=REGION,
            universe=UNIVERSE,
            delay=DELAY,
            neutralization=NEUTRALIZATION,
        )
        print("\n✅ DRY-RUN 通过: Gate 0 (8槽满载) + Gate 1 (红队通行证) + Gate 5 (Tabu) + "
              "Gate 3 (骨架去重) + Gate 2 (AST 量纲) 全部就绪。")
        for idx, e in enumerate(corrected, 1):
            print(f"   S{idx} (post-correct): {e[:100]}{'...' if len(e) > 100 else ''}")
        return

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

    print("\n" + "=" * 118)
    print("【AEGIS Gatekeeper 内核先行裁决】")
    if isinstance(res, dict):
        if res.get("step1"):
            print(f"  Step 1 (|Sh|>=1.0 熔断): {res['step1'].get('message', res['step1'])}")
        print(f"  Step 2 合规通过数: {len(res.get('step2_passed', []))}")
        print(f"  终极生产准入: {len(res.get('final_passed', []))}")
        if res.get("prescriptions"):
            print(f"  Gate 4 处方白名单: {json.dumps(res['prescriptions'], ensure_ascii=False)[:400]}")

    print_summary_table()


if __name__ == "__main__":
    asyncio.run(main())
