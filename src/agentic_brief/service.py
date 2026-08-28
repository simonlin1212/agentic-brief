"""Cloud Run HTTP surface for the viewer and autonomous runner."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import bleach
from flask import Flask, abort, jsonify, render_template
from markdown import markdown
from markupsafe import Markup, escape

from agentic_brief.pipeline import BriefingResult, generate_briefing
from agentic_brief.store import BriefStore, ClaimStatus, FirestoreBriefStore

BriefGenerator = Callable[[], Awaitable[BriefingResult]]
ExecutionKeyFactory = Callable[[], str]
logger = logging.getLogger(__name__)

_MARKDOWN_TAGS = {
    "a",
    "blockquote",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}


def _json_safe(document: dict[str, Any]) -> dict[str, Any]:
    """Convert Firestore timestamps into stable API strings."""
    return {
        key: value.isoformat().replace("+00:00", "Z")
        if isinstance(value, datetime)
        else value
        for key, value in document.items()
    }


def _render_safe_markdown(value: str) -> Markup:
    """Format model output while neutralising any embedded raw HTML."""
    normalized = re.sub(r"(?m)^ {1,3}([*+-]) ", r"    \1 ", value)
    escaped = str(escape(normalized))
    rendered = markdown(escaped, extensions=["sane_lists"])
    sanitized = bleach.clean(
        rendered,
        tags=_MARKDOWN_TAGS,
        attributes={"a": ["href", "title"]},
        protocols={"https"},
        strip=True,
    )
    return Markup(sanitized)


def _singapore_execution_key() -> str:
    """Return the daily idempotency key used by the 07:00 SGT schedule."""
    return datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()


def create_app(
    *,
    mode: str | None = None,
    store: BriefStore | None = None,
    brief_generator: BriefGenerator = generate_briefing,
    execution_key_factory: ExecutionKeyFactory = _singapore_execution_key,
) -> Flask:
    """Create either the public read-only viewer or private runner service."""
    service_mode = (mode or os.getenv("AGENTIC_BRIEF_SERVICE_MODE", "web")).strip()
    if service_mode not in {"web", "runner"}:
        raise RuntimeError("AGENTIC_BRIEF_SERVICE_MODE must be 'web' or 'runner'.")

    app = Flask(__name__)
    active_store = store or FirestoreBriefStore()

    @app.get("/health")
    def health():
        return jsonify({"service": service_mode, "status": "ok"})

    if service_mode == "web":

        @app.get("/")
        def home():
            latest = active_store.get_latest()
            safe_latest = _json_safe(latest) if latest else None
            brief_html = (
                _render_safe_markdown(str(safe_latest["daily_brief"]))
                if safe_latest
                else None
            )
            return render_template(
                "index.html",
                brief=safe_latest,
                brief_html=brief_html,
            )

        @app.get("/api/latest")
        def latest_api():
            latest = active_store.get_latest()
            if latest is None:
                abort(404)
            return jsonify(_json_safe(latest))

    else:

        @app.post("/run")
        def run_pipeline():
            execution_key = execution_key_factory()
            claim = active_store.claim(execution_key)
            if claim.status == ClaimStatus.COMPLETED:
                return jsonify(
                    {
                        "execution_key": execution_key,
                        "status": "already_completed",
                    }
                )
            if claim.status == ClaimStatus.RUNNING:
                return (
                    jsonify(
                        {
                            "execution_key": execution_key,
                            "status": "already_running",
                        }
                    ),
                    503,
                    {"Retry-After": "900"},
                )
            try:
                if claim.token is None:
                    raise RuntimeError("acquired execution claim has no fencing token")
                result = asyncio.run(brief_generator())
                active_store.save(
                    result,
                    execution_key=execution_key,
                    claim_token=claim.token,
                )
            except Exception:
                try:
                    if claim.token is not None:
                        active_store.release_claim(execution_key, claim.token)
                except Exception:
                    logger.exception("Failed to release scheduled execution claim")
                logger.exception("Scheduled briefing run failed")
                return jsonify({"status": "failed"}), 500
            return jsonify({"run_id": result.run_id, "status": "completed"}), 201

    return app
