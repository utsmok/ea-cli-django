# Task 20: Production Testing & Frontend Verification

## Overview

Add comprehensive tests for recently completed production features and implement automated frontend verification to ensure all routes work as expected.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)
**Created:** 2025-12-26

## Why This Task Is Needed

During the implementation of Tasks 8, 9, 10, 12, 14, 15, 16, and 18, some tests were added but critical gaps remain:

1. **Missing backend tests** for production-critical features
2. **No frontend verification** - changes to routes/views weren't tested in browser
3. **No integration tests** for the full request→response cycle
4. **No regression tests** to prevent future breakage

## Missing Tests

### 1. Security Settings Tests (Task 08)
**File:** `src/apps/settings/tests/test_security_validation.py` (NEW)

**Tests needed:**
- [ ] SECRET_KEY validation in production
- [ ] DEBUG=False enforcement
- [ ] ALLOWED_HOSTS validation (no wildcards in prod)
- [ ] Password validator enforcement (12 char min)
- [ ] HTTPS/HSTS settings validation
- [ ] Secure cookie settings validation

**Example test:**
```python
def test_production_requires_secure_settings(monkeypatch):
    """Test that production environment requires secure settings."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "")

    # Should raise error or use fallback with warning
    with pytest.warns(UserWarning):
        from django.conf import settings
        assert settings.SECRET_KEY is not None
        assert len(settings.SECRET_KEY) >= 50
```

### 2. Health Check Endpoint Tests (Task 16)
**File:** `src/apps/api/tests/test_health_checks.py` (NEW)

**Tests needed:**
- [ ] Health check returns 200 with service info
- [ ] Readiness check returns 200 when all services healthy
- [ ] Readiness check returns 503 when database unavailable
- [ ] Readiness check returns 200 when cache unavailable (degraded)
- [ ] Health checks work without authentication
- [ ] Response schemas match documentation

**Example test:**
```python
@pytest.mark.django_db
def test_health_check_returns_200(client):
    """Test health check endpoint returns 200."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
```

### 3. Rate Limiting Tests (Task 16)
**File:** `src/apps/dashboard/tests/test_rate_limiting.py` (NEW)

**Tests needed:**
- [ ] Rate limit enforced after threshold
- [ ] Rate limit resets after time window
- [ ] Rate limit key includes user ID
- [ ] Rate limit works for anonymous users (IP-based)
- [ ] Rate limiting bypassed for staff/admin (if applicable)
- [ ] Response includes rate limit headers

**Example test:**
```python
@pytest.mark.django_db
def test_rate_limit_enforced(client, django_user_model):
    """Test that rate limit is enforced."""
    user = django_user_model.objects.create_user(username="testuser")
    client.force_login(user)

    # Make 100 requests - should all succeed
    for _ in range(100):
        response = client.get("/dashboard/")
        assert response.status_code == 200

    # 101st request should be rate limited
    response = client.get("/dashboard/")
    assert response.status_code == 429
```

### 4. Transaction Rollback Tests (Task 15)
**File:** `src/apps/documents/tests/test_transactions.py` (NEW)

**Tests needed:**
- [ ] PDF download failure rolls back document creation
- [ ] Batch processor failure doesn't affect other items
- [ ] Atomic transaction decorator prevents partial saves
- [ ] Transaction error handling and logging
- [ ] Savepoint behavior for nested transactions

**Example test:**
```python
@pytest.mark.django_db
async def test_pdf_download_failure_rolls_back_document_creation():
    """Test that failed PDF download rolls back document creation."""
    from apps.core.models import CopyrightItem
    from apps.documents.services.download import create_or_link_document

    item = await CopyrightItem.objects.acreate(material_id=999999)

    # Mock file operation to fail
    with pytest.raises(Exception):
        await create_or_link_document(
            item,
            Path("/nonexistent/file.pdf"),
            mock_pdf_metadata
        )

    # Verify no document was created
    assert await CopyrightItem.objects.filter(material_id=999999).acount() == 1
    assert item.document is None
```

