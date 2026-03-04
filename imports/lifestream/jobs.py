"""
Job execution functions for Lifestream scheduler.

Handles running Python import modules and shell commands as scheduled jobs.
"""

import importlib
import logging
import os
import subprocess
from datetime import datetime

from .notifications import send_failure_notifications

logger = logging.getLogger(__name__)

# Base directory is the project root (parent of imports/)
basedir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run_import(job_name: str) -> None:
    """
    Run an import job by importing and executing its main() function.
    
    This mimics what run_import.sh does but in-process.
    
    Args:
        job_name: The name of the module to import and run (e.g., 'lastfm', 'flickr')
    
    Raises:
        Exception: Re-raises any exception from the job after logging and notifying
    """
    logger.info(f"Starting job: {job_name}")
    start_time = datetime.now()
    
    try:
        # Import the module
        module = importlib.import_module(job_name)
        
        # Reload to ensure fresh state
        importlib.reload(module)
        
        # Most import scripts have a main() function, some run at import time
        if hasattr(module, "main"):
            module.main()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Completed job: {job_name} in {duration:.1f}s")
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Job {job_name} failed after {duration:.1f}s: {e}")
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
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=basedir,
            capture_output=True,
            text=True,
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if result.returncode != 0:
            error_msg = f"Command failed with exit code {result.returncode}: {result.stderr}"
            logger.error(f"Shell job {job_name} failed: {result.stderr}")
            send_failure_notifications(job_name, error_msg, duration)
            raise RuntimeError(error_msg)
        
        logger.info(f"Completed shell job: {job_name} in {duration:.1f}s")
        
    except RuntimeError:
        # Already handled above with notification
        raise
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Shell job {job_name} failed after {duration:.1f}s: {e}")
        send_failure_notifications(job_name, e, duration)
        raise
