"""
tests/test_v41_architecture.py
AEGIS V4.1 架构核心不变量全面自动化验证套件
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import aegis_mcp_server
from core.agent_backends import BuiltinAgentBackend
from core.anti_laziness import AntiLazinessAuditor
from core.campaign_store import CampaignStore, check_directory_hygiene
from core.crowding_pairing import FieldCrowdingProfiler
from core.dgp_schema import HypothesisSpec
from core.dimension_rules import ASTSymbolicVisitor, DimensionAuditor
from core.fastexpr_ast import (
    build_named_ablation_and_placebo,
    canonical_equivalence_key,
    parse_fastexpr,
    validate_horizon_lattice,
    validate_snc,
)
from core.field_resolver import DatasetFieldResolver
from core.gatekeeper import Gatekeeper
from core.operator_registry import OperatorRegistry
from core.production_gate import ProductionGate
from core.research_service import ResearchService


class TestV41ArchitectureInvariants(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_operator_registry_exact_104_ssot(self):
        """[Invariant 1] 104 官方算子单一事实源：严禁合并 phantom fallback ops，索引 < 1KB"""
        OperatorRegistry._LOADED = False
        OperatorRegistry.load()
        names = OperatorRegistry.get_all_operator_names()
        self.assertEqual(len(names), 104)
        for phantom in (
            "exp", "jump_decay", "ts_max", "ts_min",
            "ts_skewness", "ts_kurtosis", "pasteurize", "group_quantile", "neg",
        ):
            self.assertNotIn(phantom, names, f"幻觉算子 {phantom} 不应存在于 104 SSOT 中")

        compact = OperatorRegistry.format_compact_index_markdown()
        self.assertLess(len(compact.encode("utf-8")), 1024)

        decay_ops = [op["name"] for op in OperatorRegistry.lookup_operators(query="decay")]
        self.assertIn("ts_decay_linear", decay_ops)
        self.assertIn("ts_decay_exp_window", decay_ops)
        self.assertNotIn("jump_decay", decay_ops)

    def test_02_fastexpr_snc_lattice_domain_ablation_and_cross_dim(self):
        """[Invariant 2] FastExpr 多行 SNC / 离散时间晶格 / 正则等价 / vec_* 保留消融 / 跨量纲除法"""
        fields_meta = {
            "news_tone": {"type": "VECTOR", "domain": "[-1, 1]", "is_sparse": False, "update_frequency": "daily", "semantic_role": "Signal_Flow"},
            "news_sent_01": {"type": "MATRIX", "domain": "[0, 1]", "is_sparse": True, "update_frequency": "daily", "semantic_role": "Signal_Flow"},
            "adv_liquidity": {"type": "MATRIX", "domain": "positive", "is_sparse": False, "update_frequency": "daily", "semantic_role": "Dimension_Anchor"},
            "fnd_tot_assets": {"type": "MATRIX", "domain": "positive", "is_sparse": False, "update_frequency": "quarterly", "semantic_role": "Dimension_Anchor"},
            "fnd_rev_q": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "quarterly", "semantic_role": "Signal_Flow"},
        }

        # Valid multiline SNC script with vec_* (exempt from operator count)
        snc_valid = (
            "news_tone_vec = vec_avg(news_tone);\n"
            "news_tone_ema = ts_decay_exp_window(news_tone_vec, 21);\n"
            "news_tone_rank = group_rank(news_tone_ema, industry);\n"
            "news_tone_neut = group_neutralize(news_tone_rank, subindustry);\n"
            "news_tone_neut"
        )
        parsed = parse_fastexpr(snc_valid)
        self.assertTrue(parsed.is_valid, parsed.errors)
        self.assertEqual(parsed.operator_count, 3)  # vec_avg exempt!
        self.assertTrue(validate_snc(parsed)["passed"])
        self.assertTrue(validate_horizon_lattice(parsed, update_frequency="daily")["passed"])

        audit_ok = DimensionAuditor.audit_expression(snc_valid, known_fields=fields_meta, category="news")
        self.assertTrue(audit_ok["is_valid"], audit_ok["issues"])

        # Bad short variable names u / x / single-token abcdef
        for bad_var_expr in (
            "u = ts_mean(news_tone, 21); rank(u)",
            "abcdef = ts_mean(news_tone_vec, 21); rank(abcdef)",
        ):
            self.assertFalse(validate_snc(bad_var_expr)["passed"], f"应拦截非法 SNC 变量名: {bad_var_expr}")

        # Bad suffix-family isomorphism
        bad_iso = "sent_ema = group_rank(vec_avg(news_tone), industry); sent_ema"
        self.assertFalse(validate_snc(bad_iso)["passed"])

        # Adjacent same-family stacking (both assignment chain & terminal Expr)
        bad_stack1 = "tone_rank = rank(vec_avg(news_tone)); peer_rank = group_rank(tone_rank, industry); peer_rank"
        bad_stack2 = "tone_rank = rank(vec_avg(news_tone)); group_rank(tone_rank, industry)"
        self.assertFalse(validate_snc(bad_stack1)["passed"])
        self.assertFalse(validate_snc(bad_stack2)["passed"])

        # Horizon & param discrete lattice checks (calibrated V4.1.1: 3/20/60 allowed, 504 blocked!)
        for bad_lat in (
            "ts_delta(news_sent_01, 17)",
            "ts_mean(news_sent_01, 37)",
            "ts_std_dev(news_sent_01, 504)",
            "winsorize(news_sent_01, std=2.5)",
            "power(adv_liquidity, 4)",
        ):
            self.assertFalse(validate_horizon_lattice(bad_lat, update_frequency="daily")["passed"], bad_lat)

        for daily_ok in (
            "ts_delta(news_sent_01, 3)",
            "ts_mean(news_sent_01, 20)",
            "ts_std_dev(news_sent_01, 60)",
        ):
            self.assertTrue(validate_horizon_lattice(daily_ok, update_frequency="daily")["passed"], daily_ok)

        # Quarterly lattice permits 66 / 125 / 252, and strictly caps at 252 (blocks 504)
        for q_ok in (
            "ts_delta(fnd_rev_q, 66)",
            "ts_mean(fnd_rev_q, 125)",
            "ts_std_dev(fnd_rev_q, 252)",
        ):
            self.assertTrue(validate_horizon_lattice(q_ok, update_frequency="quarterly")["passed"], q_ok)
        self.assertFalse(validate_horizon_lattice("ts_std_dev(fnd_rev_q, 504)", update_frequency="quarterly")["passed"])

        # Canonical equivalence invariant to variable rename & commutative add
        e_a = "tone_a_ema = ts_mean(news_sent_01, 21); tone_b_ema = ts_mean(adv_liquidity, 5); add(tone_a_ema, tone_b_ema)"
        e_b = "sig_x_ema = ts_mean(adv_liquidity, 10); sig_y_ema = ts_mean(news_sent_01, 63); add(sig_x_ema, sig_y_ema)"
        self.assertEqual(canonical_equivalence_key(e_a), canonical_equivalence_key(e_b))

        # Ablation & placebo preserve vec_* and extract args[1] from trade_when/if_else
        gated_vec = (
            "tone_ema = ts_decay_linear(vec_avg(news_tone), 21);\n"
            "liq_gate = trade_when(greater(adv_liquidity, 1000), tone_ema, -1);\n"
            "group_neutralize(liq_gate, subindustry)"
        )
        ctrl = build_named_ablation_and_placebo(gated_vec)
        self.assertEqual(ctrl["ablation_expr"], "rank(vec_avg(news_tone))")
        self.assertIn("ts_delay(vec_avg(news_tone), 252)", ctrl["placebo_expr"])

        # Cross-dimension divide blocked
        cross_div = "group_rank(divide(news_sent_01, fnd_tot_assets), subindustry)"
        audit_cross = DimensionAuditor.audit_expression(cross_div, known_fields=fields_meta, category="other", strict_lattice=True)
        self.assertFalse(audit_cross["is_valid"])
        self.assertTrue(any("跨量纲除法违规" in iss for iss in audit_cross["issues"]))

    def test_03_field_resolver_and_crowding_pair_hygiene(self):
        """[Invariant 3] Dirty 跨数据集字段剔除与 [0,1]/Dimension_Anchor 配对过滤"""
        finnews_path = os.path.join(self.root_dir, "knowledge_base", "fields", "GLB", "finnews_nlp_scores.json")
        with open(finnews_path, "r", encoding="utf-8") as f:
            fin_data = json.load(f)
        self.assertNotIn("fnd23_tot_assets", fin_data.get("fields", {}))

        self.assertTrue(
            DatasetFieldResolver._is_dirty_cross_dataset_field(
                {"cross_dataset_note": "injected anchor"}, target_dataset_id="finnews_nlp_scores"
            )
        )
        self.assertTrue(
            DatasetFieldResolver._is_dirty_cross_dataset_field(
                {"dataset": {"id": "fundamental23"}}, target_dataset_id="finnews_nlp_scores"
            )
        )

        # Crowding pairing rejects [0,1] paired with Dimension_Anchor
        fields = {
            "cold_sent_01": {"coverage": 0.45, "alpha_count": 2, "domain": "[0, 1]", "semantic_role": "Signal_Flow"},
            "warm_sent_a": {"coverage": 0.88, "alpha_count": 300, "domain": "unbounded", "semantic_role": "Signal_Flow"},
            "hot_sent_scale": {"coverage": 0.90, "alpha_count": 400, "domain": "unbounded", "semantic_role": "Signal_Flow"},
            "hot_tot_assets": {"coverage": 0.96, "alpha_count": 500, "domain": "positive", "semantic_role": "Dimension_Anchor"},
        }
        profiler = FieldCrowdingProfiler(fields)
        pairs = profiler.candidate_pairs(limit=8)
        for p in pairs:
            if p["main_anchor"] == "cold_sent_01":
                self.assertNotEqual(p["normalizer"], "hot_tot_assets", f"不得推荐跨量纲配对: {p}")

    def test_04_gatekeeper_production_gate_and_evidence_status(self):
        """[Invariant 4] info_warnings 与 defect warnings 拆分、Turnover 统一 [0.05, 0.50]、INFERRED 证据锁"""
        base_checks = [
            {"name": "MATCHES_THEMES", "result": "WARNING"},
            {"name": "MATCHES_COMPETITION", "result": "WARNING"},
            {"name": "MATCHES_PYRAMID", "result": "WARNING"},
            {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"},
        ]
        good_alpha = {
            "alpha_id": "V41_ALPHA_OK",
            "expression": "group_rank(ts_decay_linear(vec_avg(news_tone), 21), subindustry)",
            "sharpe": 1.85,
            "fitness": 1.45,
            "margin_bps": 18.0,
            "turnover": 0.45,  # between 0.35 and 0.50!
            "prod_corr": 0.30,
            "self_corr": 0.15,
            "self_corr_verified": True,
            "horizon_verdict": "PLATEAU",
            "yearly_stats": [{"year": y, "sharpe": 1.85} for y in range(2016, 2026)],
            "checks": base_checks,
        }
        parsed = Gatekeeper.parse_brain_checks(good_alpha)
        self.assertEqual(len(parsed["warnings"]), 0)
        self.assertEqual(len(parsed["info_warnings"]), 3)

        mgf = Gatekeeper.compute_master_good_flag(good_alpha)
        self.assertTrue(mgf["turnover_passed"], "Turnover=0.45 应在统一区间 [0.05, 0.50] 内通过")
        self.assertTrue(mgf["warn_passed"])

        gate_ok = ProductionGate.evaluate(good_alpha, region="USA", trial_count=20)
        self.assertTrue(gate_ok["eligible"], gate_ok["reasons"])

        # Defect warning CONCENTRATED_WEIGHT blocks ALL PASS
        bad_cw_alpha = dict(good_alpha)
        bad_cw_alpha["checks"] = base_checks + [{"name": "CONCENTRATED_WEIGHT", "result": "WARNING"}]
        gate_bad = ProductionGate.evaluate(bad_cw_alpha, region="USA", trial_count=20)
        self.assertFalse(gate_bad["eligible"])
        self.assertTrue(any("WARNING" in r for r in gate_bad["reasons"]))

        # INFERRED semantic_provenance cannot fake MEASURED
        inferred_meta = {
            "coverage": 0.90,
            "evidence_status": "MEASURED",
            "semantic_provenance": "INFERRED_FROM_DESCRIPTION",
        }
        self.assertEqual(HypothesisSpec.infer_evidence_status(inferred_meta), "INFERRED")
        measured_meta = dict(inferred_meta, probe_verified=True)
        self.assertEqual(HypothesisSpec.infer_evidence_status(measured_meta), "MEASURED")

    def test_05_agent_backend_fail_fast_no_agent_tasks(self):
        """[Invariant 5] 默认无 tasks_dir 时 0ms Fail-Fast，绝不创建 .agent_tasks 也不轮询"""
        env_patch = {k: "" for k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY", "AEGIS_MOCK_MODE")}
        with mock.patch.dict(os.environ, env_patch, clear=False):
            for k in env_patch:
                os.environ.pop(k, None)
            backend = BuiltinAgentBackend()
            self.assertIsNone(backend.tasks_dir)
            t0 = time.time()
            with self.assertRaises(RuntimeError) as cm:
                backend.send_message_sync(role="aegis-swarm-generator", model="default", prompt="test", timeout=60)
            elapsed = time.time() - t0
            self.assertLess(elapsed, 0.5)
            self.assertIn("Fail-Fast", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(self.tmp_dir.name, ".agent_tasks")))

    def test_06_campaign_store_hygiene_and_exhaustion_gate(self):
        """[Invariant 6] 三文件收敛、目录卫生拦截与 C_eff 四维穷尽门槛"""
        cdir = os.path.join(self.tmp_dir.name, "camp_hygiene")
        store = CampaignStore(cdir)
        store.init_campaign("USA_news12", "USA", "TOP1000", "news12", 1, "news")
        hyg = check_directory_hygiene(cdir)
        self.assertTrue(hyg["clean"], hyg)

        # Dropping rogue .py triggers hygiene failure
        rogue_py = os.path.join(cdir, "hack_grid.py")
        with open(rogue_py, "w", encoding="utf-8") as f:
            f.write("print('bad')\n")
        hyg_bad = check_directory_hygiene(cdir)
        self.assertFalse(hyg_bad["clean"])
        self.assertIn("hack_grid.py", hyg_bad["rogue_files"])

        # Exhaustion gate: C_eff=2.0 -> min_hyp=3, min_fam=2, min_exp=12, min_vec=2 (when has_vector_fields=True)
        premature = AntiLazinessAuditor.evaluate_exhaustion_gate(
            {
                "orthogonal_hypotheses_count": 1,
                "mechanism_families_covered": ["SMOOTH"],
                "vec_scalarizers_tested": ["vec_avg"],
                "distinct_core_skeletons_count": 3,
                "open_near_miss_leads": [{"alpha_id": "A1"}],
            },
            effective_rank=2.0,
            has_vector_fields=True,
        )
        self.assertFalse(premature["allowed"])
        self.assertEqual(premature["verdict"], "DENIED_PREMATURE")
        self.assertEqual(len(premature["missing_requirements"]), 5)

        satisfied = AntiLazinessAuditor.evaluate_exhaustion_gate(
            {
                "orthogonal_hypotheses_count": 3,
                "mechanism_families_covered": ["SMOOTH", "DIFF"],
                "vec_scalarizers_tested": ["vec_avg", "vec_stddev"],
                "distinct_core_skeletons_count": 12,
                "open_near_miss_leads": [],
            },
            effective_rank=2.0,
            has_vector_fields=True,
        )
        self.assertTrue(satisfied["allowed"], satisfied)
        self.assertEqual(satisfied["verdict"], "EXHAUSTED_CERTIFIED")

    def test_07_research_service_end_to_end_lifecycle(self):
        """[Invariant 7] ResearchService 全闭环: Scope Lock, C_eff, Settings-Last, Holdout Mask/Unmask, Certify & Exhaust"""
        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_test_ds_v41"

        # 1. Init campaign (Scope Lock)
        init_res = svc.init_or_load_campaign(
            region="USA", universe="TOP1000", dataset_id="test_ds_v41", delay=1, category="news", campaign_name=cid
        )
        self.assertEqual(init_res["mode"], "GREENFIELD")

        # Scope Lock violation rejected
        with self.assertRaises(ValueError):
            svc.init_or_load_campaign(
                region="USA", universe="TOP1000", dataset_id="other_dataset", delay=1, category="news", campaign_name=cid
            )

        # 2. Spectral C_eff profiling: orthogonal vs collinear PnL series
        rng = np.random.default_rng(42)
        ortho_pnl = {
            f"f_{i}": rng.normal(0.0, 1.0, 200).tolist()
            for i in range(4)
        }
        fields_meta = {
            f"f_{i}": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"}
            for i in range(4)
        }
        prof_ortho = svc.profile_dataset(cid, fields_meta=fields_meta, pnl_series_map=ortho_pnl)
        self.assertGreater(prof_ortho["effective_rank"], 3.2)

        base_vec = rng.normal(0.0, 1.0, 200)
        collinear_pnl = {f"f_{i}": (base_vec * (i + 1)).tolist() for i in range(4)}
        prof_col = svc.profile_dataset(cid, fields_meta=fields_meta, pnl_series_map=collinear_pnl)
        self.assertLess(prof_col["effective_rank"], 1.3)

        # 3. Register hypothesis & enforce Expression-First Settings-Last + Holdout Masking
        svc.register_hypothesis(
            campaign_id=cid,
            hypothesis_id="HYP_MOMO_01",
            economic_mechanism="新闻增量变化率引发机构资金缓步再平衡漂移",
            counterparty="反应滞后的被动调仓资金与噪声交易者",
            field_roles=[{"field_id": "f_0", "role": "Signal_Flow"}],
            mechanism_intents=["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
            falsification_criterion="若 5日/21日 均无法取得正夏普或接近零则证伪",
            fields_meta=fields_meta,
        )

        bad_setting_var = [{
            "slot": 1,
            "hypothesis_ref": "HYP_MOMO_01",
            "change_axis": "temporal_diff",
            "prediction": "测试非法提前改 decay=4 应被 Expression-First 拦截且预计提升 Sharpe",
            "expression": "diff_rank = group_rank(ts_delta(f_0, 21), subindustry); diff_rank",
        }]
        with self.assertRaises(PermissionError):
            svc.run_experiment(cid, "HYP_MOMO_01", bad_setting_var, mode="discovery", settings={"decay": 4}, fields_meta=fields_meta)

        with self.assertRaises(PermissionError):
            svc.run_experiment(cid, "HYP_MOMO_01", bad_setting_var, mode="settings_calibration", settings={"decay": 4}, fields_meta=fields_meta)

        # Successful discovery run with internal 2Y holdout masked in agent output
        def _mock_exec(var, eff_settings):
            return {
                "alpha_id": "A_DISC_01",
                "sharpe": 1.65,
                "fitness": 1.35,
                "turnover": 0.25,
                "margin_bps": 16.0,
                "prod_corr": 0.28,
                "self_corr": 0.12,
                "self_corr_verified": True,
                "horizon_verdict": "PLATEAU",
                "yearly_stats": [{"year": 2016 + i, "sharpe": 1.70} for i in range(10)],
                "two_year_sharpe": 1.80,
                "checks": [
                    {"name": "MATCHES_THEMES", "result": "WARNING"},
                    {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"},
                ],
            }

        run_disc = svc.run_experiment(
            cid, "HYP_MOMO_01", bad_setting_var, mode="discovery", sim_executor=_mock_exec, fields_meta=fields_meta
        )
        self.assertTrue(run_disc["holdout_masked"])
        agent_r = run_disc["results"][0]
        self.assertNotIn("sharpe", agent_r)
        self.assertNotIn("holdout_2y_sharpe", agent_r)
        self.assertNotIn("two_year_sharpe", agent_r)
        self.assertIn("is_core_sharpe", agent_r)
        self.assertIn("trimmed_is_sharpe", agent_r)
        self.assertEqual(len(agent_r["yearly_stats"]), 8)

        # Now that parent achieved |Sharpe| >= 1.25, settings_calibration is unlocked!
        cal_res = svc.run_experiment(
            cid,
            "HYP_MOMO_01",
            [{
                "slot": 1,
                "hypothesis_ref": "HYP_MOMO_01",
                "change_axis": "decay_calibration",
                "prediction": "校准 decay=4 后换手降低至 18% 且 Sharpe 维持 >= 1.60",
                "expression": "group_rank(ts_decay_linear(ts_delta(f_0, 21), 5), subindustry)",
            }],
            mode="settings_calibration",
            settings={"decay": 4, "truncation": 0.08},
            sim_executor=lambda v, s: {**_mock_exec(v, s), "alpha_id": "A_CAL_01", "sharpe": 1.82},
            fields_meta=fields_meta,
        )
        self.assertEqual(cal_res["results"][0]["alpha_id"], "A_CAL_01")

        # Premature DECLARE_EXHAUSTED denied
        exh_denied = svc.request_verdict(cid, "DECLARE_EXHAUSTED", rationale="想提前下班")
        self.assertEqual(exh_denied["verdict"], "DENIED_PREMATURE")

        # CERTIFY_ALPHA unmasks holdout and certifies ALL PASS into certified_champions.json
        cert = svc.request_verdict(cid, "CERTIFY_ALPHA", alpha_id="A_CAL_01", rationale="指标全面达标")
        self.assertEqual(cert["verdict"], "CERTIFIED_ALL_PASS", cert)
        self.assertTrue(cert["eligible"])
        self.assertTrue(os.path.exists(cert["champions_file"]))
        with open(cert["champions_file"], "r", encoding="utf-8") as cf:
            champs = json.load(cf)
        self.assertEqual(len(champs), 1)
        self.assertEqual(champs[0]["alpha_id"], "A_CAL_01")

    def test_08_aegis_mcp_server_tools_and_cli(self):
        """[Invariant 8] FastMCP 7 工具完整注册与 CLI operators 查询"""
        tool_mgr = getattr(aegis_mcp_server.mcp, "_tool_manager", None)
        self.assertIsNotNone(tool_mgr)
        registered = set(tool_mgr._tools.keys()) if hasattr(tool_mgr, "_tools") else set()
        expected = {
            "init_or_load_campaign",
            "campaign_status",
            "profile_dataset",
            "register_hypothesis",
            "run_experiment",
            "request_verdict",
            "lookup_operators",
        }
        self.assertTrue(expected.issubset(registered), f"缺失工具: {expected - registered}")

        proc = subprocess.run(
            [sys.executable, os.path.join(self.root_dir, "aegis_mcp_server.py"), "cli", "operators", "--query", "decay"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        op_names = [o["name"] for o in payload.get("operators", [])]
        self.assertIn("ts_decay_linear", op_names)
        self.assertNotIn("jump_decay", op_names)

        # Verify live-IO MCP tools are async def (no asyncio.run inside running event loop crash!)
        for async_tool in ("init_or_load_campaign", "profile_dataset", "run_experiment", "request_verdict"):
            self.assertTrue(tool_mgr._tools[async_tool].is_async, f"{async_tool} 必须注册为异步 MCP 工具")

    def test_09_snc_hard_gate_closes_both_backdoors(self):
        """[Adversarial 9] 关闭 SNC 两道后门：拦截 4+ 算子单行意面 & 拦截胡编后缀/泛化前缀"""
        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_snc"
        fields_meta = {
            "f_0": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"},
        }
        svc.init_or_load_campaign("USA", "TOP1000", "adv_snc", 1, "news", campaign_name=cid)
        svc.register_hypothesis(
            cid, "HYP_SNC", "新闻热度变化引发机构配置调仓漂移", "被动调仓资金",
            [{"field_id": "f_0", "role": "Signal_Flow"}],
            ["TEMPORAL_DECAY", "CROSS_SECTIONAL_RELATIVE"],
            "若 5d/21d 夏普均 < 0.5 则证伪",
            fields_meta=fields_meta,
        )

        # Backdoor A: 7-layer single-line spaghetti MUST be rejected by ResearchService!
        spaghetti = "group_neutralize(winsorize(zscore(ts_decay_linear(ts_delta(ts_mean(f_0, 5), 10), 21)), std=4), subindustry)"
        with self.assertRaises(ValueError) as cm_a:
            svc.run_experiment(
                cid, "HYP_SNC",
                [{"slot": 1, "hypothesis_ref": "HYP_SNC", "change_axis": "spaghetti", "prediction": "测试单行深嵌套拦截，预期被 SNC 阻断", "expression": spaghetti}],
                mode="discovery", dry_run=True, fields_meta=fields_meta,
            )
        self.assertIn("SNC-Missing", str(cm_a.exception))

        # Backdoor B: Made-up suffixes & generic prefixes MUST be rejected!
        for fake_snc in (
            "foo_banana = ts_decay_linear(f_0, 21); bar_orange = group_rank(foo_banana, industry); bar_orange",
            "news_banana = ts_decay_linear(f_0, 21); news_orange = group_rank(news_banana, industry); news_orange",
            "news_signal = ts_decay_linear(f_0, 21); news_alpha = group_rank(news_signal, industry); news_alpha",
        ):
            self.assertFalse(validate_snc(fake_snc)["passed"], f"必须拦截胡编/泛化后缀: {fake_snc}")
            with self.assertRaises(ValueError):
                svc.run_experiment(
                    cid, "HYP_SNC",
                    [{"slot": 1, "hypothesis_ref": "HYP_SNC", "change_axis": "fake_snc", "prediction": "测试胡编后缀应被拦截", "expression": fake_snc}],
                    mode="discovery", dry_run=True, fields_meta=fields_meta,
                )

    def test_10_mcp_async_live_loop_chunking_profiling_and_certify(self):
        """[Adversarial 10] MCP 运行中事件循环实盘压测：<=4 分块、CANCELLED 重试、分层物理画像、CERTIFY_ALPHA 全自动取证"""
        import asyncio
        import types

        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_live_mcp_e2e"
        fields_meta = {
            f"rev_cluster_{i}": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.92, "alpha_count": i, "semantic_role": "Signal_Flow"}
            for i in range(6)
        }
        fields_meta.update({
            f"sent_cluster_{i}": {"type": "MATRIX", "domain": "[-1, 1]", "is_sparse": False, "update_frequency": "daily", "coverage": 0.85, "alpha_count": i + 10, "semantic_role": "Catalyst"}
            for i in range(6)
        })

        submitted_chunk_sizes = []
        cancelled_once = {"done": False}
        alpha_counter = {"n": 0}
        alpha_expr_map = {}

        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload
                self.headers = {"Retry-After": "0"}
            def json(self):
                return self._payload

        class _FakeClient:
            base_url = "https://api.worldquantbrain.com"
            async def _request(self, method, url):
                if "/multi/" in url:
                    loc_id = url.rsplit("/", 1)[-1]
                    if loc_id == "chunk_cancel":
                        return _FakeResp({"status": "CANCELLED"})
                    kids = loc_id.split("__")
                    return _FakeResp({"status": "COMPLETE", "children": [f"https://api.worldquantbrain.com/simulations/child/{k}" for k in kids]})
                if "/child/" in url:
                    aid = url.rsplit("/", 1)[-1]
                    return _FakeResp({"status": "COMPLETE", "alpha": aid})
                return _FakeResp({"status": "COMPLETE"})

        fake_bm = types.SimpleNamespace(brain_client=_FakeClient())

        async def _create_multi_simulation(items):
            # Enforce real brain-mcp <= 8 hard limit!
            if len(items) > 8:
                return {"error": "Maximum 8 alpha expressions allowed per request"}
            submitted_chunk_sizes.append(len(items))
            if not cancelled_once["done"] and len(submitted_chunk_sizes) == 2:
                cancelled_once["done"] = True
                return {"location": "https://api.worldquantbrain.com/simulations/multi/chunk_cancel"}
            aids = []
            for it in items:
                alpha_counter["n"] += 1
                aid = f"LIVE_A_{alpha_counter['n']}"
                alpha_expr_map[aid] = it["regular"]
                aids.append(aid)
            return {"location": f"https://api.worldquantbrain.com/simulations/multi/{'__'.join(aids)}"}

        async def _get_alpha_details(aid):
            return {
                "id": aid,
                "is": {
                    "sharpe": 1.95,
                    "fitness": 1.50,
                    "turnover": 0.22,
                    "margin": 0.0018,
                    "longCount": 420,
                    "shortCount": 410,
                    "checks": [
                        {"name": "MATCHES_THEMES", "result": "WARNING"},
                        {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"},
                    ],
                },
                "settings": {"decay": 0, "truncation": 0.025, "neutralization": "SUBINDUSTRY"},
            }

        async def _get_alpha_yearly_stats(aid):
            return {"records": [[2016 + i, 100.0, 1e6, 400, 400, 0.22, 1.90] for i in range(10)]}

        async def _get_alpha_pnl(aid):
            seed = int(aid.rsplit("_", 1)[-1])
            rng = np.random.default_rng(100 + seed)
            cum = np.cumsum(rng.normal(0.01, 1.0, 60)).tolist()
            return {"records": [[f"2024-01-{i+1:02d}", v] for i, v in enumerate(cum)]}

        async def _check_correlation(aid):
            return {
                "alpha_id": aid,
                "checks": {
                    "production": {"max_correlation": 0.32, "passes_check": True},
                    "self": {"max_correlation": 0.18, "passes_check": True},
                },
            }

        async def _check_self_correlation(aid, threshold=0.7):
            return {"alpha_id": aid, "max_correlation": 0.18, "passes_check": True}

        fake_bm.create_multi_simulation = _create_multi_simulation
        fake_bm.get_alpha_details = _get_alpha_details
        fake_bm.get_alpha_yearly_stats = _get_alpha_yearly_stats
        fake_bm.get_alpha_pnl = _get_alpha_pnl
        fake_bm.check_correlation = _check_correlation
        fake_bm.check_self_correlation = _check_self_correlation

        async def _scenario():
            with mock.patch("core.research_service.get_brain_module", return_value=fake_bm), \
                 mock.patch.object(aegis_mcp_server, "_SERVICE", svc), \
                 mock.patch.object(svc, "_resolve_fields", return_value={k: HypothesisSpec.normalize_field_profile(k, v) for k, v in fields_meta.items()}), \
                 mock.patch.dict(os.environ, {"AEGIS_LIVE_POLL_MIN_SEC": "0.01", "AEGIS_LIVE_RETRY_BACKOFF_SEC": "0.01"}):
                await aegis_mcp_server.mcp.call_tool(
                    "init_or_load_campaign",
                    {"region": "USA", "universe": "TOP1000", "dataset_id": "live_ds", "delay": 1, "category": "news", "campaign_name": cid},
                )
                # 1. Live profile_dataset via MCP inside running loop (NO asyncio.run crash!)
                prof_raw = await aegis_mcp_server.mcp.call_tool(
                    "profile_dataset",
                    {"campaign_id": cid, "use_live_probe": True},
                )
                prof = json.loads(prof_raw[0][0].text) if isinstance(prof_raw, tuple) else json.loads(prof_raw[0].text)
                self.assertEqual(prof["method"], "pnl_series_eigen")
                self.assertGreater(len(prof["measured_physics"]), 0)
                first_phys = next(iter(prof["measured_physics"].values()))
                self.assertEqual(first_phys["evidence_status"], "MEASURED")
                self.assertAlmostEqual(first_phys["measured_coverage"], 0.83, places=2)

                # 2. Register hypothesis and run 10 variants via MCP -> proves <= 4 chunking + CANCELLED retry + N/2N horizon!
                await aegis_mcp_server.mcp.call_tool(
                    "register_hypothesis",
                    {
                        "campaign_id": cid,
                        "hypothesis_id": "HYP_LIVE",
                        "economic_mechanism": "营收预期与舆情增量引发机构调仓漂移",
                        "counterparty": "反应滞后的被动基金",
                        "field_roles": [{"field_id": "rev_cluster_0", "role": "Signal_Flow"}],
                        "mechanism_intents": ["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
                        "falsification_criterion": "若 5d/21d 均无显著正夏普则证伪",
                    },
                )
                submitted_chunk_sizes.clear()
                cancelled_once["done"] = False
                ten_variants = [
                    # Slot 1 & 2 form an N/2N plateau pair on rev_cluster_0!
                    {"slot": 1, "hypothesis_ref": "HYP_LIVE", "change_axis": "h_5d", "prediction": "5日营收预期增量捕捉短周期反应不足，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(rev_cluster_0, 5), subindustry)"},
                    {"slot": 2, "hypothesis_ref": "HYP_LIVE", "change_axis": "h_21d", "prediction": "21日营收预期高原配对与 5日同号持续，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(rev_cluster_0, 21), subindustry)"},
                ]
                for i in range(1, 5):
                    ten_variants.append({
                        "slot": len(ten_variants) + 1,
                        "hypothesis_ref": "HYP_LIVE",
                        "change_axis": f"field_rev_{i}",
                        "prediction": "跨字段正交验证营收增量效应，预期样本内核心 Sharpe >= 1.0",
                        "expression": f"group_rank(ts_delta(rev_cluster_{i}, 21), subindustry)",
                    })
                for i in range(4):
                    ten_variants.append({
                        "slot": len(ten_variants) + 1,
                        "hypothesis_ref": "HYP_LIVE",
                        "change_axis": f"field_sent_{i}",
                        "prediction": "跨语义簇舆情衰减漂移验证，预期样本内核心 Sharpe >= 1.0 且换手可控",
                        "expression": f"group_neutralize(ts_decay_linear(sent_cluster_{i}, 21), subindustry)",
                    })
                self.assertEqual(len(ten_variants), 10)

                run_raw = await aegis_mcp_server.mcp.call_tool(
                    "run_experiment",
                    {"campaign_id": cid, "hypothesis_id": "HYP_LIVE", "variants": ten_variants, "mode": "discovery", "dry_run": False},
                )
                run_res = json.loads(run_raw[0][0].text) if isinstance(run_raw, tuple) else json.loads(run_raw[0].text)
                self.assertEqual(run_res["status"], "COMPLETED")
                self.assertEqual(len(run_res["results"]), 10)
                # Verify all chunks respected <= 4 AND retry happened on cancelled chunk!
                self.assertTrue(all(sz <= 4 for sz in submitted_chunk_sizes), submitted_chunk_sizes)
                self.assertGreaterEqual(len(submitted_chunk_sizes), 4)  # 3 chunks + 1 retry
                # Slot 1 & 2 auto-annotated as PLATEAU!
                self.assertEqual(run_res["results"][0].get("horizon_verdict"), "PLATEAU")

                # 3. CERTIFY_ALPHA via MCP on Slot 1 alpha_id -> auto-enriches & certifies ALL PASS (NO DEADLOCK!)
                target_aid = run_res["results"][0]["alpha_id"]
                cert_raw = await aegis_mcp_server.mcp.call_tool(
                    "request_verdict",
                    {"campaign_id": cid, "action": "CERTIFY_ALPHA", "alpha_id": target_aid, "rationale": "全量实盘证据闭环发证"},
                )
                cert = json.loads(cert_raw[0][0].text) if isinstance(cert_raw, tuple) else json.loads(cert_raw[0].text)
                self.assertEqual(cert["verdict"], "CERTIFIED_ALL_PASS", cert)
                self.assertTrue(cert["eligible"])

        asyncio.run(_scenario())

    def test_11_two_layer_canonical_allows_n2n_horizon_probe_blocks_exact_and_microtune(self):
        """[Adversarial 11] 双层等价键：放行合法 N/2N 高原探针，拦截改名重复与相邻窗口微调"""
        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_horizon"
        fields_meta = {
            "f_0": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"},
        }
        svc.init_or_load_campaign("USA", "TOP1000", "adv_h", 1, "news", campaign_name=cid)
        svc.register_hypothesis(
            cid, "HYP_H", "信息扩散具有多周期持续性", "被动基金",
            [{"field_id": "f_0", "role": "Signal_Flow"}],
            ["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
            "若仅单窗有效而配对窗失效则证伪",
            fields_meta=fields_meta,
        )

        # 1. Legal N/2N pair (5d + 21d, ratio 4.2x) MUST PASS!
        pair_vars = [
            {"slot": 1, "hypothesis_ref": "HYP_H", "change_axis": "h_5d", "prediction": "短窗 5日增量捕捉信息扩散初段，预期样本内核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(f_0, 5), subindustry)"},
            {"slot": 2, "hypothesis_ref": "HYP_H", "change_axis": "h_21d", "prediction": "配对 21日形成 N/2N 高原验证，预期维持同号正 Sharpe >= 1.2", "expression": "group_rank(ts_delta(f_0, 21), subindustry)"},
        ]
        res = svc.run_experiment(
            cid, "HYP_H", pair_vars, mode="discovery",
            sim_executor=lambda v, s: {"sharpe": 1.60, "fitness": 1.20, "turnover": 0.25, "margin_bps": 14.0, "checks": [{"name": "OK", "result": "PASS"}]},
            fields_meta=fields_meta,
        )
        self.assertEqual(len(res["results"]), 2)
        self.assertEqual(res["results"][0].get("horizon_verdict"), "PLATEAU")

        # 2. Variable-renamed duplicate of 5d MUST BE REJECTED by Exact Canonical Tabu!
        dup_rename = [{"slot": 1, "hypothesis_ref": "HYP_H", "change_axis": "dup", "prediction": "测试换变量名重复表达式应被精确等价键拦截，预期阻断", "expression": "news_delta = ts_delta(f_0, 5); group_rank(news_delta, subindustry)"}]
        with self.assertRaises(ValueError) as cm_dup:
            svc.run_experiment(cid, "HYP_H", dup_rename, mode="discovery", dry_run=True, fields_meta=fields_meta)
        self.assertIn("Exact Canonical Tabu", str(cm_dup.exception))

        # 3. Adjacent micro-tuning pair (20d vs 21d, ratio 1.05x) MUST BE REJECTED!
        adj_vars = [
            {"slot": 1, "hypothesis_ref": "HYP_H", "change_axis": "m1", "prediction": "测试相邻窗口 20日均值微调，预期被反微调门禁阻断", "expression": "group_neutralize(ts_mean(f_0, 20), subindustry)"},
            {"slot": 2, "hypothesis_ref": "HYP_H", "change_axis": "m2", "prediction": "测试相邻窗口 21日均值微调，与 20日倍率 1.05 应被拦截", "expression": "group_neutralize(ts_mean(f_0, 21), subindustry)"},
        ]
        with self.assertRaises(ValueError) as cm_adj:
            svc.run_experiment(cid, "HYP_H", adj_vars, mode="discovery", dry_run=True, fields_meta=fields_meta)
        self.assertIn("反微调拦截", str(cm_adj.exception))

    def test_12_audit_bus_dual_control_lagged_placebo_corroborates_true_alpha(self):
        """[Adversarial 12] AuditBus 修正双对照符号：真 Alpha 正确判 CORROBORATED，外壳伪影正确判 FALSIFIED"""
        from core.audit_bus import AuditBus, ST_CORROBORATED, ST_FALSIFIED
        from core.falsifiable_probe import materialize, validate_probe

        job = {
            "batch_id": "B00001-dualctrl",
            "batch_seq": 1,
            "spec": {"region": "USA", "universe": "TOP1000", "delay": 1, "neutralization": "SUBINDUSTRY"},
            "hypothesis": {"hypothesis_id": "HYP_DC", "counterparty": "卖方", "causal_chain": "资产扩张被证伪"},
            "field_profiles": {"fnd69_qta": {"domain": "positive", "is_sparse": False, "update_frequency": "quarterly"}},
            "items": [{"slot": 1, "expression": "group_rank(divide(ts_delta(fnd69_qta, 252), ts_mean(fnd69_qta, 252)), industry)"}],
        }
        probe = validate_probe({
            "abstain": False,
            "independent_mechanism": "押注激进扩表被市场证伪杀估值，做空扩表最快组",
            "counterparty": "卖方承销动机资金",
            "mechanism_claim": "公司资产扩张率同比差分机制在行业内排序显著优于裸总资产排序，且依赖当期信息",
            "falsifiable_predictions": [
                {"prediction": "移除差分后表现下降", "falsify_if": "与裸排序无差异"},
                {"prediction": "滞后1年安慰剂失效", "falsify_if": "滞后壳仍高夏普"},
            ],
            "decider": {"metric": "sharpe_2y", "min_delta": 0.30},
        })

        # Case 1: True Alpha (parent=2.00, strip=0.80, lagged_placebo=0.05) -> MUST BE ST_CORROBORATED!
        d1 = os.path.join(self.tmp_dir.name, "ab_true")
        os.makedirs(d1, exist_ok=True)
        m1 = materialize(d1, job, probe)
        self.assertTrue(m1["ok"], m1)
        exprs1 = {e["role"]: e["expression"] for e in m1["entries"]}
        r1_path = os.path.join(d1, "res_true.json")
        with open(r1_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": [
                {"expression": exprs1["parent"], "metrics": {"sharpe": 2.00, "two_year_sharpe": 2.00}},
                {"expression": exprs1["strip"], "metrics": {"sharpe": 0.80, "two_year_sharpe": 0.80}},
                {"expression": exprs1["placebo"], "metrics": {"sharpe": 0.05, "two_year_sharpe": 0.05}},
            ]}, f)
        out1 = AuditBus(d1).record_outcome(m1["run_id"], r1_path)
        self.assertEqual(out1["payload"]["verdict"], ST_CORROBORATED, out1)
        self.assertFalse(out1["payload"]["evidence"]["complexity_artifact"])
        self.assertEqual(out1["payload"]["evidence"]["rule"], "dual_control_lagged_placebo")

        # Case 2: Complexity shell artifact (parent=1.80, strip=0.40, lagged_placebo=1.65) -> MUST BE ST_FALSIFIED!
        d2 = os.path.join(self.tmp_dir.name, "ab_fake")
        os.makedirs(d2, exist_ok=True)
        m2 = materialize(d2, job, probe)
        exprs2 = {e["role"]: e["expression"] for e in m2["entries"]}
        r2_path = os.path.join(d2, "res_fake.json")
        with open(r2_path, "w", encoding="utf-8") as f:
            json.dump({"alpha_results": [
                {"expression": exprs2["parent"], "metrics": {"sharpe": 1.80, "two_year_sharpe": 1.80}},
                {"expression": exprs2["strip"], "metrics": {"sharpe": 0.40, "two_year_sharpe": 0.40}},
                {"expression": exprs2["placebo"], "metrics": {"sharpe": 1.65, "two_year_sharpe": 1.65}},
            ]}, f)
        out2 = AuditBus(d2).record_outcome(m2["run_id"], r2_path)
        self.assertEqual(out2["payload"]["verdict"], ST_FALSIFIED, out2)
        self.assertTrue(out2["payload"]["evidence"]["complexity_artifact"])

    def test_13_holdout_zero_algebraic_leakage_and_fail_closed_missing_yearly(self):
        """[Adversarial 13] 封死 Holdout 代数反推与缺失 yearly_stats 橡皮章放行"""
        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_holdout"
        fields_meta = {
            "f_0": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"},
        }
        svc.init_or_load_campaign("USA", "TOP1000", "adv_ho", 1, "news", campaign_name=cid)
        svc.register_hypothesis(
            cid, "HYP_HO", "跨期舆情变化驱动收益漂移", "被动资金",
            [{"field_id": "f_0", "role": "Signal_Flow"}],
            ["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
            "若核心 8 年无稳健正夏普则证伪",
            fields_meta=fields_meta,
        )

        # 8Y core = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0] -> avg=1.25, trimmed(drop 3.0)=1.00; last 2Y = [2.50, 2.50]; 10Y = 1.50
        yearly_10 = [{"year": 2016 + i, "sharpe": s} for i, s in enumerate([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0, 2.5, 2.5])]
        run_res = svc.run_experiment(
            cid, "HYP_HO",
            [{"slot": 1, "hypothesis_ref": "HYP_HO", "change_axis": "base", "prediction": "预期验证 8 年核心样本内无代数泄露且屏蔽近 2 年检查项，Sharpe >= 1.2", "expression": "group_rank(ts_delta(f_0, 21), subindustry)"}],
            mode="discovery",
            sim_executor=lambda v, s: {
                "alpha_id": "A_HO_LEAK",
                "sharpe": 1.50,
                "fitness": 1.25,
                "turnover": 0.25,
                "margin_bps": 15.0,
                "yearly_stats": yearly_10,
                "two_year_sharpe": 2.50,
                "checks": [
                    {"name": "LOW_2Y_SHARPE", "result": "FAIL"},
                    {"name": "LADDER_SHARPE", "result": "WARNING"},
                    {"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "FAIL"},
                ],
            },
            fields_meta=fields_meta,
        )
        r0 = run_res["results"][0]
        # Cannot reverse-engineer 2Y holdout: no 10Y sharpe, no 2Y fails/warnings!
        self.assertNotIn("sharpe", r0)
        self.assertNotIn("holdout_2y_sharpe", r0)
        self.assertAlmostEqual(r0["is_core_sharpe"], 1.25, places=3)
        self.assertAlmostEqual(r0["trimmed_is_sharpe"], 1.00, places=3)
        self.assertEqual(r0["fail_count"], 1)
        self.assertNotIn("LOW_2Y_SHARPE", str(r0["fails"]))
        self.assertNotIn("LADDER_SHARPE", str(r0["defect_warnings"]))

        # Fail-Closed CERTIFY_ALPHA when yearly_stats is missing!
        cert_missing = svc.request_verdict(
            cid, "CERTIFY_ALPHA",
            alpha_id="A_NO_YEARLY",
            expression="group_rank(ts_delta(f_0, 21), subindustry)",
            sim_result={
                "sharpe": 2.10, "fitness": 1.65, "turnover": 0.22, "margin_bps": 18.0,
                "prod_corr": 0.25, "self_corr": 0.15, "self_corr_verified": True,
                "horizon_verdict": "PLATEAU",
                "checks": [{"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"}],
            },
        )
        self.assertEqual(cert_missing["verdict"], "REJECTED")
        self.assertFalse(cert_missing["eligible"])
        self.assertFalse(cert_missing["holdout"]["holdout_verified"])
        self.assertFalse(cert_missing["holdout"]["holdout_passed"])
        self.assertTrue(any("yearly_stats" in r for r in cert_missing["reasons"]))

    def test_14_settings_last_neutralization_equiv_dedup_surgery_decrowding_and_rag(self):
        """[Adversarial 14] Settings-Last 锁 neutralization + 数学等价去重 + Surgery 对照槽 + ProdCorr 三杠杆 + 1KB RAG + 80% 语义簇覆盖"""
        from core.rag_memory import RAGMemoryEngine

        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_p1"
        fields_meta = {
            "cold_rev_a": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.90, "alpha_count": 2, "semantic_role": "Signal_Flow"},
            "hot_rev_b": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.95, "alpha_count": 500, "semantic_role": "Signal_Flow"},
            "anchor_cap": {"type": "MATRIX", "domain": "positive", "is_sparse": False, "update_frequency": "daily", "coverage": 0.96, "alpha_count": 300, "semantic_role": "Dimension_Anchor"},
        }
        svc.init_or_load_campaign("USA", "TOP1000", "adv_p1", 1, "news", campaign_name=cid)
        svc.register_hypothesis(
            cid, "HYP_P1", "营收变化与行业中性化收益漂移", "被动资金",
            [{"field_id": "hot_rev_b", "role": "Signal_Flow"}],
            ["EXPECTATION_SURPRISE", "RESIDUAL_EXTRACTION"],
            "若核心夏普 < 1.0 则证伪",
            fields_meta=fields_meta,
        )

        # 1. Neutralization smuggling in discovery MUST raise PermissionError!
        with self.assertRaises(PermissionError):
            svc.run_experiment(
                cid, "HYP_P1",
                [{"slot": 1, "hypothesis_ref": "HYP_P1", "change_axis": "neut", "prediction": "偷改 STATISTICAL 应被拦截", "expression": "group_neutralize(ts_delta(hot_rev_b, 21), subindustry)"}],
                mode="discovery", settings={"neutralization": "STATISTICAL"}, dry_run=True, fields_meta=fields_meta,
            )

        # 2. Multi-slot surgery (len=3) without parent_control MUST raise ValueError!
        with self.assertRaises(ValueError) as cm_surg:
            svc.run_experiment(
                cid, "HYP_P1",
                [
                    {"slot": 1, "hypothesis_ref": "HYP_P1", "change_axis": "s1", "prediction": "缺对照槽1", "expression": "group_neutralize(ts_delta(hot_rev_b, 5), subindustry)"},
                    {"slot": 2, "hypothesis_ref": "HYP_P1", "change_axis": "s2", "prediction": "缺对照槽2", "expression": "group_neutralize(ts_delta(cold_rev_a, 5), subindustry)"},
                    {"slot": 3, "hypothesis_ref": "HYP_P1", "change_axis": "s3", "prediction": "缺对照槽3", "expression": "group_rank(ts_delta(cold_rev_a, 21), industry)"},
                ],
                mode="surgery", dry_run=True, fields_meta=fields_meta,
            )
        self.assertIn("parent_control", str(cm_surg.exception))

        # 3. ProdCorr >= 0.65 returns 3-lever de-crowding prescription + unlocks settings_calibration
        disc = svc.run_experiment(
            cid, "HYP_P1",
            [{"slot": 1, "hypothesis_ref": "HYP_P1", "change_axis": "base", "prediction": "预期获得高夏普但高生产相关性并触发三杠杆去拥挤处方反馈", "expression": "group_neutralize(ts_delta(hot_rev_b, 21), subindustry)"}],
            mode="discovery",
            sim_executor=lambda v, s: {
                "alpha_id": "A_CROWDED", "sharpe": 1.75, "fitness": 1.30, "turnover": 0.25, "margin_bps": 16.0,
                "prod_corr": 0.78, "checks": [{"name": "OK", "result": "PASS"}],
            },
            fields_meta=fields_meta,
        )
        rx = disc["results"][0].get("de_crowding_prescription")
        self.assertIsNotNone(rx)
        self.assertEqual(len(rx["levers"]), 3)
        self.assertTrue(any(f["field_id"] == "cold_rev_a" for f in rx["levers"][0]["suggested_cold_fields"]))

        # 4. Mathematically equivalent outer neutralization (MARKET vs SUBINDUSTRY on inner group_neutralize(..., subindustry)) MUST BE BLOCKED!
        with self.assertRaises(ValueError) as cm_eq:
            svc.run_experiment(
                cid, "HYP_P1",
                [{"slot": 1, "hypothesis_ref": "HYP_P1", "change_axis": "redundant_neut", "prediction": "测试内层已做 subindustry 中性化时外层切换 MARKET 应被等价拦截", "expression": "group_neutralize(ts_delta(hot_rev_b, 21), subindustry)"}],
                mode="settings_calibration", settings={"decay": 0, "truncation": 0.025, "neutralization": "MARKET"},
                dry_run=True, fields_meta=fields_meta,
            )
        self.assertIn("Settings 等价冗余拦截", str(cm_eq.exception))

        # 5. RAGMemoryEngine no longer dumps 16.1KB operator menu!
        pyr_ctx = RAGMemoryEngine.load_pyramid_context("USA", 1, "other", dgp_signatures=[])
        self.assertIn("Authorized Operators (104 SSOT)", pyr_ctx)
        self.assertNotIn("ts_decay_exp_window(x, d", pyr_ctx)
        self.assertLess(len(pyr_ctx.encode("utf-8")), 4500, f"金字塔上下文不应再倾倒 16KB 算子表，实测 {len(pyr_ctx.encode('utf-8'))} 字节")

        # 6. Exhaustion gate enforces >= 80% semantic cluster coverage!
        exh_low_cov = AntiLazinessAuditor.evaluate_exhaustion_gate(
            {
                "orthogonal_hypotheses_count": 5,
                "mechanism_families_covered": ["SMOOTH", "DIFF", "NORM", "RANK"],
                "distinct_core_skeletons_count": 20,
                "open_near_miss_leads": [],
                "semantic_clusters_total": 4,
                "semantic_clusters_tested": 2,
                "semantic_cluster_coverage": 0.50,
            },
            effective_rank=2.0,
            has_vector_fields=False,
        )
        self.assertFalse(exh_low_cov["allowed"])
        self.assertTrue(any("语义簇覆盖率" in m for m in exh_low_cov["missing_requirements"]))

    def test_15_snc_blocks_single_line_wrapper_and_overstuffed_rhs(self):
        """[Adversarial 15] 封死 SNC 1 行包壳伪多行与单行塞入 4+ 嵌套算子绕过"""
        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_snc_wrap"
        fields_meta = {
            "f_0": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"},
        }
        svc.init_or_load_campaign("USA", "TOP1000", "adv_snc_w", 1, "news", campaign_name=cid)
        svc.register_hypothesis(
            cid, "HYP_W", "机构关注度聚集引发跨周截面重估与再平衡溢价", "反应滞后的被动基金",
            [{"field_id": "f_0", "role": "Signal_Flow"}],
            ["TEMPORAL_DECAY", "CROSS_SECTIONAL_RELATIVE"],
            "若 21日衰减截面中性化无正夏普则证伪",
            fields_meta=fields_meta,
        )

        # 1. Single-assignment wrapper around 6-op nested spaghetti MUST BE BLOCKED!
        sneaky_1 = (
            "news_tone_neut = group_neutralize(winsorize(zscore(ts_decay_linear(ts_delta(ts_mean(f_0, 5), 10), 21)), std=4), subindustry);\n"
            "news_tone_neut"
        )
        res_1 = validate_snc(sneaky_1, require_snc_when_complex=True)
        self.assertFalse(res_1["passed"])
        self.assertTrue(any("SNC-CollapsedStep" in v for v in res_1["violations"]), res_1["violations"])
        with self.assertRaises(ValueError) as cm1:
            svc.run_experiment(
                cid, "HYP_W",
                [{"slot": 1, "hypothesis_ref": "HYP_W", "change_axis": "wrap1", "prediction": "测试单行包壳伪多行必须被 SNC-CollapsedStep 拦截", "expression": sneaky_1}],
                mode="discovery", dry_run=True, fields_meta=fields_meta,
            )
        self.assertIn("SNC-CollapsedStep", str(cm1.exception))

        # 2. Two-assignment cheat where line 2 still stuffs 5 nested ops MUST BE BLOCKED!
        sneaky_2 = (
            "news_tone_ema = ts_mean(f_0, 5);\n"
            "news_tone_neut = group_neutralize(winsorize(zscore(ts_decay_linear(ts_delta(news_tone_ema, 10), 21)), std=4), subindustry);\n"
            "news_tone_neut"
        )
        res_2 = validate_snc(sneaky_2, require_snc_when_complex=True)
        self.assertFalse(res_2["passed"])
        self.assertTrue(any("SNC-CollapsedStep" in v for v in res_2["violations"]), res_2["violations"])

        # 3. Genuine multi-step SNC decomposition (each RHS <= 3 ops, >= 2 assignments) MUST PASS!
        clean_snc = (
            "news_tone_diff = ts_delta(ts_mean(f_0, 5), 10);\n"
            "news_tone_ema = ts_decay_linear(news_tone_diff, 21);\n"
            "news_tone_norm = winsorize(zscore(news_tone_ema), std=4);\n"
            "news_tone_neut = group_neutralize(news_tone_norm, subindustry);\n"
            "news_tone_neut"
        )
        self.assertTrue(validate_snc(clean_snc, require_snc_when_complex=True)["passed"])
        ok = svc.run_experiment(
            cid, "HYP_W",
            [{"slot": 1, "hypothesis_ref": "HYP_W", "change_axis": "clean_snc", "prediction": "规范多步 SNC 拆解应通过编译门禁并预期稳定夏普", "expression": clean_snc}],
            mode="discovery", dry_run=True, fields_meta=fields_meta,
        )
        self.assertEqual(ok["validated_count"], 1)

    def test_16_live_single_chunk_real_brain_signature_and_corr_busy_retry(self):
        """[Adversarial 16] 实盘 n=1/5 契约匹配真实 brain-mcp create_simulation 关键字签名 + 相对 URL + correlation_busy 重试"""
        import asyncio
        import inspect
        import types
        from core.sim_runner import get_brain_module

        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "USA_adv_single_sig"
        fields_meta = {
            f"sig_f_{i}": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.9, "semantic_role": "Signal_Flow"}
            for i in range(6)
        }
        single_calls = []
        multi_calls = []
        corr_calls = {"n": 0}
        polled_urls = []

        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload
                self.headers = {"Retry-After": "0"}
            def json(self):
                return self._payload

        class _FakeClient:
            base_url = "https://api.worldquantbrain.com"
            async def _request(self, method, url):
                polled_urls.append(url)
                self.assert_no_double = "/simulations/simulations/" not in url
                if not self.assert_no_double:
                    raise AssertionError(f"URL 拼接重复了 /simulations/: {url}")
                if "/multi/" in url:
                    kids = url.rsplit("/", 1)[-1].split("__")
                    return _FakeResp({"status": "COMPLETE", "children": [f"/simulations/child/{k}" for k in kids]})
                if "/single/" in url:
                    aid = url.rsplit("/", 1)[-1]
                    return _FakeResp({"status": "COMPLETE", "alpha": aid})
                if "/child/" in url:
                    aid = url.rsplit("/", 1)[-1]
                    return _FakeResp({"status": "COMPLETE", "alpha": aid})
                return _FakeResp({"status": "COMPLETE"})

        # Exact signature matching real brain-mcp/main.py create_simulation!
        async def _real_sig_create_simulation(
            type: str = "REGULAR",
            region: str = "USA",
            universe: str = "TOP3000",
            delay: int = 1,
            decay: int = 4,
            neutralization: str = "SUBINDUSTRY",
            truncation: float = 0.08,
            test_period: str = "P0Y0M",
            nan_handling: str = "ON",
            alpha_expression: str = None,
            pasteurization: str = "ON",
        ):
            assert isinstance(type, str), f"type 必须是 str，不能是 {type.__class__}"
            assert isinstance(alpha_expression, str) and len(alpha_expression) > 0
            single_calls.append({"region": region, "universe": universe, "delay": delay, "decay": decay, "neutralization": neutralization, "truncation": truncation, "alpha_expression": alpha_expression})
            return {"success": True, "id": f"S_{len(single_calls)}", "location": f"/simulations/single/SINGLE_A_{len(single_calls)}"}

        # Cross-verify our fake signature matches real brain-mcp if present in workspace
        real_bm = get_brain_module()
        if real_bm is not None and hasattr(real_bm, "create_simulation"):
            real_params = set(inspect.signature(real_bm.create_simulation).parameters.keys())
            fake_params = set(inspect.signature(_real_sig_create_simulation).parameters.keys())
            self.assertTrue(fake_params.issubset(real_params), f"签名偏离真实 brain-mcp: {fake_params - real_params}")

        async def _create_multi_simulation(items):
            assert 2 <= len(items) <= 8
            multi_calls.append(len(items))
            aids = [f"MULTI_A_{len(multi_calls)}_{i+1}" for i in range(len(items))]
            return {"location": f"/simulations/multi/{'__'.join(aids)}"}

        async def _get_alpha_details(aid):
            return {
                "id": aid,
                "is": {
                    "sharpe": 1.92, "fitness": 1.48, "turnover": 0.24, "margin": 0.0016,
                    "checks": [{"name": "LOW_SUB_UNIVERSE_SHARPE", "result": "PASS"}],
                },
                "settings": {"decay": 0, "truncation": 0.025, "neutralization": "SUBINDUSTRY"},
            }

        async def _get_alpha_yearly_stats(aid):
            return {"records": [[2016 + i, 100.0, 1e6, 400, 400, 0.24, 1.88] for i in range(10)]}

        async def _check_self_correlation(aid, threshold=0.7):
            return {"alpha_id": aid, "max_correlation": 0.14, "passes_check": True}

        async def _check_correlation(aid):
            corr_calls["n"] += 1
            if corr_calls["n"] == 1:
                return {"status": "pending", "checks": {"production": {"max_correlation": None, "status": "pending"}}}
            if corr_calls["n"] == 2:
                return {"status": "correlation_busy", "retry_after": 0.01, "checks": {"production": {"max_correlation": None, "status": "correlation_busy"}}}
            return {"alpha_id": aid, "checks": {"production": {"max_correlation": 0.29, "passes_check": True}, "self": {"max_correlation": 0.14, "passes_check": True}}}

        fake_bm = types.SimpleNamespace(
            brain_client=_FakeClient(),
            create_simulation=_real_sig_create_simulation,
            create_multi_simulation=_create_multi_simulation,
            get_alpha_details=_get_alpha_details,
            get_alpha_yearly_stats=_get_alpha_yearly_stats,
            check_self_correlation=_check_self_correlation,
            check_correlation=_check_correlation,
        )

        async def _scenario():
            with mock.patch("core.research_service.get_brain_module", return_value=fake_bm), \
                 mock.patch.object(svc, "_resolve_fields", return_value={k: HypothesisSpec.normalize_field_profile(k, v) for k, v in fields_meta.items()}), \
                 mock.patch.dict(os.environ, {"AEGIS_LIVE_POLL_MIN_SEC": "0.01", "AEGIS_LIVE_RETRY_BACKOFF_SEC": "0.01"}):
                await svc.init_or_load_campaign_async("USA", "TOP1000", "sig_ds", 1, "news", campaign_name=cid)
                svc.register_hypothesis(
                    cid, "HYP_SIG", "多字段情绪扩散引发跨周动量重估", "滞后被动基金",
                    [{"field_id": "sig_f_0", "role": "Signal_Flow"}],
                    ["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
                    "若 5d/21d 均无显著正夏普则证伪",
                    fields_meta=fields_meta,
                )
                # Batch of 5 variants -> chunks [4, 1] -> exercises BOTH create_multi_simulation AND real-sig create_simulation!
                five_vars = [
                    {"slot": 1, "hypothesis_ref": "HYP_SIG", "change_axis": "h5", "prediction": "5日增量捕捉短窗动量，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(sig_f_0, 5), subindustry)"},
                    {"slot": 2, "hypothesis_ref": "HYP_SIG", "change_axis": "h21", "prediction": "21日高原配对与 5日同号持续，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(sig_f_0, 21), subindustry)"},
                    {"slot": 3, "hypothesis_ref": "HYP_SIG", "change_axis": "f1", "prediction": "正交字段 1 验证，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(sig_f_1, 21), subindustry)"},
                    {"slot": 4, "hypothesis_ref": "HYP_SIG", "change_axis": "f2", "prediction": "正交字段 2 验证，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(sig_f_2, 21), subindustry)"},
                    {"slot": 5, "hypothesis_ref": "HYP_SIG", "change_axis": "f3_single_chunk", "prediction": "第 5 条落入单槽分块，检验 create_simulation 关键字签名，预期正常回测", "expression": "group_rank(ts_delta(sig_f_3, 21), subindustry)"},
                ]
                res5 = await svc.run_experiment_async(cid, "HYP_SIG", five_vars, mode="discovery", dry_run=False)
                self.assertEqual(len(res5["results"]), 5)
                self.assertEqual(multi_calls, [4])
                self.assertEqual(len(single_calls), 1)
                self.assertEqual(single_calls[0]["alpha_expression"], "group_rank(ts_delta(sig_f_3, 21), subindustry)")
                self.assertEqual(res5["results"][4]["alpha_id"], "SINGLE_A_1")
                # Also verify correlation_busy/pending retried until 0.29 succeeded!
                self.assertGreaterEqual(corr_calls["n"], 3)
                self.assertAlmostEqual(res5["results"][0]["prod_corr"], 0.29, places=2)
                self.assertTrue(all("/simulations/simulations/" not in u for u in polled_urls))

        asyncio.run(_scenario())

    def test_17_targeted_alpha_id_hydration_and_research_tree_holdout_mask(self):
        """[Adversarial 17] 情况 2 指定 seed_alpha_id 自动水合真实设置/法医病灶 + RESEARCH_TREE.md 零 Holdout fail_count 泄露"""
        import asyncio
        import types

        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        fields_meta = {
            "f_seed": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.92, "alpha_count": 200, "semantic_role": "Signal_Flow"},
            "f_cold": {"type": "MATRIX", "domain": "unbounded", "is_sparse": False, "update_frequency": "daily", "coverage": 0.88, "alpha_count": 3, "semantic_role": "Signal_Flow"},
        }

        async def _get_alpha_details(aid):
            return {
                "id": aid,
                "regular": {"code": "group_rank(ts_decay_linear(f_seed, 21), industry)"},
                "settings": {
                    "region": "USA", "universe": "TOP1000", "delay": 1,
                    "decay": 4, "truncation": 0.08, "neutralization": "INDUSTRY", "nanHandling": "ON",
                },
                "is": {
                    "sharpe": 1.48, "fitness": 1.12, "turnover": 0.28, "margin": 0.0014,
                    "checks": [
                        {"name": "LOW_SHARPE", "result": "FAIL"},
                        {"name": "CONCENTRATED_WEIGHT", "result": "WARNING"},
                        {"name": "MATCHES_THEMES", "result": "WARNING"},
                    ],
                },
            }

        async def _get_alpha_yearly_stats(aid):
            return {"records": [[2016 + i, 100.0, 1e6, 420, 410, 0.28, 1.45] for i in range(10)]}

        async def _check_correlation(aid):
            return {"alpha_id": aid, "checks": {"production": {"max_correlation": 0.74, "passes_check": False}, "self": {"max_correlation": 0.20, "passes_check": True}}}

        async def _check_self_correlation(aid, threshold=0.7):
            return {"alpha_id": aid, "max_correlation": 0.20, "passes_check": True}

        fake_bm = types.SimpleNamespace(
            get_alpha_details=_get_alpha_details,
            get_alpha_yearly_stats=_get_alpha_yearly_stats,
            check_correlation=_check_correlation,
            check_self_correlation=_check_self_correlation,
        )

        async def _scenario():
            with mock.patch("core.research_service.get_brain_module", return_value=fake_bm), \
                 mock.patch.object(aegis_mcp_server, "_SERVICE", svc), \
                 mock.patch.object(svc, "_resolve_fields", return_value={k: HypothesisSpec.normalize_field_profile(k, v) for k, v in fields_meta.items()}):
                # 1. MCP init_or_load_campaign with ONLY seed_alpha_id + dataset_id (auto-fills region/universe/delay + settings + diagnosis!)
                init_raw = await aegis_mcp_server.mcp.call_tool(
                    "init_or_load_campaign",
                    {"seed_alpha_id": "TARGET_ALPHA_777", "dataset_id": "seed_ds_test", "category": "news"},
                )
                init_res = json.loads(init_raw[0][0].text) if isinstance(init_raw, tuple) else json.loads(init_raw[0].text)
                self.assertEqual(init_res["mode"], "TARGETED_OPTIMIZATION")
                self.assertEqual(init_res["scope_lock"]["region"], "USA")
                self.assertEqual(init_res["scope_lock"]["universe"], "TOP1000")
                diag = init_res.get("seed_diagnosis")
                self.assertIsNotNone(diag)
                self.assertEqual(diag["settings"]["decay"], 4)
                self.assertEqual(diag["settings"]["neutralization"], "INDUSTRY")
                self.assertTrue(diag["parent_eligible_for_calibration"])
                self.assertIsNotNone(diag.get("de_crowding_prescription"))
                self.assertIn("CONCENTRATED_WEIGHT", diag["defect_warnings"])

                cid = init_res["campaign_id"]
                svc.register_hypothesis(
                    cid, "HYP_SURG_SEED", "用低拥挤冷字段替代原高相关主锚并保留连续幅度", "滞后被动基金",
                    [{"field_id": "f_cold", "role": "Signal_Flow"}],
                    ["TEMPORAL_DECAY", "CROSS_SECTIONAL_RELATIVE"],
                    "若手术后核心 Sharpe 未提升或仍拥挤则证伪",
                    parent_alpha_id="TARGET_ALPHA_777",
                    fields_meta=fields_meta,
                )

                # 2. Surgery with seed alpha's REAL baseline settings (decay=4, truncation=0.08, neutralization=INDUSTRY) MUST SUCCEED!
                surg_res = await svc.run_experiment_async(
                    cid, "HYP_SURG_SEED",
                    [{
                        "slot": 1, "hypothesis_ref": "HYP_SURG_SEED", "change_axis": "cold_replace",
                        "prediction": "切换冷字段并沿用母本真实 decay=4/INDUSTRY 基线，预期降相关且核心 Sharpe >= 1.4",
                        "expression": "group_neutralize(ts_decay_linear(f_cold, 21), industry)",
                    }],
                    mode="surgery",
                    settings={"decay": 4, "truncation": 0.08, "neutralization": "INDUSTRY"},
                    sim_executor=lambda v, s: {
                        "alpha_id": "SURG_CHILD_01",
                        "sharpe": 1.55, "fitness": 1.25, "turnover": 0.25, "margin_bps": 15.0,
                        "yearly_stats": [{"year": 2016 + i, "sharpe": 1.40} for i in range(8)] + [{"year": 2024, "sharpe": 0.30}, {"year": 2025, "sharpe": 0.40}],
                        "checks": [{"name": "LOW_SHARPE", "result": "PASS"}, {"name": "LOW_2Y_SHARPE", "result": "FAIL"}],
                    },
                    fields_meta=fields_meta,
                )
                # 3. Verify NEITHER agent_item NOR RESEARCH_TREE.md leaks LOW_2Y_SHARPE fail_count!
                ar = surg_res["results"][0]
                self.assertEqual(ar["fail_count"], 0)
                self.assertEqual(ar["status"], "NEAR_MISS")
                with open(init_res["research_tree_path"], "r", encoding="utf-8") as tf:
                    tree_txt = tf.read()
                row_line = [ln for ln in tree_txt.splitlines() if "SURG_CHILD_01" in ln][0]
                self.assertIn("| 0/0 |", row_line, f"RESEARCH_TREE.md 不应泄露 LOW_2Y_SHARPE 的 fail_count: {row_line}")
                self.assertNotIn("0.30", tree_txt)
                self.assertNotIn("1.55", tree_txt)

                # 4. settings_calibration unlocked immediately from hydrated seed_sharpe=1.48 >= 1.25!
                cal_dry = await svc.run_experiment_async(
                    cid, "HYP_SURG_SEED",
                    [{
                        "slot": 1, "hypothesis_ref": "HYP_SURG_SEED", "change_axis": "decay_6",
                        "prediction": "校准 decay=6 压降换手，预期保持核心夏普且通过全部检查",
                        "expression": "group_rank(ts_decay_linear(f_seed, 21), industry)",
                    }],
                    mode="settings_calibration",
                    settings={"decay": 6, "truncation": 0.08, "neutralization": "INDUSTRY"},
                    dry_run=True,
                    fields_meta=fields_meta,
                )
                self.assertEqual(cal_dry["validated_count"], 1)

        asyncio.run(_scenario())

    def test_18_async_enqueue_resume_compact_summary_holdout_and_hygiene(self):
        """[Adversarial 18] MCP 极速入队 + 断点续传不重发 + 幂等收割 + <1KB 脱敏关键摘要 + 零碎片三文件卫生"""
        import asyncio
        import types

        svc = ResearchService(workspace_root=self.root_dir, campaigns_root=self.tmp_dir.name)
        cid = "GLB_async_queue_e2e"
        fields_meta = {
            f"earn_f_{i}": {
                "type": "MATRIX", "domain": "unbounded", "is_sparse": False,
                "update_frequency": "daily", "coverage": 0.90, "alpha_count": i * 20, "semantic_role": "Signal_Flow",
            }
            for i in range(6)
        }

        submitted_locations = []
        poll_fail_once = {"triggered": False}

        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload
                self.headers = {"Retry-After": "0"}
            def json(self):
                return self._payload

        class _FakeClient:
            base_url = "https://api.worldquantbrain.com"
            async def _request(self, method, url):
                if "/multi/chunk_resume_test" in url and not poll_fail_once["triggered"]:
                    poll_fail_once["triggered"] = True
                    raise RuntimeError("simulated network drop mid-poll")
                if "/multi/" in url:
                    raw_tail = url.rsplit("/", 1)[-1]
                    kids = raw_tail.replace("chunk_resume_test__", "").split("__")
                    return _FakeResp({"status": "COMPLETE", "children": [f"/simulations/child/{k}" for k in kids]})
                if "/child/" in url:
                    aid = url.rsplit("/", 1)[-1]
                    return _FakeResp({"status": "COMPLETE", "alpha": aid})
                return _FakeResp({"status": "COMPLETE"})

        async def _create_multi_simulation(items):
            assert 2 <= len(items) <= 4
            idx = len(submitted_locations) + 1
            aids = [f"Q_ALPHA_{idx}_{k+1}" for k in range(len(items))]
            prefix = "chunk_resume_test__" if idx == 2 else ""
            loc = f"/simulations/multi/{prefix}{'__'.join(aids)}"
            submitted_locations.append(loc)
            return {"location": loc}

        async def _get_alpha_details(aid):
            return {
                "id": aid,
                "is": {
                    "sharpe": 1.88, "fitness": 1.44, "turnover": 0.23, "margin": 0.0017,
                    "longCount": 420, "shortCount": 410,
                    "checks": [
                        {"name": "LOW_SHARPE", "result": "PASS"},
                        {"name": "LOW_2Y_SHARPE", "result": "FAIL"},
                    ],
                },
                "settings": {"decay": 0, "truncation": 0.025, "neutralization": "SUBINDUSTRY"},
            }

        async def _get_alpha_yearly_stats(aid):
            # 8Y core = 1.65, 2Y holdout = 0.50 (must NOT leak in compact summary!)
            return {
                "records": (
                    [[2016 + i, 100.0, 1e6, 400, 400, 0.23, 1.65] for i in range(8)]
                    + [[2024, 10.0, 1e6, 400, 400, 0.23, 0.50], [2025, 10.0, 1e6, 400, 400, 0.23, 0.50]]
                )
            }

        async def _get_alpha_pnl(aid):
            seed = sum(ord(c) for c in aid)
            rng = np.random.default_rng(seed)
            cum = np.cumsum(rng.normal(0.01, 1.0, 40)).tolist()
            return {"records": [[f"2024-01-{i+1:02d}", v] for i, v in enumerate(cum)]}

        async def _check_self_correlation(aid, threshold=0.7):
            return {"alpha_id": aid, "max_correlation": 0.16, "passes_check": True}

        async def _check_correlation(aid):
            pcorr = 0.76 if aid.endswith("_1") else 0.28
            return {"alpha_id": aid, "checks": {"production": {"max_correlation": pcorr, "passes_check": pcorr < 0.7}, "self": {"max_correlation": 0.16, "passes_check": True}}}

        fake_bm = types.SimpleNamespace(
            brain_client=_FakeClient(),
            create_multi_simulation=_create_multi_simulation,
            get_alpha_details=_get_alpha_details,
            get_alpha_yearly_stats=_get_alpha_yearly_stats,
            get_alpha_pnl=_get_alpha_pnl,
            check_self_correlation=_check_self_correlation,
            check_correlation=_check_correlation,
        )

        async def _scenario():
            with mock.patch("core.research_service.get_brain_module", return_value=fake_bm), \
                 mock.patch.object(aegis_mcp_server, "_SERVICE", svc), \
                 mock.patch.object(svc, "_resolve_fields", return_value={k: HypothesisSpec.normalize_field_profile(k, v) for k, v in fields_meta.items()}), \
                 mock.patch.dict(os.environ, {"AEGIS_LIVE_INITIAL_WAIT_SEC": "0.0", "AEGIS_LIVE_POLL_MIN_SEC": "0.01", "AEGIS_LIVE_RETRY_BACKOFF_SEC": "0.01"}):
                await aegis_mcp_server.mcp.call_tool(
                    "init_or_load_campaign",
                    {"region": "GLB", "universe": "MINVOL1M", "dataset_id": "earnings6_q", "delay": 1, "category": "earnings", "campaign_name": cid},
                )

                # 1. Non-blocking MCP profile_dataset(use_live_probe=True, enqueue=True) returns QUEUED in <1s!
                p_raw = await aegis_mcp_server.mcp.call_tool(
                    "profile_dataset",
                    {"campaign_id": cid, "use_live_probe": True, "enqueue": True},
                )
                p_q = json.loads(p_raw[0][0].text) if isinstance(p_raw, tuple) else json.loads(p_raw[0].text)
                self.assertEqual(p_q["status"], "QUEUED")
                self.assertIn("cli run-job", p_q["cli_command"])
                # Directory hygiene strictly clean (still only 3 files!)
                cdir = os.path.join(self.tmp_dir.name, cid)
                self.assertTrue(check_directory_hygiene(cdir)["clean"])

                # Run queued probe job silently -> upgrades C_eff to pnl_series_eigen and returns compact summary!
                submitted_locations.clear()
                poll_fail_once["triggered"] = True  # no crash during probe
                p_done = await svc.execute_job_async(cid, p_q["job_id"], compact=True)
                self.assertEqual(p_done["status"], "COMPLETED")
                self.assertEqual(p_done["method"], "pnl_series_eigen")
                self.assertGreater(len(p_done["measured"]), 0)

                # 2. Register hypothesis and enqueue 6 variants (2 chunks: 4 + 2) via MCP!
                await aegis_mcp_server.mcp.call_tool(
                    "register_hypothesis",
                    {
                        "campaign_id": cid,
                        "hypothesis_id": "HYP_Q",
                        "economic_mechanism": "财报预期扩散滞后引发跨周相对重估溢价",
                        "counterparty": "反应滞后的全球被动配置资金",
                        "field_roles": [{"field_id": "earn_f_0", "role": "Signal_Flow"}],
                        "mechanism_intents": ["EXPECTATION_SURPRISE", "CROSS_SECTIONAL_RELATIVE"],
                        "falsification_criterion": "若 5d/21d 均无显著正夏普则证伪",
                    },
                )
                six_vars = [
                    {"slot": 1, "hypothesis_ref": "HYP_Q", "change_axis": "h5", "prediction": "5日增量捕捉反应不足，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(earn_f_0, 5), subindustry)"},
                    {"slot": 2, "hypothesis_ref": "HYP_Q", "change_axis": "h21", "prediction": "21日高原配对与 5日同号持续，预期核心 Sharpe >= 1.2", "expression": "group_rank(ts_delta(earn_f_0, 21), subindustry)"},
                    {"slot": 3, "hypothesis_ref": "HYP_Q", "change_axis": "f1", "prediction": "正交字段 1 检验，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(earn_f_1, 21), subindustry)"},
                    {"slot": 4, "hypothesis_ref": "HYP_Q", "change_axis": "f2", "prediction": "正交字段 2 检验，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(earn_f_2, 21), subindustry)"},
                    {"slot": 5, "hypothesis_ref": "HYP_Q", "change_axis": "f3", "prediction": "正交字段 3 检验，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(earn_f_3, 21), subindustry)"},
                    {"slot": 6, "hypothesis_ref": "HYP_Q", "change_axis": "f4", "prediction": "正交字段 4 检验，预期核心 Sharpe >= 1.0", "expression": "group_rank(ts_delta(earn_f_4, 21), subindustry)"},
                ]
                e_raw = await aegis_mcp_server.mcp.call_tool(
                    "run_experiment",
                    {"campaign_id": cid, "hypothesis_id": "HYP_Q", "variants": six_vars, "mode": "discovery", "enqueue": True},
                )
                e_q = json.loads(e_raw[0][0].text) if isinstance(e_raw, tuple) else json.loads(e_raw[0].text)
                self.assertEqual(e_q["status"], "QUEUED")
                self.assertEqual(e_q["variant_count"], 6)
                self.assertEqual(e_q["chunk_count"], 2)

                # Duplicate in-flight enqueue of the same expression MUST BE BLOCKED!
                with self.assertRaises(ValueError) as cm_dup_q:
                    await svc.run_experiment_async(cid, "HYP_Q", [six_vars[0]], mode="discovery", enqueue=True)
                self.assertIn("Exact Canonical Tabu", str(cm_dup_q.exception))

                # 3. Execute job: chunk 1 completes, chunk 2 submits then crashes mid-poll -> resume MUST NOT re-submit!
                submitted_locations.clear()
                poll_fail_once["triggered"] = False
                with self.assertRaises(RuntimeError):
                    await svc.execute_job_async(cid, e_q["job_id"], compact=True)
                self.assertEqual(len(submitted_locations), 2)

                # Resume same job -> finishes cleanly with ZERO extra submissions!
                summary_1 = await svc.execute_job_async(cid, e_q["job_id"], compact=True)
                self.assertEqual(len(submitted_locations), 2, "断点续传不得重复向 BRAIN 提交已入队分块！")
                self.assertEqual(summary_1["status"], "COMPLETED")
                self.assertTrue(summary_1["holdout_masked"])
                self.assertEqual(len(summary_1["results"]), 6)
                self.assertEqual(summary_1["results"][0].get("hv"), "PLATEAU")
                # Verify strict Holdout masking & compact < 1KB payload!
                compact_bytes = len(json.dumps(summary_1, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                self.assertLess(compact_bytes, 1024, f"6 槽精简摘要必须 < 1KB，实测 {compact_bytes} 字节")
                for row in summary_1["results"]:
                    self.assertNotIn("sh", row)
                    self.assertNotIn("h2y", row)
                    self.assertNotIn("LOW_2Y_SHARPE", row.get("fails", []))
                    self.assertAlmostEqual(row["is_core"], 1.65, places=2)

                # 4. Idempotent re-run of completed job -> returns cached summary with 0 BRAIN calls & 0 duplicate rows!
                summary_2 = await svc.execute_job_async(cid, e_q["job_id"], compact=True)
                self.assertEqual(summary_2, summary_1)
                self.assertEqual(len(submitted_locations), 2)
                self.assertEqual(svc.campaign_status(cid)["summary"]["total_experiments"], 6)
                self.assertTrue(check_directory_hygiene(cdir)["clean"])

                # 5. Subprocess CLI `jobs` & idempotent `run-job` return clean compact JSON on stdout!
                p_jobs = subprocess.run(
                    [sys.executable, os.path.join(self.root_dir, "aegis_mcp_server.py"), "cli", "jobs", "--campaign", cid, "--campaigns-root", self.tmp_dir.name],
                    capture_output=True, text=True, check=True,
                )
                j_list = json.loads(p_jobs.stdout)
                self.assertEqual(j_list["count"], 2)

                p_rj = subprocess.run(
                    [sys.executable, os.path.join(self.root_dir, "aegis_mcp_server.py"), "cli", "run-job", "--campaign", cid, "--job", e_q["job_id"], "--campaigns-root", self.tmp_dir.name],
                    capture_output=True, text=True, check=True,
                )
                rj_out = json.loads(p_rj.stdout)
                self.assertEqual(rj_out["status"], "COMPLETED")
                self.assertLess(len(p_rj.stdout.encode("utf-8")), 1024)

        asyncio.run(_scenario())


if __name__ == "__main__":
    unittest.main()
