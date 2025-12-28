# Implementation Plan: Comprehensive Codebase Cleanup and Refactoring
Generated: 2025-12-27

## Goal

Clean up and refactor the Easy Access Platform Django project to remove technical debt, improve maintainability, and prepare for future feature development. The codebase has evolved from a CLI tool (`ea-cli/`) to a modern Django web platform, and now needs systematic cleanup.

## Research Summary

### Analysis Methods Used
- Line-of-code analysis for all Python files in `src/apps/`
- Import analysis with `ruff check --select F401`
- Pattern matching for dead code (TODO, FIXME, stub tests)
- Cross-reference analysis between legacy `ea-cli/` and new `src/apps/`
- Dependencies and imports verification

### Key Findings

1. **Unused Imports (18 fixable issues)**
   - Mostly in test files (unused `Client`, timezone imports)
   - One unused import in production code (`QLIK_CREATEABLE_FIELDS` in processor.py)

2. **Stub Apps (Intentionally Kept)**
   - `apps.classification` exists as a stub for future ML features - **KEEP**
   - `apps.enrichment/admin.py` is a stub file - can be removed

3. **Test Issues**
   - 2 skipped tests in `dashboard/tests/test_views.py` (verified by code review)
   - 2 skipped tests in `core/tests/test_e2e_pipeline.py` (conditional skipif)
   - Tests are otherwise well-implemented with 282+ passing

4. **Large Files Needing Refactoring**
   - `steps/views.py` (790 LOC) - repetitive view patterns
   - `core/services/osiris.py` (674 LOC) - large service module
   - `core/tests/test_e2e_pipeline.py` (642 LOC) - large test file
   - `ingest/admin.py` (467 LOC) - large admin file

5. **Project Root Clutter**
   - 8 markdown/documentation files in root (should be in `docs/`)
   - 3 test result `.txt` files (should be in `test_results/` or gitignored)
   - 2 duplicate screenshot directories (`screenshots/` and `test_screenshots/`)
   - Runtime directories that should be gitignored: `downloads/`, `ingestion_batches/`, `logs/`

6. **Dependency Analysis**
   - All declared dependencies in `pyproject.toml` are actively used
   - No obvious unused dependencies found

## Current State Analysis

### File Organization (171 Python files in src/apps/)

| App | Files | Status | Notes |
|-----|-------|--------|-------|
| core | ~25 files | Healthy | Central models, well-organized services |
| ingest | ~30 files | Healthy | Complete functionality |
| enrichment | ~12 files | Healthy | Minor stub in admin.py |
| documents | ~10 files | Healthy | Complete functionality |
| dashboard | ~12 files | Healthy | Complete functionality |
| api | ~8 files | Healthy | Complete functionality |
| steps | ~8 files | Needs refactoring | views.py too large (790 LOC) |
| users | ~6 files | Healthy | Complete functionality |
| settings | ~6 files | Healthy | Complete functionality |
| classification | ~3 files | **STUB** | Placeholder for future ML features |

### Code Quality Observations

**Positive:**
- Clean separation between apps
- Consistent use of services layer
- Good test coverage (282+ passing tests)
- Modern async patterns throughout
- No imports from legacy `ea-cli` in new code

**Needs Improvement:**
- Repetitive view patterns in `steps/views.py`
- Large service files that could be split
- Stub admin file that can be removed
- Project root cluttered with temporary files

## What We're NOT Doing

- Removing or refactoring the legacy `ea-cli/` directory (marked as reference-only)
- Removing the `apps.classification` stub app (will be developed next)
- Changing the database schema (data model is stable)
- Modifying the 7-step processing pipeline logic
- Changing the async/task architecture
- Rewriting the admin interface

## Implementation Phases

### Phase 1: Quick Wins (Low Risk, High Impact)

**Overview**: Remove obvious dead code and clean up project structure.

#### 1.1 Fix Unused Imports

