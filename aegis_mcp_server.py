"""
aegis_mcp_server.py
AEGIS V4.1 宿主驱动量化研究 MCP Server 与 CLI 工具入口

将全部研究闭环逻辑封装在 7 个受控状态机工具中暴露给外部顶级宿主智能体，
彻底取代旧版 `.agent_tasks/` 邮箱轮询与黑盒 `main.py` 大循环:
  1. `init_or_load_campaign` — 初始化或加载战役，硬锁 Region/Universe/Dataset/Delay Scope
  2. `campaign_status`       — 查看当前作用域、假说树、实验进度、目录卫生与下一步建议
  3. `profile_dataset`       — 计算数据集有效秩 C_eff (支持 P0Y0M 实盘探针或离线结构代理)
  4. `register_hypothesis`   — 在编写表达式前预注册 DGP 因果假说与字段角色
  5. `run_experiment`        — 执行 SNC/晶格/量纲/去重/RedTeam 门禁与回测 (discovery/surgery 屏蔽近2年Holdout)
  6. `request_verdict`       — 申请终审发证 (`CERTIFY_ALPHA`) 或 C_eff 科学穷尽裁决 (`DECLARE_EXHAUSTED`)
  7. `lookup_operators`      — 按需查询账号 104 个正式授权算子签名，杜绝幻觉算子
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from mcp.server.fastmcp import FastMCP

from core.campaign_store import archive_legacy_scripts, check_directory_hygiene
from core.research_service import ResearchService


mcp = FastMCP("aegis-quant-research")
_SERVICE = ResearchService(workspace_root=_ROOT_DIR)


def get_service() -> ResearchService:
    return _SERVICE


@mcp.tool()
async def init_or_load_campaign(
    region: str = "",
    universe: str = "",
    dataset_id: str = "",
    delay: Optional[int] = None,
    category: str = "other",
    seed_alpha_id: Optional[str] = None,
    campaign_name: Optional[str] = None,
    seed_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    初始化或加载研究战役，物理锁定 Region / Universe / Dataset / Delay 作用域 (Scope Lock)。
    - 从零挖掘 (GREENFIELD): 必须提供 region / universe / dataset_id / delay。
    - 靶向优化 (TARGETED_OPTIMIZATION): 传入 seed_alpha_id 后将自动从 Brain 平台水合表达式、真实物理设置、年报、相关性与法医病灶诊断。
    """
    return await _SERVICE.init_or_load_campaign_async(
        region=region,
        universe=universe,
        dataset_id=dataset_id,
        delay=delay,
        category=category,
        seed_alpha_id=seed_alpha_id,
        campaign_name=campaign_name,
        seed_profile=seed_profile,
    )


@mcp.tool()
def campaign_status(campaign_id: str) -> Dict[str, Any]:
    """查询指定战役的锁定作用域、数据画像 C_eff、假说树、目录卫生及下一步研究动作。"""
    return _SERVICE.campaign_status(campaign_id=campaign_id)


@mcp.tool()
async def profile_dataset(
    campaign_id: str,
    use_live_probe: bool = False,
    enqueue: bool = False,
) -> Dict[str, Any]:
    """
    分析锁定数据集物理画像并测定特征有效秩 C_eff 与分层语义簇实测物理特征。
    强烈建议实盘探针传 use_live_probe=True, enqueue=True：1秒内落盘离线基线并把实盘探针入队 campaign.db，
    再通过后台执行 `python3 aegis_mcp_server.py cli run-job --campaign <id> --job <job_id>` 静默跑完，彻底避免 3 分钟 MCP 超时。
    """
    return await _SERVICE.profile_dataset_async(
        campaign_id=campaign_id,
        use_live_probe=use_live_probe,
        enqueue=enqueue,
    )


@mcp.tool()
def register_hypothesis(
    campaign_id: str,
    hypothesis_id: str,
    economic_mechanism: str,
    counterparty: str,
    field_roles: List[Dict[str, Any]],
    mechanism_intents: List[str],
    falsification_criterion: str,
    parent_alpha_id: Optional[str] = None,
) -> Dict[str, Any]:
    """在写任何 FastExpr 之前预注册 DGP 经济学假说规格与可证伪判据。"""
    return _SERVICE.register_hypothesis(
        campaign_id=campaign_id,
        hypothesis_id=hypothesis_id,
        economic_mechanism=economic_mechanism,
        counterparty=counterparty,
        field_roles=field_roles,
        mechanism_intents=mechanism_intents,
        falsification_criterion=falsification_criterion,
        parent_alpha_id=parent_alpha_id,
    )


