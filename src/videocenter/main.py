import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from videocenter.api.exception_handlers import register_exception_handlers
from videocenter.api.middleware import RequestContextMiddleware
from videocenter.api.router import api_router
from videocenter.core.config import get_settings
from videocenter.core.logging import configure_logging
from videocenter.schemas.error import STANDARD_ERROR_RESPONSES
from videocenter.services.downloads import restore_download_queue

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.media_root.mkdir(parents=True, exist_ok=True)
    restored_downloads = restore_download_queue()
    logger.info(
        "Download queue recovery completed",
        extra={
            "download_event": "recovery_completed",
            "restored_download_count": restored_downloads,
        },
    )
    logger.info("Application started")
    yield
    logger.info("Application stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="私人影视资源管理、下载与播放服务",
    debug=settings.debug,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    responses=STANDARD_ERROR_RESPONSES,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app, settings)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str | None]:
    return {
        "name": settings.app_name,
        "environment": settings.environment.value,
        "docs": "/docs" if settings.docs_enabled else None,
    }
