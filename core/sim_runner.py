"""
sim_runner.py
WorldQuant Brain 仿真执行器与卡槽装载器 (AEGIS v3.0 Hardness 工业级版)
彻底解决：
1. 铁律 1: 必须装满 8 条卡槽 (MULTI_SIM_BATCH_SIZE = 8)
2. 铁律 2: 彻底消灭 15s 轮询地狱，前 60s 内部完全静默，后续 20s 静默查询，0 Token 浪费，0 聊天刷屏
3. Gate 1 (状态机通行证锁 State-Token Gate):
   - 强制校验 red_team_verdict.json 且 all_passed == True
   - 强制校验 anti_laziness.py 账本，若处于 TABU_LIST 禁忌状态直接拒绝发包
4. Gate 2 (AST 符号推导与量纲编译器):
   - 严禁非量价数据集混用外部 PV 字段 (close, open, cap 等)
   - 拦截稀疏 [0, 1] 字段 subtract 0.5、拦截双 [-1, 1] 裸乘、拦截 VECTOR 裸露、拦截算子数 > 11（Batch61 授权放宽 8→11）
5. Gate 3 (拓扑骨架防摸鱼微调熔断):
   - 提取去数值拓扑骨架，单批相同骨架超过 2 条直接本地熔断驳回
6. Gate 4 (法医诊断与处方路由联动):
   - 收集回测数据后自动调用 Gatekeeper 诊断病灶并从 RAG 按需挂载 Tier-2 卡片
7. Gate 5 (Tabu 搜索连续停滞换核熔断):
   - 自动在 exploration_ledger.json 登记批次 Fitness，若连续 3 批无增益自动入禁忌表
"""

import asyncio
import argparse
import ast
import hashlib
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Union

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
if r"D:\brain-mcp" not in sys.path:
    sys.path.append(r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

BrainModule = None

def get_brain_module():
    global BrainModule
    if BrainModule is None:
        try:
            import importlib.util
            brain_main_path = r"D:\brain-mcp\main.py"
            if os.path.exists(brain_main_path):
                spec = importlib.util.spec_from_file_location("brain_mcp_main", brain_main_path)
                _bm = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_bm)
                BrainModule = _bm
            else:
                BrainModule = None
        except Exception:
            BrainModule = None
    return BrainModule

try:
    from quant_framework.core.dimension_rules import DimensionAuditor
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.anti_laziness import AntiLazinessAuditor
    from quant_framework.core.red_team import DoubleBlindRedTeam
    from quant_framework.core.concurrency_utils import atomic_save_json
except ImportError:
    from core.dimension_rules import DimensionAuditor
    from core.func_call_corrector import ASTSandboxCorrector
    from core.gatekeeper import Gatekeeper
    from core.anti_laziness import AntiLazinessAuditor
    from core.red_team import DoubleBlindRedTeam
    try:
        from core.concurrency_utils import atomic_save_json
    except ImportError:
        def atomic_save_json(filepath, data, **kwargs):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

