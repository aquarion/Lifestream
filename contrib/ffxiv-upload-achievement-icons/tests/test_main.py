"""Tests for main update_achievement_images script."""

import configparser
import logging
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add the script directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# pylint: disable=wrong-import-position
from update_achievement_images import (  # noqa: E402
    CustomFormatter,
    SSHClient,
    process_achivement,
    validate_config,
)

# pylint: enable=wrong-import-position
# flake8: noqa E402


class TestCustomFormatter(unittest.TestCase):
    """Test cases for CustomFormatter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = CustomFormatter()

    def test_format_debug_message(self):
        """Test formatting debug level message."""
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=10,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        # Should contain debug message and reset color code
        self.assertIn("Debug message", formatted)
        self.assertIn("\x1b[0m", formatted)  # Reset code

    def test_format_error_message(self):
        """Test formatting error level message."""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        # Should contain error message and appropriate color
        self.assertIn("Error message", formatted)
        self.assertIn("\x1b[31;20m", formatted)  # Red color


class TestSSHClient(unittest.TestCase):
    """Test cases for SSHClient class."""

    @patch("update_achievement_images.Connection")
    def test_initialization_success(self, mock_connection_class):
        """Test successful SSH client initialization."""
        mock_connection = Mock()
        mock_connection_class.return_value = mock_connection

        client = SSHClient("test.server.com", "testuser")

        self.assertEqual(client.connection, mock_connection)
        mock_connection_class.assert_called_with(
            host="test.server.com", user="testuser", connect_kwargs={"compress": True}
        )

    @patch("update_achievement_images.Connection")
    def test_initialization_failure(self, mock_connection_class):
        """Test SSH client initialization failure."""
        from paramiko import ssh_exception as SSH_Exception

        mock_connection_class.side_effect = SSH_Exception.AuthenticationException(
            "Auth failed"
        )

        with patch("update_achievement_images.logger"):
            client = SSHClient("test.server.com", "testuser")

            self.assertIsNone(client.connection)

    @patch("update_achievement_images.Connection")
    def test_context_manager(self, mock_connection_class):
        """Test SSH client as context manager."""
        mock_connection = Mock()
        mock_connection_class.return_value = mock_connection

        client = SSHClient("test.server.com", "testuser")

        # Test __enter__
        result = client.__enter__()
        self.assertEqual(result, client)

        # Test __exit__
        client.__exit__(None, None, None)
        # Should close connection in destructor

    def test_check_or_create_directory_exists(self):
        """Test checking directory that already exists."""
        client = SSHClient.__new__(SSHClient)  # Create instance without __init__
        client.connection = Mock()
        client.sftp = Mock()

        # Mock directory exists
        client.sftp.stat.return_value = Mock()

        result = client.check_or_create_directory("/existing/path")
        self.assertTrue(result)
        client.sftp.stat.assert_called_with("/existing/path")

    def test_check_or_create_directory_create(self):
        """Test creating directory that doesn't exist."""
        client = SSHClient.__new__(SSHClient)
        client.connection = Mock()
        client.sftp = Mock()

        # Mock directory doesn't exist
        client.sftp.stat.side_effect = IOError("Directory not found")

        result = client.check_or_create_directory("/new/path")
        self.assertTrue(result)
        client.sftp.mkdir.assert_called_with("/new/path")


