"""Tests for lifestream.core.db module."""

from unittest.mock import MagicMock, call, patch

import pytest

from lifestream import db


class TestGetConnection:
    """Tests for database connection functions."""

    def test_get_connection_uses_config(self):
        """Test that get_connection uses config settings."""
        mock_config = MagicMock()
        mock_config.items.return_value = [
            ("hostname", "localhost"),
            ("database", "test_db"),
            ("username", "test_user"),
            ("password", "test_pass"),
        ]

        with patch.object(db, "config", mock_config):
            with patch.object(db.MySQLdb, "connect") as mock_connect:
                db.get_connection()

                mock_connect.assert_called_once_with(
                    user="test_user",
                    passwd="test_pass",
                    db="test_db",
                    host="localhost",
                    charset="utf8mb4",
                )

    def test_get_cursor_sets_utf8(self):
        """Test that get_cursor configures UTF-8."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        cursor = db.get_cursor(mock_conn)

        assert cursor is mock_cursor
        calls = mock_cursor.execute.call_args_list
        assert call("SET NAMES utf8mb4;") in calls
        assert call("SET CHARACTER SET utf8mb4;") in calls
        assert call("SET character_set_connection=utf8mb4;") in calls


class TestEntryStore:
    """Tests for EntryStore class."""

    def test_no_db_true_dispatches_to_nodb_backend(self):
        """EntryStore(no_db=True) resolves to the NoDbEntryStore backend."""
        store = db.EntryStore(no_db=True)
        assert isinstance(store, db.NoDbEntryStore)
        assert store.no_db is True

    def test_no_db_false_dispatches_to_mysql_backend(self):
        """EntryStore(no_db=False) resolves to the MysqlEntryStore backend."""
        store = db.EntryStore(no_db=False)
        assert isinstance(store, db.MysqlEntryStore)
        assert store.no_db is False

    def test_no_db_is_read_only_on_nodb_backend(self):
        """no_db can't be flipped after construction, unlike the old mutable flag."""
        store = db.EntryStore(no_db=True)
        with pytest.raises(AttributeError):
            store.no_db = False

    def test_no_db_is_read_only_on_mysql_backend(self):
        """Same immutability check, but for the other concrete backend —
        MysqlEntryStore defines its own no_db property too."""
        store = db.EntryStore(no_db=False)
        with pytest.raises(AttributeError):
            store.no_db = True

    def test_no_db_mode_prints_instead_of_writing(self, capsys):
        """Test that --no-db mode prints instead of database operations."""
        store = db.EntryStore(no_db=True)
        store.add_entry(
            type="test",
            id="123",
            title="Test Entry",
            source="test_source",
            date="2024-01-01",
        )

        captured = capsys.readouterr()
        assert "[NO-DB] INSERT:" in captured.out
        assert "type=test" in captured.out

    def test_get_by_id_returns_entry(self):
        """Test get_by_id returns an entry when found."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "type": "test", "systemid": "123"}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            result = store.get_by_id("test", "123")

            assert result == {"id": 1, "type": "test", "systemid": "123"}

    def test_get_by_id_returns_none_when_not_found(self):
        """Test get_by_id returns None when entry not found."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            result = store.get_by_id("test", "nonexistent")

            assert result is None

    def test_delete_entry_removes_entry(self):
        """Test delete_entry executes DELETE query."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.delete_entry("test", "123")

                mock_cursor.execute.assert_called()
                mock_conn.commit.assert_called()

    def test_add_stat_replaces_stat(self):
        """Test add_stat uses REPLACE INTO."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                result = store.add_stat("2024-01-01", "test_stat", 42)

                assert result is True
                mock_conn.commit.assert_called()

    def test_no_db_add_stat_prints(self, capsys):
        """Test add_stat in no-db mode prints instead of writing."""
        store = db.EntryStore(no_db=True)
        result = store.add_stat("2024-01-01", "test_stat", 42)

        captured = capsys.readouterr()
        assert "[NO-DB] STAT:" in captured.out
        assert result is True

    def test_add_entry_inserts_new_entry(self):
        """add_entry executes INSERT when the entry does not yet exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Entry doesn't exist
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                result = store.add_entry(
                    type="test", id="abc", title="T", source="s", date="2024-01-01"
                )

        assert result is db.EntryResult.INSERTED
        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO" in sql for sql in executed_sqls)
        mock_conn.commit.assert_called()

    def test_add_entry_preserves_empty_fulldata_json_object(self):
        """Regression: `if fulldata_json:` treated an explicitly-passed
        empty object ({}) the same as omitted, leaving it as a raw dict
        that pymysql can't bind as a query parameter at all - not silent
        data loss but an outright TypeError, confirmed against a real
        MySQL/MariaDB connection - unlike a populated payload (a GitHub
        Copilot review finding on PR #206)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_entry(
                    type="test",
                    id="abc",
                    title="T",
                    source="s",
                    date="2024-01-01",
                    fulldata_json={},
                )

        insert_params = next(
            c.args[1]
            for c in mock_cursor.execute.call_args_list
            if "INSERT INTO" in c.args[0]
        )
        assert insert_params[-1] == "{}"

    def test_add_entry_updates_existing_when_update_true(self):
        """add_entry executes UPDATE when the entry exists and update=True."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "date_created": "2024-01-01"
        }  # Entry exists
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                result = store.add_entry(
                    type="test",
                    id="abc",
                    title="Updated",
                    source="s",
                    date="2024-01-02",
                    update=True,
                )

        assert result is db.EntryResult.UPDATED
        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any("UPDATE" in sql for sql in executed_sqls)
        mock_conn.commit.assert_called()

    def test_add_entry_returns_skipped_for_existing_when_update_false(self):
        """add_entry returns SKIPPED and does not UPDATE when entry exists and update=False."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "date_created": "2024-01-01"
        }  # Entry exists
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                result = store.add_entry(
                    type="test",
                    id="abc",
                    title="T",
                    source="s",
                    date="2024-01-01",
                    update=False,
                )

        assert result is db.EntryResult.SKIPPED
        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert not any("UPDATE" in sql for sql in executed_sqls)
        assert not any("INSERT" in sql for sql in executed_sqls)

    def test_add_location_executes_replace(self):
        """add_location issues REPLACE INTO lifestream_locations."""
        from datetime import datetime

        import pytz

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=pytz.utc)

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_location(ts, "test_source", 51.5, -0.1, "London")

        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any(
            "replace into lifestream_locations" in sql.lower() for sql in executed_sqls
        )
        mock_conn.commit.assert_called()

    def test_add_location_persists_fulldata(self):
        """add_location serializes the fulldata argument into fulldata_json, not empty string."""
        from datetime import datetime

        import pytz

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=pytz.utc)

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_location(
                    ts,
                    "test_source",
                    51.5,
                    -0.1,
                    "London",
                    fulldata={"raw": "payload"},
                )

        params = [c.args[1] for c in mock_cursor.execute.call_args_list]
        assert any('"raw": "payload"' in str(p[-1]) for p in params)

    def test_get_historic_entries_returns_matching_rows(self):
        """get_historic_entries queries lifestream with a DictCursor."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"title": "T", "systemid": "1", "source": "tumblr", "type": "text"}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            result = store.get_historic_entries("2016-01-01", "2016-01-02")

        assert result == [
            {"title": "T", "systemid": "1", "source": "tumblr", "type": "text"}
        ]
        assert mock_conn.cursor.call_args == call(db.pymysql.cursors.DictCursor)
        args, _ = mock_cursor.execute.call_args
        assert "tumblr" in args[0] and "twitter" in args[0]
        assert args[1] == ("2016-01-01", "2016-01-02")

    def test_get_historic_entries_upper_bound_is_exclusive(self):
        """The window is half-open, so a row exactly at date_to is not this
        run's - it belongs to the next, adjacent window instead, and an
        inclusive upper bound would replay it in both."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            store.get_historic_entries("2016-01-01", "2016-01-02")

        args, _ = mock_cursor.execute.call_args
        assert ">= %s" in args[0]
        assert "< %s" in args[0]
        assert "between" not in args[0].lower()

    def test_no_db_get_historic_entries_returns_empty_list(self):
        """--no-db mode returns no rows rather than touching the database."""
        store = db.EntryStore(no_db=True)
        result = store.get_historic_entries("2016-01-01", "2016-01-02")

        assert result == []

    def test_add_location_without_fulldata_stores_empty_string(self):
        """add_location with no fulldata stores an empty string, not the string 'None'."""
        from datetime import datetime

        import pytz

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=pytz.utc)

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_location(ts, "test_source", 51.5, -0.1, "London")

        params = [c.args[1] for c in mock_cursor.execute.call_args_list]
        assert any(p[-1] == "" for p in params)


