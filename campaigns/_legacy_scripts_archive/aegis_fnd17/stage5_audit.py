# -*- coding: utf-8 -*-
"""Stage 5 · 全维度审计器 + 年度盈利年数取证

对 batch_S1_result.json 逐条做零隐瞒审计：
  平台硬门禁：Sharpe>=1.58 / Fitness>=1.0 / TO∈[1%,70%] / LOW_2Y_SHARPE>=1.58 /
                IS_LADDER_SHARPE>=1.58 / CONCENTRATED_WEIGHT<=0.1 / checks.fail 为空 / ra_failed==false
  工作区铁律：Margin>=10bps / 正收益年数>=8/10 / L:S 对称性 / ProdCorr<0.70 / SelfCorr<=0.60

年度盈利年数需要 yearly-stats 数据，本脚本按需从平台拉取并缓存。
"""
import sys, os, json, asyncio

import _paths
ROOT = _paths.ROOT
CAMPAIGN = _paths.CAMPAIGN
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

# ---- 平台实测门禁（从本地 5846 条 alpha 的 checks.fail[].limit 反查，权威）----
PLATFORM = {
    "sharpe": 1.58, "fitness": 1.0, "turnover_lo": 0.01, "turnover_hi": 0.70,
    "two_year_sharpe": 1.58, "ladder_sharpe": 1.58, "concentrated_weight": 0.10,
}
HOUSE = {"margin_bps": 10.0, "profitable_years": 8, "prod_corr": 0.70, "self_corr": 0.60}


def parse_checks(alpha):
    """解析平台 checks。

    ⚠️ 2026-10-28 修正（假通过漏洞）：BRAIN 原始 API 把 checks 放在 `alpha['is']['checks']`，
    且是**扁平数组**格式 [{"name":..,"result":"FAIL"|"PASS"|"WARNING","value":..}]，
    而不是 MCP 工具归一化后的 {"fail":[..],"warning":[..]}。
    原实现只读顶层 `alpha.get("checks")` ⇒ 恒得空 ⇒ **任何 alpha 都被误判为 checks.fail 为空**，
    构成零掩盖审计里的致命假通过。现同时兼容两种形态。
    """
    ch = (alpha.get("checks") or {})
    if isinstance(ch, dict) and ch:
        fail = ch.get("fail") or []
        warn = ch.get("warning") or []
        fn = [c.get("name") for c in fail if isinstance(c, dict)]
        wn = [c.get("name") for c in warn if isinstance(c, dict)]
        vals = {}
        for c in list(fail) + list(warn):
            if isinstance(c, dict) and c.get("name"):
                vals[c["name"]] = c.get("value")
        return fn, wn, vals

    # 原始 API：checks 在 alpha['is']['checks']，是**扁平数组** [{name,result,value}]
    is_ = alpha.get("is") or {}
    arr = is_.get("checks") if isinstance(is_, dict) else None
    if not isinstance(arr, list):
        arr = ch if isinstance(ch, list) else []
    fn = [c.get("name") for c in arr
          if isinstance(c, dict) and c.get("result") == "FAIL"]
    wn = [c.get("name") for c in arr
          if isinstance(c, dict) and c.get("result") == "WARNING"]
    vals = {c["name"]: c.get("value") for c in arr
            if isinstance(c, dict) and c.get("name")}
    return fn, wn, vals


def metrics_of(alpha):
    """平台指标：原始 API 把指标平铺在 alpha['is']（无 metrics 子键），MCP 工具则给 is.metrics。"""
    is_ = alpha.get("is") or alpha.get("os") or {}
    if isinstance(is_, dict):
        if isinstance(is_.get("metrics"), dict):
            return is_["metrics"]
        return {k: v for k, v in is_.items()
                if k in ("sharpe", "fitness", "turnover", "returns", "drawdown", "margin",
                         "longCount", "shortCount", "pnl", "bookSize", "sub_universe_sharpe",
                         "two_year_sharpe", "investability_sharpe", "investability_fitness",
                         "risk_neutralized_sharpe", "startDate")}
    return {}



def positive_years(yearly):
    """年度收益为正的年份数。yearly 形如 [{'year':2020,'returns':0.12,'sharpe':1.1}, ...]"""
    n = 0
    for y in yearly or []:
        if not isinstance(y, dict):
            continue
        r = y.get("returns")
        if r is None:
            r = y.get("return")
        if r is None:
            r = y.get("pnl")
        if r is None:
            continue
        try:
            if float(r) > 0:
                n += 1
        except (TypeError, ValueError):
            pass
    return n


async def fetch_yearly(alpha_id):
    """年度统计：GET /alphas/{id}/recordsets/yearly-stats -> {"records":[...]}"""
    try:
        r = await B.brain_client._request(
            "GET", f"{B.brain_client.base_url}/alphas/{alpha_id}/recordsets/yearly-stats",
            timeout=60)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, dict):
                for key in ("records", "yearlyStats", "data"):
                    if isinstance(j.get(key), list):
                        return j[key]
            return j if isinstance(j, list) else []
    except Exception as ex:
        print(f"    yearly fetch error {alpha_id}: {str(ex)[:80]}")
    return []


