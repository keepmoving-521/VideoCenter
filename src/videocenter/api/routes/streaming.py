import subprocess
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import AppException, ConflictError, NotFoundError
from videocenter.models.hls import HlsTask
from videocenter.models.media import LocalResource
from videocenter.schemas.history import HistoryRead, PlaybackProgressUpdate
from videocenter.schemas.hls import (
    HlsCacheCleanupRequest,
    HlsCacheCleanupResult,
    HlsTaskRead,
)
from videocenter.schemas.streaming import (
    PlaybackAudioTrackList,
    PlaybackBrowserCompatibility,
    PlaybackResourceDetail,
    PlaybackSubtitle,
    PlaybackSubtitleList,
    PlaybackVideoQuality,
)
from videocenter.services.downloads import update_media_download_status
from videocenter.services.hls import (
    cleanup_hls_cache,
    create_or_reuse_hls_task,
    hls_playlist_path,
    hls_segment_path,
    start_hls_task,
)
from videocenter.services.playback_capabilities import (
    aspect_ratio,
    evaluate_browser_compatibility,
    video_quality_label,
)
from videocenter.services.streaming import (
    ByteRange,
    is_not_modified,
    iter_file_range,
    parse_range_header,
)
from videocenter.services.subtitles import (
    discover_external_subtitles,
    get_external_subtitle,
    subtitle_as_webvtt,
)
from videocenter.services.watch_history import save_watch_history

router = APIRouter()
CACHE_CONTROL = "private, max-age=3600, no-transform"


@router.post(
    "/{resource_id}/hls",
    response_model=HlsTaskRead,
    status_code=202,
)
def create_hls_transcoding_task(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    if not Path(resource.file_path).is_file():
        _mark_resource_missing(db, resource)
        raise NotFoundError("视频文件已丢失", code="VIDEO_FILE_MISSING")
    task = create_or_reuse_hls_task(db, resource)
    if task.status.value == "waiting":
        start_hls_task(task.id)
    return HlsTaskRead.from_task(task)


@router.get("/hls-tasks/{task_id}", response_model=HlsTaskRead)
def get_hls_task(
    task_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(HlsTask, task_id)
    if task is None:
        raise NotFoundError("HLS 转码任务不存在", code="HLS_TASK_NOT_FOUND")
    return HlsTaskRead.from_task(task)


@router.post("/hls/cache/cleanup", response_model=HlsCacheCleanupResult)
def cleanup_hls_transcoding_cache(
    payload: HlsCacheCleanupRequest,
    db: Session = Depends(get_db),
):
    task_ids, directory_count, reclaimed_bytes = cleanup_hls_cache(
        db,
        max_age_hours=payload.max_age_hours,
    )
    return HlsCacheCleanupResult(
        cleaned_task_count=len(task_ids),
        cleaned_task_ids=task_ids,
        removed_directory_count=directory_count,
        reclaimed_bytes=reclaimed_bytes,
    )


@router.get("/hls/{task_id}/index.m3u8")
def get_hls_playlist(
    task_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(HlsTask, task_id)
    if task is None:
        raise NotFoundError("HLS 转码任务不存在", code="HLS_TASK_NOT_FOUND")
    return FileResponse(
        hls_playlist_path(task),
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "private, max-age=60, no-transform"},
    )


@router.get("/hls/{task_id}/segments/{segment_name}")
def get_hls_segment(
    task_id: Annotated[int, ApiPath(gt=0)],
    segment_name: Annotated[str, ApiPath(min_length=1, max_length=128)],
    db: Session = Depends(get_db),
):
    task = db.get(HlsTask, task_id)
    if task is None:
        raise NotFoundError("HLS 转码任务不存在", code="HLS_TASK_NOT_FOUND")
    return FileResponse(
        hls_segment_path(task, segment_name),
        media_type="video/mp2t",
        headers={"Cache-Control": "private, max-age=86400, immutable, no-transform"},
    )


@router.get("/{resource_id}")
def stream_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=512),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match", max_length=512),
    ] = None,
    if_modified_since: Annotated[
        str | None,
        Header(alias="If-Modified-Since", max_length=128),
    ] = None,
    db: Session = Depends(get_db),
):
    resource, path, file_size, byte_range, headers, not_modified = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    if not_modified:
        return Response(status_code=304, headers=headers)

    if byte_range is None:
        return FileResponse(path, media_type=resource.mime_type, headers=headers)

    return StreamingResponse(
        iter_file_range(str(path), byte_range),
        status_code=206,
        media_type=resource.mime_type,
        headers={
            **headers,
            "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{file_size}",
            "Content-Length": str(byte_range.length),
        },
    )