class TestValidateConfig(unittest.TestCase):
    """Test cases for validate_config function."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = configparser.ConfigParser()

    def test_valid_config(self):
        """Test validation with valid configuration."""
        # Add required sections and values
        self.config.add_section("local")
        self.config.add_section("remote")

        self.config.set("local", "data_directory", "/tmp/data")
        self.config.set("local", "icon_directory", "/tmp/icons")
        self.config.set("remote", "remote_server", "example.com")
        self.config.set("remote", "remote_user", "testuser")
        self.config.set("remote", "remote_icon_directory", "/remote/icons")

        # Should not raise any exception
        validate_config(self.config)

    def test_missing_section(self):
        """Test validation with missing section."""
        # Only add local section, missing remote
        self.config.add_section("local")

        with self.assertRaises((ValueError, configparser.NoSectionError)):
            validate_config(self.config)

    def test_missing_option(self):
        """Test validation with missing required option."""
        self.config.add_section("local")
        self.config.add_section("remote")

        # Missing required options
        self.config.set("local", "data_directory", "/tmp/data")
        # Missing icon_directory and remote options

        with self.assertRaises((ValueError, configparser.NoOptionError)):
            validate_config(self.config)


class TestProcessAchievement(unittest.TestCase):
    """Test cases for process_achivement function."""

    def setUp(self):
        """Set up test fixtures."""
        self.achievement = {"ID": 1, "Name": "Test Achievement", "Icon": 123456}

        self.saint_coinach_client = Mock()
        self.ssh_client = Mock()
        self.files = {}

        self.config = configparser.ConfigParser()
        self.config.add_section("remote")
        self.config.add_section("local")
        self.config.set("remote", "remote_icon_directory", "/remote/icons")
        self.config.set("local", "icon_directory", "/local/icons")

    def test_process_achievement_no_name(self):
        """Test processing achievement with no name."""
        achievement_no_name = {"ID": 1, "Name": None, "Icon": 123456}

        with patch("update_achievement_images.logger") as mock_logger:
            result = process_achivement(
                achievement_no_name,
                self.saint_coinach_client,
                self.ssh_client,
                self.files,
                self.config,
            )

            self.assertFalse(result)
            mock_logger.info.assert_called()

    @patch("os.path.isdir")
    def test_process_achievement_no_icon_path(self, mock_isdir):
        """Test processing achievement when local icon image doesn't exist."""
        # Mock find_icons_path to return a valid string
        self.saint_coinach_client.find_icons_path.return_value = "/local/icons/path"
        # Mock isdir to return True so we get past the directory check
        mock_isdir.return_value = True
        self.saint_coinach_client.icon_path.return_value = "123456.png"
        self.saint_coinach_client.icon_image.return_value = "123456.png"

        # Mock that the file doesn't exist
        with patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = False

            with patch("update_achievement_images.logger") as mock_logger:
                result = process_achivement(
                    self.achievement,
                    self.saint_coinach_client,
                    self.ssh_client,
                    self.files,
                    self.config,
                )

                self.assertFalse(result)
                mock_logger.warning.assert_called()

    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_process_achievement_file_not_found(
        self, mock_isfile, mock_isdir, mock_exists
    ):
        """Test processing achievement when local file doesn't exist."""
        # Mock find_icons_path to return a valid string
        self.saint_coinach_client.find_icons_path.return_value = "/local/icons/path"
        self.saint_coinach_client.icon_path.return_value = "/local/icon/path.tex"
        self.saint_coinach_client.icon_image.return_value = "icon.tex"

        # Mock directory exists but file doesn't
        mock_isdir.return_value = True
        mock_isfile.return_value = False
        mock_exists.return_value = False

        with patch("update_achievement_images.logger") as mock_logger:
            result = process_achivement(
                self.achievement,
                self.saint_coinach_client,
                self.ssh_client,
                self.files,
                self.config,
            )

            self.assertFalse(result)
            mock_logger.warning.assert_called()

    @patch("os.path.exists")
    @patch("os.stat")
    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_process_achievement_success(
        self, mock_isfile, mock_isdir, mock_stat, mock_exists
    ):
        """Test successful achievement processing."""
        # Mock file exists and has size
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        mock_stat_result = Mock()
        mock_stat_result.st_size = 1024
        mock_stat.return_value = mock_stat_result

        # Mock find_icons_path to return a valid string
        self.saint_coinach_client.find_icons_path.return_value = "/local/icons/path"
        self.saint_coinach_client.icon_path.return_value = "/local/icon/123456.tex"
        self.saint_coinach_client.icon_image.return_value = "icon.tex"

        # Mock that file doesn't exist on remote
        # remote_filepath = "/remote/icons/123456.png"
        self.files = {}  # Empty files means file doesn't exist on remote

        # Mock successful upload
        self.ssh_client.put.return_value = True

        with patch("update_achievement_images.logger") as _mock_logger:
            result = process_achivement(
                self.achievement,
                self.saint_coinach_client,
                self.ssh_client,
                self.files,
                self.config,
            )

            self.assertTrue(result)
            self.ssh_client.put.assert_called()


if __name__ == "__main__":
    unittest.main()
