"""Tests for lifestream.core.cache module."""

import os
import pickle
import time
from unittest.mock import MagicMock, patch

from lifestream.core import cache


class TestRedisConnection:
    """Tests for Redis connection functions."""

    def test_get_redis_connection_creates_connection(self):
        """Test that get_redis_connection creates a Redis client."""
        # Reset module state
        cache._redis_connection = None

        with patch.object(cache, "redis") as mock_redis_module:
            mock_conn = MagicMock()
            mock_redis_module.Redis.return_value = mock_conn

            result = cache.get_redis_connection()

            assert result is mock_conn
            mock_redis_module.Redis.assert_called_once()

        # Clean up
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


class TestFileCache:
    """Tests for file_cache decorator."""

    def test_file_cache_returns_cached_result(self):
        """Test that file_cache returns cached data when fresh."""
        cache_id = f"test_cache_{time.time()}"
        cache_path = f"/tmp/{cache_id}"

        with open(cache_path, "wb") as f:
            pickle.dump({"cached": True}, f)

        try:

            @cache.file_cache(cache_id, maxage=3600)
            def expensive_function():
                return {"computed": True}

            result = expensive_function()
            assert result == {"cached": True}
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)

    def test_file_cache_computes_when_expired(self):
        """Test that file_cache recomputes when cache is expired."""
        cache_id = f"test_expired_{time.time()}"
        cache_path = f"/tmp/{cache_id}"

        with open(cache_path, "wb") as f:
            pickle.dump({"cached": True}, f)

        old_time = time.time() - 7200
        os.utime(cache_path, (old_time, old_time))

        try:

            @cache.file_cache(cache_id, maxage=3600)
            def expensive_function():
                return {"computed": True}

            result = expensive_function()
            assert result == {"computed": True}
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)

    def test_file_cache_creates_new_cache(self):
        """Test that file_cache creates cache file when none exists."""
        cache_id = f"test_new_{time.time()}"
        cache_path = f"/tmp/{cache_id}"

        if os.path.exists(cache_path):
            os.unlink(cache_path)

        try:

            @cache.file_cache(cache_id, maxage=3600)
            def expensive_function():
                return {"computed": True}

            result = expensive_function()

            assert result == {"computed": True}
            assert os.path.exists(cache_path)
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)
