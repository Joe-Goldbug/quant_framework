# -*- coding: utf-8 -*-
"""B4 终结组合扫描查重 + 预检 (发射前本地干跑, 不烧配额)."""
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "news"
NEUT = "INDUSTRY"

EOC, VWAP, PVW = "news_eod_close", "news_eod_vwap", "news_post_vwap"
U, D = "news_max_up_amt", "news_max_dn_amt"
UR = "news_max_up_ret"
VHEX = "high_price_excursion_stddev"
CNT = f"add(vec_count({VHEX}), 1)"
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"

CANDIDATES = [
    {"id": 1, "type": "CPV_ANCHOR_DEN_RANK",
     "expression": f"reverse(rank(divide(subtract({EOC}, {PVW}), {ANCHOR_DEN})))"},
    {"id": 2, "type": "CPV_CNT_RANK",
     "expression": f"reverse(rank(divide(subtract({EOC}, {PVW}), {CNT})))"},
    {"id": 3, "type": "UXCPV_RANK",
     "expression": f"reverse(rank(multiply({U}, subtract({EOC}, {PVW}))))"},
    {"id": 4, "type": "DXCPV_RANK_FIXED",
     "expression": f"rank(multiply({D}, subtract({PVW}, {EOC})))"},
    {"id": 5, "type": "UXCPV_BF60_TSRANK250",
     "expression": f"reverse(ts_rank(ts_backfill(multiply({U}, subtract({EOC}, {PVW})), 60), 250))"},
    {"id": 6, "type": "CPV_BF60_TSRANK250",
     "expression": f"reverse(ts_rank(ts_backfill(subtract({EOC}, {PVW}), 60), 250))"},
    {"id": 7, "type": "UXCPV_RET_RANK",
     "expression": f"reverse(rank(multiply({UR}, subtract({EOC}, {PVW}))))"},
    {"id": 8, "type": "CPVxCVW",
     "expression": f"reverse(rank(multiply(subtract({EOC}, {PVW}), subtract({EOC}, {VWAP}))))"},
]

FIELDS_FILE = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1", "news12_fields_full.json")
with open(FIELDS_FILE, encoding="utf-8") as f:
    raw = json.load(f)
fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
known = [x["id"] for x in fields]
known_set = set(known)

corrector = ASTSandboxCorrector()
conn = sqlite3.connect(corrector.db_path)
cur = conn.cursor()

ops_whitelist = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
                 "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
                 "ts_delta", "ts_decay_linear", "trade_when", "greater", "less", "vec_avg",
                 "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "days_from_last_change",
                 "industry", "subindustry", "sector", "market"}

n_dup = 0
for it in CANDIDATES:
    fixed = corrector.correct_expression(it["expression"])
    h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, NEUT)
    cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
    row = cur.fetchone()
    audit = DimensionAuditor.audit_expression(fixed, known, category=CATEGORY)
    tokens = set(audit["tokens_found"])
    used = tokens & known_set
    unknown = {t for t in tokens if t not in known_set and t not in ops_whitelist and not t.isdigit()}
    dup_mark = ""
    if row:
        n_dup += 1
        dup_mark = f" | DUP历史: {row[0][:70]}"
    print(f"slot{it['id']} [{it['type']}] ops={audit['operator_count']} fields={len(used)} "
          f"len={len(it['expression'])} valid={audit['is_valid']} unknown={unknown or '-'}{dup_mark}", flush=True)
    if unknown:
        raise SystemExit(f"slot{it['id']} 未知标识符: {unknown}")
    if not audit["is_valid"]:
        raise SystemExit(f"slot{it['id']} 审计失败: {audit['issues']}")
    if not (2 <= len(used) <= 3):
        raise SystemExit(f"slot{it['id']} 字段数 {len(used)} 越界")
    if audit["operator_count"] > 10:
        raise SystemExit(f"slot{it['id']} ops {audit['operator_count']} > 10")
    if len(it["expression"]) > 857:
        raise SystemExit(f"slot{it['id']} 超长")
conn.close()
print(f"\nB4 查重完成: {n_dup}/8 历史重复 (<=2 合法)", flush=True)
