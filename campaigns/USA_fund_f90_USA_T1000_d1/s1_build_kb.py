# -*- coding: utf-8 -*-
"""AEGIS Stage 1: 生成 fundamental90 字段物理画像契约
落盘 -> knowledge_base/fields/USA/fundamental90.json

物理实测证据 (2026-10-28):
  * 平台 datafields 元数据把 133 个字段一律标为 VECTOR (event input)。
  * 实测 ts_zscore(fnd90_game_noa, 252) 裸用 -> 平台报错
    "Operator ts_zscore does not support event inputs ... If fields is vector type should use vec_* operator"。
  * 实测 ts_zscore(vec_avg(fnd90_game_noa), 252) -> 回测成功完成 (alpha ZYQGwX9n)。
    结论: 全部 fnd90 字段为 VECTOR 事件类型，必须先用 vec_* 降维，严禁裸用。
  * 基准物理 (ZYQGwX9n, USA/TOP1000/d1, NONE/decay0):
    sharpe=0.19 fitness=0.03 turnover=46.29% returns=1.46% margin=0.63bps
    longCount=373 shortCount=337 (多空比 1.107, 对称良好, 无明显零膨胀死重)
    sub_universe_sharpe=-0.33 two_year_sharpe=-0.39 (单字段一阶水平值跨子池不稳定)
"""
import json, os, sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KB_PATH = os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental90.json")

raw = json.load(open(os.path.join(HERE, "f90_fields_raw.json"), encoding="utf-8"))

# ---- 显式角色标注 (人工经济学判定) ----
SIGNAL_FLOW = {
    # 盈利能力 / 效率的"变化量" —— 核心方向预测源
    "fnd90_game_gma_chg", "fnd90_us_game_gma_chg",
    "fnd90_game_asset_turnover_chg", "fnd90_us_game_asset_turnover_chg",
    "fnd90_game_labor_efficiency_chg", "fnd90_us_game_labor_efficiency_chg",
    "fnd90_game_deferred_sal_chg", "fnd90_us_game_deferred_sal_chg",
    "fnd90_game_depreciation_chg", "fnd90_us_game_depreciation_chg",
    "fnd90_game_capex_dep", "fnd90_us_game_capex_dep",
    "fnd90_game_capex_sale", "fnd90_us_game_capex_sale",
    # 现金回报与盈利质量
    "fnd90_qes_gamef_icfroe_1y", "fnd90_qes_gamef_icfroe_3y", "fnd90_qes_gamef_icfroe_5y",
    "fnd90_us_qes_gamef_icfroe_1y", "fnd90_us_qes_gamef_icfroe_3y", "fnd90_us_qes_gamef_icfroe_5y",
    "fnd90_qes_gamef_grossprofit_asset", "fnd90_us_qes_gamef_grossprofit_asset",
    "fnd90_game_optimism_gma", "fnd90_us_game_optimism_gma",
    "fnd90_game_optimism_sale", "fnd90_us_game_optimism_sale",
    # 综合质量打分
    "fnd90_qes_gamef_pscore", "fnd90_us_qes_gamef_pscore",
    "fnd90_qes_gamef_mohanram", "fnd90_us_qes_gamef_mohanram",
    "fnd90_qes_gamef_score", "fnd90_us_qes_gamef_score",
    "fnd90_qes_gamef_earnigs_timeliness", "fnd90_us_qes_gamef_earnigs_timeliness",
    # 营运资本 / 杠杆变迁
    "fnd90_game_inventory_chg", "fnd90_us_game_inventory_chg",
    "fnd90_game_receivable_chg", "fnd90_us_game_receivable_chg",
    "fnd90_game_total_debt_chg", "fnd90_us_game_total_debt_chg",
    "fnd90_game_deferred_tax_asset_chg", "fnd90_us_game_deferred_tax_asset_chg",
    "fnd90_game_deferred_tax_liab_chg", "fnd90_us_game_deferred_tax_liab_chg",
    "fnd90_game_other_asset_gr", "fnd90_us_game_other_asset_gr",
    # 税务与负债结构
    "fnd90_game_tax_rate", "fnd90_us_game_tax_rate",
    "fnd90_game_inc_cash_tax", "fnd90_us_game_inc_cash_tax",
    "fnd90_game_eff_interest_rate", "fnd90_us_game_eff_interest_rate",
    "fnd90_game_cash_flow_coverage", "fnd90_us_game_cash_flow_coverage",
    "fnd90_game_short_term_debt", "fnd90_us_game_short_term_debt",
    "fnd90_game_debt_convertible", "fnd90_us_game_debt_convertible",
    "fnd90_game_amortization_rate", "fnd90_us_game_amortization_rate",
    "fnd90_game_prepaid_expense", "fnd90_us_game_prepaid_expense",
    "fnd90_game_non_oper_inc", "fnd90_us_game_non_oper_inc",
    "fnd90_game_interest_investment_inc", "fnd90_us_game_interest_investment_inc",
    # 养老金（表外索取权）
    "fnd90_game_pension_pbo", "fnd90_us_game_pension_pbo",
    "fnd90_game_pension_ev", "fnd90_us_game_pension_ev",
    "fnd90_game_pension_debt_equi_pbo", "fnd90_us_game_pension_debt_equi_pbo",
    "fnd90_game_pension_discount_rate", "fnd90_us_game_pension_discount_rate",
    "fnd90_game_pension_expense", "fnd90_us_game_pension_expense",
    "fnd90_game_pension_interest", "fnd90_us_game_pension_interest",
    "contingent_liabilities_equity_ratio", "illiquid_asset_ratio", "preferred_equity_proportion",
}

