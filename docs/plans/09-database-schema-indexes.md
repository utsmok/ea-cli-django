# Task 09: Database Schema & Indexes

## Overview

Fix critical database schema issues and add missing indexes to support the application's scale (50k-400k items).

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)

## Issues Addressed

### 1. Duplicate `filehash` Field in Document Model (Critical)
**File:** `src/apps/documents/models.py:95, 112`

**Problem:**
The `Document` model defines `filehash` twice. The second definition shadows the first.

```python
class Document(TimestampedModel):
    # ... other fields ...
    filehash = models.CharField(max_length=255, unique=True, db_index=True)  # Line 95
    # ... other fields ...
    filename = models.CharField(max_length=2048, null=True, blank=True)
    # ... more fields ...
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)  # Line 112 - DUPLICATE!
```

This causes:
- Database migration confusion (which field wins?)
- Potential data inconsistency
- Query results may use wrong field

**Fix:** Remove the duplicate at line 112, keep the unique indexed version.

### 2. Missing Database Indexes (High)

Multiple fields lack indexes despite being used in filters and queries. At 50k-400k items, this causes slow queries.

#### Missing Indexes:

| Model | Field | Query Location | Why It's Needed |
|-------|-------|----------------|-----------------|
| `CopyrightItem` | `course_code` | `core/models.py:242` | Filtered in enrichment |
| `CopyrightItem` | `department` | Views, admin | Faculty resolution |
| `CopyrightItem` | `url` | Canvas checks | Composite with `file_exists` |
| `Person` | `main_name` | Model usage | Has index on `input_name` but not `main_name` |

## Implementation Steps

### Step 1: Fix Duplicate filehash Field

**File:** `src/apps/documents/models.py`

**Action:** Remove the duplicate definition at line 112.

```python
# BEFORE (lines ~90-115)
class Document(TimestampedModel):
    # ... other fields ...
    file = models.FileField(upload_to="downloads/%Y/%m/", null=True, blank=True)
    filehash = models.CharField(max_length=255, unique=True, db_index=True)  # Line 95 - KEEP THIS
    # ... other fields ...
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filesize = models.IntegerField(null=True, blank=True)
    # ... more fields ...
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)  # Line 112 - REMOVE THIS

# AFTER
class Document(TimestampedModel):
    # ... other fields ...
    file = models.FileField(upload_to="downloads/%Y/%m/", null=True, blank=True)
    filehash = models.CharField(max_length=255, unique=True, db_index=True)  # Keep this one
    # ... other fields ...
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filesize = models.IntegerField(null=True, blank=True)
    # ... rest of fields without duplicate ...
```

**Migration Required:** Yes, to remove the duplicate column.

### Step 2: Add Indexes to CopyrightItem Model

**File:** `src/apps/core/models.py`

**Current Meta class (around line ~240):**

```python
class Meta:
    ordering = ["-modified_at"]
    indexes = [
        models.Index(
            fields=["workflow_status", "faculty", "material_id", "v2_manual_classification", "manual_classification"]
        ),
    ]
```

**Updated Meta class:**

```python
class Meta:
    ordering = ["-modified_at"]
    indexes = [
        # Existing composite index
        models.Index(
            fields=["workflow_status", "faculty", "material_id", "v2_manual_classification", "manual_classification"],
            name="core_workflow_idx"
        ),
        # NEW: Single column indexes for filtering
        models.Index(fields=["course_code"], name="core_course_code_idx"),
        models.Index(fields=["department"], name="core_department_idx"),
        # NEW: Composite index for Canvas file checks (url + file_exists)
        models.Index(fields=["url", "file_exists"], name="core_canvas_check_idx"),
        # NEW: Index for enrichment queries
        models.Index(fields=["enrichment_status"], name="core_enrichment_status_idx"),
    ]
```

### Step 3: Add Index to Person Model

**File:** `src/apps/core/models.py`

**Current Person.Meta (around line ~160):**

