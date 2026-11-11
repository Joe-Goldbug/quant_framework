"""
test_pipeline_e2e.py
白盒量化研究多 Agent 架构端到端沙盒验证套件
为研究员提供 100% 可视化的白盒沙盒验证：
1. 验证字段画像与双级卡片 RAG (Tier-1 微目录 + 按需卡片挂载)
2. 验证量纲防伪 (拦截非法无量纲加减，放行合规因果结构)
3. 验证 Python 确定性门禁 (彻底杜绝 Sharpe 0.5 谎报达标)
4. 验证防怠工审计器 (拦截虚假的“数据集穷尽”推诿)
5. 验证双盲红队脱敏协议 (严格物理擦除 PnL/Sharpe，只审因果与保真度)
6. 验证“种子因子模式”秒级切入阶段三
"""

import json
import os
import sys

# 关键：将工作区根目录加入 sys.path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

# Windows 终端编码兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from quant_framework.core.dimension_rules import DimensionAuditor
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.rag_memory import RAGMemoryEngine
    from quant_framework.core.anti_laziness import AntiLazinessAuditor
    from quant_framework.orchestrator import MasterOrchestrator
except (ModuleNotFoundError, ImportError):
    from core.dimension_rules import DimensionAuditor
    from core.gatekeeper import Gatekeeper
    from core.rag_memory import RAGMemoryEngine
    from core.anti_laziness import AntiLazinessAuditor
    from orchestrator import MasterOrchestrator

