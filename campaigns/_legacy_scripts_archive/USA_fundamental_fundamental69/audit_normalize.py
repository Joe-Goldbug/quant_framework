# -*- coding: utf-8 -*-
"""
结果归一化与门禁裁决器 (Normalizer + Authoritative Gatekeeper)

修复的致命审计漏洞 (2026-10-28)
--------------------------------
BRAIN 平台把「刚好不达标」的检查项从 `checks.fail` **挪到 `checks.warning`**，
但 `ra.ra_failed_checks` 仍如实列出它们。于是：

    checks.fail == []        <- 只读这个会误报「零失败」
    ra.ra_failed_checks == ["LOW_SHARPE", "CONCENTRATED_WEIGHT"]
    ra.ra_failed == true     <- 这才是权威的「不可提交」信号

FCF_Q6 冠军 xAr0rmLJ 就是这样被前序会话误记为 `fails=[]` 的。
本模块强制以 **union(checks.fail, ra.ra_failed_checks)** 为权威失败集，
并以 `ra.ra_failed == false` 作为提交资格的唯一判据。

CLUSTER_TEST / MATCHES_THEMES 恒为 warning，不进入失败集（平台语义如此）。
"""

import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 战役门槛政策 (USA/EUR)
THRESHOLDS = {
    "sharpe_min": 1.58,
    "fitness_min": 1.00,
    "margin_min_bps": 10.0,
    "turnover_min": 0.05,
    "turnover_max": 0.50,
    "prod_corr_max": 0.70,
    "self_corr_max": 0.60,
    "require_zero_fail": True,
    "require_zero_warning": True,
    "submission_forbidden": True,
}

# 恒为 warning、不构成失败的门禁项
BENIGN_WARNINGS = {"CLUSTER_TEST", "MATCHES_THEMES"}


def normalize(result: dict, slot: int) -> dict:
    """把平台原始 result 归一化成战役统一字段（含权威失败集）。"""
    m = result.get("metrics") or result.get("is") or {}
    ra = result.get("ra") or {}
    chk = result.get("checks") or {}

    fail_names = []
    fail_detail = []
    for f in (chk.get("fail") or []):
        if isinstance(f, dict):
            fail_names.append(f.get("name"))
            fail_detail.append(f)
        else:
            fail_names.append(str(f))

    warn_names = []
    warn_detail = []
    for w in (chk.get("warning") or []):
        if isinstance(w, dict):
            warn_names.append(w.get("name"))
            warn_detail.append(w)
        else:
            warn_names.append(str(w))

    # ★ 权威失败集 = checks.fail ∪ ra.ra_failed_checks
    ra_fail = list(ra.get("ra_failed_checks") or [])
    authoritative_fail = sorted(set([n for n in fail_names if n] + ra_fail))

    # 真实警告 = warning ∩ (ra_failed_checks) 之外的项；
    # 平台把不达标的项挪进 warning，所以 warning 里出现的门禁项同样计入风险
    substantive_warnings = sorted(
        set(n for n in warn_names if n and n not in BENIGN_WARNINGS)
    )

    to = m.get("turnover")
    mgn = m.get("margin")
    mgn_bps = (mgn * 10000) if isinstance(mgn, (int, float)) else None
    sh = m.get("sharpe")
    fit = m.get("fitness")

    local_fail = []
    if isinstance(sh, (int, float)) and sh < THRESHOLDS["sharpe_min"]:
        local_fail.append(f"LOW_SHARPE({sh}<{THRESHOLDS['sharpe_min']})")
    if isinstance(fit, (int, float)) and fit < THRESHOLDS["fitness_min"]:
        local_fail.append(f"LOW_FITNESS({fit}<{THRESHOLDS['fitness_min']})")
    if isinstance(mgn_bps, (int, float)) and mgn_bps < THRESHOLDS["margin_min_bps"]:
        local_fail.append(f"LOW_MARGIN({mgn_bps:.2f}bps<{THRESHOLDS['margin_min_bps']})")
    if isinstance(to, (int, float)) and not (THRESHOLDS["turnover_min"] <= to <= THRESHOLDS["turnover_max"]):
        local_fail.append(f"TURNOVER({to})")
    if authoritative_fail:
        local_fail.append("PLATFORM:" + ",".join(authoritative_fail))

    return {
        "slot": slot,
        "alpha_id": result.get("alpha_id") or result.get("id"),
        "expression": result.get("code") or result.get("expression"),
        "status": result.get("status"),
        "sharpe": sh,
        "fitness": fit,
        "turnover": to,
        "returns": m.get("returns"),
        "margin": mgn,
        "margin_bps": round(mgn_bps, 2) if isinstance(mgn_bps, (int, float)) else None,
        "drawdown": m.get("drawdown"),
        "long_count": m.get("longCount"),
        "short_count": m.get("shortCount"),
        "sub_universe_sharpe": m.get("sub_universe_sharpe"),
        "two_year_sharpe": m.get("two_year_sharpe"),
        "investability_sharpe": m.get("investability_sharpe"),
        "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
        "self_correlation": m.get("selfCorrelation"),
        "prod_correlation": m.get("prodCorrelation"),
        # ★ 权威字段
        "ra_failed": ra.get("ra_failed"),
        "ppa_failed": ra.get("ppa_failed"),
        "authoritative_fail": authoritative_fail,
        "checks_fail": fail_names,
        "checks_warning": warn_names,
        "substantive_warnings": substantive_warnings,
        "fail_detail": fail_detail,
        "warning_detail": warn_detail,
        "local_gate_fail": local_fail,
        "passes_local_gates": len(local_fail) == 0,
        "submittable": (not authoritative_fail) and (not local_fail),
    }


def summarize(rows: list) -> dict:
    best = max(rows, key=lambda r: (r.get("fitness") or -9, r.get("sharpe") or -9)) if rows else None
    passing = [r for r in rows if r["passes_local_gates"]]
    return {
        "n_slots": len(rows),
        "n_passing": len(passing),
        "n_submittable": len([r for r in rows if r["submittable"]]),
        "best_by_fitness": ({"alpha_id": best["alpha_id"], "sharpe": best["sharpe"],
                              "fitness": best["fitness"], "expression": best["expression"],
                              "authoritative_fail": best["authoritative_fail"]}
                             if best else None),
        "passing_alpha_ids": [r["alpha_id"] for r in passing],
    }


def print_table(rows: list):
    print(f"{'slot':>4} {'alpha_id':<10} {'Sharpe':>7} {'Fit':>6} {'TO':>7} "
          f"{'Mgnbps':>8} {'subU':>6} {'2Y':>6}  authoritative_fail")
    print("-" * 108)
    for r in rows:
        print(f"{r['slot']:>4} {str(r['alpha_id']):<10} {str(r['sharpe']):>7} "
              f"{str(r['fitness']):>6} {str(r['turnover']):>7} "
              f"{str(r['margin_bps']):>8} {str(r['sub_universe_sharpe']):>6} "
              f"{str(r['two_year_sharpe']):>6}  {','.join(r['authoritative_fail']) or 'NONE'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="batch_*_result.json (含 alpha_results)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as f:
        doc = json.load(f)
    raw = doc.get("alpha_results", [])
    rows = [normalize(r, i + 1) for i, r in enumerate(raw)]
    doc["normalized"] = rows
    doc["summary"] = summarize(rows)
    doc["threshold_policy"] = THRESHOLDS
    out = args.out or args.path
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, default=str)
    print_table(rows)
    print()
    print(json.dumps(doc["summary"], ensure_ascii=False, indent=2))
