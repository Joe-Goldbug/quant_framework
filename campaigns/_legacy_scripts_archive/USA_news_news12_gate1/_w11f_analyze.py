# -*- coding: utf-8 -*-
"""Wave11-F 结果分析: 逐槽对拍成功标准 + 基线合并 + 前沿重算."""
import json, glob, os, sys

CAMPAIGN = os.path.join(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(CAMPAIGN, "_baseline_final.json")
W11 = os.path.join(CAMPAIGN, "_baseline_w11.json")

# 成功标准 (来自 agent 审计的预注册)
CRITERIA = {
    1: ("A1_WINDOW120", "Sh>=1.58 过 LOW_SHARPE; 证伪 Sh<=1.50"),
    2: ("R2_DFLC_TON", "TO<=90% 且 Sh>=1.30; 三分支: 恒真退化/门生效/书宽崩塌"),
    3: ("M1a_GROUP_STACK", "Sh>=1.20 且 TO<=0.65 = 新前沿点; 证伪 Sh<=0.90"),
    4: ("CTRL_CVW_TSRANK250", "建立裸核基线 (预期 Sh1.35-1.50/TO115-125%)"),
    5: ("M2a_AMP_BF20_TSRANK40", "Sh>=0.90 且 TO<=0.25 = 低 TO 区新点"),
    6: ("D1_PE_GATE", "门增益 = Sh(D1)-Sh(CTRL) >= -0.15 且 TO<=80%"),
    7: ("D2_SI_GATE", "门增益 >= -0.15 且 sub>=0.5"),
    8: ("D3_PE_SI", "|Sh| 显著 (>0.5) 即开辟慢引擎战线; 负值按预注册处理"),
}


def load_rows():
    rows = []
    for f in glob.glob(os.path.join(CAMPAIGN, "batch_*_result.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for r in d.get("alpha_results", []):
            m = r.get("metrics") or {}
            if not m.get("sharpe"):
                continue
            rows.append(m)
    return rows


def main():
    fs = sorted(glob.glob(os.path.join(CAMPAIGN, "batch_w11f_*_result.json")))
    if not fs:
        print("no w11f result yet"); return
    d = json.load(open(fs[-1]))
    sd = json.load(open(fs[-1].replace("_result", "")))
    print(f"=== Wave11-F 结果对拍 ({os.path.basename(fs[-1])}) ===")
    ctrl_sh = None
    recs = []
    for i, r in enumerate(d["alpha_results"]):
        m = r.get("metrics") or {}
        ch = r.get("checks") or {}
        sid = sd["items"][i]["id"]
        name, crit = CRITERIA.get(sid, ("?", ""))
        if sid == 4:
            ctrl_sh = m.get("sharpe")
        recs.append((sid, name, m, ch))
        to, ret = m.get("turnover") or 0, m.get("returns") or 0
        cl = next((c.get("value") for c in (ch.get("warning") or [])
                   if isinstance(c, dict) and c.get("name") == "CLUSTER_TEST"), None)
        print(f"\n槽{sid} {name}")
        print(f"  Sh={m.get('sharpe'):.2f} Fit={m.get('fitness'):.2f} TO={to*100:.1f}% "
              f"Ret={ret*100:.2f}% R/TO={(ret/to if to else 0):.3f} 2Y={m.get('two_year_sharpe'):.2f} "
              f"sub={m.get('sub_universe_sharpe'):.2f} rn={m.get('risk_neutralized_sharpe'):.2f} "
              f"L/S={m.get('longCount')}/{m.get('shortCount')} CL={cl} DD={(m.get('drawdown') or 0)*100:.1f}%")
        print(f"  标准: {crit}")
        f_ = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        w_ = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("warning") or [])]
        print(f"  FAIL={f_}  WARN={w_}")
    # 门增益
    if ctrl_sh is not None:
        print(f"\n=== 门增益 (D 线, 对照 CTRL Sh={ctrl_sh:.2f}) ===")
        for sid, name, m, ch in recs:
            if sid in (6, 7):
                print(f"  槽{sid} {name}: dSh={m.get('sharpe')-ctrl_sh:+.2f} "
                      f"dTO={(m.get('turnover') or 0)*100:.1f}% (vs CTRL)")
    # 全库前沿重算
    rows = load_rows()
    import collections
    b = collections.defaultdict(float)
    for m in rows:
        k = int((m.get("turnover") or 0) * 100 // 10) * 10
        b[k] = max(b[k], m.get("sharpe") or 0)
    print("\n=== 全库 (Sh,TO) 前沿 (n=%d) ===" % len(rows))
    for k in sorted(b):
        print(f"  TO {k:>3}-{k+10:<3}% : maxSh={b[k]:.2f}")
    print("\n全库 Fit top5:")
    for m in sorted(rows, key=lambda x: -(x.get("fitness") or 0))[:5]:
        print(f"  Fit={m.get('fitness'):.2f} Sh={m.get('sharpe'):.2f} "
              f"TO={(m.get('turnover') or 0)*100:.1f}% Ret={(m.get('returns') or 0)*100:.2f}%")


if __name__ == "__main__":
    main()
