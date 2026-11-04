---
name: aegis-orchestrator
description: WorldQuant Brain 架构降权后的总控交互接口。实际总控由纯 Python 状态机 (main.py / run_this.sh) 接管，负责全自动轮询与阶梯早停。
mainAgent: true
subagent: true
model: Gemini 3.8 Flash (High)
---

# 角色 03：数学形态优化器 (已从前置阻断降权为 func2 辅助战术)

> [!NOTE]
> **架构调整公告 (GrandMaster 对齐)**：
> 原帖中回测前仅有轻量级 `Tech Auditor`（字段真实性与 Vector 降维）和本地 2ms AST 纠错。
> 本角色的量纲形态优化战术已内嵌至 `func2`（深水区精炼）中作为算子平替与形态处方使用，不再在回测前进行形式化量纲推导阻断。
