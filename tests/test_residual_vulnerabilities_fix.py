import sys
import os
import json
import math

sys.path.insert(0, os.path.abspath("."))
from core.gatekeeper import Gatekeeper
from core.dimension_rules import DimensionAuditor
from core.crowding_pairing import FieldCrowdingProfiler
from core.field_resolver import DatasetFieldResolver
from main import AegisPipelineController


def test_vulnerability_1_near_miss_brain_checks():
    """
    漏洞 1 验证:
    WorldQuant Brain API 原生返回中，Sharpe < 1.58 会在 checks 中标记 LOW_SHARPE=FAIL 或 LOW_GLB_EMEA_SHARPE=FAIL。
    修复前: fail_count == 0 会导致所有准冠军被拒。
    修复后: 忽略性能类 Fail，仅严守结构性合规 (CW, Coverage 等)。
    """
    # 模拟真实 Brain 返回的 qMLPOJPK 指标体
    q_alpha = {
        "id": "qMLPOJPK",
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "metrics": {
            "sharpe": 1.54,
            "fitness": 1.35,
            "turnover": 0.22,
            "margin_bps": 19.03,
            "prodCorrelation": 0.6548,
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 1.54},
                {"name": "LOW_GLB_EMEA_SHARPE", "result": "FAIL", "value": 0.95},
                {"name": "DATA_COVERAGE", "result": "PASS", "value": 0.98}
            ]
        }
    }

    # 1. 已核验 ProdCorr=0.6548 的 qMLPOJPK 应成功鉴定为准冠军
    is_nm = Gatekeeper.is_near_miss_champion(q_alpha, region="GLB")
    assert is_nm is True, f"qMLPOJPK 带着 LOW_SHARPE FAIL 应被成功认定为准冠军，实际返回 {is_nm}"

    # 2. 如果存在集中度违规 (CONCENTRATED_WEIGHT FAIL)，必须被拦截
    cw_alpha = {
        "id": "bad_cw",
        "expression": "group_neutralize(f1, subindustry)",
        "metrics": {
            "sharpe": 1.54,
            "fitness": 1.35,
            "turnover": 0.22,
            "margin_bps": 19.03,
            "prodCorrelation": 0.6548,
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 1.54},
                {"name": "CONCENTRATED_WEIGHT", "result": "FAIL", "value": 0.15}
            ]
        }
    }
    assert Gatekeeper.is_near_miss_champion(cw_alpha, region="GLB") is False

    # 3. 如果存在数据覆盖率违规 (DATA_COVERAGE FAIL)，属于结构性硬伤，必须被拦截
    cov_alpha = {
        "id": "bad_cov",
        "expression": "group_neutralize(f1, subindustry)",
        "metrics": {
            "sharpe": 1.54,
            "fitness": 1.35,
            "turnover": 0.22,
            "margin_bps": 19.03,
            "prodCorrelation": 0.6548,
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 1.54},
                {"name": "DATA_COVERAGE", "result": "FAIL", "value": 0.10}
            ]
        }
    }
    assert Gatekeeper.is_near_miss_champion(cov_alpha, region="GLB") is False

    # 4. 预拉取相关性阶段 (allow_pending_prod_corr=True):
    # 当尚未拉取 prodCorrelation 时 (prod_corr=None)，应允许作为潜在准冠军参与 ProdCorr 预拉取
    q_pending = {
        "id": "qMLPOJPK",
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "metrics": {
            "sharpe": 1.54,
            "fitness": 1.35,
            "turnover": 0.22,
            "margin_bps": 19.03,
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 1.54}
            ]
        }
    }
    assert Gatekeeper.is_near_miss_champion(q_pending, region="GLB", allow_pending_prod_corr=False) is False
    assert Gatekeeper.is_near_miss_champion(q_pending, region="GLB", allow_pending_prod_corr=True) is True
    print("✅ 漏洞 1 验证通过: Brain 原生 LOW_SHARPE 不再误杀准冠军，预拉取支持 allow_pending_prod_corr。")


