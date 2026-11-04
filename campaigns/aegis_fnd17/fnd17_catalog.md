# fundamental17 (USA / TOP1000 / delay 1) — Field Catalog

402 fields total; 289 usable (40 nominal FX/currency codes + 73 embedded price-volume are BANNED). 100% MATRIX type. Updated on quarterly/annual report cadence => naturally low turnover; a bare cross-sectional LEVEL on a static field is a value factor, not a signal.

Legend per field: `id | ac=<alphaCount> uc=<userCount> cov=<coverage> | <domain> | <sparse?> | <twin tag> | description`

- `ac` = platform alphaCount (how many platform alphas already use it). **ac<=5 is the anti-crowding target; ac=0 is virgin.**
- `cov` < 0.80 => sparse (many NaN) => needs `ts_backfill` or NaN handling.
- Twin tags: PTM=prior trailing 12M, Y1A=one year ago, PFY=prior fiscal year, PQ=prior quarter, PP=prior period, PM=prior month, P2/P3=prior 2nd/3rd period. **A current-period field + its twin is the dataset's crown jewel: it is a genuine second-order surprise vs the company's OWN history, and twins are usually ac=0~3.**
- Domains: `unbounded` = absolute amounts (sign follows accounting), `[-1,1]` = signed ratio (can be +/-), `[0,inf)` = non-negative ratio (leverage/turnover/coverage), `[-1,1]R` = ratio that may be positive-biased.

## accrual_quality  —  Q-Quality / Accrual (earnings quality, cash vs accrual)

- `fnd17_aniacnorm` | ac=0 uc=0 cov=0.936 | unbounded | - | - | Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year
- `fnd17_atmtt` | ac=0 uc=0 cov=0.908 | unbounded | - | - | Total assets, trailing twelve months
- `fnd17_atotce` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Common equity (book value) - most recent fiscal year
- `fnd17_cainq` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Net income available to common shareholders for the most recent quarter
- `fnd17_inq` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Net income (earnings after taxes) for the most recent quarter
- `fnd17_aniac` | ac=2 uc=2 cov=0.936 | unbounded | - | - | Net income available to common shareholders for the most recent fiscal year
- `fnd17_aniexclxor` | ac=2 uc=2 cov=0.936 | unbounded | - | - | Net income excluding extraordinary items for the most recent fiscal year
- `fnd17_aninorm` | ac=2 uc=1 cov=0.936 | unbounded | - | - | Net income after taxes excluding unusual or one-time items for the most recent fiscal year
- `fnd17_qtotce` | ac=2 uc=1 cov=0.937 | unbounded | - | - | Common equity (book value) - most recent quarter
- `fnd17_fcf1a` | ac=5 uc=4 cov=0.935 | unbounded | - | - | Free cash flow - most recent fiscal year
- `fnd17_rhsfcfq` | ac=5 uc=5 cov=0.916 | unbounded | - | - | Free cash flow per share for the most recent quarter, annualized
- `fnd17_rhsfcfmtt` | ac=6 uc=6 cov=0.904 | unbounded | - | - | Free cash flow per share over the trailing 12 months
- `fnd17_fcfq` | ac=7 uc=6 cov=0.922 | unbounded | - | - | Free cash flow for the most recent quarter
- `fnd17_aniacinclx` | ac=8 uc=1 cov=0.936 | unbounded | - | - | Net income available to common including extraordinary items for the most recent fiscal year
- `fnd17_ani` | ac=9 uc=2 cov=0.936 | unbounded | - | - | Net income (earnings after taxes) for the most recent fiscal year
- `fnd17_fcfmtt` | ac=10 uc=6 cov=0.910 | unbounded | - | - | Free cash flow - trailing 12 months
- `fnd17_ata` | ac=14 uc=4 cov=0.937 | unbounded | - | - | Total assets - most recent fiscal year

## profitability_roa_roe  —  Q-Profitability (ROA / ROE / margin)

