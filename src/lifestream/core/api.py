"""Public HTTP API (#134): read/write access to the `lifestream` /
`lifestream_locations` / `owntracks_unhandled` tables, replacing Panopticon
(lifestream-web)'s direct database access. Implements the contract in
lifestream-web's `docs/api/openapi.yaml` / `docs/superpowers/specs/
2026-09-04-lifestream-api-design.md`. Mounted under `/v1` by
`lifestream.core.webserver.create_app()`.
"""

import hmac
import json
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import BaseModel, Field, ValidationError
from pymysql.err import IntegrityError

from lifestream.core.config import config
from lifestream.core.db import EntryResult, EntryStore, LocationDedupLockError
from lifestream.core.ratelimit import DEFAULT_RATE_LIMIT, limiter

router = APIRouter()

# How long a minted X-API-Key token stays valid after signing. Callers mint a
# fresh token (see mint_api_token) rather than sending the long-lived
# [webserver] api_key secret itself, so a token that leaks via a log or
# proxy is only usable for this long, unlike the raw secret it's derived
# from.
API_TOKEN_MAX_AGE_SECONDS = 300

# Fixed payload signed into every token: it carries no per-caller claims (all
# callers share one secret), so its only job is giving TimestampSigner
# something to sign and embed a timestamp alongside.
_TOKEN_PAYLOAD = b"lifestream-api"


def get_entry_store() -> Generator[EntryStore, None, None]:
    """A fresh EntryStore per request, closed once the request finishes.

    MysqlEntryStore opens its connection lazily and never closes it itself
    (fine for a one-shot importer process, which exits right after) - a
    long-running webserver handling many requests needs the `yield`/
    `finally` here instead, or every request leaks a MySQL connection.
    """
    store = EntryStore()
    try:
        yield store
    finally:
        store.close()


def _configured_api_secret() -> str | None:
    return config.get("webserver", "api_key", fallback="") or None


def mint_api_token(secret: str) -> str:
    """Mint an X-API-Key token by signing a fixed payload with `secret` and
    an embedded timestamp (itsdangerous's TimestampSigner). How long the
    result stays valid is entirely up to the verifying side
    (API_TOKEN_MAX_AGE_SECONDS) - deliberately not a parameter here, since a
    caller that could pick its own expiry could just mint a token that
    never expires."""
    return TimestampSigner(secret).sign(_TOKEN_PAYLOAD).decode("ascii")


def _verify_api_token(token: str, secret: str) -> bool:
    try:
        unsigned = TimestampSigner(secret).unsign(
            token.encode("ascii"), max_age=API_TOKEN_MAX_AGE_SECONDS
        )
    except (BadSignature, SignatureExpired, UnicodeEncodeError):
        # UnicodeEncodeError: a real token is always ASCII (itsdangerous's
        # own base64/hex alphabet), so a non-ASCII X-API-Key is simply
        # invalid, not a server error - it must be rejected the same way a
        # malformed-but-ASCII token is, not raise past this function.
        return False
    # A valid signature alone isn't enough: unsign() only proves *some*
    # payload was signed with this secret, not which one. Without this
    # check, a timestamped signature minted for anything else that ever
    # shares this secret (present or future) would double as a valid API
    # token - checking the payload keeps this verifier specific to tokens
    # actually minted by mint_api_token().
    return unsigned == _TOKEN_PAYLOAD


def _has_valid_api_key(request: Request) -> bool:
    """Whether `request` carries a valid, unexpired X-API-Key token signed
    with the configured secret (see mint_api_token). Used both to gate
    writes and to decide whether reads get precise or redacted locations."""
    secret = _configured_api_secret()
    provided = request.headers.get("X-API-Key")
    if not secret or not provided:
        return False
    return _verify_api_token(provided, secret)


def require_api_key(request: Request) -> None:
    if not _has_valid_api_key(request):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


_owntracks_basic = HTTPBasic(auto_error=False)


