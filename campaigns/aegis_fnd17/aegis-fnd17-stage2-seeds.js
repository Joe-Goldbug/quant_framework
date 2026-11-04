export const meta = {
  name: 'aegis-fnd17-stage2-seeds',
  description: 'AEGIS fundamental17 cold-start: Phase-0 seed synthesis, tech audit, red-team double-blind audit (zero backtest quota)',
  phases: [
    { title: 'SeedSynthesis', detail: '8 orthogonal seed prototypes from the 8-question framework' },
    { title: 'TechAudit', detail: 'field truth / zero-PV / FastExpr syntax / axiom compliance' },
    { title: 'RedTeam', detail: 'double-blind causal + AST-fidelity judgement' },
  ],
}

// ---- 路径常量（必须是独立顶层 const；上一版把它们塞进 CTX 模板串导致
//      SHORTLIST is not defined，8 个 agent 秒退）----
const CTX_PATH = "D:\\python\\Lib\\site-packages\\cnhkmcp\\untracked\\APP\\.agents\\quant_framework\\campaigns\\aegis_fnd17\\CAMPAIGN_CONTEXT.md"
const BASE_DIR = "D:\\python\\Lib\\site-packages\\cnhkmcp\\untracked\\APP\\.agents\\quant_framework\\campaigns\\aegis_fnd17"

