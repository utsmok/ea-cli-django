"""
Retry logic with exponential backoff for external API calls.

Only retries on transient errors (timeouts, rate limits).
Does NOT retry on authentication/authorization failures (401, 403).
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_retryable_error(response: httpx.Response) -> bool:
    """
    Determine if an HTTP response indicates a retryable error.

    Retryable: 429 (rate limit), 408 (timeout), 502, 503, 504 (gateway errors)
    Not retryable: 401 (unauthorized), 403 (forbidden), 404 (not found), 4xx client errors
    """
    status = response.status_code

    # Retry on rate limits
    if status == 429:
        return True

    # Retry on timeouts and gateway errors
    if status in (408, 502, 503, 504):
        return True

    # Do NOT retry on auth failures or client errors
    if 400 <= status < 500:
        return False

    # Retry on other 5xx errors
    if status >= 500:
        return True

    return False


async def retry_with_exponential_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)

    Returns:
        Result of the function call

    Raises:
        Exception: The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            last_exception = e

            # Check if this error is retryable
            if is_retryable_error(e.response):
                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    # Extract Retry-After header if present
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(float(retry_after), delay)
                        except ValueError:
                            pass

                    logger.warning(
                        f"Retryable error {e.response.status_code} on attempt {attempt + 1}/{max_retries + 1}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Max retries ({max_retries}) exceeded for status {e.response.status_code}"
                    )
            else:
                # Not retryable - raise immediately
                logger.debug(f"Non-retryable error {e.response.status_code} - failing immediately")
                raise

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exception = e

            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), max_delay)
                logger.warning(
                    f"{type(e).__name__} on attempt {attempt + 1}/{max_retries + 1}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {type(e).__name__}"
                )

        except Exception as e:
            # Unknown exception - don't retry
            logger.error(f"Unexpected exception {type(e).__name__}: {e}")
            raise

    # All retries exhausted
    logger.error(f"All retry attempts failed: {last_exception}")
    raise last_exception


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
):
    """
    Decorator for async functions that adds retry logic with exponential backoff.

    Usage:
        @async_retry(max_retries=3, base_delay=1.0)
        async def fetch_data(url):
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async def _attempt():
                return await func(*args, **kwargs)

            return await retry_with_exponential_backoff(
                _attempt,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
            )

        return wrapper

    return decorator
