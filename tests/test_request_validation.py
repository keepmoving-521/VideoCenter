from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests.support.api import ApiAssertions
from videocenter.main import app
from videocenter.schemas.download import DownloadCreate
from videocenter.schemas.history import HistoryUpsert
from videocenter.schemas.media import MediaCreate


def test_path_ids_must_be_positive(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.get("/api/v1/media/0")
    api_assertions.assert_validation_error(response, ["path", "media_id"])


def test_search_query_rejects_whitespace_only(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.get("/api/v1/media", params={"query": "   "})
    api_assertions.assert_validation_error(response, ["query", "query"])


def test_request_body_rejects_unknown_fields(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.post(
        "/api/v1/media",
        json={"title": "Movie", "unknown": "value"},
    )
    api_assertions.assert_validation_error(response, ["body", "unknown"])


def test_media_title_is_trimmed():
    payload = MediaCreate(title="  Movie title  ")
    assert payload.title == "Movie title"


def test_media_title_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        MediaCreate(title="   ")


def test_media_core_fields_are_normalized():
    payload = MediaCreate(
        title="Movie",
        sort_title="  Movie, The  ",
        alternative_titles=[" Alias ", "alias", "第二片名"],
        release_date="2024-05-20",
        content_rating=" PG-13 ",
    )

    assert payload.sort_title == "Movie, The"
    assert payload.alternative_titles == ["Alias", "第二片名"]
    assert payload.release_year == 2024
    assert payload.content_rating == "PG-13"


def test_media_model_values_preserve_python_date_and_serialize_urls():
    payload = MediaCreate(
        title="Movie",
        release_date="2024-05-20",
        poster_url="https://example.com/poster.jpg",
    )

    values = payload.to_model_values()

    assert values["release_date"] == date(2024, 5, 20)
    assert values["poster_url"] == "https://example.com/poster.jpg"


def test_release_year_must_match_release_date():
    with pytest.raises(ValidationError, match="上映年份必须与上映日期的年份一致"):
        MediaCreate(
            title="Movie",
            release_year=2023,
            release_date="2024-05-20",
        )


def test_alternative_titles_have_size_and_content_limits():
    with pytest.raises(ValidationError):
        MediaCreate(title="Movie", alternative_titles=[" "])

    with pytest.raises(ValidationError):
        MediaCreate(title="Movie", alternative_titles=["Alias"] * 51)


def test_empty_media_update_is_rejected(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.patch("/api/v1/media/1", json={})
    api_assertions.assert_validation_error(response, ["body"])


def test_required_media_fields_cannot_be_set_to_null(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.patch("/api/v1/media/1", json={"title": None})
    api_assertions.assert_validation_error(response, ["body", "title"])


@pytest.mark.parametrize(
    "target_name",
    ["../movie.mp4", "movie?.mp4", "movie.mp4.", "folder/movie.mp4"],
)
def test_download_target_name_rejects_unsafe_values(target_name):
    with pytest.raises(ValidationError):
        DownloadCreate(
            source_url="https://example.com/movie.mp4",
            target_name=target_name,
        )


def test_history_position_cannot_exceed_duration():
    with pytest.raises(ValidationError, match="播放位置不能超过视频总时长"):
        HistoryUpsert(
            media_id=1,
            position_seconds=101,
            duration_seconds=100,
        )


def test_history_rejects_non_finite_numbers():
    with pytest.raises(ValidationError):
        HistoryUpsert(
            media_id=1,
            position_seconds=float("inf"),
        )


def test_range_header_rejects_multiple_ranges(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    response = api_client.get(
        "/api/v1/stream/1",
        headers={"Range": "bytes=0-10,20-30"},
    )
    api_assertions.assert_validation_error(response, ["header", "Range"])


def test_openapi_documents_positive_path_ids():
    schema = app.openapi()
    parameters = schema["paths"]["/api/v1/media/{media_id}"]["get"]["parameters"]
    media_id = next(item for item in parameters if item["name"] == "media_id")
    assert media_id["schema"]["exclusiveMinimum"] == 0
