"""Tests for SaintCoinach module."""

import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

# Add lib/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))

# pylint: disable=wrong-import-position,import-error
from SaintCoinach import SaintCoinach  # noqa: E402

# pylint: enable=wrong-import-position,import-error


class TestSaintCoinach(unittest.TestCase):
    """Test cases for SaintCoinach class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        # Create test config
        self.config = MagicMock()
        self.config.get.return_value = "test_value"

        # Initialize SaintCoinach instance
        self.saint_coinach = SaintCoinach(self.temp_db.name, self.config)

        # Create test table
        cursor = self.saint_coinach.db_connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                ID INTEGER PRIMARY KEY,
                Name TEXT,
                Icon INTEGER
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS updates (
                thing TEXT PRIMARY KEY,
                timestamp DATETIME
            )
        """
        )
        self.saint_coinach.db_connection.commit()

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "saint_coinach"):
            self.saint_coinach.db_connection.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_initialization(self):
        """Test SaintCoinach initialization."""
        self.assertIsNotNone(self.saint_coinach.db_connection)
        self.assertEqual(self.saint_coinach.config, self.config)
        self.assertIsNone(self.saint_coinach.icons_path)

    def test_set_log_level_debug(self):
        """Test setting log level to debug."""
        # Test that the method runs without error
        self.saint_coinach.set_log_level(logging.DEBUG)

        # The actual logger should have the level set
        logger = logging.getLogger("SaintCoinach")
        self.assertEqual(logger.level, logging.DEBUG)

    def test_set_log_level_with_int(self):
        """Test setting log level with integer value."""
        # Test that the method runs without error
        self.saint_coinach.set_log_level(10)  # DEBUG level

        # The actual logger should have the level set
        logger = logging.getLogger("SaintCoinach")
        self.assertEqual(logger.level, 10)
        """Test counting achievements in empty database."""
        count = self.saint_coinach.count_achievements()
        self.assertEqual(count, 0)

    def test_count_achievements_with_data(self):
        """Test counting achievements with test data."""
        # Insert test data
        cursor = self.saint_coinach.db_connection.cursor()
        cursor.execute(
            "INSERT INTO achievements (ID, Name, Icon) VALUES (1, 'Test Achievement', 123)"
        )
        cursor.execute(
            "INSERT INTO achievements (ID, Name, Icon) VALUES (2, 'Another Achievement', 456)"
        )
        self.saint_coinach.db_connection.commit()

        count = self.saint_coinach.count_achievements()
        self.assertEqual(count, 2)

    def test_get_achievement_exists(self):
        """Test getting an achievement that exists."""
        # Insert test data
        cursor = self.saint_coinach.db_connection.cursor()
        cursor.execute(
            "INSERT INTO achievements (ID, Name, Icon) VALUES (1, 'Test Achievement', 123)"
        )
        self.saint_coinach.db_connection.commit()

        achievement = self.saint_coinach.get_achievement(1)
        self.assertIsNotNone(achievement)
        self.assertEqual(achievement["ID"], 1)
        self.assertEqual(achievement["Name"], "Test Achievement")
        self.assertEqual(achievement["Icon"], 123)

    def test_get_achievement_not_exists(self):
        """Test getting an achievement that doesn't exist."""
        achievement = self.saint_coinach.get_achievement(999)
        self.assertIsNone(achievement)

    def test_icon_path_with_icon_id(self):
        """Test generating icon path from icon ID."""
        path = self.saint_coinach.icon_path(123456)
        expected = "123000/123456.png"
        self.assertEqual(path, expected)

    def test_icon_path_no_icons_path(self):
        """Test icon_path when icons_path is not set."""
        path = self.saint_coinach.icon_path(123456)
        expected = "123000/123456.png"
        self.assertEqual(path, expected)

    def test_save_update_timestamp(self):
        """Test saving update timestamp."""
        with patch("sqlite3.connect") as mock_connect:
            mock_cursor = Mock()
            mock_connection = Mock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            # Create a new instance for this test to use the mocked connection
            saint_coinach = SaintCoinach(":memory:", self.config)
            saint_coinach.db_connection = mock_connection

            saint_coinach.save_update_timestamp("test_update")

            mock_cursor.execute.assert_called()
            mock_connection.commit.assert_called()

    def test_was_timestamp_updated_within_recent(self):
        """Test checking if timestamp was updated recently."""
        # Save a timestamp for "test_thing"
        self.saint_coinach.save_update_timestamp("test_thing")

        # Check if it was updated within the last hour (3600 seconds)
        result = self.saint_coinach.was_timestamp_updated_within("test_thing", 3600)
        self.assertTrue(result)

    def test_was_timestamp_updated_within_old(self):
        """Test checking if timestamp was updated long ago."""
        # This should return False for a non-existent timestamp
        result = self.saint_coinach.was_timestamp_updated_within("nonexistent", 1)
        self.assertFalse(result)

    @patch("requests.get")
    def test_update_achievement_database_success(self, mock_get):
        """Test successful database update."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            "ID,Name,Icon\n"
            "Header Row 2\n"
            "Header Row 3\n"
            "1,Test Achievement,123\n"
            "2,Another Achievement,456"
        )
        mock_get.return_value = mock_response

        # Mock schema file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".sql"
        ) as temp_schema:
            temp_schema.write(
                "CREATE TABLE IF NOT EXISTS achievements (ID INTEGER, Name TEXT, Icon INTEGER);"
            )
            temp_schema_path = temp_schema.name

        try:
            self.saint_coinach.update_achievement_database(temp_schema_path)

            # Verify achievements were inserted
            count = self.saint_coinach.count_achievements()
            self.assertEqual(count, 2)

        finally:
            os.unlink(temp_schema_path)

    @patch("SaintCoinach.iglob")
    @patch("os.path.isdir")
    @patch("os.path.basename")
    def test_find_icons_path_found(self, mock_basename, mock_isdir, mock_iglob):
        """Test finding icons path when directory exists."""

        # Mock that both base directory and versioned subdirectory exist
        def isdir_side_effect(path):
            # Return True for both base directory and versioned subdirectory
            return path in ["/test/icons", "/test/icons/2024.01.01.0000.0000"]

        mock_isdir.side_effect = isdir_side_effect
        # Mock that we find a versioned directory
        mock_iglob.return_value = ["/test/icons/2024.01.01.0000.0000"]
        # Mock basename to return the version string
        mock_basename.return_value = "2024.01.01.0000.0000"

        self.saint_coinach.find_icons_path("/test/icons")

        self.assertEqual(
            self.saint_coinach.icons_path, "/test/icons/2024.01.01.0000.0000/ui/icon"
        )
        # Verify the mocks were called
        mock_iglob.assert_called_with("/test/icons/*")

    @patch("os.path.isdir")
    def test_find_icons_path_not_found(self, mock_isdir):
        """Test finding icons path when directory doesn't exist."""
        mock_isdir.return_value = False

        with self.assertRaises(IOError):
            self.saint_coinach.find_icons_path("/nonexistent/path")


if __name__ == "__main__":
    unittest.main()
