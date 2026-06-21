from fastapi import APIRouter

from videocenter.schemas.system import MediaToolsStatus
from videocenter.services.media_tools import detect_media_tools

router = APIRouter()


@router.get("/media-tools", response_model=MediaToolsStatus)
def get_media_tools_status():
    return detect_media_tools()
