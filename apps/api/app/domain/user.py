"""用户领域模型（纯数据类，无 IO / 无 DB 依赖）。

承载脱离 ORM 会话后仍可安全访问的用户快照；``password_hash`` 为内部字段，
仅用于服务层校验，不进入对外的 public dict。
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    """用户快照。"""

    user_id: str
    email: str
    password_hash: str
    display_name: str
    status: str
    email_verified: bool
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_public_dict(self) -> dict[str, Any]:
        """对外公开字段（不含 password_hash）。"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "status": self.status,
            "email_verified": self.email_verified,
            "created_at": self.created_at,
        }
