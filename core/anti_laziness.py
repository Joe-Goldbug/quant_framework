"""
anti_laziness.py
防摸鱼、禁忌搜索与防谎报穷尽审计器 (AEGIS v3.0 Hardness 版)
彻底解决：
1. 依据知识库画像自动构建内部必测因果交互表 (不依赖外部 PV)
2. 禁忌搜索与强制换核熔断器 (Tabu Search Circuit Breaker):
   - 在 exploration_ledger.json 中记录每个字段组合 (Signal_Field, Catalyst_Field) 每次测试的最高 Fitness
   - 若同一字段组合连续 3 个批次边际改善 ΔFitness < 0.03，自动将该组合列入 TABU_LIST 锁定
   - 彻底打破 Agent 在单个弱字段 (如 0.38 夏普) 上连续死磕 50 批的调参怪圈！
3. 穷尽声明法医审核：必测交互表测试覆盖率 < 80% 时，物理驳回“该数据集无 Alpha / 已穷尽”的谎报！
"""

import json
import os
import sys
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class AntiLazinessAuditor:
    TABU_STAGNATION_BATCHES = 3
    TABU_MIN_FITNESS_DELTA = 0.03

    @classmethod
    def generate_required_interactions(cls, kb_fields_json_path: str, max_grid_size: int = 0) -> list:
        """
        基于物理画像分桶 (type x domain x is_sparse x skewness) 构建有界正交必测网格 (AEGIS v3.2):
        1. 兼容全 Signal_Flow 数据集 (如 dl_riskfree_returns): 无 Anchor/Catalyst 标签时，
           自动构建同源跨桶信号相对差配对 (Peer_Spread)，彻底解决角色笛卡尔积为空的问题;
        2. 兼容 domain=None 的原始画像 (如 fundamental23): 自动回退为 unbounded 桶，不依赖角色标签;
        3. 严格封顶网格总规模（默认按候选池动态 24~40），防止穷尽覆盖率 (80%) 分母失控膨胀
           —— 原实现在 fundamental23 上生成 32566 项必测 (80% = 26053 项 ≈ 1300+ 批)，
           使「允许宣布穷尽」在数学上永远不可达。
        """
        with open(kb_fields_json_path, 'r', encoding='utf-8') as f:
            kb = json.load(f)

        fields = kb.get("fields", kb) if isinstance(kb, dict) else {}
        valid_items = []
        for fid, meta in fields.items():
            if not isinstance(meta, dict) or fid in ("dataset_id", "region", "universe", "delay", "total_fields"):
                continue
            cov = meta.get("coverage")
            try:
                cov_f = float(cov) if cov is not None else 1.0
            except (TypeError, ValueError):
                cov_f = 1.0
            if cov_f < 0.20:
                continue
            try:
                ac = float(meta.get("alpha_count", meta.get("alphaCount", 0)) or 0)
            except (TypeError, ValueError):
                ac = 0.0
            dom = str(meta.get("domain") or "unbounded")
            sparse = bool(meta.get("is_sparse", meta.get("sparse_zero", False)))
            skew = str(meta.get("skewness") or "medium")
            ftype = str(meta.get("type") or "MATRIX").upper()
            role = str(meta.get("semantic_role") or "Signal_Flow")
            bucket_key = f"{ftype}|{dom}|sp={int(sparse)}|sk={skew}"
            valid_items.append((fid, ac, cov_f, role, bucket_key))

        if not valid_items:
            return []

        # 动态封顶: 小数据集 24 项、大数据集最多 40 项（避免从「永不可穷尽」摆到「1 批即穷尽」）
        effective_max = max_grid_size or min(40, max(24, 24 + len(valid_items) // 100))

        # 优先选择高覆盖、低拥挤 (alpha_count 低) 的代表性字段
        valid_items.sort(key=lambda x: (x[1], -x[2]))

        # 从每个物理分桶轮询抽取代表性主信号 (最多 8 个核心主锚)
        by_bucket: Dict[str, List[tuple]] = {}
        for item in valid_items:
            by_bucket.setdefault(item[4], []).append(item)

        core_signals = []
        while len(core_signals) < min(8, len(valid_items)):
            added = False
            for b_key in sorted(by_bucket.keys()):
                if by_bucket[b_key]:
                    core_signals.append(by_bucket[b_key].pop(0))
                    added = True
                    if len(core_signals) >= 8:
                        break
            if not added:
                break

        # 辅助锚点池: 优先使用 Catalyst/Scale/Anchor 角色；全部缺失时（纯 Signal_Flow 数据集）
        # 退化为高覆盖低拥挤的异桶字段做 Peer_Spread 相对强弱配对
        aux_pool = [x[0] for x in valid_items if any(r in x[3] for r in ("Catalyst", "Scale", "Anchor", "Uncertainty"))]
        if not aux_pool:
            aux_pool = [x[0] for x in sorted(valid_items, key=lambda x: (-x[2], x[1]))[:4]]

        required_grid = []
        for fid, _, _, _, b_key in core_signals:
            # 1) 自身时序与分布形态探针 (id 命名与 update_ledger_and_check_tabu 记账保持兼容)
            required_grid.append({
                "paradigm": "Self_Dynamics",
                "physics_bucket": b_key,
                "signal_field": fid,
                "catalyst_field": None,
                "anchor_field": None,
                "id": f"P1_{fid}_self_dynamics",
            })
            # 2) 跨字段正交交互探针 (每个核心主信号最多配对 2 个正交锚，严控网格规模)
            paired_cnt = 0
            for aux_f in aux_pool:
                if aux_f == fid:
                    continue
                required_grid.append({
                    "paradigm": "Orthogonal_Interaction",
                    "physics_bucket": b_key,
                    "signal_field": fid,
                    "catalyst_field": aux_f,
                    "anchor_field": aux_f,
                    "id": f"P2_{fid}_gated_by_{aux_f}",
                })
                paired_cnt += 1
                if paired_cnt >= 2 or len(required_grid) >= effective_max:
                    break
            if len(required_grid) >= effective_max:
                break

        return required_grid[:effective_max]

    @classmethod
    def load_ledger(cls, ledger_path: str) -> dict:
        if os.path.exists(ledger_path):
            try:
                with open(ledger_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "tabu_list": {},
            "pair_histories": {},
            "tested_records": []
        }

    @classmethod
    def save_ledger(cls, ledger_path: str, data: dict):
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        with open(ledger_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def check_tabu(cls, ledger_path: str, signal_field: str, catalyst_field: Optional[str] = None) -> Tuple[bool, str]:
        """
        检查指定字段对是否处于 Tabu 禁忌锁定状态
        """
        ledger = cls.load_ledger(ledger_path)
        pair_key = f"{signal_field}:{catalyst_field or 'NONE'}"
        
        tabu_info = ledger.get("tabu_list", {}).get(pair_key)
        if tabu_info:
            return True, (
                f"【Tabu 禁忌熔断拦截】字段对 ({pair_key}) 连续 {tabu_info.get('stagnation_batches', 3)} 批"
                f"边际改善 ΔFitness < {cls.TABU_MIN_FITNESS_DELTA}，已被禁忌表物理锁定！"
                f"系统强制切换至下一个未测高优字段或新因果变动源！"
            )
        return False, "OK"

    @classmethod
    def update_ledger_and_check_tabu(cls, ledger_path: str, batch_id: str, 
                                     signal_field: str, catalyst_field: Optional[str], 
                                     batch_max_fitness: float, expressions: list) -> dict:
        """
        记录批次回测结果，并执行 3 批停滞检测：若 ΔFitness < 0.03 连续 3 批则自动加入 Tabu List
        """
        ledger = cls.load_ledger(ledger_path)
        pair_key = f"{signal_field}:{catalyst_field or 'NONE'}"
        
        pair_hist = ledger.setdefault("pair_histories", {}).setdefault(pair_key, [])
        pair_hist.append({
            "batch_id": batch_id,
            "max_fitness": batch_max_fitness,
            "expr_count": len(expressions)
        })

        # 记录已测 interaction_id
        interaction_id = f"P2_{signal_field}_gated_by_{catalyst_field}" if catalyst_field else f"P1_{signal_field}_self_dynamics"
        ledger.setdefault("tested_records", []).append({
            "batch_id": batch_id,
            "interaction_id": interaction_id,
            "signal_field": signal_field,
            "catalyst_field": catalyst_field,
            "max_fitness": batch_max_fitness
        })

        is_tabu_triggered = False
        tabu_reason = ""

        # 基于历史最高水位线 (High-Water Mark) 的 Tabu 停滞熔断 (AEGIS v3.1 修复震荡逃逸 Bug)
        if len(pair_hist) >= cls.TABU_STAGNATION_BATCHES:
            # 历史前序最高水位线 (前 N-2 批)
            best_prev = max(x["max_fitness"] for x in pair_hist[:-2])
            # 最近 2 批中的最高表现
            best_recent = max(x["max_fitness"] for x in pair_hist[-2:])
            
            # 若最近两批未能将历史最高水位线推升至少 0.03 (即使 0.74 -> 0.60 -> 0.74 震荡依然被精准捕获)
            if (best_recent - best_prev) < cls.TABU_MIN_FITNESS_DELTA:
                is_tabu_triggered = True
                tabu_reason = (
                    f"【Tabu 水位线停滞熔断】字段对 [{pair_key}] 累计测试 {len(pair_hist)} 批！"
                    f"此前最高水位线为 {best_prev:.2f}，最近两批最高仅为 {best_recent:.2f} (增量 {best_recent - best_prev:+.2f} < {cls.TABU_MIN_FITNESS_DELTA})！"
                    f"连续停滞未能突破，触发 AEGIS Tabu 强制换核熔断！"
                )
                ledger.setdefault("tabu_list", {})[pair_key] = {
                    "stagnation_batches": len(pair_hist),
                    "best_prev": best_prev,
                    "best_recent": best_recent,
                    "reason": tabu_reason
                }
                print(f"\n🛑 {tabu_reason}")

        cls.save_ledger(ledger_path, ledger)
        return {
            "pair_key": pair_key,
            "is_tabu": is_tabu_triggered,
            "reason": tabu_reason,
            "history_len": len(pair_hist)
        }

    @classmethod
    def verify_exhaustion_claim(cls, ledger_path: str, required_grid: list) -> dict:
        """核查 Agent 声称“数据集穷尽”是否属实"""
        if not os.path.exists(ledger_path):
            return {
                "allowed_to_give_up": False,
                "reason": "未找到任何测试账本 (exploration_ledger.json)，禁止谎称穷尽！",
                "coverage_pct": 0.0,
                "untested_combinations": [x["id"] for x in required_grid]
            }

        ledger = cls.load_ledger(ledger_path)
        tested_ids = set(item.get("interaction_id") for item in ledger.get("tested_records", []))
        total_required = len(required_grid)
        tested_count = len(tested_ids.intersection(set(x["id"] for x in required_grid)))
        
        coverage = tested_count / total_required if total_required > 0 else 1.0
        untested = [x["id"] for x in required_grid if x["id"] not in tested_ids]

        if coverage < 0.80:
            return {
                "allowed_to_give_up": False,
                "reason": f"怠工警告！必测因果交互空间覆盖率仅 {coverage*100:.1f}% (< 80%)，尚有 {len(untested)} 组核心经济学交互未测，严禁放弃！",
                "coverage_pct": coverage,
                "untested_combinations": untested[:5]
            }

        return {
            "allowed_to_give_up": True,
            "reason": f"已系统性测试 {tested_count}/{total_required} 组核心因果交互 (覆盖率 {coverage*100:.1f}%)，允许判定该数据集在当前 Universe 下缺乏生命力。",
            "coverage_pct": coverage
        }
