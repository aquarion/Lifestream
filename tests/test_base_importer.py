from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import BaseImporter, ConfigurationError


def _raise(exc):
    raise exc


class ConcreteImporter(BaseImporter):
    """Minimal concrete importer for testing."""

    name = "test_importer"
    description = "Test"

    def __init__(self, run_fn=None):
        super().__init__()
        self._run_fn = run_fn

    def run(self):
        if self._run_fn:
            self._run_fn()


class TestBaseImporterExecute:
    def test_execute_returns_0_on_success(self):
        imp = ConcreteImporter()
        with patch("lifestream.importers.base.setup_logging"):
            result = imp.execute([])
        assert result == 0

    def test_execute_returns_5_on_validate_config_false(self):
        imp = ConcreteImporter()
        imp.validate_config = MagicMock(return_value=False)
        with patch("lifestream.importers.base.setup_logging"):
            result = imp.execute([])
        assert result == 5

    def test_execute_returns_5_on_configuration_error(self):
        imp = ConcreteImporter(run_fn=lambda: _raise(ConfigurationError("missing key")))
        with patch("lifestream.importers.base.setup_logging"):
            result = imp.execute([])
        assert result == 5

    def test_execute_returns_1_on_unexpected_exception(self):
        imp = ConcreteImporter(run_fn=lambda: _raise(RuntimeError("boom")))
        with patch("lifestream.importers.base.setup_logging"):
            result = imp.execute([])
        assert result == 1

    def test_execute_returns_130_on_keyboard_interrupt(self):
        imp = ConcreteImporter(run_fn=lambda: _raise(KeyboardInterrupt()))
        with patch("lifestream.importers.base.setup_logging"):
            result = imp.execute([])
        assert result == 130

    def test_require_config_raises_on_missing_key(self):
        imp = ConcreteImporter()
        mock_config = MagicMock()
        mock_config.has_option.return_value = False

        with patch("lifestream.importers.base.config", mock_config):
            with pytest.raises(
                ConfigurationError,
                match=r"Missing required config keys in \[test_importer\]: api_key, username",
            ):
                imp.require_config("api_key", "username")
