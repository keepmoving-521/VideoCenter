import pytest

from videocenter.services.streaming import ByteRange, parse_range_header


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-99", ByteRange(0, 99)),
        ("bytes=100-", ByteRange(100, 999)),
        ("bytes=-100", ByteRange(900, 999)),
        ("bytes=0-9999", ByteRange(0, 999)),
    ],
)
def test_parse_range_header(header, expected):
    assert parse_range_header(header, 1000) == expected


def test_parse_range_header_rejects_out_of_bounds_range():
    with pytest.raises(ValueError):
        parse_range_header("bytes=1000-", 1000)
