"""
core/fastexpr_ast.py
WorldQuant Brain FastExpr 统一 AST 编译器与双阶段门禁核心 (AEGIS V4.1)

统一替代分散在各模块中的 `ast.parse(..., mode='eval')`：
1. 原生支持 BRAIN 多行分号语义赋值 (SNC 规范) 与单行表达式，通过 `mode='exec'` 编译并内联局部变量。
2. 强制执行 SNC 语义命名同构检查 (`validate_snc`) 与相邻语句去重。
3. 强制执行经济学时间尺度离散晶格 (`validate_horizon_lattice`)，封堵连续窗口与非线性参数微调过拟合。
4. 提供变量名无关的正则等价键 (`canonical_equivalence_key`) 与保留 `vec_*` 且定位 `args[1]` 的双向消融/安慰剂构造器 (`build_named_ablation_and_placebo`)。
"""
from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.operator_registry import OperatorRegistry


DAILY_LATTICE: Set[int] = {1, 3, 5, 10, 20, 21, 60, 63, 126, 252}
MONTHLY_LATTICE: Set[int] = {20, 21, 42, 60, 63, 126, 252}
QUARTERLY_LATTICE: Set[int] = {60, 63, 66, 125, 126, 252}
WINSORIZE_STD_LATTICE: Set[float] = {3.0, 4.0}
POWER_EXP_LATTICE: Set[float] = {0.25, 0.5, 1.0, 1.5, 2.0}

SNC_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{5,40}$")
GENERIC_VAR_STEMS: Set[str] = {
    "tmp", "temp", "var", "val", "value", "res", "result", "out", "output",
    "data", "sig", "signal", "alpha", "factor", "step", "item", "foo", "bar",
    "test", "expr", "inter", "mid", "part", "comp", "component",
}

OP_FAMILY_MAP: Dict[str, str] = {
    "zscore": "NORM",
    "group_zscore": "NORM",
    "normalize": "NORM",
    "group_normalize": "NORM",
    "scale": "NORM",
    "group_scale": "NORM",
    "winsorize": "NORM",
    "quantile": "NORM",
    "ts_zscore": "TS_NORM",
    "ts_scale": "TS_NORM",
    "ts_quantile": "TS_NORM",
    "rank": "RANK",
    "group_rank": "RANK",
    "ts_rank": "TS_RANK",
    "ts_mean": "SMOOTH",
    "ts_sum": "SMOOTH",
    "ts_decay_linear": "SMOOTH",
    "ts_decay_exp_window": "SMOOTH",
    "ts_target_tvr_decay": "SMOOTH",
    "ts_median": "SMOOTH",
    "ts_backfill": "FILL",
    "group_backfill": "FILL",
    "ts_delta": "DIFF",
    "ts_av_diff": "DIFF",
    "subtract": "DIFF",
    "ts_delay": "LAG",
    "divide": "RATIO",
    "multiply": "INTERACT",
    "add": "COMBINE",
    "ts_corr": "COUPLE",
    "ts_covariance": "COUPLE",
    "ts_regression": "REGRESS",
    "group_neutralize": "NEUTRALIZE",
    "trade_when": "GATE",
    "if_else": "GATE",
    "filter": "GATE",
    "ts_std_dev": "DISPERSION",
    "ts_ir": "RATIO",
    "ts_arg_max": "EXTREMA",
    "ts_arg_min": "EXTREMA",
    "s_log_1p": "COMPRESS",
    "log": "COMPRESS",
    "sqrt": "COMPRESS",
    "signed_power": "NONLINEAR",
    "power": "NONLINEAR",
    "abs": "MAGNITUDE",
    "sign": "SIGN",
    "reverse": "SIGN",
    "right_tail": "TAIL",
    "left_tail": "TAIL",
    "tail": "TAIL",
    "bucket": "BUCKET",
    "truncate": "NORM",
    "hump": "SMOOTH",
}

SNC_SUFFIX_ALLOWED_FAMILIES: Dict[str, Set[str]] = {
    "zscore": {"NORM", "TS_NORM"},
    "norm": {"NORM", "TS_NORM"},
    "scaled": {"NORM", "TS_NORM"},
    "scale": {"NORM", "TS_NORM"},
    "winsor": {"NORM"},
    "rank": {"RANK", "TS_RANK"},
    "pct": {"RANK", "TS_RANK", "NORM"},
    "quantile": {"NORM", "TS_NORM"},
    "ema": {"SMOOTH"},
    "ma": {"SMOOTH"},
    "mean": {"SMOOTH"},
    "sum": {"SMOOTH"},
    "decay": {"SMOOTH"},
    "smooth": {"SMOOTH"},
    "delta": {"DIFF"},
    "chg": {"DIFF"},
    "diff": {"DIFF"},
    "shock": {"DIFF", "TS_NORM"},
    "surprise": {"DIFF", "TS_NORM"},
    "mom": {"DIFF", "SMOOTH", "RANK"},
    "accel": {"DIFF"},
    "lag": {"LAG"},
    "delay": {"LAG"},
    "gate": {"GATE"},
    "gated": {"GATE"},
    "cond": {"GATE"},
    "mask": {"GATE"},
    "ratio": {"RATIO", "COUPLE"},
    "div": {"RATIO"},
    "spread": {"DIFF", "RATIO"},
    "neut": {"NEUTRALIZE"},
    "neutral": {"NEUTRALIZE"},
    "resid": {"NEUTRALIZE", "REGRESS", "DIFF"},
    "residual": {"NEUTRALIZE", "REGRESS", "DIFF"},
    "std": {"DISPERSION"},
    "vol": {"DISPERSION"},
    "corr": {"COUPLE", "REGRESS"},
    "cov": {"COUPLE"},
    "beta": {"REGRESS", "COUPLE"},
    "reg": {"REGRESS"},
    "vec": {"VEC"},
    "scalar": {"VEC"},
    "avg": {"SMOOTH", "VEC"},
    "max": {"EXTREMA", "VEC"},
    "min": {"EXTREMA", "VEC"},
    "fill": {"FILL"},
    "filled": {"FILL"},
    "backfill": {"FILL"},
    "filter": {"GATE"},
    "z": {"NORM", "TS_NORM"},
    "win": {"NORM"},
    "power": {"NONLINEAR"},
    "pow": {"NONLINEAR"},
    "rev": {"SIGN"},
    "inv": {"SIGN"},
    "abs": {"MAGNITUDE"},
    "mag": {"MAGNITUDE"},
    "tail": {"TAIL"},
    "bucket": {"BUCKET"},
    "log": {"COMPRESS"},
    "comp": {"COMPRESS", "NONLINEAR"},
    "ir": {"RATIO"},
    "signal": set(),
    "alpha": set(),
}