@mcp.tool()
async def run_experiment(
    campaign_id: str,
    hypothesis_id: str,
    variants: List[Dict[str, Any]],
    mode: str = "discovery",
    settings: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    enqueue: bool = False,
) -> Dict[str, Any]:
    """
    提交批量变体执行多行 SNC 编译门禁、离散晶格检验、量纲守恒审查、双层等价去重、反微调、RedTeam 与分块仿真回测。
    - 实盘在线回测强烈建议传 `enqueue=True`：1 秒内跑完 100% 静态门禁并持久化入队 `campaign.db`，返回 `job_id` 与 `cli_command`，
      随后由后台任务或轻量执行子 Agent 静默运行 `cli run-job`（0 轮询 Token、无 3 分钟 MCP 超时、完成后仅回传 <1KB 脱敏关键摘要）。
    - discovery(1~20)/surgery(1~8) 锁定物理设置并彻底屏蔽 10Y 全局 sharpe 与近 2 年 Holdout；settings_calibration(1~4) 须已有 |Sharpe|>=1.25 母本。
    """
    return await _SERVICE.run_experiment_async(
        campaign_id=campaign_id,
        hypothesis_id=hypothesis_id,
        variants=variants,
        mode=mode,
        settings=settings,
        dry_run=dry_run,
        enqueue=enqueue,
    )


@mcp.tool()
async def request_verdict(
    campaign_id: str,
    action: str,
    alpha_id: Optional[str] = None,
    expression: Optional[str] = None,
    rationale: str = "",
) -> Dict[str, Any]:
    """
    申请正式研究终审裁决 (原生异步，自动补齐 Brain 实盘 yearly_stats / ProdCorr / SelfCorr / 跨批 HorizonProbe 证据链):
    - action='CERTIFY_ALPHA': 解封近 2 年 Holdout (缺 yearly_stats 必 Fail-Closed 拒签) 并运行 ProductionGate (ALL PASS + ProdCorr < 0.65) 发证写入 certified_champions.json
    - action='DECLARE_EXHAUSTED': 依据 C_eff 与字段语义簇覆盖率 >= 80% 裁决数据集是否已系统穷尽
    """
    return await _SERVICE.request_verdict_async(
        campaign_id=campaign_id,
        action=action,
        alpha_id=alpha_id,
        expression=expression,
        rationale=rationale,
    )


@mcp.tool()
def lookup_operators(query: str = "", category: str = "") -> Dict[str, Any]:
    """按关键词或分类查询账号 104 个正式授权算子的精确定义与描述 (Single Source of Truth)。"""
    return _SERVICE.lookup_operators(query=query, category=category)


def _run_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="aegis_mcp_server.py cli", description="AEGIS V4.1 CLI Toolbelt")
    sub = parser.add_subparsers(dest="subcmd", required=True)

    op_p = sub.add_parser("operators", help="Lookup authorized WorldQuant Brain operators")
    op_p.add_argument("--query", default="", help="Keyword filter")
    op_p.add_argument("--category", default="", help="Category filter")

    st_p = sub.add_parser("status", help="Inspect campaign status")
    st_p.add_argument("--campaign", required=True, help="Campaign ID")

    hy_p = sub.add_parser("hygiene", help="Verify V4.1 3-file campaign directory hygiene")
    hy_p.add_argument("--campaign-dir", required=True, help="Path to campaign directory")

    ar_p = sub.add_parser("archive-legacy", help="Losslessly archive stray legacy .py scripts under campaigns/")
    ar_p.add_argument("--campaigns-root", default=os.path.join(_ROOT_DIR, "campaigns"), help="Path to campaigns root")

    rj_p = sub.add_parser("run-job", help="Silently execute a queued experiment/probe job in background (0 MCP timeout, <1KB summary)")
    rj_p.add_argument("--campaign", required=True, help="Campaign ID")
    rj_p.add_argument("--job", required=True, help="Queued Job ID (from enqueue=True)")
    rj_p.add_argument("--campaigns-root", default=None, help="Optional custom campaigns root directory")
    rj_p.add_argument("--full", action="store_true", help="Output full response instead of compact <1KB summary")

    jb_p = sub.add_parser("jobs", help="List queued/running/completed jobs in campaign.db")
    jb_p.add_argument("--campaign", required=True, help="Campaign ID")
    jb_p.add_argument("--status", default=None, help="Filter by status (QUEUED/RUNNING/COMPLETED/FAILED)")
    jb_p.add_argument("--campaigns-root", default=None, help="Optional custom campaigns root directory")

    args = parser.parse_args(argv)
    if args.subcmd == "operators":
        res = _SERVICE.lookup_operators(query=args.query, category=args.category)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.subcmd == "status":
        res = _SERVICE.campaign_status(campaign_id=args.campaign)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.subcmd == "hygiene":
        res = check_directory_hygiene(args.campaign_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("clean") else 2
    if args.subcmd == "archive-legacy":
        res = archive_legacy_scripts(args.campaigns_root, recursive=True)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.subcmd == "run-job":
        svc = ResearchService(workspace_root=_ROOT_DIR, campaigns_root=args.campaigns_root) if args.campaigns_root else _SERVICE
        res = svc.execute_job(
            campaign_id=args.campaign,
            job_id=args.job,
            compact=(not args.full),
            log_to_stderr=True,
        )
        print(json.dumps(res, ensure_ascii=False, separators=(",", ":") if not args.full else None, indent=None if not args.full else 2))
        return 0
    if args.subcmd == "jobs":
        svc = ResearchService(workspace_root=_ROOT_DIR, campaigns_root=args.campaigns_root) if args.campaigns_root else _SERVICE
        res = svc.list_jobs(campaign_id=args.campaign, status=args.status)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        sys.exit(_run_cli(sys.argv[2:]))
    mcp.run()