def test_vulnerability_2_operator_phase_in_batch_and_prompts():
    """
    漏洞 2 验证:
    - 研究挖掘阶段: max_ast_operators=8, max_champion_operators=6
    - 准冠军定向优化阶段: max_ast_operators=10, max_champion_operators=10
    - batch json 中必须持久化该参数
    - prompt 中必须包含阶段算子数硬约束指令
    """
    # 1. 挖掘阶段控制器
    ctrl_discovery = AegisPipelineController(region="GLB", category="other", dataset_id="techindi_model")
    assert ctrl_discovery.max_champion_operators == 6
    assert ctrl_discovery.max_ast_operators == 8

    # 2. 准冠军定向优化阶段控制器 (带 targeted_alpha_id)
    ctrl_opt = AegisPipelineController(region="GLB", category="other", dataset_id="techindi_model", targeted_alpha_id="qMLPOJPK")
    assert ctrl_opt.max_champion_operators == 10
    assert ctrl_opt.max_ast_operators == 10

    # 3. 验证 prompt 包含阶段算子硬约束
    mock_seed = {
        "id": "SEED_TEST",
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "fields_used": ["f1"]
    }
    # 挖掘阶段 prompt
    # mock client to intercept prompt
    class MockClient:
        def __init__(self):
            self.tasks_dir = None
            self.last_prompt = ""
            self.mock_fallback = False
            self.mock_only = True
        def create_session(self, role, model):
            return self
        async def send_message(self, prompt, json_mode=True, context=None):
            self.last_prompt = prompt
            return []
        def send_message_sync(self, prompt, json_mode=True, context=None):
            self.last_prompt = prompt
            return [{
                "slot": 1,
                "optimize_reason": "test empirical validation",
                "expression": "ts_decay_linear(f1, 10)",
                "neutralization": "SUBINDUSTRY",
                "type": "empirical_probe",
                "original_alpha": "f1"
            }]
        def send_message_sync(self, prompt, json_mode=True, context=None):
            self.last_prompt = prompt
            return [{
                "slot": 1,
                "optimize_reason": "test empirical validation",
                "expression": "ts_decay_linear(f1, 10)",
                "neutralization": "SUBINDUSTRY",
                "type": "empirical_probe",
                "original_alpha": "f1"
            }]

    ctrl_discovery.client = MockClient()
    _ = ctrl_discovery.generate_swarm_variants(mock_seed, step=1)
    assert "算子数硬约束 (常规研究挖掘阶段)" in ctrl_discovery.client.last_prompt
    assert "<= 6" in ctrl_discovery.client.last_prompt
    assert "<= 8" in ctrl_discovery.client.last_prompt

    ctrl_opt.client = MockClient()
    _ = ctrl_opt.generate_swarm_variants(mock_seed, step=1)
    assert "算子数硬约束 (准冠军定向优化阶段)" in ctrl_opt.client.last_prompt
    assert "<= 10" in ctrl_opt.client.last_prompt
    print("✅ 漏洞 2 验证通过: 阶段算子约束完整注入 prompt 与批次参数。")


def test_vulnerability_3_champion_score_unverified_penalty():
    """
    漏洞 3 验证:
    compute_champion_score() 将未核实 ProdCorr 默认按 0.70 保守计入，
    确保已核实的准冠军 (如 qMLPOJPK 0.6548) 得分高于未核实因子！
    """
    # qMLPOJPK: 已核实 ProdCorr = 0.6548
    q_verified = {
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "fitness": 1.35,
        "margin_bps": 19.03,
        "prod_corr": 0.6548,
        "prod_corr_verified": True,
        "operator_count": 3
    }
    # 同等优秀未核实候选 (prod_corr=None)
    q_unverified = {
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "fitness": 1.35,
        "margin_bps": 19.03,
        "prod_corr": None,
        "prod_corr_verified": False,
        "operator_count": 3
    }

    score_verified = AegisPipelineController.compute_champion_score(q_verified)
    score_unverified = AegisPipelineController.compute_champion_score(q_unverified)

    assert score_verified > score_unverified, (
        f"已核实准冠军得分 ({score_verified:.4f}) 必须高于未核实因子 ({score_unverified:.4f})！"
    )

    # 验证未核实 factor 的 prod_corr 等效惩罚为 0.70: 1 - 0.70^2 = 0.51
    expected_corr_penalty = 1.0 - 0.70**2
    base = 1.35 * math.log(19.03) * (1.0 - 0.04 * 3)
    expected_unverified_score = base * expected_corr_penalty
    assert math.isclose(score_unverified, expected_unverified_score, rel_tol=1e-3)
    print("✅ 漏洞 3 验证通过: 未核实 ProdCorr 按 0.70 保守惩罚，qMLPOJPK 评分高于未核实因子。")