// ---- 内联字段元数据（Workflow 沙箱无文件系统访问）----
const FIELD_TABLE = {"fnd17_ani":{"ac":9,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Net income (earnings after taxes) for the most recent fiscal year"},"fnd17_aniac":{"ac":2,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Net income available to common shareholders for the most recent fiscal year"},"fnd17_cainq":{"ac":1,"uc":1,"cov":0.9373,"dom":"unbounded","sp":false,"desc":"Net income available to common shareholders for the most recent quarter"},"fnd17_inq":{"ac":1,"uc":1,"cov":0.9373,"dom":"unbounded","sp":false,"desc":"Net income (earnings after taxes) for the most recent quarter"},"fnd17_aniacnorm":{"ac":0,"uc":0,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year"},"fnd17_aninorm":{"ac":2,"uc":1,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Net income after taxes excluding unusual or one-time items for the most recent fiscal year"},"fnd17_aniexclxor":{"ac":2,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Net income excluding extraordinary items for the most recent fiscal year"},"fnd17_aniacinclx":{"ac":8,"uc":1,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Net income available to common including extraordinary items for the most recent fiscal year"},"fnd17_fcfmtt":{"ac":10,"uc":6,"cov":0.9102,"dom":"unbounded","sp":false,"desc":"Free cash flow - trailing 12 months"},"fnd17_fcfq":{"ac":7,"uc":6,"cov":0.9216,"dom":"unbounded","sp":false,"desc":"Free cash flow for the most recent quarter"},"fnd17_fcf1a":{"ac":5,"uc":4,"cov":0.9353,"dom":"unbounded","sp":false,"desc":"Free cash flow - most recent fiscal year"},"fnd17_rhsfcfmtt":{"ac":6,"uc":6,"cov":0.9045,"dom":"unbounded","sp":false,"desc":"Free cash flow per share over the trailing 12 months"},"fnd17_rhsfcfq":{"ac":5,"uc":5,"cov":0.9159,"dom":"unbounded","sp":false,"desc":"Free cash flow per share for the most recent quarter, annualized"},"fnd17_ata":{"ac":14,"uc":4,"cov":0.9372,"dom":"unbounded","sp":false,"desc":"Total assets - most recent fiscal year"},"fnd17_atmtt":{"ac":0,"uc":0,"cov":0.9083,"dom":"unbounded","sp":false,"desc":"Total assets, trailing twelve months"},"fnd17_atotce":{"ac":1,"uc":1,"cov":0.9372,"dom":"unbounded","sp":false,"desc":"Common equity (book value) - most recent fiscal year"},"fnd17_qtotce":{"ac":2,"uc":1,"cov":0.9366,"dom":"unbounded","sp":false,"desc":"Common equity (book value) - most recent quarter"},"fnd17_tcpaorq":{"ac":4,"uc":3,"cov":0.9316,"dom":"unbounded","sp":false,"desc":"Return on average assets for the most recent quarter (annualized)"},"fnd17_tcpaormtt":{"ac":4,"uc":3,"cov":0.9072,"dom":"unbounded","sp":false,"desc":"Return on average assets over the trailing 12 months (percentage)"},"fnd17_tcpaormtp":{"ac":0,"uc":0,"cov":0.8638,"dom":"unbounded","sp":false,"desc":"Return on average assets for the prior trailing twelve months"},"fnd17_aroapct":{"ac":2,"uc":2,"cov":0.9313,"dom":"unbounded","sp":false,"desc":"Return on average assets for the most recent fiscal year"},"fnd17_qroipct":{"ac":2,"uc":2,"cov":0.8364,"dom":"unbounded","sp":false,"desc":"Return on investment for the most recent quarter (annualized)"},"fnd17_aroipct":{"ac":8,"uc":2,"cov":0.8348,"dom":"unbounded","sp":false,"desc":"Return on investment for the most recent fiscal year"},"fnd17_ttmroipct":{"ac":5,"uc":1,"cov":0.8134,"dom":"unbounded","sp":false,"desc":"Return on investment - trailing 12 month"},"fnd17_qroepct":{"ac":5,"uc":2,"cov":0.8892,"dom":"unbounded","sp":false,"desc":"Return on average equity for the most recent quarter (annualized)"},"fnd17_ttmroepct":{"ac":3,"uc":2,"cov":0.8693,"dom":"unbounded","sp":false,"desc":"Return on average equity - trailing 12 month"},"fnd17_ptmroepct":{"ac":0,"uc":0,"cov":0.8297,"dom":"unbounded","sp":false,"desc":"Return on average equity for the prior trailing twelve months"},"fnd17_ttmopmgn":{"ac":3,"uc":3,"cov":0.8993,"dom":"[-1, 1]","sp":false,"desc":"Operating margin over the trailing 12 months"},"fnd17_tcpngmpoq":{"ac":2,"uc":2,"cov":0.9004,"dom":"[-1, 1]","sp":false,"desc":"Operating margin - most recent quarter"},"fnd17_tcpngmpoa":{"ac":1,"uc":1,"cov":0.901,"dom":"[-1, 1]","sp":false,"desc":"Operating margin - 1st historical fiscal year"},"fnd17_2tcpngmpoa":{"ac":3,"uc":3,"cov":0.8957,"dom":"[-1, 1]","sp":false,"desc":"Operating Margin - 2nd historical fiscal year"},"fnd17_ry5ngmpo":{"ac":2,"uc":2,"cov":0.791,"dom":"[-1, 1]","sp":true,"desc":"Operating Margin - 5 year average"},"fnd17_qgrosmgn":{"ac":7,"uc":3,"cov":0.7501,"dom":"[-1, 1]","sp":true,"desc":"Gross Margin - most recent quarter"},"fnd17_ttmgrosmgn":{"ac":3,"uc":2,"cov":0.748,"dom":"[-1, 1]","sp":true,"desc":"Gross margin over the trailing 12 months"},"fnd17_gmntrendgr":{"ac":7,"uc":3,"cov":0.6518,"dom":"[-1, 1]","sp":true,"desc":"Five-year growth rate of gross margin"},"fnd17_npmtrendgr":{"ac":3,"uc":2,"cov":0.5376,"dom":"[-1, 1]","sp":true,"desc":"Five-year growth rate of net profit margin"},"fnd17_ngmpnmtt":{"ac":3,"uc":3,"cov":0.9003,"dom":"[-1, 1]","sp":false,"desc":"Net Profit Margin % - trailing 12 month"},"fnd17_ngmpnmtp":{"ac":8,"uc":4,"cov":0.8831,"dom":"[-1, 1]","sp":false,"desc":"Net Profit Margin % - prior trailing 12 month"},"fnd17_aptmgnpct":{"ac":3,"uc":3,"cov":0.903,"dom":"[-1, 1]","sp":false,"desc":"Pretax margin - 1st historical fiscal year"},"fnd17_aptmgnpct2":{"ac":1,"uc":1,"cov":0.8976,"dom":"[-1, 1]","sp":false,"desc":"Pretax Margin - 2nd historical fiscal year"},"fnd17_tcpngmpna":{"ac":2,"uc":2,"cov":0.903,"dom":"[-1, 1]","sp":false,"desc":"Net Profit Margin % - 1st historical fiscal year"},"fnd17_a2netmrgn":{"ac":12,"uc":7,"cov":0.8976,"dom":"[-1, 1]","sp":false,"desc":"Net Profit Margin % - 2nd historical fiscal year"},"fnd17_qastturn":{"ac":3,"uc":3,"cov":0.8633,"dom":"[0, inf)","sp":false,"desc":"Asset turnover ratio for the most recent quarter, annualized"},"fnd17_ttmastturn":{"ac":0,"uc":0,"cov":0.8396,"dom":"[0, inf)","sp":false,"desc":"Asset turnover - trailing 12 months"},"fnd17_aastturn":{"ac":6,"uc":6,"cov":0.8626,"dom":"[0, inf)","sp":false,"desc":"Asset turnover - most recent fiscal year"},"fnd17_ainvturn":{"ac":1,"uc":1,"cov":0.5246,"dom":"[0, inf)","sp":true,"desc":"Inventory turnover - most recent fiscal year"},"fnd17_qinvturn":{"ac":0,"uc":0,"cov":0.518,"dom":"[0, inf)","sp":true,"desc":"Inventory turnover - most recent quarter (annualized)"},"fnd17_ttminvturn":{"ac":0,"uc":0,"cov":0.5071,"dom":"[0, inf)","sp":true,"desc":"Inventory turnover - trailing 12 months"},"fnd17_arecturn":{"ac":1,"uc":1,"cov":0.7807,"dom":"[0, inf)","sp":true,"desc":"Receivables turnover - most recent fiscal year"},"fnd17_qrecturn":{"ac":0,"uc":0,"cov":0.774,"dom":"[0, inf)","sp":true,"desc":"Receivables turnover - most recent quarter (annualized)"},"fnd17_ttmrecturn":{"ac":8,"uc":1,"cov":0.7561,"dom":"[0, inf)","sp":true,"desc":"Receivables turnover - trailing 12 months"},"fnd17_qtotd2eq":{"ac":1,"uc":1,"cov":0.8982,"dom":"[0, inf)","sp":false,"desc":"Total debt to shareholder equity ratio for the most recent quarter"},"fnd17_qtotd2eq2":{"ac":2,"uc":1,"cov":0.8722,"dom":"[0, inf)","sp":false,"desc":"Total debt to shareholder equity ratio for the most recent quarter, measured one year ago"},"fnd17_atotd2eq":{"ac":2,"uc":2,"cov":0.8965,"dom":"unbounded","sp":false,"desc":"Total debt to shareholders\u2019 equity for the most recent fiscal year"},"fnd17_2qe2dtlq":{"ac":2,"uc":2,"cov":0.8721,"dom":"[0, inf)","sp":false,"desc":"Long-term debt to equity ratio for the most recent quarter one year ago"},"fnd17_qe2dtlq":{"ac":1,"uc":1,"cov":0.8978,"dom":"[0, inf)","sp":false,"desc":"Long-term debt to shareholder equity ratio for the most recent quarter"},"fnd17_qtotd2ast":{"ac":3,"uc":2,"cov":0.936,"dom":"unbounded","sp":false,"desc":"Total debt to total assets for the most recent quarter"},"fnd17_atotd2ast":{"ac":4,"uc":3,"cov":0.937,"dom":"unbounded","sp":false,"desc":"Total debt to total assets for the most recent fiscal year"},"fnd17_atotd":{"ac":2,"uc":2,"cov":0.9371,"dom":"unbounded","sp":false,"desc":"Total debt - most recent fiscal year"},"fnd17_atotltd":{"ac":2,"uc":2,"cov":0.9371,"dom":"unbounded","sp":false,"desc":"Long-term debt (total) - most recent fiscal year"},"fnd17_qtotd":{"ac":0,"uc":0,"cov":0.936,"dom":"unbounded","sp":false,"desc":"Total debt - most recent quarter"},"fnd17_qtotltd":{"ac":9,"uc":1,"cov":0.9357,"dom":"unbounded","sp":false,"desc":"Long-term debt (total), most recent quarter"},"fnd17_netdebt_a":{"ac":1,"uc":1,"cov":0.9373,"dom":"unbounded","sp":false,"desc":"Net debt (total debt minus cash and equivalents) for the last fiscal year"},"fnd17_netdebt_i":{"ac":2,"uc":2,"cov":0.9367,"dom":"unbounded","sp":false,"desc":"Net debt (total debt minus cash and equivalents) for the latest interim period"},"fnd17_qtotd2cap":{"ac":3,"uc":1,"cov":0.8646,"dom":"[0, inf)","sp":false,"desc":"Ratio of total debt to total capital for the most recent quarter"},"fnd17_atotd2cap":{"ac":4,"uc":2,"cov":0.8641,"dom":"unbounded","sp":false,"desc":"Total debt to total capital percentage, most recent fiscal year"},"fnd17_acurratio":{"ac":5,"uc":5,"cov":0.7448,"dom":"[0, inf)","sp":true,"desc":"Current ratio for the most recent fiscal year (current assets divided by current liabilities)"},"fnd17_qcurratio":{"ac":2,"uc":2,"cov":0.7445,"dom":"[0, inf)","sp":true,"desc":"Current ratio for the most recent quarter"},"fnd17_qcurratio2":{"ac":1,"uc":1,"cov":0.7187,"dom":"[0, inf)","sp":true,"desc":"Current ratio - most recent quarter, 1 year ago"},"fnd17_aquickrati":{"ac":0,"uc":0,"cov":0.5167,"dom":"[0, inf)","sp":true,"desc":"Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities"},"fnd17_qquickrati":{"ac":2,"uc":2,"cov":0.5116,"dom":"[0, inf)","sp":true,"desc":"Quick ratio for the most recent quarter"},"fnd17_qquickrat2":{"ac":0,"uc":0,"cov":0.4989,"dom":"[0, inf)","sp":true,"desc":"Quick ratio for the most recent quarter one year ago"},"fnd17_aintcov":{"ac":3,"uc":3,"cov":0.6199,"dom":"[0, inf)","sp":true,"desc":"Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense"},"fnd17_ttmintcov":{"ac":1,"uc":1,"cov":0.6489,"dom":"[0, inf)","sp":true,"desc":"Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months"},"fnd17_ptmintcov":{"ac":0,"uc":0,"cov":0.6415,"dom":"[0, inf)","sp":true,"desc":"Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense"},"fnd17_voctniq":{"ac":8,"uc":3,"cov":0.6673,"dom":"[0, inf)","sp":true,"desc":"Interest coverage ratio for the most recent quarter"},"fnd17_hsca":{"ac":6,"uc":3,"cov":0.9357,"dom":"unbounded","sp":false,"desc":"Cash and cash equivalents at fiscal year-end"},"fnd17_qcash":{"ac":5,"uc":5,"cov":0.9357,"dom":"unbounded","sp":false,"desc":"Cash and cash equivalents for the most recent quarter"},"fnd17_sphsca":{"ac":13,"uc":6,"cov":0.9351,"dom":"unbounded","sp":false,"desc":"Cash per share - most recent fiscal year"},"fnd17_sphscq":{"ac":14,"uc":6,"cov":0.935,"dom":"unbounded","sp":false,"desc":"Cash and equivalents per share for the most recent quarter"},"fnd17_qrev":{"ac":0,"uc":0,"cov":0.9371,"dom":"unbounded","sp":false,"desc":"Revenue for the most recent quarter"},"fnd17_ttmrev":{"ac":0,"uc":0,"cov":0.9291,"dom":"unbounded","sp":false,"desc":"Revenue over the trailing 12 months; units: millions"},"fnd17_arev":{"ac":2,"uc":2,"cov":0.9371,"dom":"unbounded","sp":false,"desc":"Total revenue (sales) for the most recent fiscal year"},"fnd17_ptmrev":{"ac":3,"uc":1,"cov":0.9094,"dom":"unbounded","sp":false,"desc":"Revenue for the prior trailing twelve months"},"fnd17_qrevps":{"ac":0,"uc":0,"cov":0.937,"dom":"unbounded","sp":false,"desc":"Revenue/share - most recent quarter (annualized)"},"fnd17_ttmrevps":{"ac":4,"uc":3,"cov":0.929,"dom":"unbounded","sp":false,"desc":"Revenue/share - trailing 12 month"},"fnd17_arevps":{"ac":2,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Revenue per share for the most recent fiscal year"},"fnd17_revgrpct":{"ac":1,"uc":1,"cov":0.8517,"dom":"[-1, 1]","sp":false,"desc":"Three-year revenue growth rate (percent)"},"fnd17_revtrendgr":{"ac":2,"uc":2,"cov":0.7834,"dom":"[-1, 1]","sp":true,"desc":"Five-year revenue growth rate"},"fnd17_revtrend10":{"ac":3,"uc":3,"cov":0.6482,"dom":"[-1, 1]","sp":true,"desc":"Ten-year revenue growth rate"},"fnd17_revps5ygr":{"ac":1,"uc":1,"cov":0.7825,"dom":"[-1, 1]","sp":true,"desc":"Five-year growth rate of revenue per share"},"fnd17_revchngin":{"ac":3,"uc":3,"cov":0.8974,"dom":"[-1, 1]","sp":false,"desc":"Percentage change in revenue versus the immediately preceding quarter"},"fnd17_revchngyr":{"ac":3,"uc":3,"cov":0.8931,"dom":"[-1, 1]","sp":false,"desc":"Percent change in revenue for the most recent quarter versus the same quarter a year ago"},"fnd17_nichngyr":{"ac":0,"uc":0,"cov":0.9266,"dom":"[-1, 1]","sp":false,"desc":"Percent change in net income for the most recent quarter versus the same quarter a year ago"},"fnd17_nichngin":{"ac":0,"uc":0,"cov":0.9307,"dom":"[-1, 1]","sp":false,"desc":"Percent change in net income versus the prior quarter"},"fnd17_ttmnichg":{"ac":0,"uc":0,"cov":0.9059,"dom":"[-1, 1]","sp":false,"desc":"Percent change in trailing 12-month net income versus the prior TTM"},"fnd17_rygnhcspe":{"ac":2,"uc":2,"cov":0.9264,"dom":"[-1, 1]","sp":false,"desc":"Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year"},"fnd17_epschngin":{"ac":6,"uc":5,"cov":0.9307,"dom":"[-1, 1]","sp":false,"desc":"Percent change in EPS from the prior quarter"},"fnd17_epschngyri":{"ac":1,"uc":1,"cov":0.9644,"dom":"[0, inf)","sp":false,"desc":"EPS Change % - year to date"},"fnd17_ghcspea":{"ac":2,"uc":1,"cov":0.9285,"dom":"[-1, 1]","sp":false,"desc":"Year-over-year percent change in annual earnings per share compared to the previous fiscal year"},"fnd17_ghcspemtt":{"ac":0,"uc":0,"cov":0.9059,"dom":"[-1, 1]","sp":false,"desc":"Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period"},"fnd17_qrevpsna":{"ac":2,"uc":2,"cov":0.937,"dom":"unbounded","sp":false,"desc":"Revenue/share - most recent quarter (not annualized)"},"fnd17_shsout":{"ac":4,"uc":3,"cov":0.9385,"dom":"unbounded","sp":false,"desc":"Shares outstanding, current"},"fnd17_shsoutbs":{"ac":3,"uc":3,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Shares outstanding on the balance sheet, most recent quarter"},"fnd17_shsoutbs2":{"ac":6,"uc":1,"cov":0.9082,"dom":"unbounded","sp":false,"desc":"Shares outstanding on the balance sheet, most recent quarter one year ago"},"fnd17_shsoutavg":{"ac":5,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Shares outstanding - average, most recent fiscal year"},"fnd17_shsoutavgq":{"ac":1,"uc":1,"cov":0.9373,"dom":"unbounded","sp":false,"desc":"Shares outstanding, average, most recent quarter"},"fnd17_shsboutavg":{"ac":2,"uc":2,"cov":0.9361,"dom":"unbounded","sp":false,"desc":"Shares outstanding Basic - average, most recent fiscal year"},"fnd17_shboutavgq":{"ac":1,"uc":1,"cov":0.9373,"dom":"unbounded","sp":false,"desc":"Shares outstanding basic, average, most recent quarter"},"fnd17_mtpbshs":{"ac":1,"uc":1,"cov":0.9092,"dom":"unbounded","sp":false,"desc":"Shares outstanding basic, average prior trailing 12 months"},"fnd17_mtpshs":{"ac":1,"uc":1,"cov":0.9092,"dom":"unbounded","sp":false,"desc":"Shares outstanding, average prior trailing 12 months"},"fnd17_mttbshs":{"ac":2,"uc":2,"cov":0.9291,"dom":"unbounded","sp":false,"desc":"Shares outstanding basic, average trailing 12 months"},"fnd17_mttshs":{"ac":1,"uc":1,"cov":0.9291,"dom":"unbounded","sp":false,"desc":"Shares outstanding - average trailing 12 month"},"fnd17_float":{"ac":2,"uc":2,"cov":0.9372,"dom":"unbounded","sp":false,"desc":"Public float (shares available for trading)"},"fnd17_acogs":{"ac":22,"uc":4,"cov":0.754,"dom":"unbounded","sp":true,"desc":"Cost of goods sold for the most recent fiscal year"},"fnd17_ttmcogs":{"ac":0,"uc":0,"cov":0.7509,"dom":"unbounded","sp":true,"desc":"Cost of goods sold over the trailing 12 months"},"fnd17_qcogs":{"ac":1,"uc":1,"cov":0.7536,"dom":"unbounded","sp":true,"desc":"Cost of goods sold for the most recent quarter"},"fnd17_pxedra":{"ac":22,"uc":7,"cov":0.3881,"dom":"unbounded","sp":true,"desc":"Research and development expense for the most recent fiscal year"},"fnd17_pxedrq":{"ac":1,"uc":1,"cov":0.3607,"dom":"unbounded","sp":true,"desc":"Research and development expense for the most recent quarter"},"fnd17_pxedrmtt":{"ac":1,"uc":1,"cov":0.3593,"dom":"unbounded","sp":true,"desc":"Research and development expense over the trailing 12 months; units: millions"},"fnd17_pxedrmtp":{"ac":20,"uc":8,"cov":0.3487,"dom":"unbounded","sp":true,"desc":"Research and development expense for the prior trailing twelve months"},"fnd17_asga2rev":{"ac":8,"uc":5,"cov":0.8028,"dom":"unbounded","sp":false,"desc":"SG&A expenses / net sales - most recent fiscal year"},"fnd17_qsga2rev":{"ac":11,"uc":5,"cov":0.7944,"dom":"unbounded","sp":true,"desc":"SG&A expenses / net sales - most recent quarter"},"fnd17_ttmsga2rev":{"ac":4,"uc":1,"cov":0.7937,"dom":"unbounded","sp":true,"desc":"SG&A expenses / net sales - trailing 12 month"},"fnd17_aintexpz":{"ac":1,"uc":1,"cov":0.7187,"dom":"unbounded","sp":true,"desc":"Total interest expense for the most recent fiscal year"},"fnd17_ttmintexp":{"ac":0,"uc":0,"cov":0.677,"dom":"unbounded","sp":true,"desc":"Interest expense over the trailing 12 months"},"fnd17_zpxetniq":{"ac":1,"uc":1,"cov":0.6641,"dom":"unbounded","sp":true,"desc":"Total interest expense for the most recent quarter"},"fnd17_ataxrate":{"ac":4,"uc":3,"cov":0.6572,"dom":"[-1, 1]","sp":true,"desc":"Effective tax rate for the most recent fiscal year"},"fnd17_ttmtaxrate":{"ac":1,"uc":1,"cov":0.6626,"dom":"[0, inf)","sp":true,"desc":"Tax rate - trailing 12 month"},"fnd17_beta":{"ac":3,"uc":3,"cov":0.7942,"dom":"unbounded","sp":true,"desc":"Beta"},"fnd17_beta_up":{"ac":14,"uc":2,"cov":0.8872,"dom":"unbounded","sp":false,"desc":"Upside beta calculated during up-market periods"},"fnd17_beta_down":{"ac":0,"uc":0,"cov":0.8424,"dom":"unbounded","sp":false,"desc":"Downside beta calculated during down-market periods"},"fnd17_annperiods":{"ac":4,"uc":4,"cov":0.9384,"dom":"unbounded","sp":false,"desc":"Number of historical periods - Annual"},"fnd17_qtrperiods":{"ac":3,"uc":2,"cov":0.9377,"dom":"unbounded","sp":false,"desc":"Number of historical quarterly periods available for the company"},"fnd17_adivshr":{"ac":1,"uc":1,"cov":0.5769,"dom":"unbounded","sp":true,"desc":"Dividend per share - most recent fiscal year"},"fnd17_ttmdivshr":{"ac":0,"uc":0,"cov":0.9286,"dom":"unbounded","sp":false,"desc":"Dividends per share - trailing 12 months"},"fnd17_dai":{"ac":0,"uc":0,"cov":0.4849,"dom":"[0, inf)","sp":true,"desc":"Dividend rate, indicated annual"},"fnd17_div":{"ac":0,"uc":0,"cov":0.5281,"dom":"unbounded","sp":true,"desc":"Dividends paid from the statement of cash flows - most recent fiscal year"},"fnd17_spdq":{"ac":0,"uc":0,"cov":0.9275,"dom":"[0, inf)","sp":false,"desc":"Dividend - most recent quarter"},"fnd17_divnq":{"ac":1,"uc":1,"cov":0.4933,"dom":"[0, inf)","sp":true,"desc":"Dividend - next quarterly declared"},"fnd17_gvay5dly":{"ac":4,"uc":1,"cov":0.4381,"dom":"[0, inf)","sp":true,"desc":"Dividend yield - 5 year average"},"fnd17_ttmpayrat":{"ac":1,"uc":1,"cov":0.6747,"dom":"[-1, 1]","sp":true,"desc":"Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings"},"fnd17_apayratio2":{"ac":6,"uc":1,"cov":0.6523,"dom":"[0, inf)","sp":true,"desc":"Payout ratio for the prior fiscal year"}}

// ---- 孪生配对表（本数据集皇冠明珠）----
const TWIN_PAIRS = ["  - fnd17_tcpaormtt (ac=4)  vs  fnd17_tcpaormtp (ac=0)   -- TTM return on average assets: now vs prior TTM","  - fnd17_ngmpnmtt (ac=3)  vs  fnd17_ngmpnmtp (ac=8)   -- TTM net profit margin: now vs prior TTM","  - fnd17_qtotd2eq (ac=1)  vs  fnd17_qtotd2eq2 (ac=2)   -- total debt / equity: now vs one year ago","  - fnd17_qcurratio (ac=2)  vs  fnd17_qcurratio2 (ac=1)   -- current ratio: now vs one year ago","  - fnd17_ttmintcov (ac=1)  vs  fnd17_ptmintcov (ac=0)   -- interest coverage: now vs prior TTM","  - fnd17_shsoutbs (ac=3)  vs  fnd17_shsoutbs2 (ac=6)   -- balance-sheet shares outstanding: now vs one year ago","  - fnd17_ttmrev (ac=0)  vs  fnd17_ptmrev (ac=3)   -- TTM revenue: now vs prior TTM"]

const AXES = {"accrual_quality":"### Axis: accrual_quality  (earnings quality / accruals (cash-backed earnings vs accrual earnings))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_aniacnorm\\` | ac=0 uc=0 cov=0.936 | unbounded | - | Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year\n- \\`fnd17_atmtt\\` | ac=0 uc=0 cov=0.908 | unbounded | - | Total assets, trailing twelve months\n- \\`fnd17_atotce\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Common equity (book value) - most recent fiscal year\n- \\`fnd17_cainq\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Net income available to common shareholders for the most recent quarter\n- \\`fnd17_inq\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Net income (earnings after taxes) for the most recent quarter\n- \\`fnd17_aniac\\` | ac=2 uc=2 cov=0.936 | unbounded | - | Net income available to common shareholders for the most recent fiscal year\n- \\`fnd17_aniexclxor\\` | ac=2 uc=2 cov=0.936 | unbounded | - | Net income excluding extraordinary items for the most recent fiscal year\n- \\`fnd17_aninorm\\` | ac=2 uc=1 cov=0.936 | unbounded | - | Net income after taxes excluding unusual or one-time items for the most recent fiscal year\n- \\`fnd17_qtotce\\` | ac=2 uc=1 cov=0.937 | unbounded | - | Common equity (book value) - most recent quarter\n- \\`fnd17_fcf1a\\` | ac=5 uc=4 cov=0.935 | unbounded | - | Free cash flow - most recent fiscal year\n- \\`fnd17_rhsfcfq\\` | ac=5 uc=5 cov=0.916 | unbounded | - | Free cash flow per share for the most recent quarter, annualized\n- \\`fnd17_rhsfcfmtt\\` | ac=6 uc=6 cov=0.904 | unbounded | - | Free cash flow per share over the trailing 12 months\n- \\`fnd17_fcfq\\` | ac=7 uc=6 cov=0.922 | unbounded | - | Free cash flow for the most recent quarter\n- \\`fnd17_aniacinclx\\` | ac=8 uc=1 cov=0.936 | unbounded | - | Net income available to common including extraordinary items for the most recent fiscal year\n- \\`fnd17_ani\\` | ac=9 uc=2 cov=0.936 | unbounded | - | Net income (earnings after taxes) for the most recent fiscal year\n- \\`fnd17_fcfmtt\\` | ac=10 uc=6 cov=0.910 | unbounded | - | Free cash flow - trailing 12 months\n- \\`fnd17_ata\\` | ac=14 uc=4 cov=0.937 | unbounded | - | Total assets - most recent fiscal year","profitability_roa_roe":"### Axis: profitability_roa_roe  (profitability (ROA / ROE / net margin) - the classic crowded quality factor)\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_ptmroepct\\` | ac=0 uc=0 cov=0.830 | unbounded | - | Return on average equity for the prior trailing twelve months\n- \\`fnd17_tcpaormtp\\` | ac=0 uc=0 cov=0.864 | unbounded | - | Return on average assets for the prior trailing twelve months\n- \\`fnd17_aptmgnpct2\\` | ac=1 uc=1 cov=0.898 | [-1, 1] | - | Pretax Margin - 2nd historical fiscal year\n- \\`fnd17_tcpngmpoa\\` | ac=1 uc=1 cov=0.901 | [-1, 1] | - | Operating margin - 1st historical fiscal year\n- \\`fnd17_aroapct\\` | ac=2 uc=2 cov=0.931 | unbounded | - | Return on average assets for the most recent fiscal year\n- \\`fnd17_qroipct\\` | ac=2 uc=2 cov=0.836 | unbounded | - | Return on investment for the most recent quarter (annualized)\n- \\`fnd17_ry5ngmpo\\` | ac=2 uc=2 cov=0.791 | [-1, 1] | SP | Operating Margin - 5 year average\n- \\`fnd17_tcpngmpna\\` | ac=2 uc=2 cov=0.903 | [-1, 1] | - | Net Profit Margin % - 1st historical fiscal year\n- \\`fnd17_tcpngmpoq\\` | ac=2 uc=2 cov=0.900 | [-1, 1] | - | Operating margin - most recent quarter\n- \\`fnd17_2tcpngmpoa\\` | ac=3 uc=3 cov=0.896 | [-1, 1] | - | Operating Margin - 2nd historical fiscal year\n- \\`fnd17_aptmgnpct\\` | ac=3 uc=3 cov=0.903 | [-1, 1] | - | Pretax margin - 1st historical fiscal year\n- \\`fnd17_ngmpnmtt\\` | ac=3 uc=3 cov=0.900 | [-1, 1] | - | Net Profit Margin % - trailing 12 month\n- \\`fnd17_npmtrendgr\\` | ac=3 uc=2 cov=0.538 | [-1, 1] | SP | Five-year growth rate of net profit margin\n- \\`fnd17_ttmgrosmgn\\` | ac=3 uc=2 cov=0.748 | [-1, 1] | SP | Gross margin over the trailing 12 months\n- \\`fnd17_ttmopmgn\\` | ac=3 uc=3 cov=0.899 | [-1, 1] | - | Operating margin over the trailing 12 months\n- \\`fnd17_ttmroepct\\` | ac=3 uc=2 cov=0.869 | unbounded | - | Return on average equity - trailing 12 month\n- \\`fnd17_tcpaormtt\\` | ac=4 uc=3 cov=0.907 | unbounded | - | Return on average assets over the trailing 12 months (percentage)\n- \\`fnd17_tcpaorq\\` | ac=4 uc=3 cov=0.932 | unbounded | - | Return on average assets for the most recent quarter (annualized)\n- \\`fnd17_qroepct\\` | ac=5 uc=2 cov=0.889 | unbounded | - | Return on average equity for the most recent quarter (annualized)\n- \\`fnd17_ttmroipct\\` | ac=5 uc=1 cov=0.813 | unbounded | - | Return on investment - trailing 12 month\n- \\`fnd17_gmntrendgr\\` | ac=7 uc=3 cov=0.652 | [-1, 1] | SP | Five-year growth rate of gross margin\n- \\`fnd17_qgrosmgn\\` | ac=7 uc=3 cov=0.750 | [-1, 1] | SP | Gross Margin - most recent quarter\n- \\`fnd17_aroipct\\` | ac=8 uc=2 cov=0.835 | unbounded | - | Return on investment for the most recent fiscal year\n- \\`fnd17_ngmpnmtp\\` | ac=8 uc=4 cov=0.883 | [-1, 1] | - | Net Profit Margin % - prior trailing 12 month\n- \\`fnd17_a2netmrgn\\` | ac=12 uc=7 cov=0.898 | [-1, 1] | - | Net Profit Margin % - 2nd historical fiscal year","efficiency_dupont":"### Axis: efficiency_dupont  (efficiency (asset turnover, DuPont drivers))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_qinvturn\\` | ac=0 uc=0 cov=0.518 | [0, inf) | SP | Inventory turnover - most recent quarter (annualized)\n- \\`fnd17_qrecturn\\` | ac=0 uc=0 cov=0.774 | [0, inf) | SP | Receivables turnover - most recent quarter (annualized)\n- \\`fnd17_ttmastturn\\` | ac=0 uc=0 cov=0.840 | [0, inf) | - | Asset turnover - trailing 12 months\n- \\`fnd17_ttminvturn\\` | ac=0 uc=0 cov=0.507 | [0, inf) | SP | Inventory turnover - trailing 12 months\n- \\`fnd17_ainvturn\\` | ac=1 uc=1 cov=0.525 | [0, inf) | SP | Inventory turnover - most recent fiscal year\n- \\`fnd17_arecturn\\` | ac=1 uc=1 cov=0.781 | [0, inf) | SP | Receivables turnover - most recent fiscal year\n- \\`fnd17_qastturn\\` | ac=3 uc=3 cov=0.863 | [0, inf) | - | Asset turnover ratio for the most recent quarter, annualized\n- \\`fnd17_aastturn\\` | ac=6 uc=6 cov=0.863 | [0, inf) | - | Asset turnover - most recent fiscal year\n- \\`fnd17_ttmrecturn\\` | ac=8 uc=1 cov=0.756 | [0, inf) | SP | Receivables turnover - trailing 12 months","leverage_solvency":"### Axis: leverage_solvency  (leverage & solvency (debt/equity, solvency ratios))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_qtotd\\` | ac=0 uc=0 cov=0.936 | unbounded | - | Total debt - most recent quarter\n- \\`fnd17_netdebt_a\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Net debt (total debt minus cash and equivalents) for the last fiscal year\n- \\`fnd17_qe2dtlq\\` | ac=1 uc=1 cov=0.898 | [0, inf) | - | Long-term debt to shareholder equity ratio for the most recent quarter\n- \\`fnd17_qtotd2eq\\` | ac=1 uc=1 cov=0.898 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter\n- \\`fnd17_2qe2dtlq\\` | ac=2 uc=2 cov=0.872 | [0, inf) | - | Long-term debt to equity ratio for the most recent quarter one year ago\n- \\`fnd17_atotd\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Total debt - most recent fiscal year\n- \\`fnd17_atotd2eq\\` | ac=2 uc=2 cov=0.896 | unbounded | - | Total debt to shareholders\u2019 equity for the most recent fiscal year\n- \\`fnd17_atotltd\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Long-term debt (total) - most recent fiscal year\n- \\`fnd17_netdebt_i\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Net debt (total debt minus cash and equivalents) for the latest interim period\n- \\`fnd17_qtotd2eq2\\` | ac=2 uc=1 cov=0.872 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter, measured one year ago\n- \\`fnd17_qtotd2ast\\` | ac=3 uc=2 cov=0.936 | unbounded | - | Total debt to total assets for the most recent quarter\n- \\`fnd17_qtotd2cap\\` | ac=3 uc=1 cov=0.865 | [0, inf) | - | Ratio of total debt to total capital for the most recent quarter\n- \\`fnd17_atotd2ast\\` | ac=4 uc=3 cov=0.937 | unbounded | - | Total debt to total assets for the most recent fiscal year\n- \\`fnd17_atotd2cap\\` | ac=4 uc=2 cov=0.864 | unbounded | - | Total debt to total capital percentage, most recent fiscal year\n- \\`fnd17_qtotltd\\` | ac=9 uc=1 cov=0.936 | unbounded | - | Long-term debt (total), most recent quarter","liquidity_coverage":"### Axis: liquidity_coverage  (liquidity & coverage (current ratio, interest coverage))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_aquickrati\\` | ac=0 uc=0 cov=0.517 | [0, inf) | SP | Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities\n- \\`fnd17_ptmintcov\\` | ac=0 uc=0 cov=0.641 | [0, inf) | SP | Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense\n- \\`fnd17_qquickrat2\\` | ac=0 uc=0 cov=0.499 | [0, inf) | SP | Quick ratio for the most recent quarter one year ago\n- \\`fnd17_qcurratio2\\` | ac=1 uc=1 cov=0.719 | [0, inf) | SP | Current ratio - most recent quarter, 1 year ago\n- \\`fnd17_ttmintcov\\` | ac=1 uc=1 cov=0.649 | [0, inf) | SP | Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months\n- \\`fnd17_qcurratio\\` | ac=2 uc=2 cov=0.745 | [0, inf) | SP | Current ratio for the most recent quarter\n- \\`fnd17_qquickrati\\` | ac=2 uc=2 cov=0.512 | [0, inf) | SP | Quick ratio for the most recent quarter\n- \\`fnd17_aintcov\\` | ac=3 uc=3 cov=0.620 | [0, inf) | SP | Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense\n- \\`fnd17_acurratio\\` | ac=5 uc=5 cov=0.745 | [0, inf) | SP | Current ratio for the most recent fiscal year (current assets divided by current liabilities)\n- \\`fnd17_qcash\\` | ac=5 uc=5 cov=0.936 | unbounded | - | Cash and cash equivalents for the most recent quarter\n- \\`fnd17_hsca\\` | ac=6 uc=3 cov=0.936 | unbounded | - | Cash and cash equivalents at fiscal year-end\n- \\`fnd17_voctniq\\` | ac=8 uc=3 cov=0.667 | [0, inf) | SP | Interest coverage ratio for the most recent quarter\n- \\`fnd17_sphsca\\` | ac=13 uc=6 cov=0.935 | unbounded | - | Cash per share - most recent fiscal year\n- \\`fnd17_sphscq\\` | ac=14 uc=6 cov=0.935 | unbounded | - | Cash and equivalents per share for the most recent quarter","growth_surprise":"### Axis: growth_surprise  (growth & surprise (revenue/earnings growth across periods))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_ghcspemtt\\` | ac=0 uc=0 cov=0.906 | [-1, 1] | - | Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period\n- \\`fnd17_nichngin\\` | ac=0 uc=0 cov=0.931 | [-1, 1] | - | Percent change in net income versus the prior quarter\n- \\`fnd17_nichngyr\\` | ac=0 uc=0 cov=0.927 | [-1, 1] | - | Percent change in net income for the most recent quarter versus the same quarter a year ago\n- \\`fnd17_qrev\\` | ac=0 uc=0 cov=0.937 | unbounded | - | Revenue for the most recent quarter\n- \\`fnd17_qrevps\\` | ac=0 uc=0 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (annualized)\n- \\`fnd17_ttmnichg\\` | ac=0 uc=0 cov=0.906 | [-1, 1] | - | Percent change in trailing 12-month net income versus the prior TTM\n- \\`fnd17_ttmrev\\` | ac=0 uc=0 cov=0.929 | unbounded | - | Revenue over the trailing 12 months; units: millions\n- \\`fnd17_epschngyri\\` | ac=1 uc=1 cov=0.964 | [0, inf) | - | EPS Change % - year to date\n- \\`fnd17_revgrpct\\` | ac=1 uc=1 cov=0.852 | [-1, 1] | - | Three-year revenue growth rate (percent)\n- \\`fnd17_revps5ygr\\` | ac=1 uc=1 cov=0.782 | [-1, 1] | SP | Five-year growth rate of revenue per share\n- \\`fnd17_arev\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Total revenue (sales) for the most recent fiscal year\n- \\`fnd17_arevps\\` | ac=2 uc=2 cov=0.936 | unbounded | - | Revenue per share for the most recent fiscal year\n- \\`fnd17_ghcspea\\` | ac=2 uc=1 cov=0.928 | [-1, 1] | - | Year-over-year percent change in annual earnings per share compared to the previous fiscal year\n- \\`fnd17_qrevpsna\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (not annualized)\n- \\`fnd17_revtrendgr\\` | ac=2 uc=2 cov=0.783 | [-1, 1] | SP | Five-year revenue growth rate\n- \\`fnd17_rygnhcspe\\` | ac=2 uc=2 cov=0.926 | [-1, 1] | - | Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year\n- \\`fnd17_ptmrev\\` | ac=3 uc=1 cov=0.909 | unbounded | - | Revenue for the prior trailing twelve months\n- \\`fnd17_revchngin\\` | ac=3 uc=3 cov=0.897 | [-1, 1] | - | Percentage change in revenue versus the immediately preceding quarter\n- \\`fnd17_revchngyr\\` | ac=3 uc=3 cov=0.893 | [-1, 1] | - | Percent change in revenue for the most recent quarter versus the same quarter a year ago\n- \\`fnd17_revtrend10\\` | ac=3 uc=3 cov=0.648 | [-1, 1] | SP | Ten-year revenue growth rate\n- \\`fnd17_ttmrevps\\` | ac=4 uc=3 cov=0.929 | unbounded | - | Revenue/share - trailing 12 month\n- \\`fnd17_epschngin\\` | ac=6 uc=5 cov=0.931 | [-1, 1] | - | Percent change in EPS from the prior quarter","share_count_dilution":"### Axis: share_count_dilution  (share count & dilution (buybacks, issuance))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_mtpbshs\\` | ac=1 uc=1 cov=0.909 | unbounded | - | Shares outstanding basic, average prior trailing 12 months\n- \\`fnd17_mtpshs\\` | ac=1 uc=1 cov=0.909 | unbounded | - | Shares outstanding, average prior trailing 12 months\n- \\`fnd17_mttshs\\` | ac=1 uc=1 cov=0.929 | unbounded | - | Shares outstanding - average trailing 12 month\n- \\`fnd17_shboutavgq\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Shares outstanding basic, average, most recent quarter\n- \\`fnd17_shsoutavgq\\` | ac=1 uc=1 cov=0.937 | unbounded | - | Shares outstanding, average, most recent quarter\n- \\`fnd17_float\\` | ac=2 uc=2 cov=0.937 | unbounded | - | Public float (shares available for trading)\n- \\`fnd17_mttbshs\\` | ac=2 uc=2 cov=0.929 | unbounded | - | Shares outstanding basic, average trailing 12 months\n- \\`fnd17_shsboutavg\\` | ac=2 uc=2 cov=0.936 | unbounded | - | Shares outstanding Basic - average, most recent fiscal year\n- \\`fnd17_shsoutbs\\` | ac=3 uc=3 cov=0.936 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter\n- \\`fnd17_shsout\\` | ac=4 uc=3 cov=0.939 | unbounded | - | Shares outstanding, current\n- \\`fnd17_shsoutavg\\` | ac=5 uc=2 cov=0.936 | unbounded | - | Shares outstanding - average, most recent fiscal year\n- \\`fnd17_shsoutbs2\\` | ac=6 uc=1 cov=0.908 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter one year ago","cost_intensity_rd":"### Axis: cost_intensity_rd  (cost intensity & R&D (margins, cost structure))\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_ttmcogs\\` | ac=0 uc=0 cov=0.751 | unbounded | SP | Cost of goods sold over the trailing 12 months\n- \\`fnd17_ttmintexp\\` | ac=0 uc=0 cov=0.677 | unbounded | SP | Interest expense over the trailing 12 months\n- \\`fnd17_aintexpz\\` | ac=1 uc=1 cov=0.719 | unbounded | SP | Total interest expense for the most recent fiscal year\n- \\`fnd17_pxedrmtt\\` | ac=1 uc=1 cov=0.359 | unbounded | SP | Research and development expense over the trailing 12 months; units: millions\n- \\`fnd17_pxedrq\\` | ac=1 uc=1 cov=0.361 | unbounded | SP | Research and development expense for the most recent quarter\n- \\`fnd17_qcogs\\` | ac=1 uc=1 cov=0.754 | unbounded | SP | Cost of goods sold for the most recent quarter\n- \\`fnd17_ttmtaxrate\\` | ac=1 uc=1 cov=0.663 | [0, inf) | SP | Tax rate - trailing 12 month\n- \\`fnd17_zpxetniq\\` | ac=1 uc=1 cov=0.664 | unbounded | SP | Total interest expense for the most recent quarter\n- \\`fnd17_ataxrate\\` | ac=4 uc=3 cov=0.657 | [-1, 1] | SP | Effective tax rate for the most recent fiscal year\n- \\`fnd17_ttmsga2rev\\` | ac=4 uc=1 cov=0.794 | unbounded | SP | SG&A expenses / net sales - trailing 12 month\n- \\`fnd17_asga2rev\\` | ac=8 uc=5 cov=0.803 | unbounded | - | SG&A expenses / net sales - most recent fiscal year\n- \\`fnd17_qsga2rev\\` | ac=11 uc=5 cov=0.794 | unbounded | SP | SG&A expenses / net sales - most recent quarter\n- \\`fnd17_pxedrmtp\\` | ac=20 uc=8 cov=0.349 | unbounded | SP | Research and development expense for the prior trailing twelve months\n- \\`fnd17_acogs\\` | ac=22 uc=4 cov=0.754 | unbounded | SP | Cost of goods sold for the most recent fiscal year\n- \\`fnd17_pxedra\\` | ac=22 uc=7 cov=0.388 | unbounded | SP | Research and development expense for the most recent fiscal year","uncertainty_scale":"### Axis: uncertainty_scale  (uncertainty / scale - USE ONLY AS A STRICTLY-POSITIVE WEIGHT OR GATE, never as the direction)\n\n\\`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc\\`\n\n- \\`fnd17_beta_down\\` | ac=0 uc=0 cov=0.842 | unbounded | - | Downside beta calculated during down-market periods\n- \\`fnd17_dai\\` | ac=0 uc=0 cov=0.485 | [0, inf) | SP | Dividend rate, indicated annual\n- \\`fnd17_div\\` | ac=0 uc=0 cov=0.528 | unbounded | SP | Dividends paid from the statement of cash flows - most recent fiscal year\n- \\`fnd17_spdq\\` | ac=0 uc=0 cov=0.927 | [0, inf) | - | Dividend - most recent quarter\n- \\`fnd17_ttmdivshr\\` | ac=0 uc=0 cov=0.929 | unbounded | - | Dividends per share - trailing 12 months\n- \\`fnd17_adivshr\\` | ac=1 uc=1 cov=0.577 | unbounded | SP | Dividend per share - most recent fiscal year\n- \\`fnd17_divnq\\` | ac=1 uc=1 cov=0.493 | [0, inf) | SP | Dividend - next quarterly declared\n- \\`fnd17_ttmpayrat\\` | ac=1 uc=1 cov=0.675 | [-1, 1] | SP | Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings\n- \\`fnd17_beta\\` | ac=3 uc=3 cov=0.794 | unbounded | SP | Beta\n- \\`fnd17_qtrperiods\\` | ac=3 uc=2 cov=0.938 | unbounded | - | Number of historical quarterly periods available for the company\n- \\`fnd17_annperiods\\` | ac=4 uc=4 cov=0.938 | unbounded | - | Number of historical periods - Annual\n- \\`fnd17_gvay5dly\\` | ac=4 uc=1 cov=0.438 | [0, inf) | SP | Dividend yield - 5 year average\n- \\`fnd17_apayratio2\\` | ac=6 uc=1 cov=0.652 | [0, inf) | SP | Payout ratio for the prior fiscal year\n- \\`fnd17_beta_up\\` | ac=14 uc=2 cov=0.887 | unbounded | - | Upside beta calculated during up-market periods"}

const FIELD_SCHEMA = {
  type: 'object',
  properties: {
    candidates: {
      type: 'array',
      description: 'Exactly TWO distinct prototypes for this question dimension',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          question_type: { type: 'string' },
          fields_used: { type: 'array', items: { type: 'string' } },
          expression: { type: 'string' },
          economic_mechanism: { type: 'string', description: 'Chinese, >=100 chars: who is the counterparty, what behavioural bias or institutional friction sustains it in OS' },
          counterparty: { type: 'string', description: 'Chinese, who is on the other side of the trade' },
          orthogonality_note: { type: 'string', description: 'Chinese, what makes this mechanism orthogonal to the other seeds' },
          operator_count: { type: 'integer' },
          crowding_note: { type: 'string', description: 'Chinese, alphaCount/userCount of each field and why anti-crowding law is satisfied' },
        },
        required: ['id', 'question_type', 'fields_used', 'expression', 'economic_mechanism', 'counterparty', 'orthogonality_note', 'operator_count', 'crowding_note'],
        additionalProperties: false,
      },
    },
  },
  required: ['candidates'],
  additionalProperties: false,
}


