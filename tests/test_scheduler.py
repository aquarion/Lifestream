"""Tests for the APScheduler-based scheduler.py job configuration/dispatch logic."""

from unittest.mock import MagicMock, patch

import scheduler


class TestParseJobOptions:
    def test_defaults_when_no_options(self):
        options = scheduler._parse_job_options("", "myjob")
        assert options == {
            "misfire_grace_time": scheduler.DEFAULT_MISFIRE_GRACE_TIME,
            "coalesce": scheduler.DEFAULT_COALESCE,
        }

    def test_parses_grace_and_coalesce(self):
        options = scheduler._parse_job_options("grace=7200 coalesce=false", "myjob")
        assert options["misfire_grace_time"] == 7200
        assert options["coalesce"] is False

    def test_coalesce_is_case_insensitive(self):
        options = scheduler._parse_job_options("coalesce=TRUE", "myjob")
        assert options["coalesce"] is True

    def test_invalid_grace_falls_back_to_default(self):
        """A malformed grace= value logs a warning and keeps the default, not raise."""
        options = scheduler._parse_job_options("grace=not-a-number", "myjob")
        assert options["misfire_grace_time"] == scheduler.DEFAULT_MISFIRE_GRACE_TIME

    def test_cmd_must_be_parsed_last_and_can_contain_spaces(self):
        options = scheduler._parse_job_options(
            "grace=100 cmd=echo hello world", "myjob"
        )
        assert options["command"] == "echo hello world"
        assert options["misfire_grace_time"] == 100

    def test_cmd_with_no_other_options(self):
        options = scheduler._parse_job_options("cmd=/bin/true", "myjob")
        assert options["command"] == "/bin/true"


class TestGetSchedules:
    def test_returns_empty_dict_when_no_schedules_section(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = False

        with patch.object(scheduler, "config", mock_config):
            assert scheduler.get_schedules() == {}

    def test_skips_comment_and_blank_lines(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("realjob", "*/15 * * * *"),
            ("commented", "; disabled for now"),
            ("hashed", "# also disabled"),
            ("blank", ""),
        ]

        with patch.object(scheduler, "config", mock_config):
            schedules = scheduler.get_schedules()

        assert list(schedules.keys()) == ["realjob"]

    def test_parses_cron_and_options(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("myjob", "*/15 * * * * | grace=1800 coalesce=false"),
        ]

        with patch.object(scheduler, "config", mock_config):
            schedules = scheduler.get_schedules()

        assert schedules["myjob"]["cron"] == "*/15 * * * *"
        assert schedules["myjob"]["misfire_grace_time"] == 1800
        assert schedules["myjob"]["coalesce"] is False

    def test_shell_job_captures_command(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("!my_shell_job", "0 3 * * * | cmd=echo hi"),
        ]

        with patch.object(scheduler, "config", mock_config):
            schedules = scheduler.get_schedules()

        assert schedules["!my_shell_job"]["command"] == "echo hi"


class TestAddJobs:
    def _mock_schedules(self, schedules):
        return patch.object(scheduler, "get_schedules", return_value=schedules)

    def test_import_job_dispatches_to_run_import(self):
        mock_scheduler = MagicMock()
        schedules = {
            "myimporter": {
                "cron": "*/15 * * * *",
                "misfire_grace_time": 3600,
                "coalesce": True,
            }
        }
        with self._mock_schedules(schedules):
            count = scheduler.add_jobs(mock_scheduler)

        assert count == 1
        _, kwargs = mock_scheduler.add_job.call_args
        assert mock_scheduler.add_job.call_args.args[0] is scheduler.run_import
        assert kwargs["args"] == ["myimporter"]
        assert kwargs["id"] == "myimporter"

    def test_shell_job_dispatches_to_run_shell_command(self):
        mock_scheduler = MagicMock()
        schedules = {
            "!backup": {
                "cron": "0 3 * * *",
                "misfire_grace_time": 3600,
                "coalesce": True,
                "command": "echo backup",
            }
        }
        with self._mock_schedules(schedules):
            scheduler.add_jobs(mock_scheduler)

        _, kwargs = mock_scheduler.add_job.call_args
        assert mock_scheduler.add_job.call_args.args[0] is scheduler.run_shell_command
        assert kwargs["args"] == ["backup", "echo backup"]
        assert kwargs["id"] == "backup"

    def test_shell_job_without_command_is_skipped(self):
        mock_scheduler = MagicMock()
        schedules = {
            "!backup": {
                "cron": "0 3 * * *",
                "misfire_grace_time": 3600,
                "coalesce": True,
            }
        }
        with self._mock_schedules(schedules):
            count = scheduler.add_jobs(mock_scheduler)

        assert count == 1
        mock_scheduler.add_job.assert_not_called()

    def test_invalid_cron_is_skipped(self):
        mock_scheduler = MagicMock()
        schedules = {
            "badjob": {
                "cron": "not a cron expression",
                "misfire_grace_time": 3600,
                "coalesce": True,
            }
        }
        with self._mock_schedules(schedules):
            scheduler.add_jobs(mock_scheduler)

        mock_scheduler.add_job.assert_not_called()


class TestRunJobNow:
    def test_runs_import_job(self):
        with patch.object(scheduler, "get_schedules", return_value={}):
            with patch.object(scheduler, "run_import") as mock_run_import:
                scheduler.run_job_now("myimporter")

        mock_run_import.assert_called_once_with("myimporter", extra_args=None)

    def test_forwards_extra_args_to_import_job(self):
        """Extra CLI args (e.g. --reauth) are forwarded through to run_import()."""
        with patch.object(scheduler, "get_schedules", return_value={}):
            with patch.object(scheduler, "run_import") as mock_run_import:
                scheduler.run_job_now("myimporter", extra_args=["--reauth"])

        mock_run_import.assert_called_once_with("myimporter", extra_args=["--reauth"])

    def test_runs_shell_job_with_configured_command(self):
        schedules = {"!backup": {"cron": "0 3 * * *", "command": "echo backup"}}
        with patch.object(scheduler, "get_schedules", return_value=schedules):
            with patch.object(scheduler, "run_shell_command") as mock_run_shell:
                scheduler.run_job_now("!backup")

        mock_run_shell.assert_called_once_with("backup", "echo backup")

    def test_ignores_extra_args_for_shell_job(self):
        """Shell jobs run a fixed cmd= from config; extra args are logged and dropped."""
        schedules = {"!backup": {"cron": "0 3 * * *", "command": "echo backup"}}
        with patch.object(scheduler, "get_schedules", return_value=schedules):
            with patch.object(scheduler, "run_shell_command") as mock_run_shell:
                scheduler.run_job_now("!backup", extra_args=["--reauth"])

        mock_run_shell.assert_called_once_with("backup", "echo backup")

    def test_shell_job_missing_command_exits(self):
        schedules = {"!backup": {"cron": "0 3 * * *"}}
        with patch.object(scheduler, "get_schedules", return_value=schedules):
            with patch.object(scheduler, "run_shell_command") as mock_run_shell:
                try:
                    scheduler.run_job_now("!backup")
                    assert False, "expected SystemExit"
                except SystemExit as e:
                    assert e.code == 1

        mock_run_shell.assert_not_called()
