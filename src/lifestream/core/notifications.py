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
    try:
        return config.getboolean("notifications", "enabled", fallback=False)
    except ValueError as e:
        logger.warning(f"Invalid 'enabled' value in [notifications] config: {e}")
        return False


def send_failure_email(job_name: str, error: Exception | str, duration: float) -> bool:
    """
    Send an email notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)

    Returns:
        True if the email was sent successfully, False otherwise (including
        when notifications/email are disabled or not configured).
    """
    if not _is_notifications_enabled():
        return False

    try:
        smtp_host = config.get("notifications", "smtp_host")
        smtp_port = config.getint("notifications", "smtp_port", fallback=587)
        smtp_user = config.get("notifications", "smtp_user", fallback=None)
        smtp_password = config.get("notifications", "smtp_password", fallback=None)
        use_tls = config.getboolean("notifications", "smtp_use_tls", fallback=True)
        from_addr = config.get("notifications", "from_address")
        to_addr = config.get("notifications", "to_address")
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logger.warning(f"Email notification not configured properly: {e}")
        return False

    subject = f"[Lifestream] Job failed: {job_name}"

    traceback_info = ""
    if isinstance(error, Exception):
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        traceback_info = f"\nTraceback:\n{''.join(tb)}"

    body = f"""Lifestream job '{job_name}' failed after {duration:.1f}s.

Error: {error}
{traceback_info}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            # sendmail() only raises if *every* recipient was refused; a
            # partial refusal (relevant here since there's just the one
            # recipient) comes back as a non-empty dict instead.
            refused = server.sendmail(from_addr, [to_addr], msg.as_string())
        if refused:
            logger.error(
                f"Notification email for job {job_name} was refused for "
                f"recipient(s): {refused}"
            )
            return False
        logger.info(f"Sent failure notification email for job {job_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification email: {e}")
        return False


def send_failure_slack(job_name: str, error: Exception | str, duration: float) -> bool:
    """
    Send a Slack notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)

    Returns:
        True if the Slack message was sent successfully, False otherwise
        (including when notifications/Slack are disabled or not configured).
    """
    if not _is_notifications_enabled():
        return False

    try:
        slack_channel = config.get("notifications", "slack_channel", fallback=None)
        if not slack_channel:
            return False

        if not config.has_section("slack"):
            logger.warning("Slack channel configured but no [slack] section found")
            return False

        webhook_url = config.get("slack", "webhook_url")
        botname = config.get("slack", "slack_botname", fallback="Lifestream")
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.warning(f"Slack notification not configured properly: {e}")
        return False

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
            return True
        logger.error(
            f"Slack notification failed: {response.status_code} {response.text}"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def send_failure_notifications(
    job_name: str, error: Exception | str, duration: float
) -> None:
    """
    Send all configured failure notifications (email and Slack).

    If notifications are enabled but both channels fail to deliver, logs at
    CRITICAL (distinct from the per-channel ERROR/WARNING logging above) so
    a total alerting-pipeline outage — which by definition can't page anyone
    — is at least visible to anyone/anything watching the log level.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)
    """
    email_sent = send_failure_email(job_name, error, duration)
    slack_sent = send_failure_slack(job_name, error, duration)

    if _is_notifications_enabled() and not email_sent and not slack_sent:
        logger.critical(
            "Both email and Slack failure notifications failed for job "
            "'%s' — this failure was not delivered anywhere. Check the "
            "[notifications]/[slack] config (SMTP creds, webhook URL).",
            job_name,
        )
