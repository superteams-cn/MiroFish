"""SimulationRunner 进程内运行时状态的单一容器。

把原先散落在 SimulationRunner 上的 7 个静态类 dict 收进一个可注入的 store 对象，
作为后续把 MonitorThread/Reconciler 等抽成独立类的前提 —— 它们将接收本 store 作为
依赖，而不再直接访问 SimulationRunner 的类属性。

语义与原类属性 dict 完全一致：进程内单例（同一进程跨请求共享），仅持有本进程
亲自拉起/接管的模拟的运行时句柄与缓存。
"""

import subprocess
import threading
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

from ...domain.run_state import SimulationRunState


@dataclass
class RunnerRuntimeStore:
    """SimulationRunner 的进程内运行时状态单一容器（可注入）。

    各字段对应原 SimulationRunner 的静态类 dict（去掉前导下划线）：
    - run_states: 内存中的运行状态实时对象（owner 视角）；
    - processes: 本进程亲自 Popen 的子进程句柄；
    - action_queues: 动作队列；
    - monitor_threads: 监控线程；
    - stdout_files / stderr_files: 日志文件句柄；
    - graph_memory_enabled: simulation_id -> 是否启用图谱记忆更新。
    """

    run_states: dict[str, SimulationRunState] = field(default_factory=dict)
    processes: dict[str, subprocess.Popen] = field(default_factory=dict)
    action_queues: dict[str, Queue] = field(default_factory=dict)
    monitor_threads: dict[str, threading.Thread] = field(default_factory=dict)
    stdout_files: dict[str, Any] = field(default_factory=dict)
    stderr_files: dict[str, Any] = field(default_factory=dict)
    graph_memory_enabled: dict[str, bool] = field(default_factory=dict)
