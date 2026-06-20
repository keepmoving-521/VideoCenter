import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions
from videocenter.api.routes.parsing import get_parser_registry
from videocenter.main import app
from videocenter.services.parsers import (
    ParsedDownload,
    ParsedEpisode,
    ParsedMediaType,
    ParsedResourceType,
    ParsedSeason,
    ParseRequest,
    ParseResult,
    ParserRegistry,
    ResourceParser,
)

pytestmark = pytest.mark.integration


class WorkflowParser(ResourceParser):
    name = "workflow"
    supported_hosts = ("parse.test",)

    def supports(self, request: ParseRequest) -> bool:
        return self.matches_host(request.hostname)

    async def parse(self, request: ParseRequest) -> ParseResult:
        return ParseResult(
            title="Parsed Series",
            source_site="Parse Test",
            source_page_url=request.source_url,
            media_type=ParsedMediaType.SERIES,
            description="Original description",
            release_year=2025,
            tags=("Sci-Fi", "Favorite"),
            downloads=(
                ParsedDownload(
                    source_url="https://cdn.parse.test/trailer.mp4",
                    quality="1080p",
                ),
            ),
            seasons=(
                ParsedSeason(
                    season_number=1,
                    title="Season One",
                    episodes=(
                        ParsedEpisode(
                            episode_number=1,
                            title="Pilot",
                            downloads=(
                                ParsedDownload(
                                    source_url="https://cdn.parse.test/s1e1.mp4",
                                    quality="1080p",
                                ),
                                ParsedDownload(
                                    source_url="https://cdn.parse.test/s1e1.vtt",
                                    resource_type=ParsedResourceType.SUBTITLE,
                                    language="zh-CN",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )


@pytest.fixture
def parser_override():
    app.dependency_overrides[get_parser_registry] = lambda: ParserRegistry([WorkflowParser()])
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_parser_registry, None)


def test_preview_confirm_and_save_parse_result(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    parser_override,
):
    preview = api_assertions.assert_status(
        api_client.post(
            "/api/v1/parsing/preview",
            json={
                "source_url": "https://parse.test/show/1",
                "preferred_language": "zh-CN",
            },
        ),
        200,
    )
    assert preview["result"]["title"] == "Parsed Series"
    assert len(preview["parse_task_id"]) == 32
    assert len(preview["preview_id"]) == 32

    edited = preview["result"]
    edited["title"] = "Confirmed Series"
    edited["description"] = "User confirmed description"
    confirmed = api_assertions.assert_status(
        api_client.post(
            "/api/v1/parsing/confirm",
            json={
                "preview_id": preview["preview_id"],
                "result": edited,
            },
        ),
        200,
    )
    assert confirmed["result"]["title"] == "Confirmed Series"

    saved = api_assertions.assert_status(
        api_client.post(
            "/api/v1/parsing/save",
            json={"confirmation_id": confirmed["confirmation_id"]},
        ),
        201,
    )
    assert saved == {
        "media_id": saved["media_id"],
        "title": "Confirmed Series",
        "tags_created": 2,
        "seasons_created": 1,
        "episodes_created": 1,
        "downloads_detected": 2,
        "subtitles_detected": 1,
    }

    media = api_assertions.assert_status(
        api_client.get(f"/api/v1/media/{saved['media_id']}"),
        200,
    )
    assert media["description"] == "User confirmed description"
    assert {tag["name"] for tag in media["tags"]} == {"Sci-Fi", "Favorite"}

    hierarchy = api_assertions.assert_status(
        api_client.get(f"/api/v1/media/{saved['media_id']}/hierarchy"),
        200,
    )
    assert hierarchy["seasons"][0]["episodes"][0]["title"] == "Pilot"

    api_assertions.assert_error(
        api_client.post(
            "/api/v1/parsing/save",
            json={"confirmation_id": confirmed["confirmation_id"]},
        ),
        status_code=409,
        code="PARSE_CONFIRMATION_ALREADY_USED",
    )


def test_confirm_rejects_changed_source_url(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    parser_override,
):
    preview = api_client.post(
        "/api/v1/parsing/preview",
        json={"source_url": "https://parse.test/show/1"},
    ).json()
    preview["result"]["source_page_url"] = "https://other.test/show/1"

    api_assertions.assert_error(
        api_client.post(
            "/api/v1/parsing/confirm",
            json={
                "preview_id": preview["preview_id"],
                "result": preview["result"],
            },
        ),
        status_code=400,
        code="PARSE_SOURCE_URL_MISMATCH",
    )


def test_save_rejects_duplicate_source_page(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    parser_override,
):
    def prepare_confirmation() -> str:
        preview = api_client.post(
            "/api/v1/parsing/preview",
            json={"source_url": "https://parse.test/show/1"},
        ).json()
        return api_client.post(
            "/api/v1/parsing/confirm",
            json={
                "preview_id": preview["preview_id"],
                "result": preview["result"],
            },
        ).json()["confirmation_id"]

    first = prepare_confirmation()
    second = prepare_confirmation()
    api_assertions.assert_status(
        api_client.post("/api/v1/parsing/save", json={"confirmation_id": first}),
        201,
    )
    error = api_assertions.assert_error(
        api_client.post(
            "/api/v1/parsing/save",
            json={"confirmation_id": second},
        ),
        status_code=409,
        code="PARSED_MEDIA_ALREADY_EXISTS",
    )
    assert error["error"]["details"]["media_id"] > 0


def test_preview_returns_standard_timeout_error(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    class SlowParser(WorkflowParser):
        name = "slow-workflow"

        async def parse(self, request: ParseRequest) -> ParseResult:
            import asyncio

            await asyncio.sleep(0.05)
            return await super().parse(request)

    app.dependency_overrides[get_parser_registry] = lambda: ParserRegistry(
        [SlowParser()],
        timeout_seconds=0.005,
        max_attempts=2,
        retry_delay_seconds=0,
    )
    try:
        error = api_assertions.assert_error(
            api_client.post(
                "/api/v1/parsing/preview",
                json={"source_url": "https://parse.test/show/1"},
            ),
            status_code=504,
            code="PARSE_TIMEOUT",
        )
    finally:
        app.dependency_overrides.pop(get_parser_registry, None)

    assert error["error"]["details"]["attempts"] == 2
