"""Tests for the APScheduler-based supervisor.py job configuration/dispatch logic."""

import sys
from unittest.mock import MagicMock, patch

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.testclient import TestClient

import supervisor


class TestParseJobOptions:
    def test_defaults_when_no_options(self):
        options = supervisor._parse_job_options("", "myjob")
        assert options == {
            "misfire_grace_time": supervisor.DEFAULT_MISFIRE_GRACE_TIME,
            "coalesce": supervisor.DEFAULT_COALESCE,
        }

    def test_parses_grace_and_coalesce(self):
        options = supervisor._parse_job_options("grace=7200 coalesce=false", "myjob")
        assert options["misfire_grace_time"] == 7200
        assert options["coalesce"] is False

    def test_coalesce_is_case_insensitive(self):
        options = supervisor._parse_job_options("coalesce=TRUE", "myjob")
        assert options["coalesce"] is True

    def test_invalid_grace_falls_back_to_default(self):
        """A malformed grace= value logs a warning and keeps the default, not raise."""
        options = supervisor._parse_job_options("grace=not-a-number", "myjob")
        assert options["misfire_grace_time"] == supervisor.DEFAULT_MISFIRE_GRACE_TIME

    def test_cmd_must_be_parsed_last_and_can_contain_spaces(self):
        options = supervisor._parse_job_options(
            "grace=100 cmd=echo hello world", "myjob"
        )
        assert options["command"] == "echo hello world"
        assert options["misfire_grace_time"] == 100

    def test_cmd_with_no_other_options(self):
        options = supervisor._parse_job_options("cmd=/bin/true", "myjob")
        assert options["command"] == "/bin/true"


