import hashlib
from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    DownloadError,
    DownloadProgressState,
    DownloadRequest,
    HttpDirectDownloader,
)


class FakeResponse(BytesIO):
    def __init__(
        self,
        content: bytes,
        *,
        content_type: str = "video/mp4",
        content_length: int | None = None,
    ) -> None:
        super().__init__(content)
        self.headers = Message()
        self.headers["Content-Length"] = str(
            len(content) if content_length is None else content_length
        )
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def test_http_direct_downloader_writes_file_and_reports_progress(
    tmp_path: Path,
    monkeypatch,
):
    content = b"video-content"
    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(content),
    )
    updates = []
    target = tmp_path / "movie.mp4"

    result = HttpDirectDownloader().download(
        DownloadRequest(
            source_url="https://example.com/movie.mp4",
            target_path=target,
            chunk_size=1024,
        ),
        progress_callback=updates.append,
    )

    assert target.read_bytes() == content
    assert result.target_path == target.resolve()
    assert result.file_size == len(content)
    assert result.mime_type == "video/mp4"
    assert result.checksum == hashlib.sha256(content).hexdigest()
    assert [update.state for update in updates] == [
        DownloadProgressState.STARTING,
        DownloadProgressState.DOWNLOADING,
        DownloadProgressState.FINALIZING,
    ]
    assert updates[1].percentage == 100


def test_http_direct_downloader_forwards_headers_and_timeout(
    tmp_path: Path,
    monkeypatch,
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return FakeResponse(b"content")

    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        fake_urlopen,
    )

    HttpDirectDownloader().download(
        DownloadRequest(
            source_url="https://example.com/movie.mp4",
            target_path=tmp_path / "movie.mp4",
            headers={"User-Agent": "VideoCenter/Test"},
            timeout_seconds=12,
        )
    )

    assert captured == {
        "user_agent": "VideoCenter/Test",
        "timeout": 12,
    }


def test_http_direct_downloader_rejects_existing_target(tmp_path: Path):
    target = tmp_path / "movie.mp4"
    target.write_bytes(b"existing")

    with pytest.raises(DownloadError, match="已存在"):
        HttpDirectDownloader().download(
            DownloadRequest(
                source_url="https://example.com/movie.mp4",
                target_path=target,
            )
        )

    assert target.read_bytes() == b"existing"


def test_http_direct_downloader_cleans_partial_file_when_cancelled(
    tmp_path: Path,
    monkeypatch,
):
    token = DownloadCancellationToken()
    target = tmp_path / "movie.mp4"
    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(b"x" * 4096),
    )

    def cancel_after_first_chunk(progress):
        if progress.state == DownloadProgressState.DOWNLOADING:
            token.cancel()

    with pytest.raises(DownloadCancelledError):
        HttpDirectDownloader().download(
            DownloadRequest(
                source_url="https://example.com/movie.mp4",
                target_path=target,
                chunk_size=1024,
            ),
            progress_callback=cancel_after_first_chunk,
            cancellation_token=token,
        )

    assert not target.exists()
    assert not target.with_suffix(".mp4.part").exists()


def test_http_direct_downloader_wraps_transport_errors(
    tmp_path: Path,
    monkeypatch,
):
    def fail_urlopen(request, timeout):
        raise OSError("network unavailable")

    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        fail_urlopen,
    )

    with pytest.raises(DownloadError, match="network unavailable"):
        HttpDirectDownloader().download(
            DownloadRequest(
                source_url="https://example.com/movie.mp4",
                target_path=tmp_path / "movie.mp4",
            )
        )


def test_http_direct_downloader_rejects_incomplete_content_length(
    tmp_path: Path,
    monkeypatch,
):
    target = tmp_path / "movie.mp4"
    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(b"short", content_length=100),
    )

    with pytest.raises(DownloadError, match="大小不完整"):
        HttpDirectDownloader().download(
            DownloadRequest(
                source_url="https://example.com/movie.mp4",
                target_path=target,
            )
        )

    assert not target.exists()
    assert not target.with_suffix(".mp4.part").exists()


def test_http_direct_downloader_verifies_expected_sha256(
    tmp_path: Path,
    monkeypatch,
):
    content = b"verified-content"
    expected = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(
        "videocenter.services.downloaders.http.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(content),
    )

    result = HttpDirectDownloader().download(
        DownloadRequest(
            source_url="https://example.com/movie.mp4",
            target_path=tmp_path / "valid.mp4",
            expected_sha256=expected.upper(),
        )
    )
    assert result.checksum == expected

    with pytest.raises(DownloadError, match="SHA-256"):
        HttpDirectDownloader().download(
            DownloadRequest(
                source_url="https://example.com/movie.mp4",
                target_path=tmp_path / "invalid.mp4",
                expected_sha256="0" * 64,
            )
        )
    assert not (tmp_path / "invalid.mp4").exists()
