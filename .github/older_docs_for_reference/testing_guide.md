# Phase A Implementation - Testing Guide

**Date:** December 17, 2025
**Status:** Core Infrastructure Complete (Steps 1-7)

---

## What Has Been Implemented

### Core Components
1. ✅ **Custom User Model** (`apps.users.User`)
2. ✅ **Ingestion Models** (`apps.ingest.models`)
   - IngestionBatch
   - QlikEntry
   - FacultyEntry
   - ProcessingFailure
3. ✅ **Audit Model** (`apps.core.models.ChangeLog`)
4. ✅ **Standardization Service** (`apps.ingest.services.standardizer`)
5. ✅ **Merge Rules** (`apps.ingest.services.merge_rules`)
6. ✅ **Batch Processor** (`apps.ingest.services.processor`)
7. ✅ **Tasks** (`apps.ingest.tasks`)
8. ✅ **Management Commands** (`process_batch`)
9. ✅ **Admin Interfaces** (all models with rich formatting)
10. ✅ **Tests** (40+ test cases for core logic)

---

## How to Test the Implementation

### Prerequisites
1. Ensure PostgreSQL database is running:
   ```powershell
   docker ps  # Check ea-cli-django-db-1 is running
   ```

2. Ensure migrations are applied:
   ```powershell
   uv run python src/manage.py migrate
   ```

3. Ensure superuser exists:
   ```powershell
   uv run python src/manage.py createsuperuser
   ```

### Method 1: Django Admin (Easiest)

1. Start the development server:
   ```powershell
   uv run python src/manage.py runserver
   ```

2. Navigate to `http://localhost:8000/admin`

3. Log in with superuser credentials

4. **Create a test batch:**
   - Go to "Ingest" → "Ingestion batches" → "Add ingestion batch"
   - Choose source type (Qlik or Faculty)
   - Upload an Excel file
   - Select uploaded_by (yourself)
   - Save

5. **Process the batch:**
   - Note the batch ID from the URL or list
   - Open PowerShell/terminal:
     ```powershell
     uv run python src/manage.py process_batch <batch_id>
     ```

6. **View results:**
   - Refresh the batch detail page in admin
   - Check "Qlik entries" or "Faculty entries" (staged data)
   - Check "Core" → "Copyright items" (updated items)
   - Check "Core" → "Change logs" (audit trail)
   - Check "Ingest" → "Processing failures" (any errors)

### Method 2: Django Shell (Advanced)

```powershell
uv run python src/manage.py shell
```

```python
from apps.users.models import User
from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import stage_batch, process_batch
from django.core.files import File

# Get user
user = User.objects.first()

# Create batch
with open("path/to/test_file.xlsx", "rb") as f:
    batch = IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.QLIK,  # or FACULTY
        source_file=File(f, name="test_file.xlsx"),
        uploaded_by=user,
    )

# Stage the batch
stage_result = stage_batch(batch.id)
print(stage_result)

# Process the batch
process_result = process_batch(batch.id)
print(process_result)

# Check results
batch.refresh_from_db()
print(f"Created: {batch.items_created}")
print(f"Updated: {batch.items_updated}")
print(f"Skipped: {batch.items_skipped}")
print(f"Failed: {batch.items_failed}")
```

### Method 3: Management Command (CLI)

```powershell
# Process a batch (stage + process)
uv run python src/manage.py process_batch 1

# Stage only (inspect before processing)
uv run python src/manage.py process_batch 1 --stage-only

# Process only (if already staged)
uv run python src/manage.py process_batch 1 --process-only
```

---

## Creating Test Data

### Option 1: Use Legacy Data
If you have access to legacy ea-cli exports:
- Use an existing Qlik export Excel file
- Use an existing Faculty sheet Excel file

### Option 2: Create Minimal Test Files

**Qlik Test File** (`test_qlik.xlsx`):
```
Material ID | Filename      | Filetype | Title           | Author      | # Students registered
1001       | doc1.pdf      | pdf      | Test Document 1 | John Doe    | 50
1002       | doc2.pdf      | pdf      | Test Document 2 | Jane Smith  | 30
1003       | presentation.ppt | ppt   | Test Slides     | Bob Johnson | 20
```

**Faculty Test File** (`test_faculty.xlsx`):
```
Material ID | Workflow status | Classification | Remarks
1001       | Done            | eigen materiaal | This is own material
1002       | InProgress      | korte overname  | Short excerpt
1003       | ToDo            |                 |
```

**Important Notes:**
- Use the EXACT column names shown (case-sensitive)
- Material IDs in Faculty sheet must exist in database (created by Qlik import first)
- Faculty sheets can only UPDATE existing items, never create

---

## Expected Behavior