class TestGetSchedules:
    def test_returns_empty_dict_when_no_schedules_section(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = False

        with patch.object(supervisor, "config", mock_config):
            assert supervisor.get_schedules() == {}

    def test_skips_comment_and_blank_lines(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("realjob", "*/15 * * * *"),
            ("commented", "; disabled for now"),
            ("hashed", "# also disabled"),
            ("blank", ""),
        ]

        with patch.object(supervisor, "config", mock_config):
            schedules = supervisor.get_schedules()

        assert list(schedules.keys()) == ["realjob"]

    def test_parses_cron_and_options(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("myjob", "*/15 * * * * | grace=1800 coalesce=false"),
        ]

        with patch.object(supervisor, "config", mock_config):
            schedules = supervisor.get_schedules()

        assert schedules["myjob"].cron == "*/15 * * * *"
        assert schedules["myjob"].misfire_grace_time == 1800
        assert schedules["myjob"].coalesce is False
        assert schedules["myjob"].is_shell is False

    def test_shell_job_captures_command(self):
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.items.return_value = [
            ("!my_shell_job", "0 3 * * * | cmd=echo hi"),
        ]

        with patch.object(supervisor, "config", mock_config):
            schedules = supervisor.get_schedules()

        entry = schedules["!my_shell_job"]
        assert entry.command == "echo hi"
        assert entry.is_shell is True
        assert entry.name == "my_shell_job"


class TestAddJobs:
    def _mock_schedules(self, schedules):
        return patch.object(supervisor, "get_schedules", return_value=schedules)

    def test_import_job_dispatches_to_run_import(self):
        mock_scheduler = MagicMock()
        schedules = {
            "myimporter": supervisor.ScheduleEntry(
                name="myimporter",
                cron="*/15 * * * *",
                is_shell=False,
                misfire_grace_time=3600,
                coalesce=True,
            )
        }
        with self._mock_schedules(schedules):
            count = supervisor.add_jobs(mock_scheduler)

        assert count == 1
        _, kwargs = mock_scheduler.add_job.call_args
        assert mock_scheduler.add_job.call_args.args[0] is supervisor.run_import
        assert kwargs["args"] == ["myimporter"]
        assert kwargs["id"] == "myimporter"

    def test_shell_job_dispatches_to_run_shell_command(self):
        mock_scheduler = MagicMock()
        schedules = {
            "!backup": supervisor.ScheduleEntry(
                name="backup",
                cron="0 3 * * *",
                is_shell=True,
                misfire_grace_time=3600,
                coalesce=True,
                command="echo backup",
            )
        }
        with self._mock_schedules(schedules):
            supervisor.add_jobs(mock_scheduler)

        _, kwargs = mock_scheduler.add_job.call_args
        assert mock_scheduler.add_job.call_args.args[0] is supervisor.run_shell_command
        assert kwargs["args"] == ["backup", "echo backup"]
        assert kwargs["id"] == "backup"

    def test_shell_job_without_command_is_skipped(self):
        mock_scheduler = MagicMock()
        schedules = {
            "!backup": supervisor.ScheduleEntry(
                name="backup",
                cron="0 3 * * *",
                is_shell=True,
                misfire_grace_time=3600,
                coalesce=True,
            )
        }
        with self._mock_schedules(schedules):
            count = supervisor.add_jobs(mock_scheduler)

        assert count == 1
        mock_scheduler.add_job.assert_not_called()

    def test_invalid_cron_is_skipped(self):
        mock_scheduler = MagicMock()
        schedules = {
            "badjob": supervisor.ScheduleEntry(
                name="badjob",
                cron="not a cron expression",
                is_shell=False,
                misfire_grace_time=3600,
                coalesce=True,
            )
        }
        with self._mock_schedules(schedules):
            supervisor.add_jobs(mock_scheduler)

        mock_scheduler.add_job.assert_not_called()


class TestRunJobNow:
    def test_runs_import_job(self):
        with patch.object(supervisor, "get_schedules", return_value={}):
            with patch.object(supervisor, "run_import") as mock_run_import:
                supervisor.run_job_now("myimporter")

        mock_run_import.assert_called_once_with("myimporter", extra_args=None)

    def test_forwards_extra_args_to_import_job(self):
        """Extra CLI args (e.g. --reauth) are forwarded through to run_import()."""
        with patch.object(supervisor, "get_schedules", return_value={}):
            with patch.object(supervisor, "run_import") as mock_run_import:
                supervisor.run_job_now("myimporter", extra_args=["--reauth"])

        mock_run_import.assert_called_once_with("myimporter", extra_args=["--reauth"])

    def test_runs_shell_job_with_configured_command(self):
        schedules = {
            "!backup": supervisor.ScheduleEntry(
                name="backup", cron="0 3 * * *", is_shell=True, command="echo backup"
            )
        }
        with patch.object(supervisor, "get_schedules", return_value=schedules):
            with patch.object(supervisor, "run_shell_command") as mock_run_shell:
                supervisor.run_job_now("!backup")

        mock_run_shell.assert_called_once_with("backup", "echo backup")

    def test_ignores_extra_args_for_shell_job(self):
        """Shell jobs run a fixed cmd= from config; extra args are logged and dropped."""
        schedules = {
            "!backup": supervisor.ScheduleEntry(
                name="backup", cron="0 3 * * *", is_shell=True, command="echo backup"
            )
        }
        with patch.object(supervisor, "get_schedules", return_value=schedules):
            with patch.object(supervisor, "run_shell_command") as mock_run_shell:
                supervisor.run_job_now("!backup", extra_args=["--reauth"])

        mock_run_shell.assert_called_once_with("backup", "echo backup")

    def test_shell_job_missing_command_exits(self):
        schedules = {
            "!backup": supervisor.ScheduleEntry(
                name="backup", cron="0 3 * * *", is_shell=True
            )
        }
        with patch.object(supervisor, "get_schedules", return_value=schedules):
            with patch.object(supervisor, "run_shell_command") as mock_run_shell:
                try:
                    supervisor.run_job_now("!backup")
                    assert False, "expected SystemExit"
                except SystemExit as e:
                    assert e.code == 1

        mock_run_shell.assert_not_called()


class TestCreateScheduler:
    def test_returns_a_background_scheduler(self):
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda section, key, fallback=None: fallback
        with patch.object(supervisor, "config", mock_config):
            sched = supervisor.create_scheduler()

        assert isinstance(sched, BackgroundScheduler)


class TestBuildApp:
    def test_lifespan_starts_and_stops_scheduler(self):
        mock_scheduler = MagicMock()

        app = supervisor.build_app(mock_scheduler)

        with TestClient(app):
            mock_scheduler.start.assert_called_once()
            mock_scheduler.shutdown.assert_not_called()

        mock_scheduler.shutdown.assert_called_once_with(wait=False)


class TestPrintJobHelp:
    def test_new_style_importer_prints_its_own_parser_help(self, capsys):
        """--run JOB --help for a new-style importer shows *its* flags (e.g. --reauth)."""
        mock_importer = MagicMock()
        with patch.dict(
            "lifestream.importers.IMPORTERS", {"myimporter": mock_importer}
        ):
            supervisor._print_job_help("myimporter")

        mock_importer.return_value.get_parser.return_value.print_help.assert_called_once()

    def test_legacy_script_runs_as_subprocess_with_help(self, tmp_path):
        (tmp_path / "imports").mkdir()
        (tmp_path / "imports" / "legacy_job.py").write_text("")

        with patch.dict("lifestream.importers.IMPORTERS", {}, clear=False):
            with patch.object(supervisor, "get_project_root", return_value=tmp_path):
                with patch.object(supervisor.subprocess, "run") as mock_run:
                    mock_run.return_value.returncode = 0
                    supervisor._print_job_help("legacy_job")

        mock_run.assert_called_once()
        assert "--help" in mock_run.call_args.args[0]

    def test_unknown_job_errors_and_exits(self, tmp_path):
        (tmp_path / "imports").mkdir()

        with patch.dict("lifestream.importers.IMPORTERS", {}, clear=False):
            with patch.object(supervisor, "get_project_root", return_value=tmp_path):
                try:
                    supervisor._print_job_help("nope")
                    assert False, "expected SystemExit"
                except SystemExit as e:
                    assert e.code == 1

    def test_shell_job_prints_explanation_without_touching_importers(self, capsys):
        supervisor._print_job_help("!backup")

        captured = capsys.readouterr()
        assert "shell job" in captured.out

    def test_falls_back_to_legacy_when_importers_registry_fails_to_import(
        self, tmp_path
    ):
        """Mirrors run_import()'s own ImportError fallback: a broken new-style
        importer registry shouldn't stop --run JOB --help for a legacy script."""
        (tmp_path / "imports").mkdir()
        (tmp_path / "imports" / "legacy_job.py").write_text("")

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "lifestream.importers":
                raise ImportError("boom")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with patch.object(supervisor, "get_project_root", return_value=tmp_path):
                with patch.object(supervisor.subprocess, "run") as mock_run:
                    mock_run.return_value.returncode = 0
                    supervisor._print_job_help("legacy_job")

        mock_run.assert_called_once()

    def test_legacy_script_failure_propagates_exit_code(self, tmp_path):
        (tmp_path / "imports").mkdir()
        (tmp_path / "imports" / "legacy_job.py").write_text("")

        with patch.dict("lifestream.importers.IMPORTERS", {}, clear=False):
            with patch.object(supervisor, "get_project_root", return_value=tmp_path):
                with patch.object(supervisor.subprocess, "run") as mock_run:
                    mock_run.return_value.returncode = 2
                    try:
                        supervisor._print_job_help("legacy_job")
                        assert False, "expected SystemExit"
                    except SystemExit as e:
                        assert e.code == 2


class TestExtractRunTarget:
    def test_space_separated_form(self):
        assert supervisor._extract_run_target(["--run", "lastfm", "--help"]) == "lastfm"

    def test_equals_form(self):
        assert supervisor._extract_run_target(["--run=lastfm", "--help"]) == "lastfm"

    def test_missing_value_after_run_errors_like_the_real_parser(self):
        """--run with no value is invalid usage; argparse exits(2) here just
        as it would when the real parser below hits the same argv."""
        try:
            supervisor._extract_run_target(["--run"])
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 2

    def test_no_run_flag(self):
        assert supervisor._extract_run_target(["--list"]) is None


class TestMainHelpRouting:
    """argv-driven coverage of main()'s pre-parser dispatch, not just its
    pieces (_extract_run_target/_print_job_help) in isolation."""

    def test_run_job_help_dispatches_before_argparse(self):
        with patch.object(sys, "argv", ["supervisor.py", "--run", "lastfm", "--help"]):
            with patch.object(supervisor, "_print_job_help") as mock_help:
                supervisor.main()

        mock_help.assert_called_once_with("lastfm")

    def test_run_equals_job_help_dispatches_before_argparse(self):
        with patch.object(sys, "argv", ["supervisor.py", "--run=lastfm", "--help"]):
            with patch.object(supervisor, "_print_job_help") as mock_help:
                supervisor.main()

        mock_help.assert_called_once_with("lastfm")

    def test_plain_help_falls_through_to_the_top_level_parser(self):
        """--help with no --run shows the supervisor's own help, unaffected.

        Asserts exit code 0 (argparse's -h action), not just "some
        SystemExit" — a regression that made this a usage error (exit 2)
        should fail this test too.
        """
        with patch.object(sys, "argv", ["supervisor.py", "--help"]):
            with patch.object(supervisor, "_print_job_help") as mock_help:
                try:
                    supervisor.main()
                    assert False, "expected SystemExit from argparse's -h action"
                except SystemExit as e:
                    assert e.code == 0

        mock_help.assert_not_called()
