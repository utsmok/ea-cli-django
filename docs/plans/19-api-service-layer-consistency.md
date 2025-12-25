# Task 19: API & Service Layer Consistency

## Overview

Fix API versioning, service layer violations in views, and add upload validation to ensure consistency across the codebase.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **MEDIUM** (Technical Debt)

## Issues Addressed

### 1. No API Versioning Strategy (Medium)

**Problem:** API routes have no version prefix (`/api/v1/`). Breaking changes will require all clients to update simultaneously.

**Files affected:**
- `src/apps/api/urls.py`

**Impact:** Difficult to evolve API without breaking existing clients.

### 2. Direct ORM Calls in Views Bypass Service Layer (Medium)

**File:** `src/apps/dashboard/views.py:241-243`

**Problem:**
```python
# Direct ORM query bypasses service layer
latest_result = EnrichmentResult.objects.filter(
    item__material_id=material_id
).order_by("-created_at").first()
```

**Impact:**
- Inconsistent caching
- Harder to test
- Violates documented architecture
- Business logic scattered

### 3. Missing Upload File Size Validation (High)

**File:** `src/apps/api/views.py:48-52`

**Problem:** No validation of uploaded file size before processing.

**Note:** This is also covered in Task 14 (Critical Bug Fixes), but including here for API completeness.

## Implementation Steps

### Step 1: Add API Versioning

**Option A: URL Path Versioning (Recommended)**

**File:** `src/apps/api/urls.py`

**Current structure:**
```python
urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("ingest/", views.trigger_ingest, name="trigger_ingest"),
    path("update-items/", views.api_update_items, name="update_items"),
]
```

**Updated with versioning:**
```python
app_name = "api"

urlpatterns = [
    # v1 API
    path("v1/", include([
        path("health/", views.health_check, name="health_check_v1"),
        path("ingest/", views.trigger_ingest, name="ingest_v1"),
        path("items/update/", views.api_update_items, name="update_items_v1"),
    ])),
]

# Maintain backwards compatibility with legacy routes (optional)
urlpatterns += [
    path("health/", views.redirect_to_v1_health, name="health_check"),
    path("ingest/", views.redirect_to_v1_ingest, name="trigger_ingest"),
    path("update-items/", views.redirect_to_v1_update, name="update_items"),
]
```

**Add redirect views:**

**File:** `src/apps/api/views.py`

```python
from django.http import HttpResponsePermanentRedirect

def redirect_to_v1_health(request):
    """Redirect legacy health endpoint to v1."""
    return HttpResponsePermanentRedirect("/api/v1/health/")

def redirect_to_v1_ingest(request):
    """Redirect legacy ingest endpoint to v1."""
    return HttpResponsePermanentRedirect("/api/v1/ingest/")

def redirect_to_v1_update(request):
    """Redirect legacy update endpoint to v1."""
    return HttpResponsePermanentRedirect("/api/v1/items/update/")
```

**Option B: Header-Based Versioning (Alternative)**

```python
from django.http import JsonResponse

class APIVersionMiddleware:
    """API version middleware using Accept header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check Accept header for version
        accept = request.META.get("HTTP_ACCEPT", "")
        if "application/vnd.api.v1+json" in accept:
            request.api_version = "v1"
        elif "application/vnd.api.v2+json" in accept:
            request.api_version = "v2"
        else:
            # Default to v1
            request.api_version = "v1"

        return self.get_response(request)
```

**Update settings:**

```python
MIDDLEWARE = [
    # ... existing middleware ...
    "apps.api.middleware.APIVersionMiddleware",
    "apps.api.middleware.RateLimitMiddleware",
]
```

### Step 2: Fix Direct ORM Calls in Views

**File:** `src/apps/dashboard/views.py:241-243`

**Current code:**
```python
# Direct ORM query
latest_result = EnrichmentResult.objects.filter(
    item__material_id=material_id
).order_by("-created_at").first()
```