### 5. Async ORM Functionality Tests (Task 10)
**File:** `src/apps/documents/tests/test_async_orm.py` (NEW)

**Tests needed:**
- [ ] Native async ORM (aget, asave, aupdate_or_create) work correctly
- [ ] No sync_to_async used in critical paths
- [ ] Async operations don't block event loop
- [ ] Error handling in async context
- [ ] Performance characteristics (non-blocking)

**Example test:**
```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_native_async_orm_operations():
    """Test that native async ORM operations work."""
    from apps.core.models import CopyrightItem

    # Test acreate
    item = await CopyrightItem.objects.acreate(material_id=12345)
    assert item.material_id == 12345

    # Test aget
    fetched = await CopyrightItem.objects.aget(material_id=12345)
    assert fetched.id == item.id

    # Test asave
    item.filename = "test.pdf"
    await item.asave()

    # Test aupdate_or_create
    item2, created = await CopyrightItem.objects.aupdate_or_create(
        material_id=12345,
        defaults={"filename": "updated.pdf"}
    )
    assert not created
    assert item2.filename == "updated.pdf"
```

### 6. Database Index Performance Tests (Task 09)
**File:** `src/apps/core/tests/test_index_performance.py` (NEW)

**Tests needed:**
- [ ] Queries use indexes (check query plans)
- [ ] Performance improvements with indexes
- [ ] Composite indexes work correctly
- [ ] Index usage on Person.main_name

**Example test:**
```python
@pytest.mark.django_db
def test_course_code_index_used(django_assert_max_num_queries):
    """Test that course_code index is used for filtering."""
    # Create test data
    for i in range(100):
        CopyrightItem.objects.create(
            material_id=10000 + i,
            course_code=f"CS{i % 10}"
        )

    # Should use index - efficient query
    with django_assert_max_num_queries(1):
        items = list(CopyrightItem.objects.filter(course_code="CS5"))
        assert len(items) == 10
```

### 7. Frontend Route Verification (NEW)
**File:** `scripts/frontend_verification.sh` (NEW)

**Automated checks needed:**
- [ ] All step views load without errors
- [ ] Dashboard loads and displays data
- [ ] API endpoints respond correctly
- [ ] Health checks accessible
- [ ] HTMX interactions work (modal loading, etc.)
- [ ] No JavaScript errors in console
- [ ] No broken links or 404s
- [ ] Authentication flows work

**Implementation approach:**
```bash
#!/bin/bash
# Frontend verification script

BASE_URL="http://localhost:8000"
SCREENSHOT_DIR="screenshots/verification_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SCREENSHOT_DIR"

# Function to check endpoint
check_endpoint() {
    local url=$1
    local name=$2
    echo "Checking $name..."
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$STATUS" -eq 200 ]; then
        echo "✅ $name: $STATUS"
    else
        echo "❌ $name: $STATUS (expected 200)"
        return 1
    fi
}

# Check all main routes
check_endpoint "$BASE_URL/dashboard/" "Dashboard"
check_endpoint "$BASE_URL/steps/" "Steps Overview"
check_endpoint "$BASE_URL/steps/qlik_ingest/" "Qlik Ingest"
check_endpoint "$BASE_URL/steps/faculty_upload/" "Faculty Upload"
check_endpoint "$BASE_URL/steps/osiris_enrichment/" "Osiris Enrichment"
check_endpoint "$BASE_URL/steps/canvas_download/" "Canvas Download"
check_endpoint "$BASE_URL/steps/pdf_extraction/" "PDF Extraction"
check_endpoint "$BASE_URL/steps/faculty_export/" "Faculty Export"
check_endpoint "$BASE_URL/api/health/" "Health Check"
check_endpoint "$BASE_URL/api/readiness/" "Readiness Check"

echo "Frontend verification complete. Screenshots saved to $SCREENSHOT_DIR"
```

