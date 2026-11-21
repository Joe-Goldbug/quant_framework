"""persist_wave_results_29_30_33.py — write fetched multi-sim results into
batch_NN_result.json in the MCP payload shape alpha_normalizer.normalize() reads:
    {alpha_id, code, settings, metrics:{...}, checks:{fail:[], warning:[]}}
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

S = {"instrumentType": "EQUITY", "region": "USA", "universe": "TOP1000", "delay": 1,
     "decay": 0, "neutralization": "STATISTICAL", "truncation": 0.08,
     "pasteurization": "ON", "nanHandling": "ON", "language": "FASTEXPR"}

Q = 'quantile(group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.05), subindustry), driver="gaussian")'

ROWS = [
 ("88RvzW3m", 29, "x29_outer_tvr05",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.05), subindustry)",
  0.94, 0.41, 0.0843, 0.0238, 0.0469, 0.000564, 0.77, 1.14, 0.52,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("YP1xp35w", 29, "x29_outer_tvr04",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.04), subindustry)",
  0.86, 0.36, 0.0754, 0.0218, 0.0473, 0.000579, 0.74, 1.07, 0.47,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("kqNJ3pVL", 29, "x29_outer_tvr03",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.03), subindustry)",
  0.80, 0.32, 0.0670, 0.0199, 0.0467, 0.000595, 0.78, 1.04, 0.41,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("GrWgwjdo", 29, "x29_outer_tvr05_quantile", Q,
  0.97, 0.43, 0.0919, 0.0248, 0.0525, 0.000541, 0.75, 1.19, 0.54,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("qMLEA2Wj", 29, "x29_outer_tvr05_sp15",
  "signed_power(group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.05), subindustry), 1.5)",
  0.83, 0.37, 0.0943, 0.0246, 0.0486, 0.000522, 0.80, 0.83, 0.50,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("E56Vwnvm", 29, "x29_three_layer",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.10), ts_target_tvr_decay(group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry), target_tvr=0.05)), target_tvr=0.05), subindustry)",
  0.74, 0.28, 0.0739, 0.0173, 0.0375, 0.000469, 0.42, 0.74, 0.11,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("xAr1x7YW", 29, "x29_outer_tvr05_weighted_slow",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), multiply(group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry), 2.0)), target_tvr=0.05), subindustry)",
  0.94, 0.41, 0.0843, 0.0238, 0.0469, 0.000564, 0.77, 1.14, 0.52,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("d5WKxJb2", 29, "x29_outer_tvr05_ind",
  "group_zscore(ts_target_tvr_decay(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_pe_ratio), subindustry)), target_tvr=0.05), industry)",
  0.94, 0.41, 0.0819, 0.0239, 0.0468, 0.000585, 0.77, 1.11, 0.51,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),

 ("akKVno8W", 30, "x30_slow1",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(diff_current_vs_hist_price_ratio_earnings), subindustry)), subindustry)",
  1.05, 0.49, 0.1080, 0.0271, 0.0468, 0.000501, 0.87, 1.30, 0.60, []),
 ("omEolVXl", 30, "x30_slow2",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(reverse(forward_pe_ratio_mean_fy1), subindustry)), subindustry)",
  0.67, 0.25, 0.1032, 0.0174, 0.0792, 0.000338, 0.30, 1.18, 0.39,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("O0AJZojJ", 30, "x30_slow3",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(oth685_91v, subindustry)), subindustry)",
  0.18, 0.04, 0.1846, 0.0084, 0.1144, 0.000092, 0.34, -0.07, 0.34,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("gJeWMx50", 30, "x30_slow4",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(oth685_cfroitrn, subindustry)), subindustry)",
  -0.78, -0.38, 0.1456, -0.0351, 0.3991, -0.000483, -0.40, -0.79, -0.39,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("JjePObJj", 30, "x30_slow5",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(blended_growth_rate_smartest, subindustry)), subindustry)",
  0.09, 0.01, 0.1063, 0.0023, 0.1107, 0.000044, 0.17, 1.44, -0.21,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("pwdvl8eg", 30, "x30_slow6",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(smartest_growth_this_vs_last_year_earnings, subindustry)), subindustry)",
  0.20, 0.04, 0.0881, 0.0049, 0.0726, 0.000112, 0.47, 0.40, 0.00,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("A1VQPk8w", 30, "x30_slow7",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(oth685_81v, subindustry)), subindustry)",
  -0.43, -0.14, 0.1743, -0.0197, 0.2739, -0.000226, 0.06, -1.65, -0.42,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("A1VQPk8e", 30, "x30_slow8",
  "group_zscore(add(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08), group_zscore(median_forward_12m_pe_ratio_hist, subindustry)), subindustry)",
  0.38, 0.10, 0.0570, 0.0092, 0.0580, 0.000323, 0.12, 0.07, 0.17,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),

 ("A1VQGZpe", 33, "x33_slow_only_t03",
  "group_zscore(ts_target_tvr_decay(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), target_tvr=0.03), subindustry)",
  0.89, 0.38, 0.0746, 0.0226, 0.0499, 0.000606, 0.72, 1.24, 0.55,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE"]),
 ("LLM5Gav2", 33, "x33_c05_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), multiply(0.5, subtract(rank(oth566_r20marsi_ret), 0.5))), target_tvr=0.03), subindustry)",
  0.77, 0.30, 0.0712, 0.0186, 0.0532, 0.000521, 0.56, 1.22, 0.42,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("A1VQGZAR", 33, "x33_c10_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), multiply(1.0, subtract(rank(oth566_r20marsi_ret), 0.5))), target_tvr=0.03), subindustry)",
  0.71, 0.26, 0.0688, 0.0167, 0.0507, 0.000485, 0.53, 1.07, 0.27,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("RREAmQgn", 33, "x33_c20_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), multiply(2.0, subtract(rank(oth566_r20marsi_ret), 0.5))), target_tvr=0.03), subindustry)",
  0.60, 0.20, 0.0656, 0.0136, 0.0536, 0.000414, 0.38, 0.77, 0.16,
  ["LOW_SHARPE", "LOW_FITNESS", "IS_LADDER_SHARPE"]),
 ("VkxdGjWY", 33, "x33_c10_tvrfast_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), multiply(1.0, subtract(rank(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08)), 0.5))), target_tvr=0.03), subindustry)",
  0.39, 0.10, 0.0641, 0.0088, 0.0511, 0.000275, 0.07, -0.19, -0.18,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("WjOLAQ5G", 33, "x33_c10_tvrfast_t05",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_pe_ratio)), multiply(1.0, subtract(rank(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08)), 0.5))), target_tvr=0.05), subindustry)",
  0.62, 0.21, 0.0821, 0.0142, 0.0518, 0.000345, 0.05, 0.14, 0.07,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("YP1xvKeM", 33, "x33_pee_c10_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(0.5, rank(diff_current_vs_hist_price_ratio_earnings)), multiply(1.0, subtract(rank(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08)), 0.5))), target_tvr=0.03), subindustry)",
  0.37, 0.10, 0.0643, 0.0084, 0.0508, 0.000262, 0.13, -0.17, -0.22,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
 ("2rAjpzYx", 33, "x33_ey_c10_t03",
  "group_zscore(ts_target_tvr_decay(add(subtract(rank(earnings_yield_industry_percentile_fy1), 0.5), multiply(1.0, subtract(rank(ts_target_tvr_decay(oth566_r20marsi_ret, target_tvr=0.08)), 0.5))), target_tvr=0.03), subindustry)",
  0.20, 0.04, 0.0644, 0.0046, 0.0818, 0.000143, -0.28, 0.52, -0.34,
  ["LOW_SHARPE", "LOW_FITNESS", "LOW_SUB_UNIVERSE_SHARPE", "IS_LADDER_SHARPE"]),
]


def main():
    by = {}
    for (aid, b, item, code, sh, fi, to, r, dd, mg, sub, y2, cl, fails) in ROWS:
        fail_items = [{"name": n, "limit": 1.58, "value": sh} for n in fails]
        warn = [{"name": "CLUSTER_TEST", "value": cl, "limit": 1.58}]
        for n in fails:
            if n == "LOW_FITNESS":
                warn.append({"name": "LOW_FITNESS", "value": fi, "limit": 1.0})
            elif n == "LOW_SUB_UNIVERSE_SHARPE":
                warn.append({"name": "LOW_SUB_UNIVERSE_SHARPE", "value": sub, "limit": 0.2})
            elif n == "LOW_2Y_SHARPE":
                warn.append({"name": "LOW_2Y_SHARPE", "value": y2, "limit": 1.58})
            elif n == "IS_LADDER_SHARPE":
                warn.append({"name": "IS_LADDER_SHARPE", "value": y2, "limit": 1.58})
        by.setdefault(b, []).append({
            "alpha_id": aid, "item_id": item, "code": code, "settings": dict(S),
            "metrics": {"sharpe": sh, "fitness": fi, "turnover": to, "returns": r,
                        "drawdown": dd, "margin": mg, "sub_universe_sharpe": sub,
                        "two_year_sharpe": y2, "cluster_test": cl,
                        "longCount": 500, "shortCount": 500, "pnl": 0,
                        "bookSize": 20000000},
            "checks": {"fail": fail_items, "warning": warn},
        })
    for b, rows in by.items():
        p = os.path.join(HERE, f"batch_{b:02d}_result.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"batch": b, "alpha_results": rows}, f, indent=2, ensure_ascii=False)
        print("wrote", os.path.basename(p), len(rows))


if __name__ == "__main__":
    main()
