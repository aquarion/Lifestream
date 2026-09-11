"""Tests for lifestream.core.notifications module."""

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
        """Test email is not sent when notifications disabled."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=False
        ):
            with patch.object(notifications, "smtplib") as mock_smtp:
                notifications.send_failure_email("test_job", Exception("test"), 1.5)
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

    def test_email_returns_false_on_malformed_smtp_port(self):
        """A non-integer smtp_port doesn't raise — it's treated as misconfigured."""
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

                    assert result is False
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
        """Test Slack message not sent when notifications disabled."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=False
        ):
            with patch.object(notifications, "requests") as mock_requests:
                notifications.send_failure_slack("test_job", Exception("test"), 1.5)
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
                    notifications.send_failure_slack("test_job", Exception("test"), 1.5)

                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    # test assertion, not URL sanitization
                    assert (
                        "hooks.slack.com"
                        in call_args[0][
                            0
                        ]  # codeql[py/incomplete-url-substring-sanitization]
                    )


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
        """A total alerting outage (both channels fail) is escalated to CRITICAL."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "send_failure_email", return_value=False):
                with patch.object(
                    notifications, "send_failure_slack", return_value=False
                ):
                    with patch.object(notifications, "logger") as mock_logger:
                        notifications.send_failure_notifications(
                            "test_job", Exception("error"), 2.5
                        )

                        mock_logger.critical.assert_called_once()

    def test_no_critical_log_when_one_channel_succeeds(self):
        """No escalation needed as long as one channel got the alert through."""
        with patch.object(
            notifications, "_is_notifications_enabled", return_value=True
        ):
            with patch.object(notifications, "send_failure_email", return_value=True):
                with patch.object(
                    notifications, "send_failure_slack", return_value=False
                ):
                    with patch.object(notifications, "logger") as mock_logger:
                        notifications.send_failure_notifications(
                            "test_job", Exception("error"), 2.5
                        )

                        mock_logger.critical.assert_not_called()
