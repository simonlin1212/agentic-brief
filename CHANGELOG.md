# Changelog

All notable changes to Agentic Brief are documented here.

## 0.1.0 — 2026-08-28

- Built the Google ADK workflow with two isolated scouts and one editor agent.
- Enforced Gemini 3.5+ and the Vertex AI `global` location at startup.
- Replaced stub data with live financial RSS and YouTube Data API sources.
- Added direct Gemini analysis of public finance videos.
- Added Firestore persistence, a private Cloud Run runner, and a public viewer.
- Added a daily 07:00 Asia/Singapore Cloud Scheduler job using OIDC.
- Added crash-safe daily idempotency with a 15-minute lease and fenced ownership tokens.
- Stored the YouTube credential in Secret Manager and split read/write identities.
- Added responsive product UI, safe Markdown rendering, and browser QA.
- Added 40+ tests with 87% package coverage at the first cloud release.
