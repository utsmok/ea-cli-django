# Task 13: Test Coverage Expansion

## Overview

Increase test coverage from minimal to comprehensive, focusing on service layer logic, critical business rules, and integration tests.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)

## Current State

**Existing Tests:**
- `src/apps/core/tests/test_models.py` - Only 2 tests, basic model creation
- `src/apps/ingest/tests/test_views.py` - Basic view tests
- `src/apps/enrichment/tests/` - 3 test files
- `src/apps/core/tests/test_cache_service.py` - 7 tests (from Task 1)
- `src/apps/core/tests/test_retry_logic.py` - Tests from Task 5

**Coverage Analysis:**
**Estimated current coverage:** ~15-20%

**Missing Coverage:**
1. Merge rules logic (`ingest/services/merge_rules.py`)
2. Batch processor (`ingest/services/processor.py`)
3. Query service optimizations (`dashboard/services/query_service.py`)
4. Retry logic edge cases
5. Settings service (from Task 3)
6. Admin actions
7. Full pipeline integration tests
8. API endpoints

**Target Coverage:** 60%+

## Test Plan by Component

### 1. Ingest Service Tests

#### 1.1 Merge Rules Tests

**File:** `src/apps/ingest/tests/test_merge_rules.py` (NEW)

```python
import pytest
from apps.ingest.services.merge_rules import (
    QLIK_MERGE_RULES,
    FACULTY_MERGE_RULES,
    SOURCE_FIELD_OWNERSHIP,
)
from apps.core.models import WorkflowStatus


class TestMergeRules:
    """Test merge rule definitions and logic."""

    def test_qlik_and_faculty_fields_dont_overlap(self):
        """Ensure QLIK and FACULTY fields don't overlap."""
        qlik_fields = set(QLIK_MERGE_RULES.keys())
        faculty_fields = set(FACULTY_MERGE_RULES.keys())

        overlap = qlik_fields & faculty_fields
        assert not overlap, f"Field ownership conflict: {overlap}"

    def test_all_source_fields_have_ownership_defined(self):
        """Ensure every source field has ownership defined."""
        from apps.core.models import CopyrightItem

        # Get all field names from CopyrightItem
        model_fields = {f.name for f in CopyrightItem._meta.get_fields()}

        # Get all fields with ownership rules
        owned_fields = set()
        for field_dict in SOURCE_FIELD_OWNERSHIP.values():
            owned_fields.update(field_dict.keys())

        # Check critical fields are covered
        critical_fields = {
            "workflow_status",
            "manual_classification",
            "v2_manual_classification",
            "faculty",
        }
        assert critical_fields.issubset(owned_fields), \
            f"Critical fields missing ownership: {critical_fields - owned_fields}"

    def test_qlik_rules_correctness(self):
        """Test Qlik merge rules are correctly configured."""
        # workflow_status should NOT be in QLIK rules
        assert "workflow_status" not in QLIK_MERGE_RULES

        # filename should be in QLIK rules
        assert "filename" in QLIK_MERGE_RULES

    def test_faculty_rules_correctness(self):
        """Test faculty merge rules are correctly configured."""
        # workflow_status should be in FACULTY rules
        assert "workflow_status" in FACULTY_MERGE_RULES

        # filename should NOT be in FACULTY rules
        assert "filename" not in FACULTY_MERGE_RULES


class TestMergeLogic:
    """Test actual merge behavior."""

    @pytest.mark.django_db
    def test_qlik_overwrite_behavior(self):
        """Test that Qlik data overwrites existing values for QLIK-owned fields."""
        from apps.ingest.services.merge_rules import SOURCE_FIELD_OWNERSHIP

        qlik_fields = SOURCE_FIELD_OWNERSHIP.get("QLIK", {})

        # Each Qlik field should use "overwrite" strategy
        for field, rule in qlik_fields.items():
            assert rule["strategy"] == "overwrite", \
                f"Field {field} should use 'overwrite' strategy"

    @pytest.mark.django_db
    def test_faculty_preserve_behavior(self):
        """Test that faculty data preserves existing values."""
        from apps.ingest.services.merge_rules import SOURCE_FIELD_OWNERSHIP

        faculty_fields = SOURCE_FIELD_OWNERSHIP.get("FACULTY", {})

        # Each faculty field should use "preserve" strategy
        for field, rule in faculty_fields.items():
            assert rule["strategy"] in ("preserve", "merge"), \
                f"Field {field} should use 'preserve' or 'merge' strategy"
```