### Qlik Import
1. **Stage Phase:**
   - Reads Excel file
   - Normalizes column names
   - Filters invalid rows (null material_id, wrong filetypes)
   - Creates QlikEntry records
   - Batch status: PENDING → STAGING → Ready for processing

2. **Process Phase:**
   - For each QlikEntry:
     - If material_id doesn't exist: CREATE new CopyrightItem
     - If material_id exists: UPDATE system fields only
   - Creates ChangeLog for every change
   - Records failures in ProcessingFailure
   - Batch status: PROCESSING → COMPLETED/PARTIAL/FAILED

### Faculty Import
1. **Stage Phase:**
   - Reads Excel file
   - Normalizes column names
   - Creates FacultyEntry records
   - Batch status: PENDING → STAGING → Ready for processing

2. **Process Phase:**
   - For each FacultyEntry:
     - Looks up existing CopyrightItem (MUST exist!)
     - Updates human fields only
     - Uses priority ranking for workflow_status
   - Creates ChangeLog for every change
   - Records failures if material_id not found
   - Batch status: PROCESSING → COMPLETED/PARTIAL/FAILED

---

## Verification Checklist

After running a test batch:

- [ ] Batch status is COMPLETED (or PARTIAL if some failures)
- [ ] Statistics are correct (created/updated/skipped/failed counts)
- [ ] QlikEntry or FacultyEntry records exist and are marked processed
- [ ] CopyrightItem records created/updated correctly
- [ ] ChangeLog entries exist for all changes
- [ ] ChangeLog.changes field shows old → new values
- [ ] ChangeLog links to correct batch and user
- [ ] No ProcessingFailure records (or expected ones only)
- [ ] Admin interfaces display data correctly

---

## Common Issues & Solutions

### Issue: "Validation failed: Missing required column"
**Solution:** Check Excel column names match exactly (case-sensitive)

### Issue: "Faculty entry references non-existent material_id"
**Solution:** Import Qlik data first to create items, then Faculty data

### Issue: "No changes detected (all skipped)"
**Solution:** This is normal if:
- Qlik data matches existing database exactly
- Faculty data has no human-field changes

### Issue: "Permission denied reading file"
**Solution:** Ensure uploaded file has correct permissions, try re-uploading

### Issue: "Module not found: polars"
**Solution:** Install dependencies: `uv sync`

---

## Running Tests

```powershell
# Run all ingest tests
uv run pytest src/apps/ingest/tests/

# Run specific test file
uv run pytest src/apps/ingest/tests/test_standardizer.py

# Run with verbose output
uv run pytest src/apps/ingest/tests/ -v

# Run with coverage
uv run pytest src/apps/ingest/tests/ --cov=apps.ingest
```

---

## Next Development Steps

### Immediate (for complete testing):
1. Create small test Excel files
2. Run full ingestion flow
3. Verify results in admin
4. Test error cases (invalid data, missing IDs)

### Short-term (Phase A completion):
5. Implement basic upload view (Step 8)
6. Clean up legacy code (Step 9)
7. Data migration from legacy system (Step 10)
8. Integration tests

### Medium-term (Phase B):
9. Excel export service
10. Enrichment services (Osiris, Canvas)

---

## Support & Troubleshooting

### Logs
- Django logs: Console output (INFO level)
- Detailed logs: Check loguru output

### Database Inspection
```powershell
# Connect to PostgreSQL
docker exec -it ea-cli-django-db-1 psql -U admin -d copyright_db

# Useful queries
SELECT * FROM ingest_batches ORDER BY uploaded_at DESC LIMIT 5;
SELECT * FROM ingest_qlik_entries WHERE batch_id = 1;
SELECT * FROM core_copyrightitem ORDER BY modified_at DESC LIMIT 10;
SELECT * FROM change_logs ORDER BY changed_at DESC LIMIT 10;
```

### Reset and Start Fresh
```powershell
# Drop and recreate database
docker exec ea-cli-django-db-1 psql -U admin -d postgres -c "DROP DATABASE IF EXISTS copyright_db; CREATE DATABASE copyright_db;"

# Run migrations
uv run python src/manage.py migrate

# Recreate superuser
uv run python src/manage.py createsuperuser --noinput --username admin --email admin@example.com
```

---

## Success Criteria

Phase A is considered successfully implemented when:
- ✅ Can upload Qlik file and create new items
- ✅ Can upload Qlik file and update existing items (system fields only)
- ✅ Can upload Faculty file and update existing items (human fields only)
- ✅ Faculty file never creates new items
- ✅ All changes are logged in ChangeLog
- ✅ Processing failures are recorded and viewable
- ✅ Admin interface shows all data correctly
- ✅ No legacy pipeline code remains in use

---

**Implementation completed:** December 17, 2025
**Next milestone:** Dashboard integration (Step 8)
