# -*- coding: utf-8 -*-
"""Phase 0: independent multi-role seed research for USA/fundamental90.
This script is deliberately offline: it creates seed/report JSON only and never
submits or starts a BRAIN simulation.
"""
import ast
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(CAMPAIGN, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))

from quant_framework.core.dimension_rules import DimensionAuditor
from quant_framework.core.red_team import DoubleBlindRedTeam
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

DATASET = "fundamental90"
REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1
RAW_PATH = os.path.join(CAMPAIGN, "f90_fields_raw.json")
OUTPUT_POOL = os.path.join(HERE, "total_signals.json")
OUTPUT_AUDIT = os.path.join(HERE, "offline_audit.json")

with open(RAW_PATH, encoding="utf-8") as f:
    raw_fields = {item["id"]: item for item in json.load(f)}

# Role 1 — Field Explorer: use real field metadata and prefer low crowding,
# adequate coverage and the empirically confirmed VECTOR representation.
# All selected features have alphaCount <= 2; no cross-dataset PV fields.
SEEDS = [
    {
        "id": "SEED_Q1_INVARIANCE",
        "question_type": "Q1 Invariance",
        "fields_used": ["fnd90_game_cash_flow_coverage", "fnd90_game_short_term_debt"],
        "expression": "subtract(vec_avg(fnd90_game_cash_flow_coverage), vec_avg(fnd90_game_short_term_debt))",
        "idea": "Liquidity capacity relative to refinancing pressure.",
        "rationale": "Cash-flow debt coverage is a solvency buffer, while short-term debt is a near-term refinancing burden. Their within-dataset spread encodes the balance-sheet resilience that broad leverage screens miss; both fields have adequate coverage and only 1-2 recorded alphas.",
        "counterparty": "Investors extrapolating reported profitability without separating cash conversion from maturity concentration.",
        "falsifiable": "Reject if results are explained by financial-sector exposure or if either component alone accounts for the spread's performance.",
    },
    {
        "id": "SEED_Q2_DYNAMICS",
        "question_type": "Q2 Dynamics",
        "fields_used": ["fnd90_game_gma_chg", "fnd90_game_asset_turnover_chg"],
        "expression": "subtract(vec_avg(fnd90_game_gma_chg), vec_avg(fnd90_game_asset_turnover_chg))",
        "idea": "Profitability improvement not accompanied by asset-use improvement.",
        "rationale": "Gross-margin change captures pricing/cost economics; asset-turnover change captures utilization. Their divergence separates margin-led improvement from broad operational improvement, where the former may prove less durable. Both are direct change features rather than extra transforms of old levels.",
        "counterparty": "Simple profitability-momentum allocators that treat all margin improvement as durable operating progress.",
        "falsifiable": "Reject if the divergence is just a sector composition proxy or if asset-turnover change adds no independent information.",
    },
    {
        "id": "SEED_Q3_ANOMALY",
        "question_type": "Q3 Anomaly",
        "fields_used": ["fnd90_game_gross_margin_vol", "fnd90_game_eps_vol"],
        "expression": "add(vec_avg(fnd90_game_gross_margin_vol), vec_avg(fnd90_game_eps_vol))",
        "idea": "Joint instability in operating economics and reported earnings.",
        "rationale": "Gross-margin volatility represents instability in unit economics; EPS volatility represents instability in the bottom line. A high joint level flags firms where operating noise propagates into earnings, potentially underpriced by investors who focus on average profitability. The signal is deliberately an anomaly/risk construct, not a claim of a single causal shock.",
        "counterparty": "Quality screens based on average margins or earnings levels that overlook instability around those averages.",
        "falsifiable": "Reject if the signal merely loads on size/industry or if either volatility field fully explains the joint score.",
    },
    {
        "id": "SEED_Q4_INTERACTION",
        "question_type": "Q4 Interaction",
        "fields_used": ["fnd90_game_gma_chg", "fnd90_game_accruals_vol"],
        "expression": "subtract(vec_avg(fnd90_game_gma_chg), vec_avg(fnd90_game_accruals_vol))",
        "idea": "Reported margin improvement discounted by accrual-quality uncertainty.",
        "rationale": "Gross-margin improvement is a positive operating signal, but high accrual volatility weakens confidence that accounting earnings convert into repeatable cash economics. A difference of the two economic legs tests whether the market distinguishes credible improvement from fragile reported improvement; no PV input is used.",
        "counterparty": "Investors buying margin acceleration without checking the reliability of accrual-based earnings.",
        "falsifiable": "Reject if the accrual-quality leg has no incremental explanatory value or sign direction is unstable across subindustries.",
    },
    {
        "id": "SEED_Q5_STRUCTURE",
        "question_type": "Q5 Structure",
        "fields_used": ["fnd90_game_inventory_days", "fnd90_game_receivable_days"],
        "expression": "add(vec_avg(fnd90_game_inventory_days), vec_avg(fnd90_game_receivable_days))",
        "idea": "Working-capital cash-conversion drag from inventory and collections.",
        "rationale": "Inventory days proxy time capital is tied in unsold goods; receivable days proxy time until sales become cash. Together they describe two distinct legs of the operating cash-conversion cycle, and a high combined burden can precede margin or liquidity stress. The form avoids a fragile ratio with uncertain denominator semantics.",
        "counterparty": "Revenue-growth strategies that reward sales expansion without accounting for inventory accumulation or collection delays.",
        "falsifiable": "Reject if industry business-model differences dominate and the two components do not add complementary information.",
    },
    {
        "id": "SEED_Q6_ACCUMULATION",
        "question_type": "Q6 Accumulation",
        "fields_used": ["fnd90_game_optimism_sale", "fnd90_game_eps_sur_vol"],
        "expression": "ts_mean(subtract(vec_avg(fnd90_game_optimism_sale), vec_avg(fnd90_game_eps_sur_vol)), 20)",
        "idea": "Persistent analyst optimism discounted by forecast-error instability.",
        "rationale": "The spread contrasts a positive sales-expectation signal with instability in historical EPS forecast errors; a short moving mean is intended to retain a persistent miscalibration state rather than react to one noisy update. Fundamental event data are VECTOR, so both inputs are explicitly reduced before time-series processing.",
        "counterparty": "Consensus-following portfolios that assume analyst optimism is equally informative across firms.",
        "falsifiable": "Reject if field definitions reveal incompatible scales or if the moving average adds no stability relative to the raw spread.",
    },
    {
        "id": "SEED_Q7_RELATIVE",
        "question_type": "Q7 Relative",
        "fields_used": ["fnd90_game_labor_efficiency_chg", "fnd90_game_sg_a_inefficiency"],
        "expression": "group_rank(subtract(vec_avg(fnd90_game_labor_efficiency_chg), vec_avg(fnd90_game_sg_a_inefficiency)), subindustry)",
        "idea": "Within-subindustry operating-efficiency improvement net of overhead inefficiency.",
        "rationale": "Subindustry ranks compare labor-efficiency change and SG&A inefficiency against peers facing similar production and cost structures. The rank spread reduces raw scale mismatch and asks whether a firm improves labor productivity while keeping overhead discipline; both fields have broad coverage in the local catalog.",
        "counterparty": "Cross-industry quality models that compare structurally different cost bases on raw levels.",
        "falsifiable": "Reject if the peer-relative construction is no better than either leg alone or if small peer groups create unstable ranks.",
    },
    {
        "id": "SEED_Q8_ESSENCE",
        "question_type": "Q8 Essence",
        "fields_used": ["fnd90_qes_gamef_icfroe_1y", "fnd90_qes_gamef_icfroe_3y"],
        "expression": "subtract(vec_avg(fnd90_qes_gamef_icfroe_1y), vec_avg(fnd90_qes_gamef_icfroe_3y))",
        "idea": "Near-term cash-return improvement relative to the longer-horizon baseline.",
        "rationale": "The 1-year incremental cash-flow return captures recent change, while its 3-year counterpart anchors the longer-horizon path. Their spread targets the essence of an expectation gap: recent cash-return improvement or deterioration beyond the broader trend, without importing price data or assuming accounting quality equals market surprise.",
        "counterparty": "Slow-moving quality allocators that rely on long-horizon averages and underweight recent fundamental inflection.",
        "falsifiable": "Reject if the 1-year and 3-year fields are constructionally redundant or if their spread is dominated by reporting cadence artifacts.",
    },
]