- `fnd17_ptmroepct` | ac=0 uc=0 cov=0.830 | unbounded | - | PTM | Return on average equity for the prior trailing twelve months
- `fnd17_tcpaormtp` | ac=0 uc=0 cov=0.864 | unbounded | - | PTM | Return on average assets for the prior trailing twelve months
- `fnd17_aptmgnpct2` | ac=1 uc=1 cov=0.898 | [-1, 1] | - | - | Pretax Margin - 2nd historical fiscal year
- `fnd17_tcpngmpoa` | ac=1 uc=1 cov=0.901 | [-1, 1] | - | - | Operating margin - 1st historical fiscal year
- `fnd17_aroapct` | ac=2 uc=2 cov=0.931 | unbounded | - | - | Return on average assets for the most recent fiscal year
- `fnd17_qroipct` | ac=2 uc=2 cov=0.836 | unbounded | - | - | Return on investment for the most recent quarter (annualized)
- `fnd17_ry5ngmpo` | ac=2 uc=2 cov=0.791 | [-1, 1] | SP | - | Operating Margin - 5 year average
- `fnd17_tcpngmpna` | ac=2 uc=2 cov=0.903 | [-1, 1] | - | - | Net Profit Margin % - 1st historical fiscal year
- `fnd17_tcpngmpoq` | ac=2 uc=2 cov=0.900 | [-1, 1] | - | - | Operating margin - most recent quarter
- `fnd17_2tcpngmpoa` | ac=3 uc=3 cov=0.896 | [-1, 1] | - | - | Operating Margin - 2nd historical fiscal year
- `fnd17_aptmgnpct` | ac=3 uc=3 cov=0.903 | [-1, 1] | - | - | Pretax margin - 1st historical fiscal year
- `fnd17_ngmpnmtt` | ac=3 uc=3 cov=0.900 | [-1, 1] | - | - | Net Profit Margin % - trailing 12 month
- `fnd17_npmtrendgr` | ac=3 uc=2 cov=0.538 | [-1, 1] | SP | - | Five-year growth rate of net profit margin
- `fnd17_ttmgrosmgn` | ac=3 uc=2 cov=0.748 | [-1, 1] | SP | - | Gross margin over the trailing 12 months
- `fnd17_ttmopmgn` | ac=3 uc=3 cov=0.899 | [-1, 1] | - | - | Operating margin over the trailing 12 months
- `fnd17_ttmroepct` | ac=3 uc=2 cov=0.869 | unbounded | - | - | Return on average equity - trailing 12 month
- `fnd17_tcpaormtt` | ac=4 uc=3 cov=0.907 | unbounded | - | - | Return on average assets over the trailing 12 months (percentage)
- `fnd17_tcpaorq` | ac=4 uc=3 cov=0.932 | unbounded | - | - | Return on average assets for the most recent quarter (annualized)
- `fnd17_qroepct` | ac=5 uc=2 cov=0.889 | unbounded | - | - | Return on average equity for the most recent quarter (annualized)
- `fnd17_ttmroipct` | ac=5 uc=1 cov=0.813 | unbounded | - | - | Return on investment - trailing 12 month
- `fnd17_gmntrendgr` | ac=7 uc=3 cov=0.652 | [-1, 1] | SP | - | Five-year growth rate of gross margin
- `fnd17_qgrosmgn` | ac=7 uc=3 cov=0.750 | [-1, 1] | SP | - | Gross Margin - most recent quarter
- `fnd17_aroipct` | ac=8 uc=2 cov=0.835 | unbounded | - | - | Return on investment for the most recent fiscal year
- `fnd17_ngmpnmtp` | ac=8 uc=4 cov=0.883 | [-1, 1] | - | PTM | Net Profit Margin % - prior trailing 12 month
- `fnd17_a2netmrgn` | ac=12 uc=7 cov=0.898 | [-1, 1] | - | - | Net Profit Margin % - 2nd historical fiscal year

## efficiency_dupont  —  Q-Efficiency (turnover / DuPont drivers)