// ---- 429 退避重试：上一版 8 个 agent 并发打 API，其中 4 个被 429 直接打死，
//      导致整批 0 产出。这里给每个 agent 调用加指数退避重试。
const sleepMs = (ms) => new Promise((r) => setTimeout(r, ms))
async function agentRetry(opts, attempts = 4) {
  let lastErr = null
  for (let i = 0; i < attempts; i++) {
    try {
      return await agent(opts.prompt, opts.opts)
    } catch (e) {
      lastErr = e
      const msg = String((e && e.message) || e)
      const isRate = /429|Too Many Requests|rate limit/i.test(msg)
      if (!isRate) throw e
      const wait = 2000 * Math.pow(2, i) + i * 500
      log(`429 backoff: retry ${i + 1}/${attempts} in ${wait}ms (${opts.opts.label || ''})`)
      await sleepMs(wait)
    }
  }
  throw lastErr
}

// ---- 保序并行：失败者变 null，**不改变下标**。
//      上一版用 parallel(...).filter(Boolean) 再按下标配对，一个 agent 挂掉
//      就让后面所有槽位的判决整体串位 —— 这是上一轮 workflow 14 个 agent
//      启动、0 结果的根因之一。
async function parallelOrdered(thunks) {
  const settled = await Promise.allSettled(thunks.map((t) => t()))
  return settled.map((r) => (r.status === 'fulfilled' ? r.value : null))
}

