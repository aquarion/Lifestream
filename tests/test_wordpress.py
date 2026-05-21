"""Tests for WordPress importer error propagation."""

import configparser
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.wordpress import WordpressImporter


class TestWordpressImporter:
    def _make_importer(self):
        imp = WordpressImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_process_site_raises_on_missing_section(self):
        """Missing config section raises ConfigurationError, not silent return."""
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.side_effect = configparser.NoSectionError("wordpress:missing")

        with patch("lifestream.importers.wordpress.config", mock_config):
            with pytest.raises(ConfigurationError, match="wordpress:missing"):
                imp.process_site("missing")

    def test_process_site_raises_on_invalid_credentials(self):
        """Invalid credentials raise RuntimeError, not silent loop exit."""
        from wordpress_xmlrpc import exceptions as wp_exc

        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        mock_client = MagicMock()
        mock_client.call.side_effect = wp_exc.InvalidCredentialsError()

        with patch("lifestream.importers.wordpress.config", mock_config):
            with patch(
                "lifestream.importers.wordpress.Client", return_value=mock_client
            ):
                with pytest.raises(RuntimeError, match="Invalid credentials"):
                    imp.process_site("mysite")
