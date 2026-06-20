import asyncio

import pytest

from videocenter.services.parsers import (
    ParsedDownload,
    ParsedEpisode,
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
