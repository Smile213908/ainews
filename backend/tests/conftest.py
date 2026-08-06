"""pytest 基线：临时文件 SQLite + 测试 API Key。

说明：流水线/源健康等内部组件直接用 app.db.engine 写库（不经 dependency override），
内存 SQLite 多连接不共享，故测试库用临时文件而非 :memory:。
"""

import os
import tempfile

_tmp_db = os.path.join(tempfile.gettempdir(), "hotmonitor_test.db")
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)

os.environ["API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app

AUTH = {"X-API-Key": "test-key"}


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
