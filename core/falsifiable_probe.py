"""
core/falsifiable_probe.py
独立出题器 —— 只出可检验的题, 不打分。

分工:
    LLM  : 盲读表达式 -> 独立陈述机制 -> 提出可检验命题 (不含任何指标)
    Python: 用 build_ablation_and_placebo() 造复杂度匹配的对照槽 (LLM 不碰表达式)
    数据  : 结算时由 AuditBus 从结果文件算出裁决

为什么 LLM 不写对照表达式:
    一旦由它生成 placebo, 它就能把 placebo 写成"其实还是同一机制", 双差分立刻失效。
    安慰剂必须由确定性代码构造, 才能保证"复杂度 1:1、机制 0:1"。

为什么先盲读:
    optimize_reason 是 agent 自己写的, 喂进去就是让被判者写判决书。
    这里不喂。让出题器独立说出"这段代码在赌什么", 再与 agent 的声明比对 ——
    不一致本身就是一条证据 (mechanism_mismatch)。

命令行:
    python -m core.falsifiable_probe --job <audit_probe_job_*.json> --campaign <dir> --dry-run
    python -m core.falsifiable_probe --job <...> --campaign <dir> --probe-json my_probe.json
    python -m core.falsifiable_probe --cost                 # 估算一次出题的开销
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ALLOWED_METRICS = ("sharpe_2y", "sharpe")
MIN_DELTA_RANGE = (0.10, 1.00)
# 只接受「我们真跑得动」的可观测形式, 避免出题器提出无法裁决的命题
SUPPORTED_OBSERVABLES = ("double_difference",)

SYSTEM_PROMPT = """你是量化研究组的独立审稿人。你看不到任何回测结果, 也不该猜测它。

给你一段 WorldQuant BRAIN FastExpr 表达式和所用字段的物理画像。请严格按顺序做三件事:

1) 盲读: 只根据表达式结构和字段物理含义, 独立说出这段代码在赌什么微观机制。
   不要复述算子名, 要说出"谁在犯错、为什么、错多久会被纠正"。

2) 指名对手盘: 这个信号的对手方具体是谁 (哪一类参与者、因为什么约束或激励而持续犯这个错)。

3) 出一个能被否证的题: 如果第 1 步说的机制为真是必要条件, 那么"移除该机制"与
   "移除一处等价复杂度的装饰"相比, 表现应当显著更差。请给出你会先看什么、什么结果会让你认输。

严格要求:
- 你没有回测数据, 不要编造数字, 不要预测 Sharpe。
- 若这段表达式在结构上根本无法形成可检验的机制命题 (纯堆叠、无语义), 直接弃权。
- 只输出 JSON, 不要任何解释性文字。