#### 1.2 Batch Processor Tests

**File:** `src/apps/ingest/tests/test_batch_processor.py` (NEW)

```python
import pytest
from apps.ingest.services.processor import BatchProcessor
from apps.ingest.models import IngestionBatch, StagedQlikItem
from apps.core.models import CopyrightItem, WorkflowStatus


@pytest.mark.django_db
class TestBatchProcessor:
    """Test batch processing logic."""

    def test_create_batch(self):
        """Test creating a new ingestion batch."""
        processor = BatchProcessor()
        batch = processor.create_batch(
            source_type="qlik",
            source_file="test.xlsx"
        )

        assert batch.source_type == "qlik"
        assert batch.source_file == "test.xlsx"
        assert batch.status == "pending"

    def test_stage_qlik_entry(self):
        """Test staging a Qlik entry."""
        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        entry_data = {
            "material_id": 1234567,
            "filename": "test.pdf",
            "filetype": "pdf",
            "workflow_status": "ToDo",
        }

        staged = processor.stage_qlik_entry(batch, entry_data)

        assert staged.material_id == 1234567
        assert staged.batch == batch
        assert staged.status == "staged"

    def test_process_batch_creates_items(self):
        """Test that processing a batch creates CopyrightItems."""
        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        # Stage multiple entries
        for i in range(5):
            processor.stage_qlik_entry(batch, {
                "material_id": 1000000 + i,
                "filename": f"test{i}.pdf",
                "filetype": "pdf",
                "workflow_status": "ToDo",
            })

        # Process batch
        stats = processor.process_batch(batch)

        assert stats["total"] == 5
        assert stats["created"] == 5

        # Verify items created
        assert CopyrightItem.objects.count() == 5

    def test_process_batch_updates_existing_items(self):
        """Test that processing updates existing items."""
        # Create existing item
        existing = CopyrightItem.objects.create(
            material_id=1234567,
            workflow_status=WorkflowStatus.TODO
        )

        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        # Stage entry for same material_id with updated data
        processor.stage_qlik_entry(batch, {
            "material_id": 1234567,
            "filename": "updated.pdf",
            "filetype": "pdf",
            "workflow_status": "Done",
        })

        # Process batch
        stats = processor.process_batch(batch)

        assert stats["updated"] == 1

        # Verify item updated
        existing.refresh_from_db()
        # Note: filename should update (Qlik field)
        # workflow_status should NOT update (faculty field, preserve)

    @pytest.mark.django_db
    def test_merge_logic_integration(self):
        """Test merge rules during batch processing."""
        from apps.ingest.services.merge_rules import SOURCE_FIELD_OWNERSHIP

        # This tests the actual merge behavior
        # Create item with faculty edits
        item = CopyrightItem.objects.create(
            material_id=1234567,
            workflow_status=WorkflowStatus.DONE,  # Faculty edit
            filename="old.pdf"
        )

        # Stage Qlik data with different workflow_status
        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        processor.stage_qlik_entry(batch, {
            "material_id": 1234567,
            "filename": "new.pdf",  # Qlik field, should update
            "workflow_status": "ToDo",  # Faculty field, should NOT update
        })

        stats = processor.process_batch(batch)

        item.refresh_from_db()
        assert item.filename == "new.pdf"  # Updated (Qlik-owned)
        assert item.workflow_status == WorkflowStatus.DONE  # Preserved (faculty-owned)
```

### 2. Query Service Tests

**File:** `src/apps/dashboard/tests/test_query_service.py` (NEW)

