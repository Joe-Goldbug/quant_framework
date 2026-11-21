# -*- coding: utf-8 -*-
"""零成本：定位 FAIL↔WARNING 翻转的真实判别变量（第 2 版，含 os/train/test 字段）。

已排除：neutralization / decay / nanHandling / maxTrade / pasteurization / stage / long+short 数量
嫌疑：truncation、os 字段存在性、train/test 分段、prod 字段、grade、classifications
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


async def fetch_all(stage):
    out, url = [], f"{B.brain_client.base_url}/users/self/alphas?limit=100&offset=0&stage={stage}"
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

    def short_of(x):
        isd = x.get("is") or {}
        ch = isd.get("checks") or []
        f = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "FAIL"]
        w = [c.get("name") for c in ch if isinstance(c, dict) and c.get("result") == "WARNING"]
        return f, w

    # 收集"LOW_SHARPE 报 FAIL"和"报 WARNING"两组
    F, W = [], []
    for x in rows:
        st = x.get("settings") or {}
        if st.get("region") != "USA" or st.get("universe") != "TOP1000" or st.get("delay") != 1:
            continue
        isd = x.get("is") or {}
        if not isinstance(isd, dict):
            continue
        f, w = short_of(x)
        rec = {
            "id": x.get("id"), "trunc": st.get("truncation"), "decay": st.get("decay"),
            "neut": st.get("neutralization"), "sharpe": isd.get("sharpe"),
            "fitness": isd.get("fitness"), "turnover": isd.get("turnover"),
            "returns": isd.get("returns"),
            "has_os": x.get("os") is not None,
            "os_keys": sorted(x.get("os").keys()) if isinstance(x.get("os"), dict) else None,
            "has_train": x.get("train") is not None,
            "has_test": x.get("test") is not None,
            "train_keys": sorted(x.get("train").keys()) if isinstance(x.get("train"), dict) else None,
            "test_keys": sorted(x.get("test").keys()) if isinstance(x.get("test"), dict) else None,
            "has_prod": x.get("prod") is not None,
            "grade": x.get("grade"), "status": x.get("status"),
            "n_class": len(x.get("classifications") or []),
            "class_ids": [c.get("id") for c in (x.get("classifications") or [])],
            "n_fail": len(f), "n_warn": len(w), "fails": f, "warns": w,
        }
        if "LOW_SHARPE" in f:
            F.append(rec)
        elif "LOW_SHARPE" in w:
            W.append(rec)

    print("=" * 110)
    print(f"LOW_SHARPE=FAIL n={len(F)}   LOW_SHARPE=WARN n={len(W)}")
    print("=" * 110)

    def cmp(name, key):
        cf = Counter(str(r[key]) for r in F)
        cw = Counter(str(r[key]) for r in W)
        onlyf = set(cf) - set(cw)
        onlyw = set(cw) - set(cf)
        sep = "  ★完全分离" if onlyf and onlyw and not (set(cf) & set(cw)) else ""
        print(f"{name:<18} FAIL={dict(cf)}")
        print(f"{'':<18} WARN={dict(cw)}{sep}")
        if onlyf and onlyw and not (set(cf) & set(cw)):
            print(f"{'':<18} 分离: FAIL独有={onlyf}  WARN独有={onlyw}")

    for k in ("trunc", "decay", "neut", "has_os", "has_train", "has_test", "has_prod",
              "status", "n_class", "os_keys", "train_keys", "test_keys", "grade"):
        cmp(k, k)

    # os 字段内容对比
    print("\n=== os 字段样例 ===")
    for tag, grp in (("FAIL", F), ("WARN", W)):
        withos = [r for r in grp if r["has_os"]]
        print(f"{tag}: has_os {len(withos)}/{len(grp)}")
        if withos:
            print("   os_keys 分布:", Counter(str(r["os_keys"]) for r in withos).most_common(3))

    # class_ids 对比
    print("\n=== classifications 对比 ===")
    print("FAIL:", Counter(tuple(sorted(r["class_ids"])) for r in F).most_common(6))
    print("WARN:", Counter(tuple(sorted(r["class_ids"])) for r in W).most_common(6))

    # n_fail 分布
    print("\n=== n_fail 分布 ===")
    print("FAIL组:", Counter(r["n_fail"] for r in F))
    print("WARN组:", Counter(r["n_fail"] for r in W))

    json.dump({"F": F, "W": W}, open(os.path.join(HERE, "gate_failwarn_probe.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)


asyncio.run(main())
