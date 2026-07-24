"""
Job execution functions for Lifestream scheduler.

Handles running Python import modules and shell commands as scheduled jobs.
"""

import importlib
import logging
import subprocess
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


def run_import(job_name: str) -> None:
    """
    Run an import job by importing and executing its main() function.

    This supports both:
    - New-style importers in lifestream.importers (preferred)
    - Legacy importers in the imports/ directory (fallback)

    Args:
        job_name: The name of the importer to run (e.g., 'lastfm', 'flickr')

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

    try:
        # Try new-style importer — only catch ImportError from the import itself,
        # not from inside the importer's run() method
        importer_cls = _IMPORTERS.get(job_name)

        if importer_cls is not None:
            importer = importer_cls()
            # run_with_setup() shares BaseImporter.execute()'s setup/validation
            # logic but lets exceptions propagate to the except clauses below,
            # instead of execute()'s own exit-code mapping swallowing them.
            importer.run_with_setup(args=[])
            return

        # Fallback to legacy import style
        module = importlib.import_module(job_name)
        importlib.reload(module)  # Reload to ensure fresh state

        # Most import scripts have a main() function, some run at import time
        if hasattr(module, "main"):
            module.main()
        else:
            logger.warning(
                "Legacy module '%s' has no main() — ran at import time or did nothing",
                job_name,
            )

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Completed job: {job_name} in {duration:.1f}s")

    except SystemExit as e:
        # Legacy imports/*.py scripts signal failure via sys.exit(), which
        # raises SystemExit — a BaseException, not an Exception — so it would
        # otherwise skip the except Exception handler below entirely and
        # never trigger a failure notification.
        duration = (datetime.now() - start_time).total_seconds()
        code = e.code
        if code in (None, 0):
            logger.info(f"Completed job: {job_name} in {duration:.1f}s")
        else:
            logger.error(
                f"Job {job_name} exited via sys.exit({code!r}) after {duration:.1f}s"
            )
            send_failure_notifications(
                job_name, RuntimeError(f"sys.exit({code!r})"), duration
            )
        raise
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.exception(f"Job {job_name} failed after {duration:.1f}s")
        send_failure_notifications(job_name, e, duration)
        raise


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