@router.head("/{resource_id}")
def head_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=512),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match", max_length=512),
    ] = None,
    if_modified_since: Annotated[
        str | None,
        Header(alias="If-Modified-Since", max_length=128),
    ] = None,
    db: Session = Depends(get_db),
):
    resource, _, file_size, byte_range, headers, not_modified = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    if not_modified:
        return Response(status_code=304, headers=headers)
    if byte_range is None:
        headers["Content-Length"] = str(file_size)
        return Response(status_code=200, media_type=resource.mime_type, headers=headers)
    headers.update(
        {
            "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{file_size}",
            "Content-Length": str(byte_range.length),
        }
    )
    return Response(status_code=206, media_type=resource.mime_type, headers=headers)


@router.get("/{resource_id}/details", response_model=PlaybackResourceDetail)
def get_playback_resource_detail(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    file_exists = Path(resource.file_path).is_file()
    if not file_exists:
        _mark_resource_missing(db, resource)
    base_url = f"/api/v1/stream/{resource.id}"
    return PlaybackResourceDetail(
        resource=resource,
        playable=file_exists and resource.is_available,
        file_exists=file_exists,
        stream_url=base_url,
        head_url=base_url,
        cover_url=(
            f"/api/v1/local-resources/{resource.id}/cover" if resource.cover_image_path else None
        ),
        preview_urls=[
            f"/api/v1/local-resources/{resource.id}/previews/{index}"
            for index in range(len(resource.preview_thumbnail_paths))
        ],
        subtitles_url=f"/api/v1/stream/{resource.id}/subtitles",
        audio_tracks_url=f"/api/v1/stream/{resource.id}/audio-tracks",
        quality_url=f"/api/v1/stream/{resource.id}/quality",
        compatibility_url=f"/api/v1/stream/{resource.id}/compatibility",
        hls_task_create_url=f"/api/v1/stream/{resource.id}/hls",
        progress_url=f"/api/v1/stream/{resource.id}/progress",
        supports_range=True,
        cache_control=CACHE_CONTROL,
    )


@router.put("/{resource_id}/progress", response_model=HistoryRead)
def save_playback_progress(
    resource_id: Annotated[int, ApiPath(gt=0)],
    payload: PlaybackProgressUpdate,
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    if resource.media_id is None:
        raise ConflictError(
            "本地资源尚未关联影视条目，无法保存播放进度",
            code="RESOURCE_NOT_ASSOCIATED",
        )
    duration_seconds = (
        payload.duration_seconds
        if payload.duration_seconds is not None
        else resource.duration_seconds
    )
    if duration_seconds is not None and payload.position_seconds > duration_seconds:
        raise AppException(
            "播放位置不能超过视频总时长",
            code="PLAYBACK_POSITION_EXCEEDS_DURATION",
            status_code=422,
        )
    return save_watch_history(
        db,
        media_id=resource.media_id,
        resource_id=resource.id,
        position_seconds=payload.position_seconds,
        duration_seconds=duration_seconds,
    )


@router.get("/{resource_id}/audio-tracks", response_model=PlaybackAudioTrackList)
def list_playback_audio_tracks(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    default_track = next(
        (track for track in resource.audio_tracks if track.get("is_default")),
        None,
    )
    return PlaybackAudioTrackList(
        resource_id=resource.id,
        default_stream_index=default_track.get("stream_index") if default_track else None,
        tracks=resource.audio_tracks,
    )


@router.get("/{resource_id}/quality", response_model=PlaybackVideoQuality)
def get_playback_video_quality(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    return PlaybackVideoQuality(
        resource_id=resource.id,
        label=video_quality_label(resource.video_width, resource.video_height),
        width=resource.video_width,
        height=resource.video_height,
        aspect_ratio=aspect_ratio(resource.video_width, resource.video_height),
        pixel_count=(
            resource.video_width * resource.video_height
            if resource.video_width and resource.video_height
            else None
        ),
        bitrate=resource.bitrate,
        video_codec=resource.video_codec,
    )


@router.get(
    "/{resource_id}/compatibility",
    response_model=PlaybackBrowserCompatibility,
)
def get_browser_compatibility(
    resource_id: Annotated[int, ApiPath(gt=0)],
    user_agent: Annotated[
        str | None,
        Header(alias="User-Agent", max_length=1024),
    ] = None,
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    compatibility = evaluate_browser_compatibility(resource, user_agent)
    return PlaybackBrowserCompatibility(
        resource_id=resource.id,
        browser_family=compatibility.browser_family,
        container=compatibility.container,
        mime_type=resource.mime_type,
        video_codec=resource.video_codec,
        audio_codec=resource.audio_codec,
        status=compatibility.status,
        direct_play=compatibility.direct_play,
        can_play_type=compatibility.can_play_type,
        reason=compatibility.reason,
        recommended_action=compatibility.recommended_action,
    )


@router.get("/{resource_id}/subtitles", response_model=PlaybackSubtitleList)
def list_playback_subtitles(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    subtitles = [
        PlaybackSubtitle(
            subtitle_id=f"embedded-{item['stream_index']}",
            source="embedded",
            format=item.get("codec"),
            language=item.get("language"),
            title=item.get("title"),
            is_default=bool(item.get("is_default")),
            is_forced=bool(item.get("is_forced")),
            access_url=None,
        )
        for item in resource.embedded_subtitles
    ]
    subtitles.extend(
        PlaybackSubtitle(
            subtitle_id=subtitle.subtitle_id,
            source="external",
            format=subtitle.format,
            language=subtitle.language,
            title=subtitle.file_name,
            is_default=False,
            is_forced=False,
            access_url=(
                f"/api/v1/stream/{resource.id}/subtitles/{subtitle.subtitle_id}?format=webvtt"
            ),
        )
        for subtitle in discover_external_subtitles(Path(resource.file_path))
    )
    return PlaybackSubtitleList(resource_id=resource.id, subtitles=subtitles)


@router.get("/{resource_id}/subtitles/{subtitle_id}")
def get_external_subtitle_file(
    resource_id: Annotated[int, ApiPath(gt=0)],
    subtitle_id: Annotated[str, ApiPath(min_length=1, max_length=64)],
    format: str = "webvtt",
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    subtitle = get_external_subtitle(Path(resource.file_path), subtitle_id)
    if subtitle is None:
        raise NotFoundError("外挂字幕不存在", code="EXTERNAL_SUBTITLE_NOT_FOUND")
    if format not in {"webvtt", "original"}:
        raise AppException(
            "字幕输出格式仅支持 webvtt 或 original",
            code="INVALID_SUBTITLE_FORMAT",
            status_code=400,
        )
    if format == "original":
        media_type = {
            "vtt": "text/vtt",
            "srt": "application/x-subrip",
            "ass": "text/x-ssa",
            "ssa": "text/x-ssa",
        }.get(subtitle.format, "text/plain")
        return FileResponse(
            subtitle.path,
            media_type=media_type,
            headers={"Cache-Control": CACHE_CONTROL},
        )
    try:
        webvtt_path = subtitle_as_webvtt(subtitle)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise AppException(
            "字幕格式转换失败",
            code="SUBTITLE_CONVERSION_FAILED",
            status_code=422,
            details=str(exc),
        ) from exc
    return FileResponse(
        webvtt_path,
        media_type="text/vtt",
        headers={"Cache-Control": CACHE_CONTROL},
    )


def _prepare_video_response(
    db: Session,
    *,
    resource_id: int,
    range_header: str | None,
    if_none_match: str | None,
    if_modified_since: str | None,
) -> tuple[LocalResource, Path, int, ByteRange | None, dict[str, str], bool]:
    resource = db.get(LocalResource, resource_id)
    if not resource:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    path = Path(resource.file_path)
    if not path.is_file():
        _mark_resource_missing(db, resource)
        raise NotFoundError("视频文件已丢失", code="VIDEO_FILE_MISSING")

    stat = path.stat()
    file_size = stat.st_size
    try:
        byte_range = parse_range_header(range_header, file_size)
    except (ValueError, TypeError):
        raise AppException(
            "无效的 Range 请求",
            status_code=416,
            code="INVALID_BYTE_RANGE",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{file_size}",
            },
        ) from None
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": CACHE_CONTROL,
        "ETag": f'"{stat.st_mtime_ns:x}-{file_size:x}"',
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
    }
    not_modified = range_header is None and is_not_modified(
        etag=headers["ETag"],
        modified_at=stat.st_mtime,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    return resource, path, file_size, byte_range, headers, not_modified


def _mark_resource_missing(db: Session, resource: LocalResource) -> None:
    if resource.is_available or resource.missing_at is None:
        resource.is_available = False
        resource.missing_at = datetime.now()
        db.flush()
        update_media_download_status(db, resource.media_id)
        db.commit()


def _get_resource_or_404(db: Session, resource_id: int) -> LocalResource:
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    return resource
