"""
orchestrator.py
AEGIS GrandMaster 量化研发总控引擎 (降权桥接与 Python 状态机版)
(对齐 WS29639 原帖 GrandMaster 设计：Python 状态机主导，废除双盲红队文字审讯与死板 L8 槽位)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Dict, List, Optional

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_framework.core.func_call_corrector import ASTSandboxCorrector
from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.gatekeeper import Gatekeeper
from quant_framework.core.rag_memory import RAGMemoryEngine
from quant_framework.core.sim_runner import SimBatchRunner
from quant_framework.core.concurrency_utils import atomic_save_json
from quant_framework.main import AegisPipelineController, REGION_NEUTRALIZATIONS_DICT

class AEGISOrchestrator(AegisPipelineController):
    """
    AEGIS 总控引擎：继承自纯 Python 宿主状态机 AegisPipelineController，
    向下完全兼容旧版命令行与模块调用接口。
    """
    def __init__(self, region: str = "USA", dataset_id: str = "news12", category: str = "news",
                 universe: str = "TOP1000", delay: int = 1, neutralization: str = None,
                 campaign_name: str = None, parallelism: int = 20, model: str = "Gemini 3.8 Flash (High)"):
        super().__init__(
            region=region,
            universe=universe,
            delay=delay,
            category=category,
            dataset_id=dataset_id,
            model=model,
            parallelism=parallelism
        )
        self.neutralization = neutralization or self.get_supported_neutralizations()[0]
        if campaign_name:
            self.campaign_dir = os.path.join(self.base_dir, "campaigns", campaign_name)
            os.makedirs(self.campaign_dir, exist_ok=True)
            self.signals_pool_file = os.path.join(self.campaign_dir, "total_signals.json")
        self.state_file = os.path.join(self.campaign_dir, "workflow_state.json")

    def run_seed_mode(self, seed_expression: str):
        """兼容性接口: 种子模式直接进入数学处方阶段"""
        state = {
            "current_stage": "STAGE_3_MATH_OPTIMIZATION",
            "seed_expression": seed_expression,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        atomic_save_json(self.state_file, state)

    def load_state(self) -> dict:
        """加载状态机记录"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"current_stage": "STAGE_0_IDLE"}

    def stage1_initialize_exploration_grid(self) -> list:
        """阶段 1: 初始化探索网格"""
        print(f"\n📋 【Stage 1: 主信号与变体网格初始化】: {self.region} / {self.category} / {self.dataset_id}")
        pool = self.load_signals_pool()
        if not pool.get("signals"):
            return self.synthesize_stage0_seeds(count=10)
        return pool.get("signals", [])

    def stage2_synthesize_seed_pool(self, raw_seeds: list) -> list:
        """阶段 2: 纯四则运算双字段种子存入储备池"""
        pool = self.load_signals_pool()
        accepted = []
        for idx, s in enumerate(raw_seeds):
            expr = s.get("expression", "")
            fixed_expr = self.corrector.correct_expression(expr)
            seed_item = {
                "id": s.get("id", f"SEED_{idx+1:02d}"),
                "expression": fixed_expr,
                "fields_used": s.get("fields_used", []),
                "economic_mechanism": s.get("economic_mechanism", s.get("hypothesis", "")),
                "times": 0
            }
            accepted.append(seed_item)
        pool["signals"].extend(accepted)
        self.save_signals_pool(pool)
        return accepted

    async def run_hardness_cycle(self, seed_id: str, base_seed_expr: str,
                                 primary_sig: str = None, alt_sigs: list = None,
                                 catalyst_fields: list = None) -> dict:
        """单种子极速发散与静默回测验证循环"""
        seed_dummy = {
            "id": seed_id,
            "expression": base_seed_expr,
            "economic_mechanism": "单种子定向衍生验证"
        }
        variants = self.generate_swarm_variants(seed_dummy)
        
        batch_filename = f"batch_{seed_id}_{int(time.time())}.json"
        batch_path = os.path.join(self.campaign_dir, batch_filename)
        known_fields = self.load_dataset_fields()

        atomic_save_json(batch_path, {
            "seed_id": seed_id,
            "region": self.region,
            "universe": self.universe,
            "delay": self.delay,
            "category": self.category,
            "known_fields": known_fields,
            "items": variants
        })

        return await SimBatchRunner.run_batch_silently(
            batch_file_path=batch_path,
            region=self.region,
            universe=self.universe,
            delay=self.delay,
            category=self.category,
            neutralization=self.neutralization
        )

MasterOrchestrator = AEGISOrchestrator

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS GrandMaster 调度引擎")
    parser.add_argument("--region", default="USA")
    parser.add_argument("--dataset", default="news12", help="数据集 ID (默认 news12)")
    parser.add_argument("--category", default="news")
    parser.add_argument("--universe", default="TOP1000")
    parser.add_argument("--delay", type=int, default=1)
    parser.add_argument("--batch-size", "--parallelism", dest="parallelism", type=int, default=20, help="单批并发槽位数 (默认 20，支持 8/20)")
    parser.add_argument("--steps-per-seed", type=int, default=3, help="每个主信号最大迭代轮数 (默认 3)")
    parser.add_argument("--max-seeds", type=int, default=20, help="最多探索主信号数量 (默认 20)")
    parser.add_argument("--seed", default=None, help="种子因子表达式")
    args = parser.parse_args()

    orchestrator = AEGISOrchestrator(
        region=args.region,
        dataset_id=args.dataset,
        category=args.category,
        universe=args.universe,
        delay=args.delay,
        parallelism=args.parallelism
    )

    if args.seed:
        asyncio.run(orchestrator.run_hardness_cycle(
            seed_id="MANUAL_SEED",
            base_seed_expr=args.seed
        ))
    else:
        asyncio.run(orchestrator.run_pipeline_loop(
            max_seeds_to_explore=args.max_seeds,
            max_steps_per_seed=args.steps_per_seed
        ))
