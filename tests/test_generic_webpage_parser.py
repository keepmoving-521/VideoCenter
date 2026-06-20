import asyncio

import pytest

from videocenter.services.parsers import (
    GenericWebPageParser,
    ParsedMediaType,
    ParsedResourceType,
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
    assert result.release_year == 2025
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


def test_generic_webpage_parser_extracts_r06_to_r10_meta_fallbacks():
    html = """
    <html>
      <head>
        <meta name="movie:title" content="Meta Movie">
        <meta name="movie:description" content="Meta movie description">
        <meta name="thumbnailUrl" content="/assets/meta-poster.jpg">
        <meta name="release_date" content="2023">
        <meta name="director" content="Director One, Director Two">
        <meta name="actor" content="Actor One">
        <meta name="actor" content="Actor Two、Actor One">
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://metadata.test/movie/1"))
    )

    assert result.title == "Meta Movie"
    assert result.description == "Meta movie description"
    assert result.poster_url == "https://metadata.test/assets/meta-poster.jpg"
    assert result.release_year == 2023
    assert result.release_date is None
    assert result.directors == ("Director One", "Director Two")
    assert result.actors == ("Actor One", "Actor Two")


def test_json_ld_fields_take_priority_and_meta_people_are_merged():
    html = """
    <html>
      <head>
        <title>HTML title</title>
        <meta property="og:title" content="Open Graph title">
        <meta property="og:description" content="Open Graph description">
        <meta property="og:image" content="/images/open-graph.jpg">
        <meta name="actor" content="Actor Two, Actor Three">
        <meta name="director" content="Director One">
        <script type="application/ld+json">
        {
          "@type": "Movie",
          "name": "Structured title",
          "description": "Structured description",
          "image": "/images/structured.jpg",
          "releaseDate": "2024-08-09",
          "director": {"name": "Director One"},
          "actors": [{"name": "Actor One"}, {"name": "Actor Two"}]
        }
        </script>
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://priority.test/movie/1"))
    )

    assert result.title == "Structured title"
    assert result.description == "Structured description"
    assert result.poster_url == "https://priority.test/images/structured.jpg"
    assert result.release_year == 2024
    assert result.release_date.isoformat() == "2024-08-09"
    assert result.directors == ("Director One",)
    assert result.actors == ("Actor One", "Actor Two", "Actor Three")


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


def test_parser_extracts_video_qualities_and_subtitles_from_html():
    html = """
    <html>
      <head><title>HTML5 Movie</title></head>
      <body>
        <video src="/video/default.mp4" height="720" type="video/mp4">
          <source src="/video/movie-1080.mp4" label="1080p" type="video/mp4">
          <source src="/video/movie-4k.m3u8" data-quality="4K"
                  type="application/vnd.apple.mpegurl">
          <track kind="subtitles" src="/subtitles/zh.vtt"
                 srclang="zh-CN" label="中文">
          <track kind="captions" src="/subtitles/en.vtt"
                 srclang="en" label="English">
        </video>
      </body>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://media.test/movie/1"))
    )

    videos = [item for item in result.downloads if item.resource_type == ParsedResourceType.VIDEO]
    subtitles = [
        item for item in result.downloads if item.resource_type == ParsedResourceType.SUBTITLE
    ]
    assert [item.quality for item in videos] == ["720p", "1080p", "4K"]
    assert [item.source_url for item in videos] == [
        "https://media.test/video/default.mp4",
        "https://media.test/video/movie-1080.mp4",
        "https://media.test/video/movie-4k.m3u8",
    ]
    assert [(item.language, item.quality) for item in subtitles] == [
        ("zh-CN", "中文"),
        ("en", "English"),
    ]


def test_parser_extracts_json_ld_series_seasons_episodes_and_downloads():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "TVSeries",
          "name": "Example Series",
          "numberOfSeasons": 2,
          "containsSeason": [
            {
              "@type": "TVSeason",
              "seasonNumber": 1,
              "name": "Season One",
              "numberOfEpisodes": 2,
              "episode": [
                {
                  "@type": "TVEpisode",
                  "episodeNumber": 1,
                  "name": "Pilot",
                  "duration": "PT45M",
                  "video": [
                    {
                      "@type": "VideoObject",
                      "contentUrl": "/series/s1e1-720.mp4",
                      "height": 720,
                      "encodingFormat": "video/mp4"
                    },
                    {
                      "@type": "VideoObject",
                      "contentUrl": "/series/s1e1-1080.mp4",
                      "videoQuality": "1080p",
                      "encodingFormat": "video/mp4"
                    }
                  ],
                  "subtitle": {
                    "@type": "Subtitle",
                    "contentUrl": "/series/s1e1-zh.vtt",
                    "inLanguage": "zh-CN",
                    "encodingFormat": "text/vtt"
                  }
                },
                {
                  "@type": "TVEpisode",
                  "episodeNumber": 2,
                  "name": "Second Episode",
                  "contentUrl": "/series/s1e2.mp4"
                }
              ]
            }
          ]
        }
        </script>
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://series.test/show/1"))
    )

    assert result.media_type == ParsedMediaType.SERIES
    assert result.season_count == 2
    assert len(result.seasons) == 1
    season = result.seasons[0]
    assert season.season_number == 1
    assert season.episode_count == 2
    assert [episode.episode_number for episode in season.episodes] == [1, 2]
    assert [item.quality for item in season.episodes[0].downloads] == [
        "720p",
        "1080p",
        None,
    ]
    assert season.episodes[0].downloads[-1].resource_type == ParsedResourceType.SUBTITLE
    assert season.episodes[0].downloads[-1].language == "zh-CN"
    assert season.episodes[1].downloads[0].source_url == ("https://series.test/series/s1e2.mp4")


def test_parser_extracts_repeated_open_graph_video_qualities_and_meta_subtitle():
    html = """
    <html>
      <head>
        <title>Meta Video</title>
        <meta property="og:video" content="/video/720.mp4">
        <meta property="og:video" content="/video/1080.mp4">
        <meta property="og:video:height" content="720">
        <meta property="og:video:height" content="1080">
        <meta property="og:video:type" content="video/mp4">
        <meta property="og:video:type" content="video/mp4">
        <meta name="video:subtitle" content="/subtitles/movie.vtt">
      </head>
    </html>
    """

    async def fetcher(url: str) -> WebPageResponse:
        return response(html, url=url)

    result = asyncio.run(
        GenericWebPageParser(fetcher).parse(ParseRequest("https://meta-video.test/movie/1"))
    )

    assert [(item.quality, item.resource_type) for item in result.downloads] == [
        ("720p", ParsedResourceType.VIDEO),
        ("1080p", ParsedResourceType.VIDEO),
        (None, ParsedResourceType.SUBTITLE),
    ]
