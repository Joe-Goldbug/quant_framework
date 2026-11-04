# -*- coding: utf-8 -*-
"""fnd17 家族全史挖掘 v3：平台 search=fnd17 过滤 + 逐条 GET 详情。

修复链：
  v1 假定 rows["results"] 存在 → 实际存在，但行内**没有 code 字段** ⇒ 字符串过滤恒 0 条。
  v2 自适应解析分页（已修）→ 仍按 x["code"] 过滤 ⇒ 依旧 0 条。
  v3 真相：平台支持 ?search=fnd17（count=310）直接过滤表达式文本 ⇒ 不必本地过滤。

只 GET（零回测配额）。输出全字段供归因：结构族 / 设置档 / 门禁。
"""
import json
import os
import sys
import asyncio
import collections

ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

OUT = os.path.join(ROOT, "campaigns", "aegis_fnd17", "fnd17_history_mined.json")


def parse_checks(ch):
    """兼容 dict{fail,warning,pass} 与 扁平 list[{name,result,value}]。"""
    fail, warn, vals = [], [], {}
    if isinstance(ch, dict):
        for c in (ch.get("fail") or []):
            fail.append(c.get("name") if isinstance(c, dict) else c)
        for c in (ch.get("warning") or []):
            warn.append(c.get("name") if isinstance(c, dict) else c)
        for c in (ch.get("pass") or []):
            if isinstance(c, dict):
                vals[c.get("name")] = c.get("value")
    elif isinstance(ch, list):
        for c in ch:
            if not isinstance(c, dict):
                continue
            r = c.get("result")
            if r == "FAIL":
                fail.append(c.get("name"))
            elif r == "WARNING":
                warn.append(c.get("name"))
            if c.get("value") is not None:
                vals[c.get("name")] = c.get("value")
    return fail, warn, vals


async def list_ids(stage):
    ids = []
    url = (f"{B.brain_client.base_url}/users/self/alphas"
           f"?limit=100&offset=0&stage={stage}&search=fnd17")
    page = 0
    while url and page < 20:
        r = await B.brain_client._request("GET", url, timeout=90)
        if r.status_code != 200:
            print(f"  ! {stage} HTTP {r.status_code} {r.text[:150]}")
            break
        j = r.json()
        rows = j.get("results") or []
        ids.extend(x.get("id") for x in rows if x.get("id"))
        page += 1
        print(f"  {stage} p{page}: +{len(rows)} (total {len(ids)})")
        if not rows:
            break
        nxt = j.get("next")
        if nxt and str(nxt).startswith("http"):
            url = nxt
        else:
            url = (f"{B.brain_client.base_url}/users/self/alphas"
                   f"?limit=100&offset={page*100}&stage={stage}&search=fnd17")
    return ids


async def main():
    await B.brain_client.ensure_authenticated()
    ids = []
    for stage in ("OS", "IS"):
        got = await list_ids(stage)
        print(f"  => {stage}: {len(got)}")
        ids.extend(got)
    # 去重
    seen, uniq = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    print(f"\n合计 {len(uniq)} 个唯一 fnd17 alpha id，开始逐条 GET 详情")

    recs = []
    for n, aid in enumerate(uniq, 1):
        try:
            r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}",
                                               timeout=60)
            if r.status_code != 200:
                print(f"  ! {aid} HTTP {r.status_code}")
                continue
            x = r.json()
        except Exception as ex:
            print(f"  ! {aid} {type(ex).__name__}")
            continue
        st = x.get("settings") or {}
        isd = x.get("is") or {}
        m = isd.get("metrics") or x.get("metrics") or {}
        fail, warn, vals = parse_checks(x.get("checks") or isd.get("checks"))
        recs.append({
            "id": x.get("id"), "code": x.get("code"), "stage": x.get("stage"),
            "status": x.get("status"), "date": x.get("date"),
            "region": st.get("region"), "universe": st.get("universe"),
            "delay": st.get("delay"), "decay": st.get("decay"),
            "neutralization": st.get("neutralization"), "truncation": st.get("truncation"),
            "nanHandling": st.get("nanHandling"), "pasteurization": st.get("pasteurization"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
            "turnover": m.get("turnover"), "returns": m.get("returns"),
            "margin": m.get("margin"), "drawdown": m.get("drawdown"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "robust_universe_sharpe": m.get("robust_universe_sharpe"),
            "investability_sharpe": m.get("investability_sharpe"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
            "ra_failed_checks": (x.get("ra") or {}).get("ra_failed_checks"),
            "checks_fail": fail, "checks_warn": warn, "checks_vals": vals,
            "prod_corr": m.get("prodCorrelation"), "self_corr": m.get("selfCorrelation"),
        })
        if n % 50 == 0:
            print(f"    ...{n}/{len(uniq)}")

    json.dump(recs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n💾 -> {OUT}  ({len(recs)} 条)")

    recs.sort(key=lambda r: -(r["sharpe"] or 0))
    print(f"\n{'id':<10}{'reg':<5}{'univ':<10}{'stg':<3}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}"
          f"{'Mgn':>7}{'2Y':>6}{'Sub':>6}{'dec':>4}{'neut':<13}{'PC':>6}{'SC':>6}  fail")
    for r in recs[:60]:
        print(f"{r['id'] or '':<10}{r['region'] or '':<5}{r['universe'] or '':<10}"
              f"{(r['stage'] or '')[:2]:<3}{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}"
              f"{(r['turnover'] or 0)*100:>7.2f}{(r['returns'] or 0)*100:>8.2f}"
              f"{(r['margin'] or 0)*10000:>7.2f}{(r['two_year_sharpe'] or 0):>6.2f}"
              f"{(r['sub_universe_sharpe'] or 0):>6.2f}{(r['decay'] if r['decay'] is not None else -1):>4}"
              f"{r['neutralization'] or '':<13}{(r['prod_corr'] or 0):>6.3f}{(r['self_corr'] or 0):>6.3f}  "
              f"{(r['checks_fail'] or [])[:3]}")

    # ---- 归因聚合 ----
    print("\n" + "=" * 100)
    print("归因聚合")
    print("=" * 100)
    byreg = collections.Counter((r["region"], r["universe"]) for r in recs)
    print("区域分布:", byreg.most_common())
    byneut = collections.Counter(r["neutralization"] for r in recs)
    print("中性化分布:", byneut.most_common())
    pass_sh = [r for r in recs if not r["checks_fail"] and (r["sharpe"] or 0) >= 1.58]
    print(f"\n★ checks.fail 为空且 Sh>=1.58 的 alpha：{len(pass_sh)} 条")
    for r in pass_sh:
        print(f"   {r['id']} {r['region']}/{r['universe']} d{r['delay']} "
              f"Sh={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']*100:.2f}% "
              f"Ret={r['returns']*100:.2f}% Mgn={r['margin']*10000:.2f}bp "
              f"2Y={r['two_year_sharpe']} PC={r['prod_corr']} SC={r['self_corr']} "
              f"dec={r['decay']} {r['neutralization']}")
        print(f"      {r['code']}")


asyncio.run(main())