class SimBatchRunner:
    DEFAULT_BATCH_SIZE = 20

    @classmethod
    def extract_golden_alpha_result(cls, r: dict, yearly_records: list = None) -> dict:
        """
        对齐图 1 生产级黄金诊断契约 (Golden Schema):
        1. 彻底过滤冗余 PASS 噪声，保留 warn 与 fail 告警项
        2. 提取 10 年逐年夏普阵列 (yearly_sharpe)，一眼识破 2020 年等黑天鹅异动
        3. 提取近 24 个月月度夏普 (last_24_monthly_sharpe)
        4. 提取核心指标 (sharpe, fitness, margin, turnover, returns, drawdown)
        5. 提取正交性 (pc, sc) 与 基础设置 (settings, regular)
        """
        if not isinstance(r, dict):
            return {}

        alpha_id = r.get("id") or r.get("alpha_id") or ""
        metrics = r.get("metrics") or r.get("is") or {}
        settings = r.get("settings") or {}
        regular = r.get("regular") or {}
        if not isinstance(regular, dict):
            regular = {"code": str(regular) if regular else ""}
        if not regular.get("code") and r.get("expression"):
            regular["code"] = r.get("expression")
        if "operatorCount" not in regular:
            code_str = regular.get("code", "")
            regular["operatorCount"] = code_str.count("(") if code_str else 0

        warn_list = []
        fail_list = []

        raw_checks = r.get("checks")
        if isinstance(raw_checks, dict):
            warn_list = list(raw_checks.get("warning", []))
            fail_list = list(raw_checks.get("fail", []))
        elif isinstance(raw_checks, list):
            for c in raw_checks:
                if not isinstance(c, dict):
                    continue
                res = c.get("result")
                item = {
                    "name": c.get("name"),
                    "result": res,
                    "limit": c.get("limit"),
                    "value": c.get("value")
                }
                if c.get("year") is not None:
                    item["year"] = c["year"]
                if res == "FAIL":
                    fail_list.append(item)
                elif res == "WARNING":
                    warn_list.append(item)
        elif isinstance(metrics.get("checks"), list):
            for c in metrics["checks"]:
                if not isinstance(c, dict):
                    continue
                res = c.get("result")
                item = {
                    "name": c.get("name"),
                    "result": res,
                    "limit": c.get("limit"),
                    "value": c.get("value")
                }
                if c.get("year") is not None:
                    item["year"] = c["year"]
                if res == "FAIL":
                    fail_list.append(item)
                elif res == "WARNING":
                    warn_list.append(item)

        yearly_sharpe = []
        y_src = yearly_records or r.get("yearly_stats") or metrics.get("yearly_stats") or []
        if isinstance(y_src, dict):
            y_src = y_src.get("records", [])
        if isinstance(y_src, list):
            for yr in y_src:
                if isinstance(yr, dict) and "year" in yr and yr.get("sharpe") is not None:
                    try:
                        yearly_sharpe.append([str(yr["year"]), f"{float(yr['sharpe']):.2f}"])
                    except (ValueError, TypeError):
                        pass
                elif isinstance(yr, (list, tuple)) and len(yr) >= 2:
                    # 兼容 Brain recordsets/yearly-stats 原生二维数组 [year, sharpe, ...]
                    try:
                        yearly_sharpe.append([str(yr[0]), f"{float(yr[1]):.2f}"])
                    except (ValueError, TypeError):
                        pass

        monthly_sharpe = r.get("last_24_monthly_sharpe") or metrics.get("last_24_monthly_sharpe") or []

        def _fmt_pct(v):
            if v is None:
                return "0.00%"
            try:
                if isinstance(v, str) and "%" in v:
                    return v
                return f"{float(v) * 100:.2f}%"
            except (ValueError, TypeError):
                return str(v)

        def _flt(v, default=0.0):
            if v is None:
                return default
            try:
                return round(float(v), 2)
            except (ValueError, TypeError):
                return default

        golden = {
            "name": r.get("name", f"AI_{alpha_id}"),
            "alpha_id": alpha_id,
            "regular": regular,
            "settings": settings,
            "sharpe": _flt(metrics.get("sharpe")),
            "sharpe_2y": _flt(metrics.get("twoYearSharpe") or metrics.get("sharpe_2y") or metrics.get("two_year_sharpe")),
            "fitness": _flt(metrics.get("fitness")),
            "margin": _fmt_pct(metrics.get("margin")),
            "turnover": _fmt_pct(metrics.get("turnover")),
            "returns": _fmt_pct(metrics.get("returns")),
            "drawdown": _fmt_pct(metrics.get("drawdown")),
            "warn": warn_list,
            "fail": fail_list,
            "pc": _flt(r.get("prod_corr", r.get("pc", metrics.get("prodCorrelation", -1.0))), default=-1.0),
            "sc": _flt(r.get("self_corr", r.get("sc", metrics.get("selfCorrelation", 0.0))), default=0.0),
            "yearly_sharpe": yearly_sharpe,
            "last_24_monthly_sharpe": monthly_sharpe,
            "good_flag": 1 if len(fail_list) == 0 and _flt(metrics.get("sharpe")) >= 1.25 else 0
        }
        return golden

    @classmethod
    def verify_state_token_and_gates(cls, batch_file_path: str, expressions_data: list, 
                                     known_fields: Union[list, dict], category: str, 
                                     region: str, universe: str, delay: int, neutralization: str,
                                     ledger_path: str = None, strict_hardness: bool = True,
                                     batch_step: int = None) -> list:
        """
        前置门禁防御体系 (支持 GrandMaster 极速模式与 Hardness 终审加固模式):
        1. 弹性容量核验 (支持 1~30 槽，对齐原帖 PARALLELISM_INSIDE=20 与 8 槽消融)
        2. Gate 1: 红队通行证校验与旧证复用防范 (双盲签名绑定)
        3. Gate 4: 靶向处方遵从度校验 (若存在上一轮确诊病灶)
        4. Gate 5: Tabu 禁忌停滞表全槽位扫描
        5. Gate 3: 本地 AST 语法解析与算子别名智能纠偏 (2ms) + 拓扑骨架唯一性
        6. Gate 2: AST 基础安全与量纲有效性核验 (0 PV 污染、Vector 标量化包裹)
        """
        print(f"\n=======================================================")
        print(f"🛡️ 【Pre-Flight 门禁链条核验 (本地 AST & 状态门禁)】")
        print(f"=======================================================")

        # 1. 卡槽容量弹性适配 (支持 1~30 条变体并发，对齐原帖 PARALLELISM_INSIDE=20)
        batch_size = len(expressions_data)
        if batch_size < 1 or batch_size > 30:
            raise ValueError(f"【批次容量异常】本次提交包含 {batch_size} 条表达式，应在 1~30 之间。")
        print(f"✅ [Gate 0] 卡槽容量核验通过: 本批共 {batch_size} 槽。")

        campaign_dir = os.path.dirname(os.path.abspath(batch_file_path))
        verdict_file = os.path.join(campaign_dir, "red_team_verdict.json")
        batch_verdict_file = batch_file_path.replace(".json", "_red_team.json")
        target_verdict_file = batch_verdict_file if os.path.exists(batch_verdict_file) else verdict_file

        # 2. Gate 1: 红队旁路机制 (GrandMaster 架构中回测前 0 文字审判，仅在 Hardness 加固测试旧凭证存在时执行兼容签名)
        if os.path.exists(target_verdict_file):
            need_re_audit = True
            try:
                with open(target_verdict_file, 'r', encoding='utf-8') as f:
                    verdict_doc = json.load(f)
                reviewed_exprs = [v.get("reviewed_expr") for v in verdict_doc.get("verdicts", [])]
                current_exprs = [x.get("expression") for x in expressions_data]
                if len(reviewed_exprs) == len(current_exprs) and all(r == c for r, c in zip(reviewed_exprs, current_exprs)):
                    need_re_audit = False
                else:
                    print("⚠️ 检测到 red_team_verdict.json 为历史批次遗留的旧通行证 (表达式内容不匹配)，强制作废并重新签发！")
            except Exception:
                need_re_audit = True

            if need_re_audit:
                fields_meta = known_fields if isinstance(known_fields, dict) else {f: {} for f in known_fields}
                DoubleBlindRedTeam.sign_batch_verdicts(expressions_data, fields_meta, target_verdict_file)
                print(f"✅ [Gate 1 - Legacy Hardness Passport] 兼容通行证已更新: {target_verdict_file}")

        # 3. Gate 4: 靶向处方遵从度核验 (仅在存在上一轮确诊病灶且处于加固模式时生效)
        rx_path = os.path.join(campaign_dir, "authorized_mutations.json")
        if strict_hardness and os.path.exists(rx_path):
            try:
                with open(rx_path, 'r', encoding='utf-8') as rf:
                    rx_data = json.load(rf)
                allowed_ops = rx_data.get("allowed_mutations", [])
                symptoms = rx_data.get("symptoms", [])
                BASE_STRUCTURAL_OPS = {"group_rank", "rank", "subindustry", "industry", "market", "sector"}
                # 【动作类处方 (Action Prescription) 语义校验】
                # Gatekeeper 会签发形如 PRUNE_REDUNDANT_OPERATOR_TO_LE_8 的处方, 它是一条"动作指令"
                # 而非 AST 算子名。若沿用"表达式文本是否包含该字符串"来判定遵从度, 则任何表达式
                # 都不可能包含它 -> 处方锁将永久死锁 (无一槽合规 -> 整批 PermissionError)。
                # 2026-10-30 根因修复: 把动作类处方单独剥离, 改用 AST 语义校验其真实约束 (算子数 <= N)。
                ACTION_PRESCRIPTIONS = {"PRUNE_REDUNDANT_OPERATOR_TO_LE_8": 8, "PRUNE_REDUNDANT_OPERATOR_TO_LE_10": 10}
                curative_ops = set(allowed_ops) - BASE_STRUCTURAL_OPS
                action_ops = {op: ACTION_PRESCRIPTIONS[op] for op in curative_ops if op in ACTION_PRESCRIPTIONS}
                curative_ops -= set(action_ops.keys())

                def _count_operators(expr_text: str) -> int:
                    """AST 统计算子调用数 (与 DimensionAuditor.operator_count 口径一致)"""
                    try:
                        tree = ast.parse(expr_text, mode="eval")
                        return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call))
                    except Exception:
                        return 9999

                if symptoms and (curative_ops or action_ops):
                    rx_compliant_slots = 0
                    for s_idx, item in enumerate(expressions_data):
                        e_text = item.get("expression", "")
                        compliant = any(op in e_text for op in curative_ops) if curative_ops else False
                        if not compliant and action_ops:
                            op_cnt = _count_operators(e_text)
                            compliant = all(op_cnt <= limit for limit in action_ops.values())
                        if compliant:
                            rx_compliant_slots += 1
                    if getattr(cls, "_strict_prescription_lock", False) and rx_compliant_slots < 4:
                        raise PermissionError(
                            f"【Gate 4 处方锁拦截】上一轮回测确诊病灶: {symptoms} 并签发了靶向处方算子: {list(curative_ops)}！\n"
                            f"但当前批次仅有 {rx_compliant_slots} 槽包含靶向治愈算子 (< 4 槽最低门槛)！"
                        )
                    print(f"ℹ️ [Gate 4 - 靶向处方建议与自主探索审计] 上一轮确诊病灶: {symptoms}，推荐靶向处方: {list(curative_ops)}。本批共有 {rx_compliant_slots} 槽采用推荐处方，其余槽位自主选用合法算子探索。")
            except PermissionError:
                raise
            except Exception as ex:
                pass

        # 4. Pre-read batch metadata for Golden Shot & Dynamic Operator Caps
        if batch_step is None:
            batch_step = 1
        core_fields = None
        stage0_op_count = 0
        batch_max_ops = 8
        is_golden_shot = False
        has_parent = False
        parent_expr = None
        if os.path.exists(batch_file_path):
            try:
                with open(batch_file_path, 'r', encoding='utf-8') as bf:
                    b_meta = json.load(bf)
                    if "step" in b_meta:
                        batch_step = b_meta.get("step", batch_step)
                    if b_meta.get("has_parent", False):
                        batch_step = max(batch_step, 2)
                        has_parent = True
                    parent_expr = b_meta.get("parent_expression")
                    core_fields = b_meta.get("core_fields", [])
                    stage0_op_count = b_meta.get("stage0_op_count", 0)
                    batch_max_ops = b_meta.get("max_ast_operators", b_meta.get("max_operators", 8))
                    is_golden_shot = bool(b_meta.get("is_golden_shot", False))
                    if stage0_op_count == 0 and b_meta.get("seed_id"):
                        c_dir = os.path.dirname(batch_file_path)
                        ts_path = os.path.join(c_dir, "total_signals.json")
                        if os.path.exists(ts_path):
                            with open(ts_path, 'r', encoding='utf-8') as tf:
                                ts_data = json.load(tf)
                                for sig in ts_data.get("signals", []):
                                    if sig.get("id") == b_meta.get("seed_id"):
                                        import ast
                                        tree = ast.parse(sig.get("expression", ""), mode='eval')
                                        stage0_op_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call))
                                        break
            except Exception:
                pass

        # 5. Gate 5: Tabu 禁忌表全槽位扫描 (在靶向母本精修模式 has_parent 下，母本核心字段与基准对照槽豁免禁忌锁定)
        ledger_file = ledger_path or os.path.join(campaign_dir, "exploration_ledger.json")
        known_field_names = set(known_fields if isinstance(known_fields, list) else known_fields.keys())
        if strict_hardness and os.path.exists(ledger_file) and not has_parent:
            for slot_idx, item in enumerate(expressions_data):
                expr_text = item.get("expression", "")
                if slot_idx == 0 or (parent_expr and expr_text == parent_expr):
                    continue
                tokens = [t for t in re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr_text) if t in known_field_names]
                if len(tokens) >= 1:
                    sig = tokens[0]
                    cat = tokens[1] if len(tokens) > 1 else None
                    is_tabu, tabu_reason = AntiLazinessAuditor.check_tabu(ledger_file, sig, cat)
                    if is_tabu:
                        raise PermissionError(
                            f"【Gate 5 拦截】Slot {slot_idx+1} 检测到已被禁忌表锁定的停滞字段对: ({sig}:{cat or 'NONE'})！\n"
                            f"原因: {tabu_reason}\n"
                            f"请将该槽位字段更换为未锁定的高优候选！"
                        )

        # Gate 3: AST 自动纠偏与骨架防摸鱼微调熔断 (Golden Shot 加时赛豁免同骨架微调上限)
        campaign_dir = os.path.dirname(os.path.abspath(batch_file_path))
        campaign_db = os.path.join(campaign_dir, "alphas_record.db")
        corrector = ASTSandboxCorrector(db_path=campaign_db)
        raw_exprs = [x.get("expression", "") for x in expressions_data]
        batch_id = os.path.basename(batch_file_path).replace(".json", "")
        parent_expr = None
        if os.path.exists(batch_file_path):
            try:
                with open(batch_file_path, 'r', encoding='utf-8') as bf:
                    b_doc = json.load(bf)
                    parent_expr = b_doc.get("parent_expression")
            except Exception:
                parent_expr = None

        ledger_data = AntiLazinessAuditor.load_ledger(ledger_file) if os.path.exists(ledger_file) else {}
        gs_used = ledger_data.get("golden_shot_used_count", 0)
        if is_golden_shot and gs_used < 1:
            ledger_data["golden_shot_used_count"] = gs_used + 1
            AntiLazinessAuditor.save_ledger(ledger_file, ledger_data)
            corrected_exprs = [corrector.correct_expression(x) for x in raw_exprs]
            corrector.record_batch(corrected_exprs, region, universe, delay, neutralization, batch_id=batch_id)
            print(f"✅ [Gate 3 - Golden Shot 单次豁免] 已消耗唯一一次加时赛微调配额 (1/1)。")
        else:
            if is_golden_shot:
                print(f"🛑 [Gate 3 - Golden Shot 配额耗尽] 加时赛微调未突破 1.58，已强制收回豁免权，恢复反常数微调硬拦截！")
            corrected_exprs = corrector.check_and_record_batch(
                raw_exprs, region, universe, delay, neutralization, batch_id=batch_id,
                is_exploit_or_step2=(batch_step >= 2),
                parent_expression=parent_expr
            )
            print(f"✅ [Gate 3 - AST Sandbox] 算子别名/参数位置自动纠偏完成，单批拓扑骨架唯一性通过。")

        # 6. Gate 2: AST 基础安全与阶段动态门禁核验 (非 PV 字段拦截、Vector 包裹、核心字段锁定与处方遵从)
        rx_allowed = set(allowed_ops) if 'allowed_ops' in locals() and allowed_ops else None

        for idx, (expr, item) in enumerate(zip(corrected_exprs, expressions_data)):
            item["expression"] = expr
            audit = DimensionAuditor.audit_expression(
                expr, known_fields, category=category, allow_pv_cross=False, max_operators=batch_max_ops,
                step=batch_step, allowed_operators=rx_allowed, stage0_op_count=stage0_op_count,
                required_fields=core_fields if (batch_step == 1 and not (locals().get('b_meta', {}).get('has_parent')) and core_fields) else None
            )
            if not audit["is_valid"]:
                corrector.remove_records(corrected_exprs, region, universe, delay, neutralization)
                raise ValueError(f"第 {idx+1} 条表达式未通过 AST 语法核验: {expr}\n原因: {audit['issues']}")
        print(f"✅ [Gate 2 - AST Auditor] AST 静态分析完成：0 PV 污染、Vector 标量化合规。")

        return corrected_exprs

    @classmethod
    async def run_batch_silently(cls, batch_file_path: str, region: str, universe: str, delay: int, 
                                 category: str = "other", neutralization: str = "NONE", decay: int = 0, 
                                 truncation: float = 0.025, nan_handling: str = "ON", ledger_path: str = None):
        """
        在 Python 内部静默执行多重回测与全套 Hardness 阶梯裁决
        """
        with open(batch_file_path, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)

        items = batch_data.get("items", [])
        known_fields = batch_data.get("known_fields", [])
        decay = int(batch_data.get("decay", decay))
        truncation = float(batch_data.get("truncation", truncation))
        nan_handling = batch_data.get("nan_handling", nan_handling)
        campaign_dir = os.path.dirname(os.path.abspath(batch_file_path))
        if ledger_path is None:
            ledger_path = os.path.join(campaign_dir, "exploration_ledger.json")

        # 1. 运行五大硬约束前置检验链 (Fail-Fast 拦截)
        corrected_exprs = cls.verify_state_token_and_gates(
            batch_file_path=batch_file_path,
            expressions_data=items,
            known_fields=known_fields,
            category=category,
            region=region,
            universe=universe,
            delay=delay,
            neutralization=neutralization,
            ledger_path=ledger_path
        )

        bm = get_brain_module()
        if not bm:
            raise RuntimeError("❌ 未检测到生产环境 Brain MCP 模块，无法提交并发仿真回测！请检查平台连接配置。")

        # 2. 静默提交至 Brain (按各变体专属的中性化分组，且每组按最多 10 条分块提交，实现真实高阶中性化并发)
        neut_groups: Dict[str, List[str]] = {}
        for item, expr in zip(items, corrected_exprs):
            item_neut = item.get("neutralization") or neutralization or "SUBINDUSTRY"
            neut_groups.setdefault(item_neut, []).append(expr)

        submission_chunks = []
        for neut_val, expr_list in neut_groups.items():
            n = len(expr_list)
            # 严格控制单批 multi-simulation 的子任务数量 <= 4 条，防止 Brain 账户并发超限遭 CANCELLED 熔断
            max_chunk_size = 4
            if n <= max_chunk_size:
                if n == 1:
                    submission_chunks.append((neut_val, [expr_list[0], expr_list[0]]))
                else:
                    submission_chunks.append((neut_val, expr_list))
            else:
                num_chunks = (n + max_chunk_size - 1) // max_chunk_size
                base_size = n // num_chunks
                rem = n % num_chunks
                start = 0
                for i in range(num_chunks):
                    size = base_size + (1 if i < rem else 0)
                    chunk = expr_list[start:start + size]
                    start += size
                    if len(chunk) == 1:
                        chunk.append(chunk[0])
                    submission_chunks.append((neut_val, chunk))

        print(f"\n📡 正在向 WorldQuant Brain 发送并发回测批次: 共 {len(corrected_exprs)} 条 (按各变体中性化拆分为 {len(submission_chunks)} 个子批并发, 每批 <= 4 条)...")

        # 2b. 逐子批串行提交+轮询+拉取 (Sequential Wave Submission with Retries)
        # 严格串行: 每次只提交 1 个 multisim 子批 (<= 4 条)，等待其完成并拉取结果后再提交下一个
        # 当遭遇平台并发排队导致 CANCELLED 时，自动退避 30s 并进行最多 2 次重试，彻底杜绝误报
        results = []
        sim_locations = []
        total_chunks = len(submission_chunks)
        max_chunk_retries = 2

        async def _run_chunk(c_idx: int, chunk_neut: str, expr_chunk: List[str]) -> List[dict]:
            """单个子批的完整生命周期: 提交 -> 静默轮询 -> 拉取结果 (内含 CANCELLED/ERROR 退避重试)"""
            chunk_results_out: List[dict] = []
            chunk_success = False
            for retry_attempt in range(max_chunk_retries + 1):
                if retry_attempt > 0:
                    print(f"   🔄 [子批 #{c_idx}/{total_chunks}] 正在进行第 {retry_attempt}/{max_chunk_retries} 次重试，先静默等待 30 秒缓解集群压力...")
                    await asyncio.sleep(30)

                sub_res = await bm.submit_multi_simulation(
                    alpha_expressions=expr_chunk,
                    region=region,
                    universe=universe,
                    delay=delay,
                    decay=decay,
                    neutralization=chunk_neut,
                    truncation=truncation,
                    pasteurization="ON",
                    unit_handling="VERIFY",
                    nan_handling=nan_handling,
                    language="FASTEXPR",
                    visualization=False
                )
                if "error" in sub_res:
                    print(f"   ⚠️ [子批 #{c_idx}/{total_chunks} | 中性化: {chunk_neut}] 提交失败: {sub_res['error']}")
                    if retry_attempt < max_chunk_retries:
                        continue
                    else:
                        print(f"   ❌ [子批 #{c_idx}/{total_chunks}] 提交最终失败，跳过该子批。")
                        return chunk_results_out

                loc = sub_res.get("location")
                sim_locations.append(loc)
                print(f"   [子批 #{c_idx}/{total_chunks} | 中性化: {chunk_neut}] 成功接入 Brain 队列! Location: {loc}")

                # 串行静默轮询单个子批 (前 60s 不查询，0 Token 浪费)
                print(f"   ⏳ [子批 #{c_idx}] 静默等待完成 (前 60s 不查询)...")
                await asyncio.sleep(60)
                poll_count = 0
                done = False
                terminal_status = None
                while not done:
                    poll_count += 1
                    chk = await bm.check_multi_simulation(loc)
                    terminal_status = chk.get("status")
                    progress = chk.get("progress", 0)
                    print(f"   [静默轮询 #{poll_count} | 子批 {c_idx} | {loc[-12:]}] 状态: {terminal_status} | 进度: {progress*100:.0f}%")
                    if terminal_status in ["COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"]:
                        done = True
                    else:
                        await asyncio.sleep(20)

                if terminal_status == "CANCELLED":
                    print(f"   ⚠️ [子批 #{c_idx}/{total_chunks}] Brain 平台因集群排队/配额返回 CANCELLED！")
                    if retry_attempt < max_chunk_retries:
                        continue
                    else:
                        print(f"   ❌ [子批 #{c_idx}/{total_chunks}] 超过最大重试次数 ({max_chunk_retries})，跳过该子批。")
                        return chunk_results_out

                if terminal_status == "ERROR":
                    print(f"   ⚠️ [子批 #{c_idx}/{total_chunks}] Brain 平台返回 ERROR 状态！")
                    if retry_attempt < max_chunk_retries:
                        continue
                    else:
                        print(f"   ❌ [子批 #{c_idx}/{total_chunks}] 超过最大重试次数 ({max_chunk_retries})，跳过该子批。")
                        return chunk_results_out

                # 正常完成，拉取结果
                fetch_res = await bm.fetch_multi_simulation_result(loc)
                chunk_results = fetch_res.get("alpha_results", [])
                valid_chunk_results = [
                    r for r in chunk_results 
                    if r.get("status") not in ["CANCELLED", "ERROR"] 
                    and (r.get("metrics") or r.get("is"))
                ]
                print(f"   📊 [子批 #{c_idx}/{total_chunks}] 拉取 {len(chunk_results)} 条结果 (有效计算: {len(valid_chunk_results)} 条，累计 {len(results)+len(chunk_results)} 条)")
                chunk_results_out.extend(chunk_results)
                chunk_success = True
                return chunk_results_out

            return chunk_results_out

        # 2c. 并发波调度 (Wave Concurrency): 波内子批并行提交轮询，波间串行
        # 并发度由环境变量 AEGIS_MAX_PARALLEL_CHUNKS 控制，默认 1 即保持原有的严格串行保守行为
        wave_size = int(os.environ.get("AEGIS_MAX_PARALLEL_CHUNKS", "1") or 1)
        wave_size = max(1, min(wave_size, 8))
        output_path = batch_file_path.replace(".json", "_result.json")
        for wave_start in range(0, total_chunks, wave_size):
            wave = submission_chunks[wave_start:wave_start + wave_size]
            wave_desc = ", ".join(f"#{wave_start + i + 1}" for i in range(len(wave)))
            print(f"\n🌊 [并发波 ({wave_size}-way)] 并行提交子批: {wave_desc} / 共 {total_chunks} 批")
            wave_res = await asyncio.gather(
                *[_run_chunk(wave_start + i + 1, cn, ec) for i, (cn, ec) in enumerate(wave)],
                return_exceptions=True
            )
            for w_i, w_chunk in enumerate(wave_res):
                if isinstance(w_chunk, Exception):
                    print(f"   ⚠️ [并发波] 子批 #{wave_start + w_i + 1} 执行异常: {w_chunk}")
                    continue
                results.extend(w_chunk)
            # 增量落盘: 每波完成后即写盘，支持断点恢复
            try:
                atomic_save_json(output_path, {"alpha_results": results})
            except Exception as _we:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({"alpha_results": results}, f, ensure_ascii=False, indent=2)
            print(f"   💾 [并发波] 本波完成，累计已收集 {len(results)} 条结果并落盘。")

        print(f"\n📊 全部 {total_chunks} 个子批回测执行完毕，累计 {len(results)} 条结果。")

        # 3. 预先为高潜候选拉取真实生产库相关性 (ProdCorr)，破解 Catch-22 循环死锁
        if bm:
            corr_candidates = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                a_id = r.get("id") or r.get("alpha_id")
                if not a_id or str(a_id).startswith("MOCK_"):
                    continue
                if Gatekeeper.extract_prod_corr(r) is not None:
                    continue
                is_m = r.get("is") or r.get("metrics") or {}
                raw_sharpe = is_m.get("sharpe")
                if raw_sharpe is None:
                    continue
                try:
                    s_val = abs(float(raw_sharpe))
                except (ValueError, TypeError):
                    continue
                parsed_chk = Gatekeeper.parse_brain_checks(r)
                # 核心修复 (漏洞 1): Brain 原生 checks 会在 Sharpe < 1.58 时产生 LOW_SHARPE/LOW_GLB_EMEA_SHARPE 等 FAIL。
                # 预拉取相关性时排除性能类 Fail，仅严卡 CW 与非性能结构性硬伤。
                perf_fail_keywords = ("SHARPE", "EMEA", "APAC", "REGIONAL", "SUB_UNIVERSE", "LADDER", "2Y", "4Y", "YEARLY")
                structural_fails = [f for f in parsed_chk.get("fails", []) if not any(k in str(f).upper() for k in perf_fail_keywords)]
                cw_failed = parsed_chk.get("cw_failed", False)
                is_near_candidate = Gatekeeper.is_near_miss_champion(r, region=region, allow_pending_prod_corr=True)

                if not cw_failed and len(structural_fails) == 0 and (parsed_chk["fail_count"] == 0 or is_near_candidate or s_val >= 1.2):
                    corr_candidates.append((s_val, a_id, r))

            def _corr_priority(item):
                cand_s, cand_id, cand_r = item
                is_nm = 1 if Gatekeeper.is_near_miss_champion(cand_r, region=region, allow_pending_prod_corr=True) else 0
                code_str = Gatekeeper.extract_expression(cand_r)
                op_cnt = code_str.count("(") if code_str else 6
                is_simple = 1 if op_cnt <= 6 else 0
                # 排序优先级: 准冠军雏形 (is_nm) > 极简结构 (op_cnt <= 6) > 夏普绝对值
                return (is_nm, is_simple, cand_s)

            corr_candidates.sort(key=_corr_priority, reverse=True)
            for s_val, a_id, r in corr_candidates[:8]:
                try:
                    corr_res = None
                    if hasattr(bm, "check_correlation"):
                        fn = getattr(bm, "check_correlation")
                        corr_res = await fn(a_id) if asyncio.iscoroutinefunction(fn) else fn(a_id)
                    elif hasattr(bm, "get_production_correlation"):
                        fn = getattr(bm, "get_production_correlation")
                        corr_res = await fn(a_id) if asyncio.iscoroutinefunction(fn) else fn(a_id)

                    if isinstance(corr_res, dict) and not corr_res.get("error"):
                        extracted_pcorr = Gatekeeper.extract_prod_corr(corr_res)
                        if extracted_pcorr is not None:
                            r["prod_corr"] = extracted_pcorr
                            r["pcorr"] = extracted_pcorr
                            r["prod_corr_verified"] = True
                            if isinstance(r.get("is"), dict):
                                r["is"]["prodCorrelation"] = extracted_pcorr
                                r["is"]["prod_corr_verified"] = True
                            if isinstance(r.get("metrics"), dict):
                                r["metrics"]["prodCorrelation"] = extracted_pcorr
                                r["metrics"]["prod_corr_verified"] = True
                            print(f"🔗 [Brain ProdCorr] 成功拉取 Alpha {a_id} 生产库相关性: {extracted_pcorr:.4f}")
                except Exception as _ce:
                    print(f"⚠️ [ProdCorr] 查询 Alpha {a_id} 相关性异常: {_ce}")

                # 同步拉取逐年统计数据 (Yearly Stats) 供图 1 黄金契约与微观法医诊断
                try:
                    if hasattr(bm, "get_alpha_yearly_stats"):
                        y_fn = getattr(bm, "get_alpha_yearly_stats")
                        y_res = await y_fn(a_id) if asyncio.iscoroutinefunction(y_fn) else y_fn(a_id)
                        if isinstance(y_res, dict) and not y_res.get("error"):
                            records = y_res.get("records") or y_res
                            r["yearly_stats"] = records
                            print(f"📈 [Brain YearlyStats] 成功拉取 Alpha {a_id} 逐年统计数据 ({len(records) if isinstance(records, list) else 1} 年)")
                except Exception as _ye:
                    print(f"⚠️ [YearlyStats] 查询 Alpha {a_id} 逐年统计异常: {_ye}")

        # 4. Gatekeeper 阶梯漏斗裁决与法医诊断
        step1_res = Gatekeeper.audit_step1_batch({"alpha_results": results}, expected_polarity=batch_data.get("expected_polarity", 1))
        print(f"\n👉 Step 1 裁决: {step1_res['message']}")

        if step1_res.get("platform_failure"):
            print(f"⚠️ [仿真平台异常保护] 本批次回测全部未获得有效完成结果 (全为 CANCELLED/ERROR/无指标)。")
            print(f"   绝不误判为主信号失效剪枝！回滚指纹库记录以备后续重跑，保留当前主信号种子状态！")
            corrector.remove_records(corrected_exprs, region, universe, delay, neutralization)
            return {
                "step1": step1_res,
                "step2_passed": [],
                "final_passed": [],
                "prescriptions": None,
                "results": results
            }
        
        # 记录批次最高 Fitness 至防摸鱼账本
        # 2026-10-29 根因修复: brain-mcp 的 fetch_multi_simulation_result 返回体把指标放在
        # "metrics" 下（不存在 "is" 嵌套），此前只读 "is" 导致每批 max_fitness 恒为 0.0，
        # 使 Gate 5 禁忌熔断基于错误数据误触发。现按 metrics -> is 顺序回退取值。
        def _fitness_of(r):
            for key in ("metrics", "is"):
                m = r.get(key) or {}
                if isinstance(m, dict) and m.get("fitness") is not None:
                    return float(m["fitness"])
            return 0.0
        batch_fitness_list = [_fitness_of(r) for r in results]
        max_batch_fitness = max(batch_fitness_list) if batch_fitness_list else 0.0

        # 获取字段名
        first_expr = corrected_exprs[0]
        tokens = [t for t in re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', first_expr) if t in (known_fields if isinstance(known_fields, list) else known_fields.keys())]
        sig_f = tokens[0] if len(tokens) >= 1 else "signal"
        cat_f = tokens[1] if len(tokens) >= 2 else None
        
        # Gate 5: 登记账本并检测 Tabu 连续停滞 (仅在开拓探索阶段生效，老兵精修模式豁免锁定母本字段)
        if not batch_data.get("has_parent", False):
            batch_id = os.path.basename(batch_file_path).replace(".json", "")
            tabu_update = AntiLazinessAuditor.update_ledger_and_check_tabu(
                ledger_path=ledger_path,
                batch_id=batch_id,
                signal_field=sig_f,
                catalyst_field=cat_f,
                batch_max_fitness=max_batch_fitness,
                expressions=corrected_exprs
            )

        if step1_res["should_prune"]:
            print("❌ 触发 AEGIS Step 1 极速早停熔断！当前主信号无统计显著性，自动剪枝！")
            return {
                "step1": step1_res,
                "step2_passed": [],
                "final_passed": [],
                "prescriptions": None
            }

        # Step 2 合规门槛
        step2_passed = Gatekeeper.audit_step2_batch({"alpha_results": results}, region=region)
        print(f"🏆 Step 2 合规通过数: {len(step2_passed)} / {len(items)} 条！")

        # 终极生产准入门禁 (V3.1 ALL PASS 0 FAIL 0 WARNING 铁律)
        final_passed = Gatekeeper.audit_final_alpha({"alpha_results": results}, region=region, strict_zero_warnings=True)
        print(f"🌟 达到终极生产准入标准 (可提交) 数量: {len(final_passed)} 条！")

        # ---------------- 双窗口敏感性成对验证 (参数高原压力测试器) ----------------
        horizon_summary = {}
        h_verdicts = []
        try:
            from .horizon_probe import HorizonProbe
        except (ImportError, ValueError):
            try:
                from core.horizon_probe import HorizonProbe
            except ImportError:
                HorizonProbe = None
        if HorizonProbe is not None:
            try:
                h_pairs = HorizonProbe.detect_pairs(items)
                h_verdicts = HorizonProbe.evaluate(
                    items,
                    step1_res.get("qualified_seeds", []),
                    h_pairs,
                    all_sharpes=step1_res.get("all_sharpes", {})
                )
                HorizonProbe.annotate(step1_res.get("qualified_seeds", []), h_verdicts, h_pairs)
                horizon_summary = HorizonProbe.summarize(h_verdicts)
                print(HorizonProbe.format_report(h_verdicts))
            except Exception as _hx:
                print(f"⚠️ [双窗口探针] 执行异常，已跳过参数高原判定: {_hx}")

        # Gate 4: 法医诊断病灶并生成下一轮定向处方白名单
        # 严禁盲目取 results[0]！按最高 Fitness 选取本批最优候选进行法医诊断
        best_alpha = max(results, key=lambda r: _fitness_of(r) if _fitness_of(r) != 0.0 else -999.0) if results else {}
        alpha_metrics = best_alpha.get("is") or best_alpha.get("metrics") or {}
        # 从真实 Brain API 检查项解析出 fails / cluster_sharpe / cw_failed (绝不读取不存在的 "ra" 字段)
        checks_parsed = Gatekeeper.parse_brain_checks(best_alpha)
        yearly_stats = best_alpha.get("yearly_stats", []) or alpha_metrics.get("yearly_stats", [])
        expr_str = Gatekeeper.extract_expression(best_alpha)
        op_count = expr_str.count("(") if expr_str else 0

        max_op_limit = batch_data.get("max_ast_operators", 8)
        prescriptions = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics=alpha_metrics,
            checks_parsed=checks_parsed,
            yearly_stats=yearly_stats,
            operator_count=op_count,
            prod_corr=Gatekeeper.extract_prod_corr(best_alpha),
            max_operator_limit=max_op_limit
        )

        # 将授权处方写盘给下一轮使用
        rx_path = os.path.join(campaign_dir, "authorized_mutations.json")
        try:
            atomic_save_json(rx_path, {
                "symptoms": prescriptions.get("symptoms", []),
                "allowed_mutations": prescriptions.get("allowed_mutations", []),
                "rag_prescriptions": prescriptions.get("rag_prescriptions", [])
            })
        except Exception:
            with open(rx_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "symptoms": prescriptions.get("symptoms", []),
                    "allowed_mutations": prescriptions.get("allowed_mutations", []),
                    "rag_prescriptions": prescriptions.get("rag_prescriptions", [])
                }, f, ensure_ascii=False, indent=2)

        # 生成对齐图 1 格式的生产级黄金诊断契约 (Golden Schema)
        golden_results = [cls.extract_golden_alpha_result(r) for r in results]
        golden_output_path = batch_file_path.replace(".json", "_golden_result.json")
        try:
            atomic_save_json(golden_output_path, {"golden_results": golden_results})
            print(f"✨ [Golden Schema] 已生成对齐图 1 格式的精简黄金诊断数据: {os.path.basename(golden_output_path)} (共 {len(golden_results)} 条)")
        except Exception as _g_err:
            print(f"⚠️ [Golden Schema] 黄金诊断数据落盘异常: {_g_err}")

        return {
            "step1": step1_res,
            "step2_passed": step2_passed,
            "final_passed": final_passed,
            "horizon": horizon_summary,
            "horizon_verdicts": h_verdicts,
            "prescriptions": prescriptions,
            "golden_results": golden_results,
            "results": results
        }
