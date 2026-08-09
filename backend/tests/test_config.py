"""数据库/缓存双环境配置装配测试（config.py）。

开发环境：不显式配 URL 时由 DB_* / REDIS_* 组件拼接到 docker compose 依赖；
生产环境：必须显式提供 DATABASE_URL / REDIS_URL，缺失即拒绝启动。
"""

import pytest

from app.config import Settings

_ENV_KEYS = [
    "DATABASE_URL", "REDIS_URL",
    "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
    "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "APP_ENV",
]


@pytest.fixture()
def clean_env(monkeypatch):
    """隔离 conftest 注入的 DATABASE_URL 与本机 .env，纯按传入字段实例化。"""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _make(**fields) -> Settings:
    return Settings(_env_file=None, **fields)  # type: ignore[call-arg]


def test_dev_assembles_urls_from_components(clean_env):
    s = _make(api_keys="k")
    assert s.app_env == "development"
    assert s.database_url == (
        "postgresql+psycopg://hotmonitor:hotmonitor@localhost:5432/hotmonitor"
    )
    assert s.redis_url == "redis://localhost:6379/0"


def test_dev_components_override(clean_env):
    s = _make(
        api_keys="k",
        db_host="192.168.1.10",
        db_port=5433,
        db_password="p@ss/word",  # 特殊字符需 URL 编码
        redis_host="192.168.1.11",
        redis_port=6380,
    )
    assert s.database_url == (
        "postgresql+psycopg://hotmonitor:p%40ss%2Fword@192.168.1.10:5433/hotmonitor"
    )
    assert s.redis_url == "redis://192.168.1.11:6380/0"


def test_explicit_url_wins_over_components(clean_env):
    s = _make(
        api_keys="k",
        database_url="sqlite:///./explicit.db",
        redis_url="redis://other:6379/2",
        db_host="ignored",
    )
    assert s.database_url == "sqlite:///./explicit.db"
    assert s.redis_url == "redis://other:6379/2"


def test_production_requires_explicit_urls(clean_env):
    with pytest.raises(ValueError, match="生产环境"):
        _make(api_keys="k", app_env="production")
    with pytest.raises(ValueError, match="生产环境"):
        _make(api_keys="k", app_env="production", database_url="postgresql+psycopg://u:p@pg:5432/db")

    s = _make(
        api_keys="k",
        app_env="production",
        database_url="postgresql+psycopg://u:p@pg:5432/db",
        redis_url="redis://redis:6379/0",
    )
    assert s.database_url.endswith("@pg:5432/db")
