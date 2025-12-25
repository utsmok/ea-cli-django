# Task 5: Task Error Handling & API Validation

## Overview

Implement comprehensive error handling with retry logic, detailed error logging, API key validation, and better error visibility to frontend.

**Current Status:** ❌ **NOT STARTED**

**Current Issues:**
- Silent failures (errors logged but not shown to users)
- No retry logic for transient failures
- Canvas API key validation missing
- PDF file existence not properly set when file not found

## Implementation Steps

### Step 1: Create Error Hierarchy

**File:** `src/apps/enrichment/exceptions.py` (NEW)

```python
class EnrichmentError(Exception):
    """Base class for enrichment errors."""
    def __init__(self, message: str, item_id: int, recoverable: bool = True):
        self.message = message
        self.item_id = item_id
        self.recoverable = recoverable
        super().__init__(message)

    def __str__(self):
        return f"[{self.item_id}] {self.message}"


class APIConnectionError(EnrichmentError):
    """Network/API connection failure - retryable."""
    def __init__(self, message: str, item_id: int):
        super().__init__(message, item_id, recoverable=True)


class AuthenticationError(EnrichmentError):
    """API authentication failure - NOT retryable."""
    def __init__(self, message: str, item_id: int):
        super().__init__(message, item_id, recoverable=False)


class DataValidationError(EnrichmentError):
    """Invalid data from API - NOT retryable."""
    def __init__(self, message: str, item_id: int):
        super().__init__(message, item_id, recoverable=False)


class FileNotFoundError(EnrichmentError):
    """File not found in Canvas - permanent condition."""
    def __init__(self, message: str, item_id: int):
        super().__init__(message, item_id, recoverable=False)
```

### Step 2: Add Retry Logic with Exponential Backoff

**File:** `src/apps/enrichment/tasks.py`

```python
import asyncio
from loguru import logger
from .exceptions import EnrichmentError, APIConnectionError, AuthenticationError, DataValidationError

async def enrich_item_with_retry(
    item_id: int,
    batch_id: int = None,
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """Enrich item with exponential backoff retry."""

    for attempt in range(max_retries):
        try:
            await enrich_item(item_id, batch_id)
            return  # Success

        except AuthenticationError as e:
            # Don't retry auth failures
            logger.error(f"Authentication failed for item {item_id}: {e}")
            await mark_item_failed(item_id, batch_id, e.message, recoverable=False)
            return

        except DataValidationError as e:
            # Don't retry validation errors
            logger.warning(f"Data validation failed for item {item_id}: {e}")
            await mark_item_failed(item_id, batch_id, e.message, recoverable=False)
            return

        except APIConnectionError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"API connection failed for item {item_id}, "
                    f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"API connection failed for item {item_id} after {max_retries} attempts")
                await mark_item_failed(item_id, batch_id, e.message, recoverable=True)

        except Exception as e:
            logger.exception(f"Unexpected error enriching item {item_id}")
            await mark_item_failed(item_id, batch_id, str(e), recoverable=False)


async def mark_item_failed(
    item_id: int,
    batch_id: int,
    error_message: str,
    recoverable: bool
):
    """Mark item as failed with detailed error info."""
    from django.utils import timezone
    from apps.enrichment.models import EnrichmentResult
    from apps.core.models import CopyrightItem

    # Update item status
    await CopyrightItem.objects.filter(material_id=item_id).aupdate(
        enrichment_status='failed',
        last_enrichment_attempt=timezone.now()
    )

    # Update result if tracking
    if batch_id:
        result = await EnrichmentResult.objects.filter(id=batch_id).afirst()
        if result:
            result.status = EnrichmentResult.Status.FAILURE
            result.error_message = error_message
            result.recoverable = recoverable
            result.retry_after = timezone.now() + timezone.timedelta(hours=1) if recoverable else None
            await result.asave()
```

### Step 3: Fix Canvas File Existence Logic

**File:** `src/apps/core/services/canvas.py`

```python
import httpx
from django.conf import settings
from django.utils import timezone
from loguru import logger

from apps.enrichment.exceptions import AuthenticationError, APIConnectionError


async def check_single_file_existence(item_data: dict, client: httpx.AsyncClient) -> dict:
    """Check file existence with proper error handling."""

    material_id = item_data.get("material_id")
    url = item_data.get("url", "")

    try:
        if "/files/" not in url:
            logger.warning(f"Invalid URL format for material_id {material_id}: {url}")
            return {
                'material_id': material_id,
                'file_exists': False,  # Explicit False
                'last_canvas_check': timezone.now(),
                'canvas_course_id': None,
            }

        file_id = url.split("/files/")[1].split("/")[0].split("?")[0]
        api_url = f"{settings.CANVAS_API_URL}/files/{file_id}"

        try:
            response = await client.get(api_url)

            if response.status_code == 404:
                # File not found - set to False and don't retry
                logger.info(f"File not found for material_id {material_id}: {file_id}")
                return {
                    'material_id': material_id,
                    'file_exists': False,  # Explicit False - prevents future checks
                    'last_canvas_check': timezone.now(),
                    'canvas_course_id': None,
                }

            response.raise_for_status()
            file_data = response.json()

            # Extract course ID from folder_id
            canvas_course_id = None
            folder_id = file_data.get("folder_id")
            if folder_id:
                canvas_course_id = await determine_course_id_from_folder(folder_id, client)

            return {
                'material_id': material_id,
                'file_exists': True,
                'last_canvas_check': timezone.now(),
                'canvas_course_id': canvas_course_id,
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid Canvas API token", material_id)
            elif e.response.status_code == 429:
                # Rate limited - retryable
                raise APIConnectionError(f"Canvas rate limit exceeded: {e}", material_id)
            else:
                logger.error(f"HTTP error checking file for material_id {material_id}: {e}")
                return {
                    'material_id': material_id,
                    'file_exists': None,  # Unknown on error
                    'last_canvas_check': timezone.now(),
                    'canvas_course_id': None,
                }

        except httpx.TimeoutException as e:
            raise APIConnectionError(f"Canvas API timeout: {e}", material_id)

    except AuthenticationError:
        raise  # Re-raise authentication errors
    except APIConnectionError:
        raise  # Re-raise connection errors
    except Exception as e:
        logger.error(f"Unexpected error checking file existence for material_id {material_id}: {e}")
        return {
            'material_id': material_id,
            'file_exists': None,  # Unknown on error
            'last_canvas_check': timezone.now(),
            'canvas_course_id': None,
        }
```

