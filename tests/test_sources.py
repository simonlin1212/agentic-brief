"""Tests for live news and YouTube tools."""

import json
import weakref
from datetime import UTC, datetime

import pytest

from agentic_brief.tools import sources

RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Market test feed</title>
    <item>
      <title>Chip demand rises</title>
      <link>https://news.google.com/articles/new-chip</link>
      <pubDate>Fri, 28 Aug 2026 00:30:00 GMT</pubDate>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>chip demand rises</title>
      <link>https://news.google.com/articles/duplicate</link>
      <pubDate>Fri, 28 Aug 2026 00:20:00 GMT</pubDate>
      <source url="https://example.com">Duplicate Wire</source>
    </item>
    <item>
      <title>Fed signals patience</title>
      <link>https://news.google.com/articles/fed</link>
      <pubDate>Thu, 27 Aug 2026 23:45:00 GMT</pubDate>
      <source url="https://apnews.com">AP</source>
    </item>
    <item>
      <title>Old market story</title>
      <link>https://news.google.com/articles/old</link>
      <pubDate>Wed, 26 Aug 2026 23:00:00 GMT</pubDate>
      <source url="https://example.com">Old Wire</source>
    </item>
  </channel>
</rss>
"""


YOUTUBE_SAMPLE = {
    "items": [
        {
            "id": {"kind": "youtube#video", "videoId": "abc123DEF45"},
            "snippet": {
                "title": "Market outlook &amp; rates",
                "channelTitle": "Example Finance",
                "publishedAt": "2026-08-28T00:00:00Z",
            },
        },
        {
            "id": {"kind": "youtube#channel", "channelId": "ignored"},
            "snippet": {"title": "Not a video"},
        },
    ]
}


def test_parse_news_feed_filters_deduplicates_and_sorts() -> None:
    cutoff = datetime(2026, 8, 27, 12, tzinfo=UTC)

    result = sources._parse_news_feed(RSS_SAMPLE, cutoff)

    assert [item["title"] for item in result] == [
        "Chip demand rises",
        "Fed signals patience",
    ]
    assert result[0] == {
        "title": "Chip demand rises",
        "source": "Reuters",
        "url": "https://news.google.com/articles/new-chip",
        "published_at": "2026-08-28T00:30:00Z",
    }


def test_parse_news_feed_rejects_malformed_empty_feed() -> None:
    cutoff = datetime(2026, 8, 27, tzinfo=UTC)

    with pytest.raises(sources.SourceFetchError, match="RSS"):
        sources._parse_news_feed(b"<rss><broken>", cutoff)


def test_fetch_headlines_returns_json_and_validates_window(monkeypatch) -> None:
    monkeypatch.setattr(sources, "_download_news_feed", lambda _query: RSS_SAMPLE)
    monkeypatch.setattr(
        sources,
        "_utc_now",
        lambda: datetime(2026, 8, 28, 1, tzinfo=UTC),
    )

    result = json.loads(sources.fetch_headlines(hours_back=24))

    assert len(result) == 2
    with pytest.raises(ValueError, match="hours_back"):
        sources.fetch_headlines(hours_back=0)


def test_fetch_headlines_tolerates_one_failed_feed(monkeypatch) -> None:
    calls = 0

    def sometimes_fails(_feed_url: str) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sources.SourceFetchError("temporary failure")
        return RSS_SAMPLE

    monkeypatch.setattr(sources, "_download_news_feed", sometimes_fails)
    monkeypatch.setattr(
        sources,
        "_utc_now",
        lambda: datetime(2026, 8, 28, 1, tzinfo=UTC),
    )

    assert len(json.loads(sources.fetch_headlines(24))) == 2


def test_fetch_headlines_fails_when_every_feed_fails(monkeypatch) -> None:
    def always_fails(_feed_url: str) -> bytes:
        raise sources.SourceFetchError("temporary failure")

    monkeypatch.setattr(sources, "_download_news_feed", always_fails)

    with pytest.raises(sources.SourceFetchError, match="All .* feeds failed"):
        sources.fetch_headlines(24)


def test_parse_youtube_search_normalizes_video_results() -> None:
    assert sources._parse_youtube_search(YOUTUBE_SAMPLE) == [
        {
            "title": "Market outlook & rates",
            "video_id": "abc123DEF45",
            "channel": "Example Finance",
            "published_at": "2026-08-28T00:00:00Z",
            "video_url": "https://www.youtube.com/watch?v=abc123DEF45",
        }
    ]


def test_rank_video_results_matches_whole_terms_not_substrings() -> None:
    videos = [
        {
            "title": "A new chair arrives at the museum",
            "video_id": "abc123DEF45",
            "channel": "WSJ News",
            "published_at": "2026-08-28T01:00:00Z",
            "video_url": "https://www.youtube.com/watch?v=abc123DEF45",
        },
        {
            "title": "Market rates and software earnings",
            "video_id": "zyx987WVU65",
            "channel": "Bloomberg Television",
            "published_at": "2026-08-28T00:00:00Z",
            "video_url": "https://www.youtube.com/watch?v=zyx987WVU65",
        },
    ]

    ranked = sources._rank_video_results(videos, "software earnings", 5)

    assert [video["video_id"] for video in ranked] == ["zyx987WVU65"]


def test_search_finance_videos_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(sources, "YOUTUBE_API_KEY", "")

    with pytest.raises(sources.ConfigurationError, match="YOUTUBE_API_KEY"):
        sources.search_finance_videos("market outlook")


def test_search_finance_videos_uses_bounded_official_request(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(sources, "YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(
        sources,
        "_utc_now",
        lambda: datetime(2026, 8, 28, 1, tzinfo=UTC),
    )

    def fake_request(params: dict[str, object]) -> dict[str, object]:
        captured.append(params)
        return YOUTUBE_SAMPLE

    monkeypatch.setattr(sources, "_request_youtube_search", fake_request)

    result = json.loads(sources.search_finance_videos("market outlook", 3))

    assert len(result) == 1
    assert len(captured) == len(sources.TRUSTED_YOUTUBE_CHANNELS)
    assert {request["channelId"] for request in captured} == set(
        sources.TRUSTED_YOUTUBE_CHANNELS.values()
    )
    for request in captured:
        assert request["part"] == "snippet"
        assert request["type"] == "video"
        assert request["maxResults"] == 3
        assert request["videoDuration"] == "medium"
        assert request["publishedAfter"] == "2026-08-27T01:00:00Z"
        assert "q" not in request
        assert "key" not in request


def test_youtube_http_error_suppresses_secret_request_url(monkeypatch) -> None:
    secret = "must-not-appear"
    request = sources.httpx.Request(
        "GET", f"https://www.googleapis.com/youtube/v3/search?key={secret}"
    )
    response = sources.httpx.Response(403, request=request)

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def get(self, *_args, **_kwargs):
            return response

    monkeypatch.setattr(sources.httpx, "Client", FakeClient)
    monkeypatch.setattr(sources, "YOUTUBE_API_KEY", secret)

    with pytest.raises(sources.SourceFetchError) as exc_info:
        sources._request_youtube_search({"part": "snippet"})

    assert secret not in str(exc_info.value)
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc123DEF45",
        "https://youtube.com/watch?v=abc123DEF45",
        "https://youtu.be/abc123DEF45",
    ],
)
def test_validate_youtube_url_accepts_public_video_urls(url: str) -> None:
    assert sources._validate_youtube_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/watch?v=abc123DEF45",
        "https://youtube.com.evil.example/watch?v=abc123DEF45",
        "https://example.com/video.mp4",
        "https://www.youtube.com/watch?v=short",
    ],
)
def test_validate_youtube_url_rejects_unsafe_or_invalid_urls(url: str) -> None:
    with pytest.raises(ValueError, match="YouTube"):
        sources._validate_youtube_url(url)


def test_analyze_video_calls_vertex_with_video_before_prompt(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeResponse:
        text = "The presenter expects capex to remain elevated."

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.update(kwargs)
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(sources, "_create_genai_client", lambda: FakeClient())

    result = sources.analyze_video("https://www.youtube.com/watch?v=abc123DEF45")

    assert result == "The presenter expects capex to remain elevated."
    assert calls["model"] == "gemini-3.5-flash"
    assert len(calls["contents"]) == 2
    assert calls["contents"][1].startswith("Analyze this finance video")


def test_analyze_video_keeps_client_alive_during_request(monkeypatch) -> None:
    class FakeResponse:
        text = "Analysis"

    class FakeModels:
        def __init__(self, client) -> None:
            self.client_ref = weakref.ref(client)

        def generate_content(self, **_kwargs):
            assert self.client_ref() is not None
            return FakeResponse()

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels(self)

    monkeypatch.setattr(sources, "_create_genai_client", FakeClient)

    result = sources.analyze_video("https://www.youtube.com/watch?v=abc123DEF45")

    assert result == "Analysis"
