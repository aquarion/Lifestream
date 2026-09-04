# Webserver (#162) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent FastAPI/uvicorn webserver to Lifestream (CORS-enabled, behind a reverse proxy), and migrate the OAuth callback catcher (CodeFetcher9000) onto it via Redis pub/sub, per `docs/superpowers/specs/2026-09-04-webserver-design.md`.

**Architecture:** `scheduler.py` is renamed to `supervisor.py` and now owns two subsystems in one process: APScheduler's `BackgroundScheduler` (jobs on a thread pool) and a FastAPI app served by uvicorn (owns the main asyncio loop). `code_fetcher.py` drops its dedicated HTTPS listener; it now publishes to / blocks on a Redis pub/sub channel that the webserver's `/keyback/` route feeds.

**Tech Stack:** FastAPI, uvicorn, Redis pub/sub (via the existing `redis` client and `lifestream.core.cache.get_redis_connection`), APScheduler `BackgroundScheduler`.

**Implementation note (not in the spec, decided during planning):** the spec describes the OAuth catcher checking "the globally-configured `key_wanted` param name" — but the webserver and the importer CLI are now *different OS processes*, so a Python module-level global can't carry that state between them. This plan stores `key_wanted` in Redis (`lifestream:oauth:key_wanted`, set by `get_code()` before it subscribes, read by the `/keyback/` route, deleted when `get_code()` returns or times out) instead of a process-local global. This preserves the single-global-in-flight-flow semantics the spec calls for; it's a cross-process fix required to make that same design actually work, not a scope change.

---

### Task 1: Add web dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add fastapi and uvicorn as runtime dependencies, httpx as a dev dependency**

In `pyproject.toml`, add to `[tool.poetry.dependencies]` (anywhere alongside the other alphabetical-ish entries, e.g. near `flake8`):

```toml
fastapi = "^0.141.1"
uvicorn = "^0.52.4"
```

And add to `[tool.poetry.group.dev.dependencies]`:

```toml
httpx = "^0.28.1"
```

