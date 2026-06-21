from dataclasses import asdict
from pathlib import Path

from videocenter.models.media import LocalResource
from videocenter.services.local_file_hashes import calculate_sha256
from videocenter.services.media_artwork import generate_video_artwork
from videocenter.services.media_probe import VideoMediaInfo, probe_video_file


def analyze_local_resource(
    resource: LocalResource,
    *,
    force: bool = False,
) -> str:
    if not force and resource.media_info_probed and resource.visual_assets_generated is not None:
        return "skipped"

    path = Path(resource.file_path)
    if not path.is_file():
        return "missing"

    if resource.checksum_sha256 is None:
        resource.checksum_sha256 = calculate_sha256(path)
    media_info = probe_video_file(path)
    _apply_media_info(resource, media_info)
    artwork = generate_video_artwork(
        path,
        checksum_sha256=resource.checksum_sha256,
        duration_seconds=media_info.duration_seconds if media_info else None,
    )
    resource.visual_assets_generated = artwork is not None
    resource.cover_image_path = artwork.cover_image_path if artwork else None
    resource.preview_thumbnail_paths = list(artwork.preview_thumbnail_paths) if artwork else []
    return "analyzed"


def _apply_media_info(
    resource: LocalResource,
    media_info: VideoMediaInfo | None,
) -> None:
    resource.media_info_probed = True
    resource.duration_seconds = media_info.duration_seconds if media_info else None
    resource.video_width = media_info.width if media_info else None
    resource.video_height = media_info.height if media_info else None
    resource.video_codec = media_info.video_codec if media_info else None
    resource.bitrate = media_info.bitrate if media_info else None
    resource.audio_codec = media_info.audio_codec if media_info else None
    resource.audio_tracks = (
        [asdict(track) for track in media_info.audio_tracks] if media_info else []
    )
    resource.embedded_subtitles = (
        [asdict(track) for track in media_info.subtitle_tracks] if media_info else []
    )