def test_vulnerability_4_golden_shot_directive():
    """
    漏洞 4 验证:
    Golden Shot 加时赛激活时，generate_swarm_variants 必须在 prompt 中注入
    微调锁定指令 (锁定母本极简结构，仅允许窗口与截面微调)。
    """
    ctrl = AegisPipelineController(region="GLB", category="other", dataset_id="techindi_model")
    mock_seed = {
        "id": "SEED_TEST",
        "expression": "group_neutralize(ts_decay_linear(f1, 20), subindustry)",
        "fields_used": ["f1"]
    }
    class MockClient:
        def __init__(self):
            self.last_prompt = ""
            self.mock_fallback = False
            self.mock_only = True
            self.tasks_dir = None
        def create_session(self, role, model):
            return self
        async def send_message(self, prompt, json_mode=True, context=None):
            self.last_prompt = prompt
            return []
        def send_message_sync(self, prompt, json_mode=True, context=None):
            self.last_prompt = prompt
            return [{
                "slot": 1,
                "optimize_reason": "test empirical validation",
                "expression": "ts_decay_linear(f1, 10)",
                "neutralization": "SUBINDUSTRY",
                "type": "empirical_probe",
                "original_alpha": "f1"
            }]

    ctrl.client = MockClient()
    _ = ctrl.generate_swarm_variants(mock_seed, step=4, is_golden_shot=True)
    assert "准冠军加时冲刺微调锁定 (Golden Shot Overtime Lock)" in ctrl.client.last_prompt
    assert "骨架拓扑硬锁定" in ctrl.client.last_prompt
    assert "窗口参数平滑微调" in ctrl.client.last_prompt
    print("✅ 漏洞 4 验证通过: Golden Shot 加时冲刺指令准确注入。")


def test_vulnerability_5_metrics_dict_and_max_op_prescription():
    """
    漏洞 5 验证:
    - diagnose_and_route_prescriptions 严格根据 max_operator_limit 签发算子剪枝指令:
      * 挖掘阶段 (limit=8): 超过 8 个算子签发 PRUNE_REDUNDANT_OPERATOR_TO_LE_8
      * 准冠军优化阶段 (limit=10): 超过 10 个算子签发 PRUNE_REDUNDANT_OPERATOR_TO_LE_10
    """
    # 9 算子在挖掘阶段 (limit=8) 属于超限
    rx_discovery = Gatekeeper.diagnose_and_route_prescriptions(
        alpha_metrics={"sharpe": 1.50, "fitness": 1.20, "margin_bps": 15.0, "turnover": 0.20},
        operator_count=9,
        max_operator_limit=8
    )
    assert "operator_count_overflow" in rx_discovery["symptoms"]
    assert "PRUNE_REDUNDANT_OPERATOR_TO_LE_8" in rx_discovery["allowed_mutations"]

    # 9 算子在优化阶段 (limit=10) 属于合规，不应报超限
    rx_opt = Gatekeeper.diagnose_and_route_prescriptions(
        alpha_metrics={"sharpe": 1.50, "fitness": 1.20, "margin_bps": 15.0, "turnover": 0.20},
        operator_count=9,
        max_operator_limit=10
    )
    assert "operator_count_overflow" not in rx_opt["symptoms"]
    assert "PRUNE_REDUNDANT_OPERATOR_TO_LE_8" not in rx_opt["allowed_mutations"]
    assert "PRUNE_REDUNDANT_OPERATOR_TO_LE_10" not in rx_opt["allowed_mutations"]

    # 11 算子在优化阶段 (limit=10) 超限，签发 LE_10
    rx_opt_11 = Gatekeeper.diagnose_and_route_prescriptions(
        alpha_metrics={"sharpe": 1.50, "fitness": 1.20, "margin_bps": 15.0, "turnover": 0.20},
        operator_count=11,
        max_operator_limit=10
    )
    assert "operator_count_overflow" in rx_opt_11["symptoms"]
    assert "PRUNE_REDUNDANT_OPERATOR_TO_LE_10" in rx_opt_11["allowed_mutations"]
    print("✅ 漏洞 5 验证通过: 阶段处方锁动态适配阶段算子限制。")


def test_conflict_1_golden_shot_exempts_skeleton_limit(tmp_path=None):
    """
    冲突 1 验证:
    Golden Shot 加时冲刺锁定母本骨架网格微调时，Gate 3 豁免同骨架微调上限。
    """
    from core.sim_runner import SimBatchRunner
    import tempfile
    
    with tempfile.TemporaryDirectory() as td:
        batch_file = os.path.join(td, "batch_test_gs.json")
        # 构造全部槽位同骨架但不同数字的批次
        items = [
            {"slot": i + 1, "expression": f"group_neutralize(ts_decay_linear(f1, {20 + i}), industry)"}
            for i in range(8)
        ]
        batch_content = {
            "seed_id": "SEED_GS",
            "step": 4,
            "region": "USA",
            "universe": "TOP1000",
            "delay": 1,
            "category": "news",
            "known_fields": ["f1"],
            "is_golden_shot": True,
            "items": items
        }
        with open(batch_file, "w", encoding="utf-8") as bf:
            json.dump(batch_content, bf)
        
        # 运行 verify_state_token_and_gates，在 is_golden_shot=True 时应当放行而不抛出摸鱼熔断
        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=batch_file,
            region="USA",
            universe="TOP1000",
            delay=1,
            category="news",
            neutralization="INDUSTRY",
            expressions_data=items,
            known_fields=["f1"]
        )
        assert len(corrected) == 8
        print("✅ 冲突 1 验证通过: Golden Shot 模式下成功豁免同骨架微调限制，杜绝死锁崩溃。")


