"""Fetch all other580 datafields (USA/TOP1000/delay1) to JSON — local pull, no MCP context bloat."""
import json
import os
import sys
import time

sys.path.insert(0, r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\trailSomeAlphas\skills\brain-feature-implementation\scripts")
os.environ.setdefault("BRAIN_USERNAME", "whitepeace567@gmail.com")
os.environ.setdefault("BRAIN_PASSWORD", "PLACEHOLDER_SET_FROM_CONFIG")

import ace_lib

API = "https://api.worldquantbrain.com"
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    cfg = json.load(open(r"D:\python\Lib\site-packages\cnhkmcp\untracked\user_config.json", encoding="utf-8"))
    creds = cfg.get("credentials") or {}
    os.environ["BRAIN_USERNAME"] = creds.get("email", "")
    os.environ["BRAIN_PASSWORD"] = creds.get("password", "")

    s = ace_lib.start_session()
    print("authenticated", flush=True)

    out = []
    seen = set()
    for t in ("MATRIX",):
        offset = 0
        limit = 50
        while True:
            url = (f"{API}/data-fields?instrumentType=EQUITY&region=USA&universe=TOP1000&delay=1"
                   f"&type={t}&dataset.id=other580&limit={limit}&offset={offset}")
            body = None
            for attempt in range(8):
                r = s.get(url)
                if r.status_code // 100 == 2:
                    body = r.json()
                    break
                wait = float(r.headers.get("Retry-After", 0) or 0)
                if r.status_code == 429:
                    wait = max(wait, 20.0)
                print(f"  type={t} off={offset} HTTP {r.status_code}; retry in {wait:.0f}s", flush=True)
                time.sleep(wait if wait else 10 * (attempt + 1))
            if body is None:
                print(f"  type={t} off={offset} FAILED after retries", flush=True)
                break
            res = body.get("results", [])
            for it in res:
                if it.get("id") not in seen:
                    seen.add(it.get("id"))
                    out.append(it)
            if offset == 0:
                print(f"  type={t} count={body.get('count')}", flush=True)
            print(f"  offset={offset} got={len(res)} total={len(out)}", flush=True)
            if len(res) < limit:
                break
            offset += limit
            time.sleep(3)

    payload = {"results": out, "count": len(out)}
    p = os.path.join(HERE, "fields_other580_USA_TOP1000_d1.json")
    json.dump(payload, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("saved", p, len(out))


if __name__ == "__main__":
    main()
