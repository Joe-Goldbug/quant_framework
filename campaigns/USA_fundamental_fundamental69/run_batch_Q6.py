# -*- coding: utf-8 -*-
"""
FCF_Q6 恢复提交器 (Recovered-Submission Runner)

背景
----
2026-10-28 前序会话在 FCF_Q6 批次上遭遇 3 次 "Failed to connect" 提交失败，
未取得 Location 头 ⇒ 平台侧未创建任何 multisimulation ⇒ 配额未消耗。
workflow_state.json 里记录的 last_multisimulation_id 实际是 Q3 的旧 ID（陈旧状态）。
Q6 的 8 条表达式已在 batch_FCF_Q6_red_team.json 取得 all_passed=True 的双盲通行证。

本脚本职责
----------
1. 复用 SimBatchRunner.verify_state_token_and_gates 完整执行 AEGIS 五大硬门禁
   (Gate0 装满8槽 / Gate1 红队通行证 / Gate3 骨架防摸鱼 / Gate4 处方锁 / Gate5 Tabu
    / Gate2 AST 量纲与 PV 隔离)，确保发包表达式经过物理审计。
2. 以「Location 落盘优先」的方式提交：拿到 Location 的第一时间写入
   simulation_status_Q6.json，随后再有连接故障也绝不重复提交 (杜绝配额双烧)。
3. 遵守铁律 2：前 60s 完全静默，之后每 20s 静默轮询，全程零聊天日志。
4. 结果落盘 batch_FCF_Q6_result.json，并保留完整 checks / ra 双形态。

硬规则
------
- 本脚本只做仿真 (simulation)，**绝不调用任何 Alpha 提交接口**。
"""

import asyncio
import json
import os
import sys
import time