def test_conflict_2_extract_expression_no_attribute_error():
    """
    冲突 2 验证:
    WorldQuant Brain 返回中 regular 为字符串或 None 时，extract_expression 健壮提取，无 AttributeError。
    """
    cand_str = {"regular": "group_neutralize(f1, industry)", "id": "TEST_STR"}
    cand_none = {"regular": None, "code": "ts_delta(f1, 5)", "id": "TEST_NONE"}
    cand_dict = {"regular": {"code": "rank(f1)"}, "id": "TEST_DICT"}

    assert Gatekeeper.extract_expression(cand_str) == "group_neutralize(f1, industry)"
    assert Gatekeeper.extract_expression(cand_none) == "ts_delta(f1, 5)"
    assert Gatekeeper.extract_expression(cand_dict) == "rank(f1)"
    print("✅ 冲突 2 验证通过: extract_expression 兼容 regular 为 str/None/dict，无崩溃风险。")


def test_conflict_3_rag_memory_zero_field_pure_skeleton(tmp_path=None):
    """
    冲突 3 验证:
    金字塔纯算子经验库严格抹除具体字段名，只保留 FastExpr 算子与分组层级，实现跨数据集纯算子聚类去重。
    """
    from core.rag_memory import RAGMemoryEngine
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        RAGMemoryEngine.EXP_DIR = td
        expr_ds1 = "group_neutralize(ts_decay_linear(subtract(predicted_fifth_quantile_ten_day_return_23, predicted_third_quantile_ten_day_return_23), 20), industry)"
        expr_ds2 = "group_neutralize(ts_decay_linear(subtract(analyst_target_spread_raw, market_cap_normalized_flow), 30), industry)"

        # 写入第一个数据集的 Alpha 经验
        RAGMemoryEngine.append_pure_operator_experience(
            region="GLB", delay=1, category="other",
            abstract_insight="长周期多空分位差分行业中性化",
            alpha_stats={"expression": expr_ds1, "sharpe": 1.60, "fitness": 1.40, "margin_bps": 20.0}
        )

        md_path = os.path.join(td, "GLB_1_other.md")
        with open(md_path, "r", encoding="utf-8") as f:
            content1 = f.read()

        # 断言 1: 不得包含任何具体字段名
        assert "predicted_fifth_quantile" not in content1
        assert "FIELD" in content1
        assert "group_neutralize(ts_decay_linear(subtract(FIELD,FIELD),NUM),industry)" in content1

        # 写入第二个数据集的完全同拓扑 Alpha 经验
        RAGMemoryEngine.append_pure_operator_experience(
            region="GLB", delay=1, category="other",
            abstract_insight="同源多空差分行业中性化",
            alpha_stats={"expression": expr_ds2, "sharpe": 1.65, "fitness": 1.45, "margin_bps": 22.0}
        )

        with open(md_path, "r", encoding="utf-8") as f:
            content2 = f.read()

        # 断言 2: 第二个数据集的同拓扑因子必须命中骨架聚类，达标验证次数累加为 2
        assert "**[达标验证次数: 2]**" in content2
        print("✅ 冲突 3 验证通过: 纯算子经验库 100% 剥离字段名，实现跨数据集算子骨架聚类累加。")


def test_conflict_4_vector_operator_exemption_and_alignment():
    """
    冲突 4 验证:
    1. _operator_count_of 豁免 vec_* 降维算子
    2. DimensionAuditor.audit_expression 同样豁免 vec_* 降维算子
    """
    vec_alpha = {
        "expression": "group_neutralize(ts_decay_linear(vec_avg(vector_field), 10), subindustry)",
        "sharpe": 1.70,
        "fitness": 1.30,
        "margin_bps": 20.0
    }
    # 原本算子数是 3 (group_neutralize, ts_decay_linear, vec_avg)，豁免 vec_* 后应为 2
    op_cnt = AegisPipelineController._operator_count_of(vec_alpha)
    assert op_cnt == 2, f"vec_* 算子应被豁免，期望 2，实际为 {op_cnt}"

    audit_res = DimensionAuditor.audit_expression(
        vec_alpha["expression"],
        known_fields={"vector_field": {"type": "VECTOR"}},
        category="news",
        max_operators=6
    )
    assert audit_res["is_valid"]
    assert audit_res["operator_count"] == 2, f"DimensionAuditor 统计算子数期望为 2，实际为 {audit_res['operator_count']}"
    print("✅ 冲突 4 验证通过: vec_* 标量化包裹算子全面豁免，前后算子口径对齐。")


