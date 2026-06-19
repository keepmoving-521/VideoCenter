from videocenter.api.routes.health import health
from videocenter.main import app


def test_health():
    assert health() == {"status": "ok"}


def test_health_route_is_registered():
    assert "/api/v1/health" in {route.path for route in app.routes}
