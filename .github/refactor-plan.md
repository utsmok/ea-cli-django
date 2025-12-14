
---

# Easy Access Platform (v2.0) - Master Development Guide
**Date:** December 14, 2025
**Target Stack:** Django 6.0, Python 3.12+, PostgreSQL 17, Polars, Docker, CatBoost.
**Status:** Implementation Ready

## 📋 Executive Summary
We are refactoring the `ea-cli` tool (Tortoise ORM/Pandas) into a robust **Django 6.0** platform.
*   **Legacy Code:** The original `ea-cli` is included as a submodule for direct field/logic reference.
*   **Database Strategy:** We are replicating the V1 schema strictness (fields, types) but porting relations to Django's ORM standards.
*   **Migration:** Data will be exported from V1 to CSV/JSON, then ingested via Polars into the V2 `StagedItem` table.

---

## 🛠 Phase 1: Infrastructure & Project Structure

### 1.1 File Structure
Initialize the repository. **Action:** Run `git submodule add <ea-cli-repo-url> ea-cli` to mount the legacy code.

```text
copyright-platform/
├── .devcontainer/devcontainer.json
├── ea-cli/                              # [SUBMODULE] Reference Code
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
├── documents/                           # [VOLUME] Mapped to local storage (NAS/Disk)
├── raw_data/                            # [VOLUME] Watch folder for Excel
├── src/
│   ├── apps/
│   │   ├── api/
│   │   ├── classification/              # Rule Engine & ML
│   │   │   ├── widget/                  # AnyWidget (Notebook)
│   │   │   └── pipeline/                # Heuristics
│   │   ├── core/                        # Organization, Person, Users
│   │   ├── dashboard/                   # HTMX Views
│   │   ├── documents/                   # PDF & Canvas Metadata models
│   │   ├── enrichment/                  # External APIs
│   │   └── ingest/                      # Polars Tasks
│   ├── config/
│   └── manage.py
├── .env.example
├── docker-compose.yml
└── pyproject.toml
```

### 1.2 Configuration
**`pyproject.toml`** (Combined Dependencies)
```toml
[project]
name = "copyright-platform"
version = "2.0.0"
requires-python = ">=3.12"
dependencies = [
    "django>=6.0",
    "django-shinobi",
    "django-htmx",
    "django-environ",
    "django-redis-tasks",
    "psycopg[binary]",
    "redis",
    "polars[xlsx,pyarrow]",
    "catboost",
    "scikit-learn",
    "watchfiles",
    "anywidget",
    "pypdf",
    "Levenshtein",
    "loguru"
]
```

---

## 💾 Phase 2: Core Data Modeling
**Objective:** Port the exact schema from `ea-cli/easy_access/db/models.py`.

### 2.1 Enums (`apps.core.choices`)
Map `ea-cli/easy_access/db/enums.py` to Django `TextChoices`.

```python
# src/apps/core/choices.py
from django.db import models

class ClassificationV2(models.TextChoices):
    # Match strings exactly from legacy enums.py
    JA_OPEN_LICENTIE = "Ja (open licentie)", "Ja (Open Licentie)"
    JA_EIGEN_WERK = "Ja (eigen werk)", "Ja (Eigen Werk)"
    JA_EASY_ACCESS = "Ja (easy access)", "Ja (Easy Access)"
    JA_ANDERS = "Ja (anders)", "Ja (anders)"
    NEE_LINK = "Nee (Link beschikbaar)", "Nee (Link beschikbaar)"
    NEE = "Nee", "Nee"
    ONBEKEND = "Onbekend", "Onbekend"
    # ... include all TIJDELIJK variants ...

class WorkflowStatus(models.TextChoices):
    TODO = "ToDo", "ToDo"
    DONE = "Done", "Done"
    IN_PROGRESS = "InProgress", "In Progress"

class Filetype(models.TextChoices):
    PDF = "pdf", "PDF"
    PPT = "ppt", "PowerPoint"
    DOC = "doc", "Word"
    UNKNOWN = "unknown", "Unknown"
    # ... map remaining from Legacy Filetype ...
```