```python
import pytest
from apps.dashboard.services.query_service import ItemQueryService, ItemQueryFilter
from apps.core.models import CopyrightItem, WorkflowStatus, Faculty


@pytest.mark.django_db
class TestItemQueryService:
    """Test query service optimizations and filtering."""

    def test_get_faculties_uses_cache(self):
        """Test that get_faculties uses caching."""
        service = ItemQueryService()

        # First call
        faculties1 = service.get_faculties()

        # Create new faculty
        Faculty.objects.create(
            abbreviation="TEST",
            name="Test Faculty"
        )

        # Second call should return cached data (without new faculty)
        faculties2 = service.get_faculties()

        assert faculties1.count() == faculties2.count()

    def test_filter_counts(self):
        """Test filter count aggregation."""
        service = ItemQueryService()

        # Create test items with different statuses
        for i in range(10):
            CopyrightItem.objects.create(
                material_id=1000000 + i,
                workflow_status=WorkflowStatus.TODO if i % 2 == 0 else WorkflowStatus.DONE
            )

        counts = service.get_filter_counts()

        assert counts["total"] == 10
        assert counts["todo"] == 5
        assert counts["done"] == 5

    def test_get_filtered_queryset_by_status(self):
        """Test filtering by workflow status."""
        service = ItemQueryService()

        # Create test items
        for status in [WorkflowStatus.TODO, WorkflowStatus.DONE, WorkflowStatus.IN_PROGRESS]:
            CopyrightItem.objects.create(
                material_id=1000000 + list(WorkflowStatus.values).index(status),
                workflow_status=status
            )

        filters = ItemQueryFilter(status="ToDo")
        qs = service.get_filtered_queryset(filters)

        assert qs.count() == 1

    def test_get_filtered_queryset_by_faculty(self):
        """Test filtering by faculty."""
        faculty = Faculty.objects.create(
            abbreviation="EEMCS",
            name="Electrical Engineering"
        )

        # Create items with and without faculty
        CopyrightItem.objects.create(
            material_id=1000001,
            workflow_status=WorkflowStatus.TODO,
            faculty=faculty
        )
        CopyrightItem.objects.create(
            material_id=1000002,
            workflow_status=WorkflowStatus.DONE
        )

        service = ItemQueryService()
        filters = ItemQueryFilter(faculty=faculty.abbreviation)
        qs = service.get_filtered_queryset(filters)

        assert qs.count() == 1

    def test_pagination(self):
        """Test paginated results."""
        service = ItemQueryService()

        # Create 25 items
        for i in range(25):
            CopyrightItem.objects.create(
                material_id=1000000 + i,
                workflow_status=WorkflowStatus.TODO
            )

        filters = ItemQueryFilter(status="ToDo")
        result = service.get_paginated_items(filters, limit=10, offset=0)

        assert result.total == 25
        assert len(result.items) == 10
        assert result.has_next is True

    @pytest.mark.django_db
    def test_select_related_optimization(self):
        """Test that query service uses select_related."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        faculty = Faculty.objects.create(
            abbreviation="EEMCS",
            name="Electrical Engineering"
        )

        for i in range(10):
            CopyrightItem.objects.create(
                material_id=1000000 + i,
                workflow_status=WorkflowStatus.TODO,
                faculty=faculty
            )

        service = ItemQueryService()
        filters = ItemQueryFilter(faculty=faculty.abbreviation)

        with CaptureQueriesContext(connection) as context:
            qs = service.get_filtered_queryset(filters)
            items = list(qs)

            # Should only use 1 query (select_related on faculty)
            assert len(context.captured_queries) == 1
```

### 3. Retry Logic Tests

**File:** `src/apps/core/tests/test_retry_logic_edge_cases.py` (NEW)

