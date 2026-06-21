"""采访子系统：对运行中的模拟环境发起 Agent 采访，并读取采访历史。

从 SimulationRunner 抽出，全部为无状态函数（按 ``run_state_dir`` + ``simulation_id``
定位模拟目录与 IPC 通道，不依赖类级状态）。SimulationRunner 以薄委托调用并传入
``RUN_STATE_DIR``，集成测试 tests/test_simulation_runner.py 守护行为等价。

错误语义：模拟/配置不存在 → AppError(404)；环境未运行 → AppError(409)。
"""

import json
import os
from typing import Any

from ...core.errors import AppError
from ...core.logger import get_logger
from ...repositories.interview_trace_repo import InterviewTraceRepository
from ..simulation_ipc import SimulationIPCClient

logger = get_logger("superfish.simulation.interview")


def interview_agent(
    run_state_dir: str,
    simulation_id: str,
    agent_id: int,
    prompt: str,
    platform: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """采访单个 Agent。

    platform 为 "twitter"/"reddit" 时只采访对应平台；None 时双平台模拟会同时采访
    两个平台并返回整合结果。

    Raises:
        AppError: 模拟不存在(404) 或环境未运行(409)。
        TimeoutError: 等待响应超时。
    """
    sim_dir = os.path.join(run_state_dir, simulation_id)
    if not os.path.exists(sim_dir):
        raise AppError(f"模拟不存在: {simulation_id}", status=404)

    ipc_client = SimulationIPCClient(sim_dir)

    if not ipc_client.check_env_alive():
        raise AppError(f"模拟环境未运行或已关闭，无法执行Interview: {simulation_id}", status=409)

    logger.info(
        f"发送Interview命令: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}"
    )

    response = ipc_client.send_interview(
        agent_id=agent_id, prompt=prompt, platform=platform, timeout=timeout
    )

    if response.status.value == "completed":
        return {
            "success": True,
            "agent_id": agent_id,
            "prompt": prompt,
            "result": response.result,
            "timestamp": response.timestamp,
        }
    else:
        return {
            "success": False,
            "agent_id": agent_id,
            "prompt": prompt,
            "error": response.error,
            "timestamp": response.timestamp,
        }


def interview_agents_batch(
    run_state_dir: str,
    simulation_id: str,
    interviews: list[dict[str, Any]],
    platform: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """批量采访多个 Agent。

    interviews 每项为 ``{"agent_id": int, "prompt": str, "platform": str(可选)}``；
    顶层 platform 为默认平台，会被每项自带的 platform 覆盖。

    Raises:
        AppError: 模拟不存在(404) 或环境未运行(409)。
        TimeoutError: 等待响应超时。
    """
    sim_dir = os.path.join(run_state_dir, simulation_id)
    if not os.path.exists(sim_dir):
        raise AppError(f"模拟不存在: {simulation_id}", status=404)

    ipc_client = SimulationIPCClient(sim_dir)

    if not ipc_client.check_env_alive():
        raise AppError(f"模拟环境未运行或已关闭，无法执行Interview: {simulation_id}", status=409)

    logger.info(
        f"发送批量Interview命令: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}"
    )

    response = ipc_client.send_batch_interview(
        interviews=interviews, platform=platform, timeout=timeout
    )

    if response.status.value == "completed":
        return {
            "success": True,
            "interviews_count": len(interviews),
            "result": response.result,
            "timestamp": response.timestamp,
        }
    else:
        return {
            "success": False,
            "interviews_count": len(interviews),
            "error": response.error,
            "timestamp": response.timestamp,
        }


def interview_all_agents(
    run_state_dir: str,
    simulation_id: str,
    prompt: str,
    platform: str | None = None,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """采访模拟中的所有 Agent（用同一问题），内部委托批量采访。

    Raises:
        AppError: 模拟/配置不存在或配置无 Agent(404)。
    """
    sim_dir = os.path.join(run_state_dir, simulation_id)
    if not os.path.exists(sim_dir):
        raise AppError(f"模拟不存在: {simulation_id}", status=404)

    # 从配置文件获取所有Agent信息
    config_path = os.path.join(sim_dir, "simulation_config.json")
    if not os.path.exists(config_path):
        raise AppError(f"模拟配置不存在: {simulation_id}", status=404)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    agent_configs = config.get("agent_configs", [])
    if not agent_configs:
        raise AppError(f"模拟配置中没有Agent: {simulation_id}", status=404)

    # 构建批量采访列表
    interviews = []
    for agent_config in agent_configs:
        agent_id = agent_config.get("agent_id")
        if agent_id is not None:
            interviews.append({"agent_id": agent_id, "prompt": prompt})

    logger.info(
        f"发送全局Interview命令: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}"
    )

    return interview_agents_batch(
        run_state_dir=run_state_dir,
        simulation_id=simulation_id,
        interviews=interviews,
        platform=platform,
        timeout=timeout,
    )


def get_interview_history(
    run_state_dir: str,
    simulation_id: str,
    platform: str | None = None,
    agent_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """获取采访历史记录（从每模拟独立的 OASIS sqlite 库读取）。

    platform 为 "reddit"/"twitter" 时只查对应平台；None 时查两个平台并按时间倒序合并、
    截断到 limit。
    """
    sim_dir = os.path.join(run_state_dir, simulation_id)

    results = []

    # 确定要查询的平台
    if platform in ("reddit", "twitter"):
        platforms = [platform]
    else:
        # 不指定platform时，查询两个平台
        platforms = ["twitter", "reddit"]

    for p in platforms:
        db_path = os.path.join(sim_dir, f"{p}_simulation.db")
        platform_results = InterviewTraceRepository.list_interviews(
            db_path=db_path, platform_name=p, agent_id=agent_id, limit=limit
        )
        results.extend(platform_results)

    # 按时间降序排序
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 如果查询了多个平台，限制总数
    if len(platforms) > 1 and len(results) > limit:
        results = results[:limit]

    return results
