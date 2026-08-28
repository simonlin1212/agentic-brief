"""Rate limiting for the free Gemini API tier.

The free tier allows 5 requests per minute per model. The pipeline issues
roughly a dozen calls per run, so without pacing it trips 429 immediately.
This spaces calls out just enough to stay under the ceiling.

Vertex AI has no such ceiling, so throttling switches itself off whenever
GOOGLE_GENAI_USE_VERTEXAI is set. Override either way with
AGENTIC_BRIEF_FREE_TIER=1/0.
"""

import asyncio
import os
import time

_ON_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() in ("TRUE", "1")

# Vertex has generous quota; only the free API tier needs pacing.
FREE_TIER = os.getenv("AGENTIC_BRIEF_FREE_TIER", "0" if _ON_VERTEX else "1") == "1"

# Free tier is 5 req/min/model; 13s leaves headroom for clock drift.
_MIN_INTERVAL_SECONDS = float(os.getenv("AGENTIC_BRIEF_MIN_INTERVAL", "13"))

_lock = asyncio.Lock()
_last_call_at = 0.0


async def throttle_model_calls(callback_context, llm_request):
    """Delay each model call so the free tier's per-minute cap is respected.

    Registered as ADK's before_model_callback. Returning None lets the request
    proceed unchanged; the only side effect is the wait.
    """
    if not FREE_TIER:
        return None

    global _last_call_at
    async with _lock:
        elapsed = time.monotonic() - _last_call_at
        wait = _MIN_INTERVAL_SECONDS - elapsed
        if wait > 0:
            print(f"  [throttle] 等待 {wait:.0f}s（免费层 5 次/分钟）")
            await asyncio.sleep(wait)
        _last_call_at = time.monotonic()
    return None
