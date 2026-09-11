"""Tests for lifestream.core.notifications module."""

import configparser
from unittest.mock import MagicMock, patch

from lifestream import notifications


class TestNotificationsEnabled:
    """Tests for notification enabled checks."""

    def test_notifications_disabled_when_no_section(self):
        """Test notifications are disabled when no [notifications] section."""
        mock_config = MagicMock()
        mock_config.has_section.return_value = False

        with patch.object(notifications, "config", mock_config):
            assert notifications._is_notifications_enabled() is False

    def test_notifications_disabled_when_enabled_false(self):
        """Test notifications are disabled when enabled=false."""
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.getboolean.return_value = False

        with patch.object(notifications, "config", mock_config):
            assert notifications._is_notifications_enabled() is False

    def test_notifications_enabled_when_configured(self):
        """Test notifications are enabled when properly configured."""
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.getboolean.return_value = True

        with patch.object(notifications, "config", mock_config):
            assert notifications._is_notifications_enabled() is True

    def test_notifications_disabled_on_malformed_enabled_value(self):
        """A non-boolean 'enabled' value doesn't raise — it's treated as disabled."""
        mock_config = MagicMock()
        mock_config.has_section.return_value = True
        mock_config.getboolean.side_effect = ValueError("not a boolean: 'maybe'")

        with patch.object(notifications, "config", mock_config):
            assert notifications._is_notifications_enabled() is False


class TestSendFailureEmail:
    """Tests for email notification sending."""

    def test_email_skipped_when_notifications_disabled(self):
        """Email returns None (not attempted), not False, when disabled —
        False is reserved for a channel that was actually attempted and
        failed."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=False
        ):
            with patch.object(notifications, "smtplib") as mock_smtp:
                result = notifications.send_failure_email(
                    "test_job", Exception("test"), 1.5
                )
                mock_smtp.SMTP.assert_not_called()
                assert result is None

    def test_email_returns_none_when_not_configured(self):
        """A missing required option (e.g. no from_address) means email was
        never attempted — that's None, not a delivery failure."""
        mock_config = MagicMock()
        mock_config.get.side_effect = configparser.NoOptionError(
            "from_address", "notifications"
        )

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                result = notifications.send_failure_email(
                    "test_job", Exception("test"), 1.5
                )

        assert result is None

    def test_email_returns_none_when_smtp_host_present_but_empty(self):
        """A required option can be present but empty ("smtp_host = ") —
        ConfigParser returns "" rather than raising, so this must still be
        treated as unconfigured (None), not fall through into an attempted
        (and doomed) send that reports False."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "smtp_host"): "",
            ("notifications", "from_address"): "from@test.com",
            ("notifications", "to_address"): "to@test.com",
        }.get((s, k), kw.get("fallback"))
        mock_config.getint.return_value = 587
        mock_config.getboolean.return_value = True

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(notifications, "smtplib") as mock_smtp:
                    result = notifications.send_failure_email(
                        "test_job", Exception("test"), 1.5
                    )

        assert result is None
        mock_smtp.SMTP.assert_not_called()

    def test_email_sent_with_correct_content(self):
        """Test email is sent with correct subject and body."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "smtp_host"): "smtp.test.com",
            ("notifications", "from_address"): "from@test.com",
            ("notifications", "to_address"): "to@test.com",
            ("notifications", "smtp_user"): kw.get("fallback"),
            ("notifications", "smtp_password"): kw.get("fallback"),
        }.get((s, k), kw.get("fallback"))
        mock_config.getint.return_value = 587
        mock_config.getboolean.return_value = True

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=None)
        mock_smtp_instance.sendmail.return_value = {}  # no recipients refused

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(
                    notifications.smtplib, "SMTP", return_value=mock_smtp_instance
                ):
                    result = notifications.send_failure_email(
                        "test_job", Exception("test error"), 1.5
                    )

                    mock_smtp_instance.starttls.assert_called_once()
                    mock_smtp_instance.sendmail.assert_called_once()
                    assert result is True

    def test_email_returns_none_on_malformed_smtp_port(self):
        """A non-integer smtp_port doesn't raise — it's treated as never
        attempted (None), not a delivery failure (False)."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "smtp_host"): "smtp.test.com",
        }.get((s, k), kw.get("fallback"))
        mock_config.getint.side_effect = ValueError("invalid literal for int()")

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(notifications, "smtplib") as mock_smtp:
                    result = notifications.send_failure_email(
                        "test_job", Exception("test"), 1.5
                    )

                    assert result is None
                    mock_smtp.SMTP.assert_not_called()

    def test_email_returns_false_when_recipient_refused(self):
        """sendmail() returning a non-empty refusal dict counts as a failed send."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "smtp_host"): "smtp.test.com",
            ("notifications", "from_address"): "from@test.com",
            ("notifications", "to_address"): "to@test.com",
            ("notifications", "smtp_user"): kw.get("fallback"),
            ("notifications", "smtp_password"): kw.get("fallback"),
        }.get((s, k), kw.get("fallback"))
        mock_config.getint.return_value = 587
        mock_config.getboolean.return_value = True

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=None)
        mock_smtp_instance.sendmail.return_value = {
            "to@test.com": (450, b"mailbox unavailable")
        }

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(
                    notifications.smtplib, "SMTP", return_value=mock_smtp_instance
                ):
                    result = notifications.send_failure_email(
                        "test_job", Exception("test error"), 1.5
                    )

                    assert result is False


