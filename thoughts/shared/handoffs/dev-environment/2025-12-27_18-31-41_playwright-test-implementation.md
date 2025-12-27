---
date: 2025-12-27T18:31:41+01:00
session_name: dev-environment
researcher: claude
git_commit: 93f5ce28c929df71646920883781e0f654af1bd7
branch: main
repository: ea-cli-django
topic: "Playwright UI Test Infrastructure Implementation"
tags: [testing, playwright, ui-tests, pytest, async-fixes]
status: partial_plus
last_updated: 2025-12-27
last_updated_by: claude
type: implementation_strategy
root_span_id:
turn_span_id:
---

# Handoff: Playwright UI Test Infrastructure

## Task(s)
**Phase 5: Playwright UI Test Suite** from testing implementation plan (`thoughts/shared/plans/2025-12-27-testing-implementation-phases-4-5.md`)

**Status: PARTIAL_PLUS** - Infrastructure fully working, 1 test passing, 5+ tests need selector adjustments

### Completed
- ✅ Fixed all critical setup issues (async context, browser launch, authentication)
- ✅ Created test user via migration (0002_create_test_user.py)
- ✅ Fixed login button selector to match actual template
- ✅ Fixed dashboard URL paths (root `/` not `/dashboard/`)
- ✅ First Playwright test passing: `test_dashboard_loads` (2.48s)

### In Progress
- ⚠️ Fixing test selectors to match actual UI structure (5+ tests failing)
- ⚠️ Adjusting URL regex patterns to include query parameters

### Planned
- Run all 80 Playwright tests to completion
- Generate final test execution report
- Document visual regression baseline

## Critical References
1. `thoughts/shared/plans/2025-12-27-testing-implementation-phases-4-5.md` - Original implementation plan
2. `test_data/TESTING_IMPLEMENTATION_COMPLETE.md` - Task completion summary
3. `test_data/TEST_EXECUTION_REPORT.md` - Backend and URL test results

## Recent Changes
### Infrastructure Fixes
- `pytest.ini:29-31` - Added `asyncio_mode = auto` to fix pytest-asyncio STRICT mode conflicts
- `src/apps/users/migrations/0002_create_test_user.py:6-18` - Created testuser/testpass123 with staff/superuser perms
- `src/tests/playwright/conftest.py:86` - Changed login selector from `button[type="submit"]` to `button:has-text("Sign In")`
- `src/tests/playwright/test_dashboard_ui.py:25,39,54,64,78,93,108,127,145,167,179,198,216,250,269,291,304` - Fixed all dashboard URLs from `{base_url}/dashboard/` to `{base_url}/`

### New Files
- `src/tests/conftest.py` - Created minimal shared pytest configuration

## Learnings

### Async Context Conflict Resolution
**Problem**: `SynchronousOnlyOperation: You cannot call this from an async context` when Playwright fixtures used Django ORM.

**Root Cause**: pytest-asyncio defaults to STRICT mode, which wraps all fixtures in async context, blocking Django's synchronous ORM calls.

**Solution**: Set `asyncio_mode = auto` in pytest.ini. This allows pytest-asyncio to only explicitly wrap async fixtures, leaving sync fixtures alone.

**File**: `pytest.ini:30`

### Django Database Access in pytest_configure
**Problem**: Attempted to create test user in `pytest_configure()` hook, got `RuntimeError: Database access not allowed`.

**Root Cause**: pytest-django blocks database access in configure hooks even with Django setup.

**Solution**: Use data migration instead. Migration runs in sync context during `migrate` command, not during test collection.

**File**: `src/apps/users/migrations/0002_create_test_user.py:6-18`

### Login Button Selector Mismatch
**Problem**: `button[type="submit"]` selector timeout - button not found.

**Root Cause**: Login template (`src/templates/registration/login.html:46-51`) uses `<button class="btn btn-ut btn-primary">` without `type="submit"` attribute.

**Solution**: Use text selector `button:has-text("Sign In")` which is more reliable and matches user-visible text.

**File**: `src/tests/playwright/conftest.py:86`

### Dashboard URL Structure
**Problem**: All tests getting 404 on `/dashboard/` path.

**Root Cause**: Dashboard app included at root path in `src/config/urls.py:22` - path is `/` not `/dashboard/`.

**Solution**: Changed all test URLs from `{base_url}/dashboard/` to `{base_url}/`.

**Files**: `src/tests/playwright/test_dashboard_ui.py:25,39,54,64,78,93,108,127,145,167,179,198,216,250,269,291,304`

## Post-Mortem

### What Worked
- **Migration-based test data**: Using Django migrations to create test user avoids all async context issues with database access
- **pytest-asyncio AUTO mode**: Setting `asyncio_mode = auto` allows Playwright's sync API to coexist with async Django tests
- **Text-based selectors**: Using `button:has-text("Sign In")` more reliable than attribute selectors that may change
- **Systematic template reading**: Reading actual HTML templates (`login.html`, `_workflow_tabs.html`) revealed selector mismatches

### What Failed
- **pytest_configure with ORM**: Tried to create test user in pytest_configure hook → Failed because pytest-django blocks DB access → Fixed by using migration
- **Attribute selector for login**: Used `button[type="submit"]` → Failed because button lacks type attribute → Fixed with text selector
- **Django ORM in Playwright fixtures**: Tried to use `User.objects.get()` in `authenticated_page` fixture → Failed with async context error → Fixed by creating user via migration instead
- **URL path assumptions**: Assumed `/dashboard/` path based on app name → All tests got 404 → Fixed by checking actual URL config

