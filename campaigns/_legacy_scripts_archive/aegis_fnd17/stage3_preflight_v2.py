# -*- coding: utf-8 -*-
"""战役 V2 预检器 —— 多基本面数据集（≤2 数据集/表达式）

与 stage3_preflight.py 的差别：
  1. 字段池从单数据集（fundamental17）扩到 10 个基本面数据集的并集
  2. 新增 G7 数据集数闸门（≤2 个不同数据集）
  3. 新增 G8 覆盖率闸门（每字段 coverage ≥ 0.50）
  4. 新增 G9 拥挤度闸门（alphaCount ≤ 5，冷字段）
  5. subtract_legs 的字段抽取从写死 fnd17_ 改为通用数据集前缀
  6. PV 污染检测改为"按字段元数据判定"，避免 oth466_a_cap 这类误伤

沿用 stage3_preflight 的 G1~G6 全部逻辑（六重本地闸门）。
"""
import ast
import collections
import json
import os
import re
import sys

import _paths

ROOT = _paths.ROOT
sys.path.insert(0, ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

import stage3_preflight as P

# ---------------- V2 契约常量 ----------------
FUND_DATASETS = [
    "fundamental17", "fundamental69", "fundamental89", "other395", "fundamental3",
    "other466", "fundamental13", "fundamental77", "fundamental23", "fundamental45",
]
MAX_DATASETS = 2
MAX_OPS_V2 = 6
MAX_FIELDS_V2 = 3
MIN_COVERAGE = 0.50
MAX_ALPHA_COUNT = 5

# 数据集前缀 → 数据集 id（注意 oth466 的字段是 oth466_xxx，不是 oth466_a_xxx）
DS_PREFIX_RE = re.compile(r"\b(fnd17|fnd69|fnd89|fnd25|fnd3|fnd13|fnd23|fnd77|fnd45|"
                          r"oth395|oth466|oth401|oth143|oth566)\b")

KB_DIR = os.path.join(ROOT, "knowledge_base", "fields", "USA")


def load_multids_meta(datasets=None):
    """加载多数据集字段元数据（并集）。返回 {field_id: meta}。"""
    datasets = datasets or FUND_DATASETS
    meta = {}
    for ds in datasets:
        p = os.path.join(KB_DIR, f"{ds}.json")
        if not os.path.exists(p):
            continue
        try:
            raw = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        rows = raw if isinstance(raw, list) else (raw.get("fields") or [])
        if isinstance(rows, dict):
            rows = [{"id": k, **v} for k, v in rows.items()]
        for e in rows:
            if not isinstance(e, dict) or "id" not in e:
                continue
            fid = e["id"]
            meta[fid] = {
                "type": e.get("type", "MATRIX"),
                "description": e.get("description", ""),
                "coverage": e.get("coverage", 0),
                "alphaCount": e.get("alphaCount", 0),
                "userCount": e.get("userCount", 0),
                "dataset": (e.get("dataset") or {}).get("id", ds),
            }
    return meta


def datasets_in(expr, meta=None):
    """表达式涉及的数据集集合。优先按字段元数据的 dataset 归属判定，
    回退到前缀正则。"""
    ds = set()
    for fid in P.field_ids(expr):
        if meta and fid in meta and meta[fid].get("dataset"):
            ds.add(meta[fid]["dataset"])
            continue
        m = re.match(r"^([a-z]+\d+)_", fid)
        if m:
            ds.add(m.group(1))
    return ds


def pv_pollution(expr, meta):
    """PV 污染判定：按字段元数据的 description 语义判定，避免误伤
    oth466_a_cap（资本支出）这类名字里含 cap 的基本面字段。"""
    hits = []
    for fid in P.field_ids(expr):
        desc = (meta.get(fid, {}) or {}).get("description", "") or ""
        low = desc.lower()
        if re.search(r"\b(market cap|market capital|share price|closing price|"
                     r"trading volume|price to (book|earnings)|p/e ratio)\b", low):
            hits.append(fid)
    # 裸量价标识符（不在任何已��基本面字段池里的）
    for t in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr):
        if t in ("close", "open", "high", "low", "vwap", "volume", "adv20", "returns"):
            hits.append(t)
    return sorted(set(hits))


