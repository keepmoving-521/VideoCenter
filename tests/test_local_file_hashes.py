import hashlib

from videocenter.services.local_file_hashes import calculate_sha256


def test_calculate_sha256_reads_file_content(tmp_path):
    path = tmp_path / "video.mkv"
    content = b"video-content" * 100_000
    path.write_bytes(content)

    assert calculate_sha256(path) == hashlib.sha256(content).hexdigest()
