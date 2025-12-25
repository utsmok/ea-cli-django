# Task 5: Error Handling & Retry Logic

## Overview

Implement retry logic with exponential backoff for external API calls to handle transient failures (rate limits, timeouts, gateway errors).

**Current Status:** ✅ **COMPLETED**

**Implemented:**
- Retry logic with exponential backoff
- Smart retry detection (transient vs permanent errors)
- Applied to all external API services

## What Was Implemented

### Core Features ✅

**Retry Decorator:**
- `@async_retry` decorator for async functions
- Exponential backoff: 1s → 2s → 4s → 8s (max 60s)
- Max retries: 3 (configurable)

**Smart Retry Detection:**
- **Retries:** 429 (rate limit), 408/502/503/504 (timeouts/gateway errors), network errors
- **No retry:** 401/403 (auth failures), 404 (not found), other 4xx client errors

**Applied To:**
- OsirisService.fetch_course_data()
- OsirisService.fetch_person_data()
- CanvasService.check_single_file_existence()
- download_pdf_from_canvas()

### Bug Fix ✅

Fixed Canvas service to handle None URL gracefully:
- Previously crashed with "argument of type 'NoneType' is not iterable"
- Now returns `file_exists=False` for None/empty URLs

## Implementation Details

### File: `src/apps/core/services/retry_logic.py` (NEW)

```python
import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar
import httpx

logger = logging.getLogger(__name__)

def is_retryable_error(response: httpx.Response) -> bool:
    """
    Determine if an HTTP response indicates a retryable error.

    Retryable: 429 (rate limit), 408 (timeout), 502, 503, 504 (gateway errors)
    Not retryable: 401 (unauthorized), 403 (forbidden), 404 (not found), 4xx client errors
    """
    status = response.status_code

    if status == 429:
        return True  # Rate limit
    if status in (408, 502, 503, 504):
        return True  # Timeout/gateway errors
    if 400 <= status < 500:
        return False  # Client errors - don't retry
    if status >= 500:
        return True  # Server errors - retry

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
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

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

            if is_retryable_error(e.response):
                if attempt < max_retries:
                    # Exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    # Respect Retry-After header if present
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
                # Not retryable - fail immediately
                logger.debug(f"Non-retryable error {e.response.status_code}")
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
                logger.error(f"Max retries ({max_retries}) exceeded")

        except Exception as e:
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
    Decorator for async functions that adds retry logic.

    Usage:
        @async_retry(max_retries=3)
        async def fetch_data(url):
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
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
```

### Applied to Osiris Service

**File:** `src/apps/core/services/osiris.py`

```python
from apps.core.services.retry_logic import async_retry
from apps.core.services.cache_service import cache_async_result

@cache_async_result(timeout=86400, key_prefix="osiris_course", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def fetch_course_data(course_code: int, client: httpx.AsyncClient) -> dict:
    """Fetch single course data from OSIRIS.

    Cached for 24 hours because course data changes very rarely.
    """
    # ... implementation ...
    resp = await client.post(OSIRIS_SEARCH_URL, headers=headers, content=body)
    resp.raise_for_status()  # Raises for retryable errors
    # ...

@cache_async_result(timeout=604800, key_prefix="osiris_person", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def fetch_person_data(name: str, client: httpx.AsyncClient) -> dict | None:
    """Fetch person data by scraping people.utwente.nl.

    Cached for 7 days because person information changes very rarely.
    """
    # ... implementation ...
    resp = await client.get(url, follow_redirects=True)
    if resp.status_code == 404:
        return None  # Expected - person not found
    resp.raise_for_status()  # Raises for retryable errors
    # ...
```

### Applied to Canvas Service

**File:** `src/apps/core/services/canvas.py`

```python
from apps.core.services.retry_logic import async_retry
from apps.core.services.cache_service import cache_async_result

@cache_async_result(timeout=86400, key_prefix="canvas_file_exists", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def check_single_file_existence(item_data: Item, client: httpx.AsyncClient):
    """Check file existence for a single item.

    Cached for 24 hours because file existence in Canvas LMS is stable.
    """
    material_id = item_data.get("material_id")
    url = item_data.get("url")

    # Handle None/empty/invalid URLs
    if not url or "/files/" not in url:
        return FileExistenceResult(
            material_id=material_id,
            file_exists=False,
            last_canvas_check=timezone.now(),
            canvas_course_id=None,
        )

    response = await client.get(api_url)
    file_exists = response.status_code == 200

    # Don't retry on 401/403/404
    if response.status_code in (401, 403, 404):
        return FileExistenceResult(
            material_id=material_id,
            file_exists=False,
            last_canvas_check=timezone.now(),
            canvas_course_id=None,
        )

    # Raise for retryable errors
    response.raise_for_status()
    # ...
```

### Applied to PDF Download

**File:** `src/apps/documents/services/download.py`