SNC_GENERIC_EXACT_NAMES: Set[str] = {
    "tmp_signal", "temp_signal", "test_signal", "my_signal", "raw_signal",
    "alpha_1", "alpha_2", "signal_1", "signal_2", "factor_1", "factor_2",
    "var_one", "var_two", "step_one", "step_two", "mid_var", "inter_var",
}

TS_ARG2_WINDOW_OPS: Set[str] = {"ts_corr", "ts_covariance", "ts_regression"}
TS_NO_WINDOW_OPS: Set[str] = {"ts_step", "ts_target_tvr_decay", "ts_delta_limit"}

SHELL_DECORATION_OPS: Set[str] = {
    "rank", "group_rank", "zscore", "group_zscore", "normalize", "group_normalize",
    "scale", "group_scale", "group_neutralize", "winsorize", "quantile", "bucket",
    "hump", "truncate", "ts_decay_linear", "ts_decay_exp_window", "ts_mean",
    "ts_backfill", "group_backfill", "ts_target_tvr_decay", "ts_av_diff",
    "ts_zscore", "ts_rank", "ts_scale",
}


def _strip_comments(text: str) -> str:
    """去除 FastExpr 中的 // 与 /* */ 注释（尊重引号边界）"""
    out: List[str] = []
    i = 0
    n = len(text)
    in_quote: Optional[str] = None
    while i < n:
        ch = text[i]
        if in_quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_top_level_statements(text: str) -> List[str]:
    """按顶层 ';' 或完整的顶层换行切分 FastExpr 语句，消除缩进陷阱"""
    stmts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_quote: Optional[str] = None
    n = len(text)
    i = 0

    def _incomplete_tail(s: str) -> bool:
        stripped = s.rstrip()
        if not stripped:
            return False
        for tok in ("==", "!=", "<=", ">=", "&&", "||", "=", "+", "-", "*", "/", ",", "("):
            if stripped.endswith(tok):
                return True
        return False

    def _starts_continuation(idx: int) -> bool:
        j = idx + 1
        while j < n and text[j] in (" ", "\t", "\r", "\n"):
            j += 1
        if j >= n:
            return False
        for tok in ("+", "-", "*", "/", "&&", "||", ",", ")"):
            if text.startswith(tok, j):
                return True
        return False

    while i < n:
        ch = text[i]
        if in_quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch in "([{":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0 and ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf.clear()
            i += 1
            continue
        if depth == 0 and ch == "\n":
            cur = "".join(buf)
            if cur.strip() and not _incomplete_tail(cur) and not _starts_continuation(i):
                stmts.append(cur.strip())
                buf.clear()
                i += 1
                continue
            buf.append(" ")
            i += 1
            continue
        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _normalize_operators_in_stmt(stmt: str) -> str:
    """将 FastExpr 逻辑运算符 (&&, ||, !) 安全转换为 Python AST 可解析语法（跳过字符串字面量）"""
    out: List[str] = []
    i = 0
    n = len(stmt)
    in_quote: Optional[str] = None
    while i < n:
        ch = stmt[i]
        if in_quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(stmt[i + 1])
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            out.append(ch)
            i += 1
            continue
        if stmt.startswith("&&", i):
            out.append(" and ")
            i += 2
            continue
        if stmt.startswith("||", i):
            out.append(" or ")
            i += 2
            continue
        if ch == "!" and not stmt.startswith("!=", i):
            out.append(" not ")
            i += 1
            continue
        # FastExpr 允许中文全角双引号等，统一替换为 ASCII 双引号
        if ch in ("“", "”"):
            out.append('"')
            i += 1
            continue
        out.append(ch)
        i += 1
    return " ".join("".join(out).split())