class TestSendFailureSlack:
    """Tests for Slack notification sending."""

    def test_slack_skipped_when_notifications_disabled(self):
        """Slack returns None (not attempted), not False, when disabled —
        False is reserved for a channel that was actually attempted and
        failed."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=False
        ):
            with patch.object(notifications, "requests") as mock_requests:
                result = notifications.send_failure_slack(
                    "test_job", Exception("test"), 1.5
                )
                mock_requests.post.assert_not_called()
                assert result is None

    def test_slack_returns_none_when_channel_not_configured(self):
        """No slack_channel configured means Slack was never attempted —
        that's None, not a delivery failure."""
        mock_config = MagicMock()
        mock_config.get.return_value = None

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                result = notifications.send_failure_slack(
                    "test_job", Exception("test"), 1.5
                )

        assert result is None

    def test_slack_returns_none_when_webhook_url_present_but_empty(self):
        """webhook_url can be present but empty ("webhook_url = ") —
        ConfigParser returns "" rather than raising, so this must still be
        treated as unconfigured (None), not fall through into an attempted
        (and doomed) post that reports False."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "slack_channel"): "test-channel",
            ("slack", "webhook_url"): "",
        }.get((s, k), kw.get("fallback"))
        mock_config.has_section.return_value = True

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(notifications, "requests") as mock_requests:
                    result = notifications.send_failure_slack(
                        "test_job", Exception("test"), 1.5
                    )

        assert result is None
        mock_requests.post.assert_not_called()

    def test_slack_message_sent_correctly(self):
        """Test Slack message is sent with correct payload."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "slack_channel"): "test-channel",
            (
                "slack",
                "webhook_url",
            ): "https://hooks.slack.com/services/T00000000/B00000000/xxxxx",
            ("slack", "slack_botname"): "TestBot",
        }.get((s, k), kw.get("fallback"))
        mock_config.has_section.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(
                    notifications.requests, "post", return_value=mock_response
                ) as mock_post:
                    result = notifications.send_failure_slack(
                        "test_job", Exception("test"), 1.5
                    )

                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    # test assertion, not URL sanitization
                    assert (
                        "hooks.slack.com"
                        in call_args[0][
                            0
                        ]  # codeql[py/incomplete-url-substring-sanitization]
                    )
                    assert result is True

    def test_slack_returns_false_on_non_200_response(self):
        """A non-200 response from the webhook counts as a failed send."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "slack_channel"): "test-channel",
            (
                "slack",
                "webhook_url",
            ): "https://hooks.slack.com/services/T00000000/B00000000/xxxxx",
            ("slack", "slack_botname"): "TestBot",
        }.get((s, k), kw.get("fallback"))
        mock_config.has_section.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(
                    notifications.requests, "post", return_value=mock_response
                ):
                    result = notifications.send_failure_slack(
                        "test_job", Exception("test"), 1.5
                    )

                    assert result is False

    def test_slack_returns_false_on_request_exception(self):
        """A network/request error sending to the webhook is a failed send."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda s, k, **kw: {
            ("notifications", "slack_channel"): "test-channel",
            (
                "slack",
                "webhook_url",
            ): "https://hooks.slack.com/services/T00000000/B00000000/xxxxx",
            ("slack", "slack_botname"): "TestBot",
        }.get((s, k), kw.get("fallback"))
        mock_config.has_section.return_value = True

        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "config", mock_config):
                with patch.object(
                    notifications.requests,
                    "post",
                    side_effect=ConnectionError("network unreachable"),
                ):
                    result = notifications.send_failure_slack(
                        "test_job", Exception("test"), 1.5
                    )

                    assert result is False