- `fnd17_qinvturn` | ac=0 uc=0 cov=0.518 | [0, inf) | SP | - | Inventory turnover - most recent quarter (annualized)
- `fnd17_qrecturn` | ac=0 uc=0 cov=0.774 | [0, inf) | SP | - | Receivables turnover - most recent quarter (annualized)
- `fnd17_ttmastturn` | ac=0 uc=0 cov=0.840 | [0, inf) | - | - | Asset turnover - trailing 12 months
- `fnd17_ttminvturn` | ac=0 uc=0 cov=0.507 | [0, inf) | SP | - | Inventory turnover - trailing 12 months
- `fnd17_ainvturn` | ac=1 uc=1 cov=0.525 | [0, inf) | SP | - | Inventory turnover - most recent fiscal year
- `fnd17_arecturn` | ac=1 uc=1 cov=0.781 | [0, inf) | SP | - | Receivables turnover - most recent fiscal year
- `fnd17_qastturn` | ac=3 uc=3 cov=0.863 | [0, inf) | - | - | Asset turnover ratio for the most recent quarter, annualized
- `fnd17_aastturn` | ac=6 uc=6 cov=0.863 | [0, inf) | - | - | Asset turnover - most recent fiscal year
- `fnd17_ttmrecturn` | ac=8 uc=1 cov=0.756 | [0, inf) | SP | - | Receivables turnover - trailing 12 months

## leverage_solvency  —  Q-Leverage & Solvency

- `fnd17_qtotd` | ac=0 uc=0 cov=0.936 | unbounded | - | - | Total debt - most recent quarter
- `fnd17_netdebt_a` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Net debt (total debt minus cash and equivalents) for the last fiscal year
- `fnd17_qe2dtlq` | ac=1 uc=1 cov=0.898 | [0, inf) | - | - | Long-term debt to shareholder equity ratio for the most recent quarter
- `fnd17_qtotd2eq` | ac=1 uc=1 cov=0.898 | [0, inf) | - | - | Total debt to shareholder equity ratio for the most recent quarter
- `fnd17_2qe2dtlq` | ac=2 uc=2 cov=0.872 | [0, inf) | - | Y1A | Long-term debt to equity ratio for the most recent quarter one year ago
- `fnd17_atotd` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Total debt - most recent fiscal year
- `fnd17_atotd2eq` | ac=2 uc=2 cov=0.896 | unbounded | - | - | Total debt to shareholders’ equity for the most recent fiscal year
- `fnd17_atotltd` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Long-term debt (total) - most recent fiscal year
- `fnd17_netdebt_i` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Net debt (total debt minus cash and equivalents) for the latest interim period
- `fnd17_qtotd2eq2` | ac=2 uc=1 cov=0.872 | [0, inf) | - | Y1A | Total debt to shareholder equity ratio for the most recent quarter, measured one year ago
- `fnd17_qtotd2ast` | ac=3 uc=2 cov=0.936 | unbounded | - | - | Total debt to total assets for the most recent quarter
- `fnd17_qtotd2cap` | ac=3 uc=1 cov=0.865 | [0, inf) | - | - | Ratio of total debt to total capital for the most recent quarter
- `fnd17_atotd2ast` | ac=4 uc=3 cov=0.937 | unbounded | - | - | Total debt to total assets for the most recent fiscal year
- `fnd17_atotd2cap` | ac=4 uc=2 cov=0.864 | unbounded | - | - | Total debt to total capital percentage, most recent fiscal year
- `fnd17_qtotltd` | ac=9 uc=1 cov=0.936 | unbounded | - | - | Long-term debt (total), most recent quarter

## liquidity_coverage  —  Q-Liquidity & Coverage