def preprocess_fastexpr(expr: str) -> Tuple[str, List[str], Optional[str]]:
    """
    预处理 Brain FastExpr 为可被 ast.parse(..., mode='exec') 解析的 Python 语句序列。
    返回: (python_code, statements_list, error_msg)
    """
    if not expr or not str(expr).strip():
        return "", [], "表达式为空"
    cleaned = _strip_comments(str(expr))
    raw_stmts = _split_top_level_statements(cleaned)
    if not raw_stmts:
        return "", [], "预处理后无有效语句"
    norm_stmts = [_normalize_operators_in_stmt(s) for s in raw_stmts if s.strip()]
    return "\n".join(norm_stmts), norm_stmts, None


@dataclass
class ParsedFastExpr:
    raw_expr: str
    python_code: str
    statements: List[str] = field(default_factory=list)
    module_ast: Optional[ast.Module] = None
    final_ast: Optional[ast.expr] = None
    assignments: Dict[str, ast.expr] = field(default_factory=dict)
    assignment_list: List[Tuple[str, ast.expr, str]] = field(default_factory=list)
    assignment_order: List[str] = field(default_factory=list)
    local_vars: Set[str] = field(default_factory=set)
    all_calls: List[str] = field(default_factory=list)
    operator_count: int = 0
    raw_call_count: int = 0
    referenced_identifiers: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    has_terminal_expr: bool = True

    @property
    def is_valid(self) -> bool:
        return self.module_ast is not None and self.final_ast is not None and not self.errors

    def to_inline_expression(self) -> str:
        if self.final_ast is None:
            return self.raw_expr.strip()
        try:
            return ast.unparse(self.final_ast)
        except Exception:
            return self.raw_expr.strip()


def _inline_variables(node: ast.AST, env: Dict[str, ast.expr], depth: int = 0) -> ast.AST:
    """深拷贝 AST 并递归内联局部变量绑定，禁止在 FunctionDef/keyword arg 上错误替换"""
    if depth > 32:
        return copy.deepcopy(node)
    if isinstance(node, ast.Name):
        if node.id in env:
            return _inline_variables(copy.deepcopy(env[node.id]), env, depth + 1)
        return copy.deepcopy(node)
    cloned = copy.deepcopy(node)
    if isinstance(cloned, ast.Call):
        cloned.args = [_inline_variables(a, env, depth) for a in cloned.args]
        for kw in cloned.keywords:
            kw.value = _inline_variables(kw.value, env, depth)
        return cloned
    for field_name, value in ast.iter_fields(cloned):
        if isinstance(value, ast.AST):
            setattr(cloned, field_name, _inline_variables(value, env, depth))
        elif isinstance(value, list):
            setattr(
                cloned,
                field_name,
                [_inline_variables(v, env, depth) if isinstance(v, ast.AST) else v for v in value],
            )
    return cloned


def parse_fastexpr(expr: str) -> ParsedFastExpr:
    """
    统一 FastExpr 解析器：
    - 支持单行与多行分号赋值语法 (mode='exec')
    - 提取 `assignments`、算子计数 (`vec_*` 不计入策略算子上限)、外部数据字段标识
    - 构造内联后的 `final_ast` 供 AST 维度检查、同构去重与反事实消融使用
    """
    OperatorRegistry.load()
    python_code, stmts, prep_err = preprocess_fastexpr(expr)
    res = ParsedFastExpr(raw_expr=str(expr or ""), python_code=python_code, statements=stmts)
    if prep_err:
        res.errors.append(prep_err)
        return res

    try:
        mod = ast.parse(python_code, mode="exec")
    except SyntaxError as e:
        res.errors.append(f"FastExpr 语法错误 (line {e.lineno}): {e.msg}")
        return res

    res.module_ast = mod
    if not mod.body:
        res.errors.append("AST 为空")
        return res

    env: Dict[str, ast.expr] = {}
    last_expr: Optional[ast.expr] = None

    for idx, stmt in enumerate(mod.body):
        raw_stmt_str = stmts[idx] if idx < len(stmts) else ""
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                res.errors.append("FastExpr 赋值左值必须是单一变量名")
                return res
            lhs = stmt.targets[0].id
            res.local_vars.add(lhs)
            res.assignment_order.append(lhs)
            # Incremental env binding prevents self-referential substitution loops
            inlined_rhs = _inline_variables(stmt.value, env)
            res.assignments[lhs] = inlined_rhs
            res.assignment_list.append((lhs, stmt.value, raw_stmt_str))
            env[lhs] = inlined_rhs
        elif isinstance(stmt, ast.Expr):
            last_expr = stmt.value
        else:
            res.errors.append(f"禁止的非表达式/赋值语句: {type(stmt).__name__}")
            return res

    if last_expr is not None:
        res.has_terminal_expr = True
        res.final_ast = _inline_variables(last_expr, env)
    elif res.assignment_order:
        res.has_terminal_expr = False
        res.final_ast = copy.deepcopy(res.assignments[res.assignment_order[-1]])
    else:
        res.errors.append("缺少终结表达式")
        return res

    ast.fix_missing_locations(res.final_ast)

    # Collect calls and external field identifiers across all statements (prior to or via module_ast)
    keep_tokens = OperatorRegistry.get_keep_tokens()
    call_func_ids: Set[int] = set()
    for stmt in mod.body:
        node_to_walk = stmt.value if isinstance(stmt, (ast.Assign, ast.Expr)) else stmt
        for node in ast.walk(node_to_walk):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                call_func_ids.add(id(node.func))
                op_name = node.func.id
                res.all_calls.append(op_name)
                res.raw_call_count += 1
                if not op_name.startswith("vec_"):
                    res.operator_count += 1
            elif isinstance(node, ast.BinOp):
                res.operator_count += 1
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if id(node) in call_func_ids:
                    continue
                ident = node.id
                if ident in res.local_vars or ident in keep_tokens or ident in set(res.all_calls):
                    continue
                if ident in ("True", "False", "true", "false", "None", "null"):
                    continue
                res.referenced_identifiers.add(ident)

    return res


