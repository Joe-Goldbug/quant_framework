# -*- coding: utf-8 -*-
"""
phase18_rKR_b63.py — 种子 rKR1qVWo 优化竣工冲刺 · Phase 18 (Batch: rKR_B63, 第 63 批)
================================================================================
【核心锚点情报】 B62 判决穿透 (trunc 0.08 批, 全批证伪负结果优势):
  - trunc 0.09 轴判决性证伪 (S7 1.36/2Y 0.93 vs 种子 1.54/2.10), 永久回设 trunc 0.025。
  - 瘦核三段式证伪: S1-S4 全灭 (0.77~1.26) + Sub 塌方 -> power 凸性壳是承载层。
  - ts_target_tvr_decay 可用性通过 (TO 7.5%/Mgn 9.2b 家族史峰), 需 trunc .025 清 CW。
  - exp vs linear 外推 2Y 抢救失败 (1.51 vs 1.53): 外层平滑类本身消耗 2Y。
  - Tabu 强制换核: mean:prob10d 对连续 3 批零达标被物理锁定。
【本批设计轴】 换核令执行 + trunc 0.025 回归: 探索 5 个未测字段对 (mean:p20d /
  mean:rel / maxprim:p10d / maxprim:p20d / maxprim:skew) + 武器迁移 (tvr / trade_when 事件锁)。
【架构承诺】 零代码改动 (仅 batch JSON + phase runner 样板), STRICT NON-SUBMISSION。
用法:
  python phase18_rKR_b63.py --dry   # 仅门禁凭据预检 (Gate 0~5, 不发外包)
  python phase18_rKR_b63.py         # 全流程静默回测 (前 60s 静默, 之后 20s 静默轮询)
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
BATCH_FILE = os.path.join(CAMPAIGN, "batch_rKR_b63.json")

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

    print("\n" + "=" * 140)
    print(f"{'Slot':<4}|{'AlphaID':<9}|{'Type':<36}|{'Sh':>6}|{'Fit':>6}|{'TO%':>7}|{'Ret%':>6}|"
          f"{'Mgn':>7}|{'2Y':>6}|{'Sub':>6}|{'L/S':>10}|{'CL':>5}| 判定 (平台检查)")
    print("-" * 140)
    print(f"{'SEED':>4}|{'rKR1qVWo':<9}|{'种子本体 (mean:p10d 对)':<36}|{1.54:>6.2f}|{0.78:>6.2f}|{16.79:>6.1f}%|{4.28:>5.2f}%|{5.10:>6.1f}b|{2.10:>6.2f}|{1.07:>6.2f}|{'439/596':>10}|{1.24:>5}| LOW_SHARPE+LOW_FITNESS (对已 Tabu)")
    print(f"{'B61S2':>4}|{'wpQKzYWQ':<9}|{'B壳双层平滑 (mean:p10d)':<36}|{1.48:>6.2f}|{0.85:>6.2f}|{11.51:>6.1f}%|{4.14:>5.2f}%|{7.18:>6.1f}b|{1.53:>6.2f}|{1.03:>6.2f}|{'439/596':>10}|{1.20:>5}| 3fail(Sh/Fit/LADDER)")
    print("-" * 140)
    verdicts = {}
    for i, it in enumerate(items):
        r = results[i] if i < len(results) else {}
        m = r.get("metrics", {}) or {}
        ck = r.get("checks", {}) or {}
        fails = [f.get("name") if isinstance(f, dict) else f for f in (ck.get("fail") or [])]
        warns = [w.get("name") if isinstance(w, dict) else w for w in (ck.get("warning") or [])]
        cl = next((w.get("value") for w in (ck.get("warning") or [])
                   if isinstance(w, dict) and w.get("name") == "CLUSTER_TEST"), None)
        if not fails and not warns and r:
            tag = "🏆 0FAIL / 0WARN"
        elif not r:
            tag = "EMPTY/CANCELLED"
        elif fails:
            tag = "FAIL:" + ",".join(fails)
        else:
            tag = "WARN:" + ",".join(warns)
        sh = m.get('sharpe', 0)
        fit = m.get('fitness', 0)
        to = m.get('turnover', 0) * 100
        ret = m.get('returns', 0) * 100
        verdicts[it["id"]] = {
            "sh": round(sh, 2), "fit": round(fit, 2), "to": round(to, 2), "ret": round(ret, 2),
            "fail": fails, "warn": warns, "alpha_id": r.get("alpha_id") or r.get("id")
        }
        print(f"{it['id']:>4}|{str(r.get('alpha_id') or r.get('id') or '-'):<9}|{it['type']:<36}|"
              f"{sh:>6.2f}|{fit:>6.2f}|{to:>6.1f}%|{ret:>5.2f}%|{m.get('margin', 0) * 10000:>6.1f}b|"
              f"{m.get('two_year_sharpe', 0):>6.2f}|{m.get('sub_universe_sharpe', 0):>6.2f}|"
              f"{str(m.get('longCount')) + '/' + str(m.get('shortCount')):>10}|"
              f"{(f'{cl:.2f}' if cl else '-'):>5}| {tag}")
    print("=" * 140)

    # 本地裁决存档 (供 next-batch 继承)
    verdict_file = os.path.join(CAMPAIGN, "verdict_rKR_B63.json")
    with open(verdict_file, "w", encoding="utf-8") as f:
        json.dump({"batch": "rKR_B63", "seed": "rKR1qVWo", "slot_metrics": verdicts,
                   "generated_at": int(time.time())}, f, ensure_ascii=False, indent=2)
    print(f"\n💾 本地裁决存档: {verdict_file}")


async def main():
    dry = "--dry" in sys.argv
    print("=" * 118)
    print("🚀 Phase 18 · Batch rKR_B63 — Tabu 强制换核执行批 + trunc 0.025 回归"
          + (" 【DRY-RUN 门禁凭据】" if dry else ""))
    print(f"   Region {REGION} | Universe {UNIVERSE} | Delay {DELAY} | Decay {DECAY} | "
          f"Neut {NEUTRALIZATION} | Trunc {TRUNCATION} | 承诺 STRICT NON-SUBMISSION")
    print("=" * 118)

    if dry:
        with open(BATCH_FILE, encoding="utf-8") as f:
            batch = json.load(f)
        items = batch["items"]
        known_fields = batch["known_fields"]
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
              "Gate 3 (骨架去重) + Gate 2 (AST 量纲·11算子上限) 全部就绪。")
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
