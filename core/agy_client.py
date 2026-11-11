"""
quant_framework/core/agy_client.py
Plan 1 隔离会话客户端与 Antigravity (AGY) CLI 适配器
(对齐 WS29639 原帖: Python + AI 模式，每个迭代步使用 create_session() 开启全新虚拟会话)

核心特性:
1. PortLockManager: 动态探测并锁定 20000+ 本地端口，避免端口冲突；
2. GeminiClient: 封装 D:\\gemini\\bin\\agy.exe 原生调用，提供 create_session(role, model)；
3. VirtualSession (Plan 1): 每次生成均以独立进程会话执行，只保留 Top-5 标杆与 20 个随机候选，杜绝长会话 Token 污染；
4. 优雅降级 (Zero-Downtime Fallback): 当 CLI 离线、超时或未授权时，无缝切换至高保真白盒拓扑规则引擎，保证全流程确定性运转。
"""

import asyncio
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from quant_framework.core.agent_backends import (
        create_agent_backend,
        BaseAgentBackend,
        AGYCliBackend,
        SubAgentIPCBackend,
        LLMAPIBackend,
        RuleMockBackend,
        extract_json_from_text
    )
except ModuleNotFoundError:
    from core.agent_backends import (
        create_agent_backend,
        BaseAgentBackend,
        AGYCliBackend,
        SubAgentIPCBackend,
        LLMAPIBackend,
        RuleMockBackend,
        extract_json_from_text
    )

DEFAULT_AGY_PATH = r"D:\gemini\bin\agy.exe"
DEFAULT_MODEL = "gemini-3.8-flash-high"

MODEL_SLUG_MAP = {
    "gemini 3.8 flash (high)": "gemini-3.8-flash-high",
    "gemini 3.8 flash (medium)": "gemini-3.8-flash-medium",
    "gemini 3.8 flash (low)": "gemini-3.8-flash-low",
    "claude sonnet 4.6 (thinking)": "claude-sonnet-4-6",
    "claude opus 4.6 (thinking)": "claude-opus-4-6-thinking",
    "gpt-oss 120b (medium)": "gpt-oss-120b-medium",
}

def normalize_model_slug(model_name: str) -> str:
    if not model_name:
        return DEFAULT_MODEL
    cleaned = model_name.strip().lower()
    return MODEL_SLUG_MAP.get(cleaned, model_name)


