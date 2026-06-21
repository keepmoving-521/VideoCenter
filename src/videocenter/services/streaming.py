import re
from dataclasses import dataclass

_RANGE_PATTERN = re.compile(r"^\s*bytes\s*=\s*(.*?)\s*$", re.IGNORECASE)


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
    if file_size < 0:
        raise ValueError("文件大小无效")

    match = _RANGE_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("不支持的 Range 请求")
    range_spec = match.group(1)
    if "," in range_spec:
        raise ValueError("不支持多段 Range 请求")
    if "-" not in range_spec:
        raise ValueError("无效的 Range 请求")

    start_text, end_text = (part.strip() for part in range_spec.split("-", maxsplit=1))
    if not start_text and not end_text:
        raise ValueError("无效的 Range 请求")
    if start_text and not start_text.isdigit():
        raise ValueError("无效的 Range 起始位置")
    if end_text and not end_text.isdigit():
        raise ValueError("无效的 Range 结束位置")
    if file_size == 0:
        raise ValueError("空文件不支持 Range 请求")

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
