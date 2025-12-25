# Task 14: Critical Bug Fixes

## Overview

Fix critical bugs that prevent core functionality from working correctly or cause data integrity issues.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **CRITICAL** (Fix Immediately)

## Issues Addressed

### 1. Path.open() Bug in PDF Download Service (Critical)

**File:** `src/apps/documents/services/download.py:125`

**Problem:**
```python
# Line 125 - BROKEN CODE
with Path.open(filepath, "wb") as f:
    async for chunk in file_response.aiter_bytes():
        f.write(chunk)
```

The code uses `Path.open()` as a static method instead of calling it on the Path instance. This will raise:
```
TypeError: Path.open() missing 1 required positional argument: 'self'
```

**Impact:** PDF download functionality is completely broken. This suggests the feature has never been tested end-to-end.

**Fix:**
```python
# Correct usage - call on instance
with filepath.open("wb") as f:
    async for chunk in file_response.aiter_bytes():
        f.write(chunk)
```

### 2. Race Condition in Dashboard Enrichment Trigger (Critical)

**File:** `src/apps/dashboard/views.py:280-283`

**Problem:**
```python
if needs_enrichment and not is_enriching:
    # Status updated BEFORE task enqueue
    data.item.enrichment_status = EnrichmentStatus.RUNNING
    data.item.save(update_fields=["enrichment_status"])

    # If THIS fails, status is stuck in RUNNING
    enrich_item.enqueue(material_id, batch_id=batch.id, result_id=result.id)
```

The enrichment status is updated synchronously before the async task is enqueued. If the enqueue operation fails (network issue, RQ worker down, etc.), the item remains stuck in `RUNNING` state forever.

**Impact:** Items get permanently stuck in RUNNING state, requiring manual intervention.

**Fix:**
```python
if needs_enrichment and not is_enriching:
    try:
        # Enqueue first, update status on success
        enrich_job = enrich_item.enqueue(
            material_id,
            batch_id=batch.id,
            result_id=result.id
        )

        # Only update status if enqueue succeeded
        data.item.enrichment_status = EnrichmentStatus.RUNNING
        data.item.save(update_fields=["enrichment_status"])
    except Exception as e:
        logger.error(f"Failed to enqueue enrichment for item {material_id}: {e}")
        # Status remains PENDING, can be retried
        return JsonResponse({
            "error": "Failed to start enrichment",
            "detail": str(e)
        }, status=503)
```

**Alternative:** Move the status update inside the task itself (first operation).

### 3. Duplicate filehash Field (Reference to Task 09)

**File:** `src/apps/documents/models.py:95, 112`

**Status:** Already documented in Task 09 (Database Schema & Indexes)

The Document model has a duplicate `filehash` field definition with conflicting constraints. This is a **critical schema issue** that must be fixed.

**Action:** See Task 09 for detailed fix.

### 4. Missing File Size Validation on Upload (High)

**File:** `src/apps/api/views.py:48-52`

**Problem:**
```python
@require_POST
def trigger_ingest(request: HttpRequest):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return HttpResponseBadRequest("Missing 'file' upload")
    # No size validation - could accept gigabyte files
```

No validation of uploaded file size before processing. Accepting arbitrarily large files can cause:
- Memory exhaustion
- Disk space exhaustion
- DoS vulnerabilities

**Fix:**
```python
@require_POST
def trigger_ingest(request: HttpRequest):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return HttpResponseBadRequest("Missing 'file' upload")

    # Validate file size (max 100MB)
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
    if uploaded.size > MAX_UPLOAD_SIZE:
        return HttpResponseBadRequest(
            f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB"
        )

    # Validate file extension
    allowed_extensions = {".xlsx", ".xls", ".csv"}
    import os
    if os.path.splitext(uploaded.name)[1].lower() not in allowed_extensions:
        return HttpResponseBadRequest(
            f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Continue processing...
```

**Additional:** Configure Django's `FILE_UPLOAD_MAX_MEMORY_SIZE` in settings:

```python
# src/config/settings.py
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB in memory
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB request body
```

## Implementation Steps

### Step 1: Fix Path.open() Bug

**File:** `src/apps/documents/services/download.py`

**Line 125:**
```python
# BEFORE
with Path.open(filepath, "wb") as f:

# AFTER
with filepath.open("wb") as f:
```

