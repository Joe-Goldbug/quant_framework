{
  "summary": {
    "pairs": 10,
    "counts": {
      "PLATEAU": 0,
      "SPIKE": 0,
      "WEAK": 0,
      "NO_DATA": 10
    },
    "plateau_slots": [],
    "spike_slots": [],
    "paired_slot_count": 20
  },
  "verdicts": [
    {
      "slots": [
        1,
        2
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM,NUM),subindustry)"
    },
    {
      "slots": [
        3,
        4
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM,NUM),industry)"
    },
    {
      "slots": [
        5,
        6
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_neutralize(ts_decay_exp_window(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM,NUM),market)"
    },
    {
      "slots": [
        7,
        8
      ],
      "windows": [
        15,
        30
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM),subindustry)"
    },
    {
      "slots": [
        9,
        10
      ],
      "windows": [
        30,
        60
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_zscore(ts_decay_linear(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM),industry)"
    },
    {
      "slots": [
        11,
        12
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM,NUM),subindustry)"
    },
    {
      "slots": [
        13,
        14
      ],
      "windows": [
        15,
        30
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_rank(ts_decay_linear(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM),industry)"
    },
    {
      "slots": [
        15,
        16
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_rank(ts_decay_exp_window(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM,NUM),market)"
    },
    {
      "slots": [
        17,
        18
      ],
      "windows": [
        15,
        30
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_neutralize(s_log_1p(ts_decay_linear(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM)),subindustry)"
    },
    {
      "slots": [
        19,
        20
      ],
      "windows": [
        10,
        20
      ],
      "sharpe_short": null,
      "sharpe_long": null,
      "stable_min_abs_sharpe": null,
      "verdict": "NO_DATA",
      "plateau_pass": false,
      "skeleton": "group_neutralize(ts_decay_exp_window(signed_power(divide(subtract(negative_score_median_value_3,negative_score_maximum_value),add(negative_score_average_value,NUM)),NUM),NUM,NUM),subindustry)"
    }
  ]
}