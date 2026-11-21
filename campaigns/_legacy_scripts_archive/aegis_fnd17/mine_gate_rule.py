# -*- coding: utf-8 -*-
"""零成本：判定平台 checks.fail vs checks.warning 的升级规则。

背景：同一 Sharpe 值在 STATISTICAL 下有时报 FAIL、有时报 WARNING。
本战役的验收标准是"零 fail"，必须先搞清楚这个升级边界，否则会把假通过当真通过。

只 GET，零配额。
"""
import json
import os
import sys
import asyncio
from collections import Counter, defaultdict

sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

HERE = os.path.dirname(os.path.abspath(__file__))
HARD = {"LOW_SHARPE", "LOW_FITNESS", "LOW_2Y_SHARPE", "IS_LADDER_SHARPE",
        "LOW_SUB_UNIVERSE_SHARPE", "LOW_ROBUST_UNIVERSE_SHARPE",
        "HIGH_TURNOVER", "LOW_TURNOVER", "CONCENTRATED_WEIGHT", "UNITS"}


async def fetch_all(stage):
    out = []
    url = f"{B.brain_client.base_url}/users/self/alphas?limit=100&offset=0&stage={stage}"
    while url:
        r = await B.brain_client._request("GET", url, timeout=120)
        if r.status_code != 200:
            break
        j = r.json()
        out.extend(j.get("results") or [])
        nxt = j.get("next")
        url = nxt if (nxt and str(nxt).startswith("http")) else None
    return out


async def main():
    await B.brain_client.ensure_authenticated()
    rows = []
    for stage in ("OS", "IS"):
        rows.extend(await fetch_all(stage))
    print(f"total {len(rows)}")

    recs = []
    for x in rows:
        st = x.get("settings") or {}
        isd = x.get("is") or {}
        if not isinstance(isd, dict):
            continue
        ch = isd.get("checks") or []
        fails = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "FAIL"]
        warns = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "WARNING"]
        vals = {c.get("name"): c.get("value") for c in ch if isinstance(c, dict)}
        recs.append({
            "id": x.get("id"), "dateCreated": x.get("dateCreated"), "stage": x.get("stage"),
            "neutralization": st.get("neutralization"), "decay": st.get("decay"),
            "truncation": st.get("truncation"), "nanHandling": st.get("nanHandling"),
            "maxTrade": st.get("maxTrade"), "pasteurization": st.get("pasteurization"),
            "universe": st.get("universe"), "delay": st.get("delay"),
            "sharpe": isd.get("sharpe"), "fitness": isd.get("fitness"),
            "turnover": isd.get("turnover"), "returns": isd.get("returns"),
            "margin": isd.get("margin"),
            "longCount": isd.get("longCount"), "shortCount": isd.get("shortCount"),
            "two_year_sharpe": vals.get("LOW_2Y_SHARPE"),
            "sub_universe_sharpe": vals.get("LOW_SUB_UNIVERSE_SHARPE"),
            "fails": fails, "warns": warns,
            "short": [c for c in set(fails + warns) if c in HARD],
        })

    json.dump(recs, open(os.path.join(HERE, "account_alpha_history_v2.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    u = [r for r in recs if r["region" if False else "universe"] == "TOP1000"
         and r["delay"] == 1 and r["neutralization"] in
         ("STATISTICAL", "MARKET", "NONE", "INDUSTRY", "SUBINDUSTRY")]

    # ---- 找"同 Sh 同时出现 FAIL 与 WARN"的对撞组 ----
    print("\n" + "=" * 110)
    print("★ 同 (neutralization, sharpe 桶) 下 FAIL vs WARN 对撞组 —— 找判别变量")
    print("=" * 110)
    groups = defaultdict(list)
    for r in u:
        if not r["sharpe"]:
            continue
        bucket = round(r["sharpe"], 1)
        groups[(r["neutralization"], bucket)].append(r)
    collide = []
    for k, g in groups.items():
        f = [x for x in g if "LOW_SHARPE" in x["fails"]]
        w = [x for x in g if "LOW_SHARPE" in x["warns"]]
        if f and w:
            collide.append((k, f, w))
    collide.sort(key=lambda x: -len(x[1]) * len(x[2]))
    print(f"对撞桶数 = {len(collide)}")

    DIMS = ["neutralization", "decay", "truncation", "nanHandling", "maxTrade",
            "pasteurization", "stage"]
    for (k, f, w) in collide[:6]:
        print(f"\n--- bucket {k}  (FAIL n={len(f)}, WARN n={len(w)}) ---")
        for d in DIMS:
            cf = Counter(str(x.get(d)) for x in f)
            cw = Counter(str(x.get(d)) for x in w)
            sep = "<<< 分离" if set(cf) != set(cw) and (not (set(cf) & set(cw))) else ""
            print(f"    {d:<16} FAIL={dict(cf)}  WARN={dict(cw)}  {sep}")
        # 其它短指标
        print(f"    FAIL组其余短指标: {Counter(tuple(sorted(x['short'])) for x in f).most_common(3)}")
        print(f"    WARN组其余短指标: {Counter(tuple(sorted(x['short'])) for x in w).most_common(3)}")
        print(f"    FAIL组 Fit: {min(x['fitness'] for x in f):.2f}~{max(x['fitness'] for x in f):.2f}"
              f"   WARN组 Fit: {min(x['fitness'] for x in w):.2f}~{max(x['fitness'] for x in w):.2f}")
        print(f"    FAIL组 long+short: {min((x['longCount'] or 0)+(x['shortCount'] or 0) for x in f)}~"
              f"{max((x['longCount'] or 0)+(x['shortCount'] or 0) for x in f)}"
              f"   WARN组: {min((x['longCount'] or 0)+(x['shortCount'] or 0) for x in w)}~"
              f"{max((x['longCount'] or 0)+(x['shortCount'] or 0) for x in w)}")
        print(f"    FAIL组日期: {min(x['dateCreated'] or '' for x in f)[:10]}~{max(x['dateCreated'] or '' for x in f)[:10]}"
              f"   WARN组日期: {min(x['dateCreated'] or '' for x in w)[:10]}~{max(x['dateCreated'] or '' for x in w)[:10]}")


asyncio.run(main())
