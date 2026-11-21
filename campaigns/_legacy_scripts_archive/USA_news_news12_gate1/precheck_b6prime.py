# -*- coding: utf-8 -*-
"""B6' 终批查重 + 预检 (红队终审版: PLO 参照点族补全 + 交互轴 x 冠军核末梢).

红队 B6 终审裁决 (2026-10-25):
  砍 槽1 PAN (语义孪生 TON, EOC-PAN == CTN 已测 20+ 变体)
  砍 槽2 PHI (== news_ton_high 已测 4 变体, 最佳 Sh 0.99)
  砍 槽4/5/8 SPYADJ (数学恒等死重: SPY_RET 横截面常数, rank(X-c)==rank(X))
  砍 槽7 RANGE_NORM_CTN (CTN/TON 双分母自归一化, 被槽6 支配)
  保留/修正: 槽3 PLO (TON 窗口低点, 库中 0 记录 = 唯一真新参照点)
            槽6 升级 (三重归一超 3 字段 -> 适配为 PLO x range_pct)
            槽7 替换 (BREAKOUT_RATIO 无量纲几何)
mandate 要求每批 8 槽 -> 补 5 个家族补全单元格 (PLO x 冠军骨架/ts_rank 壳,
  BREAKOUT x ts_rank 壳, 交互轴 x 冠军核 U/D 末梢).
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
U, D = "news_max_up_amt", "news_max_dn_amt"
VHEX = "high_price_excursion_stddev"
PHI, PLO = "highest_price_pre_news", "lowest_price_pre_news"
RANGE = "main_session_price_range"
ANCHOR_DEN = f"ts_backfill(vec_count({VHEX}), 120)"

CANDIDATES = [
    # ---- PLO 参照点族 (红队保留 + 家族补全) ----
    {"id": 1, "type": "CLOSE_VS_PRELOW",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({VHEX}))))"},
    {"id": 2, "type": "CLOSE_VS_PRELOW_ANCHOR",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), {ANCHOR_DEN})))"},
    {"id": 3, "type": "CLOSE_VS_PRELOW_TSRANK250",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({VHEX})), 250))"},
    {"id": 4, "type": "BREAKOUT_RATIO",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), subtract(vec_avg({PHI}), vec_avg({PLO})))))"},
    {"id": 5, "type": "BREAKOUT_RATIO_TSRANK250",
     "expression": f"reverse(ts_rank(divide(subtract({EOC}, vec_avg({PLO})), subtract(vec_avg({PHI}), vec_avg({PLO}))), 250))"},
    {"id": 6, "type": "RANGE_NORM_PLO",
     "expression": f"reverse(rank(divide(subtract({EOC}, vec_avg({PLO})), vec_avg({RANGE}))))"},
    # ---- 交互轴 x 冠军核末梢 (家族从未测过的交互单元格) ----
    {"id": 7, "type": "UXCTN",
     "expression": f"reverse(rank(multiply({U}, subtract({EOC}, {TON}))))"},
    {"id": 8, "type": "DXCTN",
     "expression": f"rank(multiply({D}, subtract({TON}, {EOC})))"},
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

# ---- 表达式级 novelty 扫描 (指纹库之外兜底: 语义重复检测) ----
print("== 表达式级 novelty 扫描 ==", flush=True)
scan_specs = [
    ("U x TON 交互 (UXCTN 语义重复?)", ["news_max_up_amt", "news_ton_last"]),
    ("D x TON 交互 (DXCTN 语义重复?)", ["news_max_dn_amt", "news_ton_last"]),
    ("PLO 使用史", ["lowest_price_pre_news"]),
    ("PHI 使用史", ["highest_price_pre_news"]),
    ("PAN 使用史", ["price_at_news_time"]),
]
for label, keys in scan_specs:
    conds = " AND ".join(["expression LIKE ?"] * len(keys))
    params = [f"%{k}%" for k in keys]
    cur.execute(f"SELECT expression FROM alpha_fingerprints WHERE {conds}", params)
    rows = cur.fetchall()
    print(f"  [{label}] 命中 {len(rows)} 条", flush=True)
    for r in rows[:6]:
        print(f"    - {r[0][:130]}", flush=True)

ops_whitelist = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
                 "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
                 "ts_delta", "ts_decay_linear", "trade_when", "greater", "less", "vec_avg",
                 "vec_sum", "vec_count", "vec_max", "vec_min", "vec_stddev", "days_from_last_change",
                 "industry", "subindustry", "sector", "market"}

print("\n== 逐槽预检 ==", flush=True)
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
print(f"\nB6' 查重完成: {n_dup}/8 历史重复 (<=2 合法)", flush=True)
