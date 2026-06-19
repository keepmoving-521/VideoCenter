from fastapi import APIRouter

from videocenter.api.routes import downloads, health, history, local_resources, media, streaming

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(media.router, prefix="/media", tags=["影视库"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["下载管理"])
api_router.include_router(local_resources.router, prefix="/local-resources", tags=["本地资源"])
api_router.include_router(streaming.router, prefix="/stream", tags=["在线播放"])
api_router.include_router(history.router, prefix="/history", tags=["观看历史"])
