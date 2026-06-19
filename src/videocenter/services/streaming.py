from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range_header(value: str | None, file_size: int) -> ByteRange | None:
    if not value:
        return None
    if not value.startswith("bytes=") or "," in value:
        raise ValueError("不支持的 Range 请求")

    start_text, end_text = value.removeprefix("bytes=").split("-", maxsplit=1)
    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("无效的 Range 请求")
        return ByteRange(max(file_size - suffix_length, 0), file_size - 1)

    start = int(start_text)
    end = int(end_text) if end_text else file_size - 1
    if start < 0 or start >= file_size or end < start:
        raise ValueError("Range 超出文件范围")
    return ByteRange(start, min(end, file_size - 1))


def iter_file_range(path: str, byte_range: ByteRange, chunk_size: int = 1024 * 1024):
    with open(path, "rb") as file:
        file.seek(byte_range.start)
        remaining = byte_range.length
        while remaining:
            chunk = file.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
