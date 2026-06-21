import pytest

from videocenter.services.streaming import ByteRange, parse_range_header


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-99", ByteRange(0, 99)),
        ("bytes=100-", ByteRange(100, 999)),
        ("bytes=-100", ByteRange(900, 999)),
        ("bytes=0-9999", ByteRange(0, 999)),
        (" Bytes = 10 - 19 ", ByteRange(10, 19)),
        ("BYTES=-2000", ByteRange(0, 999)),
    ],
)
def test_parse_range_header(header, expected):
    assert parse_range_header(header, 1000) == expected


def test_parse_range_header_rejects_out_of_bounds_range():
    with pytest.raises(ValueError):
        parse_range_header("bytes=1000-", 1000)


@pytest.mark.parametrize(
    "header",
    [
        "items=0-10",
        "bytes=0-10,20-30",
        "bytes=-",
        "bytes=abc-10",
        "bytes=10-abc",
        "bytes=20-10",
        "bytes=-0",
    ],
)
def test_parse_range_header_rejects_invalid_ranges(header):
    with pytest.raises(ValueError):
        parse_range_header(header, 1000)


def test_empty_file_rejects_range_but_allows_no_range():
    assert parse_range_header(None, 0) is None
    with pytest.raises(ValueError):
        parse_range_header("bytes=0-", 0)
