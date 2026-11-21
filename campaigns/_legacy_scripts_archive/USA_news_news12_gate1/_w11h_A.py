# -*- coding: utf-8 -*-
"""Task A: frontier actuarial analysis on master dataset."""
import json, os, math, statistics
from collections import defaultdict

D = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(D, '_w11h_master.json'), encoding='utf-8'))

def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

out = []
P = out.append

P(f"# Task A 计算 (master={len(rows)} 行)")

# ---------- 0. sanity: metric availability ----------
n_sh = sum(1 for r in rows if num(r['sh']) is not None)
P(f"有 sh 的行: {n_sh}")

# ---------- Law verification ----------
errs = []
for r in rows:
    sh, fit, to, ret = num(r['sh']), num(r['fit']), num(r['to']), num(r['ret'])
    if None in (sh, fit, to, ret):
        continue
    pred = sh * math.sqrt(abs(ret) / max(to, 0.11))
    errs.append(abs(pred - fit))
P(f"[Law1 校验] Fit=Sh*sqrt(|Ret|/max(TO,0.11)): n={len(errs)}, mean|err|={statistics.mean(errs):.4f}, max={max(errs):.4f}")

cons = []
for r in rows:
    sh, to, ret = num(r['sh']), num(r['to']), num(r['ret'])
    if None in (sh, to, ret) or to <= 0:
        continue
    cons.append(sh * sh * (ret / to))
cons = [c for c in cons if c == c]
P(f"[Law2] Sh^2*(Ret/TO): n={len(cons)}, mean={statistics.mean(cons):.4f}, median={statistics.median(cons):.4f}, "
  f"max={max(cons):.4f}, p95={sorted(cons)[int(0.95*len(cons))]:.4f}, >0.30 的行数={sum(1 for c in cons if c>0.30)}")

cl_err = []
cl_n = 0
for r in rows:
    pass  # CLUSTER_TEST values not stored in master (only names); skip
P("[Law4] CLUSTER_TEST 数值未在主集存储（仅 warn 名），从原始 result 文件单独抽取见下")

# CLUSTER_TEST value extraction from raw results
cl_pairs = []
import glob
for f in sorted(glob.glob(os.path.join(D, 'batch_*_result.json'))):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    for r in d.get('alpha_results', []):
        m = r.get('metrics', {}) or {}
        ck = r.get('checks', {}) or {}
        cl = None
        for c in ck.get('warning', []) or []:
            if c.get('name') == 'CLUSTER_TEST':
                cl = c.get('value')
        if cl is not None:
            cl_pairs.append((m.get('sharpe'), cl))
if cl_pairs:
    diffs = [sh - cl for sh, cl in cl_pairs if sh is not None]
    P(f"[Law4] CL≈Sh-x: n={len(cl_pairs)}, mean diff={statistics.mean(diffs):.4f}, "
      f"median={statistics.median(diffs):.4f}, max CL value={max(c for _, c in cl_pairs):.3f}")

# MATCHES_THEMES equivalence
mt_warn_only = 0; mt_total = 0
for f in sorted(glob.glob(os.path.join(D, 'batch_*_result.json'))):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    for r in d.get('alpha_results', []):
        ck = r.get('checks', {}) or {}
        wn = {c.get('name') for c in ck.get('warning', []) or []}
        fl = {c.get('name') for c in ck.get('fail', []) or []}
        ra = (r.get('ra', {}) or {}).get('ra_failed_checks', []) or []
        hard = fl | set(ra)
        if 'MATCHES_THEMES' in wn:
            mt_total += 1
            if 'MATCHES_THEMES' in hard:
                mt_warn_only += 1
P(f"[Law5] MT 警告与 hard fail 同现: {mt_warn_only}/{mt_total}")

# ---------- A1: per-src (Sh, TO) frontier ----------
P("\n## A1 按 src 分组前沿 (每批取 Sh 最大行)")
by_src = defaultdict(list)
for r in rows:
    by_src[r['src']].append(r)

def wave_key(s):
    import re
    m = re.search(r'(gate\d+|w\d+[a-z]?)', s)
    return m.group(1) if m else s

frontier = []
for src, rs in by_src.items():
    valid = [r for r in rs if num(r['sh']) is not None and num(r['to']) is not None]
    if not valid:
        continue
    best = max(valid, key=lambda r: num(r['sh']))
    frontier.append((wave_key(src), num(best['sh']), num(best['to']), num(best['fit']), num(best['ret']), num(best['y2']), best['aid'], len(rs)))
frontier.sort(key=lambda x: (x[0], -x[1]))
for w, sh, to, fit, ret, y2, aid, n in frontier:
    P(f"{w:10s} n={n:2d} bestSh={sh:6.2f} TO={to*100:6.1f}% Fit={fit if fit is not None else float('nan'):5.2f} Ret={ret if ret is not None else float('nan'):7.4f} Y2={y2 if y2 is not None else float('nan'):5.2f} {aid}")

# ---------- A2: conservation distribution (done above, more detail) ----------
P("\n## A2 Sh^2*(Ret/TO) 分布")
cs = sorted(cons)
P(f"n={len(cs)} mean={statistics.mean(cs):.4f} median={statistics.median(cs):.4f} min={cs[0]:.4f} "
  f"p90={cs[int(0.90*len(cs))]:.4f} p95={cs[int(0.95*len(cs))]:.4f} p99={cs[int(0.99*len(cs))]:.4f} max={cs[-1]:.4f}")
top = sorted(cons)[-8:]
P("top8: " + ", ".join(f"{c:.4f}" for c in top))
# fit max
fits = sorted(num(r['fit']) for r in rows if num(r['fit']) is not None)
P(f"Fit: max={fits[-1]:.3f} p95={fits[int(0.95*len(fits))]:.3f} median={statistics.median(fits):.3f}")

