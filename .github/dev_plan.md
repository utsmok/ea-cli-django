# Implementation Plan: Easy Access Platform — Phase A (Updated)

**Version:** 6.0 (Consolidated)
**Date:** December 18, 2025
**Status:** Phase A mostly complete — final polish, export parity, and migration remaining ✅

---

## Executive Summary 🚀
- Phase A (Core Data & Ingestion) is functionally complete: the Django ingestion pipeline (Qlik + Faculty), staging models, batch processor, standardizer, merge rules, excel export baseline, dashboard upload UI, and management commands are implemented and thoroughly tested.
- Remaining high-priority work: Step 9 (Excel export parity & formatting) and Step 10 (run legacy data migration to load enrichment data). Note: key parts of Step 9 (two-sheet workbook structure, per-faculty bucket workbooks, backup strategy and update-tracking CSV/text) are already implemented in the current codebase (ExportService + ExcelBuilder), but styling/conditional-formatting parity and test updates remain. Final validation against legacy outputs and a few polish items (exact formatting, Windows locking edge-cases, large-scale testing) are still outstanding.
- I archived the previous planning and session docs to `.github/older_docs_for_reference/` and left `agents.md` + this `dev_plan.md` in the root.

---

## Phase A — Completed (high level) ✅
- Identity foundation: custom `apps.users.User` model created and migrated
- Ingestion & audit models: `IngestionBatch`, `FacultyEntry`, `QlikEntry`, `ProcessingFailure`, `ChangeLog`
- Standardizer service (Polars): clean, testable transformations for Qlik & Faculty
- Merge rules & comparison strategies: explicit QLIK / FACULTY ownership
- Batch processor: transactional, logs ChangeLog, records failures
- Excel export: ExportService and `ExcelBuilder` implemented. The exporter creates per-faculty folders and workflow bucket workbooks (inbox/in_progress/done/overview), each workbook contains two sheets ("Complete data" + "Data entry"). Backup/rotation, `update_info_*.txt`, and `update_overview.csv` are implemented; some styling and conditional-formatting to reach byte-for-byte legacy parity remains and a couple of tests need adjusting to the new API.
- Dashboard UI: upload, batch listing, batch detail, status API, download endpoints
- Management commands: `process_batch`, `load_faculties`, `assign_faculties`, `load_legacy_data` (created, not yet executed)
- Test coverage: ~48/49 tests passing; many unit and integration tests implemented
- Critical bug fixes: faculty mapping and export schema inference resolved (see archived `FACULTY_AND_EXPORT_FIX.md`)

---

## Phase A — Outstanding Tasks (priority list) ⚠️

1. Step 9: Excel Export — Legacy parity & polish 🔧
   - 9.1 Load enrichment data into Django (run `load_legacy_data`) — command exists and is ready; run `--dry-run` then actual import (blocker for enriched exports)
   - 9.2 Two-sheet structure ("Complete data" + "Data entry") — IMPLEMENTED via `ExcelBuilder.build_workbook_for_dataframe`
   - 9.3 Excel styling & conditional formatting to match legacy precisely — PARTIAL: many styling helpers and validations implemented, but a final pass is required to match legacy visuals and conditional rules
   - 9.4 Workbook protection & locking behavior (fix openpyxl warnings) — PARTIAL: sheet protection / lock/unlock behavior implemented; some openpyxl deprecation/warning handling and Windows file-lock edge cases remain
   - 9.5 Backup system & summary CSV/text (timestamped backups) — IMPLEMENTED (`ExportService` backs up existing export tree and writes `update_info_*.txt`)
   - 9.6 Export update tracking (manifest & summary statistics) — IMPLEMENTED (`update_overview.csv` and per-faculty update info files)
   - 9.7 Tests & parity automation — NEW: update unit tests (e.g., `test_excel_builder.py`) to use the new `ExcelBuilder` / `ExportService` API and add automated parity/round-trip checks; some existing tests still expect the legacy API and must be updated
   - Verification: byte-for-byte or functional parity tests with legacy exports and round-trip tests (add automated comparisons once styling parity is complete)

2. Step 10: Legacy data migration (ready but not executed)
   - `load_legacy_data` management command exists and is ready; provide the legacy DB path and run `--dry-run` to inspect counts, then run actual import
   - Note: there is currently no `verify_migration` management command in the repository — create one (or add post-import verification to `load_legacy_data`) to validate mapping and surfacing edge-cases after import
   - After import, run export parity checks (exports should contain enrichment: courses, persons, course->person links)

3. Final verification & acceptance
   - Run full test suite and update failing tests (some unit tests reference the legacy ExcelBuilder API and require changes)
   - Add automated export parity checks (visual diffs and functional checks) and run comparisons with legacy outputs
   - Run scale/perf checks with a large Qlik export (recommended; see Risks) and ensure ExportService holds up (Polars helps but DB writes may need tuning)

