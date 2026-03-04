"""Tests for lifestream.core.jobs module."""

from unittest.mock import MagicMock, patch

import pytest
from lifestream.core import jobs


class TestRunImport:
    """Tests for run_import function."""

    def test_run_import_calls_main_if_exists(self):
        """Test run_import calls module's main() function."""
        mock_module = MagicMock()
        mock_module.main = MagicMock()

        with patch.object(jobs.importlib, "import_module", return_value=mock_module):
            with patch.object(jobs.importlib, "reload", return_value=mock_module):
                with patch.object(jobs, "send_failure_notifications"):
                    jobs.run_import("test_module")
                    mock_module.main.assert_called_once()

    def test_run_import_skips_main_if_not_exists(self):
        """Test run_import works for modules without main()."""
        mock_module = MagicMock(spec=[])  # No main attribute

        with patch.object(jobs.importlib, "import_module", return_value=mock_module):
            with patch.object(jobs.importlib, "reload", return_value=mock_module):
                with patch.object(jobs, "send_failure_notifications"):
                    # Should not raise
                    jobs.run_import("test_module")

    def test_run_import_sends_notification_on_failure(self):
        """Test run_import sends notification when job fails."""
        mock_module = MagicMock()
        mock_module.main.side_effect = Exception("Job failed!")

        with patch.object(jobs.importlib, "import_module", return_value=mock_module):
            with patch.object(jobs.importlib, "reload", return_value=mock_module):
                with patch.object(jobs, "send_failure_notifications") as mock_notify:
                    with pytest.raises(Exception, match="Job failed!"):
                        jobs.run_import("test_module")

                    mock_notify.assert_called_once()
                    call_args = mock_notify.call_args[0]
                    assert call_args[0] == "test_module"

    def test_run_import_reloads_module(self):
        """Test run_import reloads module for fresh state."""
        mock_module = MagicMock()

        with patch.object(jobs.importlib, "import_module", return_value=mock_module):
            with patch.object(
                jobs.importlib, "reload", return_value=mock_module
            ) as mock_reload:
                with patch.object(jobs, "send_failure_notifications"):
                    jobs.run_import("test_module")
                    mock_reload.assert_called_once_with(mock_module)


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
