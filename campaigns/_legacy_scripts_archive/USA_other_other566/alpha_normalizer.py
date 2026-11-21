"""
alpha_normalizer.py — normalize the platform's two alpha payload shapes into one.

Shape A (brain-mcp `fetch_multi_simulation_result`):
    {"code": ..., "metrics": {...}, "checks": {"fail": [...], "warning": [...]}}

Shape B (direct GET /alphas/{id}, what ace_lib returns):
    {"regular": {"code": ...}, "is": {"sharpe": ..., "checks": [ {name, result, value, limit}, ... ]},
     "ra": {...}, "pyramids": {...}}

`normalize(alpha)` returns a flat dict with the keys collect_ledger.py expects.
"""

IS_KEYS = ("sharpe", "fitness", "turnover", "returns", "drawdown", "margin",
           "pnl", "bookSize", "longCount", "shortCount", "subUniverseSharpe",
           "twoYearSharpe", "investabilitySharpe", "riskNeutralizedSharpe")


def _get(d, *names, default=None):
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return default


def normalize(alpha, fallback_code=None):
    """Flatten either payload shape into the ledger's canonical record."""
    if not isinstance(alpha, dict):
        return None

    # ---- code ----
    code = fallback_code or ""
    if not code:
        reg = alpha.get("regular")
        if isinstance(reg, dict):
            code = reg.get("code") or ""
        elif isinstance(reg, str):
            code = reg
    code = code or alpha.get("code") or alpha.get("expression") or ""

    # ---- metrics ----
    m = alpha.get("metrics") if isinstance(alpha.get("metrics"), dict) else None
    if m is None:
        isb = alpha.get("is") if isinstance(alpha.get("is"), dict) else {}
        m = {
            "sharpe": _get(isb, "sharpe"),
            "fitness": _get(isb, "fitness"),
            "turnover": _get(isb, "turnover"),
            "returns": _get(isb, "returns"),
            "drawdown": _get(isb, "drawdown"),
            "margin": _get(isb, "margin"),
            "pnl": _get(isb, "pnl"),
            "longCount": _get(isb, "longCount"),
            "shortCount": _get(isb, "shortCount"),
            "sub_universe_sharpe": _get(isb, "subUniverseSharpe", "sub_universe_sharpe"),
            "two_year_sharpe": _get(isb, "twoYearSharpe", "two_year_sharpe"),
            "investability_sharpe": _get(isb, "investabilitySharpe", "investability_sharpe"),
        }
        rn = alpha.get("riskNeutralized")
        if isinstance(rn, dict):
            m["risk_neutralized_sharpe"] = _get(rn, "sharpe")
    else:
        m = dict(m)
        m.setdefault("risk_neutralized_sharpe", m.get("risk_neutralized_sharpe"))

    # ---- checks ----
    fails, warns, cluster = [], [], None
    two_year, sub_univ = None, None
    chk = alpha.get("checks")
    if isinstance(chk, dict):
        for c in chk.get("fail", []) or []:
            if isinstance(c, dict):
                fails.append(c.get("name"))
                if c.get("name") == "CLUSTER_TEST":
                    cluster = c.get("value")
        for c in chk.get("warning", []) or []:
            if isinstance(c, dict):
                warns.append(c.get("name"))
                if c.get("name") == "CLUSTER_TEST":
                    cluster = c.get("value")
                if c.get("name") == "LOW_2Y_SHARPE":
                    two_year = c.get("value")
                if c.get("name") == "LOW_SUB_UNIVERSE_SHARPE":
                    sub_univ = c.get("value")
    elif isinstance(chk, list):
        for c in chk:
            if not isinstance(c, dict):
                continue
            res = str(c.get("result") or "").upper()
            if res == "FAIL":
                fails.append(c.get("name"))
            elif res == "WARNING":
                warns.append(c.get("name"))
            if c.get("name") == "CLUSTER_TEST":
                cluster = c.get("value")
            if c.get("name") == "LOW_2Y_SHARPE":
                two_year = c.get("value")
            if c.get("name") == "LOW_SUB_UNIVERSE_SHARPE":
                sub_univ = c.get("value")
    else:
        isb = alpha.get("is") if isinstance(alpha.get("is"), dict) else {}
        for c in isb.get("checks", []) or []:
            if not isinstance(c, dict):
                continue
            res = str(c.get("result") or "").upper()
            if res == "FAIL":
                fails.append(c.get("name"))
            elif res == "WARNING":
                warns.append(c.get("name"))
            if c.get("name") == "CLUSTER_TEST":
                cluster = c.get("value")
            if c.get("name") == "LOW_2Y_SHARPE":
                two_year = c.get("value")
            if c.get("name") == "LOW_SUB_UNIVERSE_SHARPE":
                sub_univ = c.get("value")

    # The direct /alphas/{id} payload omits twoYearSharpe / subUniverseSharpe from
    # `is`; the platform still reports them as the VALUE of the LOW_2Y_SHARPE and
    # LOW_SUB_UNIVERSE_SHARPE checks, so harvest them from there.
    if two_year is None:
        two_year = m.get("two_year_sharpe")
    if sub_univ is None:
        sub_univ = m.get("sub_universe_sharpe")

    ra = alpha.get("ra") if isinstance(alpha.get("ra"), dict) else {}
    if not ra:
        isb = alpha.get("is") if isinstance(alpha.get("is"), dict) else {}
        ra = isb.get("ra") if isinstance(isb.get("ra"), dict) else {}

    return {
        "alpha_id": alpha.get("id") or alpha.get("alpha_id"),
        "expression": (code or "").strip(),
        "status": alpha.get("status"),
        "sharpe": m.get("sharpe"),
        "fitness": m.get("fitness"),
        "turnover": m.get("turnover"),
        "returns": m.get("returns"),
        "drawdown": m.get("drawdown"),
        "margin_bps": (m.get("margin") or 0.0) * 10000.0,
        "sub_universe_sharpe": sub_univ if sub_univ is not None else m.get("sub_universe_sharpe"),
        "two_year_sharpe": two_year if two_year is not None else m.get("two_year_sharpe"),
        "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
        "investability_sharpe": m.get("investability_sharpe"),
        "pnl": m.get("pnl"),
        "long_count": m.get("longCount"),
        "short_count": m.get("shortCount"),
        "fail_count": len(fails),
        "fails": fails,
        "warnings": warns,
        "cluster_test": cluster,
        "ra_failed": ra.get("ra_failed"),
        "ppa_failed": ra.get("ppa_failed"),
        "pyramid_short": ra.get("pyramid_short"),
        "settings": alpha.get("settings"),
        "pyramids": alpha.get("pyramids"),
    }