UNCERTAINTY_SCALE = {
    # 波动 / 可变性 / 分歧标尺
    "fnd90_game_accruals_vol", "fnd90_us_game_accruals_vol",
    "fnd90_game_eps_vol", "fnd90_us_game_eps_vol",
    "fnd90_game_eps_sur_vol", "fnd90_us_game_eps_sur_vol",
    "fnd90_game_gross_margin_vol", "fnd90_us_game_gross_margin_vol",
    "fnd90_game_sg_a_vol", "fnd90_us_game_sg_a_vol",
    "fnd90_game_relative_rtn_vol", "fnd90_us_game_relative_rtn_vol",
    "fnd90_qes_gamef_cashflow_var", "fnd90_us_qes_gamef_cashflow_var",
    "fnd90_qes_gamef_earn_var", "fnd90_us_qes_gamef_earn_var",
    # 法证 / 困境风险标尺
    "fnd90_qes_gamef_chs_default", "fnd90_us_qes_gamef_chs_default",
    "fnd90_qes_gamef_ohlson", "fnd90_us_qes_gamef_ohlson",
    "fnd90_qes_gamef_cscore", "fnd90_us_qes_gamef_cscore",
    "fnd90_game_earning_smooth", "fnd90_us_game_earning_smooth",
    "fnd90_game_sg_a_inefficiency", "fnd90_us_game_sg_a_inefficiency",
    "fnd90_game_sg_a_cost_ratio", "fnd90_us_game_sg_a_cost_ratio",
    "fnd90_game_noa", "fnd90_us_game_noa",
}

CATALYST_EVENT = {
    # 离散事件 / 计数型 / 反复性科目
    "fnd90_game_esop_grant", "fnd90_us_game_esop_grant",
    "fnd90_game_equity_dilution", "fnd90_us_game_equity_dilution",
    "fnd90_game_serial_special", "fnd90_us_game_serial_special",
    "fnd90_qes_gamef_negative_earnings", "fnd90_us_qes_gamef_negative_earnings",
    "fnd90_game_an_cov_chng", "fnd90_us_game_an_cov_chng",
    "fnd90_qes_gamef_chs_default", "fnd90_us_qes_gamef_chs_default",
}

DIMENSION_ANCHOR = {
    # 同数据集内生基准标尺（严禁外部 close/volume/cap）
    "fnd90_game_non_production_asset", "fnd90_us_game_non_production_asset",
    "fnd90_game_minority_interest", "fnd90_us_game_minority_interest",
    "fnd90_game_finished_goods", "fnd90_us_game_finished_goods",
    "fnd90_game_inventory_days", "fnd90_us_game_inventory_days",
    "fnd90_game_receivable_days", "fnd90_us_game_receivable_days",
    "fnd90_game_payble_days", "fnd90_us_game_payble_days",
}

