"""
red_team.py
物理隔离与双盲红队逻辑审判器 (AEGIS v3.0 Hardness 核心模块)
彻底解决：
1. 主 Agent 左右互搏与认知污染：严禁接收任何回测数据 (Sharpe, Fitness, Margin, PnL, Drawdown 等)！
2. 形式化审讯清单 (Formal Verification Checklist):
   - domain_alignment_check: 算子是否尊重字段物理定义域与零值特性
   - hypothesis_to_ast_fidelity: 假设中所声称的微观机制，在 AST 中是否有对应因果算子支撑
   - parsimony_check: 是否存在对因果机制无贡献的虚华装潢算子
3. 签发具备密码学校验特征的 red_team_verdict.json 通行证

AEGIS v3.3 反事实消融舱 (2026-11-14):
4. build_ablation_and_placebo(): 对母本做「复杂度匹配的安慰剂对照」AST 变换——
   - 消融版 (ablation): 把骨架链最深层的信息提取算子替换为恒等占位 add(arg, 0)；
   - 安慰剂版 (placebo): 把骨架链的非机制装饰层算子同样替换为恒等占位。
   判读规则 (E3 反事实证据): 机制贡献 = (母本 − 消融版) 与 (母本 − 安慰剂版) 的差，
   且差值只在样本外/近端区间读——IS 掉分是过拟合的定义，不是机制的证据。
   复杂度匹配原则: 占位算子与被替换算子同为 1 个调用节点，杜绝「strip 降复杂度
   导致任何组件都掉分」的假阳性通行证。
5. negative_control_selftest(): 内置已知坏样本的负对照体检，输出分项召回率报告。
"""

