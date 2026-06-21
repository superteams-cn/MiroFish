"""用户仓储：users 表的全部数据访问（session_scope + 行<->领域映射）。

收编原先散落在 auth 路由里的内联 ``session_scope`` / ``UserRow`` 查询，
对外只收发 ``User`` 领域快照。
"""

from __future__ import annotations

from datetime import datetime

from ..core.db import session_scope
from ..db_models import UserRow
from ..domain.user import User


def _row_to_user(row: UserRow) -> User:
    return User(
        user_id=row.user_id,
        email=row.email,
        password_hash=row.password_hash or "",
        display_name=row.display_name or "",
        status=row.status,
        email_verified=row.email_verified,
        created_at=row.created_at or "",
        updated_at=row.updated_at or "",
    )


class UserRepository:
    """users 表数据访问。"""

    @staticmethod
    def get_by_email(email: str) -> User | None:
        with session_scope() as session:
            row = session.query(UserRow).filter(UserRow.email == email).first()
            return _row_to_user(row) if row else None

    @staticmethod
    def get_by_id(user_id: str) -> User | None:
        with session_scope() as session:
            row = session.get(UserRow, user_id)
            return _row_to_user(row) if row else None

    @staticmethod
    def email_exists(email: str) -> bool:
        with session_scope() as session:
            return session.query(UserRow).filter(UserRow.email == email).first() is not None

    @staticmethod
    def create(
        user_id: str,
        email: str,
        password_hash: str,
        display_name: str,
        email_verified: bool,
        created_at: str,
        updated_at: str,
    ) -> User:
        """创建用户。唯一索引兜底并发；冲突时 commit 抛 IntegrityError 由调用方感知。"""
        with session_scope() as session:
            # 二次确认唯一（防 TOCTOU；唯一索引最终兜底）
            if session.query(UserRow).filter(UserRow.email == email).first() is not None:
                raise ValueError("email_taken")
            row = UserRow(
                user_id=user_id,
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                status="active",
                email_verified=email_verified,
                created_at=created_at,
                updated_at=updated_at,
            )
            session.add(row)
            session.flush()
            return _row_to_user(row)

    @staticmethod
    def mark_verified(user_id: str) -> None:
        """置邮箱已验证（幂等：已验证则不改 updated_at）。"""
        with session_scope() as session:
            row = session.get(UserRow, user_id)
            if row is not None and row.status == "active" and not row.email_verified:
                row.email_verified = True
                row.updated_at = datetime.now().isoformat()

    @staticmethod
    def set_password(user_id: str, password_hash: str) -> None:
        with session_scope() as session:
            row = session.get(UserRow, user_id)
            if row is not None:
                row.password_hash = password_hash
                row.updated_at = datetime.now().isoformat()
