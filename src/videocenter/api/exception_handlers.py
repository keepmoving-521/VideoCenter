import logging
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from videocenter.api.middleware import REQUEST_ID_HEADER
from videocenter.core.config import Settings
from videocenter.core.exceptions import AppException
from videocenter.schemas.error import ErrorDetail, ErrorMeta, ErrorResponse

logger = logging.getLogger(__name__)


def error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
        ),
        meta=ErrorMeta(
            request_id=request_id,
            timestamp=datetime.now(UTC),
            path=request.url.path,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers=response_headers,
    )


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request, exc: AppException
    ) -> JSONResponse:
        logger.warning(
            "Application error",
            extra={
                "error_code": exc.code,
                "status_code": exc.status_code,
                "request_method": request.method,
                "request_path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        return error_response(
            request=request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "Request validation failed",
            extra={
                "error_code": "VALIDATION_ERROR",
                "status_code": 422,
                "request_method": request.method,
                "request_path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        return error_response(
            request=request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            details=exc.errors(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else HTTPStatus(exc.status_code).phrase
        )
        details = None if isinstance(exc.detail, str) else exc.detail
        logger.warning(
            "HTTP error",
            extra={
                "error_code": f"HTTP_{exc.status_code}",
                "status_code": exc.status_code,
                "request_method": request.method,
                "request_path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        return error_response(
            request=request,
            status_code=exc.status_code,
            code=f"HTTP_{exc.status_code}",
            message=message,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_exception(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        logger.exception(
            "Database operation failed",
            extra={
                "error_code": "DATABASE_ERROR",
                "status_code": 500,
                "request_method": request.method,
                "request_path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        return error_response(
            request=request,
            status_code=500,
            code="DATABASE_ERROR",
            message="数据库操作失败",
            details=str(exc) if settings.debug else None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled application error",
            extra={
                "error_code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
                "request_method": request.method,
                "request_path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        return error_response(
            request=request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="服务器内部错误",
            details=str(exc) if settings.debug else None,
        )
