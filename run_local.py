"""Run one briefing cycle locally and print the result.

This is the development entry point. Cloud Run uses app.py instead.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from agentic_brief.agent import root_agent  # noqa: E402

TRIGGER = (
    "Produce today's briefing. Focus on US equities and the sectors with the "
    "most movement in the last 24 hours."
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="agentic_brief")
    session = await runner.session_service.create_session(
        app_name="agentic_brief", user_id="simon"
    )

    async for event in runner.run_async(
        user_id="simon",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=TRIGGER)]),
    ):
        if event.author and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"\n{'=' * 60}\n[{event.author}]\n{'=' * 60}\n{text}")

    final = await runner.session_service.get_session(
        app_name="agentic_brief", user_id="simon", session_id=session.id
    )
    print(f"\n{'=' * 60}\nstate 里的产出键: {list(final.state.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
