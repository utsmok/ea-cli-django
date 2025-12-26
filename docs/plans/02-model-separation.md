# Task 2: Model Separation (QlikItem Creation)

## Overview

Create a separate `QlikItem` model to serve as a read-only mirror of Qlik/CRC source data, separating system-managed fields from human-managed fields in `CopyrightItem`.

**Current Status:** ✅ **COMPLETE** (Implemented as Mirror Table)

**Rationale:**
- **Clear data lineage:** Distinguish between source data and user edits
- **Prevent accidental modification:** Qlik fields are read-only by design
- **Better audit trail:** Explicit tracking of data provenance
- **Cleaner migrations:** Source data structure changes won't affect human fields

## Architecture

```
┌─────────────────┐
│   QlikItem      │ (Read-only mirror of Qlik/CRC)
│  - system fields│
│  - metadata     │
└────────┬────────┘
         │ OneToOne
         │
┌────────▼────────┐
│ CopyrightItem   │ (Human-managed workflow data)
│  - workflow     │
│  - classification│
│  - remarks      │
└─────────────────┘
```

## Implementation Steps

### Step 1: Create QlikItem Model

**File:** `src/apps/core/models.py`

Add the `QlikItem` model (before `CopyrightItem`):

```python
class QlikItem(TimestampedModel):
    """
    Read-only mirror of Qlik/CRC source data.
    Represents system-managed fields from the copyright database.

    This model should NEVER be directly modified by users.
    All updates come through the ingestion pipeline.
    """

    # Primary identifier
    material_id = models.BigIntegerField(primary_key=True)

    # File metadata from Qlik
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    filetype = models.CharField(max_length=50, choices=Filetype.choices)
    url = models.URLField(max_length=2048, null=True, blank=True)

    # CRC extracted metadata
    title = models.CharField(max_length=2048, null=True, blank=True)
    author = models.CharField(max_length=2048, null=True, blank=True)
    publisher = models.CharField(max_length=2048, null=True, blank=True)

    # Course/period information from Qlik
    period = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=2048, null=True, blank=True)
    course_code = models.CharField(max_length=2048, null=True, blank=True)
    course_name = models.CharField(max_length=2048, null=True, blank=True)

    # Status from source
    status = models.CharField(max_length=50, choices=Status.choices)

    # Identifiers
    isbn = models.CharField(max_length=255, null=True, blank=True)
    doi = models.CharField(max_length=255, null=True, blank=True)

    # Ownership
    owner = models.CharField(max_length=2048, null=True, blank=True)
    in_collection = models.BooleanField(null=True, blank=True)

    # Metrics from Qlik
    picturecount = models.IntegerField(default=0)
    reliability = models.IntegerField(default=0)
    pages_x_students = models.IntegerField(default=0)
    count_students_registered = models.IntegerField(default=0)
    retrieved_from_copyright_on = models.DateTimeField(null=True, blank=True)

    # Content metrics
    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)

    # Canvas metadata
    canvas_course_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    # ML classification (system-generated)
    ml_classification = models.CharField(
        max_length=100,
        choices=Classification.choices,
        default=Classification.NIET_GEANALYSEERD,
        null=True,
        blank=True,
    )

    # Ingestion tracking
    last_qlik_update = models.DateTimeField(auto_now=True)
    qlik_source_file = models.CharField(max_length=512, null=True, blank=True)

    class Meta:
        db_table = "qlik_items"
        verbose_name = "Qlik Item"
        verbose_name_plural = "Qlik Items"
        ordering = ["-last_qlik_update"]
        indexes = [
            models.Index(fields=["material_id", "last_qlik_update"]),
            models.Index(fields=["filehash"]),
            models.Index(fields=["canvas_course_id"]),
            models.Index(fields=["course_code"]),
        ]

    def __str__(self):
        return f"QlikItem {self.material_id} - {self.filename}"

    @property
    def is_read_only(self):
        """This model should always be read-only."""
        return True
```

### Step 2: Refactor CopyrightItem Model

**File:** `src/apps/core/models.py`

Modify `CopyrightItem` to use OneToOne relationship:

