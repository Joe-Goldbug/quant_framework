import json, math, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def cs(fit, mgn_bps, pc, ops=3):
    return round(fit * math.log(mgn_bps) * (1 - pc ** 2) * (1 - 0.04 * ops), 4)


P = "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), target_tvr=0.12), industry)"

rows = [
    ("omEJzwwv", 34, "s1_momentum_orth", "group_zscore(ts_target_tvr_decay(vector_neut(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), ts_delta(close, 20)), target_tvr=0.12), industry)", "STATISTICAL", 1.26, 0.59, 0.0301, 0.1391, 4.33, 1.18, 0, None, None),
    ("58EA673n", 34, "s2_vol_parity", "group_zscore(ts_target_tvr_decay(divide(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), add(ts_std_dev(returns, 60), 0.001)), target_tvr=0.12), industry)", "STATISTICAL", 1.10, 0.46, 0.0262, 0.1489, 3.52, 1.25, 0, None, None),
    ("npvezkYz", 34, "s3_hump", "group_zscore(hump(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), hump=0.003), industry)", "STATISTICAL", 1.17, 0.39, 0.0283, 0.2593, 2.18, 1.25, 4, None, None),
    ("d5W378gK", 34, "s4_tail_shrink_p05", "signed_power(group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), target_tvr=0.12), industry), 0.5)", "STATISTICAL", 1.26, 0.58, 0.0273, 0.1285, 4.25, 1.72, 0, None, None),
    ("3qok6Y3O", 34, "s5_label5_x_prob", "group_zscore(ts_target_tvr_decay(multiply(subtract(oth566_r20marsi_label_5, 3), oth566_r20marsi_prob_5), target_tvr=0.12), industry)", "STATISTICAL", 0.93, 0.39, 0.0241, 0.1404, 3.43, 1.42, 3, None, None),
    ("58EA679n", 34, "s6_consensus_eq", "group_zscore(ts_target_tvr_decay(add(group_zscore(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), industry), group_zscore(multiply(oth566_return, group_rank(oth566_prob_2, industry)), industry)), target_tvr=0.12), industry)", "STATISTICAL", 1.24, 0.59, 0.0307, 0.1372, 4.47, 1.94, 1, None, None),
    ("GrWK8063", 34, "s7_consensus_7030", "group_zscore(ts_target_tvr_decay(add(group_zscore(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), industry), multiply(0.4286, group_zscore(multiply(oth566_return, group_rank(oth566_prob_2, industry)), industry))), target_tvr=0.12), industry)", "STATISTICAL", 1.25, 0.59, 0.0306, 0.1365, 4.48, 1.89, 2, None, None),
    ("omEJzwv6", 34, "s8_prob_power2", "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, signed_power(oth566_r20marsi_prob_5, 2)), target_tvr=0.12), industry)", "STATISTICAL", 1.26, 0.59, 0.0305, 0.1414, 4.32, 1.95, 0, None, None),
    ("RRElaZYe", 34, "s9_anchor_2day", "quantile(ts_target_tvr_decay(multiply(oth566_return, group_rank(oth566_prob_2, industry)), target_tvr=0.12), driver=\"gaussian\")", "STATISTICAL", 1.08, 0.49, 0.0289, 0.1417, 4.08, 1.75, 3, None, None),
    ("O0AMmwm1", 34, "s10_consensus_vol", "group_zscore(ts_target_tvr_decay(add(group_zscore(divide(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), add(ts_std_dev(returns, 60), 0.001)), industry), group_zscore(multiply(oth566_return, group_rank(oth566_prob_2, industry)), industry)), target_tvr=0.12), industry)", "STATISTICAL", 1.16, 0.52, 0.0283, 0.1395, 4.05, 1.56, 3, None, None),
    ("wpQ2zrWd", 35, "t1_tsquantile250", "group_zscore(ts_target_tvr_decay(ts_quantile(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 250), target_tvr=0.12), industry)", "STATISTICAL", 1.25, 0.58, 0.0293, 0.1371, 4.27, 1.95, 3, None, None),
    ("mLo0zvl9", 35, "t2_tsrank250", "group_zscore(ts_target_tvr_decay(ts_rank(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 250), target_tvr=0.12), industry)", "STATISTICAL", 1.19, 0.54, 0.0280, 0.1340, 4.18, 1.86, 3, None, None),
    ("9qxd6n29", 35, "t3_tszscore250", "group_zscore(ts_target_tvr_decay(ts_zscore(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 250), target_tvr=0.12), industry)", "STATISTICAL", 1.21, 0.55, 0.0285, 0.1386, 4.12, 1.82, 3, None, None),
    ("e75V2jWN", 35, "t4_tsquantile120", "group_zscore(ts_target_tvr_decay(ts_quantile(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 120), target_tvr=0.12), industry)", "STATISTICAL", 1.12, 0.49, 0.0258, 0.1375, 3.76, 1.57, 4, None, None),
    ("2rAXZYx8", 35, "t5_tsquantile_ret_only", "group_zscore(ts_target_tvr_decay(ts_quantile(oth566_r20marsi_ret, 250), target_tvr=0.12), industry)", "STATISTICAL", 1.24, 0.57, 0.0290, 0.1371, 4.24, 1.89, 3, None, None),
    ("9qxd6n39", 35, "t6_tsquantile250_tvr08", "group_zscore(ts_target_tvr_decay(ts_quantile(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 250), target_tvr=0.08), industry)", "STATISTICAL", 1.06, 0.47, 0.0244, 0.0979, 4.98, 1.56, 4, None, None),
    ("O0AMm3jJ", 35, "t7_tsquantile250_gauss", "quantile(ts_target_tvr_decay(ts_quantile(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 250), target_tvr=0.12), driver=\"gaussian\")", "STATISTICAL", 1.19, 0.55, 0.0296, 0.1388, 4.27, 1.56, 0, None, None),
    ("e75V2jZl", 35, "t8_tsquantile60", "group_zscore(ts_target_tvr_decay(ts_quantile(multiply(oth566_r20marsi_ret, oth566_r20marsi_prob_5), 60), target_tvr=0.12), industry)", "STATISTICAL", 1.21, 0.55, 0.0285, 0.1376, 4.14, 1.46, 4, None, None),
    ("E568aJjP", 34, "n_SECTOR", P, "SECTOR", 1.00, 0.61, 0.0460, 0.1246, 7.39, 1.38, 0, 0.6477, -0.7093),
    ("xArbWY9p", 34, "n_CROWDING", P, "CROWDING", 1.05, 0.59, 0.0395, 0.1256, 6.29, 1.56, 0, 0.6227, -0.7334),
    ("wpQ2zzJ5", 34, "n_REV_MOM", P, "REVERSION_AND_MOMENTUM", 1.15, 0.58, 0.0372, 0.1451, 5.13, 1.99, 0, 0.6712, -0.6821),
    ("vR1pzeQr", 34, "n_FAST", P, "FAST", 0.96, 0.41, 0.0308, 0.1675, 3.67, 1.66, 2, None, None),
    ("Xg9vlQvm", 34, "n_SLOW_AND_FAST", P, "SLOW_AND_FAST", 1.08, 0.42, 0.0266, 0.1720, 3.10, 2.26, 0, None, None),
]

