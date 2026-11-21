# -*- coding: utf-8 -*-
"""AEGIS R7 统一执行 + 法医分析 + 报告更新（自包含，供定时任务/人工触发）。

顺序跑 R7A / R7B / R7C 三批仿真，做门禁裁决与法医归因，追加 R7 章节到 CAMPAIGN_REPORT.md，
更新 local_alpha_status.json。绝不调用任何 alpha 提交接口。

前置：模拟端点配额需在 2026-10-29 23:00 UTC+8 重置后才有额度。
用法：D:/python/python.exe stage10_run_R7.py
"""
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.dirname(ROOT))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ.setdefault("API_SETTINGS_TIMEOUT", "120")

from quant_framework.core.sim_runner import SimBatchRunner  # noqa: E402
from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402

DB = os.path.join(ROOT, "alphas_record.db")
NEUT = "NONE"
BATCHES = [
    ("batch_R7A.json", "stage4_run_summary_R7A.json", "R7A"),
    ("batch_R7B.json", "stage4_run_summary_R7B.json", "R7B"),
    ("batch_R7C.json", "stage4_run_summary_R7C.json", "R7C"),
]
REPORT = os.path.join(HERE, "CAMPAIGN_REPORT.md")
STATUS = os.path.join(HERE, "local_alpha_status.json")


def release_fingerprints(batch_path):
    b = json.load(open(batch_path, encoding="utf-8"))
    c = ASTSandboxCorrector()
    md5s = [c.compute_fingerprint(c.correct_expression(m["expression"]), "USA", "TOP1000", 1, NEUT)
            for m in b["slot_meta"]]
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    q = ",".join("?" * len(md5s))
    cur.execute(f"DELETE FROM alpha_fingerprints WHERE md5_hash IN ({q})", md5s)
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


async def run_one(batch_file, summary_file, tag):
    batch_path = os.path.join(HERE, batch_file)
    summary_path = os.path.join(HERE, summary_file)
    for attempt in range(1, 4):
        release_fingerprints(batch_path)
        print(f"\n=== [{tag}] attempt {attempt}/3 ===")
        try:
            res = await SimBatchRunner.run_batch_silently(
                batch_file_path=batch_path, region="USA", universe="TOP1000", delay=1,
                category="fundamental", neutralization=NEUT, decay=0, truncation=0.025,
                nan_handling="ON")
        except Exception as e:
            print(f"[{tag}] attempt {attempt} 失败: {repr(e)[:300]}")
            release_fingerprints(batch_path)
            if attempt < 3:
                await asyncio.sleep(20 * attempt)
                continue
            return None
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(f"[{tag}] ok -> {summary_file}")
        return res
    return None


def extract_metrics(summary):
    if not summary:
        return None
    rs = summary.get("alpha_results", [])
    rows = []
    for r in rs:
        m = r.get("metrics", {})
        rows.append({
            "sharpe": m.get("sharpe"), "fitness": m.get("fitness"), "turnover": m.get("turnover"),
            "returns": m.get("returns"), "drawdown": m.get("drawdown"), "margin": m.get("margin"),
            "longCount": m.get("longCount"), "shortCount": m.get("shortCount"),
            "two_year_sharpe": m.get("two_year_sharpe"),
            "risk_neutralized_sharpe": m.get("risk_neutralized_sharpe"),
            "sub_universe_sharpe": m.get("sub_universe_sharpe"),
            "code": r.get("code"), "id": r.get("id"),
        })
    return rows


def analyze():
    print("\n\n############ R7 法医分析 ############")
    meta_files = {"R7A": "batch_R7A.json", "R7B": "batch_R7B.json", "R7C": "batch_R7C.json"}
    summaries = {}
    for tag, sf, _ in [(t, s, None) for t, s, _ in BATCHES]:
        sp = os.path.join(HERE, sf)
        summaries[tag] = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else None

    best_overall = {"sharpe": -9, "tag": "", "code": ""}
    all_rows = []
    for tag, mf in meta_files.items():
        summ = summaries.get(tag)
        if not summ:
            print(f"[{tag}] 无回测结果（可能配额未恢复），跳过")
            continue
        meta = json.load(open(os.path.join(HERE, mf), encoding="utf-8"))["slot_meta"]
        rows = extract_metrics(summ)
        if not rows:
            continue
        print(f"\n--- {tag} ({len(rows)} 条) ---")
        print(f"{'role':<34}{'Sharpe':>8}{'Fit':>7}{'TO%':>7}{'2y':>7}{'rn':>7}{'L/S':>9}")
        for i, r in enumerate(rows):
            s = meta[i] if i < len(meta) else {}
            role = (s.get("role") or "")[:34]
            lsl = f"{r['longCount']}/{r['shortCount']}"
            print(f"{role:<34}{r['sharpe']:>8.2f}{r['fitness']:>7.2f}{r['turnover']*100:>7.2f}"
                  f"{r['two_year_sharpe']:>7.2f}{r['risk_neutralized_sharpe']:>7.2f}{lsl:>9}")
            r["tag"] = tag
            r["role"] = role
            r["datasets"] = "+".join(s.get("datasets", []))
            all_rows.append(r)
            if r["sharpe"] is not None and abs(r["sharpe"]) > abs(best_overall["sharpe"]):
                best_overall = {"sharpe": r["sharpe"], "tag": tag, "code": r["code"]}

    qual = [r for r in all_rows if r["sharpe"] is not None and abs(r["sharpe"]) >= 1.00]
    print("\n=== R7 汇总 ===")
    print(f"总变体: {len(all_rows)} | 通过 Step1(|Sharpe|>=1.0): {len(qual)}")
    print(f"R6 基准最佳 |Sharpe|: 0.73 (S4 应计-回购)")
    if best_overall["sharpe"] > -9:
        print(f"R7 最佳 |Sharpe|: {abs(best_overall['sharpe']):.2f} [{best_overall['tag']}] -> {best_overall['code'][:80]}")
    for r in sorted(qual, key=lambda z: -abs(z["sharpe"])):
        print(f"  达标: {r['tag']} {r['role']} Sharpe={r['sharpe']:.2f} (已本地标记，未提交)")

    # 写报告章节
    write_report_section(all_rows, qual, best_overall)
    # 更新本地状态
    update_status(qual)
    return all_rows, qual


