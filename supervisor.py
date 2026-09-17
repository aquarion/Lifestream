#!/usr/bin/env python3
"""
Lifestream Supervisor - APScheduler-based job runner with Redis persistence.

This replaces the crontab-based scheduling with a single daemon that:
- Reads schedules from config.ini
- Persists job state in Redis (survives restarts)
- Coalesces missed runs (runs once on wake-up, not N times)
- Guards against concurrent runs of the same job within this process
  (APScheduler's max_instances=1) — this is an in-process, in-memory guard
  only. It does not provide cross-process or cross-host locking, so two
  separate supervisor daemons sharing the same Redis job store could still
  run the same job concurrently.

Usage:
    python supervisor.py              # Run supervisor daemon
    python supervisor.py --list       # List configured jobs
    python supervisor.py --run JOB    # Run a specific job immediately
    python supervisor.py --run JOB --help  # Show JOB's own importer-specific flags
    python supervisor.py --status     # Show job status and next run times

Extra args after `--run JOB` (e.g. `--reauth`) are forwarded straight to the
importer, so they're invisible to this top-level --help — use
`--run JOB --help` to see what JOB itself accepts.
"""

import argparse
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

import uvicorn
from apscheduler.executors.pool import ThreadPoolExecutor  # noqa: E402
from apscheduler.jobstores.redis import RedisJobStore  # noqa: E402
from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402

from lifestream.core.config import config, get_project_root  # noqa: E402
from lifestream.core.jobs import run_import, run_shell_command  # noqa: E402
from lifestream.core.webserver import create_app  # noqa: E402

logger = logging.getLogger("Supervisor")

# Default misfire grace time (1 hour) - jobs missed within this window will run once
DEFAULT_MISFIRE_GRACE_TIME = 3600

# Default coalesce setting - combine multiple missed runs into one
DEFAULT_COALESCE = True


def _parse_job_options(opts_str, job_name):
    """Parse key=value options from the pipe-separated part of a cron expression."""
    options = {
        "misfire_grace_time": DEFAULT_MISFIRE_GRACE_TIME,
        "coalesce": DEFAULT_COALESCE,
    }
    # cmd= must be last since its value may contain spaces
    if "cmd=" in opts_str:
        before_cmd, cmd_value = opts_str.split("cmd=", 1)
        options["command"] = cmd_value.strip()
        opts_str = before_cmd
    for opt in opts_str.split():
        if "=" not in opt:
            continue
        key, value = opt.split("=", 1)
        if key == "grace":
            try:
                options["misfire_grace_time"] = int(value)
            except ValueError:
                logger.warning(
                    f"Invalid grace time '{value}' for job {job_name}, "
                    f"using default {DEFAULT_MISFIRE_GRACE_TIME}s"
                )
        elif key == "coalesce":
            options["coalesce"] = value.lower() == "true"
    return options


@dataclass(frozen=True)
class ScheduleEntry:
    """
    A parsed, typed row from the `[schedules]` section of config.ini.

    `is_shell` (whether the job name had a `!` prefix, dispatched to
    `run_shell_command` rather than `run_import`) is computed once here
    instead of being re-derived from `name` at each of the three call
    sites that need it.
    """

    name: str
    cron: str
    is_shell: bool
    misfire_grace_time: int = DEFAULT_MISFIRE_GRACE_TIME
    coalesce: bool = DEFAULT_COALESCE
    command: str | None = None


def get_schedules() -> dict[str, ScheduleEntry]:
    """Read schedules from config.ini [schedules] section."""
    schedules: dict[str, ScheduleEntry] = {}

    if not config.has_section("schedules"):
        logger.warning("No [schedules] section found in config.ini")
        return schedules

    for job_name, cron_expr in config.items("schedules"):
        if not cron_expr or cron_expr.startswith(";") or cron_expr.startswith("#"):
            continue

        # Format: "*/15 * * * *" or "*/15 * * * * | grace=7200 coalesce=false"
        # Shell jobs: "*/15 * * * * | cmd=shell command here"  (cmd= must be last)
        parts = cron_expr.split("|")
        cron = parts[0].strip()
        options = (
            _parse_job_options(parts[1].strip(), job_name) if len(parts) > 1 else {}
        )

        is_shell = job_name.startswith("!")
        schedules[job_name] = ScheduleEntry(
            name=job_name[1:] if is_shell else job_name,
            cron=cron,
            is_shell=is_shell,
            misfire_grace_time=options.get(
                "misfire_grace_time", DEFAULT_MISFIRE_GRACE_TIME
            ),
            coalesce=options.get("coalesce", DEFAULT_COALESCE),
            command=options.get("command"),
        )

    return schedules


