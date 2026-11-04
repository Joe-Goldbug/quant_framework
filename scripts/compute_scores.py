import math

alphas = [
    {
        'id': '88RgeN6o (Seed)',
        'sharpe': 1.75,
        'fitness': 1.14,
        'margin_bps': 20.24,
        'prod_corr': 0.7231,
        'ops': 6,
        'drawdown': 0.0820,
        'turnover': 0.0526,
        'fails': ['LOW_GLB_EMEA_SHARPE (0.63)', 'LOW_GLB_APAC_SHARPE (0.92)', 'CLUSTER_TEST (0.94)']
    },
    {
        'id': '88RK0Avl (Novy-Marx GP/A)',
        'sharpe': 1.51,
        'fitness': 0.88,
        'margin_bps': 20.03,
        'prod_corr': 0.7458,
        'ops': 6,
        'drawdown': 0.0483,
        'turnover': 0.0440,
        'fails': []
    },
    {
        'id': 'kqNLwRJ6 (Pricing Power x Turnover)',
        'sharpe': 1.42,
        'fitness': 0.78,
        'margin_bps': 20.51,
        'prod_corr': 0.7181,
        'ops': 7,
        'drawdown': 0.0370,
        'turnover': 0.0371,
        'fails': []
    },
    {
        'id': 'xArPA62b (State-Freezing GP/A)',
        'sharpe': 1.47,
        'fitness': 0.83,
        'margin_bps': 21.65,
        'prod_corr': 0.7464,
        'ops': 9,
        'drawdown': 0.0441,
        'turnover': 0.0388,
        'fails': []
    },
    {
        'id': 'A1Vg1Wrw (State-Freezing Pricing Power)',
        'sharpe': 1.37,
        'fitness': 0.73,
        'margin_bps': 21.83,
        'prod_corr': 0.7165,
        'ops': 10,
        'drawdown': 0.0377,
        'turnover': 0.0341,
        'fails': []
    }
]

print(f"{'Alpha ID / Model':<38} | {'Score':<7} | {'Sharpe':<6} | {'Margin':<9} | {'Turnover':<8} | {'Drawdown':<8} | {'ProdCorr':<8} | {'Fails'}")
print("-" * 115)
for a in alphas:
    fit = a['fitness']
    ln_margin = math.log(a['margin_bps'])
    corr_penalty = 1 - (a['prod_corr'] ** 2)
    op_penalty = 1 - 0.04 * a['ops']
    score = fit * ln_margin * corr_penalty * op_penalty
    fails_str = "None (ALL PASS)" if not a['fails'] else f"{len(a['fails'])} FAILS"
    print(f"{a['id']:<38} | {score:<7.4f} | {a['sharpe']:<6.2f} | {a['margin_bps']:<5.2f} bps | {a['turnover']*100:<6.2f}% | {a['drawdown']*100:<6.2f}% | {a['prod_corr']:<8.4f} | {fails_str}")
