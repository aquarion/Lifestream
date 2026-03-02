#!/usr/bin/env python3
"""
Lifestream Scheduler - APScheduler-based job runner with Redis persistence.

This replaces the crontab-based scheduling with a single daemon that:
- Reads schedules from config.ini
- Persists job state in Redis (survives restarts)
- Coalesces missed runs (runs once on wake-up, not N times)
- Handles locking per-job

Usage:
    python scheduler.py              # Run scheduler daemon
    python scheduler.py --list       # List configured jobs
    python scheduler.py --run JOB    # Run a specific job immediately
    python scheduler.py --status     # Show job status and next run times
"""

import argparse
import configparser
import importlib
import logging
import os
import signal
import sys
from datetime import datetime

# Parse arguments BEFORE importing lifestream (which has its own argparse setup)
parser = argparse.ArgumentParser(
    description="Lifestream Scheduler",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=__doc__,
)
parser.add_argument("--list", action="store_true", help="List configured jobs")
parser.add_argument("--status", action="store_true", help="Show job status")
parser.add_argument("--run", metavar="JOB", help="Run a specific job immediately")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
SCHEDULER_ARGS, remaining_args = parser.parse_known_args()

# Replace sys.argv with remaining args so lifestream's argparse doesn't break
sys.argv = [sys.argv[0]] + remaining_args

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Set up path for imports - lifestream expects to run from imports/ directory
basedir = os.path.dirname(os.path.abspath(__file__))
imports_dir = os.path.join(basedir, "imports")
os.chdir(imports_dir)  # Change to imports/ so lifestream finds config correctly
sys.path.insert(0, imports_dir)

import lifestream
from lifestream.cache import get_redis_connection

logger = logging.getLogger("Scheduler")

# Default misfire grace time (1 hour) - jobs missed within this window will run once
DEFAULT_MISFIRE_GRACE_TIME = 3600

# Default coalesce setting - combine multiple missed runs into one
DEFAULT_COALESCE = True


def get_schedules():
    """Read schedules from config.ini [schedules] section."""
    schedules = {}
    
    if not lifestream.config.has_section("schedules"):
        logger.warning("No [schedules] section found in config.ini")
        return schedules
    
    for job_name, cron_expr in lifestream.config.items("schedules"):
        # Skip disabled jobs (commented with ; or #, or empty value)
        if not cron_expr or cron_expr.startswith(";") or cron_expr.startswith("#"):
            continue
        
        # Parse options from cron expression
        # Format: "*/15 * * * *" or "*/15 * * * * | grace=7200 coalesce=false"
        parts = cron_expr.split("|")
        cron = parts[0].strip()
        
        options = {
            "misfire_grace_time": DEFAULT_MISFIRE_GRACE_TIME,
            "coalesce": DEFAULT_COALESCE,
        }
        
        if len(parts) > 1:
            for opt in parts[1].split():
                if "=" in opt:
                    key, value = opt.split("=", 1)
                    if key == "grace":
                        options["misfire_grace_time"] = int(value)
                    elif key == "coalesce":
                        options["coalesce"] = value.lower() == "true"
        
        schedules[job_name] = {"cron": cron, **options}
    
    return schedules


def run_import(job_name):
    """
    Run an import job by importing and executing its main() function.
    
    This mimics what run_import.sh does but in-process.
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
        raise


def run_shell_command(job_name, command):
    """Run a shell command (for special jobs like ffxiv_update_achievements)."""
    import subprocess
    
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
            logger.error(f"Shell job {job_name} failed: {result.stderr}")
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
        
        logger.info(f"Completed shell job: {job_name} in {duration:.1f}s")
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Shell job {job_name} failed after {duration:.1f}s: {e}")
        raise


def create_scheduler():
    """Create and configure the APScheduler instance."""
    # Get Redis connection settings from config
    redis_host = lifestream.config.get("redis", "host", fallback="localhost")
    redis_port = int(lifestream.config.get("redis", "port", fallback=6379))
    redis_username = lifestream.config.get("redis", "username", fallback=None)
    redis_password = lifestream.config.get("redis", "password", fallback=None)
    
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
    
    scheduler = BlockingScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )
    
    return scheduler


def add_jobs(scheduler):
    """Add all configured jobs to the scheduler."""
    schedules = get_schedules()
    
    for job_name, config in schedules.items():
        cron = config["cron"]
        
        try:
            trigger = CronTrigger.from_crontab(cron)
        except ValueError as e:
            logger.error(f"Invalid cron expression for {job_name}: {cron} - {e}")
            continue
        
        # Check if it's a shell command (starts with !)
        if job_name.startswith("!"):
            actual_name = job_name[1:]
            command = cron  # For shell commands, cron is actually the command
            scheduler.add_job(
                run_shell_command,
                trigger=trigger,
                args=[actual_name, command],
                id=actual_name,
                name=actual_name,
                misfire_grace_time=config["misfire_grace_time"],
                coalesce=config["coalesce"],
                replace_existing=True,
            )
        else:
            scheduler.add_job(
                run_import,
                trigger=trigger,
                args=[job_name],
                id=job_name,
                name=job_name,
                misfire_grace_time=config["misfire_grace_time"],
                coalesce=config["coalesce"],
                replace_existing=True,
            )
        
        logger.info(f"Scheduled job: {job_name} with cron '{cron}'")
    
    return len(schedules)


def list_jobs():
    """List all configured jobs from config.ini."""
    schedules = get_schedules()
    
    if not schedules:
        print("No jobs configured in [schedules] section of config.ini")
        return
    
    print(f"{'Job Name':<25} {'Schedule':<20} {'Grace(s)':<10} {'Coalesce'}")
    print("-" * 70)
    
    for job_name, config in sorted(schedules.items()):
        print(f"{job_name:<25} {config['cron']:<20} {config['misfire_grace_time']:<10} {config['coalesce']}")


def show_status():
    """Show current job status and next run times."""
    scheduler = create_scheduler()
    
    jobs = scheduler.get_jobs()
    
    if not jobs:
        print("No jobs currently scheduled")
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


def run_job_now(job_name):
    """Run a specific job immediately."""
    schedules = get_schedules()
    
    if job_name not in schedules:
        # Try to run it anyway - maybe it's a valid import
        logger.info(f"Job {job_name} not in schedules, attempting direct run...")
    
    run_import(job_name)


def main():
    args = SCHEDULER_ARGS
    
    if args.debug:
        logging.getLogger("").setLevel(logging.DEBUG)
        logging.getLogger("apscheduler").setLevel(logging.DEBUG)
    
    if args.list:
        list_jobs()
        return
    
    if args.status:
        show_status()
        return
    
    if args.run:
        run_job_now(args.run)
        return
    
    # Default: run the scheduler daemon
    logger.info("Starting Lifestream Scheduler...")
    
    scheduler = create_scheduler()
    
    # Handle shutdown gracefully
    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    # Add all jobs from config
    job_count = add_jobs(scheduler)
    
    if job_count == 0:
        logger.error("No jobs configured! Add jobs to [schedules] in config.ini")
        sys.exit(1)
    
    logger.info(f"Scheduler started with {job_count} jobs")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