**Fix - Move to service layer:**

**File:** `src/apps/dashboard/services/query_service.py`

**Add new method:**

```python
class ItemQueryService:
    # ... existing methods ...

    def get_latest_enrichment_result(self, material_id: int) -> EnrichmentResult | None:
        """
        Get the latest enrichment result for an item.

        Cached for 15 minutes.
        """
        cache_key = f"enrichment_result:{material_id}:latest"

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = EnrichmentResult.objects.filter(
            item__material_id=material_id
        ).order_by("-created_at").first()

        # Cache for 15 minutes
        cache.set(cache_key, result, timeout=60 * 15)

        return result
```

**Update view:**

**File:** `src/apps/dashboard/views.py:241-243`

```python
# Before:
# latest_result = EnrichmentResult.objects.filter(
#     item__material_id=material_id
# ).order_by("-created_at").first()

# After:
service = ItemQueryService()
latest_result = service.get_latest_enrichment_result(material_id)
```

**Audit for other violations:**

```bash
# Find all direct ORM calls in views
grep -r "objects.filter\|objects.get\|objects.all" src/apps/*/views.py | grep -v "service"
```

**Fix any other violations similarly.**

### Step 3: Add File Upload Validation (API)

**File:** `src/apps/api/views.py`

```python
from django.core.exceptions import ValidationError
from loguru import logger

# ... existing imports ...

# Constants
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def validate_upload_file(uploaded_file) -> tuple[bool, str | None]:
    """
    Validate uploaded file before processing.

    Returns:
        (is_valid, error_message)
    """
    if not uploaded_file:
        return False, "No file provided"

    # Check file size
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return False, f"File too large. Maximum size is {max_mb}MB"

    # Check file extension
    import os
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    if file_ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(ALLOWED_UPLOAD_EXTENSIONS)
        return False, f"Invalid file type. Allowed: {allowed}"

    return True, None


@require_POST
@login_required
def trigger_ingest(request: HttpRequest):
    """Trigger file ingestion with validation."""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return HttpResponseBadRequest("Missing 'file' upload")

    # Validate file
    is_valid, error_msg = validate_upload_file(uploaded)
    if not is_valid:
        logger.warning(f"Upload validation failed: {error_msg}")
        return HttpResponseBadRequest(error_msg)

    # Continue with processing...
```

**Add Django settings for upload limits:**

**File:** `src/config/settings.py`

```python
# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB in memory
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB request body
```

### Step 4: Create API Documentation

**File:** `src/apps/api/docs.md` (NEW)

```markdown
# Easy Access API Documentation

## Versioning

The API uses URL path versioning: `/api/v1/...`

## Base URL

```
Production: https://your-domain.com/api/v1/
Development: http://localhost:8000/api/v1/
```

## Endpoints

### Health Check

**GET** `/api/v1/health/`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "cache": "ok"
  }
}
```

### Ingest File

**POST** `/api/v1/ingest/`

Upload and process Qlik export or faculty sheet.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `file` field with Excel/CSV file

**Limits:**
- Max file size: 100MB
- Allowed extensions: `.xlsx`, `.xls`, `.csv`

**Response:**
```json
{
  "success": true,
  "batch_id": 123,
  "status": "processing"
}
```

### Update Items

**POST** `/api/v1/items/update/`

Bulk update copyright items.

**Request:**
```json
{
  "item_ids": [1234567, 1234568, 1234569],
  "workflow_status": "Done",
  "remarks": "Processed"
}
```

**Response:**
```json
{
  "success": true,
  "updated_count": 3,
  "errors": []
}
```

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error type",
  "detail": "Detailed error message",
  "status_code": 400
}
```

## Rate Limiting

- Authenticated users: 100 requests/hour
- Anonymous users: 1000 requests/hour

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Authentication

Most endpoints require authentication via Django session auth.

Include session cookie with requests.
```

### Step 5: Add API Tests

**File:** `src/apps/api/tests/test_api_consistency.py` (NEW)

