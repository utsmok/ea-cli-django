# Master Development Plan: Easy Access Platform v2.0
**Date:** December 16, 2025
**Target Stack:** Django 6.0, Python 3.12+, PostgreSQL 17, Polars, Docker, CatBoost, HTMX.

## 1. Executive Summary

This document serves as the unified source of truth for refactoring the legacy `ea-cli` tool (Python/Pandas/TortoiseORM) into a modern, scalable Web Platform (`copyright-platform`).

**Goal:** Create a robust system for managing copyright compliance in university course materials.
**Key Shift:** Moving from a local CLI tool that manipulates Excel files on disk to a collaborative Web Application with a centralized database, asynchronous processing, and intelligent classification.

---

## 2. Architecture & Tech Stack

### 2.1 Core Technologies
*   **Web Framework:** Django 6.0 (Async enabled).
*   **Database:** PostgreSQL 17 (Required for efficient JSONField querying and huge dataset support).
*   **Task Queue:** Django 6.0 `db_background_tasks` (Native async tasks) or Celery (if higher throughput needed). *Decision: Start with Native Tasks.*
*   **Data Processing:** Polars (High-performance DataFrame handling for Excel ingestion).
*   **Frontend:** HTMX (Dynamic interactions), Alpine.js (Client state), TailwindCSS/DaisyUI (Styling).
*   **Intelligence:** CatBoost (Gradient Boosting for classification), Scikit-Learn/Levenshtein (fuzz matching).
*   **Environment:** Docker Compose (Production parity).

### 2.2 Project Structure
The project lives in `src/` and is organized into decoupled Django apps:

```text
src/
├── apps/
│   ├── core/              # Domain Models (CopyrightItem, Course, Person)
│   ├── users/             # System Authentication (Admins, Editors) - [NEW]
│   ├── ingest/            # Data Ingestion (Polars pipeline)
│   ├── enrichment/        # External APIs (Osiris, Canvas)
│   ├── classification/    # ML & Rule Engine - [NEW]
│   ├── documents/         # PDF Storage & Processing
│   ├── dashboard/         # UI Views (HTMX)
│   └── api/               # REST/Ninja API (Optional, for Widget)
├── config/                # Settings & WSGI/ASGI
└── manage.py
```

---

## 3. Data Architecture Strategy

The schema is undergoing a strict migration from TortoiseORM (`ea-cli`) to Django Models.

### 3.1 Core Models (`apps.core`)
*   **`CopyrightItem`**: The central entity.
    *   **Migration Note:** Fields must match `ea-cli/easy_access/db/models.py`.
    *   **Enums:** All strings must be converted to `django.db.models.TextChoices`.
*   **`Organization` / `Faculty`**: Hierarchical data.
*   **`Course`**: Academic courses.
*   **`StagedItem`**: A temporary holding pen for raw Excel data before it is validated and merged into `CopyrightItem`.

### 3.2 People vs. Users (Crucial Distinction)
*   **`apps.users.User`**: The **Application User** (e.g., Copyright Office Employee) who logs in to the dashboard.
    *   *Implementation:* Extend `AbstractUser`.
*   **`apps.core.Person`**: A **Metadata Entity** (e.g., a Professor teaching a course).
    *   *Relationship:* `Person` is linked to `Course` via `CourseEmployee`.
    *   *Note:* A `Person` does NOT log in. They are data scraping targets.

---

## 4. Module Implementation Plan

### 4.1 Ingestion Module (`apps.ingest`)
Responsibility: Reading raw Excel files and populating `StagedItem`.

*   **Technology:** Polars (`pl.read_excel`, `pl.scan_excel`).
*   **Workflow:**
    1.  User uploads Excel via Dashboard.
    2.  `ingest_task(file)` triggers in background.
    3.  Polars reads file, normalizes headers (using legacy `standardize_dataframe` logic).
    4.  Bulk Insert into `StagedItem`.
    5.  Trigger `merge_task` to upsert valid items into `CopyrightItem`.
*   **Legacy Reference:** `ea-cli/easy_access/utils.py` (Standardization logc).

### 4.2 Documents Module (`apps.documents`)
Responsibility: Managing PDF files and Canvas Metadata.

