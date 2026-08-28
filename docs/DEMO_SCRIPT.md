# Four-Minute Demo Script

Target length: 3:45–4:00. Spoken copy is ready for English narration.

## 0:00–0:25 — The problem

**On screen:** Open the public Agentic Brief page at the hero section.

**Voiceover:**

> Every morning, market research starts with the same manual loop: scan the news, watch current financial commentary, decide what actually changed, and work out whether several sources agree or one loud source is creating a false consensus. Agentic Brief completes that work autonomously before the day starts. It is not a chatbot waiting for a prompt.

## 0:25–0:55 — The output

**On screen:** Scroll through TOP SIGNALS, CONTRADICTIONS, THIN ICE, and WHAT CHANGED.

**Voiceover:**

> This is a real cloud-generated briefing. Top Signals ranks sectors by fresh attention. Contradictions preserves disagreements instead of blending them into a vague summary. Thin Ice marks claims supported by only one feed. What Changed states what is genuinely unusual, and is allowed to say that nothing changed.

## 0:55–1:35 — The agent design

**On screen:** Show `docs/architecture.svg`, zoom into the collector section.

**Voiceover:**

> The workflow is built with Google ADK. A News Scout reads current CNBC, MarketWatch, and Federal Reserve feeds. A separate Video Scout searches trusted official finance channels through the YouTube Data API. The scouts cannot see each other's output. That information boundary is deliberate: one source cannot influence how the other source is interpreted. Only after both finish does the Editor Agent compare their reports.

## 1:35–2:05 — Gemini reads video

**On screen:** Show `src/agentic_brief/tools/sources.py`, highlighting `Part.from_uri`, then briefly show the video URL in the current API result.

**Voiceover:**

> The Video Scout does not summarize a thumbnail. Gemini 3.5 on Vertex AI receives the public YouTube video directly and inspects its audio and visible frames. It extracts the actual thesis, reasoning, timeframe, falsifiable predictions, and caveats. Recent videos are limited to four to twenty minutes so an unattended run remains bounded.

## 2:05–2:45 — Autonomous Google Cloud execution

**On screen:** Cloud Console. Show Cloud Scheduler job `agentic-brief-daily`, then Cloud Run services `agentic-brief-runner` and `agentic-brief-web`, then Firestore collections.

**Voiceover:**

> Cloud Scheduler triggers the private runner every morning at seven, Singapore time. It uses an OIDC service identity with only Cloud Run Invoker permission. Anonymous requests to the runner receive HTTP four-oh-three. Completed runs are written atomically to Firestore. A separate public Cloud Run service has read-only database access and displays the latest result. The YouTube credential is stored in Secret Manager, outside both the repository and container image.

## 2:45–3:15 — Evidence from a real run

**On screen:** Return to the live page. Highlight the software consensus and the Marvell or guidance contradiction.

**Voiceover:**

> In this live run, both scouts raised software and semiconductors, but they did not tell the same story. News coverage framed major earnings as a recovery signal. Video commentary warned that market breadth remained narrow and strong guidance was still being punished. The Editor kept that conflict visible and marked the claims that rested on only one source.

## 3:15–3:40 — Reliability

**On screen:** Terminal showing `40 passed` and coverage, then GitHub Actions.

**Voiceover:**

> The system fails fast if deployment drifts below Gemini three point five or away from the required global Vertex location. Tests cover source failures, secret-safe errors, URL validation, Firestore writes, public and private routes, and safe rendering. The first cloud release passed more than forty tests with eighty-seven percent package coverage.

## 3:40–3:58 — Close

**On screen:** Public page hero and URL.

**Voiceover:**

> Agentic Brief turns a real daily research process into autonomous, evidence-aware work. The result is ready before the reader arrives, and uncertainty remains visible instead of being summarized away.

## Recording checklist

- Keep the browser at 1440×900 or larger.
- Show the `.run.app` URL in the address bar.
- Show the Google Cloud project name and Cloud Run/Scheduler panels.
- Never reveal `.env`, API keys, Secret Manager values, billing IDs, or account tokens.
- Blur personal account email if it appears prominently.
- Keep the final edit under four minutes.
