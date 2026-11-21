# -*- coding: utf-8 -*-
"""落盘 FND23_Q8 结果 + 裁决"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

rows = [
 {"slot":1,"alpha_id":"2rAdAlPJ","expression":"group_zscore(winsorize(divide(fnd23_cf_m_olto, total_assets_5), std=3), industry)",
  "sharpe":0.59,"fitness":0.22,"turnover":0.0719,"returns":0.0168,"margin":0.000466,
  "long_count":489,"short_count":546,"sub_universe_sharpe":0.27,"two_year_sharpe":0.66,
  "investability_sharpe":0.63,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_SUB_UNIVERSE_SHARPE","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":2,"alpha_id":"xArgrjXl","expression":"group_zscore(winsorize(divide(ts_delta(total_assets_5, 252), total_assets_5), std=3), industry)",
  "sharpe":0.28,"fitness":0.07,"turnover":0.0889,"returns":0.0082,"margin":0.000185,
  "long_count":465,"short_count":570,"sub_universe_sharpe":0.05,"two_year_sharpe":0.41,
  "investability_sharpe":0.38,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_SUB_UNIVERSE_SHARPE","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":3,"alpha_id":"RREWE70g","expression":"group_zscore(winsorize(divide(fnd23_cf_m_sspf, total_assets_5), std=3), industry)",
  "sharpe":-0.42,"fitness":-0.13,"turnover":0.0747,"returns":-0.0126,"margin":-0.000336,
  "long_count":538,"short_count":498,"sub_universe_sharpe":0.22,"two_year_sharpe":-1.23,
  "investability_sharpe":-0.42,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","LOW_SUB_UNIVERSE_SHARPE","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":4,"alpha_id":"88R1Rlkq","expression":"group_zscore(winsorize(divide(fnd23_cf_m_fcos, total_assets_5), std=3), industry)",
  "sharpe":0.66,"fitness":0.25,"turnover":0.076,"returns":0.0183,"margin":0.000481,
  "long_count":537,"short_count":498,"sub_universe_sharpe":0.34,"two_year_sharpe":0.96,
  "investability_sharpe":0.6,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_SUB_UNIVERSE_SHARPE","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TROVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":5,"alpha_id":"YP1q17wA","expression":"group_zscore(winsorize(divide(fnd23_cf_m_xecs, total_assets_5), std=3), industry)",
  "sharpe":-0.24,"fitness":-0.06,"turnover":0.0644,"returns":-0.0066,"margin":-0.000206,
  "long_count":598,"short_count":437,"sub_universe_sharpe":-0.32,"two_year_sharpe":0.21,
  "investability_sharpe":-0.22,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_SUB_UNIVERSE_SHARPE","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":6,"alpha_id":"qMLqLjkO","expression":"group_zscore(winsorize(divide(subtract(fnd23_cf_m_olto, fnd23_icsm_m_taiv), total_assets_5), std=3), industry)",
  "sharpe":0.58,"fitness":0.21,"turnover":0.0795,"returns":0.0162,"margin":0.000409,
  "long_count":510,"short_count":526,"sub_universe_sharpe":0.47,"two_year_sharpe":0.49,
  "investability_sharpe":0.54,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","LOW_SUB_UNIVERSE_SHARPE","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":7,"alpha_id":"QPvXv7qM","expression":"group_zscore(winsorize(ts_delta(divide(fnd23_cf_m_olto, total_assets_5), 252), std=3), industry)",
  "sharpe":-0.15,"fitness":-0.03,"turnover":0.0857,"returns":-0.0039,"margin":-0.000091,
  "long_count":543,"short_count":492,"sub_universe_sharpe":-0.13,"two_year_sharpe":-0.27,
  "investability_sharpe":-0.3,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_SUB_UNIVERSE_SHARPE","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","MATCHES_PYRAMID","MATCHES_THEMES"]},
 {"slot":8,"alpha_id":"e75R5zgd","expression":"group_zscore(winsorize(divide(fnd23_icsm_m_ists, fnd23_icsm_m_taiv), std=3), industry)",
  "sharpe":0.05,"fitness":0.01,"turnover":0.085,"returns":0.0015,"margin":0.000035,
  "long_count":493,"short_count":542,"sub_universe_sharpe":0.34,"two_year_sharpe":0.84,
  "investability_sharpe":0.14,"risk_neutralized_sharpe":None,"ra_failed":True,
  "authoritative_fail":["LOW_SHARPE","LOW_FITNESS","LOW_2Y_SHARPE"],
  "warnings":["CLUSTER_TEST","MATCHES_THEMES"],
  "checks_pass":["LOW_TURNOVER","HIGH_TURNOVER","CONCENTRATED_WEIGHT","LOW_SUB_UNIVERSE_SHARPE","MATCHES_PYRAMID","MATCHES_THEMES"]},
]

DECISION = (
 "0/8 通过门禁，但实现了结构性突破：8/8 全部 CONCENTRATED_WEIGHT PASS、广度 900-1035 只、"
 "turnover 6.4-8.9%，这是账户内基本面信号首次同时满足「广度 + 无浓度失败 + 合理换手」。"
 "机制排序（Sharpe）：营运资本变动/总资产 0.66（subU 0.34 距门槛 0.35 仅差 0.01，drawdown 仅 5.67%，最接近通过）"
 "> 经营现金流/总资产 0.59 > 应计缺口 (CFO-TAIV)/TA 0.58（subU 0.47 通过，2Y 0.49 是短板）"
 "> 资产增长 0.28 > 特殊项目占比 0.05；净发行 -0.42、CAPEX 强度 -0.24、现金盈利变化 -0.15 为负向或无效。"
 "核心结论：(1) fnd23 数据集本身健康（无浓度失败、广度满分），失败纯粹是信号强度不足，Sharpe 0.05-0.66 距 1.58 仍有大差距；"
 "(2) 现金流质量族（营运资本 + CFO + 应计缺口）三个成员全部为正且 Sharpe 0.58-0.66 高度一致，"
 "说明「现金确认质量」是 fnd23 的真实信号方向，值得深化；"
 "(3) 资产增长与净发行在本数据集不工作，与文献的负向预期相反；"
 "(4) 账户内已验证的 Sharpe 放大器是 power(x, 3~4) 尾部锐化 —— 账户最高 Sharpe 1.67 的 alpha 用 power(...,4)，"
 "fnd17 冠军用 power(subtract(group_rank(...), 0.5), 3)，而本批的 group_zscore 未锐化尾部。"
 "下一批应：(a) 只保留现金流质量族三成员；"
 "(b) 施加 power 锐化放大 Sharpe；"
 "(c) 用 ts_backfill 处理 fnd23 季度更新的空窗期（fnd17 冠军用了 ts_backfill(f,120)/250），"
 "这可能是 sub_universe_sharpe 与 2Y 的短板来源。无 alpha 提交。"
)

doc = {
 "multisimulation_id": "4aM63daZX4IDb6M15yaSzbPW",
 "status": "COMPLETE",
 "total_requested": 8,
 "total_created": 8,
 "simulation_only": True,
 "alpha_submission_calls": 0,
 "alpha_results": rows,
 "batch_decision": DECISION,
 "threshold_policy": {
   "all_fail_items_required_zero": True, "all_warning_items_required_zero": True,
   "sharpe_min": 1.58, "fitness_min": 1.0, "margin_min_bps": 10,
   "turnover_min": 0.05, "turnover_max": 0.5, "submission_forbidden": True},
}

out = os.path.join(HERE, "batch_FND23_Q8_result.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
print("written", out)
