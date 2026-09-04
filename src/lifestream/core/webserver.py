"""FastAPI webserver for Lifestream.

Serves the OAuth callback route that replaces CodeFetcher9000's dedicated
per-flow listener (see lifestream.core.code_fetcher for the importer-CLI
side of that handoff) and a health check, plus a base for future #134/#135
API routes. Run by supervisor.py via uvicorn, behind a reverse proxy that
terminates TLS.
"""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from lifestream.core.cache import get_redis_connection
from lifestream.core.config import config, get_project_root

logger = logging.getLogger("Webserver")

# Shared with lifestream.core.code_fetcher.get_code() — must match exactly.
OAUTH_KEY_WANTED_REDIS_KEY = "lifestream:oauth:key_wanted"
OAUTH_CALLBACK_CHANNEL = "lifestream:oauth:callback"


def _allowed_origins() -> list[str]:
    """Parse the comma-separated [webserver] allowed_origins config value."""
    raw = config.get("webserver", "allowed_origins", fallback="")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _template_path(name: str):
    return get_project_root() / "templates" / name


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

    @app.get("/test/success")
    def test_success() -> FileResponse:
        return FileResponse(_template_path("success.html"), media_type="text/html")

    @app.get("/keyback/")
    def keyback(request: Request):
        params: dict[str, list[str]] = {}
        for key, value in request.query_params.multi_items():
            params.setdefault(key, []).append(value)

        cxn = get_redis_connection()
        raw_key_wanted = cxn.get(OAUTH_KEY_WANTED_REDIS_KEY)
        key_wanted = (
            raw_key_wanted.decode("utf-8")
            if isinstance(raw_key_wanted, bytes)
            else raw_key_wanted
        )

        if key_wanted and key_wanted in params:
            cxn.publish(OAUTH_CALLBACK_CHANNEL, json.dumps(params))
            return FileResponse(_template_path("success.html"), media_type="text/html")

        body = _template_path("failure.html").read_text(encoding="utf-8")
        body = body.replace("[[params]]", str(params)).replace(
            "[[key_wanted]]", str(key_wanted)
        )
        return HTMLResponse(body)

    return app