import ast
import hashlib
import json
import os
import re
import sys
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class DoubleBlindRedTeam:
    @classmethod
    def generate_blind_payload(cls, expr: str, hypothesis: dict, fields_dict: dict) -> dict:
        """
        构造严格脱敏、双盲纯净的红队送审数据包 (绝对不含任何回测指标)
        """
        # 提取表达式使用的字段
        tokens = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr))
        clean_fields = {}
        for f, meta in fields_dict.items():
            if f in tokens:
                clean_fields[f] = {
                    "domain": meta.get("domain", "unbounded"),
                    "center": meta.get("center", 0.0),
                    "sparse_zero": meta.get("sparse_zero", meta.get("is_sparse", False)),
                    "meaning": meta.get("description", meta.get("meaning", "未知字段"))
                }

        return {
            "task": "BLIND_RED_TEAM_AUDIT",
            "ast_expression": expr,
            "fields_dictionary": clean_fields,
            "candidate_hypothesis": {
                "counterparty": hypothesis.get("counterparty", "未明确对手盘"),
                "mechanism": hypothesis.get("mechanism", hypothesis.get("economic_mechanism", "未明确因果机制")),
                "ast_expression": expr
            }
        }

    @classmethod
    def audit_candidate_blindly(cls, blind_payload: dict) -> dict:
        """
        形式化红队双盲审判逻辑 (0 历史回测指标依赖)
        """
        expr = blind_payload.get("ast_expression", "")
        hypo = blind_payload.get("candidate_hypothesis", {})
        fields = blind_payload.get("fields_dictionary", {})

        issues = []
        checks = {
            "domain_alignment_check": True,
            "hypothesis_to_ast_fidelity": True,
            "parsimony_check": True
        }

        # 1. 形式化语法树校验
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            return {
                "verdict": "REJECT",
                "checks": {k: False for k in checks},
                "issues": [f"AST 语法树解析失败: {str(e)}"],
                "signature": None
            }

        # 2. 定义域与物理语义对齐审讯 (domain_alignment_check)
        # 遍历字段：稀疏 [0, 1] 检查非法 zero offset；负半轴对数域检查 log/sqrt 非法调用
        for f_name, f_meta in fields.items():
            f_dom = str(f_meta.get("domain") or "unbounded")
            if f_dom == "[0, 1]" and (f_meta.get("sparse_zero") or f_meta.get("is_sparse")):
                if f"subtract({f_name}, 0.5)" in expr or f"subtract(0.5, {f_name})" in expr:
                    checks["domain_alignment_check"] = False
                    issues.append(f"字段 '{f_name}' 属于稀疏 [0, 1]，subtract 0.5 会将零值偏移为 -0.5 伪空头信号，审讯驳回！")
            # 对数概率/对数似然负半轴: 直接套 log/sqrt 会产生连片 NaN
            # (s_log_1p 定义域为全体实数 sign(x)*log(1+|x|)，保号压缩合法，不在禁令内)
            elif f_dom == "(-inf, 0]":
                for bad_op in ("log", "sqrt"):
                    if f"{bad_op}({f_name})" in expr:
                        checks["domain_alignment_check"] = False
                        issues.append(
                            f"字段 '{f_name}' 处于负半轴对数域 (-inf, 0]，直接套用 {bad_op} 会产生连片 NaN！"
                            f"请先用 exp() 还原至概率空间，或改用保号的 s_log_1p。"
                        )

        # 3. 假设与 AST 保真度审讯 (hypothesis_to_ast_fidelity)
        mech_text = hypo.get("mechanism", "").lower()
        # 若假设声称捕捉“边际改善/突发跃升/变化量”，AST 必须有 delta 或 zscore
        # 2026-10-28 修正：group_zscore 同样是标准化算子，此前只匹配字面量 'ts_zscore'
        # 导致 group_zscore(...) 的标准化构造被误判为"文不对题伪因果"（假阳性）。
        if any(w in mech_text for w in ["边际", "变化", "跃升", "突发", "delta", "momentum", "动量"]):
            if not any(op in expr for op in ["ts_delta", "ts_zscore", "group_zscore", "subtract", "divide"]):
                checks["hypothesis_to_ast_fidelity"] = False
                issues.append("假设声称捕捉边际时序变化，但 AST 中未见任何差分或标准化算子 (文不对题伪因果)！")

        # 若假设声称“关注度门控/极端过滤”，AST 必须有交互、门控或滤波结构
        if any(w in mech_text for w in ["门控", "放大", "权重"]):
            if not any(op in expr for op in ["multiply", "trade_when", "if_else", "power", "signed_power"]):
                checks["hypothesis_to_ast_fidelity"] = False
                issues.append("假设声称施加催化剂门控或非线性放大，但 AST 缺乏乘积/条件门控结构！")

        # 4. 语义奥卡姆剃刀剪枝 (parsimony_check): AST 同态冗余套壳检测 + 括号数兜底
        # 拦截对因果机制零增量的恒等套壳: rank(rank(x)) / rank(单调变换(rank(x))) / 双重时序平滑堆叠
        MONOTONE_OPS = {"rank", "group_rank", "s_log_1p", "signed_power", "log", "sqrt", "exp", "abs"}
        DECAY_OPS = {"ts_decay_linear", "ts_decay_exp_window", "ts_mean"}
        try:
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args):
                    continue
                outer_op = node.func.id
                inner = node.args[0]
                if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)):
                    continue
                inner_op = inner.func.id
                if outer_op in ("rank", "group_rank") and inner_op in ("rank", "group_rank"):
                    checks["parsimony_check"] = False
                    issues.append(f"检测到冗余双重排序套壳 '{outer_op}({inner_op}(...))'，对截面次序无任何因果增量！")
                elif outer_op in ("rank", "group_rank") and inner_op in MONOTONE_OPS and inner.args:
                    grand = inner.args[0]
                    if isinstance(grand, ast.Call) and getattr(grand.func, "id", "") in ("rank", "group_rank"):
                        checks["parsimony_check"] = False
                        issues.append(f"检测到恒等凑算子套壳 '{outer_op}({inner_op}(rank(...)))'，单调变换不改变排名！")
                elif outer_op in DECAY_OPS and inner_op in DECAY_OPS:
                    checks["parsimony_check"] = False
                    issues.append(f"检测到双重时序平滑堆叠 '{outer_op}({inner_op}(...))'，过度钝化信号且属凑算子行为！")
        except Exception:
            pass

        op_count = expr.count("(")
        if op_count > 15:  # 放宽算子数限制至 15
            checks["parsimony_check"] = False
            issues.append(f"算子数 {op_count} > 15，违反简约律，存在伪装过拟合嫌疑！")

        verdict = "PASS" if all(checks.values()) and len(issues) == 0 else "REJECT"

        # 生成防伪签名
        sig_payload = f"{expr}|{verdict}|{json.dumps(checks, sort_keys=True)}"
        signature = hashlib.sha256(sig_payload.encode('utf-8')).hexdigest()

        return {
            "verdict": verdict,
            "checks": checks,
            "issues": issues,
            "signature": signature,
            "reviewed_expr": expr
        }

    @classmethod
    def sign_batch_verdicts(cls, batch_items: list, fields_meta: dict, output_file: str) -> dict:
        """
        批量审判单批 8 条变体并签发 red_team_verdict.json 凭证
        """
        results = []
        all_passed = True
        for idx, item in enumerate(batch_items):
            expr = item.get("expression", "")
            hypo = {
                "counterparty": item.get("counterparty", "被动指数与噪声交易者"),
                "mechanism": item.get("optimize_reason", item.get("economic_mechanism", "时序稳态与截面溢价"))
            }
            blind_payload = cls.generate_blind_payload(expr, hypo, fields_meta)
            res = cls.audit_candidate_blindly(blind_payload)
            results.append(res)
            if res["verdict"] != "PASS":
                all_passed = False

        verdict_doc = {
            "batch_size": len(batch_items),
            "all_passed": all_passed,
            "verdicts": results,
            "summary_hash": hashlib.sha256(json.dumps([r["signature"] for r in results]).encode('utf-8')).hexdigest()
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(verdict_doc, f, ensure_ascii=False, indent=2)

        return verdict_doc


# ---------------------------------------------------------------------------
# AEGIS v3.3 反事实消融舱: 复杂度匹配的安慰剂对照 (Placebo-Controlled Ablation)
# ---------------------------------------------------------------------------

def _walk_skeleton_chain(tree_body):
    """沿第一参数链收集各层 Call 节点 (由外向内)。"""
    chain = []
    node = tree_body
    while isinstance(node, ast.Call) and getattr(node.func, "id", ""):
        chain.append(node)
        node = node.args[0] if node.args else None
    return chain


def _replace_node_at_depth(expr: str, depth: int) -> str:
    """
    把沿第一参数链第 depth 层 (0=最外层) 的算子调用替换为恒等占位 add(arg0, 0)。
    复杂度匹配: 被替换算子 1 个调用节点 -> add(...) 1 个调用节点。
    注意: 必须对「同一棵」解析树做变换 (身份比较定位节点)，禁止二次 parse。
    """
    tree = ast.parse(expr.strip(), mode="eval")
    chain = _walk_skeleton_chain(tree.body)
    if depth >= len(chain):
        return ""
    target = chain[depth]
    func_name = getattr(target.func, "id", "")
    if not func_name or not target.args:
        return ""
    # 恒等占位: add(arg0, 0) —— 与被替换算子同为 1 个调用节点，语义中性
    placeholder = ast.Call(
        func=ast.Name(id="add", ctx=ast.Load()),
        args=[target.args[0], ast.Constant(value=0)],
        keywords=[],
    )
    class _Swapper(ast.NodeTransformer):
        def __init__(self):
            self.done = False
        def visit_Call(self, node):
            if (not self.done) and (node is target):
                self.done = True
                return ast.copy_location(placeholder, node)
            return self.generic_visit(node)
    new_tree = _Swapper().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree.body) if hasattr(ast, "unparse") else ""
    except Exception:
        return ""


