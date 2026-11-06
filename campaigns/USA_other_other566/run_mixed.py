# -*- coding: utf-8 -*-
"""
run_mixed.py — 单次多重回测提交，每个 child 携带自己的平台设置。

run_multisim.py 会把不同 (decay, neutralization, truncation) 的槽位拆成多次提交，
这对「同一批里扫 neutralization」的实验很致命（8 次串行 ≈ 8 倍墙钟时间）。
本脚本直接把 8 条不同设置的表达式塞进同一个 payload —— 平台的多重回测数组里
每个元素本就是一份完整的 simulation spec，settings 可以逐条不同。

关键点：提交后必须**回读每个 alpha 的 settings** 验证平台确实按逐条设置执行，
否则整批结论作废。本脚本在输出里逐行打印 decay/neut，并在不匹配时报警。

用法:
    python run_mixed.py batch_28.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_multisim import (  # noqa: E402
    API, HERE, build_settings, fetch_children, resilient_get, resilient_post,
    start_session, wait_complete,
)
from alpha_normalizer import normalize  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        batch = json.load(f)
    items = batch["items"]
    name = os.path.basename(path)
    print(f"\n=== {name} :: {batch.get('family')} :: {len(items)} exprs (mixed settings) ===", flush=True)

    payload = []
    for it in items:
        st = build_settings(it.get("decay", 0), it.get("neutralization", "INDUSTRY"),
                            it.get("truncation", 0.08))
        payload.append({"type": "REGULAR", "settings": st, "regular": it["expr"]})

    s = start_session()
    print("authenticated", flush=True)
    r = resilient_post(s, f"{API}/simulations", payload)
    if r.status_code // 100 != 2:
        print(f"SUBMIT FAILED {r.status_code}: {r.text[:600]}")
        sys.exit(1)
    loc = r.headers.get("Location")
    print(f"  LOC: {loc}", flush=True)

    final = wait_complete(s, loc)
    if not final or final.get("status") != "COMPLETE":
        print(f"  NOT COMPLETE: {(final or {}).get('status')}")
        sys.exit(1)

    recs = fetch_children(s, loc)
    out = {
        "batch_file": name,
        "batch": batch.get("batch"),
        "family": batch.get("family"),
        "hypothesis": batch.get("hypothesis"),
        "location": loc,
        "fetched_at": int(time.time()),
        "alpha_results": recs,
    }
    outp = os.path.join(HERE, name.replace(".json", "_result.json"))
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  saved -> {outp}", flush=True)

    want = {it["expr"]: it for it in items}
    mismatch = 0
    for rec in recs:
        reg = rec.get("regular") or {}
        code = (reg.get("code") if isinstance(reg, dict) else reg) or ""
        it = want.get(code.strip())
        st = rec.get("settings") or {}
        exp = (it or {}).get("neutralization")
        got = st.get("neutralization")
        ok = (exp is None or exp == got) and (it is None or it.get("decay") == st.get("decay"))
        if not ok:
            mismatch += 1
        m = normalize(rec) or {}
        print(f"    {str((it or {}).get('id'))[:26]:<27} {rec.get('alpha_id')} "
              f"Sh={m.get('sharpe')} Fit={m.get('fitness')} TO={m.get('turnover')} "
              f"Mgn={m.get('margin_bps')} 2Y={m.get('two_year_sharpe')} CL={m.get('cluster_test')} "
              f"fails={m.get('fail_count')} neut={got} decay={st.get('decay')} "
              f"{'' if ok else '  <<< SETTINGS MISMATCH'}", flush=True)
    print(f"  settings mismatches: {mismatch}/{len(recs)}", flush=True)


if __name__ == "__main__":
    main()
