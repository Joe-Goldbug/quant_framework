# -*- coding: utf-8 -*-
"""V2 cross-dataset preflight for axis B (4 permitted datasets). Local only, zero quota."""
import ast, json, os, re, sys

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, os.path.join(ROOT, "quant_framework"))
sys.path.insert(0, ROOT)
sys.path.insert(0, CAMP)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

KB = os.path.join(ROOT, "quant_framework", "knowledge_base", "fields", "USA")
PERMITTED = ["other466", "fundamental3", "fundamental13", "fundamental23"]

# field-id -> dataset, from KB (authoritative)
FIELDS = {}
for ds in PERMITTED:
    raw = json.load(open(os.path.join(KB, ds + ".json"), encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("fields", [])
    for e in raw:
        if isinstance(e, dict) and "id" in e:
            FIELDS[e["id"]] = {"ds": ds, "desc": e.get("description", ""),
                               "cov": e.get("coverage", 0), "ac": e.get("alphaCount", 0),
                               "uc": e.get("userCount", 0), "type": e.get("type", "MATRIX")}

OPS = {
    "add","subtract","divide","multiply","abs","sign","power","signed_power","sqrt","log","s_log_1p",
    "exp","max","min","rank","group_rank","quantile","group_quantile","scale","group_scale","zscore",
    "group_zscore","ts_mean","ts_sum","ts_std_dev","ts_min","ts_max","ts_rank","ts_delta","ts_delay",
    "ts_corr","ts_decay_linear","ts_decay_exp_window","trade_when","if_else","winsorize","hump",
    "group_neutralize","jump_decay","vec_avg","vec_sum","vec_choose","vec_count","vec_max","vec_min",
    "vec_std","vec_norm","vec_percentage","vec_ir","regression_neut","ts_av_diff","ts_target_tvr_decay",
    "truncate","filter","ts_std","ts_moving_average","ts_avg","decay_linear","ts_decay_exponential",
    "ts_decay_exp","sub","div","neg","std","corr","group_cartesian_product","bucket","ts_mean_",
}
GROUPS = {"market","sector","industry","subindustry"}
PV = {"close","open","high","low","vwap","volume","cap","adv20","returns","sharesout","split","dividend"}
BANNED = {"group_neutralize","bucket","trade_when","hump","signed_power","quantile","ts_arg_max",
          "ts_arg_min","reverse","neg","ts_neutralize"}
ZERO_MEAN_TOP = {"zscore","ts_zscore","group_zscore","ts_delta","ts_av_diff","ts_rank","ts_mean",
                 "ts_decay_linear","ts_decay_exp_window","ts_std_dev","ts_corr","subtract","power"}
ALLOWED_WINDOWS = {3,5,10,20,60,120,252}
BACKFILL_WINDOWS = ALLOWED_WINDOWS | {250}


def _meta_dict():
    m = {}
    for fid, e in FIELDS.items():
        m[fid] = {"type": e["type"], "domain": "unbounded", "is_sparse": False,
                  "description": e["desc"], "alphaCount": e["ac"], "coverage": e["cov"]}
    return m


META = _meta_dict()


def expr_fields(expr):
    """All dataset fields referenced, via AST name extraction."""
    tree = ast.parse(expr, mode="eval")
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            if n.id in OPS or n.id in GROUPS or n.id in PV:
                continue
            out.add(n.id)
    return sorted(out)


def calls_of(expr):
    tree = ast.parse(expr, mode="eval")
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            calls.append(getattr(n.func, "id", "") or getattr(n.func, "attr", ""))
    body = tree.body
    if isinstance(body, ast.Call):
        root = body
    elif isinstance(body, ast.Expression) and isinstance(body.value, ast.Call):
        root = body.value
    else:
        root = None
    top = (getattr(root.func, "id", "") or getattr(root.func, "attr", "")) if root is not None else None
    return calls, tree, top


def numeric_windows(expr):
    tree = ast.parse(expr, mode="eval")
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            if fn.startswith("ts_") or fn == "winsorize":
                for a in n.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, (int, float)):
                        out.append((fn, a.value))
    return out


def zero_mean_top(expr):
    """Structural zero-mean check (mirrors stage3_preflight.profile semantics)."""
    tree = ast.parse(expr, mode="eval")
    body = tree.body
    root = body if isinstance(body, ast.Call) else (body.value if isinstance(body, ast.Expression) and isinstance(body.value, ast.Call) else None)
    fn = getattr(root.func, "id", "") or getattr(root.func, "attr", "")
    if fn in ("zscore","ts_zscore","group_zscore","subtract","ts_delta","ts_av_diff"):
        return True, fn
    if fn == "power":
        args = root.args
        if len(args) >= 2 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, int) and args[1].value % 2 == 1:
            return True, fn
        return False, fn
    return False, fn


