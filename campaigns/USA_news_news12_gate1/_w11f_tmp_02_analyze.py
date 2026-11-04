# -*- coding: utf-8 -*-
"""W11F 主分析：gap 驱动 / 前沿 / turnover 机理 / 低 TO 天花板 / amplitude bf 覆盖。
只读已有文件，仅写 _w11f_tmp_ 开头的新文件。"""
import json, re, math
from collections import defaultdict, Counter

BASE = r"D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_news_news12_gate1"
rows = json.load(open(BASE + "/_w11f_tmp_rows.json", encoding="utf-8"))
R = [r for r in rows if r["m"]["sharpe"] is not None and r["m"]["turnover"] is not None]
print("usable rows:", len(R))

def pearson(xs, ys):
    n = len(xs)
    if n < 3: return float("nan")
    mx = sum(xs)/n; my = sum(ys)/n
    sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    sxx = sum((x-mx)**2 for x in xs); syy = sum((y-my)**2 for y in ys)
    if sxx <= 0 or syy <= 0: return float("nan")
    return sxy / math.sqrt(sxx*syy)

def rankdata(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    rk = [0.0]*len(v); i = 0
    while i < len(v):
        j = i
        while j+1 < len(v) and v[idx[j+1]] == v[idx[i]]: j += 1
        avg = (i + j)/2.0 + 1
        for k in range(i, j+1): rk[idx[k]] = avg
        i = j+1
    return rk

def spearman(xs, ys):
    return pearson(rankdata(xs), rankdata(ys))

# ---------- 结构特征解析 ----------
def feats(expr):
    f = {}
    f["ts_rank250"] = bool(re.search(r"ts_rank\s*\(\s*[^,]+,\s*250\s*\)", expr))
    f["ts_rank_any"] = bool(re.search(r"ts_rank\s*\(", expr))
    f["ts_rank_other"] = f["ts_rank_any"] and not f["ts_rank250"]
    f["rank"] = bool(re.search(r"(?<!ts_)(?<!\w)rank\s*\(", expr))
    f["ts_backfill"] = bool(re.search(r"ts_backfill\s*\(", expr))
    m = re.search(r"ts_backfill\s*\([^,]+,\s*(\d+)\s*\)", expr)
    f["bf_win"] = int(m.group(1)) if m else None
    f["ts_mean"] = bool(re.search(r"ts_mean\s*\(", expr))
    f["ts_std"] = bool(re.search(r"ts_std_dev\s*\(", expr))
    f["ts_delta"] = bool(re.search(r"ts_delta\s*\(", expr))
    f["ts_sum"] = bool(re.search(r"ts_sum\s*\(", expr))
    f["ts_decay"] = bool(re.search(r"ts_decay_linear\s*\(", expr))
    f["ts_zscore"] = bool(re.search(r"ts_zscore\s*\(", expr))
    f["zscore"] = bool(re.search(r"(?<!ts_)(?<!\w)zscore\s*\(", expr))
    f["winsorize"] = bool(re.search(r"winsorize\s*\(", expr))
    f["reverse"] = bool(re.search(r"(?<!\w)reverse\s*\(", expr))
    f["hump"] = bool(re.search(r"hump\s*\(", expr))
    f["ts_returns"] = bool(re.search(r"ts_returns\s*\(", expr))
    f["group_neutral"] = bool(re.search(r"group_(rank|zscore|neutralize)\s*\(", expr))
    f["scale"] = bool(re.search(r"(?<!\w)scale\s*\(", expr))
    f["sigmoid"] = bool(re.search(r"sigmoid\s*\(", expr))
    f["power"] = bool(re.search(r"(?<!\w)power\s*\(", expr))
    f["regression"] = bool(re.search(r"regression_(beta|neutral|resi)\s*\(", expr))
    f["vec_avg"] = bool(re.search(r"vec_avg\s*\(", expr))
    f["vec_norm"] = bool(re.search(r"vec_norm\s*\(", expr))
    return f

FIELDMAP = [
    ("amplitude", ["news_max_up_amt", "news_max_dn_amt"]),
    ("vwap_close", ["news_eod_close", "news_eod_vwap", "news_ton_last", "news_open",
                    "news_post_vwap", "news_eod_low", "news_eod_high", "news_ton_high", "news_open_gap"]),
    ("excursion_stddev", ["high_price_excursion_stddev", "news_high_exc_stddev", "news_low_exc_stddev"]),
    ("ret", ["news_max_up_ret", "news_max_dn_ret", "news_prev_day_ret", "news_indx_perf"]),
    ("atr", ["news_atr14", "news_atr_ratio"]),
    ("intraday", ["news_mins_3_pct_up","news_mins_4_pct_up","news_mins_5_pct_up","news_mins_20_pct_up",
                  "news_mins_3_pct_dn","news_mins_4_pct_dn","news_mins_5_pct_dn","news_mins_20_pct_dn",
                  "news_pct_30sec","news_pct_1min","news_pct_5_min","news_pct_30min","news_pct_60min","news_pct_120min"]),
    ("fundamental", ["news_pe_ratio", "news_eps_actual", "news_cap", "news_short_interest"]),
    ("vol", ["news_ratio_vol", "news_tot_ticks"]),
]
F2FAM = {}
for fam, fs in FIELDMAP:
    for x in fs: F2FAM[x] = fam

def fieldfam(expr):
    used = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr))
    fams = set()
    for fld in used:
        if fld in F2FAM: fams.add(F2FAM[fld])
        elif fld.startswith("news_"): fams.add("other_news")
        elif fld == "high_price_excursion_stddev": fams.add("excursion_stddev")
    if not fams: fams.add("none")
    return "+".join(sorted(fams))

