# Implementation Plan: Easy Access Platform Refactor

**Version:** 5.0 (Final - Consolidated)
**Date:** December 16, 2025
**Current Phase:** Phase A (Core Data & Ingestion)
**Status:** Ready for Implementation

---

## 0. Document Purpose & Methodology

This document provides a **step-by-step implementation plan** for refactoring the legacy `ea-cli` tool into a modern Django 6.0 web application. It consolidates insights from previous planning iterations and addresses critical gaps identified during architectural review.

### Key Principles
1. **Incremental Development:** Each step must be completable and testable independently
2. **Legacy Code Reuse:** Leverage existing logic from `ea-cli/` submodule where appropriate (especially standardization, merge rules, export formatting)
3. **Web-First Architecture:** Design for async tasks, multi-user access, and UI responsiveness
4. **Data Integrity:** Maintain complete audit trails and never lose data
5. **Test-Driven:** Write tests before refactoring complex logic

### Success Criteria for Phase A
- ✅ Users can upload Excel files via web UI (no more local folders)
- ✅ System tracks who uploaded what and when (full audit trail)
- ✅ Merge logic correctly handles "System Fields" (Qlik) vs "Human Fields" (Faculty)
- ✅ Excel exports match legacy format exactly (backward compatibility)
- ✅ No dependency on legacy `pipeline.py` or `merging.py`

---

## 1. Architectural Overview

### 1.1 Current State Analysis
**Status:** Partial Django port with legacy dependencies

**Existing Structure:**
```text
src/apps/
├── core/               # ✅ Models exist (CopyrightItem, Enums)
│                      # ❌ No ChangeLog model
│                      # ❌ Contains legacy services/
├── ingest/            # ⚠️  Has tasks.py, utils.py
│                      # ❌ No models.py
│                      # ❌ No services/ subdirectory
├── dashboard/         # ⚠️  Basic structure exists
├── enrichment/        # 🔮 Phase B - ignore for now
├── classification/    # 🔮 Phase C - ignore for now
├── documents/         # 🔮 Phase B - ignore for now
└── api/              # 🔮 Phase C - ignore for now
```

**Critical Issues:**
1. ❌ **No User Model:** Currently using Django's default `auth.User`
2. ❌ **No Audit Trail:** Can't track who uploaded/changed what
3. ❌ **Staging Logic Missing:** No models for `IngestionBatch`, `FacultyEntry`, `QlikEntry`
4. ⚠️  **Legacy Dependencies:** Still relies on complex `pipeline.py` and `merging.py` strategies

### 1.2 Phase A Target Architecture
**Goal:** Web-based ingestion with full audit trail and simplified merge logic

```text
src/apps/
├── users/              # [NEW] Custom User Model
│   └── models.py      # User(AbstractUser)
├── core/
│   └── models.py      # CopyrightItem, ChangeLog [+], Course, Organization
├── ingest/
│   ├── models.py      # [NEW] IngestionBatch, FacultyEntry, QlikEntry, ProcessingFailure
│   ├── tasks.py       # [REFACTOR] Async task orchestration
│   ├── services/      # [NEW]
│   │   ├── standardizer.py   # Clean Polars transformations
│   │   ├── processor.py      # Field ownership merge logic
│   │   ├── comparison.py     # Ranked field comparison rules
│   │   └── excel_builder.py  # Legacy-compatible export
│   └── management/commands/
│       ├── load_legacy.py    # [NEW] One-time data migration
│       └── process_batch.py  # [NEW] Manual trigger
└── dashboard/
    └── views.py       # [UPDATE] Upload/Download endpoints
```

### 1.3 Data Flow (Phase A)

```
┌─────────────────┐
│  User Uploads   │
│  Excel File via │
│   Dashboard     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  IngestionBatch Created     │
│  - source_file stored       │
│  - uploaded_by = request.user │
│  - status = PENDING         │
└────────┬────────────────────┘
         │
         ▼ (async task triggered)
┌─────────────────────────────┐
│  Standardizer Service       │
│  - Read with Polars         │
│  - Normalize columns        │
│  - Parse enums              │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Create FacultyEntry or     │
│  QlikEntry records          │
│  - Raw standardized data    │
│  - Link to IngestionBatch   │
└────────┬────────────────────┘
         │
         ▼ (after staging complete)
┌─────────────────────────────┐
│  Processor Service          │
│  - Apply field ownership    │
│  - Compare with existing    │
│  - Create/Update Items      │
│  - Log all changes          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  ChangeLog entries created  │
│  - item, batch, user, changes │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  IngestionBatch.status =    │
│  COMPLETED                  │
└─────────────────────────────┘
```

### 1.4 Future Phases (Scope Preview)

**Phase B - Enrichment (Post-Phase A):**
- Add `apps/enrichment` services for Osiris scraping
- Add `apps/documents` for Canvas PDF downloads
- Trigger enrichment automatically after Qlik ingestion

**Phase C - Dashboard & Classification (Post-Phase B):**
- Replace Excel exports with HTMX grid editor
- Add ML classification suggestions
- User permission system

---

## 2. Phase A Implementation Steps

---

### 📋 STEP 0: Pre-Implementation Checklist

**Before starting Step 1, verify:**
- [ ] Legacy `ea-cli` submodule is accessible at `ea-cli/`
- [ ] Current database is backed up (or acceptable to reset)
- [ ] Development environment is running (local, w/ postgres & redis docker containers running on localhost)
- [ ] You have reviewed existing code in `src/apps/core/models.py`
- [ ] Ensure all django settings are correct (e.g., `INSTALLED_APPS`, `AUTH_USER_MODEL` placeholder, database config)
**Database Reset:**
Delete `db.sqlite3` and/or recreate the postgres+redis containers from scratch, delete all migration files, start fresh


---

### 🔐 STEP 1: Identity Foundation (CRITICAL - DO FIRST)

**Why:** The custom user model must exist before any other app creates ForeignKeys to it. Changing this later requires complex data migrations.

**Current State:** Project uses Django's default `auth.User`
**Target State:** Custom user model at `apps.users.User`

**Implementation:**

1. **Create the users app:**
   ```bash
   cd src
   python manage.py startapp users apps/users
   ```

2. **Define the User model** (`src/apps/users/models.py`):
   ```python
   from django.contrib.auth.models import AbstractUser
   from django.db import models

   class User(AbstractUser):
       """
       Custom user model for the Easy Access platform.

       Currently extends AbstractUser with no additional fields.
       Future additions: department, role, permissions.
       """

       class Meta:
           db_table = 'users'
           verbose_name = 'User'
           verbose_name_plural = 'Users'

       def __str__(self):
           return self.get_full_name() or self.username
   ```

3. **Update settings** (`src/config/settings.py`):
   ```python
   INSTALLED_APPS = [
       # ... existing apps ...
       'apps.users',  # Add near the top, before other custom apps
       'apps.core',
       'apps.ingest',
       # ...
   ]

   # Critical: Set custom user model
   AUTH_USER_MODEL = 'users.User'
   ```

4. **Register in admin** (`src/apps/users/admin.py`):
   ```python
   from django.contrib import admin
   from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
   from .models import User

   @admin.register(User)
   class UserAdmin(BaseUserAdmin):
       pass  # Inherits all default UserAdmin functionality
   ```

5. **Handle existing migrations:**

   **If choosing Option A (Clean slate):**
   ```bash
   # From project root
   rm src/db.sqlite3
   find src/apps -path "*/migrations/*.py" -not -name "__init__.py" -delete
   find src/apps -path "*/migrations/*.pyc" -delete
   ```

   **If choosing Option B (Keep data):**
   - Stop here and consult Django documentation for swapping user models
   - This is complex and not recommended for early-stage projects

6. **Create migrations:**
   ```bash
   python src/manage.py makemigrations users
   python src/manage.py makemigrations  # For all apps
   python src/manage.py migrate
   ```

7. **Create superuser:**
   ```bash
   python src/manage.py createsuperuser
   ```

8. **Verify:**
   - Start dev server: `python src/manage.py runserver`
   - Visit `/admin` and log in
   - Navigate to Users section - should see your custom User model

**⚠️ Critical Warning:**
Do NOT proceed to Step 2 until this step is complete and verified. All subsequent models will reference this user model.

---

### 📊 STEP 2: Ingestion & Audit Models

**Why:**
- Current approach lacks visibility into ingestion history
- Can't track who uploaded what file
- Can't retry failed ingestions
- No audit trail for data changes

**Current State:** No `ingest/models.py` file exists
**Target State:** Complete staging and audit infrastructure

**Legacy Reference:**
- `ea-cli/easy_access/db/models.py` (StagedFacultyUpdate, ChangeLog, ProcessingError)
- See refactor_plan.md Step 1 for detailed field specifications

**Implementation:**

1. **Create `src/apps/ingest/models.py`** with the following models:

   ```python
   from django.db import models
   from django.conf import settings
   from apps.core.models import TimestampedModel


   class IngestionBatch(TimestampedModel):
       """
       Tracks a single file upload and its processing lifecycle.
       Groups all entries from one Excel file.
       """
       class Type(models.TextChoices):
           FACULTY = "FACULTY", "Faculty Sheet"
           QLIK = "QLIK", "Qlik Export"

       class Status(models.TextChoices):
           PENDING = "PENDING", "Pending"
           STAGING = "STAGING", "Staging Data"
           STAGED = "STAGED", "Data Staged"
           PROCESSING = "PROCESSING", "Processing"
           COMPLETED = "COMPLETED", "Completed"
           ERROR = "ERROR", "Error"

       source_file = models.FileField(upload_to="ingest/%Y/%m/")
       ingestion_type = models.CharField(max_length=50, choices=Type.choices)
       status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
       uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

       # Processing results
       items_created = models.IntegerField(default=0)
       items_updated = models.IntegerField(default=0)
       items_skipped = models.IntegerField(default=0)
       items_failed = models.IntegerField(default=0)

       # Detailed log of processing
       log = models.TextField(blank=True)
       error_message = models.TextField(blank=True)

       completed_at = models.DateTimeField(null=True, blank=True)

       class Meta:
           ordering = ['-created_at']
           indexes = [
               models.Index(fields=['status', '-created_at']),
               models.Index(fields=['ingestion_type', '-created_at']),
           ]

       def __str__(self):
           return f"{self.get_ingestion_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


   class FacultyEntry(TimestampedModel):
       """
       Stores one row from a Faculty sheet after standardization.
       Raw faculty data before merging into CopyrightItem.
       """
       ingestion = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="faculty_entries")

       # Link to target item
       material_id = models.BigIntegerField(db_index=True)

       # Faculty-editable fields (stored as standardized strings)
       v2_manual_classification = models.CharField(max_length=255, null=True, blank=True)
       v2_lengte = models.CharField(max_length=50, null=True, blank=True)
       v2_overnamestatus = models.CharField(max_length=100, null=True, blank=True)
       manual_classification = models.CharField(max_length=255, null=True, blank=True)  # V1 field
       manual_identifier = models.CharField(max_length=255, null=True, blank=True)
       remarks = models.TextField(null=True, blank=True)
       scope = models.CharField(max_length=50, null=True, blank=True)
       workflow_status = models.CharField(max_length=50, null=True, blank=True)

       # Processing tracking
       processed = models.BooleanField(default=False)
       processing_error = models.TextField(null=True, blank=True)

       class Meta:
           unique_together = [('ingestion', 'material_id')]
           indexes = [
               models.Index(fields=['material_id']),
               models.Index(fields=['ingestion', 'processed']),
           ]

       def __str__(self):
           return f"Faculty Entry {self.material_id} from {self.ingestion}"


   class QlikEntry(TimestampedModel):
       """
       Stores one row from a Qlik export after standardization.
       Raw Qlik data before merging into CopyrightItem.
       """
       ingestion = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="qlik_entries")

       # Complete item data from Qlik (stored as JSONField for flexibility)
       # This includes ALL fields from the Qlik export
       data = models.JSONField()

       # Extracted key for indexing
       material_id = models.BigIntegerField(db_index=True)

       # Processing tracking
       processed = models.BooleanField(default=False)
       processing_error = models.TextField(null=True, blank=True)
       is_new_item = models.BooleanField(null=True)  # Determined during processing

       class Meta:
           unique_together = [('ingestion', 'material_id')]
           indexes = [
               models.Index(fields=['material_id']),
               models.Index(fields=['ingestion', 'processed']),
           ]

       def __str__(self):
           return f"Qlik Entry {self.material_id} from {self.ingestion}"


   class ProcessingFailure(TimestampedModel):
       """
       Tracks items that failed during processing for inspection and retry.
       """
       batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="failures")
       material_id = models.BigIntegerField(db_index=True, null=True)

       error_type = models.CharField(max_length=100)
       error_message = models.TextField()
       traceback = models.TextField(blank=True)

       # Raw data that failed (for debugging)
       failed_data = models.JSONField()

       # Resolution tracking
       resolved = models.BooleanField(default=False)
       resolved_at = models.DateTimeField(null=True, blank=True)
       resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
       resolution_notes = models.TextField(blank=True)

       class Meta:
           ordering = ['-created_at']
           indexes = [
               models.Index(fields=['resolved', '-created_at']),
               models.Index(fields=['batch', 'resolved']),
           ]

       def __str__(self):
           return f"Failure: {self.error_type} - Material {self.material_id}"
   ```

