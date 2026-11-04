# -*- coding: utf-8 -*-
"""Survey balance-sheet-semantic fields across the 4 permitted V2 datasets."""
import json, io, os, re

KB = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\knowledge_base\fields\USA"
CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"

def load(ds):
    raw = json.load(io.open(os.path.join(KB, ds + ".json"), encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("fields", [])
    return {e["id"]: e for e in raw if isinstance(e, dict) and "id" in e}

DS = ["other466", "fundamental3", "fundamental13", "fundamental23"]
KBALL = {d: load(d) for d in DS}

AX = json.load(io.open(os.path.join(CAMP, "axis_field_packs.json"), encoding="utf-8"))
PACK = {f["id"] for f in AX["B_balance_sheet"]["fields"]}

HIST = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
HC = "\n".join((a.get("code") or "") for a in HIST)

PAT = re.compile(r"(tangible|goodwill|intangible|liabilit|debt|equity|book value|book_value|"
                 r"asset|capital|leverage|solven|liquid|working capital|current|revenue|net cash|"
                 r"cash and cash|retained|paid-in|payable|receivab|inventor|reserve|deficit|"
                 r"borrow|note payable|secured|unsecured|premium|treasury|shares out|share count)", re.I)

# PV-risk tokens in id or desc
PVTOK = re.compile(r"(market cap|market capitalization|mktcap|\bcap\b|closing price|share price|"
                   r"price to|per share price)", re.I)

for d in DS:
    print(f"\n{'='*100}\n== {d}  ({len(KBALL[d])} fields)\n{'='*100}")
    rows = []
    for fid, e in KBALL[d].items():
        desc = e.get("description", "") or ""
        if not PAT.search(desc) and not PAT.search(fid):
            continue
        cov = e.get("coverage", 0) or 0
        ac = e.get("alphaCount", 0)
        uc = e.get("userCount", 0)
        if cov < 0.55:
            continue
        pv = "PV?" if PVTOK.search(desc) else ""
        rows.append((ac, fid, cov, uc, e.get("type"), "PACK" if fid in PACK else "", pv, desc[:110].replace("\n", " ")))
    rows.sort(key=lambda r: (r[0], -r[2]))
    for r in rows[:90]:
        print(f"  ac{r[0]:<3} uc{r[3]:<3} cov{r[2]:<7} {str(r[4])[:6]:6s} {r[5]:4s} {r[6]:4s} {r[1]:44s} | {r[7]}")
    print(f"  ... total matched (cov>=0.55): {len(rows)}")
