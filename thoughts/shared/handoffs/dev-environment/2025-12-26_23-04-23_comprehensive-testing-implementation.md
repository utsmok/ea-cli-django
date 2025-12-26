---
date: 2025-12-26T23:04:23+00:00
session_name: dev-environment
researcher: Claude
git_commit: ea1ab29b5a02afff76ab2bae0c46da618abbfb83
branch: main
repository: ea-cli-django
topic: "Comprehensive Testing Implementation for Django Copyright Compliance Platform"
tags: [testing, pytest, infrastructure, e2e, playwright, test-coverage]
status: in_progress
last_updated: 2025-12-26
last_updated_by: Claude
type: implementation_strategy
root_span_id:
turn_span_id:
---

# Handoff: Comprehensive Testing Infrastructure Implementation

## Task(s)

**Overall Goal**: Transform the test suite from 168 mock-heavy unit tests to 400+ comprehensive tests that verify actual system behavior, including end-to-end pipeline tests, URL coverage, backend response verification, and Playwright UI tests.

### Completed Tasks

✅ **Phase 1: Test Infrastructure Setup (COMPLETE)**
- Created central test configuration with shared fixtures
- Updated pytest.ini with markers and improved configuration
- Created .env.test for test environment configuration
- Updated .gitignore for test artifacts
- Added test dependencies (pytest-xdist, pytest-html, pytest-playwright)
- Created test data generation script
- Generated `test_data/e2e/base_case_5.xlsx` with 5 representative items
- Verified existing tests still pass (32 passed, 1 pre-existing failure)

### In Progress

🔄 **Phase 2: Base Case Pipeline Test Suite (PENDING)**
- Create `src/apps/core/tests/test_e2e_pipeline.py` with 8 pipeline tests
- Test all 7 steps of the processing pipeline with REAL external APIs
- Verify complete workflow: ingest → enrich → PDF → export

### Planned Tasks

📋 **Phase 3: Comprehensive URL/Endpoint Test Suite**
- Create URL discovery script to enumerate all 41+ endpoints
- Test authentication, permissions, errors, and form submissions
- Target: 200+ endpoint tests

📋 **Phase 4: Backend Response Test Suite**
- Create curl-like HTTP tests for status codes, headers, DB state
- Test HTMX-specific behaviors (HX-Trigger, HX-Redirect, polling)
- Target: 50+ HTTP layer tests

📋 **Phase 5: Playwright UI Test Suite**
- Install and configure Playwright
- Create browser automation tests for dashboard, ingestion, steps UI
- Implement visual regression screenshots
- Target: 30+ browser UI tests

## Critical References

1. **Implementation Plan**: `/home/sam/.claude/plans/snuggly-orbiting-gray.md`
   - Complete 4-phase testing strategy
   - File creation checklist (18 new files)
   - Test execution commands and success criteria

2. **Continuity Ledger**: `thoughts/ledgers/CONTINUITY_CLAUDE-dev-environment.md`
   - Current project state and working set
   - Key decisions and constraints

3. **Test Infrastructure**: `src/conftest.py`
   - Central fixtures for all tests
   - User management (admin, staff, faculty)
   - External API credential fixtures
   - Pytest marker definitions

## Recent Changes

### Created Files

- `src/conftest.py` - Central pytest configuration with shared fixtures (170 lines)
- `.env.test` - Test environment configuration with external API credential placeholders
- `test_data/e2e/base_case_5.xlsx` - Small test dataset with 5 representative items (8.5KB)
- `scripts/create_test_data.py` - Python script to generate base_case_5.xlsx from full Qlik export

### Modified Files

- `pytest.ini:7-23` - Added pytest markers (slow, external_api, pipeline, htmx, playwright), skip Playwright by default, strict marker enforcement
- `pyproject.toml:52-55` - Added test dependencies: pytest-xdist, pytest-html, pytest-playwright, playwright
- `.gitignore:22-48` - Added test artifacts (test_screenshots/, playwright-report/, pytest-results/), made test_data/e2e/ commit-able

## Learnings

### Project Architecture

**7-Step Processing Pipeline:**
1. Ingest Qlik Export (Excel → Database)
2. Ingest Faculty Sheet (human updates)
3. Enrich from Osiris (external API)
4. Enrich from People Pages (merged with Step 3)
5. Get PDF Status from Canvas (external API)
6. Extract PDF Details (OCR/PDF parsing)
7. Export Faculty Sheets (Excel output)

