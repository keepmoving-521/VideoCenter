from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.schemas.parsing import (
    ParseConfirmRequest,
    ParseConfirmResponse,
    ParsePreviewRequest,
    ParsePreviewResponse,
    ParseSaveRequest,
    ParseSaveResponse,
)
from videocenter.services.background_tasks import (
    complete_resource_parse_background_task,
    create_resource_parse_background_task,
    fail_resource_parse_background_task,
)
from videocenter.services.parse_persistence import save_parse_result
from videocenter.services.parse_workflow import (
    ParseWorkflowStore,
    parse_workflow_store,
)
from videocenter.services.parsers import (
    ParserRegistry,
    create_default_parser_registry,
)

router = APIRouter()
parser_registry = create_default_parser_registry()


def get_parser_registry() -> ParserRegistry:
    return parser_registry


def get_parse_workflow_store() -> ParseWorkflowStore:
    return parse_workflow_store


@router.post(
    "/preview",
    response_model=ParsePreviewResponse,
    tags=["资源解析"],
)
async def preview_resource_page(
    payload: ParsePreviewRequest,
    db: Session = Depends(get_db),
    registry: ParserRegistry = Depends(get_parser_registry),
    store: ParseWorkflowStore = Depends(get_parse_workflow_store),
):
    parse_task_id = uuid4().hex
    source_url = str(payload.source_url)
    background_task = create_resource_parse_background_task(
        db,
        parse_task_id=parse_task_id,
        source_url=source_url,
        preferred_language=payload.preferred_language,
    )
    try:
        result = await registry.parse_url(
            source_url,
            preferred_language=payload.preferred_language,
            task_id=parse_task_id,
        )
    except Exception as exc:
        fail_resource_parse_background_task(db, background_task, exc)
        raise
    complete_resource_parse_background_task(
        db,
        background_task,
        title=result.title,
        source_site=result.source_site,
        downloads_detected=len(result.downloads)
        + sum(len(episode.downloads) for season in result.seasons for episode in season.episodes),
        subtitles_detected=sum(
            download.resource_type.value == "subtitle" for download in result.downloads
        )
        + sum(
            download.resource_type.value == "subtitle"
            for season in result.seasons
            for episode in season.episodes
            for download in episode.downloads
        ),
    )
    preview_id, expires_at = store.create_preview(result)
    return ParsePreviewResponse(
        parse_task_id=parse_task_id,
        background_task_id=background_task.id,
        preview_id=preview_id,
        expires_at=expires_at,
        result=result,
    )


@router.post(
    "/confirm",
    response_model=ParseConfirmResponse,
    tags=["资源解析"],
)
def confirm_parse_result(
    payload: ParseConfirmRequest,
    store: ParseWorkflowStore = Depends(get_parse_workflow_store),
):
    confirmation_id, expires_at = store.confirm(
        payload.preview_id,
        payload.result,
    )
    return ParseConfirmResponse(
        confirmation_id=confirmation_id,
        expires_at=expires_at,
        result=payload.result,
    )


@router.post(
    "/save",
    response_model=ParseSaveResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["资源解析"],
)
def save_confirmed_parse_result(
    payload: ParseSaveRequest,
    db: Session = Depends(get_db),
    store: ParseWorkflowStore = Depends(get_parse_workflow_store),
):
    result = store.consume_confirmation(payload.confirmation_id)
    try:
        media, stats = save_parse_result(db, result)
    except Exception:
        db.rollback()
        store.restore_confirmation(payload.confirmation_id, result)
        raise
    return ParseSaveResponse(
        media_id=media.id,
        title=media.title,
        **stats,
    )
