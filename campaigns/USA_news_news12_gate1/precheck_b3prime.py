# -*- coding: utf-8 -*-
"""B3' 终版查重: 5 保留 + CPV新轴(2) + UXCVW_RET(4) + CPV_TSRANK250(8)."""
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

EOC, VWAP, TON, OPEN, PVW = "news_eod_close", "news_eod_vwap", "news_ton_last", "news_open", "news_post_vwap"
U, D = "news_max_up_amt", "news_max_dn_amt"
UR = "news_max_up_ret"
VHEX = "high_price_excursion_stddev"
AMP = f"divide({U}, add({U}, {D}))"
CPV = f"subtract({EOC}, {PVW})"

CANDIDATES = [
    {"id": 1, "type": "COPEN_VECAVG_TSRANK250", "neut": "INDUSTRY",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, {OPEN}), vec_avg({VHEX})), 250))"},
    {"id": 2, "type": "CPV_RANK", "neut": "INDUSTRY",
     "expression": f"reverse(rank({CPV}))"},
    {"id": 3, "type": "CTN_VECMAX_TSRANK250", "neut": "INDUSTRY",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, {TON}), vec_max({VHEX})), 250))"},
    {"id": 4, "type": "UXCVW_RET_RANK", "neut": "INDUSTRY",
     "expression": f"reverse(rank(multiply({UR}, subtract({EOC}, {VWAP}))))"},
    {"id": 5, "type": "HARDGATE_AMP_TSRANK250", "neut": "INDUSTRY",
     "expression": f"trade_when(greater(vec_count({VHEX}), 0), reverse(ts_rank({AMP}, 250)), 0)"},
    {"id": 6, "type": "UXCVW_RANK", "neut": "INDUSTRY",
     "expression": f"reverse(rank(multiply({U}, subtract({EOC}, {VWAP}))))"},
    {"id": 7, "type": "UXCVW_BF60_TSRANK250", "neut": "INDUSTRY",
     "expression": f"reverse(ts_rank(ts_backfill(multiply({U}, subtract({EOC}, {VWAP})), 60), 250))"},
    {"id": 8, "type": "CPV_TSRANK250", "neut": "INDUSTRY",
     "expression": f"reverse(ts_rank({CPV}, 250))"},
]

FIELDS_FILE = os.path.join(os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1"), "news12_fields_full.json")
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
    h = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, it["neut"])
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
print(f"\nB3' 终版查重完成: {n_dup}/8 历史重复 (<=2 合法)", flush=True)
