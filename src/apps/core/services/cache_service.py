"""
Cache service for Redis-based caching with decorators and invalidation utilities.

Provides:
- cache_query_result: Decorator for caching function results
- invalidate_pattern: Invalidate cache keys by pattern
- invalidate_key: Invalidate a specific cache key
"""

from collections.abc import Callable
from functools import wraps

from django.core.cache import cache
from loguru import logger


def cache_query_result(
    timeout: int = 300,
    key_prefix: str = "query",
    cache_name: str = "default",
):
    """
    Decorator for caching query results with automatic invalidation.

    Args:
        timeout: Cache TTL in seconds
        key_prefix: Prefix for cache key
        cache_name: Which cache to use (default or queries)

    Example:
        @cache_query_result(timeout=300, key_prefix="filter_counts", cache_name="queries")
        def _get_filter_counts(self, base_qs) -> dict[str, int]:
            # ... expensive query ...
            return counts
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]

            # Add args to key (handle unhashable types)
            if args:
                for arg in args:
                    # Handle QuerySet, dict, list, etc.
                    if hasattr(arg, "query"):
                        # For QuerySets, use a hash of the query
                        key_parts.append(str(hash(str(arg.query))))
                    elif isinstance(arg, (dict, list)):
                        key_parts.append(str(hash(str(arg))))
                    else:
                        key_parts.append(str(arg))

            # Add kwargs to key (sorted for consistency)
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (dict, list)):
                        key_parts.append(f"{k}={hash(str(v))}")
                    else:
                        key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            from django.core.cache import caches

            try:
                cache_backend = caches[cache_name]
            except Exception:
                # Cache backend doesn't exist, fall back to default
                cache_backend = caches["default"]

            result = cache_backend.get(cache_key)

            if result is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return result

            # Execute and cache
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            cache_backend.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


def invalidate_pattern(pattern: str) -> None:
    """
    Invalidate all cache keys matching a pattern.

    Note: This requires Redis SCAN command. Not efficient for large patterns.
    Prefer specific key invalidation where possible.

    Args:
        pattern: Pattern to match (without wildcards, * is added automatically)

    Example:
        invalidate_pattern("filter_counts")  # Clears all keys with "filter_counts"
    """
    from django.core.cache import caches

    # Try queries cache first, fall back to default
    try:
        cache_backend = caches["queries"]
    except Exception:
        cache_backend = caches["default"]

    try:
        # Use django-redis's delete_pattern method
        cache_backend.delete_pattern(f"*{pattern}*")
        logger.info(f"Invalidated cache pattern: *{pattern}*")
    except Exception as e:
        logger.error(f"Failed to invalidate pattern *{pattern}*: {e}")


def invalidate_key(key: str) -> None:
    """
    Invalidate a specific cache key.

    Args:
        key: Full cache key to invalidate

    Example:
        invalidate_key("ea_platform:query:filter_counts:...")
    """
    try:
        cache.delete(key)
        logger.debug(f"Invalidated cache key: {key}")
    except Exception as e:
        logger.error(f"Failed to invalidate key {key}: {e}")


def cache_async_result(
    timeout: int = 300,
    key_prefix: str = "async",
    cache_name: str = "default",
):
    """
    Decorator for caching async function results.

    Similar to cache_query_result but for async functions.

    Args:
        timeout: Cache TTL in seconds
        key_prefix: Prefix for cache key
        cache_name: Which cache to use (default or queries)

    Example:
        @cache_async_result(timeout=86400, key_prefix="osiris_course")
        async def fetch_course_details(self, course_code: int):
            # ... expensive API call ...
            return data
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]

            # Add args to key
            if args:
                for arg in args:
                    if isinstance(arg, (dict, list)):
                        key_parts.append(str(hash(str(arg))))
                    else:
                        key_parts.append(str(arg))

            # Add kwargs to key
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (dict, list)):
                        key_parts.append(f"{k}={hash(str(v))}")
                    else:
                        key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            from django.core.cache import caches

            try:
                cache_backend = caches[cache_name]
            except Exception:
                # Cache backend doesn't exist, fall back to default
                cache_backend = caches["default"]

            result = cache_backend.get(cache_key)

            if result is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return result

            # Execute and cache
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            cache_backend.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator
