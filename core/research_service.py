"""
core/research_service.py
AEGIS V4.1.1 宿主驱动核心服务层 (Host-Driven Stateful Research Service)

核心约束与闭环保证:
1. 宿主状态真源: 全部依托 CampaignStore (campaign.db + RESEARCH_TREE.md + certified_champions.json);
2. Scope Lock: region / universe / delay / dataset_id 在 init_or_load_campaign 后不可篡改;
3. 静态零缺陷门禁: FastExpr AST (强制多行 SNC 编译门禁 + 离散晶格 + 104 SSOT) + DimensionAuditor + 双层正则去重 + 反微调 + Surgery 对照槽 + RedTeam;
4. 弹性并发 & Expression-First Settings-Last: discovery(1~20), surgery(1~8), settings_calibration(1~4 且需父本 |Sharpe|>=1.25)，全锁 decay/truncation/neutralization 与数学等价 Settings 去重;
5. Holdout 彻底防泄漏 + Fail-Closed 复核: discovery/surgery 严禁返回 10 年全局 sharpe 与 2Y/LADDER 检查项，仅返回 8Y is_core_sharpe + trimmed_is_sharpe；CERTIFY_ALPHA 缺少真实 yearly_stats 必拒签;
6. 完整实盘证据闭环: <=4 分块并发 + CANCELLED 退避重试 + 自动拉取 yearly_stats / check_correlation / check_self_correlation / 跨批 HorizonProbe 高原验证;
7. C_eff + 语义簇覆盖率 80% 科学穷尽裁决 + ProdCorr >= 0.65 三杠杆去拥挤诊断反馈。
"""
from __future__ import annotations

import ast
import asyncio
import concurrent.futures
import inspect
import json
import math
import os
import re
import sys
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, TypeVar

import numpy as np

from core.anti_laziness import AntiLazinessAuditor
from core.campaign_store import CampaignStore, check_directory_hygiene
from core.dgp_schema import HypothesisSpec
from core.dimension_rules import DimensionAuditor
from core.fastexpr_ast import (
    OP_FAMILY_MAP,
    build_named_ablation_and_placebo,
    exact_canonical_key,
    extract_all_windows,
    parse_fastexpr,
    topology_equivalence_key,
)
from core.field_resolver import DatasetFieldResolver
from core.func_call_corrector import ASTSandboxCorrector
from core.gatekeeper import Gatekeeper
from core.horizon_probe import HorizonProbe
from core.operator_registry import OperatorRegistry
from core.production_gate import ProductionGate
from core.red_team import DoubleBlindRedTeam
from core.sim_runner import get_brain_module


T = TypeVar("T")

DEFAULT_DISCOVERY_SETTINGS: Dict[str, Any] = {
    "decay": 0,
    "truncation": 0.025,
    "neutralization": "SUBINDUSTRY",
    "nanHandling": "ON",
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
}

MODE_BATCH_LIMITS: Dict[str, Tuple[int, int]] = {
    "discovery": (1, 20),
    "surgery": (1, 8),
    "settings_calibration": (1, 4),
}

NEUTRALIZATION_HIERARCHY: Dict[str, int] = {
    "NONE": 0,
    "MARKET": 1,
    "COUNTRY": 2,
    "SECTOR": 3,
    "INDUSTRY": 4,
    "SUBINDUSTRY": 5,
}

GROUP_NEUT_OPS: Set[str] = {
    "group_neutralize",
    "group_zscore",
    "group_normalize",
    "group_scale",
    "group_rank",
}

HOLDOUT_LEAK_KEYWORDS: Tuple[str, ...] = ("2Y", "TWO_YEAR", "LADDER", "RECENT")
LIVE_CHUNK_SIZE = 4
MAX_TOPOLOGY_CAMPAIGN_WINDOWS = 4
MAX_WINDOW_ONLY_RATIO = 0.10


