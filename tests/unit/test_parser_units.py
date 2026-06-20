import asyncio

import pytest

from videocenter.services.parsers import (
    GenericWebPageParser,
    ParsedResourceType,
    ParseRequest,
    ParseResult,
    ParserRegistry,
    ResourceParser,
    WebPageResponse,
)
from videocenter.services.parsers.webpage import (
    WebPageMetadataParser,
    parse_json_ld,
    parse_release_year,
    schema_downloads,
)


class BlockingParser(ResourceParser):
    name = "blocking"
    supported_hosts = ("unit.test",)

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    def supports(self, request: ParseRequest) -> bool:
        return self.matches_host(request.hostname)

    async def parse(self, request: ParseRequest) -> ParseResult:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        if self.fail:
            raise ValueError("broken page")
        return ParseResult(
            title="Unit Movie",
            source_site="Unit",
            source_page_url=request.source_url,
        )


def test_concurrent_duplicate_requests_share_one_parser_execution():
    async def run() -> tuple[ParseResult, ParseResult, int]:
        parser = BlockingParser()
        registry = ParserRegistry([parser])
        first = asyncio.create_task(
            registry.parse_url(
                "https://unit.test/movie/1",
                task_id="first-task",
            )
        )
        await parser.started.wait()
        second = asyncio.create_task(
            registry.parse_url(
                "https://unit.test/movie/1",
                task_id="second-task",
            )
        )
        await asyncio.sleep(0)
        parser.release.set()
        first_result, second_result = await asyncio.gather(first, second)
        return first_result, second_result, parser.calls

    first_result, second_result, calls = asyncio.run(run())

    assert calls == 1
    assert first_result is second_result


def test_failed_inflight_request_does_not_block_later_parse():
    async def run() -> int:
        parser = BlockingParser(fail=True)
        registry = ParserRegistry([parser], max_attempts=1)
        first = asyncio.create_task(registry.parse_url("https://unit.test/movie/1"))
        await parser.started.wait()
        second = asyncio.create_task(registry.parse_url("https://unit.test/movie/1"))
        parser.release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, ValueError) for result in results)

        parser.fail = False
        parser.started.clear()
        parser.release = asyncio.Event()
        third = asyncio.create_task(registry.parse_url("https://unit.test/movie/1"))
        await parser.started.wait()
        parser.release.set()
        await third
        return parser.calls

    assert asyncio.run(run()) == 2


def test_duplicate_wait_event_links_to_owner_task(caplog):
    async def run() -> None:
        parser = BlockingParser()
        registry = ParserRegistry([parser])
        first = asyncio.create_task(
            registry.parse_url(
                "https://unit.test/movie/1",
                task_id="owner-task",
            )
        )
        await parser.started.wait()
        second = asyncio.create_task(
            registry.parse_url(
                "https://unit.test/movie/1",
                task_id="waiting-task",
            )
        )
        await asyncio.sleep(0)
        parser.release.set()
        await asyncio.gather(first, second)

    with caplog.at_level(
        "INFO",
        logger="videocenter.services.parsers.registry",
    ):
        asyncio.run(run())

    duplicate = next(
        record
        for record in caplog.records
        if getattr(record, "parse_event", None) == "duplicate_wait"
    )
    assert duplicate.parse_task_id == "waiting-task"
    assert duplicate.shared_parse_task_id == "owner-task"


def test_cancelling_waiter_does_not_cancel_shared_parse():
    async def run() -> tuple[str, int]:
        parser = BlockingParser()
        registry = ParserRegistry([parser])
        owner = asyncio.create_task(registry.parse_url("https://unit.test/movie/1"))
        await parser.started.wait()
        waiter = asyncio.create_task(registry.parse_url("https://unit.test/movie/1"))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        parser.release.set()
        result = await owner
        return result.title, parser.calls

    assert asyncio.run(run()) == ("Unit Movie", 1)


def test_webpage_metadata_parser_preserves_repeated_media_tags():
    document = WebPageMetadataParser()
    document.feed(
        """
        <meta property="og:video" content="/720.mp4">
        <meta property="og:video" content="/1080.mp4">
        <video><track kind="subtitles" src="/zh.vtt" srclang="zh-CN"></video>
        """
    )

    assert document.meta["og:video"] == "/720.mp4"
    assert document.meta_values["og:video"] == ["/720.mp4", "/1080.mp4"]
    assert document.media_elements[0]["resource_type"] == "subtitle"


def test_json_ld_and_download_helpers_ignore_bad_items_and_deduplicate():
    objects = parse_json_ld(
        [
            "{broken",
            """
            {
              "@type": "VideoObject",
              "contentUrl": "/movie.mp4",
              "encoding": {
                "@type": "VideoObject",
                "contentUrl": "/movie.mp4"
              },
              "subtitle": {
                "@type": "Subtitle",
                "contentUrl": "/movie.vtt",
                "inLanguage": "zh-CN"
              }
            }
            """,
        ]
    )

    downloads = schema_downloads(objects[0], base_url="https://unit.test/page")

    assert len(downloads) == 2
    assert downloads[0].resource_type == ParsedResourceType.VIDEO
    assert downloads[1].resource_type == ParsedResourceType.SUBTITLE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Released 2024", 2024),
        ("Part 2", None),
        ("1888", 1888),
        ("2101", None),
    ],
)
def test_release_year_parser_uses_supported_year_range(value, expected):
    assert parse_release_year(value) == expected


def test_generic_parser_uses_structured_title_before_html_title():
    html = """
    <html><head>
      <title>HTML title</title>
      <meta property="og:title" content="Open Graph title">
      <script type="application/ld+json">
        {"@type": "Movie", "name": "Structured title"}
      </script>
    </head></html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return WebPageResponse(url=url, content_type="text/html", text=html)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://unit.test/movie/1"))
    )

    assert result.title == "Structured title"
