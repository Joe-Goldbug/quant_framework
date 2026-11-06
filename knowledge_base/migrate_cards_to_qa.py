"""
knowledge_base/migrate_cards_to_qa.py
将现存静态知识卡片及 e756njNE -> LLM5zxla 实战突破轨迹
全面重构提炼为【痛点病灶 & 因果决策型 QA (问答)】并写入 LanceDB
"""

import json
import os
import sys
from typing import Dict, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from knowledge_base.lancedb_manager import LanceDBQAManager


def convert_card_to_qa(card_data: dict, filename: str) -> dict:
    """
    将旧版静态卡片转换为通用因果 QA (非死板模板，注重机理与权衡)
    """
    card_id = card_data.get("card_id") or filename.replace(".json", "")
    tag = card_data.get("tag", "general")
    title = card_data.get("title") or card_data.get("issue") or card_id

    # 1. CARD_NONPARAMETRIC_TS_QUANTILE_01
    if "QUANTILE" in card_id or "ts_quantile" in str(card_data):
        q = "当使用文本情绪、事件计数等低频另类数据时，为什么时序 Z-Score (ts_zscore) 容易在历史早期 (如 2015/2018) 出现严重失血？有哪些替代算子及其权衡取舍？"
        a = (
            "【微观根因】：\n"
            "另类数据通常含有大量零值或阶段性讨论断流。冷门标的的 250 天滚动标准差 σ_250 -> 0。此时 ts_zscore 存在分母趋零爆炸风险，偶发脉冲会被放大为 +50 ~ +100 的极端异常值，严重扭曲空头排序。\n\n"
            "【权衡决策树】：\n"
            "1. ts_zscore：仅适用于数据稠密连续、方差平稳的高频或宏观特征。遇到稀疏零膨胀数据严禁裸用。\n"
            "2. ts_av_diff：消除均值偏置且不除以方差，但缺乏跨时间方差稳态，截面离散度随时间大幅漂移 (实测夏普往往仅 0.4~0.6)。\n"
            "3. ts_rank：严格有界于 [0, 1] 免疫分母爆炸，但均匀阶梯分布抹平了极端情绪的肥尾凸性 (实测夏普约 1.26)。\n"
            "4. ts_quantile：先通过经验分位数有界于 [0, 1] 杜绝除零发散，再通过逆正态累积分布 Φ^(-1) 映射保留高斯尾部敏感度。适合既需要尾部非线性惩罚、又必须杜绝零方差爆炸的场景 (实战夏普可达 1.63+)。\n\n"
            "【反模式】：\n"
            "切勿在未做零方差检查时直接对另类数据套用 ts_zscore；当数据含大量 0 时，优先评估 ts_quantile。"
        )
        symptom = "历史早期 (如 2015/2018) 夏普断崖式下跌，底层含大量零值，ts_zscore 分母爆炸"
        tags = "ts_quantile,ts_zscore,zero_variance,sparse_data,sentiment"

    # 2. CARD_CW_01
    elif "CW_01" in card_id or "集中度" in str(card_data):
        q = "当 Alpha 回测出现集中度指标违规 (CW > 0.10) 导致平台硬拦截时，为什么普通截断 (winsorize/truncate) 会失效？底层机理与有效解法是什么？"
        a = (
            "【微观根因】：\n"
            "集中度超标通常源于极少数标的的极端重定价。简单的截断 (truncate) 或仿射标准化 (z-score) 无法改变标的间的序关系与头部极值权重聚合，因此无法从根本上消除集中度违规。\n\n"
            "【权衡决策树】：\n"
            "1. 方案 A (凹函数非线性压缩)：使用 s_log_1p(x) 或 sign(x)*sqrt(abs(x))。保持单调性的同时拉平头部尖峰，压降 CW。\n"
            "2. 方案 B (截面秩变换)：使用 rank(x) 或 group_rank(x, subindustry)。将数值强制转换为均匀离散分布，彻底根除 CW 异常。\n\n"
            "【反模式】：\n"
            "严禁在 settings 中试图通过不断调小 truncation (如 0.02) 来试图解决 CW，实证证明完全无效。"
        )
        symptom = "CW > 0.10 集中度超标硬拦截，使用截断算子无法消除"
        tags = "CW,concentration,s_log_1p,rank,truncation"

    # 3. CARD_FITNESS_FLOOR_TURNOVER_01
    elif "FITNESS_FLOOR" in card_id or "12.5%" in str(card_data):
        q = "当 Alpha 换手率偏低 (如 4%~9%) 且夏普/Fitness 停滞时，如何利用平台的 12.5% Turnover 免罚底线来释放 Alpha 潜力？"
        a = (
            "【微观根因】：\n"
            "平台的 Fitness 官方公式为: Fitness = Sharpe * sqrt(|Returns| / max(Turnover, 0.125))。\n"
            "当 Turnover <= 0.125 时，分母固定为 0.125，分母对换手率的偏导数恒为 0 (∂Fitness / ∂Turnover = 0)。此时换手率从 4% 上升到 12.5% 完全零惩罚！\n\n"
            "【权衡决策树】：\n"
            "1. 若换手 < 10.5%：严禁盲目调大 decay 或加大 ts_backfill 窗口。这会过度平滑信号，压低回报率与夏普。\n"
            "2. 释放换手动作：将过长的 ts_backfill (如 60) 缩短为 30 或 20，微调 decay 让换手精准落入 10.5%~12.5% 黄金区间，以换取更高的信息响应速度与年化收益。\n\n"
            "【反模式】：\n"
            "换手率严守 12.5% 硬顶，一旦突破 12.5%，分母惩罚将立即线性放大。"
        )
        symptom = "Turnover 仅 4%~9%，Fitness 停滞，研究员过度平滑导致收益受阻"
        tags = "fitness_floor,turnover,decay,backfill,sharpe"

    # 4. CARD_NEUTRALIZATION_OCCAM_01
    elif "NEUTRALIZATION" in card_id or "中性化" in str(card_data):
        q = "在选择中性化方法时，如何根据数据特性权衡【单层外壳 (group_rank)】与【复合残差中性化 (group_neutralize)】？"
        a = (
            "【微观根因】：\n"
            "复合残差中性化在消除风格暴露的同时，会消耗较多算子配额并带来过拟合风险。如果数据自身的横截面行业离散度本就很强，盲目套用残差往往导致有效信号被当作残差剔除。\n\n"
            "【权衡决策树】：\n"
            "1. 方案 A (奥卡姆极简外层)：直接使用 group_rank(x, sector/subindustry)。7~8 个算子即可跑出 1.63+ 高夏普，结构极度鲁棒。\n"
            "2. 方案 B (复合残差中性化)：当因子存在明显的宏观大盘或行业共振挤压 (如 Cluster 警告频繁)，且单层排序无法剔除系统性贝塔时，再启用 group_neutralize。\n\n"
            "【反模式】：\n"
            "严禁机械教条地认为'必须残差中性化'。真实生产中，极简的单外层排序往往具有更优越的样本外稳定性。"
        )
        symptom = "算子超标或过度中性化导致夏普衰减，Cluster 测试警告"
        tags = "neutralization,group_rank,group_neutralize,occam_razor"

    # 5. 通用默认转换
    else:
        q = f"在量化研发中，如何诊断与应对关于 [{title}] 的病灶与权衡？"
        a = f"【核心机理】：\n{card_data.get('one_line', title)}\n\n【决策启示】：\n{json.dumps(card_data.get('dynamic_decision_tree') or card_data, ensure_ascii=False, indent=2)}"
        symptom = card_data.get("symptom", title)
        tags = card_data.get("tag", "quant_rule")

    return {
        "id": f"QA_{card_id.upper()}",
        "question": q,
        "answer": a,
        "symptom": symptom,
        "tags": tags,
        "source_type": "forum",
        "source_id": card_id,
        "heat_score": 88.0
    }


