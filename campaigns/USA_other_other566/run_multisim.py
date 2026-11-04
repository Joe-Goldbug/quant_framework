"""
run_multisim.py — self-contained BRAIN multi-simulation runner for the other566 campaign.

Uses ace_lib (clean import, no bs4/redis/mcp deps) to POST the platform's own
multi-simulation payload — a LIST of {type, settings, regular} objects, one per
expression — then polls to COMPLETE and persists every child's alpha details to
`batch_NN_result.json` so the exploration ledger is reproducible from disk.

Payload shape was verified against brain-mcp's `_build_multisim_payload`:
    POST {base}/simulations
    [{"type":"REGULAR","settings":{...},"regular":"<expr>"}, ...]

Usage:
    python run_multisim.py batch_10.json batch_11.json ...
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

REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1
DECAY = 4
NEUTRALIZATION = "INDUSTRY"
TRUNCATION = 0.08


def build_settings():
    return {
        "instrumentType": "EQUITY",
        "region": REGION,
        "universe": UNIVERSE,
        "delay": DELAY,
        "decay": DECAY,
        "neutralization": NEUTRALIZATION,
        "truncation": TRUNCATION,
        "pasteurization": "ON",
        "language": "FASTEXPR",
        "visualization": False,
        "testPeriod": "P0Y0M",
        "maxTrade": "OFF",
        "unitHandling": "VERIFY",
        "nanHandling": "ON",
    }


def build_payload(exprs):
    return [{"type": "REGULAR", "settings": build_settings(), "regular": e} for e in exprs]


def wait_complete(s, location, max_wait=2400):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            r = s.get(location)
        except Exception:
            time.sleep(10)
            continue
        if r.status_code // 100 != 2:
            time.sleep(10)
            continue
        j = r.json()
        st = j.get("status")
        if st == "COMPLETE":
            return j
        if st in ("ERROR", "FAIL"):
            print(f"  SIM STATUS {st}: {json.dumps(j, ensure_ascii=False)[:300]}")
            return j
        time.sleep(max(float(r.headers.get("Retry-After", 0) or 5), 4))
    return None


def fetch_children(s, location):
    j = s.get(location).json()
    children = j.get("children") or []
    out = []
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
        out.append(rec)
    return out


def run_batch(s, path):
    with open(path, "r", encoding="utf-8") as f:
        batch = json.load(f)
    exprs = [it["expr"] for it in batch["items"]]
    name = os.path.basename(path)
    print(f"\n=== {name} :: {batch.get('family')} :: {len(exprs)} exprs ===", flush=True)

    r = s.post(f"{API}/simulations", json=build_payload(exprs))
    if r.status_code // 100 != 2:
        print(f"  SUBMIT FAILED {r.status_code}: {r.text[:400]}")
        return None
    location = r.headers.get("Location")
    print(f"  LOC: {location}", flush=True)

    final = wait_complete(s, location)
    if not final or final.get("status") != "COMPLETE":
        print(f"  NOT COMPLETE ({(final or {}).get('status')})")
        return None

    results = fetch_children(s, location)
    out = {
        "batch_file": name,
        "batch": batch.get("batch"),
        "family": batch.get("family"),
        "hypothesis": batch.get("hypothesis"),
        "location": location,
        "fetched_at": int(time.time()),
        "alpha_results": results,
    }
    outp = os.path.join(HERE, name.replace(".json", "_result.json"))
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  saved -> {outp}", flush=True)

    from alpha_normalizer import normalize
    for rec in results:
        n = normalize(rec) or {}
        m = n or {}
        print(f"    {rec.get('alpha_id')} Sh={m.get('sharpe')} Fit={m.get('fitness')} "
              f"TO={m.get('turnover')} Mgn={m.get('margin_bps')} 2Y={m.get('two_year_sharpe')} "
              f"CL={m.get('cluster_test')} fails={m.get('fail_count')}", flush=True)
    return out


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(1)
    s = start_session()
    print("authenticated", flush=True)
    for p in paths:
        try:
            run_batch(s, p)
        except Exception as exc:
            import traceback
            print(f"  ERROR on {p}: {exc}")
            traceback.print_exc()
    print("\nDONE")


if __name__ == "__main__":
    main()
