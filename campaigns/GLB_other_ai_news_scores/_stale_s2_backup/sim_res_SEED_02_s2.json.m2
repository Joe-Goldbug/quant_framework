{
  "mock": true,
  "corrected_exprs": [
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 10, 0.8), subindustry)",
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 20, 0.8), subindustry)",
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 10, 0.8), industry)",
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 20, 0.8), industry)",
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 10, 0.8), market)",
    "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 20, 0.8), market)",
    "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 15), subindustry)",
    "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 30), subindustry)",
    "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 30), industry)",
    "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 60), industry)",
    "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 10, 0.8), subindustry)",
    "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 20, 0.8), subindustry)",
    "group_rank(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 15), industry)",
    "group_rank(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 30), industry)",
    "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 10, 0.8), market)",
    "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 20, 0.8), market)",
    "group_neutralize(s_log_1p(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 15)), subindustry)",
    "group_neutralize(s_log_1p(ts_decay_linear(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 30)), subindustry)",
    "group_neutralize(ts_decay_exp_window(signed_power(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 1.5), 10, 0.8), subindustry)",
    "group_neutralize(ts_decay_exp_window(signed_power(divide(subtract(negative_score_median_value_3, negative_score_maximum_value), add(negative_score_average_value, 1)), 1.5), 20, 0.8), subindustry)"
  ]
}