def seed_database():
    mgr = LanceDBQAManager()
    cards_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "cards"))
    
    qa_list = []
    if os.path.exists(cards_dir):
        for fname in os.listdir(cards_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(cards_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    qa_item = convert_card_to_qa(data, fname)
                    qa_list.append(qa_item)
                except Exception as e:
                    print(f"⚠️ 解析卡片失败 {fname}: {e}")

    # 追加 e756njNE -> LLM5zxla 的战役核心实战复盘 QA
    qa_list.append({
        "id": "QA_BATTLE_E756NJNE_LLM5ZXLA_01",
        "question": "当种子 Alpha 遭遇 2023 年高缺失断流 (60% NaN) 与 2015/2018 早期零讨论年份失血双重夹击时，如何从数学上彻底根除？",
        "answer": (
            "【底层数学根因】：\n"
            "1. 2023 年多空颠倒：2023 年数据缺失率超 60%，缺失标的产生 0 值。原表达式 0 > -ratio 导致 600 只无讨论标的全量冲入多头，AI 科技牛股冲入空头引发爆亏。\n"
            "2. 2015/2018 分母爆炸：为解决 2023 引入滚动 ts_zscore(x, 250)，但在早期无发帖标的中 σ_250 -> 0，除零发散产生 +50~100 极值，导致 2015/2018 严重失血。\n\n"
            "【最终突破与权衡方案】：\n"
            "引入有界高斯分位映射算子 ts_quantile(x, 250, 'gaussian')：\n"
            "- 数学机制: Quantile_t = Φ^(-1)(ts_rank(x, 250))。先通过经验分位数有界于 [0, 1] 彻底杜绝除以零发散，再通过标准正态逆分布函数 Φ^(-1) 映射保留极端情绪的非线性肥尾特征。\n"
            "- 实战成效: 冠军 LLM5zxla 斩获 Sharpe 1.63、Fitness 1.18、0 FAIL，2014~2023 连续 10 年 100% 全胜，2023 年贡献 +1.23 夏普与 $457k 纯利。"
        ),
        "symptom": "2023 年高缺失断流导致多空倒挂，早期稀疏年份 σ->0 分母爆炸失血",
        "tags": "ts_quantile,zero_variance,2023_crisis,e756njNE,LLM5zxla",
        "source_type": "battle_post_mortem",
        "source_id": "e756njNE_LLM5zxla",
        "heat_score": 99.0
    })

    inserted = mgr.add_qa_records(qa_list, table_name=mgr.FORUM_TABLE)
    print(f"🎉 成功向 LanceDB 表 [{mgr.FORUM_TABLE}] 写入 {inserted} 条原子化 QA 决策经验！")
    print(f"📊 当前数据库状态: {mgr.get_stats()}")


if __name__ == "__main__":
    seed_database()
