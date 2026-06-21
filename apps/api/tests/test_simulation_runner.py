"""SimulationRunner 集成测试（不起真实子进程）。

聚焦深拆 SimulationRunner（→ ProcessController/OwnershipLock/RunStateStore/...）前
最易回归的「编排逻辑」：
- 运行态持久化往返（RunStateStore 边界）；
- 进程探活与「死进程→终态」对账（ProcessController + 对账边界）；
- 监控所有权 CAS：抢占/确认/释放/TTL 过期接管（OwnershipLock 边界）；
- 启动对账 reconcile 终结已死运行。

需要 Postgres（conftest 已建表）。通过伪造 PID 与受控 sim 目录达成确定性，无需 OASIS。
"""

import os
import time
import uuid

import pytest

from app.repositories.run_state_repo import RunStateRepository
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState


@pytest.fixture
def runner_cleanup():
    """记录用过的 simulation_id，测试后清理 DB 行与进程内缓存，避免跨用例污染。"""
    created: list[str] = []
    yield created
    for sid in created:
        try:
            RunStateRepository.delete(sid)
        except Exception:
            pass
        SimulationRunner._run_states.pop(sid, None)
        SimulationRunner._graph_memory_enabled.pop(sid, None)


def _new_sid(created: list[str]) -> str:
    sid = f"sim_test_{uuid.uuid4().hex[:12]}"
    created.append(sid)
    return sid


# ───────────────────────── 纯工具：解析 / 探活 ─────────────────────────


def test_parse_etime_formats():
    assert SimulationRunner._parse_etime("05") is None  # 单段非法
    assert SimulationRunner._parse_etime("01:02") == 62  # mm:ss
    assert SimulationRunner._parse_etime("01:02:03") == 3723  # hh:mm:ss
    assert SimulationRunner._parse_etime("2-00:00:00") == 172800  # dd-hh:mm:ss
    assert SimulationRunner._parse_etime("") is None


def test_pid_alive_basic():
    assert SimulationRunner._pid_alive(os.getpid()) is True
    assert SimulationRunner._pid_alive(None) is False
    # 999999 几乎不可能存在 → ProcessLookupError → 判死
    assert SimulationRunner._pid_alive(999999) is False


def test_has_simulation_end(tmp_path):
    sim_dir = tmp_path / "sim_x"
    (sim_dir / "reddit").mkdir(parents=True)
    log = sim_dir / "reddit" / "actions.jsonl"
    log.write_text('{"event":"step"}\n', encoding="utf-8")
    assert SimulationRunner._has_simulation_end(str(sim_dir)) is False
    log.write_text('{"event":"step"}\n{"event":"simulation_end"}\n', encoding="utf-8")
    assert SimulationRunner._has_simulation_end(str(sim_dir)) is True


# ───────────────────────── 运行态持久化往返 ─────────────────────────


def test_run_state_persistence_roundtrip(runner_cleanup):
    sid = _new_sid(runner_cleanup)
    state = SimulationRunState(
        simulation_id=sid,
        runner_status=RunnerStatus.RUNNING,
        current_round=3,
        total_rounds=10,
        process_pid=4242,
        graph_id="graph_abc",
        graph_memory_enabled=True,
    )
    SimulationRunner._save_run_state(state)

    # 清掉进程内缓存，强制走 DB 重建路径
    SimulationRunner._run_states.pop(sid, None)
    loaded = SimulationRunner._load_run_state(sid)
    assert loaded is not None
    assert loaded.simulation_id == sid
    assert loaded.runner_status == RunnerStatus.RUNNING
    assert loaded.current_round == 3
    assert loaded.total_rounds == 10
    assert loaded.process_pid == 4242
    assert loaded.graph_id == "graph_abc"
    assert loaded.graph_memory_enabled is True