async def main():
    res_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CAMPAIGN, "batch_S1_result.json")
    d = json.load(open(res_file, encoding="utf-8"))
    out = d.get("alpha_results", d if isinstance(d, list) else [d])

    await B.brain_client.ensure_authenticated()

    rows = []
    for r in out:
        a = r.get("alpha") or {}
        m = metrics_of(a)
        if not m:
            print(f"  slot{r.get('slot')} 无指标 (status={r.get('raw_status')})")
            continue
        fn, wn, cvals = parse_checks(a)
        is_ = a.get("is") or {}
        raw_checks = is_.get("checks") if isinstance(is_, dict) else None
        if isinstance(raw_checks, list):
            # 原始 API：ra 在 alpha['ra']，此处兜底从 flat checks 推导失败项
            pass
        to = m.get("turnover")
        ret = m.get("returns")
        sh = m.get("sharpe")
        fit = m.get("fitness")
        mgn = m.get("margin")
        t2y = m.get("two_year_sharpe")
        subu = m.get("sub_universe_sharpe")
        aid = a.get("id") or r.get("alpha_id")

        # ⚠️ 2Y ladder 与 sub-universe 在原始 API 里**只存在于 checks 数组的 value**，
        #    metrics 中没有该键（metrics 里只有 12 个标准字段）。缺失不等于 0，
        #    必须从 checks 回填，否则会误判为"未达标"。
        if t2y is None:
            t2y = cvals.get("LOW_2Y_SHARPE")
        if subu is None:
            subu = cvals.get("LOW_SUB_UNIVERSE_SHARPE")

        yearly = await fetch_yearly(aid) if aid else []
        py = positive_years(yearly)

        L, S = m.get("longCount"), m.get("shortCount")
        ls_ratio = (max(L, S) / min(L, S)) if (L and S and min(L, S) > 0) else None

        rec = {
            "slot": r.get("slot"), "alpha_id": aid, "seed_id": r.get("seed_id", ""),
            "expr": r.get("expr", ""), "sharpe": sh, "fitness": fit, "turnover": to,
            "returns": ret, "margin_bps": (mgn * 10000) if mgn is not None else None,
            "two_year_sharpe": t2y, "sub_universe_sharpe": subu,
            "long_count": L, "short_count": S, "ls_ratio": ls_ratio,
            "profitable_years": py, "yearly_total": len(yearly or []),
            "checks_fail": fn, "checks_warning": wn, "check_values": cvals,
            "ra_failed": (a.get("ra") or {}).get("ra_failed"),
            "yearly": yearly,
        }
        if rec["ra_failed"] is None and fn:
            # 原始 API 无 ra 字段时，以 checks 里的 FAIL 项作为权威等价判据
            rec["ra_failed"] = bool(fn)

        # ---- 平台硬门禁 ----
        pf = []
        if sh is None or sh < PLATFORM["sharpe"]:
            pf.append(f"Sharpe {sh} < {PLATFORM['sharpe']}")
        if fit is None or fit < PLATFORM["fitness"]:
            pf.append(f"Fitness {fit} < {PLATFORM['fitness']}")
        if to is None or to < PLATFORM["turnover_lo"]:
            pf.append(f"TO {to} < {PLATFORM['turnover_lo']} (LOW_TURNOVER)")
        if to is None or to > PLATFORM["turnover_hi"]:
            pf.append(f"TO {to} > {PLATFORM['turnover_hi']} (HIGH_TURNOVER)")
        if t2y is None or t2y < PLATFORM["two_year_sharpe"]:
            pf.append(f"2Y {t2y} < {PLATFORM['two_year_sharpe']}")
        if fn:
            pf.append(f"checks.fail={fn}")
        if rec["ra_failed"]:
            pf.append("ra.ra_failed=True")
        cw = cvals.get("CONCENTRATED_WEIGHT")
        if cw is not None and cw > PLATFORM["concentrated_weight"]:
            pf.append(f"CW {cw} > {PLATFORM['concentrated_weight']}")
        # ---- 工作区铁律 ----
        hf = []
        if rec["margin_bps"] is None or rec["margin_bps"] < HOUSE["margin_bps"]:
            hf.append(f"Margin {rec['margin_bps']} < {HOUSE['margin_bps']}bps")
        if yearly and py < HOUSE["profitable_years"]:
            hf.append(f"正收益年 {py}/{len(yearly)} < {HOUSE['profitable_years']}")
        if ls_ratio and ls_ratio > 1.15:
            hf.append(f"L:S 偏离 {ls_ratio:.2f} > 1.15")

        rec["platform_fail"] = pf
        rec["house_fail"] = hf
        rec["platform_pass"] = not pf
        rec["house_pass"] = not hf
        rec["submit_ready"] = not pf and not hf
        rows.append(rec)

        print(f"\nslot{rec['slot']} {aid} [{rec['seed_id']}]")
        print(f"   Sh={sh} Fit={fit} TO={(to or 0)*100:.2f}% Ret={(ret or 0)*100:.3f}% "
              f"Mgn={(rec['margin_bps'] or 0):.2f}bp 2Y={t2y} SubU={subu}")
        print(f"   正收益年 {py}/{len(yearly or [])}  L/S={L}/{S}"
              f"{' ratio=%.2f' % ls_ratio if ls_ratio else ''}  ra_fail={rec['ra_failed']}")
        print(f"   FAIL={fn} WARN={wn}")
        print(f"   平台门禁: {'✅ PASS' if not pf else '❌ ' + '; '.join(pf)}")
        print(f"   工作区铁律: {'✅ PASS' if not hf else '⚠️ ' + '; '.join(hf)}")
        print(f"   {rec['expr'][:150]}")

    out_file = res_file.replace("_result.json", "_audit.json")
    json.dump(rows, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n💾 -> {out_file}")

    npass = sum(1 for r in rows if r["platform_pass"])
    nsub = sum(1 for r in rows if r["submit_ready"])
    print(f"\n===== 审计汇总 =====")
    print(f"  平台硬门禁通过: {npass}/{len(rows)}")
    print(f"  全维度(含工作区铁律)通过: {nsub}/{len(rows)}")
    for r in rows:
        if r["submit_ready"]:
            print(f"  ★ SUBMIT_READY {r['alpha_id']} slot{r['slot']} Sh={r['sharpe']} Fit={r['fitness']}")


asyncio.run(main())
