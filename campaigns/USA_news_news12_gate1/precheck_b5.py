# -*- coding: utf-8 -*-
"""B5 归一器扫描批查重 + 预检 (2026-10-25).

背景修正: 原 B5 草案的 fade 槽 (5m/10m vs 120m) 实为 Wave6 W 批已测
(main_pct_change 版 8/8 负 Sharpe = 预测延续非反转), 故重设计为
'最佳分子 x 未测归一器' 程序——延续'分母 2Y 效应分子依赖'主线:
  - volsurge (main_session_volume_ratio): V 批只在 close-vwap/gap/range/
    p10/p120/bench 上测过 (Sh 0.16-1.32), 最佳分子 CTN/COPEN/CPV 未测
  - range/ATR (session_range_to_atr_ratio): 从未作为归一器测试 (0 用户)
"""
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

EOC, VWAP, TON = "news_eod_close", "news_eod_vwap", "news_ton_last"
OPEN, PVW = "news_open", "news_post_vwap"
VOLSURGE = "main_session_volume_ratio"
RANGEATR = "main_session_range_to_atr_ratio"
UPI, DPI = "max_pct_increase_post_news", "max_pct_decrease_post_news"

CANDIDATES = [
    {"id": 1, "type": "CTN_PER_VOLSURGE",
     "expression": f"reverse(rank(divide(subtract({EOC}, {TON}), vec_avg({VOLSURGE}))))"},
    {"id": 2, "type": "CPV_PER_VOLSURGE",
     "expression": f"reverse(rank(divide(subtract({EOC}, {PVW}), vec_avg({VOLSURGE}))))"},
    {"id": 3, "type": "COPEN_PER_VOLSURGE",
     "expression": f"reverse(rank(divide(subtract({EOC}, {OPEN}), vec_avg({VOLSURGE}))))"},
    {"id": 4, "type": "CTN_PER_RANGEATR",
     "expression": f"reverse(rank(divide(subtract({EOC}, {TON}), vec_avg({RANGEATR}))))"},
    {"id": 5, "type": "CPV_PER_RANGEATR",
     "expression": f"reverse(rank(divide(subtract({EOC}, {PVW}), vec_avg({RANGEATR}))))"},
    {"id": 6, "type": "CTN_PER_TOTTICKS",
     "expression": f"reverse(rank(divide(subtract({EOC}, {TON}), news_tot_ticks)))"},
    {"id": 7, "type": "COPEN_PER_RANGEATR",
     "expression": f"reverse(rank(divide(subtract({EOC}, {OPEN}), vec_avg({RANGEATR}))))"},
    {"id": 8, "type": "REACTION_ASYMMETRY",
     "expression": f"reverse(rank(subtract(vec_avg({UPI}), vec_avg({DPI}))))"},
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
        raise SystemExit(f"slot{it['id']} 字段数 {len(used)} 越界 (需 2-3)")
    if audit["operator_count"] > 10:
        raise SystemExit(f"slot{it['id']} ops {audit['operator_count']} > 10")
    if len(it["expression"]) > 857:
        raise SystemExit(f"slot{it['id']} 超长")
conn.close()
print(f"\nB5 查重完成: {n_dup}/8 历史重复 (<=2 合法)", flush=True)