- `fnd17_aquickrati` | ac=0 uc=0 cov=0.517 | [0, inf) | SP | - | Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities
- `fnd17_ptmintcov` | ac=0 uc=0 cov=0.641 | [0, inf) | SP | PTM | Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense
- `fnd17_qquickrat2` | ac=0 uc=0 cov=0.499 | [0, inf) | SP | Y1A | Quick ratio for the most recent quarter one year ago
- `fnd17_qcurratio2` | ac=1 uc=1 cov=0.719 | [0, inf) | SP | Y1A | Current ratio - most recent quarter, 1 year ago
- `fnd17_ttmintcov` | ac=1 uc=1 cov=0.649 | [0, inf) | SP | - | Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months
- `fnd17_qcurratio` | ac=2 uc=2 cov=0.745 | [0, inf) | SP | - | Current ratio for the most recent quarter
- `fnd17_qquickrati` | ac=2 uc=2 cov=0.512 | [0, inf) | SP | - | Quick ratio for the most recent quarter
- `fnd17_aintcov` | ac=3 uc=3 cov=0.620 | [0, inf) | SP | - | Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense
- `fnd17_acurratio` | ac=5 uc=5 cov=0.745 | [0, inf) | SP | - | Current ratio for the most recent fiscal year (current assets divided by current liabilities)
- `fnd17_qcash` | ac=5 uc=5 cov=0.936 | unbounded | - | - | Cash and cash equivalents for the most recent quarter
- `fnd17_hsca` | ac=6 uc=3 cov=0.936 | unbounded | - | - | Cash and cash equivalents at fiscal year-end
- `fnd17_voctniq` | ac=8 uc=3 cov=0.667 | [0, inf) | SP | - | Interest coverage ratio for the most recent quarter
- `fnd17_sphsca` | ac=13 uc=6 cov=0.935 | unbounded | - | - | Cash per share - most recent fiscal year
- `fnd17_sphscq` | ac=14 uc=6 cov=0.935 | unbounded | - | - | Cash and equivalents per share for the most recent quarter

## growth_surprise  —  Q-Growth & Surprise

- `fnd17_ghcspemtt` | ac=0 uc=0 cov=0.906 | [-1, 1] | - | PTM | Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period
- `fnd17_nichngin` | ac=0 uc=0 cov=0.931 | [-1, 1] | - | PQ | Percent change in net income versus the prior quarter
- `fnd17_nichngyr` | ac=0 uc=0 cov=0.927 | [-1, 1] | - | Y1A | Percent change in net income for the most recent quarter versus the same quarter a year ago
- `fnd17_qrev` | ac=0 uc=0 cov=0.937 | unbounded | - | - | Revenue for the most recent quarter
- `fnd17_qrevps` | ac=0 uc=0 cov=0.937 | unbounded | - | - | Revenue/share - most recent quarter (annualized)
- `fnd17_ttmnichg` | ac=0 uc=0 cov=0.906 | [-1, 1] | - | - | Percent change in trailing 12-month net income versus the prior TTM
- `fnd17_ttmrev` | ac=0 uc=0 cov=0.929 | unbounded | - | - | Revenue over the trailing 12 months; units: millions
- `fnd17_epschngyri` | ac=1 uc=1 cov=0.964 | [0, inf) | - | - | EPS Change % - year to date
- `fnd17_revgrpct` | ac=1 uc=1 cov=0.852 | [-1, 1] | - | - | Three-year revenue growth rate (percent)
- `fnd17_revps5ygr` | ac=1 uc=1 cov=0.782 | [-1, 1] | SP | - | Five-year growth rate of revenue per share
- `fnd17_arev` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Total revenue (sales) for the most recent fiscal year
- `fnd17_arevps` | ac=2 uc=2 cov=0.936 | unbounded | - | - | Revenue per share for the most recent fiscal year
- `fnd17_ghcspea` | ac=2 uc=1 cov=0.928 | [-1, 1] | - | - | Year-over-year percent change in annual earnings per share compared to the previous fiscal year
- `fnd17_qrevpsna` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Revenue/share - most recent quarter (not annualized)
- `fnd17_revtrendgr` | ac=2 uc=2 cov=0.783 | [-1, 1] | SP | - | Five-year revenue growth rate
- `fnd17_rygnhcspe` | ac=2 uc=2 cov=0.926 | [-1, 1] | - | - | Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year
- `fnd17_ptmrev` | ac=3 uc=1 cov=0.909 | unbounded | - | PTM | Revenue for the prior trailing twelve months
- `fnd17_revchngin` | ac=3 uc=3 cov=0.897 | [-1, 1] | - | - | Percentage change in revenue versus the immediately preceding quarter
- `fnd17_revchngyr` | ac=3 uc=3 cov=0.893 | [-1, 1] | - | Y1A | Percent change in revenue for the most recent quarter versus the same quarter a year ago
- `fnd17_revtrend10` | ac=3 uc=3 cov=0.648 | [-1, 1] | SP | - | Ten-year revenue growth rate
- `fnd17_ttmrevps` | ac=4 uc=3 cov=0.929 | unbounded | - | - | Revenue/share - trailing 12 month
- `fnd17_epschngin` | ac=6 uc=5 cov=0.931 | [-1, 1] | - | PQ | Percent change in EPS from the prior quarter

