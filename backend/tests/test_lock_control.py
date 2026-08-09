"""分布式锁、源健康告警、手动触发接口测试（R-102/R-303/FR-7.2）。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core import source_health
from app.core.redis import acquire_lock, release_lock
from app.db import engine
from app.models import Notification, SourceHealth
from app.pipeline.hotspot_check import progress
from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_lock_mutual_exclusion():
    assert await acquire_lock("test_lock", 60, "token-a") is True
    assert await acquire_lock("test_lock", 60, "token-b") is False  # 互斥
    await release_lock("test_lock", "token-a")
    assert await acquire_lock("test_lock", 60, "token-b") is True
    await release_lock("test_lock", "token-b")


def test_source_health_alert_after_3_failures():
    source_health.record_success("test_source")
    for i in range(3):
        triggered = source_health.record_failure("test_source", f"错误 {i}")
    assert triggered is True  # 第 3 次失败触发告警（R-303）

    with Session(engine) as session:
        health = session.get(SourceHealth, "test_source")
        assert health.consecutive_failures == 3
        assert health.alert_open is True
        alerts = session.exec(
            select(Notification).where(Notification.type == "alert")
        ).all()
        assert any("test_source" in a.title for a in alerts)

    # 恢复前不重复告警（FR-6.2）
    assert source_health.record_failure("test_source", "又挂了") is False
    # 成功后清零复位
    source_health.record_success("test_source")
    with Session(engine) as session:
        health = session.get(SourceHealth, "test_source")
        assert health.consecutive_failures == 0
        assert health.alert_open is False


def test_manual_trigger_and_status(client: TestClient):
    r = client.post("/api/check-hotspots", headers=AUTH)
    assert r.status_code == 202
    r = client.get("/api/check-hotspots/status", headers=AUTH)
    assert r.status_code == 200
    assert "running" in r.json()


def test_status_includes_reports(client: TestClient):
    """进度弹窗契约：status 返回本轮逐词报告（含 keyword_id 供点击查看）。"""
    progress.reports = [
        {
            "keyword": "AI",
            "keyword_id": "00000000-0000-0000-0000-000000000001",
            "collected": 10,
            "candidates": 5,
            "analyzed": 4,
            "created": 2,
            "errors": [],
        }
    ]
    try:
        r = client.get("/api/check-hotspots/status", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["reports"][0]["keyword"] == "AI"
        assert body["reports"][0]["keyword_id"]
        assert body["reports"][0]["created"] == 2
    finally:
        progress.reports = []


def test_manual_trigger_conflict_409(client: TestClient):
    progress.running = True
    progress.total_keywords = 5
    progress.done_keywords = 2
    try:
        r = client.post("/api/check-hotspots", headers=AUTH)
        assert r.status_code == 409
        assert "检查进行中" in str(r.json()["detail"])
    finally:
        progress.running = False


def test_settings_runtime_config(client: TestClient):
    r = client.get("/api/settings", headers=AUTH)
    assert r.json()["twitter_quota"] == "15"  # 默认值

    r = client.put("/api/settings/twitter_quota", json={"value": "8"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["value"] == "8"

    r = client.put("/api/settings/unknown_key", json={"value": "1"}, headers=AUTH)
    assert r.status_code == 404


def test_sources_health_api(client: TestClient, session: Session):
    session.add(SourceHealth(source="hackernews", consecutive_failures=0))
    session.commit()
    r = client.get("/api/sources/health", headers=AUTH)
    assert r.status_code == 200
    sources = {s["source"] for s in r.json()}
    assert "hackernews" in sources


def test_keyword_check_trigger(client: TestClient, session: Session, monkeypatch):
    from app.models import Keyword
    from app.routers import control

    async def _dummy_check(keyword_id, trigger="manual"):
        return {"ok": True, "hotspots_created": 0}

    # 只测路由层（202/409/404），不真的启动后台采集任务，避免测试间互相干扰
    monkeypatch.setattr(control, "run_single_keyword_check", _dummy_check)

    kw = Keyword(text="单关键词测试", is_active=True)
    session.add(kw)
    session.commit()
    session.refresh(kw)

    r = client.post(f"/api/keywords/{kw.id}/check", headers=AUTH)
    assert r.status_code == 202

    # 关键词不存在 → 404
    from uuid import uuid4

    r = client.post(f"/api/keywords/{uuid4()}/check", headers=AUTH)
    assert r.status_code == 404

    # 锁占用时冲突 409
    progress.running = True
    try:
        r = client.post(f"/api/keywords/{kw.id}/check", headers=AUTH)
        assert r.status_code == 409
    finally:
        progress.running = False
