# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp_v2a_preflight import show, META
import stage3_preflight as P

CAND = [
 ("A_01 未解释应计",
  "power(subtract(multiply(0.5, group_rank(fnd89_jones_accrual_r2_other_11, sector)), group_rank(oth395_other_11_11, sector)), 3)",
  "以综合应计相对总资产的高位为坏，Jones 模型 R2 作为盈利质量修正项并给予 0.5 权重，对未解释应计做空。",
  "只按账面利润与现金流叙事买入而不分解应计来源的成长主题资金"),
 ("A_02 自身历史分位回归",
  "power(subtract(multiply(0.5, group_rank(fnd89_jones_accrual_r2_other_11, industry)), group_rank(oth395_best11_d1_current_t, industry)), 3)",
  "捕捉应计比率相对自身历史中枢的跃升幅度，并用 Jones 模型 R2 权重修正应计被解释的程度。",
  "把单季应计跳升当作盈利改善而追涨的业绩预期交易资金"),
 ("A_03 金融资产应计分解",
  "power(subtract(multiply(0.5, group_rank(fnd89_jones_nondiscretionary_accrual_other_11, sector)), group_rank(oth395_other_13_11, sector)), 3)",
  "以金融资产应计占总资产的高位为坏，非裁量应计水平为质量修正项，分离资产负债表驱动的应计。",
  "把金融资产应计当作经营改善而抬估值倍数的并购成长资金"),
 ("A_04 应计稳定性",
  "power(subtract(group_rank(fnd89_best11_d1_min, sector), group_rank(fnd89_best11_d1_max, sector)), 3)",
  "用应计比率历史最高值减历史最低值的价差衡量应计波动，高波动代表盈利质量差因而做空。",
  "偏好应计稳定但绝对水平一般的低波动资金"),
 ("A_05 资产扩张驱动",
  "group_zscore(subtract(group_rank(fnd89_jones_accrual_r2_other_11, sector), group_rank(oth395_asset_d1_asset_change, sector)), sector)",
  "以资产扩张比率为驱动源，与 Jones 模型 R2 的行业内结构做差，刻画扩张型资产负债表操纵。",
  "按资产扩张速度追逐产能成长故事而无视应计构成的扩张型资金"),
 ("A_06 group_zscore 幅度型",
  "subtract(group_zscore(fnd89_jones_accrual_r2_other_11, sector), group_zscore(oth395_other_11_11, sector))",
  "在行业内用连续标准分刻画 Jones 模型解释力与综合应计的落差，保留幅度信息以抬高信号离散度。",
  "以应计模型解释力与应计水平同时定价为口号的低频质量筛选资金"),
]
for tag, expr, mech, cp in CAND:
    show(tag, expr, mech, cp)
