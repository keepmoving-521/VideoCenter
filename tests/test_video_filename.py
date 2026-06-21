import pytest

from videocenter.models.media import MediaType
from videocenter.services.video_filename import parse_video_filename


@pytest.mark.parametrize(
    ("file_name", "title", "year"),
    [
        ("The.Matrix.1999.1080p.BluRay.x265.mkv", "The Matrix", 1999),
        ("流浪地球.2019.2160p.WEB-DL.mp4", "流浪地球", 2019),
        ("A Quiet Movie.m4v", "A Quiet Movie", None),
    ],
)
def test_parse_movie_filename(file_name, title, year):
    result = parse_video_filename(file_name)

    assert result.media_type == MediaType.MOVIE
    assert result.title == title
    assert result.release_year == year
    assert result.season_number is None
    assert result.episode_number is None


@pytest.mark.parametrize(
    ("file_name", "title", "season", "episode"),
    [
        ("The.Show.S02E07.1080p.WEB-DL.mkv", "The Show", 2, 7),
        ("The Show 2x07 HDTV.mp4", "The Show", 2, 7),
        ("示例剧 第3季 第12集.mp4", "示例剧", 3, 12),
        ("Specials.S00E01.mkv", "Specials", 0, 1),
    ],
)
def test_parse_series_filename(file_name, title, season, episode):
    result = parse_video_filename(file_name)

    assert result.media_type == MediaType.SERIES
    assert result.title == title
    assert result.season_number == season
    assert result.episode_number == episode