(`httpx` is required by `fastapi.testclient.TestClient`, which the new tests use — it's not needed at runtime.)

- [ ] **Step 2: Install and lock**

Run: `poetry lock && poetry install`
Expected: resolves successfully, `poetry.lock` is updated, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "🎇 Add fastapi/uvicorn/httpx dependencies for #162 webserver"
```

---

### Task 2: Webserver module — health check + CORS

**Files:**
- Create: `src/lifestream/core/webserver.py`
- Create: `tests/test_webserver.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_webserver.py`:

```python
"""Tests for the Lifestream webserver (FastAPI app: CORS, health check, and
the OAuth catcher route that replaces CodeFetcher9000's dedicated listener)."""

import configparser
from unittest.mock import patch

from fastapi.testclient import TestClient

from lifestream.core import webserver


def _cfg(allowed_origins="https://panopticon.aquarionics.com"):
    cfg = configparser.ConfigParser()
    cfg.add_section("webserver")
    cfg.set("webserver", "allowed_origins", allowed_origins)
    return cfg


class TestAllowedOrigins:
    def test_parses_comma_separated_origins(self):
        cfg = _cfg("https://a.example.com, https://b.example.com")
        with patch.object(webserver, "config", cfg):
            assert webserver._allowed_origins() == [
                "https://a.example.com",
                "https://b.example.com",
            ]

    def test_empty_when_section_missing(self):
        cfg = configparser.ConfigParser()
        with patch.object(webserver, "config", cfg):
            assert webserver._allowed_origins() == []


class TestHealth:
    def test_health_returns_ok(self):
        with patch.object(webserver, "config", _cfg()):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_cors_header_present_for_allowed_origin(self):
        with patch.object(
            webserver, "config", _cfg("https://panopticon.aquarionics.com")
        ):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get(
            "/health", headers={"Origin": "https://panopticon.aquarionics.com"}
        )

        assert (
            response.headers["access-control-allow-origin"]
            == "https://panopticon.aquarionics.com"
        )

    def test_cors_header_absent_for_disallowed_origin(self):
        with patch.object(
            webserver, "config", _cfg("https://panopticon.aquarionics.com")
        ):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/health", headers={"Origin": "https://evil.example.com"})

        assert "access-control-allow-origin" not in response.headers
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/test_webserver.py -v`
Expected: FAIL (or collection error) — `lifestream.core.webserver` doesn't exist yet.

- [ ] **Step 3: Implement the module (health + CORS only for now)**

Create `src/lifestream/core/webserver.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_webserver.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lifestream/core/webserver.py tests/test_webserver.py
git commit -m "🎇 Add Lifestream webserver: FastAPI app with CORS + health check"
```

---

### Task 3: Webserver module — OAuth catcher route (`/keyback/`, `/test/success`)

**Files:**
- Modify: `src/lifestream/core/webserver.py`
- Modify: `tests/test_webserver.py`

This is the FastAPI-side half of the OAuth handoff. It reads which key is
currently wanted from Redis (set by `code_fetcher.get_code()` in Task 5, in
the separate importer-CLI process), and on a match, publishes the callback
params to a Redis channel and serves `success.html`; otherwise it serves
`failure.html` with the same `[[params]]`/`[[key_wanted]]` substitution
`CodeFetcher9000`'s old `MyHandler.failure()` did.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_webserver.py`:

```python
import json
from unittest.mock import MagicMock


class TestKeyback:
    def _app(self):
        with patch.object(webserver, "config", _cfg()):
            return webserver.create_app()

    def test_matching_key_publishes_and_serves_success_page(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = b"access_token"

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?access_token=abc123")

        assert response.status_code == 200
        assert "Sorry" not in response.text
        mock_cxn.publish.assert_called_once()
        channel, payload = mock_cxn.publish.call_args.args
        assert channel == webserver.OAUTH_CALLBACK_CHANNEL
        assert json.loads(payload) == {"access_token": ["abc123"]}

    def test_non_matching_key_serves_failure_page_with_substitution(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = b"access_token"

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?error=access_denied")

        assert response.status_code == 200
        assert "Sorry" in response.text
        assert "error" in response.text
        assert "access_token" in response.text
        mock_cxn.publish.assert_not_called()

    def test_no_key_wanted_in_redis_serves_failure_page(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?access_token=abc123")

        assert response.status_code == 200
        assert "Sorry" in response.text
        mock_cxn.publish.assert_not_called()


class TestTestSuccessRoute:
    def test_serves_success_page_unconditionally(self):
        with patch.object(webserver, "config", _cfg()):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/test/success")

        assert response.status_code == 200
        assert "Sorry" not in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/test_webserver.py -v`
Expected: FAIL — `/keyback/` and `/test/success` return 404 (routes don't exist yet).

- [ ] **Step 3: Implement the routes**

In `src/lifestream/core/webserver.py`, add these imports at the top:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from lifestream.core.cache import get_redis_connection
from lifestream.core.config import config, get_project_root
```

(replacing the existing `from fastapi import FastAPI` and
`from lifestream.core.config import config` lines)

Add these module-level constants, right after `logger = logging.getLogger("Webserver")`:

```python
# Shared with lifestream.core.code_fetcher.get_code() — must match exactly.
OAUTH_KEY_WANTED_REDIS_KEY = "lifestream:oauth:key_wanted"
OAUTH_CALLBACK_CHANNEL = "lifestream:oauth:callback"
```

Add this helper function above `create_app`:

```python
def _template_path(name: str):
    return get_project_root() / "templates" / name
```

Inside `create_app`, after the `@app.get("/health")` block, add:

```python
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
```

Add `import json` to the top of the file, alongside `import logging`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_webserver.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lifestream/core/webserver.py tests/test_webserver.py
git commit -m "🎇 Add /keyback/ OAuth catcher route to the webserver"
```

---

### Task 4: Rewrite `code_fetcher.py` — `get_url()` / `are_we_working()`

**Files:**
- Modify: `src/lifestream/core/code_fetcher.py`
- Modify: `tests/test_code_fetcher.py` (full rewrite — the old tests assert on certfile/keyfile, which no longer exist)

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_code_fetcher.py`:

```python
"""Tests for code_fetcher: the importer-CLI-process side of the OAuth
handoff with the Lifestream webserver's /keyback/ route (see
lifestream.core.webserver). The webserver is the actual HTTP listener now —
this module publishes what key it's waiting for and blocks on Redis pub/sub
until the webserver's route delivers the matching callback."""

import configparser

from lifestream.core import code_fetcher


def _cfg(domain="example.com"):
    cfg = configparser.ConfigParser()
    cfg.add_section("webserver")
    if domain is not None:
        cfg.set("webserver", "domain", domain)
    return cfg
```

- [ ] **Step 2: Run the tests to verify they pass (empty test module)**

Run: `poetry run pytest tests/test_code_fetcher.py -v`
Expected: PASS (0 tests collected) — this just confirms the import doesn't
error before we add real test bodies.

- [ ] **Step 3: Add the `get_url`/`are_we_working` tests**

Append to `tests/test_code_fetcher.py`:

```python
from unittest.mock import patch

import pytest


class TestGetUrl:
    def test_get_url_builds_https_keyback_url(self):
        with patch.object(code_fetcher, "config", _cfg("example.com")):
            assert code_fetcher.get_url() == "https://example.com/keyback/"


class TestAreWeWorking:
    def test_raises_we_say_not_today_when_not_configured(self):
        cfg = configparser.ConfigParser()
        with patch.object(code_fetcher, "config", cfg):
            with pytest.raises(code_fetcher.WeSayNotToday):
                code_fetcher.are_we_working()

    def test_returns_true_when_domain_configured(self):
        with patch.object(code_fetcher, "config", _cfg("example.com")):
            assert code_fetcher.are_we_working() is True
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `poetry run pytest tests/test_code_fetcher.py -v`
Expected: FAIL — `code_fetcher.get_url()` still reads `[CodeFetcher9000]`
certfile/keyfile/port config that isn't set here, and raises.

- [ ] **Step 5: Rewrite `get_url()` and `are_we_working()`**

In `src/lifestream/core/code_fetcher.py`, replace `get_url()` and
`are_we_working()`:

```python
def get_url() -> str:
    """URL the OAuth provider should redirect the user's browser back to."""
    domain = config.get("webserver", "domain")
    return f"https://{domain}/keyback/"


def are_we_working() -> bool:
    """Check that the webserver is configured to build OAuth redirect URLs."""
    try:
        config.get("webserver", "domain")
    except configparser.Error as e:
        logger.error("Webserver not configured: %s", e)
        raise WeSayNotToday() from e
    return True
```

Leave the rest of the file (imports, `logger`, `WeSayNotToday`, the
`http.server`-based `MyHandler`/`code`/`key_wanted`/`get_code`) untouched for
now — Task 5 replaces `get_code` and removes the rest.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_code_fetcher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add src/lifestream/core/code_fetcher.py tests/test_code_fetcher.py
git commit -m "🔄️ Point code_fetcher get_url/are_we_working at [webserver] config"
```

---

### Task 5: Rewrite `code_fetcher.py` — `get_code()` via Redis pub/sub

**Files:**
- Modify: `src/lifestream/core/code_fetcher.py`
- Modify: `tests/test_code_fetcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_code_fetcher.py`:

```python
import json
from unittest.mock import MagicMock


class TestGetCode:
    def test_sets_key_wanted_and_returns_matching_message(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.return_value = {
            "type": "message",
            "data": json.dumps({"access_token": ["abc123"]}),
        }

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["abc123"]}
        mock_cxn.set.assert_called_once_with(
            code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY, "access_token", ex=5
        )
        mock_pubsub.subscribe.assert_called_once_with(
            code_fetcher.OAUTH_CALLBACK_CHANNEL
        )
        mock_cxn.delete.assert_called_once_with(code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY)
        mock_pubsub.close.assert_called_once()

    def test_ignores_non_message_events_and_mismatched_keys(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"code": ["other"]})},
            {"type": "message", "data": json.dumps({"access_token": ["right"]})},
        ]

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["right"]}

    def test_raises_timeout_error_when_no_message_arrives(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.return_value = None

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with pytest.raises(TimeoutError):
                code_fetcher.get_code("access_token", timeout=0.05)

        mock_cxn.delete.assert_called_once_with(code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/test_code_fetcher.py -v -k TestGetCode`
Expected: FAIL — old `get_code` starts an `http.server.HTTPServer` and
expects `[CodeFetcher9000]` certfile/keyfile config; `OAUTH_KEY_WANTED_REDIS_KEY`
doesn't exist yet.

- [ ] **Step 3: Rewrite the module**

Replace the entire contents of `src/lifestream/core/code_fetcher.py`:

```python
"""CodeFetcher9000 - the importer-CLI-process side of the OAuth callback
handoff with the Lifestream webserver.

The actual HTTP listener is the persistent webserver (see
lifestream.core.webserver, served by supervisor.py) — this module publishes
which callback key an importer is waiting for, then blocks on Redis pub/sub
until the webserver's /keyback/ route delivers the matching params.
"""

import configparser
import json
import logging
import time

from lifestream.core.cache import get_redis_connection
from lifestream.core.config import config

logger = logging.getLogger("CodeFetcher")

# Shared with lifestream.core.webserver — must match exactly.
OAUTH_KEY_WANTED_REDIS_KEY = "lifestream:oauth:key_wanted"
OAUTH_CALLBACK_CHANNEL = "lifestream:oauth:callback"

DEFAULT_TIMEOUT_SECONDS = 300


class WeSayNotToday(Exception):
    """Raised when the webserver isn't configured/available; callers should fall back."""

    pass


def get_url() -> str:
    """URL the OAuth provider should redirect the user's browser back to."""
    domain = config.get("webserver", "domain")
    return f"https://{domain}/keyback/"


def are_we_working() -> bool:
    """Check that the webserver is configured to build OAuth redirect URLs."""
    try:
        config.get("webserver", "domain")
    except configparser.Error as e:
        logger.error("Webserver not configured: %s", e)
        raise WeSayNotToday() from e
    return True


def get_code(key_wanted_arg: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """
    Block until the webserver's /keyback/ route delivers a callback matching
    `key_wanted_arg`.

    Sets `key_wanted_arg` in Redis so the webserver (a different process)
    knows what it's waiting for, subscribes to the shared callback channel,
    and returns the published params dict (same {key: [values]} shape
    urllib.parse.parse_qs produces) once a matching message arrives.

    Raises TimeoutError if nothing arrives within `timeout` seconds.
    """
    cxn = get_redis_connection()
    cxn.set(OAUTH_KEY_WANTED_REDIS_KEY, key_wanted_arg, ex=timeout)

    pubsub = cxn.pubsub()
    pubsub.subscribe(OAUTH_CALLBACK_CHANNEL)

    logger.info(
        "Waiting for OAuth callback (key=%s, timeout=%ss)", key_wanted_arg, timeout
    )

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=1.0)
            if message is None or message.get("type") != "message":
                continue
            params = json.loads(message["data"])
            if key_wanted_arg in params:
                return params
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for OAuth callback "
            f"(key={key_wanted_arg})"
        )
    finally:
        cxn.delete(OAUTH_KEY_WANTED_REDIS_KEY)
        pubsub.close()
```

This removes `http.server`, `ssl`, `urllib.parse`, `get_project_root`, the
`MyHandler` class, and the `code`/`key_wanted` module globals entirely — the
webserver module (`lifestream.core.webserver`) now owns request handling and
template rendering.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_code_fetcher.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `poetry run pytest tests/ -v`
Expected: PASS. In particular check `tests/test_facebook_base.py` still
passes — it mocks `code_fetcher` entirely via `patch(...)`, so it shouldn't
be affected by the rewrite, but confirm no import-time breakage.

- [ ] **Step 6: Commit**

```bash
git add src/lifestream/core/code_fetcher.py tests/test_code_fetcher.py
git commit -m "🔄️ Rewrite code_fetcher.get_code() to use Redis pub/sub instead of a dedicated HTTPS listener"
```

---

### Task 6: Rename `scheduler.py` → `supervisor.py`, switch to `BackgroundScheduler`

**Files:**
- Modify (rename): `scheduler.py` → `supervisor.py`
- Modify (rename): `tests/test_scheduler.py` → `tests/test_supervisor.py`

- [ ] **Step 1: Rename both files with git**

```bash
git mv scheduler.py supervisor.py
git mv tests/test_scheduler.py tests/test_supervisor.py
```

- [ ] **Step 2: Update the test file's references**

In `tests/test_supervisor.py`, replace every `import scheduler` with
`import supervisor`, and every `scheduler.` attribute access (e.g.
`scheduler._parse_job_options`, `scheduler.DEFAULT_MISFIRE_GRACE_TIME`,
`scheduler.get_schedules`, `scheduler.add_jobs`, `scheduler.run_import`,
`scheduler.run_shell_command`, `scheduler.run_job_now`,
`scheduler.config`) with the equivalent `supervisor.` access. Do **not**
change the string literals inside test data (e.g. `"scheduler.py"` doesn't
appear in this file, but job names like `"myjob"` are untouched either way).

- [ ] **Step 3: Run the renamed tests to confirm they still pass under the new name**

Run: `poetry run pytest tests/test_supervisor.py -v`
Expected: PASS (all tests, same count as before the rename) — this
confirms the rename+find/replace didn't break anything before we touch
behavior.

- [ ] **Step 4: Add a test asserting the scheduler type**

Append to `tests/test_supervisor.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler


class TestCreateScheduler:
    def test_returns_a_background_scheduler(self):
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda section, key, fallback=None: fallback
        with patch.object(supervisor, "config", mock_config):
            sched = supervisor.create_scheduler()

        assert isinstance(sched, BackgroundScheduler)
```

- [ ] **Step 5: Run to verify it fails**

Run: `poetry run pytest tests/test_supervisor.py -v -k TestCreateScheduler`
Expected: FAIL — `create_scheduler()` still returns a `BlockingScheduler`.

- [ ] **Step 6: Switch the scheduler class**

In `supervisor.py`, change the import:

```python
from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
```

(replacing `from apscheduler.schedulers.blocking import BlockingScheduler`)

And in `create_scheduler()`, change:

```python
    scheduler = BackgroundScheduler(
```

(replacing `scheduler = BlockingScheduler(`)

- [ ] **Step 7: Run to verify it passes**

Run: `poetry run pytest tests/test_supervisor.py -v`
Expected: PASS (all tests including the new one)

- [ ] **Step 8: Commit**

```bash
git add supervisor.py tests/test_supervisor.py
git status  # confirm scheduler.py / tests/test_scheduler.py show as deleted (renamed)
git commit -m "🔄️ Rename scheduler.py to supervisor.py, switch to BackgroundScheduler"
```

---

### Task 7: Wire the webserver into `supervisor.py`

**Files:**
- Modify: `supervisor.py`
- Modify: `tests/test_supervisor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_supervisor.py`:

```python
from fastapi.testclient import TestClient


class TestBuildApp:
    def test_lifespan_starts_and_stops_scheduler(self):
        mock_scheduler = MagicMock()

        app = supervisor.build_app(mock_scheduler)

        with TestClient(app):
            mock_scheduler.start.assert_called_once()
            mock_scheduler.shutdown.assert_not_called()

        mock_scheduler.shutdown.assert_called_once_with(wait=False)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/test_supervisor.py -v -k TestBuildApp`
Expected: FAIL — `supervisor.build_app` doesn't exist yet.

- [ ] **Step 3: Add `build_app()` and wire it into `main()`**

In `supervisor.py`:

1. Add these imports at the top, alongside the existing ones:

```python
from contextlib import asynccontextmanager

import uvicorn

from lifestream.core.webserver import create_app  # noqa: E402
```

2. Remove the now-unused `import signal` line (uvicorn installs its own
   SIGINT/SIGTERM handlers and this plan hooks scheduler shutdown into the
   app's lifespan instead, so both subsystems stop through one path).

3. Add this function, after `run_job_now()` and before `main()`:

```python
def build_app(scheduler):
    """Build the FastAPI app, wired to start/stop `scheduler` via the app's
    own lifespan — so uvicorn's signal handling drives both subsystems'
    startup/shutdown through one coordinated path instead of two competing
    signal handlers."""

    @asynccontextmanager
    async def lifespan(app):
        logger.info("Starting scheduler...")
        scheduler.start()
        try:
            yield
        finally:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=False)

    return create_app(lifespan=lifespan)
```

4. Replace the default (no-flag) branch at the bottom of `main()` — currently:

```python
    # Default: run the scheduler daemon
    logger.info("Starting Lifestream Scheduler...")

    scheduler = create_scheduler()

    # Handle shutdown gracefully
    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Add all jobs from config
    job_count = add_jobs(scheduler)

    if job_count == 0:
        logger.error("No jobs configured! Add jobs to [schedules] in config.ini")
        sys.exit(1)

    logger.info(f"Scheduler started with {job_count} jobs")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")
        logger.error(
            "Check that Redis is running and reachable (see [redis] in config.ini)"
        )
        sys.exit(1)
```

with:

```python
    # Default: run the supervisor (scheduler + webserver)
    logger.info("Starting Lifestream Supervisor...")

    scheduler = create_scheduler()
    job_count = add_jobs(scheduler)

    if job_count == 0:
        logger.error("No jobs configured! Add jobs to [schedules] in config.ini")
        sys.exit(1)

    logger.info(f"Supervisor configured with {job_count} jobs")

    app = build_app(scheduler)
    host = config.get("webserver", "host", fallback="0.0.0.0")
    port = int(config.get("webserver", "port", fallback=8000))

    try:
        logger.info(f"Starting webserver on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Supervisor failed to start: {e}")
        logger.error(
            "Check that Redis is running and reachable (see [redis] in config.ini)"
        )
        sys.exit(1)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `poetry run pytest tests/test_supervisor.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full test suite**

Run: `poetry run pytest tests/ -v`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add supervisor.py tests/test_supervisor.py
git commit -m "🎇 Wire the webserver into supervisor.py via FastAPI lifespan"
```

---

### Task 8: Config, systemd unit, and README updates

**Files:**
- Modify: `config.example.ini`
- Modify (rename): `docs/lifestream-scheduler.service` → `docs/lifestream-supervisor.service`
- Modify: `README.md`

- [ ] **Step 1: Replace `[CodeFetcher9000]` with `[webserver]` in `config.example.ini`**

Replace:

```ini
[CodeFetcher9000]
certfile = /etc/letsencrypt/live/domain.com/fullchain.pem
keyfile = /etc/letsencrypt/live/domain.com/privkey.pem
domain = domain.com
port = 2871
```

with:

```ini
[webserver]
; Internal bind address for the FastAPI/uvicorn webserver. The reverse
; proxy in front of it terminates TLS and forwards requests here.
host = 0.0.0.0
port = 8000
; Comma-separated list of origins allowed to make cross-origin (CORS)
; requests to this webserver's API routes.
allowed_origins = https://panopticon.aquarionics.com
; Public-facing hostname used to build OAuth redirect URLs
; (https://{domain}/keyback/) — register this as the app's OAuth redirect
; URI with each provider (Facebook, etc.).
domain = domain.com
```

- [ ] **Step 2: Update the scheduler comment block in `config.example.ini`**

Replace:

```
; Configure import schedules here instead of using crontab.
; Run with: python scheduler.py
```

with:

```
; Configure import schedules here instead of using crontab.
; Run with: python supervisor.py
```

- [ ] **Step 3: Rename and update the systemd unit**

```bash
git mv docs/lifestream-scheduler.service docs/lifestream-supervisor.service
```

In `docs/lifestream-supervisor.service`, update:

- The comment header: `# Lifestream Scheduler systemd service` →
  `# Lifestream Supervisor systemd service`
- Every `lifestream-scheduler` reference (install path, `systemctl enable`,
  `systemctl restart`, `journalctl -u`) → `lifestream-supervisor`
- `Description=Lifestream Import Scheduler` →
  `Description=Lifestream Supervisor (scheduler + webserver)`
- `ExecStart=/usr/bin/poetry run python scheduler.py` →
  `ExecStart=/usr/bin/poetry run python supervisor.py`
- `SyslogIdentifier=lifestream-scheduler` →
  `SyslogIdentifier=lifestream-supervisor`

- [ ] **Step 4: Update `README.md`**

In `README.md`:

- Line 8, `- **Flexible scheduling**: APScheduler with Redis persistence for
  reliable job execution` → add a webserver bullet right after it:

```markdown
- **Flexible scheduling**: APScheduler with Redis persistence for reliable job execution
- **Webserver**: FastAPI/uvicorn webserver behind a reverse proxy, with CORS support — serves the OAuth callback catcher and future data APIs
```

- Line 30, `poetry run python scheduler.py --run lastfm` →
  `poetry run python supervisor.py --run lastfm`

- Line 38, `- **[redis]**: Redis connection for caching and scheduler
  persistence` → `- **[redis]**: Redis connection for caching and scheduler
  persistence` (unchanged) — but add a new bullet after it:

```markdown
- **[webserver]**: host/port to bind, CORS allowed_origins, and the public domain used for OAuth redirect URLs
```

- Lines 45-69 (the "### Scheduler (Recommended)" section) → replace the
  whole section:

```markdown
### Supervisor (Recommended)

The supervisor runs all import jobs (APScheduler + Redis persistence) and
the webserver (OAuth callback catcher, future data APIs) in one process:

```bash
# List configured jobs
poetry run python supervisor.py --list

# Check next run times
poetry run python supervisor.py --status

# Run a single job immediately
poetry run python supervisor.py --run lastfm

# Start the supervisor (scheduler + webserver)
poetry run python supervisor.py
```

For production, install the systemd service:

```bash
sudo cp docs/lifestream-supervisor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lifestream-supervisor
```
```

- Line 84, `bin/run_import.sh` (legacy; superseded by the scheduler above).`
  → `` `bin/run_import.sh` (legacy; superseded by the supervisor above).``

- Line 89, `scheduler.py          # Main scheduler daemon` →
  `supervisor.py         # Main supervisor daemon (scheduler + webserver)`

- [ ] **Step 5: Verify no stale references remain**

Run: `grep -rn "scheduler.py\|lifestream-scheduler\|CodeFetcher9000" README.md config.example.ini docs/lifestream-supervisor.service`
Expected: no output (all references updated). Note: `supervisor.py`'s own
internal variable/function names like `create_scheduler()` and comments
describing "the scheduler" (the APScheduler subsystem) are expected and
correct — only the *file/service/section* renames matter here.

- [ ] **Step 6: Commit**

```bash
git add config.example.ini docs/lifestream-supervisor.service README.md
git commit -m "📖 Update config template, systemd unit, and README for supervisor.py rename"
```

---

### Task 9: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `poetry run pytest tests/ -v`
Expected: PASS, 0 failures.

- [ ] **Step 2: Run pre-commit hooks across the changed files**

Run: `poetry run pre-commit run --files pyproject.toml poetry.lock supervisor.py src/lifestream/core/webserver.py src/lifestream/core/code_fetcher.py tests/test_supervisor.py tests/test_webserver.py tests/test_code_fetcher.py config.example.ini docs/lifestream-supervisor.service README.md`
Expected: PASS (black/isort/flake8 clean). Fix and re-run if anything fails.

- [ ] **Step 3: Sanity-check the supervisor starts (requires local Redis)**

Run: `poetry run python supervisor.py --list`
Expected: prints the configured `[schedules]` jobs from your local
`config.ini` (or the "No jobs configured" message if you don't have one set
up locally) — confirms the module imports cleanly end-to-end.

- [ ] **Step 4: Confirm no leftover references to the old module name**

Run: `grep -rln "import scheduler\b" --include="*.py" .`
Expected: no output.