2. **Update `src/apps/core/models.py`** - Add ChangeLog model:

   ```python
   class ChangeLog(TimestampedModel):
       """
       Audit trail for all changes to CopyrightItem records.
       Tracks both ingestion-based updates and manual edits.
       """
       class ChangeType(models.TextChoices):
           CREATED = "CREATED", "Item Created"
           UPDATED = "UPDATED", "Item Updated"
           MANUAL_EDIT = "MANUAL_EDIT", "Manual Edit"
           BULK_UPDATE = "BULK_UPDATE", "Bulk Update"

       item = models.ForeignKey('CopyrightItem', on_delete=models.CASCADE, related_name="history")
       batch = models.ForeignKey('ingest.IngestionBatch', null=True, blank=True, on_delete=models.SET_NULL)
       user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

       change_type = models.CharField(max_length=20, choices=ChangeType.choices, default=ChangeType.UPDATED)

       # Store actual changes: {'field_name': {'old': 'value', 'new': 'value'}}
       changes = models.JSONField()

       # Optional context
       notes = models.TextField(blank=True)

       class Meta:
           ordering = ['-timestamp']
           indexes = [
               models.Index(fields=['item', '-timestamp']),
               models.Index(fields=['batch', '-timestamp']),
               models.Index(fields=['user', '-timestamp']),
           ]

       def __str__(self):
           return f"{self.get_change_type_display()} - {self.item.material_id} at {self.timestamp}"
   ```

3. **Remove old models from core** (if they exist):
   - Delete any `StagedItem` definitions in `core/models.py`
   - Delete any `ItemUpdate` definitions

4. **Create admin interfaces** (`src/apps/ingest/admin.py`):

   ```python
   from django.contrib import admin
   from django.utils.html import format_html
   from .models import IngestionBatch, FacultyEntry, QlikEntry, ProcessingFailure


   class FacultyEntryInline(admin.TabularInline):
       model = FacultyEntry
       extra = 0
       fields = ['material_id', 'workflow_status', 'processed', 'processing_error']
       readonly_fields = ['material_id', 'processed', 'processing_error']
       can_delete = False


   class QlikEntryInline(admin.TabularInline):
       model = QlikEntry
       extra = 0
       fields = ['material_id', 'is_new_item', 'processed', 'processing_error']
       readonly_fields = ['material_id', 'is_new_item', 'processed', 'processing_error']
       can_delete = False


   @admin.register(IngestionBatch)
   class IngestionBatchAdmin(admin.ModelAdmin):
       list_display = ['id', 'ingestion_type', 'status', 'uploaded_by', 'created_at', 'items_summary']
       list_filter = ['status', 'ingestion_type', 'created_at']
       readonly_fields = ['created_at', 'modified_at', 'completed_at']

       fieldsets = [
           ('Basic Info', {
               'fields': ['source_file', 'ingestion_type', 'uploaded_by', 'status']
           }),
           ('Results', {
               'fields': ['items_created', 'items_updated', 'items_skipped', 'items_failed']
           }),
           ('Logs', {
               'fields': ['log', 'error_message'],
               'classes': ['collapse']
           }),
           ('Timestamps', {
               'fields': ['created_at', 'modified_at', 'completed_at']
           }),
       ]

       inlines = [FacultyEntryInline, QlikEntryInline]

       def items_summary(self, obj):
           return f"✓{obj.items_created} ~{obj.items_updated} ✗{obj.items_failed}"
       items_summary.short_description = "Summary"


   @admin.register(ProcessingFailure)
   class ProcessingFailureAdmin(admin.ModelAdmin):
       list_display = ['id', 'batch', 'material_id', 'error_type', 'resolved', 'created_at']
       list_filter = ['resolved', 'error_type', 'created_at']
       readonly_fields = ['created_at', 'modified_at', 'traceback']

       actions = ['mark_resolved']

       def mark_resolved(self, request, queryset):
           from django.utils import timezone
           updated = queryset.update(
               resolved=True,
               resolved_at=timezone.now(),
               resolved_by=request.user
           )
           self.message_user(request, f"{updated} failures marked as resolved.")
       mark_resolved.short_description = "Mark selected as resolved"
   ```

5. **Create migrations:**
   ```bash
   python src/manage.py makemigrations ingest
   python src/manage.py makemigrations core  # For ChangeLog
   python src/manage.py migrate
   ```

6. **Verify in admin:**
   - Navigate to `/admin/ingest/`
   - Should see IngestionBatch, ProcessingFailure models
   - Check `/admin/core/changelog/`

**✅ Completion Criteria:**
- [ ] All four ingestion models created and migrated
- [ ] ChangeLog model added to core
- [ ] Admin interfaces functional
- [ ] Can create test IngestionBatch through admin
- [ ] ForeignKey to User model works correctly

---

### 🔄 STEP 3: Data Standardization Service

**Why:**
- Current `ingest/utils.py` mixes I/O with transformation logic
- Need pure, testable transformation functions
- Must match legacy normalization exactly for backward compatibility

**Current State:** `ingest/utils.py` exists but has mixed concerns
**Target State:** Clean service layer for data transformations

**Legacy Reference:**
- `ea-cli/easy_access/utils.py` (standardize_dataframe function)
- `ea-cli/easy_access/sheets/sheet.py` (column renaming logic)

**Implementation:**

1. **Create `src/apps/ingest/services/` directory:**
   ```bash
   mkdir src/apps/ingest/services
   touch src/apps/ingest/services/__init__.py
   ```

2. **Create `src/apps/ingest/services/standardizer.py`:**

   ```python
   """
   Data standardization service for ingestion pipeline.

   Transforms raw Excel data into clean, normalized DataFrames.
   This is a pure transformation layer - no I/O, no database access.
   """
   import polars as pl
   from typing import Literal
   from loguru import logger

   # Import university structure mappings
   from config.university import DEPARTMENT_MAPPING, FACULTY_ABBREVIATIONS


   class DataFrameStandardizer:
       """
       Standardizes raw Excel data from Qlik or Faculty sheets.

       Based on legacy ea-cli/easy_access/utils.py::standardize_dataframe
       """

       @staticmethod
       def standardize(
           df: pl.DataFrame,
           source_type: Literal["faculty", "qlik"]
       ) -> pl.DataFrame:
           """
           Apply standardization pipeline to raw data.

           Args:
               df: Raw Polars DataFrame from Excel
               source_type: "faculty" or "qlik" to apply appropriate rules

           Returns:
               Standardized DataFrame with normalized columns and values
           """
           logger.info(f"Standardizing {source_type} data: {df.shape[0]} rows, {df.shape[1]} columns")

           # Step 1: Normalize column names
           df = DataFrameStandardizer._normalize_columns(df)

           # Step 2: Cast to string and handle null markers
           df = DataFrameStandardizer._normalize_values(df)

           # Step 3: Apply source-specific transformations
           if source_type == "qlik":
               df = DataFrameStandardizer._apply_qlik_rules(df)
           elif source_type == "faculty":
               df = DataFrameStandardizer._apply_faculty_rules(df)

           # Step 4: Map department to faculty
           df = DataFrameStandardizer._map_faculty(df)

           logger.info(f"Standardization complete: {df.shape[0]} rows retained")
           return df

       @staticmethod
       def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
           """
           Normalize column names to lowercase with underscores.
           Maps common Excel column variations to standard names.
           """
           # Basic normalization
           df = df.rename(lambda col: (
               col.strip()
               .replace(" ", "_")
               .replace("#", "count_")
               .replace("?", "")
               .lower()
           ))

           # Map known column variations (from legacy system)
           column_mapping = {
               "material_id": "material_id",
               "materialid": "material_id",
               "id": "material_id",
               # Add more mappings as discovered
           }

           # Apply mappings if columns exist
           for old_name, new_name in column_mapping.items():
               if old_name in df.columns and old_name != new_name:
                   df = df.rename({old_name: new_name})

           return df

       @staticmethod
       def _normalize_values(df: pl.DataFrame) -> pl.DataFrame:
           """
           Cast all columns to string and normalize null markers.
           Handles: "-", "N/A", "null", empty strings as NULL.
           """
           # Cast all to string first
           df = df.select([
               pl.col(col).cast(pl.Utf8).alias(col)
               for col in df.columns
           ])

           # Define null markers (from legacy system)
           null_markers = ["-", "N/A", "n/a", "null", "NULL", "None", ""]

           # Replace null markers with actual NULL
           df = df.with_columns([
               pl.when(pl.col(col).str.strip_chars().is_in(null_markers))
               .then(None)
               .otherwise(pl.col(col))
               .alias(col)
               for col in df.columns
           ])

           return df

       @staticmethod
       def _apply_qlik_rules(df: pl.DataFrame) -> pl.DataFrame:
           """
           Apply Qlik-specific transformation rules.

           - Ensure material_id is present
           - Parse dates if needed
           - Validate required fields
           """
           required_fields = ["material_id", "title"]  # Add more as needed

           for field in required_fields:
               if field not in df.columns:
                   logger.warning(f"Missing required Qlik field: {field}")
                   df = df.with_columns(pl.lit(None).alias(field))

           # Ensure material_id is integer
           if "material_id" in df.columns:
               df = df.with_columns(
                   pl.col("material_id").cast(pl.Int64, strict=False)
               )

           return df

       @staticmethod
       def _apply_faculty_rules(df: pl.DataFrame) -> pl.DataFrame:
           """
           Apply Faculty-specific transformation rules.

           - Ensure material_id for lookup
           - Normalize enum values to match Django choices
           """
           if "material_id" not in df.columns:
               raise ValueError("Faculty sheet must contain material_id column")

           # Ensure material_id is integer
           df = df.with_columns(
               pl.col("material_id").cast(pl.Int64, strict=False)
           )

           # Normalize workflow status values
           if "workflow_status" in df.columns:
               status_mapping = {
                   "todo": "ToDo",
                   "to do": "ToDo",
                   "inprogress": "InProgress",
                   "in progress": "InProgress",
                   "done": "Done",
               }
               df = df.with_columns(
                   pl.col("workflow_status")
                   .str.to_lowercase()
                   .replace_strict(status_mapping, default=None)
               )

           return df

       @staticmethod
       def _map_faculty(df: pl.DataFrame) -> pl.DataFrame:
           """
           Map department codes to faculty using university structure.

           Uses DEPARTMENT_MAPPING from config.university module.
           """
           if "department" not in df.columns:
               logger.debug("No department column found, skipping faculty mapping")
               return df

           # Apply mapping with fallback to "UNM" (Unmapped)
           df = df.with_columns(
               pl.col("department")
               .replace_strict(DEPARTMENT_MAPPING, default="UNM")
               .alias("faculty")
           )

           return df
   ```

