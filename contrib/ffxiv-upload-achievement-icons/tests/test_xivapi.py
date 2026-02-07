"""Tests for XIVAPI module."""

import logging
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add lib/python to path for imports

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))


# pylint: disable=wrong-import-position,import-error
from XIVAPI import XIVClient  # noqa: E402

# pylint: enable=wrong-import-position,import-error


class TestXIVClient(unittest.TestCase):
    """Test cases for XIVClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345"
        self.client = XIVClient(self.api_key)

    def test_initialization(self):
        """Test XIVClient initialization."""
        self.assertEqual(self.client.api_key, self.api_key)

    def test_set_log_level(self):
        """Test setting log level."""
        # Test that the method runs without error
        self.client.set_log_level(logging.INFO)

        # The actual logger should have the level set
        logger = logging.getLogger("XIVAPI")
        self.assertEqual(logger.level, logging.INFO)

    @patch("requests.get")
    def test_call_basic(self, mock_get):
        """Test basic API call."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        result = self.client._call("/test")

        mock_get.assert_called_once()
        self.assertEqual(result, {"test": "data"})

        # Check that API key was included in params
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["private_key"], self.api_key)

    @patch("requests.get")
    def test_call_with_pagination(self, mock_get):
        """Test API call with pagination parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        self.client._call("/test", limit=500, page=2)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["limit"], 500)
        self.assertEqual(params["page"], 2)
        self.assertEqual(params["private_key"], self.api_key)

    @patch("requests.get")
    def test_call_no_limit(self, mock_get):
        """Test API call with no limit."""
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        self.client._call("/test", limit=None)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        self.assertNotIn("limit", params)

    @patch("requests.get")
    def test_get_achievement(self, mock_get):
        """Test getting a specific achievement."""
        mock_response = Mock()
        expected_data = {"ID": 123, "Name": "Test Achievement", "Icon": 456}
        mock_response.json.return_value = expected_data
        mock_get.return_value = mock_response

        result = self.client.get_achievement(123)

        self.assertEqual(result, expected_data)
        call_args = mock_get.call_args
        self.assertIn("/achievement/123", call_args[0][0])

    @patch("requests.get")
    def test_list_achievements_single_page(self, mock_get):
        """Test listing achievements with single page response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Results": [
                {"ID": 1, "Name": "Achievement 1"},
                {"ID": 2, "Name": "Achievement 2"},
            ],
            "Pagination": {"PageNext": None, "PageTotal": 1},
        }
        mock_get.return_value = mock_response

        result = self.client.list_achievements()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ID"], 1)
        self.assertEqual(result[1]["ID"], 2)

        # Should only make one API call for single page
        self.assertEqual(mock_get.call_count, 1)

    @patch("requests.get")
    def test_list_achievements_multiple_pages(self, mock_get):
        """Test listing achievements with multiple pages."""
        # First page response
        first_page = {
            "Results": [{"ID": 1, "Name": "Achievement 1"}],
            "Pagination": {"PageNext": 2, "PageTotal": 2},
        }

        # Second page response
        second_page = {
            "Results": [{"ID": 2, "Name": "Achievement 2"}],
            "Pagination": {"PageNext": None, "PageTotal": 2},
        }

        # Configure mock to return different responses for each call
        mock_response_1 = Mock()
        mock_response_1.json.return_value = first_page
        mock_response_2 = Mock()
        mock_response_2.json.return_value = second_page

        mock_get.side_effect = [mock_response_1, mock_response_2]

        result = self.client.list_achievements()

        # Should get results from both pages
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ID"], 1)
        self.assertEqual(result[1]["ID"], 2)

        # Should make two API calls for two pages
        self.assertEqual(mock_get.call_count, 2)

        # Check that second call included page parameter
        second_call_args = mock_get.call_args_list[1]
        params = second_call_args[1]["params"]
        self.assertEqual(params["page"], 2)

    @patch("requests.get")
    def test_api_timeout(self, mock_get):
        """Test that API calls include timeout parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        self.client._call("/test")

        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["timeout"], 10)

    @patch("requests.get")
    def test_api_base_url(self, mock_get):
        """Test that API calls use correct base URL."""
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        self.client._call("/achievement/123")

        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://xivapi.com/achievement/123")


if __name__ == "__main__":
    unittest.main()
