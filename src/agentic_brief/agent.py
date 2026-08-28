"""Agentic Brief - autonomous morning research briefing.

Two scouts read news and finance video; an editor then synthesises one
briefing. Runs unattended on a schedule - no chat loop.

X/Twitter was scoped out: its API has no usable free read tier, and routing
it through a local machine would break the "everything runs in the cloud"
property this agent is built on.

On the free Gemini tier the scouts run one after another with pacing between
calls. With billing enabled (AGENTIC_BRIEF_FREE_TIER=0) they run concurrently.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from agentic_brief import prompt
from agentic_brief.config import MODEL_DEEP, MODEL_FAST
from agentic_brief.throttle import FREE_TIER, throttle_model_calls
from agentic_brief.tools.sources import (
    analyze_video,
    fetch_headlines,
    search_finance_videos,
)

news_scout = LlmAgent(
    name="news_scout",
    model=MODEL_FAST,
    description="Reads financial news and extracts market-moving events.",
    instruction=prompt.NEWS_SCOUT,
    tools=[fetch_headlines],
    output_key="news_findings",
    before_model_callback=throttle_model_calls,
)

video_scout = LlmAgent(
    name="video_scout",
    model=MODEL_FAST,
    description="Watches finance videos and extracts their actual arguments.",
    instruction=prompt.VIDEO_SCOUT,
    tools=[search_finance_videos, analyze_video],
    output_key="video_findings",
    before_model_callback=throttle_model_calls,
)

_scouts = [news_scout, video_scout]

# The scouts share no state and never see each other's output, so one loud
# source cannot colour the others' reading. That property holds whether they
# run concurrently or in sequence - only the wall-clock cost differs.
collectors = (
    SequentialAgent(
        name="collectors",
        description="Runs the source scouts one at a time (free-tier pacing).",
        sub_agents=_scouts,
    )
    if FREE_TIER
    else ParallelAgent(
        name="collectors",
        description="Runs both source scouts concurrently.",
        sub_agents=_scouts,
    )
)

editor = LlmAgent(
    name="editor",
    model=MODEL_DEEP,
    description="Synthesises the scout reports into one briefing.",
    instruction=prompt.SYNTHESIZER,
    output_key="daily_brief",
    before_model_callback=throttle_model_calls,
)

root_agent = SequentialAgent(
    name="agentic_brief",
    description="Collect from both sources, then synthesise one briefing.",
    sub_agents=[collectors, editor],
)
