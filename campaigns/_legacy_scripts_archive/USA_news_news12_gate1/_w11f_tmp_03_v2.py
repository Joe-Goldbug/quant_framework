# -*- coding: utf-8 -*-
"""W11F 分析 v2：平衡括号解析函数调用参数，重算 ts_rank/ts_backfill 窗口统计、低 TO 天花板、
amplitude bf 覆盖（结果文件 + 提交文件双源）。只读，仅写 _w11f_tmp_ 新文件。"""
import json, re
from collections import defaultdict, Counter

BASE = r"D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_news_news12_gate1"
rows = json.load(open(BASE + "/_w11f_tmp_rows.json", encoding="utf-8"))
R = [r for r in rows if r["m"]["sharpe"] is not None and r["m"]["turnover"] is not None]

def find_calls(expr, fname):
    res = []
    for m in re.finditer(r"(?<![\w.])" + fname + r"\s*\(", expr):
        i = m.end(); depth = 1; j = i
        while j < len(expr) and depth > 0:
            if expr[j] == '(': depth += 1
            elif expr[j] == ')': depth -= 1
            j += 1
        if depth == 0:
            res.append(expr[i:j-1])
    return res

def split_args(s):
    args = []; depth = 0; cur = ""
    for c in s:
        if c == '(': depth += 1
        elif c == ')': depth -= 1
        if c == ',' and depth == 0:
            args.append(cur.strip()); cur = ""
        else:
            cur += c
    if cur.strip(): args.append(cur.strip())
    return args

def call_windows(expr, fname):
    """返回 fname 的所有窗口参数（数字）"""
    ws = []
    for argstr in find_calls(expr, fname):
        args = split_args(argstr)
        if len(args) >= 2 and re.fullmatch(r"\d+", args[1]):
            ws.append(int(args[1]))
    return ws

def first_arg_has(expr, fname, target):
    """fname 的第一个参数里是否出现 target 子串"""
    for argstr in find_calls(expr, fname):
        args = split_args(argstr)
        if args and target in args[0]:
            return True
    return False

# ---------- 重算结构特征 ----------
for r in R:
    e = r["expr"]
    r["tr250"] = any(w == 250 for w in call_windows(e, "ts_rank"))
    r["tr_any"] = bool(find_calls(e, "ts_rank"))
    r["tr_other"] = r["tr_any"] and not r["tr250"]
    r["bf_any"] = bool(find_calls(e, "ts_backfill"))
    r["bf_wins"] = call_windows(e, "ts_backfill")
    r["bf_win"] = r["bf_wins"][0] if r["bf_wins"] else None
    r["has_rank"] = bool(find_calls(e, "rank"))
    r["plain_rank_only"] = r["has_rank"] and not r["tr_any"]

AMP_FIELDS = ("news_max_up_amt", "news_max_dn_amt")
def is_amp(expr):
    return any(f in expr for f in AMP_FIELDS)

print("="*72)
print("修正后：ts_rank 窗口分布（全部行）")
print("="*72)
c = Counter()
for r in R:
    for w in call_windows(r["expr"], "ts_rank"):
        c[w] += 1
print("ts_rank 窗口出现次数:", dict(sorted(c.items())))
c2 = Counter()
for r in R:
    for w in call_windows(r["expr"], "ts_backfill"):
        c2[w] += 1
print("ts_backfill 窗口出现次数:", dict(sorted(c2.items())))