# 值域人工判定：明确为"占比/比率"的字段 -> [0,1]；得分类为整数有界；其余无界
DOMAIN_01 = {
    "fnd90_game_debt_convertible", "fnd90_us_game_debt_convertible",
    "fnd90_game_finished_goods", "fnd90_us_game_finished_goods",
    "fnd90_game_minority_interest", "fnd90_us_game_minority_interest",
    "fnd90_game_pension_pbo", "fnd90_us_game_pension_pbo",
    "fnd90_game_pension_ev", "fnd90_us_game_pension_ev",
    "contingent_liabilities_equity_ratio", "illiquid_asset_ratio", "preferred_equity_proportion",
    "fnd90_game_sg_a_cost_ratio", "fnd90_us_game_sg_a_cost_ratio",
    "fnd90_game_tax_rate", "fnd90_us_game_tax_rate",
}

SPARSE_LOW_COVERAGE_THRESHOLD = 0.45

fields = {}
for r in raw:
    fid = r["id"]
    cov = r.get("coverage", 0.0)
    # 角色优先级: Catalyst_Event > Uncertainty_Scale > Dimension_Anchor > Signal_Flow > 默认
    if fid in CATALYST_EVENT:
        role = "Catalyst_Event"
    elif fid in UNCERTAINTY_SCALE:
        role = "Uncertainty_Scale"
    elif fid in DIMENSION_ANCHOR:
        role = "Dimension_Anchor"
    elif fid in SIGNAL_FLOW:
        role = "Signal_Flow"
    else:
        role = "Unclassified"

    domain = "[0, 1]" if fid in DOMAIN_01 else "unbounded"
    fields[fid] = {
        "type": "VECTOR",               # 实测：裸用报 "does not support event inputs"，必须 vec_* 降维
        "requires_vector_wrapper": True,
        "domain": domain,
        "is_sparse": cov < SPARSE_LOW_COVERAGE_THRESHOLD,
        "semantic_role": role,
        "description": r.get("description", ""),
        "coverage": cov,
        "alpha_count": r.get("alphaCount", 0),
        "user_count": r.get("userCount", 0),
        "crowding": "极低 (平台 %d 个 alpha 使用)" % r.get("alphaCount", 0),
        "update_frequency": "季度/年度基本面 (低频，需 ts_backfill 或长窗平滑)",
        "zero_inflation": "低覆盖字段(%s)存在缺失零膨胀风险" % ("是" if cov < SPARSE_LOW_COVERAGE_THRESHOLD else "否"),
    }

doc = {
    "dataset_id": "fundamental90",
    "dataset_name": "Governance, Accounting, Management, and Equality",
    "category": "fundamental",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "total_fields": len(fields),
    "dataset_coverage": 0.774,
    "dataset_user_count": 79,
    "dataset_alpha_count": 135,
    "dataset_value_score": 5.0,
    "dataset_pyramid_multiplier": 1.1,
    "physical_probe_evidence": [
        "平台 datafields 元数据把 133 字段一律标注 type=VECTOR；实测 ts_zscore(裸字段) 报 'does not support event inputs'，ts_zscore(vec_avg(字段)) 回测成功 -> 物理类型判定为 VECTOR 事件型，必须 vec_* 降维后方可参与运算。",
        "基准物理量 (alpha ZYQGwX9n): turnover=46.29% 偏高 -> 需 ts_decay_* / 更长平滑窗压制换手；longCount=373 / shortCount=337 -> 多空比 1.107，无零膨胀死重。",
        "全部 133 字段 alphaCount <= 2，数据集整体仅 135 个 alpha 使用，属平台极低拥挤度处女地。",
        "研究员存量 470 条 alpha (其中 70 条已提交 OS) 中 fnd90 使用数 = 0，ProdCorr 撞车风险极低。",
        "家族结构: fnd90_game_* (全球, 覆盖随字段变动 0.271~0.870) / fnd90_us_game_* (美国, 统一覆盖 0.828, 描述带 [Ascending]/[Descending] 与 [Quality.*] 方向标签) / fnd90_*qes_gamef_* (QES 法证综合分: Piotroski, Ohlson, Mohanram, C-Score, CHS 违约概率, icfroe, earn_var, cashflow_var) / 3 个独立表外索取权比率。",
    ],
    "fields": fields,
}

os.makedirs(os.path.dirname(KB_PATH), exist_ok=True)
with open(KB_PATH, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)

from collections import Counter
print("written:", KB_PATH)
print("role dist:", Counter(v["semantic_role"] for v in fields.values()))
print("sparse:", sum(1 for v in fields.values() if v["is_sparse"]))
