# -*- coding: utf-8 -*-
"""Paired inner-normalization analysis + skeleton fingerprint history."""
import json, io, os, re, ast, collections, statistics, sqlite3, sys

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, os.path.join(ROOT, "quant_framework")); sys.path.insert(0, ROOT); sys.path.insert(0, CAMP)
from quant_framework.core.func_call_corrector import ASTSandboxCorrector

H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
def sig(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9: return None
    return abs(ret)/abs(sh)
def ops(code):
    try: t = ast.parse(code, mode="eval")
    except Exception: return []
    return [getattr(n.func,"id","") or getattr(n.func,"attr","") for n in ast.walk(t) if isinstance(n, ast.Call)]
def top(code):
    try: t = ast.parse(code, mode="eval")
    except Exception: return None
    b=t.body
    root = b if isinstance(b, ast.Call) else (b.value if isinstance(b, ast.Expression) and isinstance(b.value, ast.Call) else None)
    return getattr(root.func,"id","") if root is not None else None

S=[a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1 and a.get("neutralization")=="STATISTICAL"]
rows=[(a,sig(a)) for a in S]; rows=[(a,s) for a,s in rows if s is not None]

print("=== PAIRED: same top-level, inner group_rank vs inner zscore (STATISTICAL USA/TOP1000/d1) ===")
for T in ["power","subtract","ts_decay_linear","zscore"]:
    for inner in ["group_rank","zscore","ts_zscore"]:
        sub=[(a,s) for a,s in rows if top(a.get("code") or "")==T and inner in ops(a.get("code") or "")]
        if len(sub)<4: continue
        sh=[a.get("sharpe") or 0 for a,_ in sub]; sg=[s for _,s in sub]
        # also require NO other inner normalizer to avoid contamination
        clean=[(a,s) for a,s in sub if not any(o in ops(a.get("code") or "") for o in ("zscore","ts_zscore") if o!=inner)]
        csh=[a.get("sharpe") or 0 for a,_ in clean]; csg=[s for _,s in clean]
        print(f"  top={T:15s} inner={inner:10s} n={len(sub):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}%"
              f"  | excl-other-normalizer n={len(clean):4d} medSh={statistics.median(csh) if csh else 0:5.2f} medSig={statistics.median(csg)*100 if csg else 0:5.2f}%")

print("\n=== power exponent effect (top=power, inner group_rank) ===")
pb=collections.defaultdict(list)
for a,s in rows:
    code=a.get("code") or ""
    if top(code)!="power" or "group_rank" not in ops(code): continue
    m=re.search(r"power\([^,]+,\s*(\d+)\)", code)
    if m: pb[int(m.group(1))].append((a,s))
for k in sorted(pb):
    v=pb[k]; sh=[a.get("sharpe") or 0 for a,_ in v]; sg=[s for _,s in v]
    print(f"  power(...,{k}) n={len(v):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in v])*100:5.2f}%")

print("\n=== group granularity: sector vs industry vs subindustry (top=power, inner group_rank) ===")
gb=collections.defaultdict(list)
for a,s in rows:
    code=a.get("code") or ""
    if top(code)!="power" or "group_rank" not in ops(code): continue
    for g in ("sector","industry","subindustry","market"):
        if re.search(r"group_rank\([^)]*,\s*"+g+r"\)", code): gb[g].append((a,s))
for k,v in gb.items():
    sh=[a.get("sharpe") or 0 for a,_ in v]; sg=[s for _,s in v]
    print(f"  {k:12s} n={len(v):4d} medSh={statistics.median(sh):5.2f} maxSh={max(sh):5.2f} medSig={statistics.median(sg)*100:5.2f}% medTO={statistics.median([a.get('turnover') or 0 for a,_ in v])*100:5.2f}%")

print("\n=== skeleton history in fingerprint DB (USA/TOP1000) ===")
db=os.path.join(ROOT,"quant_framework","alphas_record.db")
conn=sqlite3.connect(db); cur=conn.cursor()
cur.execute("SELECT skeleton_str, COUNT(*) FROM alpha_fingerprints WHERE region='USA' AND universe='TOP1000' GROUP BY skeleton_str ORDER BY COUNT(*) DESC LIMIT 30")
for sk,n in cur.fetchall():
    print(f"  n={n:3d}  {sk[:150]}")
conn.close()