**Files to modify:**
- `src/apps/api/tests/test_urls.py`
- `src/apps/core/tests/test_e2e_pipeline.py`
- `src/apps/core/tests/test_task_execution.py`
- `src/apps/dashboard/tests/test_urls.py`
- `src/apps/documents/tests/test_docs.py`
- `src/apps/enrichment/tests/test_urls.py`
- `src/apps/ingest/services/processor.py`
- `src/apps/ingest/tests/test_urls.py`
- `src/apps/steps/tests/test_urls.py`
- `src/conftest.py`
- `src/tests/conftest.py`
- `src/tests/playwright/conftest.py`
- `src/tests/playwright/test_visual_regression.py`

**Action:** Run `uv run ruff check --select F401 --fix` to auto-fix all 18 unused imports.

**Verification:**
```bash
uv run ruff check src --select F401
# Should return "No errors found"
```

#### 1.2 Remove Stub Admin File

**File to delete:** `src/apps/enrichment/admin.py`

**Reason:** File contains only `# Register your models here.` comment and no actual code. Django apps work fine without admin.py if no custom admin is needed.

**Verification:**
```bash
uv run python src/manage.py check
# Should pass without errors
```

#### 1.3 Consolidate Duplicate Screenshot Directories

**Current state:**
- `screenshots/` - older verification screenshots (subdirs for different test runs)
- `test_screenshots/` - newer Playwright screenshots

**Action:**
1. Consolidate all screenshots to `test_screenshots/`
2. Delete `screenshots/` directory
3. Update any references (found in `.gitignore` already has both)

**Files:**
- Delete: `screenshots/` directory (and contents)

**Verification:**
```bash
ls screenshots/  # Should fail: directory not found
```

#### 1.4 Clean Up Test Result Files

**Files to move:**
- `test_results.txt` - move to `test_results/`
- `test_failures.txt` - move to `test_results/`
- `test_failures_combined.txt` - move to `test_results/`
- `enrichment_results.txt` - move to `test_results/`

**Action:** Create `test_results/` directory, move all `.txt` result files there, then add `test_results/*.txt` to `.gitignore`.

**Files to create:**
- `test_results/.gitkeep`
- Update `.gitignore` to include `test_results/*.txt`

**Success Criteria:**
- [ ] Test result files moved to `test_results/`
- [ ] `.gitignore` updated to ignore `test_results/*.txt`
- [ ] No `.txt` files in project root except `.env.example`, `.gitignore`, etc.

---

### Phase 2: Large File Refactoring

**Overview**: Split large files into smaller, more maintainable modules.

#### 2.1 Split steps/views.py (790 LOC)

**Current file:** `src/apps/steps/views.py`

**Issue:** Repetitive view patterns for each processing step. Each step has:
- Index view (GET)
- Run action view (POST)
- Status check view (GET)

**Proposed structure:**

```
src/apps/steps/
  views/
    __init__.py        # Re-exports for backwards compatibility
    helpers.py         # _parse_item_ids and other utilities
    ingest.py          # Step 1 & 2: Ingest views
    enrich.py          # Step 3 & 4: Enrichment views
    pdf.py             # Step 5 & 6: PDF views
    export.py          # Step 7: Export views
```

**Refactoring approach:**
1. Extract `_parse_item_ids` to `helpers.py`
2. Create base classes or mixins for common view patterns
3. Group step-specific views into modules
4. Update `views.py` to be a package with `__init__.py` re-exporting

**Files to create:**
- `src/apps/steps/views/helpers.py` - utility functions
- `src/apps/steps/views/ingest.py` - ingest-related views
- `src/apps/steps/views/enrich.py` - enrichment-related views
- `src/apps/steps/views/pdf.py` - PDF-related views
- `src/apps/steps/views/export.py` - export-related views
- Convert `views.py` to `views/__init__.py`

**Verification:**
```bash
# All tests should still pass
uv run pytest src/apps/steps/tests/

# Manual verification: visit each step page
```

#### 2.2 Split core/services/osiris.py (674 LOC)

**Current file:** `src/apps/core/services/osiris.py`

**Proposed structure:**