// ---- 断路器：整批若一条都没产出，直接抛，避免下游拿空数组继续跑。
function requireNonEmpty(arr, label) {
  if (!arr || arr.length === 0) {
    throw new Error(`FATAL: ${label} produced zero usable results - aborting rather than shipping an empty batch.`)
  }
  return arr
}

phase('SeedSynthesis')

const QUESTIONS = [
  { n: 'Q1', t: 'Invariance', axes: ['profitability_roa_roe', 'efficiency_dupont', 'cost_intensity_rd'],
     focus: 'Scale invariance: divide an absolute amount by an INTERNAL scale anchor (total assets / revenue / equity) to get a comparable "output per unit of resource". NEVER use price or market cap as the denominator. The trap: a raw ROA LEVEL is the most crowded quality factor in existence (ac=4 means 4 platform alphas already use it) - so you must either use a twin pair (now vs own history) or build a SECOND-ORDER deviation from the company own history.' },
  { n: 'Q2', t: 'Dynamics', axes: ['growth_surprise', 'profitability_roa_roe'],
     focus: 'Temporal dynamics: the dataset ships "prior period / one year ago" TWIN fields, so the difference between the current reading and the company OWN prior reading is a genuine second-order expectation gap. Alternatively ts_delta / ts_av_diff to capture the speed of change. You must state explicitly which side makes money (improvement long / deterioration short, or the reverse) and why.' },
  { n: 'Q3', t: 'Anomaly', axes: ['cost_intensity_rd', 'liquidity_coverage', 'uncertainty_scale'],
     focus: 'Anomaly shock: an extreme deviation of a ratio from its OWN historical baseline. Use ts_av_diff (deviation from own rolling mean) or ts_zscore over a legal window. You must pick reversion OR continuation and justify it from an institutional reason. NOTE: ts_zscore as INTERNAL normalisation destroys the signal - only zscore / group_zscore as the OUTERMOST layer is acceptable.' },
  { n: 'Q4', t: 'Interaction', axes: ['accrual_quality', 'leverage_solvency', 'liquidity_coverage'],
     focus: 'Cross-field synergy: two fields that only mean something TOGETHER (e.g. cash-backed earnings vs leverage; coverage vs debt). HARD RULE (axiom 1): NEVER multiply two signed variables (both can be negative) - that creates a fake positive when both collapse. If you use multiply, the weight term must be STRICTLY POSITIVE (e.g. rank(x), or a [0,inf) ratio).' },
  { n: 'Q5', t: 'Structure', axes: ['cost_intensity_rd', 'accrual_quality', 'efficiency_dupont'],
     focus: 'Structural share: a sub-item as a share of a total (margin structure, expense ratio, leverage mix). If the denominator can be 0 or negative you MUST add an epsilon (add(x,1)) or restructure so the ratio is well defined.' },
  { n: 'Q6', t: 'Accumulation', axes: ['growth_surprise', 'cost_intensity_rd', 'uncertainty_scale'],
     focus: 'Cumulative memory: how the effect accumulates and decays over time - use ts_mean / ts_decay_linear as a memory kernel. HARD RULE: ts_decay_* must NEVER be nested inside ts_backfill (two time operators contaminate each other and explode turnover). Correct order: reduce -> ts_backfill -> normalise -> outer decay.' },
  { n: 'Q7', t: 'Relative', axes: ['efficiency_dupont', 'leverage_solvency', 'profitability_roa_roe'],
     focus: 'Cross-sectional relativity: strength WITHIN a peer group. RED LINE: group_rank / group_zscore must NEVER be the OUTERMOST operator (output is pinned to [0,1] => one-sided book => pure beta illusion). The outermost layer must be a zero-mean construct: zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff.' },
  { n: 'Q8', t: 'Essence', axes: ['growth_surprise', 'accrual_quality', 'share_count_dilution'],
     focus: 'Essential expectation gap: the market only pays for the SURPRISE beyond expectations. Build it as "current reading vs the company OWN historical baseline" (twin pair, or ts_mean baseline) - a second-order gap. NEVER cross-sectionally rank a first-order bare level.' },
]

