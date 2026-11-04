# -*- coding: utf-8 -*-
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import stage3_preflight as P
import stage3_preflight_v2 as V2
META = V2.load_multids_meta(["fundamental89", "other395"])
SHORT = [
 "fnd89_jones_accrual_r2_other_11","fnd89_jones_accrual_r2_other_12","fnd89_jones_accrual_r2_other_13",
 "fnd89_jones_accrual_r2_major_11","fnd89_jones_accrual_r2_major_12","fnd89_jones_accrual_r2_major_13",
 "fnd89_jones_nondiscretionary_accrual_other_11","fnd89_jones_nondiscretionary_accrual_other_12",
 "fnd89_jones_nondiscretionary_accrual_other_13","fnd89_jones_nondiscretionary_accrual_major_11",
 "fnd89_jones_nondiscretionary_accrual_major_13",
 "fnd89_jones_accrual_pct_other_11","fnd89_jones_accrual_pct_other_12","fnd89_jones_accrual_pct_other_13",
 "fnd89_jones_accrual_pct_major_11","fnd89_jones_accrual_pct_major_13",
 "fnd89_best11_d1_current_t","fnd89_best11_d1_mean","fnd89_best11_d1_max","fnd89_best11_d1_min",
 "fnd89_best11_d1_dts","fnd89_best11_d1_accum_4q","fnd89_best11_d1_length",
 "fnd89_fixed1313_d1_current_t","fnd89_fixed1313_d1_mean","fnd89_fixed1313_d1_max","fnd89_fixed1313_d1_min",
 "fnd89_csjones_sector_other_11","fnd89_csjones_sector_other_12","fnd89_csjones_sector_other_13",
 "fnd89_csjones_sector_r2_other_11","fnd89_csjones_sector_r2_other_12","fnd89_csjones_sector_r2_other_13",
 "fnd89_csjones_industry_other_11","fnd89_csjones_industry_other_12","fnd89_csjones_industry_other_13",
 "fnd89_csjones_industry_r2_other_11","fnd89_csjones_industry_r2_other_12","fnd89_csjones_industry_r2_other_13",
 "fnd89_csjones_all_other_11","fnd89_csjones_all_other_12","fnd89_csjones_all_other_13",
 "fnd89_csjones_all_r2_other_11","fnd89_csjones_all_r2_other_12","fnd89_csjones_all_r2_other_13",
 "fnd89_major_11_11","fnd89_major_13_11","fnd89_major_12_11",
 "fnd89_other_11_11","fnd89_other_12_11","fnd89_other_13_11","fnd89_other_14_11","fnd89_other_15_11",
 "fnd89_asset_41_11","fnd89_asset_61_11","fnd89_asset_64_11",
 "fnd89_asset_d1_asset_change","fnd89_major_d1_asset_change","fnd89_other_d1_asset_change",
 "fnd89_best11_d1_asset_double_history","fnd89_best11_d1_asset_half_history",
 "oth395_jones_accrual_r2_other_11","oth395_jones_accrual_r2_major_11",
 "oth395_jones_nondiscretionary_accrual_other_11","oth395_jones_nondiscretionary_accrual_major_11",
 "oth395_jones_accrual_pct_other_11","oth395_jones_accrual_pct_major_11",
 "oth395_best11_d1_current_t","oth395_best11_d1_mean","oth395_best11_d1_max","oth395_best11_d1_min",
 "oth395_best11_d1_dts","oth395_best11_d1_accum_4q","oth395_best11_d1_length",
 "oth395_fixed1313_d1_current_t","oth395_fixed1313_d1_mean","oth395_fixed1313_d1_max","oth395_fixed1313_d1_min",
 "oth395_other_11_11","oth395_other_12_11","oth395_other_13_11","oth395_other_14_11","oth395_other_15_11",
 "oth395_asset_41_11","oth395_asset_61_11","oth395_asset_64_11",
 "oth395_asset_d1_asset_change","oth395_major_d1_asset_change","oth395_other_d1_asset_change",
 "oth395_csjones_sector_other_11","oth395_csjones_sector_other_12","oth395_csjones_sector_other_13",
 "oth395_csjones_industry_other_11","oth395_csjones_industry_other_12","oth395_csjones_industry_other_13",
 "oth395_csjones_all_other_11","oth395_csjones_all_other_12","oth395_csjones_all_other_13",
 "oth395_csjones_industry_r2_other_11","oth395_csjones_sector_r2_other_11",
]
print("%-48s %-10s %-7s %-4s %s" % ("FIELD","FAMILY","COV","AC","DESC"))
for f in SHORT:
    m = META.get(f)
    if not m:
        print("%-48s MISSING" % f); continue
    fam = P.unit_family(m.get("description",""))
    print("%-48s %-10s %.4f  %-4s %s" % (f, fam, m.get("coverage") or 0, m.get("alphaCount"), (m.get("description") or "").replace(chr(10),' ')[:92]))