entries = []
for (aid, w, tag, expr, neut, sh, fit, ret, tvr, mgn, m2y, nfail, pcmax, pcmin) in rows:
    absmax = round(max(abs(pcmax), abs(pcmin)), 4) if pcmax is not None else None
    entries.append({
        "wave": w, "item_id": tag, "alpha_id": aid, "expression": expr,
        "neutralization": neut, "sharpe": sh, "fitness": fit, "returns": ret,
        "turnover": tvr, "margin_bps": mgn, "two_year_sharpe": m2y,
        "fail_count": nfail, "gate_zero_fail": nfail == 0,
        "prod_corr_reported_max": pcmax, "prod_corr_min": pcmin,
        "prod_corr_abs_max": absmax, "prod_corr_verified": pcmax is not None,
        "gate_prod_corr_065": (absmax is not None and absmax < 0.65),
        "champion_score_strict_abs": cs(fit, mgn, absmax) if absmax is not None else None,
        "champion_score_platform_max": cs(fit, mgn, pcmax) if pcmax is not None else None,
    })

ledger = {
    "campaign": "USA_other_other566", "waves": [34, 35], "date": "2026-11-06",
    "region": "USA", "universe": "TOP1000", "delay": 1, "dataset": "other566",
    "parent": "kqNgXQqd",
    "settings": {"decay": 0, "truncation": 0.08, "pasteurization": "ON",
                 "nan_handling": "ON", "unit_handling": "VERIFY"},
    "n_new_entries": len(entries), "entries": entries,
}
json.dump(ledger, open("wave34_35_ledger.json", "w"), indent=1, ensure_ascii=False)

