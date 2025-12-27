# Testing Implementation Plan: Phases 4 & 5 + URL Test Fixes

**Created**: 2025-12-27
**Status**: ✅ COMPLETE
**Session**: dev-environment
**Completed**: 2025-12-27

## Overview

Complete the comprehensive test suite for the Django Copyright Compliance Platform by implementing:
- Phase 4: Backend Response Test Suite (~50 tests)
- Fix 37 failing URL/endpoint tests from Phase 3
- Phase 5: Playwright UI Test Suite (~30 tests)

**Context from Previous Phases:**
- Phase 1: Test Infrastructure ✅ Complete
- Phase 2: E2E Pipeline Tests ✅ Complete (8 tests passing)
- Phase 3: URL/Endpoint Tests ⚠️ Complete but 37/96 tests failing

## Current State

From handoff `2025-12-27_00-05-36_phase-3-url-endpoint-tests-complete.md`:

**Phase 3 Results:**
- 96 URL/endpoint tests created
- 59 tests PASSING
- 37 tests FAILING

**Failure Categories:**
1. Unimplemented view methods (18 tests)
2. Different auth expectations (8 tests)
3. Missing fixtures or data (6 tests)
4. Wrong test expectations (5 tests)

## Plan

### Phase 4: Backend Response Test Suite (~50 tests)

**Goal**: Verify HTTP layer behavior - status codes, headers, JSON schemas, HTMX responses.

**Tasks:**

1. **Create `src/tests/test_backend_responses.py`**
   - Test HTTP status codes (200, 201, 204, 400, 403, 404, 500)
   - Verify JSON schemas for API endpoints
   - Test validation error messages
   - Verify HTMX-specific headers (HX-Trigger, HX-Redirect, HX-Refresh)
   - Test response content types (JSON vs HTML)
   - Verify database state changes after requests

2. **Test Coverage by App:**
   - `dashboard/`: POST endpoints, filtering, pagination
   - `ingest/`: File upload, batch operations
   - `enrichment/`: Enrichment triggers, status checks
   - `api/`: All API v1 endpoints
   - `steps/`: Step transitions, bulk operations

3. **HTMX Behavior Testing:**
   - HX-Trigger headers for client-side events
   - HX-Redirect for navigation
   - HX-Refresh for page reloads
   - Polling behavior for async operations

**Success Criteria:**
- All backend response tests pass
- HTMX headers properly verified
- JSON schemas validated
- Database state changes verified

**Files to Create:**
- `src/tests/test_backend_responses.py` (500+ lines)

### Task: Fix 37 Failing URL Tests (from Phase 3)

**Goal**: Fix failing tests from Phase 3 to increase test pass rate.

**Tasks:**

1. **Categorize Failures** (Run tests and categorize):
   ```bash
   uv run pytest src/apps/*/tests/test_urls*.py -v 2>&1 | grep FAILED
   ```

2. **Fix by Category:**

   **A. Unimplemented Views (18 tests)**
   - Check if view exists in views.py
   - If missing: either implement or mark test as xfail/skip
   - Document why view is unimplemented

   **B. Auth Expectations (8 tests)**
   - Tests expect 403 but get 302 redirect
   - Fix test to expect redirect to login
   - Or add proper authentication

   **C. Missing Fixtures (6 tests)**
   - Add required fixtures to conftest.py
   - Create test data in test setup

   **D. Wrong Expectations (5 tests)**
   - Verify actual behavior is correct
   - Update test assertions

3. **Update Phase 3 Test Files:**
   - `src/apps/dashboard/tests/test_urls_comprehensive.py`
   - `src/apps/ingest/tests/test_urls_comprehensive.py`
   - `src/apps/enrichment/tests/test_urls_comprehensive.py`
   - `src/apps/api/tests/test_urls_comprehensive.py`
   - `src/apps/steps/tests/test_urls_comprehensive.py`

**Success Criteria:**
- Reduce failing tests from 37 to <10
- Document why any remaining failures exist
- All new tests have proper fixtures

### Phase 5: Playwright UI Test Suite (~30 tests)

**Goal**: End-to-end browser testing with visual regression.

**Tasks:**

1. **Install Playwright** (if not already installed):
   ```bash
   uv add --group playwright pytest-playwright playwright
   uv run playwright install chromium
   ```

2. **Create `src/tests/playwright/` Directory:**
   ```
   src/tests/playwright/
   ├── conftest.py           # Playwright fixtures
   ├── test_dashboard_ui.py  # Dashboard browsing, filtering
   ├── test_ingestion_ui.py  # File upload, batch processing
   ├── test_steps_ui.py      # Step navigation, transitions
   └── test_visual_regression.py  # Screenshot comparisons
   ```

