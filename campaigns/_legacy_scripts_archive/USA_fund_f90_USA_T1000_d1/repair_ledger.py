# -*- coding: utf-8 -*-
"""修复 exploration_ledger.json：用真实 Fitness 回填（此前因 sim_runner 解析 bug 全记为 0.0）
并据此重算 Tabu 禁忌（仅当连续 2 批 ΔFitness < 0.03 才锁定）。非破坏性：先备份。"""
import json, os, shutil, sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LED = os.path.join(HERE, "exploration_ledger.json")
shutil.copyfile(LED, LED + ".bak_fitness")
led = json.load(open(LED, encoding="utf-8"))

# 1) 用真实回测结果回填每批的 max_fitness
BATCH_FILES = {
    "batch_R1": "batch_R1_result.json",
    "batch_R3": "batch_R3_result.json",
    "batch_R4": "batch_R4_result.json",
    "batch_R5": "batch_R5_result.json",
    "batch_R6": "batch_R6_result.json",
    "batch_R7": "batch_R7_result.json",
}
real = {}
for b, f in BATCH_FILES.items():
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    fits = []
    for r in json.load(open(p, encoding="utf-8"))["alpha_results"]:
        m = r.get("metrics") or r.get("is") or {}
        fits.append(float(m.get("fitness") or 0.0))
    real[b] = max(fits) if fits else 0.0
print("真实批次最高 Fitness:", {k: round(v, 3) for k, v in real.items()})

# 2) 回填历史
for pair, hist in led.get("pair_histories", {}).items():
    for h in hist:
        b = h.get("batch_id")
        # 同名 batch_R1 曾被两次回测(NONE / SUBINDUSTRY)，结果文件只保留最后一次(SUBINDUSTRY)
        if b in real:
            h["max_fitness"] = real[b]
            h["fitness_source"] = "backfilled_from_real_result"

# 3) 重算 Tabu：只有当最近两批相对此前最高水位线的增量均 < 0.03 才锁定
new_tabu = {}
for pair, hist in led.get("pair_histories", {}).items():
    seq = [h.get("max_fitness", 0.0) for h in hist]
    if len(seq) < 3:
        continue
    best_prev = max(seq[:-2]) if len(seq) > 2 else 0.0
    best_recent = max(seq[-2:])
    if best_recent - best_prev < 0.03:
        new_tabu[pair] = {
            "stagnation_batches": len(seq),
            "best_prev": round(best_prev, 4),
            "best_recent": round(best_recent, 4),
            "reason": f"【Tabu(重算)】配对 {pair} 历史序列 {[round(x,3) for x in seq]}，"
                      f"最近两批最高 {best_recent:.3f} 相对此前水位 {best_prev:.3f} 增量 "
                      f"{best_recent-best_prev:+.3f} < 0.03",
        }

removed = [p for p in led.get("tabu_list", {}) if p not in new_tabu]
kept = [p for p in led.get("tabu_list", {}) if p in new_tabu]
led["tabu_list"] = new_tabu
led["_fitness_repair"] = {"backfilled_batches": {k: round(v, 4) for k, v in real.items()},
                          "released_pairs": removed, "kept_pairs": kept}
json.dump(led, open(LED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("\n解除误锁配对:", removed)
print("维持锁定配对:", kept)
for p, v in new_tabu.items():
    print(f"  LOCKED {p}: {v['reason']}")