```python
class Person(TimestampedModel):
    # ... fields ...
    input_name = models.CharField(max_length=2048, db_index=True)  # Already indexed
    main_name = models.CharField(max_length=2048)  # NOT indexed
```

**Updated Person.Meta:**

```python
class Meta:
    verbose_name = "Person"
    verbose_name_plural = "People"
    ordering = ["main_name"]
    indexes = [
        models.Index(fields=["input_name"], name="core_person_input_name_idx"),
        models.Index(fields=["main_name"], name="core_person_main_name_idx"),  # NEW
    ]
```

### Step 4: Create Migration

```bash
# Create migration for schema changes
uv run python src/manage.py makemigrations documents --name fix_duplicate_filehash
uv run python src/manage.py makemigrations core --name add_missing_indexes
```

**Review the migrations** to ensure they're correct:

```bash
# Show migration SQL
uv run python src/manage.py sqlmigrate documents <migration_number>
uv run python src/manage.py sqlmigrate core <migration_number>
```

### Step 5: Run Migration

```bash
# Run on development first
uv run python src/manage.py migrate

# Verify indexes created
uv run python src/manage.py dbshell
```

**In PostgreSQL shell:**
```sql
-- Check indexes on copyright_items table
\d+ copyright_items

-- Check indexes on documents table
\d+ documents

-- Check indexes on people table
\d+ people

-- Check index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE tablename IN ('copyright_items', 'documents', 'people')
ORDER BY tablename, indexname;
```

## Performance Impact Analysis

### Before Adding Indexes

At 100k items, these queries would be slow:

```python
# Query 1: Filter by course_code (no index)
CopyrightItem.objects.filter(course_code="202400123")  # Full table scan

# Query 2: Filter by department (no index)
CopyrightItem.objects.filter(department="EEMCS")  # Full table scan

# Query 3: Canvas file existence check (no index)
CopyrightItem.objects.filter(url__contains="/files/", file_exists=True)  # Full table scan
```

**Estimated query time:** 500ms-2s (depending on data size)

### After Adding Indexes

Same queries now use indexes:

```python
# Query 1: Uses core_course_code_idx
CopyrightItem.objects.filter(course_code="202400123")  # Index scan

# Query 2: Uses core_department_idx
CopyrightItem.objects.filter(department="EEMCS")  # Index scan

# Query 3: Uses core_canvas_check_idx
CopyrightItem.objects.filter(url__contains="/files/", file_exists=True)  # Index scan
```

**Estimated query time:** 5-50ms (10-100x faster)

## Testing

### 1. Test Duplicate Field Fix

```python
# In Django shell
from apps.documents.models import Document

# Check that filehash is unique and indexed
field = Document._meta.get_field("filehash")
assert field.unique == True, "filehash should be unique"
assert field.db_index == True, "filehash should be indexed"

# Check there's only one filehash field
filehash_fields = [f for f in Document._meta.get_fields() if f.name == "filehash"]
assert len(filehash_fields) == 1, "Should have exactly one filehash field"
```

### 2. Test Indexes Exist

```python
# In Django shell
from apps.core.models import CopyrightItem, Person
from django.db import connection

# Check CopyrightItem indexes
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'copyright_items'
        ORDER BY indexname
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    print("CopyrightItem indexes:", indexes)

    # Verify new indexes exist
    assert "core_course_code_idx" in indexes
    assert "core_department_idx" in indexes
    assert "core_canvas_check_idx" in indexes

# Check Person indexes
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'people'
        ORDER BY indexname
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    print("Person indexes:", indexes)

    # Verify new index exists
    assert "core_person_main_name_idx" in indexes
```

### 3. Benchmark Query Performance

