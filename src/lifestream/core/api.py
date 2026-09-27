"""Public HTTP API (#134): read/write access to the `lifestream` /
`lifestream_locations` / `owntracks_unhandled` tables, replacing Panopticon
(lifestream-web)'s direct database access. Implements the contract in
lifestream-web's `docs/api/openapi.yaml` / `docs/superpowers/specs/
2026-09-04-lifestream-api-design.md`. Mounted under `/v1` by
`lifestream.core.webserver.create_app()`.
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import BaseModel, Field

from lifestream.core.config import config
from lifestream.core.db import EntryResult, EntryStore

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


def get_entry_store() -> EntryStore:
    return EntryStore()


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
        TimestampSigner(secret).unsign(
            token.encode("ascii"), max_age=API_TOKEN_MAX_AGE_SECONDS
        )
    except (BadSignature, SignatureExpired):
        return False
    return True


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


def _decode_json(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
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
    alt: float | None = None
    alt_vague: float | None = None
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


@router.get("/entries", response_model=EntriesPage)
def list_entries(
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
def search_entries(
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
def create_entry(
    body: EntryInput,
    response: Response,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Entry:
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
    response.status_code = 201 if result == EntryResult.INSERTED else 200
    row = store.get_by_id(body.type, body.systemid)
    if row is None:
        # Only reachable with update=False against a store that failed to
        # persist the just-created row - not expected outside test doubles.
        raise HTTPException(status_code=400, detail="Entry could not be read back")
    return _entry_from_row(row)


@router.get("/locations", response_model=list[Location])
def list_locations(
    request: Request,
    from_: datetime = Query(..., alias="from"),
    to: datetime | None = None,
    source: str | None = None,
    store: EntryStore = Depends(get_entry_store),
) -> list[Location]:
    redact = not _has_valid_api_key(request)
    rows = store.list_locations(date_from=from_, date_to=to, source=source)
    return [_location_from_row(row, redact=redact) for row in rows]


@router.post("/locations")
def create_location(
    body: LocationInput,
    response: Response,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Location:
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
    response.status_code = 201 if created else 200
    return _location_from_row(row, redact=False)


@router.get("/locations/heatmap", response_model=list[HeatmapPoint])
def get_location_heatmap(
    from_: datetime = Query(..., alias="from"),
    to: datetime | None = None,
    source: str | None = None,
    store: EntryStore = Depends(get_entry_store),
) -> list[HeatmapPoint]:
    points = store.get_location_heatmap(date_from=from_, date_to=to, source=source)
    return [HeatmapPoint(**point) for point in points]


@router.get("/locations/latest", response_model=Location)
def get_latest_location(
    request: Request, store: EntryStore = Depends(get_entry_store)
) -> Location:
    row = store.get_latest_location()
    if row is None:
        raise HTTPException(status_code=404, detail="No location points recorded yet.")
    redact = not _has_valid_api_key(request)
    return _location_from_row(row, redact=redact)


@router.post("/locations/unhandled", status_code=201)
def create_unhandled_location(
    body: UnhandledLocationInput,
    _: None = Depends(require_api_key),
    store: EntryStore = Depends(get_entry_store),
) -> Response:
    store.add_unhandled_location(body.type, body.fulldata_json)
    return Response(status_code=201)