3. **Create `src/apps/ingest/services/validators.py`:**

   ```python
   """
   Field validation utilities for ingestion pipeline.

   Validates individual field values against Django model constraints.
   """
   from typing import Any, Optional
   from apps.core.models import (
       WorkflowStatus, ClassificationV2, OvernameStatus,
       Lengte, Classification
   )


   class FieldValidator:
       """Validates field values before database insertion."""

       @staticmethod
       def validate_workflow_status(value: Optional[str]) -> Optional[str]:
           """Validate workflow_status against enum."""
           if value is None:
               return None

           try:
               # Check if value is valid choice
               WorkflowStatus(value)
               return value
           except ValueError:
               return None

       @staticmethod
       def validate_classification_v2(value: Optional[str]) -> Optional[str]:
           """Validate v2_manual_classification against enum."""
           if value is None:
               return None

           try:
               ClassificationV2(value)
               return value
           except ValueError:
               return None

       @staticmethod
       def validate_lengte(value: Optional[str]) -> Optional[str]:
           """Validate v2_lengte against enum."""
           if value is None:
               return None

           try:
               Lengte(value)
               return value
           except ValueError:
               return None

       @staticmethod
       def validate_overname_status(value: Optional[str]) -> Optional[str]:
           """Validate v2_overnamestatus against enum."""
           if value is None:
               return None

           try:
               OvernameStatus(value)
               return value
           except ValueError:
               return None
   ```

4. **Create tests** (`src/apps/ingest/tests/test_standardizer.py`):

   ```python
   import pytest
   import polars as pl
   from apps.ingest.services.standardizer import DataFrameStandardizer


   def test_normalize_columns():
       """Test column name normalization."""
       df = pl.DataFrame({
           "Material ID": [1, 2, 3],
           "File Name": ["a.pdf", "b.pdf", "c.pdf"],
           "# Students": [10, 20, 30]
       })

       result = DataFrameStandardizer._normalize_columns(df)

       assert "material_id" in result.columns
       assert "file_name" in result.columns
       assert "count_students" in result.columns


   def test_normalize_null_markers():
       """Test that null markers are converted to None."""
       df = pl.DataFrame({
           "field1": ["value", "-", "N/A"],
           "field2": ["", "null", "actual"]
       })

       result = DataFrameStandardizer._normalize_values(df)

       assert result["field1"][0] == "value"
       assert result["field1"][1] is None
       assert result["field1"][2] is None
       assert result["field2"][2] == "actual"


   def test_qlik_standardization():
       """Test full Qlik standardization pipeline."""
       df = pl.DataFrame({
           "Material ID": [123, 456],
           "Title": ["Book A", "Book B"],
           "Department": ["EEMCS", "TNW"]
       })

       result = DataFrameStandardizer.standardize(df, source_type="qlik")

       assert "material_id" in result.columns
       assert "faculty" in result.columns
       assert result["faculty"][0] is not None
   ```

5. **Update `src/apps/ingest/services/__init__.py`:**
   ```python
   from .standardizer import DataFrameStandardizer
   from .validators import FieldValidator

   __all__ = ['DataFrameStandardizer', 'FieldValidator']
   ```

6. **Run tests:**
   ```bash
   pytest src/apps/ingest/tests/test_standardizer.py -v
   ```

**✅ Completion Criteria:**
- [ ] Standardizer service created with pure functions
- [ ] No file I/O in standardizer (only DataFrame transformations)
- [ ] Column normalization matches legacy behavior
- [ ] Null marker handling works correctly
- [ ] Tests pass
- [ ] Service can handle both Qlik and Faculty data

**📝 Notes:**
- This service is used by tasks but has NO Django dependencies
- Can be tested in isolation with pure Polars DataFrames
- Faculty mapping depends on `config/university.py` being properly configured

---

### ⚙️ STEP 4: Field Comparison & Merge Rules

**Why:**
- Legacy `merging.py` uses complex "Strategy" pattern (~300 lines)
- Need simpler, explicit "Field Ownership" model
- Must preserve the ranked comparison logic for quality data

**Current State:** Legacy `services/pipeline.py` and `services/merging.py` exist
**Target State:** Clean comparison and merge rule system

**Legacy Reference:**
- `ea-cli/easy_access/merge_rules.py` (field priority lists)
- `ea-cli/easy_access/db/update.py` (update logic - ~1,800 lines!)

**Design Decision:**
Instead of abstract strategies, we use **explicit field ownership**:
- **Qlik fields:** System-managed (title, author, status, student counts, etc.)
- **Faculty fields:** Human-managed (classification, workflow_status, remarks, scope)

**Implementation:**

1. **Create `src/apps/ingest/services/comparison.py`:**

   ```python
   """
   Field comparison strategies for merge logic.

   Determines which value should win when comparing old vs new data.
   Based on legacy ea-cli/easy_access/merge_rules.py
   """
   from enum import Enum
   from typing import Any, Optional, List
   from dataclasses import dataclass


   class ComparisonStrategy(Enum):
       """Strategy for resolving conflicts between old and new values."""
       PRIORITY_LIST = "priority_list"  # Use ranked list
       ALWAYS_UPDATE = "always_update"   # New value always wins
       NEVER_UPDATE = "never_update"     # Old value always wins
       UPDATE_IF_NULL = "update_if_null" # Only update if old is NULL
       MANUAL_ONLY = "manual_only"       # Only via manual edit, not ingestion


   @dataclass
   class FieldComparisonRule:
       """Rule for comparing a single field."""
       field_name: str
       strategy: ComparisonStrategy
       priority_list: Optional[List[Any]] = None  # For PRIORITY_LIST strategy

       def should_update(self, old_value: Any, new_value: Any) -> bool:
           """
           Determine if old_value should be replaced with new_value.

           Returns:
               True if update should happen, False otherwise
           """
           if self.strategy == ComparisonStrategy.ALWAYS_UPDATE:
               return new_value is not None

           elif self.strategy == ComparisonStrategy.NEVER_UPDATE:
               return False

           elif self.strategy == ComparisonStrategy.UPDATE_IF_NULL:
               return old_value is None and new_value is not None

           elif self.strategy == ComparisonStrategy.MANUAL_ONLY:
               return False  # Ingestion never updates this

           elif self.strategy == ComparisonStrategy.PRIORITY_LIST:
               return self._compare_by_priority(old_value, new_value)

           return False

       def _compare_by_priority(self, old_value: Any, new_value: Any) -> bool:
           """
           Compare values using priority list.
           Lower index = higher priority.
           """
           if not self.priority_list:
               return False

           try:
               old_priority = self.priority_list.index(old_value) if old_value in self.priority_list else 999
               new_priority = self.priority_list.index(new_value) if new_value in self.priority_list else 999

               # Update if new value has higher priority (lower index)
               return new_priority < old_priority
           except (ValueError, TypeError):
               return False


   class MergeRuleSet:
       """Collection of field comparison rules for an ingestion type."""

       def __init__(self, rules: List[FieldComparisonRule]):
           self.rules = {rule.field_name: rule for rule in rules}

       def should_update_field(self, field_name: str, old_value: Any, new_value: Any) -> bool:
           """Check if a specific field should be updated."""
           if field_name not in self.rules:
               # No rule = don't update (safe default)
               return False

           return self.rules[field_name].should_update(old_value, new_value)

       def get_updates(self, old_item: dict, new_data: dict) -> dict:
           """
           Generate dict of fields that should be updated.

           Args:
               old_item: Current database values (as dict)
               new_data: New values from ingestion (as dict)

           Returns:
               Dict of {field_name: new_value} for fields that should update
           """
           updates = {}

           for field_name, rule in self.rules.items():
               if field_name not in new_data:
                   continue

               old_value = old_item.get(field_name)
               new_value = new_data.get(field_name)

               if rule.should_update(old_value, new_value):
                   updates[field_name] = new_value

           return updates
   ```

