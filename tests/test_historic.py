"""Tests for the historic replay importer."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.historic import HistoricImporter

WHEN = datetime(2016, 8, 3, 10, 0, 0)


def retweet_row(title, handle, full_text=None, systemid="tweet1"):
    """A lifestream row for a retweet, as python-twitter's AsDict() shapes it."""
    retweeted = {"user": {"screen_name": handle}}
    if full_text is not None:
        retweeted["full_text"] = full_text
    row = list(tweet_row(title, systemid))
    row[3] = json.dumps({"id_str": systemid, "retweeted_status": retweeted})
    return tuple(row)


def tweet_row(title, systemid="tweet1"):
    """A lifestream row as imports/tweets.py stores one.

    `source` is the client the tweet was sent from, not "twitter" - which is
    why the importer matches tweets on `type` instead.
    """
    return (
        title,
        WHEN,
        f"http://twitter.com/aquarion/status/{systemid}",
        json.dumps({"id_str": systemid}),
        systemid,
        "Twitter for Android",
        "twitter",
    )


class TestHistoricImporter:
    def _make_importer(self):
        imp = HistoricImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = False
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_get_oauth_path_uses_configured_secrets_file(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="/path/to/secrets.oauth")
        assert imp.get_oauth_path() == "/path/to/secrets.oauth"

    def test_run_skips_reblog_and_auth_when_nothing_in_window(self):
        """No matching rows means no OAuth flow is even triggered."""
        imp = self._make_importer()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        with patch("lifestream.importers.historic.authenticate") as mock_auth:
            imp.run()

        mock_auth.assert_not_called()

    def test_run_reblogs_matching_post(self):
        imp = self._make_importer()
        fulldata = json.dumps({"reblog_key": "rbkey123"})
        row = (
            "A title",
            datetime(2016, 8, 3, 10, 0, 0),
            "http://example.tumblr.com/post/1",
            fulldata,
            "systemid1",
            "tumblr",
            "text",
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [row]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_called_once()
        _, kwargs = mock_tumblr.reblog.call_args
        assert kwargs["id"] == "systemid1"
        assert kwargs["reblog_key"] == "rbkey123"
        assert kwargs["state"] == "queue"

    def test_run_does_not_touch_dbcxn_in_no_db_mode(self):
        """--no-db must not crash by reaching for a cursor on a None dbcxn."""
        imp = self._make_importer()
        imp._entry_store.no_db = True
        imp._entry_store.dbcxn = None

        with patch("lifestream.importers.historic.authenticate") as mock_auth:
            imp.run()  # should not raise

        mock_auth.assert_not_called()

    def test_run_skips_rows_without_title_or_fulldata(self):
        imp = self._make_importer()
        when = datetime(2016, 8, 3, 10, 0, 0)
        rows = [
            (None, when, "url", "{}", "id1", "tumblr", "text"),
            ("Has title", when, "url", None, "id2", "tumblr", "text"),
        ]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_not_called()

    def test_run_skips_posts_already_on_the_history_blog(self):
        """A reblog on the history blog must not be reblogged onto it again."""
        imp = self._make_importer()
        when = datetime(2016, 8, 3, 10, 0, 0)
        own = json.dumps(
            {"reblog_key": "rbkey123", "blog_name": "aquarions-of-history"}
        )
        row = (
            "A title",
            when,
            "https://aquarions-of-history.tumblr.com/post/1",
            own,
            "systemid1",
            "tumblr",
            "text",
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [row]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_not_called()

    def test_run_skips_own_post_without_blog_name_by_url(self):
        """Older rows may have no blog_name; the post URL still identifies it."""
        imp = self._make_importer()
        when = datetime(2016, 8, 3, 10, 0, 0)
        rows = [
            (
                "Mine",
                when,
                "https://aquarions-of-history.tumblr.com/post/1",
                json.dumps({"reblog_key": "a"}),
                "id1",
                "tumblr",
                "text",
            ),
            (
                "Theirs",
                when,
                "https://someone-else.tumblr.com/post/2",
                json.dumps({"reblog_key": "b"}),
                "id2",
                "tumblr",
                "text",
            ),
        ]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_called_once()
        _, kwargs = mock_tumblr.reblog.call_args
        assert kwargs["id"] == "id2"


class TestHistoricTumblrConfig:
    def _make_importer(self):
        imp = HistoricImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = False
        return imp

    def test_to_blog_defaults_when_unconfigured(self):
        imp = self._make_importer()
        assert imp.to_blog == "aquarions-of-history"

    def test_to_blog_reads_historic_section(self):
        imp = self._make_importer()
        with patch(
            "lifestream.importers.historic.get_config_value",
            return_value="somewhere-else",
        ):
            assert imp.to_blog == "somewhere-else"

    def test_to_blog_falls_back_when_configured_blank(self):
        imp = self._make_importer()
        with patch("lifestream.importers.historic.get_config_value", return_value=""):
            assert imp.to_blog == "aquarions-of-history"

    def test_reblog_targets_the_configured_blog(self):
        imp = self._make_importer()
        row = (
            "A title",
            WHEN,
            "https://example.tumblr.com/post/1",
            json.dumps({"reblog_key": "rbkey123"}),
            "systemid1",
            "tumblr",
            "text",
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [row]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with (
            patch(
                "lifestream.importers.historic.authenticate", return_value=mock_tumblr
            ),
            patch(
                "lifestream.importers.historic.get_config_value",
                return_value="somewhere-else",
            ),
        ):
            imp.run()

        args, _ = mock_tumblr.reblog.call_args
        assert args[0] == "somewhere-else"

    def test_own_post_check_follows_the_configured_blog(self):
        """A post on the old default is fair game once the blog is changed."""
        imp = self._make_importer()
        with patch(
            "lifestream.importers.historic.get_config_value",
            return_value="somewhere-else",
        ):
            assert imp._is_own_post({"blog_name": "somewhere-else"}, "") is True
            assert imp._is_own_post({"blog_name": "aquarions-of-history"}, "") is False


class TestHistoricTweetReplay:
    def _make_importer(self, rows, configured=True):
        imp = HistoricImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = False

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        config = {
            "atproto_username": "history.example.com" if configured else None,
            "atproto_password": "app-password" if configured else None,
            "atproto_server_base": None,
            "tumblr_blog": "aquarions-of-history",
        }
        self._config = lambda _section, key, default=None: config.get(key, default)
        return imp

    def _run(self, imp, already_replayed=False):
        mock_client = MagicMock()
        with (
            patch("lifestream.importers.historic.AtClient", return_value=mock_client),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                return_value=3600 if already_replayed else False,
            ),
            patch("lifestream.importers.historic.authenticate"),
        ):
            imp.run()
        return mock_client

    def test_replays_a_tweet_to_bluesky(self):
        imp = self._make_importer([tweet_row("Hello from 2016")])
        client = self._run(imp)

        client.login.assert_called_once_with("history.example.com", "app-password")
        client.send_post.assert_called_once_with(text="Hello from 2016")

    def test_mentions_are_defanged_before_posting(self):
        """The @ substitution predates Bluesky but the intent still holds."""
        imp = self._make_importer([tweet_row("morning @someone")])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="morning 💬someone")

    def test_tweets_are_skipped_when_no_account_is_configured(self):
        imp = self._make_importer([tweet_row("Hello from 2016")], configured=False)
        client = self._run(imp)

        client.login.assert_not_called()
        client.send_post.assert_not_called()

    def test_a_tweet_already_replayed_is_not_posted_twice(self):
        """A coalesced catch-up run must not repost the same tweet."""
        imp = self._make_importer([tweet_row("Hello from 2016")])
        client = self._run(imp, already_replayed=True)

        client.send_post.assert_not_called()

    def test_an_over_length_tweet_is_truncated(self):
        imp = self._make_importer([tweet_row("x" * 400)])
        client = self._run(imp)

        _, kwargs = client.send_post.call_args
        assert len(kwargs["text"]) == 300
        assert kwargs["text"].endswith("…")

    def test_a_tweet_at_the_limit_is_left_alone(self):
        imp = self._make_importer([tweet_row("x" * 300)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="x" * 300)

    def test_a_tweet_is_skipped_if_the_replay_check_fails(self):
        """Redis being unreachable must not mean posting blind."""
        imp = self._make_importer([tweet_row("Hello from 2016")])
        mock_client = MagicMock()
        with (
            patch("lifestream.importers.historic.AtClient", return_value=mock_client),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                side_effect=OSError("no redis"),
            ),
        ):
            imp.run()

        mock_client.send_post.assert_not_called()

    def test_tumblr_is_not_authenticated_for_a_tweet_only_window(self):
        imp = self._make_importer([tweet_row("Hello from 2016")])
        with (
            patch("lifestream.importers.historic.AtClient"),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                return_value=False,
            ),
            patch("lifestream.importers.historic.authenticate") as mock_auth,
        ):
            imp.run()

        mock_auth.assert_not_called()

    def test_a_retweet_is_posted_with_an_attribution_prefix(self):
        imp = self._make_importer(
            [retweet_row("RT @someone: truncated ver…", "someone", "the full thing")]
        )
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] the full thing")

    def test_a_retweet_without_stored_body_strips_twitters_own_prefix(self):
        imp = self._make_importer(
            [retweet_row("RT @someone: what they said", "someone")]
        )
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] what they said")

    def test_a_retweet_body_still_has_its_mentions_defanged(self):
        imp = self._make_importer(
            [retweet_row("RT @someone: hi", "someone", "hi @thirdparty")]
        )
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] hi 💬thirdparty")

    def test_an_ordinary_tweet_gets_no_prefix(self):
        imp = self._make_importer([tweet_row("just me talking")])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="just me talking")

    def test_a_tweet_with_no_fulldata_still_replays(self):
        row = list(tweet_row("Hello from 2016"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="Hello from 2016")

    def test_a_retweet_with_no_fulldata_is_attributed_from_its_title(self):
        """Older rows have no fulldata, so the RT prefix is all there is."""
        row = list(tweet_row("RT @someone: what they said"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] what they said")

    def test_a_fulldata_less_retweet_body_is_defanged(self):
        row = list(tweet_row("RT @someone: hi @thirdparty"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] hi 💬thirdparty")

    def test_a_fulldata_less_ordinary_tweet_is_untouched(self):
        """Only a leading RT prefix counts - an @ mid-sentence is not one."""
        row = list(tweet_row("talking about @someone: they are great"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(
            text="talking about 💬someone: they are great"
        )

    def test_the_old_rt_colon_convention_is_attributed(self):
        """Pre-retweet-button clients typed "RT: @handle:" by hand."""
        row = list(
            tweet_row(
                "RT: @bigcalm: http://www.todaysbigthing.com/2009/08/20 "
                "(via @Xalior)",
                systemid="3448309763",
            )
        )
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(
            text=(
                "[RT:💬bigcalm] http://www.todaysbigthing.com/2009/08/20 "
                "(via 💬Xalior)"
            )
        )

    def test_a_handle_only_retweet_prefix_needs_no_colon(self):
        row = list(tweet_row("RT @someone what they said"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="[RT:💬someone] what they said")

    def test_a_tweet_merely_starting_with_rt_is_not_a_retweet(self):
        row = list(tweet_row("RTs are not endorsements @someone"))
        row[3] = None
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(
            text="RTs are not endorsements 💬someone"
        )

    def test_non_object_fulldata_falls_back_to_the_title(self):
        """Valid JSON that is not an object - "null" - must not blow up."""
        row = list(tweet_row("Hello from 2016"))
        row[3] = "null"
        imp = self._make_importer([tuple(row)])
        client = self._run(imp)

        client.send_post.assert_called_once_with(text="Hello from 2016")

    def test_a_failed_post_gives_its_replay_claim_back(self):
        """Otherwise the rerun the failure prompts would skip the tweet."""
        imp = self._make_importer([tweet_row("Hello from 2016")])
        mock_client = MagicMock()
        mock_client.send_post.side_effect = OSError("bluesky is down")
        mock_redis = MagicMock()

        with (
            patch("lifestream.importers.historic.AtClient", return_value=mock_client),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                return_value=False,
            ),
            patch(
                "lifestream.importers.historic.get_redis_connection",
                return_value=mock_redis,
            ),
        ):
            with pytest.raises(OSError):
                imp.run()

        mock_redis.delete.assert_called_once_with("historic:replayed:tweet1")

    def test_a_claim_release_failure_does_not_mask_the_post_failure(self):
        imp = self._make_importer([tweet_row("Hello from 2016")])
        mock_client = MagicMock()
        mock_client.send_post.side_effect = OSError("bluesky is down")

        with (
            patch("lifestream.importers.historic.AtClient", return_value=mock_client),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                return_value=False,
            ),
            patch(
                "lifestream.importers.historic.get_redis_connection",
                side_effect=OSError("no redis either"),
            ),
        ):
            with pytest.raises(OSError, match="bluesky is down"):
                imp.run()

    def test_a_successful_post_keeps_its_replay_claim(self):
        imp = self._make_importer([tweet_row("Hello from 2016")])
        mock_redis = MagicMock()

        with (
            patch("lifestream.importers.historic.AtClient"),
            patch(
                "lifestream.importers.historic.get_config_value",
                side_effect=self._config,
            ),
            patch(
                "lifestream.importers.historic.check_and_set_backoff",
                return_value=False,
            ),
            patch(
                "lifestream.importers.historic.get_redis_connection",
                return_value=mock_redis,
            ),
        ):
            imp.run()

        mock_redis.delete.assert_not_called()