# ---------- A3: Fit>=1.0 requirement ----------
P("\n## A3 Fit>=1.0 数学要求 vs 实际")
# Fit = Sh*sqrt(Ret/TO) => need Ret = (1/Sh)^2 * TO
# at conservation level c: Sh^2*Ret/TO = c => Fit = sqrt(c) => max fit = sqrt(max c)
P(f"若守恒 c=0.16 则 Fit 上限=sqrt(0.16)={math.sqrt(0.16):.3f}; 观测 max c={max(cons):.4f} => Fit 上限={math.sqrt(max(cons)):.3f}")
P(f"Fit>=1.0 需要 c>=1.0，即守恒乘积提升 {1.0/max(cons):.2f}x (相对 max) 或 {1.0/0.16:.2f}x (相对典型 0.16)")
# required Ret at various Sh for Fit=1.0, TO=0.7
for sh in [1.58, 1.65, 1.69]:
    ret_need = (1.0/sh)**2 * 0.7
    P(f"  TO=70% 时 Fit=1.0 需 Ret>={ret_need:.4f} (Sh={sh}); 全场 Ret 最大值={max(num(r['ret']) for r in rows if num(r['ret']) is not None):.4f}")
rets = sorted(num(r['ret']) for r in rows if num(r['ret']) is not None)
P(f"Ret 分布: n={len(rets)} median={statistics.median(rets):.4f} p95={rets[int(0.95*len(rets))]:.4f} max={rets[-1]:.4f}")
# low-TO region Ret ceiling
low_to = [(num(r['to']), num(r['ret']), num(r['sh'])) for r in rows if num(r['to']) is not None and num(r['to']) <= 0.25 and num(r['ret']) is not None]
if low_to:
    P(f"TO<=25% 区: n={len(low_to)}, max Ret={max(x[1] for x in low_to):.4f}, max Sh={max(x[2] for x in low_to):.2f}")
    for thr in [0.3, 0.5, 0.7]:
        grp = [(t, rt, s) for t, rt, s in [(num(r['to']), num(r['ret']), num(r['sh'])) for r in rows
               if num(r['to']) is not None and num(r['to']) <= thr and num(r['ret']) is not None]]
        if grp:
            P(f"  TO<={thr*100:.0f}%: n={len(grp)}, maxRet={max(x[1] for x in grp):.4f}, maxSh={max(x[2] for x in grp):.2f}")

# ---------- A4: no-fail-no-warn zone ----------
P("\n## A4 无 fail 无 warn 行")
clean = [r for r in rows if not r['fails'] and not r['warns']]
P(f"数量: {len(clean)}")
if clean:
    best = max(clean, key=lambda r: num(r['sh']) if num(r['sh']) is not None else -99)
    P(f"最高 Sh={num(best['sh'])} TO={num(best['to'])*100:.1f}% Ret={num(best['ret'])} Y2={num(best['y2'])} Fit={num(best['fit'])} Sub={num(best['sub'])} aid={best['aid']}")
    P(f"  expr: {best['expr'][:150]}")
    for r in sorted(clean, key=lambda r: -(num(r['sh']) or -99))[:5]:
        P(f"  {r['aid']} Sh={num(r['sh']):.2f} TO={num(r['to'])*100:.1f}% Ret={num(r['ret']):.4f} Y2={num(r['y2']):.2f} Fit={num(r['fit']):.2f}")

# fails=[] only (warns allowed)
clean2 = [r for r in rows if not r['fails']]
P(f"\n仅 fail=[] (允许 warn): {len(clean2)} 行")
if clean2:
    best = max(clean2, key=lambda r: num(r['sh']) if num(r['sh']) is not None else -99)
    P(f"最高 Sh={num(best['sh'])} TO={num(best['to'])*100:.1f}% Ret={num(best['ret'])} Y2={num(best['y2'])} Fit={num(best['fit'])} warns={best['warns']} aid={best['aid']}")
    for r in sorted(clean2, key=lambda r: -(num(r['sh']) or -99))[:5]:
        P(f"  {r['aid']} Sh={num(r['sh']):.2f} TO={num(r['to'])*100:.1f}% Ret={num(r['ret']):.4f} Y2={num(r['y2']):.2f} Fit={num(r['fit']):.2f} warns={r['warns']}")

# ---------- global tops ----------
P("\n## 全局 Top10 Sh")
for r in sorted(rows, key=lambda r: -(num(r['sh']) or -99))[:10]:
    P(f"  Sh={num(r['sh']):5.2f} Fit={num(r['fit']):5.2f} TO={num(r['to'])*100:5.1f}% Ret={num(r['ret']):.4f} Y2={num(r['y2']):5.2f} fails={len(r['fails'])} warns={r['warns']} {r['aid']}")

# ---------- (Sh,TO) ladder check ----------
P("\n## A1b (Sh,TO) 阶梯前沿 (按 TO 分桶取 max Sh)")
buckets = [(0, 0.1), (0.1, 0.25), (0.25, 0.375), (0.375, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.3), (1.3, 99)]
for lo, hi in buckets:
    grp = [r for r in rows if num(r['to']) is not None and lo <= num(r['to']) < hi and num(r['sh']) is not None]
    if grp:
        b = max(grp, key=lambda r: num(r['sh']))
        P(f"TO[{lo:.2f},{hi:.2f}): n={len(grp):3d} maxSh={num(b['sh']):5.2f} (Fit={num(b['fit']):.2f}, Ret={num(b['ret']):.4f}, Y2={num(b['y2']):.2f}) {b['aid']}")

txt = "\n".join(out)
open(os.path.join(D, '_w11h_A_out.txt'), 'w', encoding='utf-8').write(txt)
print(txt)