def _rhs_outer_op_and_arg_vars(rhs: ast.expr) -> Tuple[Optional[str], List[str]]:
    """提取赋值右值最外层算子名及其直接引用的变量名列表"""
    arg_vars: List[str] = []
    if isinstance(rhs, ast.Call) and isinstance(rhs.func, ast.Name):
        op_name = rhs.func.id
        for arg in rhs.args:
            if isinstance(arg, ast.Name):
                arg_vars.append(arg.id)
        return op_name, arg_vars
    if isinstance(rhs, ast.BinOp):
        op_map = {
            ast.Add: "add",
            ast.Sub: "subtract",
            ast.Mult: "multiply",
            ast.Div: "divide",
        }
        for side in (rhs.left, rhs.right):
            if isinstance(side, ast.Name):
                arg_vars.append(side.id)
        return op_map.get(type(rhs.op)), arg_vars
    if isinstance(rhs, ast.UnaryOp) and isinstance(rhs.op, ast.USub):
        if isinstance(rhs.operand, ast.Name):
            arg_vars.append(rhs.operand.id)
        return "reverse", arg_vars
    return None, arg_vars


def _count_ast_non_vec_ops(node: ast.AST, operators: Set[str]) -> int:
    """统计单条 AST 子树内的非 vec_* 算子调用数（用于阻断单行包壳堆叠）。"""
    cnt = 0
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            fn = sub.func.id
            if fn.startswith("vec_"):
                continue
            if fn in operators or fn in OP_FAMILY_MAP:
                cnt += 1
        elif isinstance(sub, ast.BinOp) and isinstance(sub.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            cnt += 1
    return cnt


def validate_snc(
    expr_or_parsed: Any,
    require_snc_when_complex: bool = False,
    min_complex_ops: int = 4,
    max_ops_per_statement: int = 3,
) -> Dict[str, Any]:
    """
    强制 SNC (Semantic Naming Convention) 编译门禁：
    1. 当 require_snc_when_complex=True 且算子数 >= 4 时，强制拆解为 >= 2 条多行分号语义赋值，
       且单条语句右值非 vec_* 算子数 <= 3，彻底封死“单行意面”与“1 行包壳伪多行”两种绕过；
    2. 所有赋值变量名必须满足 `^[a-z][a-z0-9_]{5,40}$`，且语义主体前缀不得全为泛化占位词 (foo/bar/tmp/var 等)；
    3. 变量名后缀必须位于授权机制词表内且与右值外层强结构算子家族严格同构，封死胡编后缀绕过；
    4. 禁止相邻语句及终结语句无维度/语义跃迁地堆叠同一家族算子。
    """
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    violations: List[str] = []
    if not parsed.is_valid:
        return {"passed": False, "violations": list(parsed.errors), "assignments": 0}

    OperatorRegistry.load()
    known_ops = OperatorRegistry.get_all_operator_names()

    if require_snc_when_complex and parsed.operator_count >= int(min_complex_ops):
        if len(parsed.assignment_list) == 0:
            violations.append(
                f"[SNC-Missing] 复杂表达式含 {parsed.operator_count} 个算子 (>= {int(min_complex_ops)})，"
                f"必须使用多行分号语义变量命名 (SNC) 拆解假设步骤，禁止单行深度嵌套堆叠"
            )
        elif len(parsed.assignment_list) < 2:
            violations.append(
                f"[SNC-CollapsedStep] 复杂表达式含 {parsed.operator_count} 个算子 (>= {int(min_complex_ops)})，"
                f"仅使用 {len(parsed.assignment_list)} 条赋值语句属于单行包壳伪多行，必须拆解为 >= 2 个语义步骤"
            )
        for lhs, rhs_node, _raw_stmt in parsed.assignment_list:
            rhs_ops = _count_ast_non_vec_ops(rhs_node, known_ops)
            if rhs_ops > int(max_ops_per_statement):
                violations.append(
                    f"[SNC-CollapsedStep] 赋值语句 `{lhs}` 右值包含 {rhs_ops} 个嵌套算子 (> {int(max_ops_per_statement)})，"
                    f"禁止把多层算子积木塞进单条语句，请拆分为清晰的中间语义变量"
                )
        if parsed.module_ast and parsed.module_ast.body:
            last_stmt = parsed.module_ast.body[-1]
            if isinstance(last_stmt, ast.Expr):
                term_ops = _count_ast_non_vec_ops(last_stmt.value, known_ops)
                if term_ops > int(max_ops_per_statement):
                    violations.append(
                        f"[SNC-CollapsedStep] 终结表达式包含 {term_ops} 个嵌套算子 (> {int(max_ops_per_statement)})，"
                        f"禁止在末尾行继续深层堆叠，请先拆解为命名语义变量"
                    )

    strong_families = {"RANK", "TS_RANK", "NORM", "TS_NORM", "SMOOTH", "NEUTRALIZE", "GATE", "DIFF"}
    prev_stmt_info: Optional[Tuple[str, str, str]] = None  # (lhs, op_name, op_family)

    for lhs, rhs_node, _raw_stmt in parsed.assignment_list:
        if not SNC_NAME_RE.match(lhs):
            violations.append(
                f"[SNC-Naming] 变量名 '{lhs}' 违反 SNC 格式规范 (`^[a-z][a-z0-9_]{{5,40}}$`，严禁 u/x/a/s1/tmp 等无意义短命名)"
            )
            continue

        tokens = [t for t in lhs.split("_") if t]
        if len(tokens) < 2:
            violations.append(
                f"[SNC-Naming] 变量名 '{lhs}' 必须使用 snake_case `<semantic>_<intent>` 两段以上结构，严禁单音节/无结构名词"
            )
            continue
        if lhs in SNC_GENERIC_EXACT_NAMES or all(t in GENERIC_VAR_STEMS or t.isdigit() for t in tokens):
            violations.append(
                f"[SNC-Generic] 变量名 '{lhs}' 缺少经济学语义主体与机制词干，严禁使用 tmp/var/step/alpha_1 等泛化命名"
            )
            continue
        prefix_tokens = tokens[:-1]
        if prefix_tokens and all(t in GENERIC_VAR_STEMS or t.isdigit() for t in prefix_tokens):
            violations.append(
                f"[SNC-GenericPrefix] 变量名 '{lhs}' 的语义主体前缀 '{'_'.join(prefix_tokens)}' 属于泛化占位词，"
                f"必须体现真实底层字段或经济学物理主体"
            )
            continue

        outer_op, arg_vars = _rhs_outer_op_and_arg_vars(rhs_node)
        if outer_op:
            if outer_op.startswith("vec_"):
                op_family = "VEC"
            else:
                op_family = OP_FAMILY_MAP.get(outer_op, "")
            suffix = tokens[-1]
            # 1) Suffix -> op_family strict isomorphism (NO silent pass backdoor!)
            if suffix in SNC_SUFFIX_ALLOWED_FAMILIES:
                allowed = SNC_SUFFIX_ALLOWED_FAMILIES[suffix]
                if allowed:
                    if op_family and op_family not in allowed:
                        violations.append(
                            f"[SNC-Isomorphism] 变量 '{lhs}' 后缀 '_{suffix}' 与右值外层算子 `{outer_op}` ({op_family}) 语义冲突"
                        )
                elif op_family in strong_families:
                    # Wildcard suffix like _signal / _alpha is not enough on strong structural ops unless an earlier intent token matches
                    has_matching_intent = any(
                        tok in SNC_SUFFIX_ALLOWED_FAMILIES
                        and bool(SNC_SUFFIX_ALLOWED_FAMILIES[tok])
                        and op_family in SNC_SUFFIX_ALLOWED_FAMILIES[tok]
                        for tok in tokens[1:-1]
                    )
                    if not has_matching_intent:
                        violations.append(
                            f"[SNC-SuffixMissing] 变量 '{lhs}' 使用泛化后缀 '_{suffix}' 承接强结构算子 `{outer_op}` ({op_family})，"
                            f"必须使用与 {op_family} 同构的授权机制后缀"
                        )
            else:
                if op_family in strong_families:
                    has_matching_suffix = any(
                        tok in SNC_SUFFIX_ALLOWED_FAMILIES
                        and bool(SNC_SUFFIX_ALLOWED_FAMILIES[tok])
                        and op_family in SNC_SUFFIX_ALLOWED_FAMILIES[tok]
                        for tok in tokens[1:]
                    )
                    if not has_matching_suffix:
                        violations.append(
                            f"[SNC-SuffixMissing] 变量 '{lhs}' 后缀 '_{suffix}' 不在授权机制词表中且未体现右值算子 `{outer_op}` ({op_family}) 的物理变换意图，"
                            f"严禁胡编无意义后缀绕过 SNC"
                        )

            # 2) Adjacent-statement same-family redundancy check
            if prev_stmt_info is not None:
                prev_lhs, prev_op, prev_family = prev_stmt_info
                if prev_lhs in arg_vars and op_family and op_family == prev_family:
                    if op_family in {"RANK", "TS_RANK", "NORM", "TS_NORM", "SMOOTH", "NEUTRALIZE"}:
                        violations.append(
                            f"[SNC-RedundantStack] 相邻语句 `{prev_lhs} ({prev_op})` -> `{lhs} ({outer_op})` 在无维度/结构跃迁下重复堆叠同家族算子 `{op_family}`"
                        )
            prev_stmt_info = (lhs, outer_op, op_family)
        else:
            prev_stmt_info = (lhs, "", "")

    # Check terminal bare expression statement for adjacent same-family redundancy against last assignment
    if parsed.module_ast and parsed.module_ast.body and prev_stmt_info is not None:
        last_stmt = parsed.module_ast.body[-1]
        if isinstance(last_stmt, ast.Expr):
            outer_op, arg_vars = _rhs_outer_op_and_arg_vars(last_stmt.value)
            if outer_op:
                op_family = "VEC" if outer_op.startswith("vec_") else OP_FAMILY_MAP.get(outer_op, "")
                prev_lhs, prev_op, prev_family = prev_stmt_info
                if prev_lhs in arg_vars and op_family and op_family == prev_family:
                    if op_family in {"RANK", "TS_RANK", "NORM", "TS_NORM", "SMOOTH", "NEUTRALIZE"}:
                        violations.append(
                            f"[SNC-RedundantStack] 终结语句 `({outer_op})` 直接承接 `{prev_lhs} ({prev_op})`，无维度跃迁地重复堆叠 `{op_family}`"
                        )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "assignments": len(parsed.assignment_list),
    }


