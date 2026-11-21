# -*- coding: utf-8 -*-
"""Mine account history for balance-sheet-structure factor evidence (local only)."""
import json, io, os, re, ast, collections, statistics

CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))

# balance-sheet-ish semantic buckets over fnd17 field names
BS_TOKENS = {
    "leverage_debt_equity": ["qtotd2eq", "atotd2eq", "2qe2dtlq", "qltd2cap", "debtcap", "altd2ast",
                             "qltd2ast", "atotd2ast", "spdtlq", "netdebt", "qtotd", "atotd", "atotltd"],
    "tangible_book": ["tanbvdolr", "atanbvps", "atanbv", "tangb"],
    "liquidity_current": ["qcurliab", "acurliab", "acurratio", "aquickrati", "aintcov", "ttmintcov",
                          "ptmintcov", "acurast", "ainventory"],
    "asset_composition": ["qtachg", "assets", "atq", "atmtt", "ttmrev", "atotse", "atotce", "qtotce"],
    "roe_roce": ["ptmroepct", "aroepct", "aroa5yavg", "tcpaormtp", "tcpaormtt", "roce"],
}

def sigma(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9:
        return None
    return abs(ret) / abs(sh)

def fields_of(code):
    return set(re.findall(r"\b[a-z0-9]+_[a-z0-9_]+\b", code))

sel = [a for a in H if a.get("region") == "USA" and a.get("universe") == "TOP1000" and a.get("delay") == 1
       and a.get("neutralization") == "STATISTICAL"]

print("=== balance-sheet bucket performance, USA/TOP1000/d1 STATISTICAL ===")
for bucket, toks in BS_TOKENS.items():
    rows = []
    for a in sel:
        fs = fields_of(a.get("code") or "")
        if any(any(t in f for f in fs) for t in toks):
            rows.append(a)
    if not rows:
        print(f"\n-- {bucket}: 0 alphas")
        continue
    shs = [a.get("sharpe") or 0 for a in rows]
    sgs = [s for s in (sigma(a) for a in rows) if s is not None]
    print(f"\n-- {bucket}: n={len(rows)} medSh={statistics.median(shs):.2f} maxSh={max(shs):.2f} "
          f"medSig={statistics.median(sgs)*100:.2f}% maxSig={max(sgs)*100:.2f}% "
          f"n(sig>=3.17)={sum(1 for s in sgs if s>=0.0317)}")
    for a in sorted(rows, key=lambda x: -(x.get("sharpe") or 0))[:4]:
        print(f"   {a['id']} dec{a.get('decay'):<3} Sh {a.get('sharpe'):5.2f} Fit {a.get('fitness'):5.2f} "
              f"sig {sigma(a)*100 if sigma(a) else 0:5.2f}% Ret {a.get('returns'):7.4f} TO {a.get('turnover'):.4f} "
              f"2Y {a.get('two_year_sharpe')} nfail {a.get('n_fail')} :: {(a.get('code') or '')[:170]}")

# ---- which specific BS fields appear at all, and their best ----
print("\n=== per-field best (USA/TOP1000/d1 STATISTICAL) for balance-sheet fields ===")
per = collections.defaultdict(list)
for a in sel:
    for f in fields_of(a.get("code") or ""):
        per[f].append(a)
BS_ALL = set()
for toks in BS_TOKENS.values():
    BS_ALL |= set(toks)
rows = []
for f, al in per.items():
    if not any(t in f for t in BS_ALL):
        continue
    best = max(al, key=lambda a: (a.get("sharpe") or 0))
    rows.append((f, len(al), best.get("sharpe") or 0, (sigma(best) or 0) * 100, best.get("fitness") or 0,
                 best.get("returns") or 0, best.get("turnover") or 0, best.get("two_year_sharpe")))
for r in sorted(rows, key=lambda x: -x[2])[:25]:
    print(f"  {r[0]:34s} n={r[1]:3d} bestSh={r[2]:5.2f} sig={r[3]:5.2f}% Fit={r[4]:5.2f} Ret={r[5]:7.4f} TO={r[6]:.4f} 2Y={r[7]}")
