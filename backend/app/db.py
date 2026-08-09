"""数据库引擎与会话（SQLModel / SQLAlchemy 2.0）。

连接串由 app.config 统一装配：开发默认拼装到 docker compose 的 PostgreSQL 16，
生产必须显式配置 DATABASE_URL；SQLite 仅用于测试与一次性迁移脚本的显式注入。
"""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args)


def init_db() -> None:
    """开发环境便捷建表；生产走 Alembic 迁移。"""
    # 确保模型已注册到 metadata
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