const seedPromises = QUESTIONS.map((q) => () => agentRetry({
  prompt:
`You are the AEGIS lead signal navigator, mining a WorldQuant BRAIN alpha for dataset fundamental17 (USA / TOP1000 / delay 1).

READ FIRST (use the Read tool): "D:\\python\\Lib\\site-packages\\cnhkmcp\\untracked\\APP\\.agents\\quant_framework\\campaigns\\aegis_fnd17\\CAMPAIGN_CONTEXT.md"
That is the complete campaign context contract: physical facts, the four hard axioms, platform gates, and the list of already-falsified patterns (do NOT re-burn them).

Your assigned 8-question dimension: ${q.n} ${q.t}
${q.focus}

You have access to TWO other axes' field lists for cross-axis pairing. Here are the field lists you may draw from:

${AXES[q.axes[0]]}

${AXES[q.axes[1]]}

${(q.axes[2] && AXES[q.axes[2]]) ? AXES[q.axes[2]] : ''}

THE TWIN PAIRS - the crown jewel of this dataset (a current-period field plus the SAME company one period earlier = a genuine second-order expectation gap, and the twins are usually ac=0-3 so they satisfy the anti-crowding law):
  - fnd17_tcpaormtt (ac=4)  vs  fnd17_tcpaormtp (ac=0)   -- TTM return on average assets: now vs prior TTM
  - fnd17_ngmpnmtt (ac=3)  vs  fnd17_ngmpnmtp (ac=8)   -- TTM net profit margin: now vs prior TTM
  - fnd17_qtotd2eq (ac=1)  vs  fnd17_qtotd2eq2 (ac=2)   -- total debt / equity: now vs one year ago
  - fnd17_qcurratio (ac=2)  vs  fnd17_qcurratio2 (ac=1)   -- current ratio: now vs one year ago
  - fnd17_ttmintcov (ac=1)  vs  fnd17_ptmintcov (ac=0)   -- interest coverage: now vs prior TTM
  - fnd17_shsoutbs (ac=3)  vs  fnd17_shsoutbs2 (ac=6)   -- balance-sheet shares outstanding: now vs one year ago
  - fnd17_ttmrev (ac=0)  vs  fnd17_ptmrev (ac=3)   -- TTM revenue: now vs prior TTM

FULL FIELD METADATA for every field above (ac = platform alphaCount, how crowded it already is):
\`field_id | ac=alphaCount uc=userCount cov=coverage | domain | sparse | description\`

- \`fnd17_aniacnorm\` | ac=0 uc=0 cov=0.9361 | unbounded | - | Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year
- \`fnd17_aquickrati\` | ac=0 uc=0 cov=0.5167 | [0, inf) | SP | Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities
- \`fnd17_atmtt\` | ac=0 uc=0 cov=0.9083 | unbounded | - | Total assets, trailing twelve months
- \`fnd17_beta_down\` | ac=0 uc=0 cov=0.8424 | unbounded | - | Downside beta calculated during down-market periods
- \`fnd17_dai\` | ac=0 uc=0 cov=0.4849 | [0, inf) | SP | Dividend rate, indicated annual
- \`fnd17_div\` | ac=0 uc=0 cov=0.5281 | unbounded | SP | Dividends paid from the statement of cash flows - most recent fiscal year
- \`fnd17_ghcspemtt\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period
- \`fnd17_nichngin\` | ac=0 uc=0 cov=0.9307 | [-1, 1] | - | Percent change in net income versus the prior quarter
- \`fnd17_nichngyr\` | ac=0 uc=0 cov=0.9266 | [-1, 1] | - | Percent change in net income for the most recent quarter versus the same quarter a year ago
- \`fnd17_ptmintcov\` | ac=0 uc=0 cov=0.6415 | [0, inf) | SP | Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense
- \`fnd17_ptmroepct\` | ac=0 uc=0 cov=0.8297 | unbounded | - | Return on average equity for the prior trailing twelve months
- \`fnd17_qinvturn\` | ac=0 uc=0 cov=0.518 | [0, inf) | SP | Inventory turnover - most recent quarter (annualized)
- \`fnd17_qquickrat2\` | ac=0 uc=0 cov=0.4989 | [0, inf) | SP | Quick ratio for the most recent quarter one year ago
- \`fnd17_qrecturn\` | ac=0 uc=0 cov=0.774 | [0, inf) | SP | Receivables turnover - most recent quarter (annualized)
- \`fnd17_qrev\` | ac=0 uc=0 cov=0.9371 | unbounded | - | Revenue for the most recent quarter
- \`fnd17_qrevps\` | ac=0 uc=0 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (annualized)
- \`fnd17_qtotd\` | ac=0 uc=0 cov=0.936 | unbounded | - | Total debt - most recent quarter
- \`fnd17_spdq\` | ac=0 uc=0 cov=0.9275 | [0, inf) | - | Dividend - most recent quarter
- \`fnd17_tcpaormtp\` | ac=0 uc=0 cov=0.8638 | unbounded | - | Return on average assets for the prior trailing twelve months
- \`fnd17_ttmastturn\` | ac=0 uc=0 cov=0.8396 | [0, inf) | - | Asset turnover - trailing 12 months
- \`fnd17_ttmcogs\` | ac=0 uc=0 cov=0.7509 | unbounded | SP | Cost of goods sold over the trailing 12 months
- \`fnd17_ttmdivshr\` | ac=0 uc=0 cov=0.9286 | unbounded | - | Dividends per share - trailing 12 months
- \`fnd17_ttmintexp\` | ac=0 uc=0 cov=0.677 | unbounded | SP | Interest expense over the trailing 12 months
- \`fnd17_ttminvturn\` | ac=0 uc=0 cov=0.5071 | [0, inf) | SP | Inventory turnover - trailing 12 months
- \`fnd17_ttmnichg\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing 12-month net income versus the prior TTM
- \`fnd17_ttmrev\` | ac=0 uc=0 cov=0.9291 | unbounded | - | Revenue over the trailing 12 months; units: millions
- \`fnd17_adivshr\` | ac=1 uc=1 cov=0.5769 | unbounded | SP | Dividend per share - most recent fiscal year
- \`fnd17_aintexpz\` | ac=1 uc=1 cov=0.7187 | unbounded | SP | Total interest expense for the most recent fiscal year
- \`fnd17_ainvturn\` | ac=1 uc=1 cov=0.5246 | [0, inf) | SP | Inventory turnover - most recent fiscal year
- \`fnd17_aptmgnpct2\` | ac=1 uc=1 cov=0.8976 | [-1, 1] | - | Pretax Margin - 2nd historical fiscal year
- \`fnd17_arecturn\` | ac=1 uc=1 cov=0.7807 | [0, inf) | SP | Receivables turnover - most recent fiscal year
- \`fnd17_atotce\` | ac=1 uc=1 cov=0.9372 | unbounded | - | Common equity (book value) - most recent fiscal year
- \`fnd17_cainq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income available to common shareholders for the most recent quarter
- \`fnd17_divnq\` | ac=1 uc=1 cov=0.4933 | [0, inf) | SP | Dividend - next quarterly declared
- \`fnd17_epschngyri\` | ac=1 uc=1 cov=0.9644 | [0, inf) | - | EPS Change % - year to date
- \`fnd17_inq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income (earnings after taxes) for the most recent quarter
- \`fnd17_mtpbshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding basic, average prior trailing 12 months
- \`fnd17_mtpshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding, average prior trailing 12 months
- \`fnd17_mttshs\` | ac=1 uc=1 cov=0.9291 | unbounded | - | Shares outstanding - average trailing 12 month
- \`fnd17_netdebt_a\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net debt (total debt minus cash and equivalents) for the last fiscal year
- \`fnd17_pxedrmtt\` | ac=1 uc=1 cov=0.3593 | unbounded | SP | Research and development expense over the trailing 12 months; units: millions
- \`fnd17_pxedrq\` | ac=1 uc=1 cov=0.3607 | unbounded | SP | Research and development expense for the most recent quarter
- \`fnd17_qcogs\` | ac=1 uc=1 cov=0.7536 | unbounded | SP | Cost of goods sold for the most recent quarter
- \`fnd17_qcurratio2\` | ac=1 uc=1 cov=0.7187 | [0, inf) | SP | Current ratio - most recent quarter, 1 year ago
- \`fnd17_qe2dtlq\` | ac=1 uc=1 cov=0.8978 | [0, inf) | - | Long-term debt to shareholder equity ratio for the most recent quarter
- \`fnd17_qtotd2eq\` | ac=1 uc=1 cov=0.8982 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter
- \`fnd17_revgrpct\` | ac=1 uc=1 cov=0.8517 | [-1, 1] | - | Three-year revenue growth rate (percent)
- \`fnd17_revps5ygr\` | ac=1 uc=1 cov=0.7825 | [-1, 1] | SP | Five-year growth rate of revenue per share
- \`fnd17_shboutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding basic, average, most recent quarter
- \`fnd17_shsoutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding, average, most recent quarter
- \`fnd17_tcpngmpoa\` | ac=1 uc=1 cov=0.901 | [-1, 1] | - | Operating margin - 1st historical fiscal year
- \`fnd17_ttmintcov\` | ac=1 uc=1 cov=0.6489 | [0, inf) | SP | Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months
- \`fnd17_ttmpayrat\` | ac=1 uc=1 cov=0.6747 | [-1, 1] | SP | Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings
- \`fnd17_ttmtaxrate\` | ac=1 uc=1 cov=0.6626 | [0, inf) | SP | Tax rate - trailing 12 month
- \`fnd17_zpxetniq\` | ac=1 uc=1 cov=0.6641 | unbounded | SP | Total interest expense for the most recent quarter
- \`fnd17_2qe2dtlq\` | ac=2 uc=2 cov=0.8721 | [0, inf) | - | Long-term debt to equity ratio for the most recent quarter one year ago
- \`fnd17_aniac\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income available to common shareholders for the most recent fiscal year
- \`fnd17_aniexclxor\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income excluding extraordinary items for the most recent fiscal year
- \`fnd17_aninorm\` | ac=2 uc=1 cov=0.9361 | unbounded | - | Net income after taxes excluding unusual or one-time items for the most recent fiscal year
- \`fnd17_arev\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total revenue (sales) for the most recent fiscal year
- \`fnd17_arevps\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Revenue per share for the most recent fiscal year
- \`fnd17_aroapct\` | ac=2 uc=2 cov=0.9313 | unbounded | - | Return on average assets for the most recent fiscal year
- \`fnd17_atotd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total debt - most recent fiscal year
- \`fnd17_atotd2eq\` | ac=2 uc=2 cov=0.8965 | unbounded | - | Total debt to shareholders’ equity for the most recent fiscal year
- \`fnd17_atotltd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Long-term debt (total) - most recent fiscal year
- \`fnd17_float\` | ac=2 uc=2 cov=0.9372 | unbounded | - | Public float (shares available for trading)
- \`fnd17_ghcspea\` | ac=2 uc=1 cov=0.9285 | [-1, 1] | - | Year-over-year percent change in annual earnings per share compared to the previous fiscal year
- \`fnd17_mttbshs\` | ac=2 uc=2 cov=0.9291 | unbounded | - | Shares outstanding basic, average trailing 12 months
- \`fnd17_netdebt_i\` | ac=2 uc=2 cov=0.9367 | unbounded | - | Net debt (total debt minus cash and equivalents) for the latest interim period
- \`fnd17_qcurratio\` | ac=2 uc=2 cov=0.7445 | [0, inf) | SP | Current ratio for the most recent quarter
- \`fnd17_qquickrati\` | ac=2 uc=2 cov=0.5116 | [0, inf) | SP | Quick ratio for the most recent quarter
- \`fnd17_qrevpsna\` | ac=2 uc=2 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (not annualized)
- \`fnd17_qroipct\` | ac=2 uc=2 cov=0.8364 | unbounded | - | Return on investment for the most recent quarter (annualized)
- \`fnd17_qtotce\` | ac=2 uc=1 cov=0.9366 | unbounded | - | Common equity (book value) - most recent quarter
- \`fnd17_qtotd2eq2\` | ac=2 uc=1 cov=0.8722 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter, measured one year ago
- \`fnd17_revtrendgr\` | ac=2 uc=2 cov=0.7834 | [-1, 1] | SP | Five-year revenue growth rate
- \`fnd17_ry5ngmpo\` | ac=2 uc=2 cov=0.791 | [-1, 1] | SP | Operating Margin - 5 year average
- \`fnd17_rygnhcspe\` | ac=2 uc=2 cov=0.9264 | [-1, 1] | - | Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year
- \`fnd17_shsboutavg\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Shares outstanding Basic - average, most recent fiscal year
- \`fnd17_tcpngmpna\` | ac=2 uc=2 cov=0.903 | [-1, 1] | - | Net Profit Margin % - 1st historical fiscal year
- \`fnd17_tcpngmpoq\` | ac=2 uc=2 cov=0.9004 | [-1, 1] | - | Operating margin - most recent quarter
- \`fnd17_2tcpngmpoa\` | ac=3 uc=3 cov=0.8957 | [-1, 1] | - | Operating Margin - 2nd historical fiscal year
- \`fnd17_aintcov\` | ac=3 uc=3 cov=0.6199 | [0, inf) | SP | Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense
- \`fnd17_aptmgnpct\` | ac=3 uc=3 cov=0.903 | [-1, 1] | - | Pretax margin - 1st historical fiscal year
- \`fnd17_beta\` | ac=3 uc=3 cov=0.7942 | unbounded | SP | Beta
- \`fnd17_ngmpnmtt\` | ac=3 uc=3 cov=0.9003 | [-1, 1] | - | Net Profit Margin % - trailing 12 month
- \`fnd17_npmtrendgr\` | ac=3 uc=2 cov=0.5376 | [-1, 1] | SP | Five-year growth rate of net profit margin
- \`fnd17_ptmrev\` | ac=3 uc=1 cov=0.9094 | unbounded | - | Revenue for the prior trailing twelve months
- \`fnd17_qastturn\` | ac=3 uc=3 cov=0.8633 | [0, inf) | - | Asset turnover ratio for the most recent quarter, annualized
- \`fnd17_qtotd2ast\` | ac=3 uc=2 cov=0.936 | unbounded | - | Total debt to total assets for the most recent quarter
- \`fnd17_qtotd2cap\` | ac=3 uc=1 cov=0.8646 | [0, inf) | - | Ratio of total debt to total capital for the most recent quarter
- \`fnd17_qtrperiods\` | ac=3 uc=2 cov=0.9377 | unbounded | - | Number of historical quarterly periods available for the company
- \`fnd17_revchngin\` | ac=3 uc=3 cov=0.8974 | [-1, 1] | - | Percentage change in revenue versus the immediately preceding quarter
- \`fnd17_revchngyr\` | ac=3 uc=3 cov=0.8931 | [-1, 1] | - | Percent change in revenue for the most recent quarter versus the same quarter a year ago
- \`fnd17_revtrend10\` | ac=3 uc=3 cov=0.6482 | [-1, 1] | SP | Ten-year revenue growth rate
- \`fnd17_shsoutbs\` | ac=3 uc=3 cov=0.9361 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter
- \`fnd17_ttmgrosmgn\` | ac=3 uc=2 cov=0.748 | [-1, 1] | SP | Gross margin over the trailing 12 months
- \`fnd17_ttmopmgn\` | ac=3 uc=3 cov=0.8993 | [-1, 1] | - | Operating margin over the trailing 12 months
- \`fnd17_ttmroepct\` | ac=3 uc=2 cov=0.8693 | unbounded | - | Return on average equity - trailing 12 month
- \`fnd17_annperiods\` | ac=4 uc=4 cov=0.9384 | unbounded | - | Number of historical periods - Annual
- \`fnd17_ataxrate\` | ac=4 uc=3 cov=0.6572 | [-1, 1] | SP | Effective tax rate for the most recent fiscal year
- \`fnd17_atotd2ast\` | ac=4 uc=3 cov=0.937 | unbounded | - | Total debt to total assets for the most recent fiscal year
- \`fnd17_atotd2cap\` | ac=4 uc=2 cov=0.8641 | unbounded | - | Total debt to total capital percentage, most recent fiscal year
- \`fnd17_gvay5dly\` | ac=4 uc=1 cov=0.4381 | [0, inf) | SP | Dividend yield - 5 year average
- \`fnd17_shsout\` | ac=4 uc=3 cov=0.9385 | unbounded | - | Shares outstanding, current
- \`fnd17_tcpaormtt\` | ac=4 uc=3 cov=0.9072 | unbounded | - | Return on average assets over the trailing 12 months (percentage)
- \`fnd17_tcpaorq\` | ac=4 uc=3 cov=0.9316 | unbounded | - | Return on average assets for the most recent quarter (annualized)
- \`fnd17_ttmrevps\` | ac=4 uc=3 cov=0.929 | unbounded | - | Revenue/share - trailing 12 month
- \`fnd17_ttmsga2rev\` | ac=4 uc=1 cov=0.7937 | unbounded | SP | SG&A expenses / net sales - trailing 12 month
- \`fnd17_acurratio\` | ac=5 uc=5 cov=0.7448 | [0, inf) | SP | Current ratio for the most recent fiscal year (current assets divided by current liabilities)
- \`fnd17_fcf1a\` | ac=5 uc=4 cov=0.9353 | unbounded | - | Free cash flow - most recent fiscal year
- \`fnd17_qcash\` | ac=5 uc=5 cov=0.9357 | unbounded | - | Cash and cash equivalents for the most recent quarter
- \`fnd17_qroepct\` | ac=5 uc=2 cov=0.8892 | unbounded | - | Return on average equity for the most recent quarter (annualized)
- \`fnd17_rhsfcfq\` | ac=5 uc=5 cov=0.9159 | unbounded | - | Free cash flow per share for the most recent quarter, annualized
- \`fnd17_shsoutavg\` | ac=5 uc=2 cov=0.9361 | unbounded | - | Shares outstanding - average, most recent fiscal year
- \`fnd17_ttmroipct\` | ac=5 uc=1 cov=0.8134 | unbounded | - | Return on investment - trailing 12 month
- \`fnd17_aastturn\` | ac=6 uc=6 cov=0.8626 | [0, inf) | - | Asset turnover - most recent fiscal year
- \`fnd17_apayratio2\` | ac=6 uc=1 cov=0.6523 | [0, inf) | SP | Payout ratio for the prior fiscal year
- \`fnd17_epschngin\` | ac=6 uc=5 cov=0.9307 | [-1, 1] | - | Percent change in EPS from the prior quarter
- \`fnd17_hsca\` | ac=6 uc=3 cov=0.9357 | unbounded | - | Cash and cash equivalents at fiscal year-end
- \`fnd17_rhsfcfmtt\` | ac=6 uc=6 cov=0.9045 | unbounded | - | Free cash flow per share over the trailing 12 months
- \`fnd17_shsoutbs2\` | ac=6 uc=1 cov=0.9082 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter one year ago
- \`fnd17_fcfq\` | ac=7 uc=6 cov=0.9216 | unbounded | - | Free cash flow for the most recent quarter
- \`fnd17_gmntrendgr\` | ac=7 uc=3 cov=0.6518 | [-1, 1] | SP | Five-year growth rate of gross margin
- \`fnd17_qgrosmgn\` | ac=7 uc=3 cov=0.7501 | [-1, 1] | SP | Gross Margin - most recent quarter
- \`fnd17_aniacinclx\` | ac=8 uc=1 cov=0.9361 | unbounded | - | Net income available to common including extraordinary items for the most recent fiscal year
- \`fnd17_aroipct\` | ac=8 uc=2 cov=0.8348 | unbounded | - | Return on investment for the most recent fiscal year
- \`fnd17_asga2rev\` | ac=8 uc=5 cov=0.8028 | unbounded | - | SG&A expenses / net sales - most recent fiscal year
- \`fnd17_ngmpnmtp\` | ac=8 uc=4 cov=0.8831 | [-1, 1] | - | Net Profit Margin % - prior trailing 12 month
- \`fnd17_ttmrecturn\` | ac=8 uc=1 cov=0.7561 | [0, inf) | SP | Receivables turnover - trailing 12 months
- \`fnd17_voctniq\` | ac=8 uc=3 cov=0.6673 | [0, inf) | SP | Interest coverage ratio for the most recent quarter
- \`fnd17_ani\` | ac=9 uc=2 cov=0.9361 | unbounded | - | Net income (earnings after taxes) for the most recent fiscal year
- \`fnd17_qtotltd\` | ac=9 uc=1 cov=0.9357 | unbounded | - | Long-term debt (total), most recent quarter
- \`fnd17_fcfmtt\` | ac=10 uc=6 cov=0.9102 | unbounded | - | Free cash flow - trailing 12 months
- \`fnd17_qsga2rev\` | ac=11 uc=5 cov=0.7944 | unbounded | SP | SG&A expenses / net sales - most recent quarter
- \`fnd17_a2netmrgn\` | ac=12 uc=7 cov=0.8976 | [-1, 1] | - | Net Profit Margin % - 2nd historical fiscal year
- \`fnd17_sphsca\` | ac=13 uc=6 cov=0.9351 | unbounded | - | Cash per share - most recent fiscal year
- \`fnd17_ata\` | ac=14 uc=4 cov=0.9372 | unbounded | - | Total assets - most recent fiscal year
- \`fnd17_beta_up\` | ac=14 uc=2 cov=0.8872 | unbounded | - | Upside beta calculated during up-market periods
- \`fnd17_sphscq\` | ac=14 uc=6 cov=0.935 | unbounded | - | Cash and equivalents per share for the most recent quarter
- \`fnd17_pxedrmtp\` | ac=20 uc=8 cov=0.3487 | unbounded | SP | Research and development expense for the prior trailing twelve months
- \`fnd17_acogs\` | ac=22 uc=4 cov=0.754 | unbounded | SP | Cost of goods sold for the most recent fiscal year
- \`fnd17_pxedra\` | ac=22 uc=7 cov=0.3881 | unbounded | SP | Research and development expense for the most recent fiscal year

HARD RULES - violating any of these gets you rejected by the tech audit:
1. Only fundamental17 internal fields (id prefix fnd17_), taken from the lists above. Field count MUST be 2 or 3.
2. Operator count <= 4. Legal operators: add / subtract / divide / multiply / ts_mean / ts_delta / ts_std_dev / ts_av_diff / ts_rank / ts_zscore / ts_backfill / ts_decay_linear / group_rank / group_zscore / zscore / rank / reverse. BANNED: group_neutralize, bucket, add(rank,rank), trade_when, hump, signed_power, quantile, multiply of two signed variables, subtract(x,0.5).
3. Time windows only from {3, 5, 10, 20, 60, 120, 252}.
4. The OUTERMOST operator MUST be zero-mean: one of zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff. NEVER group_rank or rank at the top.
5. NO price / volume / market cap / valuation-multiple fields at all: no nprice, mktcap, ev_cur, pr*dayprc, vol*, priceavg*, *price2bk*, *peexclxor*, *spfcr*, ebitda2ev*, awcappspr, qwcappspr, yield. Also no external close/open/high/low/vwap/returns/volume/cap/adv20.
6. No FX / currency-code fields.
7. ANTI-CROWDING: prefer ac <= 5 (ac = 0 is virgin). fundamental17 is the single most crowded fundamental dataset on the platform (dataset alphaCount=781, userCount=380, valueScore=1) - so a bare first-order cross-sectional level on a hot field is BANNED. If a field has ac > 5 you MUST build a second-order surprise (twin pair, or deviation from own history) around it.
8. The expression must parse with Python ast.parse, balanced parentheses, legal FastExpr operator names. group_* operators take the group as a BARE literal (market / sector / industry / subindustry, NO quotes).
9. economic_mechanism (Chinese, >= 100 characters) must state: (a) WHO is on the other side of the trade - what behavioural bias or institutional friction keeps the pattern alive out-of-sample; (b) WHY this expression structure captures that mechanism; (c) the expected DIRECTION (which side you long).
10. counterparty: separately, in Chinese.
11. orthogonality_note: in Chinese, explain why this is ORTHOGONAL IN MECHANISM (not in operator choice) to the other seven seeds.
12. IMPORTANT dataset-specific physics: the data updates on quarterly/annual report cadence, so a signal that keeps producing cross-sectional dispersion on days with no new filings is actually trading a STATIC value factor, not the mechanism you declared. Prefer constructions whose variation comes from the ARRIVAL of new information (twins, ts_delta on a field that just updated) over constructions that merely re-rank static levels.
13. IMPORTANT: ratio fields (margin / growth / turnover / coverage) are naturally positively biased or signed. If you treat a ratio as "higher is better" without de-meaning it, you are actually trading the crowded quality factor, NOT your declared mechanism. Make sure the declared mechanism matches what the AST really computes.
14. If your mechanism text mentions marginal change / jump / delta / momentum (Chinese: bianhua, yuesheng, tubian, dongliang) then the expression MUST contain ts_delta, ts_zscore, subtract or divide. If it mentions gating / filtering / weighting / interaction (Chinese: menkong, guolv, fangda, quan Zhong, jiaohu) then the expression MUST contain multiply or power. The local engine mechanically checks this and will reject a mismatch.

Read the context file, pick fields that genuinely exist, then write the expression. Every field id must appear VERBATIM in the metadata table above.

Produce EXACTLY TWO candidates for your question dimension. They must be genuinely different mechanisms (not two cosmetic re-spellings of one idea): candidate A and candidate B must use DIFFERENT field pairs, and at least one of them must NOT share its core field pair with the other. Candidate A should be your best single idea; candidate B should be your second-best, genuinely orthogonal idea within the same 8-question dimension. Each candidate needs its own id (e.g. "${q.n}A" / "${q.n}B").

Return the structured JSON only.`,
  opts: { label: `seed:${q.n}`, phase: 'SeedSynthesis', schema: FIELD_SCHEMA, agentType: 'general-purpose' },
}))

const seedSlabs = requireNonEmpty(await parallelOrdered(seedPromises), 'SeedSynthesis')
log(`Phase 0 seed synthesis: ${seedSlabs.filter(Boolean).length}/8 question-slabs produced`)

// ★ 关键修复：上一版先 filter(Boolean) 再 zip，导致 auditResults[i] 与 seedResults[i]
//   错位（一个 agent 挂掉，整条流水线索引全部串位）。这里改成**按 key 严格配对**。
const seedPool = []
seedSlabs.forEach((slab) => {
  const cs = (slab && slab.candidates) || []
  cs.forEach((c) => {
    if (c && c.expression && c.id) seedPool.push(c)
  })
})
log(`Phase 0 seed pool: ${seedPool.length} candidates from ${seedSlabs.filter(Boolean).length} slabs`)

phase('TechAudit')

const AUDIT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'REJECT'] },
    issues: { type: 'array', items: { type: 'string' } },
    field_truth_ok: { type: 'boolean' },
    zero_pv_ok: { type: 'boolean' },
    syntax_ok: { type: 'boolean' },
    operator_count_ok: { type: 'boolean' },
    field_count_ok: { type: 'boolean' },
    window_ok: { type: 'boolean' },
    top_level_zero_mean_ok: { type: 'boolean' },
    axiom_compliance: { type: 'string', description: 'Chinese, check each of the four axioms one by one' },
    corrected_expression: { type: 'string', description: 'If a purely mechanical defect (window value, operator alias, quote around group) can be fixed without changing the economics, give the corrected expression; otherwise identical to the original' },
  },
  required: ['verdict', 'issues', 'field_truth_ok', 'zero_pv_ok', 'syntax_ok', 'operator_count_ok', 'field_count_ok', 'window_ok', 'top_level_zero_mean_ok', 'axiom_compliance', 'corrected_expression'],
  additionalProperties: false,
}

