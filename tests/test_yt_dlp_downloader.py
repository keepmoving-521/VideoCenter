import hashlib
from pathlib import Path

import pytest

from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    DownloadError,
    DownloadProgressState,
    DownloadRequest,
    YtDlpDownloader,
)


class FakeYoutubeDL:
    last_options = None

    def __init__(self, options):
        self.options = options
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, source_url, download):
        target = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
        content = b"yt-dlp-content"
        hook = self.options["progress_hooks"][0]
        hook(
            {
                "status": "downloading",
                "filename": str(target),
                "downloaded_bytes": len(content) // 2,
                "total_bytes": len(content),
                "speed": 1024,
            }
        )
        target.write_bytes(content)
        hook(
            {
                "status": "finished",
                "filename": str(target),
                "downloaded_bytes": len(content),
                "total_bytes": len(content),
            }
        )
        return {
            "extractor_key": "Example",
            "format_id": "best",
        }

    def prepare_filename(self, info):
        del info
        return self.options["outtmpl"].replace("%(ext)s", "mp4")


def test_yt_dlp_downloader_uses_python_api_and_progress_hooks(tmp_path: Path):
    target = tmp_path / "video.mp4"
    updates = []

    result = YtDlpDownloader(FakeYoutubeDL).download(
        DownloadRequest(
            source_url="https://video.example.com/watch/123",
            target_path=target,
            headers={"Referer": "https://video.example.com/"},
            timeout_seconds=15,
            overwrite=True,
        ),
        progress_callback=updates.append,
    )

    assert result.target_path == target.resolve()
    assert result.file_size == len(b"yt-dlp-content")
    assert result.checksum == hashlib.sha256(b"yt-dlp-content").hexdigest()
    assert result.extra == {"extractor": "Example", "format_id": "best"}
    assert [update.state for update in updates] == [
        DownloadProgressState.STARTING,
        DownloadProgressState.DOWNLOADING,
        DownloadProgressState.FINALIZING,
    ]
    assert FakeYoutubeDL.last_options["noplaylist"] is True
    assert FakeYoutubeDL.last_options["outtmpl"].endswith(".%(ext)s")
    assert FakeYoutubeDL.last_options["socket_timeout"] == 15
    assert FakeYoutubeDL.last_options["http_headers"]["Referer"].startswith("https://")


def test_yt_dlp_downloader_verifies_sha256(tmp_path: Path):
    target = tmp_path / "video.mp4"

    with pytest.raises(DownloadError, match="SHA-256"):
        YtDlpDownloader(FakeYoutubeDL).download(
            DownloadRequest(
                source_url="https://video.example.com/watch/123",
                target_path=target,
                expected_sha256="0" * 64,
            )
        )

    assert not target.exists()


def test_yt_dlp_downloader_maps_cancelled_extraction(tmp_path: Path):
    class CancelledYoutubeDL(FakeYoutubeDL):
        def extract_info(self, source_url, download):
            self.options["progress_hooks"][0](
                {
                    "status": "downloading",
                    "downloaded_bytes": 1,
                    "total_bytes": 10,
                }
            )
            raise RuntimeError("yt-dlp interrupted")

    token = DownloadCancellationToken()

    def cancel_on_progress(progress):
        if progress.state == DownloadProgressState.DOWNLOADING:
            token.cancel()

    with pytest.raises(DownloadCancelledError):
        YtDlpDownloader(CancelledYoutubeDL).download(
            DownloadRequest(
                source_url="https://video.example.com/watch/123",
                target_path=tmp_path / "video.mp4",
            ),
            progress_callback=cancel_on_progress,
            cancellation_token=token,
        )


def test_yt_dlp_downloader_reports_missing_dependency(tmp_path: Path, monkeypatch):
    downloader = YtDlpDownloader()
    monkeypatch.setattr(
        "videocenter.services.downloaders.yt_dlp.importlib.import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )

    with pytest.raises(DownloadError, match="未安装"):
        downloader.download(
            DownloadRequest(
                source_url="https://video.example.com/watch/123",
                target_path=tmp_path / "video.mp4",
            )
        )