2. **Create `src/apps/ingest/services/merge_rules.py`:**

   ```python
   """
   Merge rule definitions for Qlik and Faculty ingestion.

   Defines which fields each ingestion type can update and how conflicts are resolved.
   Based on legacy ea-cli/easy_access/merge_rules.py
   """
   from .comparison import FieldComparisonRule, ComparisonStrategy, MergeRuleSet
   from apps.core.models import WorkflowStatus, ClassificationV2


   # ============================================================================
   # QLIK INGESTION RULES
   # ============================================================================
   # Qlik is the source of truth for system/technical fields
   # NEW items: Create with all fields
   # EXISTING items: Update only specific system fields

   QLIK_UPDATABLE_FIELDS = [
       # Technical metadata
       FieldComparisonRule(
           field_name="title",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="author",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="filename",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="url",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # Canvas integration
       FieldComparisonRule(
           field_name="canvas_course_id",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="file_exists",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="status",  # Published/Unpublished/Deleted
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # Student metrics
       FieldComparisonRule(
           field_name="count_students_registered",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="pages_x_students",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # System timestamps
       FieldComparisonRule(
           field_name="last_scan_date_university",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="last_scan_date_course",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # ML predictions (Qlik-generated)
       FieldComparisonRule(
           field_name="ml_prediction",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # NEVER update human fields from Qlik
       FieldComparisonRule(
           field_name="v2_manual_classification",
           strategy=ComparisonStrategy.NEVER_UPDATE
       ),
       FieldComparisonRule(
           field_name="workflow_status",
           strategy=ComparisonStrategy.UPDATE_IF_NULL  # Only set initial value
       ),
   ]

   QLIK_MERGE_RULES = MergeRuleSet(QLIK_UPDATABLE_FIELDS)


   # ============================================================================
   # FACULTY INGESTION RULES
   # ============================================================================
   # Faculty sheets are source of truth for human-managed fields
   # NEVER creates new items (only updates existing)
   # ALWAYS overwrites with current sheet values (no priority lists for now)

   FACULTY_UPDATABLE_FIELDS = [
       # V2 Classification fields
       FieldComparisonRule(
           field_name="v2_manual_classification",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="v2_lengte",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="v2_overnamestatus",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # Legacy V1 classification
       FieldComparisonRule(
           field_name="manual_classification",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # Human annotations
       FieldComparisonRule(
           field_name="manual_identifier",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="remarks",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),
       FieldComparisonRule(
           field_name="scope",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # Workflow tracking
       FieldComparisonRule(
           field_name="workflow_status",
           strategy=ComparisonStrategy.ALWAYS_UPDATE
       ),

       # NEVER update system fields from Faculty
       FieldComparisonRule(
           field_name="title",
           strategy=ComparisonStrategy.NEVER_UPDATE
       ),
       FieldComparisonRule(
           field_name="author",
           strategy=ComparisonStrategy.NEVER_UPDATE
       ),
       FieldComparisonRule(
           field_name="count_students_registered",
           strategy=ComparisonStrategy.NEVER_UPDATE
       ),
   ]

   FACULTY_MERGE_RULES = MergeRuleSet(FACULTY_UPDATABLE_FIELDS)
   ```

3. **Create tests** (`src/apps/ingest/tests/test_comparison.py`):

   ```python
   import pytest
   from apps.ingest.services.comparison import (
       FieldComparisonRule, ComparisonStrategy, MergeRuleSet
   )
   from apps.ingest.services.merge_rules import QLIK_MERGE_RULES, FACULTY_MERGE_RULES


   def test_always_update_strategy():
       """Test ALWAYS_UPDATE strategy."""
       rule = FieldComparisonRule("title", ComparisonStrategy.ALWAYS_UPDATE)

       assert rule.should_update("old", "new") is True
       assert rule.should_update("old", None) is False
       assert rule.should_update(None, "new") is True


   def test_never_update_strategy():
       """Test NEVER_UPDATE strategy."""
       rule = FieldComparisonRule("locked_field", ComparisonStrategy.NEVER_UPDATE)

       assert rule.should_update("old", "new") is False
       assert rule.should_update(None, "new") is False


   def test_update_if_null_strategy():
       """Test UPDATE_IF_NULL strategy."""
       rule = FieldComparisonRule("optional_field", ComparisonStrategy.UPDATE_IF_NULL)

       assert rule.should_update(None, "new") is True
       assert rule.should_update("old", "new") is False


   def test_priority_list_strategy():
       """Test PRIORITY_LIST strategy with workflow status example."""
       priority_list = ["Done", "InProgress", "ToDo"]
       rule = FieldComparisonRule(
           "workflow_status",
           ComparisonStrategy.PRIORITY_LIST,
           priority_list=priority_list
       )

       # Higher priority (lower index) should win
       assert rule.should_update("ToDo", "Done") is True
       assert rule.should_update("Done", "ToDo") is False
       assert rule.should_update("InProgress", "Done") is True


   def test_qlik_rules_protect_human_fields():
       """Test that Qlik rules never update human-managed fields."""
       old_item = {
           "title": "Old Title",
           "v2_manual_classification": "Ja (eigen werk)",
           "workflow_status": "Done"
       }
       new_data = {
           "title": "New Title",
           "v2_manual_classification": "Onbekend",  # Shouldn't update!
           "workflow_status": "ToDo"  # Shouldn't update!
       }

       updates = QLIK_MERGE_RULES.get_updates(old_item, new_data)

       assert "title" in updates
       assert "v2_manual_classification" not in updates
       assert "workflow_status" not in updates


   def test_faculty_rules_protect_system_fields():
       """Test that Faculty rules never update system-managed fields."""
       old_item = {
           "title": "System Title",
           "count_students_registered": 100,
           "v2_manual_classification": "Onbekend"
       }
       new_data = {
           "title": "Should Not Update",
           "count_students_registered": 999,
           "v2_manual_classification": "Ja (eigen werk)"
       }

       updates = FACULTY_MERGE_RULES.get_updates(old_item, new_data)

       assert "title" not in updates
       assert "count_students_registered" not in updates
       assert "v2_manual_classification" in updates
   ```

4. **Run tests:**
   ```bash
   pytest src/apps/ingest/tests/test_comparison.py -v
   ```

**✅ Completion Criteria:**
- [ ] Comparison strategy system implemented and tested
- [ ] Qlik merge rules defined (system fields only)
- [ ] Faculty merge rules defined (human fields only)
- [ ] Cross-contamination prevented (tests pass)
- [ ] Rules are explicit and readable (no complex inheritance)

**📝 Notes:**
- This is a **major simplification** from legacy merging.py
- Field ownership is now explicit in merge_rules.py
- Easy to audit: "Which fields can Qlik update?" → Read QLIK_MERGE_RULES
- Can extend to PRIORITY_LIST strategy later if needed (e.g., for workflow status)

---

### ⚙️ STEP 5: Batch Processor (The Engine)

**Why:**
- Orchestrates the actual database updates
- Applies merge rules from Step 4
- Creates audit trail via ChangeLog
- Handles both NEW items (Qlik) and UPDATE-only (Faculty)

**Current State:** No processor exists
**Target State:** Clean processor service

**Implementation:**

1. **Create `src/apps/ingest/services/processor.py`:**

   ```python
   """
   Batch processing engine for ingestion pipeline.

   Applies merge rules and updates CopyrightItem records.
   Replaces legacy ea-cli/easy_access/db/update.py (~1,800 lines)
   """
   from django.db import transaction
   from django.utils import timezone
   from loguru import logger
   from typing import Dict, List, Optional

   from apps.core.models import CopyrightItem, ChangeLog
   from apps.ingest.models import (
       IngestionBatch, FacultyEntry, QlikEntry, ProcessingFailure
   )
   from .merge_rules import QLIK_MERGE_RULES, FACULTY_MERGE_RULES


   class BatchProcessor:
       """
       Processes an IngestionBatch and updates CopyrightItems.
       """

       def __init__(self, batch: IngestionBatch):
           self.batch = batch
           self.stats = {
               "created": 0,
               "updated": 0,
               "skipped": 0,
               "failed": 0
           }
           self.logs: List[str] = []

       def process(self):
           """
           Main processing entrypoint.
           Delegates to Qlik or Faculty processor based on batch type.
           """
           logger.info(f"Processing batch {self.batch.id} ({self.batch.get_ingestion_type_display()})")

           try:
               self.batch.status = IngestionBatch.Status.PROCESSING
               self.batch.save(update_fields=['status'])

               if self.batch.ingestion_type == IngestionBatch.Type.QLIK:
                   self._process_qlik_entries()
               elif self.batch.ingestion_type == IngestionBatch.Type.FACULTY:
                   self._process_faculty_entries()

               # Mark complete
               self.batch.status = IngestionBatch.Status.COMPLETED
               self.batch.completed_at = timezone.now()
               self.batch.items_created = self.stats["created"]
               self.batch.items_updated = self.stats["updated"]
               self.batch.items_skipped = self.stats["skipped"]
               self.batch.items_failed = self.stats["failed"]
               self.batch.log = "\n".join(self.logs)
               self.batch.save()

               logger.info(f"Batch {self.batch.id} completed: {self.stats}")

           except Exception as e:
               logger.exception(f"Batch {self.batch.id} failed")
               self.batch.status = IngestionBatch.Status.ERROR
               self.batch.error_message = str(e)
               self.batch.save()
               raise

       def _process_qlik_entries(self):
           """
           Process Qlik entries: Create NEW or Update EXISTING.
           """
           entries = QlikEntry.objects.filter(
               ingestion=self.batch,
               processed=False
           ).select_related('ingestion')

           logger.info(f"Processing {entries.count()} Qlik entries")

           # Pre-fetch existing items for efficiency
           material_ids = [e.material_id for e in entries]
           existing_items = {
               item.material_id: item
               for item in CopyrightItem.objects.filter(material_id__in=material_ids)
           }

           for entry in entries:
               try:
                   with transaction.atomic():
                       existing_item = existing_items.get(entry.material_id)

                       if existing_item:
                           # UPDATE existing item
                           self._update_item_from_qlik(existing_item, entry)
                       else:
                           # CREATE new item
                           self._create_item_from_qlik(entry)

                       entry.processed = True
                       entry.save(update_fields=['processed'])

               except Exception as e:
                   logger.error(f"Failed to process Qlik entry {entry.material_id}: {e}")
                   self._record_failure(entry, str(e))
                   entry.processing_error = str(e)
                   entry.processed = True  # Mark as processed to avoid retry
                   entry.save()

       def _create_item_from_qlik(self, entry: QlikEntry):
           """Create a new CopyrightItem from Qlik data."""
           data = entry.data

           item = CopyrightItem.objects.create(
               material_id=entry.material_id,
               # Map all fields from data dict
               **self._map_qlik_data_to_fields(data)
           )

           # Create audit log
           ChangeLog.objects.create(
               item=item,
               batch=self.batch,
               user=self.batch.uploaded_by,
               change_type=ChangeLog.ChangeType.CREATED,
               changes={"created": "New item from Qlik"},
               notes=f"Created from Qlik ingestion {self.batch.id}"
           )

           self.stats["created"] += 1
           self.logs.append(f"Created item {item.material_id}")

       def _update_item_from_qlik(self, item: CopyrightItem, entry: QlikEntry):
           """Update existing CopyrightItem with Qlik data."""
           # Get current values as dict
           old_values = {
               field: getattr(item, field)
               for field in QLIK_MERGE_RULES.rules.keys()
           }

           # Determine which fields should update
           updates = QLIK_MERGE_RULES.get_updates(old_values, entry.data)

           if not updates:
               self.stats["skipped"] += 1
               return

           # Apply updates
           for field, value in updates.items():
               setattr(item, field, value)
           item.save(update_fields=list(updates.keys()))

           # Create audit log
           changes = {
               field: {"old": old_values[field], "new": value}
               for field, value in updates.items()
           }
           ChangeLog.objects.create(
               item=item,
               batch=self.batch,
               user=self.batch.uploaded_by,
               change_type=ChangeLog.ChangeType.UPDATED,
               changes=changes,
               notes=f"Updated from Qlik ingestion {self.batch.id}"
           )

           self.stats["updated"] += 1
           self.logs.append(f"Updated item {item.material_id}: {list(updates.keys())}")

       def _process_faculty_entries(self):
           """
           Process Faculty entries: UPDATE-only (never creates).
           """
           entries = FacultyEntry.objects.filter(
               ingestion=self.batch,
               processed=False
           ).select_related('ingestion')

           logger.info(f"Processing {entries.count()} Faculty entries")

           # Pre-fetch existing items
           material_ids = [e.material_id for e in entries]
           existing_items = {
               item.material_id: item
               for item in CopyrightItem.objects.filter(material_id__in=material_ids)
           }

           for entry in entries:
               try:
                   with transaction.atomic():
                       existing_item = existing_items.get(entry.material_id)

                       if not existing_item:
                           # Faculty data can't create items
                           self.logs.append(f"Skipped {entry.material_id}: Item not found")
                           self.stats["skipped"] += 1
                           entry.processed = True
                           entry.save(update_fields=['processed'])
                           continue

                       self._update_item_from_faculty(existing_item, entry)
                       entry.processed = True
                       entry.save(update_fields=['processed'])

               except Exception as e:
                   logger.error(f"Failed to process Faculty entry {entry.material_id}: {e}")
                   self._record_failure(entry, str(e))
                   entry.processing_error = str(e)
                   entry.processed = True
                   entry.save()

       def _update_item_from_faculty(self, item: CopyrightItem, entry: FacultyEntry):
           """Update CopyrightItem with Faculty sheet data."""
           # Build new data dict from entry
           new_data = {
               'v2_manual_classification': entry.v2_manual_classification,
               'v2_lengte': entry.v2_lengte,
               'v2_overnamestatus': entry.v2_overnamestatus,
               'manual_classification': entry.manual_classification,
               'manual_identifier': entry.manual_identifier,
               'remarks': entry.remarks,
               'scope': entry.scope,
               'workflow_status': entry.workflow_status,
           }

           # Get current values
           old_values = {
               field: getattr(item, field)
               for field in FACULTY_MERGE_RULES.rules.keys()
           }

           # Determine updates
           updates = FACULTY_MERGE_RULES.get_updates(old_values, new_data)

           if not updates:
               self.stats["skipped"] += 1
               return

           # Apply updates
           for field, value in updates.items():
               setattr(item, field, value)
           item.save(update_fields=list(updates.keys()))

           # Create audit log
           changes = {
               field: {"old": old_values[field], "new": value}
               for field, value in updates.items()
           }
           ChangeLog.objects.create(
               item=item,
               batch=self.batch,
               user=self.batch.uploaded_by,
               change_type=ChangeLog.ChangeType.UPDATED,
               changes=changes,
               notes=f"Updated from Faculty sheet {self.batch.id}"
           )

           self.stats["updated"] += 1
           self.logs.append(f"Updated item {item.material_id}: {list(updates.keys())}")

       def _map_qlik_data_to_fields(self, data: dict) -> dict:
           """Map Qlik data dict to CopyrightItem field names."""
           # This mapping depends on your exact Qlik export structure
           # Adjust field names as needed
           return {
               'title': data.get('title'),
               'author': data.get('author'),
               'filename': data.get('filename'),
               'url': data.get('url'),
               'canvas_course_id': data.get('canvas_course_id'),
               'file_exists': data.get('file_exists'),
               'status': data.get('status'),
               'count_students_registered': data.get('count_students_registered'),
               # Add remaining fields...
           }

       def _record_failure(self, entry, error_message: str):
           """Record a processing failure."""
           ProcessingFailure.objects.create(
               batch=self.batch,
               material_id=getattr(entry, 'material_id', None),
               error_type="ProcessingError",
               error_message=error_message,
               failed_data=entry.data if isinstance(entry, QlikEntry) else entry.__dict__
           )
           self.stats["failed"] += 1
   ```

