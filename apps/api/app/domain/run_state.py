"""模拟运行态领域模型（纯数据类，无 IO / 无 DB 依赖）。

承载 OASIS 模拟的实时运行快照：运行器状态、双平台进度、最近动作、
以及无状态可恢复所需的 owner/offset/进程启动时刻等字段。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class RunnerStatus(StrEnum):
    """运行器状态"""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"  # 进程被外部杀死/崩溃且未跑到 simulation_end（可重新启动）


@dataclass
class AgentAction:
    """Agent动作记录"""

    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """每轮摘要"""

    round_num: int
    start_time: str
    end_time: str | None = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: list[int] = field(default_factory=list)
    actions: list[AgentAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """模拟运行状态（实时）"""

    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE

    # 进度信息
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0

    # 各平台独立轮次和模拟时间（用于双平台并行显示）
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0

    # 平台状态
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0

    # 平台完成状态（通过检测 actions.jsonl 中的 simulation_end 事件）
    twitter_completed: bool = False
    reddit_completed: bool = False

    # 每轮摘要
    rounds: list[RoundSummary] = field(default_factory=list)

    # 最近动作（用于前端实时展示）
    recent_actions: list[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50

    # 时间戳
    started_at: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None

    # 错误信息
    error: str | None = None

    # 进程ID（用于停止）
    process_pid: int | None = None

    # ===== 无状态可恢复（档位 A）相关字段 =====
    # 进程近似绝对启动时刻（epoch 秒），用于 PID 探活时防 PID 复用误判
    process_start_time: float | None = None
    # 动作日志已读字节偏移（持久化，接管时从断点续读，避免重复推送图谱记忆）
    twitter_log_offset: int = 0
    reddit_log_offset: int = 0
    # 监控所有权：哪个进程实例在监控本模拟 + 心跳时间（防多进程重复监控）
    owner_id: str | None = None
    owner_heartbeat: float | None = None
    # 图谱记忆配置（持久化，便于其他进程接管时重建 updater）
    graph_id: str | None = None
    graph_memory_enabled: bool = False

    def add_action(self, action: AgentAction):
        """添加动作到最近动作列表"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[: self.max_recent_actions]

        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1

        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # 各平台独立轮次和时间
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
            # 无状态可恢复字段
            "process_start_time": self.process_start_time,
            "twitter_log_offset": self.twitter_log_offset,
            "reddit_log_offset": self.reddit_log_offset,
            "owner_id": self.owner_id,
            "owner_heartbeat": self.owner_heartbeat,
            "graph_id": self.graph_id,
            "graph_memory_enabled": self.graph_memory_enabled,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """包含最近动作的详细信息"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result

    @classmethod
    def from_data(cls, simulation_id: str, data: dict) -> "SimulationRunState":
        """从持久化 data dict 重建运行态（含最近动作）。解析失败由调用方处理。"""
        state = cls(
            simulation_id=simulation_id,
            runner_status=RunnerStatus(data.get("runner_status", "idle")),
            current_round=data.get("current_round", 0),
            total_rounds=data.get("total_rounds", 0),
            simulated_hours=data.get("simulated_hours", 0),
            total_simulation_hours=data.get("total_simulation_hours", 0),
            twitter_current_round=data.get("twitter_current_round", 0),
            reddit_current_round=data.get("reddit_current_round", 0),
            twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
            reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
            twitter_running=data.get("twitter_running", False),
            reddit_running=data.get("reddit_running", False),
            twitter_completed=data.get("twitter_completed", False),
            reddit_completed=data.get("reddit_completed", False),
            twitter_actions_count=data.get("twitter_actions_count", 0),
            reddit_actions_count=data.get("reddit_actions_count", 0),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            process_pid=data.get("process_pid"),
            process_start_time=data.get("process_start_time"),
            twitter_log_offset=data.get("twitter_log_offset", 0),
            reddit_log_offset=data.get("reddit_log_offset", 0),
            owner_id=data.get("owner_id"),
            owner_heartbeat=data.get("owner_heartbeat"),
            graph_id=data.get("graph_id"),
            graph_memory_enabled=data.get("graph_memory_enabled", False),
        )
        for a in data.get("recent_actions", []):
            state.recent_actions.append(
                AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                )
            )
        return state
