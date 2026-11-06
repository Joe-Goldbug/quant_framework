"""
score_and_select.py — final gate, correlation verification and champion selection.

Consumes exploration_ledger.json, applies the AEGIS production gate, and writes:
  * campaign_champions.json  — the champion + runner-ups, with the AEGIS
    Champion_Score = Fitness x ln(Margin_bps) x (1 - ProdCorr^2) x (1 - 0.04*OpCount)
  * correlation_report.json  — verified ProdCorr / SelfCorr for the shortlisted alphas

ProdCorr/SelfCorr are NOT in the simulation payload; they must be measured with
brain-mcp check_correlation / check_self_correlation. This script accepts a
correlations.json map (alpha_id -> {prod_corr, self_corr}) so the measured
values feed the champion score and the final gate.
"""

import glob
import json
import math
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))

MIN_MARGIN_BPS = 10.0
FINAL_SHARPE = 1.58
FINAL_FITNESS = 1.00
TURNOVER_LO, TURNOVER_HI = 0.05, 0.50
PROD_CORR_MAX = 0.70
SELF_CORR_MAX = 0.70

# The PLATFORM's own HIGH_TURNOVER limit is 0.70, not AEGIS's internal 0.50, and the
# platform treats LOW_FITNESS as a WARNING (not a FAIL) while turnover stays under
# 0.70. So "0 platform fails" is a weaker statement than "passes the platform's
# submission gate", and both are weaker than AEGIS's internal production gate.
PLATFORM_TURNOVER_MAX = 0.70


