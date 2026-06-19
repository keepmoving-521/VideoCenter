import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from videocenter.main import app
from videocenter.schemas.download import DownloadCreate
from videocenter.schemas.history import HistoryUpsert
from videocenter.schemas.media import MediaCreate


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def assert_validation_error(response, location: list[str]) -> None:
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(item["loc"] == location for item in error["details"])


def test_path_ids_must_be_positive(client):
    response = client.get("/api/v1/media/0")
    assert_validation_error(response, ["path", "media_id"])


def test_search_query_rejects_whitespace_only(client):
    response = client.get("/api/v1/media", params={"query": "   "})
    assert_validation_error(response, ["query", "query"])


def test_request_body_rejects_unknown_fields(client):
    response = client.post(
        "/api/v1/media",
        json={"title": "Movie", "unknown": "value"},
    )
    assert_validation_error(response, ["body", "unknown"])


def test_media_title_is_trimmed():
    payload = MediaCreate(title="  Movie title  ")
    assert payload.title == "Movie title"


def test_media_title_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        MediaCreate(title="   ")


def test_empty_media_update_is_rejected(client):
    response = client.patch("/api/v1/media/1", json={})
    assert_validation_error(response, ["body"])


def test_required_media_fields_cannot_be_set_to_null(client):
    response = client.patch("/api/v1/media/1", json={"title": None})
    assert_validation_error(response, ["body", "title"])


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


def test_range_header_rejects_multiple_ranges(client):
    response = client.get(
        "/api/v1/stream/1",
        headers={"Range": "bytes=0-10,20-30"},
    )
    assert_validation_error(response, ["header", "Range"])


def test_openapi_documents_positive_path_ids():
    schema = app.openapi()
    parameters = schema["paths"]["/api/v1/media/{media_id}"]["get"]["parameters"]
    media_id = next(item for item in parameters if item["name"] == "media_id")
    assert media_id["schema"]["exclusiveMinimum"] == 0
