"""Central configuration for Agentic Brief."""

import os
import re

from dotenv import load_dotenv

load_dotenv()


def _validate_location(value: str) -> str:
    """Keep the hackathon-required Gemini location from drifting."""
    location = value.strip().lower()
    if location != "global":
        raise RuntimeError(
            "GOOGLE_CLOUD_LOCATION must be 'global' for Gemini 3.5; "
            f"received {value!r}."
        )
    return location


def _validate_lookback_hours(value: str) -> int:
    """Return a bounded lookback window suitable for daily source scans."""
    try:
        hours = int(value)
    except ValueError as exc:
        raise RuntimeError(
            "AGENTIC_BRIEF_LOOKBACK_HOURS must be an integer from 1 to 168."
        ) from exc
    if not 1 <= hours <= 168:
        raise RuntimeError("AGENTIC_BRIEF_LOOKBACK_HOURS must be from 1 to 168.")
    return hours


def _validate_model(value: str) -> str:
    """Reject model overrides below the hackathon's Gemini 3.5 floor."""
    model = value.strip()
    match = re.fullmatch(r"gemini-(\d+)\.(\d+)(?:-[a-z0-9.-]+)?", model)
    if match is None or tuple(map(int, match.groups())) < (3, 5):
        raise RuntimeError(
            f"Agentic Brief requires Gemini 3.5 or newer; received {value!r}."
        )
    return model


# Hackathon requirement: Gemini 3.5 or newer. Do NOT downgrade to 2.5.
MODEL_FAST = "gemini-3.5-flash"
MODEL_DEEP = _validate_model(os.getenv("AGENTIC_BRIEF_DEEP_MODEL", "gemini-3.5-flash"))

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = _validate_location(os.getenv("GOOGLE_CLOUD_LOCATION", "global"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# How far back each run looks for material.
LOOKBACK_HOURS = _validate_lookback_hours(
    os.getenv("AGENTIC_BRIEF_LOOKBACK_HOURS", "24")
)
