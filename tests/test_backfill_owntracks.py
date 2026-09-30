"""Tests for the one-off OwnTracks archive backfill
(lifestream.backfill_owntracks)."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from lifestream import backfill_owntracks as bf

SINCE = datetime(2024, 11, 17, 9, 35, 10, tzinfo=timezone.utc)
SINCE_EPOCH = int(SINCE.timestamp())


def _row(tst, lat=51.75, lon=-1.21, tid="aq", **extra):
    payload = {"_type": "location", "tid": tid, "lat": lat, "lon": lon, "tst": tst}
    payload.update(extra)
    return {"id": tst, "fulldata_json": json.dumps(payload)}


def _stored(tst, lat_vague=51.75, long_vague=-1.21, device="aq"):
    """A row as lifestream_locations returns it (naive UTC timestamp)."""
    return {
        "id": tst,
        "device": device,
        "timestamp": datetime.fromtimestamp(tst, tz=timezone.utc).replace(tzinfo=None),
        "lat_vague": lat_vague,
        "long_vague": long_vague,
    }


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

    def test_loads_every_stored_owntracks_point(self, store):
        bf.backfill(store, SINCE, commit=True)

        kwargs = store.list_locations.call_args.kwargs
        assert kwargs["source"] == "owntracks"
        assert kwargs["date_from"] == bf.STORE_FLOOR
        assert "date_to" not in kwargs

    def test_archive_query_uses_naive_utc_with_a_margin(self, store):
        bf.backfill(store, SINCE, commit=True)

        arrived_after = store.list_unhandled_locations.call_args.kwargs["arrived_after"]
        assert arrived_after.tzinfo is None
        assert arrived_after < SINCE.replace(tzinfo=None)


class TestAlreadyStored:
    def test_existing_point_is_never_rewritten(self, store):
        # A rerun: this fix was backfilled before. create_location would
        # REPLACE the row (same id, source, device) and call it new.
        store.list_locations.return_value = [_stored(SINCE_EPOCH + 5)]
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 5)]

        counts = bf.backfill(store, SINCE, commit=True)

        store.create_location.assert_not_called()
        assert counts["already_stored"] == 1
        assert counts["created"] == 0

    def test_same_fix_time_on_another_device_is_still_replayed(self, store):
        store.list_locations.return_value = [_stored(SINCE_EPOCH + 5, device="other")]
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 5)]

        counts = bf.backfill(store, SINCE, commit=True)

        assert counts["created"] == 1

    def test_a_missing_device_uses_the_writers_placeholder(self, store):
        store.list_locations.return_value = [
            _stored(SINCE_EPOCH + 5, device="old-data")
        ]
        store.list_unhandled_locations.return_value = [
            {
                "id": 1,
                "fulldata_json": json.dumps(
                    {
                        "_type": "location",
                        "lat": 51.0,
                        "lon": -1.0,
                        "tst": SINCE_EPOCH + 5,
                    }
                ),
            }
        ]

        counts = bf.backfill(store, SINCE, commit=True)

        assert counts["already_stored"] == 1

    def test_duplicate_archive_rows_are_written_once(self, store):
        # The phone resent the same fix: two archive rows, one tst.
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 5),
            _row(SINCE_EPOCH + 5),
        ]

        counts = bf.backfill(store, SINCE, commit=True)

        assert store.create_location.call_count == 1
        assert (counts["created"], counts["already_stored"]) == (1, 1)


class TestDryRunMatchesTheWriter:
    """The dry run models create_location's rule: skip a point if the latest
    stored point strictly before it is in the same 0.1 degree cell, compared by
    the two-decimal values that were persisted."""

    def _dry(self, store):
        counts = bf.backfill(store, SINCE, commit=False)
        store.create_location.assert_not_called()
        return counts

    def test_writes_nothing_and_simulates_dedup(self, store):
        store.list_locations.return_value = [_stored(SINCE_EPOCH - 60)]  # (51.8, -1.2)
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 1),  # same cell as the stored point: skipped
            _row(SINCE_EPOCH + 2, lat=52.5, lon=-1.0),  # new cell: kept
            _row(SINCE_EPOCH + 3, lat=52.5, lon=-1.0),  # same as previous: skipped
            _row(SINCE_EPOCH + 4),  # back to the first cell: kept
        ]
        counts = self._dry(store)

        assert (counts["created"], counts["deduped"]) == (2, 2)

    def test_first_point_is_kept_when_nothing_is_stored(self, store):
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]

        assert self._dry(store)["created"] == 1

    def test_compares_persisted_two_decimal_values_not_raw_fixes(self, store):
        # 51.749 is stored as lat_vague 51.75, whose cell is 51.8; the next
        # fix, 51.751, is also cell 51.8, so the writer skips it. Comparing
        # raw fixes would see 51.7 vs 51.8 and wrongly keep both.
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 1, lat=51.749),
            _row(SINCE_EPOCH + 2, lat=51.751),
        ]
        counts = self._dry(store)

        assert (counts["created"], counts["deduped"]) == (1, 1)

    def test_a_stored_point_with_a_null_longitude_does_not_crash(self, store):
        store.list_locations.return_value = [_stored(SINCE_EPOCH - 60, long_vague=None)]
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]

        # The writer only dedupes against a predecessor with both values.
        assert self._dry(store)["created"] == 1

    def test_finds_a_predecessor_older_than_any_fixed_lookback(self, store):
        old = int((SINCE - timedelta(days=200)).timestamp())
        store.list_locations.return_value = [_stored(old)]  # (51.8, -1.2)
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 1)]

        assert self._dry(store)["deduped"] == 1

    def test_stored_points_after_since_are_predecessors_too(self, store):
        # A point already stored after --since sits between two replayed
        # ones and is what the later one is compared against.
        store.list_locations.return_value = [
            _stored(SINCE_EPOCH + 50, lat_vague=52.5, long_vague=-1.0)
        ]
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 10, lat=51.75),
            _row(SINCE_EPOCH + 100, lat=52.5, lon=-1.0),
        ]
        counts = self._dry(store)

        # +10 is kept (nothing before it); +100 matches the stored +50 point.
        assert (counts["created"], counts["deduped"]) == (1, 1)

    def test_equal_fix_times_do_not_precede_each_other(self, store):
        # Two devices report at the same instant, in different cells. The
        # writer looks strictly earlier, so neither is the other's
        # predecessor and both are kept.
        store.list_unhandled_locations.return_value = [
            _row(SINCE_EPOCH + 5, lat=51.75, tid="a"),
            _row(SINCE_EPOCH + 5, lat=52.5, lon=-1.0, tid="b"),
        ]

        assert self._dry(store)["created"] == 2

    def test_already_stored_points_are_skipped_in_a_dry_run_too(self, store):
        store.list_locations.return_value = [_stored(SINCE_EPOCH + 5)]
        store.list_unhandled_locations.return_value = [_row(SINCE_EPOCH + 5)]

        counts = self._dry(store)

        assert (counts["already_stored"], counts["created"]) == (1, 0)


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
