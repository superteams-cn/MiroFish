"""
数据库层（Postgres + SQLAlchemy 2.0 同步引擎）。

设计要点：
- 同步引擎 + 连接池，可在 FastAPI 同步路由及后台线程中安全使用；
- 通过 ``session_scope()`` 上下文管理器提供「每操作一会话」的事务边界；
- ``init_db()`` 在应用启动时建表（幂等）。
"""

import contextlib
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .logger import get_logger
from .settings import settings

logger = get_logger("superfish.db")


class Base(DeclarativeBase):
    """ORM 基类。"""


# 连接池 + pre_ping（自动剔除失效连接，避免长时间空闲后报错）
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """提供一个带自动提交/回滚的事务性会话。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """开发/测试环境的建表引导（幂等，基于 ORM 模型的 ``create_all``）。

    schema 的「演进」由 Alembic 统一管理（``alembic upgrade head``）——
    历史上散落在此的裸 SQL 补列迁移已收编为 migrations/ 下的版本化迁移。

    使用约定（避免两套机制在同一库上打架）：
    - 持久化/生产环境：仅用 ``alembic upgrade head`` 维护 schema；
    - 一次性/测试库：可用本函数 ``create_all`` 快速建表（无迁移历史）。
    """
    # 导入以注册 ORM 模型到 Base.metadata
    from .. import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪（Postgres / create_all 引导）")