# Role 2 — Main Signal Synthesizer has proposed eight different mechanisms.
# Role 3 — deterministic Tech Auditor: field existence/type, parser, dimensions,
# vector wrappers, operator budget (<=4), and price-volume contamination.
PV_NAMES = {"close", "open", "high", "low", "vwap", "volume", "cap", "adv20", "returns", "sharesout", "split", "dividend"}
VECTOR_WRAPPERS = {"vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "vec_norm", "vec_range"}
KNOWN_OPERATORS = {
    "add", "subtract", "multiply", "divide", "ts_mean", "ts_delta", "ts_std_dev",
    "ts_zscore", "group_rank", "group_zscore", "vec_avg", "vec_sum", "vec_count",
    "vec_max", "vec_min", "vec_stddev", "vec_norm", "vec_range", "abs", "reverse",
}
GROUP_NAMES = {"market", "sector", "industry", "subindustry"}

# Each call node counts toward the strict total operator limit (vector reductions included).
# The legacy builder incorrectly excluded vec_* from its <=4 seed budget.

def inspect_expr(expr):
    tree = ast.parse(expr, mode="eval")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    fields = set()
    used_pv = set()
    unwrapped_vectors = []
    unknown_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in KNOWN_OPERATORS:
                unknown_calls.append(ast.unparse(node.func))
        elif isinstance(node, ast.Name):
            if node.id in PV_NAMES:
                used_pv.add(node.id)
            elif node.id not in KNOWN_OPERATORS and node.id not in GROUP_NAMES:
                if node.id in raw_fields:
                    fields.add(node.id)
                else:
                    # Names can be function kwargs; none are used in this seed set.
                    fields.add(node.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in raw_fields and raw_fields[node.id].get("type") == "VECTOR":
            parent_wrapped = any(
                isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                and parent.func.id in VECTOR_WRAPPERS
                and node in ast.walk(parent.args[0]) if parent.args else False
                for parent in calls
            )
            if not parent_wrapped:
                unwrapped_vectors.append(node.id)
    return tree, calls, fields, used_pv, unwrapped_vectors, unknown_calls

# Give nodes parents for checking actual vector-wrapper ancestry.
def vector_wrapper_check(tree):
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    failures = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in raw_fields and raw_fields[node.id].get("type") == "VECTOR":
            cur = node
            found = False
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Name) and cur.func.id in VECTOR_WRAPPERS:
                    found = True
                    break
            if not found:
                failures.append(node.id)
    return failures

tech_results = []
red_results = []
for seed in SEEDS:
    expr = seed["expression"]
    tree, calls, fields, pv_fields, _, unknown_calls = inspect_expr(expr)
    missing = sorted(f for f in seed["fields_used"] if f not in raw_fields)
    unexpected = sorted(fields - set(seed["fields_used"]))
    not_referenced = sorted(set(seed["fields_used"]) - fields)
    wrong_type = sorted(f for f in seed["fields_used"] if f in raw_fields and raw_fields[f].get("type") != "VECTOR")
    unwrapped = vector_wrapper_check(tree)
    # Existing auditor provides an independent AST / PV / field-dimension pass.
    meta = {
        f: {"type": raw_fields[f]["type"], "domain": "unbounded", "is_sparse": False,
            "description": raw_fields[f].get("description", "")}
        for f in seed["fields_used"] if f in raw_fields
    }
    dimension = DimensionAuditor.audit_expression(expr, meta, category="fundamental", allow_pv_cross=False, max_operators=4)
    tech_pass = (
        len(calls) <= 4 and not missing and not unexpected and not not_referenced and
        not wrong_type and not unwrapped and not pv_fields and not unknown_calls and
        dimension.get("is_valid", False)
    )
    tech_results.append({
        "seed_id": seed["id"], "expression": expr, "field_ids_exist": not missing,
        "fields_are_VECTOR": not wrong_type, "all_vectors_wrapped": not unwrapped,
        "field_reference_match": not unexpected and not not_referenced,
        "ast_operator_count_including_vector_casts": len(calls), "operator_budget_max": 4,
        "unknown_operators": unknown_calls, "pv_contamination_fields": sorted(pv_fields),
        "dimension_auditor": dimension, "technical_pass": bool(tech_pass),
    })

    # Role 4 — blind causal red-team verdict. Deliberately no performance results supplied.
    blind_fields = {
        f: {"domain": "unbounded", "center": 0.0, "sparse_zero": False,
            "meaning": raw_fields[f].get("description", "")}
        for f in seed["fields_used"] if f in raw_fields
    }
    payload = DoubleBlindRedTeam.generate_blind_payload(
        expr,
        {"counterparty": seed["counterparty"], "mechanism": seed["rationale"]},
        blind_fields,
    )
    verdict = DoubleBlindRedTeam.audit_candidate_blindly(payload)
    red_results.append({"seed_id": seed["id"], **verdict})

# Topology diversity without numeric parameter tweaks.
corrector = ASTSandboxCorrector(":memory:")
skeletons = {s["id"]: corrector.get_canonical_skeleton(s["expression"]) for s in SEEDS}
skeleton_freq = Counter(skeletons.values())
# Q2 and Q4 may share subtract/vec topology only if their field identities differ;
# skeleton checking is reported, not falsely claimed as eight unique AST forms.

all_green = all(x["technical_pass"] for x in tech_results) and all(x["verdict"] == "PASS" for x in red_results)
report = {
    "run_mode": "OFFLINE_ONLY_NO_SIMULATION_NO_SUBMISSION",
    "dataset_id": DATASET, "region": REGION, "universe": UNIVERSE, "delay": DELAY,
    "research_roles": [
        "Field Explorer: selected real low-crowding fields and honored VECTOR metadata",
        "Main Signal Synthesizer: eight 8-question causal hypotheses",
        "Tech Auditor: independent field/type/operator/PV/AST/dimension checks",
        "Blind Red Team: hypothesis-to-expression and parsimony review with no metrics",
    ],
    "strict_operator_budget": "<=4 total AST Call nodes including vec_* wrappers",
    "technical_results": tech_results,
    "red_team_results": red_results,
    "skeleton_frequency": dict(skeleton_freq),
    "all_green": all_green,
    "limitations": [
        "No raw daily panel distribution or point-in-time field history was examined; data-shape/time semantics remain to be confirmed.",
        "Static passes establish syntax and metadata consistency only, not alpha profitability or absence of out-of-sample decay.",
        "The legacy stage2 report excluded vector casts from its <=4 operator budget; this audit counts them and can fail candidates accordingly.",
    ],
}
with open(OUTPUT_AUDIT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

pool = {
    "dataset_id": DATASET, "region": REGION, "universe": UNIVERSE, "delay": DELAY,
    "category": "fundamental", "phase": "PHASE_0_OFFLINE",
    "submission_forbidden": True,
    "all_green": all_green,
    "seeds": [{**seed, "times": 0, "status": "UNTESTED"} for seed in SEEDS],
}
with open(OUTPUT_POOL, "w", encoding="utf-8") as f:
    json.dump(pool, f, ensure_ascii=False, indent=2)

print("Offline seed pool:", OUTPUT_POOL)
print("Offline audit:", OUTPUT_AUDIT)
print("ALL GREEN:", all_green)
for x in tech_results:
    red = next(r for r in red_results if r["seed_id"] == x["seed_id"])
    print(f"{x['seed_id']}: operators={x['ast_operator_count_including_vector_casts']}/4 tech={'PASS' if x['technical_pass'] else 'FAIL'} red={red['verdict']}")
