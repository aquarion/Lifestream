"""Rate limiting for the public API (#134): slowapi (backed by the `limits`
library), keyed by client IP.

Uses `limits`' default in-memory storage rather than a `redis://` backend:
supervisor.py runs the webserver as a single uvicorn process (no multiple
workers/instances), so per-process counters are already effectively global.
Move to a Redis-backed `storage_uri` if that ever changes (e.g. multiple
webserver instances behind a load balancer).

Defined in its own module, rather than inline in webserver.py or api.py, so
both can import the same `limiter` without a circular import: api.py's
routes need it (or, currently, just the shared default limit applied by
SlowAPIMiddleware) and webserver.py's create_app() needs it to wire up the
middleware and exception handler.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Applied to every route by SlowAPIMiddleware unless exempted (see
# webserver.py's /health route) - generous enough for a legitimate poller
# (e.g. Panopticon refreshing the feed) while bounding scraping/abuse of the
# unauthenticated GET endpoints and brute-force attempts against the
# X-API-Key check on writes.
DEFAULT_RATE_LIMIT = "60/minute"

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])