**Test:**
```python
# Test PDF download actually works
import asyncio
from apps.documents.services.download import download_pdf_from_canvas

async def test():
    # This should work after fix
    result = await download_pdf_from_canvas(
        url="https://example.com/file.pdf",
        filepath=Path("/tmp/test.pdf"),
        client=httpx.AsyncClient()
    )
    print(f"Download result: {result}")

asyncio.run(test())
```

### Step 2: Fix Enrichment Race Condition

**File:** `src/apps/dashboard/views.py`

**Update the enrichment trigger logic (around line 280-283):**

```python
if needs_enrichment and not is_enriching:
    try:
        # Enqueue first, update status on success
        enrich_job = enrich_item.enqueue(
            material_id,
            batch_id=batch.id,
            result_id=result.id
        )

        # Only update status if enqueue succeeded
        data.item.enrichment_status = EnrichmentStatus.RUNNING
        data.item.save(update_fields=["enrichment_status"])

        logger.info(
            f"Successfully enqueued enrichment for item {material_id}, "
            f"job ID: {enrich_job.id}"
        )
    except Exception as e:
        logger.exception(f"Failed to enqueue enrichment for item {material_id}")
        return JsonResponse({
            "error": "Failed to start enrichment",
            "detail": str(e)
        }, status=503)
```

### Step 3: Add File Size Validation

**Files:**
- `src/apps/api/views.py` - Add validation to trigger_ingest()
- `src/config/settings.py` - Configure upload limits

### Step 4: Add Tests for Bugs

**File:** `src/apps/documents/tests/test_download_bugfixes.py` (NEW)

```python
import pytest
from pathlib import Path
from apps.documents.services.download import download_pdf_from_canvas

@pytest.mark.asyncio
async def test_path_open_fix():
    """Test that Path.open is called correctly on instance."""
    # This test should pass after the fix
    # Before fix, this would raise TypeError
    test_path = Path("/tmp/test_download.pdf")

    # Mock the actual download, just test file operations
    # ...
```

## Testing

### 1. Test PDF Download

```bash
# Test that PDF download works end-to-end
uv run python src/manage.py shell

from apps.documents.services.download import download_undownloaded_pdfs
from apps.dashboard.services.query_service import ItemQueryService
import asyncio

async def test():
    service = ItemQueryService()
    # Get items needing PDF download
    filters = ItemQueryFilter(file_exists=False)
    result = await service.get_paginated_items(filters, limit=1)

    if result.items:
        import httpx
        async with httpx.AsyncClient() as client:
            downloaded = await download_undownloaded_pdfs(client, result.items)
            print(f"Downloaded: {downloaded}")

asyncio.run(test())
```

### 2. Test Enrichment Trigger

```bash
# Test enrichment doesn't get stuck on RQ failure
# 1. Stop RQ worker
# 2. Trigger enrichment via UI
# 3. Verify status remains PENDING (not stuck in RUNNING)
# 4. Check error message is shown
```

### 3. Test File Upload Validation

```bash
# Test with curl
# Try uploading file larger than 100MB - should be rejected
curl -X POST http://localhost:8000/api/ingest/ \
  -F "file=@large_file.xlsx" \
  -H "Authorization: Token ..."

# Expected: 400 Bad Request with size error message
```

## Success Criteria

- [ ] Path.open() bug fixed (filepath.open("wb"))
- [ ] Enrichment status no longer gets stuck in RUNNING
- [ ] File upload size validation added (100MB max)
- [ ] File extension validation added
- [ ] Django upload limits configured in settings
- [ ] PDF download tested end-to-end
- [ ] Enrichment trigger tested with RQ worker stopped
- [ ] Upload validation tested with large files
- [ ] Tests added for bug fixes

## Files Modified

- `src/apps/documents/services/download.py` - Fix Path.open() usage
- `src/apps/dashboard/views.py` - Fix enrichment race condition
- `src/apps/api/views.py` - Add file size validation
- `src/config/settings.py` - Add upload limits
- `src/apps/documents/tests/test_download_bugfixes.py` - NEW: Tests

## Related Tasks

- **Task 09:** Database Schema & Indexes (duplicate filehash field)
- **Task 15:** Transaction Management (related data integrity issues)

## Benefits

1. **PDF download actually works** - Core feature functional
2. **No stuck enrichments** - Items can be retried on failure
3. **DoS protection** - Upload size limits prevent abuse
4. **Better error messages** - Users see actionable feedback

---

**Next Task:** [Task 15: Transaction Management](15-transaction-management.md)
