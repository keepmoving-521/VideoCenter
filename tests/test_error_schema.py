from fastapi.testclient import TestClient

from videocenter.main import app


def test_openapi_uses_standard_error_response_schema():
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/media/{media_id}"]["get"]

    assert operation["responses"]["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert "ErrorResponse" in schema["components"]["schemas"]


def test_success_response_also_contains_request_id_header():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
