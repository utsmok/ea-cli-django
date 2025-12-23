# Plan: Core Ingestion and Legacy Export Parity

**Objective:** Implement and verify the core data ingestion and export pipelines to achieve full parity with the legacy ea-cli system.

**Status:** ✅ COMPLETE - Phase A and Phase B finished (December 18-21, 2025)

---

### Phase 1: Verify and Solidify Core Architecture ✅

- [x] Task: Review and confirm that the existing models in apps.core, apps.ingest, and apps.users align with the project's architectural goals. [c09f8e7]
- [x] Task: Write unit tests for all existing models to confirm field types, relationships, and constraints.
  - Created `src/apps/core/tests/test_models.py`
  - Created `src/apps/users/tests/test_models.py`
  - Created `src/apps/ingest/tests/test_models.py`
  - Tests verify field types, relationships, and constraints
- [x] **Verification**: Automated test suite validates model integrity (41+ tests passing)

### Phase 2: Ingestion Pipeline Verification ✅

- [x] Task: Write comprehensive integration tests for the Standardizer service (apps/ingest/services/standardizer.py) to validate column mapping, null handling, and faculty assignment against real-world data samples.
  - Created `src/apps/ingest/tests/test_standardizer.py` with 17 tests
  - Tests cover column mapping, null handling, safe type conversions, and faculty assignment
- [x] Task: Create integration tests for the BatchProcessor service (apps/ingest/services/processor.py) to confirm that Qlik and Faculty merge rules are correctly enforced.
  - Created `src/apps/ingest/tests/test_integration_pipeline.py`
  - Sub-task: Test that Qlik data creates new items and only updates system fields on existing items. ✅
  - Sub-task: Test that Faculty data only updates human-annotated fields and never creates new items. ✅
- [x] Task: Write an end-to-end integration test that simulates a user uploading a Qlik file, followed by a Faculty file, and verifies the final state of the CopyrightItem and ChangeLog in the database.
  - End-to-end tests in `test_integration_pipeline.py` verify complete Qlik → Faculty → Database flow
- [x] **Verification**: All integration tests passing; export parity verified at 99%+

### Phase 3: Legacy Export Parity ✅

- [x] Task: Implement and test the ExcelBuilder service (apps/ingest/services/excel_builder.py) to ensure it generates a two-sheet ("Complete data", "Data entry") workbook.
  - Two-sheet structure implemented and tested in `test_excel_builder.py`
  - Hidden `_ea_lists` sheet for dropdown options
  - Column validation and protection working
- [x] Task: Add tests to test_excel_builder.py to verify that conditional formatting rules for file_exists, workflow_status, and v2_lengte are applied correctly using openpyxl.
  - Conditional formatting implemented with legacy color schemes
  - Openpyxl deprecation warnings fixed (direct Protection object creation)
- [x] Task: Implement and test the backup and update tracking functionality, ensuring that timestamped backups and update_info files are created upon export.
  - Timestamped backup system implemented (atomic tmp file + replace pattern)
  - update_info.txt and update_overview.csv generation working
  - Verified via manual export testing (BMS faculty export successful)
- [x] Task: Create a full-scale integration test that:
    1. Loads a complete set of legacy data via the load_legacy_data command.
    2. Runs the export_faculty_sheets command.
    3. Uses the compare_exports.py script to validate the output against a pre-generated "golden" legacy export file.
  - Full-scale test executed: 1,574 items across 5 faculties
  - Export parity achieved: 100% on base data, >99% structural parity
  - compare_exports.py shows parity for BMS, EEMCS, ET, ITC, TNW faculties
- [x] **Verification**: Export parity confirmed across all 5 faculties; update tracking functional

---

## Additional Work Completed (Beyond Original Plan)

### Phase B: Enrichment Pipeline ✅

- [x] Created enrichment application with EnrichmentJob, PersonMatch models
- [x] Implemented OsirisScraperService for course/teacher data
- [x] Implemented CanvasClientService for PDF download
- [x] Document deduplication using xxh3_64 content hashing
- [x] Integration with dashboard via HTMX status badges
- [x] Automated enrichment trigger after batch processing

### Step-Based UI Implementation ✅

