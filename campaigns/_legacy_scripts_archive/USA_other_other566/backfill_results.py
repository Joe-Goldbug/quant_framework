"""
backfill_results.py — persist every completed batch's alpha details to disk.

For each multisimulation location recorded in multisim_locations.json, walk the
children and fetch each produced alpha's full details from the platform. The
output shape matches what run_multisim.py writes, so collect_ledger.py can
consume both without change.
"""

import json
import os
import sys
import time

sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\trailSomeAlphas\skills\brain-feature-implementation\scripts")

from ace_lib import start_session  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.worldquantbrain.com"


def main():
    with open(os.path.join(HERE, "multisim_locations.json"), "r", encoding="utf-8") as f:
        locs = json.load(f)

    s = start_session()
    print("authenticated\n", flush=True)

    for bnum, loc in sorted(locs.items(), key=lambda kv: int(kv[0])):
        outp = os.path.join(HERE, f"batch_{int(bnum):02d}_result.json")
        if os.path.exists(outp):
            print(f"batch {bnum}: already persisted, skipping")
            continue

        bpath = os.path.join(HERE, f"batch_{int(bnum):02d}.json")
        batch = {}
        if os.path.exists(bpath):
            with open(bpath, "r", encoding="utf-8") as f:
                batch = json.load(f)

        try:
            children = s.get(loc).json().get("children") or []
        except Exception as exc:
            print(f"batch {bnum}: children fetch failed: {exc}")
            continue

        results = []
        for c in children:
            cid = c if isinstance(c, str) else c.get("id")
            cloc = f"{API}/simulations/{cid}"
            try:
                cj = s.get(cloc).json()
            except Exception:
                cj = {}
            aid = cj.get("alpha")
            rec = {"child_id": cid, "child_status": cj.get("status"),
                   "alpha_id": aid, "location": cloc}
            if aid:
                try:
                    rec.update(s.get(f"{API}/alphas/{aid}").json())
                except Exception as exc:
                    rec["fetch_error"] = str(exc)
            results.append(rec)

        out = {
            "batch_file": f"batch_{int(bnum):02d}.json",
            "batch": batch.get("batch", int(bnum)),
            "family": batch.get("family"),
            "hypothesis": batch.get("hypothesis"),
            "location": loc,
            "fetched_at": int(time.time()),
            "alpha_results": results,
        }
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        from alpha_normalizer import normalize
        got = 0
        for rec in results:
            m = normalize(rec) or {}
            if m.get("sharpe") is not None:
                got += 1
            print(f"  B{bnum} {rec.get('alpha_id')} Sh={m.get('sharpe')} "
                  f"Fit={m.get('fitness')} TO={m.get('turnover')} "
                  f"Mgn={m.get('margin_bps')} 2Y={m.get('two_year_sharpe')} "
                  f"CL={m.get('cluster_test')} fails={m.get('fail_count')}", flush=True)
        print(f"batch {bnum}: {got}/{len(results)} resolved -> {outp}\n", flush=True)


if __name__ == "__main__":
    main()