2. **Delete legacy services:**
   ```bash
   # If these exist:
   rm src/apps/core/services/pipeline.py
   rm src/apps/core/services/merging.py
   ```

3. **Update `src/apps/ingest/services/__init__.py`:**
   ```python
   from .standardizer import DataFrameStandardizer
   from .validators import FieldValidator
   from .processor import BatchProcessor

   __all__ = ['DataFrameStandardizer', 'FieldValidator', 'BatchProcessor']
   ```

**✅ Completion Criteria:**
- [ ] Processor can handle both Qlik and Faculty batches
- [ ] Uses merge rules correctly (no cross-contamination)
- [ ] Creates ChangeLog entries for all changes
- [ ] Records failures in ProcessingFailure model
- [ ] Updates batch statistics correctly
- [ ] Legacy pipeline.py and merging.py removed

---

### 📊 STEP 6: Excel Export Service (Legacy Compatibility)

**Why:**
- Users depend on Excel workflow until Dashboard (Phase C) is ready
- Must maintain exact format compatibility (columns, validation, formatting)
- Allows gradual migration without disrupting current processes

**Current State:** No export service in Django app
**Target State:** Excel builder service matching legacy output exactly

**Legacy Reference:**
- `ea-cli/easy_access/sheets/export.py` (main export logic ~483 lines)
- `ea-cli/easy_access/sheets/sheet.py` (formatting, protection, validation)
- `ea-cli/easy_access/sheets/analysis.py` (faculty overview generation)

**Design Decision:**
- Service returns BytesIO object (in-memory file), NOT disk file
- Django view serves this as HTTP response
- Use Polars for data retrieval (not direct ORM iteration)

**Implementation:**

1. **Create `src/apps/ingest/services/excel_builder.py`:**

   ```python
   """
   Excel export service for backward compatibility.

   Generates faculty-specific Excel sheets matching legacy ea-cli format.
   Based on ea-cli/easy_access/sheets/export.py
   """
   from io import BytesIO
   from typing import Optional, Dict
   import polars as pl
   from openpyxl import Workbook
   from openpyxl.styles import Font, PatternFill, Alignment
   from openpyxl.worksheet.datavalidation import DataValidation
   from openpyxl.worksheet.protection import SheetProtection
   from loguru import logger

   from apps.core.models import CopyrightItem, Organization


   class ExcelBuilder:
       """
       Builds Excel files for faculty sheets.

       Matches legacy export format including:
       - Column ordering
       - Data validation rules
       - Conditional formatting
       - Sheet protection
       - Multiple sheets per faculty
       """

       # Column definitions (must match legacy exactly)
       FACULTY_SHEET_COLUMNS = [
           'material_id',
           'title',
           'author',
           'filename',
           'url',
           'workflow_status',
           'v2_manual_classification',
           'v2_lengte',
           'v2_overnamestatus',
           'remarks',
           'scope',
           'count_students_registered',
           'pagecount',
           # Add remaining columns from legacy...
       ]

       EDITABLE_COLUMNS = [
           'workflow_status',
           'v2_manual_classification',
           'v2_lengte',
           'v2_overnamestatus',
           'remarks',
           'scope',
       ]

       def __init__(self, faculty_code: Optional[str] = None):
           """
           Initialize builder for specific faculty or all.

           Args:
               faculty_code: Faculty abbreviation (e.g., 'EEMCS'), or None for all
           """
           self.faculty_code = faculty_code

       def build(self) -> BytesIO:
           """
           Build Excel file and return as BytesIO.

           Returns:
               BytesIO object containing Excel file
           """
           logger.info(f"Building Excel export for faculty: {self.faculty_code or 'ALL'}")

           # Fetch data
           data = self._fetch_data()

           if data.is_empty():
               logger.warning("No data to export")
               return self._create_empty_workbook()

           # Create workbook
           wb = Workbook()
           wb.remove(wb.active)  # Remove default sheet

           # Group by faculty and create sheets
           for faculty_code in data['faculty'].unique():
               faculty_data = data.filter(pl.col('faculty') == faculty_code)
               self._create_faculty_sheet(wb, faculty_code, faculty_data)

           # Add overview sheet
           self._create_overview_sheet(wb, data)

           # Save to BytesIO
           output = BytesIO()
           wb.save(output)
           output.seek(0)

           logger.info(f"Excel export created: {len(wb.sheetnames)} sheets")
           return output

       def _fetch_data(self) -> pl.DataFrame:
           """
           Fetch CopyrightItem data as Polars DataFrame.

           Uses Django ORM but converts to Polars for processing.
           """
           queryset = CopyrightItem.objects.all()

           if self.faculty_code:
               queryset = queryset.filter(faculty__abbreviation=self.faculty_code)

           # Convert to list of dicts
           data = list(queryset.values(*self.FACULTY_SHEET_COLUMNS))

           if not data:
               return pl.DataFrame()

           # Convert to Polars for efficient processing
           df = pl.DataFrame(data)

           # Apply any transformations needed
           df = self._transform_for_export(df)

           return df

       def _transform_for_export(self, df: pl.DataFrame) -> pl.DataFrame:
           """Apply transformations for Excel export."""
           # Convert enums to display values
           # Handle null values
           # Format dates
           # etc.
           return df

       def _create_faculty_sheet(self, wb: Workbook, faculty_code: str, data: pl.DataFrame):
           """
           Create sheet for one faculty.

           Applies legacy formatting, validation, and protection.
           """
           ws = wb.create_sheet(title=faculty_code)

           # Write headers
           for col_idx, col_name in enumerate(self.FACULTY_SHEET_COLUMNS, start=1):
               cell = ws.cell(row=1, column=col_idx)
               cell.value = col_name
               cell.font = Font(bold=True)
               cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

           # Write data
           for row_idx, row in enumerate(data.iter_rows(named=True), start=2):
               for col_idx, col_name in enumerate(self.FACULTY_SHEET_COLUMNS, start=1):
                   cell = ws.cell(row=row_idx, column=col_idx)
                   cell.value = row.get(col_name)

                   # Lock non-editable cells
                   if col_name not in self.EDITABLE_COLUMNS:
                       cell.protection = SheetProtection(locked=True)

           # Add data validation for enum fields
           self._add_data_validation(ws, data.height)

           # Protect sheet (allow editing only specific columns)
           ws.protection.sheet = True
           ws.protection.enable()

       def _add_data_validation(self, ws, num_rows: int):
           """
           Add data validation to editable columns.

           Replicates legacy validation rules.
           """
           # Workflow status validation
           workflow_col = self._get_column_letter('workflow_status')
           workflow_validation = DataValidation(
               type="list",
               formula1='"ToDo,InProgress,Done"',
               allow_blank=True
           )
           ws.add_data_validation(workflow_validation)
           workflow_validation.add(f'{workflow_col}2:{workflow_col}{num_rows+1}')

           # Classification validation
           classification_col = self._get_column_letter('v2_manual_classification')
           classification_values = '"Ja (eigen werk),Ja (open licentie),Nee,Onbekend"'
           classification_validation = DataValidation(
               type="list",
               formula1=classification_values,
               allow_blank=True
           )
           ws.add_data_validation(classification_validation)
           classification_validation.add(f'{classification_col}2:{classification_col}{num_rows+1}')

           # Add remaining validations...

       def _create_overview_sheet(self, wb: Workbook, data: pl.DataFrame):
           """Create summary overview sheet."""
           ws = wb.create_sheet(title="Overview", index=0)

           # Summary statistics by faculty
           summary = data.group_by('faculty').agg([
               pl.count('material_id').alias('total_items'),
               pl.sum('count_students_registered').alias('total_students'),
               # Add more aggregations...
           ])

           # Write summary to sheet
           ws['A1'] = "Faculty"
           ws['B1'] = "Total Items"
           ws['C1'] = "Total Students"

           for row_idx, row in enumerate(summary.iter_rows(named=True), start=2):
               ws.cell(row=row_idx, column=1, value=row['faculty'])
               ws.cell(row=row_idx, column=2, value=row['total_items'])
               ws.cell(row=row_idx, column=3, value=row['total_students'])

       def _create_empty_workbook(self) -> BytesIO:
           """Create empty workbook when no data available."""
           wb = Workbook()
           ws = wb.active
           ws.title = "No Data"
           ws['A1'] = "No data available for export"

           output = BytesIO()
           wb.save(output)
           output.seek(0)
           return output

       def _get_column_letter(self, column_name: str) -> str:
           """Get Excel column letter for field name."""
           from openpyxl.utils import get_column_letter
           try:
               col_idx = self.FACULTY_SHEET_COLUMNS.index(column_name) + 1
               return get_column_letter(col_idx)
           except ValueError:
               return 'A'
   ```

