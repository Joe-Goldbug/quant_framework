# -*- coding: utf-8 -*-
"""零成本核查：MARKET 档的高收益是否为市场 Beta 幻觉？

S4Q 结论选了 MARKET+decay0+nanON 作为下一批基线，但 MARKET 只中和市场 beta，
不做行业/风格中和 ⇒ 其 Ret 可能含未剥离的市场暴露。

平台 metrics 里有两个直接判据（本次会话第一次被利用）：
  riskNeutralized.sharpe       —— 市场中性化后的 Sharpe
  investabilityConstrained.*   —— 可投资约束下的表现
若 MARKET 档的 risk_neutralized_sharpe 显著低于 raw sharpe，
而 STATISTICAL 档两者接近 ⇒ MARKET 的优势就是 Beta 幻觉，基线选择要改。

只 GET，零配额。
"""
import json
import os
import sys
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents"
sys.path.insert(0, r"D:\brain-mcp")
sys.path.insert(0, ROOT)
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as B

B.brain_client.session.trust_env = False
B.brain_client.session.proxies = {}

CASES = [
    ("MARKET   d0 OFF", "QPvXdRn5"),
    ("MARKET   d0 ON ", "ZYQGLgQd"),
    ("MARKET   d8 OFF", "0mYvWp1v"),
    ("MARKET   d8 ON ", "e75RJabp"),
    ("STAT     d0 OFF", "LLMJAVre"),
    ("STAT     d0 ON ", "VkxJo7R0"),
    ("STAT     d8 OFF", "xArgarYw"),
    ("STAT     d8 ON ", "QPvLv6V5"),
    ("EUR 冠军 3qVlb3dN", "3qVlb3dN"),
]


async def main():
    await B.brain_client.ensure_authenticated()
    print("=" * 126)
    print("★ Beta 幻觉核查：raw Sharpe vs riskNeutralized.sharpe vs investability")
    print("=" * 126)
    print(f"{'档':<20}{'id':<11}{'Sh':>7}{'RiskNeutSh':>12}{'比值':>8}"
          f"{'InvSh':>7}{'InvFit':>7}{'Ret%':>8}{'TO%':>7}{'Mgn':>9}{'Sub':>7}{'RobU':>7}")
    out = []
    for label, aid in CASES:
        r = await B.brain_client._request("GET", f"{B.brain_client.base_url}/alphas/{aid}",
                                           timeout=60)
        if r.status_code != 200:
            print(f"  ! {aid} HTTP {r.status_code}")
            continue
        x = r.json()
        isd = x.get("is") or {}
        m = isd.get("metrics") if isinstance(isd.get("metrics"), dict) else isd
        rn = m.get("riskNeutralized") or {}
        ic = m.get("investabilityConstrained") or {}
        vals = {c["name"]: c.get("value") for c in (isd.get("checks") or [])
                if isinstance(c, dict) and c.get("value") is not None}
        sh = m.get("sharpe") or 0
        rnsh = rn.get("sharpe")
        ratio = (rnsh / sh) if (rnsh is not None and sh) else None
        st = x.get("settings") or {}
        print(f"{label:<20}{aid:<11}{sh:>7.2f}"
              f"{(rnsh if rnsh is not None else 0):>12.2f}"
              f"{(ratio if ratio is not None else 0):>8.2f}"
              f"{(ic.get('sharpe') or 0):>7.2f}{(ic.get('fitness') or 0):>7.2f}"
              f"{(m.get('returns') or 0)*100:>8.2f}{(m.get('turnover') or 0)*100:>7.2f}"
              f"{(m.get('margin') or 0)*10000:>9.2f}"
              f"{(vals.get('LOW_SUB_UNIVERSE_SHARPE') or 0):>7.2f}"
              f"{(vals.get('LOW_ROBUST_UNIVERSE_SHARPE') or 0):>7.2f}")
        out.append({"label": label, "id": aid, "sharpe": sh, "rn_sharpe": rnsh,
                    "ratio": ratio, "inv_sharpe": ic.get("sharpe"),
                    "inv_fitness": ic.get("fitness"), "returns": m.get("returns"),
                    "turnover": m.get("turnover"), "margin": m.get("margin"),
                    "neut": st.get("neutralization"), "decay": st.get("decay"),
                    "nan": st.get("nanHandling")})
        await asyncio.sleep(0.25)

    json.dump(out, open(os.path.join(HERE, "beta_hallucination_check.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 裁决 ----
    print("\n" + "=" * 126)
    print("裁决")
    print("=" * 126)
    mkt = [o for o in out if o["neut"] == "MARKET" and o["rn_sharpe"] is not None]
    sta = [o for o in out if o["neut"] == "STATISTICAL" and o["rn_sharpe"] is not None]
    if mkt:
        print(f"  MARKET 档 RiskNeut/Sharpe 比值: {[round(o['ratio'],3) for o in mkt]}"
              f"  均值 {sum(o['ratio'] for o in mkt)/len(mkt):.3f}")
    if sta:
        print(f"  STAT   档 RiskNeut/Sharpe 比值: {[round(o['ratio'],3) for o in sta]}"
              f"  均值 {sum(o['ratio'] for o in sta)/len(sta):.3f}")
    eur = next((o for o in out if o["id"] == "3qVlb3dN"), None)
    if eur and eur["rn_sharpe"] is not None:
        print(f"\n  ★ 参照：EUR 冠军 3qVlb3dN（MARKET 档，已提交 OS，fail 全空）")
        print(f"     raw Sh={eur['sharpe']:.2f}  RiskNeut Sh={eur['rn_sharpe']:.2f}  "
              f"比值={eur['ratio']:.3f}  InvSh={eur['inv_sharpe']:.2f} "
              f"InvFit={eur['inv_fitness']:.2f}")
        print(f"     ⇒ EUR 冠军用 MARKET 档时 RiskNeut/Sharpe = {eur['ratio']:.3f}，"
              f"这是**平台已接受**的基准")
    if mkt and sta:
        mr = sum(o["ratio"] for o in mkt) / len(mkt)
        sr = sum(o["ratio"] for o in sta) / len(sta)
        print(f"\n  MARKET({mr:.3f}) vs STAT({sr:.3f})："
              f"{'MARKET 的 Beta 污染更轻 ✅ 基线选择成立' if mr >= sr - 0.05 else 'MARKET 的 Beta 污染更重 ⚠️ 需重新评估'}")


asyncio.run(main())
