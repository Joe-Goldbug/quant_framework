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


def build_settings(decay=DECAY, neutralization=NEUTRALIZATION, truncation=TRUNCATION):
    return {
        "instrumentType": "EQUITY",
        "region": REGION,
        "universe": UNIVERSE,
        "delay": DELAY,
        "decay": decay,
        "neutralization": neutralization,
        "truncation": truncation,
        "pasteurization": "ON",
        "language": "FASTEXPR",
        "visualization": False,
        "testPeriod": "P0Y0M",
        "maxTrade": "OFF",
        "unitHandling": "VERIFY",
        "nanHandling": "ON",
    }


def build_payload(items):
    """One payload entry per item. An item may override the platform decay via
    its own 'decay' key — decay is a simulation setting, not part of the
    expression, so items with different decay values must be split into
    separate multi-simulations by the caller."""
    return [{"type": "REGULAR", "settings": build_settings(), "regular": it["expr"]}
            for it in items]


def wait_complete(s, location, max_wait=2400):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            r = resilient_get(s, location)
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
    """Fetch results for either a multi-simulation (children list) or a single
    simulation (the simulation object itself carries the alpha id)."""
    j = resilient_get(s, location).json()
    children = j.get("children") or []
    if not children:
        # single-simulation submission
        aid = j.get("alpha")
        if not aid:
            return []
        rec = {"child_id": j.get("id"), "child_status": j.get("status"),
               "alpha_id": aid, "location": location}
        try:
            rec.update(resilient_get(s, f"{API}/alphas/{aid}").json())
        except Exception as exc:
            rec["fetch_error"] = str(exc)
        return [rec]
    out = []
    for c in children:
        cid = c if isinstance(c, str) else c.get("id")
        cloc = f"{API}/simulations/{cid}"
        try:
            cj = resilient_get(s, cloc).json()
        except Exception:
            cj = {}
        aid = cj.get("alpha")
        rec = {"child_id": cid, "child_status": cj.get("status"),
               "alpha_id": aid, "location": cloc}
        if aid:
            try:
                rec.update(resilient_get(s, f"{API}/alphas/{aid}").json())
            except Exception as exc:
                rec["fetch_error"] = str(exc)
        out.append(rec)
    return out


def resilient_post(s, path, payload, retries=4):
    """POST with session re-establishment. The platform periodically drops
    long-lived sessions (RemoteDisconnected), which kills a multi-wave batch
    partway through; re-login and retry rather than losing the whole wave."""
    import time as _t
    last = None
    for attempt in range(retries):
        try:
            return s.post(path, json=payload)
        except Exception as exc:
            last = exc
            print(f"     POST attempt {attempt+1} failed ({exc}); re-authenticating",
                  flush=True)
            _t.sleep(10)
            try:
                s = start_session()
            except Exception:
                _t.sleep(20)
    raise last


def resilient_get(s, url, **kw):
    """GET with one re-authentication retry."""
    try:
        return s.get(url, **kw)
    except Exception as exc:
        print(f"     GET failed ({exc}); re-authenticating", flush=True)
        import time as _t
        _t.sleep(8)
        s = start_session()
        return s.get(url, **kw)


def run_batch(s, path):
    with open(path, "r", encoding="utf-8") as f:
        batch = json.load(f)
    items = batch["items"]
    name = os.path.basename(path)
    print(f"\n=== {name} :: {batch.get('family')} :: {len(items)} exprs ===", flush=True)

    # Group items by their per-item platform settings overrides. The platform's
    # `decay`, `neutralization` and `truncation` are SIMULATION settings, not part
    # of the expression, so items with different settings must be split into
    # separate multi-simulations.
    groups = {}
    for it in items:
        key = (it.get("decay", DECAY),
               it.get("neutralization", NEUTRALIZATION),
               it.get("truncation", TRUNCATION))
        groups.setdefault(key, []).append(it)

    all_results = []
    location = None
    for (dec, neut, trunc), grp in sorted(groups.items()):
        exprs = [it["expr"] for it in grp]
        print(f"  -- decay={dec} neut={neut} trunc={trunc}: {len(exprs)} exprs", flush=True)
        payload = [{"type": "REGULAR", "settings": build_settings(dec, neut, trunc), "regular": e}
                   for e in exprs]
        # A multi-simulation requires >=2 entries; a single entry must be
        # submitted WITHOUT the wrapping array ("Multi-simulations require
        # multiple simulations in request array").
        if len(payload) == 1:
            payload = payload[0]
        r = resilient_post(s, f"{API}/simulations", payload)
        if r.status_code // 100 != 2:
            print(f"  SUBMIT FAILED {r.status_code}: {r.text[:400]}")
            continue
        loc = r.headers.get("Location")
        location = location or loc
        print(f"     LOC: {loc}", flush=True)

        final = wait_complete(s, loc)
        if not final or final.get("status") != "COMPLETE":
            print(f"     NOT COMPLETE ({(final or {}).get('status')})")
            continue
        all_results.extend(fetch_children(s, loc))

    if not all_results:
        print("  no results")
        return None

    out = {
        "batch_file": name,
        "batch": batch.get("batch"),
        "family": batch.get("family"),
        "hypothesis": batch.get("hypothesis"),
        "location": location,
        "fetched_at": int(time.time()),
        "alpha_results": all_results,
    }
    outp = os.path.join(HERE, name.replace(".json", "_result.json"))
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  saved -> {outp}", flush=True)

    from alpha_normalizer import normalize
    for rec in all_results:
        m = normalize(rec) or {}
        print(f"    {rec.get('alpha_id')} Sh={m.get('sharpe')} Fit={m.get('fitness')} "
              f"TO={m.get('turnover')} Mgn={m.get('margin_bps')} 2Y={m.get('two_year_sharpe')} "
              f"CL={m.get('cluster_test')} fails={m.get('fail_count')} "
              f"decay={(rec.get('settings') or {}).get('decay')}", flush=True)
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