ch = json.load(open("campaign_champions.json"))
meta = ch["campaign_metadata"]
meta["total_batches_simulated"] = 35
meta["total_alphas_simulated"] = 258 + len(entries)
meta["status"] = "NO_PRODUCTION_PASS"
meta.setdefault("champion", {})["alpha_id"] = "kqNgXQqd"
meta["champion"]["champion_score"] = 0.5703
meta["champion"]["selection_rule"] = "strict abs-max prod corr < 0.65, then Champion_Score"
meta["champion_note"] = (
    "Absolute-correlation audit changed the ranking: every higher-margin variant of this seed carries one "
    "production alpha at |corr| = 0.68-0.73 in the NEGATIVE tail, while the platform's reported "
    "'max_correlation' only looks at the positive side. Under the strict ProdCorr < 0.65 requirement only "
    "kqNgXQqd qualifies (abs max 0.5052)."
)
meta["correlation_audit_finding"] = {
    "statement": "platform prod 'max_correlation' can understate true max |corr| by up to 0.11",
    "evidence": {
        "kqNgXQqd_statistical": {"max": 0.5052, "min": -0.4705, "abs_max": 0.5052},
        "E568aJjP_sector": {"max": 0.6477, "min": -0.7093, "abs_max": 0.7093},
        "xArbWY9p_crowding": {"max": 0.6227, "min": -0.7334, "abs_max": 0.7334},
        "wpQ2zzJ5_reversion_momentum": {"max": 0.6712, "min": -0.6821, "abs_max": 0.6821},
    },
    "action": "champion selection must use abs_max, not the reported max",
}
ch["wave34_35"] = {
    "hypotheses_tested": [
        "PV momentum orthogonalization (vector_neut vs 20d price change)",
        "risk-parity vol scaling (divide by ts_std_dev(returns,60))",
        "hump turnover control (hump=0.003, no ts_mean shell)",
        "tail shrink signed_power(p=0.5)",
        "cold label x confidence (r20marsi_label_5 x prob_5)",
        "properly-scaled 2-leg consensus (equal / 70-30 / vol-scaled)",
        "confidence power 2",
        "time-series self-relative normalization (ts_quantile / ts_rank / ts_zscore @ 60/120/250)",
        "full neutralization map (SECTOR / CROWDING / REVERSION_AND_MOMENTUM / FAST / SLOW_AND_FAST)",
    ],
    "outcome": "ALL FALSIFIED - every construction variant collapses into the Sharpe 1.19-1.27 / R 2.6-3.1% / TO 13-14% band",
    "neutralization_map": "STAT gives IR (Sh 1.27, R 3.04%, Mgn 4.37, 2Y 1.86); SECTOR gives unit-turnover profit (Sh 1.00, R 4.60%, Mgn 7.39, 2Y 1.38) - same frontier, different points",
    "best_fitness_reached": 0.61, "best_sharpe_reached": 1.27, "best_margin_reached_bps": 7.39,
    "new_zero_fail_alphas": [e["alpha_id"] for e in entries if e["gate_zero_fail"]],
    "champion": "kqNgXQqd", "champion_score": 0.5703,
}
json.dump(ch, open("campaign_champions.json", "w"), indent=1, ensure_ascii=False)

print("total alphas:", meta["total_alphas_simulated"], "| zero-fail new:", sum(1 for e in entries if e["gate_zero_fail"]))
for e in entries:
    if e["gate_zero_fail"]:
        print("%-9s %-24s Sh %.2f Fit %.2f Mgn %.2f 2Y %.2f absPC %-7s CS %s" % (
            e["alpha_id"], e["item_id"], e["sharpe"], e["fitness"], e["margin_bps"],
            e["two_year_sharpe"], e["prod_corr_abs_max"], e["champion_score_strict_abs"]))
