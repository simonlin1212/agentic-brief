"""Tests for one complete ADK briefing cycle."""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from agentic_brief.pipeline import generate_briefing


class FakeSessionService:
    """Minimal ADK session service used by pipeline tests."""

    def __init__(self, state: dict[str, str]) -> None:
        self._state = state

    async def create_session(self, **_kwargs):
        return SimpleNamespace(id="session-1")

    async def get_session(self, **_kwargs):
        return SimpleNamespace(state=self._state)


class FakeRunner:
    """Minimal runner that produces no intermediate events."""

    def __init__(self, state: dict[str, str]) -> None:
        self.session_service = FakeSessionService(state)

    async def run_async(self, **_kwargs) -> AsyncIterator[object]:
        if False:
            yield object()


@pytest.mark.anyio
async def test_generate_briefing_returns_all_agent_outputs() -> None:
    runner = FakeRunner(
        {
            "daily_brief": "# Top signals\nSoftware",
            "news_findings": '[{"event":"earnings"}]',
            "video_findings": '[{"claim":"AI demand"}]',
        }
    )

    result = await generate_briefing(runner=runner)

    assert result.daily_brief == "# Top signals\nSoftware"
    assert result.news_findings.startswith("[")
    assert result.video_findings.startswith("[")
    assert result.run_id.endswith("Z")
    assert result.generated_at.tzinfo is not None


@pytest.mark.anyio
async def test_generate_briefing_rejects_missing_editor_output() -> None:
    runner = FakeRunner({"news_findings": "[]", "video_findings": "[]"})

    with pytest.raises(RuntimeError, match="daily_brief"):
        await generate_briefing(runner=runner)
