from fastapi.testclient import TestClient

from videocenter.api.routes.health import health


def test_health():
    assert health() == {"status": "ok"}


def test_health_route_is_registered(api_client: TestClient):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