*   **Storage:** Use `django-storages` (S3-compatible) or persistent Docker Volume.
*   **Models:**
    *   `PDF`: Stores file reference, page count, and extraction status.
    *   `PDFCanvasMetadata`: Locking status, visibility settings from Canvas.
*   **Logic:** Port `pdf/download.py` to async services using `httpx`.

### 4.3 Enrichment Module (`apps.enrichment`)
Responsibility: Fetching missing data from external sources.

*   **Osiris Service:** Scrapes `people.utwente.nl` or Osiris API.
    *   *Logic:* Async `httpx` scraper.
    *   *Retry Policy:* Respect API rate limits.
*   **Canvas Service:** Checks if files still exist on Canvas.

### 4.4 Intelligence Module (`apps.classification`)
Responsibility: Automated classification of items (`Open License`, `Own Work`, etc.).

*   **Architecture:** Hybrid Funnel.
    1.  **Gate 1 (Rules):** Deterministic Python classes (e.g., `OwnWorkRule` checks if Author == Teacher).
    2.  **Gate 2 (Heuristics):** Fuzzy string matching (Levenshtein).
    3.  **Gate 3 (ML):** CatBoost Classifier.
*   **Interactive Widget:**
    *   An `AnyWidget` (Python+React) implementation for use in Jupyter/Marimo notebooks.
    *   Allows data scientists to label "low confidence" items directly in a notebook environment.

### 4.5 Dashboard Module (`apps.dashboard`)
Responsibility: The main user interface.

*   **Views:**
    *   `InboxView`: Filter items with `workflow_status='ToDo'`.
    *   `DetailView`: Split screen (PDF preview + Metadata form).
*   **HTMX Features:**
    *   **Inline Editing:** Change status/classification without page reload.
    *   **Polling:** Progress bars for long-running Ingestion tasks.

---

## 5. Development Roadmap (Step-by-Step)

### Phase 1: Foundation (Current Status)
- [x] Scaffold Django Project.
- [x] Initial `core` models port (partial).
- [ ] **Action:** Finish porting `PDF` and `PDFCanvasMetadata` models to `apps.documents`.
- [ ] **Action:** Create `apps.users` and configure `AUTH_USER_MODEL`.

### Phase 2: Ingestion Pipeline
- [ ] Implement `apps.ingest.services.IngestService` using Polars.
- [ ] Create `ingest_file` background task.
- [ ] Verify massive Excel import (performance check).

### Phase 3: Migration Data
- [ ] Write `management/commands/migrate_legacy_sqlite.py`.
- [ ] Import data from `ea-cli/copyright.db` (SQLite) to Postgres.
- [ ] Verify checksums/counts.

### Phase 4: UI & Dashboard
- [ ] create `base.html` with Tailwind/DaisyUI.
- [ ] Implement `CopyrightItemListView` with HTMX filtering.
- [ ] Implement "Split View" for PDF inspection.

### Phase 5: Intelligence Layer
- [ ] Implement `apps.classification.pipeline.rules`.
- [ ] Train initial CatBoost model on migrated data.
- [ ] Connect `run_classification_pipeline` to the Ingestion trigger.

### Phase 6: Interactive Widget
- [ ] Build `apps/classification/widget` (JS bundle).
- [ ] Test `CopyrightLabeler` widget in a Marimo notebook within Docker.

---

## 6. Guidelines & Best Practices

*   **Async First:** Code dealing with I/O (Canvas API, Disk, DB) should be async compatible where possible.
*   **Type Hinting:** All new code must be fully typed (`mypy` strictness compliant).
*   **Testing:**
    *   `pytest-django` for all tests.
    *   Integration tests for the Pipeline are critical.
*   **No "Magical" Folders:** Unlike the CLI, do not rely on moving files between physical folders (`Inbox/`, `Done/`). Use Database Statuses!

## 7. Next Immediate Steps
1.  Complete the model definitions in `src/apps/documents/models.py`.
2.  Set up the `apps.users` app and finalize the Auth model.
3.  Write the `migrate_legacy_sqlite` command to populate the DB with real data for testing.
