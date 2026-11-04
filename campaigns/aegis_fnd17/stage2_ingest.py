# -*- coding: utf-8 -*-
"""Stage 2 · 工作流产物回收器（把 Workflow 的 agent transcript 落成 slices/*.json）

Workflow 工具的返回值不在磁盘上；每个 sub-agent 的完整对话在
`~/.claude/projects/<slug>/<session>/subagents/workflows/<runId>/agent-*.jsonl`。
本脚本把这些 transcript 里的 **StructuredOutput tool_use 的 input** 抠出来，
按 label（seed:Q1 / audit:Q1A / redteam:Q1A）归类，写成 slices/slice_{A,B,C,D}.json
与 stage2_workflow_raw.json，供 stage3_assemble.py 消费。

用法：
    python stage2_ingest.py [--run-id wf_xxx] [--session-dir <path>]
"""
import argparse
import json
import os
import re
import sys

import _paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _paths.ROOT
CAMPAIGN = _paths.CAMPAIGN

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def default_workflow_root():
    """~/.claude/projects/*/*/subagents/workflows —— 取最近修改的 session 下的所有 run。"""
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    cands = []
    for proj in os.listdir(base):
        p = os.path.join(base, proj)
        if not os.path.isdir(p):
            continue
        for sess in os.listdir(p):
            wf = os.path.join(p, sess, "subagents", "workflows")
            if os.path.isdir(wf):
                cands.append((os.path.getmtime(wf), wf))
    cands.sort(reverse=True)
    return cands[0][1] if cands else None


def iter_agent_files(wf_root):
    for d in sorted(os.listdir(wf_root)):
        p = os.path.join(wf_root, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if f.startswith("agent-") and f.endswith(".jsonl"):
                yield d, os.path.join(p, f)


def extract_tool_inputs(jsonl_path):
    """抽出 transcript 里所有 StructuredOutput / tool_use 的 input。"""
    out = []
    try:
        lines = open(jsonl_path, encoding="utf-8").read().splitlines()
    except Exception:
        return out
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        msg = d.get("message") or {}
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") != "tool_use":
                continue
            inp = c.get("input")
            if isinstance(inp, dict):
                out.append((c.get("name") or "", inp))
    return out


def label_from_prompt(jsonl_path):
    """agent 的 label 藏在 meta.json 里没有；退而求其次：从第一条 user prompt 里抠标识。"""
    try:
        lines = open(jsonl_path, encoding="utf-8").read().splitlines()
    except Exception:
        return ""
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        msg = d.get("message") or {}
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        txt = ""
        if isinstance(content, str):
            txt = content
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    txt += c.get("text") or ""
        # 审计/红队 prompt 里有 "Audit this Phase-0 prototype:\n  id: X"
        m = re.search(r"^\s*id:\s*(\S+)\s*$", txt, re.M)
        if m:
            return m.group(1)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--session-dir", default=None, help="workflows 根目录（含多个 run 子目录）")
    args = ap.parse_args()

    wf_root = args.session_dir or default_workflow_root()
    if not wf_root or not os.path.isdir(wf_root):
        print("❌ 找不到 workflow transcript 目录")
        return 1
    if args.run_id:
        wf_root = os.path.join(wf_root, args.run_id)
        if not os.path.isdir(wf_root):
            print(f"❌ run 不存在: {wf_root}")
            return 1

    print(f"[INGEST] workflow root = {wf_root}")

    seeds, audits, rts = [], [], []
    for run, path in iter_agent_files(wf_root):
        tools = extract_tool_inputs(path)
        sid = label_from_prompt(path)
        for name, inp in tools:
            if not isinstance(inp, dict):
                continue
            if "candidates" in inp and isinstance(inp.get("candidates"), list):
                cands = inp["candidates"]
                for c in cands:
                    if isinstance(c, dict) and c.get("expression"):
                        c.setdefault("agent", run)
                        seeds.append(c)
                print(f"  seed slab  run={run} id={sid} n={len(cands)}")
            elif "expression" in inp and "question_type" in inp and "fields_used" in inp:
                # 旧版扁平 schema（上一轮 workflow 的产出）—— 同样是真种子
                inp.setdefault("id", sid or "LEGACY")
                inp.setdefault("agent", run)
                seeds.append(inp)
                print(f"  seed flat  run={run} id={inp.get('id')}")
            elif "verdict" in inp and "corrected_expression" in inp:
                audits.append({"id": sid, "run": run, "audit": inp})
                print(f"  audit      run={run} id={sid} verdict={inp.get('verdict')}")
            elif "verdict" in inp and "final_expression" in inp:
                rts.append({"id": sid, "run": run, "redteam": inp})
                print(f"  redteam    run={run} id={sid} verdict={inp.get('verdict')}")

    print(f"\n  合计: seeds={len(seeds)} audits={len(audits)} redteams={len(rts)}")

    raw = {
        "workflow_root": wf_root,
        "seeds": seeds,
        "audits": audits,
        "redteams": rts,
    }
    rawp = os.path.join(CAMPAIGN, "stage2_workflow_raw.json")
    json.dump(raw, open(rawp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[SAVED] {rawp}")

    if not seeds:
        print("⚠️ 没有任何种子产出 —— workflow 可能仍在跑或 agent 全灭。")
        return 2

    # ---- 合并审计 + 红队判决到每条种子 ----
    audit_by_id = {a["id"]: a["audit"] for a in audits if a.get("id")}
    rt_by_id = {r["id"]: r["redteam"] for r in rts if r.get("id")}

    # ---- 切片：按字段组合的"来源多样性"分成 A/B/C/D 四片 ----
    #  切片只是**并行装配的分组**，不是语义分组；Stage 3 装配器会跨片挑选 8 槽。
    buckets = {"A": [], "B": [], "C": [], "D": []}
    keys = sorted(buckets)
    for i, s in enumerate(seeds):
        keys[i % 4]
        # 轮转填充，保证每片字段尽可能不重叠
        buckets[keys[i % 4]].append(s)

    slice_dir = os.path.join(CAMPAIGN, "slices")
    os.makedirs(slice_dir, exist_ok=True)
    for k in keys:
        cs = buckets[k]
        # 合入审计/红队结论
        for c in cs:
            a = audit_by_id.get(c.get("id"))
            r = rt_by_id.get(c.get("id"))
            if a:
                c["tech_audit"] = a
                if a.get("corrected_expression"):
                    c["expression"] = a["corrected_expression"]
            if r:
                c["redteam"] = r
                if r.get("final_expression"):
                    c["expression"] = r["final_expression"]
            c["mechanism"] = c.get("economic_mechanism", "")
            c["fields"] = c.get("fields_used", [])
            c["optimize_reason"] = c.get("economic_mechanism", "")
            c["counterparty"] = c.get("counterparty", "")
            c["treatment_tag"] = c.get("treatment_tag", "none")
            c["self_check"] = c.get("self_check", {})
        p = os.path.join(slice_dir, f"slice_{k}.json")
        json.dump({"agent": k, "candidates": cs}, open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"[SAVED] {p}  ({len(cs)} 条)")

    # ---- 判决汇总 ----
    def v(audit_by_id, rt_by_id, sid):
        a = (audit_by_id.get(sid) or {}).get("verdict")
        r = (rt_by_id.get(sid) or {}).get("verdict")
        return a, r

    print("\n===== 逐条判决 =====")
    for s in seeds:
        a, r = v(audit_by_id, rt_by_id, s.get("id"))
        print(f"  {str(s.get('id')):<10} tech={str(a):<7} rt={str(r):<7} {s.get('expression','')[:92]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
