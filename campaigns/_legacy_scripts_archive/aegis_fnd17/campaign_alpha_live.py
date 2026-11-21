# -*- coding: utf-8 -*-
"""战役全部回测 alpha 的权威榜（实时 GET 详情，正确解析字段）。

字段解析修正（相对 mine_fnd17_history_v3）：
  code    → alpha['regular']['code']        （不是 alpha['code']）
  metrics → alpha['is'] 平铺                  （不是 alpha['is']['metrics']）
  checks  → alpha['is']['checks'] 扁平数组
只 GET，零配额。
"""
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

# 战役回测产出（从 S1/S2 结果文件 + S3 A/B 脚本常量汇总）
CAMPAIGN_IDS = {
    # S3 EUR_ORIG (decay=0 / MARKET / nan=OFF)
    "S3_01": "rKRvRR9a", "S3_02": "WjO6OOoQ", "S3_03": "akKqKKQ1", "S3_04": "xAr0rr2W",
    "S3_05": "ZYQeQQzZ", "S3_06": "0mY0YYg8", "S3_07": "j2YbYYGo", "S3_08": "1YNQNNPQ",
    # S3 CAMPAIGN (decay=8 / STATISTICAL / nan=ON)
    "S3C_01": "kqN2N93O", "S3C_02": "zq313emK", "S3C_03": "QPvLv6V5", "S3C_04": "1YNQN0dX",
    "S3C_05": "6XdvdN9J", "S3C_06": "wpQMQWEx", "S3C_07": "omEMEZgn", "S3C_08": "P0odoKOK",
}


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
    out = {}
    for tag, aid in CAMPAIGN_IDS.items():
        r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}",
                                           timeout=60)
        if r.status_code != 200:
            print(f"  ! {aid} HTTP {r.status_code}")
            continue
        x = r.json()
        isd = x.get("is") or {}
        m = isd.get("metrics") if isinstance(isd.get("metrics"), dict) else isd
        st = x.get("settings") or {}
        fail, warn, vals = parse_checks(isd.get("checks") or x.get("checks"))
        out[aid] = {
            "tag": tag, "id": aid,
            "code": (x.get("regular") or {}).get("code"),
            "region": st.get("region"), "universe": st.get("universe"),
            "delay": st.get("delay"), "decay": st.get("decay"),
            "neutralization": st.get("neutralization"), "nanHandling": st.get("nanHandling"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": m.get("turnover"), "returns": m.get("returns"),
            "margin": m.get("margin"), "drawdown": m.get("drawdown"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "robust_universe_sharpe": m.get("robust_universe_sharpe"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
            "ra_failed_checks": (x.get("ra") or {}).get("ra_failed_checks"),
            "checks_fail": fail, "checks_warn": warn,
            "prod_corr": m.get("prodCorrelation"), "self_corr": m.get("selfCorrelation"),
        }
        await asyncio.sleep(0.3)

    json.dump(out, open(os.path.join(HERE, "campaign_alpha_live.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    rows = sorted(out.values(), key=lambda r: -(r["sharpe"] or 0))
    print(f"{'tag':<8}{'id':<10}{'Sh':>7}{'Fit':>7}{'TO%':>7}{'Ret%':>8}{'Mgn':>8}"
          f"{'2Y':>7}{'Sub':>6}{'dec':>4}{'neut':<13}{'L/S':>11}  fail")
    for r in rows:
        print(f"{r['tag']:<8}{r['id']:<10}{(r['sharpe'] or 0):>7.2f}{(r['fitness'] or 0):>7.2f}"
              f"{(r['turnover'] or 0)*100:>7.2f}{(r['returns'] or 0)*100:>8.2f}"
              f"{(r['margin'] or 0)*10000:>8.2f}{(r['two_year_sharpe'] or 0):>7.2f}"
              f"{(r['sub_universe_sharpe'] or 0):>6.2f}"
              f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization'] or '':<13}"
              f"{str(r['longCount'])+'/'+str(r['shortCount']):>11}  {(r['checks_fail'] or [])[:3]}")

    print("\n【最佳】", rows[0]["id"])
    print("  code :", rows[0]["code"])
    print(f"  Sh={rows[0]['sharpe']} Fit={rows[0]['fitness']} TO={rows[0]['turnover']*100:.2f}% "
          f"Ret={rows[0]['returns']*100:.2f}% Mgn={rows[0]['margin']*10000:.2f}bp "
          f"2Y={rows[0]['two_year_sharpe']} Sub={rows[0]['sub_universe_sharpe']}")
    print("  fail :", rows[0]["checks_fail"])
    print("  warn :", rows[0]["checks_warn"])
    print("  ra   :", rows[0]["ra_failed"], rows[0]["ra_failed_checks"])


asyncio.run(main())
