# Webserver (#162) — Design

## Problem

Lifestream has no persistent HTTP server. `#162` asks for one, behind a reverse
proxy, with CORS support, to serve two purposes:

1. Replace `CodeFetcher9000` (`src/lifestream/core/code_fetcher.py`), the
   dedicated short-lived HTTPS OAuth-callback listener each importer spins up
   for itself.
2. Provide the basis for a real-time API for `#134` (Open API for Panopticon)
   and `#135` (move API writes from lifestream-web) — those endpoints
   themselves are out of scope for this issue.

## Scope

In scope:
- A new persistent webserver, embedded in the renamed job-runner process.
- Migrating the OAuth catcher (`/keyback/` route) onto it, updating the one
  new-style caller (`facebook_base.py`).
- Config, CORS, and a health-check route.

Out of scope:
- The actual `#134`/`#135` API endpoints (Panopticon data access) — a
  follow-up issue.
- `imports/wow.py` and `imports/destiny2.py`, the two legacy
  (`lifestream_legacy`) OAuth callers — left on the old CodeFetcher9000 path
  until those importers are migrated or retired.
- Reverse proxy / firewall configuration — infra, not code.

## Architecture

The long-running process is renamed from `scheduler.py` to **`supervisor.py`**
(systemd unit `lifestream-scheduler.service` → `lifestream-supervisor.service`,
logger identifier `Supervisor`). It now owns two subsystems in one process:

- **Job scheduling**: APScheduler switches from `BlockingScheduler` to
  `BackgroundScheduler`. Jobs run on APScheduler's own thread pool instead of
  the main thread — this is the only behavioral change to the scheduling
  logic itself (`jobs.py`, cron parsing, coalescing, locking are untouched).
- **Webserver**: FastAPI app served by uvicorn, with `uvicorn.run(...)` (or
  `uvicorn.Server(...).run()`) as the process's main blocking call, owning the
  asyncio event loop. `supervisor.py`'s startup sequence becomes: build the
  scheduler, call `scheduler.start()` (non-blocking under
  `BackgroundScheduler`), then hand control to uvicorn.

One process, one systemd unit, both subsystems share the same lifecycle
(restart policy, logging, working directory).

The webserver speaks **plain HTTP only** — the reverse proxy in front of it
(per the issue) terminates TLS. This removes the need for `ssl.SSLContext`
and cert/key file management from the webserver path entirely.

CORS is handled by FastAPI's `CORSMiddleware`, configured from a new
`[webserver]` config.ini section (see Config below) — origins are
configurable, not hardcoded, so adding a consumer later doesn't require a
code change.

## OAuth catcher migration

`code_fetcher.py` is rewritten to drop `http.server`/TLS entirely:

- **`are_we_working()`** — now checks that the `[webserver]` config section
  is present and has the fields it needs (`domain`, at minimum), instead of
  checking certfile/keyfile readability. Importers keep their existing
  fallback behavior (manual PIN entry with a "configure it for an easier
  flow" message) when it's not configured.
- **`get_url()`** — builds `https://{domain}/keyback/` from `[webserver]`
  config. No port in the URL (the reverse proxy fronts this on the standard
  HTTPS port); `domain` remains a distinct config value from the webserver's
  internal bind host/port.
- **`get_code(key_wanted_arg)`** (unchanged signature, still synchronous,
  still called from importer CLI processes) — subscribes to a Redis pub/sub
  channel, blocks on `pubsub.get_message()` in a loop with a timeout (default
  300s matching typical OAuth-flow patience), returns the parsed callback
  params dict once a message arrives, or raises a timeout error.
- **New FastAPI route `GET /keyback/`** on the supervisor's webserver —
  parses query params the same way `MyHandler.do_GET()` does today (checks
  whether the globally-configured `key_wanted` param name is present),
  publishes the params as JSON to the Redis channel, renders
  `templates/success.html` / `templates/failure.html` exactly as before (same
  `[[params]]`/`[[key_wanted]]` template substitution in the failure case).

This preserves the **single global in-flight OAuth flow** semantics of today
(no per-flow `state` nonce, no concurrent-flow support) — these are
manually-triggered `--reauth` flows that only ever run one at a time in
practice, so this isn't a regression, just carrying forward the existing
constraint.

**Caller updates:** `facebook_base.py` is the only new-style importer using
`code_fetcher` (`are_we_working()` / `get_url()` / `get_code()`) — no call-site
changes needed there since the public function signatures don't change.
`imports/wow.py` and `imports/destiny2.py` (legacy, `lifestream_legacy`
package) keep using the old dedicated-listener `code_fetcher.py` in that
package, untouched.

## Config

New `[webserver]` section in `config.ini`:

```ini
[webserver]
host = 0.0.0.0
port = 8000
allowed_origins = https://panopticon.aquarionics.com
domain = your.public.domain
```

- `host`/`port` — internal bind address for uvicorn (behind the reverse proxy).
- `allowed_origins` — comma-separated list passed to `CORSMiddleware`.
- `domain` — the public-facing hostname used to build OAuth redirect URLs
  (`get_url()`).

The `[CodeFetcher9000]` config section (`certfile`, `keyfile`, `domain`,
`port`) is removed once migration is complete.

## Testing

- FastAPI `TestClient` tests for the app: `/keyback/` success/failure
  rendering (parity with today's `MyHandler` behavior), CORS headers present
  on a sample route, `/health` returns 200.
- `code_fetcher.get_code()` / publish-side tests using a fake Redis (the
  existing `conftest.py` `mock_redis()` fixture likely covers this).
- A `supervisor.py` startup test verifying `BackgroundScheduler` and uvicorn
  both come up without one blocking the other.

## Rollout (infra, not code)

The reverse proxy needs to route the public HTTPS `/keyback/` path (and
future API paths) to the supervisor's internal HTTP port. This is a
deployment change outside this repo's code and isn't part of this PR.
