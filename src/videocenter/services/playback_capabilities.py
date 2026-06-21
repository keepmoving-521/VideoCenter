from dataclasses import dataclass
from enum import StrEnum
from math import gcd
from pathlib import Path

from videocenter.models.media import LocalResource


class BrowserSupportStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BrowserCompatibility:
    browser_family: str
    container: str | None
    status: BrowserSupportStatus
    direct_play: bool
    can_play_type: str
    reason: str
    recommended_action: str


def video_quality_label(width: int | None, height: int | None) -> str | None:
    if height is None:
        return None
    if height >= 4320:
        return "8K"
    if height >= 2160:
        return "4K"
    for threshold in (1440, 1080, 720, 576, 480, 360, 240):
        if height >= threshold:
            return f"{threshold}p"
    return f"{height}p"


def aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def evaluate_browser_compatibility(
    resource: LocalResource,
    user_agent: str | None,
) -> BrowserCompatibility:
    browser = _browser_family(user_agent)
    container = Path(resource.file_name).suffix.casefold().removeprefix(".") or None
    video_codec = _normalize_video_codec(resource.video_codec)
    audio_codec = _normalize_audio_codec(resource.audio_codec)

    if container in {"mp4", "m4v"} and video_codec == "h264":
        if audio_codec in {None, "aac", "mp3"}:
            return _result(browser, container, BrowserSupportStatus.SUPPORTED, "标准 MP4/H.264")
        return _result(
            browser,
            container,
            BrowserSupportStatus.UNKNOWN,
            f"视频兼容，但音频编码 {audio_codec} 需要浏览器实际探测",
        )

    if container == "webm" and video_codec in {"vp8", "vp9"}:
        if browser in {"chrome", "edge", "firefox"} and audio_codec in {
            None,
            "opus",
            "vorbis",
        }:
            return _result(
                browser,
                container,
                BrowserSupportStatus.SUPPORTED,
                f"{browser} 支持 WebM/{video_codec}",
            )
        return _result(
            browser,
            container,
            BrowserSupportStatus.UNKNOWN,
            "WebM 支持取决于浏览器及音频编码",
        )

    if video_codec in {"hevc", "av1"}:
        return _result(
            browser,
            container,
            BrowserSupportStatus.UNKNOWN,
            f"{video_codec.upper()} 支持取决于浏览器、系统和硬件解码能力",
        )

    if container in {"mkv", "avi", "ts", "mov"}:
        return _result(
            browser,
            container,
            BrowserSupportStatus.UNSUPPORTED,
            f"浏览器通常不能直接播放 {container.upper()} 容器",
        )

    return _result(
        browser,
        container,
        BrowserSupportStatus.UNKNOWN,
        "缺少可靠的容器或编码兼容性信息",
    )


def _result(
    browser: str,
    container: str | None,
    status: BrowserSupportStatus,
    reason: str,
) -> BrowserCompatibility:
    return BrowserCompatibility(
        browser_family=browser,
        container=container,
        status=status,
        direct_play=status == BrowserSupportStatus.SUPPORTED,
        can_play_type=(
            "probably"
            if status == BrowserSupportStatus.SUPPORTED
            else ""
            if status == BrowserSupportStatus.UNSUPPORTED
            else "maybe"
        ),
        reason=reason,
        recommended_action=(
            "direct_play"
            if status == BrowserSupportStatus.SUPPORTED
            else "transcode"
            if status == BrowserSupportStatus.UNSUPPORTED
            else "client_probe"
        ),
    )


def _browser_family(user_agent: str | None) -> str:
    value = (user_agent or "").casefold()
    if "edg/" in value:
        return "edge"
    if "firefox/" in value:
        return "firefox"
    if "chrome/" in value or "crios/" in value:
        return "chrome"
    if "safari/" in value and "chrome/" not in value:
        return "safari"
    return "unknown"


def _normalize_video_codec(value: str | None) -> str | None:
    codec = (value or "").casefold()
    if codec in {"h264", "avc", "avc1"}:
        return "h264"
    if codec in {"hevc", "h265", "hev1", "hvc1"}:
        return "hevc"
    if codec in {"vp8", "vp9", "av1"}:
        return codec
    return codec or None


def _normalize_audio_codec(value: str | None) -> str | None:
    codec = (value or "").casefold()
    if codec in {"aac", "mp3", "opus", "vorbis"}:
        return codec
    return codec or None
