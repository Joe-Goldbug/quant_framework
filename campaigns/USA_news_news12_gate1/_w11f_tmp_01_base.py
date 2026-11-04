# -*- coding: utf-8 -*-
"""W11F 数据基座：合并所有 batch_*_result.json 的 alpha_results 与同前缀 batch_*.json 的 items(type/expression)。
只读，不修改任何已有文件。输出合并行集到 _w11f_tmp_rows.json。"""
import json, glob, os, re, sys

BASE = r"D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_news_news12_gate1"
OUT = os.path.join(BASE, "_w11f_tmp_rows.json")

# 1. 提交文件：expression -> (type, optimize_reason, batch_name)
expr_meta = {}
for f in sorted(glob.glob(os.path.join(BASE, "batch_*.json"))):
    if f.endswith("_result.json"):
        continue
    bname = os.path.basename(f)[:-5]
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("SKIP submit file", bname, e); continue
    for it in d.get("items", []):
        expr = it.get("expression")
        if not expr:
            continue
        # 同一表达式可能在多个 batch 出现，保留第一个并记录所有 type
        if expr in expr_meta:
            expr_meta[expr]["types"].append((bname, it.get("type", "")))
        else:
            expr_meta[expr] = {"types": [(bname, it.get("type", ""))],
                               "reason": it.get("optimize_reason", "")}
print("submit exprs:", len(expr_meta))

# 2. result 文件
rows = []
n_files = 0
for f in sorted(glob.glob(os.path.join(BASE, "batch_*_result.json"))):
    bname = os.path.basename(f)[:-len("_result.json")]
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("SKIP result file", bname, e); continue
    n_files += 1
    for r in d.get("alpha_results", []):
        code = r.get("code", "")
        m = r.get("metrics", {}) or {}
        ch = r.get("checks", {}) or {}
        cl = None
        for w in ch.get("warning", []) or []:
            if w.get("name") == "CLUSTER_TEST":
                cl = w.get("value")
        meta = expr_meta.get(code, {})
        types = [t for (_, t) in meta.get("types", []) if t]
        rows.append({
            "batch": bname,
            "alpha_id": r.get("alpha_id", ""),
            "expr": code,
            "type": types[0] if types else "",
            "types_all": types,
            "reason": meta.get("reason", ""),
            "settings": r.get("settings", {}),
            "m": {k: m.get(k) for k in ["sharpe","fitness","turnover","returns","drawdown","margin",
                                          "longCount","shortCount","sub_universe_sharpe",
                                          "two_year_sharpe","risk_neutralized_sharpe"]},
            "cl": cl,
            "fail": [c.get("name") for c in ch.get("fail", []) or []],
            "warning": [c.get("name") for c in ch.get("warning", []) or []],
            "status": r.get("status", ""),
        })
print("result files:", n_files, "rows:", len(rows))

# 去重（同表达式同设置重复提交）
seen = {}
dedup = []
for r in rows:
    key = (r["expr"], json.dumps(r["settings"], sort_keys=True))
    if key in seen:
        continue
    seen[key] = 1
    dedup.append(r)
print("dedup rows:", len(dedup))

n_cl = sum(1 for r in dedup if r["cl"] is not None)
print("rows with CLUSTER_TEST value:", n_cl)
n_expr_meta = sum(1 for r in dedup if r["type"])
print("rows matched to submit type:", n_expr_meta)

json.dump(dedup, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("saved:", OUT)
