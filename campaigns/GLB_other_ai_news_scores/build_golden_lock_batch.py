"""Build the locked-skeleton knob-sweep batch for GLB/D1/MINVOL1M.

Locked architecture (from zq3N3xPX / KPJGg2qE):
  group_rank(
      divide(
          group_neutralize(ts_SMOOTH(SIGNAL, W), INNER_GROUP),
          add(group_rank(assets_total_2, subindustry), C)
      ),
      subindustry)

Three knobs only:
  C     in {0.15, 0.20, 0.25}      -> stronger size tilt, lower ProdCorr
  INNER in {country, subindustry}  -> country unlocks EMEA cross-country baseline
  SMOOTH in {ts_mean 120, ts_decay_linear 180} -> more turnover / returns for Fitness
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

SIGNAL = "add(negative_score_maximum_value, negative_score_maximum_value_3, filter=True)"

C_VALUES = [0.15, 0.20, 0.25]
INNER_GROUPS = ["country", "subindustry"]
SMOOTHINGS = [
    ("ts_mean", 120, "窗口 250->120：释放 Turnover，抬 Returns 以推 Fitness >= 1.0"),
    ("ts_decay_linear", 180, "ts_mean(250)->ts_decay_linear(180)：近端加权，换手温和上行"),
]


def build_expression(c, inner, smooth_op, window):
    return (
        "group_rank(divide(group_neutralize("
        f"{smooth_op}({SIGNAL}, {window}), {inner}), "
        f"add(group_rank(assets_total_2, subindustry), {c})), subindustry)"
    )


def main():
    kb = json.load(io.open(os.path.join(ROOT, "knowledge_base", "fields", "GLB", "ai_news_scores.json"), encoding="utf-8"))
    known_fields = dict(kb["fields"])
    fnd = json.load(io.open(os.path.join(ROOT, "knowledge_base", "fields", "GLB", "fundamental23.json"), encoding="utf-8"))
    anchor = dict(fnd["fields"]["assets_total_2"])
    anchor["companion_source"] = "fundamental23"
    anchor["role_note"] = "总资产规模内生锚 (coverage 0.96)，仅作 divide 分母的规模归一基准"
    known_fields["assets_total_2"] = anchor

    items = []
    slot = 0
    for smooth_op, window, smooth_reason in SMOOTHINGS:
        for inner in INNER_GROUPS:
            for c in C_VALUES:
                slot += 1
                reason = (
                    f"锁定黄金骨架 divide(group_neutralize(...), add(group_rank(assets_total_2, subindustry), c))；"
                    f"旋钮1 分母常数 c={c}（压缩首尾比，削弱对母本 qMLA5lKZ 的相关性）；"
                    f"旋钮2 内层分组={inner}（country 消除跨国基线差以激活 EMEA）；"
                    f"旋钮3 {smooth_reason}。"
                )
                items.append({
                    "slot": slot,
                    "optimize_reason": reason,
                    "expression": build_expression(c, inner, smooth_op, window),
                    "neutralization": "COUNTRY",
                    "type": "exploit",
                    "original_alpha": "KPJGg2qE",
                    "knobs": {"c": c, "inner_group": inner, "smoothing": f"{smooth_op}_{window}"},
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

    out = os.path.join(HERE, "batch_GOLDEN_LOCK_s1.json")
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"wrote {out} with {len(items)} slots")
    for it in items:
        print(it["slot"], it["expression"])


if __name__ == "__main__":
    main()