def test_normalizer_rotation_in_candidate_pairs():
    """
    验证 candidate_pairs 破解归一化字段单一垄断:
    Top 高覆盖归一锚在候选配对中轮换分配，避免单一 normalizer 垄断全部种子。
    """
    mock_fields = {
        'cold_1': {'alpha_count': 1, 'coverage': 0.3},
        'cold_2': {'alpha_count': 2, 'coverage': 0.35},
        'cold_3': {'alpha_count': 3, 'coverage': 0.4},
        'cold_4': {'alpha_count': 4, 'coverage': 0.45},
        'norm_1': {'alpha_count': 100, 'coverage': 0.99},
        'norm_2': {'alpha_count': 50, 'coverage': 0.95},
        'norm_3': {'alpha_count': 80, 'coverage': 0.90},
    }
    profiler = FieldCrowdingProfiler(mock_fields)
    pairs = profiler.candidate_pairs(limit=6)
    norms_used = [p['normalizer'] for p in pairs]
    unique_norms = set(norms_used)
    assert len(unique_norms) >= 3, f"归一化字段必须在 top 候选间轮换，实际使用: {norms_used}"
    print(f"✅ 归一化字段轮换验证通过: {norms_used}")


def test_subtree_motif_frequency_cap():
    """
    验证 Stage 0 复合子树母题频次物理上限门禁 (<= 35%):
    当 LLM 在多个种子中重复复现局部惯用语 (如 add(reverse(F), 1)) 时，
    系统在第 2 次之后物理拦截 (count=6 时 cap=2)，杜绝全员收敛到单一伪模板。
    """
    resolver = DatasetFieldResolver()
    fields = resolver.resolve_fields(region='GLB', category='other', dataset_id='techindi_model')
    prof = FieldCrowdingProfiler(fields)
    pairs = prof.candidate_pairs(limit=6)

    ctrl = AegisPipelineController(region='GLB', category='other', dataset_id='techindi_model', base_dir='.')
    raw_seeds = []
    # 3 条包含 add(reverse(norm), 1) 复合子树母题 (3 算子 <= 3)
    for i in range(3):
        p = pairs[i]
        raw_seeds.append({
            'id': f'SEED_REV_{i+1:02d}',
            'cluster_ref': f'cluster_rev_{i+1}',
            'hypothesis_type': 'LEVEL',
            'fields_used': [p['main_anchor'], p['normalizer']],
            'field_semantics_mapping': f"{p['main_anchor']} is cold, {p['normalizer']} is norm",
            'economic_mechanism': 'test mechanism',
            'expected_polarity': 1,
            'expression': f"divide({p['main_anchor']}, add(reverse({p['normalizer']}), 1))"
        })
    # 3 条使用纯对数赔率差分 subtract(cold, norm) (2 算子 <= 3)
    for i in range(3):
        p = pairs[i+3]
        raw_seeds.append({
            'id': f'SEED_DIFF_{i+1:02d}',
            'cluster_ref': f'cluster_diff_{i+1}',
            'hypothesis_type': 'LEVEL',
            'fields_used': [p['main_anchor'], p['normalizer']],
            'field_semantics_mapping': f"{p['main_anchor']} is cold, {p['normalizer']} is norm",
            'economic_mechanism': 'test mechanism',
            'expected_polarity': 1,
            'expression': f"subtract({p['main_anchor']}, {p['normalizer']})"
        })

    class MockSession:
        def send_message_sync(self, prompt, json_mode=True, context=None):
            return {'signals': raw_seeds}

    class MockClient:
        tasks_dir = None
        mock_only = False
        mock_fallback = False
        def create_session(self, role, model):
            return MockSession()

    ctrl.client = MockClient()
    seeds = ctrl.synthesize_stage0_seeds(count=6)
    # count=6 -> max_subtree_cap = max(2, int(6 * 0.35)) = 2.
    # 3 条 SEED_REV 中仅存活 2 条 (子树母题截断)，3 条 SEED_DIFF 中仅存活 1 条 (简单差分限额 max_simple=1)，总计存活 3 条 (3/6 = 50% 达标)
    rev_survived = [s for s in seeds if "SEED_REV" in s["id"]]
    assert len(rev_survived) == 2, f"子树母题应被硬性截断为 2 条，实际存活 {len(rev_survived)} 条！"
    assert len(seeds) == 3, f"总存活数期望 3 条 (2 复合子树 + 1 最简差分)，实际 {len(seeds)} 条！"
    print(f"✅ 子树母题频次硬门禁验证通过: 3 条重复子树种子被精确截断为 {len(rev_survived)} 条，总存活 3 条！")