def require_owntracks_auth(
    credentials: HTTPBasicCredentials | None = Depends(_owntracks_basic),
) -> None:
    """HTTP Basic auth for the OwnTracks endpoint. The OwnTracks app can only
    send a fixed username/password, not the signed, expiring X-API-Key token
    the rest of the write API uses, so this checks the password against its
    own `[webserver] owntracks_password` (the username is ignored). Unset
    means the endpoint is closed to everyone, rather than open."""
    # raw=True: a password containing `%` would otherwise raise
    # InterpolationSyntaxError from ConfigParser and 500 every request.
    expected = config.get("webserver", "owntracks_password", raw=True, fallback="")
    if (
        not expected
        or credentials is None
        or not hmac.compare_digest(
            credentials.password.encode("utf-8"), expected.encode("utf-8")
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _decode_json(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if isinstance(decoded, dict):
        return decoded
    if isinstance(decoded, str):
        # Some existing importers (atproto_posts, via
        # item.post.model_dump_json()) pass fulldata_json as an
        # already-JSON-encoded string rather than a dict; add_entry() then
        # re-encodes that string, double-encoding it in storage. Unwrap the
        # extra layer instead of surfacing those rows as a decode failure.
        try:
            twice_decoded = json.loads(decoded)
        except (TypeError, ValueError):
            return None
        return twice_decoded if isinstance(twice_decoded, dict) else None
    return None


class Entry(BaseModel):
    type: str
    systemid: str
    title: str | None = None
    source: str
    url: str | None = None
    image: str | None = None
    date_created: datetime
    date_updated: datetime
    fulldata_json: dict[str, Any] | None = None


class EntryInput(BaseModel):
    type: str
    systemid: str
    title: str
    source: str
    date_created: datetime
    url: str | None = None
    image: str | None = None
    fulldata_json: dict[str, Any] | None = None
    update: bool = False


class EntriesPage(BaseModel):
    items: list[Entry]
    total: int
    offset: int
    limit: int


class Location(BaseModel):
    id: int | None = None
    source: str
    device: str | None = None
    lat: float | None = None
    long: float | None = None
    # int, not float: lifestream_locations.alt/alt_vague are plain INT
    # columns and create_location() always rounds to a whole number before
    # storing - a float type here would let FastAPI's schema and the JSON
    # response (e.g. 13.0) disagree with both the OpenAPI contract and what
    # was actually persisted.
    alt: int | None = None
    alt_vague: int | None = None
    lat_vague: float | None = None
    long_vague: float | None = None
    accuracy: int = 0
    title: str | None = None
    icon: str | None = None
    timestamp: datetime
    fulldata_json: dict[str, Any] | None = None


class LocationInput(BaseModel):
    source: str
    device: str | None = None
    lat: float = Field(ge=-90, le=90)
    long: float = Field(ge=-180, le=180)
    alt: float | None = None
    accuracy: int = 0
    title: str | None = None
    icon: str | None = None
    timestamp: datetime
    fulldata_json: dict[str, Any] | None = None


class HeatmapPoint(BaseModel):
    lat: float
    long: float
    count: int
    title: str | None = None
    icon: str | None = None


class UnhandledLocationInput(BaseModel):
    type: str
    fulldata_json: dict[str, Any]


def _entry_from_row(row: dict[str, Any]) -> Entry:
    return Entry(
        type=row["type"],
        systemid=row["systemid"],
        title=row.get("title"),
        source=row["source"],
        url=row.get("url") or None,
        image=row.get("image") or None,
        date_created=row["date_created"],
        date_updated=row["date_updated"],
        fulldata_json=_decode_json(row.get("fulldata_json")),
    )


def _location_from_row(row: dict[str, Any], *, redact: bool) -> Location:
    return Location(
        id=row.get("id"),
        source=row["source"],
        device=row.get("device"),
        lat=None if redact else row.get("lat"),
        long=None if redact else row.get("long"),
        alt=row.get("alt"),
        alt_vague=row.get("alt_vague"),
        lat_vague=row.get("lat_vague"),
        long_vague=row.get("long_vague"),
        accuracy=row.get("accuracy") or 0,
        title=row.get("title"),
        icon=row.get("icon"),
        timestamp=row["timestamp"],
        fulldata_json=None if redact else _decode_json(row.get("fulldata_json")),
    )


# Every route below carries its own @limiter.limit(...), rather than
# relying on the app-level default_limits SlowAPIMiddleware applies in
# webserver.py: this router is mounted via app.include_router(), and
# FastAPI/Starlette represent an included router's routes as one lazy
# proxy in app.routes rather than flattened APIRoutes, which is what
# SlowAPIMiddleware's route lookup walks to find a handler - so its
# default-limits path silently never matches these routes at all. The
# per-route decorator enforces inline (it doesn't depend on that lookup),
# which is also why every route here takes a `request: Request` parameter
# - slowapi requires it to identify the caller.
@router.get("/entries", response_model=EntriesPage)
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_entries(
    request: Request,
    after: datetime | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    store: EntryStore = Depends(get_entry_store),
) -> EntriesPage:
    rows, total = store.list_entries(
        after=after, date_from=from_, date_to=to, offset=offset, limit=limit
    )
    return EntriesPage(
        items=[_entry_from_row(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/entries/search", response_model=EntriesPage)
@limiter.limit(DEFAULT_RATE_LIMIT)
def search_entries(
    request: Request,
    q: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    store: EntryStore = Depends(get_entry_store),
) -> EntriesPage:
    rows, total = store.search_entries(q=q, offset=offset, limit=limit)
    return EntriesPage(
        items=[_entry_from_row(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/entries")
@limiter.limit(DEFAULT_RATE_LIMIT)
def create_entry(
    request: Request,
    body: EntryInput,
    response: Response,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Entry:
    try:
        result = store.add_entry(
            type=body.type,
            id=body.systemid,
            title=body.title,
            source=body.source,
            date=body.date_created,
            url=body.url or "",
            image=body.image or "",
            fulldata_json=body.fulldata_json,
            update=body.update,
        )
    except IntegrityError:
        # add_entry()'s own SELECT-then-INSERT isn't atomic: a concurrent
        # request for the same (type, systemid) can insert between our
        # SELECT and INSERT, so ours then fails the table's primary key.
        # The other request's write already won, so this one is the same
        # idempotent no-op its own SELECT would have hit had it run a
        # moment later - re-read and return that row instead of a 500.
        result = EntryResult.SKIPPED

    if store.no_db:
        # NoDbEntryStore never persists anything, so there's no row to read
        # back - echo the input instead, mirroring create_location's no-db
        # behavior rather than treating "nothing to read back" as failure.
        response.status_code = 200
        return Entry(
            type=body.type,
            systemid=body.systemid,
            title=body.title,
            source=body.source,
            url=body.url,
            image=body.image,
            date_created=body.date_created,
            date_updated=datetime.now(timezone.utc),
            fulldata_json=body.fulldata_json,
        )

    response.status_code = 201 if result == EntryResult.INSERTED else 200
    row = store.get_by_id(body.type, body.systemid)
    if row is None:
        # Only reachable against a store that failed to persist a write
        # this function didn't already special-case (no-db, a lost-race
        # duplicate) - not expected against a real MySQL-backed store.
        raise HTTPException(status_code=400, detail="Entry could not be read back")
    return _entry_from_row(row)


@router.get("/locations", response_model=list[Location])
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_locations(
    request: Request,
    from_: datetime = Query(..., alias="from"),
    to: datetime | None = None,
    source: str | None = None,
    store: EntryStore = Depends(get_entry_store),
) -> list[Location]:
    redact = not _has_valid_api_key(request)
    # `to` defaults to now (per the documented contract) rather than being
    # passed through as an unbounded upper limit - otherwise an omitted `to`
    # would include any future-dated rows (e.g. from clock-skewed clients).
    rows = store.list_locations(
        date_from=from_, date_to=to or datetime.now(timezone.utc), source=source
    )
    return [_location_from_row(row, redact=redact) for row in rows]


@router.post("/locations")
@limiter.limit(DEFAULT_RATE_LIMIT)
def create_location(
    request: Request,
    body: LocationInput,
    response: Response,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Location:
    try:
        row, created = store.create_location(
            source=body.source,
            lat=body.lat,
            lon=body.long,
            timestamp=body.timestamp,
            device=body.device,
            alt=body.alt,
            accuracy=body.accuracy,
            title=body.title,
            icon=body.icon,
            fulldata_json=body.fulldata_json,
        )
    except LocationDedupLockError as e:
        # Contention on this source's dedup lock, not a client error - the
        # caller should retry rather than the write silently racing.
        raise HTTPException(status_code=503, detail=str(e)) from e
    response.status_code = 201 if created else 200
    return _location_from_row(row, redact=False)


@router.get("/locations/heatmap", response_model=list[HeatmapPoint])
@limiter.limit(DEFAULT_RATE_LIMIT)
def get_location_heatmap(
    request: Request,
    from_: datetime = Query(..., alias="from"),
    to: datetime | None = None,
    source: str | None = None,
    store: EntryStore = Depends(get_entry_store),
) -> list[HeatmapPoint]:
    points = store.get_location_heatmap(
        date_from=from_, date_to=to or datetime.now(timezone.utc), source=source
    )
    return [HeatmapPoint(**point) for point in points]


@router.get("/locations/latest", response_model=Location)
@limiter.limit(DEFAULT_RATE_LIMIT)
def get_latest_location(
    request: Request, store: EntryStore = Depends(get_entry_store)
) -> Location:
    row = store.get_latest_location()
    if row is None:
        raise HTTPException(status_code=404, detail="No location points recorded yet.")
    redact = not _has_valid_api_key(request)
    return _location_from_row(row, redact=redact)


@router.post("/locations/unhandled", status_code=201)
@limiter.limit(DEFAULT_RATE_LIMIT)
def create_unhandled_location(
    request: Request,
    body: UnhandledLocationInput,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Response:
    store.add_unhandled_location(body.type, body.fulldata_json)
    return Response(status_code=201)


def _location_from_owntracks(payload: dict[str, Any]) -> LocationInput | None:
    """Map an OwnTracks `_type: location` payload to a LocationInput, or
    None if it lacks a usable position/timestamp (see the OwnTracks JSON
    docs for the field meanings). Mirrors what lifestream-web's
    owntracks.php stored: `tid` as the device, `inregions` as the title."""
    try:
        acc = payload.get("acc")
        inregions = payload.get("inregions")
        return LocationInput(
            source="owntracks",
            device=payload.get("tid"),
            lat=payload["lat"],
            long=payload["lon"],
            alt=payload.get("alt"),
            accuracy=int(acc) if acc else 0,
            # '' not None when absent: owntracks.php stored an empty string.
            title=" / ".join(inregions) if isinstance(inregions, list) else "",
            timestamp=datetime.fromtimestamp(payload["tst"], tz=timezone.utc),
            fulldata_json=payload,
        )
    except (KeyError, TypeError, ValueError, OverflowError, OSError, ValidationError):
        return None


# Why an OwnTracks payload was archived to `owntracks_unhandled` (its `why`
# column). Every payload is archived, so this says what else happened to it.
WHY_STORED = "stored"  # a location, saved as a point
WHY_DEDUPE = "dedupe"  # a valid location skipped: same 0.1 degree cell as the last
WHY_INVALID_LOCATION = "invalid_location"  # a location without usable lat/lon/tst
WHY_UNHANDLED_TYPE = "unhandled_type"  # any other _type (status, transition, ...)


def _store_owntracks_location(store: EntryStore, payload: dict[str, Any]) -> str:
    """Store `payload` as a location point if it is a usable location, and
    return the WHY_* reason it should be archived under."""
    if payload.get("_type") != "location":
        return WHY_UNHANDLED_TYPE
    location = _location_from_owntracks(payload)
    if location is None:
        return WHY_INVALID_LOCATION
    try:
        _, created = store.create_location(
            source=location.source,
            lat=location.lat,
            lon=location.long,
            timestamp=location.timestamp,
            device=location.device,
            alt=location.alt,
            accuracy=location.accuracy,
            title=location.title,
            icon=location.icon,
            fulldata_json=location.fulldata_json,
        )
    except LocationDedupLockError as e:
        # Not the payload's fault: 503 so the app retries it.
        raise HTTPException(status_code=503, detail=str(e)) from e
    return WHY_STORED if created else WHY_DEDUPE


@router.post("/owntracks")
@limiter.limit(DEFAULT_RATE_LIMIT)
def receive_owntracks(
    request: Request,
    payload: dict[str, Any] = Body(...),
    _: None = Depends(require_owntracks_auth),
    store: EntryStore = Depends(get_entry_store),
) -> list[Any]:
    """Receive an OwnTracks app's HTTP-mode POST directly, replacing
    lifestream-web's owntracks.php shim (#135). Location payloads are stored
    as location points; every payload is also archived raw, as the shim did,
    with a `why` saying what became of it. A location that can't be stored
    (missing/invalid fields) is only archived, not rejected: OwnTracks
    retries non-2xx responses, so failing here would make the app resend the
    same bad payload indefinitely."""
    why = _store_owntracks_location(store, payload)
    store.add_unhandled_location(str(payload.get("_type", "unknown")), payload, why)
    # The OwnTracks protocol lets the response carry objects for the app
    # (friends, cards); we have none to send.
    return []