**Key Discovery**: During testing, tasks automatically use `ImmediateBackend` (synchronous execution) instead of RQ when `IS_TESTING=True`. This is a feature, not a bug - allows testing task logic without worker.

### Test Data Structure

**Column Names in Qlik Export:**
- "Material id", "Department", "Course code", "Filetype", "Classification"
- Note: Different from model field names (material_id, faculty, etc.)

**Test Data Generation Strategy:**
- Full qlik_data.xlsx has 1575 rows (225KB)
- Created pragmatic sampling strategy: select items from different positions (0%, 25%, 50%, 75%, 100%) to ensure diversity
- Resulting base_case_5.xlsx covers multiple departments and course codes

### Current Test State

**Baseline**: 168 tests, 93.5% passing rate
- Strengths: Model tests, API validation, authentication tests, async ORM tests
- Gaps: POST endpoints untested, background tasks not properly tested, no E2E pipeline tests
- Pre-existing failures: 11 tests (6.5%), mostly in documents/transactions and enrichment/tasks

## Post-Mortem

### What Worked

✅ **Centralized Fixtures Approach**
- Creating `src/conftest.py` with shared fixtures eliminated code duplication
- User fixtures (admin_user, staff_user, faculty_user) enable comprehensive permission testing
- `authenticated_client` fixture reduces boilerplate in every test

✅ **Pytest Marker Strategy**
- Markers allow selective test execution: `pytest -m "not slow and not playwright"`
- Skip Playwright tests by default since they're slow
- `external_api` marker identifies tests requiring network credentials

✅ **Pragmatic Test Data Generation**
- Initial approach with complex filters failed (only found 1 item)
- Pivoted to simple position-based sampling (0%, 25%, 50%, 75%, 100%)
- Result: 5 diverse items representing different departments and course types

### What Failed

❌ **Column Name Mismatch**
- Error: `polars.exceptions.ColumnNotFoundError: unable to find column "faculty"`
- Cause: Qlik export uses "Department" not "faculty", "Material id" not "material_id"
- Fix: Updated script to use actual column names from source file

❌ **Overly Restrictive Filtering**
- Initial attempt to filter by (Department == "EEMCS") AND (Filetype == "pdf") AND (Course code != null) found only 1 item
- Learned: Test data doesn't perfectly match all criteria
- Fix: Switched to position-based sampling for guaranteed diversity

### Key Decisions

**Decision 1: Use Real External APIs in Tests**
- Alternatives considered: Mock all APIs, use fixtures, hit real APIs
- Reason: User explicitly requested "Hit real test APIs" to catch actual API changes
- Trade-off: Tests require network and credentials, but provide actual integration coverage
- Mitigation: Mark with `@pytest.mark.external_api` to skip when needed

**Decision 2: Skip Playwright by Default**
- Alternatives considered: Run all tests always, separate suites
- Reason: Browser tests are slow (5-10s each) and flaky
- Implementation: `addopts = -m "not playwright"` in pytest.ini
- Override: Run with `pytest -m playwright` when needed

