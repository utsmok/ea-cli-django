# Specification: Core Ingestion and Legacy Export Parity

**Objective:** Implement and verify the core data ingestion pipeline for both Qlik and Faculty data sources, and ensure the Excel export functionality matches the legacy system's output with 100% fidelity in structure, style, and data.

## 1. Functional Requirements

### 1.1. Two-Phase Ingestion Pipeline
- **Staging:** The system must read raw data from uploaded Qlik and Faculty Excel files and store it in dedicated staging models (ingest.QlikEntry, ingest.FacultyEntry). This phase must not alter the core CopyrightItem data.
- **Processing:** A separate, triggerable process must read from the staging models, apply merge rules, and update the core CopyrightItem table.
- **Auditability:** Every creation or modification of a CopyrightItem must generate a core.ChangeLog entry, linking the change to the source ingestion.IngestionBatch and the user who initiated the upload.

### 1.2. Data Standardization
- All incoming data must be processed through a DataFrameStandardizer service.
- This service is responsible for:
    - Normalizing column headers.
    - Standardizing null values (e.g., "N/A", "-", "") to None.
    - Mapping department codes to their corresponding faculty abbreviations.

### 1.3. Merge & Conflict Resolution
- The system must enforce strict field ownership rules:
    - **Qlik:** Can create new items and update system-of-record fields (e.g., 	title, author, student counts).
    - **Faculty:** Can only update human-annotated fields (e.g., v2_manual_classification, workflow_status,
emarks) on existing items.
- A BatchProcessor service will orchestrate this logic, using the defined merge rules to prevent data cross-contamination.

### 1.4. High-Fidelity Excel Export
- The system must generate per-faculty Excel workbooks that are functionally and visually identical to the legacy ea-cli exports.
- **Structural Parity:**
    - Two-sheet structure: "Complete data" (read-only) and "Data entry" (editable).
    - Hidden _ea_lists sheet for populating data validation dropdowns.
- **Styling and Formatting:**
    - Conditional formatting must be applied to file_exists, workflow_status, and v2_lengte columns, matching legacy color schemes.
    - Specific columns must be protected (read-only) on the "Data entry" sheet.
- **Data & Workflow Parity:**
    - Exports must be separated into workflow buckets (inbox, in_progress, done, overview).
    - The system must create timestamped backups of previous exports and generate update_info.txt and update_overview.csv files to track changes.

## 2. Non-Functional Requirements
- **Performance:** The Polars-based DataFrameStandardizer and prefetch_related in export queries should ensure that a full-scale export (~1,500 items) completes in under 10 seconds.
- **Test Coverage:** All services (Standardizer, Processor, ExcelBuilder) must be covered by unit and integration tests.
- **Code Style:** All new code must adhere to the guidelines in conductor/product-guidelines.md, including the use of uv,
uff, modern type hints, and Google-style docstrings.

## 3. Verification & Success Criteria
- **Ingestion:** Successfully ingest a test Qlik file, creating new CopyrightItem records and associated ChangeLog entries.
- **Update:** Successfully ingest a test Faculty sheet, updating only the designated "human-editable" fields on existing items.
- **Export Parity:** The compare_exports.py script must show >99% structural and data parity between the generated Django export and a golden-standard legacy export.
- **Round-Trip Test:** An exported "Data entry" sheet can be modified, re-ingested, and the changes are correctly applied and logged.