def _extract_numeric_constant(node: ast.AST) -> Optional[float]:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _extract_numeric_constant(node.operand)
        return -inner if inner is not None else None
    return None


def validate_horizon_lattice(
    expr_or_parsed: Any,
    update_frequency: str = "daily",
) -> Dict[str, Any]:
    """
    强制时间尺度与超参离散晶格校验 (反过拟合铁律)：
    - 日频时间窗 d ∈ {1, 5, 10, 21, 63, 126, 252}
    - 月频时间窗 d ∈ {21, 42, 63, 126, 252}
    - 季频时间窗 d ∈ {63, 66, 125, 126, 252, 504}
    - winsorize std ∈ {3, 4}
    - power / signed_power exponent ∈ {0.25, 0.5, 1.0, 1.5, 2.0}
    """
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    violations: List[str] = []
    if not parsed.is_valid or parsed.final_ast is None:
        return {"passed": False, "violations": list(parsed.errors), "windows": []}

    freq = (update_frequency or "daily").strip().lower()
    if freq in ("quarterly", "quarter", "q"):
        allowed_windows = QUARTERLY_LATTICE | DAILY_LATTICE
    elif freq in ("monthly", "month", "m"):
        allowed_windows = MONTHLY_LATTICE | DAILY_LATTICE
    else:
        allowed_windows = DAILY_LATTICE

    windows_found: List[int] = []

    for node in ast.walk(parsed.final_ast):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        fn = node.func.id

        # 1) winsorize std lattice
        if fn == "winsorize":
            std_val: Optional[float] = None
            for kw in node.keywords:
                if kw.arg == "std":
                    std_val = _extract_numeric_constant(kw.value)
            if std_val is None and len(node.args) >= 2:
                std_val = _extract_numeric_constant(node.args[1])
            if std_val is not None and std_val not in WINSORIZE_STD_LATTICE:
                violations.append(
                    f"[Lattice-Param] winsorize(std={std_val:g}) 非法：仅允许离散截断档 {sorted(WINSORIZE_STD_LATTICE)}，禁止连续微调边界"
                )
            continue

        # 2) power / signed_power exponent lattice
        if fn in ("power", "signed_power"):
            exp_val: Optional[float] = None
            for kw in node.keywords:
                if kw.arg in ("y", "exp", "exponent"):
                    exp_val = _extract_numeric_constant(kw.value)
            if exp_val is None and len(node.args) >= 2:
                exp_val = _extract_numeric_constant(node.args[1])
            if exp_val is not None and exp_val not in POWER_EXP_LATTICE:
                violations.append(
                    f"[Lattice-Param] {fn}(exponent={exp_val:g}) 非法：仅允许离散凸度档 {sorted(POWER_EXP_LATTICE)}，禁止曲线拟合指数"
                )
            continue

        # 3) Time-series lookback window lattice
        if fn.startswith("ts_") and fn not in TS_NO_WINDOW_OPS:
            win_node: Optional[ast.AST] = None
            for kw in node.keywords:
                if kw.arg in ("d", "lookback", "window"):
                    win_node = kw.value
                    break
            if win_node is None:
                win_idx = 2 if fn in TS_ARG2_WINDOW_OPS else 1
                if len(node.args) > win_idx:
                    win_node = node.args[win_idx]
            if win_node is not None:
                val = _extract_numeric_constant(win_node)
                if val is not None:
                    if val <= 0 or abs(val - round(val)) > 1e-9:
                        violations.append(f"[Lattice-Window] {fn} 窗口参数 `{val}` 必须为正整数周期")
                    else:
                        w_int = int(round(val))
                        windows_found.append(w_int)
                        if w_int not in allowed_windows:
                            violations.append(
                                f"[Lattice-Window] {fn}(d={w_int}) 脱离 {freq} 经济学时间晶格 {sorted(allowed_windows)}，禁止随意构造非标准窗口过拟合"
                            )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "windows": windows_found,
        "allowed_windows": sorted(allowed_windows),
    }


