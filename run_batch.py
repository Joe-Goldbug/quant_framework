"""
run_batch.py
AEGIS GrandMaster 纯 Python 仿真批次驱动器
由反重力内置 Agent 全程思考生成，100% 告别外部 agy.exe 与死模板
"""
import asyncio
import os
import sys
import json

sys.path.insert(0, ".")
from core.sim_runner import SimBatchRunner

async def main():
    batch_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not batch_file or not os.path.exists(batch_file):
        print(f"Error: Batch file not found: {batch_file}")
        sys.exit(1)

    with open(batch_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    region = meta.get("region", "GLB")
    universe = meta.get("universe", "MINVOL10M")
    delay = meta.get("delay", 1)
    category = meta.get("category", "fundamental")
    decay = meta.get("decay", 0)
    truncation = meta.get("truncation", 0.025)
    campaign_dir = os.path.dirname(os.path.abspath(batch_file))
    ledger_path = os.path.join(campaign_dir, "exploration_ledger.json")

    print(f"\n🚀 【开始执行回测批次】: {batch_file}")
    print(f"📍 目标: {region} / {universe} / Delay {delay} / {category}")
    print(f"📊 批次包含 {len(meta.get('items', []))} 条经过内置 Agent 深度构思的变体\n")

    res = await SimBatchRunner.run_batch_silently(
        batch_file_path=batch_file,
        region=region,
        universe=universe,
        delay=delay,
        category=category,
        neutralization=None,
        decay=decay,
        truncation=truncation,
        ledger_path=ledger_path
    )

    print("\n=======================================================")
    print("🏁 【批次回测执行与裁决完毕】")
    step1 = res.get("step1", {})
    print(f"👉 Step 1 初筛: {step1.get('message')}")
    print(f"   最高 |Sharpe|: {step1.get('max_abs_sharpe', 0.0):.2f}")
    print(f"   达标变体数: {len(step1.get('qualified_seeds', []))}")

    step2_passed = res.get("step2_passed", [])
    print(f"👉 Step 2 合规通过数: {len(step2_passed)}")
    for p in step2_passed:
        print(f"   🌟 [Step 2] Sharpe: {p.get('sharpe'):.2f} | Fitness: {p.get('fitness'):.2f} | Margin: {p.get('margin_bps'):.1f}bps | Expr: {p.get('expression')}")

    final_passed = res.get("final_passed", [])
    print(f"🏆 终极生产达标通过数: {len(final_passed)}")
    for f_alpha in final_passed:
        print(f"   🔥 [PRODUCTION ALPHA] Sharpe: {f_alpha.get('sharpe'):.2f} | Fitness: {f_alpha.get('fitness'):.2f} | Margin: {f_alpha.get('margin_bps'):.1f}bps")
        print(f"      Expr: {f_alpha.get('expression')}")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
