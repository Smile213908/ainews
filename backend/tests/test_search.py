"""异步搜索任务测试（FR-3.2）：提交 ≤1s 受理、轮询取结果、不落库、空词 422。"""

import time

import respx
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, func, select

from app.db import engine
from app.models import Hotspot
from tests.conftest import AUTH

BING_HTML = """
<html><body><ol id="b_results">
  <li class="b_algo"><h2><a href="https://example.com/s1">Kimi 搜索结果一</a></h2>
    <div class="b_caption"><p>摘要一</p></div></li>
</ol></body></html>
"""


def test_search_async_task_lifecycle(client: TestClient):
    with respx.mock:
        respx.get("https://www.bing.com/search").mock(
            return_value=Response(200, text=BING_HTML)
        )
        started = time.time()
        r = client.post("/api/search", json={"query": "Kimi"}, headers=AUTH)
        elapsed = time.time() - started

        assert r.status_code == 202
        assert elapsed < 1.0  # 提交受理 ≤1s（FR-3.2）
        task_id = r.json()["task_id"]

        # 轮询任务状态直到完成（mock 需覆盖后台任务执行期间）
        result = None
        for _ in range(50):
            r = client.get(f"/api/search/{task_id}", headers=AUTH)
            body = r.json()
            if body["status"] in ("completed", "failed"):
                result = body
                break
            time.sleep(0.1)

    assert result is not None
    assert result["status"] == "completed"
    assert result["result"][0]["title"] == "Kimi 搜索结果一"
    assert result["result"][0]["ai_reviewed"] is True

    # 搜索结果不落库（FR-3.1）
    with Session(engine) as session:
        total = session.exec(select(func.count()).select_from(Hotspot)).one()
    assert total == 0


def test_search_blank_query_422(client: TestClient):
    r = client.post("/api/search", json={"query": "  "}, headers=AUTH)
    assert r.status_code == 422


def test_search_task_not_found(client: TestClient):
    r = client.get("/api/search/nonexistent", headers=AUTH)
    assert r.status_code == 404
