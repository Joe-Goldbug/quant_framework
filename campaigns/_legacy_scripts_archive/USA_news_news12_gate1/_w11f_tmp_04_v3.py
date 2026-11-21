# -*- coding: utf-8 -*-
"""W11F 分析 v3：机制组合覆盖度、CL 上限、TO<=25% 区、前沿形状量化。只读。"""
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
        if depth == 0: res.append(expr[i:j-1])
    return res

def has(expr, fname): return bool(find_calls(expr, fname))
def win_of(expr, fname):
    ws = []
    for a in find_calls(expr, fname):
        # 取最后一个数字参数作窗口
        nums = re.findall(r"(?:^|[\s,(])(\d+)(?:$|[\s,)])", a)
        ws += [int(x) for x in nums]
    return ws

AMP = ("news_max_up_amt", "news_max_dn_amt")
def fams_of(expr):
    s = set()
    if any(f in expr for f in AMP): s.add("amplitude")
    if any(x in expr for x in ["high_price_excursion_stddev","news_high_exc_stddev","news_low_exc_stddev"]): s.add("excursion")
    if any(x in expr for x in ["news_eod_close","news_eod_vwap","news_ton_last","news_open","news_post_vwap","news_eod_low","news_eod_high","news_ton_high","news_open_gap"]): s.add("vwap_close")
    if any(x in expr for x in ["news_max_up_ret","news_max_dn_ret","news_prev_day_ret","news_indx_perf"]): s.add("ret")
    if not s: s.add("other")
    return s

print("="*72); print("A. CL 上限与 CL-Sh 联合分布"); print("="*72)
cls = [(r["cl"], r) for r in R if r["cl"] is not None]
cls.sort(key=lambda x: -x[0])
print("CL max=%.2f  行数 CL>=1.5: %d, CL>=1.4: %d, CL>=1.3: %d" % (cls[0][0],
      sum(1 for c,_ in cls if c>=1.5), sum(1 for c,_ in cls if c>=1.4), sum(1 for c,_ in cls if c>=1.3)))
for c, r in cls[:10]:
    print("CL=%.2f Sh=%.2f gap=%+.2f TO=%.3f [%s] %s" % (c, r["m"]["sharpe"], c-r["m"]["sharpe"], r["m"]["turnover"], r["batch"], r["expr"][:110]))

print("\n-- CL>=1.5 行的共同特征 --")
hi_cl = [r for c, r in cls if c >= 1.5]
for key in ["ts_rank","ts_backfill","ts_decay_linear","ts_mean","winsorize","group_rank","group_neutralize","zscore","ts_zscore","hump","regression_neutral","vec_avg","trade_when"]:
    n = sum(1 for r in hi_cl if has(r["expr"], key))
    if n: print("  %-18s %d/%d" % (key, n, len(hi_cl)))
fc = Counter()
for r in hi_cl:
    for f in fams_of(r["expr"]): fc[f] += 1
print("  字段族:", dict(fc))
sc = Counter(str(r["settings"].get("neutralization")) for r in hi_cl)
print("  中性化:", dict(sc))

print("\n" + "="*72); print("B. TO<=25% 区现状"); print("="*72)
t25 = [r for r in R if r["m"]["turnover"] <= 0.25]
print("TO<=25%% 行数: %d, max Sh=%.2f" % (len(t25), max(r["m"]["sharpe"] for r in t25)))
for r in sorted(t25, key=lambda r: -r["m"]["sharpe"])[:8]:
    print("  Sh=%.2f TO=%.3f CL=%s Fit=%.2f [%s] %s" % (r["m"]["sharpe"], r["m"]["turnover"], r["cl"], r["m"]["fitness"], r["batch"], r["expr"][:110]))

print("\n" + "="*72); print("C. 机制组合覆盖度（高 Sh 区 Sh>=1.4 的 n=%d 行用了什么）" % len([r for r in R if r["m"]["sharpe"]>=1.4])); print("="*72)
hi = [r for r in R if r["m"]["sharpe"] >= 1.4]
combos = Counter()
for r in hi:
    tags = []
    if has(r["expr"], "ts_rank"): tags.append("ts_rank")
    if has(r["expr"], "ts_backfill"): tags.append("ts_backfill")
    if has(r["expr"], "ts_decay_linear"): tags.append("ts_decay")
    if has(r["expr"], "ts_mean"): tags.append("ts_mean")
    if has(r["expr"], "winsorize"): tags.append("winsorize")
    if has(r["expr"], "group_rank"): tags.append("group_rank")
    if has(r["expr"], "group_neutralize"): tags.append("group_neut")
    if has(r["expr"], "ts_zscore") or has(r["expr"], "zscore"): tags.append("zscore")
    if has(r["expr"], "trade_when"): tags.append("trade_when")
    if has(r["expr"], "hump"): tags.append("hump")
    if has(r["expr"], "ts_std_dev"): tags.append("ts_std")
    if has(r["expr"], "ts_delta"): tags.append("ts_delta")
    if has(r["expr"], "ts_sum"): tags.append("ts_sum")
    combos["+".join(sorted(tags)) if tags else "plain_rank_or_raw"] += 1
for k, v in combos.most_common(): print("  %-70s %d" % (k, v))