### 8. Integration Tests (NEW)
**File:** `src/apps/tests/test_integration.py` (NEW)

**End-to-end tests needed:**
- [ ] Full ingest → enrich → export pipeline
- [ ] User uploads file → processing → results visible
- [ ] API authentication → request → response
- [ ] WebSocket/HTMX live updates work
- [ ] Error handling and recovery

**Example test:**
```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_full_ingestion_pipeline(client, tmp_path):
    """Test complete ingestion pipeline."""
    from apps.ingest.services.processor import BatchProcessor

    # Upload file
    excel_file = create_test_excel_file(tmp_path)

    # Trigger ingestion
    response = client.post("/api/trigger_ingest/", {
        "file": excel_file
    })
    assert response.status_code == 200

    # Wait for processing
    await asyncio.sleep(2)

    # Verify results
    assert CopyrightItem.objects.filter(course_code="CS101").exists()
```

## Implementation Steps

### Step 1: Backend Unit Tests
1. Create `src/apps/settings/tests/test_security_validation.py`
2. Create `src/apps/api/tests/test_health_checks.py`
3. Create `src/apps/dashboard/tests/test_rate_limiting.py`
4. Create `src/apps/documents/tests/test_transactions.py`
5. Create `src/apps/documents/tests/test_async_orm.py`
6. Create `src/apps/core/tests/test_index_performance.py`

### Step 2: Frontend Verification Script
1. Create `scripts/frontend_verification.sh`
2. Add curl-based checks for all routes
3. Add screenshot capture functionality
4. Add JavaScript error detection
5. Create `screenshots/` .gitignore entry

### Step 3: Integration Tests
1. Create `src/apps/tests/test_integration.py`
2. Add end-to-end pipeline tests
3. Add multi-user interaction tests
4. Add error recovery tests

### Step 4: Run and Verify
1. Run all new tests: `uv run pytest src/apps/*/tests/ -v`
2. Run frontend verification: `bash scripts/frontend_verification.sh`
3. Fix any failures
4. Update documentation

## Success Criteria

- [ ] All backend tests pass (50+ new tests)
- [ ] Frontend verification script runs without errors
- [ ] All routes return 200 status
- [ ] No JavaScript console errors
- [ ] Integration tests pass
- [ ] Screenshots capture successfully
- [ ] Test coverage increases by at least 15%

## Files Created/Modified

### New Files
- `src/apps/settings/tests/test_security_validation.py`
- `src/apps/api/tests/test_health_checks.py`
- `src/apps/dashboard/tests/test_rate_limiting.py`
- `src/apps/documents/tests/test_transactions.py`
- `src/apps/documents/tests/test_async_orm.py`
- `src/apps/core/tests/test_index_performance.py`
- `src/apps/tests/test_integration.py`
- `scripts/frontend_verification.sh`
- `scripts/README.md` (documentation for verification scripts)
- `.gitignore` (add `screenshots/`)

### Modified Files
- `docs/plans/README.md` (add Task 20)
- `pytest.ini` (if needed for async test configuration)

## Estimated Effort

- Backend tests: 4-6 hours
- Frontend verification: 2-3 hours
- Integration tests: 3-4 hours
- **Total: 9-13 hours**

## Dependencies

- Requires server running (`./start-dev.sh` or `docker compose up`)
- Requires test database
- Requires headless browser (optional, for JS error detection)

## Related Tasks

- Builds on: Tasks 8, 9, 10, 12, 14, 15, 16, 18
- Enables: Task 13 (Test Coverage Expansion)
- Blocks: Production deployment until verified

## Notes

- Frontend verification can be run manually or in CI/CD
- Some tests may require mock external services (Osiris, Canvas)
- Integration tests may need test data fixtures
- Consider using Playwright or Selenium for deeper frontend testing

---

**Next Task:** Task 13: Test Coverage Expansion (extend coverage beyond these gaps)