```
src/apps/core/services/osiris/
  __init__.py        # Public API exports (backwards compatible)
  courses.py         # Course-related functions
  persons.py         # Person-related functions
  scraping.py        # HTTP client and scraping utilities
  constants.py       # FACULTY_ABBREVS, URLs, etc.
```

**Files to create:**
- `src/apps/core/services/osiris/__init__.py` (current file becomes this)
- `src/apps/core/services/osiris/courses.py`
- `src/apps/core/services/osiris/persons.py`
- `src/apps/core/services/osiris/scraping.py`
- `src/apps/core/services/osiris/constants.py`

**Backwards compatibility:** The `__init__.py` should re-export all public functions so existing imports continue to work.

**Code to extract to `constants.py`:**
```python
OSIRIS_SEARCH_URL = "https://utwente.osiris-student.nl/..."
PEOPLE_SEARCH_URL = "https://people.utwente.nl/overview?query="
FACULTY_ABBREVS = ["BMS", "ET", "EEMCS", "ITC", "TNW"]
```

**Functions to extract to `courses.py`:**
- `gather_target_course_codes()`
- `select_missing_or_stale_courses()`
- `fetch_and_parse_courses()`
- `fetch_course_data()`
- `_fetch_course_details()`

**Functions to extract to `persons.py`:**
- `fetch_person_data()`
- `fetch_and_parse_persons()`
- `_parse_person_page()`

**Functions to extract to `scraping.py`:**
- `OsirisScraperService` class (if exists)
- HTTP client utilities
- Retry logic specific to scraping

**Verification:**
```bash
# All imports should still work
uv run pytest src/apps/core/tests/test_osiris_faculty_extraction.py
```

#### 2.3 Review Other Large Files

**Files to review but NOT necessarily split:**

1. **core/tests/test_e2e_pipeline.py (642 LOC)**
   - Large end-to-end test file
   - Consider splitting by test class if needed
   - Acceptable as-is if tests are logically grouped
   - **Decision:** Leave as-is for now

2. **ingest/admin.py (467 LOC)**
   - Large admin configuration
   - Consider extracting to separate admin modules if admin complexity grows
   - **Decision:** Leave as-is for now

---

### Phase 3: Root Directory Cleanup

**Overview**: Move documentation and organize project root.

#### 3.1 Consolidate Documentation Files

**Files in project root to move to `docs/`:**

| Current Location | Target Location |
|------------------|-----------------|
| `TESTING.md` | `docs/testing.md` |
| `TESTING_RESULTS.md` | `docs/testing-results.md` (or delete) |
| `TEST_SUITE_COMPLETE.md` | `docs/test-suite-complete.md` (or delete) |
| `IMPLEMENTATION_SUMMARY.md` | `docs/implementation-summary.md` |
| `PLANS.md` | `docs/plans.md` |
| `AGENTS.md` | `docs/agents.md` |

**Keep in root:**
- `CLAUDE.md` - Used by Claude Code tooling
- `README.md` - Project entry point

**Action:** Move files and update any internal references.

#### 3.2 Update .gitignore

**Add to `.gitignore`:**
```
# Test results
test_results/
test_results/*.txt

# Temporary runtime directories (already partially covered)
downloads/
ingestion_batches/
```

#### 3.3 Review Runtime Directories

**Directories to verify are properly gitignored:**
- `logs/` - runtime logs
- `downloads/` - downloaded PDFs
- `ingestion_batches/` - uploaded files
- `exports/` - generated exports (already partially covered)

**Current gitignore has:** `exports/backups/`

**Add:**
```
exports/faculty_sheets/
```

---

### Phase 4: Test Cleanup

**Overview**: Address skipped tests and improve test organization.

#### 4.1 Review Skipped Tests

**Files with skipped tests:**

1. **dashboard/tests/test_views.py (2 skipped)**
   - `test_enrichment_status_not_updated_on_enqueue_failure`
   - `test_enrichment_status_updated_after_successful_enqueue`
   - Reason: "Race condition fix verified by code review"

   **Action:** These tests have good documentation explaining why they're skipped. Keep them as-is, but consider adding a comment to review after the next enrichment changes.

