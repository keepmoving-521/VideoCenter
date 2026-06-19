from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from videocenter.api.exception_handlers import register_exception_handlers
from videocenter.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from videocenter.core.config import AppEnvironment, Settings
from videocenter.core.exceptions import NotFoundError


def create_test_app(*, debug_details: bool = False) -> FastAPI:
    settings = Settings(
        environment=AppEnvironment.DEVELOPMENT,
        debug=debug_details,
        log_file_enabled=False,
        _env_file=None,
    )
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app, settings)

    @app.get("/business-error")
    def business_error():
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")

    @app.get("/http-error")
    def http_error():
        raise HTTPException(status_code=403, detail="无权访问")

    @app.get("/validation")
    def validation(limit: int = Query(ge=1)):
        return {"limit": limit}

    @app.get("/database-error")
    def database_error():
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    @app.get("/unexpected-error")
    def unexpected_error():
        raise RuntimeError("sensitive internal detail")

    return app


def test_business_exception_uses_stable_error_code():
    with TestClient(create_test_app()) as client:
        response = client.get("/business-error")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"] == {
        "code": "MEDIA_NOT_FOUND",
        "message": "影视条目不存在",
        "details": None,
    }
    assert payload["meta"]["path"] == "/business-error"
    assert payload["meta"]["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_http_exception_is_normalized():
    with TestClient(create_test_app()) as client:
        response = client.get("/http-error")

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "HTTP_403",
        "message": "无权访问",
        "details": None,
    }


def test_validation_exception_contains_field_details():
    with TestClient(create_test_app()) as client:
        response = client.get("/validation", params={"limit": 0})

    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "请求参数校验失败"
    assert payload["details"][0]["loc"] == ["query", "limit"]


def test_database_exception_hides_internal_details():
    with TestClient(create_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/database-error")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "DATABASE_ERROR",
        "message": "数据库操作失败",
        "details": None,
    }


def test_unexpected_exception_hides_details_by_default():
    with TestClient(create_test_app(), raise_server_exceptions=False) as client:
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "服务器内部错误",
        "details": None,
    }


def test_debug_mode_exposes_unexpected_exception_details():
    with TestClient(create_test_app(debug_details=True), raise_server_exceptions=False) as client:
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"]["details"] == "sensitive internal detail"


def test_valid_client_request_id_is_preserved():
    request_id = "client-request-123"
    with TestClient(create_test_app()) as client:
        response = client.get(
            "/business-error",
            headers={REQUEST_ID_HEADER: request_id},
        )

    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert response.json()["meta"]["request_id"] == request_id


def test_invalid_client_request_id_is_replaced():
    with TestClient(create_test_app()) as client:
        response = client.get(
            "/business-error",
            headers={REQUEST_ID_HEADER: "bad"},
        )

    generated_id = response.headers[REQUEST_ID_HEADER]
    assert generated_id != "bad"
    assert len(generated_id) == 32