def preflight_v2(expr, optimize_reason, counterparty, meta,
                 op_cap=MAX_OPS_V2, max_datasets=MAX_DATASETS,
                 max_fields=MAX_FIELDS_V2, min_coverage=MIN_COVERAGE,
                 max_alpha_count=MAX_ALPHA_COUNT):
    """七重闸门：G1 语法 / G2 量纲 / G3 结构 / G4 单位 / G5 红队 / G6 骨架 /
       G7 数据集数 / G8 覆盖率 / G9 拥挤度。返回 {ok, issues[], checks{}}"""
    issues, checks = [], {}

    # ---------- G1 语法 ----------
    try:
        calls, tree, top = P.ast_calls(expr)
        checks["syntax_ok"] = True
    except SyntaxError as e:
        return {"ok": False, "issues": [f"G1 语法错误: {e}"],
                "checks": {"syntax_ok": False}}

    checks["top_level"] = top
    checks["operator_count"] = len(calls)
    fids = P.field_ids(expr)
    checks["field_count"] = len(fids)
    checks["fields_used"] = fids

    # ---------- G7 数据集数闸门（V2 新增） ----------
    dss = datasets_in(expr, meta)
    checks["datasets_used"] = sorted(dss)
    checks["dataset_count"] = len(dss)
    checks["dataset_count_ok"] = len(dss) <= max_datasets
    if not checks["dataset_count_ok"]:
        issues.append(f"G7 数据集数 {len(dss)} > {max_datasets}: {sorted(dss)}")

    # ---------- G3 结构契约 ----------
    checks["operator_count_ok"] = len(calls) <= op_cap
    if not checks["operator_count_ok"]:
        issues.append(f"G3 算子数 {len(calls)} > {op_cap}")
    checks["field_count_ok"] = len(fids) <= max_fields
    if not checks["field_count_ok"]:
        issues.append(f"G3 字段数 {len(fids)} > {max_fields}")

    root = tree.body if isinstance(tree.body, ast.Call) else tree.body[0].value
    zm, pos = P.profile(root)
    checks["top_level_zero_mean_ok"] = bool(zm) and top not in P.FORBIDDEN_TOP
    checks["top_level_profile"] = {"zero_mean": zm, "strictly_positive": pos}
    if not checks["top_level_zero_mean_ok"]:
        issues.append(f"G3 最外层算子 '{top}' 输出非零均值")

    bad_ops = [c for c in calls if c in P.BANNED_OPS]
    checks["banned_ops"] = bad_ops
    if bad_ops:
        issues.append(f"G3 黑名单算子: {sorted(set(bad_ops))}")

    # ---------- G8/G9 覆盖率与拥挤度（V2 新增） ----------
    low_cov = []
    crowded = []
    unknown = []
    for f in fids:
        m = meta.get(f)
        if not m:
            unknown.append(f)
            continue
        if (m.get("coverage") or 0) < min_coverage:
            low_cov.append((f, m.get("coverage")))
        if (m.get("alphaCount") or 0) > max_alpha_count:
            crowded.append((f, m.get("alphaCount")))
    checks["field_truth_ok"] = not unknown
    if unknown:
        issues.append(f"G3 字段不在任何基本面数据集池中: {unknown}")
    checks["coverage_ok"] = not low_cov
    if low_cov:
        issues.append(f"G8 覆盖率 < {min_coverage}: {low_cov}")
    checks["crowding_ok"] = not crowded
    if crowded:
        issues.append(f"G9 拥挤度 alphaCount > {max_alpha_count}: {crowded}")

    # ---------- PV 污染（语义判定） ----------
    pv = pv_pollution(expr, meta)
    checks["pv_clean"] = not pv
    if pv:
        issues.append(f"G3 PV/量价污染: {pv}")

    # ---------- 窗口白名单 ----------
    wins = P.numeric_windows(expr)
    checks["windows"] = wins
    bad_w = [(f, v) for f, v in wins
             if not (v in P.ALLOWED_WINDOWS or (f == "ts_backfill" and v in P.BACKFILL_WINDOWS))]
    checks["window_ok"] = not bad_w
    if bad_w:
        issues.append(f"G3 窗口不在白名单: {bad_w}")

    # ---------- G2 量纲审计 ----------
    audit = DimensionAuditor.audit_expression(expr, meta, category="fundamental",
                                              allow_pv_cross=False, max_operators=P.ENGINE_MAX_OPS)
    checks["dimension_audit"] = {"is_valid": audit["is_valid"], "issues": audit["issues"],
                                 "operator_count": audit.get("operator_count")}
    if not audit["is_valid"]:
        issues.append(f"G2 量纲审计失败: {audit['issues']}")

    # ---------- G4 单位一致性（通用数据集前缀） ----------
    legs = subtract_legs_v2(tree, meta)
    checks["subtract_legs"] = legs
    unit_issues = []
    for a, b in legs:
        if not a or not b or "|" in a or "|" in b:
            continue
        fa = meta.get(a, {}).get("description", "")
        fb = meta.get(b, {}).get("description", "")
        ua, ub = P.unit_family(fa), P.unit_family(fb)
        if ua != ub and "unbounded" not in (ua, ub):
            unit_issues.append(f"subtract({a}[{ua}], {b}[{ub}]) 量纲族不一致")
    checks["unit_consistent"] = not unit_issues
    if unit_issues:
        issues.append("G4 " + "; ".join(unit_issues))

    # ---------- G5 双盲红队 ----------
    blind = DoubleBlindRedTeam.generate_blind_payload(
        expr, {"mechanism": optimize_reason, "counterparty": counterparty or "未明确对手盘"},
        meta)
    rt = DoubleBlindRedTeam.audit_candidate_blindly(blind)
    checks["engine_redteam"] = {"verdict": rt["verdict"], "issues": rt["issues"]}
    if rt["verdict"] != "PASS":
        issues.append(f"G5 红队审判: {rt['issues']}")

    return {"ok": not issues, "issues": issues, "checks": checks}


def subtract_legs_v2(tree, meta):
    """找出所有 subtract 调用的两腿字段（通用数据集前缀）。"""
    legs = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "subtract" and len(n.args) == 2:
            pair = []
            for a in n.args:
                if isinstance(a, ast.Name):
                    pair.append(a.id)
                elif isinstance(a, ast.Call):
                    sub = sorted(set(DS_PREFIX_RE.pattern and
                                     re.findall(r"\b(?:fnd|oth)[a-z0-9]*_[a-z0-9_]+\b",
                                                ast.unparse(a))))
                    pair.append(sub[0] if len(sub) == 1 else "|".join(sub) if sub else None)
                else:
                    pair.append(None)
            legs.append(pair)
    return legs


def skeleton_check(exprs, region="USA", universe="TOP1000", delay=1):
    """G6 骨架唯一性 + 跨批指纹查重。"""
    return P.skeleton_and_fingerprint(exprs, region=region, universe=universe, delay=delay)


if __name__ == "__main__":
    meta = load_multids_meta()
    print(f"多数据集字段池: {len(meta)} 字段")
    by_ds = collections.Counter(m["dataset"] for m in meta.values())
    for k, v in sorted(by_ds.items(), key=lambda x: -x[1]):
        print(f"   {k:<16}{v}")
