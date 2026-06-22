from fastapi import APIRouter

from videocenter.api.routes import (
    catalog,
    downloads,
    health,
    history,
    local_resources,
    media,
    media_directories,
    notifications,
    parsing,
    streaming,
    system,
    tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router, prefix="/system", tags=["系统"])
api_router.include_router(parsing.router, prefix="/parsing")
api_router.include_router(catalog.router)
api_router.include_router(media.router, prefix="/media", tags=["影视库"])
api_router.include_router(
    media_directories.router,
    prefix="/media-directories",
    tags=["媒体目录"],
)
api_router.include_router(downloads.router, prefix="/downloads", tags=["下载管理"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
api_router.include_router(local_resources.router, prefix="/local-resources", tags=["本地资源"])
api_router.include_router(streaming.router, prefix="/stream", tags=["在线播放"])
api_router.include_router(history.router, prefix="/history", tags=["观看历史"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["后台任务"])