class TestListEntries:
    """Tests for EntryStore.list_entries (public API, #134)."""

    def test_applies_exclusions_and_returns_total(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 2}
        mock_cursor.fetchall.return_value = [{"type": "steam", "systemid": "1"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            items, total = store.list_entries()

        assert items == [{"type": "steam", "systemid": "1"}]
        assert total == 2
        count_sql, count_params = mock_cursor.execute.call_args_list[0].args
        assert "title IS NOT NULL" in count_sql
        assert "source NOT IN" in count_sql
        assert count_params == ["tumblr", "lastfm"]

    def test_orders_by_date_created_by_default(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            store.list_entries()

        select_sql, _ = mock_cursor.execute.call_args_list[1].args
        assert "ORDER BY date_created ASC" in select_sql

    def test_orders_by_date_updated_when_after_given(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            store.list_entries(after="2024-01-01T00:00:00")

        select_sql, select_params = mock_cursor.execute.call_args_list[1].args
        assert "ORDER BY date_updated ASC" in select_sql
        assert "date_updated >= %s" in select_sql
        assert "2024-01-01T00:00:00" in select_params

    def test_applies_date_range_filters(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            store.list_entries(date_from="2024-01-01", date_to="2024-02-01")

        select_sql, select_params = mock_cursor.execute.call_args_list[1].args
        assert "date_created >= %s" in select_sql
        assert "date_created < %s" in select_sql
        assert select_params[-4:-2] == ["2024-01-01", "2024-02-01"]

    def test_no_db_returns_empty(self):
        store = db.EntryStore(no_db=True)
        assert store.list_entries() == ([], 0)


class TestSearchEntries:
    """Tests for EntryStore.search_entries (public API, #134)."""

    def test_searches_by_title_like(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 1}
        mock_cursor.fetchall.return_value = [{"title": "Matching Entry"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            items, total = store.search_entries(q="Match")

        assert items == [{"title": "Matching Entry"}]
        assert total == 1
        _, count_params = mock_cursor.execute.call_args_list[0].args
        assert count_params[-1] == "%Match%"

    def test_no_db_returns_empty(self):
        store = db.EntryStore(no_db=True)
        assert store.search_entries(q="anything") == ([], 0)


class TestListLocations:
    """Tests for EntryStore.list_locations (public API, #134)."""

    def test_filters_by_range_and_source(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"source": "owntracks"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            result = store.list_locations(
                date_from="2024-01-01", date_to="2024-02-01", source="owntracks"
            )

        assert result == [{"source": "owntracks"}]
        sql, params = mock_cursor.execute.call_args.args
        assert "timestamp >= %s" in sql
        assert "timestamp < %s" in sql
        assert "source = %s" in sql
        assert "ORDER BY timestamp ASC" in sql
        assert params == ["2024-01-01", "2024-02-01", "owntracks"]

    def test_no_db_returns_empty(self):
        store = db.EntryStore(no_db=True)
        assert store.list_locations(date_from="2024-01-01") == []


class TestGetLocationHeatmap:
    """Tests for EntryStore.get_location_heatmap (public API, #134)."""

    def test_aggregates_in_sql_not_python(self):
        """Regression: this used to SELECT every raw matching row and group
        them in Python, which loads unbounded result sets into memory for a
        wide date range (a GitHub Copilot review finding on PR #206). The
        grouping/counting must happen in SQL - verified here via the query
        shape, since a mocked cursor can't itself group rows the way a real
        GROUP BY does (see the real-MariaDB verification in the PR)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"lat": 51.5, "long": -0.1, "count": 2, "title": "Home", "icon": "house"},
            {"lat": 40.0, "long": -70.0, "count": 1, "title": None, "icon": None},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            points = store.get_location_heatmap(date_from="2024-01-01")

        # No Python-side grouping: fetchall()'s rows pass straight through.
        assert points == mock_cursor.fetchall.return_value
        sql = mock_cursor.execute.call_args.args[0]
        assert "GROUP BY ROUND(lat, 2), ROUND(`long`, 2)" in sql
        assert "COUNT(*) AS count" in sql
        assert "ROUND(lat, 2) AS lat" in sql
        assert "ROUND(`long`, 2) AS `long`" in sql

    def test_no_db_returns_empty(self):
        store = db.EntryStore(no_db=True)
        assert store.get_location_heatmap(date_from="2024-01-01") == []


class TestGetLatestLocation:
    """Tests for EntryStore.get_latest_location (public API, #134)."""

    def test_returns_most_recent_row(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"source": "owntracks", "id": 123}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            result = store.get_latest_location()

        assert result == {"source": "owntracks", "id": 123}
        sql = mock_cursor.execute.call_args.args[0]
        assert "ORDER BY timestamp DESC LIMIT 1" in sql

    def test_returns_none_when_no_rows(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            assert store.get_latest_location() is None

    def test_no_db_returns_none(self):
        store = db.EntryStore(no_db=True)
        assert store.get_latest_location() is None


class TestCreateLocation:
    """Tests for EntryStore.create_location (public API's POST /v1/locations,
    #134) — mirrors lifestream-web's add_location() dedup rule.

    Every real MySQL round trip here issues GET_LOCK before the dedup
    SELECT, so mocked fetchone() results are supplied via side_effect as
    [lock-acquisition result, dedup-SELECT result] rather than a single
    static return_value.
    """

    LOCK_ACQUIRED = {"acquired": 1}
    LOCK_NOT_ACQUIRED = {"acquired": 0}

    def test_skips_duplicate_within_rounding(self):
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            self.LOCK_ACQUIRED,
            {"lat_vague": 51.51, "long_vague": -0.09},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            row, created = store.create_location(
                source="owntracks",
                lat=51.53,
                lon=-0.08,
                timestamp=datetime(2024, 6, 1, 12, 0, 0),
            )

        assert created is False
        assert row == {"lat_vague": 51.51, "long_vague": -0.09}
        # No INSERT/REPLACE should have run for a deduped write.
        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert not any("REPLACE" in sql for sql in executed_sqls)

    def test_inserts_when_not_a_duplicate(self):
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                mock_cursor.fetchone.side_effect = [
                    self.LOCK_ACQUIRED,
                    None,  # no prior point
                ]
                store = db.EntryStore(no_db=False)
                row, created = store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 12, 0, 0),
                    title="Home",
                )

        assert created is True
        assert row["source"] == "owntracks"
        assert row["lat"] == 51.5
        assert row["title"] == "Home"
        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any("REPLACE INTO lifestream_locations" in sql for sql in executed_sqls)
        mock_conn.commit.assert_called()

    def test_no_db_inserts_and_returns_echoed_row(self, capsys):
        from datetime import datetime

        store = db.EntryStore(no_db=True)
        row, created = store.create_location(
            source="owntracks",
            lat=51.5,
            lon=-0.1,
            timestamp=datetime(2024, 6, 1, 12, 0, 0),
        )

        assert created is True
        assert row["source"] == "owntracks"
        captured = capsys.readouterr()
        assert "[NO-DB] LOCATION (API):" in captured.out

    def test_no_db_matches_mysql_normalization(self):
        """NoDbEntryStore.create_location is a preview of what the real
        backend would do - it should apply the same normalization
        (device/fulldata_json NOT NULL defaults, integer altitude, UTC
        epoch for naive timestamps), not a stale copy that drifted from
        MysqlEntryStore's fixes."""
        from datetime import datetime

        store = db.EntryStore(no_db=True)
        row, _ = store.create_location(
            source="owntracks",
            lat=51.5,
            lon=-0.1,
            timestamp=datetime(2024, 6, 1, 12, 0, 0),  # naive
            alt=12.7,
        )

        assert row["device"] == "old-data"
        assert row["fulldata_json"] == ""
        assert row["alt"] == 13
        assert row["alt_vague"] == 13
        assert row["id"] == 1717243200  # UTC epoch for 2024-06-01T12:00:00Z

    def test_serializes_the_dedup_check_with_an_advisory_lock(self):
        """Regression: the read-then-write dedup check used to run with no
        locking, so two concurrent requests for the same source could both
        read the same predecessor and both insert (a GitHub Copilot review
        finding on PR #206). GET_LOCK/RELEASE_LOCK, scoped to `source` and
        spanning the whole check-then-insert, close that window."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 12, 0, 0),
                )

        executed = [c.args for c in mock_cursor.execute.call_args_list]
        assert executed[0] == (
            "SELECT GET_LOCK(%s, 5) AS acquired",
            ("lifestream_location_dedup:owntracks",),
        )
        assert executed[-1] == (
            "SELECT RELEASE_LOCK(%s)",
            ("lifestream_location_dedup:owntracks",),
        )

    def test_raises_and_skips_release_when_lock_not_acquired(self):
        """Regression: GET_LOCK's result was previously discarded, so a
        timeout (0) or error (NULL) still fell through into the
        check-then-insert as if protected - silently reintroducing the
        exact race the lock exists to prevent (a GitHub Copilot review
        finding on PR #206). A failed acquisition must raise before ever
        reaching that block, and must never call RELEASE_LOCK for a lock
        this connection doesn't hold."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = self.LOCK_NOT_ACQUIRED
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                with pytest.raises(db.LocationDedupLockError):
                    store.create_location(
                        source="owntracks",
                        lat=51.5,
                        lon=-0.1,
                        timestamp=datetime(2024, 6, 1, 12, 0, 0),
                    )

        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert "SELECT RELEASE_LOCK(%s)" not in executed_sqls
        assert not any("REPLACE" in sql for sql in executed_sqls)
        mock_conn.commit.assert_not_called()

    def test_releases_lock_even_if_insert_raises(self):
        """The lock must not be held forever just because this particular
        write failed - RELEASE_LOCK runs in a `finally`."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.side_effect = RuntimeError("boom")

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                with pytest.raises(RuntimeError):
                    store.create_location(
                        source="owntracks",
                        lat=51.5,
                        lon=-0.1,
                        timestamp=datetime(2024, 6, 1, 12, 0, 0),
                    )

        executed = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert executed[-1] == "SELECT RELEASE_LOCK(%s)"

    def test_omitted_device_defaults_to_schema_default_not_null(self):
        """lifestream_locations.device is `NOT NULL DEFAULT 'old-data'` -
        binding an explicit NULL bypasses that default and fails under
        strict SQL mode, so an omitted device must be normalized in Python
        instead of passed through as None (a GitHub Copilot review finding
        on PR #206)."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
                store = db.EntryStore(no_db=False)
                row, _ = store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 12, 0, 0),
                )

        assert row["device"] == "old-data"
        insert_params = next(
            c.args[1]
            for c in mock_cursor.execute.call_args_list
            if "REPLACE INTO lifestream_locations" in c.args[0]
        )
        # Params are positional: (id, source, device, accuracy, lat, long,
        # alt, lat_vague, long_vague, alt_vague, timestamp, title, icon,
        # fulldata_json) - `device` is index 2.
        assert insert_params[2] == "old-data"

    def test_omitted_fulldata_json_defaults_to_empty_string_not_null(self):
        """lifestream_locations.fulldata_json is NOT NULL - binding an
        explicit NULL for an omitted payload fails the insert instead of
        recording the location (a GitHub Copilot review finding on
        PR #206); the legacy add_location() already used "" for the same
        reason."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
                store = db.EntryStore(no_db=False)
                row, _ = store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 12, 0, 0),
                )

        assert row["fulldata_json"] == ""
        insert_params = next(
            c.args[1]
            for c in mock_cursor.execute.call_args_list
            if "REPLACE INTO lifestream_locations" in c.args[0]
        )
        assert insert_params[-1] == ""

    def test_naive_and_aware_timestamps_for_the_same_instant_agree(self):
        """Regression: epoch was computed via a naive timestamp.timestamp()
        call, which Python interprets in the server's *local* timezone - so
        the same wall-clock string produced a different epoch id depending
        on the server's own timezone setting (a GitHub Copilot review
        finding on PR #206). A naive input must be treated as UTC, matching
        every other timestamp in this table."""
        from datetime import datetime, timezone

        def _insert(ts):
            mock_cursor = MagicMock()
            mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            with patch.object(db, "get_connection", return_value=mock_conn):
                with patch.object(db, "get_cursor", return_value=mock_cursor):
                    store = db.EntryStore(no_db=False)
                    row, _ = store.create_location(
                        source="owntracks", lat=51.5, lon=-0.1, timestamp=ts
                    )
            return row["id"]

        naive_epoch = _insert(datetime(2024, 6, 1, 12, 0, 0))
        aware_epoch = _insert(datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc))

        assert naive_epoch == aware_epoch

    def test_non_utc_aware_timestamp_converted_before_epoch(self):
        """A timezone-aware timestamp in a non-UTC zone must be converted,
        not just have its tzinfo stripped - otherwise the "same wall clock,
        different zone" case would silently derive the wrong instant."""
        from datetime import datetime, timedelta, timezone

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        plus_five = timezone(timedelta(hours=5))
        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                row, _ = store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 17, 0, 0, tzinfo=plus_five),
                )

        # 17:00 in UTC+5 is 12:00 UTC - must match the UTC-noon epoch above.
        expected = int(datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        assert row["id"] == expected

    def test_altitude_rounded_to_int_for_int_column(self):
        """lifestream_locations.alt/alt_vague are plain INT columns - a raw
        float would be silently truncated by MySQL, so the response would
        claim more precision than was actually persisted (a GitHub Copilot
        review finding on PR #206). alt and alt_vague must be the same
        rounded integer, both in the stored row and the response."""
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                mock_cursor.fetchone.side_effect = [self.LOCK_ACQUIRED, None]
                store = db.EntryStore(no_db=False)
                row, _ = store.create_location(
                    source="owntracks",
                    lat=51.5,
                    lon=-0.1,
                    timestamp=datetime(2024, 6, 1, 12, 0, 0),
                    alt=12.7,
                )

        assert row["alt"] == 13
        assert row["alt_vague"] == 13
        insert_params = next(
            c.args[1]
            for c in mock_cursor.execute.call_args_list
            if "REPLACE INTO lifestream_locations" in c.args[0]
        )
        # Positional params: (id, source, device, accuracy, lat, long, alt,
        # lat_vague, long_vague, alt_vague, ...) - alt is index 6, alt_vague
        # index 9.
        assert insert_params[6] == 13
        assert insert_params[9] == 13


class TestAddUnhandledLocation:
    """Tests for EntryStore.add_unhandled_location (public API's
    POST /v1/locations/unhandled, #134) — mirrors raw_location_data()."""

    def test_inserts_type_and_json_payload(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_unhandled_location("waypoints", {"lat": 1, "lon": 2})

        sql, params = mock_cursor.execute.call_args.args
        assert "owntracks_unhandled" in sql
        assert params[0] == "waypoints"
        assert '"lat": 1' in params[1]
        # No reason given: stored as NULL.
        assert "`why`" in sql
        assert params[2] is None
        mock_conn.commit.assert_called()

    def test_records_why(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_connection", return_value=mock_conn):
            with patch.object(db, "get_cursor", return_value=mock_cursor):
                store = db.EntryStore(no_db=False)
                store.add_unhandled_location("location", {"lat": 1}, "dedupe")

        _, params = mock_cursor.execute.call_args.args
        assert params[2] == "dedupe"

    def test_no_db_prints_instead_of_writing(self, capsys):
        store = db.EntryStore(no_db=True)
        store.add_unhandled_location("waypoints", {"lat": 1}, "unhandled_type")

        captured = capsys.readouterr()
        assert "[NO-DB] UNHANDLED LOCATION:" in captured.out
        assert "why=unhandled_type" in captured.out


class TestClose:
    """Tests for EntryStore.close() (used by the public API's per-request
    dependency, lifestream.core.api.get_entry_store, so a long-running
    webserver process doesn't leak one MySQL connection per request - a
    GitHub Copilot review finding on PR #206)."""

    def test_closes_an_opened_connection(self):
        mock_conn = MagicMock()

        with patch.object(db, "get_connection", return_value=mock_conn):
            store = db.EntryStore(no_db=False)
            store.get_by_id("test", "123")  # forces the lazy connection open
            store.close()

        mock_conn.close.assert_called_once()

    def test_does_not_force_a_connection_just_to_close_it(self):
        """A store that never ran a query - e.g. an API request that hit an
        endpoint not needing the DB - must not open a connection purely to
        immediately close it."""
        mock_conn = MagicMock()

        with patch.object(db, "get_connection", return_value=mock_conn) as get_conn:
            store = db.EntryStore(no_db=False)
            store.close()

        get_conn.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_no_db_close_is_a_noop(self):
        store = db.EntryStore(no_db=True)
        store.close()  # must not raise
