"""运行态仓储：simulation_run_states 表的常规数据访问（session_scope）。

收编 SimulationRunner 中「直读直写」运行态快照的 DB 代码（load/save/bulk/all/delete）。
注意：监控所有权的 CAS（``with_for_update`` 行锁 + 实例/TTL 判定）属并发关键的
业务逻辑，仍保留在 SimulationRunner 内，不在此层。
"""

from __future__ import annotations

from datetime import datetime

from ..core.db import session_scope
from ..db_models import SimulationRunStateRow


class RunStateRepository:
    """simulation_run_states 表的常规读写（收发持久化 data dict）。"""

    @staticmethod
    def load_raw(simulation_id: str) -> dict | None:
        """读取单个运行态快照的 data dict；不存在返回 None。"""
        with session_scope() as session:
            row = session.get(SimulationRunStateRow, simulation_id)
            return dict(row.data) if row and row.data else None

    @staticmethod
    def load_raw_bulk(simulation_ids: list[str]) -> dict[str, dict]:
        """批量读取多个运行态快照（单次查询），返回 {simulation_id: data}。"""
        if not simulation_ids:
            return {}
        with session_scope() as session:
            rows = (
                session.query(SimulationRunStateRow)
                .filter(SimulationRunStateRow.simulation_id.in_(simulation_ids))
                .all()
            )
            return {r.simulation_id: dict(r.data) for r in rows if r.data}

    @staticmethod
    def load_all_raw() -> dict[str, dict]:
        """读取全部运行态快照，返回 {simulation_id: data}（用于对账/退出收集）。"""
        with session_scope() as session:
            rows = session.query(SimulationRunStateRow).all()
            return {r.simulation_id: dict(r.data) for r in rows if r.data}

    @staticmethod
    def save_raw(simulation_id: str, data: dict) -> None:
        """保存运行态快照 data dict（upsert）。"""
        with session_scope() as session:
            row = session.get(SimulationRunStateRow, simulation_id)
            if row is None:
                row = SimulationRunStateRow(simulation_id=simulation_id)
                session.add(row)
            row.data = data
            row.updated_at = datetime.now().isoformat()

    @staticmethod
    def delete(simulation_id: str) -> None:
        """删除运行态快照（不存在则忽略）。"""
        with session_scope() as session:
            row = session.get(SimulationRunStateRow, simulation_id)
            if row is not None:
                session.delete(row)
