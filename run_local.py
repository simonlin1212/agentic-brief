"""Run one briefing cycle locally and print the result.

This is the development entry point. Cloud Run uses app.py instead.
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from agentic_brief.pipeline import generate_briefing  # noqa: E402


async def main() -> None:
    result = await generate_briefing()
    print(result.daily_brief)


if __name__ == "__main__":
    asyncio.run(main())
