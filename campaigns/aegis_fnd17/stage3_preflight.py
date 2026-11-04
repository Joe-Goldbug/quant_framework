# -*- coding: utf-8 -*-
"""Stage 3 · 零配额预检器（独立于任何回测）

对候选表达式执行六重本地闸门：
  G1 语法/AST 合法性
  G2 引擎量纲审计（DimensionAuditor）：PV 污染 / 稀疏零偏移 / 双[-1,1]裸乘 / 算子数 / VECTOR 裸露
  G3 战役结构契约：字段数 2~3 / 算子数 <=4 / 窗口白名单 / 最外层零均值 / 黑名单算子 / add(rank,rank)
  G4 单位一致性人工标注核对（subtract 的两腿必须同为 per-share / 同为 % / 同为 total）
  G5 双盲红队逻辑保真（DoubleBlindRedTeam）
  G6 AST 骨架唯一性（单批同骨架 <=2）+ 指纹库跨批查重（历史 >=4 次熔断）

★ 修复点：ast.walk 的遍历顺序 **不是** 源码顺序，最外层算子必须用
  tree.body[0].value.func 直接取，不能用 calls[-1]。
"""
import ast, json, os, re, sys, hashlib, collections

import _paths
ROOT = _paths.ROOT
sys.path.insert(0, ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

# ---------------- 战役契约常量（与 AGENT_BRIEF.md 同源） ----------------
ALLOWED_WINDOWS = {3, 5, 10, 20, 60, 120, 252}
BACKFILL_WINDOWS = ALLOWED_WINDOWS | {250}          # ts_backfill 允许 250（跨两年）
MAX_OPS_PHASE0 = 4
MAX_OPS_TERMINAL = 6
ENGINE_MAX_OPS = 11
MIN_FIELDS, MAX_FIELDS = 2, 3

BANNED_OPS = {
    "group_neutralize",   # 引擎黑名单
    "bucket",             # 本账户 8 槽全 0.00
    "trade_when",         # 本账户实测有害
    "hump",               # 本账户有害
    "signed_power",       # 本账户有害
    "quantile", "ts_arg_max", "ts_arg_min",
    "reverse", "neg",     # 本战役黑名单
    "ts_neutralize",
}
ZERO_MEAN_TOP = {"zscore", "ts_zscore", "group_zscore", "ts_delta", "ts_av_diff",
                 "ts_rank", "ts_mean", "ts_decay_linear", "ts_decay_exp_window",
                 "ts_std_dev", "ts_corr"}
# 最外层绝对禁止（输出恒 [0,1] ⇒ 组合单边）
FORBIDDEN_TOP = {"group_rank", "rank", "quantile", "group_quantile", "bucket"}


def _calls_of(node):
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            out.append(getattr(n.func, "id", "") or getattr(n.func, "attr", ""))
    return out


def profile(node):
    """结构化判定一个 AST 子树的 (is_zero_mean, is_strictly_positive)。

    is_zero_mean        : 输出以 0 为对称中心（标准化/差分类构造，或这些构造的线性组合）
    is_strictly_positive: 输出恒 > 0（可作为 multiply 的恒正权重腿）
    """
    if isinstance(node, ast.Constant):
        v = node.value
        return (False, bool(isinstance(v, (int, float)) and v > 0))
    if not isinstance(node, ast.Call):
        return (False, False)
    fn = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
    args = node.args

    if fn in ("zscore", "ts_zscore", "group_zscore"):
        return (True, False)
    if fn in ("ts_delta", "ts_av_diff", "subtract"):
        return (True, False)
    if fn in ("ts_mean", "ts_sum", "ts_decay_linear", "ts_decay_exp_window",
              "ts_std_dev", "ts_max", "ts_min", "ts_corr", "ts_rank"):
        return (True, False)
    if fn in ("rank", "group_rank", "quantile", "group_quantile"):
        return (False, True)          # [0,1] ⇒ 恒非负 ⇒ 可当权重腿，但不可当零均值
    if fn in ("abs", "sqrt", "exp"):
        return (False, True)          # 非负输出 ⇒ 恒正权重腿
    if fn == "power":
        # ★ 2026-10-28 修正：整数幂**保号**（平台文档原文 "power(x, y) can drop the sign
        #   of x when y is non-integer" ⇒ 整数幂不丢符号）。
        #   奇数次幂作用在**对称零均值**信号上仍是对称零均值（x↦x^k 保持关于 0 的对称性）。
        #   本账户 USA/TOP1000/d1 新闻冠军正是 power(subtract(group_rank(x,g),0.5), 5) 结构
        #   （Sh 1.65~1.67 / Fit 0.95~0.97 / 零 CONCENTRATED_WEIGHT）⇒ 该结构必须被判为零均值。
        #   偶数次幂 / 非整数幂 ⇒ 丢符号 ⇒ 非负 ⇒ 恒正权重腿。
        exp = None
        if len(args) >= 2 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, (int, float)):
            exp = args[1].value
        base = profile(args[0]) if args else (False, False)
        if exp is not None and isinstance(exp, int) and exp % 2 == 1 and base[0]:
            return (True, False)      # 奇整数幂 + 零均值基 ⇒ 仍零均值
        return (False, True)
    if fn == "add":
        profiles = [profile(a) for a in args]
        # 全零均值 ⇒ 线性和仍零均值
        if profiles and all(p[0] for p in profiles):
            return (True, False)
        # 至少一条恒正、且无一条被判定为"可正可负的有符号量" ⇒ 恒正
        if profiles and any(p[1] for p in profiles) and not any(p[0] for p in profiles):
            return (False, True)
        return (True, False)
    if fn == "multiply":
        profiles = [profile(a) for a in args]
        # 有符号腿 × 恒正腿 ⇒ 近似零均值（引擎审计另行拦截双 [-1,1] 裸乘）
        if any(p[0] for p in profiles) and any(p[1] for p in profiles):
            return (True, False)
        return (False, False)
    if fn in ("ts_backfill", "winsorize", "s_log_1p", "log", "scale", "group_scale",
              "divide", "abs"):
        return profile(args[0]) if args else (False, False)
    return (False, False)

