# -*- coding: utf-8 -*-
"""
Stage 2 辅助 · Workflow 脚本生成器 (AEGIS fundamental17)
为什么需要生成器：Workflow 脚本运行在 JS 沙箱里，**没有文件系统访问**，
所以字段元数据必须在生成期全部内联进提示词；同时上一版手写脚本踩了
JS 作用域坑（SHORTLIST 被写进 CTX 模板串里导致 8 个 agent 秒退），
用生成器可以彻底杜绝这类手抄错误，并保证 UTF-8 正确写入。

产出：aegis-fnd17-stage2-seeds.js
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "aegis-fnd17-stage2-seeds.js")

# 2026-10-28 housekeeping：战役目录从 .agents/aegis_coldstart/ 搬到 .agents/campaigns/。
# 全部路径改为**向上探测** .agents 根（靠 quant_framework/core 特征），不写死绝对路径。
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
    return os.path.abspath(os.path.join(os.path.dirname(cur), "..", ".."))


AGENTS = _find_agents_root(HERE)


def _first_existing(*cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[0]


SHORTLIST = _first_existing(
    os.path.join(AGENTS, "campaigns", "aegis_fnd17", "fnd17_shortlist.json"),
    os.path.join(AGENTS, "_legacy", "aegis_coldstart", "fnd17_shortlist.json"),
)
RAW = os.path.join(AGENTS, "knowledge_base", "fields", "USA", "fundamental17_raw_full.json")
PROFILE = os.path.join(AGENTS, "knowledge_base", "fields", "USA", "fundamental17.json")

BASE = HERE
# 不要预先 .replace("\\","\\\\")：js_str() 会自己做 JS 字符串转义，
# 预先转义会被转义两次 -> 渲染出 quadruple backslash，Read 工具读不到文件。
CTX_PATH = os.path.join(BASE, "CAMPAIGN_CONTEXT.md")

AXIS_LABEL = {
    "accrual_quality": "earnings quality / accruals (cash-backed earnings vs accrual earnings)",
    "profitability_roa_roe": "profitability (ROA / ROE / net margin) - the classic crowded quality factor",
    "efficiency_dupont": "efficiency (asset turnover, DuPont drivers)",
    "leverage_solvency": "leverage & solvency (debt/equity, solvency ratios)",
    "liquidity_coverage": "liquidity & coverage (current ratio, interest coverage)",
    "growth_surprise": "growth & surprise (revenue/earnings growth across periods)",
    "share_count_dilution": "share count & dilution (buybacks, issuance)",
    "cost_intensity_rd": "cost intensity & R&D (margins, cost structure)",
    "uncertainty_scale": "uncertainty / scale - USE ONLY AS A STRICTLY-POSITIVE WEIGHT OR GATE, never as the direction",
}

# 孪生配对（已在 fundamental17_raw_full.json 中逐一核实存在）
TWIN_PAIRS = [
    ("fnd17_tcpaormtt", "fnd17_tcpaormtp", "TTM return on average assets: now vs prior TTM"),
    ("fnd17_ngmpnmtt", "fnd17_ngmpnmtp", "TTM net profit margin: now vs prior TTM"),
    ("fnd17_qtotd2eq", "fnd17_qtotd2eq2", "total debt / equity: now vs one year ago"),
    ("fnd17_qcurratio", "fnd17_qcurratio2", "current ratio: now vs one year ago"),
    ("fnd17_ttmintcov", "fnd17_ptmintcov", "interest coverage: now vs prior TTM"),
    ("fnd17_shsoutbs", "fnd17_shsoutbs2", "balance-sheet shares outstanding: now vs one year ago"),
    ("fnd17_ttmrev", "fnd17_ptmrev", "TTM revenue: now vs prior TTM"),
]


def desc_of(raw_by_id, fid, fallback=""):
    f = raw_by_id.get(fid)
    if not f:
        return fallback
    return (f.get("description") or fallback).strip()


def js_obj(d):
    """把 python dict/list 序列化成**真正的 JS 字面量**（不是字符串）。

    上一版用 js_str(json.dumps(...)) 把 AXES / FIELD_TABLE 写成了 JS 字符串，
    于是 `AXES[q.axes[0]]` 恒为 undefined、`${FIELD_TABLE}` 渲染成 [object Object]，
    8 个 agent 全部拿不到字段清单。现在直接输出对象字面量。
    """
    if isinstance(d, dict):
        return "{" + ",".join(f"{js_str(k)}:{js_obj(v)}" for k, v in d.items()) + "}"
    if isinstance(d, list):
        return "[" + ",".join(js_obj(v) for v in d) + "]"
    return js_str(d)


def js_str(s):
    """安全地把标量转成 JS 字面量（保留中文，用 \\u 转义避免任何编码风险）。"""
    if s is None:
        return "null"
    if s is True:
        return "true"
    if s is False:
        return "false"
    if isinstance(s, (int, float)):
        return repr(s)
    out = []
    for ch in str(s):
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("\\u%04x" % ord(ch))
    return '"' + "".join(out) + '"'


def build_field_table(short, raw_by_id):
    """内联 143 个精选字段的完整元数据（审计 + 红队用）。"""
    rows = {}
    for axis, entries in short["axes"].items():
        for e in entries:
            fid = e["id"]
            d = desc_of(raw_by_id, fid, e.get("desc", ""))
            rows[fid] = {
                "ac": e.get("ac"), "uc": e.get("uc"), "cov": e.get("cov"),
                "dom": e.get("domain"), "sp": bool(e.get("is_sparse")),
                "desc": d[:150],
            }
    return rows


def build_field_table_text(field_table):
    """人类可读的字段元数据清单（给 agent 直接读）。

    注意：这段文本会被**原样插入 JS 模板字符串**，所以必须把反引号和 ${ 转义掉，
    否则 markdown 的 `code` 反引号会提前闭合模板字符串（实测导致 JS 语法错误）。
    """
    lines = ["`field_id | ac=alphaCount uc=userCount cov=coverage | domain | sparse | description`", ""]
    for fid, m in sorted(field_table.items(), key=lambda kv: (kv[1]["ac"] if kv[1]["ac"] is not None else 99, kv[0])):
        lines.append(
            f"- `{fid}` | ac={m['ac']} uc={m['uc']} cov={m['cov']} | {m['dom']} | "
            f"{'SP' if m['sp'] else '-'} | {m['desc']}"
        )
    return "\n".join(lines)


def escape_template_literal(s):
    """把纯文本安全地塞进 JS 模板字符串：转义反引号、反斜杠与 ${ 插值起始。"""
    s = s.replace("\\", "\\\\")
    s = s.replace("`", "\\`")
    s = s.replace("${", "\\${")
    return s


def build_axis_block(axis, entries, raw_by_id):
    lines = [f"### Axis: {axis}  ({AXIS_LABEL.get(axis, axis)})", ""]
    lines.append("`id | ac=alphaCount uc=userCount cov=coverage | domain | SP=sparse | desc`")
    lines.append("")
    for e in sorted(entries, key=lambda x: (x["ac"], x["id"])):
        d = desc_of(raw_by_id, e["id"], e.get("desc", ""))
        cov = e.get("cov")
        cov_s = f"{cov:.3f}" if isinstance(cov, (int, float)) else "?"
        sp = "SP" if e.get("is_sparse") else "-"
        lines.append(
            f"- `{e['id']}` | ac={e.get('ac','?')} uc={e.get('uc','?')} cov={cov_s} | "
            f"{e.get('domain','?')} | {sp} | {d}"
        )
    return "\n".join(lines)


TEMPLATE = r'''export const meta = {
  name: 'aegis-fnd17-stage2-seeds',
  description: 'AEGIS fundamental17 cold-start: Phase-0 seed synthesis, tech audit, red-team double-blind audit (zero backtest quota)',
  phases: [
    { title: 'SeedSynthesis', detail: '8 orthogonal seed prototypes from the 8-question framework' },
    { title: 'TechAudit', detail: 'field truth / zero-PV / FastExpr syntax / axiom compliance' },
    { title: 'RedTeam', detail: 'double-blind causal + AST-fidelity judgement' },
  ],
}

// ---- 路径常量（必须是独立顶层 const；上一版把它们塞进 CTX 模板串导致
//      SHORTLIST is not defined，8 个 agent 秒退）----
const CTX_PATH = __CTX_PATH__
const BASE_DIR = __BASE_DIR__

// ---- 内联字段元数据（Workflow 沙箱无文件系统访问）----
const FIELD_TABLE = __FIELD_TABLE__

// ---- 孪生配对表（本数据集皇冠明珠）----
const TWIN_PAIRS = [
__TWIN_PAIRS__
]

const AXES = __AXES__

const FIELD_SCHEMA = {
  type: 'object',
  properties: {
    candidates: {
      type: 'array',
      description: 'Exactly TWO distinct prototypes for this question dimension',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          question_type: { type: 'string' },
          fields_used: { type: 'array', items: { type: 'string' } },
          expression: { type: 'string' },
          economic_mechanism: { type: 'string', description: 'Chinese, >=100 chars: who is the counterparty, what behavioural bias or institutional friction sustains it in OS' },
          counterparty: { type: 'string', description: 'Chinese, who is on the other side of the trade' },
          orthogonality_note: { type: 'string', description: 'Chinese, what makes this mechanism orthogonal to the other seeds' },
          operator_count: { type: 'integer' },
          crowding_note: { type: 'string', description: 'Chinese, alphaCount/userCount of each field and why anti-crowding law is satisfied' },
        },
        required: ['id', 'question_type', 'fields_used', 'expression', 'economic_mechanism', 'counterparty', 'orthogonality_note', 'operator_count', 'crowding_note'],
        additionalProperties: false,
      },
    },
  },
  required: ['candidates'],
  additionalProperties: false,
}


// ---- 429 退避重试：上一版 8 个 agent 并发打 API，其中 4 个被 429 直接打死，
//      导致整批 0 产出。这里给每个 agent 调用加指数退避重试。
const sleepMs = (ms) => new Promise((r) => setTimeout(r, ms))
async function agentRetry(opts, attempts = 4) {
  let lastErr = null
  for (let i = 0; i < attempts; i++) {
    try {
      return await agent(opts.prompt, opts.opts)
    } catch (e) {
      lastErr = e
      const msg = String((e && e.message) || e)
      const isRate = /429|Too Many Requests|rate limit/i.test(msg)
      if (!isRate) throw e
      const wait = 2000 * Math.pow(2, i) + i * 500
      log(`429 backoff: retry ${i + 1}/${attempts} in ${wait}ms (${opts.opts.label || ''})`)
      await sleepMs(wait)
    }
  }
  throw lastErr
}

// ---- 保序并行：失败者变 null，**不改变下标**。
//      上一版用 parallel(...).filter(Boolean) 再按下标配对，一个 agent 挂掉
//      就让后面所有槽位的判决整体串位 —— 这是上一轮 workflow 14 个 agent
//      启动、0 结果的根因之一。
async function parallelOrdered(thunks) {
  const settled = await Promise.allSettled(thunks.map((t) => t()))
  return settled.map((r) => (r.status === 'fulfilled' ? r.value : null))
}

// ---- 断路器：整批若一条都没产出，直接抛，避免下游拿空数组继续跑。
function requireNonEmpty(arr, label) {
  if (!arr || arr.length === 0) {
    throw new Error(`FATAL: ${label} produced zero usable results - aborting rather than shipping an empty batch.`)
  }
  return arr
}

phase('SeedSynthesis')

const QUESTIONS = [
  { n: 'Q1', t: 'Invariance', axes: ['profitability_roa_roe', 'efficiency_dupont', 'cost_intensity_rd'],
     focus: 'Scale invariance: divide an absolute amount by an INTERNAL scale anchor (total assets / revenue / equity) to get a comparable "output per unit of resource". NEVER use price or market cap as the denominator. The trap: a raw ROA LEVEL is the most crowded quality factor in existence (ac=4 means 4 platform alphas already use it) - so you must either use a twin pair (now vs own history) or build a SECOND-ORDER deviation from the company own history.' },
  { n: 'Q2', t: 'Dynamics', axes: ['growth_surprise', 'profitability_roa_roe'],
     focus: 'Temporal dynamics: the dataset ships "prior period / one year ago" TWIN fields, so the difference between the current reading and the company OWN prior reading is a genuine second-order expectation gap. Alternatively ts_delta / ts_av_diff to capture the speed of change. You must state explicitly which side makes money (improvement long / deterioration short, or the reverse) and why.' },
  { n: 'Q3', t: 'Anomaly', axes: ['cost_intensity_rd', 'liquidity_coverage', 'uncertainty_scale'],
     focus: 'Anomaly shock: an extreme deviation of a ratio from its OWN historical baseline. Use ts_av_diff (deviation from own rolling mean) or ts_zscore over a legal window. You must pick reversion OR continuation and justify it from an institutional reason. NOTE: ts_zscore as INTERNAL normalisation destroys the signal - only zscore / group_zscore as the OUTERMOST layer is acceptable.' },
  { n: 'Q4', t: 'Interaction', axes: ['accrual_quality', 'leverage_solvency', 'liquidity_coverage'],
     focus: 'Cross-field synergy: two fields that only mean something TOGETHER (e.g. cash-backed earnings vs leverage; coverage vs debt). HARD RULE (axiom 1): NEVER multiply two signed variables (both can be negative) - that creates a fake positive when both collapse. If you use multiply, the weight term must be STRICTLY POSITIVE (e.g. rank(x), or a [0,inf) ratio).' },
  { n: 'Q5', t: 'Structure', axes: ['cost_intensity_rd', 'accrual_quality', 'efficiency_dupont'],
     focus: 'Structural share: a sub-item as a share of a total (margin structure, expense ratio, leverage mix). If the denominator can be 0 or negative you MUST add an epsilon (add(x,1)) or restructure so the ratio is well defined.' },
  { n: 'Q6', t: 'Accumulation', axes: ['growth_surprise', 'cost_intensity_rd', 'uncertainty_scale'],
     focus: 'Cumulative memory: how the effect accumulates and decays over time - use ts_mean / ts_decay_linear as a memory kernel. HARD RULE: ts_decay_* must NEVER be nested inside ts_backfill (two time operators contaminate each other and explode turnover). Correct order: reduce -> ts_backfill -> normalise -> outer decay.' },
  { n: 'Q7', t: 'Relative', axes: ['efficiency_dupont', 'leverage_solvency', 'profitability_roa_roe'],
     focus: 'Cross-sectional relativity: strength WITHIN a peer group. RED LINE: group_rank / group_zscore must NEVER be the OUTERMOST operator (output is pinned to [0,1] => one-sided book => pure beta illusion). The outermost layer must be a zero-mean construct: zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff.' },
  { n: 'Q8', t: 'Essence', axes: ['growth_surprise', 'accrual_quality', 'share_count_dilution'],
     focus: 'Essential expectation gap: the market only pays for the SURPRISE beyond expectations. Build it as "current reading vs the company OWN historical baseline" (twin pair, or ts_mean baseline) - a second-order gap. NEVER cross-sectionally rank a first-order bare level.' },
]

const seedPromises = QUESTIONS.map((q) => () => agentRetry({
  prompt:
`You are the AEGIS lead signal navigator, mining a WorldQuant BRAIN alpha for dataset fundamental17 (USA / TOP1000 / delay 1).

READ FIRST (use the Read tool): __CTX_PATH__
That is the complete campaign context contract: physical facts, the four hard axioms, platform gates, and the list of already-falsified patterns (do NOT re-burn them).

Your assigned 8-question dimension: ${q.n} ${q.t}
${q.focus}

You have access to TWO other axes' field lists for cross-axis pairing. Here are the field lists you may draw from:

${AXES[q.axes[0]]}

${AXES[q.axes[1]]}

${(q.axes[2] && AXES[q.axes[2]]) ? AXES[q.axes[2]] : ''}

THE TWIN PAIRS - the crown jewel of this dataset (a current-period field plus the SAME company one period earlier = a genuine second-order expectation gap, and the twins are usually ac=0-3 so they satisfy the anti-crowding law):
__TWIN_PAIRS__

FULL FIELD METADATA for every field above (ac = platform alphaCount, how crowded it already is):
__FIELD_TABLE_TEXT__

HARD RULES - violating any of these gets you rejected by the tech audit:
1. Only fundamental17 internal fields (id prefix fnd17_), taken from the lists above. Field count MUST be 2 or 3.
2. Operator count <= 4. Legal operators: add / subtract / divide / multiply / ts_mean / ts_delta / ts_std_dev / ts_av_diff / ts_rank / ts_zscore / ts_backfill / ts_decay_linear / group_rank / group_zscore / zscore / rank / reverse. BANNED: group_neutralize, bucket, add(rank,rank), trade_when, hump, signed_power, quantile, multiply of two signed variables, subtract(x,0.5).
3. Time windows only from {3, 5, 10, 20, 60, 120, 252}.
4. The OUTERMOST operator MUST be zero-mean: one of zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff. NEVER group_rank or rank at the top.
5. NO price / volume / market cap / valuation-multiple fields at all: no nprice, mktcap, ev_cur, pr*dayprc, vol*, priceavg*, *price2bk*, *peexclxor*, *spfcr*, ebitda2ev*, awcappspr, qwcappspr, yield. Also no external close/open/high/low/vwap/returns/volume/cap/adv20.
6. No FX / currency-code fields.
7. ANTI-CROWDING: prefer ac <= 5 (ac = 0 is virgin). fundamental17 is the single most crowded fundamental dataset on the platform (dataset alphaCount=781, userCount=380, valueScore=1) - so a bare first-order cross-sectional level on a hot field is BANNED. If a field has ac > 5 you MUST build a second-order surprise (twin pair, or deviation from own history) around it.
8. The expression must parse with Python ast.parse, balanced parentheses, legal FastExpr operator names. group_* operators take the group as a BARE literal (market / sector / industry / subindustry, NO quotes).
9. economic_mechanism (Chinese, >= 100 characters) must state: (a) WHO is on the other side of the trade - what behavioural bias or institutional friction keeps the pattern alive out-of-sample; (b) WHY this expression structure captures that mechanism; (c) the expected DIRECTION (which side you long).
10. counterparty: separately, in Chinese.
11. orthogonality_note: in Chinese, explain why this is ORTHOGONAL IN MECHANISM (not in operator choice) to the other seven seeds.
12. IMPORTANT dataset-specific physics: the data updates on quarterly/annual report cadence, so a signal that keeps producing cross-sectional dispersion on days with no new filings is actually trading a STATIC value factor, not the mechanism you declared. Prefer constructions whose variation comes from the ARRIVAL of new information (twins, ts_delta on a field that just updated) over constructions that merely re-rank static levels.
13. IMPORTANT: ratio fields (margin / growth / turnover / coverage) are naturally positively biased or signed. If you treat a ratio as "higher is better" without de-meaning it, you are actually trading the crowded quality factor, NOT your declared mechanism. Make sure the declared mechanism matches what the AST really computes.
14. If your mechanism text mentions marginal change / jump / delta / momentum (Chinese: bianhua, yuesheng, tubian, dongliang) then the expression MUST contain ts_delta, ts_zscore, subtract or divide. If it mentions gating / filtering / weighting / interaction (Chinese: menkong, guolv, fangda, quan Zhong, jiaohu) then the expression MUST contain multiply or power. The local engine mechanically checks this and will reject a mismatch.

Read the context file, pick fields that genuinely exist, then write the expression. Every field id must appear VERBATIM in the metadata table above.

Produce EXACTLY TWO candidates for your question dimension. They must be genuinely different mechanisms (not two cosmetic re-spellings of one idea): candidate A and candidate B must use DIFFERENT field pairs, and at least one of them must NOT share its core field pair with the other. Candidate A should be your best single idea; candidate B should be your second-best, genuinely orthogonal idea within the same 8-question dimension. Each candidate needs its own id (e.g. "${q.n}A" / "${q.n}B").

Return the structured JSON only.`,
  opts: { label: `seed:${q.n}`, phase: 'SeedSynthesis', schema: FIELD_SCHEMA, agentType: 'general-purpose' },
}))

const seedSlabs = requireNonEmpty(await parallelOrdered(seedPromises), 'SeedSynthesis')
log(`Phase 0 seed synthesis: ${seedSlabs.filter(Boolean).length}/8 question-slabs produced`)

// ★ 关键修复：上一版先 filter(Boolean) 再 zip，导致 auditResults[i] 与 seedResults[i]
//   错位（一个 agent 挂掉，整条流水线索引全部串位）。这里改成**按 key 严格配对**。
const seedPool = []
seedSlabs.forEach((slab) => {
  const cs = (slab && slab.candidates) || []
  cs.forEach((c) => {
    if (c && c.expression && c.id) seedPool.push(c)
  })
})
log(`Phase 0 seed pool: ${seedPool.length} candidates from ${seedSlabs.filter(Boolean).length} slabs`)

phase('TechAudit')

const AUDIT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'REJECT'] },
    issues: { type: 'array', items: { type: 'string' } },
    field_truth_ok: { type: 'boolean' },
    zero_pv_ok: { type: 'boolean' },
    syntax_ok: { type: 'boolean' },
    operator_count_ok: { type: 'boolean' },
    field_count_ok: { type: 'boolean' },
    window_ok: { type: 'boolean' },
    top_level_zero_mean_ok: { type: 'boolean' },
    axiom_compliance: { type: 'string', description: 'Chinese, check each of the four axioms one by one' },
    corrected_expression: { type: 'string', description: 'If a purely mechanical defect (window value, operator alias, quote around group) can be fixed without changing the economics, give the corrected expression; otherwise identical to the original' },
  },
  required: ['verdict', 'issues', 'field_truth_ok', 'zero_pv_ok', 'syntax_ok', 'operator_count_ok', 'field_count_ok', 'window_ok', 'top_level_zero_mean_ok', 'axiom_compliance', 'corrected_expression'],
  additionalProperties: false,
}

const auditPromises = seedPool.map((s) => () => agentRetry({
  prompt:
`You are the AEGIS technical auditor - a cold-blooded fact-finder. No literary debate, only hard facts.

READ FIRST (use the Read tool): __CTX_PATH__
(the campaign contract: the four axioms and the falsified-pattern list)

Here is the complete authoritative metadata for every field you may see:
__FIELD_TABLE_TEXT__

Audit this Phase-0 prototype:
  id: ${s.id}
  question_type: ${s.question_type}
  expression: ${s.expression}
  fields_used: ${JSON.stringify(s.fields_used)}
  economic_mechanism: ${s.economic_mechanism}

Checklist - your verdict must be grounded in each item:
1. FIELD TRUTH: does every fnd17_ id in the expression appear VERBATIM in the metadata table above? Does fields_used match EXACTLY the fields the expression uses (no more, no fewer)?
2. ZERO PV CONTAMINATION: any price / volume / market cap / valuation-multiple field, or any external PV field (close/open/high/low/vwap/returns/volume/cap/adv20)?
3. FASTEXPR SYNTAX: balanced parens, legal operator names, group_* takes a BARE literal (market/sector/industry/subindustry, no quotes), and the whole thing parses as a Python expression.
4. OPERATOR COUNT <= 4. Count the call parentheses.
5. FIELD COUNT in {2,3}.
6. WINDOW WHITELIST: every time-window argument in {3,5,10,20,60,120,252}. (ts_backfill's lookback is a gap-fill length rather than a window, but keep it 252 for consistency; if it is 250/63/126 just correct it to 252 and note it in issues.)
7. OUTERMOST ZERO-MEAN: the outermost operator must be one of zscore / ts_zscore / group_zscore / ts_delta / ts_av_diff. group_rank or rank at the top => REJECT.
8. FOUR AXIOMS:
   - axiom 1 (sign / zero conservation): are ratio fields de-meaned before any power or multiply? Is there a multiply of two signed variables? Is any multiply weight term strictly positive?
   - axiom 2 (position symmetry): do sparse fields (cov < 0.80) need ts_backfill to avoid tied-zeros dead weight?
   - axiom 3 (Occam): field count, operator count, legal windows, no grid fiddling.
   - axiom 4 (anti-crowding): what is the ac of each field used? Is it <= 5? If a field has ac > 5, is it wrapped in a second-order surprise (twin pair / own-history deviation)?
9. BANNED OPERATORS: group_neutralize / bucket / add(rank,rank) / trade_when / hump / signed_power / quantile / subtract(x,0.5).

Any hard violation => verdict REJECT with a locatable issue string.
If the ONLY problem is mechanically fixable (a window value, an operator alias, quotes around a group name, a field id typo), give the corrected expression AND still pass, noting what you changed in issues. If the fix would change the economics, REJECT instead.

Return the structured JSON only.`,
  opts: { label: `audit:${s.id}`, phase: 'TechAudit', schema: AUDIT_SCHEMA, agentType: 'general-purpose' },
}))

// ★ parallel() 保序：失败的 thunk 变成 null 而不是被删除。
//   所以这里**不能**先 filter(Boolean) 再按下标取值 —— 必须先按原位取值再过滤。
const auditRaw = await parallelOrdered(auditPromises)
const auditById = new Map()
auditRaw.forEach((a, i) => { if (a && seedPool[i]) auditById.set(seedPool[i].id, a) })

const passed = []
const rejected = []
seedPool.forEach((s) => {
  const a = auditById.get(s.id)
  if (!a) { rejected.push({ seed: s, reason: 'audit agent returned nothing' }); return }
  if (a.verdict === 'PASS') passed.push({ ...s, expression: a.corrected_expression || s.expression, audit: a })
  else rejected.push({ seed: s, reason: (a.issues || []).join('; '), audit: a })
})
log(`Tech audit: ${passed.length} passed / ${rejected.length} rejected`)

phase('RedTeam')

const RT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'REJECT'] },
    causal_assessment: { type: 'string', description: 'Chinese: is the causal chain self-consistent, who is the counterparty, what bias/friction keeps it alive in OS' },
    fidelity_assessment: { type: 'string', description: 'Chinese: does the AST compute 100% what the hypothesis claims' },
    rejection_reason: { type: 'string', description: 'If REJECT, one line stating the flaw' },
    counterparty_confirmed: { type: 'boolean' },
    fidelity_confirmed: { type: 'boolean' },
    parsimony_confirmed: { type: 'boolean' },
    final_expression: { type: 'string' },
  },
  required: ['verdict', 'causal_assessment', 'fidelity_assessment', 'rejection_reason', 'counterparty_confirmed', 'fidelity_confirmed', 'parsimony_confirmed', 'final_expression'],
  additionalProperties: false,
}

const rtPromises = passed.map((s) => () => agentRetry({
  prompt:
`You are the AEGIS double-blind red-team auditor - the overfitting and hallucination shredder. You hold a veto.

READ FIRST (use the Read tool): __CTX_PATH__
(the campaign contract: four axioms, gates, and the falsified-pattern list - use it to judge whether this re-burns a known failure)

PHYSICAL ISOLATION RULE: you must NOT see any backtest metric (Sharpe / Fitness / Margin / PnL / Drawdown do not exist in Stage 2 - it is zero-backtest by design). Judge only from three things: the physical meaning of the fields, the submitted causal micro-hypothesis, and the final AST.

Candidate under review:
  id: ${s.id}
  question_type: ${s.question_type}
  expression: ${s.expression}
  fields_used: ${JSON.stringify(s.fields_used)}
  economic_mechanism: ${s.economic_mechanism}
  counterparty: ${s.counterparty}

Authoritative metadata for the fields it uses (and for every candidate alternative field):
__FIELD_TABLE_TEXT__

TWIN PAIRS available in this dataset (current vs the company OWN prior period):
__TWIN_PAIRS__

Interrogate on two axes:
1. IS THE CAUSAL ECONOMIC CHAIN SELF-CONSISTENT?
   - Why can this pattern make money? Specifically: why does the market price it wrong at first, and what corrects it?
   - Who is the counterparty? What specific behavioural bias or institutional friction lets this persist OUT OF SAMPLE? If the only answer is "markets are inefficient", it is pseudo-logic => REJECT.
   - Do the 2-3 fields have real business logic together, or are two unrelated numbers being forced?
   - DATASET-SPECIFIC RISK: fundamental17 updates on a quarterly/annual report cadence. If the signal keeps producing cross-sectional dispersion on days with NO new filings, it is really trading a STATIC cross-sectional level (the value factor), not the declared mechanism. Check whether that is the case here.
   - SIGN RISK: ratio fields (margin / growth / ROA / turnover) are naturally positively biased or signed. If the expression treats the ratio as "higher is better" without de-meaning, it is actually trading the crowded quality factor. Judge whether the DECLARED mechanism matches what the AST actually computes.
2. DOES THE EXPRESSION FAITHFULLY IMPLEMENT THE HYPOTHESIS (AST fidelity)?
   - If the hypothesis claims a second-order expectation gap, does the AST really difference current vs a historical baseline?
   - If the hypothesis claims structural synergy, is there a genuine ratio / interaction structure?
   - Any decorative, meaningless operators? Any claimed mechanism MISSING from the AST?
   - Is the DIRECTION coherent? If the AST actually captures "high ratio = good" but the hypothesis claims "expectation-gap reversion", are those two really linked?

Only give PASS when the causal chain is self-consistent AND the code implements the hypothesis 100%.
Give final_expression: if you find a way to improve FIDELITY WITHOUT changing the economics (e.g. the mechanism claims a change but the AST uses a bare level), give the corrected expression; otherwise identical to the original.

Return the structured JSON only.`,
  opts: { label: `redteam:${s.id}`, phase: 'RedTeam', schema: RT_SCHEMA, agentType: 'general-purpose' },
}))

// ★ parallel() 保序：失败的 thunk 变成 null 而不是被删除。
//   所以这里**不能**先 filter(Boolean) 再按下标取值 —— 必须先按原位取值再过滤。
const rtRaw = await parallelOrdered(rtPromises)
const rtById = new Map()
rtRaw.forEach((r, i) => { if (r && passed[i]) rtById.set(passed[i].id, r) })
const finalPassed = []
passed.forEach((s) => {
  const r = rtById.get(s.id)
  if (!r) return
  if (r.verdict === 'PASS') finalPassed.push({ ...s, expression: r.final_expression || s.expression, redteam: r })
})

log(`Red team: ${finalPassed.length}/${passed.length} survived`)

return {
  accepted: finalPassed.map(s => ({
    id: s.id, question_type: s.question_type, fields_used: s.fields_used,
    expression: s.expression, economic_mechanism: s.economic_mechanism,
    counterparty: s.counterparty, orthogonality_note: s.orthogonality_note,
    operator_count: s.operator_count, crowding_note: s.crowding_note,
    redteam_verdict: s.redteam.verdict, causal: s.redteam.causal_assessment,
    fidelity: s.redteam.fidelity_assessment,
  })),
  rejected_by_tech: rejected.map(r => ({ id: r.seed.id, expression: r.seed.expression, reason: r.reason })),
  rejected_by_redteam: passed.filter((s) => { const r = rtById.get(s.id); return r && r.verdict === 'REJECT' })
    .map((s) => ({ id: s.id, expression: s.expression, reason: (rtById.get(s.id).rejection_reason) || '' })),
}
'''


def main():
    short = json.load(open(SHORTLIST, encoding="utf-8"))
    raw = json.load(open(RAW, encoding="utf-8"))
    raw_by_id = {f["id"]: f for f in raw}

    field_table = build_field_table(short, raw_by_id)
    field_table_text = build_field_table_text(field_table)
    axes = {ax: build_axis_block(ax, entries, raw_by_id)
            for ax, entries in short["axes"].items()}
    # AXES 的值会被插进模板字符串 —— 必须转义反引号与 ${，否则提前闭合模板串
    axes_esc = {k: escape_template_literal(v) for k, v in axes.items()}

    twin_lines = []
    for cur, old, label in TWIN_PAIRS:
        ac_cur = (raw_by_id.get(cur) or {}).get("alphaCount")
        ac_old = (raw_by_id.get(old) or {}).get("alphaCount")
        twin_lines.append(
            f"  - {cur} (ac={ac_cur})  vs  {old} (ac={ac_old})   -- {label}")

    script = (TEMPLATE
              .replace("__CTX_PATH__", js_str(CTX_PATH))
              .replace("__BASE_DIR__", js_str(BASE))
              .replace("__FIELD_TABLE_TEXT__", escape_template_literal(field_table_text))
              .replace("__FIELD_TABLE__", js_obj(field_table))
              .replace("__TWIN_PAIRS__", escape_template_literal("\n".join(twin_lines)))
              .replace("__AXES__", js_obj(axes_esc))
              )
    # TWIN_PAIRS 在模板里是数组字面量，必须是合法的 JS 元素 —— 用 JSON 字符串数组最稳
    script = re.sub(r"const TWIN_PAIRS = \[.*?\n\]",
                    "const TWIN_PAIRS = " + js_obj(twin_lines),
                    script, flags=re.S)

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)

    print(f"[SAVED] {OUT}  ({len(script)} chars)")
    print(f"  field_table entries: {len(field_table)}")
    print(f"  axes: {list(axes.keys())}")


if __name__ == "__main__":
    main()
