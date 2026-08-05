"""鉴权测试（FR-7.1）：无凭据/错误凭据一律 401。"""

from fastapi.testclient import TestClient

from tests.conftest import AUTH


def test_missing_key_401(client: TestClient):
    assert client.get("/api/keywords").status_code == 401
    assert client.get("/api/hotspots").status_code == 401
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/sources/health").status_code == 401


def test_wrong_key_401(client: TestClient):
    r = client.get("/api/keywords", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_valid_key_200(client: TestClient):
    assert client.get("/api/keywords", headers=AUTH).status_code == 200


def test_health_open(client: TestClient):
    assert client.get("/api/health").status_code == 200