def create_scheduler():
    """Create and configure the APScheduler instance."""
    # Get Redis connection settings from config
    redis_host = config.get("redis", "host", fallback="localhost")
    redis_port = int(config.get("redis", "port", fallback=6379))
    redis_username = config.get("redis", "username", fallback=None)
    redis_password = config.get("redis", "password", fallback=None)

    jobstores = {
        "default": RedisJobStore(
            host=redis_host,
            port=redis_port,
            username=redis_username,
            password=redis_password,
            jobs_key="lifestream:scheduler:jobs",
            run_times_key="lifestream:scheduler:run_times",
        )
    }

    executors = {
        # Use threads, not processes - imports share config/logging
        "default": ThreadPoolExecutor(max_workers=3)
    }

    job_defaults = {
        "coalesce": DEFAULT_COALESCE,
        "max_instances": 1,  # Only one instance of each job at a time
        "misfire_grace_time": DEFAULT_MISFIRE_GRACE_TIME,
    }

    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )

    return scheduler


def add_jobs(scheduler):
    """Add all configured jobs to the scheduler."""
    schedules = get_schedules()

    for job_key, entry in schedules.items():
        try:
            trigger = CronTrigger.from_crontab(entry.cron)
        except ValueError as e:
            logger.error(f"Invalid cron expression for {job_key}: {entry.cron} - {e}")
            continue

        if entry.is_shell:
            if not entry.command:
                logger.error(f"Shell job '{entry.name}' has no cmd= option, skipping")
                continue
            scheduler.add_job(
                run_shell_command,
                trigger=trigger,
                args=[entry.name, entry.command],
                id=entry.name,
                name=entry.name,
                misfire_grace_time=entry.misfire_grace_time,
                coalesce=entry.coalesce,
                replace_existing=True,
            )
        else:
            scheduler.add_job(
                run_import,
                trigger=trigger,
                args=[entry.name],
                id=entry.name,
                name=entry.name,
                misfire_grace_time=entry.misfire_grace_time,
                coalesce=entry.coalesce,
                replace_existing=True,
            )

        logger.info(f"Scheduled job: {job_key} with cron '{entry.cron}'")

    return len(schedules)


def list_jobs():
    """List all configured jobs from config.ini."""
    schedules = get_schedules()

    if not schedules:
        print("No jobs configured in [schedules] section of config.ini")
        return

    print(f"{'Job Name':<25} {'Schedule':<20} {'Grace(s)':<10} {'Coalesce'}")
    print("-" * 70)

    for job_key, entry in sorted(schedules.items()):
        print(
            f"{job_key:<25} {entry.cron:<20} {entry.misfire_grace_time:<10} {entry.coalesce}"
        )


def show_status():
    """Show current job status and next run times."""
    scheduler = create_scheduler()

    jobs = scheduler.get_jobs()

    if not jobs:
        print("No jobs currently scheduled")
        scheduler.shutdown(wait=False)
        return

    print(f"{'Job Name':<25} {'Next Run':<25} {'Status'}")
    print("-" * 70)

    now = datetime.now()
    for job in sorted(jobs, key=lambda j: j.next_run_time or now):
        next_run = job.next_run_time
        if next_run:
            next_str = next_run.strftime("%Y-%m-%d %H:%M:%S")
            if next_run < now:
                status = "OVERDUE"
            else:
                status = "scheduled"
        else:
            next_str = "N/A"
            status = "paused"

        print(f"{job.name:<25} {next_str:<25} {status}")

    scheduler.shutdown(wait=False)


def run_job_now(job_name, extra_args=None):
    """
    Run a specific job immediately.

    Args:
        job_name: The job to run (as it appears in [schedules], including any
            leading '!' for shell jobs).
        extra_args: Extra CLI arguments to forward to the importer, e.g.
            ['--reauth']. Ignored for shell jobs, which take a fixed command
            from config rather than argparse-style flags.
    """
    schedules = get_schedules()
    entry = schedules.get(job_name)

    if entry is not None and entry.is_shell:
        if not entry.command:
            logger.error(
                f"Shell job '{entry.name}' not found in schedules or has no cmd= configured"
            )
            sys.exit(1)
        if extra_args:
            logger.warning(
                "Ignoring extra args %s for shell job '%s' (shell jobs run a fixed "
                "cmd= from config, not argparse flags)",
                extra_args,
                entry.name,
            )
        run_shell_command(entry.name, entry.command)
        return

    if job_name.startswith("!") and entry is None:
        logger.error(
            f"Shell job '{job_name[1:]}' not found in schedules or has no cmd= configured"
        )
        sys.exit(1)

    if job_name not in schedules:
        logger.info(f"Job {job_name} not in schedules, attempting direct run...")

    run_import(job_name, extra_args=extra_args)


