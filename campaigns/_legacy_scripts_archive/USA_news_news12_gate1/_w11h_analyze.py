# -*- coding: utf-8 -*-
"""Wave11-H 回收对拍: 预注册标准逐槽判决 + CW 修复排序 + 锚点轴归因."""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

RES = None
for f in sorted(os.listdir(BASE)):
    if f.startswith("batch_w11h_") and f.endswith("_result.json"):
        RES = os.path.join(BASE, f)
if not RES:
    print("NO RESULT FILE"); sys.exit(1)

data = json.load(open(RES, encoding="utf-8"))
results = data["alpha_results"]
print(f"== Wave11-H 对拍 ({len(results)} 槽) ==\n")

# 预注册标准 (来自 phase13_wave11h_anchor.py)
CRIT = {
    1: ("CW_FIX", "CW 转绿 且 Ret>=7.5", "CW 仍 fail 且 Ret<7"),
    2: ("CW_FIX", "CW 转绿 且 (Sh>=1.25 或 2Y>=2.10)", "Sh<=1.00"),
    3: ("CW_FIX", "CW 转绿 且 Sh>=0.95", "CW fail (bf2 修复不迁移)"),
    4: ("ISOLATION", "Sh>=1.35 (pre 腿独立强度)", "Sh<=0.9 (pre 腿仅交互项)"),
    5: ("CW_FIX", "CW 转绿 (VHEX 推广成立)", "CW fail (推广有边界)"),
    6: ("ANCHOR", "2Y>=2.00 (锚点按 2Y 排序)", "2Y<1.80"),
    7: ("ANCHOR", "CW 转绿 (blend 轴安全对照成立)", "CW fail"),
    8: ("VIRGIN", "Sh>=1.30 (量能确认成立)", "Sh 低 -> 换有符号版重测"),
}

rows = []
for it, r in zip(range(1, 9), results):
    m = r.get("metrics") or {}
    ch = r.get("checks") or {}
    names = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
    wnames = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
    to, ret = m.get("turnover") or 0, m.get("returns") or 0
    rows.append({
        "slot": it, "aid": r.get("alpha_id") or r.get("id"),
        "sh": m.get("sharpe") or 0, "fit": m.get("fitness") or 0,
        "to": to, "ret": ret, "rto": (ret / to) if to else 0,
        "mgn": (m.get("margin") or 0) * 1e4, "y2": m.get("two_year_sharpe") or 0,
        "sub": m.get("sub_universe_sharpe") or 0, "rn": m.get("risk_neutralized_sharpe") or 0,
        "lc": m.get("longCount"), "sc": m.get("shortCount"), "dd": m.get("drawdown") or 0,
        "cw": "CONCENTRATED_WEIGHT" not in names, "fails": names, "warns": wnames,
        "sh2rto": (m.get("sharpe") or 0) ** 2 * ((ret / to) if to else 0),
    })

hdr = f"{'槽':>2} {'Sh':>6} {'Fit':>5} {'TO%':>7} {'Ret%':>7} {'R/TO':>7} {'Mgn':>7} {'2Y':>6} {'sub':>5} {'rn':>5} {'L/S':>11} {'CW':>4} {'Sh²·R/TO':>8}"
print(hdr)
for r in rows:
    print(f"{r['slot']:>2} {r['sh']:>6.2f} {r['fit']:>5.2f} {r['to']*100:>7.1f} {r['ret']*100:>7.2f} "
          f"{r['rto']:>7.3f} {r['mgn']:>7.2f} {r['y2']:>6.2f} {r['sub']:>5.2f} {r['rn']:>5.2f} "
          f"{str(r['lc'])+'/'+str(r['sc']):>11} {'ok' if r['cw'] else 'F':>4} {r['sh2rto']:>8.3f}")