def _run_coro_sync(coro: Coroutine[Any, Any, T]) -> T:
    """在任意同步或已有运行事件循环的上下文中安全执行协程（彻底消除 asyncio.run 冲突）。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _join_sim_url(base_url: str, target: Any) -> str:
    """安全拼接 Brain 仿真轮询 URL，杜绝 /simulations/simulations/ 重复路径。"""
    base = str(base_url or "https://api.worldquantbrain.com").rstrip("/")
    u = str(target or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/"):
        return f"{base}{u}"
    if u.startswith("simulations/"):
        return f"{base}/{u}"
    return f"{base}/simulations/{u.lstrip('/')}"


class ResearchService:
    """AEGIS V4.1.1 确定性量化研究宿主服务引擎"""

    def __init__(self, workspace_root: Optional[str] = None, campaigns_root: Optional[str] = None):
        self.workspace_root = os.path.abspath(
            workspace_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.campaigns_root = os.path.abspath(
            campaigns_root or os.path.join(self.workspace_root, "campaigns")
        )
        os.makedirs(self.campaigns_root, exist_ok=True)
        OperatorRegistry.load()

    @staticmethod
    def _sanitize_campaign_id(name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(name or "").strip())
        if not clean or clean in (".", ".."):
            raise ValueError("campaign_id 非法")
        return clean

    def _get_store(self, campaign_id: str) -> Tuple[str, CampaignStore]:
        cid = self._sanitize_campaign_id(campaign_id)
        cdir = os.path.join(self.campaigns_root, cid)
        return cdir, CampaignStore(cdir)

    def _resolve_fields(
        self,
        camp: dict,
        override_fields: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        target_ds = str(camp["dataset_id"])
        if isinstance(override_fields, dict) and override_fields:
            cleaned: Dict[str, Dict[str, Any]] = {}
            for fid, meta in override_fields.items():
                if not isinstance(meta, dict):
                    meta = {"description": str(meta)}
                if DatasetFieldResolver._is_dirty_cross_dataset_field(meta, target_dataset_id=target_ds):
                    continue
                cleaned[fid] = HypothesisSpec.normalize_field_profile(fid, meta)
            return cleaned

        resolver = DatasetFieldResolver(self.workspace_root)
        return resolver.resolve_fields(
            region=camp["region"],
            category=camp.get("category") or "other",
            dataset_id=camp["dataset_id"],
        )

    @staticmethod
    def _field_stem(fid: str) -> str:
        s = re.sub(r"\b\d+\b", "", fid.lower())
        s = re.sub(
            r"(_\d+|day\d*|q\d*|bin\d*|label\d*|variant\d*|v\d+|mean|median|max|min|stddev|std|lower|upper|confidence|score)",
            "",
            s,
        )
        s = re.sub(r"_+", "_", s).strip("_") or fid.lower()
        parts = [p for p in s.split("_") if p]
        return "_".join(parts[:2]) if len(parts) >= 2 else s

    @classmethod
    def _build_semantic_clusters(cls, fields_meta: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 (semantic_role, 词干簇, type) 对字段分组，支持分层抽样探针与 80% 簇覆盖率审计。"""
        groups: Dict[Tuple[str, str, str], List[str]] = {}
        for fid in sorted(fields_meta.keys()):
            m = fields_meta[fid]
            role = str(m.get("semantic_role") or "Signal_Flow")
            ftype = str(m.get("type") or "MATRIX").upper()
            stem = cls._field_stem(fid)
            groups.setdefault((role, stem, ftype), []).append(fid)

        clusters: List[Dict[str, Any]] = []
        for idx, ((role, stem, ftype), fids) in enumerate(sorted(groups.items()), 1):
            cold = sorted(
                fids,
                key=lambda x: (
                    int(fields_meta[x].get("alpha_count", 0) or 0),
                    -float(fields_meta[x].get("coverage") or 0.0),
                    x,
                ),
            )
            clusters.append({
                "cluster_id": f"CL_{idx:02d}_{stem}",
                "semantic_role": role,
                "field_type": ftype,
                "stem": stem,
                "field_count": len(fids),
                "cold_representatives": cold[:3],
                "fields": fids,
            })
        return clusters

    @classmethod
    def _select_stratified_probe_fields(
        cls,
        fields_meta: Dict[str, Dict[str, Any]],
        clusters: List[Dict[str, Any]],
        max_fields: int = 12,
    ) -> List[str]:
        """按语义簇轮询分层抽样代表字段（优先高覆盖且跨簇正交），杜绝字母序前 8 字段盲人摸象。"""
        if not clusters:
            return sorted(fields_meta.keys())[:max_fields]
        ordered_queues: List[List[str]] = []
        for cl in clusters:
            ranked = sorted(
                cl["fields"],
                key=lambda x: (
                    -float(fields_meta[x].get("coverage") or 0.0),
                    int(fields_meta[x].get("alpha_count", 0) or 0),
                    x,
                ),
            )
            ordered_queues.append(ranked)

        selected: List[str] = []
        seen: Set[str] = set()
        round_idx = 0
        while len(selected) < max_fields:
            added = False
            for q in ordered_queues:
                if round_idx < len(q):
                    fid = q[round_idx]
                    if fid not in seen:
                        seen.add(fid)
                        selected.append(fid)
                        added = True
                        if len(selected) >= max_fields:
                            break
            if not added:
                break
            round_idx += 1
        return selected

    @staticmethod
    def _compute_ceff_from_corr_matrix(corr_matrix: np.ndarray) -> Tuple[float, List[float]]:
        if corr_matrix.size == 0:
            return 1.0, [1.0]
        sym = 0.5 * (corr_matrix + corr_matrix.T)
        evals = np.linalg.eigvalsh(sym)
        pos = np.clip(evals, 0.0, None)
        total = float(np.sum(pos))
        if total <= 1e-12:
            return 1.0, [1.0]
        probs = pos / total
        entropy = -sum(float(p * math.log(p)) for p in probs if p > 1e-12)
        ceff = float(math.exp(entropy))
        spectrum = [round(float(x), 6) for x in sorted(pos.tolist(), reverse=True)]
        return round(max(1.0, ceff), 4), spectrum

    @classmethod
    def _estimate_offline_effective_rank(
        cls,
        fields_meta: Dict[str, Dict[str, Any]],
        pnl_series_map: Optional[Dict[str, List[float]]] = None,
    ) -> Tuple[float, List[float], str]:
        if isinstance(pnl_series_map, dict) and len(pnl_series_map) >= 1:
            valid_series = []
            for k in sorted(pnl_series_map.keys()):
                arr = pnl_series_map[k]
                if isinstance(arr, (list, tuple)) and len(arr) >= 2:
                    valid_series.append(np.asarray(arr, dtype=float))
            if len(valid_series) == 1:
                return 1.0, [1.0], "pnl_series_single"
            if len(valid_series) >= 2:
                min_len = min(len(v) for v in valid_series)
                mat = np.vstack([v[:min_len] for v in valid_series])
                stds = np.std(mat, axis=1)
                non_const = mat[stds > 1e-12]
                if len(non_const) >= 2:
                    corr = np.corrcoef(non_const)
                    corr = np.nan_to_num(corr, nan=0.0)
                    np.fill_diagonal(corr, 1.0)
                    ceff, spec = cls._compute_ceff_from_corr_matrix(corr)
                    return ceff, spec, "pnl_series_eigen"

        fids = sorted(fields_meta.keys())
        if not fids:
            return 1.0, [1.0], "empty_fallback"

        n = len(fids)
        if n > 80:
            step = n / 80.0
            fids = [fids[int(i * step)] for i in range(80)]
            n = len(fids)

        corr = np.eye(n, dtype=float)
        stems = [cls._field_stem(f) for f in fids]
        roles = [str(fields_meta[f].get("semantic_role") or "") for f in fids]
        doms = [str(fields_meta[f].get("domain") or "") for f in fids]
        freqs = [str(fields_meta[f].get("update_frequency") or "") for f in fids]
        for i in range(n):
            for j in range(i + 1, n):
                if stems[i] == stems[j]:
                    sim = 0.88
                elif roles[i] and roles[i] == roles[j] and doms[i] == doms[j] and freqs[i] == freqs[j]:
                    sim = 0.65
                elif roles[i] and roles[i] == roles[j]:
                    sim = 0.35
                else:
                    sim = 0.05
                corr[i, j] = sim
                corr[j, i] = sim
        ceff, spec = cls._compute_ceff_from_corr_matrix(corr)
        return ceff, spec, "offline_structural_proxy"

    @staticmethod
    def _universe_approx_size(universe: str) -> int:
        m = re.search(r"(\d{3,4})", str(universe or ""))
        if m:
            try:
                return max(100, int(m.group(1)))
            except ValueError:
                pass
        return 1000

    def _infer_dataset_from_fields(
        self,
        region: str,
        field_ids: List[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """当研究员仅提供 seed_alpha_id 时，按表达式引用字段自动反查所属数据集与分类。"""
        clean_fids = [
            f for f in (field_ids or [])
            if f and f not in DimensionAuditor.EXTERNAL_PV_FIELDS
        ]
        if not clean_fids:
            return None, None
        region_dir = os.path.join(self.workspace_root, "knowledge_base", "fields", str(region or "USA").upper())
        if not os.path.isdir(region_dir):
            return None, None
        best_ds: Optional[str] = None
        best_cat: Optional[str] = None
        best_hits = 0
        for fname in sorted(os.listdir(region_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(region_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    doc = json.load(fp)
            except Exception:
                continue
            fields_map = doc.get("fields") if isinstance(doc, dict) else None
            if not isinstance(fields_map, dict):
                continue
            ds_id = str(doc.get("dataset_id") or os.path.splitext(fname)[0])
            hits = sum(
                1 for fid in clean_fids
                if fid in fields_map
                and not DatasetFieldResolver._is_dirty_cross_dataset_field(fields_map[fid], target_dataset_id=ds_id)
            )
            if hits > best_hits:
                best_hits = hits
                best_ds = ds_id
                best_cat = str(doc.get("category") or "other")
        return best_ds, best_cat

    async def _hydrate_seed_alpha_profile_async(
        self,
        seed_alpha_id: str,
        provided_profile: Optional[dict] = None,
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """从 Brain 平台自动水合目标 seed_alpha_id 的表达式、真实设置、年报、相关性与法医病灶。"""
        profile: Dict[str, Any] = dict(provided_profile) if isinstance(provided_profile, dict) else {}
        profile.setdefault("alpha_id", seed_alpha_id)
        has_expr = bool(profile.get("expression") or profile.get("code"))
        has_settings = isinstance(profile.get("settings"), dict) and bool(profile.get("settings"))
        warning: Optional[str] = None

        if not (has_expr and has_settings):
            bm = get_brain_module()
            if bm and hasattr(bm, "get_alpha_details"):
                try:
                    details = await bm.get_alpha_details(seed_alpha_id)
                    if isinstance(details, dict) and not details.get("error"):
                        reg = details.get("regular")
                        expr = (reg.get("code") if isinstance(reg, dict) else None) or details.get("expression") or details.get("code")
                        is_b = details.get("is") or {}
                        settings = details.get("settings") or {}
                        if expr:
                            profile.setdefault("expression", expr)
                        if isinstance(settings, dict) and settings:
                            profile.setdefault("settings", settings)
                        if isinstance(is_b, dict) and is_b:
                            profile.setdefault("is", is_b)
                            profile.setdefault("metrics", is_b)
                            profile.setdefault("checks", is_b.get("checks", []))
                            for k in ("sharpe", "fitness", "turnover", "margin"):
                                if profile.get(k) is None and is_b.get(k) is not None:
                                    profile[k] = is_b.get(k)
                        profile = await self._enrich_live_alpha_evidence_async(
                            bm,
                            seed_alpha_id,
                            profile,
                            fetch_prod_corr=True,
                            fetch_self_corr=True,
                            fetch_yearly=True,
                        )
                    else:
                        warning = f"拉取 seed_alpha_id={seed_alpha_id} 详情失败: {details}"
                except Exception as exc:
                    warning = f"水合 seed_alpha_id={seed_alpha_id} 异常: {exc}"
            else:
                warning = "未检测到在线 Brain MCP 连接，无法自动水合 seed_alpha_id 详情（可显式传入 seed_profile）"

        return profile, warning

    def _build_seed_diagnosis(
        self,
        seed_profile: Dict[str, Any],
        camp: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """将已水合的目标 Alpha 整理为结构化法医诊断卡片，供宿主在情况 2 中直接启动靶向手术。"""
        if not isinstance(seed_profile, dict):
            return None
        expr = str(seed_profile.get("expression") or seed_profile.get("code") or "").strip()
        settings = seed_profile.get("settings") if isinstance(seed_profile.get("settings"), dict) else {}
        is_m = seed_profile.get("is") or seed_profile.get("metrics") or {}
        if not isinstance(is_m, dict):
            is_m = {}
        if not expr and not settings and not is_m:
            return None

        parsed_expr = parse_fastexpr(expr) if expr else None
        parsed_chk = Gatekeeper.parse_brain_checks(seed_profile)
        holdout = Gatekeeper.compute_internal_holdout_stats(seed_profile)
        pcorr = Gatekeeper.extract_prod_corr(seed_profile)
        scorr = Gatekeeper.extract_self_corr(seed_profile)
        sharpe = seed_profile.get("sharpe") if seed_profile.get("sharpe") is not None else is_m.get("sharpe")
        fitness = seed_profile.get("fitness") if seed_profile.get("fitness") is not None else is_m.get("fitness")
        turnover = seed_profile.get("turnover") if seed_profile.get("turnover") is not None else is_m.get("turnover")
        margin_bps = seed_profile.get("margin_bps")
        if margin_bps is None:
            rm = seed_profile.get("margin") if seed_profile.get("margin") is not None else is_m.get("margin")
            if rm is not None:
                rm_f = float(rm)
                margin_bps = round(rm_f * 10000.0 if abs(rm_f) <= 1.0 else rm_f, 4)

        diag_metrics = {
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "margin": (float(margin_bps) / 10000.0) if margin_bps is not None else is_m.get("margin"),
        }
        forensic = Gatekeeper.diagnose_and_route_prescriptions(
            alpha_metrics=diag_metrics,
            checks_parsed=parsed_chk,
            yearly_stats=seed_profile.get("yearly_stats"),
            operator_count=parsed_expr.operator_count if (parsed_expr and parsed_expr.is_valid) else 0,
            prod_corr=pcorr,
        )
        controls = build_named_ablation_and_placebo(parsed_expr) if (parsed_expr and parsed_expr.is_valid) else None

        decrowd = None
        if pcorr is not None and pcorr >= 0.65 and expr:
            try:
                rf = self._resolve_fields(camp)
            except FileNotFoundError:
                rf = {}
            decrowd = self._build_decrowding_prescription(expr, pcorr, rf)

        try:
            sh_abs = abs(float(sharpe or 0.0))
        except (TypeError, ValueError):
            sh_abs = 0.0

        out: Dict[str, Any] = {
            "alpha_id": seed_profile.get("alpha_id"),
            "expression": expr,
            "referenced_fields": sorted(parsed_expr.referenced_identifiers) if (parsed_expr and parsed_expr.is_valid) else [],
            "operator_count": parsed_expr.operator_count if (parsed_expr and parsed_expr.is_valid) else 0,
            "settings": {
                "decay": settings.get("decay"),
                "truncation": settings.get("truncation"),
                "neutralization": settings.get("neutralization"),
                "nanHandling": settings.get("nanHandling"),
            },
            "metrics": {
                "sharpe": sharpe,
                "is_core_sharpe": holdout.get("is_core_sharpe"),
                "trimmed_is_sharpe": holdout.get("trimmed_is_sharpe"),
                "holdout_2y_sharpe": holdout.get("holdout_2y_sharpe"),
                "fitness": fitness,
                "turnover": turnover,
                "margin_bps": margin_bps,
                "prod_corr": pcorr,
                "self_corr": scorr,
            },
            "fails": parsed_chk.get("fails", []),
            "defect_warnings": parsed_chk.get("warnings", []),
            "info_warnings": parsed_chk.get("info_warnings", []),
            "symptoms": forensic.get("symptoms", []),
            "forensic_clues": forensic.get("forensic_clues", []),
            "recommended_surgery_controls": controls,
            "parent_eligible_for_calibration": bool(sh_abs >= 1.25),
        }
        if decrowd:
            out["de_crowding_prescription"] = decrowd
        return out

    # ------------------------------------------------------------------
    # Tool 1: init_or_load_campaign (async + sync wrapper)
    # ------------------------------------------------------------------
    async def init_or_load_campaign_async(
        self,
        region: str = "",
        universe: str = "",
        dataset_id: str = "",
        delay: Optional[int] = None,
        category: str = "other",
        seed_alpha_id: Optional[str] = None,
        campaign_name: Optional[str] = None,
        seed_profile: Optional[dict] = None,
    ) -> Dict[str, Any]:
        hydrated_profile: Dict[str, Any] = {}
        hydration_warning: Optional[str] = None
        if seed_alpha_id:
            hydrated_profile, hydration_warning = await self._hydrate_seed_alpha_profile_async(
                seed_alpha_id=seed_alpha_id,
                provided_profile=seed_profile,
            )
            s_set = hydrated_profile.get("settings") if isinstance(hydrated_profile.get("settings"), dict) else {}
            if not region and s_set.get("region"):
                region = str(s_set["region"])
            if not universe and s_set.get("universe"):
                universe = str(s_set["universe"])
            if delay is None and s_set.get("delay") is not None:
                delay = int(s_set["delay"])
            if not dataset_id:
                seed_expr = str(hydrated_profile.get("expression") or hydrated_profile.get("code") or "")
                parsed_s = parse_fastexpr(seed_expr) if seed_expr else None
                ref_fids = sorted(parsed_s.referenced_identifiers) if (parsed_s and parsed_s.is_valid) else []
                inferred_ds, inferred_cat = self._infer_dataset_from_fields(region or "USA", ref_fids)
                if inferred_ds:
                    dataset_id = inferred_ds
                    if category == "other" and inferred_cat:
                        category = inferred_cat
                else:
                    raise ValueError(
                        f"已拉取 seed_alpha_id={seed_alpha_id} (region={region or 'UNKNOWN'}, fields={ref_fids})，"
                        f"但本地字段知识库未能自动匹配唯一 dataset_id，请显式传入 dataset_id 参数以建立 Scope Lock。"
                    )
        elif isinstance(seed_profile, dict) and seed_profile:
            hydrated_profile = dict(seed_profile)

        if delay is None:
            delay = 1
        if not region or not universe or not dataset_id:
            raise ValueError("init_or_load_campaign 必须提供完整的 region / universe / dataset_id（或提供可自动水合的 seed_alpha_id）")

        cid = self._sanitize_campaign_id(
            campaign_name
            or (f"{region.upper()}_{dataset_id.lower()}_{seed_alpha_id}" if seed_alpha_id else f"{region.upper()}_{dataset_id.lower()}")
        )
        cdir, store = self._get_store(cid)

        meta: Dict[str, Any] = {}
        if hydrated_profile:
            meta["seed_profile"] = hydrated_profile
        camp = store.init_campaign(
            campaign_id=cid,
            region=region,
            universe=universe,
            dataset_id=dataset_id,
            delay=int(delay),
            category=category,
            seed_alpha_id=seed_alpha_id,
            metadata=meta or None,
        )
        stored_seed_profile = (camp.get("metadata") or {}).get("seed_profile") or hydrated_profile
        seed_diag = self._build_seed_diagnosis(stored_seed_profile, camp) if stored_seed_profile else None

        res: Dict[str, Any] = {
            "campaign_id": cid,
            "campaign_dir": cdir,
            "mode": "TARGETED_OPTIMIZATION" if camp.get("seed_alpha_id") else "GREENFIELD",
            "scope_lock": {
                "region": camp["region"],
                "universe": camp["universe"],
                "dataset_id": camp["dataset_id"],
                "delay": camp["delay"],
                "category": camp["category"],
            },
            "seed_alpha_id": camp.get("seed_alpha_id"),
            "summary": store.get_summary(cid),
            "research_tree_path": store.tree_md_path,
            "champions_path": store.champions_path,
        }
        if seed_diag:
            res["seed_diagnosis"] = seed_diag
        if hydration_warning:
            res["hydration_warning"] = hydration_warning
        return res

    def init_or_load_campaign(
        self,
        region: str = "",
        universe: str = "",
        dataset_id: str = "",
        delay: Optional[int] = None,
        category: str = "other",
        seed_alpha_id: Optional[str] = None,
        campaign_name: Optional[str] = None,
        seed_profile: Optional[dict] = None,
    ) -> Dict[str, Any]:
        return _run_coro_sync(
            self.init_or_load_campaign_async(
                region=region,
                universe=universe,
                dataset_id=dataset_id,
                delay=delay,
                category=category,
                seed_alpha_id=seed_alpha_id,
                campaign_name=campaign_name,
                seed_profile=seed_profile,
            )
        )

    # ------------------------------------------------------------------
    # Tool 2: campaign_status
    # ------------------------------------------------------------------
    def campaign_status(self, campaign_id: str) -> Dict[str, Any]:
        cdir, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'，请先调用 init_or_load_campaign 初始化。")
        prof = store.get_dataset_profile(campaign_id)
        summary = store.get_summary(campaign_id)
        hygiene = check_directory_hygiene(cdir)
        hyps = store.list_hypotheses(campaign_id)
        active_jobs = [
            {
                "job_id": j["job_id"],
                "job_type": j["job_type"],
                "hypothesis_id": j.get("hypothesis_id") or "",
                "mode": j.get("mode") or "",
                "status": j["status"],
                "cli_command": self._job_cli_command(campaign_id, j["job_id"]),
                "updated_at": j.get("updated_at"),
            }
            for j in store.list_jobs(campaign_id, limit=15)
            if j.get("status") in ("QUEUED", "RUNNING")
        ]

        if active_jobs:
            next_action = f"run background job via CLI: {active_jobs[0]['cli_command']}"
        elif prof is None:
            next_action = "profile_dataset"
        elif not hyps:
            next_action = "register_hypothesis"
        elif summary["total_experiments"] == 0:
            next_action = "run_experiment(mode='discovery', enqueue=True)"
        elif summary["open_near_miss_leads"]:
            next_action = "run_experiment(mode='surgery', enqueue=True) or request_verdict(action='CERTIFY_ALPHA')"
        else:
            next_action = "register_hypothesis / run_experiment(enqueue=True) / request_verdict"

        return {
            "campaign_id": campaign_id,
            "scope_lock": {
                "region": camp["region"],
                "universe": camp["universe"],
                "dataset_id": camp["dataset_id"],
                "delay": camp["delay"],
                "category": camp["category"],
                "seed_alpha_id": camp.get("seed_alpha_id"),
            },
            "dataset_profile": prof or {"status": "UNPROFILED"},
            "hypotheses": [
                {"hypothesis_id": h["hypothesis_id"], "status": h["status"], "intents": h["mechanism_intents"]}
                for h in hyps
            ],
            "pending_jobs": active_jobs,
            "summary": summary,
            "directory_hygiene": hygiene,
            "certified_champions": store.get_certified_champions(),
            "next_recommended_action": next_action,
        }

    @staticmethod
    def _job_cli_command(campaign_id: str, job_id: str) -> str:
        return f"python3 aegis_mcp_server.py cli run-job --campaign {campaign_id} --job {job_id}"

    # ------------------------------------------------------------------
    # Tool 3: profile_dataset (async + sync wrapper + enqueue support)
    # ------------------------------------------------------------------
    async def profile_dataset_async(
        self,
        campaign_id: str,
        fields_meta: Optional[Dict[str, dict]] = None,
        pnl_series_map: Optional[Dict[str, List[float]]] = None,
        use_live_probe: bool = False,
        enqueue: bool = False,
    ) -> Dict[str, Any]:
        _, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")

        resolved = self._resolve_fields(camp, override_fields=fields_meta)
        clusters = self._build_semantic_clusters(resolved)
        live_pnl_map = pnl_series_map
        measured_physics: Dict[str, Dict[str, Any]] = {}
        live_probe_warning: Optional[str] = None

        if use_live_probe and enqueue and not live_pnl_map:
            # Save offline baseline profile immediately, then enqueue live P0Y0M probe job in campaign.db (<1s return!)
            ceff, spectrum, method = self._estimate_offline_effective_rank(resolved, pnl_series_map=None)
            has_vec = any(str(m.get("type", "")).upper() == "VECTOR" for m in resolved.values())
            role_counts: Dict[str, int] = {}
            freq_counts: Dict[str, int] = {}
            for m in resolved.values():
                r = str(m.get("semantic_role") or "Unassigned")
                u = str(m.get("update_frequency") or "daily")
                role_counts[r] = role_counts.get(r, 0) + 1
                freq_counts[u] = freq_counts.get(u, 0) + 1
            store.save_dataset_profile(
                campaign_id=campaign_id,
                effective_rank=ceff,
                has_vector_fields=has_vec,
                field_count=len(resolved),
                eigen_spectrum=spectrum,
                profile_data={
                    "method": method,
                    "role_counts": role_counts,
                    "frequency_counts": freq_counts,
                    "semantic_clusters": clusters,
                    "measured_physics": {},
                },
            )
            sample_fids = self._select_stratified_probe_fields(resolved, clusters, max_fields=12)
            job_id = f"JOB_PROF_{uuid.uuid4().hex[:8].upper()}"
            store.enqueue_job(
                job_id=job_id,
                campaign_id=campaign_id,
                job_type="profile_probe",
                mode="profile_probe",
                payload={
                    "sample_fids": sample_fids,
                    "fields_meta_override": fields_meta,
                },
            )
            chunk_count = max(1, (len(sample_fids) + LIVE_CHUNK_SIZE - 1) // LIVE_CHUNK_SIZE)
            return {
                "status": "QUEUED",
                "job_id": job_id,
                "campaign_id": campaign_id,
                "job_type": "profile_probe",
                "probe_field_count": len(sample_fids),
                "chunk_count": chunk_count,
                "offline_effective_rank": ceff,
                "field_count": len(resolved),
                "semantic_cluster_count": len(clusters),
                "has_vector_fields": has_vec,
                "cli_command": self._job_cli_command(campaign_id, job_id),
                "note": "离线画像已落盘且实盘 P0Y0M 探针已持久化入队。请以非阻塞后台任务运行 cli_command 静默执行，完成后自动升级 campaign.db 并回传 <1KB 实测物理摘要。",
            }

        if use_live_probe and not live_pnl_map:
            probe_out = await self._run_live_p0y0m_probe_async(camp, resolved, clusters)
            live_pnl_map = probe_out.get("pnl_map")
            measured_physics = probe_out.get("measured_physics") or {}
            live_probe_warning = probe_out.get("warning")
            # Upgrade resolved fields with empirically measured physical attributes
            for fid, phys in measured_physics.items():
                if fid in resolved:
                    resolved[fid]["evidence_status"] = "MEASURED"
                    if phys.get("measured_coverage") is not None:
                        resolved[fid]["coverage"] = phys["measured_coverage"]
                    if phys.get("measured_update_frequency"):
                        resolved[fid]["update_frequency"] = phys["measured_update_frequency"]
                    if phys.get("measured_is_sparse") is not None:
                        resolved[fid]["is_sparse"] = phys["measured_is_sparse"]

        return self._persist_and_format_profile(
            store=store,
            campaign_id=campaign_id,
            resolved=resolved,
            clusters=clusters,
            live_pnl_map=live_pnl_map,
            measured_physics=measured_physics,
            live_probe_warning=live_probe_warning,
        )

    def _persist_and_format_profile(
        self,
        store: CampaignStore,
        campaign_id: str,
        resolved: Dict[str, dict],
        clusters: List[Dict[str, Any]],
        live_pnl_map: Optional[Dict[str, List[float]]],
        measured_physics: Dict[str, Dict[str, Any]],
        live_probe_warning: Optional[str] = None,
    ) -> Dict[str, Any]:
        ceff, spectrum, method = self._estimate_offline_effective_rank(resolved, pnl_series_map=live_pnl_map)
        has_vec = any(str(m.get("type", "")).upper() == "VECTOR" for m in resolved.values())
        role_counts: Dict[str, int] = {}
        freq_counts: Dict[str, int] = {}
        for m in resolved.values():
            r = str(m.get("semantic_role") or "Unassigned")
            u = str(m.get("update_frequency") or "daily")
            role_counts[r] = role_counts.get(r, 0) + 1
            freq_counts[u] = freq_counts.get(u, 0) + 1

        profile_payload: Dict[str, Any] = {
            "method": method,
            "role_counts": role_counts,
            "frequency_counts": freq_counts,
            "semantic_clusters": clusters,
            "measured_physics": measured_physics,
        }
        if live_probe_warning:
            profile_payload["live_probe_warning"] = live_probe_warning

        store.save_dataset_profile(
            campaign_id=campaign_id,
            effective_rank=ceff,
            has_vector_fields=has_vec,
            field_count=len(resolved),
            eigen_spectrum=spectrum,
            profile_data=profile_payload,
        )

        # Stratified sample cards across clusters (up to 30) so host sees diverse clusters instead of alphabetical head
        strat_ids = self._select_stratified_probe_fields(resolved, clusters, max_fields=30)
        sample_cards = [
            {
                "field_id": fid,
                "type": resolved[fid].get("type", "MATRIX"),
                "domain": resolved[fid].get("domain"),
                "is_sparse": resolved[fid].get("is_sparse"),
                "coverage": resolved[fid].get("coverage"),
                "alpha_count": resolved[fid].get("alpha_count"),
                "update_frequency": resolved[fid].get("update_frequency"),
                "semantic_role": resolved[fid].get("semantic_role"),
                "evidence_status": resolved[fid].get("evidence_status"),
                "measured_physics": measured_physics.get(fid),
            }
            for fid in strat_ids
        ]

        out: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "effective_rank": ceff,
            "method": method,
            "eigen_spectrum": spectrum,
            "has_vector_fields": has_vec,
            "field_count": len(resolved),
            "semantic_cluster_count": len(clusters),
            "semantic_clusters": [
                {
                    "cluster_id": cl["cluster_id"],
                    "semantic_role": cl["semantic_role"],
                    "field_type": cl["field_type"],
                    "field_count": cl["field_count"],
                    "cold_representatives": cl["cold_representatives"],
                }
                for cl in clusters[:20]
            ],
            "role_counts": role_counts,
            "frequency_counts": freq_counts,
            "measured_physics": measured_physics,
            "fields_sample": sample_cards,
        }
        if live_probe_warning:
            out["live_probe_warning"] = live_probe_warning
        return out

    def profile_dataset(
        self,
        campaign_id: str,
        fields_meta: Optional[Dict[str, dict]] = None,
        pnl_series_map: Optional[Dict[str, List[float]]] = None,
        use_live_probe: bool = False,
        enqueue: bool = False,
    ) -> Dict[str, Any]:
        return _run_coro_sync(
            self.profile_dataset_async(
                campaign_id=campaign_id,
                fields_meta=fields_meta,
                pnl_series_map=pnl_series_map,
                use_live_probe=use_live_probe,
                enqueue=enqueue,
            )
        )

    async def _run_live_p0y0m_probe_async(
        self,
        camp: dict,
        resolved: Dict[str, dict],
        clusters: List[Dict[str, Any]],
        sample_fids_override: Optional[List[str]] = None,
        checkpoint_state: Optional[Dict[str, Any]] = None,
        checkpoint_save_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_log_cb: Optional[Callable[[str], None]] = None,
        initial_wait_sec: float = 0.0,
    ) -> Dict[str, Any]:
        """按语义簇分层抽样 <= 12 代表字段，分块 (<=4) 执行 P0Y0M 实盘探针（支持断点续传与静默轮询）。"""
        bm = get_brain_module()
        if not (bm and hasattr(bm, "create_multi_simulation") and hasattr(bm, "get_alpha_pnl")):
            return {"pnl_map": None, "measured_physics": {}, "warning": "Brain MCP 未连接，回退至离线结构代理"}

        sample_fids = list(sample_fids_override) if sample_fids_override else self._select_stratified_probe_fields(resolved, clusters, max_fields=12)
        sample_fids = [f for f in sample_fids if f in resolved]
        if len(sample_fids) < 2:
            return {"pnl_map": None, "measured_physics": {}, "warning": "字段数不足 2 个，跳过实盘谱探针"}

        base_url = str(getattr(getattr(bm, "brain_client", None), "base_url", "https://api.worldquantbrain.com")).rstrip("/")
        univ_size = float(self._universe_approx_size(camp.get("universe", "TOP1000")))
        poll_sleep_min = float(os.environ.get("AEGIS_LIVE_POLL_MIN_SEC", "1.0"))
        poll_default = float(os.environ.get("AEGIS_LIVE_POLL_INTERVAL_SEC", "15.0"))
        max_polls = int(os.environ.get("AEGIS_LIVE_POLL_MAX_STEPS", "120"))
        retry_backoff_sec = float(os.environ.get("AEGIS_LIVE_RETRY_BACKOFF_SEC", "5.0"))

        async def _poll(u: str) -> dict:
            full = _join_sim_url(base_url, u)
            for _ in range(max_polls):
                resp = await bm.brain_client._request("GET", full)
                data = resp.json() if hasattr(resp, "json") else (resp if isinstance(resp, dict) else {})
                ra = float(getattr(resp, "headers", {}).get("Retry-After", 0) or 0)
                st = str(data.get("status", "")).upper()
                if (ra == 0 and (data.get("children") or data.get("alpha") or st in ("COMPLETE", "COMPLETED", "DONE"))) or st in ("ERROR", "CANCELLED"):
                    return data
                await asyncio.sleep(max(poll_sleep_min, min(ra or poll_default, 30.0)))
            return {"status": "ERROR"}

        state: Dict[str, Any] = checkpoint_state if isinstance(checkpoint_state, dict) else {}
        chunks_ckpt: Dict[str, Dict[str, Any]] = state.setdefault("chunks", {})
        pnl_map: Dict[str, List[float]] = dict(state.get("pnl_map") or {})
        measured_physics: Dict[str, Dict[str, Any]] = dict(state.get("measured_physics") or {})
        warnings: List[str] = list(state.get("warnings") or [])

        total_chunks = (len(sample_fids) + LIVE_CHUNK_SIZE - 1) // LIVE_CHUNK_SIZE
        # Chunk into <= 4 per request (brain-mcp hard cap is 8; 4 minimizes queue contention)
        for c_idx, start in enumerate(range(0, len(sample_fids), LIVE_CHUNK_SIZE)):
            ck_key = str(c_idx)
            ck_entry = chunks_ckpt.get(ck_key) or {}
            if ck_entry.get("status") == "DONE":
                continue

            chunk_fids = sample_fids[start:start + LIVE_CHUNK_SIZE]
            items = []
            for fid in chunk_fids:
                meta = resolved[fid]
                expr = f"rank(vec_avg({fid}))" if str(meta.get("type", "")).upper() == "VECTOR" else f"rank({fid})"
                items.append({
                    "type": "REGULAR",
                    "settings": {
                        "instrumentType": "EQUITY",
                        "region": camp["region"],
                        "universe": camp["universe"],
                        "delay": camp["delay"],
                        "decay": 0,
                        "neutralization": "SUBINDUSTRY",
                        "truncation": 0.025,
                        "pasteurization": "ON",
                        "unitHandling": "VERIFY",
                        "nanHandling": "ON",
                        "language": "FASTEXPR",
                        "visualization": False,
                        "testPeriod": "P0Y0M",
                    },
                    "regular": expr,
                })
            padded_single = False
            if len(items) == 1:
                items.append(dict(items[0]))
                padded_single = True

            for attempt in range(3):
                try:
                    loc = ck_entry.get("location") if ck_entry.get("status") == "SUBMITTED" else None
                    resumed = bool(loc)
                    if not loc:
                        sub = await bm.create_multi_simulation(items)
                        loc = sub.get("location") if isinstance(sub, dict) else None
                        if not loc:
                            if attempt < 2:
                                await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                                continue
                            warnings.append(f"分块探针 #{c_idx + 1} 提交失败: {sub}")
                            break
                        ck_entry = {"status": "SUBMITTED", "location": loc, "padded_single": padded_single}
                        chunks_ckpt[ck_key] = ck_entry
                        if checkpoint_save_cb:
                            checkpoint_save_cb(state)
                        if progress_log_cb:
                            progress_log_cb(f"[AEGIS probe] chunk {c_idx + 1}/{total_chunks} submitted ({len(chunk_fids)} fields)")
                        if initial_wait_sec > 0:
                            await asyncio.sleep(initial_wait_sec)
                    elif progress_log_cb:
                        progress_log_cb(f"[AEGIS probe] chunk {c_idx + 1}/{total_chunks} resuming from saved location")

                    parent_state = await _poll(loc)
                    if str(parent_state.get("status", "")).upper() == "CANCELLED" and attempt < 2:
                        ck_entry = {"status": "PENDING"}
                        chunks_ckpt[ck_key] = ck_entry
                        if checkpoint_save_cb:
                            checkpoint_save_cb(state)
                        await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                        continue

                    children = parent_state.get("children") or []
                    eff_pad = bool(ck_entry.get("padded_single", padded_single))
                    effective_children = children[:1] if eff_pad else children[:len(chunk_fids)]
                    for idx, child_url in enumerate(effective_children):
                        fid = chunk_fids[idx]
                        c_state = await _poll(child_url)
                        aid = c_state.get("alpha")
                        if not aid:
                            continue
                        pnl_res = await bm.get_alpha_pnl(aid)
                        records = (pnl_res or {}).get("records", []) if isinstance(pnl_res, dict) else []
                        series = []
                        for row in records:
                            if isinstance(row, (list, tuple)) and len(row) >= 2 and isinstance(row[1], (int, float)):
                                series.append(float(row[1]))
                            elif isinstance(row, dict) and row.get("pnl") is not None:
                                series.append(float(row["pnl"]))
                        if len(series) >= 3:
                            diffs = [series[i] - series[i - 1] for i in range(1, len(series))]
                            pnl_map[fid] = diffs

                        if hasattr(bm, "get_alpha_details"):
                            try:
                                det = await bm.get_alpha_details(aid)
                                is_b = (det or {}).get("is") or {}
                                tvr = is_b.get("turnover")
                                lc = is_b.get("longCount")
                                sc = is_b.get("shortCount")
                                phys_entry: Dict[str, Any] = {
                                    "probe_alpha_id": aid,
                                    "evidence_status": "MEASURED",
                                }
                                if lc is not None and sc is not None:
                                    active = float(lc) + float(sc)
                                    cov = round(min(1.0, max(0.0, active / univ_size)), 4)
                                    phys_entry["measured_coverage"] = cov
                                    phys_entry["measured_is_sparse"] = bool(cov < 0.35)
                                if tvr is not None:
                                    tvr_f = float(tvr)
                                    phys_entry["measured_rank_turnover"] = round(tvr_f, 4)
                                    if tvr_f < 0.03:
                                        phys_entry["measured_update_frequency"] = "quarterly"
                                    elif tvr_f < 0.12:
                                        phys_entry["measured_update_frequency"] = "monthly"
                                    else:
                                        phys_entry["measured_update_frequency"] = "daily"
                                measured_physics[fid] = phys_entry
                            except Exception as det_err:
                                warnings.append(f"字段 {fid} 详情提取失败: {det_err}")

                    ck_entry = {"status": "DONE", "location": loc}
                    chunks_ckpt[ck_key] = ck_entry
                    state["pnl_map"] = pnl_map
                    state["measured_physics"] = measured_physics
                    state["warnings"] = warnings
                    if checkpoint_save_cb:
                        checkpoint_save_cb(state)
                    if progress_log_cb:
                        progress_log_cb(f"[AEGIS probe] chunk {c_idx + 1}/{total_chunks} done (resumed={resumed})")
                    break
                except Exception as chunk_err:
                    warnings.append(f"分块实盘探针异常: {chunk_err}")
                    break

        return {
            "pnl_map": pnl_map if len(pnl_map) >= 2 else None,
            "measured_physics": measured_physics,
            "warning": "; ".join(warnings) if warnings else None,
        }

    # ------------------------------------------------------------------
    # Tool 4: register_hypothesis
    # ------------------------------------------------------------------
    def register_hypothesis(
        self,
        campaign_id: str,
        hypothesis_id: str,
        economic_mechanism: str,
        counterparty: str,
        field_roles: Any,
        mechanism_intents: List[str],
        falsification_criterion: str,
        parent_alpha_id: Optional[str] = None,
        fields_meta: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, Any]:
        _, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")

        if len(str(economic_mechanism or "").strip()) < 12:
            raise ValueError("economic_mechanism 必须 >= 12 字符并阐述真实经济学传导机理")
        if len(str(counterparty or "").strip()) < 4:
            raise ValueError("counterparty 必须明确错误定价对手盘")
        if not isinstance(mechanism_intents, list) or not (1 <= len(mechanism_intents) <= 3):
            raise ValueError("mechanism_intents 必须为 1~3 个机制意图的非空列表")
        if len(str(falsification_criterion or "").strip()) < 10:
            raise ValueError("falsification_criterion 必须明确可证伪标准 (>= 10 字符)")

        try:
            known_fields = self._resolve_fields(camp, override_fields=fields_meta)
        except FileNotFoundError:
            known_fields = {}

        allow_pv = str(camp.get("category") or "").lower() in ("pv", "price_volume", "price")
        role_fids: List[str] = []
        if isinstance(field_roles, list):
            for fr in field_roles:
                if isinstance(fr, dict) and fr.get("field_id"):
                    role_fids.append(str(fr["field_id"]))
                elif isinstance(fr, str):
                    role_fids.append(fr)
        elif isinstance(field_roles, dict):
            role_fids.extend(str(k) for k in field_roles.keys())

        if known_fields:
            for fid in role_fids:
                if fid in DimensionAuditor.EXTERNAL_PV_FIELDS and not allow_pv:
                    raise ValueError(f"【Scope Lock 违规】非量价分类禁止在 field_roles 混入外部 PV 字段 '{fid}'")
                if fid not in known_fields and fid not in DimensionAuditor.EXTERNAL_PV_FIELDS:
                    raise ValueError(f"【Scope Lock 违规】字段 '{fid}' 不属于锁定数据集 {camp['dataset_id']}！")

        saved = store.register_hypothesis(
            campaign_id=campaign_id,
            hypothesis_id=hypothesis_id,
            economic_mechanism=economic_mechanism.strip(),
            counterparty=counterparty.strip(),
            field_roles=field_roles,
            mechanism_intents=[str(x).strip().upper() for x in mechanism_intents if str(x).strip()],
            falsification_criterion=falsification_criterion.strip(),
            parent_alpha_id=parent_alpha_id,
        )
        return saved

    # ------------------------------------------------------------------
    # Tool 5: run_experiment (async + sync wrapper)
    # ------------------------------------------------------------------
    def _validate_settings_gate(self, camp: dict, store: CampaignStore, mode: str, settings: Optional[dict]) -> Dict[str, Any]:
        eff = dict(DEFAULT_DISCOVERY_SETTINGS)
        seed_profile = (camp.get("metadata") or {}).get("seed_profile") or {}
        seed_settings = seed_profile.get("settings") if isinstance(seed_profile, dict) else None
        if isinstance(seed_settings, dict):
            for k in ("decay", "truncation", "neutralization", "nanHandling"):
                if k in seed_settings and seed_settings[k] is not None:
                    eff[k] = seed_settings[k]

        if isinstance(settings, dict):
            for lk, camp_val in (
                ("region", camp["region"]),
                ("universe", camp["universe"]),
                ("dataset_id", camp["dataset_id"]),
                ("delay", camp["delay"]),
            ):
                if lk in settings and settings[lk] is not None:
                    if str(settings[lk]).strip().upper() != str(camp_val).strip().upper():
                        raise ValueError(f"【Scope Lock 拦截】禁止篡改锁定参数 `{lk}`: {settings[lk]} != {camp_val}")
            for k, v in settings.items():
                if v is not None:
                    eff[k] = v

        summary = store.get_summary(camp["campaign_id"])
        seed_sharpe = 0.0
        if isinstance(seed_profile, dict):
            m = seed_profile.get("metrics") or seed_profile.get("is") or seed_profile
            try:
                seed_sharpe = abs(float(m.get("sharpe") or 0.0))
            except (TypeError, ValueError):
                seed_sharpe = 0.0
        has_eligible_parent = bool(summary.get("parent_eligible") or seed_sharpe >= 1.25)

        if mode == "settings_calibration":
            if not has_eligible_parent:
                raise PermissionError(
                    "【Expression-First, Settings-Last 拦截】当前尚无表达式达到基准 |Sharpe| >= 1.25，"
                    "禁止提前进入 mode='settings_calibration' 调整 decay/truncation/neutralization！"
                )
            eff["neutralization"] = str(eff.get("neutralization") or "SUBINDUSTRY").strip().upper()
            return eff

        # In discovery / surgery: lock decay, truncation, AND neutralization to baseline (close neutralization smuggling!)
        base_decay = int((seed_settings or {}).get("decay", DEFAULT_DISCOVERY_SETTINGS["decay"]) or 0)
        base_trunc = float((seed_settings or {}).get("truncation", DEFAULT_DISCOVERY_SETTINGS["truncation"]) or 0.025)
        base_neut = str((seed_settings or {}).get("neutralization") or DEFAULT_DISCOVERY_SETTINGS["neutralization"]).strip().upper()
        cur_decay = int(eff.get("decay", 0) or 0)
        cur_trunc = float(eff.get("truncation", 0.025) or 0.025)
        cur_neut = str(eff.get("neutralization") or base_neut).strip().upper()
        eff["neutralization"] = cur_neut

        if cur_decay != base_decay or abs(cur_trunc - base_trunc) > 1e-9 or cur_neut != base_neut:
            raise PermissionError(
                f"【Expression-First, Settings-Last 拦截】在 mode='{mode}' 阶段禁止修改物理设置 "
                f"(decay={cur_decay}, truncation={cur_trunc}, neutralization={cur_neut}) "
                f"偏离基准 (decay={base_decay}, truncation={base_trunc}, neutralization={base_neut})！"
                f"必须先打磨表达式至 |Sharpe| >= 1.25 再切换到 mode='settings_calibration'。"
            )
        return eff

    @staticmethod
    def _outer_group_neutralization_scope(parsed) -> Optional[str]:
        """检测表达式最外层是否已执行 group_neutralize / group_zscore / group_rank 等组内去均值/排序及其分组粒度。"""
        if not parsed or not parsed.is_valid or parsed.final_ast is None:
            return None
        node = parsed.final_ast
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in GROUP_NEUT_OPS:
            for arg in node.args[1:]:
                if isinstance(arg, ast.Name):
                    g = arg.id.strip().upper()
                    if g in NEUTRALIZATION_HIERARCHY:
                        return g
            for kw in node.keywords:
                if kw.arg in ("group", "g") and isinstance(kw.value, ast.Name):
                    g = kw.value.id.strip().upper()
                    if g in NEUTRALIZATION_HIERARCHY:
                        return g
        return None

    @classmethod
    def _effective_settings_signature(cls, parsed, exact_key: str, eff_settings: dict) -> Tuple[str, Optional[str]]:
        """
        构造数学等价去重后的 Settings 签名：
        若表达式最外层已执行 group_*(..., subindustry)，则外层设置 NONE/MARKET/COUNTRY/SECTOR/INDUSTRY/SUBINDUSTRY
        均已被内层更细粒度组内中性化 subsumed，归一化为同一签名以拦截冗余回测。
        """
        decay = int(eff_settings.get("decay", 0) or 0)
        trunc = round(float(eff_settings.get("truncation", 0.025) or 0.025), 6)
        outer_neut = str(eff_settings.get("neutralization") or "SUBINDUSTRY").strip().upper()
        inner_g = cls._outer_group_neutralization_scope(parsed)
        subsumed_note: Optional[str] = None
        if inner_g and outer_neut in NEUTRALIZATION_HIERARCHY:
            if NEUTRALIZATION_HIERARCHY[inner_g] >= NEUTRALIZATION_HIERARCHY[outer_neut]:
                eff_neut = f"SUBSUMED_BY_INNER_{inner_g}"
                subsumed_note = inner_g
            else:
                eff_neut = outer_neut
        else:
            eff_neut = outer_neut
        sig = f"{exact_key}|d={decay}|t={trunc}|n={eff_neut}"
        return sig, subsumed_note

    @staticmethod
    def _is_holdout_check_name(item: Any) -> bool:
        s = str(item or "").upper()
        return any(kw in s for kw in HOLDOUT_LEAK_KEYWORDS)

    @classmethod
    def _mask_result_for_agent(cls, res_item: dict, mode: str) -> dict:
        """
        discovery / surgery 阶段严格零泄露屏蔽近 2 年 Holdout：
        1. 彻底移除 10 年全局 `sharpe` 以及一切 `holdout_2y_sharpe` / `two_year_sharpe` / `sharpe_2y` / `ladder_2y_sharpe` 字段，
           仅保留 8 年样本内核心 `is_core_sharpe` 与剔除最佳黑天鹅年的 `trimmed_is_sharpe`，封死代数反推；
        2. 过滤 `fails` / `defect_warnings` 中所有含 `2Y` / `TWO_YEAR` / `LADDER` / `RECENT` 的近期检查项并重算 `fail_count`；
        3. 截断 `yearly_stats` 末尾 2 年。
        """
        if mode not in ("discovery", "surgery"):
            return dict(res_item)

        masked = dict(res_item)
        for k in ("sharpe", "holdout_2y_sharpe", "ladder_2y_sharpe", "two_year_sharpe", "sharpe_2y"):
            masked.pop(k, None)

        if isinstance(masked.get("fails"), list):
            filtered_fails = [f for f in masked["fails"] if not cls._is_holdout_check_name(f)]
            masked["fails"] = filtered_fails
            masked["fail_count"] = len(filtered_fails)
        if isinstance(masked.get("defect_warnings"), list):
            masked["defect_warnings"] = [w for w in masked["defect_warnings"] if not cls._is_holdout_check_name(w)]

        if isinstance(masked.get("yearly_stats"), list) and len(masked["yearly_stats"]) >= 3:
            masked["yearly_stats"] = masked["yearly_stats"][:-2]
        masked["holdout_masked"] = True
        return masked

    @staticmethod
    def _extract_families_and_vecs(parsed) -> Tuple[List[str], List[str]]:
        fams: Set[str] = set()
        vecs: Set[str] = set()
        for op in parsed.all_calls:
            if op.startswith("vec_"):
                vecs.add(op)
            elif op in OP_FAMILY_MAP:
                fams.add(OP_FAMILY_MAP[op])
        return sorted(fams), sorted(vecs)

    @staticmethod
    def _window_pair_ratio(w1: List[int], w2: List[int]) -> Optional[float]:
        if not w1 or not w2 or len(w1) != len(w2):
            return None
        ratios = []
        for a, b in zip(w1, w2):
            if a == b:
                continue
            if a <= 0 or b <= 0:
                return None
            ratios.append(max(a, b) / float(min(a, b)))
        if not ratios:
            return 1.0
        return ratios[0] if len(ratios) == 1 else max(ratios)

    @classmethod
    def _build_decrowding_prescription(
        cls,
        expr: str,
        prod_corr: Optional[float],
        resolved_fields: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """当 ProdCorr >= 0.65 时，生成可落地的三杠杆去拥挤处方（冷字段 / 非对称内生交互 / 去秩保留幅度）。"""
        if prod_corr is None or prod_corr < 0.65:
            return None
        parsed = parse_fastexpr(expr)
        used = set(parsed.referenced_identifiers) if parsed.is_valid else set()
        calls = set(parsed.all_calls) if parsed.is_valid else set()

        cold_cands = [
            {
                "field_id": fid,
                "alpha_count": int(m.get("alpha_count", 0) or 0),
                "coverage": m.get("coverage"),
                "domain": m.get("domain"),
                "semantic_role": m.get("semantic_role"),
            }
            for fid, m in resolved_fields.items()
            if fid not in used and float(m.get("coverage") or 0.0) >= 0.30
        ]
        cold_cands.sort(key=lambda x: (x["alpha_count"], -(float(x["coverage"] or 0.0)), x["field_id"]))

        anchor_cands = [
            {
                "field_id": fid,
                "coverage": m.get("coverage"),
                "domain": m.get("domain"),
                "semantic_role": m.get("semantic_role"),
            }
            for fid, m in resolved_fields.items()
            if fid not in used and float(m.get("coverage") or 0.0) >= 0.80
        ]
        anchor_cands.sort(key=lambda x: (-(float(x["coverage"] or 0.0)), x["field_id"]))

        uses_rank = bool(calls.intersection({"rank", "group_rank"}))
        return {
            "symptom": "prod_corr_overflow",
            "prod_corr": round(float(prod_corr), 4),
            "threshold": 0.65,
            "levers": [
                {
                    "lever": "1_COLD_FIELD_REPLACEMENT",
                    "action": "用同数据集低拥挤度冷字段替换当前高拥挤主锚，严禁仅调窗口或换 decay 企图降相关",
                    "suggested_cold_fields": cold_cands[:5],
                },
                {
                    "lever": "2_ASYMMETRIC_ENDOGENOUS_INTERACTION",
                    "action": "引入同数据集高覆盖内生基准字段构建差值/比值或回归残差，剥离全市场共模因子暴露",
                    "suggested_anchor_fields": anchor_cands[:3],
                },
                {
                    "lever": "3_CARDINAL_MAGNITUDE_RETENTION",
                    "action": (
                        "检测到表达式使用了 rank/group_rank 拍平截面幅度：改用 winsorize(std=4) + zscore/group_neutralize 保留连续分布幅度"
                        if uses_rank
                        else "已保留连续幅度；优先联合杠杆 1（换冷主锚）与杠杆 2（内生基准正交剥离）打破共线性"
                    ),
                    "uses_rank_currently": uses_rank,
                },
            ],
        }

    @classmethod
    def _compute_horizon_verdict_from_store(
        cls,
        store: CampaignStore,
        campaign_id: str,
        expr: str,
        sharpe: Optional[float],
        topo_key: str,
        core_skeleton: str,
    ) -> Tuple[Optional[str], bool, Dict[str, Any]]:
        """基于当前战役 campaign.db 中同拓扑不同晶格窗口的历史实验，自动运行 HorizonProbe 高原验证。"""
        wins = extract_all_windows(expr)
        if not wins:
            return "STATIC_CROSS_SECTION", True, {"reason": "无时序回看窗口的纯截面信号"}

        hist = store.list_experiments(campaign_id, topology_key=topo_key) if topo_key else []
        if not hist and core_skeleton:
            hist = store.list_experiments(campaign_id, core_skeleton=core_skeleton)

        pool_items: List[Dict[str, Any]] = []
        all_sharpes: Dict[str, float] = {}
        seen_exprs: Set[str] = set()

        def _add_entry(ex_s: str, sh_v: Optional[float], slot_i: int) -> None:
            norm = re.sub(r"\s+", "", (ex_s or "").strip().lower())
            if not norm or norm in seen_exprs:
                return
            seen_exprs.add(norm)
            pool_items.append({"slot": slot_i, "expression": ex_s})
            if sh_v is not None:
                all_sharpes[norm] = float(sh_v)

        _add_entry(expr, sharpe, 1)
        slot_seq = 2
        for h in hist:
            if h.get("mode") == "control":
                continue
            h_expr = h.get("expression") or ""
            h_sh = h.get("sharpe") if h.get("sharpe") is not None else h.get("is_core_sharpe")
            _add_entry(h_expr, h_sh, slot_seq)
            slot_seq += 1

        if len(pool_items) < 2:
            return None, False, {
                "reason": "尚无同拓扑配对离散窗口实验，无法判定 PLATEAU vs SPIKE",
                "current_windows": wins,
            }

        pairs = HorizonProbe.detect_pairs(pool_items)
        if not pairs:
            return None, False, {
                "reason": "同拓扑已有实验但未形成 [1.6x, 4.2x] 合法 N/2N 高原配对窗口",
                "current_windows": wins,
            }

        verdicts = HorizonProbe.evaluate(pool_items, pool_items, pairs, all_sharpes=all_sharpes)
        target_norm = re.sub(r"\s+", "", expr.strip().lower())
        best_v: Optional[str] = None
        matched_info: Dict[str, Any] = {}
        for p, v in zip(pairs, verdicts):
            ea = re.sub(r"\s+", "", str(p.get("expr_short") or p.get("expr_a") or "").strip().lower())
            eb = re.sub(r"\s+", "", str(p.get("expr_long") or p.get("expr_b") or "").strip().lower())
            if target_norm in (ea, eb):
                best_v = str(v.get("verdict") or "")
                matched_info = dict(v)
                if best_v in ProductionGate.ACCEPTED_HORIZON_VERDICTS:
                    break
        if best_v:
            return best_v, best_v in ProductionGate.ACCEPTED_HORIZON_VERDICTS, matched_info
        return None, False, {"reason": "HorizonProbe 未能对目标表达式定性", "current_windows": wins}

    async def run_experiment_async(
        self,
        campaign_id: str,
        hypothesis_id: str,
        variants: List[dict],
        mode: str = "discovery",
        settings: Optional[dict] = None,
        dry_run: bool = False,
        enqueue: bool = False,
        sim_executor: Optional[Callable[[dict, dict], Any]] = None,
        fields_meta: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, Any]:
        cdir, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")

        # 1. Directory hygiene check
        hygiene = check_directory_hygiene(cdir)
        if not hygiene["clean"]:
            raise PermissionError(
                f"【Directory Hygiene 拦截】战役目录存在违规散落文件/脚本: {hygiene['rogue_files']}，"
                f"V4.1 仅允许 campaign.db / RESEARCH_TREE.md / certified_champions.json。"
            )

        # 2. Hypothesis check
        hyp = store.get_hypothesis(campaign_id, hypothesis_id)
        if not hyp:
            raise ValueError(f"【假说先行拦截】假说 '{hypothesis_id}' 尚未在战役 '{campaign_id}' 注册！")

        # 3. Elastic batch sizing
        mode_l = str(mode or "discovery").strip().lower()
        if mode_l not in MODE_BATCH_LIMITS:
            raise ValueError(f"不支持的实验模式 '{mode}'，仅允许 {list(MODE_BATCH_LIMITS.keys())}")
        min_n, max_n = MODE_BATCH_LIMITS[mode_l]
        if not isinstance(variants, list) or not (min_n <= len(variants) <= max_n):
            raise ValueError(
                f"【弹性并发越界】mode='{mode_l}' 批量大小必须位于 [{min_n}, {max_n}]，实际传入 {len(variants) if isinstance(variants, list) else 0}"
            )

        # 3b. Surgery multi-slot control anchor enforcement
        if mode_l == "surgery" and len(variants) >= 3:
            has_parent_ctrl = any(
                isinstance(v, dict) and str(v.get("type") or "").strip().lower() == "parent_control"
                for v in variants
            )
            if not has_parent_ctrl:
                raise ValueError(
                    "【Surgery 对照组硬约束】多槽位 surgery (n >= 3) 必须包含至少 1 个 type='parent_control' 母本基准对照槽，"
                    "以建立同批可比基线并阻断漂移自嗨！"
                )

        # 4. Expression-First, Settings-Last + Scope Lock on settings (incl. neutralization lock)
        eff_settings = self._validate_settings_gate(camp, store, mode_l, settings)

        # 5. Field metadata
        try:
            resolved_fields = self._resolve_fields(camp, override_fields=fields_meta)
        except FileNotFoundError:
            resolved_fields = {}

        allow_pv = str(camp.get("category") or "").lower() in ("pv", "price_volume", "price")
        hyp_payload = {
            "hypothesis_id": hyp["hypothesis_id"],
            "economic_cluster": hyp["economic_mechanism"],
            "field_roles": hyp["field_roles"],
            "counterparty": hyp["counterparty"],
            "mechanism_intents": hyp["mechanism_intents"],
        }

        # Pre-load existing calibration signatures for mathematical-equivalence settings dedup
        existing_cal_sigs: Set[str] = set()
        if mode_l == "settings_calibration":
            for old_exp in store.list_experiments(campaign_id):
                old_p = parse_fastexpr(old_exp.get("expression") or "")
                if old_p.is_valid:
                    old_ex_key = exact_canonical_key(old_p)
                    try:
                        old_set = json.loads(old_exp.get("settings_json") or "{}")
                    except Exception:
                        old_set = {}
                    old_sig, _ = self._effective_settings_signature(old_p, old_ex_key, old_set)
                    existing_cal_sigs.add(old_sig)

        validated_variants: List[dict] = []
        batch_exact_seen: Set[str] = set()
        pending_canon_keys = store.get_pending_canonical_keys(campaign_id)
        batch_cal_sigs_seen: Set[str] = set()
        batch_topo_entries: Dict[str, List[Tuple[int, List[int]]]] = {}
        batch_core_counts: Dict[str, int] = {}
        non_probe_window_only_count = 0
        non_control_total = 0
        recommended_surgery_controls: Optional[Dict[str, Any]] = None

        for idx, var in enumerate(variants):
            if not isinstance(var, dict):
                raise ValueError(f"Slot {idx + 1} 变体不是 dict")
            slot = int(var.get("slot", idx + 1))
            expr = str(var.get("expression") or "").strip()
            if not expr:
                raise ValueError(f"Slot {slot} 缺少 expression")

            # Block per-variant custom settings smuggling during discovery/surgery (decay, truncation, neutralization)
            if mode_l in ("discovery", "surgery"):
                for sk in ("decay", "truncation"):
                    if sk in var and var[sk] is not None and abs(float(var[sk]) - float(eff_settings.get(sk))) > 1e-9:
                        raise PermissionError(
                            f"【Expression-First Settings-Last 拦截】Slot {slot} 在 '{mode_l}' 阶段试图私自设置 `{sk}={var[sk]}`"
                        )
                if var.get("neutralization") is not None:
                    v_neut = str(var["neutralization"]).strip().upper()
                    if v_neut != str(eff_settings.get("neutralization", "SUBINDUSTRY")).strip().upper():
                        raise PermissionError(
                            f"【Expression-First Settings-Last 拦截】Slot {slot} 在 '{mode_l}' 阶段试图私自切换 `neutralization={v_neut}`"
                        )

            parsed = parse_fastexpr(expr)
            if not parsed.is_valid:
                raise ValueError(f"Slot {slot} FastExpr 语法错误: {'; '.join(parsed.errors)}")

            # Scope Lock on referenced fields
            if resolved_fields:
                for fid in parsed.referenced_identifiers:
                    if fid in DimensionAuditor.EXTERNAL_PV_FIELDS and not allow_pv:
                        raise ValueError(f"【Scope Lock 拦截】Slot {slot} 在非量价分类下混入外部 PV 字段 '{fid}'")
                    if fid not in resolved_fields and fid not in DimensionAuditor.EXTERNAL_PV_FIELDS:
                        raise ValueError(f"【Scope Lock 拦截】Slot {slot} 使用了非本数据集字段 '{fid}'")

            # Frequency inference for horizon lattice
            used_freqs = {
                str(resolved_fields[fid].get("update_frequency") or "daily").lower()
                for fid in parsed.referenced_identifiers
                if fid in resolved_fields
            }
            upd_freq = "quarterly" if "quarterly" in used_freqs else ("monthly" if "monthly" in used_freqs else "daily")

            v_type = str(var.get("type") or "").strip().lower()
            is_control = v_type in ("parent_control", "ablation_control", "placebo_control")
            if v_type == "parent_control" and recommended_surgery_controls is None:
                recommended_surgery_controls = build_named_ablation_and_placebo(parsed)

            # Hard SNC compilation gate (require_snc_when_complex=True for non-control expressions!)
            audit = DimensionAuditor.audit_expression(
                expr,
                known_fields=resolved_fields if resolved_fields else sorted(parsed.referenced_identifiers),
                category=camp["category"],
                allow_pv_cross=allow_pv,
                max_operators=10 if mode_l in ("surgery", "settings_calibration") else 8,
                hypothesis=hyp_payload,
                update_frequency=upd_freq,
                strict_lattice=True,
                require_snc_when_complex=(not is_control),
            )
            if not audit["is_valid"]:
                raise ValueError(f"【AST / SNC / Lattice / Dimension 拦截】Slot {slot}: {'; '.join(audit['issues'])}")

            # DGP Variant schema (5-key V4.1 or 9-key legacy)
            v_check = dict(var)
            v_check.setdefault("hypothesis_ref", hyp["hypothesis_id"])
            ok_hyp, hyp_iss = HypothesisSpec.audit_variant_hypothesis(v_check, hyp_payload, resolved_fields or None)
            if not ok_hyp:
                raise ValueError(f"【假说契约拦截】Slot {slot}: {'; '.join(hyp_iss)}")

            # DoubleBlind RedTeam
            rt_payload = DoubleBlindRedTeam.generate_blind_payload(
                expr,
                {"counterparty": hyp["counterparty"], "mechanism": hyp["economic_mechanism"]},
                resolved_fields,
            )
            rt_res = DoubleBlindRedTeam.audit_candidate_blindly(rt_payload)
            if rt_res.get("verdict") == "REJECT":
                raise ValueError(f"【RedTeam 拦截】Slot {slot}: {'; '.join(rt_res.get('issues', []))}")

            # Two-layer canonical keys:
            # - exact_key preserves discrete lattice windows -> strictly unique (allows N/2N horizon probes!)
            # - topo_key strips windows -> bounded to <= 2 per batch (valid N/2N ratio) and <= 4 across campaign
            exact_key = exact_canonical_key(parsed)
            topo_key = topology_equivalence_key(parsed)
            core_skel = ASTSandboxCorrector.get_core_skeleton(expr)
            wins = extract_all_windows(parsed)

            if mode_l == "settings_calibration":
                cal_sig, subsumed_inner = self._effective_settings_signature(parsed, exact_key, eff_settings)
                if cal_sig in batch_cal_sigs_seen or cal_sig in existing_cal_sigs:
                    if subsumed_inner:
                        raise ValueError(
                            f"【Settings 等价冗余拦截】Slot {slot} 表达式最外层已执行 group_*({subsumed_inner.lower()})，"
                            f"切换更粗粒度外层 neutralization='{eff_settings.get('neutralization')}' 与已有实验数学等价，严禁浪费预算！"
                        )
                    raise ValueError(
                        f"【Settings 重复拦截】Slot {slot} 相同的 (expression, decay, truncation, neutralization) 组合已回测过！"
                    )
                batch_cal_sigs_seen.add(cal_sig)

            if not is_control and mode_l != "settings_calibration":
                non_control_total += 1
                # Layer 1: exact canonical uniqueness (blocks variable rename / `+` vs `add` / exact re-runs / duplicate in-flight queue)
                if exact_key in batch_exact_seen or exact_key in pending_canon_keys or store.has_canonical_key(campaign_id, exact_key):
                    raise ValueError(
                        f"【Exact Canonical Tabu 拦截】Slot {slot} 精确等价表达式已被历史、在途队列或同批占坑，严禁变相重复回测"
                    )
                batch_exact_seen.add(exact_key)

                # Layer 2: topology window budget + legal N/2N HorizonProbe check
                prior_in_batch = batch_topo_entries.get(topo_key, [])
                if len(prior_in_batch) >= 2:
                    raise ValueError(
                        f"【反微调拦截】Slot {slot} 同拓扑骨架单批最多允许 2 个槽位组成 N/2N 高原探针，严禁单批网格扫窗！"
                    )
                if len(prior_in_batch) == 1:
                    prev_slot, prev_wins = prior_in_batch[0]
                    ratio = self._window_pair_ratio(prev_wins, wins)
                    if ratio is None or not (1.6 <= ratio <= 4.2):
                        raise ValueError(
                            f"【反微调拦截】Slot {slot} 与 Slot {prev_slot} 同拓扑窗口倍率 ({prev_wins} vs {wins}, ratio={ratio}) "
                            f"不在合法 N/2N 高原探针区间 [1.6, 4.2]，禁止相邻窗口微调！"
                        )

                hist_topo_exps = store.list_experiments(campaign_id, topology_key=topo_key)
                hist_topo_non_ctrl = [h for h in hist_topo_exps if h.get("mode") != "control"]
                if len(hist_topo_non_ctrl) + len(prior_in_batch) + 1 > MAX_TOPOLOGY_CAMPAIGN_WINDOWS:
                    raise ValueError(
                        f"【反微调拦截】Slot {slot} 同拓扑骨架累计窗口变体已超上限 ({MAX_TOPOLOGY_CAMPAIGN_WINDOWS})，"
                        f"请进行结构/字段级创新而非继续换窗口！"
                    )

                if hist_topo_non_ctrl and len(prior_in_batch) == 0:
                    # Check whether this cross-batch window is a legitimate N/2N partner for an existing window
                    is_legit_partner = False
                    if len(hist_topo_non_ctrl) <= 2:
                        for he in hist_topo_non_ctrl:
                            hw = extract_all_windows(he.get("expression") or "")
                            r = self._window_pair_ratio(hw, wins)
                            if r is not None and 1.6 <= r <= 4.2:
                                is_legit_partner = True
                                break
                    if not is_legit_partner:
                        non_probe_window_only_count += 1

                batch_topo_entries.setdefault(topo_key, []).append((slot, wins))

                batch_core_counts[core_skel] = batch_core_counts.get(core_skel, 0) + 1
                if store.count_core_skeleton(campaign_id, core_skel) + batch_core_counts[core_skel] > 8:
                    raise ValueError(f"【Core Skeleton 耗尽拦截】Slot {slot} 核心骨架 `{core_skel}` 累计探索超上限")

            fams, vecs = self._extract_families_and_vecs(parsed)
            validated_variants.append({
                "slot": slot,
                "variant": var,
                "expression": expr,
                "canonical_key": exact_key,
                "topology_key": topo_key,
                "core_skeleton": core_skel,
                "fields_used": sorted(parsed.referenced_identifiers),
                "is_control": is_control,
                "fams": fams,
                "vecs": vecs,
            })

        # Batch-level anti-micro-tuning ratio guard (MAX_WINDOW_ONLY_RATIO = 0.10)
        if non_control_total >= 4 and mode_l != "settings_calibration":
            win_ratio = non_probe_window_only_count / float(non_control_total)
            if win_ratio > MAX_WINDOW_ONLY_RATIO:
                raise ValueError(
                    f"【反微调拦截】本批非 N/2N 探针纯窗口微调占比 {win_ratio * 100:.1f}% "
                    f"({non_probe_window_only_count}/{non_control_total}) > {MAX_WINDOW_ONLY_RATIO * 100:.0f}% 硬上限！"
                )

        if dry_run:
            res_dry: Dict[str, Any] = {
                "status": "DRY_RUN_VALIDATED",
                "campaign_id": campaign_id,
                "hypothesis_id": hypothesis_id,
                "mode": mode_l,
                "settings": eff_settings,
                "validated_count": len(validated_variants),
                "variants": [
                    {
                        "slot": v["slot"],
                        "canonical_key": v["canonical_key"],
                        "topology_key": v["topology_key"],
                        "core_skeleton": v["core_skeleton"],
                    }
                    for v in validated_variants
                ],
            }
            if recommended_surgery_controls:
                res_dry["recommended_surgery_controls"] = recommended_surgery_controls
            return res_dry

        if enqueue:
            job_id = f"JOB_EXP_{uuid.uuid4().hex[:8].upper()}"
            store.enqueue_job(
                job_id=job_id,
                campaign_id=campaign_id,
                job_type="experiment",
                hypothesis_id=hypothesis_id,
                mode=mode_l,
                payload={
                    "hypothesis_id": hypothesis_id,
                    "mode": mode_l,
                    "settings": eff_settings,
                    "validated_variants": validated_variants,
                    "recommended_surgery_controls": recommended_surgery_controls,
                    "fields_meta_override": fields_meta,
                },
            )
            chunk_count = max(1, (len(validated_variants) + LIVE_CHUNK_SIZE - 1) // LIVE_CHUNK_SIZE)
            q_resp: Dict[str, Any] = {
                "status": "QUEUED",
                "job_id": job_id,
                "campaign_id": campaign_id,
                "hypothesis_id": hypothesis_id,
                "mode": mode_l,
                "variant_count": len(validated_variants),
                "chunk_count": chunk_count,
                "cli_command": self._job_cli_command(campaign_id, job_id),
                "note": "静态门禁已 100% 通过并持久化入队。请通过后台任务或轻量执行子 Agent 运行 cli_command 静默执行回测，完成后将自动落盘 campaign.db 并回传 <1KB 脱敏关键摘要。",
            }
            if recommended_surgery_controls:
                q_resp["recommended_surgery_controls"] = recommended_surgery_controls
            return q_resp

        # 6. Execute simulations (injected executor in tests/offline, else chunked Brain MCP live runner)
        raw_results: List[dict] = []
        if sim_executor is not None:
            for vv in validated_variants:
                r = sim_executor(vv["variant"], eff_settings)
                if asyncio.iscoroutine(r):
                    r = await r
                raw_results.append(r if isinstance(r, dict) else {})
        else:
            raw_results = await self._execute_live_variants_async(camp, validated_variants, eff_settings, mode_l=mode_l)

        return self._finalize_experiment_results(
            store=store,
            campaign_id=campaign_id,
            hypothesis_id=hypothesis_id,
            mode_l=mode_l,
            eff_settings=eff_settings,
            validated_variants=validated_variants,
            raw_results=raw_results,
            resolved_fields=resolved_fields,
            recommended_surgery_controls=recommended_surgery_controls,
        )

    def _finalize_experiment_results(
        self,
        store: CampaignStore,
        campaign_id: str,
        hypothesis_id: str,
        mode_l: str,
        eff_settings: Dict[str, Any],
        validated_variants: List[dict],
        raw_results: List[dict],
        resolved_fields: Dict[str, dict],
        recommended_surgery_controls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """将全量真实结果持久化至 campaign.db、补齐 HorizonProbe，并向调用方返回严格 Holdout 屏蔽后的结果视图。"""
        agent_results: List[dict] = []
        recorded_meta: List[Tuple[dict, dict, str]] = []
        for idx, (vv, raw) in enumerate(zip(validated_variants, raw_results)):
            raw_copy = dict(raw) if isinstance(raw, dict) else {}
            is_m = raw_copy.get("is") or raw_copy.get("metrics") or {}
            if not isinstance(is_m, dict):
                is_m = {}
            sharpe = raw_copy.get("sharpe") if raw_copy.get("sharpe") is not None else is_m.get("sharpe")
            fitness = raw_copy.get("fitness") if raw_copy.get("fitness") is not None else is_m.get("fitness")
            turnover = raw_copy.get("turnover") if raw_copy.get("turnover") is not None else is_m.get("turnover")
            margin_bps = raw_copy.get("margin_bps")
            if margin_bps is None:
                rm = raw_copy.get("margin") if raw_copy.get("margin") is not None else is_m.get("margin")
                if rm is not None:
                    rm_f = float(rm)
                    margin_bps = rm_f * 10000.0 if abs(rm_f) <= 1.0 else rm_f
            pcorr = Gatekeeper.extract_prod_corr(raw_copy)
            scorr = Gatekeeper.extract_self_corr(raw_copy)
            parsed_chk = Gatekeeper.parse_brain_checks(raw_copy)
            holdout = Gatekeeper.compute_internal_holdout_stats(raw_copy)

            alpha_id = raw_copy.get("alpha_id") or raw_copy.get("id") or f"SIM_{campaign_id}_{vv['slot']}_{idx+1}"
            sh_f = float(sharpe) if sharpe is not None else 0.0
            status_tag = (
                "CONTROL"
                if vv["is_control"]
                else ("NEAR_MISS" if abs(sh_f) >= 1.25 and parsed_chk["fail_count"] == 0 else "RECORDED")
            )

            # Determine core IS Sharpe to store & show safely
            is_core_val = (
                holdout["is_core_sharpe"]
                if holdout.get("holdout_verified")
                else (float(sharpe) if sharpe is not None else None)
            )
            trimmed_val = (
                holdout["trimmed_is_sharpe"]
                if holdout.get("holdout_verified")
                else is_core_val
            )

            store.record_experiment(
                campaign_id,
                {
                    "hypothesis_id": hypothesis_id,
                    "slot": vv["slot"],
                    "mode": "control" if vv["is_control"] else mode_l,
                    "expression": vv["expression"],
                    "canonical_key": vv["canonical_key"],
                    "topology_key": vv["topology_key"],
                    "core_skeleton": vv["core_skeleton"],
                    "settings": eff_settings,
                    "change_axis": str(vv["variant"].get("change_axis") or ""),
                    "prediction": str(vv["variant"].get("prediction") or vv["variant"].get("optimize_reason") or ""),
                    "sharpe": float(sharpe) if sharpe is not None else None,
                    "is_core_sharpe": is_core_val,
                    "holdout_2y_sharpe": holdout["holdout_2y_sharpe"],
                    "fitness": float(fitness) if fitness is not None else None,
                    "turnover": float(turnover) if turnover is not None else None,
                    "margin_bps": float(margin_bps) if margin_bps is not None else None,
                    "prod_corr": pcorr,
                    "self_corr": scorr,
                    "fail_count": parsed_chk["fail_count"],
                    "warning_count": len(parsed_chk["warnings"]),
                    "checks": is_m.get("checks") or raw_copy.get("checks") or [],
                    "raw_result": raw_copy,
                    "alpha_id": alpha_id,
                    "status": status_tag,
                    "vec_ops": vv["vecs"],
                    "mechanism_families": vv["fams"],
                    "fields_used": vv["fields_used"],
                },
            )
            recorded_meta.append((vv, raw_copy, alpha_id))

            agent_item: Dict[str, Any] = {
                "slot": vv["slot"],
                "alpha_id": alpha_id,
                "expression": vv["expression"],
                "is_core_sharpe": is_core_val,
                "trimmed_is_sharpe": trimmed_val,
                "sharpe": sharpe,
                "fitness": fitness,
                "turnover": turnover,
                "margin_bps": margin_bps,
                "prod_corr": pcorr,
                "self_corr": scorr,
                "fail_count": parsed_chk["fail_count"],
                "fails": list(parsed_chk["fails"]),
                "defect_warnings": list(parsed_chk["warnings"]),
                "info_warnings": list(parsed_chk["info_warnings"]),
                "status": status_tag,
            }
            if isinstance(raw_copy.get("yearly_stats"), list):
                agent_item["yearly_stats"] = list(raw_copy["yearly_stats"])

            decrowd = self._build_decrowding_prescription(vv["expression"], pcorr, resolved_fields)
            if decrowd:
                agent_item["de_crowding_prescription"] = decrowd

            if mode_l in ("discovery", "surgery"):
                agent_item.update({k: raw_copy.get(k) for k in ("two_year_sharpe", "sharpe_2y", "ladder_2y_sharpe") if k in raw_copy})
                agent_item = self._mask_result_for_agent(agent_item, mode_l)
                if not vv["is_control"]:
                    masked_sh = float(is_core_val) if is_core_val is not None else 0.0
                    agent_item["status"] = (
                        "NEAR_MISS"
                        if abs(masked_sh) >= 1.25 and int(agent_item.get("fail_count") or 0) == 0
                        else "RECORDED"
                    )
            else:
                agent_item["holdout_2y_sharpe"] = holdout["holdout_2y_sharpe"]
            agent_results.append(agent_item)

        # Post-persist cross-window HorizonProbe annotation across batch + campaign history
        for idx, (vv, raw_copy, alpha_id) in enumerate(recorded_meta):
            if not raw_copy.get("horizon_verdict"):
                sh_v = raw_copy.get("sharpe")
                if sh_v is None and isinstance(raw_copy.get("is"), dict):
                    sh_v = raw_copy["is"].get("sharpe")
                hv, h_rob, _ = self._compute_horizon_verdict_from_store(
                    store, campaign_id, vv["expression"], sh_v, vv["topology_key"], vv["core_skeleton"]
                )
                if hv:
                    raw_copy["horizon_verdict"] = hv
                    raw_copy["horizon_robust"] = h_rob
                    raw_copy["plateau_pass"] = h_rob
                    store.update_experiment_evidence(campaign_id, alpha_id, raw_copy)
                    agent_results[idx]["horizon_verdict"] = hv

        store.render_research_tree(campaign_id)
        summary_after = store.get_summary(campaign_id)
        resp: Dict[str, Any] = {
            "status": "COMPLETED",
            "campaign_id": campaign_id,
            "hypothesis_id": hypothesis_id,
            "mode": mode_l,
            "settings": eff_settings,
            "holdout_masked": mode_l in ("discovery", "surgery"),
            "results": agent_results,
        }
        if hypothesis_id in (summary_after.get("stagnation_tabu_hypotheses") or []):
            resp["stagnation_tabu_alert"] = (
                f"假说 '{hypothesis_id}' 连续多轮实验未能推升样本内最高水位线 (>=+0.03)，触发 Tabu 停滞告警，建议切换正交字段簇或核心机理！"
            )
        if recommended_surgery_controls:
            resp["recommended_surgery_controls"] = recommended_surgery_controls
        return resp

    @staticmethod
    def _build_compact_experiment_summary(full_resp: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """裁剪为 < 1KB 级高密度脱敏关键摘要，杜绝长报文污染主 Agent 上下文并严格保持 Holdout 屏蔽。"""
        masked_mode = bool(full_resp.get("holdout_masked"))
        compact_rows: List[Dict[str, Any]] = []
        decrowd_summary: Optional[Dict[str, Any]] = None

        for r in full_resp.get("results") or []:
            row: Dict[str, Any] = {
                "slot": r.get("slot"),
                "id": r.get("alpha_id"),
                "is_core": round(float(r["is_core_sharpe"]), 2) if r.get("is_core_sharpe") is not None else None,
                "trim_is": round(float(r["trimmed_is_sharpe"]), 2) if r.get("trimmed_is_sharpe") is not None else None,
                "fit": round(float(r["fitness"]), 2) if r.get("fitness") is not None else None,
                "tvr": round(float(r["turnover"]), 3) if r.get("turnover") is not None else None,
                "mgn": round(float(r["margin_bps"]), 1) if r.get("margin_bps") is not None else None,
            }
            if not masked_mode:
                if r.get("sharpe") is not None:
                    row["sh"] = round(float(r["sharpe"]), 2)
                if r.get("holdout_2y_sharpe") is not None:
                    row["h2y"] = round(float(r["holdout_2y_sharpe"]), 2)
            if r.get("prod_corr") is not None:
                row["pcorr"] = round(float(r["prod_corr"]), 3)
            if r.get("self_corr") is not None:
                row["scorr"] = round(float(r["self_corr"]), 3)
            if r.get("fails"):
                row["fails"] = list(r["fails"])
            if r.get("defect_warnings"):
                row["warns"] = list(r["defect_warnings"])
            if r.get("horizon_verdict"):
                row["hv"] = r["horizon_verdict"]
            if r.get("status") and r["status"] != "RECORDED":
                row["st"] = r["status"]
            compact_rows.append(row)

            rx = r.get("de_crowding_prescription")
            if rx and decrowd_summary is None:
                levers = rx.get("levers") or []
                cold_ids = [c.get("field_id") for c in (levers[0].get("suggested_cold_fields") or [])[:3]] if len(levers) > 0 else []
                anch_ids = [a.get("field_id") for a in (levers[1].get("suggested_anchor_fields") or [])[:2]] if len(levers) > 1 else []
                drop_rank = bool(levers[2].get("uses_rank_currently")) if len(levers) > 2 else False
                decrowd_summary = {"cold": cold_ids, "anchors": anch_ids, "drop_rank": drop_rank}

        out: Dict[str, Any] = {
            "job_id": job_id,
            "campaign": full_resp.get("campaign_id"),
            "hyp": full_resp.get("hypothesis_id"),
            "mode": full_resp.get("mode"),
            "status": "COMPLETED",
            "holdout_masked": masked_mode,
            "results": compact_rows,
        }
        if decrowd_summary:
            out["decrowd"] = decrowd_summary
        if full_resp.get("stagnation_tabu_alert"):
            out["tabu_alert"] = full_resp.get("hypothesis_id")
        return out

    @staticmethod
    def _build_compact_profile_summary(prof_resp: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """将实盘探针画像裁剪为极简高信噪比摘要，供主 Agent 直接进入假说构建。"""
        phys_brief: Dict[str, Dict[str, Any]] = {}
        for fid, p in (prof_resp.get("measured_physics") or {}).items():
            phys_brief[fid] = {
                k: v for k, v in (
                    ("cov", p.get("measured_coverage")),
                    ("freq", p.get("measured_update_frequency")),
                    ("sparse", p.get("measured_is_sparse")),
                    ("tvr", p.get("measured_rank_turnover")),
                ) if v is not None
            }
        out: Dict[str, Any] = {
            "job_id": job_id,
            "campaign": prof_resp.get("campaign_id"),
            "status": "COMPLETED",
            "c_eff": prof_resp.get("effective_rank"),
            "method": prof_resp.get("method"),
            "fields": prof_resp.get("field_count"),
            "clusters": prof_resp.get("semantic_cluster_count"),
            "has_vec": prof_resp.get("has_vector_fields"),
            "measured": phys_brief,
        }
        if prof_resp.get("live_probe_warning"):
            out["warn"] = prof_resp["live_probe_warning"]
        return out

    def run_experiment(
        self,
        campaign_id: str,
        hypothesis_id: str,
        variants: List[dict],
        mode: str = "discovery",
        settings: Optional[dict] = None,
        dry_run: bool = False,
        enqueue: bool = False,
        sim_executor: Optional[Callable[[dict, dict], Any]] = None,
        fields_meta: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, Any]:
        return _run_coro_sync(
            self.run_experiment_async(
                campaign_id=campaign_id,
                hypothesis_id=hypothesis_id,
                variants=variants,
                mode=mode,
                settings=settings,
                dry_run=dry_run,
                enqueue=enqueue,
                sim_executor=sim_executor,
                fields_meta=fields_meta,
            )
        )

    @staticmethod
    def _parse_yearly_stats_response(raw_ys: Any) -> List[Dict[str, Any]]:
        """将 brain-mcp get_alpha_yearly_stats 的返回体规范化为 [{year, sharpe, ...}, ...]。"""
        if isinstance(raw_ys, list):
            return raw_ys
        if not isinstance(raw_ys, dict):
            return []
        records = raw_ys.get("records")
        schema = raw_ys.get("schema") or {}
        props = schema.get("properties") if isinstance(schema, dict) else None
        col_names = [p.get("name") for p in props if isinstance(p, dict)] if isinstance(props, list) else []
        if not isinstance(records, list):
            return []
        out: List[Dict[str, Any]] = []
        for row in records:
            if isinstance(row, dict):
                out.append(row)
            elif isinstance(row, (list, tuple)) and row:
                if col_names and len(col_names) == len(row):
                    out.append(dict(zip(col_names, row)))
                else:
                    # WorldQuant yearly-stats default column order: [year, pnl, bookSize, longCount, shortCount, turnover, sharpe, ...]
                    sh_val = None
                    if len(row) >= 7 and isinstance(row[6], (int, float)):
                        sh_val = float(row[6])
                    elif len(row) >= 2 and isinstance(row[1], (int, float)):
                        sh_val = float(row[1])
                    out.append({"year": row[0], "sharpe": sh_val})
        return out

    @staticmethod
    def _extract_corr_from_brain_resp(resp: Any, kind: str) -> Optional[float]:
        if not isinstance(resp, dict):
            return None
        checks = resp.get("checks")
        if isinstance(checks, dict):
            sub = checks.get(kind)
            if isinstance(sub, dict) and sub.get("max_correlation") is not None:
                try:
                    return float(sub["max_correlation"])
                except (TypeError, ValueError):
                    pass
        if resp.get("max_correlation") is not None:
            try:
                return float(resp["max_correlation"])
            except (TypeError, ValueError):
                pass
        cd = resp.get("correlation_data")
        if isinstance(cd, dict) and cd.get("max") is not None:
            try:
                return float(cd["max"])
            except (TypeError, ValueError):
                pass
        return None

    async def _enrich_live_alpha_evidence_async(
        self,
        bm: Any,
        alpha_id: str,
        base_doc: Dict[str, Any],
        fetch_prod_corr: bool = False,
        fetch_self_corr: bool = True,
        fetch_yearly: bool = True,
    ) -> Dict[str, Any]:
        """自动补全 Brain 实盘证据链 (details / yearly_stats / self_corr / prod_corr)。"""
        doc = dict(base_doc)
        if not bm or not alpha_id:
            return doc

        # 1. Alpha details / checks if missing
        if (not doc.get("checks") and not (isinstance(doc.get("is"), dict) and doc["is"].get("checks"))) and hasattr(bm, "get_alpha_details"):
            try:
                details = await bm.get_alpha_details(alpha_id)
                if isinstance(details, dict) and not details.get("error"):
                    is_b = details.get("is") or {}
                    doc["is"] = is_b
                    doc["metrics"] = is_b
                    doc["checks"] = is_b.get("checks", [])
                    doc.setdefault("settings", details.get("settings"))
                    for k in ("sharpe", "fitness", "turnover", "margin"):
                        if doc.get(k) is None and is_b.get(k) is not None:
                            doc[k] = is_b.get(k)
            except Exception:
                pass

        # 2. Yearly stats (for real Internal Holdout & Master good_flag)
        if fetch_yearly and not doc.get("yearly_stats") and hasattr(bm, "get_alpha_yearly_stats"):
            try:
                raw_ys = await bm.get_alpha_yearly_stats(alpha_id)
                parsed_ys = self._parse_yearly_stats_response(raw_ys)
                if parsed_ys:
                    doc["yearly_stats"] = parsed_ys
            except Exception:
                pass

        # 3. Local self-correlation (fast incremental cache, zero platform correlation lock)
        if fetch_self_corr and Gatekeeper.extract_self_corr(doc) is None and hasattr(bm, "check_self_correlation"):
            try:
                sc_resp = await bm.check_self_correlation(alpha_id)
                sc_val = self._extract_corr_from_brain_resp(sc_resp, "self")
                if sc_val is not None:
                    doc["self_corr"] = sc_val
                    doc["self_corr_verified"] = True
            except Exception:
                pass

        # 4. Production correlation (and self backup via check_correlation) with pending/busy backoff retry
        if fetch_prod_corr and Gatekeeper.extract_prod_corr(doc) is None and hasattr(bm, "check_correlation"):
            max_corr_attempts = max(1, int(os.environ.get("AEGIS_CORR_RETRY_ATTEMPTS", "3") or 3))
            base_backoff = float(os.environ.get("AEGIS_LIVE_RETRY_BACKOFF_SEC", "5.0") or 5.0)
            for corr_attempt in range(max_corr_attempts):
                try:
                    cc_resp = await bm.check_correlation(alpha_id)
                    pc_val = self._extract_corr_from_brain_resp(cc_resp, "production")
                    if pc_val is not None:
                        doc["prod_corr"] = pc_val
                        doc["prod_corr_verified"] = True
                        doc.pop("prod_corr_status", None)
                    if Gatekeeper.extract_self_corr(doc) is None:
                        sc_val = self._extract_corr_from_brain_resp(cc_resp, "self")
                        if sc_val is not None:
                            doc["self_corr"] = sc_val
                            doc["self_corr_verified"] = True
                    if pc_val is not None:
                        break
                    cc_status = str((cc_resp or {}).get("status") or "").strip().lower() if isinstance(cc_resp, dict) else ""
                    if cc_status in ("pending", "correlation_busy"):
                        doc["prod_corr_status"] = cc_status
                        if corr_attempt < max_corr_attempts - 1:
                            ra_val = (cc_resp or {}).get("retry_after")
                            try:
                                wait_s = float(ra_val) if ra_val is not None else (base_backoff * (corr_attempt + 1))
                            except (TypeError, ValueError):
                                wait_s = base_backoff * (corr_attempt + 1)
                            wait_s = min(wait_s, 15.0)
                            if base_backoff < 0.2:
                                wait_s = min(wait_s, base_backoff)
                            await asyncio.sleep(max(0.01, wait_s))
                            continue
                    break
                except Exception:
                    if corr_attempt < max_corr_attempts - 1:
                        await asyncio.sleep(max(0.01, min(base_backoff * (corr_attempt + 1), 15.0)))
                        continue
                    break

        return doc

    @staticmethod
    async def _submit_single_simulation_async(bm: Any, sim_item: Dict[str, Any]) -> Any:
        """适配真实 brain-mcp create_simulation 关键字参数契约，同时兼容单 dict mock。"""
        fn = bm.create_simulation
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            params = {}
        if "alpha_expression" in params or "region" in params:
            s = sim_item.get("settings") or {}
            kwargs: Dict[str, Any] = {
                "type": str(sim_item.get("type") or "REGULAR"),
                "region": str(s.get("region") or "USA"),
                "universe": str(s.get("universe") or "TOP3000"),
                "delay": int(s.get("delay", 1)),
                "decay": int(round(float(s.get("decay", 0) or 0))),
                "neutralization": str(s.get("neutralization") or "SUBINDUSTRY"),
                "truncation": float(s.get("truncation", 0.025)),
                "test_period": str(s.get("testPeriod") or "P0Y0M"),
                "nan_handling": str(s.get("nanHandling") or "ON"),
                "pasteurization": str(s.get("pasteurization") or "ON"),
                "alpha_expression": str(sim_item.get("regular") or ""),
            }
            filtered = {k: v for k, v in kwargs.items() if k in params} if params else kwargs
            return await fn(**filtered)
        return await fn(sim_item)

    async def _execute_live_variants_async(
        self,
        camp: dict,
        validated_variants: List[dict],
        eff_settings: dict,
        mode_l: str = "discovery",
        checkpoint_state: Optional[Dict[str, Any]] = None,
        checkpoint_save_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_log_cb: Optional[Callable[[str], None]] = None,
        initial_wait_sec: float = 0.0,
    ) -> List[dict]:
        bm = get_brain_module()
        if not bm or not hasattr(bm, "create_multi_simulation"):
            raise RuntimeError(
                "❌ 未检测到可用 Brain MCP 实盘连接，且未注入 sim_executor/dry_run=True，无法执行在线仿真。"
            )

        base_url = str(getattr(getattr(bm, "brain_client", None), "base_url", "https://api.worldquantbrain.com")).rstrip("/")
        poll_sleep_min = float(os.environ.get("AEGIS_LIVE_POLL_MIN_SEC", "1.0"))
        poll_default = float(os.environ.get("AEGIS_LIVE_POLL_INTERVAL_SEC", "20.0"))
        max_polls = int(os.environ.get("AEGIS_LIVE_POLL_MAX_STEPS", "120"))
        retry_backoff_sec = float(os.environ.get("AEGIS_LIVE_RETRY_BACKOFF_SEC", "5.0"))

        async def _poll(u: str) -> dict:
            url = _join_sim_url(base_url, u)
            for _ in range(max_polls):
                resp = await bm.brain_client._request("GET", url)
                data = resp.json() if hasattr(resp, "json") else (resp if isinstance(resp, dict) else {})
                ra = float(getattr(resp, "headers", {}).get("Retry-After", 0) or 0)
                st = str(data.get("status", "")).upper()
                if (ra == 0 and (data.get("children") or data.get("alpha") or st in ("COMPLETE", "COMPLETED", "DONE"))) or st in ("ERROR", "CANCELLED"):
                    return data
                await asyncio.sleep(max(poll_sleep_min, min(ra or poll_default, 30.0)))
            return {"status": "ERROR"}

        def _make_sim_item(ex: str) -> dict:
            return {
                "type": "REGULAR",
                "settings": {
                    "instrumentType": "EQUITY",
                    "region": camp["region"],
                    "universe": camp["universe"],
                    "delay": camp["delay"],
                    "decay": int(eff_settings.get("decay", 0)),
                    "neutralization": eff_settings.get("neutralization", "SUBINDUSTRY"),
                    "truncation": float(eff_settings.get("truncation", 0.025)),
                    "pasteurization": "ON",
                    "unitHandling": "VERIFY",
                    "nanHandling": eff_settings.get("nanHandling", "ON"),
                    "language": "FASTEXPR",
                    "visualization": False,
                },
                "regular": ex,
            }

        state: Dict[str, Any] = checkpoint_state if isinstance(checkpoint_state, dict) else {}
        chunks_ckpt: Dict[str, Dict[str, Any]] = state.setdefault("chunks", {})
        all_out: List[dict] = []
        total_chunks = max(1, (len(validated_variants) + LIVE_CHUNK_SIZE - 1) // LIVE_CHUNK_SIZE)

        # Strict <= 4 chunking (brain-mcp hard cap is <= 8) + checkpoint/resume + CANCELLED retry with exponential backoff
        for c_idx, start in enumerate(range(0, len(validated_variants), LIVE_CHUNK_SIZE)):
            ck_key = str(c_idx)
            ck_entry = chunks_ckpt.get(ck_key) or {}
            chunk = validated_variants[start:start + LIVE_CHUNK_SIZE]
            if ck_entry.get("status") == "DONE" and isinstance(ck_entry.get("results"), list) and len(ck_entry["results"]) == len(chunk):
                all_out.extend(ck_entry["results"])
                if progress_log_cb:
                    progress_log_cb(f"[AEGIS job] chunk {c_idx + 1}/{total_chunks} already DONE (resumed from campaign.db)")
                continue

            chunk_results: Optional[List[dict]] = None

            for attempt in range(3):
                payload = [_make_sim_item(v["expression"]) for v in chunk]
                padded_single = False
                use_single_api = (len(payload) == 1 and hasattr(bm, "create_simulation"))
                if len(payload) == 1 and not use_single_api:
                    payload.append(dict(payload[0]))
                    padded_single = True

                loc = ck_entry.get("location") if ck_entry.get("status") == "SUBMITTED" else None
                resumed = bool(loc)
                if loc:
                    use_single_api = bool(ck_entry.get("use_single_api", use_single_api))
                    padded_single = bool(ck_entry.get("padded_single", padded_single))
                    if progress_log_cb:
                        progress_log_cb(f"[AEGIS job] chunk {c_idx + 1}/{total_chunks} resuming saved location")
                else:
                    if use_single_api:
                        sub = await self._submit_single_simulation_async(bm, payload[0])
                    else:
                        sub = await bm.create_multi_simulation(payload)

                    loc = sub.get("location") if isinstance(sub, dict) else None
                    if not loc:
                        if attempt < 2:
                            await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                            continue
                        raise RuntimeError(f"Brain 仿真提交失败 (chunk {c_idx + 1}): {sub}")

                    ck_entry = {
                        "status": "SUBMITTED",
                        "location": loc,
                        "use_single_api": use_single_api,
                        "padded_single": padded_single,
                    }
                    chunks_ckpt[ck_key] = ck_entry
                    if checkpoint_save_cb:
                        checkpoint_save_cb(state)
                    if progress_log_cb:
                        progress_log_cb(f"[AEGIS job] chunk {c_idx + 1}/{total_chunks} submitted ({len(chunk)} slots)")
                    if initial_wait_sec > 0:
                        await asyncio.sleep(initial_wait_sec)

                p_state = await _poll(loc)
                p_status = str(p_state.get("status", "")).upper()
                if p_status == "CANCELLED" and attempt < 2:
                    ck_entry = {"status": "PENDING"}
                    chunks_ckpt[ck_key] = ck_entry
                    if checkpoint_save_cb:
                        checkpoint_save_cb(state)
                    await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                    continue

                if use_single_api:
                    child_alphas: List[Optional[str]] = [p_state.get("alpha")]
                else:
                    children = p_state.get("children") or []
                    eff_children = children[:1] if padded_single else children
                    child_alphas = []
                    cancelled_child = False
                    for idx in range(len(chunk)):
                        if idx >= len(eff_children):
                            child_alphas.append(None)
                            continue
                        c_state = await _poll(eff_children[idx])
                        if str(c_state.get("status", "")).upper() == "CANCELLED":
                            cancelled_child = True
                        child_alphas.append(c_state.get("alpha"))
                    if cancelled_child and attempt < 2:
                        ck_entry = {"status": "PENDING"}
                        chunks_ckpt[ck_key] = ck_entry
                        if checkpoint_save_cb:
                            checkpoint_save_cb(state)
                        await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                        continue

                chunk_results = []
                for idx, aid in enumerate(child_alphas):
                    if not aid:
                        chunk_results.append({"status": "ERROR", "expression": chunk[idx]["expression"]})
                        continue
                    details = await bm.get_alpha_details(aid)
                    is_block = (details or {}).get("is") or {}
                    item_doc: Dict[str, Any] = {
                        "id": aid,
                        "alpha_id": aid,
                        "expression": chunk[idx]["expression"],
                        "is": is_block,
                        "metrics": is_block,
                        "sharpe": is_block.get("sharpe"),
                        "fitness": is_block.get("fitness"),
                        "turnover": is_block.get("turnover"),
                        "margin": is_block.get("margin"),
                        "checks": is_block.get("checks", []),
                        "settings": (details or {}).get("settings", eff_settings),
                    }
                    parsed_c = Gatekeeper.parse_brain_checks(item_doc)
                    try:
                        sh_abs = abs(float(is_block.get("sharpe") or 0.0))
                    except (TypeError, ValueError):
                        sh_abs = 0.0
                    need_prod = bool((sh_abs >= 1.50 and parsed_c["fail_count"] == 0) or mode_l == "settings_calibration")
                    need_self = bool(sh_abs >= 1.25 or mode_l == "settings_calibration")
                    item_doc = await self._enrich_live_alpha_evidence_async(
                        bm,
                        aid,
                        item_doc,
                        fetch_prod_corr=need_prod,
                        fetch_self_corr=need_self,
                        fetch_yearly=True,
                    )
                    chunk_results.append(item_doc)

                ck_entry = {
                    "status": "DONE",
                    "location": loc,
                    "use_single_api": use_single_api,
                    "padded_single": padded_single,
                    "results": chunk_results,
                }
                chunks_ckpt[ck_key] = ck_entry
                if checkpoint_save_cb:
                    checkpoint_save_cb(state)
                if progress_log_cb:
                    progress_log_cb(f"[AEGIS job] chunk {c_idx + 1}/{total_chunks} completed (resumed={resumed})")
                break

            all_out.extend(chunk_results if chunk_results is not None else [{"status": "ERROR"} for _ in chunk])

        return all_out

    # ------------------------------------------------------------------
    # Background Silent Job Runner (CLI `run-job` — 0 MCP timeout, 0 LLM polling, <1KB summary)
    # ------------------------------------------------------------------
    async def execute_job_async(
        self,
        campaign_id: str,
        job_id: str,
        compact: bool = True,
        sim_executor: Optional[Callable[[dict, dict], Any]] = None,
        log_to_stderr: bool = False,
    ) -> Dict[str, Any]:
        """
        执行已通过全部静态门禁并持久化在 campaign.db 的异步任务（支持断点续传、幂等防重、静默轮询与 <1KB 脱敏摘要）。
        供 `python3 aegis_mcp_server.py cli run-job` 在后台独立进程/子 Agent 中静默调用。
        """
        _, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")
        job = store.get_job(job_id)
        if not job or job.get("campaign_id") != campaign_id:
            raise ValueError(f"在战役 '{campaign_id}' 中未找到作业 '{job_id}'")

        # Idempotent return if already COMPLETED (never double-submit or double-record!)
        if job.get("status") == "COMPLETED" and isinstance(job.get("summary"), dict) and job["summary"]:
            return dict(job["summary"])

        def _log(msg: str) -> None:
            if log_to_stderr:
                print(msg, file=sys.stderr, flush=True)

        progress_state: Dict[str, Any] = dict(job.get("progress") or {})

        def _save_ckpt(st: Dict[str, Any]) -> None:
            store.update_job(job_id, status="RUNNING", progress=st)

        store.update_job(job_id, status="RUNNING", error_message="")
        payload = job.get("payload") or {}
        job_type = str(job.get("job_type") or "")

        try:
            if job_type == "experiment":
                hypothesis_id = str(payload.get("hypothesis_id") or job.get("hypothesis_id") or "")
                mode_l = str(payload.get("mode") or job.get("mode") or "discovery")
                eff_settings = dict(payload.get("settings") or {})
                validated_variants = list(payload.get("validated_variants") or [])
                recommended_controls = payload.get("recommended_surgery_controls")
                override_fields = payload.get("fields_meta_override")
                try:
                    resolved_fields = self._resolve_fields(camp, override_fields=override_fields)
                except FileNotFoundError:
                    resolved_fields = {}

                if sim_executor is not None:
                    raw_results = []
                    for vv in validated_variants:
                        r = sim_executor(vv["variant"], eff_settings)
                        if asyncio.iscoroutine(r):
                            r = await r
                        raw_results.append(r if isinstance(r, dict) else {})
                else:
                    init_wait = float(os.environ.get("AEGIS_LIVE_INITIAL_WAIT_SEC", "60.0"))
                    raw_results = await self._execute_live_variants_async(
                        camp=camp,
                        validated_variants=validated_variants,
                        eff_settings=eff_settings,
                        mode_l=mode_l,
                        checkpoint_state=progress_state,
                        checkpoint_save_cb=_save_ckpt,
                        progress_log_cb=_log,
                        initial_wait_sec=init_wait,
                    )

                full_resp = self._finalize_experiment_results(
                    store=store,
                    campaign_id=campaign_id,
                    hypothesis_id=hypothesis_id,
                    mode_l=mode_l,
                    eff_settings=eff_settings,
                    validated_variants=validated_variants,
                    raw_results=raw_results,
                    resolved_fields=resolved_fields,
                    recommended_surgery_controls=recommended_controls,
                )
                compact_summary = self._build_compact_experiment_summary(full_resp, job_id=job_id)
                store.update_job(job_id, status="COMPLETED", progress=progress_state, summary=compact_summary)
                return compact_summary if compact else full_resp

            if job_type == "profile_probe":
                override_fields = payload.get("fields_meta_override")
                resolved = self._resolve_fields(camp, override_fields=override_fields)
                clusters = self._build_semantic_clusters(resolved)
                sample_fids = payload.get("sample_fids") or None
                init_wait = float(os.environ.get("AEGIS_LIVE_PROBE_INITIAL_WAIT_SEC", os.environ.get("AEGIS_LIVE_INITIAL_WAIT_SEC", "30.0")))
                probe_out = await self._run_live_p0y0m_probe_async(
                    camp=camp,
                    resolved=resolved,
                    clusters=clusters,
                    sample_fids_override=sample_fids,
                    checkpoint_state=progress_state,
                    checkpoint_save_cb=_save_ckpt,
                    progress_log_cb=_log,
                    initial_wait_sec=init_wait,
                )
                live_pnl_map = probe_out.get("pnl_map")
                measured_physics = probe_out.get("measured_physics") or {}
                live_probe_warning = probe_out.get("warning")
                for fid, phys in measured_physics.items():
                    if fid in resolved:
                        resolved[fid]["evidence_status"] = "MEASURED"
                        if phys.get("measured_coverage") is not None:
                            resolved[fid]["coverage"] = phys["measured_coverage"]
                        if phys.get("measured_update_frequency"):
                            resolved[fid]["update_frequency"] = phys["measured_update_frequency"]
                        if phys.get("measured_is_sparse") is not None:
                            resolved[fid]["is_sparse"] = phys["measured_is_sparse"]

                prof_resp = self._persist_and_format_profile(
                    store=store,
                    campaign_id=campaign_id,
                    resolved=resolved,
                    clusters=clusters,
                    live_pnl_map=live_pnl_map,
                    measured_physics=measured_physics,
                    live_probe_warning=live_probe_warning,
                )
                compact_summary = self._build_compact_profile_summary(prof_resp, job_id=job_id)
                store.update_job(job_id, status="COMPLETED", progress=progress_state, summary=compact_summary)
                return compact_summary if compact else prof_resp

            raise ValueError(f"不支持的作业类型: '{job_type}'")
        except Exception as exc:
            store.update_job(job_id, status="FAILED", progress=progress_state, error_message=str(exc))
            raise

    def execute_job(
        self,
        campaign_id: str,
        job_id: str,
        compact: bool = True,
        sim_executor: Optional[Callable[[dict, dict], Any]] = None,
        log_to_stderr: bool = False,
    ) -> Dict[str, Any]:
        return _run_coro_sync(
            self.execute_job_async(
                campaign_id=campaign_id,
                job_id=job_id,
                compact=compact,
                sim_executor=sim_executor,
                log_to_stderr=log_to_stderr,
            )
        )

    def list_jobs(self, campaign_id: str, status: Optional[str] = None) -> Dict[str, Any]:
        _, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")
        jobs = store.list_jobs(campaign_id, status=status)
        return {
            "campaign_id": campaign_id,
            "count": len(jobs),
            "jobs": [
                {
                    "job_id": j["job_id"],
                    "job_type": j["job_type"],
                    "hypothesis_id": j.get("hypothesis_id") or "",
                    "mode": j.get("mode") or "",
                    "status": j["status"],
                    "cli_command": self._job_cli_command(campaign_id, j["job_id"]),
                    "error_message": j.get("error_message") or "",
                    "updated_at": j.get("updated_at"),
                }
                for j in jobs
            ],
        }

    # ------------------------------------------------------------------
    # Tool 6: request_verdict (async + sync wrapper)
    # ------------------------------------------------------------------
    async def request_verdict_async(
        self,
        campaign_id: str,
        action: str,
        alpha_id: Optional[str] = None,
        expression: Optional[str] = None,
        sim_result: Optional[dict] = None,
        rationale: str = "",
        evidence_fetcher: Optional[Callable[[str, dict], Any]] = None,
    ) -> Dict[str, Any]:
        _, store = self._get_store(campaign_id)
        camp = store.get_campaign(campaign_id)
        if not camp:
            raise ValueError(f"未找到战役 '{campaign_id}'")

        act = str(action or "").strip().upper()
        summary = store.get_summary(campaign_id)

        if act == "CERTIFY_ALPHA":
            stored_exp = store.get_experiment_by_alpha_id(campaign_id, alpha_id) if alpha_id else None
            candidate: Dict[str, Any] = {}
            topo_key = ""
            core_skel = ""
            if stored_exp:
                try:
                    candidate = json.loads(stored_exp.get("raw_result_json") or "{}")
                except Exception:
                    candidate = {}
                candidate.setdefault("alpha_id", stored_exp.get("alpha_id"))
                candidate.setdefault("expression", stored_exp.get("expression"))
                topo_key = str(stored_exp.get("topology_key") or "")
                core_skel = str(stored_exp.get("core_skeleton") or "")
                if stored_exp.get("holdout_2y_sharpe") is not None:
                    candidate.setdefault("holdout_2y_sharpe", stored_exp["holdout_2y_sharpe"])
            if isinstance(sim_result, dict):
                candidate.update(sim_result)
            if alpha_id:
                candidate.setdefault("alpha_id", alpha_id)
            if expression:
                candidate.setdefault("expression", expression)
            candidate.setdefault("region", camp["region"])
            candidate.setdefault("universe", camp["universe"])
            candidate.setdefault("delay", camp["delay"])

            # Auto-enrich missing production evidence (yearly_stats, prod_corr, self_corr, checks)
            # Note: skip live network fetch when an explicit offline sim_result snapshot is supplied
            target_aid = candidate.get("alpha_id")
            if evidence_fetcher is not None and target_aid:
                extra = evidence_fetcher(str(target_aid), candidate)
                if asyncio.iscoroutine(extra):
                    extra = await extra
                if isinstance(extra, dict):
                    candidate.update(extra)
            elif target_aid and sim_result is None:
                bm = get_brain_module()
                if bm is not None:
                    candidate = await self._enrich_live_alpha_evidence_async(
                        bm,
                        str(target_aid),
                        candidate,
                        fetch_prod_corr=True,
                        fetch_self_corr=True,
                        fetch_yearly=True,
                    )

            # Auto-compute HorizonProbe verdict from campaign history if missing
            cand_expr = str(candidate.get("expression") or "")
            if cand_expr and not candidate.get("horizon_verdict"):
                if not topo_key:
                    topo_key = topology_equivalence_key(cand_expr)
                if not core_skel:
                    core_skel = ASTSandboxCorrector.get_core_skeleton(cand_expr)
                cand_sh = candidate.get("sharpe")
                if cand_sh is None and isinstance(candidate.get("is"), dict):
                    cand_sh = candidate["is"].get("sharpe")
                hv, h_rob, _ = self._compute_horizon_verdict_from_store(
                    store, campaign_id, cand_expr, cand_sh, topo_key, core_skel
                )
                if hv:
                    candidate["horizon_verdict"] = hv
                    candidate["horizon_robust"] = h_rob
                    candidate["plateau_pass"] = h_rob

            holdout = Gatekeeper.compute_internal_holdout_stats(candidate)
            if stored_exp and target_aid:
                store.update_experiment_evidence(
                    campaign_id=campaign_id,
                    alpha_id=str(target_aid),
                    raw_result=candidate,
                    prod_corr=Gatekeeper.extract_prod_corr(candidate),
                    self_corr=Gatekeeper.extract_self_corr(candidate),
                    is_core_sharpe=holdout.get("is_core_sharpe"),
                    holdout_2y_sharpe=holdout.get("holdout_2y_sharpe"),
                )

            gate_res = ProductionGate.evaluate(
                candidate,
                region=camp["region"],
                trial_count=max(20, int(summary.get("total_experiments", 0) or 20)),
            )
            reasons = list(gate_res.get("reasons", []))
            # Fail-Closed Holdout verification: missing yearly_stats MUST reject!
            if not holdout.get("holdout_verified"):
                reasons.append(
                    f"缺少 >= 3 年真实 yearly_stats (当前={holdout.get('yearly_count', 0)} 年)，"
                    f"Internal Holdout 近 2 年复核无法验证（Fail-Closed 拒签）"
                )
            elif not holdout.get("holdout_passed"):
                reasons.append(
                    f"内部 Holdout 近2年复核未通过: holdout_2y_sharpe={holdout['holdout_2y_sharpe']:.2f}, "
                    f"is_core={holdout['is_core_sharpe']:.2f}, ratio={holdout['holdout_ratio']:.2f}"
                )

            eligible = bool(gate_res.get("eligible") and holdout.get("holdout_verified") and holdout.get("holdout_passed"))
            verdict_str = "CERTIFIED_ALL_PASS" if eligible else "REJECTED"
            store.record_verdict(
                campaign_id=campaign_id,
                action=act,
                alpha_id=candidate.get("alpha_id"),
                expression=candidate.get("expression"),
                verdict=verdict_str,
                details={"reasons": reasons, "holdout": holdout, "evidence": gate_res.get("evidence")},
                rationale=rationale,
            )
            if eligible:
                ev = gate_res.get("evidence") or {}
                cert_doc = {
                    "alpha_id": candidate.get("alpha_id") or ev.get("alpha_id"),
                    "expression": candidate.get("expression") or ev.get("expression"),
                    "sharpe": ev.get("sharpe"),
                    "fitness": ev.get("fitness"),
                    "margin_bps": ev.get("margin_bps"),
                    "turnover": ev.get("turnover"),
                    "prod_corr": ev.get("prod_corr"),
                    "self_corr": ev.get("self_corr"),
                    **(gate_res.get("certificate") or {}),
                    "holdout": holdout,
                }
                champ_path = store.record_certified_champion(campaign_id, cert_doc)
                return {
                    "verdict": verdict_str,
                    "eligible": True,
                    "certificate": cert_doc,
                    "holdout": holdout,
                    "champions_file": champ_path,
                }

            rej_payload: Dict[str, Any] = {
                "verdict": verdict_str,
                "eligible": False,
                "reasons": reasons,
                "holdout": holdout,
                "evidence": gate_res.get("evidence"),
            }
            pcorr_now = Gatekeeper.extract_prod_corr(candidate)
            if pcorr_now is not None and pcorr_now >= 0.65:
                try:
                    rf = self._resolve_fields(camp)
                except FileNotFoundError:
                    rf = {}
                rej_payload["de_crowding_prescription"] = self._build_decrowding_prescription(cand_expr, pcorr_now, rf)
            return rej_payload

        if act == "DECLARE_EXHAUSTED":
            prof = store.get_dataset_profile(campaign_id)
            if not prof:
                res = {
                    "allowed": False,
                    "verdict": "DENIED_PREMATURE",
                    "missing_requirements": ["尚未调用 profile_dataset 完成特征有效秩 C_eff 测量，严禁空口宣告数据集穷尽"],
                }
            else:
                res = AntiLazinessAuditor.evaluate_exhaustion_gate(
                    store_summary=summary,
                    effective_rank=prof["effective_rank"],
                    has_vector_fields=prof["has_vector_fields"],
                )
            store.record_verdict(
                campaign_id=campaign_id,
                action=act,
                alpha_id=None,
                expression=None,
                verdict=res["verdict"],
                details=res,
                rationale=rationale,
            )
            return res

        raise ValueError(f"未知的判决动作 '{action}'，仅支持 CERTIFY_ALPHA 或 DECLARE_EXHAUSTED")

    def request_verdict(
        self,
        campaign_id: str,
        action: str,
        alpha_id: Optional[str] = None,
        expression: Optional[str] = None,
        sim_result: Optional[dict] = None,
        rationale: str = "",
        evidence_fetcher: Optional[Callable[[str, dict], Any]] = None,
    ) -> Dict[str, Any]:
        return _run_coro_sync(
            self.request_verdict_async(
                campaign_id=campaign_id,
                action=action,
                alpha_id=alpha_id,
                expression=expression,
                sim_result=sim_result,
                rationale=rationale,
                evidence_fetcher=evidence_fetcher,
            )
        )

    # ------------------------------------------------------------------
    # Tool 7: lookup_operators
    # ------------------------------------------------------------------
    @staticmethod
    def lookup_operators(query: str = "", category: str = "") -> Dict[str, Any]:
        matches = OperatorRegistry.lookup_operators(query=query, category=category)
        return {
            "count": len(matches),
            "operators": matches,
        }