# 外部量价字段（跨数据集污染）
PV_FIELDS = {"close", "open", "high", "low", "vwap", "volume", "cap", "adv20",
             "returns", "sharesout", "split", "dividend"}

# 内嵌量价的 fnd17 字段（伪装形态）
PV_EMBEDDED_PAT = re.compile(
    r"fnd17_(nprice|mktcap|ev_cur|pr1dayprc|priceavg|price2bk|peexclxor|spfcr|"
    r"ebitda2ev|awcappspr|qwcappspr|yield|vol|pr1day|mktcap)", re.I)

# 量纲族标注：用于 G4 单位一致性核对
# 优先级：per_share > ratio-like > percent > total > unbounded
# 关键：ROA/ROE/margin/payout/tax rate 本质都是百分比口径，必须先于 "total" 判定，
# 否则 "Return on average assets" 会被 "assets" 误判为总额口径。
_UNIT_RULES = [
    # 百分比优先：'Percent change in TTM EPS' 这类'增速'口径本质是百分比，
    # 即使它修饰的底层量是每股口径 —— 它与另一个 % 字段相减才是合法的。
    ("percent",   re.compile(r"(percent change|percentage change|percent\s|%|growth rate|change %|"
                            r"percent of|as a percent)", re.I)),
    ("per_share", re.compile(r"(per share|pershare|/share|earnings per share|\beps\b|_ps\b)", re.I)),
    ("percent",   re.compile(r"(return on |margin|payout ratio|effective tax rate|tax rate|"
                            r"interest rate|rate for)", re.I)),
    ("ratio",     re.compile(r"(ratio|per employee|turnover|coverage|current ratio|quick ratio)", re.I)),
    ("total",     re.compile(r"(total|revenue|net income|ebitda|\bebit\b|assets|equity|debt|"
                            r"dividends paid|taxes paid|employees|shares outstanding|book value)", re.I)),
]


def unit_family(desc: str) -> str:
    """粗粒度量纲族标注（用于 subtract 两腿可比性核对）。"""
    d = desc or ""
    for fam, pat in _UNIT_RULES:
        if pat.search(d):
            return fam
    return "unbounded"


