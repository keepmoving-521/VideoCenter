import pytest

from videocenter.services.downloads import safe_target_name


def test_safe_target_name_removes_unsafe_characters():
    assert safe_target_name("../my:video?.mp4") == "my_video_.mp4"


def test_safe_target_name_rejects_empty_name():
    with pytest.raises(ValueError):
        safe_target_name("...")