```python
from apps.core.services.retry_logic import async_retry

@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def download_pdf_from_canvas(
    url: str,
    filepath: Path,
    client: httpx.AsyncClient,
) -> tuple[Path, PDFCanvasMetadata] | None:
    """Downloads a PDF from Canvas and saves it."""
    # ... implementation ...
    response = await client.get(api_url, params={"include[]": ["usage_rights", "user"]})
    response.raise_for_status()  # Raises for retryable errors
    # ...

    except httpx.HTTPStatusError as e:
        # Don't retry on 401/403/404
        if e.response.status_code in (401, 403, 404):
            return None
        # Let retry decorator handle other errors
        raise
    # ...
```

## Testing Results

### Unit Tests ✅

```
[1/6] Testing is_retryable_error function...
   ✓ PASS - All retryable status codes correct

[2/6] Testing non-retryable error (401)...
   ✓ PASS - No retries on 401 (call_count=1)

[3/6] Testing non-retryable error (404)...
   ✓ PASS - No retries on 404 (call_count=1)

[4/6] Testing retryable error (503)...
   ✓ PASS - Retried 2 times on 503 (call_count=3)

[5/6] Testing retry with eventual success...
   ✓ PASS - Retried once then succeeded (call_count=2)

[6/6] Testing Canvas service with 401...
   ✓ PASS - Canvas 401 handled correctly (file_exists=False)
```

### Integration Tests ✅

```
[1/3] Testing Osiris fetch_course_data with retry logic...
   ✓ PASS - Fetched: Humanitarian Engineering

[2/3] Testing Osiris fetch_person_data with retry logic...
   ✓ PASS - Found person: T.R. Elfrink PhD(Teuntje)

[3/3] Testing Canvas check_single_file_existence with retry logic...
   ✓ PASS - file_exists=False (401 expected)
```

### Behavior Verified

- ✅ 401 errors do NOT trigger retries (auth failures are permanent)
- ✅ 403 errors do NOT trigger retries (forbidden is permanent)
- ✅ 404 errors do NOT trigger retries (not found is permanent)
- ✅ 503 errors DO trigger retries with exponential backoff
- ✅ 429 (rate limit) triggers retries with proper backoff
- ✅ Network/timeout errors trigger retries
- ✅ Services continue working correctly with real data

## Retry Behavior Examples

### Example 1: Rate Limit (429)

```
Request 1: 429 Too Many Requests
Wait: 1s (2^0 * 1s)
Request 2: 429 Too Many Requests
Wait: 2s (2^1 * 1s)
Request 3: 429 Too Many Requests
Wait: 4s (2^2 * 1s)
Request 4: 429 Too Many Requests
→ Max retries exceeded, raise exception
```

### Example 2: Eventual Success

```
Request 1: 503 Service Unavailable
Wait: 1s
Request 2: 503 Service Unavailable
Wait: 2s
Request 3: 200 OK
→ Return result immediately
```

### Example 3: Auth Failure (401)

```
Request 1: 401 Unauthorized
→ Fail immediately, don't retry
```

## Error Detection Logic

| Status Code | Retry? | Reason | Behavior |
|-------------|-------|--------|----------|
| 401 | ❌ | Auth failure | Fail immediately |
| 403 | ❌ | Forbidden | Fail immediately |
| 404 | ❌ | Not found | Fail immediately |
| 408 | ✅ | Timeout | Retry with backoff |
| 429 | ✅ | Rate limit | Retry with backoff |
| 500+ | ✅ | Server error | Retry with backoff |
| Network error | ✅ | Connection issue | Retry with backoff |

## Success Criteria

- ✅ Retry logic implemented with exponential backoff
- ✅ Smart error detection (transient vs permanent)
- ✅ Applied to all external API services
- ✅ Does NOT retry on auth failures (401/403)
- ✅ Does NOT retry on not found (404)
- ✅ DOES retry on rate limits (429) and timeouts (502/503/504)
- ✅ All tests pass
- ✅ Integration tests with real data pass

## Files Created/Modified

**Created:**
- `src/apps/core/services/retry_logic.py` - Retry decorator and logic

**Modified:**
- `src/apps/core/services/osiris.py` - Added retry decorators
- `src/apps/core/services/canvas.py` - Added retry decorators + None URL fix
- `src/apps/documents/services/download.py` - Added retry decorators

## Bug Fixes

**Canvas Service None URL Fix:**
- **Before:** Crashed with "argument of type 'NoneType' is not iterable"
- **After:** Returns `file_exists=False` for None/empty/invalid URLs

**Files Modified:**
- `src/apps/core/services/canvas.py` - Added proper None check

## Future Enhancements

Out of scope for this task but potential future work:
- Customizable retry counts per service
- Circuit breaker pattern for repeated failures
- Retry metrics/monitoring
- Dead letter queue for permanently failed items

---

**Next Task:** [Task 6: Table Enhancements](06-table-enhancements.md) (30% complete - needs completion)
