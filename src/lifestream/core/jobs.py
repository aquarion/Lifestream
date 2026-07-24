"""
Job execution functions for Lifestream scheduler.

Handles running Python import modules and shell commands as scheduled jobs.
"""

import logging
import subprocess
import sys
from datetime import datetime

from lifestream.core.config import get_project_root
from lifestream.core.notifications import send_failure_notifications

logger = logging.getLogger(__name__)

_IMPORTERS: dict = {}
_IMPORTERS_IMPORT_ERROR: ImportError | None = None
try:
    from lifestream.importers import IMPORTERS as _IMPORTERS
except ImportError as _import_err:
    _IMPORTERS_IMPORT_ERROR = _import_err


def run_import(job_name: str, extra_args: list[str] | None = None) -> None:
    """
    Run an import job.

    This supports both:
    - New-style importers in lifestream.importers (preferred): run in-process.
    - Legacy importers in the imports/ directory (fallback): run as a subprocess.

    Legacy scripts run out-of-process (rather than via importlib.reload() in the
    scheduler's own process) because several of them mutate module-level global
    state (e.g. a shared argparse.ArgumentParser in lifestream_legacy.arguments)
    at import time. That's safe for a fresh `python imports/x.py` process per run
    (how they always ran under crontab), but reload()ing the same long-lived
    process repeatedly re-runs that top-level code against state left over from
    the previous run and raises on the second invocation (e.g. "argument --site:
    conflicting option string"). Subprocess isolation sidesteps this, and any
    other import-time global-state footgun these scripts might have, without
    requiring each one to be individually audited/fixed.

    Args:
        job_name: The name of the importer to run (e.g., 'lastfm', 'flickr')
        extra_args: Extra CLI arguments to pass to the importer, e.g.
            ['--reauth']. Only meaningful for manual/`--run` invocations —
            scheduled cron runs never pass any.

    Raises:
        Exception: Re-raises any exception from the job after logging and notifying
    """
    if _IMPORTERS_IMPORT_ERROR is not None:
        logger.warning(
            "Failed to import lifestream.importers (legacy fallback only): %s",
            _IMPORTERS_IMPORT_ERROR,
        )

    logger.info(f"Starting job: {job_name}")
    start_time = datetime.now()

    # Try new-style importer — only catch ImportError from the import itself,
    # not from inside the importer's run() method
    importer_cls = _IMPORTERS.get(job_name)

    if importer_cls is not None:
        try:
            importer = importer_cls()
            # run_with_setup() shares BaseImporter.execute()'s setup/validation
            # logic but lets exceptions propagate to the except clauses below,
            # instead of execute()'s own exit-code mapping swallowing them.
            importer.run_with_setup(args=extra_args or [])
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.exception(f"Job {job_name} failed after {duration:.1f}s")
            send_failure_notifications(job_name, e, duration)
            raise
        return

    _run_legacy_import(job_name, start_time, extra_args)


def _run_legacy_import(
    job_name: str, start_time: datetime, extra_args: list[str] | None = None
) -> None:
    """Run a legacy imports/<job_name>.py script as its own subprocess."""
    script_path = get_project_root() / "imports" / f"{job_name}.py"
    if not script_path.exists():
        duration = (datetime.now() - start_time).total_seconds()
        error = RuntimeError(f"No importer found for job '{job_name}'")
        logger.error(str(error))
        send_failure_notifications(job_name, error, duration)
        raise error

    cmd = [sys.executable, str(script_path)]
    # Legacy scripts (imports/lifestream_legacy) decide their own log level by
    # checking "--debug"/"--verbose" in their own sys.argv. A subprocess starts
    # with none of that, so without forwarding it explicitly, a legacy job's
    # own logging silently stays at WARNING regardless of how the scheduler
    # itself was invoked.
    if "--debug" in sys.argv:
        cmd.append("--debug")
    elif "--verbose" in sys.argv:
        cmd.append("--verbose")
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        cwd=get_project_root(),
        capture_output=True,
        text=True,
        timeout=3600,
    )

    duration = (datetime.now() - start_time).total_seconds()

    if result.returncode != 0:
        error_msg = (
            f"Legacy script {job_name}.py exited with code {result.returncode}: "
            f"{result.stderr[-2000:]}"
        )
        logger.error(f"Job {job_name} failed after {duration:.1f}s: {result.stderr}")
        send_failure_notifications(job_name, RuntimeError(error_msg), duration)
        raise RuntimeError(error_msg)

    if result.stdout:
        logger.debug("[%s stdout]\n%s", job_name, result.stdout)
    if result.stderr:
        logger.debug("[%s stderr]\n%s", job_name, result.stderr)

    logger.info(f"Completed job: {job_name} in {duration:.1f}s")


def run_shell_command(job_name: str, command: str) -> None:
    """
    Run a shell command as a scheduled job.

    Used for special jobs that need to run external scripts
    (e.g., ffxiv_update_achievements).

    Args:
        job_name: A descriptive name for the job (for logging)
        command: The shell command to execute

    Raises:
        RuntimeError: If the command exits with non-zero status
        Exception: Re-raises any other exception after logging and notifying
    """
    logger.info(f"Starting shell job: {job_name}")
    start_time = datetime.now()
    basedir = get_project_root()

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=basedir,
            capture_output=True,
            text=True,
            timeout=3600,
        )

        duration = (datetime.now() - start_time).total_seconds()

        if result.returncode != 0:
            error_msg = (
                f"Command failed with exit code {result.returncode}: {result.stderr}"
            )
            logger.error(f"Shell job {job_name} failed: {result.stderr}")
            send_failure_notifications(job_name, error_msg, duration)
            raise RuntimeError(error_msg)

        logger.info(f"Completed shell job: {job_name} in {duration:.1f}s")

    except RuntimeError:
        # Already handled above with notification
        raise
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.exception(f"Shell job {job_name} failed after {duration:.1f}s")
        send_failure_notifications(job_name, e, duration)
        raise