2. **Create tests** (`src/apps/ingest/tests/test_excel_builder.py`):

   ```python
   import pytest
   from io import BytesIO
   from openpyxl import load_workbook
   from apps.ingest.services.excel_builder import ExcelBuilder
   from apps.core.models import CopyrightItem, Organization


   @pytest.mark.django_db
   def test_excel_builder_creates_file():
       """Test that builder creates valid Excel file."""
       # Create test data
       faculty = Organization.objects.create(
           name="Electrical Engineering",
           abbreviation="EEMCS",
           org_type=Organization.Type.FACULTY
       )
       CopyrightItem.objects.create(
           material_id=123,
           title="Test Item",
           faculty=faculty
       )

       # Build Excel
       builder = ExcelBuilder(faculty_code="EEMCS")
       output = builder.build()

       # Verify it's valid Excel
       assert isinstance(output, BytesIO)
       wb = load_workbook(output)
       assert "EEMCS" in wb.sheetnames


   @pytest.mark.django_db
   def test_excel_has_correct_columns():
       """Test that exported sheet has all required columns."""
       faculty = Organization.objects.create(
           name="Test Faculty",
           abbreviation="TEST",
           org_type=Organization.Type.FACULTY
       )
       CopyrightItem.objects.create(
           material_id=456,
           title="Test",
           faculty=faculty
       )

       builder = ExcelBuilder(faculty_code="TEST")
       output = builder.build()

       wb = load_workbook(output)
       ws = wb["TEST"]

       # Check headers
       headers = [cell.value for cell in ws[1]]
       assert "material_id" in headers
       assert "title" in headers
       assert "workflow_status" in headers
   ```

3. **Update `src/apps/ingest/services/__init__.py`:**
   ```python
   from .standardizer import DataFrameStandardizer
   from .validators import FieldValidator
   from .processor import BatchProcessor
   from .excel_builder import ExcelBuilder

   __all__ = [
       'DataFrameStandardizer',
       'FieldValidator',
       'BatchProcessor',
       'ExcelBuilder'
   ]
   ```

4. **Verify export matches legacy:**
   ```bash
   # Run legacy export
   cd ea-cli
   python -m easy_access.sheets.export --faculty EEMCS --output /tmp/legacy.xlsx

   # Run new export (via Django shell)
   cd ../src
   python manage.py shell
   >>> from apps.ingest.services import ExcelBuilder
   >>> builder = ExcelBuilder('EEMCS')
   >>> output = builder.build()
   >>> with open('/tmp/new.xlsx', 'wb') as f:
   >>>     f.write(output.getvalue())

   # Compare files manually or with script
   ```

**✅ Completion Criteria:**
- [ ] ExcelBuilder service created
- [ ] Returns BytesIO (not disk file)
- [ ] Includes all legacy columns in correct order
- [ ] Data validation rules applied
- [ ] Sheet protection implemented
- [ ] Overview sheet generated
- [ ] Output matches legacy format exactly
- [ ] Tests verify structure and content

**📝 Notes:**
- This is **temporary** - Phase C will replace with HTMX dashboard
- Focus on exact compatibility, not new features
- Openpyxl version must match legacy (check pyproject.toml)
- May need to port additional formatting from `sheet.py`

---

### ⚡ STEP 7: Async Task Orchestration

**Why:**
- File uploads can take 30+ seconds → browser timeout
- Need background processing with progress updates
- User should not wait for processing to complete

**Current State:** `ingest/tasks.py` exists but incomplete
**Target State:** Full async task pipeline

**Design Decision:**
Use Django's native background tasks (Django 6.0) OR Celery. For Phase A, native tasks are sufficient.

**Implementation:**

1. **Update `src/apps/ingest/tasks.py`:**

   ```python
   """
   Async tasks for ingestion pipeline.

   Handles file upload → standardization → staging → processing flow.
   """
   from django.db import transaction
   from django.utils import timezone
   from loguru import logger
   import polars as pl

   from apps.ingest.models import IngestionBatch, FacultyEntry, QlikEntry
   from apps.ingest.services import DataFrameStandardizer, BatchProcessor


   def stage_batch_task(batch_id: int):
       """
       Stage 1: Read file, standardize, create entries.

       Args:
           batch_id: ID of IngestionBatch to process
       """
       try:
           batch = IngestionBatch.objects.get(id=batch_id)
           batch.status = IngestionBatch.Status.STAGING
           batch.save(update_fields=['status'])

           logger.info(f"Staging batch {batch_id} ({batch.get_ingestion_type_display()})")

           # Read file with Polars
           df = pl.read_excel(batch.source_file.path)

           # Standardize
           source_type = "qlik" if batch.ingestion_type == IngestionBatch.Type.QLIK else "faculty"
           df = DataFrameStandardizer.standardize(df, source_type=source_type)

           # Bulk create entries
           if batch.ingestion_type == IngestionBatch.Type.QLIK:
               entries = [
                   QlikEntry(
                       ingestion=batch,
                       material_id=row['material_id'],
                       data=row,  # Store full row as JSON
                   )
                   for row in df.iter_rows(named=True)
               ]
               QlikEntry.objects.bulk_create(entries, batch_size=1000)
               logger.info(f"Created {len(entries)} Qlik entries")

           elif batch.ingestion_type == IngestionBatch.Type.FACULTY:
               entries = [
                   FacultyEntry(
                       ingestion=batch,
                       material_id=row['material_id'],
                       v2_manual_classification=row.get('v2_manual_classification'),
                       v2_lengte=row.get('v2_lengte'),
                       v2_overnamestatus=row.get('v2_overnamestatus'),
                       manual_classification=row.get('manual_classification'),
                       manual_identifier=row.get('manual_identifier'),
                       remarks=row.get('remarks'),
                       scope=row.get('scope'),
                       workflow_status=row.get('workflow_status'),
                   )
                   for row in df.iter_rows(named=True)
               ]
               FacultyEntry.objects.bulk_create(entries, batch_size=1000, ignore_conflicts=True)
               logger.info(f"Created {len(entries)} Faculty entries")

           # Update status
           batch.status = IngestionBatch.Status.STAGED
           batch.save(update_fields=['status'])

           # Trigger processing
           process_batch_task(batch_id)

       except Exception as e:
           logger.exception(f"Failed to stage batch {batch_id}")
           batch = IngestionBatch.objects.get(id=batch_id)
           batch.status = IngestionBatch.Status.ERROR
           batch.error_message = f"Staging failed: {str(e)}"
           batch.save()
           raise


   def process_batch_task(batch_id: int):
       """
       Stage 2: Process entries and update CopyrightItems.

       Args:
           batch_id: ID of IngestionBatch to process
       """
       try:
           batch = IngestionBatch.objects.get(id=batch_id)

           logger.info(f"Processing batch {batch_id}")

           # Run processor
           processor = BatchProcessor(batch)
           processor.process()

           logger.info(f"Batch {batch_id} processing complete")

       except Exception as e:
           logger.exception(f"Failed to process batch {batch_id}")
           raise
   ```

2. **Create management command for manual trigger** (`src/apps/ingest/management/commands/process_batch.py`):

   ```python
   from django.core.management.base import BaseCommand
   from apps.ingest.models import IngestionBatch
   from apps.ingest.tasks import stage_batch_task


   class Command(BaseCommand):
       help = 'Process an ingestion batch'

       def add_arguments(self, parser):
           parser.add_argument('batch_id', type=int, help='ID of batch to process')

       def handle(self, *args, **options):
           batch_id = options['batch_id']

           try:
               batch = IngestionBatch.objects.get(id=batch_id)
               self.stdout.write(f"Processing batch {batch_id}...")

               stage_batch_task(batch_id)

               self.stdout.write(self.style.SUCCESS(f"Batch {batch_id} processed successfully"))

           except IngestionBatch.DoesNotExist:
               self.stdout.write(self.style.ERROR(f"Batch {batch_id} not found"))
           except Exception as e:
               self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
   ```

3. **Test task execution:**
   ```bash
   python src/manage.py shell
   >>> from apps.ingest.models import IngestionBatch
   >>> from apps.ingest.tasks import stage_batch_task
   >>> # Create test batch first via admin
   >>> stage_batch_task(1)
   ```

**✅ Completion Criteria:**
- [ ] Tasks can be triggered manually
- [ ] Staging task reads file and creates entries
- [ ] Processing task calls BatchProcessor
- [ ] Errors are caught and logged to batch
- [ ] Can monitor batch status via admin

---

### 🌐 STEP 8: Dashboard Integration (Upload & Download)

**Why:**
- Users need web interface to upload files
- Need endpoint to download Excel exports
- Replace local folder monitoring

**Current State:** Basic dashboard structure exists
**Target State:** Functional upload/download views

**Implementation:**

