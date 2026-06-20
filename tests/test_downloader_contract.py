from pathlib import Path

import pytest

from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    Downloader,
    DownloadProgress,
    DownloadProgressState,
    DownloadRequest,
    DownloadResult,
)


class ExampleDownloader(Downloader):
    name = "example"

    def download(
        self,
        request: DownloadRequest,
        *,
        progress_callback=None,
        cancellation_token=None,
    ) -> DownloadResult:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    state=DownloadProgressState.DOWNLOADING,
                    downloaded_bytes=5,
                    total_bytes=10,
                )
            )
        return DownloadResult(
            target_path=request.target_path,
            file_size=10,
            mime_type="video/mp4",
        )


def test_download_request_normalizes_input():
    request = DownloadRequest(
        source_url="HTTPS://Example.COM:443/video.mp4#player",
        target_path=Path("data/media/video.mp4"),
        headers={" User-Agent ": " VideoCenter/0.1 "},
    )

    assert request.source_url == "https://example.com/video.mp4"
    assert request.hostname == "example.com"
    assert request.scheme == "https"
    assert request.headers == {"User-Agent": "VideoCenter/0.1"}


@pytest.mark.parametrize(
    "source_url",
    [
        "file:///tmp/video.mp4",
        "not-a-url",
        "https://user:secret@example.com/video.mp4",
        "https://example.com:bad/video.mp4",
    ],
)
def test_download_request_rejects_unsafe_urls(source_url: str):
    with pytest.raises(ValueError):
        DownloadRequest(
            source_url=source_url,
            target_path=Path("video.mp4"),
        )


def test_download_progress_reports_percentage():
    progress = DownloadProgress(
        state="downloading",
        downloaded_bytes=25,
        total_bytes=100,
        speed_bytes_per_second=10,
    )

    assert progress.percentage == 25
    assert progress.remaining_seconds == 7.5
    with pytest.raises(ValueError):
        DownloadProgress(
            state="downloading",
            downloaded_bytes=101,
            total_bytes=100,
        )

    assert (
        DownloadProgress(
            state="downloading",
            downloaded_bytes=25,
            total_bytes=None,
            speed_bytes_per_second=10,
        ).remaining_seconds
        is None
    )


def test_downloader_contract_supports_progress_and_result():
    downloader = ExampleDownloader()
    updates: list[DownloadProgress] = []
    request = DownloadRequest(
        source_url="https://example.com/video.mp4",
        target_path=Path("data/media/video.mp4"),
    )

    result = downloader.download(request, progress_callback=updates.append)

    assert downloader.supports(request) is True
    assert updates[0].percentage == 50
    assert result.target_path == request.target_path
    assert result.file_size == 10


def test_cancellation_token_is_cooperative():
    downloader = ExampleDownloader()
    token = DownloadCancellationToken()
    token.cancel()

    assert token.is_cancelled is True
    with pytest.raises(DownloadCancelledError):
        downloader.download(
            DownloadRequest(
                source_url="https://example.com/video.mp4",
                target_path=Path("video.mp4"),
            ),
            cancellation_token=token,
        )