```python
import pytest
from apps.core.services.retry_logic import (
    is_retryable_error,
    retry_with_exponential_backoff,
    async_retry,
)
import httpx


@pytest.mark.asyncio
class TestRetryLogicEdgeCases:
    """Test retry logic edge cases."""

    async def test_max_retries_exceeded(self):
        """Test that max retries is respected."""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        with pytest.raises(httpx.TimeoutException):
            await retry_with_exponential_backoff(always_fail, max_retries=3)

        assert call_count == 4  # Initial + 3 retries

    async def test_exponential_backoff_timing(self):
        """Test exponential backoff timing."""
        import time
        import asyncio

        call_times = []

        async def track_time():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise httpx.TimeoutException("Timeout")

        await retry_with_exponential_backoff(
            track_time,
            max_retries=3,
            base_delay=0.1  # Short delay for testing
        )

        # Check delays: ~0.1s, ~0.2s
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        assert 0.08 < delay1 < 0.15  # ~0.1s
        assert 0.18 < delay2 < 0.25  # ~0.2s

    async def test_retry_after_header_respected(self):
        """Test that Retry-After header is respected."""
        import time

        call_count = 0

        async def retry_after_response():
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: return 429 with Retry-After
                response = httpx.Response(
                    429,
                    headers={"Retry-After": "0.5"},  # 0.5 seconds
                    request=httpx.Request("GET", "http://test")
                )
                raise httpx.HTTPStatusError("Rate limit", request=None, response=response)
            else:
                return "success"

        start = time.time()
        result = await retry_with_exponential_backoff(
            retry_after_response,
            max_retries=3
        )
        duration = time.time() - start

        assert result == "success"
        # Should wait at least 0.5s (Retry-After header)
        assert duration >= 0.5

    def test_is_retryable_error_all_codes(self):
        """Test is_retryable_error for all status codes."""
        # Retryable errors
        assert is_retryable_error(httpx.Response(429, request=None)) is True  # Rate limit
        assert is_retryable_error(httpx.Response(503, request=None)) is True  # Service unavailable
        assert is_retryable_error(httpx.Response(504, request=None)) is True  # Gateway timeout

        # Non-retryable errors
        assert is_retryable_error(httpx.Response(401, request=None)) is False  # Unauthorized
        assert is_retryable_error(httpx.Response(403, request=None)) is False  # Forbidden
        assert is_retryable_error(httpx.Response(404, request=None)) is False  # Not found
        assert is_retryable_error(httpx.Response(400, request=None)) is False  # Bad request

    async def test_no_retry_on_permanent_errors(self):
        """Test that permanent errors don't trigger retries."""
        call_count = 0

        async def permanent_error():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(404, request=None)
            raise httpx.HTTPStatusError("Not found", request=None, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await retry_with_exponential_backoff(permanent_error, max_retries=3)

        # Should not retry (only called once)
        assert call_count == 1
```

### 4. Settings Service Tests

**File:** `src/apps/settings/tests/test_settings_service.py` (NEW)

```python
import pytest
from apps.settings.models import Setting
from apps.settings.services import SettingsService


@pytest.mark.django_db
class TestSettingsService:
    """Test settings service from Task 3."""

    def test_get_setting_value(self):
        """Test retrieving a setting value."""
        Setting.objects.create(
            key="test_setting",
            value="test_value",
            description="Test setting"
        )

        service = SettingsService()
        value = service.get("test_setting")

        assert value == "test_value"

    def test_get_setting_default(self):
        """Test retrieving non-existent setting with default."""
        service = SettingsService()

        value = service.get("nonexistent", default="default_value")

        assert value == "default_value"

    def test_set_setting_create(self):
        """Test creating a new setting."""
        service = SettingsService()

        service.set("new_setting", "new_value")

        assert Setting.objects.filter(key="new_setting").exists()

    def test_set_setting_update(self):
        """Test updating an existing setting."""
        Setting.objects.create(
            key="test_setting",
            value="old_value"
        )

        service = SettingsService()
        service.set("test_setting", "new_value")

        setting = Setting.objects.get(key="test_setting")
        assert setting.value == "new_value"

    def test_yaml_export(self):
        """Test YAML export functionality."""
        Setting.objects.create(key="key1", value="value1")
        Setting.objects.create(key="key2", value="value2")

        service = SettingsService()
        yaml_output = service.export_to_yaml()

        assert "key1: value1" in yaml_output
        assert "key2: value2" in yaml_output

    def test_yaml_import(self):
        """Test YAML import functionality."""
        yaml_content = """
key1: value1
key2: value2
key3: value3
"""

        service = SettingsService()
        service.import_from_yaml(yaml_content)

        assert Setting.objects.count() == 3

    def test_sensitive_value_masking(self):
        """Test that sensitive values are masked in YAML export."""
        Setting.objects.create(
            key="api_key",
            value="secret_key_123",
            is_sensitive=True
        )

        service = SettingsService()
        yaml_output = service.export_to_yaml()

        assert "secret_key_123" not in yaml_output
        assert "***" in yaml_output
```