const auditPromises = seedPool.map((s) => () => agentRetry({
  prompt:
`You are the AEGIS technical auditor - a cold-blooded fact-finder. No literary debate, only hard facts.

READ FIRST (use the Read tool): "D:\\python\\Lib\\site-packages\\cnhkmcp\\untracked\\APP\\.agents\\quant_framework\\campaigns\\aegis_fnd17\\CAMPAIGN_CONTEXT.md"
(the campaign contract: the four axioms and the falsified-pattern list)

Here is the complete authoritative metadata for every field you may see:
\`field_id | ac=alphaCount uc=userCount cov=coverage | domain | sparse | description\`

- \`fnd17_aniacnorm\` | ac=0 uc=0 cov=0.9361 | unbounded | - | Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year
- \`fnd17_aquickrati\` | ac=0 uc=0 cov=0.5167 | [0, inf) | SP | Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities
- \`fnd17_atmtt\` | ac=0 uc=0 cov=0.9083 | unbounded | - | Total assets, trailing twelve months
- \`fnd17_beta_down\` | ac=0 uc=0 cov=0.8424 | unbounded | - | Downside beta calculated during down-market periods
- \`fnd17_dai\` | ac=0 uc=0 cov=0.4849 | [0, inf) | SP | Dividend rate, indicated annual
- \`fnd17_div\` | ac=0 uc=0 cov=0.5281 | unbounded | SP | Dividends paid from the statement of cash flows - most recent fiscal year
- \`fnd17_ghcspemtt\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period
- \`fnd17_nichngin\` | ac=0 uc=0 cov=0.9307 | [-1, 1] | - | Percent change in net income versus the prior quarter
- \`fnd17_nichngyr\` | ac=0 uc=0 cov=0.9266 | [-1, 1] | - | Percent change in net income for the most recent quarter versus the same quarter a year ago
- \`fnd17_ptmintcov\` | ac=0 uc=0 cov=0.6415 | [0, inf) | SP | Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense
- \`fnd17_ptmroepct\` | ac=0 uc=0 cov=0.8297 | unbounded | - | Return on average equity for the prior trailing twelve months
- \`fnd17_qinvturn\` | ac=0 uc=0 cov=0.518 | [0, inf) | SP | Inventory turnover - most recent quarter (annualized)
- \`fnd17_qquickrat2\` | ac=0 uc=0 cov=0.4989 | [0, inf) | SP | Quick ratio for the most recent quarter one year ago
- \`fnd17_qrecturn\` | ac=0 uc=0 cov=0.774 | [0, inf) | SP | Receivables turnover - most recent quarter (annualized)
- \`fnd17_qrev\` | ac=0 uc=0 cov=0.9371 | unbounded | - | Revenue for the most recent quarter
- \`fnd17_qrevps\` | ac=0 uc=0 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (annualized)
- \`fnd17_qtotd\` | ac=0 uc=0 cov=0.936 | unbounded | - | Total debt - most recent quarter
- \`fnd17_spdq\` | ac=0 uc=0 cov=0.9275 | [0, inf) | - | Dividend - most recent quarter
- \`fnd17_tcpaormtp\` | ac=0 uc=0 cov=0.8638 | unbounded | - | Return on average assets for the prior trailing twelve months
- \`fnd17_ttmastturn\` | ac=0 uc=0 cov=0.8396 | [0, inf) | - | Asset turnover - trailing 12 months
- \`fnd17_ttmcogs\` | ac=0 uc=0 cov=0.7509 | unbounded | SP | Cost of goods sold over the trailing 12 months
- \`fnd17_ttmdivshr\` | ac=0 uc=0 cov=0.9286 | unbounded | - | Dividends per share - trailing 12 months
- \`fnd17_ttmintexp\` | ac=0 uc=0 cov=0.677 | unbounded | SP | Interest expense over the trailing 12 months
- \`fnd17_ttminvturn\` | ac=0 uc=0 cov=0.5071 | [0, inf) | SP | Inventory turnover - trailing 12 months
- \`fnd17_ttmnichg\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing 12-month net income versus the prior TTM
- \`fnd17_ttmrev\` | ac=0 uc=0 cov=0.9291 | unbounded | - | Revenue over the trailing 12 months; units: millions
- \`fnd17_adivshr\` | ac=1 uc=1 cov=0.5769 | unbounded | SP | Dividend per share - most recent fiscal year
- \`fnd17_aintexpz\` | ac=1 uc=1 cov=0.7187 | unbounded | SP | Total interest expense for the most recent fiscal year
- \`fnd17_ainvturn\` | ac=1 uc=1 cov=0.5246 | [0, inf) | SP | Inventory turnover - most recent fiscal year
- \`fnd17_aptmgnpct2\` | ac=1 uc=1 cov=0.8976 | [-1, 1] | - | Pretax Margin - 2nd historical fiscal year
- \`fnd17_arecturn\` | ac=1 uc=1 cov=0.7807 | [0, inf) | SP | Receivables turnover - most recent fiscal year
- \`fnd17_atotce\` | ac=1 uc=1 cov=0.9372 | unbounded | - | Common equity (book value) - most recent fiscal year
- \`fnd17_cainq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income available to common shareholders for the most recent quarter
- \`fnd17_divnq\` | ac=1 uc=1 cov=0.4933 | [0, inf) | SP | Dividend - next quarterly declared
- \`fnd17_epschngyri\` | ac=1 uc=1 cov=0.9644 | [0, inf) | - | EPS Change % - year to date
- \`fnd17_inq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income (earnings after taxes) for the most recent quarter
- \`fnd17_mtpbshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding basic, average prior trailing 12 months
- \`fnd17_mtpshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding, average prior trailing 12 months
- \`fnd17_mttshs\` | ac=1 uc=1 cov=0.9291 | unbounded | - | Shares outstanding - average trailing 12 month
- \`fnd17_netdebt_a\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net debt (total debt minus cash and equivalents) for the last fiscal year
- \`fnd17_pxedrmtt\` | ac=1 uc=1 cov=0.3593 | unbounded | SP | Research and development expense over the trailing 12 months; units: millions
- \`fnd17_pxedrq\` | ac=1 uc=1 cov=0.3607 | unbounded | SP | Research and development expense for the most recent quarter
- \`fnd17_qcogs\` | ac=1 uc=1 cov=0.7536 | unbounded | SP | Cost of goods sold for the most recent quarter
- \`fnd17_qcurratio2\` | ac=1 uc=1 cov=0.7187 | [0, inf) | SP | Current ratio - most recent quarter, 1 year ago
- \`fnd17_qe2dtlq\` | ac=1 uc=1 cov=0.8978 | [0, inf) | - | Long-term debt to shareholder equity ratio for the most recent quarter
- \`fnd17_qtotd2eq\` | ac=1 uc=1 cov=0.8982 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter
- \`fnd17_revgrpct\` | ac=1 uc=1 cov=0.8517 | [-1, 1] | - | Three-year revenue growth rate (percent)
- \`fnd17_revps5ygr\` | ac=1 uc=1 cov=0.7825 | [-1, 1] | SP | Five-year growth rate of revenue per share
- \`fnd17_shboutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding basic, average, most recent quarter
- \`fnd17_shsoutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding, average, most recent quarter
- \`fnd17_tcpngmpoa\` | ac=1 uc=1 cov=0.901 | [-1, 1] | - | Operating margin - 1st historical fiscal year
- \`fnd17_ttmintcov\` | ac=1 uc=1 cov=0.6489 | [0, inf) | SP | Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months
- \`fnd17_ttmpayrat\` | ac=1 uc=1 cov=0.6747 | [-1, 1] | SP | Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings
- \`fnd17_ttmtaxrate\` | ac=1 uc=1 cov=0.6626 | [0, inf) | SP | Tax rate - trailing 12 month
- \`fnd17_zpxetniq\` | ac=1 uc=1 cov=0.6641 | unbounded | SP | Total interest expense for the most recent quarter
- \`fnd17_2qe2dtlq\` | ac=2 uc=2 cov=0.8721 | [0, inf) | - | Long-term debt to equity ratio for the most recent quarter one year ago
- \`fnd17_aniac\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income available to common shareholders for the most recent fiscal year
- \`fnd17_aniexclxor\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income excluding extraordinary items for the most recent fiscal year
- \`fnd17_aninorm\` | ac=2 uc=1 cov=0.9361 | unbounded | - | Net income after taxes excluding unusual or one-time items for the most recent fiscal year
- \`fnd17_arev\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total revenue (sales) for the most recent fiscal year
- \`fnd17_arevps\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Revenue per share for the most recent fiscal year
- \`fnd17_aroapct\` | ac=2 uc=2 cov=0.9313 | unbounded | - | Return on average assets for the most recent fiscal year
- \`fnd17_atotd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total debt - most recent fiscal year
- \`fnd17_atotd2eq\` | ac=2 uc=2 cov=0.8965 | unbounded | - | Total debt to shareholders’ equity for the most recent fiscal year
- \`fnd17_atotltd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Long-term debt (total) - most recent fiscal year
- \`fnd17_float\` | ac=2 uc=2 cov=0.9372 | unbounded | - | Public float (shares available for trading)
- \`fnd17_ghcspea\` | ac=2 uc=1 cov=0.9285 | [-1, 1] | - | Year-over-year percent change in annual earnings per share compared to the previous fiscal year
- \`fnd17_mttbshs\` | ac=2 uc=2 cov=0.9291 | unbounded | - | Shares outstanding basic, average trailing 12 months
- \`fnd17_netdebt_i\` | ac=2 uc=2 cov=0.9367 | unbounded | - | Net debt (total debt minus cash and equivalents) for the latest interim period
- \`fnd17_qcurratio\` | ac=2 uc=2 cov=0.7445 | [0, inf) | SP | Current ratio for the most recent quarter
- \`fnd17_qquickrati\` | ac=2 uc=2 cov=0.5116 | [0, inf) | SP | Quick ratio for the most recent quarter
- \`fnd17_qrevpsna\` | ac=2 uc=2 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (not annualized)
- \`fnd17_qroipct\` | ac=2 uc=2 cov=0.8364 | unbounded | - | Return on investment for the most recent quarter (annualized)
- \`fnd17_qtotce\` | ac=2 uc=1 cov=0.9366 | unbounded | - | Common equity (book value) - most recent quarter
- \`fnd17_qtotd2eq2\` | ac=2 uc=1 cov=0.8722 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter, measured one year ago
- \`fnd17_revtrendgr\` | ac=2 uc=2 cov=0.7834 | [-1, 1] | SP | Five-year revenue growth rate
- \`fnd17_ry5ngmpo\` | ac=2 uc=2 cov=0.791 | [-1, 1] | SP | Operating Margin - 5 year average
- \`fnd17_rygnhcspe\` | ac=2 uc=2 cov=0.9264 | [-1, 1] | - | Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year
- \`fnd17_shsboutavg\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Shares outstanding Basic - average, most recent fiscal year
- \`fnd17_tcpngmpna\` | ac=2 uc=2 cov=0.903 | [-1, 1] | - | Net Profit Margin % - 1st historical fiscal year
- \`fnd17_tcpngmpoq\` | ac=2 uc=2 cov=0.9004 | [-1, 1] | - | Operating margin - most recent quarter
- \`fnd17_2tcpngmpoa\` | ac=3 uc=3 cov=0.8957 | [-1, 1] | - | Operating Margin - 2nd historical fiscal year
- \`fnd17_aintcov\` | ac=3 uc=3 cov=0.6199 | [0, inf) | SP | Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense
- \`fnd17_aptmgnpct\` | ac=3 uc=3 cov=0.903 | [-1, 1] | - | Pretax margin - 1st historical fiscal year
- \`fnd17_beta\` | ac=3 uc=3 cov=0.7942 | unbounded | SP | Beta
- \`fnd17_ngmpnmtt\` | ac=3 uc=3 cov=0.9003 | [-1, 1] | - | Net Profit Margin % - trailing 12 month
- \`fnd17_npmtrendgr\` | ac=3 uc=2 cov=0.5376 | [-1, 1] | SP | Five-year growth rate of net profit margin
- \`fnd17_ptmrev\` | ac=3 uc=1 cov=0.9094 | unbounded | - | Revenue for the prior trailing twelve months
- \`fnd17_qastturn\` | ac=3 uc=3 cov=0.8633 | [0, inf) | - | Asset turnover ratio for the most recent quarter, annualized
- \`fnd17_qtotd2ast\` | ac=3 uc=2 cov=0.936 | unbounded | - | Total debt to total assets for the most recent quarter
- \`fnd17_qtotd2cap\` | ac=3 uc=1 cov=0.8646 | [0, inf) | - | Ratio of total debt to total capital for the most recent quarter
- \`fnd17_qtrperiods\` | ac=3 uc=2 cov=0.9377 | unbounded | - | Number of historical quarterly periods available for the company
- \`fnd17_revchngin\` | ac=3 uc=3 cov=0.8974 | [-1, 1] | - | Percentage change in revenue versus the immediately preceding quarter
- \`fnd17_revchngyr\` | ac=3 uc=3 cov=0.8931 | [-1, 1] | - | Percent change in revenue for the most recent quarter versus the same quarter a year ago
- \`fnd17_revtrend10\` | ac=3 uc=3 cov=0.6482 | [-1, 1] | SP | Ten-year revenue growth rate
- \`fnd17_shsoutbs\` | ac=3 uc=3 cov=0.9361 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter
- \`fnd17_ttmgrosmgn\` | ac=3 uc=2 cov=0.748 | [-1, 1] | SP | Gross margin over the trailing 12 months
- \`fnd17_ttmopmgn\` | ac=3 uc=3 cov=0.8993 | [-1, 1] | - | Operating margin over the trailing 12 months
- \`fnd17_ttmroepct\` | ac=3 uc=2 cov=0.8693 | unbounded | - | Return on average equity - trailing 12 month
- \`fnd17_annperiods\` | ac=4 uc=4 cov=0.9384 | unbounded | - | Number of historical periods - Annual
- \`fnd17_ataxrate\` | ac=4 uc=3 cov=0.6572 | [-1, 1] | SP | Effective tax rate for the most recent fiscal year
- \`fnd17_atotd2ast\` | ac=4 uc=3 cov=0.937 | unbounded | - | Total debt to total assets for the most recent fiscal year
- \`fnd17_atotd2cap\` | ac=4 uc=2 cov=0.8641 | unbounded | - | Total debt to total capital percentage, most recent fiscal year
- \`fnd17_gvay5dly\` | ac=4 uc=1 cov=0.4381 | [0, inf) | SP | Dividend yield - 5 year average
- \`fnd17_shsout\` | ac=4 uc=3 cov=0.9385 | unbounded | - | Shares outstanding, current
- \`fnd17_tcpaormtt\` | ac=4 uc=3 cov=0.9072 | unbounded | - | Return on average assets over the trailing 12 months (percentage)
- \`fnd17_tcpaorq\` | ac=4 uc=3 cov=0.9316 | unbounded | - | Return on average assets for the most recent quarter (annualized)
- \`fnd17_ttmrevps\` | ac=4 uc=3 cov=0.929 | unbounded | - | Revenue/share - trailing 12 month
- \`fnd17_ttmsga2rev\` | ac=4 uc=1 cov=0.7937 | unbounded | SP | SG&A expenses / net sales - trailing 12 month
- \`fnd17_acurratio\` | ac=5 uc=5 cov=0.7448 | [0, inf) | SP | Current ratio for the most recent fiscal year (current assets divided by current liabilities)
- \`fnd17_fcf1a\` | ac=5 uc=4 cov=0.9353 | unbounded | - | Free cash flow - most recent fiscal year
- \`fnd17_qcash\` | ac=5 uc=5 cov=0.9357 | unbounded | - | Cash and cash equivalents for the most recent quarter
- \`fnd17_qroepct\` | ac=5 uc=2 cov=0.8892 | unbounded | - | Return on average equity for the most recent quarter (annualized)
- \`fnd17_rhsfcfq\` | ac=5 uc=5 cov=0.9159 | unbounded | - | Free cash flow per share for the most recent quarter, annualized
- \`fnd17_shsoutavg\` | ac=5 uc=2 cov=0.9361 | unbounded | - | Shares outstanding - average, most recent fiscal year
- \`fnd17_ttmroipct\` | ac=5 uc=1 cov=0.8134 | unbounded | - | Return on investment - trailing 12 month
- \`fnd17_aastturn\` | ac=6 uc=6 cov=0.8626 | [0, inf) | - | Asset turnover - most recent fiscal year
- \`fnd17_apayratio2\` | ac=6 uc=1 cov=0.6523 | [0, inf) | SP | Payout ratio for the prior fiscal year
- \`fnd17_epschngin\` | ac=6 uc=5 cov=0.9307 | [-1, 1] | - | Percent change in EPS from the prior quarter
- \`fnd17_hsca\` | ac=6 uc=3 cov=0.9357 | unbounded | - | Cash and cash equivalents at fiscal year-end
- \`fnd17_rhsfcfmtt\` | ac=6 uc=6 cov=0.9045 | unbounded | - | Free cash flow per share over the trailing 12 months
- \`fnd17_shsoutbs2\` | ac=6 uc=1 cov=0.9082 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter one year ago
- \`fnd17_fcfq\` | ac=7 uc=6 cov=0.9216 | unbounded | - | Free cash flow for the most recent quarter
- \`fnd17_gmntrendgr\` | ac=7 uc=3 cov=0.6518 | [-1, 1] | SP | Five-year growth rate of gross margin
- \`fnd17_qgrosmgn\` | ac=7 uc=3 cov=0.7501 | [-1, 1] | SP | Gross Margin - most recent quarter
- \`fnd17_aniacinclx\` | ac=8 uc=1 cov=0.9361 | unbounded | - | Net income available to common including extraordinary items for the most recent fiscal year
- \`fnd17_aroipct\` | ac=8 uc=2 cov=0.8348 | unbounded | - | Return on investment for the most recent fiscal year
- \`fnd17_asga2rev\` | ac=8 uc=5 cov=0.8028 | unbounded | - | SG&A expenses / net sales - most recent fiscal year
- \`fnd17_ngmpnmtp\` | ac=8 uc=4 cov=0.8831 | [-1, 1] | - | Net Profit Margin % - prior trailing 12 month
- \`fnd17_ttmrecturn\` | ac=8 uc=1 cov=0.7561 | [0, inf) | SP | Receivables turnover - trailing 12 months
- \`fnd17_voctniq\` | ac=8 uc=3 cov=0.6673 | [0, inf) | SP | Interest coverage ratio for the most recent quarter
- \`fnd17_ani\` | ac=9 uc=2 cov=0.9361 | unbounded | - | Net income (earnings after taxes) for the most recent fiscal year
- \`fnd17_qtotltd\` | ac=9 uc=1 cov=0.9357 | unbounded | - | Long-term debt (total), most recent quarter
- \`fnd17_fcfmtt\` | ac=10 uc=6 cov=0.9102 | unbounded | - | Free cash flow - trailing 12 months
- \`fnd17_qsga2rev\` | ac=11 uc=5 cov=0.7944 | unbounded | SP | SG&A expenses / net sales - most recent quarter
- \`fnd17_a2netmrgn\` | ac=12 uc=7 cov=0.8976 | [-1, 1] | - | Net Profit Margin % - 2nd historical fiscal year
- \`fnd17_sphsca\` | ac=13 uc=6 cov=0.9351 | unbounded | - | Cash per share - most recent fiscal year
- \`fnd17_ata\` | ac=14 uc=4 cov=0.9372 | unbounded | - | Total assets - most recent fiscal year
- \`fnd17_beta_up\` | ac=14 uc=2 cov=0.8872 | unbounded | - | Upside beta calculated during up-market periods
- \`fnd17_sphscq\` | ac=14 uc=6 cov=0.935 | unbounded | - | Cash and equivalents per share for the most recent quarter
- \`fnd17_pxedrmtp\` | ac=20 uc=8 cov=0.3487 | unbounded | SP | Research and development expense for the prior trailing twelve months
- \`fnd17_acogs\` | ac=22 uc=4 cov=0.754 | unbounded | SP | Cost of goods sold for the most recent fiscal year
- \`fnd17_pxedra\` | ac=22 uc=7 cov=0.3881 | unbounded | SP | Research and development expense for the most recent fiscal year

Audit this Phase-0 prototype:
  id: ${s.id}
  question_type: ${s.question_type}
  expression: ${s.expression}
  fields_used: ${JSON.stringify(s.fields_used)}
  economic_mechanism: ${s.economic_mechanism}

Checklist - your verdict must be grounded in each item:
1. FIELD TRUTH: does every fnd17_ id in the expression appear VERBATIM in the metadata table above? Does fields_used match EXACTLY the fields the expression uses (no more, no fewer)?
2. ZERO PV CONTAMINATION: any price / volume / market cap / valuation-multiple field, or any external PV field (close/open/high/low/vwap/returns/volume/cap/adv20)?
3. FASTEXPR SYNTAX: balanced parens, legal operator names, group_* takes a BARE literal (market/sector/industry/subindustry, no quotes), and the whole thing parses as a Python expression.
4. OPERATOR COUNT <= 4. Count the call parentheses.
5. FIELD COUNT in {2,3}.
6. WINDOW WHITELIST: every time-window argument in {3,5,10,20,60,120,252}. (ts_backfill's lookback is a gap-fill length rather than a window, but keep it 252 for consistency; if it is 250/63/126 just correct it to 252 and note it in issues.)
7. OUTERMOST ZERO-MEAN: the outermost operator must be one of zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff. group_rank or rank at the top => REJECT.
8. FOUR AXIOMS:
   - axiom 1 (sign / zero conservation): are ratio fields de-meaned before any power or multiply? Is there a multiply of two signed variables? Is any multiply weight term strictly positive?
   - axiom 2 (position symmetry): do sparse fields (cov < 0.80) need ts_backfill to avoid tied-zeros dead weight?
   - axiom 3 (Occam): field count, operator count, legal windows, no grid fiddling.
   - axiom 4 (anti-crowding): what is the ac of each field used? Is it <= 5? If a field has ac > 5, is it wrapped in a second-order surprise (twin pair / own-history deviation)?
9. BANNED OPERATORS: group_neutralize / bucket / add(rank,rank) / trade_when / hump / signed_power / quantile / subtract(x,0.5).

Any hard violation => verdict REJECT with a locatable issue string.
If the ONLY problem is mechanically fixable (a window value, an operator alias, quotes around a group name, a field id typo), give the corrected expression AND still pass, noting what you changed in issues. If the fix would change the economics, REJECT instead.

Return the structured JSON only.`,
  opts: { label: `audit:${s.id}`, phase: 'TechAudit', schema: AUDIT_SCHEMA, agentType: 'general-purpose' },
}))