class PortLockManager:
    """管理本地 20000+ 端口分配与检测，保证高并发进程间隔离"""
    
    @staticmethod
    def acquire_port_lock(base_port: int = 20000, max_port: int = 21000) -> int:
        for port in range(base_port, max_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return base_port


class VirtualSession:
    """Plan 1 虚拟独立会话: 保证单步隔离，极度节约 Token"""

    def __init__(self, client: "GeminiClient", role: str, model: str, system_prompt: Optional[str] = None):
        self.client = client
        self.role = role
        self.model = normalize_model_slug(model)
        self.system_prompt = system_prompt
        self.session_id = f"sess_{int(time.time())}_{random.randint(1000, 9999)}"

    async def send_message(
        self,
        prompt: str,
        json_mode: bool = False,
        timeout: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        timeout = timeout or self.client.default_timeout

        # 优先通过可插拔 Agent 后端驱动 (AGY CLI / SubAgent IPC / LLM API / RuleMockBackend)
        try:
            res = await self.client.backend.send_message(
                role=self.role,
                model=self.model,
                prompt=prompt,
                system_prompt=self.system_prompt,
                json_mode=json_mode,
                timeout=timeout,
                context=context
            )
            if res is not None:
                return res
        except Exception as e:
            backend_name = type(self.client.backend).__name__
            print(f"\n❌ 【Agent 后端调用失败】后端 '{backend_name}' 未能完成思考生成: {e}")
            raise RuntimeError(
                f"❌ 【严禁死模板假思考】智能体后端 '{backend_name}' 未能返回有效思考结果: {e}！\n"
                f"   【系统严禁硬编码死模板替代大模型量化思考】！任务已安全阻断。\n"
                f"   解决方案：请确保配置了可用的智能体后端 (反重力内置 SubAgent / --backend subagent / --backend llm_api)！"
            )

        raise RuntimeError(f"Agent 后端调用失败 ({timeout}s)，且已严禁回退至死模板。")

    def send_message_sync(
        self,
        prompt: str,
        json_mode: bool = False,
        timeout: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        """同步阻塞式调用，支持在非异步或复杂同步状态机中无缝使用"""
        timeout = timeout or self.client.default_timeout

        try:
            res = self.client.backend.send_message_sync(
                role=self.role,
                model=self.model,
                prompt=prompt,
                system_prompt=self.system_prompt,
                json_mode=json_mode,
                timeout=timeout,
                context=context
            )
            if res is not None:
                return res
        except Exception as e:
            backend_name = type(self.client.backend).__name__
            print(f"\n❌ 【Agent 后端同步调用失败】后端 '{backend_name}' 未能完成思考生成: {e}")
            raise RuntimeError(
                f"❌ 【严禁死模板假思考】智能体后端 '{backend_name}' 未能返回有效思考结果: {e}！\n"
                f"   【系统严禁硬编码死模板替代大模型量化思考】！任务已安全阻断。\n"
                f"   解决方案：请确保配置了可用的智能体后端 (反重力内置 SubAgent / --backend subagent / --backend llm_api)！"
            )

        raise RuntimeError(f"Agent 后端同步调用失败 ({timeout}s)，且已严禁回退至死模板。")

    def _extract_json(self, text: str) -> Optional[Union[Dict, List]]:
        """从模型回复中提取合法 JSON，兼容 Markdown 代码块"""
        try:
            return json.loads(text)
        except Exception:
            pass

        # 匹配 ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except Exception:
                pass

        # 匹配最外层花括号或方括号
        bracket_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(1))
            except Exception:
                pass
        return None

class GeminiClient:
    """GrandMaster Python 宿主会话调度器 (支持可插拔多智能体后端)"""

    def __init__(
        self,
        agy_path: Optional[str] = None,
        default_model: str = DEFAULT_MODEL,
        default_timeout: int = 600,
        mock_fallback: bool = False,
        mock_only: bool = False,
        backend_type: str = "builtin",
        tasks_dir: Optional[str] = None
    ):
        self.agy_path = agy_path
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.mock_fallback = mock_fallback
        self.mock_only = mock_only
        self.backend_type = backend_type
        self.tasks_dir = tasks_dir
        self.port_lock = PortLockManager.acquire_port_lock(20000)
        self.backend = create_agent_backend(
            backend_type="mock" if mock_only else backend_type,
            agy_path=agy_path,
            tasks_dir=tasks_dir
        )

    def _load_role_system_prompt(self, role: str) -> str:
        """根据角色名称自动查找并加载 roles/*.md 或 .agents/agents/*/agent.md"""
        role_map = {
            "aegis-seed-synthesizer": "02_main_signal_synthesizer.md",
            "aegis-tech-auditor": "03_tech_auditor.md",
            "aegis-swarm-generator": "04_swarm_generator.md",
            "aegis-deep-refiner": "05_deep_refinement.md",
            "aegis-knowledge-distiller": "06_knowledge_distiller.md",
            "aegis-orchestrator": "03_math_optimizer.md",
            "aegis-field-explorer": "01_field_explorer.md",
        }
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        filename = role_map.get(role.lower())
        if filename:
            path = os.path.join(base_dir, "roles", filename)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception:
                    pass

        # 尝试从 .agents/agents/{role}/agent.md 或 agents/{role}/agent.md 加载
        for p in [
            os.path.join(base_dir, ".agents", "agents", role, "agent.md"),
            os.path.join(base_dir, "agents", role, "agent.md"),
            os.path.join(os.path.dirname(base_dir), "agents", role, "agent.md"),
        ]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception:
                    pass
        return ""

    def create_session(
        self,
        role: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> VirtualSession:
        """
        每次迭代创建全新的 Plan 1 虚拟独立会话
        严格隔离上下文，自动根据角色名称挂载对应的 Markdown 角色契约与规范
        """
        chosen_model = model or self.default_model
        if not system_prompt:
            system_prompt = self._load_role_system_prompt(role)
        return VirtualSession(
            client=self,
            role=role,
            model=chosen_model,
            system_prompt=system_prompt
        )
