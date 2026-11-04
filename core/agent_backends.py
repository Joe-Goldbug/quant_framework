"""
quant_framework/core/agent_backends.py
多智能体可插拔执行后端适配器 (Pluggable Multi-Agent Execution Backends)

支持四大驱动后端:
1. AGYCliBackend: 原生调用 Antigravity CLI (D:\\gemini\\bin\\agy.exe)
2. SubAgentIPCBackend (🌟 Freebuff / Cursor / 外部宿主平台内置子 Agent 邮箱协议):
   - Python 状态机将任务下发至 .agent_tasks/task_{role}_{id}.json
   - 外部平台内置 Sub-agent 读取任务并写入 .agent_tasks/response_{role}_{id}.json
   - Python 状态机自动捕获响应并继续执行，实现真正的无 CLI 宿主内置子 Agent 协同！
3. LLMAPIBackend: 标准 HTTP API 驱动 (OpenAI / DeepSeek / Claude / Local Ollama 等)
   - 基于 Python 标准库 urllib.request 实现，0 外部 pip 依赖，跨平台 100% 便携
4. RuleMockBackend: 离线白盒拓扑规则引擎 (毫秒级单元测试与保底降级)
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
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

# -------------------------------------------------------------
# 辅助函数: JSON 提取与模型名标准化
# -------------------------------------------------------------
def extract_json_from_text(text: str) -> Optional[Union[Dict, List]]:
    """从模型回复中提取合法 JSON，兼容 Markdown 代码块"""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    bracket_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1))
        except Exception:
            pass
    return None


class BaseAgentBackend(ABC):
    """智能体后端抽象基类"""
    
    @abstractmethod
    async def send_message(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 60,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        pass

    def send_message_sync(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 60,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果处于异步循环中，在新线程中创建独立事件循环执行
                import concurrent.futures
                def _run_in_thread():
                    return asyncio.run(self.send_message(
                        role, model, prompt, system_prompt, json_mode, timeout, context
                    ))
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_run_in_thread)
                    return future.result(timeout=timeout + 10)
            else:
                return loop.run_until_complete(self.send_message(
                    role, model, prompt, system_prompt, json_mode, timeout, context
                ))
        except RuntimeError:
            return asyncio.run(self.send_message(
                role, model, prompt, system_prompt, json_mode, timeout, context
            ))


# -------------------------------------------------------------
# 后端 1: Antigravity CLI 后端 (AGY)
# -------------------------------------------------------------
class AGYCliBackend(BaseAgentBackend):
    def __init__(self, agy_path: str = r"D:\gemini\bin\agy.exe"):
        self.agy_path = agy_path

    async def send_message(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 60,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        if not os.path.exists(self.agy_path):
            raise FileNotFoundError(f"未找到 AGY CLI 可执行文件: {self.agy_path}")

        cmd = [
            self.agy_path,
            "-p", prompt,
            "--agent", role,
            "--model", model,
            "--disable-slash-commands",
            "--dangerously-skip-permissions",
            "--print-timeout", f"{timeout}s"
        ]

        t0 = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
            if proc.returncode == 0 and stdout_data:
                res = stdout_data.decode("utf-8", errors="replace").strip()
                if json_mode:
                    parsed = extract_json_from_text(res)
                    if parsed is not None:
                        return parsed
                return res
            err_msg = stderr_data.decode("utf-8", errors="replace").strip() if stderr_data else "无标准错误"
            raise RuntimeError(f"AGY CLI 退出码 {proc.returncode}: {err_msg}")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            raise TimeoutError(f"AGY CLI 调用超时 ({timeout}s)")


# -------------------------------------------------------------
# 后端 2: AI 工具原生内置智能体驱动 (BuiltinAgentBackend / SubAgentIPCBackend)
# 「断点挂起-恢复 (Yield & Resume)」状态机
# -------------------------------------------------------------
EXIT_CODE_YIELD = 20  # 状态机挂起专用退出码

class BuiltinAgentBackend(BaseAgentBackend):
    """
    AI 工具原生内置智能体驱动 (Built-in Agent Backend)
    采用「断点挂起-恢复 (Yield & Resume)」状态机模式：
    1. 首次到达思考节点时，生成任务卡片 .agent_tasks/task_{role}_{tag}.json；
    2. 若未检测到响应，立即打印任务路径并 sys.exit(20) 挂起，交还控制权给当前 AI 工具；
    3. AI 工具在原生上下文中阅读任务并写入 resp_{role}_{tag}.json；
    4. 再次执行同一命令时，状态机检测到响应已就绪，立即消费结果继续推进回测与门禁；
    彻底终结「同步死锁」与「聊天框长睡眠轮询」，100% 真实调用当前 AI 工具内置大模型算力！
    """
    def __init__(self, tasks_dir: Optional[str] = None, poll_interval: float = 0.5):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.tasks_dir = tasks_dir or os.path.join(base_dir, ".agent_tasks")
        os.makedirs(self.tasks_dir, exist_ok=True)
        self.poll_interval = poll_interval

    async def send_message(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 120,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        context = context or {}
        tag = context.get("task_tag") or f"{context.get('seed_id', 'init')}_step_{context.get('step', 0)}"
        clean_tag = re.sub(r"[^\w\-]", "_", str(tag))
        
        task_id = f"task_{role}_{clean_tag}"
        task_file = os.path.join(self.tasks_dir, f"{task_id}.json")
        resp_file = os.path.join(self.tasks_dir, f"resp_{role}_{clean_tag}.json")

        # 1. 检查响应是否已就绪 (Resume 阶段)
        if os.path.exists(resp_file):
            try:
                with open(resp_file, "r", encoding="utf-8") as rf:
                    raw_content = rf.read().strip()
                if raw_content:
                    parsed_json = extract_json_from_text(raw_content)
                    if parsed_json is not None:
                        try:
                            if os.path.exists(task_file):
                                os.remove(task_file)
                            # 注意：切勿在此处 os.remove(resp_file)，保留响应文件以支持多节点断点重入幂等恢复！
                        except Exception:
                            pass
                        print(f"\n✅ [AI 内置 Agent 响应接收成功] 角色: {role} (消费响应，继续推进状态机！)")
                        return parsed_json if json_mode else raw_content
                    elif not json_mode:
                        try:
                            if os.path.exists(task_file):
                                os.remove(task_file)
                            # 注意：切勿在此处 os.remove(resp_file)，保留响应文件以支持多节点断点重入幂等恢复！
                        except Exception:
                            pass
                        return raw_content
            except Exception as e:
                print(f"⚠️  [BuiltinAgent] 读取已有响应异常: {e}")

        # 2. 响应未就绪，下发任务卡片并断点挂起 (Yield 阶段)
        task_payload = {
            "task_id": task_id,
            "role": role,
            "instruction": f"请当前 AI 工具内置 Agent 扮演角色 [{role}] 完成以下思考与表达式生成任务",
            "system_prompt": system_prompt or "",
            "prompt": prompt,
            "json_mode": json_mode,
            "context": context,
            "status": "WAITING_FOR_BUILTIN_AGENT",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expected_response_file": resp_file
        }

        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_payload, f, ensure_ascii=False, indent=2)

        # 检查是否是在离线单元测试或显式要求内联等待的环境
        if os.environ.get("AEGIS_MOCK_MODE") == "1" or os.environ.get("AEGIS_IPC_INLINE_WAIT") == "1":
            # 单元测试专用: 简易短轮询等待测试桩写入
            t0 = time.time()
            while time.time() - t0 < timeout:
                if os.path.exists(resp_file):
                    try:
                        with open(resp_file, "r", encoding="utf-8") as rf:
                            raw_content = rf.read().strip()
                        if raw_content:
                            parsed = extract_json_from_text(raw_content)
                            if parsed is not None:
                                try:
                                    if os.path.exists(task_file):
                                        os.remove(task_file)
                                except Exception:
                                    pass
                                return parsed if json_mode else raw_content
                    except Exception:
                        pass
                await asyncio.sleep(self.poll_interval)
            raise TimeoutError(f"内置 Agent 任务 {task_id} 在测试等待超时。")

        # 生产/实操模式：绝不原地死锁死等！立即打印断点卡片并 sys.exit(20) 挂起交还控制权！
        print("\n" + "=" * 70)
        print(f"⏸️  【AEGIS 状态机断点挂起 (Yield)】等待当前 AI 工具内置 Agent 完成量化推演")
        print(f"🎯 角色契约: {role}")
        print(f"📄 任务描述文件: {task_file}")
        print(f"📥 期待响应路径: {resp_file}")
        print(f"💡 恢复执行步骤:")
        print(f"   1. 当前 AI 工具内置 Agent 读取任务文件并在原生上下文中推演；")
        print(f"   2. 将合法 JSON 结果写入响应路径: {resp_file}；")
        print(f"   3. 重新执行当前命令以自动恢复状态机运行 (Resume)！")
        print("=" * 70 + "\n")
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(EXIT_CODE_YIELD)

# 兼容别名
SubAgentIPCBackend = BuiltinAgentBackend


# -------------------------------------------------------------
# 后端 3: 标准 HTTP LLM API (OpenAI / DeepSeek / Claude / Local Ollama)
# -------------------------------------------------------------
class LLMAPIBackend(BaseAgentBackend):
    """
    通用标准 LLM API 驱动 (支持 OpenAI / DeepSeek / OneAPI / Local Ollama)
    纯 Python 标准库实现，零额外第三方库依赖！
    """
    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        self.api_base = (api_base or os.environ.get("OPENAI_API_BASE") or os.environ.get("LLM_API_BASE") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY") or ""
        self.default_model = default_model or os.environ.get("OPENAI_MODEL") or os.environ.get("LLM_MODEL") or "deepseek-chat"

    async def send_message(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 60,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        endpoint = f"{self.api_base}/chat/completions"
        target_model = model or self.default_model
        
        # 兼容一些模型名
        if "gemini" in target_model.lower() and "deepseek" in self.default_model.lower():
            target_model = self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": f"You are {role}, an expert quantitative finance subagent."})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.7,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }

        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)

        try:
            resp_json = await loop.run_in_executor(None, _fetch)
            content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            if json_mode:
                parsed = extract_json_from_text(content)
                if parsed is not None:
                    return parsed
            return content
        except Exception as e:
            raise RuntimeError(f"LLM API 调用失败 ({endpoint}): {e}")


# -------------------------------------------------------------
# 后端 4: 离线白盒规则引擎 (RuleMockBackend)
# -------------------------------------------------------------
class RuleMockBackend(BaseAgentBackend):
    """确定性白盒规则引擎，用于离线单元测试与极速门禁核查"""
    def __init__(self, fallback_fn=None):
        self.fallback_fn = fallback_fn

    async def send_message(
        self,
        role: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        timeout: int = 60,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any], List[Any]]:
        if self.fallback_fn:
            return self.fallback_fn(role, prompt, json_mode=json_mode, context=context)
        return {"status": "mock_success", "role": role} if json_mode else f"Mock response for {role}"


# -------------------------------------------------------------
# 后端工厂方法 (Backend Factory)
# -------------------------------------------------------------
def create_agent_backend(
    backend_type: str = "builtin",
    agy_path: Optional[str] = None,
    tasks_dir: Optional[str] = None,
    mock_fallback_fn=None,
    **kwargs
) -> BaseAgentBackend:
    """
    根据配置签发 Agent 后端:
    - 'builtin' / 'auto' / 'subagent' / 'ipc': AI 工具原生内置智能体驱动 (0 外部进程, 0 API Key) [默认且唯一推荐]
    - 'mock': 离线规则引擎 (仅限单元测试)
    - 'llm_api': 显式指定 HTTP API 时使用
    - 'agy': 显式指定外部 agy.exe 时使用
    """
    backend_type = (backend_type or "builtin").lower()

    if backend_type == "mock" or os.environ.get("AEGIS_MOCK_MODE") == "1":
        return RuleMockBackend(fallback_fn=mock_fallback_fn)

    # 检查显式环境变量指定
    if os.environ.get("AEGIS_AGENT_BACKEND"):
        backend_type = os.environ.get("AEGIS_AGENT_BACKEND").lower()

    if backend_type in ("llm_api", "openai", "api"):
        return LLMAPIBackend()

    if backend_type == "agy" and agy_path:
        return AGYCliBackend(agy_path=agy_path)

    # 默认且核心标准: 直接使用当前 AI 工具内置的 Agent 模型 (0 外部进程调用，0 API Key 依赖)
    print("🤖 [AgentBackend] 已启用 AI 工具内置 Agent 驱动 (直接使用当前环境大模型，取消外部 agy 进程与 API Key 依赖)！")
    return SubAgentIPCBackend(tasks_dir=tasks_dir)
