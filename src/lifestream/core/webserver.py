"""FastAPI webserver for Lifestream.

Serves the OAuth callback route that replaces CodeFetcher9000's dedicated
per-flow listener (see lifestream.core.code_fetcher for the importer-CLI
side of that handoff), a health check, and the public data API (#134,
lifestream.core.api) that replaces Panopticon's direct database access. Run
by supervisor.py via uvicorn, behind a reverse proxy that terminates TLS.
"""

import html
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.types import Lifespan

from lifestream.core.api import router as api_router
from lifestream.core.cache import get_redis_connection
from lifestream.core.code_fetcher import (
    OAUTH_CALLBACK_CHANNEL,
    OAUTH_KEY_WANTED_REDIS_KEY,
)
from lifestream.core.config import config, get_project_root

logger = logging.getLogger("Webserver")


def _allowed_origins() -> list[str]:
    """Parse the comma-separated [webserver] allowed_origins config value."""
    raw = config.get("webserver", "allowed_origins", fallback="")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _template_path(name: str) -> Path:
    return get_project_root() / "templates" / name


def create_app(lifespan: Lifespan[FastAPI] | None = None) -> FastAPI:
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

    app.include_router(api_router, prefix="/v1")

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": exc.status_code, "message": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Built from exc.errors() rather than str(exc): the latter includes
        # a rendered source snippet (file path + line number), which isn't
        # appropriate for a public API's error responses.
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return JSONResponse(
            status_code=400,
            content={"status": 400, "message": details or "Invalid request"},
        )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/test/success")
    def test_success() -> FileResponse:
        return FileResponse(_template_path("success.html"), media_type="text/html")

    @app.get("/keyback/", response_model=None)
    def keyback(request: Request) -> FileResponse | HTMLResponse:
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
        body = body.replace("[[params]]", html.escape(str(params))).replace(
            "[[key_wanted]]", html.escape(str(key_wanted))
        )
        return HTMLResponse(body)

    return app
