# Comprehensive Refactor Plan: ea-cli to Django v2.0 (Detailed)

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