1. **Update `src/apps/dashboard/views.py`:**

   ```python
   from django.shortcuts import render, redirect
   from django.contrib.auth.decorators import login_required
   from django.contrib import messages
   from django.http import HttpResponse, FileResponse
   from django.views.decorators.http import require_http_methods

   from apps.ingest.models import IngestionBatch
   from apps.ingest.tasks import stage_batch_task
   from apps.ingest.services import ExcelBuilder
   from apps.core.models import Organization


   @login_required
   def dashboard_home(request):
       """Main dashboard view."""
       recent_batches = IngestionBatch.objects.select_related('uploaded_by').order_by('-created_at')[:10]

       context = {
           'recent_batches': recent_batches,
           'faculties': Organization.objects.filter(org_type=Organization.Type.FACULTY)
       }
       return render(request, 'dashboard/home.html', context)


   @login_required
   @require_http_methods(["POST"])
   def upload_file(request):
       """Handle file upload and trigger processing."""
       if 'file' not in request.FILES:
           messages.error(request, "No file provided")
           return redirect('dashboard:home')

       file = request.FILES['file']
       ingestion_type = request.POST.get('ingestion_type')

       if ingestion_type not in [IngestionBatch.Type.QLIK, IngestionBatch.Type.FACULTY]:
           messages.error(request, "Invalid ingestion type")
           return redirect('dashboard:home')

       # Validate file extension
       if not file.name.endswith(('.xlsx', '.xls')):
           messages.error(request, "Only Excel files (.xlsx, .xls) are supported")
           return redirect('dashboard:home')

       # Create batch
       batch = IngestionBatch.objects.create(
           source_file=file,
           ingestion_type=ingestion_type,
           uploaded_by=request.user,
           status=IngestionBatch.Status.PENDING
       )

       # Trigger async processing
       try:
           stage_batch_task(batch.id)
           messages.success(request, f"File uploaded successfully. Batch #{batch.id} is processing.")
       except Exception as e:
           messages.error(request, f"Failed to start processing: {str(e)}")

       return redirect('dashboard:home')


   @login_required
   def download_faculty_sheet(request, faculty_code):
       """Download Excel export for specific faculty."""
       try:
           # Verify faculty exists
           faculty = Organization.objects.get(
               abbreviation=faculty_code,
               org_type=Organization.Type.FACULTY
           )
       except Organization.DoesNotExist:
           messages.error(request, f"Faculty {faculty_code} not found")
           return redirect('dashboard:home')

       # Build Excel
       builder = ExcelBuilder(faculty_code=faculty_code)
       output = builder.build()

       # Serve as download
       response = HttpResponse(
           output.getvalue(),
           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
       )
       response['Content-Disposition'] = f'attachment; filename="{faculty_code}_export.xlsx"'

       return response


   @login_required
   def download_all_sheets(request):
       """Download Excel export for all faculties."""
       builder = ExcelBuilder()  # No faculty_code = export all
       output = builder.build()

       from datetime import datetime
       filename = f"all_faculties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

       response = HttpResponse(
           output.getvalue(),
           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
       )
       response['Content-Disposition'] = f'attachment; filename="{filename}"'

       return response
   ```

2. **Create URL routes** (`src/apps/dashboard/urls.py`):

   ```python
   from django.urls import path
   from . import views

   app_name = 'dashboard'

   urlpatterns = [
       path('', views.dashboard_home, name='home'),
       path('upload/', views.upload_file, name='upload'),
       path('download/<str:faculty_code>/', views.download_faculty_sheet, name='download_faculty'),
       path('download/all/', views.download_all_sheets, name='download_all'),
   ]
   ```

3. **Create basic template** (`src/templates/dashboard/home.html`):

   ```html
   {% extends 'base.html' %}

   {% block content %}
   <div class="container mx-auto px-4 py-8">
       <h1 class="text-3xl font-bold mb-8">Easy Access Dashboard</h1>

       {% if messages %}
           {% for message in messages %}
           <div class="alert alert-{{ message.tags }} mb-4">
               {{ message }}
           </div>
           {% endfor %}
       {% endif %}

       <!-- Upload Section -->
       <div class="card bg-base-100 shadow-xl mb-8">
           <div class="card-body">
               <h2 class="card-title">Upload Data</h2>
               <form method="post" action="{% url 'dashboard:upload' %}" enctype="multipart/form-data">
                   {% csrf_token %}
                   <div class="form-control">
                       <label class="label">
                           <span class="label-text">Ingestion Type</span>
                       </label>
                       <select name="ingestion_type" class="select select-bordered" required>
                           <option value="QLIK">Qlik Export</option>
                           <option value="FACULTY">Faculty Sheet</option>
                       </select>
                   </div>
                   <div class="form-control mt-4">
                       <label class="label">
                           <span class="label-text">Excel File</span>
                       </label>
                       <input type="file" name="file" class="file-input file-input-bordered" accept=".xlsx,.xls" required>
                   </div>
                   <div class="card-actions justify-end mt-6">
                       <button type="submit" class="btn btn-primary">Upload & Process</button>
                   </div>
               </form>
           </div>
       </div>

       <!-- Download Section -->
       <div class="card bg-base-100 shadow-xl mb-8">
           <div class="card-body">
               <h2 class="card-title">Download Faculty Sheets</h2>
               <div class="flex flex-wrap gap-2">
                   <a href="{% url 'dashboard:download_all' %}" class="btn btn-secondary">
                       Download All
                   </a>
                   {% for faculty in faculties %}
                   <a href="{% url 'dashboard:download_faculty' faculty.abbreviation %}" class="btn btn-outline">
                       {{ faculty.abbreviation }}
                   </a>
                   {% endfor %}
               </div>
           </div>
       </div>

       <!-- Recent Batches -->
       <div class="card bg-base-100 shadow-xl">
           <div class="card-body">
               <h2 class="card-title">Recent Ingestions</h2>
               <div class="overflow-x-auto">
                   <table class="table">
                       <thead>
                           <tr>
                               <th>ID</th>
                               <th>Type</th>
                               <th>Status</th>
                               <th>Uploaded By</th>
                               <th>Created</th>
                               <th>Results</th>
                           </tr>
                       </thead>
                       <tbody>
                           {% for batch in recent_batches %}
                           <tr>
                               <td>{{ batch.id }}</td>
                               <td>{{ batch.get_ingestion_type_display }}</td>
                               <td>
                                   <span class="badge badge-{{ batch.status|lower }}">
                                       {{ batch.get_status_display }}
                                   </span>
                               </td>
                               <td>{{ batch.uploaded_by.get_full_name|default:batch.uploaded_by.username }}</td>
                               <td>{{ batch.created_at|date:"Y-m-d H:i" }}</td>
                               <td>
                                   {% if batch.status == 'COMPLETED' %}
                                       ✓{{ batch.items_created }} ~{{ batch.items_updated }} ✗{{ batch.items_failed }}
                                   {% endif %}
                               </td>
                           </tr>
                           {% endfor %}
                       </tbody>
                   </table>
               </div>
           </div>
       </div>
   </div>
   {% endblock %}
   ```

4. **Update main URLs** (`src/config/urls.py`):

   ```python
   from django.contrib import admin
   from django.urls import path, include

   urlpatterns = [
       path('admin/', admin.site.urls),
       path('', include('apps.dashboard.urls')),
   ]
   ```

**✅ Completion Criteria:**
- [ ] Can upload files via web UI
- [ ] Upload triggers async processing
- [ ] Can download faculty-specific sheets
- [ ] Can download all-faculty export
- [ ] Dashboard shows recent batch status
- [ ] Error messages display correctly

---

### 🗑️ STEP 9: Legacy Code Cleanup

**Why:**
- Remove confusing legacy code
- Prevent accidental use of old methods
- Clean codebase for future development

**Actions:**

1. **Delete legacy management commands** (if they exist):
   ```bash
   rm -f src/apps/ingest/management/commands/watch.py
   rm -f src/apps/ingest/management/commands/ingest_raw.py
   rm -f src/apps/ingest/management/commands/ingest_faculty.py
   ```

2. **Delete or archive legacy services:**
   ```bash
   # If these exist:
   rm -f src/apps/core/services/pipeline.py
   rm -f src/apps/core/services/merging.py

   # If services dir is now empty:
   rmdir src/apps/core/services
   ```

3. **Clean up ingest/utils.py:**
   - Review `src/apps/ingest/utils.py`
   - If logic has been ported to services, delete file
   - If some utilities remain, document what's left

4. **Update imports across codebase:**
   ```bash
   # Search for any remaining imports of deleted modules
   grep -r "from apps.core.services.pipeline" src/
   grep -r "from apps.core.services.merging" src/
   ```

5. **Remove unused dependencies** (check `pyproject.toml`):
   - If TortoiseORM was installed: `uv remove tortoise-orm`
   - Remove any CLI-specific packages no longer needed

**✅ Completion Criteria:**
- [ ] All legacy command files deleted
- [ ] Legacy service files removed
- [ ] No broken imports remain
- [ ] Tests still pass after cleanup
- [ ] Documentation updated to reflect new structure

---

### 💾 STEP 10: Legacy Data Migration

**Why:**
- Need to import existing data from legacy `ea-cli` system
- Preserve historical context and relationships
- One-time operation to seed new database

**Current State:** No migration tooling exists
**Target State:** All legacy data imported with audit trail

**Legacy Reference:**
- `ea-cli/copyright.db` (SQLite database)
- Legacy models: `ea-cli/easy_access/db/models.py`

**Design Decision:**
- Export from legacy as CSV (portable, inspectable)
- Import bypasses staging (direct to CopyrightItem)
- Create ChangeLog entries marking migration source

**Implementation:**

1. **Create export script in legacy repo** (`ea-cli/scripts/export_for_migration.py`):

   ```python
   """
   Export legacy data for migration to Django system.

   Run this in the ea-cli environment, not Django.
   """
   import asyncio
   import csv
   from pathlib import Path
   from easy_access.db.models import CopyrightItem
   from tortoise import Tortoise


   async def export_items():
       """Export all CopyrightItem records to CSV."""
       await Tortoise.init(
           db_url='sqlite://copyright.db',
           modules={'models': ['easy_access.db.models']}
       )

       items = await CopyrightItem.all()

       output_file = Path('migration_export.csv')

       # Define fields to export (must match Django model)
       fields = [
           'material_id', 'title', 'author', 'filename', 'url',
           'workflow_status', 'v2_manual_classification', 'v2_lengte',
           'v2_overnamestatus', 'manual_classification', 'remarks',
           'scope', 'pagecount', 'count_students_registered',
           # Add all relevant fields...
       ]

       with output_file.open('w', newline='', encoding='utf-8') as f:
           writer = csv.DictWriter(f, fieldnames=fields)
           writer.writeheader()

           for item in items:
               row = {field: getattr(item, field, None) for field in fields}
               writer.writerow(row)

       print(f"Exported {len(items)} items to {output_file}")
       await Tortoise.close_connections()


   if __name__ == '__main__':
       asyncio.run(export_items())
   ```

