"""业务 API 测试：关键词 CRUD（FR-1）、热点筛选排序分页（FR-2）、通知（FR-4）。"""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Hotspot, Keyword, Notification
from app.scoring import calc_hot_score, importance_rank
from tests.conftest import AUTH


def _mk_hotspot(session: Session, **kw) -> Hotspot:
    hs = Hotspot(
        title=kw.get("title", "t"),
        url=kw.get("url", f"https://example.com/{uuid4()}"),
        source=kw.get("source", "bing"),
        importance=kw.get("importance", "low"),
        relevance=kw.get("relevance", 80),
        like_count=kw.get("like_count"),
        retweet_count=kw.get("retweet_count"),
        view_count=kw.get("view_count"),
        keyword_id=kw.get("keyword_id"),
    )
    hs.hot_score = calc_hot_score(hs.like_count, hs.retweet_count, hs.view_count)
    hs.importance_rank = importance_rank(hs.importance)
    session.add(hs)
    session.commit()
    session.refresh(hs)
    return hs


# ---------- 关键词 ----------
def test_keyword_create_blank_rejected(client: TestClient):
    assert client.post("/api/keywords", json={"text": "   "}, headers=AUTH).status_code == 422


def test_keyword_create_duplicate_409(client: TestClient):
    r1 = client.post("/api/keywords", json={"text": "DeepSeek"}, headers=AUTH)
    assert r1.status_code == 201
    r2 = client.post("/api/keywords", json={"text": "DeepSeek"}, headers=AUTH)
    assert r2.status_code == 409


def test_keyword_toggle_and_list_count(client: TestClient, session: Session):
    kw = Keyword(text="AI  Agent")
    session.add(kw)
    session.commit()
    session.refresh(kw)
    _mk_hotspot(session, keyword_id=kw.id)

    r = client.patch(f"/api/keywords/{kw.id}/toggle", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r = client.get("/api/keywords", headers=AUTH)
    item = next(k for k in r.json() if k["id"] == str(kw.id))
    assert item["hotspot_count"] == 1


def test_keyword_delete_keeps_hotspots(client: TestClient, session: Session):
    kw = Keyword(text="OpenAI")
    session.add(kw)
    session.commit()
    session.refresh(kw)
    hs = _mk_hotspot(session, keyword_id=kw.id)

    assert client.delete(f"/api/keywords/{kw.id}", headers=AUTH).status_code == 204
    session.refresh(hs)
    assert hs.keyword_id is None  # 热点保留，关联置空（FR-1.4）


# ---------- 热点 ----------
def test_hotspot_sort_importance(client: TestClient, session: Session):
    _mk_hotspot(session, importance="low", title="低")
    _mk_hotspot(session, importance="urgent", title="急")
    _mk_hotspot(session, importance="high", title="高")

    r = client.get("/api/hotspots?sort=importance", headers=AUTH)
    titles = [i["title"] for i in r.json()["items"]]
    assert titles == ["急", "高", "低"]  # R-402


def test_hotspot_sort_hot_uses_precomputed(client: TestClient, session: Session):
    _mk_hotspot(session, title="冷", like_count=1, view_count=10)
    _mk_hotspot(session, title="爆", like_count=10000, retweet_count=5000, view_count=10**7)

    r = client.get("/api/hotspots?sort=hot", headers=AUTH)
    items = r.json()["items"]
    assert items[0]["title"] == "爆"
    assert items[0]["hot_score_normalized"] >= 80
    assert items[0]["hot_level"] == "爆"  # R-403


def test_hotspot_filters_and_pagination(client: TestClient, session: Session):
    for _ in range(25):
        _mk_hotspot(session, source="bing", importance="medium")
    _mk_hotspot(session, source="weibo", importance="urgent")

    r = client.get("/api/hotspots?source=weibo", headers=AUTH)
    assert r.json()["total"] == 1

    r = client.get("/api/hotspots?page=2&page_size=20", headers=AUTH)
    body = r.json()
    assert body["total"] == 26
    assert body["total_pages"] == 2
    assert len(body["items"]) == 6


def test_hotspot_stats(client: TestClient, session: Session):
    _mk_hotspot(session, source="bilibili", importance="urgent")
    _mk_hotspot(session, source="bilibili")

    r = client.get("/api/hotspots/stats", headers=AUTH)
    body = r.json()
    assert body["total"] == 2
    assert body["today_new"] == 2
    assert body["urgent_count"] == 1
    assert body["by_source"]["bilibili"] == 2


def test_hotspot_delete(client: TestClient, session: Session):
    hs = _mk_hotspot(session)
    assert client.delete(f"/api/hotspots/{hs.id}", headers=AUTH).status_code == 204
    assert client.delete(f"/api/hotspots/{hs.id}", headers=AUTH).status_code == 404


# ---------- 通知 ----------
def test_notification_flow(client: TestClient, session: Session):
    n1 = Notification(type="hotspot", title="新热点")
    n2 = Notification(type="alert", title="源失效")
    session.add(n1)
    session.add(n2)
    session.commit()
    session.refresh(n1)

    r = client.get("/api/notifications/unread-count", headers=AUTH)
    assert r.json()["unread"] == 2

    r = client.patch(f"/api/notifications/{n1.id}/read", headers=AUTH)
    assert r.json()["is_read"] is True

    r = client.post("/api/notifications/read-all", headers=AUTH)
    assert r.json()["updated"] == 1

    assert client.delete(f"/api/notifications/{n1.id}", headers=AUTH).status_code == 204
    assert client.post("/api/notifications/clear", headers=AUTH).status_code == 204
    assert client.get("/api/notifications", headers=AUTH).json() == []