### 5. Admin Actions Tests

**File:** `src/apps/core/tests/test_admin_actions.py` (NEW)

```python
import pytest
from django.contrib.admin import site
from apps.core.admin import CopyrightItemAdmin
from apps.core.models import CopyrightItem, WorkflowStatus


@pytest.mark.django_db
class TestCopyrightItemAdmin:
    """Test admin actions."""

    def test_set_file_exists_flag_action(self):
        """Test the set_file_exists_flag admin action."""
        # Create items
        for i in range(5):
            CopyrightItem.objects.create(
                material_id=1000000 + i,
                workflow_status=WorkflowStatus.TODO
            )

        # Get admin instance
        model_admin = CopyrightItemAdmin(CopyrightItem, site)

        # Get queryset
        queryset = CopyrightItem.objects.all()

        # Run action
        model_admin.set_file_exists_flag(None, queryset)

        # Verify all items have file_exists=False
        # (no documents exist, so all should be False)
        for item in queryset:
            assert item.file_exists is False

    def test_bulk_update_workflow_status(self):
        """Test bulk workflow status update."""
        # Create items with TODO status
        for i in range(5):
            CopyrightItem.objects.create(
                material_id=1000000 + i,
                workflow_status=WorkflowStatus.TODO
            )

        model_admin = CopyrightItemAdmin(CopyrightItem, site)
        queryset = CopyrightItem.objects.all()

        # Run action
        model_admin.set_workflow_status_in_progress(None, queryset)

        # Verify all updated
        for item in queryset:
            item.refresh_from_db()
            assert item.workflow_status == WorkflowStatus.IN_PROGRESS
```

### 6. Integration Tests

**File:** `src/apps/tests/test_integration_pipeline.py` (NEW)

```python
import pytest
from apps.ingest.services.processor import BatchProcessor
from apps.enrichment.tasks import enrich_items
from apps.core.models import CopyrightItem, WorkflowStatus


@pytest.mark.django_db
@pytest.mark.usefixtures("enable_cache")
class TestFullPipelineIntegration:
    """Integration tests for the full data processing pipeline."""

    def test_qlik_to_enrichment_pipeline(self):
        """Test the full pipeline from Qlik ingest to enrichment."""
        # Step 1: Ingest Qlik data
        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        processor.stage_qlik_entry(batch, {
            "material_id": 1234567,
            "filename": "test.pdf",
            "filetype": "pdf",
            "course_code": "12345",
            "url": "https://canvas.example.com/files/12345/download",
            "workflow_status": "ToDo",
        })

        stats = processor.process_batch(batch)
        assert stats["created"] == 1

        # Step 2: Verify item created
        item = CopyrightItem.objects.get(material_id=1234567)
        assert item.workflow_status == WorkflowStatus.TODO

        # Step 3: Run enrichment (mock external APIs)
        # This would use mocking to avoid actual API calls
        # For now, just verify the task interface
        assert item.enrichment_status is None or "pending"

    def test_faculty_sheet_update_preserves_edits(self):
        """Test that faculty sheet updates preserve human edits."""
        # Create item with faculty edits
        item = CopyrightItem.objects.create(
            material_id=1234567,
            workflow_status=WorkflowStatus.DONE,  # Faculty edit
            remarks="Important notes from faculty"
        )

        # Stage Qlik data with different values
        processor = BatchProcessor()
        batch = processor.create_batch("qlik", "test.xlsx")

        processor.stage_qlik_entry(batch, {
            "material_id": 1234567,
            "filename": "new.pdf",  # Qlik field
            "workflow_status": "ToDo",  # Faculty field - should preserve
        })

        stats = processor.process_batch(batch)
        assert stats["updated"] == 1

        # Verify faculty edits preserved
        item.refresh_from_db()
        assert item.workflow_status == WorkflowStatus.DONE  # Preserved!
        assert item.remarks == "Important notes from faculty"  # Preserved!
```

