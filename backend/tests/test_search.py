"""同步搜索接口测试（FR-3.1）：Bing 命中 + Twitter 无 Key 跳过，结果不落库。"""

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


def test_search_aggregates_and_skips_db(client: TestClient):
    with respx.mock:
        respx.get("https://www.bing.com/search").mock(
            return_value=Response(200, text=BING_HTML)
        )
        r = client.post("/api/search", json={"query": "Kimi"}, headers=AUTH)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["title"] == "Kimi 搜索结果一"
    assert items[0]["ai_reviewed"] is True  # 降级 Provider 也产出分析字段

    # 搜索结果不落库（FR-3.1 验收）
    with Session(engine) as session:
        total = session.exec(select(func.count()).select_from(Hotspot)).one()
    assert total == 0


def test_search_blank_query(client: TestClient):
    r = client.post("/api/search", json={"query": "  "}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == []
