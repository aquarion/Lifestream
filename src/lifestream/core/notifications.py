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


def _load_email_config() -> dict | None:
    """Read and validate [notifications] SMTP settings.

    Returns None if the section/options are missing, malformed, or any
    required value (smtp_host, from_address, to_address) is present but
    empty — ConfigParser hands an empty option back as "" rather than
    raising, so that has to be checked explicitly.
    """
    try:
        cfg = {
            "smtp_host": config.get("notifications", "smtp_host"),
            "smtp_port": config.getint("notifications", "smtp_port", fallback=587),
            "smtp_user": config.get("notifications", "smtp_user", fallback=None),
            "smtp_password": config.get(
                "notifications", "smtp_password", fallback=None
            ),
            "use_tls": config.getboolean(
                "notifications", "smtp_use_tls", fallback=True
            ),
            "from_addr": config.get("notifications", "from_address"),
            "to_addr": config.get("notifications", "to_address"),
        }
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logger.warning(f"Email notification not configured properly: {e}")
        return None

    if not cfg["smtp_host"] or not cfg["from_addr"] or not cfg["to_addr"]:
        logger.warning(
            "Email notification not configured properly: smtp_host, "
            "from_address, and to_address must all be non-empty"
        )
        return None

    return cfg


def send_failure_email(
    job_name: str, error: Exception | str, duration: float
) -> bool | None:
    """
    Send an email notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)

    Returns:
        True if the email was sent.
        False if email was configured and enabled but sending failed.
        None if notifications are disabled or email isn't configured —
        no delivery was attempted.
    """
    if not _is_notifications_enabled():
        return None

    cfg = _load_email_config()
    if cfg is None:
        return None

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
    msg["From"] = cfg["from_addr"]
    msg["To"] = cfg["to_addr"]

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["smtp_user"] and cfg["smtp_password"]:
                server.login(cfg["smtp_user"], cfg["smtp_password"])
            # sendmail() raises SMTPRecipientsRefused if *every* recipient
            # was refused; with more than one recipient, a *partial*
            # refusal instead comes back as a non-empty dict here. There's
            # only one recipient today, so this defensive check is a no-op
            # in practice, but it's cheap insurance if that ever changes.
            refused = server.sendmail(
                cfg["from_addr"], [cfg["to_addr"]], msg.as_string()
            )
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


def send_failure_slack(
    job_name: str, error: Exception | str, duration: float
) -> bool | None:
    """
    Send a Slack notification when a job fails.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)

    Returns:
        True if the Slack message was sent.
        False if Slack was configured and enabled but sending failed.
        None if notifications are disabled or Slack isn't configured —
        no delivery was attempted.
    """
    if not _is_notifications_enabled():
        return None

    try:
        slack_channel = config.get("notifications", "slack_channel", fallback=None)
        if not slack_channel:
            return None

        if not config.has_section("slack"):
            logger.warning("Slack channel configured but no [slack] section found")
            return None

        webhook_url = config.get("slack", "webhook_url")
        botname = config.get("slack", "slack_botname", fallback="Lifestream")
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logger.warning(f"Slack notification not configured properly: {e}")
        return None

    # webhook_url can be present but empty (e.g. "webhook_url = "), which
    # ConfigParser hands back as "" rather than raising — that must count
    # as unconfigured (None), not fall through into an attempted (and
    # doomed) post that reports False.
    if not webhook_url:
        logger.warning("Slack notification not configured properly: empty webhook_url")
        return None

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

    If at least one channel is actually configured and enabled, and every
    channel that was attempted failed to send, this is the alerting
    pipeline itself going dark — the one failure mode this function can't
    report through its own channels. Log it at CRITICAL (distinct from the
    per-channel ERROR/WARNING logging above) so it's visible to anyone/
    anything watching the log level, independent of email/Slack.

    Note: send_failure_email()/send_failure_slack() return None (not
    False) when a channel isn't configured, so an unconfigured channel
    never counts as "failed" here — otherwise a deliberate single-channel
    setup (e.g. only email configured) would be misreported as "both
    email and Slack failing" on every ordinary send failure.

    Args:
        job_name: Name of the failed job
        error: The error/exception that occurred
        duration: How long the job ran before failing (seconds)
    """
    email_sent = send_failure_email(job_name, error, duration)
    slack_sent = send_failure_slack(job_name, error, duration)

    attempted_and_failed = email_sent is False or slack_sent is False
    any_succeeded = email_sent is True or slack_sent is True

    if attempted_and_failed and not any_succeeded:
        logger.critical(
            "NOTIFICATION_PIPELINE_DOWN: every configured failure-alert "
            "channel failed to send for job '%s' — no alert was delivered "
            "for this failure. Check the [notifications]/[slack] config "
            "(SMTP creds, webhook URL).",
            job_name,
        )
