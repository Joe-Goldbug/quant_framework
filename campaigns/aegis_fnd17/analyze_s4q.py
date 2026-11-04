# -*- coding: utf-8 -*-
"""S4Q 设置档全交叉结果 + 三因子主效应分解（只 GET）。"""
import json
import os
import sys
import asyncio
import itertools

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}


def parse_checks(ch):
    fail, warn, vals = [], [], {}
    if isinstance(ch, list):
        for c in ch:
            if not isinstance(c, dict):
                continue
            if c.get("result") == "FAIL":
                fail.append(c.get("name"))
            elif c.get("result") == "WARNING":
                warn.append(c.get("name"))
            if c.get("value") is not None:
                vals[c.get("name")] = c.get("value")
    elif isinstance(ch, dict):
        for c in (ch.get("fail") or []):
            fail.append(c.get("name") if isinstance(c, dict) else c)
        for c in (ch.get("warning") or []):
            warn.append(c.get("name") if isinstance(c, dict) else c)
    return fail, warn, vals


async def main():
    await B.brain_client.ensure_authenticated()
    batch = json.load(open(os.path.join(HERE, "batch_S4Q_SETTINGS_CROSS.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(HERE, "batch_S4Q_SETTINGS_CROSS_state.json"), encoding="utf-8"))
    locs = state.get("locs", {})

    rows = []
    for it in batch["items"]:
        loc = (locs.get(str(it["slot"])) or {}).get("loc")
        if not loc:
            continue
        r = await B.brain_client._request("GET", loc, timeout=60)
        j = r.json()
        aid = j.get("alpha") or j.get("alpha_id") or j.get("id")
        if isinstance(aid, str):
            ar = await B.brain_client._request("GET",
                                               f"{B.brain_client.base_url}/alphas/{aid}",
                                               timeout=60)
            x = ar.json()
        else:
            x = j.get("alpha") or {}
        isd = x.get("is") or {}
        m = isd.get("metrics") if isinstance(isd.get("metrics"), dict) else isd
        fail, warn, vals = parse_checks(isd.get("checks") or x.get("checks"))
        pf = it.get("probe_factors") or {}
        rows.append({
            "slot": it["slot"], "id": x.get("id"), "pf": pf,
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": m.get("turnover"), "returns": m.get("returns"),
            "margin": m.get("margin"),
            "two_year_sharpe": vals.get("LOW_2Y_SHARPE"),
            "sub_universe_sharpe": vals.get("LOW_SUB_UNIVERSE_SHARPE"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "checks_fail": fail, "checks_warn": warn,
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
        })
        await asyncio.sleep(0.2)

    json.dump(rows, open(os.path.join(HERE, "S4Q_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    def g(r, k):
        v = r.get(k)
        return v if isinstance(v, (int, float)) else 0

    print("=" * 118)
    print("S4Q 设置档全交叉 · 载体结构 GRP/ASSET/营业利润率（8 格，表达式完全相同）")
    print("=" * 118)
    print(f"{'neut':<13}{'dec':>4}{'nan':>5}{'id':<10}{'Sh':>7}{'Fit':>6}{'TO%':>7}"
          f"{'Ret%':>8}{'Mgn':>9}{'2Y':>7}{'Sub':>7}{'ra_fail':>9}  fail")
    order = [(n, d, nan) for n in ("MARKET", "STATISTICAL") for d in (0, 8)
             for nan in ("OFF", "ON")]
    for key in order:
        sel = [r for r in rows if (r["pf"].get("neut"), r["pf"].get("decay"),
                                   r["pf"].get("nan")) == key]
        if not sel:
            continue
        r = sel[0]
        print(f"{key[0]:<13}{key[1]:>4}{key[2]:>5}{r['id']:<10}{g(r,'sharpe'):>7.2f}"
              f"{g(r,'fitness'):>6.2f}{g(r,'turnover')*100:>7.2f}{g(r,'returns')*100:>8.2f}"
              f"{g(r,'margin')*10000:>9.2f}{g(r,'two_year_sharpe'):>7.2f}"
              f"{g(r,'sub_universe_sharpe'):>7.2f}{str(r['ra_failed']):>9}  "
              f"{(r['checks_fail'] or [])[:2]}")

    # ---------- 三因子主效应 ----------
    print("\n" + "=" * 118)
    print("主效应（各因子在其余两因子上的边际平均）")
    print("=" * 118)
    for factor in ("neut", "decay", "nan"):
        print(f"\n  -- {factor} --")
        for lvl in sorted({str(r['pf'].get(factor)) for r in rows},
                          key=lambda z: (z.isdigit(), z)):
            sel = [r for r in rows if str(r["pf"].get(factor)) == lvl]
            sh = [g(x, "sharpe") for x in sel]
            to = [g(x, "turnover") for x in sel]
            rt = [g(x, "returns") for x in sel]
            mg = [g(x, "margin") for x in sel]
            fit = [g(x, "fitness") for x in sel]
            print(f"     {lvl:<14} n={len(sel)}  Sh_mean={sum(sh)/len(sh):>6.2f} "
                  f"Sh_max={max(sh):>6.2f}  Fit_mean={sum(fit)/len(fit):>5.2f}  "
                  f"TO%={sum(to)/len(to)*100:>6.2f}  Ret%={sum(rt)/len(rt)*100:>6.2f}  "
                  f"Mgn={sum(mg)/len(mg)*10000:>7.2f}bp")

    # ---------- 门禁达标画像反解 ----------
    print("\n" + "=" * 118)
    print("★ 门禁达标画像反解：每格若 Sharpe 抬到 1.58，还差什么？")
    print("=" * 118)
    print(f"{'neut':<13}{'dec':>4}{'nan':>5}{'Sh_now':>8}{'Ret_now':>9}{'Fit@1.58':>10}"
          f"{'需Ret(Fit)':>11}{'需Ret(Mgn)':>11}{'瓶颈':>10}")
    for key in order:
        sel = [r for r in rows if (r["pf"].get("neut"), r["pf"].get("decay"),
                                   r["pf"].get("nan")) == key]
        if not sel:
            continue
        r = sel[0]
        to, ret = g(r, "turnover"), g(r, "returns")
        denom = max(to, 0.125)
        fit_at_158 = 1.58 * (ret / denom) ** 0.5 if denom else 0
        need_ret_fit = (1.0 ** 2) * denom / (1.58 ** 2)
        need_ret_mgn = 0.5 * to
        need = max(need_ret_fit, need_ret_mgn)
        bottleneck = ("Ret" if need_ret_fit >= need_ret_mgn else "Margin")
        ok = "✅" if (fit_at_158 >= 1.0 and ret >= need_ret_mgn) else "❌"
        print(f"{key[0]:<13}{key[1]:>4}{key[2]:>5}{g(r,'sharpe'):>8.2f}{ret*100:>8.2f}%"
              f"{fit_at_158:>10.3f}{need_ret_fit*100:>10.2f}%{need_ret_mgn*100:>10.2f}%"
              f"{bottleneck:>10}  {ok}")

    # ---------- 最佳格 ----------
    best = max(rows, key=lambda r: g(r, "sharpe"))
    print(f"\n【最高 Sharpe】{best['id']} {best['pf']}")
    print(f"   Sh={g(best,'sharpe'):.2f} Fit={g(best,'fitness'):.2f} "
          f"TO={g(best,'turnover')*100:.2f}% Ret={g(best,'returns')*100:.2f}% "
          f"Mgn={g(best,'margin')*10000:.2f}bp 2Y={g(best,'two_year_sharpe'):.2f} "
          f"Sub={g(best,'sub_universe_sharpe'):.2f}")
    print(f"   fail={best['checks_fail']}")

    print("\n" + "=" * 118)
    print("★ 找「Sharpe 最高 且 已过 Fit/Margin」或「最接近」的格")
    print("=" * 118)
    def score(r):
        to, ret = g(r, "turnover"), g(r, "returns")
        fit_at = 1.58 * (ret / max(to, 0.125)) ** 0.5
        mgn_at = ret / to * 20 * 100 if to else 0
        gate = min(fit_at, mgn_at / 10)      # 1.0 = 双门禁在 Sh=1.58 时恰好达标
        return gate
    for r in sorted(rows, key=score, reverse=True):
        to, ret = g(r, "turnover"), g(r, "returns")
        fit_at = 1.58 * (ret / max(to, 0.125)) ** 0.5
        mgn_at = ret / to * 20 * 100 if to else 0
        print(f"   {r['pf']['neut']:<13} dec={r['pf']['decay']} nan={r['pf']['nan']:<4} "
              f"Sh={g(r,'sharpe'):>5.2f} → 若 Sh=1.58: Fit={fit_at:>5.3f} Mgn={mgn_at:>6.2f}bp "
              f"TO={to*100:>5.2f}%  门禁余量={score(r):>5.2f}")


asyncio.run(main())
