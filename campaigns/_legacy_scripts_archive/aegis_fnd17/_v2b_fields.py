# -*- coding: utf-8 -*-
"""V2_B axis: local-only field explorer over the 4 permitted datasets."""
import json, io, os, re, sys

KB = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\knowledge_base\fields\USA"
CAMP = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\aegis_fnd17"

def load_kb(ds):
    raw = json.load(io.open(os.path.join(KB, ds + ".json"), encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("fields", [])
    return {e["id"]: e for e in raw if isinstance(e, dict) and "id" in e}

KBALL = {ds: load_kb(ds) for ds in ["other466", "fundamental3", "fundamental13", "fundamental23"]}

AXIS = json.load(io.open(os.path.join(CAMP, "axis_field_packs.json"), encoding="utf-8"))
B = AXIS["B_balance_sheet"]
PACK = {f["id"]: f for f in B["fields"]}

COLD = json.load(io.open(os.path.join(CAMP, "multids_cold_pool.json"), encoding="utf-8"))
COLDIDX = {}
for ds, v in COLD.items():
    for f in v.get("fields", []):
        COLDIDX[f["id"]] = dict(f, ds=ds)

HIST = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
HIST_CODES = "\n".join((a.get("code") or "") for a in HIST)
HIST_IDS = {a["id"] for a in HIST}

def field_row(fid):
    ds = None
    for d, m in KBALL.items():
        if fid in m:
            ds = d
            break
    kb = KBALL[ds].get(fid, {}) if ds else {}
    cold = COLDIDX.get(fid, {})
    pack = PACK.get(fid, {})
    return {
        "id": fid, "ds": ds,
        "desc": kb.get("description", ""),
        "cov": kb.get("coverage", cold.get("cov", pack.get("cov"))),
        "ac": kb.get("alphaCount", cold.get("ac", pack.get("ac"))),
        "uc": kb.get("userCount", cold.get("uc", pack.get("uc"))),
        "type": kb.get("type", "MATRIX"),
        "in_pack": fid in PACK,
        "in_cold": fid in COLDIDX,
        "hist_hits": len(re.findall(r"\b" + re.escape(fid) + r"\b", HIST_CODES)),
    }

def show(fids):
    for fid in fids:
        r = field_row(fid)
        print(f"{r['id']:38s} {str(r['ds']):14s} cov={r['cov']} ac={r['ac']} uc={r['uc']} pack={int(r['in_pack'])} cold={int(r['in_cold'])} hist={r['hist_hits']} | {r['desc'][:95]}")

if __name__ == "__main__":
    print("KB sizes:", {k: len(v) for k, v in KBALL.items()})
    print("pack fields:", len(PACK))
    print("cold idx:", len(COLDIDX))
    print()
    if len(sys.argv) > 1:
        show(sys.argv[1:])