def test_stage0_shock_temporal_admission():
    """
    验证 Stage 0 复杂度预算与假说类型举证准入 (Complexity Budget <= 3 + Evidentiary Admission):
    1. LEVEL 假说: 必须为纯代数 (0 时序算子)，带 ts_delta 则拒绝
    2. SHOCK 假说: 准入且仅准入 1 个基础时序突变算子 (ts_delta/ts_zscore)，总算子数 <= 3
    3. SHOCK 假说: 若包含 cross-sectional 算子 (group_neutralize) 或装饰算子 (winsorize) 则拒绝
    """
    resolver = DatasetFieldResolver()
    fields = resolver.resolve_fields(region='GLB', category='other', dataset_id='techindi_model')
    prof = FieldCrowdingProfiler(fields)
    pairs = prof.candidate_pairs(limit=6)
    p0, p1, p2 = pairs[0], pairs[1], pairs[2]

    ctrl = AegisPipelineController(region='GLB', category='other', dataset_id='techindi_model', base_dir='.')

    test_cases = [
        # 1. 合规 LEVEL: 纯代数，算子数 1 <= 3 -> 应准入通过
        {
            "id": "SEED_01",
            "cluster_ref": "c1",
            "hypothesis_type": "LEVEL",
            "fields_used": [p0['main_anchor'], p0['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"subtract({p0['main_anchor']}, {p0['normalizer']})"
        },
        # 2. 违规 LEVEL: 偷带时序算子 ts_delta -> 应被过滤
        {
            "id": "SEED_02",
            "cluster_ref": "c2",
            "hypothesis_type": "LEVEL",
            "fields_used": [p0['main_anchor'], p0['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"ts_delta({p0['main_anchor']}, 5)"
        },
        # 3. 合规 SHOCK: 举证突变冲击，1 个 ts_delta，总算子数 2 <= 3 -> 应准入通过
        {
            "id": "SEED_03",
            "cluster_ref": "c3",
            "hypothesis_type": "SHOCK",
            "fields_used": [p1['main_anchor'], p1['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"subtract(ts_delta({p1['main_anchor']}, 5), {p1['normalizer']})"
        },
        # 4. 违规 SHOCK: 嵌套 group_neutralize 跨截面算子 -> 应被拒绝
        {
            "id": "SEED_04",
            "cluster_ref": "c4",
            "hypothesis_type": "SHOCK",
            "fields_used": [p1['main_anchor'], p1['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"group_neutralize(ts_delta({p1['main_anchor']}, 5), subindustry)"
        },
        # 5. 违规 SHOCK: 嵌套装潢算子 winsorize -> 应被拒绝
        {
            "id": "SEED_05",
            "cluster_ref": "c5",
            "hypothesis_type": "SHOCK",
            "fields_used": [p1['main_anchor'], p1['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"winsorize(ts_delta({p1['main_anchor']}, 5), std=3)"
        },
        # 6. 合规 LEVEL: 纯代数，算子数 2 <= 3 -> 应准入通过 (确保 6 条中存活 3 条达到 50% 存活率)
        {
            "id": "SEED_06",
            "cluster_ref": "c6",
            "hypothesis_type": "LEVEL",
            "fields_used": [p2['main_anchor'], p2['normalizer']],
            "field_semantics_mapping": "map",
            "economic_mechanism": "mech",
            "expected_polarity": 1,
            "expression": f"multiply({p2['main_anchor']}, reverse({p2['normalizer']}))"
        }
    ]

    class MockSession:
        def send_message_sync(self, prompt, json_mode=True, context=None):
            return {'signals': test_cases}

    class MockClient:
        tasks_dir = None
        mock_only = False
        mock_fallback = False
        def create_session(self, role, model):
            return MockSession()

    ctrl.client = MockClient()
    seeds = ctrl.synthesize_stage0_seeds(count=6)
    survived_ids = [s['id'] for s in seeds]
    assert "SEED_01" in survived_ids, "SEED_01 (合规 LEVEL) 必须存活！"
    assert "SEED_02" not in survived_ids, "SEED_02 (违规 LEVEL 带时序) 必须被拦截！"
    assert "SEED_03" in survived_ids, "SEED_03 (合规 SHOCK 带 1 个突变算子) 必须准入存活！"
    assert "SEED_04" not in survived_ids, "SEED_04 (违规 SHOCK 偷带 group_*) 必须被拦截！"
    assert "SEED_05" not in survived_ids, "SEED_05 (违规 SHOCK 偷带 winsorize) 必须被拦截！"
    assert "SEED_06" in survived_ids, "SEED_06 (合规 LEVEL 乘法) 必须存活！"
    print(f"✅ Stage 0 举证准入与算子预算验证通过: 仅合规 SEED_01, SEED_03, SEED_06 准入 ({survived_ids})")


def test_stage0_temporal_call_count_ast_fix():
    """验证集合去重漏洞修复: 双重 ts_delta 即使算子集合为 1，但 AST 节点数为 2，必须被严格拦截"""
    from main import AegisPipelineController
    ctrl = AegisPipelineController(region='GLB', category='other', dataset_id='techindi_model', base_dir='.')
    
    # 构造双重 ts_delta: subtract(ts_delta(f1, 5), ts_delta(f2, 5))
    expr_double = "subtract(ts_delta(field_a, 5), ts_delta(field_b, 5))"
    temporal_calls = ctrl._get_ast_temporal_calls(expr_double)
    assert len(temporal_calls) == 2, f"AST 遍历必须检测到 2 次时序算子调用，当前: {temporal_calls}"
    assert temporal_calls == ["ts_delta", "ts_delta"]

    # 单次合法 ts_decay_linear
    expr_single = "divide(ts_decay_linear(field_a, 10), field_b)"
    single_calls = ctrl._get_ast_temporal_calls(expr_single)
    assert len(single_calls) == 1 and single_calls[0] == "ts_decay_linear"
    print("✅ Stage 0 时序算子 AST 节点真实调用计数修复验证通过 (根除 set 去重漏洞)！")


def test_operator_registry_ssot_and_no_field_misidentification():
    """验证 SSOT 单一事实源与高阶算子误判拦截修复"""
    from core.operator_registry import OperatorRegistry
    from core.dimension_rules import DimensionAuditor

    all_ops = OperatorRegistry.get_all_operator_names()
    assert len(all_ops) >= 100, f"官方授权算子库数量应 >= 100，实际: {len(all_ops)}"
    assert "ts_regression" in all_ops
    assert "hump" in all_ops
    assert "right_tail" in all_ops
    assert "left_tail" in all_ops
    assert "bucket" in all_ops
    assert "reduce_avg" in all_ops

    # 验证 DimensionAuditor 绝不把合法高阶算子当成非法数据集字段
    fields_dict = {"feature_alpha": {"type": "MATRIX", "category": "other"}}
    expr = "ts_regression(bucket(feature_alpha, buckets=5), feature_alpha, 20)"
    audit = DimensionAuditor.audit_expression(
        expr,
        known_fields=fields_dict,
        category="other",
        max_operators=8
    )
    assert audit["is_valid"], f"合规高阶算子 ts_regression/bucket 审核不应报错: {audit.get('issues')}"
    print("✅ SSOT 104 官方算子库与 DimensionAuditor 高阶算子免误杀验证通过！")


def test_autonomous_operator_freedom_step2():
    """验证 Step >= 2 自主选算子自由: 移除 Gate 4 处方白名单拦截后，选用合法算子 (如 hump 降换手) 完全通畅"""
    from core.dimension_rules import DimensionAuditor
    fields_dict = {"feature_alpha": {"type": "MATRIX", "category": "other"}}
    expr = "hump(feature_alpha, threshold=0.02)"
    
    # 模拟上一轮仅授权了 ts_decay_linear，但 Agent 自主选用 hump 降换手
    audit = DimensionAuditor.audit_expression(
        expr,
        known_fields=fields_dict,
        category="other",
        max_operators=8,
        step=2,
        allowed_operators={"ts_decay_linear"}  # 不包含 hump
    )
    assert audit["is_valid"], f"Step >= 2 自主选用平台官方算子 hump 不得被拦截: {audit.get('issues')}"
    print("✅ Step >= 2 自主选算子自由验证通过: 彻底解除处方白名单对 Agent 的物理绑架！")


def test_prod_corr_065_early_warning_diagnostic():
    """验证 1: ProdCorr 诊断阈值前移至 0.65 预警线"""
    from core.gatekeeper import Gatekeeper
    
    # 0.68 处于高危边缘区 [0.65, 0.70)
    rx_68 = Gatekeeper.diagnose_and_route_prescriptions({}, prod_corr=0.68)
    assert "prod_corr_elevated_above_065" in rx_68["symptoms"], f"ProdCorr 0.68 必须确诊 prod_corr_elevated_above_065: {rx_68['symptoms']}"
    assert "SUBSTITUTE_LOW_ALPHA_COUNT_FIELD" in rx_68["allowed_mutations"]
    assert "group_neutralize" in rx_68["allowed_mutations"]
    
    # 0.72 处于严重越线区 >= 0.70
    rx_72 = Gatekeeper.diagnose_and_route_prescriptions({}, prod_corr=0.72)
    assert "prod_corr_overflow" in rx_72["symptoms"], f"ProdCorr 0.72 必须确诊 prod_corr_overflow: {rx_72['symptoms']}"

    # 0.55 处于安全区 < 0.65
    rx_55 = Gatekeeper.diagnose_and_route_prescriptions({}, prod_corr=0.55)
    assert "prod_corr_overflow" not in rx_55["symptoms"]
    assert "prod_corr_elevated_above_065" not in rx_55["symptoms"]
    print("✅ 终态微调 1 验证通过: ProdCorr 0.65 预警诊断机制与脱敏处方下发正常！")


def test_golden_shot_directive_no_ironlaw_conflict_and_parallelism():
    """验证 2: Golden Shot 加时冲刺指令消除正交铁律冲突，并动态适配 parallelism"""
    from main import AegisPipelineController
    ctrl = AegisPipelineController(region='GLB', category='other', dataset_id='techindi_model', parallelism=12, base_dir='.')
    
    captured_prompt = None
    class CaptureSession:
        def send_message_sync(self, prompt, json_mode=True, context=None):
            nonlocal captured_prompt
            captured_prompt = prompt
            return [{"slot": i+1, "optimize_reason": "r", "expression": "f1", "neutralization": "market", "type": "exploit", "original_alpha": "f1"} for i in range(12)]

    class CaptureClient:
        tasks_dir = None
        mock_only = False
        mock_fallback = False
        def create_session(self, role, model):
            return CaptureSession()

    ctrl.client = CaptureClient()
    seed = {"id": "S1", "expression": "add(f1, f2)", "fields_used": ["f1", "f2"]}
    parent = {"alpha_id": "P1", "sharpe": 1.52, "margin_bps": 20.0, "metrics": {"yearly_stats": []}}
    
    ctrl.generate_swarm_variants(seed, parent_alpha=parent, is_golden_shot=True, step=4)
    assert captured_prompt is not None
    assert "变体的 12 个槽位全部针对母本做高精度网格微调" in captured_prompt, "必须动态使用 self.parallelism 槽位数！"
    assert "变体的 8 个槽位" not in captured_prompt
    assert "构思 10 组正交算子拓扑骨架" not in captured_prompt, "Golden Shot 模式下必须清空 ironlaw_directive，杜绝冲突！"
    print("✅ 终态微调 2 验证通过: Golden Shot 指令冲突已彻底消除，槽位数动态匹配！")


def test_stage0_temporal_calls_wildcard_ts_prefix():
    """验证 3: Stage 0 _get_ast_temporal_calls 联动 OperatorRegistry 覆盖全部 ts_* 算子"""
    from main import AegisPipelineController
    ctrl = AegisPipelineController(region='GLB', category='other', dataset_id='techindi_model', base_dir='.')
    
    # 测试不在旧 17 算子列表中的新官方时序算子 (ts_av_diff, ts_ir, ts_skewness)
    expr1 = "subtract(ts_av_diff(field_a, 10), field_b)"
    calls1 = ctrl._get_ast_temporal_calls(expr1)
    assert calls1 == ["ts_av_diff"], f"ts_av_diff 必须被 AST 捕获，实际: {calls1}"

    expr2 = "divide(ts_ir(field_a, 20), field_b)"
    calls2 = ctrl._get_ast_temporal_calls(expr2)
    assert calls2 == ["ts_ir"], f"ts_ir 必须被 AST 捕获，实际: {calls2}"
    print("✅ 终态微调 3 验证通过: _get_ast_temporal_calls 全面覆盖 104 算子库中的全部 ts_* 算子！")


if __name__ == "__main__":
    test_vulnerability_1_near_miss_brain_checks()
    test_vulnerability_2_operator_phase_in_batch_and_prompts()
    test_vulnerability_3_champion_score_unverified_penalty()
    test_vulnerability_4_golden_shot_directive()
    test_vulnerability_5_metrics_dict_and_max_op_prescription()
    test_conflict_1_golden_shot_exempts_skeleton_limit()
    test_conflict_2_extract_expression_no_attribute_error()
    test_conflict_3_rag_memory_zero_field_pure_skeleton()
    test_conflict_4_vector_operator_exemption_and_alignment()
    test_normalizer_rotation_in_candidate_pairs()
    test_subtree_motif_frequency_cap()
    test_stage0_shock_temporal_admission()
    test_stage0_temporal_call_count_ast_fix()
    test_operator_registry_ssot_and_no_field_misidentification()
    test_autonomous_operator_freedom_step2()
    test_prod_corr_065_early_warning_diagnostic()
    test_golden_shot_directive_no_ironlaw_conflict_and_parallelism()
    test_stage0_temporal_calls_wildcard_ts_prefix()
    print("\n🎉 全部 5 处漏洞、4 处跨模块冲突与 9 项完美终态加固测试 100% 通过！")
