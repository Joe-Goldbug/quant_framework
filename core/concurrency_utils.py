"""
concurrency_utils.py
AEGIS 3.0 工业级并发与原子化 I/O 基础设施
彻底解决:
1. Windows WinError 32 文件独占锁冲突
2. 多 Agent 并发读写共享 JSON 产生的状态覆盖踩踏 (State Trampling)
3. SQLite 数据库在并发访问时的 "database is locked" 异常
"""

import json
import os
import sqlite3
import sys
import time
import uuid
from typing import Any, Dict, Optional


def atomic_save_json(filepath: str, data: Any, indent: int = 2, max_retries: int = 5) -> None:
    """
    原子化落盘 JSON 文件:
    1. 写入带有唯一 PID+UUID 的临时文件;
    2. flush + fsync 强制刷盘;
    3. 利用操作系统的原子重命名 (os.replace) 瞬时替换目标文件;
    4. 内置 Windows 平台针对临时文件锁的指数退避重试.
    """
    filepath = os.path.abspath(filepath)
    parent_dir = os.path.dirname(filepath)
    os.makedirs(parent_dir, exist_ok=True)

    temp_file = f"{filepath}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise IOError(f"原子写入临时文件失败: {temp_file}, 错误: {e}")

    # 重试执行原子替换 (针对 Windows 系统中被防病毒软件/只读句柄短暂锁定的情况)
    last_err = None
    for attempt in range(max_retries):
        try:
            os.replace(temp_file, filepath)
            return
        except PermissionError as pe:
            last_err = pe
            time.sleep(0.05 * (2 ** attempt))
        except Exception as e:
            last_err = e
            break

    # 兜底清理临时文件
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except Exception:
            pass

    raise PermissionError(f"原子替换目标文件失败 ({max_retries}次重试): {filepath}, 错误: {last_err}")


def get_sqlite_wal_connection(db_path: str, timeout: float = 15.0) -> sqlite3.Connection:
    """
    获取开启 WAL (Write-Ahead Logging) 模式与高容忍 Busy Timeout 的 SQLite 连接
    支持多进程并发读、单写安全，杜绝 database is locked.
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)};")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def get_sharded_log_path(base_dir: str, prefix: str = "batch", tag: Optional[str] = None) -> str:
    """
    签发独立的不可变分片日志路径，从物理上杜绝多 Agent 写入同一个 log 文件引起的句柄争夺
    """
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    clean_tag = f"_{tag}" if tag else ""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    filename = f"{prefix}{clean_tag}_{timestamp}_{rand_suffix}.jsonl"
    return os.path.join(logs_dir, filename)