// ★ parallel() 保序：失败的 thunk 变成 null 而不是被删除。
//   所以这里**不能**先 filter(Boolean) 再按下标取值 —— 必须先按原位取值再过滤。
const auditRaw = await parallelOrdered(auditPromises)
const auditById = new Map()
auditRaw.forEach((a, i) => { if (a && seedPool[i]) auditById.set(seedPool[i].id, a) })

const passed = []
const rejected = []
seedPool.forEach((s) => {
  const a = auditById.get(s.id)
  if (!a) { rejected.push({ seed: s, reason: 'audit agent returned nothing' }); return }
  if (a.verdict === 'PASS') passed.push({ ...s, expression: a.corrected_expression || s.expression, audit: a })
  else rejected.push({ seed: s, reason: (a.issues || []).join('; '), audit: a })
})
log(`Tech audit: ${passed.length} passed / ${rejected.length} rejected`)

phase('RedTeam')

const RT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'REJECT'] },
    causal_assessment: { type: 'string', description: 'Chinese: is the causal chain self-consistent, who is the counterparty, what bias/friction keeps it alive in OS' },
    fidelity_assessment: { type: 'string', description: 'Chinese: does the AST compute 100% what the hypothesis claims' },
    rejection_reason: { type: 'string', description: 'If REJECT, one line stating the flaw' },
    counterparty_confirmed: { type: 'boolean' },
    fidelity_confirmed: { type: 'boolean' },
    parsimony_confirmed: { type: 'boolean' },
    final_expression: { type: 'string' },
  },
  required: ['verdict', 'causal_assessment', 'fidelity_assessment', 'rejection_reason', 'counterparty_confirmed', 'fidelity_confirmed', 'parsimony_confirmed', 'final_expression'],
  additionalProperties: false,
}

