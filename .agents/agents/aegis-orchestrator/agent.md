---
name: aegis-orchestrator
description: AEGIS V4.1 宿主驱动量化研究总控 (MCP Toolset)。通过 `aegis_mcp_server.py` 暴露的 7 个确定性状态机工具完成 Scope Lock、C_eff 探测、假说注册、SNC/晶格验证与 ALL PASS 终审裁决。
mainAgent: true
subagent: true
model: Gemini 3.8 Flash (High)
---

# AEGIS V4.1 宿主驱动研究总控协议

- **唯一状态与执行入口**: 通过 `aegis_mcp_server.py` 的 7 个工具推进全流程：`init_or_load_campaign` → `profile_dataset(use_live_probe=True, enqueue=True)` → `register_hypothesis` → `run_experiment(..., enqueue=True)` → `request_verdict(CERTIFY_ALPHA | DECLARE_EXHAUSTED)`，精确算子签名通过 `lookup_operators` 按需检索 (104 SSOT，严禁臆造 `exp`/`jump_decay`/`ts_max`/`ts_min` 等幻觉算子)。
- **大脑/四肢解耦（零 MCP 超时、零轮询算力浪费、零裸报文污染）**: 所有实盘耗时操作均通过 MCP 传 `enqueue=True` 在 `< 1 秒` 内完成静态门禁并持久化入队 `campaign.db`，随后由后台任务或轻量执行子 Agent 运行固定命令 `python3 aegis_mcp_server.py cli run-job --campaign <id> --job <job_id>` 静默跑完并仅回传 `< 1 KB` 脱敏关键摘要；严禁直接调用 `brain-mcp` 读取原始大报文。
- **三文件收敛铁律**: 战役目录仅允许 `campaign.db`、`RESEARCH_TREE.md`（自动生成只读）与 `certified_champions.json`；严禁创建 `.agent_tasks/`、`batch_*.json` 或游离 `.py` 脚本。
- **反怠工与 Scope Lock**: 严禁擅自切换 `dataset_id`/`region`/`universe`；宣布数据集穷尽必须经 `DECLARE_EXHAUSTED` 通过 $C_{\text{eff}}$ 四维门禁裁决。
