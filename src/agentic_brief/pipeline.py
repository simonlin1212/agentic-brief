"""Execute one autonomous Agentic Brief research cycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from agentic_brief.agent import root_agent

APP_NAME = "agentic_brief"
USER_ID = "scheduled-runner"
TRIGGER = (
    "Produce today's briefing. Focus on US equities and the sectors with the "
    "most movement in the last 24 hours."
)


@dataclass(frozen=True, slots=True)
class BriefingResult:
    """Persistable output from all three agents in one pipeline run."""

    run_id: str
    generated_at: datetime
    daily_brief: str
    news_findings: str
    video_findings: str

    def to_document(self) -> dict[str, Any]:
        """Return the Firestore representation of this run."""
        return asdict(self)


async def generate_briefing(runner: Any | None = None) -> BriefingResult:
    """Run both scouts and the editor, then return their durable outputs."""
    active_runner = runner or InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await active_runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    async for _event in active_runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=TRIGGER)]),
    ):
        pass

    final = await active_runner.session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    state = final.state
    daily_brief = str(state.get("daily_brief", "")).strip()
    if not daily_brief:
        raise RuntimeError("Agent pipeline completed without a daily_brief output.")

    generated_at = datetime.now(UTC)
    run_id = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    return BriefingResult(
        run_id=run_id,
        generated_at=generated_at,
        daily_brief=daily_brief,
        news_findings=str(state.get("news_findings", "")),
        video_findings=str(state.get("video_findings", "")),
    )