def outer_layer(expr):
    e = expr.strip()
    m = re.match(r"^(reverse|rank|zscore|winsorize|scale|group_rank|group_zscore|ts_zscore|sigmoid|normalize|vec_norm)\s*\(", e)
    return m.group(1) if m else "raw"

for r in R:
    r["f"] = feats(r["expr"])
    r["fam"] = fieldfam(r["expr"])
    r["outer"] = outer_layer(r["expr"])
    m = r["m"]
    r["gap"] = (r["cl"] - m["sharpe"]) if r["cl"] is not None else None
    r["width"] = (m["longCount"] or 0) + (m["shortCount"] or 0)

RG = [r for r in R if r["gap"] is not None]
print("rows with gap:", len(RG))
gaps = [r["gap"] for r in RG]
print("gap: mean=%.4f median=%.4f min=%.4f max=%.4f" % (sum(gaps)/len(gaps), sorted(gaps)[len(gaps)//2], min(gaps), max(gaps)))

# ================= 1. gap 驱动因素 =================
print("\n" + "="*70)
print("1. GAP 驱动因素（gap = CLUSTER_TEST - Sharpe）")
print("="*70)
METRICS = ["sub_universe_sharpe","two_year_sharpe","turnover","returns","longCount","shortCount",
           "width","drawdown","margin","risk_neutralized_sharpe","sharpe","fitness"]
print("\n-- 相关度 (Pearson / Spearman) --")
corr_out = {}
for k in METRICS:
    xs, ys = [], []
    for r in RG:
        v = r["gap"]
        mv = r["m"].get(k)
        if k == "width": mv = r["width"]
        if mv is None: continue
        xs.append(v); ys.append(mv)
    p = pearson(xs, ys); s = spearman(xs, ys)
    corr_out[k] = (p, s, len(xs))
    print("%-26s n=%3d  pearson=%+.3f  spearman=%+.3f" % (k, len(xs), p, s))

print("\n-- gap 分组统计（按特征有无）--")
group_stats = {}
for key in ["ts_rank250","ts_rank_other","rank","ts_backfill","ts_mean","ts_std","ts_delta",
            "ts_zscore","zscore","winsorize","reverse","hump","ts_decay","group_neutral",
            "scale","sigmoid","power","regression","vec_avg","vec_norm"]:
    a = [r["gap"] for r in RG if r["f"][key]]
    b = [r["gap"] for r in RG if not r["f"][key]]
    if len(a) >= 5 and len(b) >= 5:
        ma = sum(a)/len(a); mb = sum(b)/len(b)
        sa = sorted(a); sb = sorted(b)
        group_stats[key] = (len(a), ma, sa[len(sa)//2], len(b), mb, sb[len(sb)//2])
        print("%-14s ON : n=%3d mean=%+.4f med=%+.4f | OFF: n=%3d mean=%+.4f med=%+.4f | diff=%+.4f"
              % (key, len(a), ma, sa[len(sa)//2], len(b), mb, sb[len(sb)//2], ma-mb))

print("\n-- gap 按 settings --")
for sk in ["neutralization","decay","universe"]:
    g = defaultdict(list)
    for r in RG: g[str(r["settings"].get(sk))].append(r["gap"])
    for k in sorted(g):
        v = g[k]; sv = sorted(v)
        print("%s=%s: n=%3d mean=%+.4f med=%+.4f min=%+.4f max=%+.4f"
              % (sk, k, len(v), sum(v)/len(v), sv[len(sv)//2], sv[0], sv[-1]))

print("\n-- gap 按字段族（单族取该族行）--")
g = defaultdict(list)
for r in RG:
    fams = r["fam"].split("+")
    for fam in set(fams): g[fam].append(r["gap"])
for k in sorted(g, key=lambda x: sum(g[x])/len(g[x])):
    v = g[k]
    print("%-18s n=%3d mean=%+.4f med=%+.4f" % (k, len(v), sum(v)/len(v), sorted(v)[len(v)//2]))

print("\n-- gap 按输出层 --")
g = defaultdict(list)
for r in RG: g[r["outer"]].append(r["gap"])
for k in sorted(g, key=lambda x: sum(g[x])/len(g[x])):
    v = g[k]
    print("%-14s n=%3d mean=%+.4f med=%+.4f" % (k, len(v), sum(v)/len(v), sorted(v)[len(v)//2]))

print("\n-- gap 最小的 10 行 --")
top10 = sorted(RG, key=lambda r: r["gap"])[:10]
for i, r in enumerate(top10, 1):
    m = r["m"]
    print("#%d gap=%+.4f  Sh=%.2f CL=%.2f TO=%.3f Fit=%.2f Ret=%.4f sub=%.2f 2Y=%.2f RN=%.2f [%s]"
          % (i, r["gap"], m["sharpe"], r["cl"], m["turnover"], m["fitness"], m["returns"],
             m["sub_universe_sharpe"], m["two_year_sharpe"], m["risk_neutralized_sharpe"], r["batch"]))
    print("    ", r["expr"][:220])

# ================= 2. 前沿分析 =================
print("\n" + "="*70)
print("2. (Sh, TO) 前沿：TO 10% 分桶")
print("="*70)
buckets = defaultdict(list)
for r in R:
    b = int(r["m"]["turnover"] // 0.10)
    buckets[b].append(r)
print("%-12s %5s %8s %8s %8s %8s %8s" % ("TO bucket","n","maxSh","Sh@max","Fit@max","Ret@max","medSh"))
frontier = {}
for b in sorted(buckets):
    grp = buckets[b]
    best = max(grp, key=lambda r: r["m"]["sharpe"])
    shs = sorted(r["m"]["sharpe"] for r in grp)
    frontier[b] = (len(grp), best["m"]["sharpe"], best["m"]["fitness"], best["m"]["returns"], shs[len(shs)//2])
    print("[%.1f,%.1f)  %5d  %7.2f %7.2f %7.4f %7.2f"
          % (b*0.1, (b+1)*0.1, len(grp), best["m"]["sharpe"], best["m"]["fitness"],
             best["m"]["returns"], shs[len(shs)//2]))

print("\n-- 全史 Fit top10 --")
fit10 = sorted(R, key=lambda r: -(r["m"]["fitness"] or -9))[:10]
for i, r in enumerate(fit10, 1):
    m = r["m"]
    print("#%d Fit=%.3f Sh=%.2f TO=%.3f Ret=%.4f 2Y=%.2f sub=%.2f CL=%s [%s]"
          % (i, m["fitness"], m["sharpe"], m["turnover"], m["returns"], m["two_year_sharpe"],
             m["sub_universe_sharpe"], r["cl"], r["batch"]))
    print("    ", r["expr"][:220])

# 目标区统计
tgt = [r for r in R if r["m"]["sharpe"] >= 1.63 and r["m"]["turnover"] <= 0.25]
tgt2 = [r for r in R if r["m"]["sharpe"] >= 1.58 and r["m"]["turnover"] <= 0.40]
print("\nSh>=1.63 & TO<=25%%: %d 行;  Sh>=1.58 & TO<=40%%: %d 行" % (len(tgt), len(tgt2)))
best_lowto = sorted([r for r in R if r["m"]["turnover"] <= 0.40], key=lambda r: -r["m"]["sharpe"])[:5]
print("TO<=40%% 中 Sh 最高 5 行:")
for r in best_lowto:
    print("  Sh=%.2f TO=%.3f Fit=%.2f CL=%s [%s] %s" % (r["m"]["sharpe"], r["m"]["turnover"], r["m"]["fitness"], r["cl"], r["batch"], r["expr"][:120]))

# ================= 3. turnover 机理 =================
print("\n" + "="*70)
print("3. Turnover 机理：ts_rank250 vs rank vs ts_backfill")
print("="*70)
def tostat(grp, name):
    if not grp: print(name, "n=0"); return
    tos = sorted(r["m"]["turnover"] for r in grp)
    shs = [r["m"]["sharpe"] for r in grp]
    def pct(p): return tos[min(len(tos)-1, int(p*len(tos)))]
    print("%-40s n=%3d TO: mean=%.3f med=%.3f p10=%.3f p25=%.3f p75=%.3f p90=%.3f | Sh mean=%.2f med=%.2f max=%.2f"
          % (name, len(grp), sum(tos)/len(tos), tos[len(tos)//2], pct(.1), pct(.25), pct(.75), pct(.9),
             sum(shs)/len(shs), sorted(shs)[len(shs)//2], max(shs)))

g250 = [r for r in R if r["f"]["ts_rank250"]]
grank = [r for r in R if r["f"]["rank"] and not r["f"]["ts_rank_any"]]
gbf = [r for r in R if r["f"]["ts_backfill"]]
tostat(g250, "ts_rank(X,250)")
tostat(grank, "rank(X) only (no ts_rank)")
tostat(gbf, "ts_backfill any")
tostat([r for r in R if not r["f"]["ts_rank_any"] and not r["f"]["ts_backfill"]], "neither ts_rank nor ts_backfill")

print("\n-- ts_rank250 子组：输入是否预平滑（ts_mean/ts_decay/ts_sum/ts_delta）--")
sm = [r for r in g250 if r["f"]["ts_mean"] or r["f"]["ts_decay"] or r["f"]["ts_sum"] or r["f"]["ts_delta"]]
ns = [r for r in g250 if not (r["f"]["ts_mean"] or r["f"]["ts_decay"] or r["f"]["ts_sum"] or r["f"]["ts_delta"])]
tostat(sm, "ts_rank250 + 预平滑")
tostat(ns, "ts_rank250 + 裸信号(无预平滑)")

print("\n-- ts_rank 窗口细分 --")
for w in [20, 60, 120, 250, 500]:
    gw = [r for r in R if re.search(r"ts_rank\s*\(\s*[^,]+,\s*%d\s*\)" % w, r["expr"])]
    tostat(gw, "ts_rank(...,%d)" % w)

print("\n-- rank(X) 子组：X 是否预平滑 --")
sm = [r for r in grank if r["f"]["ts_mean"] or r["f"]["ts_decay"] or r["f"]["ts_sum"] or r["f"]["ts_delta"] or r["f"]["ts_backfill"]]
ns = [r for r in grank if not (r["f"]["ts_mean"] or r["f"]["ts_decay"] or r["f"]["ts_sum"] or r["f"]["ts_delta"] or r["f"]["ts_backfill"])]
tostat(sm, "rank + 预平滑/backfill")
tostat(ns, "rank + 裸信号")

print("\n-- ts_backfill 窗口细分 --")
for w in [1, 2, 3, 5, 10, 20, 60, 120, 250]:
    gw = [r for r in R if re.search(r"ts_backfill\s*\(\s*[^,]+,\s*%d\s*\)" % w, r["expr"])]
    tostat(gw, "ts_backfill(...,%d)" % w)

# 同一字段族内 ts_rank250 vs rank 的对比（控制字段）
print("\n-- 控制字段族：族内 ts_rank250 vs rank TO 对比 --")
for fam in ["excursion_stddev", "amplitude", "vwap_close", "ret", "intraday"]:
    a = [r for r in R if r["f"]["ts_rank250"] and fam in r["fam"]]
    b = [r for r in R if r["f"]["rank"] and not r["f"]["ts_rank_any"] and fam in r["fam"]]
    if a and b:
        ta = sum(r["m"]["turnover"] for r in a)/len(a)
        tb = sum(r["m"]["turnover"] for r in b)/len(b)
        print("%-18s ts_rank250: n=%3d TO=%.3f | rank: n=%3d TO=%.3f | diff=%+.3f"
              % (fam, len(a), ta, len(b), tb, ta-tb))

# ================= 4. 低 TO 区天花板 =================
print("\n" + "="*70)
print("4. 低 TO 区 [10%, 40%] Sh 天花板")
print("="*70)
low = [r for r in R if 0.10 <= r["m"]["turnover"] <= 0.40]
print("低 TO 行数: %d / %d" % (len(low), len(R)))
print("\n-- 按字段族（含多族拆算）--")
g = defaultdict(list)
for r in low:
    for fam in set(r["fam"].split("+")): g[fam].append(r)
for k in sorted(g, key=lambda x: -max(r["m"]["sharpe"] for r in g[x])):
    grp = g[k]
    best = max(grp, key=lambda r: r["m"]["sharpe"])
    print("%-18s n=%3d maxSh=%.2f (TO=%.3f Fit=%.2f) medSh=%.2f"
          % (k, len(grp), best["m"]["sharpe"], best["m"]["turnover"], best["m"]["fitness"],
             sorted(r["m"]["sharpe"] for r in grp)[len(grp)//2]))
    print("      best: ", best["expr"][:200])

print("\n-- 按结构特征 --")
for key in ["ts_rank250","ts_rank_other","rank","ts_backfill","ts_mean","ts_std","ts_delta",
            "ts_zscore","zscore","winsorize","reverse","hump","ts_decay","group_neutral","scale"]:
    a = [r for r in low if r["f"][key]]
    if a:
        best = max(a, key=lambda r: r["m"]["sharpe"])
        print("%-14s n=%3d maxSh=%.2f medSh=%.2f  best: %s" % (key, len(a), best["m"]["sharpe"],
              sorted(r["m"]["sharpe"] for r in a)[len(a)//2], best["expr"][:100]))

print("\n-- amplitude 族 bf 参数覆盖 --")
amp = [r for r in R if "amplitude" in r["fam"]]
print("amplitude 行数: %d" % len(amp))
bfc = Counter()
for r in amp:
    m = re.search(r"ts_backfill\s*\([^,]+,\s*(\d+)\s*\)", r["expr"])
    bfc[m.group(1) if m else "NO_BF"] += 1
print("amplitude bf 窗口分布:", dict(sorted(bfc.items(), key=lambda x: (x[0]=="NO_BF", x[0]))))
# 全部行 bf 分布
bfall = Counter()
for r in R:
    for w in re.findall(r"ts_backfill\s*\([^,]+,\s*(\d+)\s*\)", r["expr"]):
        bfall[w] += 1
    if not r["f"]["ts_backfill"]: bfall["NO_BF"] += 1
print("全部行 bf 窗口分布:", dict(sorted(bfall.items(), key=lambda x: (x[0]=="NO_BF", x[0]))))
# amplitude 低 TO 行
amp_low = [r for r in low if "amplitude" in r["fam"]]
print("amplitude 低TO行: %d, maxSh=%.2f" % (len(amp_low), max((r["m"]["sharpe"] for r in amp_low), default=float('nan'))))
for r in sorted(amp_low, key=lambda r: -r["m"]["sharpe"])[:5]:
    print("   Sh=%.2f TO=%.3f CL=%s %s" % (r["m"]["sharpe"], r["m"]["turnover"], r["cl"], r["expr"][:150]))

# amplitude 各 bf 的 Sh/TO 表现
print("\n-- amplitude 按 bf 窗口的表现 --")
g = defaultdict(list)
for r in amp:
    m = re.search(r"ts_backfill\s*\([^,]+,\s*(\d+)\s*\)", r["expr"])
    g[m.group(1) if m else "NO_BF"].append(r)
for k in sorted(g, key=lambda x: (x=="NO_BF", int(x) if x!="NO_BF" else 0)):
    grp = g[k]
    tos = sorted(r["m"]["turnover"] for r in grp); shs = sorted(r["m"]["sharpe"] for r in grp)
    print("bf=%-6s n=%3d TO med=%.3f Sh max=%.2f med=%.2f" % (k, len(grp), tos[len(tos)//2], shs[-1], shs[len(shs)//2]))

# 保存中间结果
out = {
    "gap_corr": corr_out,
    "gap_group": group_stats,
    "frontier": {str(k): v for k, v in frontier.items()},
    "gap_top10": [{"gap": r["gap"], "expr": r["expr"], "batch": r["batch"],
                   "m": r["m"], "cl": r["cl"]} for r in top10],
    "fit_top10": [{"expr": r["expr"], "batch": r["batch"], "m": r["m"], "cl": r["cl"]} for r in fit10],
}
json.dump(out, open(BASE + "/_w11f_tmp_analysis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nsaved _w11f_tmp_analysis.json")

# ================= 1b. 高 Sh 子集的条件 gap 分析 =================
print("\n" + "="*70)
print("1b. 条件 gap：Sh>=1.3 子集（n 变化）与 Sh>=1.58 子集")
print("="*70)
for thr in [1.3, 1.58]:
    sub = [r for r in RG if r["m"]["sharpe"] >= thr]
    print("\n-- Sh>=%.2f: n=%d gap mean=%+.4f med=%+.4f --" % (thr, len(sub), sum(r["gap"] for r in sub)/len(sub), sorted(r["gap"] for r in sub)[len(sub)//2]))
    print("-- 特征 ON/OFF --")
    for key in ["ts_rank250","ts_rank_other","rank","ts_backfill","ts_mean","ts_std","ts_delta",
                "ts_zscore","zscore","winsorize","reverse","hump","ts_decay","group_neutral","scale","vec_avg"]:
        a = [r["gap"] for r in sub if r["f"][key]]
        b = [r["gap"] for r in sub if not r["f"][key]]
        if len(a) >= 4 and len(b) >= 4:
            print("%-14s ON : n=%3d mean=%+.4f med=%+.4f | OFF: n=%3d mean=%+.4f med=%+.4f | diff=%+.4f"
                  % (key, len(a), sum(a)/len(a), sorted(a)[len(a)//2], len(b), sum(b)/len(b), sorted(b)[len(b)//2],
                     sum(a)/len(a)-sum(b)/len(b)))
    print("-- 字段族 --")
    g = defaultdict(list)
    for r in sub:
        for fam in set(r["fam"].split("+")): g[fam].append(r["gap"])
    for k in sorted(g, key=lambda x: sum(g[x])/len(g[x])):
        v = g[k]
        print("%-18s n=%3d mean=%+.4f med=%+.4f" % (k, len(v), sum(v)/len(v), sorted(v)[len(v)//2]))
    print("-- settings --")
    for sk in ["neutralization","decay","universe"]:
        g = defaultdict(list)
        for r in sub: g[str(r["settings"].get(sk))].append(r["gap"])
        for k in sorted(g):
            v = g[k]
            print("%s=%s: n=%3d mean=%+.4f med=%+.4f" % (sk, k, len(v), sum(v)/len(v), sorted(v)[len(v)//2]))

# 高 Sh 且 CL>=Sh 的行（gap>=0）——零警告候选特征
print("\n-- gap>=0（CL>=Sh）的行 --")
gp = [r for r in RG if r["gap"] >= 0]
print("n=%d" % len(gp))
for r in sorted(gp, key=lambda r: -r["m"]["sharpe"])[:15]:
    print("gap=%+.3f Sh=%.2f CL=%.2f TO=%.3f [%s] %s" % (r["gap"], r["m"]["sharpe"], r["cl"], r["m"]["turnover"], r["batch"], r["expr"][:130]))

