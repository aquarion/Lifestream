"""FastAPI webserver for Lifestream.

Serves the OAuth callback route that replaces CodeFetcher9000's dedicated
per-flow listener (see lifestream.core.code_fetcher for the importer-CLI
side of that handoff) and a health check, plus a base for future #134/#135
API routes. Run by supervisor.py via uvicorn, behind a reverse proxy that
terminates TLS.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lifestream.core.config import config

logger = logging.getLogger("Webserver")


def _allowed_origins() -> list[str]:
    """Parse the comma-separated [webserver] allowed_origins config value."""
    raw = config.get("webserver", "allowed_origins", fallback="")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(lifespan=None) -> FastAPI:
    """Build the FastAPI app: CORS, health check, and (Task 3) the OAuth
    catcher route. `lifespan` is an optional async context manager factory
    (see supervisor.py's build_app), used to hook subsystem startup/shutdown
    into uvicorn's own signal handling."""
    app = FastAPI(title="Lifestream", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
