# Implementation Plan: Easy Access Platform — Phase B (Enrichment)

**Version:** 1.3 (Implemented)
**Status:** ✅ COMPLETE
**Goal:** Automate the enrichment of copyright data using external sources (Osiris) and facilitate document acquisition (Canvas) via Django-native patterns.

---

## 1. Executive Summary 🚀

Phase B transforms the platform from a data storage system into an intelligence-gathering hub. It focuses on:
- **Automated Metadata Scrapping**: Replicating browser-based requests to Osiris to fill gaps in course and teacher data.
- **Document Acquisition**: Using system-wide Canvas API tokens to download and store PDFs.
- **ORM-Centric Storage**: Moving from raw `pathlib` disk writes to Django's `FileField` system for better auditability and database-linked file management.
- **Asynchronous Orchestration**: Native integration with the Phase A ingestion pipeline to trigger enrichment automatically.

---

## 2. Architectural Deep Dive: Integration Points 🏗️

### 2.1 Core Model Enhancements (`apps.core.models`)
Phase B will directly extend the current `CopyrightItem` and relation models to store enrichment state.

#### [MODIFY] [CopyrightItem](file:///c:/dev/ea-cli-django/src/apps/core/models.py#L210)
Add fields to track enrichment lifecycle:
- `enrichment_status`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`.
- `last_enrichment_attempt`: `DateTimeField` for TTL calculation.
- `extraction_status`: Tracks progress of `kreuzberg` text extraction.
- `document`: `ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL)` (was OneToOne, now ForeignKey for deduplication).

#### [MODIFY] [Person](file:///c:/dev/ea-cli-django/src/apps/core/models.py#L151)
Enrich `Person` records with Osiris data:
- `is_verified`: Boolean indicating the person was found in Osiris.
- `metadata`: `JSONField` for additional scraper data (department info, titles).

### 2.2 New Domain Applications

#### `apps.enrichment` (Osiris & People Matching)
- **Model**: `EnrichmentJob(TaskedModel)`
    - Tracks a batch of items being enriched.
    - Fields: `job_type` (OSIRIS, PEOPLE_PAGE), `items_processed`, `errors`.
- **Service**: `OsirisScraperService`
    - `fetch_course_details(course_code: int) -> dict`
    - Logic: Uses `httpx` with full header replication from [osiris.py](file:///c:/dev/ea-cli-django/ea-cli/easy_access/enrichment/osiris.py).
    - Returns standardized dicts for `Course` and `Person` updates.

#### `apps.documents` (Canvas & Storage)
- **Model**: `Document(TimestampedModel)`
    - Fields: `file = FileField(upload_to="downloads/%Y/%m/")`, `filehash = CharField(max_length=255, unique=True)`, `original_url`.
    - Relations: `items = Reverse relation via CopyrightItem.document`.
- **Service**: `CanvasClientService`
    - `download_item_file(item: CopyrightItem) -> File`
    - Logic: Uses system-wide API token. Implements rate-limit handling (429 retries).
- **Service**: `PDFExtractorService`
    - `extract_content(doc: Document) -> str`
    - Logic: Wrapper around `kreuzberg.extract_file`.

---

## 3. Implementation Workflow: Sequence of Operations 🎡

### Step 1: Ingestion Pipeline Hook
The Phase B enrichment starts immediately after the Phase A [process_batch](file:///c:/dev/ea-cli-django/src/apps/ingest/tasks.py#L111) task completes.

```python
# target: apps.ingest.tasks.process_batch
def process_batch(batch_id):
    # ... existing Phase A processor logic ...

    # NEW: Trigger Phase B Enrichment
    from apps.enrichment.tasks import trigger_batch_enrichment
    trigger_batch_enrichment.delay(batch_id)
```

### Step 2: Osiris Scraping & Matching
The `OsirisScraperService` iterates through newly created `CopyrightItem` records that have a `course_code`.
1.  **Lookup**: Check `src.apps.core.Course` for existing fresh data (TTL check).
2.  **Scrape**: If missing/stale, replicate browser request to Osiris.
3.  **Sync**: Update `Course`, `Person`, and `CourseEmployee` relations.
4.  **Audit**: Log changes via `src.apps.core.ChangeLog` with `change_source=ENRICHMENT`.

### Step 3: Canvas Download & Storage
Items with a valid `url` containing `/files/` are queued for download.
- **Download**: Fetch raw bytes using system-wide token.
2.  **Deduplicate**: Before saving, calculate `xxh3_64` hash. If a `Document` with this hash already exists, link to it instead of creating a new one.
3.  **Store**: If new, wrap in `django.core.files.File` and save to the `Document` model's `FileField`.
4.  **Hash**: Store `hash` in `Document.filehash` and `CopyrightItem.filehash`.

---

## 4. Phase B — Logical Sprints 🗓️

### Sprint 1: Storage & Models 🧱
- **Implementation**: Define `EnrichmentJob` and `Document` models.
- **Migration**: Update `CopyrightItem` with enrichment status fields.
- **Config**: Move `CANVAS_API_TOKEN` and `OSIRIS_HEADERS` to `src/config/settings.py` (env-backed).

### Sprint 2: Scraper Services 🧬
- **Implementation**: Port `OsirisScraperService`.
- **Logic**: Implement the "Browser Header Replication" layer.
- **Verification**: Management command `verify_osiris_connection` to test scraping success.

### Sprint 3: Document Management 📂
- **Implementation**: `CanvasClientService` and `PDFExtractorService`.
- **Tooling**: Add `kreuzberg` to `pyproject.toml`.
- **Integration**: Ensure files are correctly saved to the media root using Django storage.

### Sprint 4: Dashboard Integration 📊
- **HTMX Partial**: Create `_enrichment_status.html` component.
- **UI**: Add "Enrich" button to item detail and batch list views.
- **Status**: Show progress bars (using Alpine.js + HTMX triggers) for long-running enrichment jobs.

---

## 5. Success Criteria ✅

- [x] **Auditability**: Every enrichment change is visible in the [ChangeLog](file:///c:/dev/ea-cli-django/src/apps/core/models.py#L344).
- [x] **Resilience**: Failed Osiris requests are logged in `EnrichmentJob.errors` and do not block the pipeline.
- [x] **Storage Integrity**: All downloaded PDFs are accessible via `Document.file.url`.
- [x] **Performance**: Enrichment runs asynchronously via Celery (simulated via background tasks), maintaining UI responsiveness.

---

## 6. Post-Implementation Summary 📝

### Key Technical Achievements
- **Document Deduplication**: Implemented content-based hashing (`xxh3_64`) to ensure a single `Document` record per unique file, significantly reducing storage overhead.
- **Scraper Reliability**: Reproduced browser headers exactly in `OsirisScraperService`, achieving stable data retrieval for courses and persons.
- **HTMX Integration**: The dashboard now supports real-time enrichment triggering and status updates without full page reloads.
- [x] **Pipeline Automation**: Enrichment is now a native stage of the data ingestion pipeline, triggered automatically upon batch processing completion.
- [x] **Frontend Polish**: Integrated Tailwind/DaisyUI for styling, added responsive navigation, and implemented manual enrichment triggers via HTMX.