## share_count_dilution  —  Q-Share Count & Dilution

- `fnd17_mtpbshs` | ac=1 uc=1 cov=0.909 | unbounded | - | PTM | Shares outstanding basic, average prior trailing 12 months
- `fnd17_mtpshs` | ac=1 uc=1 cov=0.909 | unbounded | - | PTM | Shares outstanding, average prior trailing 12 months
- `fnd17_mttshs` | ac=1 uc=1 cov=0.929 | unbounded | - | - | Shares outstanding - average trailing 12 month
- `fnd17_shboutavgq` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Shares outstanding basic, average, most recent quarter
- `fnd17_shsoutavgq` | ac=1 uc=1 cov=0.937 | unbounded | - | - | Shares outstanding, average, most recent quarter
- `fnd17_float` | ac=2 uc=2 cov=0.937 | unbounded | - | - | Public float (shares available for trading)
- `fnd17_mttbshs` | ac=2 uc=2 cov=0.929 | unbounded | - | - | Shares outstanding basic, average trailing 12 months
- `fnd17_shsboutavg` | ac=2 uc=2 cov=0.936 | unbounded | - | - | Shares outstanding Basic - average, most recent fiscal year
- `fnd17_shsoutbs` | ac=3 uc=3 cov=0.936 | unbounded | - | - | Shares outstanding on the balance sheet, most recent quarter
- `fnd17_shsout` | ac=4 uc=3 cov=0.939 | unbounded | - | - | Shares outstanding, current
- `fnd17_shsoutavg` | ac=5 uc=2 cov=0.936 | unbounded | - | - | Shares outstanding - average, most recent fiscal year
- `fnd17_shsoutbs2` | ac=6 uc=1 cov=0.908 | unbounded | - | Y1A | Shares outstanding on the balance sheet, most recent quarter one year ago

## cost_intensity_rd  —  Q-Cost Intensity & R&D

- `fnd17_ttmcogs` | ac=0 uc=0 cov=0.751 | unbounded | SP | - | Cost of goods sold over the trailing 12 months
- `fnd17_ttmintexp` | ac=0 uc=0 cov=0.677 | unbounded | SP | - | Interest expense over the trailing 12 months
- `fnd17_aintexpz` | ac=1 uc=1 cov=0.719 | unbounded | SP | - | Total interest expense for the most recent fiscal year
- `fnd17_pxedrmtt` | ac=1 uc=1 cov=0.359 | unbounded | SP | - | Research and development expense over the trailing 12 months; units: millions
- `fnd17_pxedrq` | ac=1 uc=1 cov=0.361 | unbounded | SP | - | Research and development expense for the most recent quarter
- `fnd17_qcogs` | ac=1 uc=1 cov=0.754 | unbounded | SP | - | Cost of goods sold for the most recent quarter
- `fnd17_ttmtaxrate` | ac=1 uc=1 cov=0.663 | [0, inf) | SP | - | Tax rate - trailing 12 month
- `fnd17_zpxetniq` | ac=1 uc=1 cov=0.664 | unbounded | SP | - | Total interest expense for the most recent quarter
- `fnd17_ataxrate` | ac=4 uc=3 cov=0.657 | [-1, 1] | SP | - | Effective tax rate for the most recent fiscal year
- `fnd17_ttmsga2rev` | ac=4 uc=1 cov=0.794 | unbounded | SP | - | SG&A expenses / net sales - trailing 12 month
- `fnd17_asga2rev` | ac=8 uc=5 cov=0.803 | unbounded | - | - | SG&A expenses / net sales - most recent fiscal year
- `fnd17_qsga2rev` | ac=11 uc=5 cov=0.794 | unbounded | SP | - | SG&A expenses / net sales - most recent quarter
- `fnd17_pxedrmtp` | ac=20 uc=8 cov=0.349 | unbounded | SP | PTM | Research and development expense for the prior trailing twelve months
- `fnd17_acogs` | ac=22 uc=4 cov=0.754 | unbounded | SP | - | Cost of goods sold for the most recent fiscal year
- `fnd17_pxedra` | ac=22 uc=7 cov=0.388 | unbounded | SP | - | Research and development expense for the most recent fiscal year