class TestSendFailureNotifications:
    """Tests for combined notification sending."""

    def test_sends_both_email_and_slack(self):
        """Test that send_failure_notifications calls both methods."""
        with patch.object(
            notifications, "send_failure_email", return_value=True
        ) as mock_email:
            with patch.object(
                notifications, "send_failure_slack", return_value=True
            ) as mock_slack:
                error = Exception("error")
                notifications.send_failure_notifications("test_job", error, 2.5)

                mock_email.assert_called_once_with("test_job", error, 2.5)
                mock_slack.assert_called_once_with("test_job", error, 2.5)

    def test_logs_critical_when_both_channels_fail(self):
        """A total alerting outage (both channels configured and fail) is
        escalated to CRITICAL."""
        with patch.object(notifications, "send_failure_email", return_value=False):
            with patch.object(notifications, "send_failure_slack", return_value=False):
                with patch.object(notifications, "logger") as mock_logger:
                    notifications.send_failure_notifications(
                        "test_job", Exception("error"), 2.5
                    )

                    mock_logger.critical.assert_called_once()
                    assert (
                        "NOTIFICATION_PIPELINE_DOWN"
                        in mock_logger.critical.call_args[0][0]
                    )

    def test_no_critical_log_when_one_channel_succeeds(self):
        """No escalation needed as long as one channel got the alert through."""
        with patch.object(notifications, "send_failure_email", return_value=True):
            with patch.object(notifications, "send_failure_slack", return_value=False):
                with patch.object(notifications, "logger") as mock_logger:
                    notifications.send_failure_notifications(
                        "test_job", Exception("error"), 2.5
                    )

                    mock_logger.critical.assert_not_called()

    def test_no_critical_log_when_notifications_disabled(self):
        """Both channels return None (not attempted) when notifications are
        disabled — that's the normal case, not a pipeline failure."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=False
        ):
            with patch.object(notifications, "logger") as mock_logger:
                notifications.send_failure_notifications(
                    "test_job", Exception("error"), 2.5
                )

                mock_logger.critical.assert_not_called()

    def test_logs_critical_when_the_only_configured_channel_fails(self):
        """This is the case the earlier plain-bool contract got wrong: a
        deliberate single-channel setup (e.g. only email configured, Slack
        section absent) still logs critical if that one channel fails — no
        alert genuinely was delivered — but the message must not claim
        "both" failed when only one was ever configured (Slack returns
        None: never attempted)."""
        with patch.object(notifications, "send_failure_email", return_value=False):
            with patch.object(notifications, "send_failure_slack", return_value=None):
                with patch.object(notifications, "logger") as mock_logger:
                    notifications.send_failure_notifications(
                        "test_job", Exception("error"), 2.5
                    )

                    mock_logger.critical.assert_called_once()
                    message = mock_logger.critical.call_args[0][0]
                    assert "NOTIFICATION_PIPELINE_DOWN" in message
                    assert "both email and slack" not in message.lower()

    def test_no_critical_log_when_the_only_configured_channel_succeeds(self):
        """A single-channel setup that succeeds is not a pipeline-down
        state, regardless of the other (unconfigured) channel."""
        with patch.object(notifications, "send_failure_email", return_value=True):
            with patch.object(notifications, "send_failure_slack", return_value=None):
                with patch.object(notifications, "logger") as mock_logger:
                    notifications.send_failure_notifications(
                        "test_job", Exception("error"), 2.5
                    )

                    mock_logger.critical.assert_not_called()

    def test_no_critical_log_when_no_channel_configured(self):
        """Notifications enabled but nothing configured at all: both return
        None (not attempted) — not a "pipeline down" state, since nothing
        was ever attempted to go down."""
        with patch.object(notifications, "send_failure_email", return_value=None):
            with patch.object(notifications, "send_failure_slack", return_value=None):
                with patch.object(notifications, "logger") as mock_logger:
                    notifications.send_failure_notifications(
                        "test_job", Exception("error"), 2.5
                    )

                    mock_logger.critical.assert_not_called()