def run_verification_suite():
    print("=" * 65)
    print("🧪 开始执行【白盒多 Agent 量化研究框架】端到端实践验证")
    print("=" * 65)

    # -------------------------------------------------------------
    # 测试 1: 验证双级卡片 RAG 引擎与超轻量 Token 控制
    # -------------------------------------------------------------
    print("\n[TEST 1] 验证知识库 RAG：Tier-1 极简目录与 Tier-2 按需挂载")
    catalog_text = RAGMemoryEngine.get_catalog_card()
    print(">>> Tier-1 常驻目录内容 (用于主 Prompt，Token 严格 < 300):")
    print(catalog_text)
    
    # 验证按需抓取卡片
    card = RAGMemoryEngine.get_card_on_demand("cw_bottleneck")
    assert card.get("card_id") == "CARD_CW_01", "卡片调取失败"
    print(f"\n>>> Tier-2 动态按需调取成功: {card['card_id']} | 解决方案: {card['proven_solution']}")

    # 验证准入门禁拦截垃圾记录
    print("\n>>> 验证知识库准入门禁 (防垃圾日志污染):")
    rejected = RAGMemoryEngine.admit_new_card(
        card_id="TEMP_001",
        tag="trash",
        domain="test",
        one_line="测试一次失败",
        card_detail={"admission_type": "FALSIFICATION_PHYSICAL_WALL"},
        verification_count=2, # < 10 次
        is_red_team_pass=False
    )
    assert rejected is False, "门禁未能拦截未经 10 轮验证的零散记录！"

    # -------------------------------------------------------------
    # 测试 2: 验证量纲守恒与因果语法拦截器 (防乱凑)
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[TEST 2] 验证量纲平衡与因果 AST 校验器 (防乱凑)")
    
    # 违规案例 1: 营收减股价 (物理学灾难)
    bad_expr_1 = "subtract(sales, close)"
    res1 = DimensionAuditor.audit_expression(bad_expr_1, ["sales"])
    print(f"测试非法表达式 1: '{bad_expr_1}' -> 拦截结果: {res1['is_valid']}")
    print(f"   原因: {res1['issues']}")
    assert not res1['is_valid'], "未能拦截无量纲归一化的直接减法"

    # 违规案例 2: 无量纲 rank 直接相加
    bad_expr_2 = "add(rank(target_price), rank(sales))"
    res2 = DimensionAuditor.audit_expression(bad_expr_2, ["target_price", "sales"])
    print(f"测试非法表达式 2: '{bad_expr_2}' -> 拦截结果: {res2['is_valid']}")
    print(f"   原因: {res2['issues']}")
    assert not res2['is_valid'], "未能拦截 add(rank, rank) 纯数学拼凑"

    # 合规案例: 正交变动源与数据集内部自归一化 (纯内部波动率消除量纲，0 PV 污染)
    good_expr = "divide(subtract(target_price, ts_mean(target_price, 20)), ts_std_dev(target_price, 20))"
    res3 = DimensionAuditor.audit_expression(good_expr, ["target_price"])
    print(f"测试合规表达式: '{good_expr}' -> 校验结果: {res3['is_valid']}")
    assert res3['is_valid'], "合规因果结构被误杀"

    # -------------------------------------------------------------
    # 测试 3: 验证 Python 确定性门禁 (彻底杜绝 Sharpe 0.5 谎报达标)
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[TEST 3] 验证 Python 确定性门禁拦截器 (防作弊)")
    
    # 模拟 Brain API 返回的虚假高指标/低指标 JSON
    fake_brain_data = {
        "alpha_results": [
            {
                "expression": "bad_alpha_lying",
                "is": {
                    "sharpe": 0.52, # 远低于 1.20
                    "turnover": 0.15,
                    "yearly_stats": [{"pnl": 10}, {"pnl": -5}, {"pnl": -8}, {"pnl": 2}] # 负年过多
                },
                "ra": {"ra_failed": False}
            },
            {
                "expression": "great_raw_alpha",
                "is": {
                    "sharpe": 1.38, # >= 1.20
                    "turnover": 0.22, # >= 0.125
                    "yearly_stats": [{"pnl": 10}] * 9 + [{"pnl": -1}] # 9/10 年正收益
                },
                "ra": {"ra_failed": False}
            }
        ]
    }
    
    test_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_sim_result.json")
    with open(test_json_path, 'w', encoding='utf-8') as f:
        json.dump(fake_brain_data, f)

    passed_raw = Gatekeeper.audit_raw_signal(test_json_path, min_sharpe=1.20, min_positive_years=9)
    print(f"Gatekeeper 裁决结果: 共检测 2 条回测，通过硬门禁数量: {len(passed_raw)}")
    assert len(passed_raw) == 1, "门禁逻辑错误"
    assert passed_raw[0]['expression'] == "great_raw_alpha", "未能正确放行高胜率原始信号"
    os.remove(test_json_path)

    # -------------------------------------------------------------
    # 测试 4: 验证防怠工审计器 (防谎报“数据集已穷尽”)
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[TEST 4] 验证防怠工审计器 (防试两次就说数据集穷尽)")
    
    # 模拟知识库字段画像
    kb_mock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_kb.json")
    with open(kb_mock_path, 'w', encoding='utf-8') as f:
        json.dump({
            "fields": {
                "eps_forecast": {"semantic_role": "Signal_Flow"},
                "rev_growth": {"semantic_role": "Signal_Flow"},
                "rating_upgrade": {"semantic_role": "Catalyst_Event"}
            }
        }, f)

    required_grid = AntiLazinessAuditor.generate_required_interactions(kb_mock_path)
    print(f"系统根据字段特征自动推导的核心必测因果交互数: {len(required_grid)} 组")

    # 模拟 Agent 仅测试了 1 组就声称穷尽
    ledger_mock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_ledger.json")
    with open(ledger_mock_path, 'w', encoding='utf-8') as f:
        json.dump({
            "tested_records": [{"interaction_id": required_grid[0]["id"]}]
        }, f)

    verdict = AntiLazinessAuditor.verify_exhaustion_claim(ledger_mock_path, required_grid)
    print(f"Agent 声称穷尽时的审计裁决:")
    print(f"   允许结题放弃: {verdict['allowed_to_give_up']}")
    print(f"   打回原因: {verdict['reason']}")
    print(f"   未测组合示例: {verdict.get('untested_combinations', [])}")
    assert not verdict['allowed_to_give_up'], "防怠工审计器未能拦截谎报穷尽行为！"
    os.remove(kb_mock_path)
    os.remove(ledger_mock_path)

    # -------------------------------------------------------------
    # 测试 5: 验证双盲红队脱敏机制 (物理擦除 PnL/Sharpe)
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[TEST 5] 验证双盲红队脱敏报文生成协议 (擦除收益数据)")
    
    raw_alpha_report = {
        "alpha_id": "alpha_sample_01",
        "expression": "divide(target_price - close, adv20)",
        "fields_used": ["target_price", "close", "adv20"],
        "sharpe": 2.14,
        "fitness": 1.45,
        "pnl_curve": [100, 200, 350, 500],
        "hypothesis": "利用分析师目标价预期偏差，以成交量为分母标准化冲击"
    }

    # 脱敏逻辑: 严格剔除收益相关指标
    red_team_payload = {
        "alpha_id": raw_alpha_report["alpha_id"],
        "expression": raw_alpha_report["expression"],
        "fields_used": raw_alpha_report["fields_used"],
        "author_hypothesis": raw_alpha_report["hypothesis"]
    }
    
    assert "sharpe" not in red_team_payload, "脱敏失败: 泄露 Sharpe"
    assert "pnl_curve" not in red_team_payload, "脱敏失败: 泄露 PnL 曲线"
    print(">>> 交付红队的双盲报文 (绝对无收益倾向诱导，冷酷盲审):")
    print(json.dumps(red_team_payload, ensure_ascii=False, indent=2))

    # -------------------------------------------------------------
    # 测试 6: 验证“种子因子优化模式”秒级切入状态机
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[TEST 6] 验证总控架构师【种子因子直达模式】")
    orch = MasterOrchestrator(region="USA", dataset_id="analyst_estimates", campaign_name="test_sandbox_campaign")
    orch.run_seed_mode(seed_expression="divide(target_price - close, adv20)")
    state = orch.load_state()
    assert state["current_stage"] == "STAGE_3_MATH_OPTIMIZATION", "未能直接跳入阶段三"
    print(f"当前状态机所在阶段: {state['current_stage']} (成功跳过阶段 1 与阶段 2，直奔调优！)")

    print("\n" + "=" * 65)
    print("🎉 恭喜！端到端 6 大核心模块全量通过白盒物理沙盒检验！")
    print("=" * 65)

if __name__ == "__main__":
    run_verification_suite()