### Step 4: Enhance Error Model

**File:** `src/apps/enrichment/models.py`

```python
class EnrichmentResult(models.Model):
    """Track enrichment batch results."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        FAILURE = 'failure', 'Failure'
        PARTIAL = 'partial', 'Partial'

    # ... existing fields ...

    # New error fields
    error_message = models.CharField(max_length=500, null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True)
    recoverable = models.BooleanField(default=True)
    retry_after = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    @property
    def can_retry(self) -> bool:
        """Whether this enrichment can be retried."""
        return (
            self.recoverable and
            self.retry_count < 3 and
            (self.retry_after is None or self.retry_after <= timezone.now())
        )
```

### Step 5: Add Frontend Error Display

**File:** `src/templates/enrichment/_result_row.html`

```django
<tr class="{{ result.status|lower }}">
  <td>{{ result.item_id }}</td>
  <td>
    {% if result.status == 'SUCCESS' %}
      <span class="badge badge-success">Success</span>
    {% elif result.status == 'FAILURE' %}
      <div class="text-error">
        <span class="badge badge-error">Failed</span>
        {% if result.error_message %}
          <p class="text-xs mt-1">{{ result.error_message }}</p>
        {% endif %}
        {% if result.can_retry %}
          <button hx-post="{% url 'enrichment:retry_result' result.id %}"
                  hx-confirm="Retry this enrichment?"
                  class="btn btn-xs btn-outline mt-2">
            Retry
          </button>
        {% endif %}
      </div>
    {% elif result.status == 'PARTIAL' %}
      <div class="text-warning">
        <span class="badge badge-warning">Partial</span>
        {% if result.error_message %}
          <p class="text-xs mt-1">{{ result.error_message }}</p>
        {% endif %}
      </div>
    {% endif %}
  </td>
  <td>{{ result.created_at }}</td>
</tr>
```

### Step 6: Add Retry View

**File:** `src/apps/enrichment/views.py`

```python
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import EnrichmentResult

@login_required
def retry_result(request, result_id: int):
    """Retry a failed enrichment."""
    result = get_object_or_404(EnrichmentResult, id=result_id)

    if not result.can_retry:
        return JsonResponse({'success': False, 'error': 'Cannot retry this result'})

    # Reset for retry
    result.status = EnrichmentResult.Status.PENDING
    result.retry_count += 1
    result.error_message = None
    result.save()

    # Trigger enrichment task
    from .tasks import enrich_item_with_retry
    enrich_item_with_retry.delay(result.item_id, result.id)

    return JsonResponse({'success': True, 'message': 'Retry started'})
```

**File:** `src/apps/enrichment/urls.py`

```python
urlpatterns = [
    # ... existing ...
    path('retry/<int:result_id>', views.retry_result, name='retry_result'),
]
```

### Step 7: Integrate with Settings (Task 3)

Once Task 3 is complete, add API key validation to the settings UI.

**File:** `src/apps/settings/services/api_validator.py`

```python
async def test_canvas_api(api_key: str, api_url: str) -> dict:
    """Test Canvas API credentials."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/courses",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )

            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'message': 'Valid credentials' if response.status_code == 200 else 'Authentication failed',
                'can_access_courses': response.status_code == 200,
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }
```

## Testing

### Unit Tests

**File:** `src/apps/enrichment/tests/test_error_handling.py` (NEW)

```python
import pytest
from apps.enrichment.exceptions import (
    APIConnectionError, AuthenticationError, DataValidationError
)
from apps.enrichment.tasks import enrich_item_with_retry

@pytest.mark.django_db
class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_auth_error_no_retry(self):
        """Test that auth errors are not retried."""
        # ... test implementation ...

    @pytest.mark.asyncio
    async def test_api_connection_retry_with_backoff(self):
        """Test that connection errors are retried with exponential backoff."""
        # ... test implementation ...
```

## Success Criteria

- [ ] Error hierarchy created (EnrichmentError subclasses)
- [ ] Retry logic implemented with exponential backoff
- [ ] Canvas file existence correctly sets False when 404
- [ ] Error model enhanced with recoverable/retry_after/can_retry
- [ ] Frontend displays specific error messages
- [ ] Retry button shown when appropriate
- [ ] Tests cover all error scenarios
- [ ] Integration with settings API validation (after Task 3)

## Estimated Time

- **Error hierarchy:** 2 hours
- **Retry logic:** 4 hours
- **Canvas fixes:** 4 hours
- **Model enhancements:** 2 hours
- **Frontend error display:** 3 hours
- **Testing:** 4 hours

**Total: 2-3 days**

---

**Next Task:** [Task 6: Table Enhancements](06-table-enhancements.md)