def tostat(grp, name):
    if not grp:
        print("%-46s n=0" % name); return None
    tos = sorted(r["m"]["turnover"] for r in grp)
    shs = sorted(r["m"]["sharpe"] for r in grp)
    cls = [r["cl"] for r in grp if r["cl"] is not None]
    def pct(p): return tos[min(len(tos)-1, int(p*len(tos)))]
    print("%-46s n=%3d TO: mean=%.3f med=%.3f p10=%.3f p25=%.3f p75=%.3f p90=%.3f | Sh: mean=%.2f med=%.2f max=%.2f"
          % (name, len(grp), sum(tos)/len(tos), tos[len(tos)//2], pct(.1), pct(.25), pct(.75), pct(.9),
             sum(shs)/len(shs), shs[len(shs)//2], shs[-1]))
    return tos

print("\n" + "="*72)
print("3. Turnover 机理（修正版）")
print("="*72)
g250 = [r for r in R if r["tr250"]]
grank = [r for r in R if r["plain_rank_only"]]
gbf = [r for r in R if r["bf_any"]]
tostat(g250, "ts_rank(X,250)")
tostat([r for r in R if r["tr_any"] and not r["tr250"]], "ts_rank(其他窗口)")
tostat(grank, "rank(X) only (无 ts_rank)")
tostat(gbf, "ts_backfill(任意窗口)")
tostat([r for r in R if not r["tr_any"] and not r["bf_any"]], "无 ts_rank 且无 ts_backfill")

print("\n-- ts_rank250 输入是否预平滑（首参含 ts_mean/ts_decay/ts_sum/ts_delta/ts_backfill/ts_std）--")
def smoothed_input(r):
    e = r["expr"]
    for argstr in find_calls(e, "ts_rank"):
        args = split_args(argstr)
        if args and len(args) >= 2 and args[1] == "250":
            a0 = args[0]
            return any(t in a0 for t in ["ts_mean", "ts_decay_linear", "ts_sum", "ts_delta", "ts_backfill", "ts_std_dev", "ts_zscore"])
    return False
sm = [r for r in g250 if smoothed_input(r)]
ns = [r for r in g250 if not smoothed_input(r)]
tostat(sm, "ts_rank250 + 预平滑输入")
tostat(ns, "ts_rank250 + 裸输入(无预平滑)")

print("\n-- rank-only 输入是否预平滑 --")
def smoothed_input_rank(r):
    e = r["expr"]
    for argstr in find_calls(e, "rank"):
        args = split_args(argstr)
        if not args: continue
        a0 = args[0]
        if "ts_rank" in a0: continue
        return any(t in a0 for t in ["ts_mean", "ts_decay_linear", "ts_sum", "ts_delta", "ts_backfill", "ts_std_dev", "ts_zscore"])
    return False
sm = [r for r in grank if smoothed_input_rank(r)]
ns = [r for r in grank if not smoothed_input_rank(r)]
tostat(sm, "rank + 预平滑/backfill 输入")
tostat(ns, "rank + 裸输入")

print("\n-- ts_rank 窗口细分 --")
for w in sorted(c):
    gw = [r for r in R if w in call_windows(r["expr"], "ts_rank")]
    tostat(gw, "ts_rank(...,%d)" % w)

print("\n-- ts_backfill 窗口细分 --")
for w in sorted(c2):
    gw = [r for r in R if w in call_windows(r["expr"], "ts_backfill")]
    tostat(gw, "ts_backfill(...,%d)" % w)

print("\n-- 同字段族内对比（控制字段）：ts_rank250 vs rank-only vs backfill --")
def fam_of(expr):
    fams = set()
    for f in AMP_FIELDS:
        if f in expr: fams.add("amplitude")
    if "high_price_excursion_stddev" in expr or "news_high_exc_stddev" in expr or "news_low_exc_stddev" in expr:
        fams.add("excursion")
    if any(x in expr for x in ["news_eod_close","news_eod_vwap","news_ton_last","news_open","news_post_vwap","news_eod_low","news_eod_high","news_ton_high","news_open_gap"]):
        fams.add("vwap_close")
    if any(x in expr for x in ["news_max_up_ret","news_max_dn_ret","news_prev_day_ret","news_indx_perf"]):
        fams.add("ret")
    return fams or {"other"}
for fam in ["amplitude", "excursion", "vwap_close", "ret"]:
    a = [r for r in R if r["tr250"] and fam in fam_of(r["expr"])]
    b = [r for r in R if r["plain_rank_only"] and fam in fam_of(r["expr"])]
    d = [r for r in R if r["bf_any"] and fam in fam_of(r["expr"])]
    line = "%-12s" % fam
    for nm, g in [("ts_rank250", a), ("rank", b), ("backfill", d)]:
        if g:
            line += " | %s n=%d TOmed=%.3f TOmean=%.3f Shmax=%.2f" % (nm, len(g),
                sorted(r["m"]["turnover"] for r in g)[len(g)//2],
                sum(r["m"]["turnover"] for r in g)/len(g), max(r["m"]["sharpe"] for r in g))
        else:
            line += " | %s n=0" % nm
    print(line)

# 同表达式族直接对照：amplitude 比率信号的不同输出层
print("\n-- amplitude 比率信号 divide(max_up, add(max_up, max_dn)) 的输出层对照 --")
pat = re.compile(r"divide\s*\(\s*news_max_up_amt\s*,\s*add\s*\(\s*news_max_up_amt\s*,\s*news_max_dn_amt\s*\)\s*\)")
amp_ratio = [r for r in R if pat.search(r["expr"])]
tostat(amp_ratio, "amplitude ratio 全部 (%d)" % len(amp_ratio))
layers = defaultdict(list)
for r in amp_ratio:
    e = r["expr"]
    if r["tr250"]: k = "ts_rank250"
    elif r["tr_any"]: k = "ts_rank_other"
    elif "ts_backfill" in e: k = "ts_backfill"
    elif re.search(r"(?<![\w.])rank\s*\(", e): k = "rank"
    else: k = "raw/other"
    layers[k].append(r)
for k in ["raw/other", "rank", "ts_backfill", "ts_rank_other", "ts_rank250"]:
    if layers.get(k): tostat(layers[k], "amplitude ratio + " + k)

# ---------- 4. 低 TO 天花板 + amplitude bf 覆盖 ----------
print("\n" + "="*72)
print("4. 低 TO 区 [10%,40%] 与 amplitude bf 覆盖（修正版）")
print("="*72)
low = [r for r in R if 0.10 <= r["m"]["turnover"] <= 0.40]
print("低 TO 行数: %d / %d" % (len(low), len(R)))
g = defaultdict(list)
for r in low:
    for fam in fam_of(r["expr"]): g[fam].append(r)
for k in sorted(g, key=lambda x: -max(r["m"]["sharpe"] for r in g[x])):
    grp = g[k]
    best = max(grp, key=lambda r: r["m"]["sharpe"])
    print("%-14s n=%3d maxSh=%.2f (TO=%.3f CL=%s) medSh=%.2f" % (k, len(grp), best["m"]["sharpe"],
          best["m"]["turnover"], best["cl"], sorted(r["m"]["sharpe"] for r in grp)[len(grp)//2]))

print("\n-- amplitude 行 bf 覆盖（结果文件）--")
amp = [r for r in R if is_amp(r["expr"])]
print("amplitude 行数: %d" % len(amp))
bfc = Counter()
for r in amp:
    ws = r["bf_wins"]
    bfc[ws[0] if ws else "NO_BF"] += 1
print("amplitude bf 分布:", dict(sorted(bfc.items(), key=lambda x: (x[0]=="NO_BF", str(x[0])))))
print("amplitude 按 bf 表现:")
g = defaultdict(list)
for r in amp:
    ws = r["bf_wins"]
    g[ws[0] if ws else "NO_BF"].append(r)
for k in sorted(g, key=lambda x: (x=="NO_BF", str(x))):
    grp = g[k]
    tos = sorted(r["m"]["turnover"] for r in grp); shs = sorted(r["m"]["sharpe"] for r in grp)
    print("  bf=%-6s n=%3d TOmed=%.3f Shmax=%.2f Shmed=%.2f" % (k, len(grp), tos[len(tos)//2], shs[-1], shs[len(shs)//2]))

print("\n-- amplitude bf 覆盖（提交文件 batch_*.json，去重表达式）--")
amp_sub = {}
for f in sorted(__import__("glob").glob(BASE + "/batch_*.json")):
    if f.endswith("_result.json"): continue
    d = json.load(open(f, encoding="utf-8"))
    for it in d.get("items", []):
        e = it.get("expression", "")
        if is_amp(e):
            amp_sub[e] = (f.split("\\")[-1].split("/")[-1], it.get("type", ""))
print("提交文件中 amplitude 去重表达式数: %d" % len(amp_sub))
bfc2 = Counter()
for e in amp_sub:
    ws = call_windows(e, "ts_backfill")
    bfc2[ws[0] if ws else "NO_BF"] += 1
print("提交文件 amplitude bf 分布:", dict(sorted(bfc2.items(), key=lambda x: (x[0]=="NO_BF", str(x[0])))))

# 全部提交表达式的 bf 分布（不限 amplitude）
bfall = Counter()
nsub = 0
for f in sorted(__import__("glob").glob(BASE + "/batch_*.json")):
    if f.endswith("_result.json"): continue
    d = json.load(open(f, encoding="utf-8"))
    for it in d.get("items", []):
        e = it.get("expression", "")
        nsub += 1
        ws = call_windows(e, "ts_backfill")
        for w in ws: bfall[w] += 1
        if not ws: bfall["NO_BF"] += 1
print("提交文件全部 %d 条 bf 分布:" % nsub, dict(sorted(bfall.items(), key=lambda x: (x[0]=="NO_BF", str(x[0])))))

# ---------- 5. 目标区深挖 ----------
print("\n" + "="*72)
print("5. 目标区 Sh>=1.63 & TO<=25% 与准目标行")
print("="*72)
hi = [r for r in R if r["m"]["sharpe"] >= 1.5]
print("Sh>=1.5 行数: %d, 其 TO 分布:" % len(hi))
tos = sorted(r["m"]["turnover"] for r in hi)
print("  TO min=%.3f p10=%.3f med=%.3f max=%.3f" % (tos[0], tos[len(tos)//10], tos[len(tos)//2], tos[-1]))
print("  Sh>=1.5 且 TO<=0.5: %d 行" % len([r for r in hi if r["m"]["turnover"] <= 0.5]))
for r in sorted([r for r in hi if r["m"]["turnover"] <= 0.6], key=lambda r: -r["m"]["sharpe"])[:10]:
    print("   Sh=%.2f TO=%.3f CL=%s Fit=%.2f [%s] %s" % (r["m"]["sharpe"], r["m"]["turnover"], r["cl"], r["m"]["fitness"], r["batch"], r["expr"][:120]))

print("\n-- CL>=1.58 的行（零警告候选）--")
clok = [r for r in R if r["cl"] is not None and r["cl"] >= 1.58]
print("n=%d" % len(clok))
for r in sorted(clok, key=lambda r: -r["m"]["sharpe"])[:12]:
    print("   CL=%.2f Sh=%.2f TO=%.3f Fit=%.2f [%s] %s" % (r["cl"], r["m"]["sharpe"], r["m"]["turnover"], r["m"]["fitness"], r["batch"], r["expr"][:120]))

# 各字段族最高 Sh 行的 TO 分布（前沿形状补充）
print("\n-- 每字段族 best-Sh 行的 TO --")
g = defaultdict(list)
for r in R:
    for fam in fam_of(r["expr"]): g[fam].append(r)
for k in sorted(g):
    best = max(g[k], key=lambda r: r["m"]["sharpe"])
    print("%-12s best Sh=%.2f @ TO=%.3f CL=%s | %s" % (k, best["m"]["sharpe"], best["m"]["turnover"], best["cl"], best["expr"][:110]))

json.dump({"ok": True}, open(BASE + "/_w11f_tmp_v2_done.json", "w"))
print("\ndone")