def ast_calls(expr: str):
    tree = ast.parse(expr, mode="eval")
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            calls.append(fn)
    # ★ 最外层算子：直接取 AST 根节点的 func，绕开 ast.walk 顺序问题
    #   mode='eval' 时 ast.parse 返回 Expression，其 .body 即根节点（可能已是 Call）
    root = tree.body if isinstance(tree.body, ast.Call) else tree.body[0].value
    top = getattr(root.func, "id", "") if isinstance(root, ast.Call) else ""
    return calls, tree, top


def field_ids(expr: str):
    return sorted(set(re.findall(r"\bfnd17_[a-z0-9_]+\b", expr)))


def numeric_windows(expr: str):
    """抽取时序窗口参数（ts_* 算子的第二个及以后位置参数 + winsorize 的 std）。"""
    tree = ast.parse(expr, mode="eval")
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = getattr(n.func, "id", "")
            if fn.startswith("ts_") or fn == "winsorize":
                for a in n.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, (int, float)):
                        out.append((fn, a.value))
    return out


def subtract_legs(tree, fields_meta):
    """找出所有 subtract 调用的两腿字段，供单位一致性核对。"""
    legs = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "subtract" and len(n.args) == 2:
            pair = []
            for a in n.args:
                if isinstance(a, ast.Name):
                    pair.append(a.id)
                elif isinstance(a, ast.Call):
                    sub = sorted(set(re.findall(r"\bfnd17_[a-z0-9_]+\b", ast.unparse(a))))
                    pair.append(sub[0] if len(sub) == 1 else "|".join(sub) if sub else None)
                else:
                    pair.append(None)
            legs.append(pair)
    return legs


