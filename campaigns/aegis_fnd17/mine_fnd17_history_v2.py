# -*- coding: utf-8 -*-
"""零配额证据采集 v2：修复 v1 的空结果问题，挖掘本账户全部 alpha 的 fnd17 家族。

v1 的 bug：假定 /users/self/alphas 返回 {"results": [...]}，但平台可能返回裸数组
⇒ j.get("results") 恒 None ⇒ out 恒空 ⇒ 落盘 []（而 3qVlb3dN 明明是 fnd17 且 OS/ACTIVE）。

本次：先打印响应形态（dict / list / 分页键），再自适应解析。
只 GET，不 POST，零回测配额。
"""
import json
import os
import sys
import asyncio

ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}


def _rows_of(j):
    """自适应解析 alpha 列表：dict(results/count/next) 或裸 list。"""
    if isinstance(j, list):
        return j, None
    if isinstance(j, dict):
        for k in ("results", "alphas", "items", "data"):
            if isinstance(j.get(k), list):
                return j[k], j.get("next") or j.get("next_url")
        return [], j.get("next")
    return [], None


async def fetch_all(stage):
    out = []
    url = f"{B.brain_client.base_url}/users/self/alphas?limit=100&offset=0&stage={stage}"
    page = 0
    while url and page < 40:
        r = await B.brain_client._request("GET", url, timeout=90)
        if r.status_code != 200:
            print(f"  ! {stage} HTTP {r.status_code} {r.text[:200]}")
            break
        j = r.json()
        if page == 0:
            print(f"  [形态诊断] {stage} type={type(j).__name__} "
                  f"keys={list(j.keys())[:12] if isinstance(j, dict) else 'N/A'}")
        rows, nxt = _rows_of(j)
        out.extend(rows)
        page += 1
        print(f"  {stage} p{page}: +{len(rows)} (total {len(out)})")
        if not rows:
            break
        if nxt and str(nxt).startswith("http"):
            url = nxt
        else:
            # 手动翻页
            off = page * 100
            url = (f"{B.brain_client.base_url}/users/self/alphas"
                   f"?limit=100&offset={off}&stage={stage}")
    return out


async def main():
    await B.brain_client.ensure_authenticated()
    allrows = []
    for stage in ("OS", "IS"):
        allrows.extend(await fetch_all(stage))

    print(f"\n总计 {len(allrows)} 条 alpha")
    f17 = [x for x in allrows if "fnd17" in (x.get("code") or "")]
    print(f"其中 fnd17 {len(f17)} 条")

    recs = []
    for x in f17:
        st = x.get("settings") or {}
        m = x.get("metrics") or (x.get("is") or {})
        if isinstance(x.get("is"), dict):
            m = x["is"].get("metrics") or m
        ch = x.get("checks") or {}
        fails = []
        if isinstance(ch, dict):
            fails = [c.get("name") if isinstance(c, dict) else c for c in (ch.get("fail") or [])]
        elif isinstance(ch, list):
            fails = [c.get("name") for c in ch
                     if isinstance(c, dict) and c.get("result") == "FAIL"]
        recs.append({
            "id": x.get("id"), "code": x.get("code"), "stage": x.get("stage"),
            "status": x.get("status"), "region": st.get("region"), "universe": st.get("universe"),
            "delay": st.get("delay"), "decay": st.get("decay"),
            "neutralization": st.get("neutralization"), "truncation": st.get("truncation"),
            "nanHandling": st.get("nanHandling"),
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": m.get("turnover"),
            "returns": m.get("returns"), "margin": m.get("margin"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "robust_universe_sharpe": m.get("robust_universe_sharpe"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "ra_failed": (x.get("ra") or {}).get("ra_failed"),
            "checks_fail": fails,
            "prod_corr": m.get("prodCorrelation"), "self_corr": m.get("selfCorrelation"),
        })

    recs.sort(key=lambda r: -(r["sharpe"] or 0))
    out_file = os.path.join(ROOT, "campaigns", "aegis_fnd17", "fnd17_history_mined.json")
    json.dump(recs, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n{'id':<11}{'reg':<5}{'univ':<10}{'stg':<4}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>8}"
          f"{'Mgn':>8}{'2Y':>6}{'SubU':>6}{'dec':>5}{'neut':<13}{'nan':<4}{'fail'}")
    for r in recs:
        print(f"{r['id'] or '':<11}{r['region'] or '':<5}{r['universe'] or '':<10}{r['stage'] or '':<4}"
              f"{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}{(r['turnover'] or 0)*100:>7.2f}"
              f"{(r['returns'] or 0)*100:>8.2f}{(r['margin'] or 0)*10000:>8.2f}"
              f"{(r['two_year_sharpe'] or 0):>6.2f}{(r['sub_universe_sharpe'] or 0):>6.2f}"
              f"{(r['decay'] if r['decay'] is not None else -1):>5}{r['neutralization'] or '':<13}"
              f"{r['nanHandling'] or '':<4}{r['checks_fail']}")
        print(f"    {r['code']}")
    print(f"\n💾 -> {out_file}  ({len(recs)} 条)")


asyncio.run(main())