### 2.2 Domain Models (`apps.core.models`)
Refactor `Organization`, `Faculty`, `Person`.

```python
from django.db import models
from .choices import *

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Organization(TimestampedModel):
    """
    Consolidates Legacy 'Organization' and 'Faculty' and 'Programme'
    Legacy: Organization (db table 'organization_data')
    """
    class Type(models.TextChoices):
        UNI = "UNI", "University"
        FACULTY = "FAC", "Faculty"
        DEPT = "DEP", "Department"
        PROG = "PROG", "Programme"

    name = models.CharField(max_length=2048, db_index=True)
    abbreviation = models.CharField(max_length=255, db_index=True)
    full_abbreviation = models.CharField(max_length=2048, unique=True, null=True)
    org_type = models.CharField(choices=Type.choices, default=Type.FACULTY)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('name', 'abbreviation')

class Person(TimestampedModel):
    # Match legacy table 'person_data'
    input_name = models.CharField(max_length=2048, unique=True, db_index=True)
    main_name = models.CharField(max_length=2048, null=True, blank=True)
    first_name = models.CharField(max_length=2048, null=True, blank=True)
    email = models.CharField(max_length=2048, null=True, blank=True)
    people_page_url = models.URLField(max_length=2048, null=True, blank=True)
    match_confidence = models.FloatField(null=True)

    orgs = models.ManyToManyField(Organization, related_name='employees')
```

### 2.3 Copyright Models (`apps.core.models`)
The core `CopyrightItem` must contain every field from `v1` and `v2`.

```python
class CopyrightItem(TimestampedModel):
    # Primary Key
    material_id = models.BigIntegerField(primary_key=True)

    # Identifiers & Status
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filehash = models.CharField(max_length=255, db_index=True, null=True)
    url = models.URLField(max_length=2048, null=True, unique=True) # Check Legacy uniqueness
    workflow_status = models.CharField(choices=WorkflowStatus.choices, default=WorkflowStatus.TODO, db_index=True)

    # Classification Fields
    v2_manual_classification = models.CharField(choices=ClassificationV2.choices, default=ClassificationV2.ONBEKEND)
    # Legacy field retention
    manual_classification = models.CharField(max_length=2048, null=True, blank=True)

    # Metadata (From legacy)
    title = models.CharField(max_length=2048, null=True)
    author = models.CharField(max_length=2048, null=True)
    publisher = models.CharField(max_length=2048, null=True)
    isbn = models.CharField(max_length=255, null=True)
    doi = models.CharField(max_length=255, null=True)

    # Statistics (Legacy: pagecount, pages_x_students, etc)
    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)
    count_students_registered = models.IntegerField(default=0)

    # Relations
    faculty = models.ForeignKey(Organization, null=True, on_delete=models.SET_NULL)
    courses = models.ManyToManyField('Course', related_name='items')

    # Workflow Extras (Legacy: last_canvas_check, file_exists)
    file_exists = models.BooleanField(null=True, default=None)
    last_canvas_check = models.DateTimeField(null=True)
    canvas_course_id = models.BigIntegerField(null=True, db_index=True)

    # ML V2 Fields (New)
    v2_predicted_classification = models.CharField(choices=ClassificationV2.choices, null=True)
    v2_prediction_confidence = models.FloatField(default=0.0)

    class Meta:
        indexes = [
            models.Index(fields=['workflow_status']),
            models.Index(fields=['filehash']),
        ]
```

### 2.4 Document Models (`apps.documents.models`)
We must port `PDFCanvasMetadata` faithfully, as it determines lock/unlock logic.

```python
class PDF(TimestampedModel):
    # Links to Copyright Item
    item = models.OneToOneField('core.CopyrightItem', related_name='pdf', on_delete=models.CASCADE)

    filename = models.CharField(max_length=2048, null=True)
    current_file_name = models.CharField(max_length=2048) # Disk location

    # Extraction status
    extraction_successful = models.BooleanField(default=False)
    extracted_text_content = models.TextField(null=True) # Flattening PDFText relation for simplicity

    def get_absolute_path(self):
        return f"/app/documents/downloads/{self.current_file_name}"

class PDFCanvasMetadata(TimestampedModel):
    pdf = models.OneToOneField(PDF, related_name='canvas_meta', on_delete=models.CASCADE)
    uuid = models.CharField(max_length=255)
    size = models.BigIntegerField()
    locked = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    unlock_at = models.DateTimeField(null=True)
```