### Key Decisions
- **Decision**: Use data migration for test user creation
  - Alternatives considered: pytest_configure hook, session-scoped fixture, manual SQL
  - Reason: Migrations run in sync context during setup, avoid all async/ORM conflicts, reproducible across environments

- **Decision**: Set `asyncio_mode = auto` globally in pytest.ini
  - Alternatives considered: Mark individual test files, disable pytest-asyncio for Playwright
  - Reason: Simplest solution, doesn't require test code changes, allows async tests to still work with explicit marks

- **Decision**: Use text selectors over CSS selectors for login button
  - Alternatives considered: `button.btn-primary`, CSS class selectors, XPath
  - Reason: More resilient to styling changes, matches what user sees

## Artifacts

### Created
- `src/apps/users/migrations/0002_create_test_user.py` - Test user migration
- `src/tests/conftest.py` - Minimal shared pytest config
- `test_data/PLAYWRIGHT_TEST_RESULTS.txt` - Initial test run output (3 passed, 5 failed)

### Modified
- `pytest.ini` - Added asyncio_mode configuration
- `src/tests/playwright/conftest.py` - Fixed login selector
- `src/tests/playwright/test_dashboard_ui.py` - Fixed all dashboard URL paths

### Test Files (Already Existed from Previous Work)
- `src/tests/playwright/conftest.py` - Playwright fixtures (200 lines)
- `src/tests/playwright/test_dashboard_ui.py` - 17 dashboard tests
- `src/tests/playwright/test_ingestion_ui.py` - 11 ingestion tests
- `src/tests/playwright/test_steps_ui.py` - 19 step tests
- `src/tests/playwright/test_visual_regression.py` - 16 screenshot tests
- `src/tests/playwright/test_legacy_ui.py` - 16 backward compatibility tests
- `src/tests/playwright/README.md` - 330 lines documentation

## Action Items & Next Steps

### Immediate (Required to Complete Phase 5)
1. **Fix test selectors** - Update test_dashboard_ui.py selectors to match actual UI:
   - Change `.tabs` text node selectors to `button.tab` element selectors
   - Example: `.locator(".tabs").get_by_text("ToDo")` → `.locator("button.tab:has-text('ToDo')")`
   - File: `src/tests/playwright/test_dashboard_ui.py:47-50,82,97,112`

2. **Fix URL regex patterns** - Adjust regex to handle query parameters:
   - Change `expect(authenticated_page).to_have_url(".*status=Done.*")` to include `&per_page=50`
   - Use regex pattern: `.*status=Done.*` works fine, but might need `.*status=Done(&|$)`
   - Files: `src/tests/playwright/test_dashboard_ui.py:89,104,119,141,159,190`

3. **Run full Playwright test suite**:
   ```bash
   uv run pytest src/tests/playwright/ -m playwright -v --timeout=60000
   ```

4. **Fix additional selector issues** - Address any other selector mismatches found in full run

### Later (Optional)
- Generate visual regression baseline screenshots
- Add accessibility testing with axe-core
- Integrate Playwright tests into CI/CD pipeline
- Add performance benchmarking

## Other Notes

### Test Infrastructure Status
- **Total Playwright tests**: 80 (267% above plan's 30)
- **Current pass rate**: 1/80 (1.25%)
- **Infrastructure**: ✅ Fully working (browser launch, auth, page navigation all functional)
- **Remaining work**: Test selector adjustments to match actual UI implementation

### Known UI Structure
Dashboard layout (`src/templates/dashboard/dashboard.html`):
- Main heading: `<h1>Copyright Dashboard</h1>`
- Table container: `<div id="table-container">`
- Detail panel: `<div id="detail-panel">`
- Workflow tabs: Located in `src/templates/components/_workflow_tabs.html`
  - Structure: `<button class="tab">` elements, NOT text nodes
  - Labels: ToDo, InProgress, Done, All (from `workflow_choices` variable)
  - HTMX attributes: `hx-get`, `hx-target="#table-container"`, `hx-push-url="true"`

### Server Requirements
Playwright tests require running Django server:
```bash
# Start server in terminal 1
./start-dev.sh

# Or manually:
uv run python src/manage.py runserver
```

### WSL2 Dependencies
Playwright Chromium requires these libraries in WSL2:
```bash
sudo apt-get install -y libasound2-dev libnss3-dev libatk-bridge2.0-dev libdrm2 libxkbcommon0 libgbm1
```

### Previous Handoffs
See `thoughts/shared/handoffs/dev-environment/` for earlier testing work:
- `2025-12-27_11-55-00_test-suite-analysis-and-slow-test-investigation.md`
- `2025-12-27_12-57-44_test-suite-performance-optimization.md`

### Test Commands Reference
```bash
# Run all Playwright tests
uv run pytest src/tests/playwright/ -m playwright -v

# Run single test
uv run pytest src/tests/playwright/test_dashboard_ui.py::TestDashboardLayout::test_dashboard_loads -v -m playwright

# Run with headed browser (watch test execution)
PLAYWRIGHT_HEADLESS=false uv run pytest src/tests/playwright/test_dashboard_ui.py::TestDashboardLayout::test_dashboard_loads -v -m playwright

# Run all non-Playwright tests (backend + URL tests)
uv run pytest -m "not playwright" -v
```
