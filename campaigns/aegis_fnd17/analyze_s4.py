# -*- coding: utf-8 -*-
"""S4 全部批次统一分析（兼容 alpha.metrics / alpha.is.metrics 两种布局）

★ 布局差异是真实的平台行为：
    create_simulation → alpha['metrics']            （扁平）
    fetch_multi / 直查 → alpha['is']['metrics']      （嵌套）
  早期 stage5_audit 只读顶层 alpha['checks'] ⇒ 恒得空 ⇒ 假通过。本模块两处都读。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_SIGMA = 0.0257
BASE_SH = 1.11
BASE_FIT = 0.53
BASE_MGN = 9.59


def metrics_of(a):
    if not isinstance(a, dict):
        return {}
    m = a.get("metrics")
    if isinstance(m, dict) and m:
        return m
    is_ = a.get("is")
    if isinstance(is_, dict):
        m = is_.get("metrics")
        if isinstance(m, dict) and m:
            return m
        if any(k in is_ for k in ("sharpe", "returns", "turnover", "fitness")):
            return is_
    return {}


def checks_of(a):
    if not isinstance(a, dict):
        return [], []
    ch = a.get("checks")
    if ch is None:
        is_ = a.get("is")
        if isinstance(is_, dict):
            ch = is_.get("checks")
    if isinstance(ch, list):
        f = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "FAIL"]
        w = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "WARNING"]
        return f, w
    if isinstance(ch, dict):
        return list(ch.get("fail") or []), list(ch.get("warning") or [])
    return [], []


def settings_of(a):
    if not isinstance(a, dict):
        return {}
    s = a.get("settings")
    if isinstance(s, dict) and s:
        return s
    is_ = a.get("is")
    if isinstance(is_, dict):
        s = is_.get("settings")
        if isinstance(s, dict):
            return s
    return {}


def load(fname):
    p = os.path.join(HERE, fname)
    if not os.path.exists(p):
        return []
    d = json.load(open(p, encoding="utf-8"))
    out = []
    for r in d.get("alpha_results", []):
        a = r.get("alpha") or {}
        m = metrics_of(a)
        if not m or m.get("sharpe") is None:
            continue
        fails, warns = checks_of(a)
        s = settings_of(a)
        sh = m.get("sharpe") or 0
        ret = m.get("returns") or 0
        to = m.get("turnover") or 0
        sigma = abs(ret) / abs(sh) if sh else 0
        out.append({
            "slot": r.get("slot"), "seed_id": r.get("seed_id") or "",
            "alpha_id": a.get("id"), "expr": r.get("expr", ""),
            "sh": sh, "fit": m.get("fitness") or 0, "ret": ret, "to": to,
            "sigma": sigma, "mgn": (m.get("margin") or 0) * 10000,
            "y2": m.get("two_year_sharpe"), "subu": m.get("sub_universe_sharpe"),
            "fails": fails, "warns": warns,
            "ls": f"{m.get('longCount')}/{m.get('shortCount')}",
            "decay": s.get("decay"), "neut": s.get("neutralization"),
            "nan": s.get("nanHandling"), "trunc": s.get("truncation"),
        })
    return out


BATCHES = [
    ("S1", "batch_S1_result.json", "一阶逐期差分"),
    ("S2", "batch_S2_result.json", "水平量行业相对价差"),
    ("S4-A", "batch_S4A_result.json", "σ 锐化探针（腿内 vs 单腿）"),
    ("S4-B", "batch_S4B_result.json", "设置档 OFAT"),
    ("S4-C", "batch_S4C_result.json", "σ 锐化施加位置（差值后锐化）"),
    ("S4-P", "batch_S4P_FACTORIAL_result.json", "设置×结构因子批（agent 越权产物）"),
    ("S4-Q", "batch_S4Q_SETTINGS_CROSS_result.json", "设置档交叉（agent 越权产物）"),
]


def main():
    print("=" * 126)
    print("S4 全批次统一分析 · USA/TOP1000/d1 · fundamental17 · 只回测不提交")
    print("=" * 126)

    allrows = []
    for tag, fn, title in BATCHES:
        rows = load(fn)
        if not rows:
            print(f"\n### {tag} —— 无结果\n")
            continue
        rows.sort(key=lambda z: -(abs(z["sh"])))
        allrows += rows
        print(f"\n{'-'*126}\n### {tag} · {title}   ({len(rows)} 条)\n{'-'*126}")
        print(f"{'slot':<5}{'seed_id':<24}{'alpha':<10}{'Sh':>6}{'Fit':>6}{'σ%':>7}"
              f"{'Ret%':>7}{'TO%':>7}{'Mgn':>7}{'2Y':>6}{'SubU':>6}  L/S      FAIL")
        for r in rows:
            print(f"{r['slot']:<5}{r['seed_id'][:23]:<24}{str(r['alpha_id']):<10}"
                  f"{r['sh']:>6.2f}{r['fit']:>6.2f}{r['sigma']*100:>7.2f}"
                  f"{r['ret']*100:>7.2f}{r['to']*100:>7.2f}{r['mgn']:>7.2f}"
                  f"{str(r['y2'] if r['y2'] is not None else '-'):>6}"
                  f"{str(r['subu'] if r['subu'] is not None else '-'):>6}"
                  f"  {r['ls']:<8}{r['fails']}")
        b = rows[0]
        print(f"  → 最佳 |Sh| {b['sh']:.2f} / σ {b['sigma']*100:.2f}% / Fit {b['fit']:.2f} "
              f"/ Mgn {b['mgn']:.2f}bp  [{b['seed_id']}]")

    if not allrows:
        return
    allrows.sort(key=lambda z: -abs(z["sh"]))
    print(f"\n{'='*126}\n### 全战役 Top 8（S1~S4）\n{'='*126}")
    print(f"{'#':<3}{'batch':<7}{'seed_id':<26}{'alpha':<10}{'Sh':>6}{'Fit':>6}{'σ%':>7}"
          f"{'Ret%':>7}{'TO%':>7}{'Mgn':>7}{'2Y':>6}{'SubU':>6}  FAIL")
    for i, r in enumerate(allrows[:8], 1):
        print(f"{i:<3}{r['_tag'] if '_tag' in r else '':<7}{r['seed_id'][:25]:<26}"
              f"{str(r['alpha_id']):<10}{r['sh']:>6.2f}{r['fit']:>6.2f}{r['sigma']*100:>7.2f}"
              f"{r['ret']*100:>7.2f}{r['to']*100:>7.2f}{r['mgn']:>7.2f}"
              f"{str(r['y2'] if r['y2'] is not None else '-'):>6}"
              f"{str(r['subu'] if r['subu'] is not None else '-'):>6}  {r['fails']}")

    print(f"\n{'='*126}")
    print("σ 杠杆目标算术（Fit=1.0 所需 σ）")
    print("=" * 126)
    print(f"  {'Sh':>6}{'σ for Fit=1':>15}{'Ret%':>9}{'Mgn@TO6.7%':>12}{'Mgn@TO2.1%':>12}")
    for sh in (1.04, 1.11, 1.30, 1.58, 1.95):
        sig = 0.125 / (sh ** 3)
        ret = sh * sig
        print(f"  {sh:>6.2f}{sig*100:>15.2f}{ret*100:>9.2f}"
              f"{20*ret/0.067:>12.1f}{20*ret/0.021:>12.1f}")
    print("\n  ⇒ σ≥3.17% 让 Sh=1.58 的 alpha 同时过 Fit 与 Margin")
    print("  ⇒ 但 σ 杠杆不解 Sharpe —— 仍须从 1.11 抬到 1.58")


if __name__ == "__main__":
    main()
