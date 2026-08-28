"""Central configuration for Agentic Brief."""
import os
from dotenv import load_dotenv

load_dotenv()

# Hackathon requirement: Gemini 3.5 or newer. Do NOT downgrade to 2.5.
MODEL_FAST = "gemini-3.5-flash"
MODEL_DEEP = os.getenv("AGENTIC_BRIEF_DEEP_MODEL", "gemini-3.5-flash")

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# How far back each run looks for material.
LOOKBACK_HOURS = int(os.getenv("AGENTIC_BRIEF_LOOKBACK_HOURS", "24"))
