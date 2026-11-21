# -*- coding: utf-8 -*-
"""
phase19_rKR_b64.py — 种子 rKR1qVWo 优化竣工冲刺 · Phase 19 (Batch: rKR_B64, 第 64 批)
================================================================================
【核心锚点情报】 B63 换核判决穿透 (trunc 0.025 批, 5 个未测对全灭负结果优势):
  - 换核判决性证伪: 天花板在 mean:p10d, Tabu 锁按研究员裁定保留 (本批物理不可碰)。
  - Fitness 数学解构 (公式全还原): fit = Sh * sqrt(ret / max(TO, 12.5%));
    只修 Sh->1.58 得 0.896 仍 fail; 组合路径需 Sh 1.62-1.65 x ret 4.6-4.8%。
  - wpQKJ1K5 (Sh 1.53/Fit 0.87) 病灶: CLUSTER_TEST 1.2 + L/S 445:590 失衡。
  - 63 批零实测处方牌: ts_delta / ts_zscore / quantile / ts_av_diff (+ signed_power)。
【本批设计轴】 处方算子攻坚: 4 个全新字段对 (skew:prob10d / skew:prob20d / skew:rel /
  maxprim:rel) x 4 张处方可执行真身, 研究员授权算子上限 11, decay=12 对齐冠军。
【架构承诺】 零代码改动 (仅 batch JSON + phase runner 样板), STRICT NON-SUBMISSION。
用法:
  python phase19_rKR_b64.py --dry   # 仅门禁凭据预检 (Gate 0~5, 不发外包)
  python phase19_rKR_b64.py         # 全流程静默回测 (前 60s 静默, 之后 20s 静默轮询)
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
BATCH_FILE = os.path.join(CAMPAIGN, "batch_rKR_b64.json")

REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1
DECAY = 12
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
    print(f"{'CHMP':>4}|{'wpQKJ1K5':<9}|{'冠军参照 (mean:p10d, decay12)':<36}|{1.53:>6.2f}|{0.87:>6.2f}|{12.83:>6.1f}%|{4.13:>5.2f}%|{6.44:>6.1f}b|{2.06:>6.2f}|{1.06:>6.2f}|{'445/590':>10}|{1.20:>5}| 仅 2 warn: Sh<1.58 / Fit<1.00")
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
    verdict_file = os.path.join(CAMPAIGN, "verdict_rKR_B64.json")
    with open(verdict_file, "w", encoding="utf-8") as f:
        json.dump({"batch": "rKR_B64", "seed": "rKR1qVWo", "slot_metrics": verdicts,
                   "generated_at": int(time.time())}, f, ensure_ascii=False, indent=2)
    print(f"\n💾 本地裁决存档: {verdict_file}")


async def main():
    dry = "--dry" in sys.argv
    print("=" * 118)
    print("🚀 Phase 19 · Batch rKR_B64 — 处方算子攻坚批 (4 全新对 x 4 处方牌, 算子上限 11)"
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
        print("\n✅ DRY-RUN 通过: Gate 0 (8槽满载) + Gate 1 (红队通行证) + Gate 4 (处方合规) + "
              "Gate 5 (Tabu) + Gate 3 (骨架去重) + Gate 2 (AST 量纲·11算子上限) 全部就绪。")
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