```python
# In Django shell
import time
from apps.core.models import CopyrightItem

# Benchmark course_code query
start = time.time()
items = list(CopyrightItem.objects.filter(course_code="202400123")[:100])
duration = time.time() - start
print(f"course_code query: {duration:.3f}s")

# Benchmark department query
start = time.time()
items = list(CopyrightItem.objects.filter(department="EEMCS")[:100])
duration = time.time() - start
print(f"department query: {duration:.3f}s")

# Should be < 100ms for indexed queries
```

### 4. Test Data Integrity

```python
# Test that existing data still works
from apps.documents.models import Document
from apps.core.models import CopyrightItem

# Check all documents have unique filehashes
duplicates = Document.objects.values("filehash").annotate(count=Count("filehash")).filter(count__gt=1)
assert duplicates.count() == 0, "Should have no duplicate filehashes"

# Check foreign keys still work
item = CopyrightItem.objects.first()
if item.document:
    print(f"Item {item.material_id} has document {item.document.filehash}")
```

## Migration Rollback Plan

If issues occur:

```bash
# Rollback specific migration
uv run python src/manage.py migrate documents <previous_migration>
uv run python src/manage.py migrate core <previous_migration>

# Or rollback all
uv run python src/manage.py migrate documents zero
uv run python src/manage.py migrate core zero
```

**SQL fallback (if migration fails):**
```sql
-- Manually drop indexes if needed
DROP INDEX IF EXISTS core_course_code_idx;
DROP INDEX IF EXISTS core_department_idx;
DROP INDEX IF EXISTS core_canvas_check_idx;
DROP INDEX IF EXISTS core_enrichment_status_idx;
DROP INDEX IF EXISTS core_person_main_name_idx;

-- Manually drop duplicate column if needed (backup first!)
-- ALTER TABLE documents DROP COLUMN filehash_2;
```

## Success Criteria

- [ ] Duplicate `filehash` field removed from Document model
- [ ] Migration created and reviewed
- [ ] Indexes added for `CopyrightItem.course_code`
- [ ] Indexes added for `CopyrightItem.department`
- [ ] Composite index added for `CopyrightItem.url` + `file_exists`
- [ ] Index added for `Person.main_name`
- [ ] All migrations run successfully
- [ ] Query performance improved (10x+ faster on indexed fields)
- [ ] Data integrity verified (no duplicates, foreign keys work)
- [ ] Application still works correctly

## Files Modified

- `src/apps/documents/models.py` - Remove duplicate filehash field
- `src/apps/core/models.py` - Add indexes to CopyrightItem and Person
- `src/apps/documents/migrations/XXXX_fix_duplicate_filehash.py` - NEW
- `src/apps/core/migrations/XXXX_add_missing_indexes.py` - NEW

## Post-Implementation Monitoring

After deploying to production, monitor:

1. **Query performance:**
   ```bash
   # Check slow queries
   uv run python src/manage.py shell -c "
   from django.db import connection
   with connection.cursor() as cursor:
       cursor.execute('SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10')
       print(cursor.fetchall())
   "
   ```

2. **Index usage:**
   ```sql
   SELECT
       schemaname,
       tablename,
       indexname,
       idx_scan AS index_scans,
       idx_tup_read AS tuples_read,
       idx_tup_fetch AS tuples_fetched
   FROM pg_stat_user_indexes
   WHERE tablename IN ('copyright_items', 'documents', 'people')
   ORDER BY idx_scan DESC;
   ```

3. **Database size:**
   ```sql
   SELECT
       tablename,
       pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS total_size
   FROM pg_tables
   WHERE tablename IN ('copyright_items', 'documents', 'people');
   ```

## Performance Benefits

| Query | Before | After | Improvement |
|-------|--------|-------|-------------|
| Filter by course_code | 500ms-2s | 5-50ms | **10-100x** |
| Filter by department | 500ms-2s | 5-50ms | **10-100x** |
| Canvas file check | 500ms-2s | 5-50ms | **10-100x** |
| Person lookup by name | 100-500ms | 5-20ms | **5-25x** |

---

**Next Task:** [Task 10: Async/ORM Consistency](10-async-orm-consistency.md)