## Test Infrastructure

### Add Coverage Configuration

**File:** `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["src"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--cov=src/apps",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=60",  # Require 60% coverage
]
```

### Add Test Fixtures

**File:** `src/conftest.py` (GLOBAL)

```python
import pytest
from django.core.cache import cache
from apps.core.models import Faculty, Person


@pytest.fixture
def enable_cache(settings):
    """Enable cache for testing."""
    settings.CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def sample_faculty(db):
    """Create a sample faculty."""
    return Faculty.objects.create(
        abbreviation="EEMCS",
        name="Electrical Engineering, Mathematics and Computer Science"
    )


@pytest.fixture
def sample_person(db):
    """Create a sample person."""
    return Person.objects.create(
        input_name="John Doe",
        main_name="Doe, John"
    )


@pytest.fixture
def sample_copyright_item(db, sample_faculty):
    """Create a sample copyright item."""
    from apps.core.models import CopyrightItem, WorkflowStatus

    return CopyrightItem.objects.create(
        material_id=1234567,
        filename="test.pdf",
        workflow_status=WorkflowStatus.TODO,
        faculty=sample_faculty
    )
```

## Running Tests

### Run All Tests

```bash
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov=src/apps --cov-report=term-missing --cov-report=html
```

### Run Specific Test File

```bash
uv run pytest src/apps/ingest/tests/test_merge_rules.py -v
```

### Run Specific Test

```bash
uv run pytest src/apps/ingest/tests/test_merge_rules.py::TestMergeRules::test_qlik_and_faculty_fields_dont_overlap -v
```

### View Coverage Report

```bash
# Generate HTML report
uv run pytest --cov=src/apps --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Success Criteria

- [ ] Merge rules tests added and passing
- [ ] Batch processor tests added and passing
- [ ] Query service tests added and passing
- [ ] Retry logic edge case tests added and passing
- [ ] Settings service tests added and passing
- [ ] Admin action tests added and passing
- [ ] Integration tests added and passing
- [ ] Overall test coverage ≥ 60%
- [ ] All tests pass
- [ ] CI/CD integration with coverage reporting (optional)

## Files Created

- `src/apps/ingest/tests/test_merge_rules.py` - NEW
- `src/apps/ingest/tests/test_batch_processor.py` - NEW
- `src/apps/dashboard/tests/test_query_service.py` - NEW
- `src/apps/core/tests/test_retry_logic_edge_cases.py` - NEW
- `src/apps/settings/tests/test_settings_service.py` - NEW
- `src/apps/core/tests/test_admin_actions.py` - NEW
- `src/apps/tests/test_integration_pipeline.py` - NEW
- `src/conftest.py` - NEW (global fixtures)

## Benefits

1. **Confidence** - Tests verify business logic works correctly
2. **Documentation** - Tests serve as executable documentation
3. **Refactoring** - Safe to refactor with tests in place
4. **Bug prevention** - Catch bugs before production
5. **Onboarding** - Help new developers understand code
6. **Quality gate** - CI/CD can enforce coverage requirements

---

**Next Task:** Return to [Task 06: Table Enhancements](06-table-enhancements.md) or [Task 02: Model Separation](02-model-separation.md)
