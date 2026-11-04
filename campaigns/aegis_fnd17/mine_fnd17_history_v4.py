# -*- coding: utf-8 -*-
"""fnd17 家族权威历史 v4：修正字段路径后重取 code + 指标。

v3 的两处致命解析错误（已定位）：
  1. code 不在 alpha['code']，而在 alpha['regular']['code']      ⇒ 过滤恒 0 条
  2. metrics 不在 alpha['is']['metrics']，而是 alpha['is'] 平铺   ⇒ 指标恒空
  3. 2Y / SubU / RobustU 不在 metrics，在 alpha['is']['checks'][].value ⇒ 必须回填

服务端 ?search=fnd17 是**模糊匹配**（会返回 news alpha），故本地再用 'fnd17_' 精确过滤。
只 GET，零回测配额。
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

OUT = os.path.join(HERE, "fnd17_history_v4.json")


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


async def list_ids(stage):
    ids, url, page = [], None, 0
    url = (f"{B.brain_client.base_url}/users/self/alphas"
           f"?limit=100&offset=0&stage={stage}&search=fnd17")
    while url and page < 20:
        r = await B.brain_client._request("GET", url, timeout=90)
        if r.status_code != 200:
            print(f"  ! {stage} HTTP {r.status_code} {r.text[:120]}")
            break
        j = r.json()
        rows = j.get("results") or []
        ids.extend(x.get("id") for x in rows if x.get("id"))
        page += 1
        if not rows:
            break
        nxt = j.get("next")
        url = nxt if (nxt and str(nxt).startswith("http")) else (
            f"{B.brain_client.base_url}/users/self/alphas"
            f"?limit=100&offset={page*100}&stage={stage}&search=fnd17")
    return ids


async def main():
    await B.brain_client.ensure_authenticated()
    ids = []
    for stage in ("OS", "IS"):
        got = await list_ids(stage)
        print(f"  {stage}: {len(got)} 个候选 id")
        ids.extend(got)
    seen, uniq = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    print(f"合计 {len(uniq)} 唯一 id → 逐条 GET")

    recs = []
    for n, aid in enumerate(uniq, 1):
        try:
            r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}",
                                               timeout=60)
            if r.status_code != 200:
                continue
            x = r.json()
        except Exception:
            continue
        code = (x.get("regular") or {}).get("code") or ""
        if "fnd17" not in code:
            continue
        st = x.get("settings") or {}
        isd = x.get("is") or {}
        m = isd.get("metrics") if isinstance(isd.get("metrics"), dict) else isd
        fail, warn, vals = parse_checks(isd.get("checks") or x.get("checks"))
        recs.append({
            "id": x.get("id"), "code": code, "stage": x.get("stage"), "status": x.get("status"),
            "dateCreated": x.get("dateCreated"), "dateSubmitted": x.get("dateSubmitted"),
            "region": st.get("region"), "universe": st.get("universe"), "delay": st.get("delay"),
            "decay": st.get("decay"), "neutralization": st.get("neutralization"),
            "truncation": st.get("truncation"), "nanHandling": st.get("nanHandling"),
            "pasteurization": st.get("pasteurization"), "maxTrade": st.get("maxTrade"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": m.get("turnover"), "returns": m.get("returns"),
            "margin": m.get("margin"), "drawdown": m.get("drawdown"),
            "two_year_sharpe": vals.get("LOW_2Y_SHARPE"),
            "sub_universe_sharpe": vals.get("LOW_SUB_UNIVERSE_SHARPE"),
            "robust_universe_sharpe": vals.get("LOW_ROBUST_UNIVERSE_SHARPE"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
            "ra_failed_checks": (x.get("ra") or {}).get("ra_failed_checks"),
            "checks_fail": fail, "checks_warn": warn,
            "prod_corr": m.get("prodCorrelation"), "self_corr": m.get("selfCorrelation"),
            "ppa_failed": (x.get("ra") or {}).get("ppa_failed"),
        })
        if n % 40 == 0:
            json.dump(recs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"    ...{n}/{len(uniq)}  已确认 fnd17 {len(recs)} 条")
        await asyncio.sleep(0.15)

    json.dump(recs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n💾 -> {OUT}   精确 fnd17 共 {len(recs)} 条")

    import collections
    print("区域:", collections.Counter((r["region"], r["universe"]) for r in recs).most_common())
    print("设置:", collections.Counter(r["neutralization"] for r in recs).most_common())
    recs.sort(key=lambda r: -(r["sharpe"] or 0))
    print(f"\n{'id':<10}{'reg':<5}{'univ':<10}{'stg':<3}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}"
          f"{'Mgn':>7}{'2Y':>6}{'Sub':>6}{'dec':>4}{'neut':<13}{'PC':>7}  fail")
    for r in recs[:45]:
        print(f"{r['id']:<10}{r['region'] or '':<5}{r['universe'] or '':<10}"
              f"{(r['stage'] or '')[:2]:<3}{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}"
              f"{(r['turnover'] or 0)*100:>7.2f}{(r['returns'] or 0)*100:>8.2f}"
              f"{(r['margin'] or 0)*10000:>7.2f}{(r['two_year_sharpe'] or 0):>6.2f}"
              f"{(r['sub_universe_sharpe'] or 0):>6.2f}"
              f"{(r['decay'] if r['decay'] is not None else -1):>4}{r['neutralization'] or '':<13}"
              f"{(r['prod_corr'] or 0):>7.3f}  {(r['checks_fail'] or [])[:2]}")


asyncio.run(main())
