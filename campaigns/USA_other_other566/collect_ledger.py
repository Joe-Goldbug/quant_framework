"""
collect_ledger.py — USA/D1/TOP1000 other566 campaign ledger builder.

Reads every batch_*.json in this directory, resolves each item's alpha metrics from
the brain-mcp result payloads (saved as batch_NN_result.json), and emits a single
flat exploration_ledger.json + a human-readable summary table.

Metrics extracted per alpha:
  sharpe, fitness, turnover, returns, drawdown, margin_bps, sub_universe_sharpe,
  two_year_sharpe, risk_neutralized_sharpe, cluster_test, plus the platform
  fail/warning check names.

Gate thresholds (AEGIS standard, USA region):
  Step 1 : |Sharpe| >= 1.0
  Step 2 : |Sharpe| >= 1.0 AND platform fail_count == 0 AND margin >= 5.0 bps
                           AND turnover <= 70%
  Final  : Sharpe >= 1.58 AND fitness >= 1.00 AND margin >= 10.0 bps
                           AND turnover in [5%, 50%] AND fail_count == 0
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

MIN_MARGIN_BPS = 10.0          # USA production dead line
STEP2_MARGIN_BPS = 5.0         # 50% of region baseline
STEP1_SHARPE = 1.0
FINAL_SHARPE = 1.58
FINAL_FITNESS = 1.00
TURNOVER_LO, TURNOVER_HI = 0.05, 0.50


def load_results():
    """Map expression -> metrics dict from every saved batch result payload."""
    from alpha_normalizer import normalize
    by_expr = {}
    for p in sorted(glob.glob(os.path.join(HERE, "batch_*_result.json"))):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for r in data.get("alpha_results", []):
            rec = normalize(r)
            if not rec or not rec.get("expression"):
                continue
            rec["source_result_file"] = os.path.basename(p)
            by_expr[rec["expression"]] = rec
    return by_expr


def gate(rec):
    """Return (step1, step2, final) booleans + reason list."""
    sh = rec.get("sharpe")
    fi = rec.get("fitness")
    to = rec.get("turnover")
    mg = rec.get("margin_bps") or 0.0
    fc = rec.get("fail_count", 0)

    s1 = sh is not None and abs(sh) >= STEP1_SHARPE
    reasons = []
    if sh is None or abs(sh) < STEP1_SHARPE:
        reasons.append(f"|Sharpe| {abs(sh) if sh is not None else 'NA'} < {STEP1_SHARPE}")
    if fc > 0:
        reasons.append(f"platform_fail={fc}")
    if mg < STEP2_MARGIN_BPS:
        reasons.append(f"margin {mg:.2f} < {STEP2_MARGIN_BPS}")
    if to is not None and to > 0.70:
        reasons.append(f"turnover {to*100:.1f}% > 70%")
    s2 = s1 and not reasons

    freasons = []
    if sh is None or sh < FINAL_SHARPE:
        freasons.append(f"Sharpe {sh} < {FINAL_SHARPE}")
    if fi is None or fi < FINAL_FITNESS:
        freasons.append(f"Fitness {fi} < {FINAL_FITNESS}")
    if mg < MIN_MARGIN_BPS:
        freasons.append(f"Margin {mg:.2f} < {MIN_MARGIN_BPS}")
    if to is not None and (to > TURNOVER_HI or to < TURNOVER_LO):
        freasons.append(f"Turnover {to*100:.1f}% outside [5,50]")
    if fc > 0:
        freasons.append(f"platform_fail={fc}")
    final = s2 and not freasons
    return s1, s2, final, reasons, freasons


def champion_score(rec, op_count=6):
    """AEGIS champion formula: Fitness x ln(Margin_bps) x (1-ProdCorr^2) x (1-0.04*OpCount).
    ProdCorr is not yet verified here -> conservative 1.0 placeholder (worst case for PC=1)."""
    fi = rec.get("fitness") or 0.0
    mg = rec.get("margin_bps") or 0.0
    if fi <= 0 or mg <= 0:
        return 0.0
    return fi * math.log(mg) * 1.0 * (1.0 - 0.04 * op_count)


def count_ops(expr):
    import ast
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return 0
    ops = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else ""
            if not fn.startswith("vec_"):
                ops.add(fn)
    return len(ops)


def _f(v, w=6, p=2, dash="--"):
    """Format a number safely, showing a dash for None."""
    if v is None:
        return f"{dash:>{w}}"
    return f"{v:>{w}.{p}f}"


def main():
    by_expr = load_results()
    ledger = []
    for p in sorted(glob.glob(os.path.join(HERE, "batch_*.json"))):
        if p.endswith("_result.json"):
            continue
        with open(p, "r", encoding="utf-8") as f:
            b = json.load(f)
        for it in b.get("items", []):
            e = it["expr"]
            rec = by_expr.get(e)
            entry = {
                "batch": b.get("batch"),
                "family": b.get("family"),
                "item_id": it.get("id"),
                "expression": e,
                "op_count": it.get("ops") or count_ops(e),
                "n_fields": len(it.get("fields") or []),
                "fields": it.get("fields"),
                "resolved": rec is not None,
            }
            if rec:
                s1, s2, fin, r1, rf = gate(rec)
                entry.update({
                    "alpha_id": rec["alpha_id"],
                    "sharpe": rec["sharpe"],
                    "fitness": rec["fitness"],
                    "turnover": rec["turnover"],
                    "margin_bps": round(rec["margin_bps"], 2),
                    "returns": rec["returns"],
                    "drawdown": rec["drawdown"],
                    "sub_universe_sharpe": rec["sub_universe_sharpe"],
                    "two_year_sharpe": rec["two_year_sharpe"],
                    "risk_neutralized_sharpe": rec["risk_neutralized_sharpe"],
                    "cluster_test": rec["cluster_test"],
                    "fail_count": rec["fail_count"],
                    "fails": rec["fails"],
                    "warnings": rec["warnings"],
                    "gate_step1": s1,
                    "gate_step2": s2,
                    "gate_final": fin,
                    "gate_reasons": r1 + rf,
                    "champion_score": round(champion_score(rec, entry["op_count"]), 4),
                })
            ledger.append(entry)

    out = {
        "campaign": "USA_other_other566",
        "region": "USA", "universe": "TOP1000", "delay": 1,
        "dataset": "other566",
        "settings": {"neutralization": "INDUSTRY", "decay": 4, "truncation": 0.08,
                     "pasteurization": "ON", "nan_handling": "ON"},
        "theme": {"name": "USA/D1 TOP1000 Theme", "pyramid": "USA/D1/OTHER",
                  "multiplier": 1.4, "user_theme_multiplier": 2.0,
                  "python_multiplier": 3.0},
        "gates": {"step1_sharpe": STEP1_SHARPE, "step2_margin_bps": STEP2_MARGIN_BPS,
                  "final_sharpe": FINAL_SHARPE, "final_fitness": FINAL_FITNESS,
                  "final_margin_bps": MIN_MARGIN_BPS,
                  "turnover_range": [TURNOVER_LO, TURNOVER_HI]},
        "n_entries": len(ledger),
        "n_resolved": sum(1 for e in ledger if e.get("resolved")),
        "n_step1": sum(1 for e in ledger if e.get("gate_step1")),
        "n_step2": sum(1 for e in ledger if e.get("gate_step2")),
        "n_final": sum(1 for e in ledger if e.get("gate_final")),
        "entries": ledger,
    }
    with open(os.path.join(HERE, "exploration_ledger.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # summary table
    print(f"{'B':>2} {'item':<12} {'Sh':>6} {'Fit':>6} {'Mgn':>7} {'TO%':>6} {'2Y':>6} {'RNS':>6} {'CL':>6} {'S1':>3} {'S2':>3} {'F':>3}  expr")
    for e in ledger:
        if not e.get("resolved"):
            print(f"{e['batch']:>2} {e['item_id']:<12} {'--':>6} {'--':>6} {'--':>7} {'--':>6} {'--':>6} {'--':>6} {'--':>6} {'  ':>3} {'  ':>3} {'  ':>3}  PENDING")
            continue
        print(f"{e['batch']:>2} {e['item_id']:<12} {_f(e['sharpe'])} {_f(e['fitness'])} "
              f"{_f(e['margin_bps'], 7)} {_f((e['turnover'] or 0)*100, 6, 1)} {_f(e['two_year_sharpe'])} "
              f"{_f(e['risk_neutralized_sharpe'])} {_f(e['cluster_test'])} "
              f"{'Y' if e['gate_step1'] else '.':>3} {'Y' if e['gate_step2'] else '.':>3} {'Y' if e['gate_final'] else '.':>3}  "
              f"{e['expression'][:78]}")

    print()
    print(f"entries={out['n_entries']} resolved={out['n_resolved']} "
          f"step1={out['n_step1']} step2={out['n_step2']} final={out['n_final']}")
    top = sorted([e for e in ledger if e.get("resolved") and e.get("sharpe") is not None],
                 key=lambda x: abs(x.get("sharpe") or 0), reverse=True)[:12]
    print("\nTop 12 by |Sharpe|:")
    for e in top:
        print(f"  B{e['batch']} {e['item_id']:<12} Sh={_f(e['sharpe'], 0)} Fit={_f(e['fitness'], 0)} "
              f"Mgn={_f(e['margin_bps'], 6)} 2Y={_f(e['two_year_sharpe'], 0)} RNS={_f(e['risk_neutralized_sharpe'], 0)} "
              f"CL={_f(e['cluster_test'], 0)} CS={_f(e['champion_score'], 0, 3)}")


if __name__ == "__main__":
    main()