def load_correlations():
    p = os.path.join(HERE, "correlations.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def champion_score(rec, prod_corr, op_count):
    fi = rec.get("fitness") or 0.0
    mg = rec.get("margin_bps") or 0.0
    if fi <= 0 or mg <= 0:
        return 0.0
    pc = 1.0 if prod_corr is None else prod_corr
    return fi * math.log(mg) * (1.0 - pc * pc) * (1.0 - 0.04 * op_count)


def final_gate(e, corr):
    """AEGIS internal production gate with correlation. Returns (pass, reasons)."""
    r = []
    sh, fi, to, mg = e.get("sharpe"), e.get("fitness"), e.get("turnover"), e.get("margin_bps")
    if sh is None or sh < FINAL_SHARPE:
        r.append(f"Sharpe {sh} < {FINAL_SHARPE}")
    if fi is None or fi < FINAL_FITNESS:
        r.append(f"Fitness {fi} < {FINAL_FITNESS}")
    if mg is None or mg < MIN_MARGIN_BPS:
        r.append(f"Margin {mg} < {MIN_MARGIN_BPS} bps")
    if to is None or to > TURNOVER_HI or to < TURNOVER_LO:
        r.append(f"Turnover {to} outside [5%,50%]")
    if e.get("fail_count", 0) > 0:
        r.append(f"platform_fail={e.get('fail_count')} ({e.get('fails')})")
    c = corr.get(e.get("alpha_id")) or {}
    pc, sc = c.get("prod_corr"), c.get("self_corr")
    if pc is not None and pc >= PROD_CORR_MAX:
        r.append(f"ProdCorr {pc} >= {PROD_CORR_MAX}")
    if sc is not None and sc > SELF_CORR_MAX:
        r.append(f"SelfCorr {sc} > {SELF_CORR_MAX}")
    return (not r), r


def platform_gate(e, corr):
    """The platform's OWN submission-relevant checks (0 FAIL) + verified correlations.
    The platform's HIGH_TURNOVER limit is 0.70 and LOW_FITNESS is only a WARNING there,
    so this gate is looser than AEGIS's internal one."""
    r = []
    if e.get("fail_count", 0) > 0:
        r.append(f"platform_fail={e.get('fail_count')} ({e.get('fails')})")
    to = e.get("turnover")
    if to is not None and to > PLATFORM_TURNOVER_MAX:
        r.append(f"Turnover {to} > platform limit {PLATFORM_TURNOVER_MAX}")
    c = corr.get(e.get("alpha_id")) or {}
    pc, sc = c.get("prod_corr"), c.get("self_corr")
    if pc is None:
        r.append("ProdCorr unverified")
    elif pc >= PROD_CORR_MAX:
        r.append(f"ProdCorr {pc} >= {PROD_CORR_MAX}")
    if sc is None:
        r.append("SelfCorr unverified")
    elif sc > SELF_CORR_MAX:
        r.append(f"SelfCorr {sc} > {SELF_CORR_MAX}")
    return (not r), r


def main():
    with open(os.path.join(HERE, "exploration_ledger.json"), "r", encoding="utf-8") as f:
        led = json.load(f)
    corr = load_correlations()

    entries = [e for e in led["entries"] if e.get("resolved") and e.get("sharpe") is not None]
    for e in entries:
        c = corr.get(e.get("alpha_id")) or {}
        e["prod_corr"] = c.get("prod_corr")
        e["self_corr"] = c.get("self_corr")
        e["champion_score"] = round(champion_score(e, e["prod_corr"], e.get("op_count") or 6), 4)
        ok, reasons = final_gate(e, corr)
        e["gate_production"] = ok
        e["production_reasons"] = reasons
        pok, preasons = platform_gate(e, corr)
        e["gate_platform"] = pok
        e["platform_reasons"] = preasons

    # Rank by the AEGIS champion formula among alphas that at least clear Step 1.
    eligible = [e for e in entries if (e.get("sharpe") or 0) >= 1.0]
    eligible.sort(key=lambda x: x.get("champion_score") or 0.0, reverse=True)

    prod_pass = [e for e in entries if e.get("gate_production")]
    plat_pass = [e for e in entries if e.get("gate_platform")]
    print(f"total resolved: {len(entries)}")
    print(f"Step1 (|Sh|>=1.0): {sum(1 for e in entries if abs(e['sharpe']) >= 1.0)}")
    print(f"0 platform fails : {sum(1 for e in entries if e.get('fail_count') == 0)}")
    print(f"PLATFORM GATE    : {len(plat_pass)}  (0 FAIL + verified ProdCorr/SelfCorr)")
    print(f"AEGIS PRODUCTION : {len(prod_pass)}")
    print()

    print("=== TOP 15 BY CHAMPION SCORE (Fitness x ln(Margin) x (1-PC^2) x (1-0.04*ops)) ===")
    for e in eligible[:15]:
        pc = e["prod_corr"] if e["prod_corr"] is not None else None
        print(f"  B{e['batch']:<3}{e['item_id']:<20} CS={e['champion_score']:>7.3f} "
              f"Sh={e['sharpe']:>5.2f} Fit={e['fitness']:>5.2f} Mgn={e['margin_bps']:>6.2f} "
              f"TO={e['turnover']*100:>5.1f}% 2Y={e['two_year_sharpe']} "
              f"PC={pc if pc is not None else '--':>7} SC={e['self_corr'] if e['self_corr'] is not None else '--'} "
              f"fails={e['fail_count']}")
        if e["production_reasons"]:
            print(f"        blocked by: {e['production_reasons']}")

    # champion assembly
    champ = None
    if prod_pass:
        champ = max(prod_pass, key=lambda x: x.get("champion_score") or 0.0)
    elif eligible:
        champ = eligible[0]

    out = {
        "campaign_metadata": {
            "region": "USA", "universe": "TOP1000", "delay": 1,
            "dataset": "other566", "theme": "USA/D1 TOP1000 Theme",
            "pyramid": "USA/D1/OTHER", "pyramid_multiplier": 1.4,
            "user_theme_multiplier": 2.0, "python_theme_multiplier": 3.0,
            "neutralization": "INDUSTRY", "truncation": 0.08,
            "pasteurization": "ON", "nan_handling": "ON",
            "total_batches_simulated": len({e["batch"] for e in entries}),
            "total_alphas_simulated": len(entries),
            "status": "PRODUCTION_PASS" if prod_pass else "NO_PRODUCTION_PASS",
        },
        "gates": {
            "final_sharpe": FINAL_SHARPE, "final_fitness": FINAL_FITNESS,
            "final_margin_bps": MIN_MARGIN_BPS,
            "turnover_range": [TURNOVER_LO, TURNOVER_HI],
            "prod_corr_max": PROD_CORR_MAX, "self_corr_max": SELF_CORR_MAX,
        },
        "n_step1": sum(1 for e in entries if abs(e["sharpe"]) >= 1.0),
        "n_zero_fail": sum(1 for e in entries if e.get("fail_count") == 0),
        "n_platform_pass": len(plat_pass),
        "n_production_pass": len(prod_pass),
    }

    if plat_pass:
        out["platform_gate_passers"] = [
            {"alpha_id": e.get("alpha_id"), "batch": e.get("batch"),
             "item_id": e.get("item_id"), "code": e.get("expression"),
             "sharpe": e.get("sharpe"), "fitness": e.get("fitness"),
             "margin_bps": e.get("margin_bps"),
             "turnover_pct": (e.get("turnover") or 0) * 100,
             "two_year_sharpe": e.get("two_year_sharpe"),
             "cluster_test": e.get("cluster_test"),
             "prod_corr": e.get("prod_corr"), "self_corr": e.get("self_corr"),
             "champion_score": e.get("champion_score"),
             "aegis_gate_blocked_by": e.get("production_reasons")}
            for e in sorted(plat_pass, key=lambda x: -(x.get("sharpe") or 0))[:12]
        ]

    if champ:
        out["best_candidate"] = {
            "alpha_id": champ.get("alpha_id"),
            "batch": champ.get("batch"), "item_id": champ.get("item_id"),
            "code": champ.get("expression"),
            "op_count": champ.get("op_count"), "n_fields": champ.get("n_fields"),
            "metrics": {
                "sharpe": champ.get("sharpe"), "fitness": champ.get("fitness"),
                "margin_bps": champ.get("margin_bps"), "turnover_pct": (champ.get("turnover") or 0) * 100,
                "returns": champ.get("returns"), "drawdown": champ.get("drawdown"),
                "two_year_sharpe": champ.get("two_year_sharpe"),
                "sub_universe_sharpe": champ.get("sub_universe_sharpe"),
                "cluster_test": champ.get("cluster_test"),
            },
            "correlation": {"prod_corr": champ.get("prod_corr"),
                            "self_corr": champ.get("self_corr")},
            "gates": {"production_pass": champ.get("gate_production"),
                      "blocked_by": champ.get("production_reasons"),
                      "platform_fails": champ.get("fails"),
                      "warnings": champ.get("warnings")},
            "champion_score": champ.get("champion_score"),
        }

    out["runner_ups"] = [
        {"rank": i + 1, "alpha_id": e.get("alpha_id"), "batch": e.get("batch"),
         "item_id": e.get("item_id"), "code": e.get("expression"),
         "sharpe": e.get("sharpe"), "fitness": e.get("fitness"),
         "margin_bps": e.get("margin_bps"), "turnover_pct": (e.get("turnover") or 0) * 100,
         "two_year_sharpe": e.get("two_year_sharpe"), "cluster_test": e.get("cluster_test"),
         "prod_corr": e.get("prod_corr"), "self_corr": e.get("self_corr"),
         "champion_score": e.get("champion_score"),
         "blocked_by": e.get("production_reasons")}
        for i, e in enumerate(eligible[:9] if champ is None else
                             [x for x in eligible if x.get("alpha_id") != champ.get("alpha_id")][:9])
    ]

    with open(os.path.join(HERE, "campaign_champions.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nwrote campaign_champions.json  (status={out['campaign_metadata']['status']})")


if __name__ == "__main__":
    main()