def extract_all_windows(expr_or_parsed: Any) -> List[int]:
    """抽取表达式中全部 ts_* 回看窗口整数（跳过 ts_step 等无窗口算子）"""
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    if not parsed.is_valid or parsed.final_ast is None:
        return []
    wins: List[int] = []
    for node in ast.walk(parsed.final_ast):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        fn = node.func.id
        if not fn.startswith("ts_") or fn in TS_NO_WINDOW_OPS:
            continue
        win_node: Optional[ast.AST] = None
        for kw in node.keywords:
            if kw.arg in ("d", "lookback", "window"):
                win_node = kw.value
                break
        if win_node is None:
            win_idx = 2 if fn in TS_ARG2_WINDOW_OPS else 1
            if len(node.args) > win_idx:
                win_node = node.args[win_idx]
        if win_node is not None:
            val = _extract_numeric_constant(win_node)
            if val is not None and val > 0:
                wins.append(int(round(val)))
    return wins


def _canonical_ast_str(node: ast.AST, keep_tokens: Set[str], preserve_constants: bool = False) -> str:
    """将 AST 规范化为无视局部变量名及可交换操作数顺序的等价键；preserve_constants 控制是否保留离散数值常量"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if preserve_constants:
                val = float(node.value)
                return str(int(round(val))) if abs(val - round(val)) < 1e-9 else f"{val:g}"
            return "<NUM>"
        return repr(node.value)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            inner = _canonical_ast_str(node.operand, keep_tokens, preserve_constants=preserve_constants)
            return f"reverse({inner})"
        return _canonical_ast_str(node.operand, keep_tokens, preserve_constants=preserve_constants)
    if isinstance(node, ast.BinOp):
        op_map = {
            ast.Add: ("add", True),
            ast.Sub: ("subtract", False),
            ast.Mult: ("multiply", True),
            ast.Div: ("divide", False),
        }
        name, comm = op_map.get(type(node.op), ("binop", False))
        l_str = _canonical_ast_str(node.left, keep_tokens, preserve_constants=preserve_constants)
        r_str = _canonical_ast_str(node.right, keep_tokens, preserve_constants=preserve_constants)
        if comm:
            pair = sorted([l_str, r_str])
            return f"{name}({pair[0]},{pair[1]})"
        return f"{name}({l_str},{r_str})"
    if isinstance(node, ast.Compare):
        parts = [_canonical_ast_str(node.left, keep_tokens, preserve_constants=preserve_constants)]
        for c in node.comparators:
            parts.append(_canonical_ast_str(c, keep_tokens, preserve_constants=preserve_constants))
        return f"cmp({','.join(parts)})"
    if isinstance(node, ast.BoolOp):
        vals = sorted(_canonical_ast_str(v, keep_tokens, preserve_constants=preserve_constants) for v in node.values)
        return f"{type(node.op).__name__.lower()}({','.join(vals)})"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        fn = node.func.id if isinstance(node.func, ast.Name) else ast.unparse(node.func)
        args_str = [_canonical_ast_str(a, keep_tokens, preserve_constants=preserve_constants) for a in node.args]
        if fn in ("add", "multiply", "ts_corr", "ts_covariance") and len(args_str) >= 2:
            if fn in ("add", "multiply") and len(args_str) == 2:
                args_str = sorted(args_str)
            elif fn in ("ts_corr", "ts_covariance") and len(args_str) >= 3:
                args_str[:2] = sorted(args_str[:2])
        kw_str = [
            f"{kw.arg}={_canonical_ast_str(kw.value, keep_tokens, preserve_constants=preserve_constants)}"
            for kw in sorted(node.keywords, key=lambda k: k.arg or "")
        ]
        return f"{fn}({','.join(args_str + kw_str)})"
    return ast.unparse(node)


def exact_canonical_key(expr_or_parsed: Any) -> str:
    """
    精确等价键（保留离散晶格窗口整数与数值常量，归一化变量名、空白、+ vs add 与交换律顺序）：
    用于严格拦截变相重复回测，同时放行合法的同骨架 N/2N 高原稳健性探针！
    """
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    if not parsed.is_valid or parsed.final_ast is None:
        return re.sub(r"\s+", "", str(expr_or_parsed or ""))
    OperatorRegistry.load()
    return _canonical_ast_str(parsed.final_ast, OperatorRegistry.get_keep_tokens(), preserve_constants=True)


def topology_equivalence_key(expr_or_parsed: Any) -> str:
    """
    拓扑骨架键（抹平数值常量为 <NUM>，归一化变量名与交换律顺序）：
    用于跟踪同拓扑多窗口探索配额（放行 2~3 个合法离散晶格窗口做 HorizonProbe 高原验证，拦截网格微调）。
    """
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    if not parsed.is_valid or parsed.final_ast is None:
        return re.sub(r"\s+", "", str(expr_or_parsed or ""))
    OperatorRegistry.load()
    return _canonical_ast_str(parsed.final_ast, OperatorRegistry.get_keep_tokens(), preserve_constants=False)


def canonical_equivalence_key(expr_or_parsed: Any, preserve_constants: bool = False) -> str:
    """向后兼容别名：默认返回拓扑骨架键，preserve_constants=True 时返回精确等价键。"""
    return exact_canonical_key(expr_or_parsed) if preserve_constants else topology_equivalence_key(expr_or_parsed)


def _extract_core_signal_node(node: ast.AST, operators: Set[str]) -> ast.AST:
    """
    从内联 AST 中剥离外层装饰性壳算子以构造精确消融信号：
    - 遇到 `vec_*` 整体保留，绝不拆开向量字段；
    - 遇到 `trade_when` / `if_else` / `filter` 时定位信号分支 `args[1]`；
    - 遇到双元关系/比值/差值时保持至底层单信号节点或直接拆解主干。
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = node.func.id
        if fn.startswith("vec_"):
            return copy.deepcopy(node)
        if fn in ("trade_when", "if_else", "filter") and len(node.args) >= 2:
            return _extract_core_signal_node(node.args[1], operators)
        if fn in SHELL_DECORATION_OPS and len(node.args) >= 1:
            return _extract_core_signal_node(node.args[0], operators)
        if fn in ("s_log_1p", "log", "sqrt", "abs", "sign", "reverse", "power", "signed_power", "ts_delay", "ts_delta") and len(node.args) >= 1:
            return _extract_core_signal_node(node.args[0], operators)
        if fn in ("divide", "subtract", "add", "multiply", "ts_corr", "ts_covariance", "ts_regression") and len(node.args) >= 1:
            return _extract_core_signal_node(node.args[0], operators)
    if isinstance(node, ast.UnaryOp):
        return _extract_core_signal_node(node.operand, operators)
    if isinstance(node, ast.BinOp):
        return _extract_core_signal_node(node.left, operators)
    return copy.deepcopy(node)


