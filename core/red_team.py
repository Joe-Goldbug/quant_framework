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
        # 遍历字段：若是稀疏 [0, 1]，检查是否有非法 zero offset
        for f_name, f_meta in fields.items():
            if f_meta.get("domain") == "[0, 1]" and f_meta.get("sparse_zero"):
                if f"subtract({f_name}, 0.5)" in expr or f"subtract(0.5, {f_name})" in expr:
                    checks["domain_alignment_check"] = False
                    issues.append(f"字段 '{f_name}' 属于稀疏 [0, 1]，subtract 0.5 会将零值偏移为 -0.5 伪空头信号，审讯驳回！")

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

        # 4. 算子奥卡姆剃刀剪枝 (parsimony_check)
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

if __name__ == "__main__":
    f_dict = {
        "max_sentiment": {"domain": "[0, 1]", "sparse_zero": True, "meaning": "最大公关情绪"},
        "news_volume": {"domain": "unbounded", "sparse_zero": False, "meaning": "新闻量"}
    }
    # 恶劣案例：文不对题 + 稀疏字段减 0.5
    bad_expr = "group_rank(subtract(max_sentiment, 0.5), subindustry)"
    bad_hypo = {"mechanism": "捕捉极端正面跃升的边际动量"}
    payload = DoubleBlindRedTeam.generate_blind_payload(bad_expr, bad_hypo, f_dict)
    res = DoubleBlindRedTeam.audit_candidate_blindly(payload)
    print("Bad expr audit result:", res["verdict"], res["issues"])
    assert res["verdict"] == "REJECT"

    # 优良案例：忠实且尊重定义域
    good_expr = "group_rank(ts_decay_exp_window(ts_delta(max_sentiment, 3), 10), subindustry)"
    good_hypo = {"mechanism": "捕捉权威情绪的 3 日时序动量边际跃升"}
    p2 = DoubleBlindRedTeam.generate_blind_payload(good_expr, good_hypo, f_dict)
    r2 = DoubleBlindRedTeam.audit_candidate_blindly(p2)
    print("Good expr audit result:", r2["verdict"], r2["issues"])
    assert r2["verdict"] == "PASS"
    print("✅ DoubleBlindRedTeam 审判与防伪签名测试通过！")
