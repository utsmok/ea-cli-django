
# proposed updated refactor plan: ea-cli to Django v2.0 (Detailed)

**Version:** 2.0
**Date:** December 14, 2025

## 1. Introduction & Guiding Principles

This document provides a detailed, phase-by-phase plan to refactor the legacy `ea-cli` tool into a modern Django 6.0 application. The primary goal is to achieve full feature parity with the legacy system while adhering to modern best practices for performance, security, and maintainability.

This plan is based on an analysis of the legacy codebase and research into current (Dec 2025) best practices for the target technology stack.

### 1.1. Core Technologies & Best Practices

*   **Django 6.0:** We will follow modern Django patterns, including separated settings files for environments and robust security measures.
    *   *Reference:* [Django Documentation](https://docs.djangoproject.com/en/6.0/)
*   **uv:** Dependency and environment management will be handled exclusively by `uv`, following the specific workflow outlined in Phase 2.
    *   *Reference:* [uv Documentation](https://astral.sh/uv)
*   **Polars:** Data processing will leverage Polars' lazy API to ensure high performance and efficient memory usage.
    *   *Reference:* [Polars User Guide](https://docs.pola.rs/user-guide/)
*   **Docker:** The production environment will be containerized using Docker, following best practices for creating minimal, secure, and efficient images.
    *   *Reference:* [Docker Best Practices for Python Developers](https://testdriven.io/blog/docker-best-practices/)

---

## 2. Phase 1: Environment & Project Setup

This phase focuses on establishing a clean, reproducible development environment and initializing the Django project structure.

### 2.1. Dependency and Environment Management with `uv`

The project will use `uv` for all Python environment and package management tasks.

1.  **Initial Setup:** To create the virtual environment and install all dependencies from `pyproject.toml`, run:
    ```bash
    uv sync
    ```
    This single command will create a `.venv` directory if one doesn't exist and install the exact package versions specified in `uv.lock`.

2.  **Managing Dependencies:**
    *   To add a new package: `uv add <package-name>`
    *   To remove a package: `uv remove <package-name>`

### 2.2. Django Project Initialization

1.  **Create Core Apps:** The project will be organized into logical Django apps within the `src/apps/` directory. Initialize the following apps:
    *   `core`: For primary models (`CopyrightItem`, `Course`, `Organization`).
    *   `documents`: For PDF-related models and logic.
    *   `people`: For the `Person` model.
    *   `ingest`: For data ingestion tasks.
    *   `enrichment`: For external API integrations.
    *   `classification`: For business rules and ML models.
    *   `dashboard`: For user-facing views.
    *   `configuration`: For managing application settings.

2.  **Settings Configuration:**
    *   Implement separate settings files for different environments. The `src/config/settings/` directory will contain:
        *   `base.py`: Common settings shared across all environments.
        *   `development.py`: Settings for local development (e.g., `DEBUG=True`).
        *   `production.py`: Settings for the production environment.
    *   Use an environment variable (e.g., `DJANGO_SETTINGS_MODULE`) to specify which settings file to use.

---

## 3. Phase 2: Core Data Modeling

This phase focuses on creating a robust Django ORM schema that faithfully represents the legacy data structures.

*   *Legacy Reference (Models):* [`ea-cli/easy_access/db/models.py`](ea-cli/easy_access/db/models.py)
*   *Legacy Reference (Enums):* [`ea-cli/easy_access/db/enums.py`](ea-cli/easy_access/db/enums.py)

### 3.1. Implement Core Models

Translate the legacy Tortoise ORM models into Django models.

1.  **Enums (`apps.core.choices`):** Convert all enums from the legacy `enums.py` into Django `TextChoices` classes.
2.  **`CopyrightItem` (`apps.core.models`):** Create a complete Django model that includes all fields from the legacy `CopyrightItem` model.
3.  **`Organization`, `Programme`, `Course` (`apps.core.models`):**
    *   Implement the consolidated `Organization` model with a `type` field as discussed.
    *   Create distinct `Programme` and `Course` models.
4.  **`Person` (`apps.people.models`):** Create the `Person` model.
5.  **PDF Models (`apps.documents.models`):** Implement `PDF`, `PDFCanvasMetadata`, and `PDFText` models.

---

## 4. Phase 3: Configuration Management

This phase replaces the legacy `settings.yaml` with a dynamic, database-driven configuration system.

*   *Legacy Reference:* [`ea-cli/settings.yaml`](ea-cli/settings.yaml)

1.  **Develop Configuration Models (`apps.configuration.models`):**
    *   Create Django models to store settings from `settings.yaml`, including university structure, API settings, and data mappings.
2.  **Create Import Command:**
    *   Develop a Django management command (`import_settings`) to parse `settings.yaml` and populate the new configuration models.

---

## 5. Phase 4: Data Pipeline Implementation

This phase replicates the core data processing logic of the legacy CLI.

*   *Legacy Reference:* [`ea-cli/easy_access/pipeline.py`](ea-cli/easy_access/pipeline.py)

### 5.1. Ingestion (`apps.ingest`)

1.  **File Watcher:** Create a management command (`watch_files`) that uses `watchfiles` to monitor `raw_data/` for new files.
2.  **Ingestion Task:** Create a management command (`ingest_file`) that:
    *   Uses **Polars' lazy API** (`pl.scan_excel`) for efficient, memory-optimized data reading.
    *   Normalizes column names.
    *   Creates or updates `CopyrightItem` records.
    *   Logs any errors to the `ProcessingFailure` model.

### 5.2. Pipeline Stages (`apps.enrichment`)

Develop management commands for each legacy pipeline stage.

1.  **`process_items`:** Applies business rules and transformations.
2.  **`enrich_items`:** Fetches data from external APIs.
3.  **`check_file_existence`:** Verifies file existence via the Canvas API.
4.  **`export_data`:** Generates Excel reports.

### 5.3. Performance Optimization

*   All database queries in the pipeline should be optimized to avoid N+1 problems by using `select_related` and `prefetch_related` where appropriate.

---

## 6. Phase 5: Admin Tools & UI

This phase focuses on providing administrative utilities and a user-facing dashboard.

### 6.1. Failure Management

*   *Legacy Reference:* `admin inspect-failures` and `admin retry-failures` commands.
1.  **Create `ProcessingFailure` Model (`apps.ingest.models`):** Logs errors from the pipeline.
2.  **Admin Integration:**
    *   Register the `ProcessingFailure` model with the Django admin.
    *   Create a custom admin action to allow administrators to retry failed items.

### 6.2. Dashboard (`apps.dashboard`)

1.  **Develop HTMX Views:** Create views to serve HTMX-powered partials for a dynamic UI.
2.  **Implement Filtering:** Re-implement all filtering capabilities from the legacy dashboard.

---

## 7. Phase 6: Docker, Security & Finalization

This phase covers the final steps of containerization, security hardening, testing, and data migration.

### 7.1. Dockerization

Create a `Dockerfile` that follows modern best practices:

1.  **Multi-Stage Build:**
    *   Use a `builder` stage to install dependencies.
    *   Use a slim final stage (e.g., `python:3.13-slim`) to copy only the necessary artifacts, minimizing image size.
2.  **Non-Root User:** Create a non-root user to run the application.
3.  **Security Scanning:** Include a step in the CI/CD pipeline to scan the final image for vulnerabilities using a tool like `trivy`.

### 7.2. Security Hardening

*   Thoroughly review and apply Django's security best practices, including configurations for middleware, password policies, and protection against common vulnerabilities like XSS, CSRF, and SQL injection.
    *   *Reference:* [Django Security Documentation](https://docs.djangoproject.com/en/6.0/topics/security/)

### 7.3. Testing and Migration

1.  **Write Comprehensive Tests:** Develop a robust suite of unit and integration tests.
2.  **Create Data Migration Script:** Develop a management command to migrate data from the legacy SQLite database to the new PostgreSQL database.


---

# Review of new refactor plan

This is a strong foundational plan, particularly in its choice of modern tooling like `uv` and `Polars`. However, because it treats the transition from a CLI to a Web Application largely as a "data model port," it misses critical architectural components required for a functional web environment—specifically regarding **asynchronous task management**, **user authentication**, and **efficient data insertion**.

Since I cannot access the private repository, the following review is based on deep analysis of the artifacts described in your plan and standard pitfalls in CLI-to-Django refactors.

### **Critical Omissions & Architectural Risks**

#### **1. The "Blocking" Problem (Missing Task Queue)**
*   **The Issue:** Phase 5 proposes "Management Commands" for ingestion (`ingest_file`) and pipeline processing (`process_items`). While valid for a CLI, a web dashboard **cannot** run these directly. If a user clicks "Ingest" on the dashboard, the browser will timeout if the process takes more than 30 seconds.
*   **The Fix:** You **must** implement a Task Queue.
    *   **Recommendation:** Add **Celery** (with Redis) or **Django-Q2**.
    *   **Refactor Implication:** The logic inside your management commands should be refactored into *Task Functions* (e.g., inside `apps/ingest/tasks.py`). The management commands then become simple wrappers that trigger these tasks, and the UI can trigger the exact same tasks asynchronously.

#### **2. The `Person` vs. `User` Conflict**
*   **The Issue:** Phase 3.1 mentions creating a `Person` model in `apps.people`. In Django, if this person is logging into the dashboard, they must be the **Auth User**.
*   **The Fix:** You must decide on the User Model **before** running the first migration (Phase 2.1).
    *   **Recommendation:** If `Person` is the system user, do **not** create a separate `Person` model. Instead, create a custom user model: `class User(AbstractUser)` inside `apps.people` (or `apps.core`).
    *   **Settings:** Set `AUTH_USER_MODEL = 'people.User'` in `base.py` immediately. Changing this later is extremely difficult.

#### **3. Polars to Django ORM Bottleneck**
*   **The Issue:** Phase 5.1 mentions using Polars for "efficient reading" but then "creating/updating CopyrightItem records."
    *   If you iterate through a Polars DataFrame and call `CopyrightItem.objects.create()` row-by-row, you lose all performance gains. It will be slower than the legacy CLI.
*   **The Fix:** Use `bulk_create` / `bulk_update`.
    *   **Refactor Detail:** Convert the Polars DataFrame to a list of model instances (dictionaries) and use `CopyrightItem.objects.bulk_create(batch_size=1000)`.

---

### **Detailed Phase-by-Phase Improvements**

Here are the specific additions needed to make the plan correct and complete.

#### **Phase 2: Core Data Modeling (Additions)**
*   **2.3 Custom User Model:** Explicitly define the Custom User Model strategy here.
    *   *Action:* Create `apps/users` or use `apps/people` to host the custom user.
*   **2.4 UUIDs:** For a data-heavy app likely to undergo migration, consider using `UUIDField` as the primary key (`id`) for `CopyrightItem` and `Organization` to prevent integer collision during imports.

#### **Phase 4: Configuration (Additions)**
*   **4.1 Secrets Management:** `settings.yaml` likely contained API keys.
    *   *Action:* Ensure `production.py` reads secrets (Canvas API tokens, DB passwords) from **Environment Variables**, not the database config model. Use `django-environ`. Database-stored config should only be for business logic (e.g., "Semester Start Date"), not credentials.

#### **Phase 5: Data Pipeline (Major Refactor Required)**
*   **5.1 Task Queue Integration:**
    *   Add `redis` service to `docker-compose.yml`.
    *   Install `celery` and `django-celery-results`.
*   **5.2 PDF Handling (Media Storage):**
    *   The plan mentions `documents` models. You need a strategy for storing the actual PDF files.
    *   *Action:* In `production.py`, configure `STORAGES`. If deploying to cloud, use `django-storages` with S3/Azure Blob. If local, ensure the Docker volume for `/media` is persistent.
*   **5.3 Idempotency:**
    *   The `ingest_file` command needs logic to prevent processing the same file twice.
    *   *Add:* A `FileHash` check or a status field on the `SourceFile` model.

#### **Phase 6: Admin & UI (Refinements)**
*   **6.3 User Feedback:**
    *   Since ingestion is now async (see point 1), the Dashboard needs a mechanism to show progress.
    *   *Add:* A polling mechanism in HTMX or a WebSocket (Django Channels) to update the "Ingestion Status" bar on the dashboard.

#### **Phase 7: Docker & Deployment (Additions)**
*   **7.4 Web Server Gateway:**
    *   `manage.py runserver` is for dev only.
    *   *Action:* Add **Gunicorn** (for WSGI) or **Uvicorn** (for ASGI/Async) to the `uv` dependencies. Update the Docker `CMD` to run `gunicorn config.wsgi:application`.
*   **7.5 Static Files:**
    *   *Action:* Add `Whitenoise` to the middleware to serve static files (CSS/JS) efficiently in production without a separate Nginx container complexity.

---

### **Revised Plan Snippet (Phase 5 Example)**

*Below is how Phase 5 should look to be "correct":*

## 5. Phase 5: Data Pipeline & Async Processing

This phase replicates the core logic using **Celery** for background execution to ensure the web UI remains responsive.

### 5.1. Async Architecture
1.  **Setup Celery:** Configure Celery with Redis as the broker.
2.  **Refactor Logic:** Move logic from CLI scripts to `apps/ingest/services.py`.
3.  **Define Tasks:** Create `apps/ingest/tasks.py` to wrap service logic (e.g., `@shared_task def task_ingest_file(file_path)`).

### 5.2. Ingestion (`apps.ingest`)
1.  **Ingest Service:**
    *   Use **Polars** to read Excel/CSV.
    *   **Optimization:** Transform Polars DF to dictionaries. Use `CopyrightItem.objects.bulk_create(..., ignore_conflicts=True)` for high-speed insertion.
2.  **File Watcher:** Keep this as a management command (`watch_files`), but instead of processing files directly, it should **dispatch a Celery task** when a file is found.

### 5.3. Enrichment & Export
1.  **Rate Limiting:** Use Celery's rate limiting features for `enrich_items` (Canvas API) to prevent 429 errors.
2.  **Export:** `export_data` should generate the Excel file, save it to `Media`, and email the link or notify the user via the Dashboard.

---

# Reply to the revised plan above

- django 6 adds in built tasks management, so we can use that instead of a library like celery.
- person vs user: person data is not related to users, persons are teachers/authors in item metadata


You can find the full legacy codebase in git submodule `ea-cli/`, and this should give more context for finalizing the refactor plan. Please review again with this additional data.

---

Based on the comprehensive legacy code provided and your specific constraints regarding **Django 6.0 built-in tasks** and the **Person vs. User distinction**, here is the reviewed and improved refactor plan.

### **Code Analysis & Findings**

1.  **Dependency on Local Filesystem:**
    *   *Legacy:* The code heavily utilizes `pathlib` to move, rename, and backup Excel files locally (e.g., `easy_access/sheets/backup.py`, `finalize_sheet` in `sheet.py`).
    *   *Web Refactor Risk:* In a Dockerized web app, writing to the local filesystem is ephemeral. Generated reports must be saved to Django `FileField`s (backed by S3 or a persistent volume) rather than relying on `os.replace` or local folder structures.

2.  **Complex Excel Logic:**
    *   *Legacy:* `easy_access/sheets/sheet.py` contains intricate `openpyxl` logic for specific table styling, conditional formatting, and data validation (dropdowns).
    *   *Refactor Need:* This cannot simply be "export data." The logic in `DataEntrySheet` and `finalize_sheet` must be ported to a dedicated `ReportGenerationService`.

3.  **The "Person" Entity:**
    *   *Legacy:* `easy_access/enrichment/osiris.py` scrapes external HTML (`people.utwente.nl`) to populate `Person`.
    *   *Confirmation:* You are correct; these are **not** system users. They are scraped metadata entities linked to Courses.
    *   *Refactor:* The `apps.people` app should remain distinct from `apps.users`.

4.  **Orchestration:**
    *   *Legacy:* `easy_access/pipeline.py` runs stages sequentially.
    *   *Refactor:* With Django 6 background tasks, these stages (Ingest -> Process -> Enrich) should be chained tasks, allowing the UI to report progress on specific steps.

---

### **Refactor Plan Review: Corrections & Improvements**

Below is the updated plan. I have removed the "Celery" requirement (replacing it with Django 6 Tasks) and clarified the Data vs. Auth models.

#### **1. Architecture Updates**

*   **Task Management:** Use Django 6.0 `db_background_tasks` (or the equivalent built-in async task feature in v6) for `ingest`, `enrich`, and `export`.
*   **Storage:** Replace direct `pathlib` manipulation with **Django Storages**.
    *   *Why:* The legacy code creates backups (`_backup_YYYY...`) and moves files between "Inbox", "In Progress", and "Done" folders. In a web app, these should be status flags in the DB, not physical folder locations.

#### **2. Phase 2: Core Data Modeling (Revised)**

*   **`apps.users` (New):**
    *   Create a custom `User` model here for application login (Admins/Editors).
*   **`apps.people` (Refined):**
    *   **Model:** `Person` (Stores scraped data: `input_name`, `people_page_url`, `orgs` JSON).
    *   **No Auth Link:** Do not link this to `settings.AUTH_USER_MODEL`.
*   **`apps.core` (Refined):**
    *   **Model:** `CopyrightItem` (The "God model").
        *   *Optimization:* The legacy code uses `tortoise.fields.JSONField` for extracting data. Ensure Django's `JSONField` is used with a GIN index (Postgres) for performance.
    *   **Model:** `Course` (Links to `Person` via `CourseEmployee`).
*   **`apps.ingest` (Staging):**
    *   Keep the `StagedCopyrightItem` model strategy found in `db/models.py`. It is crucial for holding raw Polars imports before validation.

#### **3. Phase 5: Pipeline & Tasks (Major Update)**

*   **Logic Porting:**
    *   Legacy `pipeline.py` `run_async` methods become **Django Background Tasks**.
*   **Step 5.1: Ingestion Task:**
    *   Create task `ingest_raw_sheet(file_id)`:
        1.  Load Excel using **Polars**.
        2.  Run `standardize_dataframe` (port logic from `utils.py`).
        3.  Bulk insert into `StagedCopyrightItem`.
        4.  Trigger `process_staged_items` task.
*   **Step 5.2: Enrichment Task (Osiris):**
    *   Port `enrichment/osiris.py` to `apps.enrichment.services.OsirisService`.
    *   **Critical:** This module uses `httpx` and `BeautifulSoup`. Keep this async structure. Django 6 supports async views/tasks natively, so `httpx` fits perfectly.
*   **Step 5.3: PDF Handling:**
    *   Legacy `db/retrieve.py` detects "deleted" PDFs.
    *   Implement `CanvasService` in `apps.documents` to handle the API calls found in `retrieve_unmarked_deleted_items`.

#### **4. Phase 6: Export & Reporting (Crucial Fixes)**

*   **Step 6.1: The Excel Generator:**
    *   Port `easy_access/sheets/sheet.py` to `apps.reporting.services.ExcelBuilder`.
    *   **Requirement:** Must support `openpyxl` TableStyles and DataValidation (dropdowns) as seen in legacy `DataEntrySheet`.
*   **Step 6.2: Workflow File Logic:**
    *   *Legacy Behavior:* The app generates `inbox.xlsx`, `in_progress.xlsx`, `done.xlsx` on the disk.
    *   *Web Behavior:* The app should **generate these on the fly** via a View, or generate and save them to a `GeneratedReport` model with a `FileField`.
    *   **Do not** try to replicate the folder-moving logic (`backup.py`) on the server. Use database state to filter `CopyrightItem.objects.filter(workflow_status='ToDo')` and generate the Excel file when requested.

---

### **Detailed Refactor Plan v2.1**

```markdown
# Comprehensive Refactor Plan: ea-cli to Django v6.0

**Version:** 2.1
**Date:** December 14, 2025

## 1. Project Setup & Configuration

### 1.1. Environment
*   **Manager:** `uv` (as per previous plan).
*   **Framework:** Django 6.0 (Async enabled).
*   **Database:** PostgreSQL (Required for efficient JSONField querying used in `Course` data).

### 1.2. App Structure
*   `apps.users`: Authentication (System Admins).
*   `apps.core`: Main domain (`CopyrightItem`, `Organization`).
*   `apps.people`: Scraped academic staff (`Person`).
*   `apps.courses`: Academic courses (`Course`, `CourseEmployee`).
*   `apps.documents`: PDF management and Canvas metadata.
*   `apps.ingest`: Staging tables and Polars logic.
*   `apps.enrichment`: Osiris/Scraping services.
*   `apps.reporting`: Excel generation (`openpyxl` logic).

---

## 2. Data Modeling (Migration from Tortoise)

### 2.1. Core Models (`apps.core`)
*   **`CopyrightItem`**:
    *   Port all fields from legacy `db/models.py`.
    *   Convert `CharEnumField` to Django `TextChoices` (e.g., `WorkflowStatus`, `ClassificationV2`).
    *   **Change:** `file_exists` (legacy: boolean/int mixed) -> `BooleanField(null=True)`.
*   **`Organization` / `Faculty`**:
    *   Use `django-mptt` or `django-treebeard` if hierarchy depth > 2, otherwise self-referential ForeignKey is fine (Legacy `hierarchy_level` suggests simple depth).

### 2.2. People & Courses (`apps.people`, `apps.courses`)
*   **`Person`**:
    *   Fields: `input_name`, `main_name`, `people_page_url` (Unique Key), `match_confidence`.
    *   *Note:* This is decoupled from `apps.users`.
*   **`Course`**:
    *   Fields: `cursuscode` (PK), `internal_id`.
    *   Rel: `teachers` (ManyToMany to `Person` through `CourseEmployee`).

---

## 3. Business Logic & Services

### 3.1. Ingestion Service (`apps.ingest`)
*   **Input:** Uploaded Excel file.
*   **Tool:** `Polars`.
*   **Logic:**
    1.  Read Excel using `pl.read_excel`.
    2.  Apply `standardize_dataframe` (Legacy `utils.py`).
    3.  Bulk insert to `StagedCopyrightItem` model.
    4.  Call `MergeService` to upsert from Staging to Core (Port logic from `db/update.py`).

### 3.2. Enrichment Service (`apps.enrichment`)
*   **Osiris Scraper:**
    *   Port `enrichment/osiris.py`.
    *   Use `httpx` (Async) to scrape `people.utwente.nl`.
    *   Implement `Levenshtein` matching logic found in legacy `fetch_person_data`.
*   **Canvas Integration:**
    *   Port `pdf/download.py` logic.
    *   Store downloaded PDFs to `apps.documents.models.PDF` (using `FileField` backed by S3/Minio).

### 3.3. Reporting Service (`apps.reporting`)
*   **Excel Engine:**
    *   Port `sheets/sheet.py`.
    *   Implement `DataEntrySheet` class to handle `openpyxl` TableStyles.
    *   **Crucial:** Re-implement the `finalize_sheet` function which adds Data Validation (dropdowns) to exported sheets. This is critical for the "Data Entry" workflow.

---

## 4. Background Tasks (Django 6.0)

Replace "Management Commands" with Django 6 background tasks.

### 4.1. Task Definitions
*   `@background_task` **`ingest_file_task(file_id)`**:
    *   Runs the Polars ingestion pipeline.
*   `@background_task` **`enrich_osiris_data_task()`**:
    *   Orchestrates the scraping of missing course/person data.
    *   Respects TTL (Time To Live) logic found in legacy `enrichment/osiris.py`.
*   `@background_task` **`generate_faculty_report_task(faculty_abbrev)`**:
    *   Generates the "Inbox/InProgress/Done" Excel files.
    *   Saves result to `GeneratedReport` model.

---

## 5. Migration Strategy (Data)

### 5.1. SQLite to Postgres
*   Legacy data is in SQLite (`easy_access/db/base.py`).
*   **Script:** Create a specialized management command `migrate_legacy_sqlite` that:
    1.  Connects to the legacy SQLite file.
    2.  Iterates `CopyrightItem` rows.
    3.  Maps enums (e.g., `WorkflowStatus.ToDo` -> `todo`).
    4.  Inserts into Postgres.

---

## 6. UI/Dashboard (`apps.dashboard`)

*   **Views:**
    *   `DashboardView`: Stats (Port `dashboard/dash.py` logic).
    *   `UploadView`: Upload raw Excel for ingestion.
    *   `ReportView`: List generated Excel files for download.
*   **HTMX:**
    *   Use HTMX to poll the status of Background Tasks (Ingestion progress bar).

```
