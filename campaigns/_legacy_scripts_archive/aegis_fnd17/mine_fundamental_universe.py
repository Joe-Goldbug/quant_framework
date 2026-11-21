# -*- coding: utf-8 -*-
"""零成本全账户基本面史挖掘：USA/TOP1000/d1 + 所有 fundamental 数据集。

目的：新战役范围 = 全部基本面数据集（≤2 个数据集/表达式）。
在花任何回测配额之前，先用免费 GET 把"本账户哪些基本面数据集真的产出过零 fail alpha"
摸清楚，形成先验地图。

只 GET，零配额。
"""
import json
import os
import sys
import asyncio
from collections import defaultdict

sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

HERE = os.path.dirname(os.path.abspath(__file__))


async def fetch_all(stage):
    out = []
    url = f"{B.brain_client.base_url}/users/self/alphas?limit=100&offset=0&stage={stage}"
    while url:
        r = await B.brain_client._request("GET", url, timeout=120)
        if r.status_code != 200:
            print(f"  ! {stage} HTTP {r.status_code} {r.text[:120]}")
            break
        j = r.json()
        out.extend(j.get("results") or [])
        nxt = j.get("next")
        url = nxt if (nxt and str(nxt).startswith("http")) else None
        print(f"  {stage}: {len(out)}", flush=True)
    return out


def ds_of(code):
    """从表达式里提取数据集前缀集合。"""
    import re
    return sorted(set(re.findall(r"\b([a-z]+\d+)_[a-z0-9_]+", code or "")))


async def main():
    await B.brain_client.ensure_authenticated()
    allrows = []
    for stage in ("OS", "IS"):
        allrows.extend(await fetch_all(stage))
    print(f"\n总计 {len(allrows)} 条 alpha")

    recs = []
    for x in allrows:
        st = x.get("settings") or {}
        isd = x.get("is") or {}
        if not isinstance(isd, dict):
            continue
        code = (x.get("regular") or {}).get("code") or x.get("code") or ""
        checks = isd.get("checks") or []
        fails = [c.get("name") for c in checks if isinstance(c, dict) and c.get("result") == "FAIL"]
        warns = [c.get("name") for c in checks if isinstance(c, dict) and c.get("result") == "WARNING"]
        vals = {c.get("name"): c.get("value") for c in checks if isinstance(c, dict)}
        recs.append({
            "id": x.get("id"), "code": code, "stage": x.get("stage"), "status": x.get("status"),
            "region": st.get("region"), "universe": st.get("universe"), "delay": st.get("delay"),
            "decay": st.get("decay"), "neutralization": st.get("neutralization"),
            "truncation": st.get("truncation"), "nanHandling": st.get("nanHandling"),
            "sharpe": isd.get("sharpe"), "fitness": isd.get("fitness"),
            "turnover": isd.get("turnover"), "returns": isd.get("returns"),
            "margin": isd.get("margin"), "drawdown": isd.get("drawdown"),
            "two_year_sharpe": vals.get("IS_LADDER_SHARPE"),
            "sub_universe_sharpe": vals.get("LOW_SUB_UNIVERSE_SHARPE"),
            "robust_universe_sharpe": vals.get("LOW_ROBUST_UNIVERSE_SHARPE"),
            "prod_corr": isd.get("prodCorrelation"), "self_corr": isd.get("selfCorrelation"),
            "n_fail": len(fails), "fails": fails, "n_warn": len(warns), "warns": warns,
            "datasets": ds_of(code),
        })

    json.dump(recs, open(os.path.join(HERE, "account_alpha_history_full.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- 报表 ----------
    print("\n" + "=" * 130)
    print("★ USA/TOP1000/d1 基本面数据集族统计（全部 stage）")
    print("=" * 130)
    fam = defaultdict(lambda: {"n": 0, "zero": 0, "os": 0, "sh": [], "best": None,
                               "ds": set(), "zero_ids": []})
    for r in recs:
        if r["region"] != "USA" or r["universe"] != "TOP1000" or r["delay"] != 1:
            continue
        key = r["datasets"][0] if r["datasets"] else "?"
        g = fam[key]
        g["n"] += 1
        g["ds"].update(r["datasets"])
        if r["n_fail"] == 0:
            g["zero"] += 1
            g["zero_ids"].append((r["id"], r["stage"], r["sharpe"], r["fitness"], r["status"]))
        if r["stage"] == "OS":
            g["os"] += 1
        if r["sharpe"] is not None:
            g["sh"].append(r["sharpe"])
            if g["best"] is None or r["sharpe"] > (g["best"][1] or -9):
                g["best"] = (r["id"], r["sharpe"], r["stage"], r["status"], r["code"])
    print(f"{'数据集':<16}{'n':>5}{'零fail':>7}{'OS':>5}{'Sh均值':>9}{'Sh最高':>8}  best")
    for k in sorted(fam, key=lambda k: -fam[k]["zero"]):
        g = fam[k]
        sm = sum(g["sh"]) / len(g["sh"]) if g["sh"] else 0
        shmax = max(g["sh"]) if g["sh"] else 0
        b = g["best"]
        print(f"{k:<16}{g['n']:>5}{g['zero']:>7}{g['os']:>5}{sm:>9.2f}{shmax:>8.2f}  "
              f"{b[0] if b else ''} Sh={b[1] if b else 0:.2f} {b[2] if b else ''} {b[3] if b else ''}")

    print("\n" + "=" * 130)
    print("★ 零 fail 明细（USA/TOP1000/d1，全部数据集族，按 Sharpe 降序）")
    print("=" * 130)
    z = sorted([r for r in recs if r["region"] == "USA" and r["universe"] == "TOP1000"
                and r["delay"] == 1 and r["n_fail"] == 0],
               key=lambda r: -(r["sharpe"] or 0))
    print(f"{'id':<11}{'stg':<5}{'Sh':>6}{'Fit':>6}{'TO%':>7}{'Ret%':>7}{'Mgn':>7}{'2Y':>6}"
          f"{'Sub':>6}{'PC':>7}{'SC':>6}{'ds':<26}{'warn'}")
    for r in z:
        print(f"{r['id']:<11}{r['stage']:<5}{(r['sharpe'] or 0):>6.2f}{(r['fitness'] or 0):>6.2f}"
              f"{(r['turnover'] or 0)*100:>7.2f}{(r['returns'] or 0)*100:>7.2f}"
              f"{(r['margin'] or 0)*10000:>7.2f}{(r['two_year_sharpe'] or 0):>6.2f}"
              f"{(r['sub_universe_sharpe'] or 0):>6.2f}{(r['prod_corr'] or 0):>7.3f}"
              f"{(r['self_corr'] or 0):>6.3f}{','.join(r['datasets'])[:25]:<26}"
              f"{','.join(r['warns'])[:30]}")
    print(f"\n零 fail 总数 = {len(z)}")


asyncio.run(main())