print("\n== 预注册判决 ==")
for r in rows:
    role, ok, no = CRIT[r["slot"]]
    if r["slot"] == 1:
        verdict = "PASS" if (r["cw"] and r["ret"] >= 0.075) else ("FAIL(证伪)" if (not r["cw"] and r["ret"] < 0.07) else "MIXED")
    elif r["slot"] == 2:
        verdict = "PASS" if (r["cw"] and (r["sh"] >= 1.25 or r["y2"] >= 2.10)) else ("FAIL(证伪)" if r["sh"] <= 1.00 else "MIXED")
    elif r["slot"] == 3:
        verdict = "PASS" if (r["cw"] and r["sh"] >= 0.95) else "FAIL"
    elif r["slot"] == 4:
        verdict = "PASS(pre独立)" if r["sh"] >= 1.35 else ("FAIL(仅交互)" if r["sh"] <= 0.9 else "中间")
    elif r["slot"] == 5:
        verdict = "PASS(推广)" if r["cw"] else "FAIL(有界)"
    elif r["slot"] == 6:
        verdict = "PASS(2Y引擎)" if r["y2"] >= 2.00 else ("FAIL" if r["y2"] < 1.80 else "中间")
    elif r["slot"] == 7:
        verdict = "PASS(安全)" if r["cw"] else "FAIL"
    else:
        verdict = "PASS(确认)" if r["sh"] >= 1.30 else "待有符号版"
    print(f"slot{r['slot']} [{role}] {verdict:<14} | 标准: {ok} | 证伪: {no}")

print("\n== CW 修复排序验证 (红队四审: H3(bf2)>H2(ts_rank250)>H1(winsorize)>H5(VHEX)) ==")
cw_fix = [r for r in rows if r["slot"] in (1, 2, 3, 5)]
fixed = [r for r in cw_fix if r["cw"]]
print(f"CW 修复槽: {[(r['slot'], 'ok' if r['cw'] else 'FAIL', round(r['sh'],2), round(r['ret']*100,2)) for r in cw_fix]}")
if fixed:
    best = max(fixed, key=lambda x: x["sh"])
    print(f"转绿槽中最佳: slot{best['slot']} Sh{best['sh']:.2f}/Ret{best['ret']*100:.2f}%/TO{best['to']*100:.1f}%")

print("\n== 锚点轴归因 ==")
print(f"H4 pre单锚 Sh{rows[3]['sh']:.2f}/CW{'ok' if rows[3]['cw'] else 'FAIL'} vs CVW单锚基线 Sh1.54/CW ok")
print(f"H7 main双锚 Sh{rows[6]['sh']:.2f}/CW{'ok' if rows[6]['cw'] else 'FAIL'} vs G8 pre双锚 Sh1.14/CW FAIL")
print(f"H6 post双锚 2Y{rows[5]['y2']:.2f} vs G8 pre双锚 2Y1.80")

print("\n== fail/warn 全景 ==")
for r in rows:
    if r["fails"] or r["warns"]:
        print(f"slot{r['slot']} FAIL={r['fails']} WARN={r['warns']}")

# 追加到 baseline
bpath = os.path.join(BASE, "_baseline_w11.json")
b = json.load(open(bpath, encoding="utf-8"))
rows_exist = b if isinstance(b, list) else b.get("rows", [])
print(f"\n[baseline] 追加前 {len(rows_exist)} 行")
exprs = json.load(open([os.path.join(BASE, f) for f in sorted(os.listdir(BASE))
                        if f.startswith("batch_w11h_") and f.endswith(".json") and "_result" not in f][-1], encoding="utf-8"))
for it, r in zip(exprs["items"], rows):
    rows_exist.append({
        "expr": it["expression"], "aid": r["aid"], "sh": r["sh"], "fit": r["fit"], "to": r["to"],
        "ret": r["ret"], "y2": r["y2"], "sub": r["sub"], "rn": r["rn"], "lc": r["lc"], "sc": r["sc"],
        "dd": r["dd"], "decay": DECAY if (DECAY := 6) else 6, "uni": "TOP1000", "neut": "INDUSTRY",
        "fails": r["fails"], "src": "wave11h", "slot": r["slot"],
    })
json.dump(rows_exist, open(bpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[baseline] 追加后 {len(rows_exist)} 行 -> {bpath}")