def write_report_section(all_rows, qual, best_overall):
    if not all_rows:
        return
    lines = []
    lines.append("\n---\n\n## 8. R7 多 Agent 优化批次（研究员 A/B/C 三向正交探索）\n")
    lines.append(f"- 执行时间：2026-10-29（配额重置后），三批共 **{len(all_rows)} 个变体**，全部真实 BRAIN 仿真。")
    lines.append(f"- **提交接口调用次数：0**（仅仿真端点；达标者本地标记，交人工终审）。")
    lines.append(f"- R6 基准最佳 |Sharpe| = **0.73**（S4 应计−回购）；R7 最佳 |Sharpe| = "
                 f"**{abs(best_overall['sharpe']):.2f}** [{best_overall['tag']}]。")
    lines.append(f"- 通过 Step1 门禁（|Sharpe|≥1.0）：**{len(qual)}** 条。\n")
    lines.append("| 批 | 角色 | 数据集 | Sharpe | Fitness | 换手% | 2y | risk-neut | L/S |")
    lines.append("| :-- | :-- | :-- | --: | --: | --: | --: | --: | :-- |")
    for r in sorted(all_rows, key=lambda z: (z["tag"], -abs(z["sharpe"] or 0))):
        lines.append(
            f"| {r['tag']} | {r['role']} | {r['datasets']} | {r['sharpe']:.2f} | {r['fitness']:.2f} | "
            f"{r['turnover']*100:.2f} | {r['two_year_sharpe']:.2f} | {r['risk_neutralized_sharpe']:.2f} | "
            f"{r['longCount']}/{r['shortCount']} |")
    lines.append("\n### 8.1 法医归因与下一步")
    if qual:
        lines.append(f"- **{len(qual)} 条越过 Step1 门禁**，进入人工终审候选（见 local_alpha_status.json，submitted=false）。")
    else:
        lines.append("- 仍无变体越过 Step1 门禁（|Sharpe|≥1.0）。下一步：对 R7 表现最好的种子做 decay 扫描（decay=30/60/120）"
                     "与 SECTOR/SUBINDUSTRY 中性化对照，并考虑把 R7B 的多字段集成结果作为独立 alpha 或与其他数据集主信号叠加。")
    lines.append(f"- 全战役累计达标/提交：**{len(qual)} / 0**。（更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}）")

    existing = open(REPORT, encoding="utf-8").read()
    # 去掉旧的 R7 章节（若存在）再追加
    if "## 8. R7 多 Agent" in existing:
        idx = existing.find("## 8. R7 多 Agent")
        existing = existing[:idx].rstrip() + "\n"
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(existing + "\n".join(lines) + "\n")
    print("[ok] 已追加 R7 章节到 CAMPAIGN_REPORT.md")


def update_status(qual):
    try:
        st = json.load(open(STATUS, encoding="utf-8"))
    except Exception:
        st = {"alphas": [], "submitted": False, "submission_api_called": 0}
    if "alphas" not in st:
        st["alphas"] = []
    for r in qual:
        st["alphas"].append({
            "id": r.get("id"), "tag": r["tag"], "role": r["role"], "expression": r["code"],
            "sharpe": r["sharpe"], "fitness": r["fitness"], "qualified_step1": True,
            "submitted": False, "note": "本地标记达标，待人工终审；未提交",
        })
    st["submitted"] = False
    st["submission_api_called"] = 0
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print(f"[ok] 更新 local_alpha_status.json（达标候选 {len(qual)} 条，submitted=false）")


async def main():
    print(f"[SAFETY] submission_forbidden=True；R7 不调用任何提交接口。开始 {datetime.now()}")
    for batch_file, summary_file, tag in BATCHES:
        await run_one(batch_file, summary_file, tag)
    analyze()


if __name__ == "__main__":
    asyncio.run(main())