---

## ⚡ Phase 3: Data Ingestion Pipeline

### 3.1 Task (`apps.ingest.tasks`)
We use Polars to read raw Excel. Reference `ea-cli/easy_access/sheets/sheet.py` to see how columns were renamed in the legacy system.

```python
from django.tasks import task
from apps.core.models import StagedItem

@task
def ingest_task(file_path):
    import polars as pl
    # Read
    df = pl.read_excel(file_path)
    # Convert dates/ints (Polars is strict, check types)
    # Bulk insert
    dicts = df.to_dicts()
    StagedItem.objects.bulk_create(
        [StagedItem(source_file=file_path, payload=d) for d in dicts]
    )
    # Trigger Enrichment
```

### 3.2 Legacy Migration
1.  **Export V1:** Use legacy codebase to dump `copyright_data` table to `migration_dump.csv`.
2.  **Import V2:** The Watchdog picks up the file.
3.  **Migration Script:** Write a Django Command that reads `StagedItem`, validates against `CopyrightItem` fields (mapping `classification` -> `v1_manual_classification`), and inserts.

---

## 🖥️ Phase 4: HTMX Dashboard
**Reference:** `ea-cli/dashboard/dash.py` (Visuals) and `data.py` (Filtering).

### 4.1 Filter Implementation (`apps.dashboard.views`)
Reimplement filters for `Faculty`, `Status` (Workflow), and `Year` (Period).

```python
def grid_partial(request):
    items = CopyrightItem.objects.select_related('pdf').all()

    # Status Filter
    if status := request.GET.get('status'):
        items = items.filter(workflow_status=status)

    # Full Text Search (Postgres)
    if q := request.GET.get('q'):
        items = items.filter(title__icontains=q)

    return render(request, "_grid.html", {"items": items[:100]})
```

---

## 🧠 Phase 5: Intelligence & Automation
**Goal:** Automate V2 Classification.

### 5.1 Hard Rules (`apps.classification.pipeline.rules`)
Reference `ea-cli/easy_access/merge_rules.py`. Convert hardcoded logic into Policy Classes.

```python
class OwnWorkRule:
    """Checks fuzzy match between Author and Course Teacher"""
    def check(self, item):
        # Implementation of Levenshtein logic from ea-cli/easy_access/utils.py
        pass
```

### 5.2 CatBoost Integration (`apps.classification.ml`)
Create the training/inference loop using the fields identified in the Models phase (e.g., `pagecount`, `filetype`).

---

## 🔬 Phase 6: The "AnyWidget" Notebook Tool
**Goal:** Advanced verification tool replacing the legacy "Dashboard Edit Mode".

### 6.1 Logic (`apps.classification.widget.backend`)
Use `anywidget` to provide a split-pane view in Marimo/Jupyter.
**Feature:** Ensure the widget can update `workflow_status` from 'ToDo' to 'Done'.

### 6.2 Visualization
In the legacy tool, PDFs were served via static files. In the widget, use `active_pdf_data = traitlets.Unicode()` to stream base64 content so it works in remote notebooks (Hubs/Docker).

---

## ✅ Implementation Checklist

1.  **Repo Setup:** Git Submodule for `ea-cli`. Docker compose up.
2.  **Schema Check:** Compare `src/apps/core/models.py` line-by-line with `ea-cli/easy_access/db/models.py`.
3.  **Migrate:** `manage.py makemigrations` -> `manage.py migrate`.
4.  **Ingest Test:** Drop a sample excel file. Verify `StagedItem` has JSON data.
5.  **View Construction:** Build the HTMX grid. Ensure PDF icons link to valid routes.
6.  **Notebook Test:** Launch Marimo (`marimo edit`), import `CopyrightLabeler`, and verify 2-way sync with Database.
