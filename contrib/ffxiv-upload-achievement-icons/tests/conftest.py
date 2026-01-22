"""Shared test fixtures and configuration for pytest."""

import configparser
import os
import sys
import tempfile
from unittest.mock import Mock

import pytest

# Ensure the lib/python directory is in the path for all tests
lib_python_path = os.path.join(os.path.dirname(__file__), "..", "lib", "python")
if lib_python_path not in sys.path:
    sys.path.insert(0, lib_python_path)


@pytest.fixture
def temp_database():
    """Create a temporary database file for testing."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    yield temp_db.name
    # Cleanup
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    config = configparser.ConfigParser()

    config.add_section("local")
    config.set("local", "data_directory", "/tmp/test_data")
    config.set("local", "icon_directory", "/tmp/test_icons")

    config.add_section("remote")
    config.set("remote", "remote_server", "test.example.com")
    config.set("remote", "remote_user", "testuser")
    config.set("remote", "remote_icon_directory", "/remote/test_icons")

    return config


@pytest.fixture
def sample_achievement():
    """Create a sample achievement record for testing."""
    return {
        "ID": 1,
        "Name": "Test Achievement",
        "Icon": 123456,
        "Description": "A test achievement for unit testing",
    }


@pytest.fixture
def mock_ssh_client():
    """Create a mock SSH client for testing."""
    mock_client = Mock()
    mock_client.connection = Mock()
    mock_client.sftp = Mock()
    return mock_client