**Decision 3: Test Data File Commit Strategy**
- Initial: Ignore all test_data/ to keep repo clean
- Revised: Commit test_data/e2e/ but ignore test_data/*
- Reason: Need reproducible test data in version control
- Implementation: Complex gitignore pattern with negation

## Artifacts

### Infrastructure Files
- `src/conftest.py` - Central pytest fixtures and configuration
- `pytest.ini` - Test markers and configuration
- `.env.test` - Test environment variables
- `pyproject.toml:47-56` - Test dependencies

### Test Data
- `test_data/e2e/base_case_5.xlsx` - 5-item test dataset
- `scripts/create_test_data.py` - Data generation script

### Documentation
- `/home/sam/.claude/plans/snuggly-orbiting-gray.md` - Complete implementation plan (4 phases)
- `thoughts/ledgers/CONTINUITY_CLAUDE-dev-environment.md` - Session continuity ledger

### Configuration Updates
- `.gitignore:22-48` - Test artifacts exclusion pattern

## Action Items & Next Steps

### Immediate Next Steps (Phase 2)

1. **Create E2E Pipeline Test Suite**
   - File: `src/apps/core/tests/test_e2e_pipeline.py`
   - Implement 8 tests:
     - `test_step1_ingest_qlik_export()` - Ingest 5 items, verify exactly 5 created
     - `test_step2_ingest_faculty_sheet()` - Apply faculty updates
     - `test_step3_enrich_from_osiris()` - REAL Osiris API enrichment
     - `test_step4_enrich_from_people_pages()` - Verify person data
     - `test_step5_get_pdf_status_from_canvas()` - REAL Canvas API PDF check
     - `test_step6_extract_pdf_details()` - PDF text extraction
     - `test_step7_export_faculty_sheets()` - Excel export
     - `test_complete_pipeline_integration()` - Full end-to-end run
   - Use `@pytest.mark.django_db(transaction=True)` for tests that commit
   - Use `@pytest.mark.external_api` for tests hitting real APIs
   - Use task `.call()` method for synchronous execution

2. **Create Task Execution Verification**
   - File: `src/apps/core/tests/test_task_execution.py`
   - Verify ImmediateBackend behavior during tests
   - Test task result handling

3. **Verify Pipeline Tests**
   - Run: `uv run pytest -m pipeline -v`
   - Target: Complete in <60 seconds
   - Verify all 5 items pass through 7 steps successfully

### Subsequent Phases

**Phase 3: URL Coverage** (Week 2)
- Create `scripts/discover_endpoints.py` for URL enumeration
- Create comprehensive URL tests for all apps (dashboard, ingest, enrichment, steps, api)
- Target: 200+ endpoint tests

**Phase 4: Backend Response** (Week 3)
- Create `src/tests/test_backend_responses.py`
- Test HTMX headers, status codes, database state changes
- Target: 50+ HTTP layer tests

**Phase 5: Playwright UI** (Week 4)
- Install: `uv add --group playwright pytest-playwright playwright && uv run playwright install chromium`
- Create browser automation tests
- Target: 30+ UI tests with screenshots

## Other Notes

### Test Execution Reference

```bash
# Fast unit tests only
uv run pytest -m unit

# Pipeline tests (requires network + credentials)
uv run pytest -m pipeline -v

# URL coverage tests
uv run pytest -k "test_urls" -v

# Backend response tests
uv run pytest -m htmx -v

# Playwright UI tests (skipped by default)
uv run pytest -m playwright --headed

# Everything except slow/playwright
uv run pytest -m "not slow and not playwright"

# Full test suite (warning: slow)
uv run pytest

# Parallel execution
uv run pytest -n auto
```

### External API Requirements

**Osiris API:**
- Base URL: https://utwente.osiris-student.nl
- Test course code: 191154340 (stable)
- No authentication required (public web scraping)

**Canvas API:**
- Base URL: https://utwente.instructure.com/api/v1
- Requires: `CANVAS_API_TOKEN` environment variable
- For tests: Set `TEST_CANVAS_API_TOKEN` in `.env.test`

### Test Organization

Current structure:
```
src/apps/
  core/tests/     → Add: test_e2e_pipeline.py, test_task_execution.py
  dashboard/tests/ → Add: test_urls_comprehensive.py, test_form_submissions.py
  ingest/tests/    → Add: test_urls_comprehensive.py
  enrichment/tests/ → Add: test_urls_comprehensive.py
  steps/tests/     → Add: test_urls_comprehensive.py
  api/tests/       → Add: test_urls_comprehensive.py

src/tests/
  backend_responses.py          → CREATE: HTTP layer tests
  playwright/                    → CREATE: Browser UI tests
    test_dashboard_ui.py
    test_ingestion_ui.py
    test_steps_ui.py
    test_visual_regression.py
```

### Key Implementation Patterns

**Task Testing Pattern:**
```python
# Use .call() for synchronous execution during tests
result = stage_batch.call(batch.id)
assert result["success"]

# For async tasks
result = await enrich_item(item_id)
assert result["success"]
```

**Database Transaction Pattern:**
```python
@pytest.mark.django_db(transaction=True)
def test_that_commits():
    # Test code that needs to see committed data
```

**HTMX Testing Pattern:**
```python
response = authenticated_client.post(url, data=post_data, HTTP_HX_Request="true")
assert response.status_code in [200, 204]
assert "HX-Trigger" in response or response.has_header("HX-Trigger")
```

### Success Metrics

**Phase 2 Success Criteria:**
- Base case pipeline test runs in <60 seconds
- All 5 items pass through 7 steps successfully
- Real API calls work (Osiris, Canvas)
- No data loss or corruption

**Overall Success Criteria:**
- 400+ tests total (from 168 baseline)
- <5 minutes to run full suite (excluding Playwright)
- <10 minutes including Playwright
- All critical paths covered
- Real API integration tested