```python
class CopyrightItem(TimestampedModel):
    """
    Human-managed workflow data for copyright items.

    Links to QlikItem (source data) via OneToOne.
    Contains only fields that users/editors modify.
    """

    # Link to source data
    material_id = models.OneToOneField(
        'QlikItem',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='material_id',
        related_name='human_data'
    )

    # Human-managed workflow fields
    workflow_status = models.CharField(
        max_length=50,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.TODO,
        db_index=True
    )
    manual_classification = models.CharField(
        max_length=100,
        choices=Classification.choices,
        null=True,
        blank=True
    )
    v2_manual_classification = models.CharField(
        max_length=100,
        choices=ClassificationV2.choices,
        null=True,
        blank=True,
        db_index=True
    )
    v2_overnamestatus = models.CharField(
        max_length=100,
        choices=OvernameStatus.choices,
        null=True,
        blank=True
    )

    # Manual identifier override
    manual_identifier = models.CharField(max_length=2048, null=True, blank=True)

    # Audit fields
    remarks = models.TextField(null=True, blank=True)
    scope = models.CharField(max_length=50, null=True, blank=True)
    auditor = models.CharField(max_length=2048, null=True, blank=True)
    last_change = models.DateTimeField(null=True, blank=True)

    # Faculty assignment (human-managed override)
    faculty = models.ForeignKey(
        'Faculty',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='copyright_items',
        db_index=True
    )

    # File verification (enrichment result)
    file_exists = models.BooleanField(null=True, blank=True, db_index=True)
    last_canvas_check = models.DateTimeField(null=True, blank=True)

    # Relationships
    courses = models.ManyToManyField('Course', related_name='copyright_items')

    # Enrichment tracking
    enrichment_status = models.CharField(max_length=50, null=True, blank=True)
    last_enrichment_attempt = models.DateTimeField(null=True, blank=True)
    extraction_status = models.CharField(max_length=50, null=True, blank=True)

    # Document link
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='copyright_items'
    )

    class Meta:
        db_table = "copyright_items"
        verbose_name = "Copyright Item"
        verbose_name_plural = "Copyright Items"
        ordering = ["-modified_at"]

    def __str__(self):
        return f"CopyrightItem {self.material_id_id} - {self.get_workflow_status_display()}"

    @property
    def source_data(self):
        """Access QlikItem source data."""
        return self.material_id
```

### Step 3: Create Migration

```bash
# Create migration
uv run python src/manage.py makemigrations core --name create_qlik_item_model
```

**Migration 2: Populate QlikItem from existing CopyrightItem**

**File:** `src/apps/core/migrations/0002_populate_qlik_items.py` (generated)

```python
from django.db import migrations

def populate_qlik_items(apps, schema_editor):
    """Copy Qlik fields from CopyrightItem to QlikItem."""
    QlikItem = apps.get_model('core', 'QlikItem')
    CopyrightItem = apps.get_model('core', 'CopyrightItem')

    # Get all existing CopyrightItems
    for item in CopyrightItem.objects.all():
        # Create corresponding QlikItem
        QlikItem.objects.create(
            material_id=item.material_id,
            filename=item.filename,
            filehash=item.filehash,
            filetype=item.filetype,
            url=item.url,
            title=item.title,
            author=item.author,
            publisher=item.publisher,
            period=item.period,
            department=item.department,
            course_code=item.course_code,
            course_name=item.course_name,
            status=item.status,
            isbn=item.isbn,
            doi=item.doi,
            owner=item.owner,
            in_collection=item.in_collection,
            picturecount=item.picturecount,
            reliability=item.reliability,
            pages_x_students=item.pages_x_students,
            count_students_registered=item.count_students_registered,
            retrieved_from_copyright_on=item.retrieved_from_copyright_on,
            pagecount=item.pagecount,
            wordcount=item.wordcount,
            canvas_course_id=item.canvas_course_id,
            ml_classification=item.ml_classification,
        )

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
        ('core', '0002_create_qlik_item_model'),
    ]

    operations = [
        migrations.RunPython(populate_qlik_items, migrations.RunPython.noop),
    ]
```

**Migration 3: Refactor CopyrightItem to use OneToOne**

This is complex - requires careful data preservation. Strategy:
1. Create new temporary columns
2. Migrate data to new structure
3. Drop old columns

**Note:** Consider using Django's `SeparateDatabaseAndState` for complex migrations.

### Step 4: Update Ingestion Logic

**File:** `src/apps/ingest/services/qlik_processor.py`

```python
async def process_qlik_entry(entry: QlikEntry, batch: IngestionBatch):
    """Process a staged Qlik entry."""

    # Update or create QlikItem (source of truth)
    qlik_item, created = await sync_to_async(QlikItem.objects.update_or_create)(
        material_id=entry.material_id,
        defaults={
            'filename': entry.filename,
            'filehash': entry.filehash,
            'filetype': entry.filetype,
            'url': entry.url,
            'title': entry.title,
            'author': entry.author,
            'publisher': entry.publisher,
            'period': entry.period,
            'department': entry.department,
            'course_code': entry.course_code,
            'course_name': entry.course_name,
            'status': entry.status,
            'isbn': entry.isbn,
            'doi': entry.doi,
            'owner': entry.owner,
            'in_collection': entry.in_collection,
            'picturecount': entry.picturecount,
            'reliability': entry.reliability,
            'pages_x_students': entry.pages_x_students,
            'count_students_registered': entry.count_students_registered,
            'pagecount': entry.pagecount,
            'wordcount': entry.wordcount,
            'canvas_course_id': entry.canvas_course_id,
            'ml_classification': entry.ml_classification,
        }
    )

    # Ensure CopyrightItem exists for human management
    copyright_item, created = await sync_to_async(CopyrightItem.objects.get_or_create)(
        material_id=qlik_item,
        defaults={
            'workflow_status': WorkflowStatus.TODO,
            'enrichment_status': 'pending',
        }
    )

    return copyright_item
```

