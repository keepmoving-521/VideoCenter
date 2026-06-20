import asyncio

import pytest

from videocenter.services.parsers import (
    ParsedDownload,
    ParsedEpisode,
    ParsedMediaType,
    ParsedResourceType,
    ParsedSeason,
    ParseRequest,
    ParseResult,
    ParserNotFoundError,
    ParserRegistry,
    ResourceParser,
)


class ExampleParser(ResourceParser):
    name = "example"
    priority = 10

    def supports(self, request: ParseRequest) -> bool:
        return "example.com" in request.source_url

    async def parse(self, request: ParseRequest) -> ParseResult:
        return ParseResult(
            title="Example Series",
            source_site="Example",
            source_page_url=request.source_url,
            media_type="series",
            seasons=(
                ParsedSeason(
                    season_number=1,
                    episodes=(
                        ParsedEpisode(
                            episode_number=1,
                            title="Pilot",
                            downloads=(
                                ParsedDownload(
                                    source_url="https://cdn.example.com/pilot.mp4",
                                    quality="1080p",
                                    mime_type="video/mp4",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )


class FallbackParser(ExampleParser):
    name = "fallback"
    priority = 1


def test_parse_request_accepts_only_http_resource_pages():
    request = ParseRequest(
        source_url="https://example.com/movie/1",
        preferred_language="zh-CN",
    )
    assert request.preferred_language == "zh-CN"

    with pytest.raises(ValueError, match="HTTP"):
        ParseRequest(source_url="file:///tmp/movie.html")
    with pytest.raises(ValueError, match="HTTP"):
        ParseRequest(source_url="not-a-url")


def test_registry_selects_highest_priority_supported_parser():
    registry = ParserRegistry([FallbackParser(), ExampleParser()])

    selected = registry.select(ParseRequest("https://example.com/movie/1"))

    assert selected.name == "example"
    assert [parser.name for parser in registry.list_parsers()] == [
        "example",
        "fallback",
    ]


def test_registry_parses_standard_nested_result():
    registry = ParserRegistry([ExampleParser()])

    result = asyncio.run(registry.parse(ParseRequest("https://example.com/series/1")))

    assert result.title == "Example Series"
    assert result.media_type == "series"
    assert result.seasons[0].episodes[0].title == "Pilot"
    assert result.seasons[0].episodes[0].downloads[0].quality == "1080p"
    assert result.media_type == ParsedMediaType.SERIES


def test_parse_result_normalizes_lists_and_serializes_standard_data():
    result = ParseResult(
        title="  Example Movie  ",
        source_site=" Example ",
        source_page_url="https://example.com/movie/1",
        release_date="2025-06-01",
        alternative_titles=(" Alias ", "alias", "", "第二片名"),
        directors=(" Director ", "director"),
        tags=(" Favorite ", "favorite"),
        downloads=(
            ParsedDownload(
                source_url="https://cdn.example.com/movie.mp4",
                resource_type=ParsedResourceType.VIDEO,
                file_size=1024,
                headers={"Referer": "https://example.com/"},
            ),
        ),
        extra={"external_id": "movie-1"},
    )

    serialized = result.model_dump(mode="json")

    assert result.title == "Example Movie"
    assert result.alternative_titles == ("Alias", "第二片名")
    assert result.directors == ("Director",)
    assert result.tags == ("Favorite",)
    assert serialized["release_date"] == "2025-06-01"
    assert serialized["media_type"] == "movie"
    assert serialized["downloads"][0]["resource_type"] == "video"
    assert result.to_media_values()["title"] == "Example Movie"
    assert "downloads" not in result.to_media_values()


@pytest.mark.parametrize(
    "payload",
    [
        {"rating": -0.1},
        {"rating": 10.1},
        {"duration_minutes": 0},
        {"poster_url": "file:///poster.jpg"},
    ],
)
def test_parse_result_rejects_invalid_media_values(payload):
    with pytest.raises(ValueError):
        ParseResult(
            title="Movie",
            source_site="Example",
            source_page_url="https://example.com/movie/1",
            **payload,
        )


def test_parsed_hierarchy_rejects_invalid_or_duplicate_numbers():
    with pytest.raises(ValueError):
        ParsedEpisode(episode_number=0, title="Invalid")
    with pytest.raises(ValueError):
        ParsedSeason(season_number=-1)
    with pytest.raises(ValueError, match="分集编号不能重复"):
        ParsedSeason(
            season_number=1,
            episodes=(
                ParsedEpisode(episode_number=1, title="One"),
                ParsedEpisode(episode_number=1, title="Duplicate"),
            ),
        )
    with pytest.raises(ValueError, match="季编号不能重复"):
        ParseResult(
            title="Series",
            source_site="Example",
            source_page_url="https://example.com/series/1",
            media_type="series",
            seasons=(
                ParsedSeason(season_number=1),
                ParsedSeason(season_number=1),
            ),
        )


def test_only_series_results_can_contain_seasons():
    with pytest.raises(ValueError, match="电视剧"):
        ParseResult(
            title="Movie",
            source_site="Example",
            source_page_url="https://example.com/movie/1",
            seasons=(ParsedSeason(season_number=1),),
        )


def test_registry_rejects_duplicate_names_and_supports_unregister():
    registry = ParserRegistry([ExampleParser()])

    with pytest.raises(ValueError, match="已注册"):
        registry.register(ExampleParser())

    removed = registry.unregister("example")
    assert removed.name == "example"
    assert registry.list_parsers() == ()

    with pytest.raises(KeyError, match="未注册"):
        registry.unregister("missing")


def test_registry_reports_when_no_parser_supports_url():
    registry = ParserRegistry([ExampleParser()])
    request = ParseRequest("https://unsupported.test/movie/1")

    with pytest.raises(ParserNotFoundError) as exc_info:
        registry.select(request)

    assert exc_info.value.source_url == request.source_url


def test_resource_parser_cannot_be_instantiated_without_contract_methods():
    class IncompleteParser(ResourceParser):
        name = "incomplete"

    with pytest.raises(TypeError):
        IncompleteParser()