2. **core/tests/test_e2e_pipeline.py (2 conditional skips)**
   - Tests with `@pytest.mark.skipif` decorators
   - These are conditional skips based on environment

   **Action:** Keep as-is - these are legitimate conditional skips.

**Recommendation:** No action needed. Skipped tests are well-documented.

#### 4.2 Consolidate conftest.py Files

**Current state:**
- `src/conftest.py` - 267 lines, comprehensive fixtures
- `src/tests/conftest.py` - 9 lines, nearly empty
- `src/tests/playwright/conftest.py` - 206 lines, Playwright-specific

**Action:**
1. Keep `src/conftest.py` as the main conftest
2. Delete `src/tests/conftest.py` (it's empty/unused)
3. Keep `src/tests/playwright/conftest.py` (has specific Playwright fixtures)

**File to delete:** `src/tests/conftest.py`

**Verification:**
```bash
uv run pytest --collect-only
# Should collect same number of tests
```

---

### Phase 5: Dependency Verification

**Overview**: Verify all dependencies are needed.

#### 5.1 Check Dependency Usage

**Method:** For each dependency in `pyproject.toml`, verify it's imported.

**Dependencies to verify:**
- `kreuzberg` - Used for file operations
- `xxhash` - Used for file hashing
- `ty` - Type checker (dev tool)
- `pyyaml` - Configuration

**Command to check usage:**
```bash
# For each dependency, search for imports
grep -r "import kreuzberg\|from kreuzberg" src/
grep -r "import xxhash\|from xxhash" src/
grep -r "import yaml\|from yaml" src/
```

**Expected:** All dependencies should have imports. If any are unused, remove from `pyproject.toml` and run `uv sync`.

---

## Testing Strategy

### Automated Verification

After each phase, run:

```bash
# Code quality checks
uv run ruff check src/
uv run ruff format --check src/

# Type checking
uv run ty src/

# Django checks
uv run python src/manage.py check

# Full test suite
uv run pytest
```

### Manual Verification

1. **Start the server:** `./start-dev.sh`
2. **Log in as staff user**
3. **Navigate through all 7 steps**
4. **Verify dashboard functionality**
5. **Check admin interface**

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|------------|
| Phase 1 | Low | Auto-fix imports, deletions are straightforward |
| Phase 2 | Medium | Large refactoring - thorough testing required |
| Phase 3 | Low | Moving files, updating imports |
| Phase 4 | Low | Minor test cleanup |
| Phase 5 | Low | Read-only verification |

---

## Success Criteria

### Automated Verification
- [ ] All 18 unused imports fixed (ruff F401 returns clean)
- [ ] No import errors after refactoring
- [ ] All tests pass (282+ tests)
- [ ] Django check passes with no warnings
- [ ] No new linting errors introduced

### Manual Verification
- [ ] All 7 steps accessible and functional
- [ ] Dashboard loads correctly
- [ ] Admin interface works
- [ ] No broken links or imports

### Code Quality
- [ ] Largest file under 500 LOC (except tests)
- [ ] No empty stub files in production code (except classification)
- [ ] All apps have clear purpose and functionality
- [ ] Documentation up to date

---

## Estimated Effort

| Phase | Estimated Time |
|-------|----------------|
| Phase 1: Quick Wins | 30 minutes |
| Phase 2: Large File Refactoring | 3-4 hours |
| Phase 3: Root Cleanup | 30 minutes |
| Phase 4: Test Cleanup | 15 minutes |
| Phase 5: Dependency Check | 15 minutes |
| **Total** | **4.5-5.5 hours** |

---

## References

- Original ticket: User request for comprehensive cleanup
- Related documentation:
  - `CLAUDE.md` - Project overview and guidelines
  - `TEST_SUITE_COMPLETE.md` - Test suite documentation
  - `IMPLEMENTATION_SUMMARY.md` - Step-based UI implementation
- Similar patterns:
  - Django best practices for app organization
  - `src/apps/core/services/` - Example of well-organized service layer