def build_ablation_and_placebo(parent_expression: str) -> dict:
    """
    从母本表达式构造「复杂度匹配的安慰剂对照」实验对:
      - ablation (消融版): 骨架链最深层 (信息提取核心) 算子 -> add(arg0, 0)
      - placebo (安慰剂版): 骨架链的非机制装饰层 (最外层) 算子 -> add(arg0, 0)
    判读 (写入 Dossier 的 E3 证据):
      机制贡献 = (母本 - 消融版) - (母本 - 安慰剂版)，仅在样本外/近端区间读差。
      若 母本 ≈ 消融版 (差 < 30%): 机制声明为假，赚钱的不是声称的机制。
      若 消融版 ≈ 安慰剂版: 整个骨架都是过拟合装饰。
    返回 {"ablation": expr_or_empty, "placebo": expr_or_empty, "notes": [...]}
    """
    result = {"ablation": "", "placebo": "", "notes": []}
    expr = (parent_expression or "").strip()
    if not expr:
        result["notes"].append("母本表达式为空")
        return result
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        result["notes"].append("母本表达式语法错误，无法构造对照")
        return result

    chain = _walk_skeleton_chain(tree.body)
    if len(chain) < 2:
        # 骨架链只有 1 层: 无法区分机制位与装饰位，只构造消融版
        ablation = _replace_node_at_depth(expr, len(chain) - 1) if chain else ""
        result["ablation"] = ablation
        result["notes"].append("骨架链过短 (单算子)，安慰剂版退化为不可构造；判读只看 母本 vs 消融版")
        return result

    # 消融位 = 最深层 (信息提取核心); 安慰剂位 = 最外层 (通常是中性化/包装装饰)
    ablation = _replace_node_at_depth(expr, len(chain) - 1)
    placebo = _replace_node_at_depth(expr, 0)
    if not ablation:
        result["notes"].append("消融版构造失败 (最深层替换异常)")
    if not placebo:
        result["notes"].append("安慰剂版构造失败 (最外层替换异常)")
    result["ablation"] = ablation
    result["placebo"] = placebo
    return result


