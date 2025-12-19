# Plan: Core Ingestion and Legacy Export Parity

**Objective:** Implement and verify the core data ingestion and export pipelines to achieve full parity with the legacy ea-cli system.

---

### Phase 1: Verify and Solidify Core Architecture

- **Task:** Review and confirm that the existing models in pps.core, pps.ingest, and pps.users align with the project's architectural goals.
- **Task:** Write unit tests for all existing models to confirm field types, relationships, and constraints.
- **Task:** Conductor - User Manual Verification 'Verify and Solidify Core Architecture' (Protocol in workflow.md)

### Phase 2: Ingestion Pipeline Verification

- **Task:** Write comprehensive integration tests for the Standardizer service (pps/ingest/services/standardizer.py) to validate column mapping, null handling, and faculty assignment against real-world data samples.
- **Task:** Create integration tests for the BatchProcessor service (pps/ingest/services/processor.py) to confirm that Qlik and Faculty merge rules are correctly enforced.
    - *Sub-task:* Test that Qlik data creates new items and only updates system fields on existing items.
    - *Sub-task:* Test that Faculty data only updates human-annotated fields and never creates new items.
- **Task:** Write an end-to-end integration test that simulates a user uploading a Qlik file, followed by a Faculty file, and verifies the final state of the CopyrightItem and ChangeLog in the database.
- **Task:** Conductor - User Manual Verification 'Ingestion Pipeline Verification' (Protocol in workflow.md)

### Phase 3: Legacy Export Parity

- **Task:** Implement and test the ExcelBuilder service (pps/ingest/services/excel_builder.py) to ensure it generates a two-sheet ("Complete data", "Data entry") workbook.
- **Task:** Add tests to 	est_excel_builder.py to verify that conditional formatting rules for ile_exists, workflow_status, and 2_lengte are applied correctly using openpyxl.
- **Task:** Implement and test the backup and update tracking functionality, ensuring that timestamped backups and update_info files are created upon export.
- **Task:** Create a full-scale integration test that:
    1. Loads a complete set of legacy data via the load_legacy_data command.
    2. Runs the export_faculty_sheets command.
    3. Uses the compare_exports.py script to validate the output against a pre-generated "golden" legacy export file.
- **Task:** Conductor - User Manual Verification 'Legacy Export Parity' (Protocol in workflow.md)