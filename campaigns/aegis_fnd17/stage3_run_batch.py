# -*- coding: utf-8 -*-
"""Stage 3 · 8 槽静默回测执行器（AEGIS fundamental17 / USA TOP1000 d1）

🔴 2026-10-28 实测：BRAIN 的 multi 批量端点（一次 POST 数组）本会话中途失效，
   8/8 全部 RemoteDisconnected；而**单条 POST（单个对象）201 正常**。
   故本脚本走单条端点：连续提交 → 断点续轮询 → 统一取指标。

纪律：
  - 本脚本 **只做回测仿真**，绝不触碰任何提交接口。
  - 201 成功后才写指纹（防幻影记录）。
  - State 文件记录全部 location，支持断点续轮询。
  - Step-1 漏斗：|Sharpe|>=1.0 且正收益年份>=8/10，否则整批 PRUNED_AT_STEP1。
"""
import sys, os, json, asyncio, time

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
print("[NET] 强制直连")

DB = os.path.join(ROOT, "quant_framework", "alphas_record.db")


def payload(expr, REGION, UNIV, DELAY, NEUT, DECAY, TRUNC, NAN="ON"):
    """单条 REGULAR 仿真载荷。

    ⚠️ maxTrade 必须给字符串 'OFF'，**不能**给 JSON null —— brain-mcp 的
       create_simulation 会把 None 字段过滤掉，但直接 _request 不做过滤，
       null 会被平台当成"未设置该字段"而报 400。
    """
    return {"type": "REGULAR",
            "settings": {"instrumentType": "EQUITY", "region": REGION, "universe": UNIV,
                         "delay": DELAY, "decay": DECAY, "neutralization": NEUT,
                         "truncation": TRUNC, "pasteurization": "ON", "language": "FASTEXPR",
                         "visualization": False, "unitHandling": "VERIFY", "nanHandling": NAN,
                         "maxTrade": "OFF"},
            "regular": expr}


def record_fingerprints(exprs, REGION, UNIV, DELAY, NEUT):
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    c = ASTSandboxCorrector(db_path=DB)
    for e in exprs:
        try:
            c.compute_fingerprint(e, REGION, UNIV, DELAY, NEUT)
        except Exception:
            pass