2. **Create import management command** (`src/apps/ingest/management/commands/load_legacy.py`):

   ```python
   """
   Load legacy data from CSV export.

   Usage:
       python manage.py load_legacy migration_export.csv
   """
   from django.core.management.base import BaseCommand
   from django.db import transaction
   from django.utils import timezone
   import csv
   from pathlib import Path

   from apps.core.models import CopyrightItem, ChangeLog, Organization
   from apps.users.models import User


   class Command(BaseCommand):
       help = 'Import legacy data from CSV export'

       def add_arguments(self, parser):
           parser.add_argument('csv_file', type=str, help='Path to CSV export file')
           parser.add_argument(
               '--dry-run',
               action='store_true',
               help='Preview without actually importing'
           )

       def handle(self, *args, **options):
           csv_path = Path(options['csv_file'])
           dry_run = options['dry_run']

           if not csv_path.exists():
               self.stdout.write(self.style.ERROR(f"File not found: {csv_path}"))
               return

           # Get or create migration user
           migration_user, _ = User.objects.get_or_create(
               username='system_migration',
               defaults={'first_name': 'System', 'last_name': 'Migration'}
           )

           # Pre-load faculty mapping
           faculties = {
               org.abbreviation: org
               for org in Organization.objects.filter(org_type=Organization.Type.FACULTY)
           }

           items_to_create = []
           logs_to_create = []

           with csv_path.open('r', encoding='utf-8') as f:
               reader = csv.DictReader(f)

               for row in reader:
                   # Map CSV fields to Django model fields
                   material_id = int(row['material_id'])

                   # Check if item already exists
                   if CopyrightItem.objects.filter(material_id=material_id).exists():
                       self.stdout.write(f"Skipping {material_id} (already exists)")
                       continue

                   # Get faculty if available
                   faculty = faculties.get(row.get('faculty'))

                   item = CopyrightItem(
                       material_id=material_id,
                       title=row.get('title'),
                       author=row.get('author'),
                       filename=row.get('filename'),
                       url=row.get('url'),
                       workflow_status=row.get('workflow_status') or 'ToDo',
                       v2_manual_classification=row.get('v2_manual_classification'),
                       v2_lengte=row.get('v2_lengte'),
                       v2_overnamestatus=row.get('v2_overnamestatus'),
                       manual_classification=row.get('manual_classification'),
                       remarks=row.get('remarks'),
                       scope=row.get('scope'),
                       pagecount=int(row.get('pagecount') or 0),
                       count_students_registered=int(row.get('count_students_registered') or 0),
                       faculty=faculty,
                       # Add remaining fields...
                   )
                   items_to_create.append(item)

               self.stdout.write(f"Prepared {len(items_to_create)} items for import")

               if dry_run:
                   self.stdout.write(self.style.WARNING("DRY RUN - No data imported"))
                   return

               # Bulk create items
               with transaction.atomic():
                   created_items = CopyrightItem.objects.bulk_create(
                       items_to_create,
                       batch_size=1000
                   )

                   self.stdout.write(self.style.SUCCESS(f"Created {len(created_items)} items"))

                   # Create audit logs
                   logs_to_create = [
                       ChangeLog(
                           item=item,
                           user=migration_user,
                           change_type=ChangeLog.ChangeType.CREATED,
                           changes={'migration': 'Imported from legacy system'},
                           notes='Legacy data migration from ea-cli'
                       )
                       for item in created_items
                   ]

                   ChangeLog.objects.bulk_create(logs_to_create, batch_size=1000)

                   self.stdout.write(self.style.SUCCESS(f"Created {len(logs_to_create)} audit logs"))

               self.stdout.write(self.style.SUCCESS("Migration complete!"))
   ```

3. **Run migration process:**

   ```bash
   # Step 1: Export from legacy system
   cd ea-cli
   python scripts/export_for_migration.py
   # Creates: migration_export.csv

   # Step 2: Copy to Django project
   cp migration_export.csv ../src/

   # Step 3: Test with dry-run
   cd ../src
   python manage.py load_legacy migration_export.csv --dry-run

   # Step 4: Execute actual import
   python manage.py load_legacy migration_export.csv

   # Step 5: Verify in Django admin
   python manage.py runserver
   # Navigate to /admin/core/copyrightitem/
   ```

4. **Create verification script** (`src/apps/ingest/management/commands/verify_migration.py`):

   ```python
   from django.core.management.base import BaseCommand
   from apps.core.models import CopyrightItem, ChangeLog


   class Command(BaseCommand):
       help = 'Verify legacy data migration'

       def handle(self, *args, **options):
           total_items = CopyrightItem.objects.count()
           migrated_items = ChangeLog.objects.filter(
               change_type=ChangeLog.ChangeType.CREATED,
               notes__contains='Legacy data migration'
           ).count()

           items_with_faculty = CopyrightItem.objects.exclude(faculty=None).count()
           items_with_classification = CopyrightItem.objects.exclude(
               v2_manual_classification='Onbekend'
           ).count()

           self.stdout.write("Migration Verification:")
           self.stdout.write(f"  Total items: {total_items}")
           self.stdout.write(f"  Migrated items: {migrated_items}")
           self.stdout.write(f"  Items with faculty: {items_with_faculty}")
           self.stdout.write(f"  Items with classification: {items_with_classification}")

           if total_items == migrated_items:
               self.stdout.write(self.style.SUCCESS("✓ All items accounted for"))
           else:
               self.stdout.write(self.style.WARNING(f"⚠ Mismatch: {total_items - migrated_items} items unaccounted"))
   ```

**✅ Completion Criteria:**
- [ ] Export script runs successfully in legacy system
- [ ] CSV contains all required fields
- [ ] Import command loads data without errors
- [ ] All items have ChangeLog entries
- [ ] Verification command confirms counts match
- [ ] Admin interface shows imported data
- [ ] Faculty relationships preserved

**📝 Notes:**
- Keep `migration_export.csv` as backup
- Migration is idempotent (safe to re-run)
- Consider exporting other models (Organization, Course) separately if needed

---

## 3. Phase A Completion Checklist

### Core Infrastructure
- [ ] **Step 1:** Custom User model created and migrated
- [ ] **Step 2:** All ingestion and audit models created
- [ ] **Step 3:** Standardization service implemented and tested
- [ ] **Step 4:** Merge rules defined and tested
- [ ] **Step 5:** Batch processor implemented
- [ ] **Step 6:** Excel export service matches legacy format
- [ ] **Step 7:** Async tasks functional
- [ ] **Step 8:** Dashboard upload/download working
- [ ] **Step 9:** Legacy code cleaned up
- [ ] **Step 10:** Data migration complete

### Functional Validation
- [ ] Can upload Qlik file via dashboard
- [ ] Qlik ingestion creates new items correctly
- [ ] Qlik ingestion updates existing items (system fields only)
- [ ] Can upload Faculty file via dashboard
- [ ] Faculty ingestion updates existing items (human fields only)
- [ ] Faculty ingestion never creates new items
- [ ] Excel exports match legacy format exactly
- [ ] All changes logged in ChangeLog
- [ ] Processing failures recorded for inspection
- [ ] Admin interface shows all models

### Testing
- [ ] Standardizer tests pass
- [ ] Comparison/merge rule tests pass
- [ ] Excel builder tests pass
- [ ] Integration test: Full Qlik ingestion flow
- [ ] Integration test: Full Faculty ingestion flow
- [ ] Verification: No legacy pipeline code remains
- [ ] Verification: No dependency on local folders

### Documentation
- [ ] README updated with new architecture
- [ ] Setup instructions for developers
- [ ] User guide for upload/download workflow
- [ ] API documentation for services (if needed)
- [ ] Known issues and limitations documented

---

## 4. Post-Phase A: Next Steps

### Phase B Preview (Enrichment)
**Goal:** Add external data sources to enrich CopyrightItems

**Key Features:**
- Osiris scraping for person/course data
- Canvas API integration for PDF metadata
- Automatic enrichment trigger after Qlik ingestion
- Staleness detection and re-enrichment

**Models to Add:**
- `EnrichmentJob` (tracks enrichment runs)
- `PersonMatch` (links authors to Person records)
- `PDFMetadata` (Canvas locking status, etc.)

**Services to Create:**
- `apps/enrichment/services/osiris_scraper.py`
- `apps/enrichment/services/canvas_client.py`
- `apps/documents/services/pdf_downloader.py`

### Phase C Preview (Dashboard & Classification)
**Goal:** Replace Excel workflow with interactive web interface

**Key Features:**
- HTMX-powered editing grid
- Inline field editing
- PDF preview split-screen
- Bulk operations
- ML classification suggestions

**Components:**
- `apps/dashboard/views` (HTMX views)
- `apps/classification/services/classifier.py` (CatBoost model)
- `apps/classification/services/rules.py` (deterministic rules)
- Permission system for editors

---

## 5. Troubleshooting Guide

### Common Issues

**Issue: "No module named 'apps.users'"**
- **Cause:** User app not in INSTALLED_APPS
- **Fix:** Add `'apps.users'` to settings.py INSTALLED_APPS

**Issue: "Column 'user_id' cannot be null"**
- **Cause:** Trying to create records without migrating to custom User
- **Fix:** Delete database and migrations, start from Step 1

**Issue: "Polars cannot read Excel file"**
- **Cause:** File corruption or unsupported format
- **Fix:** Check file extension, try re-saving as .xlsx

**Issue: "Task does not complete"**
- **Cause:** No async worker running OR exception swallowed
- **Fix:** Check batch status in admin, review logs

**Issue: "Excel export has wrong columns"**
- **Cause:** FACULTY_SHEET_COLUMNS doesn't match legacy
- **Fix:** Compare with ea-cli/easy_access/sheets/export.py line-by-line

**Issue: "Faculty ingestion creates new items"**
- **Cause:** Bug in processor._process_faculty_entries
- **Fix:** Should skip non-existent items, never create

### Performance Optimization

**Slow batch processing:**
- Ensure `select_related()` used in processor
- Verify `bulk_create()` batch_size appropriate (default 1000)
- Check database indexes on material_id

**Large Excel exports:**
- Consider pagination or streaming for huge datasets
- Use Polars lazy API if memory constrained
- Add export progress indicator

---

## 6. Final Review & Sign-Off

At the end of Phase A, the system will have:

✅ **Architecture:**
- Clean separation: Models → Services → Tasks → Views
- No dependency on local filesystem folders
- Full audit trail (who did what, when)
- Async processing (no browser timeouts)

✅ **Data Integrity:**
- Field ownership enforced (System vs Human)
- All changes logged in ChangeLog
- Failed items captured in ProcessingFailure
- Idempotent operations (safe to retry)

✅ **User Experience:**
- Web-based upload (no more file copying)
- Status tracking for ingestions
- Excel download maintains workflow compatibility
- Admin interface for inspection

✅ **Code Quality:**
- Testable services (no Django dependencies)
- Explicit merge rules (no complex strategies)
- Legacy code removed (no confusion)
- Ready for Phase B (enrichment)

---

## Appendix A: Key Design Decisions

### Why Custom User Model?
- Required before any ForeignKeys to User
- Allows future extensions (departments, roles)
- Django best practice for new projects

### Why Separate FacultyEntry and QlikEntry?
- Different data structures
- Different validation rules
- Explicit staging → easier debugging

### Why Field Ownership Model?
- Simpler than Strategy pattern
- Explicit rules easy to audit
- Prevents cross-contamination
- Matches mental model of users

### Why BytesIO for Excel?
- No disk I/O required
- Works in containerized environments
- Easier to test (no file cleanup)
- Direct HTTP streaming

### Why Polars over Pandas?
- 2-10x faster for large datasets
- Better memory efficiency
- Native lazy evaluation
- Modern API

---

## Appendix B: Field Mapping Reference

### Qlik Updatable Fields (System-Managed)
```python
title, author, filename, url, canvas_course_id, file_exists,
status, count_students_registered, pages_x_students,
last_scan_date_university, last_scan_date_course, ml_prediction
```

### Faculty Updatable Fields (Human-Managed)
```python
v2_manual_classification, v2_lengte, v2_overnamestatus,
manual_classification, manual_identifier, remarks, scope,
workflow_status
```

### Protected Fields (Never Updated by Ingestion)
```python
material_id (primary key - immutable)
created_at, modified_at (auto-managed)
```

---

**Document Version:** 5.0 Final
**Last Updated:** December 16, 2025
**Status:** ✅ Ready for Implementation
