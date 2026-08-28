"""Live financial-news and YouTube data tools for Agentic Brief."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
from google import genai
from google.genai import errors, types

from agentic_brief.config import LOOKBACK_HOURS, MODEL_FAST, YOUTUBE_API_KEY

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
NEWS_FEEDS = (
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://www.federalreserve.gov/feeds/press_monetary.xml",
)
TRUSTED_YOUTUBE_CHANNELS = {
    "CNBC Television": "UCrp_UI8XtuYfpiqluWLD7Lw",
    "Bloomberg Television": "UCIALMKvObZNtJ6AmdCLP7Lg",
    "Yahoo Finance": "UCEAZeUIeJs0IjQiqTCdVSIg",
    "Financial Times": "UCoUxsWakJucWg46KW5RsvPw",
    "WSJ News": "UCMliswJ7oukCeW35GSayhRA",
}
_MARKET_TERMS = {
    "ai",
    "bank",
    "earnings",
    "economy",
    "fed",
    "inflation",
    "market",
    "nvidia",
    "oil",
    "rate",
    "rates",
    "sector",
    "semiconductor",
    "stock",
    "stocks",
}
_MARKET_PHRASES = {"wall street"}
_QUERY_STOPWORDS = {"and", "for", "from", "market", "outlook", "stock", "stocks", "the"}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HTTP_TIMEOUT_SECONDS = 12.0
_MAX_HEADLINES = 30
_MAX_PER_FEED = 10
logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """Raised when a required integration setting is missing."""


class SourceFetchError(RuntimeError):
    """Raised when an external source fails or returns unusable data."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _download_news_feed(feed_url: str) -> bytes:
    headers = {"User-Agent": "AgenticBrief/0.1 (+hackathon research agent)"}
    try:
        with httpx.Client(
            timeout=_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(feed_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(
            f"News RSS returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise SourceFetchError("News RSS could not be reached.") from exc
    return response.content


def _entry_datetime(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def _parse_news_feed(feed_bytes: bytes, cutoff: datetime) -> list[dict[str, str]]:
    parsed = feedparser.parse(feed_bytes)
    if getattr(parsed, "bozo", 0) and not parsed.entries:
        raise SourceFetchError("RSS feed was malformed and contained no entries.")

    feed_title = unescape(str(parsed.feed.get("title", "Unknown source"))).strip()
    findings: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for entry in parsed.entries:
        published_at = _entry_datetime(entry)
        if published_at is None or published_at < cutoff:
            continue

        title = unescape(str(entry.get("title", ""))).strip()
        link = str(entry.get("link", "")).strip()
        source_data = entry.get("source") or {}
        source = str(source_data.get("title", feed_title)).strip()
        normalized_title = " ".join(title.casefold().split())
        if not title or not link or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        findings.append(
            {
                "title": title,
                "source": source or "Unknown source",
                "url": link,
                "published_at": _iso_z(published_at),
            }
        )

    findings.sort(key=lambda item: item["published_at"], reverse=True)
    return findings


def fetch_headlines(hours_back: int = 24) -> str:
    """Fetches financial news headlines from the last N hours.

    Args:
        hours_back: How many hours of history to pull. Defaults to 24.

    Returns:
        JSON array of headline objects with title, source, url, published_at.

    Raises:
        ValueError: If hours_back is outside the supported 1-168 hour range.
        SourceFetchError: If the RSS source is unavailable or malformed.
    """
    if not 1 <= hours_back <= 168:
        raise ValueError("hours_back must be from 1 to 168.")

    cutoff = _utc_now() - timedelta(hours=hours_back)
    combined: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    successful_feeds = 0
    for feed_url in NEWS_FEEDS:
        try:
            feed_items = _parse_news_feed(_download_news_feed(feed_url), cutoff)
        except SourceFetchError as exc:
            logger.warning(
                "Skipping unavailable RSS feed %s: %s",
                urlparse(feed_url).hostname,
                exc,
            )
            continue
        successful_feeds += 1
        for item in feed_items[:_MAX_PER_FEED]:
            normalized_title = " ".join(item["title"].casefold().split())
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)
            combined.append(item)

    if successful_feeds == 0:
        raise SourceFetchError(f"All {len(NEWS_FEEDS)} news RSS feeds failed.")

    combined.sort(key=lambda item: item["published_at"], reverse=True)
    return json.dumps(combined[:_MAX_HEADLINES], ensure_ascii=False)


def _request_youtube_search(params: dict[str, object]) -> dict[str, Any]:
    request_params = {**params, "key": YOUTUBE_API_KEY}
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = client.get(YOUTUBE_SEARCH_URL, params=request_params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(
            f"YouTube Data API returned HTTP {exc.response.status_code}."
        ) from None
    except httpx.RequestError:
        raise SourceFetchError("YouTube Data API could not be reached.") from None
    except ValueError as exc:
        raise SourceFetchError("YouTube Data API returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise SourceFetchError("YouTube Data API returned an invalid payload.")
    return payload


def _parse_youtube_search(payload: dict[str, Any]) -> list[dict[str, str]]:
    videos: list[dict[str, str]] = []
    for item in payload.get("items", []):
        identity = item.get("id", {})
        snippet = item.get("snippet", {})
        if identity.get("kind") != "youtube#video":
            continue
        video_id = str(identity.get("videoId", ""))
        if not _VIDEO_ID_RE.fullmatch(video_id):
            continue
        videos.append(
            {
                "title": unescape(str(snippet.get("title", ""))).strip(),
                "video_id": video_id,
                "channel": unescape(str(snippet.get("channelTitle", ""))).strip(),
                "published_at": str(snippet.get("publishedAt", "")),
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return videos


def _rank_video_results(
    videos: list[dict[str, str]], query: str, max_results: int
) -> list[dict[str, str]]:
    query_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", query.casefold())
        if len(token) >= 3 and token not in _QUERY_STOPWORDS
    }

    def score(video: dict[str, str]) -> tuple[int, str]:
        title = video["title"].casefold()
        title_terms = set(re.findall(r"[a-z0-9]+", title))
        query_hits = sum(term in title_terms for term in query_terms)
        market_hits = sum(term in title_terms for term in _MARKET_TERMS)
        market_hits += sum(phrase in title for phrase in _MARKET_PHRASES)
        return query_hits * 3 + market_hits, video["published_at"]

    deduplicated: dict[str, dict[str, str]] = {}
    for video in videos:
        deduplicated.setdefault(video["video_id"], video)
    relevant = [video for video in deduplicated.values() if score(video)[0] > 0]
    return sorted(relevant, key=score, reverse=True)[:max_results]


def search_finance_videos(query: str, max_results: int = 5) -> str:
    """Searches YouTube for recent finance videos matching a query.

    Args:
        query: Search term, e.g. "semiconductor outlook".
        max_results: Maximum videos to return, from 1 to 10. Defaults to 5.

    Returns:
        JSON array with title, video_id, channel, published_at, video_url.

    Raises:
        ConfigurationError: If YOUTUBE_API_KEY is not configured.
        ValueError: If query or max_results is invalid.
        SourceFetchError: If YouTube returns an error or invalid response.
    """
    clean_query = query.strip()
    if not clean_query or len(clean_query) > 200:
        raise ValueError("query must contain from 1 to 200 characters.")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be from 1 to 10.")
    if not YOUTUBE_API_KEY:
        raise ConfigurationError(
            "YOUTUBE_API_KEY is required for YouTube Data API search."
        )

    published_after = _utc_now() - timedelta(hours=LOOKBACK_HOURS)
    base_params: dict[str, object] = {
        "part": "snippet",
        "type": "video",
        "order": "date",
        "maxResults": 3,
        "videoDuration": "medium",
        "publishedAfter": _iso_z(published_after),
        "regionCode": "US",
        "relevanceLanguage": "en",
        "safeSearch": "moderate",
    }
    candidates: list[dict[str, str]] = []
    for channel_id in TRUSTED_YOUTUBE_CHANNELS.values():
        payload = _request_youtube_search({**base_params, "channelId": channel_id})
        candidates.extend(_parse_youtube_search(payload))

    return json.dumps(
        _rank_video_results(candidates, clean_query, max_results),
        ensure_ascii=False,
    )


def _validate_youtube_url(video_url: str) -> str:
    parsed = urlparse(video_url)
    if parsed.scheme != "https":
        raise ValueError("A valid HTTPS YouTube video URL is required.")

    host = (parsed.hostname or "").lower()
    video_id = ""
    if host in {"youtube.com", "www.youtube.com"} and parsed.path == "/watch":
        query_values = httpx.QueryParams(parsed.query)
        video_id = query_values.get("v", "")
    elif host == "youtu.be" and parsed.path.count("/") == 1:
        video_id = parsed.path.removeprefix("/")

    if not _VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("A valid public YouTube video URL is required.")
    return video_url


def _create_genai_client() -> genai.Client:
    return genai.Client(
        http_options=types.HttpOptions(api_version="v1", timeout=120_000)
    )


def analyze_video(video_url: str) -> str:
    """Analyses a YouTube video's actual argument using Gemini's video reading.

    Args:
        video_url: Full public YouTube URL of the video to analyse.

    Returns:
        A summary of the argument, reasoning, timeframe, and predictions.

    Raises:
        ValueError: If video_url is not a supported public YouTube URL.
        SourceFetchError: If Vertex AI fails or returns no analysis.
    """
    safe_url = _validate_youtube_url(video_url)
    prompt = (
        "Analyze this finance video using both its audio and visible content. "
        "Extract the presenter's actual thesis, supporting evidence, affected "
        "market sectors, timeframe, falsifiable predictions, and important "
        "caveats. Distinguish claims from observed facts. Return concise prose "
        "with timestamps for the strongest evidence."
    )
    client = _create_genai_client()
    try:
        response = client.models.generate_content(
            model=MODEL_FAST,
            contents=[
                types.Part.from_uri(
                    file_uri=safe_url,
                    mime_type="video/mp4",
                    media_resolution="MEDIA_RESOLUTION_LOW",
                ),
                prompt,
            ],
        )
    except errors.APIError as exc:
        raise SourceFetchError(
            f"Vertex AI could not analyze the YouTube video (HTTP {exc.code})."
        ) from exc
    except httpx.HTTPError:
        raise SourceFetchError("Vertex AI video analysis timed out.") from None

    analysis = (response.text or "").strip()
    if not analysis:
        raise SourceFetchError("Vertex AI returned an empty video analysis.")
    return analysis