const rtPromises = passed.map((s) => () => agentRetry({
  prompt:
`You are the AEGIS double-blind red-team auditor - the overfitting and hallucination shredder. You hold a veto.

READ FIRST (use the Read tool): "D:\\python\\Lib\\site-packages\\cnhkmcp\\untracked\\APP\\.agents\\quant_framework\\campaigns\\aegis_fnd17\\CAMPAIGN_CONTEXT.md"
(the campaign contract: four axioms, gates, and the falsified-pattern list - use it to judge whether this re-burns a known failure)

PHYSICAL ISOLATION RULE: you must NOT see any backtest metric (Sharpe / Fitness / Margin / PnL / Drawdown do not exist in Stage 2 - it is zero-backtest by design). Judge only from three things: the physical meaning of the fields, the submitted causal micro-hypothesis, and the final AST.

Candidate under review:
  id: ${s.id}
  question_type: ${s.question_type}
  expression: ${s.expression}
  fields_used: ${JSON.stringify(s.fields_used)}
  economic_mechanism: ${s.economic_mechanism}
  counterparty: ${s.counterparty}

Authoritative metadata for the fields it uses (and for every candidate alternative field):
\`field_id | ac=alphaCount uc=userCount cov=coverage | domain | sparse | description\`

- \`fnd17_aniacnorm\` | ac=0 uc=0 cov=0.9361 | unbounded | - | Normalized net income available to common (excludes unusual/one-time items) for the most recent fiscal year
- \`fnd17_aquickrati\` | ac=0 uc=0 cov=0.5167 | [0, inf) | SP | Quick ratio for the most recent fiscal year: (cash + short-term investments + accounts receivable) divided by current liabilities
- \`fnd17_atmtt\` | ac=0 uc=0 cov=0.9083 | unbounded | - | Total assets, trailing twelve months
- \`fnd17_beta_down\` | ac=0 uc=0 cov=0.8424 | unbounded | - | Downside beta calculated during down-market periods
- \`fnd17_dai\` | ac=0 uc=0 cov=0.4849 | [0, inf) | SP | Dividend rate, indicated annual
- \`fnd17_div\` | ac=0 uc=0 cov=0.5281 | unbounded | SP | Dividends paid from the statement of cash flows - most recent fiscal year
- \`fnd17_ghcspemtt\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing-twelve-month EPS versus the prior trailing-twelve-month period
- \`fnd17_nichngin\` | ac=0 uc=0 cov=0.9307 | [-1, 1] | - | Percent change in net income versus the prior quarter
- \`fnd17_nichngyr\` | ac=0 uc=0 cov=0.9266 | [-1, 1] | - | Percent change in net income for the most recent quarter versus the same quarter a year ago
- \`fnd17_ptmintcov\` | ac=0 uc=0 cov=0.6415 | [0, inf) | SP | Interest coverage for the prior trailing 12 months, defined as EBIT divided by interest expense
- \`fnd17_ptmroepct\` | ac=0 uc=0 cov=0.8297 | unbounded | - | Return on average equity for the prior trailing twelve months
- \`fnd17_qinvturn\` | ac=0 uc=0 cov=0.518 | [0, inf) | SP | Inventory turnover - most recent quarter (annualized)
- \`fnd17_qquickrat2\` | ac=0 uc=0 cov=0.4989 | [0, inf) | SP | Quick ratio for the most recent quarter one year ago
- \`fnd17_qrecturn\` | ac=0 uc=0 cov=0.774 | [0, inf) | SP | Receivables turnover - most recent quarter (annualized)
- \`fnd17_qrev\` | ac=0 uc=0 cov=0.9371 | unbounded | - | Revenue for the most recent quarter
- \`fnd17_qrevps\` | ac=0 uc=0 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (annualized)
- \`fnd17_qtotd\` | ac=0 uc=0 cov=0.936 | unbounded | - | Total debt - most recent quarter
- \`fnd17_spdq\` | ac=0 uc=0 cov=0.9275 | [0, inf) | - | Dividend - most recent quarter
- \`fnd17_tcpaormtp\` | ac=0 uc=0 cov=0.8638 | unbounded | - | Return on average assets for the prior trailing twelve months
- \`fnd17_ttmastturn\` | ac=0 uc=0 cov=0.8396 | [0, inf) | - | Asset turnover - trailing 12 months
- \`fnd17_ttmcogs\` | ac=0 uc=0 cov=0.7509 | unbounded | SP | Cost of goods sold over the trailing 12 months
- \`fnd17_ttmdivshr\` | ac=0 uc=0 cov=0.9286 | unbounded | - | Dividends per share - trailing 12 months
- \`fnd17_ttmintexp\` | ac=0 uc=0 cov=0.677 | unbounded | SP | Interest expense over the trailing 12 months
- \`fnd17_ttminvturn\` | ac=0 uc=0 cov=0.5071 | [0, inf) | SP | Inventory turnover - trailing 12 months
- \`fnd17_ttmnichg\` | ac=0 uc=0 cov=0.9059 | [-1, 1] | - | Percent change in trailing 12-month net income versus the prior TTM
- \`fnd17_ttmrev\` | ac=0 uc=0 cov=0.9291 | unbounded | - | Revenue over the trailing 12 months; units: millions
- \`fnd17_adivshr\` | ac=1 uc=1 cov=0.5769 | unbounded | SP | Dividend per share - most recent fiscal year
- \`fnd17_aintexpz\` | ac=1 uc=1 cov=0.7187 | unbounded | SP | Total interest expense for the most recent fiscal year
- \`fnd17_ainvturn\` | ac=1 uc=1 cov=0.5246 | [0, inf) | SP | Inventory turnover - most recent fiscal year
- \`fnd17_aptmgnpct2\` | ac=1 uc=1 cov=0.8976 | [-1, 1] | - | Pretax Margin - 2nd historical fiscal year
- \`fnd17_arecturn\` | ac=1 uc=1 cov=0.7807 | [0, inf) | SP | Receivables turnover - most recent fiscal year
- \`fnd17_atotce\` | ac=1 uc=1 cov=0.9372 | unbounded | - | Common equity (book value) - most recent fiscal year
- \`fnd17_cainq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income available to common shareholders for the most recent quarter
- \`fnd17_divnq\` | ac=1 uc=1 cov=0.4933 | [0, inf) | SP | Dividend - next quarterly declared
- \`fnd17_epschngyri\` | ac=1 uc=1 cov=0.9644 | [0, inf) | - | EPS Change % - year to date
- \`fnd17_inq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net income (earnings after taxes) for the most recent quarter
- \`fnd17_mtpbshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding basic, average prior trailing 12 months
- \`fnd17_mtpshs\` | ac=1 uc=1 cov=0.9092 | unbounded | - | Shares outstanding, average prior trailing 12 months
- \`fnd17_mttshs\` | ac=1 uc=1 cov=0.9291 | unbounded | - | Shares outstanding - average trailing 12 month
- \`fnd17_netdebt_a\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Net debt (total debt minus cash and equivalents) for the last fiscal year
- \`fnd17_pxedrmtt\` | ac=1 uc=1 cov=0.3593 | unbounded | SP | Research and development expense over the trailing 12 months; units: millions
- \`fnd17_pxedrq\` | ac=1 uc=1 cov=0.3607 | unbounded | SP | Research and development expense for the most recent quarter
- \`fnd17_qcogs\` | ac=1 uc=1 cov=0.7536 | unbounded | SP | Cost of goods sold for the most recent quarter
- \`fnd17_qcurratio2\` | ac=1 uc=1 cov=0.7187 | [0, inf) | SP | Current ratio - most recent quarter, 1 year ago
- \`fnd17_qe2dtlq\` | ac=1 uc=1 cov=0.8978 | [0, inf) | - | Long-term debt to shareholder equity ratio for the most recent quarter
- \`fnd17_qtotd2eq\` | ac=1 uc=1 cov=0.8982 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter
- \`fnd17_revgrpct\` | ac=1 uc=1 cov=0.8517 | [-1, 1] | - | Three-year revenue growth rate (percent)
- \`fnd17_revps5ygr\` | ac=1 uc=1 cov=0.7825 | [-1, 1] | SP | Five-year growth rate of revenue per share
- \`fnd17_shboutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding basic, average, most recent quarter
- \`fnd17_shsoutavgq\` | ac=1 uc=1 cov=0.9373 | unbounded | - | Shares outstanding, average, most recent quarter
- \`fnd17_tcpngmpoa\` | ac=1 uc=1 cov=0.901 | [-1, 1] | - | Operating margin - 1st historical fiscal year
- \`fnd17_ttmintcov\` | ac=1 uc=1 cov=0.6489 | [0, inf) | SP | Interest coverage ratio (EBIT divided by interest expense) over the trailing 12 months
- \`fnd17_ttmpayrat\` | ac=1 uc=1 cov=0.6747 | [-1, 1] | SP | Payout ratio over the trailing 12 months, defined as cash dividends as a percent of earnings
- \`fnd17_ttmtaxrate\` | ac=1 uc=1 cov=0.6626 | [0, inf) | SP | Tax rate - trailing 12 month
- \`fnd17_zpxetniq\` | ac=1 uc=1 cov=0.6641 | unbounded | SP | Total interest expense for the most recent quarter
- \`fnd17_2qe2dtlq\` | ac=2 uc=2 cov=0.8721 | [0, inf) | - | Long-term debt to equity ratio for the most recent quarter one year ago
- \`fnd17_aniac\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income available to common shareholders for the most recent fiscal year
- \`fnd17_aniexclxor\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Net income excluding extraordinary items for the most recent fiscal year
- \`fnd17_aninorm\` | ac=2 uc=1 cov=0.9361 | unbounded | - | Net income after taxes excluding unusual or one-time items for the most recent fiscal year
- \`fnd17_arev\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total revenue (sales) for the most recent fiscal year
- \`fnd17_arevps\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Revenue per share for the most recent fiscal year
- \`fnd17_aroapct\` | ac=2 uc=2 cov=0.9313 | unbounded | - | Return on average assets for the most recent fiscal year
- \`fnd17_atotd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Total debt - most recent fiscal year
- \`fnd17_atotd2eq\` | ac=2 uc=2 cov=0.8965 | unbounded | - | Total debt to shareholders’ equity for the most recent fiscal year
- \`fnd17_atotltd\` | ac=2 uc=2 cov=0.9371 | unbounded | - | Long-term debt (total) - most recent fiscal year
- \`fnd17_float\` | ac=2 uc=2 cov=0.9372 | unbounded | - | Public float (shares available for trading)
- \`fnd17_ghcspea\` | ac=2 uc=1 cov=0.9285 | [-1, 1] | - | Year-over-year percent change in annual earnings per share compared to the previous fiscal year
- \`fnd17_mttbshs\` | ac=2 uc=2 cov=0.9291 | unbounded | - | Shares outstanding basic, average trailing 12 months
- \`fnd17_netdebt_i\` | ac=2 uc=2 cov=0.9367 | unbounded | - | Net debt (total debt minus cash and equivalents) for the latest interim period
- \`fnd17_qcurratio\` | ac=2 uc=2 cov=0.7445 | [0, inf) | SP | Current ratio for the most recent quarter
- \`fnd17_qquickrati\` | ac=2 uc=2 cov=0.5116 | [0, inf) | SP | Quick ratio for the most recent quarter
- \`fnd17_qrevpsna\` | ac=2 uc=2 cov=0.937 | unbounded | - | Revenue/share - most recent quarter (not annualized)
- \`fnd17_qroipct\` | ac=2 uc=2 cov=0.8364 | unbounded | - | Return on investment for the most recent quarter (annualized)
- \`fnd17_qtotce\` | ac=2 uc=1 cov=0.9366 | unbounded | - | Common equity (book value) - most recent quarter
- \`fnd17_qtotd2eq2\` | ac=2 uc=1 cov=0.8722 | [0, inf) | - | Total debt to shareholder equity ratio for the most recent quarter, measured one year ago
- \`fnd17_revtrendgr\` | ac=2 uc=2 cov=0.7834 | [-1, 1] | SP | Five-year revenue growth rate
- \`fnd17_ry5ngmpo\` | ac=2 uc=2 cov=0.791 | [-1, 1] | SP | Operating Margin - 5 year average
- \`fnd17_rygnhcspe\` | ac=2 uc=2 cov=0.9264 | [-1, 1] | - | Year-over-year percent change in EPS for the most recent quarter compared to the same quarter last year
- \`fnd17_shsboutavg\` | ac=2 uc=2 cov=0.9361 | unbounded | - | Shares outstanding Basic - average, most recent fiscal year
- \`fnd17_tcpngmpna\` | ac=2 uc=2 cov=0.903 | [-1, 1] | - | Net Profit Margin % - 1st historical fiscal year
- \`fnd17_tcpngmpoq\` | ac=2 uc=2 cov=0.9004 | [-1, 1] | - | Operating margin - most recent quarter
- \`fnd17_2tcpngmpoa\` | ac=3 uc=3 cov=0.8957 | [-1, 1] | - | Operating Margin - 2nd historical fiscal year
- \`fnd17_aintcov\` | ac=3 uc=3 cov=0.6199 | [0, inf) | SP | Interest coverage ratio for the most recent fiscal year, calculated as EBIT divided by interest expense
- \`fnd17_aptmgnpct\` | ac=3 uc=3 cov=0.903 | [-1, 1] | - | Pretax margin - 1st historical fiscal year
- \`fnd17_beta\` | ac=3 uc=3 cov=0.7942 | unbounded | SP | Beta
- \`fnd17_ngmpnmtt\` | ac=3 uc=3 cov=0.9003 | [-1, 1] | - | Net Profit Margin % - trailing 12 month
- \`fnd17_npmtrendgr\` | ac=3 uc=2 cov=0.5376 | [-1, 1] | SP | Five-year growth rate of net profit margin
- \`fnd17_ptmrev\` | ac=3 uc=1 cov=0.9094 | unbounded | - | Revenue for the prior trailing twelve months
- \`fnd17_qastturn\` | ac=3 uc=3 cov=0.8633 | [0, inf) | - | Asset turnover ratio for the most recent quarter, annualized
- \`fnd17_qtotd2ast\` | ac=3 uc=2 cov=0.936 | unbounded | - | Total debt to total assets for the most recent quarter
- \`fnd17_qtotd2cap\` | ac=3 uc=1 cov=0.8646 | [0, inf) | - | Ratio of total debt to total capital for the most recent quarter
- \`fnd17_qtrperiods\` | ac=3 uc=2 cov=0.9377 | unbounded | - | Number of historical quarterly periods available for the company
- \`fnd17_revchngin\` | ac=3 uc=3 cov=0.8974 | [-1, 1] | - | Percentage change in revenue versus the immediately preceding quarter
- \`fnd17_revchngyr\` | ac=3 uc=3 cov=0.8931 | [-1, 1] | - | Percent change in revenue for the most recent quarter versus the same quarter a year ago
- \`fnd17_revtrend10\` | ac=3 uc=3 cov=0.6482 | [-1, 1] | SP | Ten-year revenue growth rate
- \`fnd17_shsoutbs\` | ac=3 uc=3 cov=0.9361 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter
- \`fnd17_ttmgrosmgn\` | ac=3 uc=2 cov=0.748 | [-1, 1] | SP | Gross margin over the trailing 12 months
- \`fnd17_ttmopmgn\` | ac=3 uc=3 cov=0.8993 | [-1, 1] | - | Operating margin over the trailing 12 months
- \`fnd17_ttmroepct\` | ac=3 uc=2 cov=0.8693 | unbounded | - | Return on average equity - trailing 12 month
- \`fnd17_annperiods\` | ac=4 uc=4 cov=0.9384 | unbounded | - | Number of historical periods - Annual
- \`fnd17_ataxrate\` | ac=4 uc=3 cov=0.6572 | [-1, 1] | SP | Effective tax rate for the most recent fiscal year
- \`fnd17_atotd2ast\` | ac=4 uc=3 cov=0.937 | unbounded | - | Total debt to total assets for the most recent fiscal year
- \`fnd17_atotd2cap\` | ac=4 uc=2 cov=0.8641 | unbounded | - | Total debt to total capital percentage, most recent fiscal year
- \`fnd17_gvay5dly\` | ac=4 uc=1 cov=0.4381 | [0, inf) | SP | Dividend yield - 5 year average
- \`fnd17_shsout\` | ac=4 uc=3 cov=0.9385 | unbounded | - | Shares outstanding, current
- \`fnd17_tcpaormtt\` | ac=4 uc=3 cov=0.9072 | unbounded | - | Return on average assets over the trailing 12 months (percentage)
- \`fnd17_tcpaorq\` | ac=4 uc=3 cov=0.9316 | unbounded | - | Return on average assets for the most recent quarter (annualized)
- \`fnd17_ttmrevps\` | ac=4 uc=3 cov=0.929 | unbounded | - | Revenue/share - trailing 12 month
- \`fnd17_ttmsga2rev\` | ac=4 uc=1 cov=0.7937 | unbounded | SP | SG&A expenses / net sales - trailing 12 month
- \`fnd17_acurratio\` | ac=5 uc=5 cov=0.7448 | [0, inf) | SP | Current ratio for the most recent fiscal year (current assets divided by current liabilities)
- \`fnd17_fcf1a\` | ac=5 uc=4 cov=0.9353 | unbounded | - | Free cash flow - most recent fiscal year
- \`fnd17_qcash\` | ac=5 uc=5 cov=0.9357 | unbounded | - | Cash and cash equivalents for the most recent quarter
- \`fnd17_qroepct\` | ac=5 uc=2 cov=0.8892 | unbounded | - | Return on average equity for the most recent quarter (annualized)
- \`fnd17_rhsfcfq\` | ac=5 uc=5 cov=0.9159 | unbounded | - | Free cash flow per share for the most recent quarter, annualized
- \`fnd17_shsoutavg\` | ac=5 uc=2 cov=0.9361 | unbounded | - | Shares outstanding - average, most recent fiscal year
- \`fnd17_ttmroipct\` | ac=5 uc=1 cov=0.8134 | unbounded | - | Return on investment - trailing 12 month
- \`fnd17_aastturn\` | ac=6 uc=6 cov=0.8626 | [0, inf) | - | Asset turnover - most recent fiscal year
- \`fnd17_apayratio2\` | ac=6 uc=1 cov=0.6523 | [0, inf) | SP | Payout ratio for the prior fiscal year
- \`fnd17_epschngin\` | ac=6 uc=5 cov=0.9307 | [-1, 1] | - | Percent change in EPS from the prior quarter
- \`fnd17_hsca\` | ac=6 uc=3 cov=0.9357 | unbounded | - | Cash and cash equivalents at fiscal year-end
- \`fnd17_rhsfcfmtt\` | ac=6 uc=6 cov=0.9045 | unbounded | - | Free cash flow per share over the trailing 12 months
- \`fnd17_shsoutbs2\` | ac=6 uc=1 cov=0.9082 | unbounded | - | Shares outstanding on the balance sheet, most recent quarter one year ago
- \`fnd17_fcfq\` | ac=7 uc=6 cov=0.9216 | unbounded | - | Free cash flow for the most recent quarter
- \`fnd17_gmntrendgr\` | ac=7 uc=3 cov=0.6518 | [-1, 1] | SP | Five-year growth rate of gross margin
- \`fnd17_qgrosmgn\` | ac=7 uc=3 cov=0.7501 | [-1, 1] | SP | Gross Margin - most recent quarter
- \`fnd17_aniacinclx\` | ac=8 uc=1 cov=0.9361 | unbounded | - | Net income available to common including extraordinary items for the most recent fiscal year
- \`fnd17_aroipct\` | ac=8 uc=2 cov=0.8348 | unbounded | - | Return on investment for the most recent fiscal year
- \`fnd17_asga2rev\` | ac=8 uc=5 cov=0.8028 | unbounded | - | SG&A expenses / net sales - most recent fiscal year
- \`fnd17_ngmpnmtp\` | ac=8 uc=4 cov=0.8831 | [-1, 1] | - | Net Profit Margin % - prior trailing 12 month
- \`fnd17_ttmrecturn\` | ac=8 uc=1 cov=0.7561 | [0, inf) | SP | Receivables turnover - trailing 12 months
- \`fnd17_voctniq\` | ac=8 uc=3 cov=0.6673 | [0, inf) | SP | Interest coverage ratio for the most recent quarter
- \`fnd17_ani\` | ac=9 uc=2 cov=0.9361 | unbounded | - | Net income (earnings after taxes) for the most recent fiscal year
- \`fnd17_qtotltd\` | ac=9 uc=1 cov=0.9357 | unbounded | - | Long-term debt (total), most recent quarter
- \`fnd17_fcfmtt\` | ac=10 uc=6 cov=0.9102 | unbounded | - | Free cash flow - trailing 12 months
- \`fnd17_qsga2rev\` | ac=11 uc=5 cov=0.7944 | unbounded | SP | SG&A expenses / net sales - most recent quarter
- \`fnd17_a2netmrgn\` | ac=12 uc=7 cov=0.8976 | [-1, 1] | - | Net Profit Margin % - 2nd historical fiscal year
- \`fnd17_sphsca\` | ac=13 uc=6 cov=0.9351 | unbounded | - | Cash per share - most recent fiscal year
- \`fnd17_ata\` | ac=14 uc=4 cov=0.9372 | unbounded | - | Total assets - most recent fiscal year
- \`fnd17_beta_up\` | ac=14 uc=2 cov=0.8872 | unbounded | - | Upside beta calculated during up-market periods
- \`fnd17_sphscq\` | ac=14 uc=6 cov=0.935 | unbounded | - | Cash and equivalents per share for the most recent quarter
- \`fnd17_pxedrmtp\` | ac=20 uc=8 cov=0.3487 | unbounded | SP | Research and development expense for the prior trailing twelve months
- \`fnd17_acogs\` | ac=22 uc=4 cov=0.754 | unbounded | SP | Cost of goods sold for the most recent fiscal year
- \`fnd17_pxedra\` | ac=22 uc=7 cov=0.3881 | unbounded | SP | Research and development expense for the most recent fiscal year

TWIN PAIRS available in this dataset (current vs the company OWN prior period):
  - fnd17_tcpaormtt (ac=4)  vs  fnd17_tcpaormtp (ac=0)   -- TTM return on average assets: now vs prior TTM
  - fnd17_ngmpnmtt (ac=3)  vs  fnd17_ngmpnmtp (ac=8)   -- TTM net profit margin: now vs prior TTM
  - fnd17_qtotd2eq (ac=1)  vs  fnd17_qtotd2eq2 (ac=2)   -- total debt / equity: now vs one year ago
  - fnd17_qcurratio (ac=2)  vs  fnd17_qcurratio2 (ac=1)   -- current ratio: now vs one year ago
  - fnd17_ttmintcov (ac=1)  vs  fnd17_ptmintcov (ac=0)   -- interest coverage: now vs prior TTM
  - fnd17_shsoutbs (ac=3)  vs  fnd17_shsoutbs2 (ac=6)   -- balance-sheet shares outstanding: now vs one year ago
  - fnd17_ttmrev (ac=0)  vs  fnd17_ptmrev (ac=3)   -- TTM revenue: now vs prior TTM

Interrogate on two axes:
1. IS THE CAUSAL ECONOMIC CHAIN SELF-CONSISTENT?
   - Why can this pattern make money? Specifically: why does the market price it wrong at first, and what corrects it?
   - Who is the counterparty? What specific behavioural bias or institutional friction lets this persist OUT OF SAMPLE? If the only answer is "markets are inefficient", it is pseudo-logic => REJECT.
   - Do the 2-3 fields have real business logic together, or are two unrelated numbers being forced?
   - DATASET-SPECIFIC RISK: fundamental17 updates on a quarterly/annual report cadence. If the signal keeps producing cross-sectional dispersion on days with NO new filings, it is really trading a STATIC cross-sectional level (the value factor), not the declared mechanism. Check whether that is the case here.
   - SIGN RISK: ratio fields (margin / growth / ROA / turnover) are naturally positively biased or signed. If the expression treats the ratio as "higher is better" without de-meaning, it is actually trading the crowded quality factor. Judge whether the DECLARED mechanism matches what the AST actually computes.
2. DOES THE EXPRESSION FAITHFULLY IMPLEMENT THE HYPOTHESIS (AST fidelity)?
   - If the hypothesis claims a second-order expectation gap, does the AST really difference current vs a historical baseline?
   - If the hypothesis claims structural synergy, is there a genuine ratio / interaction structure?
   - Any decorative, meaningless operators? Any claimed mechanism MISSING from the AST?
   - Is the DIRECTION coherent? If the AST actually captures "high ratio = good" but the hypothesis claims "expectation-gap reversion", are those two really linked?

Only give PASS when the causal chain is self-consistent AND the code implements the hypothesis 100%.
Give final_expression: if you find a way to improve FIDELITY WITHOUT changing the economics (e.g. the mechanism claims a change but the AST uses a bare level), give the corrected expression; otherwise identical to the original.

Return the structured JSON only.`,
  opts: { label: `redteam:${s.id}`, phase: 'RedTeam', schema: RT_SCHEMA, agentType: 'general-purpose' },
}))

// ★ parallel() 保序：失败的 thunk 变成 null 而不是被删除。
//   所以这里**不能**先 filter(Boolean) 再按下标取值 —— 必须先按原位取值再过滤。
const rtRaw = await parallelOrdered(rtPromises)
const rtById = new Map()
rtRaw.forEach((r, i) => { if (r && passed[i]) rtById.set(passed[i].id, r) })
const finalPassed = []
passed.forEach((s) => {
  const r = rtById.get(s.id)
  if (!r) return
  if (r.verdict === 'PASS') finalPassed.push({ ...s, expression: r.final_expression || s.expression, redteam: r })
})

log(`Red team: ${finalPassed.length}/${passed.length} survived`)

return {
  accepted: finalPassed.map(s => ({
    id: s.id, question_type: s.question_type, fields_used: s.fields_used,
    expression: s.expression, economic_mechanism: s.economic_mechanism,
    counterparty: s.counterparty, orthogonality_note: s.orthogonality_note,
    operator_count: s.operator_count, crowding_note: s.crowding_note,
    redteam_verdict: s.redteam.verdict, causal: s.redteam.causal_assessment,
    fidelity: s.redteam.fidelity_assessment,
  })),
  rejected_by_tech: rejected.map(r => ({ id: r.seed.id, expression: r.seed.expression, reason: r.reason })),
  rejected_by_redteam: passed.filter((s) => { const r = rtById.get(s.id); return r && r.verdict === 'REJECT' })
    .map((s) => ({ id: s.id, expression: s.expression, reason: (rtById.get(s.id).rejection_reason) || '' })),
}