def _replace_with_lagged_placebo(node: ast.AST, target_fields: Set[str], lag_days: int = 252) -> ast.AST:
    """
    将表达式中的真实字段替换为 ts_delay(..., 252) 滞后失效安慰剂，
    关键修复：若字段由 vec_* 包裹，则在 vec_* 外层施加 ts_delay(vec_*(field), 252)，保留向量类型合法性。
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = node.func.id
        if fn.startswith("vec_") and any(
            isinstance(n, ast.Name) and n.id in target_fields for n in ast.walk(node)
        ):
            return ast.Call(
                func=ast.Name(id="ts_delay", ctx=ast.Load()),
                args=[copy.deepcopy(node), ast.Constant(value=lag_days)],
                keywords=[],
            )
        cloned = copy.deepcopy(node)
        cloned.args = [_replace_with_lagged_placebo(a, target_fields, lag_days) for a in cloned.args]
        for kw in cloned.keywords:
            kw.value = _replace_with_lagged_placebo(kw.value, target_fields, lag_days)
        return cloned
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in target_fields:
        return ast.Call(
            func=ast.Name(id="ts_delay", ctx=ast.Load()),
            args=[ast.Name(id=node.id, ctx=ast.Load()), ast.Constant(value=lag_days)],
            keywords=[],
        )
    cloned = copy.deepcopy(node)
    for field_name, value in ast.iter_fields(cloned):
        if isinstance(value, ast.AST):
            setattr(cloned, field_name, _replace_with_lagged_placebo(value, target_fields, lag_days))
        elif isinstance(value, list):
            setattr(
                cloned,
                field_name,
                [_replace_with_lagged_placebo(v, target_fields, lag_days) if isinstance(v, ast.AST) else v for v in value],
            )
    return cloned


def build_named_ablation_and_placebo(
    expr_or_parsed: Any,
    known_fields: Optional[Set[str]] = None,
    lag_days: int = 252,
) -> Dict[str, Any]:
    """
    构建语义保留的 Slot 2 (Ablation 极简基线) 与 Slot 3 (Placebo 252日滞后结构空壳)：
    - 自动穿透多行 SNC 变量绑定并还原合法单行控制变体；
    - `vec_*` 整体保留不被拆毁；
    - `trade_when`/`if_else`/`filter` 精准切入 `args[1]` 提取主信号。
    """
    parsed = expr_or_parsed if isinstance(expr_or_parsed, ParsedFastExpr) else parse_fastexpr(str(expr_or_parsed))
    OperatorRegistry.load()
    all_ops = OperatorRegistry.get_all_operator_names()
    raw_fallback = str(expr_or_parsed or "").strip()

    if not parsed.is_valid or parsed.final_ast is None:
        return {
            "ablation_expr": f"rank({raw_fallback})" if raw_fallback else "rank(close)",
            "placebo_expr": f"ts_delay({raw_fallback}, {lag_days})" if raw_fallback else f"ts_delay(close, {lag_days})",
            "core_signal": raw_fallback,
            "primary_field": "close",
            "fields": [],
            "has_vec": "vec_" in raw_fallback,
            "inlined_expr": raw_fallback,
        }

    inlined_expr = ast.unparse(parsed.final_ast)
    fields = sorted(parsed.referenced_identifiers)
    if known_fields:
        matched = [f for f in fields if f in known_fields]
        target_fields = set(matched) if matched else set(fields)
    else:
        target_fields = set(fields)

    core_node = _extract_core_signal_node(parsed.final_ast, all_ops)
    core_signal = ast.unparse(core_node)

    # Identify primary field inside core_node first
    core_names = [
        n.id for n in ast.walk(core_node)
        if isinstance(n, ast.Name) and n.id not in OperatorRegistry.get_keep_tokens()
    ]
    primary_field = core_names[0] if core_names else (fields[0] if fields else "close")

    # Ablation wraps core_signal in bare rank() unless already ranked
    if core_signal.startswith("rank(") and core_signal.endswith(")"):
        ablation_expr = core_signal
    else:
        ablation_expr = f"rank({core_signal})"

    # Placebo injects ts_delay(..., lag_days) inside the identical outer shell
    if target_fields:
        placebo_node = _replace_with_lagged_placebo(parsed.final_ast, target_fields, lag_days=lag_days)
        placebo_expr = ast.unparse(placebo_node)
    else:
        placebo_expr = f"ts_delay({inlined_expr}, {lag_days})"

    return {
        "ablation_expr": ablation_expr,
        "placebo_expr": placebo_expr,
        "core_signal": core_signal,
        "primary_field": primary_field,
        "fields": fields,
        "has_vec": any(op.startswith("vec_") for op in parsed.all_calls),
        "inlined_expr": inlined_expr,
    }