```python
import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import io


class APIConsistencyTestCase(TestCase):
    """Test API consistency and validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

    def test_api_v1_endpoints_work(self):
        """Test v1 API endpoints are accessible."""
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)

    def test_legacy_endpoints_redirect(self):
        """Test legacy endpoints redirect to v1."""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 301)  # Permanent redirect

    def test_file_upload_rejects_large_files(self):
        """Test that large files are rejected."""
        # Create a fake 101MB file
        large_content = b"x" * (101 * 1024 * 1024)
        large_file = SimpleUploadedFile(
            "large.xlsx",
            large_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response = self.client.post("/api/v1/ingest/", {"file": large_file})

        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", response.json()["error"].lower())

    def test_file_upload_rejects_invalid_extensions(self):
        """Test that invalid file types are rejected."""
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"some text",
            content_type="text/plain"
        )

        response = self.client.post("/api/v1/ingest/", {"file": invalid_file})

        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid file type", response.json()["error"].lower())

    def test_file_upload_accepts_valid_files(self):
        """Test that valid files are accepted."""
        # Create a minimal xlsx file (just header)
        valid_file = SimpleUploadedFile(
            "test.xlsx",
            b"PK\x03\x04...",  # Actual xlsx content would go here
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response = self.client.post("/api/v1/ingest/", {"file": valid_file})

        # Should not return 400 (may return other status depending on processing)
        self.assertNotEqual(response.status_code, 400)
```

## Testing

### 1. Test API Versioning

```bash
# Test v1 endpoint
curl http://localhost:8000/api/v1/health/

# Test legacy redirect
curl -I http://localhost:8000/api/health/
# Expected: HTTP/1.1 301 Moved Permanently
# Location: /api/v1/health/
```

### 2. Test Upload Validation

```bash
# Test with file that's too large
dd if=/dev/zero of=large.xlsx bs=1M count=101
curl -X POST http://localhost:8000/api/v1/ingest/ \
  -F "file=@large.xlsx" \
  -H "Cookie: sessionid=..."

# Expected: 400 Bad Request with size error

# Test with invalid extension
echo "test" > test.txt
curl -X POST http://localhost:8000/api/v1/ingest/ \
  -F "file=@test.txt" \
  -H "Cookie: sessionid=..."

# Expected: 400 Bad Request with type error
```

### 3. Run Tests

```bash
uv run pytest src/apps/api/tests/test_api_consistency.py -v
```

## Success Criteria

- [ ] API versioning implemented (v1 endpoints)
- [ ] Legacy endpoints redirect to v1
- [ ] Direct ORM calls moved to service layer
- [ ] File upload validation added (size + extension)
- [ ] Upload limits configured in settings
- [ ] API documentation created
- [ ] API tests pass
- [ ] Service layer no longer violated
- [ ] Caching works correctly through service layer

## Files Created/Modified

- `src/apps/api/urls.py` - Add versioning (v1/)
- `src/apps/api/views.py` - Add redirect views, upload validation
- `src/apps/dashboard/views.py` - Remove direct ORM calls
- `src/apps/dashboard/services/query_service.py` - Add get_latest_enrichment_result
- `src/config/settings.py` - Add upload limits
- `src/apps/api/docs.md` - NEW: API documentation
- `src/apps/api/tests/test_api_consistency.py` - NEW: Tests

## Related Tasks

- **Task 12:** API Validation & Documentation (Shinobi schemas)
- **Task 14:** Critical Bug Fixes (upload validation overlap)
- **Task 16:** Production Readiness (rate limiting)

## Benefits

1. **API evolution** - Can add v2 without breaking v1 clients
2. **Service layer consistency** - All DB calls go through services
3. **Better caching** - Service layer caching applies consistently
4. **Testability** - Easier to mock service layer
5. **Documentation** - Clear API contract for consumers
6. **Security** - Upload validation prevents abuse

---

**End of New Tasks**
