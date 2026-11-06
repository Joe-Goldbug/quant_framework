# -*- coding: utf-8 -*-
"""
gate_report.py — 对某一批回测结果按「种子 kqNgXQqd 重构通关门禁」逐条打分。

五道硬门 (来自优化任务书):
  1. IS Sharpe        >= 1.65
  2. IS Fitness       >= 1.05
  3. Cluster Test Sh  >= 1.60
  4. Margin           >= 15.0 bps
  5. Returns > Drawdown  且  Returns >= 5.5% 且  Drawdown <= 2.8%

平台指标恒等式 (战役报告 4 处逐位验证):
  margin_bps = returns / turnover * 20
  fitness    = sharpe * sqrt(returns / max(turnover, 0.125))

用法:
  python gate_report.py batch_25_result.json [batch_26_result.json ...]
"""
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))

GATES = {
    "sharpe": 1.65,
    "fitness": 1.05,
    "cluster": 1.60,
    "margin_bps": 15.0,
    "returns": 0.055,
    "drawdown_max": 0.028,
    "turnover_min": 0.05,
    "turnover_max": 0.50,
}


def load_expr_map(batch_name):
    p = os.path.join(HERE, batch_name.replace("_result.json", ".json"))
    if not os.path.exists(p):
        return {}
    try:
        b = json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}
    return {it["expr"].strip(): it["id"] for it in b.get("items", []) if "expr" in it}


def num(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def score(rec, expr_map):
    isd = rec.get("is") or {}
    raw_checks = isd.get("checks") or []
    fails = [c.get("name") for c in raw_checks if str(c.get("result")) == "FAIL"]
    warns = [c.get("name") for c in raw_checks if str(c.get("result")) == "WARNING"]
    cluster_map = {c.get("name"): c.get("value") for c in raw_checks}

    sharpe = num(isd.get("sharpe"))
    fitness = num(isd.get("fitness"))
    turnover = num(isd.get("turnover"))
    returns = num(isd.get("returns"))
    drawdown = num(isd.get("drawdown"))
    margin_pct = num(isd.get("margin"))
    margin_bps = margin_pct * 10000 if margin_pct is not None else None
    cluster = num(cluster_map.get("CLUSTER_TEST"))
    two_year = num(cluster_map.get("LOW_2Y_SHARPE"))

    reg = rec.get("regular")
    expr = reg.get("code", "") if isinstance(reg, dict) else (reg or "")
    tid = expr_map.get(expr.strip()) or expr_map.get(expr.replace(" ", ""))

    gate = {}
    if sharpe is not None:
        gate["Sh"] = sharpe >= GATES["sharpe"]
    if fitness is not None:
        gate["Fit"] = fitness >= GATES["fitness"]
    if cluster is not None:
        gate["Cl"] = cluster >= GATES["cluster"]
    if margin_bps is not None:
        gate["Mgn"] = margin_bps >= GATES["margin_bps"]
    if returns is not None and drawdown is not None:
        gate["R>DD"] = (returns > drawdown) and returns >= GATES["returns"] and drawdown <= GATES["drawdown_max"]
    if turnover is not None:
        gate["TO"] = GATES["turnover_min"] <= turnover <= GATES["turnover_max"]

    n_pass = sum(1 for v in gate.values() if v)
    return {
        "alpha_id": rec.get("alpha_id"),
        "item_id": tid,
        "sharpe": sharpe,
        "fitness": fitness,
        "cluster": cluster,
        "margin_bps": margin_bps,
        "turnover_pct": turnover * 100 if turnover is not None else None,
        "returns_pct": returns * 100 if returns is not None else None,
        "drawdown_pct": drawdown * 100 if drawdown is not None else None,
        "r_to": (returns / turnover) if (returns is not None and turnover) else None,
        "two_year": two_year,
        "fails": fails,
        "warns": warns,
        "gate": gate,
        "n_pass": n_pass,
        "n_gate": len(gate),
        "expr": expr,
    }


def main():
    files = sys.argv[1:]
    if not files:
        files = sorted(f for f in os.listdir(HERE) if f.endswith("_result.json"))
    rows = []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(HERE, f)
        if not os.path.exists(p):
            print(f"missing: {p}")
            continue
        d = json.load(open(p, encoding="utf-8"))
        expr_map = load_expr_map(os.path.basename(p))
        for rec in d.get("alpha_results", []):
            if not rec.get("alpha_id"):
                print(f"  [no alpha] {os.path.basename(p)} child={rec.get('child_id')} status={rec.get('child_status')}")
                continue
            r = score(rec, expr_map)
            r["batch"] = os.path.basename(p)
            rows.append(r)

    rows.sort(key=lambda r: (-r["n_pass"], -(r["sharpe"] or 0)))
    hdr = f"{'batch':<12}{'item_id':<24}{'alpha':<11}{'Sh':>6}{'Fit':>6}{'Cl':>6}{'Mgn':>7}{'TO%':>7}{'R%':>7}{'DD%':>7}{'R/TO':>6}  gates"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        g = "".join(k if v else "." for k, v in r["gate"].items())
        bnum = "".join(ch for ch in r["batch"] if ch.isdigit())[:3] or r["batch"][:3]
        print(f"B{bnum:<11}{str(r['item_id'])[:23]:<24}{str(r['alpha_id']):<11}"
              f"{(r['sharpe'] if r['sharpe'] is not None else 0):>6.2f}"
              f"{(r['fitness'] if r['fitness'] is not None else 0):>6.2f}"
              f"{(r['cluster'] if r['cluster'] is not None else 0):>6.2f}"
              f"{(r['margin_bps'] if r['margin_bps'] is not None else 0):>7.2f}"
              f"{(r['turnover_pct'] if r['turnover_pct'] is not None else 0):>7.2f}"
              f"{(r['returns_pct'] if r['returns_pct'] is not None else 0):>7.2f}"
              f"{(r['drawdown_pct'] if r['drawdown_pct'] is not None else 0):>7.2f}"
              f"{(r['r_to'] if r['r_to'] is not None else 0):>6.3f}  {g} ({r['n_pass']}/{r['n_gate']})"
              + (f"  FAIL={r['fails']}" if r["fails"] else ""))

    print("\n[gate legend] Sh=Sharpe>=1.65  Fit=Fitness>=1.05  Cl=Cluster>=1.60  "
          "Mgn=Margin>=15bps  R>DD=Returns>DD & R>=5.5% & DD<=2.8%  TO=Turnover in [5%,50%]")


if __name__ == "__main__":
    main()