def preflight_v2(expr, mechanism, counterparty, max_ops=6, max_fields=3, max_datasets=2, min_cov=0.55):
    issues, checks = [], {}
    try:
        calls, tree, top = calls_of(expr)
    except SyntaxError as e:
        return {"ok": False, "issues": [f"G1 语法错误: {e}"], "checks": {}}

    fids = expr_fields(expr)
    dss = sorted({FIELDS[f]["ds"] for f in fids if f in FIELDS})
    checks["operator_count"] = len(calls)
    checks["field_count"] = len(fids)
    checks["fields_used"] = fids
    checks["datasets_used"] = dss
    checks["dataset_count"] = len(dss)
    checks["top_level"] = top

    if len(calls) > max_ops:
        issues.append(f"G3 算子数 {len(calls)} > {max_ops}")
    if not (2 <= len(fids) <= max_fields):
        issues.append(f"G3 字段数 {len(fids)} 不在 [2,{max_fields}]")
    if len(dss) > max_datasets:
        issues.append(f"G7 数据集数 {len(dss)} > {max_datasets}: {dss}")

    zm, ztop = zero_mean_top(expr)
    checks["top_level_zero_mean"] = zm
    if not zm:
        issues.append(f"G3 最外层 '{top}' 非零均值构造")
    if top in ("group_rank", "rank", "quantile", "group_quantile", "bucket"):
        issues.append(f"G3 顶层 {top} 输出恒 [0,1] ⇒ 组合单边")

    bad = sorted({c for c in calls if c in BANNED})
    checks["banned_ops"] = bad
    if bad:
        issues.append(f"G3 黑名单算子: {bad}")

    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "add" and len(n.args) == 2:
            f = [getattr(a.func, "id", "") for a in n.args if isinstance(a, ast.Call)]
            if len(f) == 2 and f[0] in ("rank","group_rank") and f[1] in ("rank","group_rank"):
                issues.append("G3 add(rank, rank) 物理拦截")

    pv_hits = sorted({t for t in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr) if t in PV})
    checks["pv_clean"] = not pv_hits
    if pv_hits:
        issues.append(f"G3 外部量价污染: {pv_hits}")
    pv_desc = [f for f in fids if f in FIELDS and re.search(r"market cap|market capitalization|mktcap", FIELDS[f]["desc"], re.I)]
    checks["pv_desc_fields"] = pv_desc
    if pv_desc:
        issues.append(f"G3 字段语义含市值: {pv_desc}")

    unknown = [f for f in fids if f not in FIELDS]
    checks["field_truth_ok"] = not unknown
    if unknown:
        issues.append(f"G3 字段不存在于 4 个许可数据集: {unknown}")
    lowcov = [(f, FIELDS[f]["cov"]) for f in fids if f in FIELDS and (FIELDS[f]["cov"] or 0) < min_cov]
    checks["low_cov_fields"] = lowcov
    if lowcov:
        issues.append(f"G3 字段覆盖率 < {min_cov}: {lowcov}")

    wins = numeric_windows(expr)
    checks["windows"] = wins
    badw = [(f, v) for f, v in wins if not (v in ALLOWED_WINDOWS or (f == "ts_backfill" and v in BACKFILL_WINDOWS))]
    checks["window_ok"] = not badw
    if badw:
        issues.append(f"G3 窗口越界: {badw}")

    audit = DimensionAuditor.audit_expression(expr, META, category="fundamental",
                                              allow_pv_cross=False, max_operators=11)
    checks["dimension_audit"] = {"is_valid": audit["is_valid"], "issues": audit["issues"]}
    if not audit["is_valid"]:
        issues.append(f"G2 量纲审计失败: {audit['issues']}")

    blind = DoubleBlindRedTeam.generate_blind_payload(expr, {"mechanism": mechanism, "counterparty": counterparty}, META)
    rt = DoubleBlindRedTeam.audit_candidate_blindly(blind)
    checks["redteam"] = {"verdict": rt["verdict"], "issues": rt["issues"]}
    if rt["verdict"] != "PASS":
        issues.append(f"G5 红队: {rt['issues']}")

    checks["unit_audit_note"] = "subtract 两腿量纲需人工核对（preflight 自动族判仅对同数据集生效）"
    checks["field_meta"] = {f: {"ds": FIELDS[f]["ds"], "cov": FIELDS[f]["cov"], "ac": FIELDS[f]["ac"],
                                "desc": FIELDS[f]["desc"][:90]} for f in fids if f in FIELDS}
    return {"ok": not issues, "issues": issues, "checks": checks}


def skeleton_history(exprs, region="USA", universe="TOP1000", delay=1):
    """Cross-batch skeleton history (read-only) + intra-batch duplicate detection."""
    import sqlite3
    db = os.path.join(ROOT, "quant_framework", "alphas_record.db")
    corr = ASTSandboxCorrector(db_path=db)
    skels = [corr.get_canonical_skeleton(e) for e in exprs]
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    hist = {}
    for sk in skels:
        h = corr.compute_skeleton_hash(sk)
        cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash=? AND region=? AND universe=?",
                    (h, region, universe))
        hist[sk] = cur.fetchone()[0]
    conn.close()
    return skels, hist
