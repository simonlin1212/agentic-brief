# Devpost Submission Copy

> Copy-paste ready. Replace only the demo-video URL after upload.

## Project name

Agentic Brief

## Tagline

An autonomous morning market briefing that finds agreement, disagreement, and thin evidence across financial news and video.

## Project URL

https://agentic-brief-web-qjv2kumm3q-as.a.run.app/

## Code repository

https://github.com/simonlin1212/agentic-brief

## Inspiration

Every morning I repeat the same research loop: scan financial news, watch current market commentary, decide which sectors are actually gaining attention, and work out whether several sources agree or one loud source is creating a false sense of consensus. Ordinary summarizers compress everything into a confident paragraph and hide the evidence quality. I wanted an agent that would complete the work before I opened my laptop, while preserving disagreements instead of smoothing them away.

## What it does

Agentic Brief runs unattended every morning. A News Scout reads current financial and central-bank RSS feeds. A separate Video Scout searches trusted official finance channels on YouTube, selects a substantive recent video, and uses Gemini 3.5 to inspect its actual audio and visible content. The two scouts are intentionally isolated and cannot see each other's state.

After both reports are complete, an Editor Agent produces four sections:

- TOP SIGNALS ranks sectors, giving more weight to themes present in both feeds.
- CONTRADICTIONS preserves disagreements between reporting and commentary.
- THIN ICE labels claims supported by only one source.
- WHAT CHANGED states what is genuinely unusual, or says that nothing material changed.

The result is written to Firestore and published to a responsive read-only briefing page. The public service cannot trigger model calls.

## How we built it

The agent workflow uses Google ADK with two isolated scout agents followed by an editor agent. All reasoning uses `gemini-3.5-flash` on Vertex AI in the `global` location. Live data comes from CNBC, MarketWatch, Federal Reserve RSS, and the YouTube Data API. Gemini's direct YouTube input reads the selected video's audio and frames rather than relying on its title or thumbnail.

The production system uses Google Cloud Run, Firestore, Cloud Scheduler, IAM, and Secret Manager. A private runner service accepts only authenticated OIDC requests from the Scheduler service account. A separate public Cloud Run service has read-only Firestore permissions. The YouTube key is mounted from Secret Manager and never enters the repository or container image.

## Challenges we ran into

The first major issue was region drift: Gemini 3.5 was available through Vertex AI in `global`, while a common `us-central1` default returned 404 and made downgrading to an ineligible model tempting. We converted that requirement into a startup validation and test.

The original Google News RSS endpoint returned 503 in the target environment, so we replaced it with several publisher and central-bank feeds and made individual feed failures non-fatal. Broad YouTube search also returned noisy and multilingual results, so we restricted discovery to five trusted official channels, filtered videos to 4–20 minutes, and ranked recent candidates locally.

The most subtle runtime bug came from constructing a temporary Gemini client in a chained expression. The underlying HTTP client closed before video analysis completed. Holding the client for the full request fixed the issue, and a lifecycle regression test now protects it.

Finally, the first cloud Scheduler test was accidentally triggered more than once. That exposed a useful production edge case: duplicate delivery must not spend model tokens, but a retry after a crashed runner must still be allowed. The runner now records an atomic 15-minute Firestore lease with a unique fencing token. Completed periods return immediately, active periods ask Scheduler to retry after the lease boundary, and stale workers cannot overwrite a replacement run. A verified duplicate completed in 0.22 seconds without calling Gemini.

## Accomplishments that we're proud of

- The system is autonomous from schedule to published result, not a chat demo.
- The two research paths are isolated by design, making the final comparison meaningful.
- Gemini reads the real finance video instead of summarizing metadata.
- The live run surfaced both agreement and a concrete contradiction around software and semiconductor guidance.
- Anonymous runner calls return HTTP 403, while the public viewer remains directly accessible.
- The final cloud release passed 48 tests with 87% package coverage and desktop/mobile browser QA.

## What we learned

Agent quality depends as much on information boundaries as prompt wording. Isolating the scouts made disagreement visible. We also learned that cloud configuration should encode eligibility rules: model version and region are enforced by code instead of being left as deployment notes. Finally, autonomous systems need honest failure boundaries. Partial RSS failure can degrade gracefully; missing all sources, an invalid credential, or an empty editor result must fail loudly.

## What's next

The next version will compare today's findings with historical Firestore briefings, measure which signals persisted, and add source-level evaluation metrics. It may also add more licensed data feeds, but `THIN ICE` will remain: expanding coverage should never hide how much evidence supports each claim.

## Built with

Google ADK, Gemini 3.5 Flash, Vertex AI, Cloud Run, Cloud Scheduler, Cloud Firestore, Secret Manager, YouTube Data API, Python, Flask, Gunicorn.

## Demo video

https://youtu.be/2GYxLUbTnRQ