print("\n-- 全库机制出现次数 --")
for key in ["ts_rank","ts_backfill","ts_decay_linear","ts_mean","ts_std_dev","ts_delta","ts_sum",
            "winsorize","group_rank","group_neutralize","zscore","ts_zscore","hump","trade_when",
            "regression_neutral","regression_beta","regression_resi","vec_avg","vec_count","vec_max",
            "vec_stddev","vec_norm","quantile","scale","sigmoid","ts_returns","ts_min","ts_max",
            "ts_median","ts_skewness","ts_kurt","ts_scale","ts_av_diff","ts_corr","ts_covariance",
            "ts_regression","ts_arg_max","ts_arg_min","bucket","days_from_last_change","group_neutralize"]:
    n = sum(1 for r in R if has(r["expr"], key))
    if n: print("  %-20s %d" % (key, n))

print("\n-- 关键交叉：ts_decay_linear × group_*；ts_rank × group_*；ts_zscore × ts_backfill --")
for a, b in [("ts_decay_linear","group_rank"),("ts_decay_linear","group_neutralize"),
             ("ts_rank","group_rank"),("ts_rank","group_neutralize"),
             ("ts_zscore","ts_backfill"),("ts_zscore","group_rank"),
             ("ts_decay_linear","winsorize"),("ts_decay_linear","ts_backfill"),
             ("hump","ts_backfill"),("regression_neutral","ts_backfill"),
             ("ts_mean","group_rank"),("winsorize","group_rank"),
             ("ts_backfill","trade_when"),("ts_rank","trade_when")]:
    n = sum(1 for r in R if has(r["expr"], a) and has(r["expr"], b))
    print("  %-16s x %-16s : %d" % (a, b, n))

print("\n-- ts_mean / ts_decay_linear / ts_backfill 窗口使用 --")
for f in ["ts_mean","ts_decay_linear","ts_std_dev","ts_delta","ts_sum"]:
    c = Counter()
    for r in R:
        for w in win_of(r["expr"], f): c[w] += 1
    if c: print("  %-16s %s" % (f, dict(sorted(c.items()))))

print("\n" + "="*72); print("D. 前沿形状量化：Sh~TO 与 Sh~gap 条件关系"); print("="*72)
def pearson(xs, ys):
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
    sxy=sum((x-mx)*(y-my) for x,y in zip(xs,ys)); sxx=sum((x-mx)**2 for x in xs); syy=sum((y-my)**2 for y in ys)
    return sxy/(sxx*syy)**0.5 if sxx>0 and syy>0 else float('nan')
tos=[r["m"]["turnover"] for r in R]; shs=[r["m"]["sharpe"] for r in R]
print("corr(TO, Sh) 全库 = %+.3f" % pearson(tos, shs))
# 分 TO 带的 gap 条件均值
for lo, hi_ in [(0,0.25),(0.25,0.5),(0.5,0.75),(0.75,1.0),(1.0,1.15),(1.15,1.35)]:
    sub=[r for r in R if lo<=r["m"]["turnover"]<hi_ and r["cl"] is not None]
    if sub:
        g=[r["cl"]-r["m"]["sharpe"] for r in sub]
        print("  TO[%.2f,%.2f): n=%3d gap mean=%+.4f med=%+.4f  Sh mean=%.2f max=%.2f"
              % (lo,hi_,len(sub),sum(g)/len(g),sorted(g)[len(g)//2],
                 sum(r["m"]["sharpe"] for r in sub)/len(sub), max(r["m"]["sharpe"] for r in sub)))

print("\n-- Sh 与 CL 的联合：满足 Sh>=1.58 的行 CL 分布 --")
sub=[r for r in R if r["m"]["sharpe"]>=1.58]
print("n=%d, CL: min=%.2f med=%.2f max=%.2f" % (len(sub), min(r["cl"] for r in sub),
      sorted(r["cl"] for r in sub)[len(sub)//2], max(r["cl"] for r in sub)))

print("\n-- amplitude 族：输出层 x 预平滑 的 TO/Sh 矩阵 --")
amp=[r for r in R if "amplitude" in fams_of(r["expr"])]
g=defaultdict(list)
for r in amp:
    e=r["expr"]
    if has(e,"ts_rank"):
        w=win_of(e,"ts_rank"); k="ts_rank"+ (str(w[0]) if w else "?")
    elif has(e,"ts_zscore") or has(e,"zscore"): k="zscore"
    elif has(e,"ts_backfill"): k="backfill"+str(win_of(e,"ts_backfill")[:1])
    elif has(e,"ts_decay_linear"): k="decay"
    elif has(e,"ts_mean"): k="ts_mean"
    elif re.search(r"(?<![\w.])rank\s*\(",e): k="rank"
    else: k="raw"
    sm = "smoothed" if any(t in e for t in ["ts_mean","ts_decay_linear","ts_sum","ts_delta","ts_backfill","ts_std_dev"]) else "raw"
    g[(k,sm)].append(r)
for k in sorted(g, key=str):
    grp=g[k]; tos2=sorted(r["m"]["turnover"] for r in grp); shs2=sorted(r["m"]["sharpe"] for r in grp)
    print("  %-22s n=%3d TOmed=%.3f Shmax=%.2f Shmed=%.2f" % (str(k), len(grp), tos2[len(tos2)//2], shs2[-1], shs2[len(shs2)//2]))

print("\ndone v3")
