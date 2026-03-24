"""Shared pytest fixtures for Lifestream tests."""

import configparser
import os
import sys
from unittest.mock import MagicMock

import pytest

# Set testing mode BEFORE any lifestream imports to skip auto-logging setup
os.environ["LIFESTREAM_TESTING"] = "1"

# Set up imports directory in path BEFORE any lifestream imports
imports_dir = os.path.join(os.path.dirname(__file__), "..", "imports")
sys.path.insert(0, imports_dir)

# Change to imports directory so lifestream can find config
os.chdir(imports_dir)


@pytest.fixture
def mock_config():
    """Create a mock config object with common test values."""
    config = configparser.ConfigParser()
    config.read_dict(
        {
            "database": {
                "hostname": "localhost",
                "database": "test_db",
                "username": "test_user",
                "password": "test_pass",
            },
            "redis": {
                "host": "localhost",
                "port": "6379",
            },
            "notifications": {
                "enabled": "true",
                "smtp_host": "smtp.test.com",
                "smtp_port": "587",
                "from_address": "test@test.com",
                "to_address": "user@test.com",
                "slack_channel": "test-channel",
            },
            "slack": {
                "token": "test-token",
                "slack_botname": "TestBot",
            },
            "global": {
                "secrets_dir": "keys/",
                "log_location": "/tmp/",
            },
        }
    )
    return config


@pytest.fixture
def mock_redis():
    """Create a mock Redis connection."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.ttl.return_value = 3600
    return mock


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor
