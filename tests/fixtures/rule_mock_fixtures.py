"""
rule_mock_fixtures.py
离线单元测试专用 Mock 夹具：承接测试环境下的模拟 Agent 响应生成。
严格与生产代码隔离，确保生产环境 core/agent_backends.py 零死代码与零模板。
"""

from typing import Any, Dict, List, Optional, Union


def handle_rule_mock(
    role: str,
    prompt: str,
    json_mode: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Union[str, Dict[str, Any], List[Any]]:
    ctx = context or {}
    role_lower = (role or "").lower()

    # 1. 技术审查专家 (aegis-tech-auditor)
    if "tech-auditor" in role_lower or "audit" in role_lower:
        candidates = ctx.get("candidate_signals") or []
        ids = [s.get("id") for s in candidates] if candidates else [
            "SEED_01", "SEED_02", "SEED_03", "SEED_04",
            "SEED_05", "SEED_06", "SEED_07", "SEED_08", "SEED_09", "SEED_10",
            "SEED_TEST", "SEED_PASS", "SEED_WIN"
        ]
        return {
            "status": "PASS",
            "approved_ids": ids
        }

    # 2. 主信号原型生成 (aegis-seed-synthesizer)
    if "seed-synthesizer" in role_lower or "synthesizer" in role_lower:
        pairings = ctx.get("pairing_candidates") or []
        fields = ctx.get("fields") or list((ctx.get("known_fields") or {}).keys())
        seeds = []
        expr_templates = [
            lambda a, b: f"subtract({a}, {b})",
            lambda a, b: f"trade_when(greater({a}, {b}), {a}, -1)",
            lambda a, b: f"trade_when(less({a}, {b}), {b}, -1)",
            lambda a, b: f"signed_power(divide({a}, {b}), 2)",
            lambda a, b: f"signed_power(subtract({a}, {b}), 0.5)",
            lambda a, b: f"divide(subtract({a}, {b}), {b})",
            lambda a, b: f"if_else(greater({a}, {b}), subtract({a}, {b}), 0)",
            lambda a, b: f"group_rank(subtract({a}, {b}), subindustry)"
        ]
        count = ctx.get("count") or 6
        for i in range(count):
            if pairings and i < len(pairings):
                f1 = pairings[i].get("main_anchor")
                f2 = pairings[i].get("normalizer") or pairings[i].get("norm_anchor")
                if not f2 and len(fields) >= 2:
                    f2 = [f for f in fields if f != f1][0]
                elif not f2:
                    f2 = "test_alpha_f2"
            elif len(fields) >= 2:
                f1 = fields[(i * 2) % len(fields)]
                f2 = fields[(i * 2 + 1) % len(fields)]
            else:
                f1 = fields[0] if fields else "test_alpha_f1"
                f2 = fields[1] if len(fields) > 1 else "test_alpha_f2"

            f1_expr = f"vec_avg({f1})" if str(f1).lower().startswith("vec_") else f1
            f2_expr = f"vec_avg({f2})" if str(f2).lower().startswith("vec_") else f2

            tmpl = expr_templates[i % len(expr_templates)]
            seeds.append({
                "id": f"SEED_{i+1:02d}",
                "cluster_ref": f"cluster_{i+1}",
                "hypothesis_type": f"TYPE_{i+1}",
                "expression": tmpl(f1_expr, f2_expr),
                "fields_used": [f1, f2],
                "economic_mechanism": f"测试宏观信号原型 {i+1}"
            })
        return seeds

    # 3. 变体群体生成与深水区精炼 (aegis-swarm-generator / aegis-deep-refiner)
    if "swarm-generator" in role_lower or "refiner" in role_lower:
        parents = ctx.get("parents") or []
        core_expr = ctx.get("core_expr")
        if not core_expr and parents and isinstance(parents, list) and isinstance(parents[0], dict):
            core_expr = parents[0].get("expression")
        if not core_expr:
            core_expr = "subtract(test_alpha_f1, test_alpha_f2)"

        parent_id = ctx.get("parent_id")
        if not parent_id and parents and isinstance(parents, list) and isinstance(parents[0], dict):
            parent_id = parents[0].get("alpha_id")
        seed_id = ctx.get("seed_id") or "SEED_TEST"
        orig_alpha = parent_id or seed_id

        category = (ctx.get("category") or "news").lower()
        is_fnd = category in ("fundamental", "fnd")
        win1 = 66 if is_fnd else 20
        win2 = 125 if is_fnd else 63
        pyramid_kb = ctx.get("pyramid_kb") or ""
        neut_list = ctx.get("neutralizations") or ["STATISTICAL", "CROWDING"]

        # 10 组成对骨架 (N, 2N)，吻合自然交易日历
        pair_generators = [
            lambda c, w, n: (f"group_rank(ts_decay_linear({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_neutralize(ts_decay_linear({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_zscore(ts_decay_linear({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_neutralize(ts_delta({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_zscore(ts_delta({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"trade_when(greater({c}, 0), ts_decay_linear({c}, {w}), -1)", n),
            lambda c, w, n: (f"group_neutralize(ts_decay_exp_window({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_zscore(ts_decay_exp_window({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_neutralize(ts_std_dev({c}, {w}), subindustry)", n),
            lambda c, w, n: (f"group_rank(ts_decay_exp_window({c}, {w}), subindustry)", n),
        ]

        variants = []
        for slot in range(1, 21):
            v_type = "EXPLOITATION" if slot <= 10 else "EXPLORATION"
            pair_idx = (slot - 1) // 2
            is_second_in_pair = ((slot - 1) % 2 == 1)
            cur_win = win2 if is_second_in_pair else win1
            cur_neut = neut_list[pair_idx % len(neut_list)]

            gen_fn = pair_generators[pair_idx % len(pair_generators)]
            expr, neut = gen_fn(core_expr, cur_win, cur_neut)

            if slot == 1 and ("winsorize" in pyramid_kb or "refiner" in role_lower):
                expr = f"group_rank(s_log_1p(winsorize({core_expr}, std=3)), subindustry)"
                neut = cur_neut
            elif slot == 2 and ("winsorize" in pyramid_kb or "refiner" in role_lower):
                expr = f"group_neutralize(s_log_1p(winsorize({core_expr}, std=3)), subindustry)"
                neut = cur_neut

            variants.append({
                "slot": slot,
                "optimize_reason": f"针对母本 {orig_alpha} 进行第 {slot} 槽因果探索，调节窗口为自然日历周期",
                "expression": expr,
                "neutralization": neut,
                "type": v_type,
                "original_alpha": orig_alpha
            })
        return variants

    return {"status": "mock_success", "role": role} if json_mode else f"Mock response for {role}"
