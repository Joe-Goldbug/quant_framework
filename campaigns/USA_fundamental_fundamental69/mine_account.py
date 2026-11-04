# -*- coding: utf-8 -*-
"""
全账户 IS alpha 挖掘器 v2 (GET-only, 零配额)

背景
----
v1 用 `regular.code` + `is.*` 解析，但列表端点返回的是**精简形态**：
  - code 在 `regular.code`（不是顶层 `code`）
  - checks 在 `is.checks`（list of {name,result,value,limit}），不是 `checks.{fail,warning}`
  - RA/PPA 失败需要按平台语义重算（见 _RA_CHECK_NAMES）

用途：建立本账户在 USA/TOP1000/delay=1 上基本面数据集族的全局地图 ——
  1. 已试过的数据集 / 字段（去重白名单）
  2. 历史上真正产出高质量 alpha 的数据集/字段
  3. 表达式骨架聚类（去常数）
  4. 设置轴画像（decay/neutralization/truncation/nan）

只做 GET，绝不调用仿真或提交接口。
"""
import asyncio
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as bm  # noqa: E402

OUT = os.path.join(HERE, "account_mining.json")

DS_RE = re.compile(r"\b((?:fnd|anl|oth|mdl|pv|news|sec|trn|opt|risk|vec)\d+)_[a-z0-9_]+")
FIELD_RE = re.compile(r"\b[a-z]{2,4}\d+_[a-z0-9_]+")

# 与 brain-mcp main.py 的 _RA_CHECK_NAMES 保持一致（RA 权威失败集）
_RA_CHECK_NAMES = {
    "LOW_SHARPE", "LOW_FITNESS", "LOW_TURNOVER", "HIGH_TURNOVER", "LOW_SUB_UNIVERSE_SHARPE",
    "LOW_2Y_SHARPE", "CONCENTRATED_WEIGHT", "SELF_CORRELATION", "PROD_CORRELATION",
    "LOW_INVESTABILITY_SHARPE", "MATCHES_PYRAMID", "DATA_DIVERSITY", "REGULAR_SUBMISSION",
    "POWER_POOL_CORRELATION", "SELF_CORRELATION_LIMIT", "UNIT_HANDLING",
}


def _bad(chk):
    """平台把「刚好不达标」挪进 WARNING，但 ra 仍算失败 —— result 不是 PASS 即算 bad。"""
    return (chk.get("result") or "").upper() in ("FAIL", "WARNING")


def parse_alpha(a):
    isd = a.get("is") or {}
    reg = a.get("regular")
    code = reg.get("code") if isinstance(reg, dict) else reg
    code = code or a.get("code") or ""
    checks = isd.get("checks") or []

    fails, warns, passes = [], [], []
    for c in checks:
        name = c.get("name")
        res = (c.get("result") or "").upper()
        if res == "FAIL":
            fails.append(name)
        elif res == "WARNING":
            warns.append(name)
        elif res in ("PASS", "OK", ""):
            passes.append(name)

    # RA 权威失败：名字在 _RA_CHECK_NAMES 且 result 不是 PASS
    ra_fail = sorted(set(c.get("name") for c in checks
                         if c.get("name") in _RA_CHECK_NAMES and _bad(c)))
    # 平台语义：LOW_SHARPE / CONCENTRATED_WEIGHT 即使是 WARNING 也进 RA 失败集
    authoritative = sorted(set(fails) | set(ra_fail))

    m = {}
    for k in ("sharpe", "fitness", "turnover", "returns", "margin", "drawdown",
              "longCount", "shortCount", "pnl", "selfCorrelation", "prodCorrelation",
              "sub_universe_sharpe", "two_year_sharpe", "investability_sharpe",
              "risk_neutralized_sharpe", "sharpe_se", "sharpe_t_stat"):
        if isd.get(k) is not None:
            m[k] = isd.get(k)
    inv = isd.get("investabilityConstrained") or {}
    rn = isd.get("riskNeutralized") or {}
    if inv.get("sharpe") is not None:
        m["investability_sharpe"] = inv.get("sharpe")
    if rn.get("sharpe") is not None:
        m["risk_neutralized_sharpe"] = rn.get("sharpe")

    st = a.get("settings") or {}
    return {
        "id": a.get("id"), "code": code,
        "dateCreated": a.get("dateCreated"), "status": a.get("status"),
        "sharpe": m.get("sharpe"), "fitness": m.get("fitness"),
        "turnover": m.get("turnover"), "returns": m.get("returns"),
        "margin": m.get("margin"), "drawdown": m.get("drawdown"),
        "long_count": m.get("longCount"), "short_count": m.get("shortCount"),
        "sub_universe_sharpe": m.get("sub_universe_sharpe"),
        "two_year_sharpe": m.get("two_year_sharpe"),
        "investability_sharpe": m.get("investability_sharpe"),
        "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
        "self_correlation": m.get("selfCorrelation"),
        "prod_correlation": m.get("prodCorrelation"),
        "authoritative_fail": authoritative,
        "checks_fail": sorted(set(fails)),
        "warnings": sorted(set(warns)),
        "settings": {k: st.get(k) for k in
                     ("decay", "neutralization", "truncation", "nanHandling",
                      "universe", "delay", "region")},
        "fields": sorted(set(FIELD_RE.findall(code))),
        "datasets": sorted(set(DS_RE.findall(code))),
    }


