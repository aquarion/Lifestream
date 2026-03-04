"""Tests for lifestream.db module."""

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
        mock_args = MagicMock()
        mock_args.no_db = True

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            store = db.EntryStore()
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
        mock_args = MagicMock()
        mock_args.no_db = False

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "type": "test", "systemid": "123"}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            with patch.object(db, "get_connection", return_value=mock_conn):
                store = db.EntryStore()
                result = store.get_by_id("test", "123")

                assert result == {"id": 1, "type": "test", "systemid": "123"}

    def test_get_by_id_returns_none_when_not_found(self):
        """Test get_by_id returns None when entry not found."""
        mock_args = MagicMock()
        mock_args.no_db = False

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            with patch.object(db, "get_connection", return_value=mock_conn):
                store = db.EntryStore()
                result = store.get_by_id("test", "nonexistent")

                assert result is None

    def test_delete_entry_removes_entry(self):
        """Test delete_entry executes DELETE query."""
        mock_args = MagicMock()
        mock_args.no_db = False

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            with patch.object(db, "get_connection", return_value=mock_conn):
                with patch.object(db, "get_cursor", return_value=mock_cursor):
                    store = db.EntryStore()
                    store.delete_entry("test", "123")

                    mock_cursor.execute.assert_called()
                    mock_conn.commit.assert_called()

    def test_add_stat_replaces_stat(self):
        """Test add_stat uses REPLACE INTO."""
        mock_args = MagicMock()
        mock_args.no_db = False

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            with patch.object(db, "get_connection", return_value=mock_conn):
                with patch.object(db, "get_cursor", return_value=mock_cursor):
                    store = db.EntryStore()
                    result = store.add_stat("2024-01-01", "test_stat", 42)

                    assert result is True
                    mock_conn.commit.assert_called()

    def test_no_db_add_stat_prints(self, capsys):
        """Test add_stat in no-db mode prints instead of writing."""
        mock_args = MagicMock()
        mock_args.no_db = True

        with patch.object(db, "get_parsed_args", return_value=mock_args):
            store = db.EntryStore()
            result = store.add_stat("2024-01-01", "test_stat", 42)

            captured = capsys.readouterr()
            assert "[NO-DB] STAT:" in captured.out
            assert result is True
