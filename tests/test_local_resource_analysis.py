from pathlib import Path

from videocenter.services.local_resource_analysis import analyze_local_resource
from videocenter.services.media_artwork import GeneratedVideoArtwork
from videocenter.services.media_probe import VideoMediaInfo


def test_analyze_local_resource_updates_media_info_and_artwork(
    model_factory,
    tmp_path: Path,
    monkeypatch,
):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    resource = model_factory.local_resource(
        file_path=str(video),
        checksum_sha256="a" * 64,
        media_info_probed=False,
        visual_assets_generated=None,
    )
    monkeypatch.setattr(
        "videocenter.services.local_resource_analysis.probe_video_file",
        lambda path: VideoMediaInfo(
            duration_seconds=90,
            width=1280,
            height=720,
            video_codec="h264",
            bitrate=4_000_000,
            audio_codec="aac",
        ),
    )
    monkeypatch.setattr(
        "videocenter.services.local_resource_analysis.generate_video_artwork",
        lambda path, **kwargs: GeneratedVideoArtwork(
            cover_image_path="cover.jpg",
            preview_thumbnail_paths=("preview.jpg",),
        ),
    )

    result = analyze_local_resource(resource)

    assert result == "analyzed"
    assert resource.duration_seconds == 90
    assert resource.video_width == 1280
    assert resource.audio_codec == "aac"
    assert resource.cover_image_path == "cover.jpg"
    assert resource.preview_thumbnail_paths == ["preview.jpg"]


def test_analyze_local_resource_skips_completed_unless_forced(
    model_factory,
    monkeypatch,
):
    resource = model_factory.local_resource(
        media_info_probed=True,
        visual_assets_generated=False,
    )
    called = False

    def probe(path):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "videocenter.services.local_resource_analysis.probe_video_file",
        probe,
    )

    assert analyze_local_resource(resource) == "skipped"
    assert called is False


def test_analyze_local_resource_reports_missing_file(model_factory):
    resource = model_factory.local_resource(
        file_path=str(Path("data/media/not-found-analysis.mp4").resolve()),
        media_info_probed=False,
        visual_assets_generated=None,
    )

    assert analyze_local_resource(resource) == "missing"
