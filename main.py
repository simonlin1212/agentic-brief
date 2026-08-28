"""Gunicorn entry point for both Cloud Run services."""

from agentic_brief.service import create_app

app = create_app()
