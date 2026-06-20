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
    UnsupportedWebsiteError,
)


class ExampleParser(ResourceParser):
    name = "example"
    priority = 10
    supported_hosts = ("example.com",)

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


class GenericParser(ExampleParser):
    name = "generic"
    priority = 100
    supported_hosts = ()

    def supports(self, request: ParseRequest) -> bool:
        return request.source_url.startswith("https://")


def test_parse_request_accepts_only_http_resource_pages():
    request = ParseRequest(
        source_url="https://example.com/movie/1",
        preferred_language="zh-CN",
    )
    assert request.preferred_language == "zh-CN"
    assert request.hostname == "example.com"

    with pytest.raises(ValueError, match="HTTP"):
        ParseRequest(source_url="file:///tmp/movie.html")
    with pytest.raises(ValueError, match="HTTP"):
        ParseRequest(source_url="not-a-url")


def test_parse_request_normalizes_url_for_parser_selection():
    request = ParseRequest("HTTPS://WWW.Example.COM:443/movie/1?lang=zh#player")

    assert request.source_url == "https://www.example.com/movie/1?lang=zh"
    assert request.hostname == "www.example.com"


def test_registry_selects_highest_priority_supported_parser():
    registry = ParserRegistry([GenericParser(), FallbackParser(), ExampleParser()])

    selected = registry.select_url("https://www.example.com/movie/1")

    assert selected.name == "example"
    assert [parser.name for parser in registry.list_parsers()] == [
        "generic",
        "example",
        "fallback",
    ]


def test_declared_host_does_not_match_lookalike_domain():
    registry = ParserRegistry([ExampleParser()])

    with pytest.raises(ParserNotFoundError):
        registry.select_url("https://example.com.attacker.test/movie/1")


def test_generic_parser_is_used_only_when_no_host_parser_matches():
    registry = ParserRegistry([GenericParser(), ExampleParser()])

    assert registry.select_url("https://example.com/movie/1").name == "example"
    assert registry.select_url("https://other.test/movie/1").name == "generic"


def test_registry_parses_standard_nested_result():
    registry = ParserRegistry([ExampleParser()])

    result = asyncio.run(registry.parse(ParseRequest("https://example.com/series/1")))

    assert result.title == "Example Series"
    assert result.media_type == "series"
    assert result.seasons[0].episodes[0].title == "Pilot"
    assert result.seasons[0].episodes[0].downloads[0].quality == "1080p"
    assert result.media_type == ParsedMediaType.SERIES

    direct_result = asyncio.run(
        registry.parse_url(
            "https://example.com/series/1",
            preferred_language="zh-CN",
        )
    )
    assert direct_result.title == "Example Series"


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


def test_registry_rejects_invalid_supported_host_configuration():
    class InvalidHostParser(ExampleParser):
        name = "invalid-host"
        supported_hosts = ("https://example.com/path",)

    with pytest.raises(ValueError, match="supported_hosts"):
        ParserRegistry([InvalidHostParser()])


def test_registry_reports_when_no_parser_supports_url():
    registry = ParserRegistry([ExampleParser()])
    request = ParseRequest("https://unsupported.test/movie/1")

    with pytest.raises(ParserNotFoundError) as exc_info:
        registry.select(request)

    assert exc_info.value.source_url == request.source_url
    assert isinstance(exc_info.value, UnsupportedWebsiteError)
    assert exc_info.value.code == "UNSUPPORTED_WEBSITE"
    assert exc_info.value.status_code == 400
    assert exc_info.value.hostname == "unsupported.test"
    assert exc_info.value.supported_hosts == ("example.com",)
    assert exc_info.value.details == {
        "hostname": "unsupported.test",
        "supported_hosts": ["example.com"],
    }


def test_supported_hosts_are_normalized_deduplicated_and_sorted():
    class MultipleHostsParser(ExampleParser):
        name = "multiple-hosts"
        supported_hosts = ("Video.Test.", "example.com")

    registry = ParserRegistry([ExampleParser(), MultipleHostsParser()])

    assert registry.supported_hosts() == ("example.com", "video.test")


def test_resource_parser_cannot_be_instantiated_without_contract_methods():
    class IncompleteParser(ResourceParser):
        name = "incomplete"

    with pytest.raises(TypeError):
        IncompleteParser()