def _print_job_help(job_name: str) -> None:
    """
    Print JOB's own --help instead of the supervisor's.

    `--run JOB` forwards unrecognized args straight to the importer (see
    main()), so those flags — e.g. OAuthImporter's --reauth — are invisible
    to `supervisor.py --help` and argparse's automatic -h/--help would
    otherwise just print the supervisor's own help before --run is even
    parsed. Dispatches to the importer's own argparse parser for new-style
    importers, or runs the legacy script with --help as a subprocess.
    """
    if job_name.startswith("!"):
        print(
            f"'{job_name}' is a shell job: it runs a fixed command from "
            "config.ini's [schedules] section and does not accept extra "
            "arguments."
        )
        return

    try:
        from lifestream.importers import IMPORTERS
    except ImportError:
        # Matches lifestream.core.jobs.run_import()'s own fallback: if the
        # new-style importer registry can't be imported, treat it as empty
        # rather than blowing up --run JOB --help for a legacy script.
        IMPORTERS = {}

    importer_cls = IMPORTERS.get(job_name)
    if importer_cls is not None:
        importer_cls().get_parser().print_help()
        return

    script_path = get_project_root() / "imports" / f"{job_name}.py"
    if script_path.exists():
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"], cwd=get_project_root()
        )
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    print(f"No importer found for job '{job_name}'", file=sys.stderr)
    sys.exit(1)


def build_app(scheduler):
    """Build the FastAPI app, wired to start/stop `scheduler` via the app's
    own lifespan — so uvicorn's signal handling drives both subsystems'
    startup/shutdown through one coordinated path instead of two competing
    signal handlers."""

    @asynccontextmanager
    async def lifespan(app):
        logger.info("Starting scheduler...")
        scheduler.start()
        try:
            yield
        finally:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=False)

    return create_app(lifespan=lifespan)


def _extract_run_target(argv: list[str]) -> str | None:
    """Return the JOB value passed to --run in argv, or None if not given.

    Delegates to a bare argparse parser (no -h) instead of hand-parsing argv,
    so it accepts exactly what the real parser below accepts for --run
    (`--run JOB`, `--run=JOB`, unambiguous prefixes) rather than a second,
    narrower reimplementation of that same flag.
    """
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--run")
    known, _ = pre_parser.parse_known_args(argv)
    return known.run


def main():
    argv = sys.argv[1:]

    # `--run JOB --help` should show JOB's own --help, not the supervisor's —
    # argparse's automatic -h/--help action would otherwise intercept it
    # before --run's value is even parsed. Handled ahead of the parser below.
    if "--help" in argv or "-h" in argv:
        run_target = _extract_run_target(argv)
        if run_target is not None:
            _print_job_help(run_target)
            return

    parser = argparse.ArgumentParser(
        description="Lifestream Supervisor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--list", action="store_true", help="List configured jobs")
    parser.add_argument("--status", action="store_true", help="Show job status")
    parser.add_argument("--run", metavar="JOB", help="Run a specific job immediately")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    # Unrecognized args are forwarded to the importer when used with --run,
    # e.g. `supervisor.py --run facebook_posts --reauth`.
    args, extra_args = parser.parse_known_args()

    from lifestream.core.logging import setup_logging

    setup_logging(debug=args.debug, verbose=args.debug)

    if args.debug:
        logging.getLogger("apscheduler").setLevel(logging.DEBUG)

    if args.list:
        list_jobs()
        return

    if args.status:
        show_status()
        return

    if args.run:
        run_job_now(args.run, extra_args=extra_args)
        return

    # Default: run the supervisor (scheduler + webserver)
    logger.info("Starting Lifestream Supervisor...")

    scheduler = create_scheduler()
    job_count = add_jobs(scheduler)

    if job_count == 0:
        logger.warning(
            "No jobs configured in [schedules] — starting the webserver anyway "
            "so the OAuth catcher is available for initial setup."
        )

    logger.info(f"Supervisor configured with {job_count} jobs")

    app = build_app(scheduler)
    host = config.get("webserver", "host", fallback="0.0.0.0")
    port = int(config.get("webserver", "port", fallback=8000))

    try:
        logger.info(f"Starting webserver on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Supervisor failed to start: {e}")
        logger.error(
            "Check that the [webserver] host/port are valid and free, and that "
            "Redis is running and reachable (see [redis] in config.ini)"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
