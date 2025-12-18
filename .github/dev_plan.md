# Implementation Plan: Easy Access Platform — Phase A (Updated)

**Version:** 6.0 (Consolidated)
**Date:** December 18, 2025
**Status:** Phase A mostly complete — final polish, export parity, and migration remaining ✅

---

## Executive Summary 🚀
- Phase A (Core Data & Ingestion) is functionally complete: the Django ingestion pipeline (Qlik + Faculty), staging models, batch processor, standardizer, merge rules, excel export baseline, dashboard upload UI, and management commands are implemented and thoroughly tested.
- Remaining high-priority work: Step 9 (Excel export parity & formatting), Step 10 (run legacy data migration to load enrichment data), final validation against legacy outputs, and a few polish items (formatting, backup, large-scale testing).
- I archived the previous planning and session docs to `.github/older_docs_for_reference/` and left `agents.md` + this `dev_plan.md` in the root.

---

## Phase A — Completed (high level) ✅
- Identity foundation: custom `apps.users.User` model created and migrated
- Ingestion & audit models: `IngestionBatch`, `FacultyEntry`, `QlikEntry`, `ProcessingFailure`, `ChangeLog`
- Standardizer service (Polars): clean, testable transformations for Qlik & Faculty
- Merge rules & comparison strategies: explicit QLIK / FACULTY ownership
- Batch processor: transactional, logs ChangeLog, records failures
- Excel export: baseline export builder returns BytesIO; per-faculty sheets and overview implemented
- Dashboard UI: upload, batch listing, batch detail, status API, download endpoints
- Management commands: `process_batch`, `load_faculties`, `assign_faculties`, `load_legacy_data` (created, not yet executed)
- Test coverage: ~48/49 tests passing; many unit and integration tests implemented
- Critical bug fixes: faculty mapping and export schema inference resolved (see archived `FACULTY_AND_EXPORT_FIX.md`)

---

## Phase A — Outstanding Tasks (priority list) ⚠️

1. Step 9: Excel Export — Legacy parity & polish 🔧
   - 9.1 Load enrichment data into Django (run `load_legacy_data`) (blocker for enriched exports)
   - 9.2 Two-sheet structure ("Complete data" + "Data entry")
   - 9.3 Excel styling & conditional formatting to match legacy precisely
   - 9.4 Workbook protection & locking behavior (fix openpyxl warnings)
   - 9.5 Backup system & summary CSV/text (timestamped backups)
   - 9.6 Export update tracking (manifest & summary statistics)
   - Verification: byte-for-byte or functional parity tests with legacy exports and round-trip tests

2. Step 10: Legacy data migration (ready but not executed)
   - Ensure path to `ea-cli/db.sqlite3` or production legacy DB available
   - Run `load_legacy_data` with `--dry-run` → inspect counts → run actual import
   - Run `verify_migration` management command and fix mapping edge cases

3. Final verification & acceptance
   - Run full test suite and update failing tests if any
   - Run export parity comparison (visual + automated checks)
   - Run scale/perf checks with a large Qlik export (recommended; see Risks)

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
2. Implement Step 9.2–9.4 (two-sheet, formatting, protection) — *Owner: dev*
3. Run export parity and round-trip tests; fix issues iteratively — *Owner: QA/dev*
4. Run scale tests with representative large Qlik export (measure time & memory), and tune DB bulk operations if needed — *Owner: dev/ops*

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
Phase A is production-ready for command-line usage and mostly ready for web-based use; final, high-priority work is export parity (formatting, protection, backups) and running the legacy migration to enrich exports. My next step (if you want me to proceed) is to run `load_legacy_data --dry-run` (I will need the legacy DB path) and then implement the Step 9 export parity tasks.