def test_get_run_state_prefers_inmemory(runner_cleanup):
    sid = _new_sid(runner_cleanup)
    state = SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.STOPPED)
    SimulationRunner._save_run_state(state)
    # _save_run_state 会把对象放进内存缓存；get_run_state 应原样返回同一对象
    assert SimulationRunner.get_run_state(sid) is state


# ───────────────────────── 监控所有权 CAS ─────────────────────────


def test_ownership_claim_still_release(runner_cleanup):
    sid = _new_sid(runner_cleanup)
    SimulationRunner._save_run_state(
        SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.RUNNING)
    )

    assert SimulationRunner._try_claim_ownership(sid) is True
    assert SimulationRunner._still_owner(sid) is True

    SimulationRunner._release_ownership(sid)
    assert SimulationRunner._still_owner(sid) is False


def test_ownership_blocked_by_live_other_but_takeover_on_expiry(runner_cleanup):
    sid = _new_sid(runner_cleanup)
    SimulationRunner._save_run_state(
        SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.RUNNING)
    )

    data = RunStateRepository.load_raw(sid)
    # 另一实例持有且心跳新鲜 → 不可抢占
    data["owner_id"] = "other-host:123"
    data["owner_heartbeat"] = time.time()
    RunStateRepository.save_raw(sid, data)
    assert SimulationRunner._try_claim_ownership(sid) is False

    # 心跳过期（> OWNER_TTL）→ 可接管
    data["owner_heartbeat"] = time.time() - (SimulationRunner.OWNER_TTL + 60)
    RunStateRepository.save_raw(sid, data)
    assert SimulationRunner._try_claim_ownership(sid) is True
    assert SimulationRunner._still_owner(sid) is True


def test_claim_ownership_missing_row_returns_false(runner_cleanup):
    sid = _new_sid(runner_cleanup)  # 未落库
    assert SimulationRunner._try_claim_ownership(sid) is False


# ───────────────────────── 死进程 → 终态对账 ─────────────────────────


def test_reconcile_state_dead_running_to_interrupted(runner_cleanup, tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    sid = _new_sid(runner_cleanup)
    state = SimulationRunState(
        simulation_id=sid, runner_status=RunnerStatus.RUNNING, process_pid=999999
    )
    SimulationRunner._save_run_state(state)
    SimulationRunner._run_states.pop(sid, None)

    reconciled = SimulationRunner._reconcile_state(SimulationRunner._load_run_state(sid))
    # 进程已死、无 simulation_end → INTERRUPTED
    assert reconciled.runner_status == RunnerStatus.INTERRUPTED
    assert reconciled.twitter_running is False
    assert reconciled.reddit_running is False
    assert reconciled.owner_id is None


def test_reconcile_state_dead_with_simulation_end_to_completed(
    runner_cleanup, tmp_path, monkeypatch
):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    sid = _new_sid(runner_cleanup)
    sim_dir = tmp_path / sid / "reddit"
    sim_dir.mkdir(parents=True)
    (sim_dir / "actions.jsonl").write_text('{"event":"simulation_end"}\n', encoding="utf-8")

    state = SimulationRunState(
        simulation_id=sid, runner_status=RunnerStatus.RUNNING, process_pid=999999
    )
    SimulationRunner._save_run_state(state)
    SimulationRunner._run_states.pop(sid, None)

    reconciled = SimulationRunner._reconcile_state(SimulationRunner._load_run_state(sid))
    assert reconciled.runner_status == RunnerStatus.COMPLETED
    assert reconciled.completed_at  # 终结时间已写


def test_reconcile_running_simulations_finalizes_dead(runner_cleanup, tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    sid = _new_sid(runner_cleanup)
    SimulationRunner._save_run_state(
        SimulationRunState(
            simulation_id=sid, runner_status=RunnerStatus.RUNNING, process_pid=999999
        )
    )
    SimulationRunner._run_states.pop(sid, None)

    result = SimulationRunner.reconcile_running_simulations()
    assert sid in result["finalized"]
    assert SimulationRunner._load_run_state(sid).runner_status == RunnerStatus.INTERRUPTED