4. Minor polish & tech debt
   - Fix openpyxl deprecation warnings (cell protection API changes)
   - Add missing conditional formatting if legacy had special rules
   - Add more integration tests for round-trip scenarios (export → edit → reimport)

5. Deployment readiness items
   - Configure file / storage quotas and backups
   - Collect static files, configure ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
   - Add monitoring for long-running exports/batches

---

## Deviations from original dev_plan.md (notable) 🔍
- Merge logic simplified: moved from complex Strategy pattern to explicit field ownership with clear comparison strategies (intentional simplification; improves auditability).
- Processing pipeline is database-backed (two-phase: Stage → Process) rather than single-pass: improves inspection, retries, and reliability.
- Polars-first approach used throughout for performance and clean transformation layer (no Pandas in standardizer).
- Dashboard (Step 8) implemented earlier than some of the export polishing — the web UI is complete and production-ready.
- Legacy migration tooling was prepared but requires the legacy DB to be executed in the environment — thus it's ready but still pending.

---

## Risks & Blockers ⚠️
- Enrichment data missing: exports lack course/person context until `load_legacy_data` is run.
- Export parity: visual/formatting differences may surface during stakeholder review; prioritize 9.3.
- Scale: large Qlik exports (tens to hundreds of thousands of rows) must be load-tested; Polars helps but DB writes (bulk-create, ChangeLog) may need tuning.
- Windows file locking during export backups: ensure export backups skip/handle locked files.

---

## Acceptance Criteria for Phase A ✅
- Excel exports match legacy format (ordering, validation dropdowns, sheet protection, overview)
- `load_legacy_data` executed and enrichment data visible in exports
- All tests pass; integration tests for round-trip and parity pass
- Performance check passed for typical production-sized exports
- Documentation updated (README, testing guide, export usage)

---

## Post-Phase A: High-level plan (Phase B & C) 📆

Phase B — Enrichment
- Add `EnrichmentJob`, `PersonMatch`, `PDFMetadata` models
- Services: `osiris_scraper.py`, `canvas_client.py`, `pdf_downloader.py`
- Trigger enrichment after Qlik ingestion; staleness detection & re-enrichment
- Add tests for enrichment job retries and data linking

Phase C — Dashboard & Classification
- HTMX grid editor for interactive editing (replace Excel workflow)
- Inline edit + audit trail exposure in UI
- ML classification service (`classifier.py`), integration tests, suggestion UX
- Permissioning & admin workflows for submitting bulk changes

---

## Immediate next actions (recommended) ✅
1. Run `load_legacy_data --dry-run` with legacy DB path and inspect counts — *Owner: infra/dev*
2. Update tests to match the refactored export API (fix `test_excel_builder.py` to use `ExcelBuilder.build_workbook_for_dataframe` or test `ExportService.export_workflow_tree`) — *Owner: dev*
3. Finish styling & conditional formatting parity (add targeted tests for conditional rules and cell protection behavior) — *Owner: dev*
4. Implement a `verify_migration` management command or add verification to `load_legacy_data` to validate mapping counts and edge cases after import — *Owner: dev/infra*
5. Run export parity and round-trip tests; fix issues iteratively — *Owner: QA/dev*
6. Run scale tests with representative large Qlik export (measure time & memory), and tune DB bulk operations if needed — *Owner: dev/ops*

---

## Where the archived docs are 📂
All prior `.md` files (planning, session notes, progress logs, status docs) have been moved to:

`.github/older_docs_for_reference/`

Files moved include:
- `dev_plan.md` (previous version) → `older_docs_for_reference/dev_plan_v5.md`
- `FACULTY_AND_EXPORT_FIX.md`
- `implementation_progress.md`
- `implementation_progress_2.md`
- `PHASE_A_COMPLETION_REPORT.md`
- `PHASE_A_STATUS.md`
- `refactor_plan_draft.md`
- `restructuring_note.md`
- `SESSION_SUMMARY_DEC17.md`
- `STEP_8_COMPLETION.md`
- `testing_guide.md`

(Keep `agents.md` and this updated `dev_plan.md` in the `.github` root.)

---

## Wrap up / Quick status (2 sentences) ✨
Phase A is nearly complete: ingestion, merge rules, standardizer, processor, and dashboard are implemented; ExportService + ExcelBuilder implement per-faculty exports, backups, and update tracking. Remaining high-priority work: finalize styling/conditional formatting parity, update tests to the refactored API, implement a `verify_migration` check, and run the legacy migration (`load_legacy_data --dry-run` first) followed by export parity validation.
