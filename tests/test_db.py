"""Tests for lifestream.core.db module."""

from unittest.mock import MagicMock, call, patch

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
                store.add_entry(
                    type="test", id="abc", title="T", source="s", date="2024-01-01"
                )

        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO" in sql for sql in executed_sqls)
        mock_conn.commit.assert_called()

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
                store.add_entry(
                    type="test",
                    id="abc",
                    title="Updated",
                    source="s",
                    date="2024-01-02",
                    update=True,
                )

        executed_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert any("UPDATE" in sql for sql in executed_sqls)
        mock_conn.commit.assert_called()

    def test_add_entry_returns_false_for_existing_when_update_false(self):
        """add_entry returns False and does not UPDATE when entry exists and update=False."""
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

        assert result is False
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