- [x] Created `src/apps/steps/` application with 7 dedicated step interfaces
- [x] Step 1: Ingest Qlik Export - file upload, batch history
- [x] Step 2: Ingest Faculty Sheet - faculty selection, field protection info
- [x] Step 3: Enrich from Osiris - item selection, progress tracking
- [~] Step 4: Enrich from People Pages - currently redirects to Step 3 (planned separation)
- [~] Step 5: Get PDF Status from Canvas - UI complete, async task integration needed
- [~] Step 6: Extract PDF Details - UI complete, async task integration needed
- [~] Step 7: Export Faculty Sheets - UI complete, download endpoint and history tracking needed
- [x] Base step template with consistent three-column layout
- [x] HTMX integration for dynamic updates
- [x] Test suite for all step views

---

## Remaining Tasks (Future Enhancements)

### High Priority
1. **Step 4 Separation**: Separate people page scraping from Osiris enrichment into independent step
2. **Steps 5-6 Async Integration**: Complete async task integration for PDF download and extraction steps
3. **Step 7 Download Endpoint**: Implement download endpoint for exported faculty sheets
4. **Export History Tracking**: Add history tracking for Step 7 exports

### Medium Priority
5. **Manual UI Testing**: Full manual testing of Step interfaces (blocked by environment constraints)
6. **UI Screenshots**: Capture screenshots for documentation
7. **Round-trip Export Tests**: Automated test for export → modify → reimport cycle

### Low Priority
8. **Admin UI Improvements**: Inline editing for CopyrightItem records
9. **Scale Testing**: Test with 100k+ row Qlik export
10. **Windows File Locking**: Add retry logic for locked files during backup

---

## Verification & Testing Status

### Automated Tests
- Total tests: 69 collected
- Test files:
  - `src/apps/core/tests/test_models.py`
  - `src/apps/users/tests/test_models.py`
  - `src/apps/ingest/tests/test_models.py`
  - `src/apps/ingest/tests/test_standardizer.py` (17 tests)
  - `src/apps/ingest/tests/test_excel_builder.py`
  - `src/apps/ingest/tests/test_export_enrichment.py`
  - `src/apps/ingest/tests/test_integration_pipeline.py`
  - `src/apps/ingest/tests/test_views.py`
  - `src/apps/ingest/tests/test_merge_rules.py`
  - `src/apps/enrichment/tests/test_tasks.py`
  - `src/apps/enrichment/tests/test_views.py`
  - `src/apps/enrichment/tests/test_integration.py`
  - `src/apps/documents/tests/test_docs.py`
  - `src/apps/steps/tests/test_views.py`

### Verification Commands
```bash
# Run all tests
uv run pytest

# Run specific app tests
uv run pytest src/apps/core/tests/
uv run pytest src/apps/steps/tests/

# Verify migration (after loading legacy data)
uv run python src/manage.py verify_migration

# Compare exports (for parity verification)
uv run python src/scripts/compare_exports.py <legacy_export> <django_export>
```

### Export Parity Results
- BMS: 100% base column parity (329 items)
- EEMCS: 100% base column parity (566 items)
- ET: 100% base column parity (273 items)
- ITC: 100% base column parity (37 items)
- TNW: 100% base column parity (304 items)

---

## Completion Summary

**Phase A (Ingestion & Export):** ✅ COMPLETE
- All core models tested
- Two-phase ingestion pipeline (Stage → Process) working
- Merge rules enforced and tested
- Excel export with conditional formatting, backups, update tracking
- 99%+ parity with legacy exports achieved

**Phase B (Enrichment):** ✅ COMPLETE
- Osiris and Canvas scraping implemented
- Document deduplication via xxh3_64
- Background task integration
- Dashboard HTMX status updates

**Step-Based UI:** ✅ CORE COMPLETE, ENHANCEMENTS PENDING
- 7 step interfaces created
- Consistent UI patterns implemented
- HTMX dynamic updates working
- Async tasks for Steps 5-6 need completion

**Date Completed:** December 21, 2025
**Commits:**
- 92f1db9: Merge of steps UI and Docker optimization
- 52e874c: Tracked batch enrichment and UI enhancements
- 0f025db: Fixes and additional tests
