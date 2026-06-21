import pytest

from videocenter.services.playback_capabilities import (
    BrowserSupportStatus,
    aspect_ratio,
    evaluate_browser_compatibility,
    video_quality_label,
)


@pytest.mark.parametrize(
    ("height", "label"),
    [
        (4320, "8K"),
        (2160, "4K"),
        (1440, "1440p"),
        (1080, "1080p"),
        (720, "720p"),
        (480, "480p"),
        (200, "200p"),
        (None, None),
    ],
)
def test_video_quality_label(height, label):
    assert video_quality_label(1920, height) == label


def test_aspect_ratio_is_reduced():
    assert aspect_ratio(1920, 1080) == "16:9"
    assert aspect_ratio(720, 480) == "3:2"
    assert aspect_ratio(None, 1080) is None


def test_mp4_h264_aac_is_supported(model_factory):
    resource = model_factory.local_resource(
        file_name="movie.mp4",
        mime_type="video/mp4",
        video_codec="h264",
        audio_codec="aac",
    )

    result = evaluate_browser_compatibility(
        resource,
        "Mozilla/5.0 Chrome/125.0 Safari/537.36",
    )

    assert result.browser_family == "chrome"
    assert result.status == BrowserSupportStatus.SUPPORTED
    assert result.direct_play is True
    assert result.can_play_type == "probably"
    assert result.recommended_action == "direct_play"


def test_webm_vp9_opus_is_supported_by_firefox(model_factory):
    resource = model_factory.local_resource(
        file_name="movie.webm",
        mime_type="video/webm",
        video_codec="vp9",
        audio_codec="opus",
    )

    result = evaluate_browser_compatibility(resource, "Mozilla/5.0 Firefox/126.0")

    assert result.status == BrowserSupportStatus.SUPPORTED
    assert result.browser_family == "firefox"


def test_mkv_is_unsupported_and_hevc_is_unknown(model_factory):
    mkv = model_factory.local_resource(
        file_name="movie.mkv",
        video_codec="h264",
        audio_codec="aac",
    )
    hevc = model_factory.local_resource(
        file_name="movie.mp4",
        video_codec="hevc",
        audio_codec="aac",
    )

    assert (
        evaluate_browser_compatibility(mkv, "Mozilla/5.0 Chrome/125.0").status
        == BrowserSupportStatus.UNSUPPORTED
    )
    assert (
        evaluate_browser_compatibility(hevc, "Mozilla/5.0 Safari/17.0").status
        == BrowserSupportStatus.UNKNOWN
    )