输出 JSON:
{
  "abstain": false,
  "abstain_reason": "",
  "independent_mechanism": "盲读得到的机制, >=15 字",
  "counterparty": "具体对手盘",
  "mechanism_claim": "一句话、可被数据否证的机制声明, >=20 字",
  "falsifiable_predictions": [
    {"prediction": "若机制为真应观察到", "falsify_if": "出现什么就认输"},
    {"prediction": "...", "falsify_if": "..."}
  ],
  "decider": {"metric": "sharpe_2y", "min_delta": 0.30},
  "confidence_note": "仅生成待验证命题, 不构成通过结论"
}"""


# ------------------------------------------------------------------ payload
def build_blind_payload(job: Dict[str, Any], slot_index: int = 0) -> Dict[str, Any]:
    """构造送审白名单。刻意不含 optimize_reason / 任何指标 / 任何历史批次。"""
    items = job.get("items") or []
    if not items:
        raise ValueError("job 中没有 items")
    item = items[slot_index] if -1 < slot_index < len(items) else items[0]
    expr = str(item.get("expression") or "").strip()
    if not expr:
        raise ValueError("item 缺少 expression")

    profiles = job.get("field_profiles") or {}
    tokens = set()
    import re
    for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr):
        if t in profiles:
            tokens.add(t)
    fields = {}
    for f in sorted(tokens):
        m = profiles.get(f) or {}
        fields[f] = {
            "domain": m.get("domain", "unbounded"),
            "sparse_zero": m.get("sparse_zero", m.get("is_sparse", False)),
            "update_frequency": m.get("update_frequency"),
            "coverage": m.get("coverage"),
            "meaning": str(m.get("description") or m.get("meaning") or "")[:120],
        }

    hypo = job.get("hypothesis") or {}
    return {
        "task": "FALSIFIABLE_PROBE",
        "ast_expression": expr,
        "fields_dictionary": fields,
        "preregistered_hypothesis": {
            "counterparty": hypo.get("counterparty"),
            "causal_chain": hypo.get("causal_chain"),
            "horizon_model": hypo.get("horizon_model"),
        },
    }


def render_prompt(payload: Dict[str, Any]) -> str:
    visible = {k: v for k, v in payload.items() if not k.startswith("_")}
    return SYSTEM_PROMPT + "\n\n【送审材料】\n" + json.dumps(visible, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ validate
def validate_probe(raw: Dict[str, Any]) -> Dict[str, Any]:
    """严格校验。宁可弃权, 不接受含糊命题。"""
    if not isinstance(raw, dict):
        raise ValueError("出题器输出不是 JSON 对象")
    if raw.get("abstain") is True:
        return {
            "abstain": True,
            "abstain_reason": str(raw.get("abstain_reason") or "未说明理由")[:200],
        }

    mech = str(raw.get("independent_mechanism") or "").strip()
    if len(mech) < 15:
        raise ValueError(f"independent_mechanism 过短 ({len(mech)} 字), 无法作为盲读基线")
    claim = str(raw.get("mechanism_claim") or "").strip()
    if len(claim) < 20:
        raise ValueError(f"mechanism_claim 过短 ({len(claim)} 字), 不可否证")

    preds = raw.get("falsifiable_predictions")
    if not isinstance(preds, list) or len(preds) < 2:
        raise ValueError("falsifiable_predictions 少于 2 条")
    clean_preds = []
    for p in preds:
        if not isinstance(p, dict):
            continue
        pv = str(p.get("prediction") or "").strip()
        fv = str(p.get("falsify_if") or "").strip()
        if not pv or not fv:
            raise ValueError("存在缺 falsify_if 的预测 —— 不可否证的命题一律拒收")
        clean_preds.append({"prediction": pv[:300], "falsify_if": fv[:300]})
    if len(clean_preds) < 2:
        raise ValueError("有效预测少于 2 条")

    dec = raw.get("decider") or {}
    metric = str(dec.get("metric") or "sharpe_2y")
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"decider.metric={metric} 不在允许集合 {ALLOWED_METRICS}")
    try:
        delta = float(dec.get("min_delta", 0.30))
    except (TypeError, ValueError):
        raise ValueError("decider.min_delta 非数值")
    if not (MIN_DELTA_RANGE[0] <= delta <= MIN_DELTA_RANGE[1]):
        raise ValueError(f"decider.min_delta={delta} 超出合理区间 {MIN_DELTA_RANGE}")

    obs = str(raw.get("observable") or "double_difference")
    if obs not in SUPPORTED_OBSERVABLES:
        raise ValueError(f"observable={obs} 当前无对应执行器, 只能出 {SUPPORTED_OBSERVABLES} 类命题")

    return {
        "abstain": False,
        "independent_mechanism": mech[:400],
        "counterparty": str(raw.get("counterparty") or "")[:200],
        "mechanism_claim": claim[:300],
        "falsifiable_predictions": clean_preds,
        "decider": {"metric": metric, "min_delta": delta,
                    "require_positive_parent": True, "rule": "double_difference"},
        "observable": obs,
        "confidence_note": str(raw.get("confidence_note") or "")[:200],
    }


# ------------------------------------------------------------------ materialize
def materialize(campaign_dir: str, job: Dict[str, Any], probe: Dict[str, Any],
                slot_index: int = 0, policy_path: Optional[str] = None) -> Dict[str, Any]:
    """把命题变成可执行实验: 记录命题 -> 造对照 -> 开实验 -> 产出待跑批次。

    对照由确定性代码构造, LLM 不参与。若骨架链过短无法造双对照, 直接拒绝materialize。
    """
    from core.audit_bus import AuditBus, resolve_policy_path
    try:
        from core.red_team import build_ablation_and_placebo
    except ImportError:
        from quant_framework.core.red_team import build_ablation_and_placebo

    if probe.get("abstain"):
        return {"ok": False, "stage": "abstain", "reason": probe.get("abstain_reason")}

    items = job.get("items") or []
    item = items[slot_index] if -1 < slot_index < len(items) else items[0]
    parent_expr = str(item.get("expression") or "").strip()

    ctrl = build_ablation_and_placebo(parent_expr)
    ablation = ctrl.get("ablation") or ""
    placebo = ctrl.get("placebo") or ""
    if not ablation or not placebo:
        return {"ok": False, "stage": "controls",
                "reason": f"无法构造双对照: {ctrl.get('notes')}. 单算子骨架无法做双差分。"}

    bus = AuditBus(campaign_dir, policy_path=policy_path or resolve_policy_path())
    batch_id = str(job.get("batch_id") or "UNKNOWN")
    probe_id = f"P-{batch_id}"

    try:
        bus.record_probe({
            "probe_id": probe_id,
            "batch_id": batch_id,
            "expression": parent_expr,
            "hypothesis_id": (job.get("hypothesis") or {}).get("hypothesis_id"),
            "mechanism_intents": item.get("mechanism_intents") or [],
            "horizon_model": (job.get("hypothesis") or {}).get("horizon_model"),
            "mechanism_claim": probe["mechanism_claim"],
            "independent_mechanism": probe["independent_mechanism"],
            "counterparty": probe.get("counterparty"),
            "falsifiable_predictions": probe["falsifiable_predictions"],
            "decider": probe["decider"],
            "slots": 3,
            "is_control": bool(job.get("is_control")),
        })
    except ValueError as e:
        return {"ok": False, "stage": "record_probe", "reason": str(e)}

    spec = {"entries": [
        {"role": "parent", "expression": parent_expr},
        {"role": "strip", "expression": ablation},
        {"role": "placebo", "expression": placebo, "control_kind": "lagged_placebo"},
    ]}
    try:
        exp = bus.open_experiment(probe_id, spec)
    except ValueError as e:
        return {"ok": False, "stage": "open_experiment", "reason": str(e)}
    run_id = exp["payload"]["run_id"]

    # 产出一个可直接投递的批次 (走原有回测链路, 不新开旁路)
    spec_meta = job.get("spec") or {}
    hyp_ref = probe.get("hypothesis_id") or spec_meta.get("hypothesis_id") or "HYP_PROBE"
    neut_val = spec_meta.get("neutralization") or "SUBINDUSTRY"
    orig_alpha = probe.get("alpha_id") or probe_id
    batch_doc = {
        "region": spec_meta.get("region") or "USA",
        "universe": spec_meta.get("universe") or "TOP1000",
        "delay": spec_meta.get("delay", 1),
        "category": spec_meta.get("category") or "other",
        "neutralization": neut_val,
        "known_fields": job.get("known_fields") or [],
        "audit_run_id": run_id,
        "audit_probe_id": probe_id,
        "items": [
            {
                "slot": 1,
                "optimize_reason": "审计对照实验母本基准槽: 复现原始完整表达并对齐 Sharpe 与 Margin 基准",
                "hypothesis_ref": hyp_ref,
                "mechanism_intents": ["CROSS_SECTIONAL_RELATIVE"],
                "economic_delta": "母本基准对照槽 (parent_control): 保持原结构验证基准 Sharpe 与换手一致性",
                "expression": parent_expr,
                "neutralization": neut_val,
                "type": "parent_control",
                "original_alpha": orig_alpha,
                "counterparty": probe.get("counterparty") or "",
            },
            {
                "slot": 2,
                "optimize_reason": "审计消融机制对照槽 (ablation_control): 剥离外层包装保留核心裸信号检验 Sharpe 净增益",
                "hypothesis_ref": hyp_ref,
                "mechanism_intents": ["CROSS_SECTIONAL_RELATIVE"],
                "economic_delta": "消融基线对照槽: 验证核心信号在无外层加工时的基准 Sharpe 贡献",
                "expression": ablation,
                "neutralization": neut_val,
                "type": "ablation_control",
                "original_alpha": orig_alpha,
                "counterparty": "",
            },
            {
                "slot": 3,
                "optimize_reason": "审计安慰剂空壳对照槽 (placebo_control): 字段滞后252日注入外层壳检验 Sharpe 是否寄生",
                "hypothesis_ref": hyp_ref,
                "mechanism_intents": ["TEMPORAL_DECAY"],
                "economic_delta": "滞后失效安慰剂槽: 检验外层包装算子在失效数据上是否伪造正 Sharpe",
                "expression": placebo,
                "neutralization": neut_val,
                "type": "placebo_control",
                "original_alpha": orig_alpha,
                "counterparty": "",
            },
        ],
    }
    out_path = os.path.join(campaign_dir, f"audit_experiment_{run_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(batch_doc, f, ensure_ascii=False, indent=2)

    return {"ok": True, "probe_id": probe_id, "run_id": run_id,
            "batch_path": out_path, "entries": spec["entries"],
            "notes": ctrl.get("notes") or []}


# ------------------------------------------------------------------ llm call
def ask_probe(payload: Dict[str, Any], llm_fn: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """调用独立会话出题。llm_fn 可注入(测试/自定义); 默认走可插拔后端。"""
    prompt = render_prompt(payload)
    if llm_fn is None:
        try:
            from core.agent_backends import create_agent_backend
        except ImportError:
            from quant_framework.core.agent_backends import create_agent_backend
        backend = create_agent_backend("builtin")
        raw = backend.send_message_sync(
            role="aegis-falsifiable-probe",
            model="default",
            prompt=prompt,
            json_mode=True,
        )
        if isinstance(raw, str):
            from core.agent_backends import extract_json_from_text
            raw = extract_json_from_text(raw) or {}
    else:
        raw = llm_fn(prompt)
        if isinstance(raw, str):
            raw = json.loads(raw)
    return raw


def run_job(job_path: str, campaign_dir: str, slot_index: int = 0,
            probe_json: Optional[str] = None, dry_run: bool = False,
            llm_fn: Optional[Callable[[str], Any]] = None,
            policy_path: Optional[str] = None) -> Dict[str, Any]:
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)
    payload = build_blind_payload(job, slot_index)

    if dry_run:
        print(render_prompt(payload))
        print("\n--- 以上是送审材料 (不含任何指标与 agent 自述) ---")
        print("手工出题后: --probe-json <文件> 即可落地。")
        return {"ok": True, "stage": "dry_run", "payload": payload}

    if probe_json:
        with open(probe_json, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = ask_probe(payload, llm_fn=llm_fn)

    try:
        probe = validate_probe(raw)
    except ValueError as e:
        print(f"❌ 出题不合规: {e}")
        return {"ok": False, "stage": "validate", "reason": str(e), "raw": raw}

    if probe.get("abstain"):
        print(f"⚪ 出题器弃权: {probe['abstain_reason']}")
        return {"ok": False, "stage": "abstain", "reason": probe["abstain_reason"]}

    # 盲读 vs agent 自述: 不一致本身就是证据, 落盘备查
    claimed = str((job.get("items") or [{}])[slot_index].get("optimize_reason") or "")
    mismatch = None
    if claimed:
        mismatch = _rough_mismatch(probe["independent_mechanism"], claimed)

    res = materialize(campaign_dir, job, probe, slot_index, policy_path)
    res["probe"] = probe
    res["mechanism_mismatch_suspected"] = mismatch
    if res.get("ok"):
        print(f"✅ 已开题 {res['probe_id']} -> {res['run_id']}")
        print(f"   待跑批次: {res['batch_path']}")
        print(f"   对照: 母本 / 消融 / 安慰剂 (复杂度由代码保证 1:1)")
        if mismatch:
            print(f"   ⚠️ 盲读机制与 agent 自述疑似不一致, 已记录 (非判决依据, 仅提示)")
    else:
        print(f"❌ {res.get('stage')}: {res.get('reason')}")
    return res


def _rough_mismatch(independent: str, claimed: str) -> bool:
    """粗粒度词重叠检查: 只作提示, 不作判决。"""
    import re as _re
    def toks(s):
        return {t for t in _re.findall(r"[\u4e00-\u9fa5]{2,}", s or "")}
    a, b = toks(independent), toks(claimed)
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / max(1, min(len(a), len(b))) < 0.15


def estimate_cost() -> Dict[str, Any]:
    """出题本身很便宜; 贵的是它出的题要占回测槽位。"""
    return {
        "prompt_chars_approx": len(SYSTEM_PROMPT) + 900,
        "tokens_per_call_approx": 2200,
        "output_tokens_approx": 600,
        "batches_to_one_probe": "5% 抽样 + 间隔>=4 批 -> 平均约 20 批出 1 题",
        "backtest_slots_per_probe": 3,
        "note": "每日 8 次出题 = 24 槽, 相对 100 批 x 20 槽 = 2000 槽 占 1.2%; token 从来不是瓶颈。",
    }


def main():
    ap = argparse.ArgumentParser(description="独立出题器 (只出题, 不打分)")
    ap.add_argument("--job", help="audit_probe_job_*.json 路径")
    ap.add_argument("--campaign", help="campaign 目录")
    ap.add_argument("--slot", type=int, default=0, help="job 中第几个 item 送审")
    ap.add_argument("--probe-json", default=None, help="手工/预生成的命题 JSON")
    ap.add_argument("--dry-run", action="store_true", help="只打印送审材料, 不调模型")
    ap.add_argument("--cost", action="store_true", help="打印成本估算")
    args = ap.parse_args()

    if args.cost:
        print(json.dumps(estimate_cost(), ensure_ascii=False, indent=2))
        return
    if not args.job or not args.campaign:
        ap.error("需要 --job 与 --campaign")
    res = run_job(args.job, args.campaign, args.slot, args.probe_json, args.dry_run)
    sys.exit(0 if res.get("ok") else 2)


if __name__ == "__main__":
    main()
