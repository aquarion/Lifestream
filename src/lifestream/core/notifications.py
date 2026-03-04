"""
Notification functions for Lifestream scheduler.

Sends failure notifications via email and Slack when jobs fail.
"""

import configparser
import logging
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText

import requests

from .config import config

logger = logging.getLogger(__name__)


def _is_notifications_enabled() -> bool:
    """Check if notifications are enabled."""
    if not config.has_section("notifications"):
        return False
    return config.getboolean("notifications", "enabled", fallback=False)


def send_failure_email(job_name: str, error: Exception | str, duration: float) -> None:
    """
    Send an email notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)
    """
    if not _is_notifications_enabled():
        return

    try:
        smtp_host = config.get("notifications", "smtp_host")
        smtp_port = config.getint("notifications", "smtp_port", fallback=587)
        smtp_user = config.get("notifications", "smtp_user", fallback=None)
        smtp_password = config.get("notifications", "smtp_password", fallback=None)
        use_tls = config.getboolean("notifications", "smtp_use_tls", fallback=True)
        from_addr = config.get("notifications", "from_address")
        to_addr = config.get("notifications", "to_address")
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.warning(f"Email notification not configured properly: {e}")
        return

    subject = f"[Lifestream] Job failed: {job_name}"
    body = f"""Lifestream job '{job_name}' failed after {duration:.1f}s.

Error: {error}

Traceback:
{traceback.format_exc()}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        logger.info(f"Sent failure notification email for job {job_name}")
    except Exception as e:
        logger.error(f"Failed to send notification email: {e}")


def send_failure_slack(job_name: str, error: Exception | str, duration: float) -> None:
    """
    Send a Slack notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)
    """
    if not _is_notifications_enabled():
        return

    try:
        slack_channel = config.get("notifications", "slack_channel", fallback=None)
        if not slack_channel:
            return

        if not config.has_section("slack"):
            logger.warning("Slack channel configured but no [slack] section found")
            return

        token = config.get("slack", "token")
        botname = config.get("slack", "slack_botname", fallback="Lifestream")
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.warning(f"Slack notification not configured properly: {e}")
        return

    webhook_url = f"https://hooks.slack.com/services/{token}"

    message = {
        "channel": f"#{slack_channel}",
        "username": botname,
        "icon_emoji": ":warning:",
        "attachments": [
            {
                "color": "danger",
                "title": f"Job failed: {job_name}",
                "text": f"```{error}```",
                "fields": [
                    {"title": "Duration", "value": f"{duration:.1f}s", "short": True},
                    {
                        "title": "Time",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "short": True,
                    },
                ],
                "footer": "Lifestream Scheduler",
            }
        ],
    }

    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        if response.status_code == 200:
            logger.info(f"Sent failure notification to Slack for job {job_name}")
        else:
            logger.error(
                f"Slack notification failed: {response.status_code} {response.text}"
            )
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")


def send_failure_notifications(
    job_name: str, error: Exception | str, duration: float
) -> None:
    """
    Send all configured failure notifications (email and Slack).

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)
    """
    send_failure_email(job_name, error, duration)
    send_failure_slack(job_name, error, duration)
