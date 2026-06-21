"""测试全局夹具：确保 Postgres 表已建好（不触碰对象存储）。

API 冒烟测试通过 TestClient 直接调用，不经过应用 lifespan，因此在这里
显式建表。需要本地/CI 提供 Postgres（CI 已配置 postgres service）。
"""

import time
import uuid

import pytest


@pytest.fixture(scope="session", autouse=True)
def _init_database() -> None:
    from app.core.db import init_db

    init_db()


@pytest.fixture(scope="session")
def auth_headers() -> dict[str, str]:
    """创建一个「已验证邮箱」的测试用户并返回带 access token 的请求头。

    业务路由（graph/report/simulation）已全部要求登录；冒烟测试需带上鉴权头
    才能命中真正的处理器，而非被 get_current_user 拦在 401。
    """
    from app.core.db import session_scope
    from app.core.security import create_access_token
    from app.db_models import UserRow

    user_id = f"user_test_{uuid.uuid4().hex[:12]}"
    now = str(int(time.time()))
    with session_scope() as session:
        session.add(
            UserRow(
                user_id=user_id,
                email=f"{user_id}@test.local",
                password_hash="",
                display_name="pytest",
                status="active",
                email_verified=True,
                created_at=now,
                updated_at=now,
            )
        )
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}
