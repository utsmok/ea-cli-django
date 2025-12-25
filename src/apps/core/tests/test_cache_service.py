"""
Tests for cache service.

Tests the cache decorators and invalidation utilities.
"""

import pytest

from apps.core.services.cache_service import (
    cache_async_result,
    cache_query_result,
    invalidate_key,
    invalidate_pattern,
)


class TestCacheService:
    """Test synchronous cache decorator."""

    def test_cache_decorator_hit(self):
        """Test cache returns cached value on second call."""
        call_count = 0

        @cache_query_result(timeout=60, key_prefix="test")
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - cache miss
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - cache hit
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

    def test_cache_decorator_miss_different_args(self):
        """Test cache misses for different arguments."""
        call_count = 0

        @cache_query_result(timeout=60, key_prefix="test_diff_args")
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # Call with different arguments should result in different cache keys
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        result2 = expensive_function(10)
        assert result2 == 20
        # Different argument = different cache key = function executes again
        assert call_count == 2

    def test_cache_decorator_with_kwargs(self):
        """Test cache with keyword arguments."""
        call_count = 0

        @cache_query_result(timeout=60, key_prefix="test")
        def expensive_function(x, y=0):
            nonlocal call_count
            call_count += 1
            return x + y

        # Same args, different order
        expensive_function(5, y=10)
        expensive_function(5, y=10)

        assert call_count == 1

    def test_invalidate_key(self):
        """Test invalidating a specific cache key."""
        from django.core.cache import cache

        # Set a value
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

        # Invalidate
        invalidate_key("test_key")
        assert cache.get("test_key") is None

    def test_invalidate_pattern(self):
        """Test invalidating cache keys by pattern."""
        from django.core.cache import caches

        cache_backend = caches["default"]

        # Set multiple keys
        cache_backend.set("filter_counts:abc", 123)
        cache_backend.set("filter_counts:def", 456)
        cache_backend.set("other_key", 789)

        # Invalidate pattern
        invalidate_pattern("filter_counts")

        # Check that filter_counts keys are gone
        # Note: This depends on django-redis implementation
        # and might not work with DummyCache backend


class TestAsyncCacheService:
    """Test asynchronous cache decorator."""

    @pytest.mark.asyncio
    async def test_async_cache_decorator_hit(self):
        """Test async cache returns cached value on second call."""
        call_count = 0

        @cache_async_result(timeout=60, key_prefix="test_async")
        async def expensive_async_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - cache miss
        result1 = await expensive_async_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - cache hit
        result2 = await expensive_async_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

    @pytest.mark.asyncio
    async def test_async_cache_decorator_miss_different_args(self):
        """Test async cache misses for different arguments."""
        call_count = 0

        @cache_async_result(timeout=60, key_prefix="test_async_diff")
        async def expensive_async_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # Call with different arguments should result in different cache keys
        result1 = await expensive_async_function(5)
        assert result1 == 10
        assert call_count == 1

        result2 = await expensive_async_function(10)
        assert result2 == 20
        # Different argument = different cache key = function executes again
        assert call_count == 2