## uncertainty_scale  —  Q-Uncertainty / Scale (weights & gates, NOT standalone direction)

- `fnd17_beta_down` | ac=0 uc=0 cov=0.842 | unbounded | - | - | Downside beta calculated during down-market periods
- `fnd17_dai` | ac=0 uc=0 cov=0.485 | [0, inf) | SP | - | Dividend rate, indicated annual
- `fnd17_div` | ac=0 uc=0 cov=0.528 | unbounded | SP | - | Dividends paid from the statement of cash flows - most recent fiscal year
- `fnd17_spdq` | ac=0 uc=0 cov=0.927 | [0, inf) | - | - | Dividend - most recent quarter
- `fnd17_ttmdivshr` | ac=0 uc=0 cov=0.929 | unbounded | - | - | Dividends per share - trailing 12 months
- `fnd17_adivshr` | ac=1 uc=1 cov=0.577 | unbounded | SP | - | Dividend per share - most recent fiscal year
- `fnd17_divnq` | ac=1 uc=1 cov=0.493 | [0, inf) | SP | - | Dividend - next quarterly declared
- `fnd17_ttmpayrat` | ac=1 uc=1 cov=0.675 | [-1, 1] | SP | - | Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings
- `fnd17_beta` | ac=3 uc=3 cov=0.794 | unbounded | SP | - | Beta
- `fnd17_qtrperiods` | ac=3 uc=2 cov=0.938 | unbounded | - | - | Number of historical quarterly periods available for the company
- `fnd17_annperiods` | ac=4 uc=4 cov=0.938 | unbounded | - | - | Number of historical periods - Annual
- `fnd17_gvay5dly` | ac=4 uc=1 cov=0.438 | [0, inf) | SP | - | Dividend yield - 5 year average
- `fnd17_apayratio2` | ac=6 uc=1 cov=0.652 | [0, inf) | SP | PFY | Payout ratio for the prior fiscal year
- `fnd17_beta_up` | ac=14 uc=2 cov=0.887 | unbounded | - | - | Upside beta calculated during up-market periods

## TWIN PAIRS (current vs own-history baseline) — the anti-crowding core

These are verified present in fundamental17_raw_full.json. Each pair is a genuine second-order expectation gap (current reading vs the SAME company one period earlier), which satisfies anti-crowding law without any price data.

- `fnd17_tcpaormtt` (ac=4) vs `fnd17_tcpaormtp` (ac=0) — TTM return on average assets: now vs prior TTM
- `fnd17_ngmpnmtt` (ac=3) vs `fnd17_ngmpnmtp` (ac=8) — TTM net profit margin: now vs prior TTM
- `fnd17_qtotd2eq` (ac=1) vs `fnd17_qtotd2eq2` (ac=2) — Total debt/equity: now vs one year ago
- `fnd17_qcurratio` (ac=2) vs `fnd17_qcurratio2` (ac=1) — Current ratio: now vs one year ago
- `fnd17_ttmintcov` (ac=1) vs `fnd17_ptmintcov` (ac=0) — Interest coverage: now vs prior TTM
- `fnd17_shsoutbs` (ac=3) vs `fnd17_shsoutbs2` (ac=6) — Balance-sheet shares outstanding: now vs 1yr ago
- `fnd17_ttmrev` (ac=0) vs `fnd17_ptmrev` (ac=3) — TTM revenue: now vs prior TTM

## BANNED FIELD CLASSES (never use)

- Nominal FX / currency codes (40): any `*currency_code*`, `*exrate*`.
- Embedded price-volume (73): `fnd17_nprice`, `fnd17_mktcap`, `fnd17_ev_cur`, `fnd17_pr1dayprc`, `fnd17_vol*`, `fnd17_priceavg*`, `fnd17_*price2bk*`, `fnd17_*peexclxor*`, `fnd17_*spfcr*`, `fnd17_ebitda2ev*`, `fnd17_awcappspr`, `fnd17_qwcappspr`, `fnd17_yield`, `fnd17_*pr*2rev*`.
- Any external PV field: close / open / high / low / vwap / returns / volume / cap / adv20.
