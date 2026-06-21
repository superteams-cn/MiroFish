"""进程控制：无状态的子进程探活与终止工具。

从 SimulationRunner 抽出，全部为纯函数（参数进、结果出，不依赖类级状态），
便于独立测试与复用。SimulationRunner 以薄委托调用这些函数。
"""

import os
import signal
import subprocess
import sys
import time

from ...domain.run_state import RunnerStatus

IS_WINDOWS = sys.platform == "win32"


def decide_terminal_status(
    *,
    already_completed: bool,
    is_own_process: bool,
    exit_code: int | None,
    has_sim_end: bool,
) -> RunnerStatus:
    """进程退出后的终态判定（纯决策，不落副作用）。

    - ``already_completed``：监控期间 _read_action_log 已据 simulation_end 置为 COMPLETED。
    - 本进程亲自 Popen（``is_own_process``）：退出码 0 或已见 simulation_end → COMPLETED，否则 FAILED。
    - 接管的孤儿（无退出码）：见 simulation_end → COMPLETED，否则 INTERRUPTED。

    completed_at / error 等副作用由调用方依据返回的状态处理。
    """
    if already_completed:
        return RunnerStatus.COMPLETED
    if is_own_process:
        if exit_code == 0 or has_sim_end:
            return RunnerStatus.COMPLETED
        return RunnerStatus.FAILED
    # 接管的孤儿无退出码
    if has_sim_end:
        return RunnerStatus.COMPLETED
    return RunnerStatus.INTERRUPTED


def parse_etime(s: str) -> int | None:
    """解析 ``ps -o etime`` 的已运行时长 [[dd-]hh:]mm:ss → 秒。"""
    s = s.strip()
    if not s:
        return None
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    parts = [int(x) for x in s.split(":")]
    if len(parts) == 3:
        h, m, sec = parts
    elif len(parts) == 2:
        h, m, sec = 0, parts[0], parts[1]
    else:
        return None
    return days * 86400 + h * 3600 + m * 60 + sec


def read_process_start_time(pid: int) -> float | None:
    """返回进程近似绝对启动时刻（epoch 秒），失败返回 None。

    用已运行时长反推：start ≈ now - elapsed。兼容 Linux（etimes 整数秒）与
    macOS（etime 格式化时长）。Windows 无 ps → 返回 None，降级为仅 os.kill 探活。
    """
    if not pid:
        return None
    # Linux: etimes（整数秒）
    try:
        out = subprocess.run(
            ["ps", "-o", "etimes=", "-p", str(pid)], capture_output=True, text=True, timeout=3
        )
        s = out.stdout.strip()
        if s and s.isdigit():
            return time.time() - int(s)
    except Exception:
        pass
    # macOS/BSD: etime（[[dd-]hh:]mm:ss）
    try:
        out = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)], capture_output=True, text=True, timeout=3
        )
        secs = parse_etime(out.stdout)
        if secs is not None:
            return time.time() - secs
    except Exception:
        pass
    return None


def pid_alive(pid: int | None, expected_start: float | None = None) -> bool:
    """PID 探活 + 防 PID 复用。expected_start 偏差 >2s 视为 PID 复用（判死）。"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在（只是非本用户）
    except OSError:
        return False
    if expected_start is not None:
        actual = read_process_start_time(pid)
        if actual is not None and abs(actual - expected_start) > 2.0:
            return False  # 同 PID 但启动时刻不符 → PID 已被复用
    return True


def has_simulation_end(sim_dir: str) -> bool:
    """检查任一平台 actions.jsonl 是否含 simulation_end 事件（判定是否自然跑完）。"""
    for platform in ("twitter", "reddit"):
        log_path = os.path.join(sim_dir, platform, "actions.jsonl")
        if not os.path.exists(log_path):
            continue
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    if '"simulation_end"' in line:
                        return True
        except Exception:
            continue
    return False


def kill_pid_group(pid: int, timeout: int = 45) -> None:
    """无 Popen 句柄时按 PID 杀进程组（start_new_session 保证 PID==PGID）。

    SIGTERM 后留出收尾时间让模拟优雅落盘，进程退出即返回；超时再 SIGKILL。
    """
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=10)
        return
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    os.killpg(pgid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.3)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