async def main():
    batch_file = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(CAMPAIGN, "batch_S1.json")
    d = json.load(open(batch_file, encoding="utf-8"))
    ST = d.get("settings", {})
    REGION, UNIV, DELAY = d["region"], d["universe"], d["delay"]
    NEUT = ST.get("neutralization", "STATISTICAL")
    DECAY = ST.get("decay", 8)
    TRUNC = ST.get("truncation", 0.08)
    items = d["items"]
    STATE = batch_file.replace(".json", "_state.json")

    await B.brain_client.ensure_authenticated()
    base = B.brain_client.base_url
    url = f"{base}/simulations"

    state = {"locs": {}}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding="utf-8"))
            print(f"  断点续传：已有 {len(state.get('locs', {}))} 条 location")
        except Exception:
            state = {"locs": {}}
    state.setdefault("locs", {})
    locs = state["locs"]

    todo = [it for it in items if str(it["slot"]) not in locs]
    print(f"  待提交 {len(todo)} 条（已有 {len(locs)} 条）")

    for it in todo:
        expr = it["expression"]
        # 逐槽设置覆盖：诊断批次（settings_probe）用它做设置档 A/B 对照
        _sp = it.get("settings_probe") or {}
        _neut = _sp.get("neutralization", NEUT)
        _decay = _sp.get("decay", DECAY)
        _trunc = _sp.get("truncation", TRUNC)
        ok = False
        for att in range(1, 6):
            try:
                r = await B.brain_client._request("POST", url, json=payload(
                    expr, REGION, UNIV, DELAY, _neut, _decay, _trunc,
                    _sp.get("nan_handling", ST.get("nan_handling", "ON"))), timeout=120.0)
                if r.status_code in (200, 201):
                    loc = r.headers.get("Location", "")
                    if loc:
                        locs[str(it["slot"])] = {"loc": loc, "expr": expr,
                                                "seed_id": it.get("seed_id", ""),
                                                "settings_probe": _sp,
                                                "neutralization": _neut, "decay": _decay,
                                                "nan_handling": _sp.get("nan_handling", ST.get("nan_handling", "ON"))}
                        try:
                            record_fingerprints([expr], REGION, UNIV, DELAY, _neut)
                        except Exception:
                            pass
                        print(f"  slot{it['slot']} 提交OK (attempt{att}) neut={_neut} decay={_decay} "
                              f"nan={_sp.get('nan_handling', ST.get('nan_handling','ON'))} {loc.split('/')[-1]}")
                        ok = True
                        break
                print(f"  slot{it['slot']} attempt{att} status={r.status_code} {r.text[:140]}")
            except Exception as ex:
                print(f"  slot{it['slot']} attempt{att} {type(ex).__name__}: {str(ex)[:110]}")
            await asyncio.sleep(15)
        if not ok:
            print(f"  slot{it['slot']} 提交失败")
        state["locs"] = locs
        json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        await asyncio.sleep(2)

    print(f"\n  共 {len(locs)} 条在跑，进入轮询")
    t0 = time.time()
    while True:
        await asyncio.sleep(45)
        done, sts = 0, []
        for k, v in locs.items():
            try:
                r = await B.brain_client._request("GET", v["loc"], timeout=60)
                j = r.json()
                st = j.get("status")
                v["status"] = st
                sts.append(f"s{k}:{st}")
                if st in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
                    done += 1
            except Exception:
                v["status"] = "POLL_ERR"
        el = int(time.time() - t0)
        print(f"  [{el//60:02d}:{el%60:02d}] done={done}/{len(locs)}  {' '.join(sts)}")
        json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        if done == len(locs) or el > 2400:
            break

    # ---------- 取完整指标 ----------
    out = []
    for k in sorted(locs, key=lambda z: int(z)):
        v = locs[k]
        rec = {"slot": int(k), "location": v["loc"], "expr": v["expr"],
               "seed_id": v.get("seed_id", "")}
        try:
            r = await B.brain_client._request("GET", v["loc"], timeout=60)
            j = r.json()
        except Exception as ex:
            rec["error"] = str(ex)
            out.append(rec)
            continue
        rec["raw_status"] = j.get("status")
        aid = j.get("alpha") or j.get("alpha_id") or j.get("id")
        rec["alpha_id"] = aid
        if aid:
            try:
                ar = await B.brain_client._request("GET", f"{base}/alphas/{aid}", timeout=60)
                if ar.status_code == 200:
                    rec["alpha"] = ar.json()
            except Exception as ex:
                rec["alpha_err"] = str(ex)
        out.append(rec)

    res_file = batch_file.replace(".json", "_result.json")
    json.dump({"alpha_results": out}, open(res_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n💾 -> {res_file}")

    # ---------- 摘要 + Step-1 漏斗 ----------
    print("\n===== S1 批次摘要 =====")
    best_abs, alive = 0.0, []
    for r in out:
        a = r.get("alpha") or {}
        m = (a.get("metrics") or a.get("is") or {})
        if not m:
            print(f"  slot{r['slot']} 无指标 (status={r.get('raw_status')}) {str(a)[:120]}")
            continue
        to = (m.get("turnover") or 0) * 100
        ret = (m.get("returns") or 0) * 100
        sh = m.get("sharpe") or 0
        # ⚠️ 原始 API 的 checks 在 alpha['is']['checks']，是**扁平数组** [{name,result,value}]
        #    （MCP 工具才归一化成 {fail:[],warning:[]}）。只读顶层 alpha['checks'] 会恒得空
        #    ⇒ 把每个 alpha 都误报成 FAIL=[]（假通过）。此处两种形态都解析。
        _ch = a.get("checks") or (m.get("checks") if isinstance(m, dict) else None) or {}
        if isinstance(_ch, dict):
            fails = [c.get("name") for c in (_ch.get("fail") or [])]
            warns = [c.get("name") for c in (_ch.get("warning") or [])]
        else:
            fails = [c.get("name") for c in (_ch or [])
                     if isinstance(c, dict) and c.get("result") == "FAIL"]
            warns = [c.get("name") for c in (_ch or [])
                     if isinstance(c, dict) and c.get("result") == "WARNING"]
        ra = (a.get("ra") or {}).get("ra_failed")
        if ra is None:
            ra = bool(fails)   # 无 ra 字段时以 checks FAIL 作为权威等价判据
        mgn = 20 * ret / to if to else 0
        print(f"  slot{r['slot']} {a.get('id','')} {r.get('seed_id','')}")
        print(f"       Sh={sh:.3f} 2Y={m.get('two_year_sharpe')} Fit={m.get('fitness')} "
              f"TO={to:.2f}% Ret={ret:.2f}% Mgn={mgn:.2f}bp SubU={m.get('sub_universe_sharpe')} "
              f"L/S={m.get('longCount')}/{m.get('shortCount')} ra_fail={ra}")
        print(f"       FAIL={fails} WARN={warns}")
        if abs(sh) > best_abs:
            best_abs = abs(sh)
        if abs(sh) >= 1.0:
            alive.append(r)
    print(f"\n  最高 |Sharpe| = {best_abs:.3f}；|Sh|>=1.0 的条数 = {len(alive)}")
    if not alive:
        print("  *** PRUNED_AT_STEP1：全批无一条满足 |Sharpe|>=1.0 ⇒ 立即换核，绝不微调重发 ***")
    else:
        print("  *** STEP1_PASSED：进入 Step-2 阶梯裁决（2Y ladder / Sub-universe / checks.fail） ***")


asyncio.run(main())
