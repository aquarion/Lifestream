from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import BaseImporter, ConfigurationError, OAuthImporter


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

    def test_run_with_setup_calls_run(self):
        """run_with_setup() calls run() when config validates."""
        run_fn = MagicMock()
        imp = ConcreteImporter(run_fn=run_fn)
        with patch("lifestream.importers.base.setup_logging"):
            imp.run_with_setup([])
        run_fn.assert_called_once()

    def test_run_with_setup_raises_configuration_error_on_invalid_config(self):
        """run_with_setup() raises ConfigurationError when validate_config() is False."""
        imp = ConcreteImporter()
        imp.validate_config = MagicMock(return_value=False)
        with patch("lifestream.importers.base.setup_logging"):
            with pytest.raises(ConfigurationError, match="Config validation failed"):
                imp.run_with_setup([])

    def test_run_with_setup_propagates_run_exceptions(self):
        """run_with_setup() lets exceptions from run() propagate uncaught."""
        imp = ConcreteImporter(run_fn=lambda: _raise(ValueError("boom")))
        with patch("lifestream.importers.base.setup_logging"):
            with pytest.raises(ValueError, match="boom"):
                imp.run_with_setup([])

    def test_execute_calls_run_with_setup(self):
        """execute() delegates to run_with_setup() rather than duplicating its logic."""
        imp = ConcreteImporter()
        with patch("lifestream.importers.base.setup_logging"):
            with patch.object(
                imp, "run_with_setup", wraps=imp.run_with_setup
            ) as mock_run_with_setup:
                result = imp.execute([])
        mock_run_with_setup.assert_called_once_with([])
        assert result == 0


class ConcreteOAuthImporter(OAuthImporter):
    """Minimal concrete OAuth importer for testing."""

    name = "test_oauth_importer"

    def run(self):
        pass


class TestOAuthImporter:
    def _make_importer(self, path):
        imp = ConcreteOAuthImporter()
        imp.get_oauth_path = MagicMock(return_value=str(path))
        return imp

    def test_load_oauth_token_returns_none_when_file_missing(self, tmp_path):
        imp = self._make_importer(tmp_path / "missing.oauth")
        assert imp.load_oauth_token() is None

    def test_load_oauth_token_returns_none_on_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.oauth"
        path.write_bytes(b"not a valid pickle stream")
        imp = self._make_importer(path)
        assert imp.load_oauth_token() is None

    def test_save_and_load_oauth_token_round_trips(self, tmp_path):
        path = tmp_path / "token.oauth"
        imp = self._make_importer(path)
        imp.save_oauth_token({"access_token": "abc123"})
        assert imp.load_oauth_token() == {"access_token": "abc123"}

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
