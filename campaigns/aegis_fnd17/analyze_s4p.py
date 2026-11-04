# -*- coding: utf-8 -*-
"""S4P 析因探针结果读取 + 假设裁决（只 GET）。"""
import json
import os
import sys
import asyncio

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
    if isinstance(ch, dict):
        for c in (ch.get("fail") or []):
            fail.append(c.get("name") if isinstance(c, dict) else c)
        for c in (ch.get("warning") or []):
            warn.append(c.get("name") if isinstance(c, dict) else c)
    elif isinstance(ch, list):
        for c in ch:
            if not isinstance(c, dict):
                continue
            if c.get("result") == "FAIL":
                fail.append(c.get("name"))
            elif c.get("result") == "WARNING":
                warn.append(c.get("name"))
            if c.get("value") is not None:
                vals[c.get("name")] = c.get("value")
    return fail, warn, vals


async def main():
    await B.brain_client.ensure_authenticated()
    batch = json.load(open(os.path.join(HERE, "batch_S4P_FACTORIAL.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(HERE, "batch_S4P_FACTORIAL_state.json"), encoding="utf-8"))
    locs = state.get("locs", {})

    rows = []
    for it in batch["items"]:
        slot = str(it["slot"])
        loc = (locs.get(slot) or {}).get("loc")
        if not loc:
            print(f"  ! slot{slot} 无 location")
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
            "robust_universe_sharpe": vals.get("LOW_ROBUST_UNIVERSE_SHARPE"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "checks_fail": fail, "checks_warn": warn,
        })
        await asyncio.sleep(0.2)

    json.dump(rows, open(os.path.join(HERE, "S4P_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    def g(r, k):
        v = r.get(k)
        return v if isinstance(v, (int, float)) else 0

    print(f"{'slot':<5}{'id':<10}{'norm':<5}{'base':<7}{'tier':<10}{'Sh':>7}{'Fit':>6}"
          f"{'TO%':>7}{'Ret%':>8}{'Mgn':>8}{'2Y':>7}{'Sub':>7}  fail")
    for r in sorted(rows, key=lambda r: (r["pf"].get("norm", ""), r["pf"].get("base", ""),
                                         r["pf"].get("tier", ""))):
        p = r["pf"]
        print(f"{r['slot']:<5}{r['id']:<10}{p.get('norm',''):<5}{p.get('base',''):<7}"
              f"{p.get('tier',''):<10}{g(r,'sharpe'):>7.2f}{g(r,'fitness'):>6.2f}"
              f"{g(r,'turnover')*100:>7.2f}{g(r,'returns')*100:>8.2f}"
              f"{g(r,'margin')*10000:>8.2f}{g(r,'two_year_sharpe'):>7.2f}"
              f"{g(r,'sub_universe_sharpe'):>7.2f}  {(r['checks_fail'] or [])[:2]}")

    # ---------- 假设裁决 ----------
    print("\n" + "=" * 100)
    print("H1 裁决：归一化方式（GRP 分位 vs AMP 保幅度）")
    print("=" * 100)
    for base in ("ASSET", "REV"):
        for tier in ("STAT_D0", "STAT_D8"):
            gsel = [r for r in rows if r["pf"].get("base") == base
                    and r["pf"].get("tier") == tier and r["pf"].get("norm") == "GRP"]
            asel = [r for r in rows if r["pf"].get("base") == base
                    and r["pf"].get("tier") == tier and r["pf"].get("norm") == "AMP"]
            if not gsel or not asel:
                continue
            gsh, ash = g(gsel[0], "sharpe"), g(asel[0], "sharpe")
            grt, art = g(gsel[0], "returns"), g(asel[0], "returns")
            gmg, amg = g(gsel[0], "margin"), g(asel[0], "margin")
            gto, ato = g(gsel[0], "turnover"), g(asel[0], "turnover")
            print(f"  {base:<6} {tier:<9} GRP: Sh={gsh:>6.2f} TO={gto*100:>5.2f}% "
                  f"Ret={grt*100:>5.2f}% Mgn={gmg*10000:>6.2f}bp  |  "
                  f"AMP: Sh={ash:>6.2f} TO={ato*100:>5.2f}% Ret={art*100:>5.2f}% "
                  f"Mgn={amg*10000:>6.2f}bp   ⇒ ΔSh={ash-gsh:+.2f} ΔRet={(art-grt)*100:+.2f}pp")

    print("\n" + "=" * 100)
    print("H2 裁决：设置档（STAT_D0 = decay0/nanOFF vs STAT_D8 = decay8/nanON）")
    print("=" * 100)
    for norm in ("GRP", "AMP"):
        for base in ("ASSET", "REV"):
            d0 = [r for r in rows if r["pf"].get("base") == base
                  and r["pf"].get("tier") == "STAT_D0" and r["pf"].get("norm") == norm]
            d8 = [r for r in rows if r["pf"].get("base") == base
                  and r["pf"].get("tier") == "STAT_D8" and r["pf"].get("norm") == norm]
            if not d0 or not d8:
                continue
            a, b = d0[0], d8[0]
            print(f"  {norm:<4} {base:<6} D0: Sh={g(a,'sharpe'):>6.2f} TO={g(a,'turnover')*100:>5.2f}% "
                  f"Ret={g(a,'returns')*100:>5.2f}% Mgn={g(a,'margin')*10000:>6.2f}bp | "
                  f"D8: Sh={g(b,'sharpe'):>6.2f} TO={g(b,'turnover')*100:>5.2f}% "
                  f"Ret={g(b,'returns')*100:>5.2f}% Mgn={g(b,'margin')*10000:>6.2f}bp   "
                  f"⇒ ΔSh={g(b,'sharpe')-g(a,'sharpe'):+.2f} "
                  f"ΔMgn={(g(b,'margin')-g(a,'margin'))*10000:+.2f}bp")

    print("\n" + "=" * 100)
    print("主效应汇总（对 4 个格取均值）")
    print("=" * 100)
    for key in ("norm", "base", "tier"):
        agg = {}
        for r in rows:
            agg.setdefault(r["pf"].get(key), []).append(r)
        print(f"\n  -- {key} --")
        for k, gsel in agg.items():
            sh = [g(x, "sharpe") for x in gsel]
            rt = [g(x, "returns") for x in gsel]
            mg = [g(x, "margin") for x in gsel]
            to = [g(x, "turnover") for x in gsel]
            print(f"     {str(k):<10} n={len(gsel)} Sh_mean={sum(sh)/len(sh):>6.2f} "
                  f"Sh_max={max(sh):>6.2f} TO%={sum(to)/len(to)*100:>6.2f} "
                  f"Ret%={sum(rt)/len(rt)*100:>6.2f} Mgn={sum(mg)/len(mg)*10000:>7.2f}bp")

    best = max(rows, key=lambda r: g(r, "sharpe"))
    print(f"\n【本批最佳】{best['id']} slot{best['slot']} "
          f"norm={best['pf'].get('norm')} base={best['pf'].get('base')} "
          f"tier={best['pf'].get('tier')}")
    print(f"   Sh={g(best,'sharpe'):.2f} Fit={g(best,'fitness'):.2f} "
          f"TO={g(best,'turnover')*100:.2f}% Ret={g(best,'returns')*100:.2f}% "
          f"Mgn={g(best,'margin')*10000:.2f}bp 2Y={g(best,'two_year_sharpe'):.2f} "
          f"Sub={g(best,'sub_universe_sharpe'):.2f}")
    print(f"   fail={best['checks_fail']}")


asyncio.run(main())
