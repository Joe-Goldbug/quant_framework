# -*- coding: utf-8 -*-
"""Detailed metadata for shortlisted V2_B fields + turnover/decay local evidence."""
import json, io, os, re, ast, collections, statistics

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
PACKIDS = [f["id"] for f in AX["B_balance_sheet"]["fields"]]

SHORT = [
    # other466
    "oth466_bs_bv_tang", "oth466_bs_bps_tang_q", "oth466_bs_tang_bps",
    "oth466_bs_assets_tot", "oth466_bs_assets_tot_q", "oth466_q_q_qta_sb",
    "oth466_bs_liab_tot", "oth466_bs_liabs_tot_q", "oth466_bs_shdl_eqt_tot",
    "oth466_bs_sh_cap_and_apic", "oth466_bs_assets_oth_intang_q",
    "oth466_rt_com_eq_tcap", "oth466_rt_assets_com_eq_q", "oth466_rt_assets_gr_q",
    "oth466_rt_cash_roce", "oth466_rt_roce", "oth466_q_aor_tr",
    "oth466_cf_cap_expend_prpty_add", "oth466_q_qe_moc_sb",
    # fundamental23
    "assets_total_3", "book_value_total_equity", "common_shares_outstanding",
    "fnd23_annfv1a_vbts", "fnd23_annfv1a_pbts", "fnd23_annfv1a_eltq",
    "fnd23_intfvm_vbts", "fnd23_intfvm_eltq", "fnd23_intfvm_tota",
    "fnd23_intfvm_dlts", "fnd23_intfvm_dttl", "fnd23_lt_debt",
    "current_maturities_long_term_debt", "current_maturities_short_term",
    "net_current_borrowings", "finance_lease_liabilities",
    "deferred_charge_goodwill", "deferred_charge_goodwill_3",
    "fnd23_tot_assets", "liabilities_equity_total", "fnd23_aor",
]
print("=== shortlist metadata (PACK=in exposed 120) ===")
for fid in SHORT:
    hit = None
    for d in DS:
        if fid in KBALL[d]:
            hit = (d, KBALL[d][fid]); break
    if not hit:
        print(f"  !! {fid} NOT FOUND"); continue
    d, e = hit
    print(f"  {fid:40s} {d:13s} cov={e.get('coverage')} dcov={e.get('dateCoverage')} ac={e.get('alphaCount')} uc={e.get('userCount')} "
          f"PACK={'Y' if fid in PACKIDS else 'n'} | {(e.get('description') or '')[:95]}")

print("\n=== fundamental23 annfv1a vs intfvm vs intfvmfm family comparison (cov/ac/desc) ===")
for fid in ["fnd23_annfv1a_tota", "fnd23_annfvmfm_tota", "fnd23_intfvm_tota", "fnd23_intfvmfm_tota",
            "fnd23_annfv1a_eltq", "fnd23_intfvm_eltq", "fnd23_intfvmfm_eltq",
            "fnd23_annfv1a_vbts", "fnd23_intfvm_vbts",
            "fnd23_annfv1a_lltl", "fnd23_intfvm_lltl",
            "fnd23_annfv1a_dttl", "fnd23_intfvm_dttl", "fnd23_intfvmfm_dttl"]:
    e = KBALL["fundamental23"].get(fid)
    if e:
        print(f"  {fid:34s} cov={e.get('coverage')} ac={e.get('alphaCount')} | {(e.get('description') or '')[:88]}")

# ---- turnover vs decay, and fundamental-signal turnover profile (local) ----
H = json.load(io.open(os.path.join(CAMP, "account_alpha_history_full.json"), encoding="utf-8"))
def sig(a):
    sh, ret = a.get("sharpe"), a.get("returns")
    if not sh or ret is None or abs(sh) < 1e-9: return None
    return abs(ret)/abs(sh)
def corr(xs, ys):
    n=len(xs)
    if n<5: return None
    mx,my=sum(xs)/n,sum(ys)/n
    sx=(sum((x-mx)**2 for x in xs))**.5; sy=(sum((y-my)**2 for y in ys))**.5
    if sx==0 or sy==0: return None
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(sx*sy)

S=[a for a in H if a.get("region")=="USA" and a.get("universe")=="TOP1000" and a.get("delay")==1 and a.get("neutralization")=="STATISTICAL"]
print("\n=== turnover vs decay (all STATISTICAL) ===")
print("  corr(TO, decay) =", round(corr([a.get('turnover') or 0 for a in S],[a.get('decay') or 0 for a in S]),3))
print("  corr(sig, decay) =", round(corr([sig(a) or 0 for a in S],[a.get('decay') or 0 for a in S]),3))
F=[a for a in S if 'fnd17' in (a.get('datasets') or [])]
print("  fnd17-only STATISTICAL n=",len(F))
print("  corr(TO, decay) =", round(corr([a.get('turnover') or 0 for a in F],[a.get('decay') or 0 for a in F]),3))
print("  corr(sig, decay) =", round(corr([sig(a) or 0 for a in F],[a.get('decay') or 0 for a in F]),3))
to=sorted(a.get('turnover') or 0 for a in F)
print("  fnd17 TO: med=%.4f p25=%.4f p75=%.4f" % (statistics.median(to), to[int(.25*len(to))], to[int(.75*len(to))]))
sg=sorted(sig(a) or 0 for a in F)
print("  fnd17 sigma: med=%.4f p75=%.4f p90=%.4f" % (statistics.median(sg), sg[int(.75*len(sg))], sg[int(.9*len(sg))]))
print("\n  fnd17 by decay bucket (TO / sigma):")
bd=collections.defaultdict(list)
for a in F: bd[a.get('decay')].append(a)
for d in sorted(bd, key=lambda x:(x is None, x)):
    v=bd[d]; t=[a.get('turnover') or 0 for a in v]; s=[sig(a) or 0 for a in v]
    print(f"    dec{str(d):<4} n={len(v):4d} medTO={statistics.median(t)*100:5.2f}% medSig={statistics.median(s)*100:5.2f}% medSh={statistics.median([a.get('sharpe') or 0 for a in v]):5.2f}")
