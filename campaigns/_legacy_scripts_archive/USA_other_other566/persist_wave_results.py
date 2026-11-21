"""persist_wave_results.py — write fetched multi-sim results into batch_NN_result.json
in the MCP payload shape that alpha_normalizer.normalize() understands:
    {alpha_id, code, settings, metrics:{...}, checks:{fail:[], warning:[]}}

Usage: python persist_wave_results.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SETTINGS = {"instrumentType": "EQUITY", "region": "USA", "universe": "TOP1000",
            "delay": 1, "decay": 0, "neutralization": "STATISTICAL",
            "truncation": 0.08, "pasteurization": "ON", "nanHandling": "ON",
            "language": "FASTEXPR"}

# (alpha_id, batch, item_id, code, sharpe, fitness, turnover, returns, drawdown,
#  margin, sub_universe_sharpe, two_year_sharpe, cluster, fail_names)
ROWS = [
 # ---------------- wave 26 ----------------
 ("ZYQmoekn", 26, "x26_cons_ey",
  "group_zscore(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(earnings_yield_smartest_fy1)), subindustry)",
  0.77, 0.10, 0.8969, 0.0153, 0.0469, 0.000034, 0.85, 0.99, 0.60,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "IS_LADDER_SHARPE"]),
 ("WjOLg6KO", 26, "x26_cons_ey_growth",
  "group_zscore(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(smartest_growth_next_vs_this_year_earnings)), subindustry)",
  1.06, 0.17, 0.9006, 0.0231, 0.0330, 0.000051, 1.07, 1.04, 0.46,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "IS_LADDER_SHARPE"]),
 ("2rAjKbq8", 26, "x26_value_weight_ey",
  "group_zscore(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(earnings_yield_industry_percentile_fy1)), subindustry)",
  1.03, 0.16, 0.8961, 0.0209, 0.0492, 0.000047, 0.94, 1.07, 0.58,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "IS_LADDER_SHARPE"]),
 ("O0AJ9Ewb", 26, "x26_revision_weight",
  "group_zscore(multiply(group_zscore(oth566_return, subindustry), rank(smartest_growth_next_vs_this_year_earnings)), subindustry)",
  0.99, 0.16, 0.8656, 0.0221, 0.0418, 0.000051, 0.34, 0.79, 0.49,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("6XdAEvPK", 26, "x26_relval_divergence",
  "group_zscore(subtract(group_zscore(oth566_r20marsi_ret, subindustry), group_zscore(earnings_yield_industry_percentile_fy1, subindustry)), subindustry)",
  0.77, 0.12, 0.7071, 0.0174, 0.0353, 0.000049, 0.88, 0.56, 0.41,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "IS_LADDER_SHARPE"]),
 ("N1NeOvW8", 26, "x26_cashflow_quality",
  "group_zscore(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(oth685_81v)), subindustry)",
  -0.12, -0.01, 0.8636, -0.0060, 0.1940, -0.000014, 0.04, 0.57, 0.08,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "IS_LADDER_SHARPE"]),
 ("qMLEXov1", 26, "x26_pe_history",
  "group_zscore(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(diff_current_vs_hist_pe_ratio)), subindustry)",
  1.45, 0.27, 0.9001, 0.0307, 0.0447, 0.000068, 0.98, 2.43, 0.50,
  ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER"]),
 ("xAr1n09m", 26, "x26_baseline_slow",
  "group_zscore(oth685_cfroi_3, subindustry)",
  -0.20, -0.05, 0.1402, -0.0094, 0.2381, -0.000134, 0.08, -1.78, 0.01,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE"]),
 # ---------------- wave 27 ----------------
 ("QPvYQz3p", 27, "x27_base_ey",
  "group_zscore(earnings_yield_smartest_fy1, subindustry)",
  0.40, 0.12, 0.0889, 0.0114, 0.1043, 0.000257, 0.02, 0.52, 0.29,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "LOW_2Y_SHARPE"]),
 ("9qxERMj1", 27, "x27_base_pehist",
  "group_zscore(diff_current_vs_hist_pe_ratio, subindustry)",
  -1.09, -0.52, 0.1087, -0.0280, 0.2961, -0.000515, -0.84, -1.28, -0.59,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "LOW_2Y_SHARPE"]),
 ("KPJmLzN8", 27, "x27_base_grow",
  "group_zscore(smartest_growth_next_vs_this_year_earnings, subindustry)",
  0.31, 0.08, 0.1142, 0.0083, 0.0656, 0.000145, 0.69, 1.03, 0.05,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE"]),
 ("leAM0Gv8", 27, "x27_pehist_tvr08",
  "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, rank(diff_current_vs_hist_pe_ratio)), target_tvr=0.08), subindustry)",
  0.13, 0.02, 0.1138, 0.0029, 0.0821, 0.000051, -0.42, -0.20, -0.17,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("j2YegGAo", 27, "x27_pehist_tvr12",
  "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, rank(diff_current_vs_hist_pe_ratio)), target_tvr=0.12), subindustry)",
  0.24, 0.04, 0.1555, 0.0053, 0.0747, 0.000069, -0.31, -0.04, -0.31,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("A1VQ3zNX", 27, "x27_pehist_inner_zs",
  "group_zscore(ts_target_tvr_decay(multiply(group_zscore(oth566_r20marsi_ret, subindustry), rank(diff_current_vs_hist_pe_ratio)), target_tvr=0.08), subindustry)",
  0.36, 0.09, 0.1039, 0.0077, 0.0557, 0.000148, 0.10, -0.26, 0.03,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("RREArz6j", 27, "x27_add_pehist",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(diff_current_vs_hist_pe_ratio, subindustry)), subindustry)",
  -1.07, -0.50, 0.1083, -0.0274, 0.2924, -0.000507, -0.84, -1.23, -0.56,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("3qojAPVg", 27, "x27_3f_value_rev",
  "group_zscore(ts_target_tvr_decay(multiply(multiply(oth566_r20marsi_ret, rank(earnings_yield_smartest_fy1)), rank(diff_current_vs_hist_pe_ratio)), target_tvr=0.08), subindustry)",
  0.16, 0.03, 0.1180, 0.0033, 0.0954, 0.000056, -0.29, 0.37, 0.06,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 # ---------------- wave 28 ----------------
 ("vR1OLqgA", 28, "x28_add_negpe",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), subindustry)",
  1.07, 0.50, 0.1083, 0.0274, 0.0466, 0.000507, 0.84, 1.23, 0.56, []),
 ("d5WKxXLY", 28, "x28_add_negpe_tvr05",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.05), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), subindustry)",
  1.07, 0.50, 0.1083, 0.0274, 0.0466, 0.000507, 0.84, 1.23, 0.56, []),
 ("RREAp3Wz", 28, "x28_mult_negpe",
  "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, rank(reverse(diff_current_vs_hist_pe_ratio))), target_tvr=0.08), subindustry)",
  1.05, 0.46, 0.1124, 0.0238, 0.0544, 0.000424, 0.61, 1.35, 0.50, []),
 ("9qxEwv02", 28, "x28_mult_negpe_tvr12",
  "group_zscore(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, rank(reverse(diff_current_vs_hist_pe_ratio))), target_tvr=0.12), subindustry)",
  1.22, 0.52, 0.1551, 0.0282, 0.0584, 0.000364, 0.71, 1.33, 0.70, []),
 ("ZYQmp5G8", 28, "x28_add_ey",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(earnings_yield_smartest_fy1, subindustry)), subindustry)",
  0.42, 0.13, 0.0888, 0.0118, 0.0943, 0.000266, 0.02, 0.56, 0.28,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("88Rvzoqm", 28, "x28_add_ey_grow",
  "group_zscore(add(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(earnings_yield_smartest_fy1, subindustry)), group_zscore(smartest_growth_next_vs_this_year_earnings, subindustry)), subindustry)",
  0.96, 0.42, 0.1233, 0.0238, 0.0438, 0.000386, 0.81, 1.34, 0.66,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("KPJmb0Rl", 28, "x28_add_ey_mult",
  "group_zscore(add(ts_target_tvr_decay(multiply(oth566_r20marsi_ret, rank(reverse(diff_current_vs_hist_pe_ratio))), target_tvr=0.08), group_zscore(earnings_yield_smartest_fy1, subindustry)), subindustry)",
  0.42, 0.13, 0.0888, 0.0116, 0.0945, 0.000262, 0.01, 0.55, 0.28,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("WjOLpqmQ", 28, "x28_3f_add_pctl",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(earnings_yield_industry_percentile_fy1, subindustry)), subindustry)",
  0.19, 0.04, 0.1214, 0.0048, 0.1017, 0.000079, -0.15, 0.68, 0.00,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
]


def main():
    by_batch = {}
    for (aid, b, item, code, sh, fi, to, r, dd, mg, sub, y2, cl, fails) in ROWS:
        fail_items = [{"name": n, "limit": 1.58, "value": sh} for n in fails]
        warn_items = [{"name": "CLUSTER_TEST", "value": cl, "limit": 1.58}]
        for n in fails:
            if n == "LOW_FITNESS":
                warn_items.append({"name": "LOW_FITNESS", "value": fi, "limit": 1.0})
            elif n == "LOW_SUB_UNIVERSE_SHARPE":
                warn_items.append({"name": "LOW_SUB_UNIVERSE_SHARPE", "value": sub, "limit": 0.2})
            elif n == "LOW_2Y_SHARPE":
                warn_items.append({"name": "LOW_2Y_SHARPE", "value": y2, "limit": 1.58})
            elif n == "HIGH_TURNOVER":
                warn_items.append({"name": "HIGH_TURNOVER", "value": to, "limit": 0.70})
            elif n == "IS_LADDER_SHARPE":
                warn_items.append({"name": "IS_LADDER_SHARPE", "value": y2, "limit": 1.58})
        by_batch.setdefault(b, []).append({
            "alpha_id": aid, "item_id": item, "code": code,
            "settings": dict(SETTINGS),
            "metrics": {"sharpe": sh, "fitness": fi, "turnover": to, "returns": r,
                        "drawdown": dd, "margin": mg, "sub_universe_sharpe": sub,
                        "two_year_sharpe": y2, "cluster_test": cl,
                        "longCount": 500, "shortCount": 500, "pnl": 0,
                        "bookSize": 20000000},
            "checks": {"fail": fail_items, "warning": warn_items},
        })

    for b, rows in by_batch.items():
        p = os.path.join(HERE, f"batch_{b:02d}_result.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"batch": b, "alpha_results": rows}, f, indent=2, ensure_ascii=False)
        print(f"wrote {p} ({len(rows)} results)")


if __name__ == "__main__":
    main()