async def main():
    rows = []
    url = ("https://api.worldquantbrain.com/users/self/alphas"
           "?limit=100&offset=0&order=-dateCreated"
           "&settings.region=USA&stage=IS")
    pages = 0
    seen = set()
    while url and pages < 130:
        try:
            data = await bm.brain_client._request_json_with_retries(
                "GET", url, op_name=f"mine_account page {pages + 1}", max_retries=8)
        except Exception as e:
            print(f"[warn] page {pages + 1} failed: {e}", flush=True)
            break
        results = data.get("results", []) or []
        for a in results:
            aid = a.get("id")
            if aid in seen:
                continue
            seen.add(aid)
            rows.append(parse_alpha(a))
        url = data.get("next")
        pages += 1
        if pages % 10 == 0 or not results:
            print(f"[page {pages}] cumulative {len(rows)}", flush=True)
        if not results:
            break

    # ---- 聚合画像 --------------------------------------------------------
    by_ds = defaultdict(list)
    for r in rows:
        for d in r["datasets"]:
            by_ds[d].append(r)

    by_field = defaultdict(list)
    for r in rows:
        for f in r["fields"]:
            by_field[f].append(r)

    def skeleton(code):
        s = re.sub(r"\b\d+(\.\d+)?\b", "NUM", code)
        return re.sub(r"\s+", "", s)

    skel = defaultdict(list)
    for r in rows:
        skel[skeleton(r["code"])].append(r)

    settings_axis = defaultdict(int)
    for r in rows:
        settings_axis[json.dumps(r["settings"], sort_keys=True)] += 1

    clean = [r for r in rows if not r["authoritative_fail"]]

    summary = {
        "total_alphas": len(rows),
        "pages": pages,
        "n_clean": len(clean),
        "clean_ids": [r["id"] for r in clean],
        "datasets": {k: {
            "n": len(v),
            "best_sharpe": max((x["sharpe"] if x["sharpe"] is not None else -9) for x in v),
            "best_fitness": max((x["fitness"] if x["fitness"] is not None else -9) for x in v),
            "n_clean": len([x for x in v if not x["authoritative_fail"]]),
            "clean_ids": [x["id"] for x in v if not x["authoritative_fail"]][:40],
            "n_fields": len(set(f for x in v for f in x["fields"])),
            "fields": sorted(set(f for x in v for f in x["fields"])),
        } for k, v in sorted(by_ds.items(),
                             key=lambda kv: -max((x["sharpe"] if x["sharpe"] is not None else -9)
                                                 for x in kv[1]))},
        "fields": {k: {
            "n": len(v),
            "best_sharpe": max((x["sharpe"] if x["sharpe"] is not None else -9) for x in v),
            "best_fitness": max((x["fitness"] if x["fitness"] is not None else -9) for x in v),
            "n_clean": len([x for x in v if not x["authoritative_fail"]]),
        } for k, v in sorted(by_field.items(),
                             key=lambda kv: -max((x["sharpe"] if x["sharpe"] is not None else -9)
                                                 for x in kv[1]))},
        "settings_axis": dict(sorted(settings_axis.items(), key=lambda kv: -kv[1])),
        "top_skeletons": {k[:200]: {
            "n": len(v),
            "best_sharpe": max((x["sharpe"] if x["sharpe"] is not None else -9) for x in v),
            "best_fitness": max((x["fitness"] if x["fitness"] is not None else -9) for x in v),
            "ids": [x["id"] for x in v][:5],
        } for k, v in sorted(skel.items(),
                             key=lambda kv: -max((x["sharpe"] if x["sharpe"] is not None else -9)
                                                 for x in kv[1]))[:80]},
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "alphas": rows}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print(f"total={summary['total_alphas']} clean={summary['n_clean']} pages={pages}")
    print("\n=== DATASETS ===")
    for k, v in summary["datasets"].items():
        print(f"{v['n']:>4} sh={v['best_sharpe']!s:<7} fit={v['best_fitness']!s:<7} "
              f"clean={v['n_clean']:<3} nf={v['n_fields']:<4} {k}")
    print("\n=== SETTINGS AXIS ===")
    for k, v in list(summary["settings_axis"].items())[:12]:
        print(f"{v:>5}  {k}")
    print(f"\n[ok] wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