def preflight(expr: str, optimize_reason: str, counterparty: str,
              known_fields: dict, fields_meta: dict, phase0: bool = True,
              op_cap_override: int = None) -> dict:
    """返回 {ok, issues[], checks{}}

    op_cap_override: 显式覆盖算子数上限。默认 Phase0 ≤4 / Phase2 ≤6（战役简约律）。
        ★ 例外授权（2026-10-28）：当移植**已在平台通关验证**的既有 alpha 结构时，
          忠实复刻原结构优先于本地简约律 —— 引擎硬上限是 11。此参数仅用于此类诊断批次。
    """
    issues, checks = [], {}

    # ---------- G1 语法 ----------
    try:
        calls, tree, top = ast_calls(expr)
        checks["syntax_ok"] = True
    except SyntaxError as e:
        return {"ok": False, "issues": [f"G1 语法错误: {e}"], "checks": {"syntax_ok": False}}

    checks["top_level"] = top
    checks["operator_count"] = len(calls)
    checks["field_count"] = len(field_ids(expr))

    # ---------- G3 战役结构契约 ----------
    op_cap = op_cap_override if op_cap_override is not None else (
        MAX_OPS_PHASE0 if phase0 else MAX_OPS_TERMINAL)
    checks["operator_count_ok"] = len(calls) <= op_cap
    if not checks["operator_count_ok"]:
        issues.append(f"G3 算子数 {len(calls)} > {op_cap}（Phase{0 if phase0 else 2} 上限）")

    checks["field_count_ok"] = MIN_FIELDS <= checks["field_count"] <= MAX_FIELDS
    if not checks["field_count_ok"]:
        issues.append(f"G3 字段数 {checks['field_count']} 不在 [{MIN_FIELDS},{MAX_FIELDS}]")

    # 最外层零均值：用结构化判定而非扁平白名单
    root = tree.body if isinstance(tree.body, ast.Call) else tree.body[0].value
    zm, pos = profile(root)
    checks["top_level_zero_mean_ok"] = bool(zm) and top not in FORBIDDEN_TOP
    checks["top_level_profile"] = {"zero_mean": zm, "strictly_positive": pos}
    if not checks["top_level_zero_mean_ok"]:
        issues.append(f"G3 最外层算子 '{top}' 输出非零均值（顶层 group_rank/rank ⇒ 组合单边）")

    bad_ops = [c for c in calls if c in BANNED_OPS]
    checks["banned_ops"] = bad_ops
    if bad_ops:
        issues.append(f"G3 黑名单算子: {sorted(set(bad_ops))}")

    # add(rank, rank) 物理拦截
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "add" and len(n.args) == 2:
            f = [getattr(a.func, "id", "") for a in n.args if isinstance(a, ast.Call)]
            if len(f) == 2 and f[0] in ("rank", "group_rank") and f[1] in ("rank", "group_rank"):
                issues.append("G3 add(rank, rank) 无量纲加总（引擎物理拦截）")

    # multiply 的权重腿必须恒正（结构化判定，而非关键词）
    mult_issues = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "multiply" and len(n.args) >= 2:
            legs = [profile(a) for a in n.args]
            if not any(leg[1] for leg in legs):
                # 没有一条腿被判定为恒正 ⇒ 可能是双有符号裸乘
                signed = [leg[0] for leg in legs]
                if all(signed):
                    mult_issues.append(
                        f"multiply 的两腿均非恒正（{', '.join(sorted(set(re.findall(r'fnd17_[a-z0-9_]+', ast.unparse(n)))))}）"
                        "⇒ 可能是双有符号裸乘伪因果")
    checks["multiply_legs_ok"] = not mult_issues
    if mult_issues:
        issues.append("G3 " + "; ".join(mult_issues))

    # PV 污染
    pv_hits = [t for t in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr) if t in PV_FIELDS]
    pv_emb = PV_EMBEDDED_PAT.findall(expr)
    checks["pv_clean"] = not pv_hits and not pv_emb
    if pv_hits:
        issues.append(f"G3 外部量价污染: {sorted(set(pv_hits))}")
    if pv_emb:
        issues.append(f"G3 内嵌量价字段污染: {sorted(set(pv_emb))}")

    # 字段真实性
    fids = field_ids(expr)
    unknown = [f for f in fids if f not in known_fields]
    checks["fields_used"] = fids
    checks["field_truth_ok"] = not unknown
    if unknown:
        issues.append(f"G3 字段不存在于 fundamental17 可用池: {unknown}")

    # 窗口白名单
    wins = numeric_windows(expr)
    checks["windows"] = wins
    bad_w = [(f, v) for f, v in wins
             if not (v in ALLOWED_WINDOWS or (f == "ts_backfill" and v in BACKFILL_WINDOWS))]
    checks["window_ok"] = not bad_w
    if bad_w:
        issues.append(f"G3 窗口不在白名单 {sorted(ALLOWED_WINDOWS)}: {bad_w}")

    # ---------- G2 引擎量纲审计 ----------
    audit = DimensionAuditor.audit_expression(expr, fields_meta, category="fundamental",
                                              allow_pv_cross=False, max_operators=ENGINE_MAX_OPS)
    checks["dimension_audit"] = {"is_valid": audit["is_valid"], "issues": audit["issues"],
                                 "operator_count": audit.get("operator_count")}
    if not audit["is_valid"]:
        issues.append(f"G2 量纲审计失败: {audit['issues']}")

    # ---------- G4 单位一致性 ----------
    legs = subtract_legs(tree, fields_meta)
    checks["subtract_legs"] = legs
    unit_issues = []
    for a, b in legs:
        if not a or not b or "|" in a or "|" in b:
            continue
        fa = fields_meta.get(a, {}).get("description", "")
        fb = fields_meta.get(b, {}).get("description", "")
        ua, ub = unit_family(fa), unit_family(fb)
        if ua != ub and "unbounded" not in (ua, ub):
            unit_issues.append(f"subtract({a}[{ua}], {b}[{ub}]) 量纲族不一致")
    checks["unit_consistent"] = not unit_issues
    if unit_issues:
        issues.append("G4 " + "; ".join(unit_issues))

    # ---------- G5 双盲红队 ----------
    blind = DoubleBlindRedTeam.generate_blind_payload(
        expr, {"mechanism": optimize_reason, "counterparty": counterparty or "未明确对手盘"},
        fields_meta)
    rt = DoubleBlindRedTeam.audit_candidate_blindly(blind)
    checks["engine_redteam"] = {"verdict": rt["verdict"], "issues": rt["issues"]}
    if rt["verdict"] != "PASS":
        issues.append(f"G5 红队审判: {rt['issues']}")

    return {"ok": not issues, "issues": issues, "checks": checks}


