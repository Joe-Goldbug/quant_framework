"""Second wave: the ts_mean window knob only (ts_decay_linear was rejected by data).

12 slots = ts_mean 120/160 x inner group {country, subindustry} x c {0.15, 0.20, 0.25}.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

SIGNAL = "add(negative_score_maximum_value, negative_score_maximum_value_3, filter=True)"
C_VALUES = [0.15, 0.20, 0.25]
INNER_GROUPS = ["country", "subindustry"]
WINDOWS = [120, 160]


def main():
    kb = json.load(io.open(os.path.join(ROOT, "knowledge_base", "fields", "GLB", "ai_news_scores.json"), encoding="utf-8"))
    known_fields = dict(kb["fields"])
    fnd = json.load(io.open(os.path.join(ROOT, "knowledge_base", "fields", "GLB", "fundamental23.json"), encoding="utf-8"))
    anchor = dict(fnd["fields"]["assets_total_2"])
    anchor["companion_source"] = "fundamental23"
    anchor["role_note"] = "总资产规模内生锚 (coverage 0.96)，仅作 divide 分母的规模归一基准"
    known_fields["assets_total_2"] = anchor

    items = []
    for window in WINDOWS:
        for inner in INNER_GROUPS:
            for c in C_VALUES:
                items.append({
                    "slot": len(items) + 1,
                    "optimize_reason": (
                        f"锁定黄金骨架；旋钮1 c={c} 压低分母首尾比以降 ProdCorr；"
                        f"旋钮2 内层分组={inner}；旋钮3 ts_mean 窗口 250->{window} 释放换手以抬 Fitness。"
                    ),
                    "expression": (
                        "group_rank(divide(group_neutralize("
                        f"ts_mean({SIGNAL}, {window}), {inner}), "
                        f"add(group_rank(assets_total_2, subindustry), {c})), subindustry)"
                    ),
                    "neutralization": "COUNTRY",
                    "type": "exploit",
                    "original_alpha": "KPJGg2qE",
                    "knobs": {"c": c, "inner_group": inner, "smoothing": f"ts_mean_{window}"},
                })

    meta = {
        "seed_id": "GOLD_LOCK",
        "step": 1,
        "region": "GLB",
        "universe": "MINVOL1M",
        "delay": 1,
        "category": "other",
        "expected_polarity": 1,
        "stage0_op_count": 7,
        "core_fields": ["negative_score_maximum_value", "negative_score_maximum_value_3", "assets_total_2"],
        "max_ast_operators": 9,
        "max_champion_operators": 7,
        "is_golden_shot": True,
        "decay": 4,
        "truncation": 0.0,
        "known_fields": known_fields,
        "items": items,
    }

    out = os.path.join(HERE, "batch_GOLDEN_LOCK_s2.json")
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"wrote {out} with {len(items)} slots")


if __name__ == "__main__":
    main()