3. **Test Scenarios:**

   **Dashboard UI (8 tests):**
   - Login and logout
   - Browse items by faculty
   - Filter by classification
   - Search functionality
   - Pagination
   - Item detail view
   - Update classification
   - Export triggers

   **Ingestion UI (7 tests):**
   - Upload Qlik file
   - View batch status
   - Process batch
   - View staged data
   - Upload faculty sheet
   - View processing errors
   - Navigate to export

   **Steps UI (10 tests):**
   - Step 1: Ingest Qlik Export
   - Step 2: Ingest Faculty Sheet
   - Step 3: Enrich from Osiris
   - Step 5: Get PDF Status
   - Step 6: Extract PDF Details
   - Step 7: Export Faculty Sheets
   - Step navigation transitions
   - Bulk operations
   - Status indicators
   - Progress displays

   **Visual Regression (5 tests):**
   - Dashboard layout
   - Table rendering
   - Form layouts
   - Modal dialogs
   - Responsive design

4. **Configure Playwright:**
   - Use `pytest.ini` marker `@pytest.mark.playwright`
   - Skip by default (already configured: `-m "not playwright"`)
   - Screenshot directory: `test_screenshots/`
   - Base URL: http://localhost:8000 (requires running server)

**Success Criteria:**
- All Playwright tests pass
- Visual regression baseline established
- Screenshots saved for manual review

**Files to Create:**
- `src/tests/playwright/conftest.py`
- `src/tests/playwright/test_dashboard_ui.py`
- `src/tests/playwright/test_ingestion_ui.py`
- `src/tests/playwright/test_steps_ui.py`
- `src/tests/playwright/test_visual_regression.py`

## Implementation Order

**Recommended Sequence:**

1. **Fix URL Tests First** (quickest win, ~2-3 hours)
   - Run tests and categorize failures
   - Fix by category
   - Verify fixes

2. **Phase 4: Backend Response Tests** (medium complexity, ~4-6 hours)
   - Create test file structure
   - Implement tests per app
   - Verify all pass

3. **Phase 5: Playwright Tests** (most complex, ~6-8 hours)
   - Install dependencies
   - Create test structure
   - Implement UI tests
   - Establish visual regression baseline

## Testing Strategy

### Run Commands

```bash
# Fix URL tests
uv run pytest src/apps/*/tests/test_urls*.py -v

# Phase 4: Backend response tests
uv run pytest src/tests/test_backend_responses.py -v -m htmx
uv run pytest src/tests/test_backend_responses.py -v -m api

# Phase 5: Playwright tests (requires server running)
# Terminal 1: Start server
uv run python src/manage.py runserver

# Terminal 2: Run Playwright tests
uv run pytest src/tests/playwright/ -v -m playwright

# Run all new tests
uv run pytest -m "not slow" --cov=src/apps --cov-report=html
```

### Fixtures Location

Add shared fixtures to:
- `src/conftest.py` - Already exists, add new fixtures here
- `src/tests/playwright/conftest.py` - Playwright-specific fixtures

### Mock Strategy

- **Use mocks for**: External APIs (Osiris, Canvas) in non-external_api tests
- **Use real calls for**: Tests marked with `@pytest.mark.external_api`
- **Mock database transactions**: Where safe to do so

## Verification

After each phase:

1. **Run Tests**: `uv run pytest <phase_tests> -v`
2. **Check Coverage**: `uv run pytest --cov=src/apps --cov-report=term-missing`
3. **Manual Testing**: For UI features, verify manually
4. **Documentation**: Update TESTING.md with new test patterns

## Success Metrics

**Overall Test Suite Targets:**
- Total tests: 400+ (from current 282)
- Pass rate: >95%
- Coverage: >80%

**By Phase:**
- URL Tests (Phase 3): 96 tests, >90% passing (from 61%)
- Backend Response (Phase 4): 50 tests, 100% passing
- Playwright (Phase 5): 30 tests, 100% passing

## Files to Modify

**New Files:**
- `src/tests/test_backend_responses.py`
- `src/tests/playwright/conftest.py`
- `src/tests/playwright/test_dashboard_ui.py`
- `src/tests/playwright/test_ingestion_ui.py`
- `src/tests/playwright/test_steps_ui.py`
- `src/tests/playwright/test_visual_regression.py`

**Modify Files:**
- `src/conftest.py` - Add new fixtures
- `src/apps/*/tests/test_urls_comprehensive.py` - Fix failing tests
- `pyproject.toml` - Add playwright dependencies if needed
- `TESTING.md` - Document new test patterns
- `.gitignore` - Add `test_screenshots/` (check if already there)

## Notes

- **Skip Playwright by default**: Already configured in pytest.ini
- **Server required for Playwright**: Tests need `runserver` running
- **Slow tests**: Mark with `@pytest.mark.slow` for long-running operations
- **External API tests**: Mark with `@pytest.mark.external_api` for real API calls
- **HTMX tests**: Mark with `@pytest.mark.htmx` for HTMX-specific behavior

## Handoff Chain

This is the implementation plan. Agent orchestration will be used for execution.
