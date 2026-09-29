"""One-off backfill of OwnTracks locations from the `owntracks_unhandled`
archive into `lifestream_locations`.

Between 2024-11-17 and the switch to `POST /v1/owntracks` (#212), the
lifestream-web shim archived every OwnTracks payload but stored no location
points. This replays the archived `location` payloads (only the legacy rows
with no `why`; the native endpoint's rows were already handled) through the
same `create_location` code the endpoint uses, so the same 0.1-degree dedup
rule applies, in fix-time (`tst`) order rather than arrival order (a phone
that was offline delivers its queue in one burst).

    lifestream-backfill-owntracks --since 2024-11-17T09:35:10          # dry run
    lifestream-backfill-owntracks --since 2024-11-17T09:35:10 --commit

`--since` is required and only points with `tst` after it are considered.
Naive values are UTC, like the table's. A point whose row already exists
(same id, source and device) is skipped, never rewritten, so re-running is
safe and never overwrites a stored point or a later edit to one.

The dry run models `create_location` exactly - the predecessor is the latest
stored point strictly before the fix, compared by the rounded values that were
persisted - so its "would create" count matches what `--commit` does.
"""

import argparse
import json
import sys
from bisect import bisect_left
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from lifestream.core.api import LocationInput, location_from_owntracks
from lifestream.core.db import EntryStore, LocationDedupLockError

# Margin when narrowing the archive query: a point is archived no earlier
# than it was fixed, but the DB's `datestamp` timezone isn't guaranteed UTC.
ARRIVAL_MARGIN_DAYS = 2
# Earlier than any stored point, so every stored owntracks row is loaded: the
# predecessor of the first replayed point can be arbitrarily old.
STORE_FLOOR = datetime(2000, 1, 1)
PROGRESS_EVERY = 500
# `device` is part of lifestream_locations' primary key, and create_location
# stores this when a point has none.
NO_DEVICE = "old-data"

Cell = tuple[float, float]


def _parse_since(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cell(lat: float, lon: float) -> Cell:
    """The 0.1-degree cell the dedup rule compares (see create_location)."""
    return (round(lat, 1), round(lon, 1))


def _persisted_cell(lat: float, lon: float) -> Cell:
    """A point's cell as create_location later reads it back: from the
    two-decimal lat_vague/long_vague it stored, not from the raw fix."""
    return _cell(round(lat, 2), round(lon, 2))


def _key(point: LocationInput) -> tuple[int, str]:
    """The (id, device) part of the primary key create_location REPLACEs on."""
    device = point.device if point.device is not None else NO_DEVICE
    return (int(point.timestamp.timestamp()), device)


class _StoredPoints:
    """The owntracks points `lifestream_locations` holds, plus those a dry
    run has pretended to create, for the writer's lookups."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        rows = sorted(rows, key=lambda row: row["timestamp"])
        self.keys = {(int(row["id"]), row["device"]) for row in rows}
        self._times = [row["timestamp"] for row in rows]
        self._cells = [self._row_cell(row) for row in rows]
        self._new_times: list[datetime] = []
        self._new_cells: list[Cell | None] = []

    @staticmethod
    def _row_cell(row: dict[str, Any]) -> Cell | None:
        # create_location only dedupes against a predecessor with both.
        if row.get("lat_vague") is None or row.get("long_vague") is None:
            return None
        return _cell(row["lat_vague"], row["long_vague"])

    def add(self, point: LocationInput) -> None:
        """Record a point as created. Points arrive in ascending time."""
        self.keys.add(_key(point))
        self._new_times.append(point.timestamp.replace(tzinfo=None))
        self._new_cells.append(_persisted_cell(point.lat, point.long))

    def predecessor_cell(self, point: LocationInput) -> Cell | None:
        """The cell of the latest stored point strictly before `point`,
        which is what create_location compares against."""
        when = point.timestamp.replace(tzinfo=None)
        latest: tuple[datetime, Cell | None] | None = None
        for times, cells in (
            (self._times, self._cells),
            (self._new_times, self._new_cells),
        ):
            i = bisect_left(times, when)
            if i and (latest is None or times[i - 1] >= latest[0]):
                latest = (times[i - 1], cells[i - 1])
        return latest[1] if latest else None


def _load_points(
    store: EntryStore, since: datetime, counts: dict[str, int]
) -> list[LocationInput]:
    """Usable archived locations with a fix time after `since`, oldest fix
    first. Updates the archived / invalid / not_after_since counts."""
    rows = store.list_unhandled_locations(
        arrived_after=since.replace(tzinfo=None) - timedelta(days=ARRIVAL_MARGIN_DAYS)
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


def _write(store: EntryStore, point: LocationInput) -> bool:
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
    return created


def _simulate(stored: _StoredPoints, point: LocationInput) -> bool:
    """Whether create_location would store `point`: not if the latest point
    strictly before it is in the same 0.1-degree cell."""
    previous = stored.predecessor_cell(point)
    return previous is None or previous != _cell(point.lat, point.long)


def backfill(store: EntryStore, since: datetime, commit: bool) -> dict[str, int]:
    """Replay archived locations after `since`. Returns counts. With
    `commit` false nothing is written and `created` is what a commit run
    would create."""
    counts = {
        "archived": 0,
        "invalid": 0,
        "not_after_since": 0,
        "already_stored": 0,
        "created": 0,
        "deduped": 0,
    }
    points = _load_points(store, since, counts)
    stored = _StoredPoints(
        store.list_locations(date_from=STORE_FLOOR, source="owntracks")
    )

    for done, point in enumerate(points, start=1):
        if _key(point) in stored.keys:
            counts["already_stored"] += 1
            continue
        created = _write(store, point) if commit else _simulate(stored, point)
        if created:
            stored.add(point)
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
    print(f"Already stored (skipped):          {counts['already_stored']}")
    print(f"{verb + ':':35}{counts['created']}")
    print(f"Skipped as same 0.1° cell:         {counts['deduped']}")
    if not args.commit:
        print("Dry run. Re-run with --commit to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