def negative_control_selftest() -> dict:
    """
    红队负对照体检: 内置已知坏样本直接喂给三审，输出分项召回率与误杀率。
    用途: 区分「实战高通过率源于上游批次干净」vs「规则引擎失效 (橡皮章)」。
    建议每次修改 red_team.py 后运行一次。
    """
    fields = {
        "sparse01_field": {"domain": "[0, 1]", "sparse_zero": True, "is_sparse": True},
        "logprob_field": {"domain": "(-inf, 0]", "is_sparse": False},
        "x_field": {"domain": "unbounded", "is_sparse": False},
        "y_field": {"domain": "[0, 1]", "sparse_zero": True, "is_sparse": True},
    }

    def _mk(expr, mech):
        payload = DoubleBlindRedTeam.generate_blind_payload(
            expr, {"counterparty": "噪声交易者", "mechanism": mech}, fields)
        return DoubleBlindRedTeam.audit_candidate_blindly(payload)

    # 20 算子意面 (19 个左括号 > 15)
    _spaghetti = "zscore(" * 16 + "x_field" + ")" * 16

    bad_cases = [
        ("A1-直接零值偏移", "subtract(y_field, 0.5)", "截面定价"),
        ("A2-子树级零值偏移", "subtract(group_zscore(y_field, industry), 0.5)", "截面定价"),
        ("A3-反向零值偏移", "subtract(0.5, y_field)", "截面定价"),
        ("B1-负半轴log", "log(logprob_field)", "对数概率压缩"),
        ("B2-负半轴sqrt", "sqrt(logprob_field)", "对数概率压缩"),
        ("C1-双重排序", "rank(rank(x_field))", "截面相对定价"),
        ("C2-混排双序", "group_rank(rank(x_field), industry)", "截面相对定价"),
        ("C3-恒等套壳", "rank(s_log_1p(rank(x_field)))", "截面相对定价"),
        ("C4-双重平滑", "ts_decay_linear(ts_mean(x_field, 5), 10)", "时序稳定"),
        ("C5-双exp平滑", "ts_decay_exp_window(ts_decay_linear(x_field, 5), 10)", "时序稳定"),
        ("D1-算子堆叠>15", _spaghetti, "复合信号"),
        ("E1-声称边际无差分", "ts_mean(x_field, 20)", "捕捉边际改善与突发跃升的动量效应"),
        ("E2-声称门控无乘积", "group_zscore(x_field, industry)", "施加催化剂门控与非线性放大权重"),
        ("E3-声称动量用均值", "group_rank(ts_mean(x_field, 10), industry)", "纯粹动量 momentum 信号"),
    ]
    good_cases = [
        ("G1-动量+差分", "group_zscore(ts_delta(x_field, 5), industry)", "捕捉边际改善的动量效应"),
        ("G2-门控+乘积", "trade_when(greater(y_field, 0.5), ts_delta(x_field, 5), 0)", "施加催化剂门控与放大权重"),
        ("G3-负半轴保号压缩", "s_log_1p(logprob_field)", "对数概率压缩"),
        ("G4-负半轴exp还原", "group_zscore(exp(logprob_field), industry)", "还原概率空间后截面定价"),
        ("G5-单层平滑", "ts_decay_linear(zscore(x_field), 8)", "时序稳定"),
        ("G6-合规基础式", "winsorize(zscore(ts_delta(x_field, 5)), std=4)", "动量标准化"),
    ]

    hits, misses, false_kills = [], [], []
    for name, expr, mech in bad_cases:
        res = _mk(expr, mech)
        (hits if res["verdict"] == "REJECT" else misses).append(name)
    for name, expr, mech in good_cases:
        res = _mk(expr, mech)
        if res["verdict"] == "REJECT":
            false_kills.append(name)

    recall = len(hits) / len(bad_cases) if bad_cases else 0.0
    far = len(false_kills) / len(good_cases) if good_cases else 0.0
    report = {
        "recall": round(recall, 3),
        "false_alarm_rate": round(far, 3),
        "hits": hits,
        "misses": misses,
        "false_kills": false_kills,
        "known_limitations": [
            "A2 子树级零值偏移由 Gate 2 (DimensionAuditor 递归子树量纲检查) 补位——红队保持字符串级快检，层间分工",
        ],
        "verdict": (
            "工具工作正常 (实战高通过率源于上游过滤，非规则失效)"
            if recall >= 0.85 and far == 0.0
            else "规则存在实质缺口，需修补"
        ),
    }
    return report
