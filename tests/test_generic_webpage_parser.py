import asyncio

import pytest

from videocenter.services.parsers import (
    GenericWebPageParser,
    ParsedMediaType,
    ParseRequest,
    WebPageResponse,
    create_default_parser_registry,
)

MOVIE_HTML = """
<!doctype html>
<html>
<head>
  <title>Fallback page title</title>
  <meta property="og:title" content="Open Graph title">
  <meta property="og:description" content="Open Graph description">
  <meta property="og:image" content="/images/fallback.jpg">
  <meta property="og:site_name" content="Example Video">
  <link rel="canonical" href="/movies/example-movie">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Movie",
    "name": "Example Movie",
    "description": "JSON-LD description",
    "datePublished": "2025-05-20",
    "duration": "PT1H35M",
    "genre": ["Drama", "Science Fiction"],
    "director": {"@type": "Person", "name": "Director One"},
    "actor": [
      {"@type": "Person", "name": "Actor One"},
      {"@type": "Person", "name": "Actor Two"}
    ],
    "image": "/images/poster.jpg",
    "aggregateRating": {"ratingValue": "8.7"}
  }
  </script>
</head>
</html>
"""


def response(html: str, *, url: str = "https://example.com/redirected") -> WebPageResponse:
    return WebPageResponse(url=url, content_type="text/html", text=html)


def test_generic_webpage_parser_extracts_json_ld_and_open_graph_metadata():
    async def fetcher(url: str) -> WebPageResponse:
        assert url == "https://example.com/input"
        return response(MOVIE_HTML)

    parser = GenericWebPageParser(fetcher)
    result = asyncio.run(parser.parse(ParseRequest("https://example.com/input")))

    assert result.title == "Example Movie"
    assert result.source_site == "Example Video"
    assert result.source_page_url == "https://example.com/movies/example-movie"
    assert result.media_type == ParsedMediaType.MOVIE
    assert result.description == "JSON-LD description"
    assert result.release_date.isoformat() == "2025-05-20"
    assert result.duration_minutes == 95
    assert result.rating == 8.7
    assert result.directors == ("Director One",)
    assert result.actors == ("Actor One", "Actor Two")
    assert result.genres == ("Drama", "Science Fiction")
    assert result.poster_url == "https://example.com/images/poster.jpg"
    assert result.extra["parser"] == "generic-webpage"


def test_generic_webpage_parser_falls_back_to_basic_html_metadata():
    html = """
    <html>
      <head>
        <title> Basic Page </title>
        <meta name="description" content="Basic description">
        <meta name="twitter:image" content="https://cdn.test/poster.jpg">
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://basic.test/page"))
    )

    assert result.title == "Basic Page"
    assert result.source_site == "basic.test"
    assert result.description == "Basic description"
    assert result.poster_url == "https://cdn.test/poster.jpg"
    assert result.media_type == ParsedMediaType.OTHER


def test_generic_webpage_parser_ignores_invalid_json_ld():
    html = """
    <html>
      <head>
        <title>Valid title</title>
        <script type="application/ld+json">{broken json</script>
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://example.test/page"))
    )
    assert result.title == "Valid title"


def test_generic_webpage_parser_requires_a_title():
    async def fetcher(url: str) -> WebPageResponse:
        return response("<html><head></head></html>", url=url)

    with pytest.raises(ValueError, match="标题"):
        asyncio.run(GenericWebPageParser(fetcher).parse(ParseRequest("https://example.test/page")))


def test_default_registry_contains_generic_webpage_fallback():
    registry = create_default_parser_registry()

    parser = registry.select_url("https://unknown.example/movie/1")

    assert parser.name == "generic-webpage"
