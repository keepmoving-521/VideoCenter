from fastapi.testclient import TestClient

from videocenter.api.routes.health import health
from videocenter.main import app


def test_health():
    assert health() == {"status": "ok"}


def test_health_route_is_registered():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