### Step 5: Update Query Service

**File:** `src/apps/dashboard/services/query_service.py`

```python
class ItemQueryService:
    def __init__(self):
        # Join QlikItem for source data
        self.base_qs = CopyrightItem.objects.select_related(
            "faculty",
            "document",
            "material_id",  # Access QlikItem via OneToOne
        )

    def get_filtered_queryset(self, filters: ItemQueryFilter):
        qs = self.base_qs.all()

        # Search across both human and Qlik fields
        if filters.search_query:
            qs = qs.filter(
                Q(material_id__title__icontains=search_term) |
                Q(material_id__filename__icontains=search_term) |
                Q(material_id__author__icontains=search_term) |
                Q(remarks__icontains=search_term)
            )

        # Filter by Qlik fields
        if filters.period:
            qs = qs.filter(material_id__period=filters.period)

        # Filter by human fields
        if filters.status:
            qs = qs.filter(workflow_status=filters.status)

        return qs
```

### Step 6: Update Templates

**File:** `src/templates/dashboard/_table_row.html`

```django
<tr class="hover:bg-primary/5 transition-colors cursor-pointer"
    hx-get="{% url 'dashboard:detail_panel' item.material_id_id %}"
    hx-target="#detail-panel">
  <td>{{ item.material_id_id }}</td>
  <td>{{ item.material_id.filename }}</td>
  <td>{{ item.material_id.title }}</td>
  <td>{% partial status_badge status_type=item.workflow_status %}</td>
  <td>{{ item.faculty }}</td>
</tr>
```

**Note:** `item.material_id` is now the QlikItem, so access fields like:
- `item.material_id.filename` (Qlik field)
- `item.workflow_status` (Human field)
- `item.material_id_id` (The actual ID)

## Data Migration Checklist

### Pre-Migration
- [ ] Backup database
- [ ] Run on staging environment first
- [ ] Count records: `CopyrightItem.objects.count()`
- [ ] Document current schema

### Migration Steps
- [ ] Create QlikItem model
- [ ] Run makemigrations
- [ ] Create data migration
- [ ] Test data migration on copy of production
- [ ] Run migration on staging
- [ ] Verify data integrity

### Post-Migration Verification
- [ ] All QlikItems created: `QlikItem.objects.count() == old_count`
- [ ] All CopyrightItems linked: Check orphaned records
- [ ] Query results match pre-migration
- [ ] Ingestion pipeline works
- [ ] UI displays correctly

## Testing

### Unit Tests

**File:** `src/apps/core/tests/test_qlik_item_model.py` (NEW)

```python
import pytest
from apps.core.models import QlikItem, CopyrightItem, WorkflowStatus

@pytest.mark.django_db
class TestQlikItemModel:
    def test_qlik_item_creation(self):
        """Test QlikItem can be created."""
        qlik_item = QlikItem.objects.create(
            material_id=12345,
            filename="test.pdf",
            filetype="pdf",
            status="Published"
        )
        assert qlik_item.material_id == 12345
        assert qlik_item.is_read_only is True

    def test_copyright_item_links_to_qlik(self):
        """Test CopyrightItem links to QlikItem."""
        qlik_item = QlikItem.objects.create(
            material_id=12345,
            filename="test.pdf",
            filetype="pdf",
            status="Published"
        )
        copyright_item = CopyrightItem.objects.create(
            material_id=qlik_item,
            workflow_status=WorkflowStatus.TODO
        )
        assert copyright_item.material_id == qlik_item
        assert copyright_item.source_data == qlik_item
```

## Rollback Strategy

### If Migration Fails
```sql
-- Drop new tables
DROP TABLE IF EXISTS qlik_items CASCADE;

-- Restore from backup
pg_restore -d copyright_db backup.sql
```

### If Issues Post-Migration
- Keep migration files for reverting
- Create reverse migration functions
- Have feature flag to use old vs new model structure

## Success Criteria

- [ ] QlikItem model created
- [ ] All existing data migrated to QlikItem
- [ ] CopyrightItem refactored to use OneToOne
- [ ] Ingestion pipeline updated
- [ ] Query service updated to join models
- [ ] Templates updated to access fields correctly
- [ ] All tests pass
- [ ] Manual testing confirms data integrity
- [ ] Performance is not degraded

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data migration failure | HIGH | Test on staging, backup DB |
| Performance degradation | MED | Add proper indexes, monitor queries |
| Breaking existing code | HIGH | Comprehensive testing, gradual rollout |
| Orphaned records | MED | Add validation checks |
| Complex rollback | HIGH | Keep detailed migration files |

---

**Next Task:** [Task 3: Settings System](03-settings-system.md)
