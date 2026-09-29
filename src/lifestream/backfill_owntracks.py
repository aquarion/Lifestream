"""One-off backfill of OwnTracks locations from the `owntracks_unhandled`
archive into `lifestream_locations`.

Between 2024-11-17 and the switch to `POST /v1/owntracks` (#212), the
lifestream-web shim archived every OwnTracks payload but stored no location
points. This replays the archived `location` payloads through the same
`create_location` code the endpoint uses, so the same 0.1-degree dedup rule
applies, in fix-time (`tst`) order rather than arrival order (a phone that
was offline delivers its queue in one burst).

    lifestream-backfill-owntracks --since 2024-11-17T09:35:10          # dry run
    lifestream-backfill-owntracks --since 2024-11-17T09:35:10 --commit

`--since` is required and only points with `tst` after it are considered, so
history that is already stored is never rewritten. Pass the timestamp of the
newest stored owntracks point. Naive values are UTC, like the table's.
Re-running is safe: points already stored dedupe or replace themselves.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from lifestream.core.api import LocationInput, location_from_owntracks
from lifestream.core.db import EntryStore, LocationDedupLockError

# Margin when narrowing the archive query: a point is archived no earlier
# than it was fixed, but the DB's `datestamp` timezone isn't guaranteed UTC.
ARRIVAL_MARGIN = timedelta(days=2)
# How far back to look for the stored point the first replayed one is
# compared against.
SEED_LOOKBACK = timedelta(days=30)
PROGRESS_EVERY = 500


def _parse_since(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cell(lat: float, lon: float) -> tuple[float, float]:
    """The 0.1-degree cell the dedup rule compares (see create_location)."""
    return (round(lat, 1), round(lon, 1))


def _load_points(
    store: EntryStore, since: datetime, counts: dict[str, int]
) -> list[LocationInput]:
    """Usable archived locations with a fix time after `since`, oldest fix
    first. Updates the archived / invalid / not_after_since counts."""
    rows = store.list_unhandled_locations(
        arrived_after=since.replace(tzinfo=None) - ARRIVAL_MARGIN
    )
    counts["archived"] = len(rows)

    points = []
    for row in rows:
        try:
            payload = json.loads(row["fulldata_json"])
        except (TypeError, ValueError):
            payload = None
        location = (
            location_from_owntracks(payload) if isinstance(payload, dict) else None
        )
        if location is None:
            counts["invalid"] += 1
        elif location.timestamp <= since:
            counts["not_after_since"] += 1
        else:
            points.append(location)
    points.sort(key=lambda point: point.timestamp)
    return points


def _seed_cell(store: EntryStore, since: datetime) -> tuple[float, float] | None:
    """The cell of the newest stored owntracks point at or before `since`,
    which the first replayed point is compared against."""
    naive_since = since.replace(tzinfo=None)
    stored = store.list_locations(
        date_from=naive_since - SEED_LOOKBACK,
        date_to=naive_since + timedelta(seconds=1),
        source="owntracks",
    )
    if stored and stored[-1].get("lat_vague") is not None:
        return _cell(stored[-1]["lat_vague"], stored[-1]["long_vague"])
    return None


def backfill(store: EntryStore, since: datetime, commit: bool) -> dict[str, int]:
    """Replay archived locations after `since`. Returns counts. With
    `commit` false nothing is written and `created` is what a commit run
    would create, simulated from the same dedup rule."""
    counts = {
        "archived": 0,
        "invalid": 0,
        "not_after_since": 0,
        "created": 0,
        "deduped": 0,
    }
    points = _load_points(store, since, counts)
    last_cell = None if commit else _seed_cell(store, since)

    for done, point in enumerate(points, start=1):
        if commit:
            _, created = store.create_location(
                source=point.source,
                lat=point.lat,
                lon=point.long,
                timestamp=point.timestamp,
                device=point.device,
                alt=point.alt,
                accuracy=point.accuracy,
                title=point.title,
                icon=point.icon,
                fulldata_json=point.fulldata_json,
            )
        else:
            cell = _cell(point.lat, point.long)
            created = cell != last_cell
            last_cell = cell
        counts["created" if created else "deduped"] += 1
        if done % PROGRESS_EVERY == 0:
            print(f"  {done}/{len(points)}", file=sys.stderr)

    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lifestream-backfill-owntracks",
        description="Replay archived OwnTracks locations into lifestream_locations.",
    )
    parser.add_argument(
        "--since",
        required=True,
        type=_parse_since,
        help="Only replay points with a fix time after this ISO timestamp "
        "(naive = UTC). Use the newest stored owntracks point's timestamp.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write the points. Without it, only report what would be written.",
    )
    args = parser.parse_args(argv)

    store = EntryStore()
    try:
        counts = backfill(store, args.since, args.commit)
    except LocationDedupLockError as e:
        print(f"Aborted, safe to re-run: {e}", file=sys.stderr)
        return 1
    finally:
        store.close()

    verb = "Created" if args.commit else "Would create"
    print(f"Archived location payloads read:   {counts['archived']}")
    print(f"Unusable (no lat/lon/tst etc.):    {counts['invalid']}")
    print(f"At or before --since (skipped):    {counts['not_after_since']}")
    print(f"{verb + ':':35}{counts['created']}")
    print(f"Skipped as same 0.1° cell:         {counts['deduped']}")
    if not args.commit:
        print("Dry run. Re-run with --commit to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
