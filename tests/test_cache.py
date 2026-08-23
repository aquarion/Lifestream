"""Tests for lifestream.core.cache module."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream import cache


class TestRedisConnection:
    """Tests for Redis connection functions."""

    def test_get_redis_connection_creates_connection(self):
        """Test that get_redis_connection creates a Redis client."""
        cache._redis_connection = None
        try:
            with patch.object(cache, "redis") as mock_redis_module:
                mock_conn = MagicMock()
                mock_conn.ping.return_value = True
                mock_redis_module.Redis.return_value = mock_conn
                mock_redis_module.exceptions = cache.redis.exceptions

                result = cache.get_redis_connection()

                assert result is mock_conn
                mock_redis_module.Redis.assert_called_once()
                mock_conn.ping.assert_called_once()
        finally:
            cache._redis_connection = None

    def test_get_redis_connection_reuses_connection(self):
        """Test that get_redis_connection reuses existing connection."""
        mock_conn = MagicMock()
        original = cache._redis_connection
        cache._redis_connection = mock_conn

        try:
            result = cache.get_redis_connection()
            assert result is mock_conn
        finally:
            cache._redis_connection = original

    def test_get_redis_connection_raises_with_clear_message_on_failure(self):
        """Test that Redis ConnectionError includes host info."""
        import redis as redis_module

        cache._redis_connection = None
        try:
            mock_conn = MagicMock()
            mock_conn.ping.side_effect = redis_module.exceptions.ConnectionError(
                "refused"
            )

            with patch.object(cache, "redis") as mock_redis_module:
                mock_redis_module.Redis.return_value = mock_conn
                mock_redis_module.exceptions = redis_module.exceptions

                with pytest.raises(
                    redis_module.exceptions.ConnectionError,
                    match="Cannot connect to Redis at",
                ):
                    cache.get_redis_connection()

            assert cache._redis_connection is None
        finally:
            cache._redis_connection = None

    def test_get_redis_connection_raises_on_auth_error(self):
        """Test that AuthenticationError includes config guidance and does not cache connection."""
        import redis as redis_module

        cache._redis_connection = None
        try:
            mock_conn = MagicMock()
            mock_conn.ping.side_effect = redis_module.exceptions.AuthenticationError(
                "WRONGPASS"
            )

            with patch.object(cache, "redis") as mock_redis_module:
                mock_redis_module.Redis.return_value = mock_conn
                mock_redis_module.exceptions = redis_module.exceptions

                with pytest.raises(
                    redis_module.exceptions.AuthenticationError,
                    match="check redis.username/password in config",
                ):
                    cache.get_redis_connection()

            assert cache._redis_connection is None
        finally:
            cache._redis_connection = None


class TestBackoff:
    """Tests for backoff functions."""

    def test_set_backoff(self):
        """Test that set_backoff sets a key with expiry."""
        mock_redis = MagicMock()
        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            cache.set_backoff("test_warning", hours=12)
            mock_redis.set.assert_called_once_with("test_warning", "1", ex=12 * 3600)

    def test_should_backoff_returns_true_when_key_exists(self):
        """Test should_backoff returns True when backoff key exists."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"1"

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.should_backoff("test_warning")
            assert result is True

    def test_should_backoff_returns_false_when_key_missing(self):
        """Test should_backoff returns False when no backoff key."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.should_backoff("test_warning")
            assert result is False

    def test_check_and_set_backoff_sets_when_not_exists(self):
        """Test check_and_set_backoff sets key if not already set."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.check_and_set_backoff("test_warning", hours=6)
            assert result is False
            mock_redis.set.assert_called_once_with("test_warning", "1", ex=6 * 3600)

    def test_check_and_set_backoff_returns_ttl_when_exists(self):
        """Test check_and_set_backoff returns TTL if already set."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"1"
        mock_redis.ttl.return_value = 7200

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.check_and_set_backoff("test_warning")
            assert result == 7200


class TestRedisCache:
    """Tests for redis_cache decorator."""

    def test_redis_cache_returns_cached_result(self):
        """Test that redis_cache returns cached data without calling the function."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"cached": true}'

        expensive_function = MagicMock(return_value={"computed": True})

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.redis_cache("test_key", maxage=3600)(expensive_function)()

        assert result == {"cached": True}
        expensive_function.assert_not_called()

    def test_redis_cache_computes_and_stores_on_miss(self):
        """Test that redis_cache calls the function and stores the JSON result on a miss."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        @cache.redis_cache("test_key", maxage=3600)
        def expensive_function():
            return {"computed": True}

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = expensive_function()

        assert result == {"computed": True}
        mock_redis.set.assert_called_once_with(
            "test_key", '{"computed": true}', ex=3600
        )

    def test_redis_cache_recomputes_on_corrupted_value(self):
        """A malformed cached value is recomputed instead of raising or wedging the cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "not valid json"

        expensive_function = MagicMock(return_value={"computed": True})

        with patch.object(cache, "get_redis_connection", return_value=mock_redis):
            result = cache.redis_cache("test_key", maxage=3600)(expensive_function)()

        assert result == {"computed": True}
        expensive_function.assert_called_once()
        mock_redis.set.assert_called_once_with(
            "test_key", '{"computed": true}', ex=3600
        )