# ---------------------------------------------------------------- 路径解析
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_agents_root(start):
    cur = os.path.abspath(start)
    probe = cur if os.path.isdir(cur) else os.path.dirname(cur)
    for _ in range(8):
        if os.path.isdir(os.path.join(probe, "quant_framework", "core")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return None


ROOT = _find_agents_root(HERE)
if ROOT is None:
    raise SystemExit("[FATAL] 无法定位 .agents 根目录 (含 quant_framework/core)")
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import main as bm  # noqa: E402  brain-mcp 生产模块
from quant_framework.core.sim_runner import SimBatchRunner  # noqa: E402

# ---------------------------------------------------------------- 战役参数
BATCH_FILE = os.path.join(HERE, "batch_FCF_Q6.json")
STATUS_FILE = os.path.join(HERE, "simulation_status_Q6.json")
RESULT_FILE = os.path.join(HERE, "batch_FCF_Q6_result.json")

REGION = "USA"
UNIVERSE = "TOP1000"
DELAY = 1
CATEGORY = "fundamental"
NEUTRALIZATION = "NONE"
DECAY = 0
TRUNCATION = 0.025
NAN_HANDLING = "ON"


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def _already_submitted():
    """幂等保护：若状态文件里已有 location，说明已提交过，绝不重发。"""
    if not os.path.exists(STATUS_FILE):
        return None
    try:
        st = _load(STATUS_FILE)
    except Exception:
        return None
    return st.get("location") or None


async def main():
    batch = _load(BATCH_FILE)
    items = batch.get("items", [])
    known_fields = batch.get("known_fields", {})

    # ---- 幂等检查 -------------------------------------------------------
    prior = _already_submitted()
    if prior:
        print(f"[SKIP] 状态文件已含 Location: {prior} —— 不重复提交，直接续接轮询。")
        location = prior
    else:
        # ---- 五大硬门禁 (物理审计) --------------------------------------
        corrected = SimBatchRunner.verify_state_token_and_gates(
            batch_file_path=BATCH_FILE,
            expressions_data=items,
            known_fields=known_fields,
            category=CATEGORY,
            region=REGION,
            universe=UNIVERSE,
            delay=DELAY,
            neutralization=NEUTRALIZATION,
        )
        print(f"[GATE] 全部硬门禁通过，待发表达式 {len(corrected)} 条。")

        # ---- 提交 (Location 落盘优先) -----------------------------------
        sub = await bm.submit_multi_simulation(
            alpha_expressions=corrected,
            instrument_type="EQUITY",
            region=REGION,
            universe=UNIVERSE,
            delay=DELAY,
            decay=DECAY,
            neutralization=NEUTRALIZATION,
            truncation=TRUNCATION,
            pasteurization="ON",
            unit_handling="VERIFY",
            nan_handling=NAN_HANDLING,
            language="FASTEXPR",
            visualization=False,
        )
        if sub.get("error"):
            raise RuntimeError(f"提交失败: {sub.get('error')} | {sub.get('details','')}")
        location = sub.get("location")
        if not location:
            raise RuntimeError(f"提交未返回 Location: {sub}")

        _save(STATUS_FILE, {
            "seed_id": batch.get("batch_id"),
            "status": "SUBMITTED",
            "simulation_id": sub.get("multisimulation_id"),
            "location": location,
            "batch_file": os.path.basename(BATCH_FILE),
            "total_requested": len(corrected),
            "total_created": len(corrected),
            "results_saved": False,
            "safe_to_resubmit": False,
            "local_exact_fingerprint_matches": 0,
            "note": "FCF_Q6 恢复提交 (前序会话 3 次连接失败未创建)。Alpha 提交接口严禁调用。",
            "submitted_at_epoch": time.time(),
        })
        print(f"[SUBMIT] Location 已落盘: {location}")

    # ---- 铁律 2：静默轮询 (前 60s 无查询) --------------------------------
    await asyncio.sleep(60)
    poll = 0
    while True:
        poll += 1
        chk = await bm.check_multi_simulation(location)
        status = chk.get("status")
        print(f"[静默轮询 #{poll}] status={status} children={chk.get('n_children')}")
        if status in ("COMPLETE", "COMPLETED", "DONE", "ERROR", "CANCELLED"):
            break
        await asyncio.sleep(20)

    if status != "COMPLETE":
        _save(STATUS_FILE, {**_load(STATUS_FILE), "status": status})
        print(f"[ABORT] 批次终态非 COMPLETE: {status}")
        return

    # ---- 拉取结果 --------------------------------------------------------
    fetched = await bm.fetch_multi_simulation_result(location)
    results = fetched.get("alpha_results", [])
    _save(RESULT_FILE, {
        "multisimulation_id": location.rstrip("/").split("/")[-1],
        "status": "COMPLETE",
        "total_requested": len(corrected) if not prior else len(items),
        "total_created": len(results),
        "simulation_only": True,
        "alpha_submission_calls": 0,
        "settings": {
            "region": REGION, "universe": UNIVERSE, "delay": DELAY,
            "decay": DECAY, "neutralization": NEUTRALIZATION,
            "truncation": TRUNCATION, "nan_handling": NAN_HANDLING,
            "pasteurization": "ON", "unit_handling": "VERIFY",
        },
        "alpha_results": results,
    })

    st = _load(STATUS_FILE)
    _save(STATUS_FILE, {**st, "status": "COMPLETE", "results_saved": True,
                        "total_created": len(results)})

    # ---- 摘要 (审计用完整形态) ------------------------------------------
    print("\n=== FCF_Q6 结果摘要 ===")
    for i, r in enumerate(results, 1):
        m = r.get("metrics") or r.get("is") or {}
        ra = r.get("ra") or {}
        chk = r.get("checks") or {}
        fails = chk.get("fail") or []
        warns = chk.get("warning") or []
        ra_fail = ra.get("ra_failed_checks") or []
        # 权威失败集：checks.fail 与 ra.ra_failed_checks 取并集 (修复历史假通过漏洞)
        all_fail = sorted(set([f.get("name") for f in fails if isinstance(f, dict)]
                               + list(ra_fail)))
        print(f"slot{i:>2} {r.get('alpha_id')} Sh={m.get('sharpe')} Fit={m.get('fitness')} "
              f"TO={m.get('turnover')} Mgn={m.get('margin')} subU={m.get('sub_universe_sharpe')} "
              f"2Y={m.get('two_year_sharpe')} RA_FAIL={all_fail} WARN={len(warns)}")
    print(f"\n[OK] 结果已写: {RESULT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
