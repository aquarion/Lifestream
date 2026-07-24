"""Tests for lifestream.core.jobs module."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream import jobs
from lifestream.importers.base import ConfigurationError


class TestRunImportLegacy:
    """Tests for run_import's legacy imports/<job>.py subprocess fallback.

    Legacy scripts run as their own subprocess (rather than importlib.reload()
    in-process) because several of them mutate module-level global state (e.g.
    a shared argparse.ArgumentParser) at import time, which breaks on a second
    reload within the same long-lived scheduler process. See jobs.py's
    run_import() docstring.
    """

    def _make_script(self, tmp_path, name="test_module"):
        imports_dir = tmp_path / "imports"
        imports_dir.mkdir(exist_ok=True)
        script = imports_dir / f"{name}.py"
        script.write_text("# stub legacy script")
        return script

    def test_runs_legacy_script_as_subprocess(self, tmp_path):
        """run_import invokes `python imports/<job>.py` as a subprocess."""
        script = self._make_script(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(jobs, "get_project_root", return_value=tmp_path):
            with patch.object(
                jobs.subprocess, "run", return_value=mock_result
            ) as mock_run:
                with patch.object(jobs, "send_failure_notifications"):
                    jobs.run_import("test_module")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args.args[0] == [jobs.sys.executable, str(script)]
        assert call_args.kwargs["cwd"] == tmp_path

    def test_does_not_run_legacy_if_new_style_found(self, tmp_path):
        """run_import uses new-style importer and skips the legacy subprocess path."""
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        with patch("lifestream.core.jobs._IMPORTERS", {"myimporter": mock_cls}):
            with patch.object(jobs.subprocess, "run") as mock_run:
                with patch.object(jobs, "send_failure_notifications"):
                    jobs.run_import("myimporter")

        mock_run.assert_not_called()

    def test_raises_and_notifies_on_nonzero_exit(self, tmp_path):
        """A legacy script exiting non-zero notifies and raises RuntimeError."""
        self._make_script(tmp_path)
        mock_result = MagicMock(returncode=1, stdout="", stderr="boom")

        with patch.object(jobs, "get_project_root", return_value=tmp_path):
            with patch.object(jobs.subprocess, "run", return_value=mock_result):
                with patch.object(jobs, "send_failure_notifications") as mock_notify:
                    with pytest.raises(RuntimeError, match="exited with code 1"):
                        jobs.run_import("test_module")

        mock_notify.assert_called_once()
        assert mock_notify.call_args[0][0] == "test_module"

    def test_raises_when_no_script_or_new_style_importer_found(self, tmp_path):
        """An unknown job name (no registry entry, no imports/<job>.py) raises clearly."""
        (tmp_path / "imports").mkdir()

        with patch.object(jobs, "get_project_root", return_value=tmp_path):
            with patch.object(jobs, "send_failure_notifications") as mock_notify:
                with pytest.raises(RuntimeError, match="No importer found"):
                    jobs.run_import("does_not_exist")

        mock_notify.assert_called_once()

    def test_repeated_runs_do_not_share_process_state(self, tmp_path):
        """Regression: each run is a fresh subprocess, so running the same
        legacy job twice in a row succeeds both times (it would previously
        crash on the second run via importlib.reload() due to shared
        module-level state, e.g. atproto_posts.py's argparse parser)."""
        self._make_script(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(jobs, "get_project_root", return_value=tmp_path):
            with patch.object(
                jobs.subprocess, "run", return_value=mock_result
            ) as mock_run:
                with patch.object(jobs, "send_failure_notifications"):
                    jobs.run_import("test_module")
                    jobs.run_import("test_module")

        assert mock_run.call_count == 2


class TestRunImportNewStyle:
    """Tests for run_import using new-style IMPORTERS registry.

    run_with_setup() itself (parse_args/logging/no-db/validate_config/run) is
    exercised in tests/test_base_importer.py; these tests only verify that
    run_import() calls it and reacts correctly to what it raises.
    """

    def test_new_style_importer_run_with_setup_called(self):
        """run_import calls importer.run_with_setup() for registered new-style importers."""
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        with patch("lifestream.core.jobs._IMPORTERS", {"myimporter": mock_cls}):
            with patch.object(jobs, "send_failure_notifications"):
                jobs.run_import("myimporter")

        mock_instance.run_with_setup.assert_called_once_with(args=[])
        mock_cls.assert_called_once_with()

    def test_new_style_importer_config_error_raises(self):
        """run_import re-raises ConfigurationError from run_with_setup() after notifying."""
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.run_with_setup.side_effect = ConfigurationError(
            "Config validation failed for myimporter"
        )

        with patch("lifestream.core.jobs._IMPORTERS", {"myimporter": mock_cls}):
            with patch.object(jobs, "send_failure_notifications") as mock_notify:
                with pytest.raises(
                    ConfigurationError, match="Config validation failed"
                ):
                    jobs.run_import("myimporter")

            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            assert args[0] == "myimporter"

        mock_cls.assert_called_once_with()

    def test_new_style_importer_exception_propagates(self):
        """run_import re-raises from importer.run_with_setup() after notifying."""
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.run_with_setup.side_effect = ValueError("API error")

        with patch("lifestream.core.jobs._IMPORTERS", {"myimporter": mock_cls}):
            with patch.object(jobs, "send_failure_notifications") as mock_notify:
                with pytest.raises(ValueError, match="API error"):
                    jobs.run_import("myimporter")

            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            assert args[0] == "myimporter"

        mock_cls.assert_called_once_with()


class TestRunShellCommand:
    """Tests for run_shell_command function."""

    def test_run_shell_command_executes_command(self):
        """Test run_shell_command executes the given command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""

        with patch.object(jobs.subprocess, "run", return_value=mock_result) as mock_run:
            with patch.object(jobs, "send_failure_notifications"):
                jobs.run_shell_command("test_job", "echo hello")

                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert call_args[0][0] == "echo hello"
                assert call_args[1]["shell"] is True

    def test_run_shell_command_raises_on_nonzero_exit(self):
        """Test run_shell_command raises RuntimeError on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "command failed"

        with patch.object(jobs.subprocess, "run", return_value=mock_result):
            with patch.object(jobs, "send_failure_notifications") as mock_notify:
                with pytest.raises(RuntimeError, match="exit code 1"):
                    jobs.run_shell_command("test_job", "false")

                mock_notify.assert_called_once()

    def test_run_shell_command_handles_subprocess_exception(self):
        """Test run_shell_command handles subprocess exceptions."""
        with patch.object(jobs.subprocess, "run", side_effect=OSError("spawn failed")):
            with patch.object(jobs, "send_failure_notifications") as mock_notify:
                with pytest.raises(OSError, match="spawn failed"):
                    jobs.run_shell_command("test_job", "some_command")

                mock_notify.assert_called_once()
