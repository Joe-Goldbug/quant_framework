# -*- coding: utf-8 -*-
"""AEGIS R10 批次装配: 从 R10_candidates.json 切分 C01-C08 -> batch_R10, C09-C16 -> batch_R11
严格遵守批次 schema (region/universe/delay/dataset/category/neutralization/decay/truncation/
submission_forbidden/known_fields/items/slot_meta)。严禁任何提交调用。"""
import json, re, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

cands = json.load(open(os.path.join(HERE, "R10_candidates.json"), encoding="utf-8"))["candidates"]

FIELD_RE = re.compile(r"(fnd90_us_[a-z0-9_]+|oth466_[a-z0-9_]+)")


def extract_counterparty(reason: str) -> str:
    m = re.search(r"对手盘[是是]?[:：]?\s*([^。]+)", reason)
    if m:
        return "对手盘" + m.group(1).strip()
    return reason[:40]


def build_batch(slots, label, purpose):
    items = []
    fields = set()
    for i, c in enumerate(slots, 1):
        e = c["expression"]
        fields.update(FIELD_RE.findall(e))
        items.append({
            "slot": i,
            "seed_id": f"R10_{c['id']}",
            "type": "CROSS_FINAL",
            "expression": e,
            "counterparty": extract_counterparty(c.get("optimize_reason", "")),
            "optimize_reason": c.get("optimize_reason", ""),
        })
    return {
        "region": "USA",
        "universe": "TOP1000",
        "delay": 1,
        "dataset": "fundamental90+other466",
        "category": "fundamental",
        "neutralization": "SUBINDUSTRY",
        "decay": 4,
        "truncation": 0.08,
        "submission_forbidden": True,
        "known_fields": sorted(fields),
        "items": items,
        "slot_meta": {"purpose": purpose, "label": label},
    }


r10 = build_batch(cands[:8], "R10", "R10 第一轮: 红队全 PASS 的 8 条正交候选 (现金/债务/盈利质量/运营资本)")
r11 = build_batch(cands[8:], "R11", "R10 第二轮: 红队全 PASS 的其余 8 条 (毛利动能/分析师预期/现金充裕度延续)")

with open(os.path.join(HERE, "batch_R10.json"), "w", encoding="utf-8") as f:
    json.dump(r10, f, ensure_ascii=False, indent=2)
with open(os.path.join(HERE, "batch_R11.json"), "w", encoding="utf-8") as f:
    json.dump(r11, f, ensure_ascii=False, indent=2)

print("batch_R10.json:", len(r10["items"]), "slots, known_fields:", len(r10["known_fields"]))
print("batch_R11.json:", len(r11["items"]), "slots, known_fields:", len(r11["known_fields"]))
print("R10 known_fields:", r10["known_fields"])
print("R11 known_fields:", r11["known_fields"])