def skeleton_and_fingerprint(exprs, region="USA", universe="TOP1000", delay=1,
                            neutralization="STATISTICAL", db_path=None):
    """G6 骨架唯一性 + 跨批指纹查重（只读，不写库）。"""
    corr = ASTSandboxCorrector(db_path=db_path or os.path.join(ROOT, "quant_framework", "alphas_record.db"))
    skels = [corr.get_canonical_skeleton(e) for e in exprs]
    freq = collections.Counter(skels)
    res = {"skeletons": skels, "freq": dict(freq), "violations": [], "history": {}}
    for sk, n in freq.items():
        if n > 2:
            res["violations"].append(f"同骨架 x{n}: {sk}")
    import sqlite3
    db = sqlite3.connect(db_path or os.path.join(ROOT, "quant_framework", "alphas_record.db"))
    cur = db.cursor()
    for sk in skels:
        h = corr.compute_skeleton_hash(sk)
        cur.execute("SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash=? AND region=? AND universe=?",
                    (h, region, universe))
        n = cur.fetchone()[0]
        res["history"][sk] = n
        if n >= 4:
            res["violations"].append(f"跨批骨架已测 {n} 次 (>=4 上限): {sk[:80]}")
    db.close()
    return res


def load_meta():
    """加载 fundamental17 字段元数据。

    ★ 鲁棒性（2026-10-29）：共享 KB 文件 knowledge_base/fields/USA/fundamental17.json
      可能在别处被改写为 list 形态（丢失 semantic_role / domain），导致原实现
      kb["fields"] 直接 TypeError、且 INVALID 字段筛选失效（402 vs 289）。
      本实现按「元数据完整度」排序择优：带 semantic_role 的 dict 形态优先
      （战役本地副本 campaigns/aegis_fnd17/knowledge_base/fundamental17.json 保留完整元数据），
      其次是无 semantic_role 的 dict，最后才退化为 list 形态兼容解析。
    """
    kb_path = os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental17.json")
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "knowledge_base", "fundamental17.json")
    cands = []
    for p in (kb_path, local_path):
        if not os.path.exists(p):
            continue
        try:
            raw = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, dict) and isinstance(raw.get("fields"), dict):
            F = raw["fields"]
            has_role = any("semantic_role" in v for v in F.values() if isinstance(v, dict))
            cands.append((0 if has_role else 1, F))
        elif isinstance(raw, list):
            cands.append((2, {e["id"]: {
                "description": e.get("description", ""),
                "semantic_role": e.get("semantic_role", "Signal_Flow"),
                "domain": e.get("domain", "unbounded"),
                "is_sparse": e.get("is_sparse", False),
                "coverage": e.get("coverage", 0),
                "alphaCount": e.get("alphaCount", 0),
                "type": e.get("type", "MATRIX"),
            } for e in raw if isinstance(e, dict) and "id" in e}))
    if not cands:
        raise FileNotFoundError(f"fundamental17 字段元数据不可用: {kb_path} / {local_path}")
    F = sorted(cands, key=lambda x: x[0])[0][1]
    valid = {k: v for k, v in F.items() if not v.get("semantic_role", "Signal_Flow").startswith("INVALID")}
    meta = {}
    for k, v in valid.items():
        meta[k] = {"type": v.get("type", "MATRIX"), "domain": v.get("domain", "unbounded"),
                   "is_sparse": v.get("is_sparse", False),
                   "description": v.get("description", ""),
                   "alphaCount": v.get("alphaCount", 0),
                   "coverage": v.get("coverage", 0)}
    return meta


if __name__ == "__main__":
    meta = load_meta()
    print(f"meta fields: {len(meta)}")
    demo = "zscore(winsorize(subtract(fnd17_tcpaormtt, fnd17_tcpaormtp), std=3))"
    r = preflight(demo, "捕捉资产回报率的边际变化", "锚定历史中枢的机械型资金", meta, meta)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1600])
