"""Placeholder data sources.

These return fixed sample payloads so the orchestration can be verified before
real API credentials exist. Each one gets replaced by a live implementation;
the signature and docstring stay the same so the agents do not change.
"""
import json


def fetch_headlines(hours_back: int = 24) -> str:
    """Fetches financial news headlines from the last N hours.

    Args:
        hours_back: How many hours of history to pull. Defaults to 24.

    Returns:
        JSON array of headline objects with title, source, url, published_at.
    """
    return json.dumps([
        {"title": "Fed officials signal patience on further cuts",
         "source": "Reuters", "url": "https://example.com/1",
         "published_at": "2026-08-26T11:00:00Z"},
        {"title": "Chipmaker guides Q4 above consensus on datacenter demand",
         "source": "Bloomberg", "url": "https://example.com/2",
         "published_at": "2026-08-26T09:30:00Z"},
    ])


def search_finance_videos(query: str, max_results: int = 5) -> str:
    """Searches YouTube for recent finance videos matching a query.

    Args:
        query: Search term, e.g. "semiconductor outlook".
        max_results: Maximum videos to return. Defaults to 5.

    Returns:
        JSON array with title, video_id, channel, published_at.
    """
    return json.dumps([
        {"title": "Why the datacenter buildout is not slowing",
         "video_id": "dQw4w9WgXcQ", "channel": "Example Finance",
         "published_at": "2026-08-26T07:00:00Z"},
    ])


def analyze_video(video_url: str) -> str:
    """Analyses a YouTube video's actual argument using Gemini's video reading.

    Args:
        video_url: Full YouTube URL of the video to analyse.

    Returns:
        A summary of the argument, reasoning, timeframe, and predictions.
    """
    return (f"[stub] Argument extracted from {video_url}: capex cycle has "
            "further to run; presenter cites three quarters of guide-ups.")
