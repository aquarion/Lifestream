"""Tests for the one-off OwnTracks archive backfill
(lifestream.backfill_owntracks)."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from lifestream import backfill_owntracks as bf

SINCE = datetime(2024, 11, 17, 9, 35, 10, tzinfo=timezone.utc)
SINCE_EPOCH = int(SINCE.timestamp())


def _row(tst, lat=51.75, lon=-1.21, **extra):
    payload = {"_type": "location", "tid": "aq", "lat": lat, "lon": lon, "tst": tst}
    payload.update(extra)
    return {"id": tst, "fulldata_json": json.dumps(payload)}


@pytest.fixture
def store():
    store = MagicMock()
    store.list_unhandled_locations.return_value = []
    store.list_locations.return_value = []
    store.create_location.return_value = ({}, True)
    return store


class TestBackfill:
    def test_replays_in_fix_time_order_not_archive_order(self, store):
        # Archive (arrival) order is the reverse of fix order: a phone that
        # was offline delivers its queue in one burst.
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 200, lat=52.0),
            _row(SINCE_EPOCH + 100, lat=53.0),
        ]
        counts = bf.backfill(store, SINCE, commit=True)

        lats = [c.kwargs["lat"] for c in store.create_location.call_args_list]
        assert lats == [53.0, 52.0]
        assert counts["created"] == 2

    def test_skips_points_at_or_before_since(self, store):
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH),
            _row(SINCE_EPOCH - 5),
            _row(SINCE_EPOCH + 1),
        ]
        counts = bf.backfill(store, SINCE, commit=True)

        assert store.create_location.call_count == 1
        assert counts["not_after_since"] == 2

    def test_unusable_payloads_are_counted_not_written(self, store):
        store.list_unhandled_locations.return_value = [
            {"id": 1, "fulldata_json": "not json"},
            {"id": 2, "fulldata_json": json.dumps({"_type": "location"})},
            {"id": 3, "fulldata_json": json.dumps([1, 2])},
            _row(SINCE_EPOCH + 1, lat=999),
        ]
        counts = bf.backfill(store, SINCE, commit=True)

        store.create_location.assert_not_called()
        assert counts["invalid"] == 4

    def test_commit_counts_what_the_store_reports(self, store):
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 1),
            _row(SINCE_EPOCH + 2),
        ]
        store.create_location.side_effect = [({}, True), ({}, False)]
        counts = bf.backfill(store, SINCE, commit=True)

        assert (counts["created"], counts["deduped"]) == (1, 1)

    def test_dry_run_writes_nothing_and_simulates_dedup(self, store):
        store.list_locations.return_value = [
            {"lat_vague": 51.75, "long_vague": -1.21}  # cell (51.8, -1.2)
        ]
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 1),  # same cell as the stored point: skipped
            _row(SINCE_EPOCH + 2, lat=52.5, lon=-1.0),  # new cell: kept
            _row(SINCE_EPOCH + 3, lat=52.5, lon=-1.0),  # same as previous: skipped
            _row(SINCE_EPOCH + 4),  # back to the first cell: kept
        ]
        counts = bf.backfill(store, SINCE, commit=False)

        store.create_location.assert_not_called()
        assert (counts["created"], counts["deduped"]) == (2, 2)

    def test_dry_run_without_a_stored_point_keeps_the_first(self, store):
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]
        counts = bf.backfill(store, SINCE, commit=False)

        assert counts["created"] == 1

    def test_archive_query_uses_naive_utc_with_a_margin(self, store):
        bf.backfill(store, SINCE, commit=True)

        arrived_after = store.list_unhandled_locations.call_args.kwargs["arrived_after"]
        assert arrived_after.tzinfo is None
        assert arrived_after < SINCE.replace(tzinfo=None)


class TestMain:
    def test_since_is_required(self):
        with pytest.raises(SystemExit):
            bf.main([])

    def test_naive_since_is_utc(self):
        assert bf._parse_since("2024-11-17T09:35:10") == SINCE

    def test_dry_run_is_the_default_and_closes_the_store(
        self, store, monkeypatch, capsys
    ):
        monkeypatch.setattr(bf, "EntryStore", lambda: store)
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]

        assert bf.main(["--since", "2024-11-17T09:35:10"]) == 0

        store.create_location.assert_not_called()
        store.close.assert_called_once()
        assert "Would create:" in capsys.readouterr().out

    def test_commit_writes(self, store, monkeypatch, capsys):
        monkeypatch.setattr(bf, "EntryStore", lambda: store)
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]

        assert bf.main(["--since", "2024-11-17T09:35:10", "--commit"]) == 0

        store.create_location.assert_called_once()
        assert "Created:" in capsys.readouterr().out

    def test_lock_contention_aborts_cleanly(self, store, monkeypatch):
        monkeypatch.setattr(bf, "EntryStore", lambda: store)
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]
        store.create_location.side_effect = bf.LocationDedupLockError("busy")

        assert bf.main(["--since", "2024-11-17T09:35:10", "--commit"]) == 1
        store.close.assert_called_once()
