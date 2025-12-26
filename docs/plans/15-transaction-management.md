# Task 15: Transaction Management & Data Integrity

## Overview

Add proper transaction wrapping to multi-step database operations to prevent partial updates and data inconsistency.

**Current Status:** ✅ **COMPLETE**
**Priority:** **HIGH** (Fix Soon)

## The Problem

Multi-step database operations throughout the codebase lack transaction boundaries. If any step fails midway, the database can be left in an inconsistent state:

**Example from PDF download:**
```python
@sync_to_async
def create_or_link_document():
    # Step 1: Create/get Document
    doc, created = Document.objects.get_or_create(...)

    # Step 2: Save file (I/O operation!)
    if created:
        doc.file.save(filepath.name, ContentFile(filepath.read_bytes()))

    # Step 3: Update CopyrightItem
    item.document = doc
    item.save()  # ❌ If this fails, Document created but not linked
```

If step 3 fails, we have an orphaned Document record and the file was saved but not linked.

## Locations Requiring Transactions

### 1. PDF Download Service

**File:** `src/apps/documents/services/download.py:219-246`

**Current Code:**
```python
@sync_to_async
def create_or_link_document():
    doc, created = Document.objects.get_or_create(
        filehash=fhash,
        defaults={...}
    )
    if created:
        doc.file.save(...)
        await doc.asave()
    item.document = doc
    item.filehash = fhash
    await item.asave(update_fields=["document", "filehash"])
```

**Issue:** No atomic wrapper - if linking fails, Document is orphaned.

### 2. Ingestion Batch Processing

**File:** `src/apps/ingest/services/processor.py`

Batch processing creates multiple CopyrightItems in a loop without transaction safety.

### 3. Faculty Sheet Import

**File:** `src/apps/ingest/services/faculty_processor.py`

Updates multiple items with faculty edits - if one fails, partial updates applied.

## Implementation Strategy

### Option 1: Use Django's `transaction.atomic()` Decorator

For sync functions:
```python
from django.db import transaction

@transaction.atomic
def create_or_link_document_sync(item_data, metadata, fhash, filepath, item):
    doc, created = Document.objects.get_or_create(...)
    if created:
        doc.file.save(...)
    item.document = doc
    item.filehash = fhash
    item.save(update_fields=["document", "filehash"])
    # All or nothing - if any exception, everything rolled back
```

For async functions:
```python
from django.db import transaction
from asgiref.sync import sync_to_async

async def create_or_link_document_async(item_data, metadata, fhash, filepath, item):
    return await sync_to_async(transaction.atomic(create_or_link_document_sync))(
        item_data, metadata, fhash, filepath, item
    )
```

### Option 2: Create Async Transaction Decorator

**File:** `src/apps/core/services/transactions.py` (NEW)

```python
"""
Async transaction management utilities.
"""
from functools import wraps
from django.db import transaction
from asgiref.sync import sync_to_async
import asyncio
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')


def atomic_async(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to make a sync function run within a transaction when called async.

    Usage:
        @atomic_async
        async def create_document(item_data):
            # All DB operations here are atomic
            doc = await Document.objects.aget_or_create(...)
            item.document = doc
            await item.asave()
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Run the sync version in a transaction
        sync_func = transaction.atomic(func)
        return await sync_to_async(sync_func)(*args, **kwargs)
    return wrapper


def atomic_service(func: Callable[P, T]) -> Callable[P, T]:
    """
    Transaction decorator that works for both sync and async functions.

    Automatically detects if function is async and applies appropriate wrapper.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if function is async
        if asyncio.iscoroutinefunction(func):
            # For async functions, run in sync_to_async with atomic
            async def run_in_transaction():
                return await sync_to_async(transaction.atomic(func))(*args, **kwargs)
            return run_in_transaction()
        else:
            # For sync functions, just use atomic
            return transaction.atomic(func)(*args, **kwargs)
    return wrapper


class TransactionalService:
    """
    Base class for services that require transaction management.

    All methods are automatically wrapped in transactions.
    """

    @classmethod
    def transaction_method(cls, func: Callable[P, T]) -> Callable[P, T]:
        """
        Decorator for service methods that should run in a transaction.

        Usage:
            class MyService(TransactionalService):
                @TransactionalService.transaction_method
                async def create_item(self, data):
                    # This runs in a transaction
                    pass
        """
        return atomic_async(func)
```

### Option 3: Context Manager for Complex Operations

```python
from django.db import transaction
from asgiref.sync import sync_to_async

async def complex_operation():
    """Multiple steps in one transaction."""
    def _sync_operation():
        with transaction.atomic():
            # Step 1: Create records
            item = CopyrightItem.objects.create(...)
            # Step 2: Link to other records
            item.faculty = faculty
            item.save()
            # Step 3: Create related records
            Document.objects.create(...)
            # If any exception, everything is rolled back

    return await sync_to_async(_sync_operation)()
```

## Implementation Steps

### Step 1: Create Transaction Utilities

**File:** `src/apps/core/services/transactions.py` (NEW)

Create the transaction decorators and utilities shown in Option 2 above.

### Step 2: Fix PDF Download Service

**File:** `src/apps/documents/services/download.py`

**Current code (lines 219-246):**
```python
@sync_to_async
def create_or_link_document(...):
    # ... non-atomic operations
```

**Fixed code:**
```python
from apps.core.services.transactions import atomic_async

@atomic_async
async def create_or_link_document(
    item_data: Item,
    pdf_metadata_obj: PDFCanvasMetadata,
    fhash: str,
    filepath: Path,
    item: CopyrightItem,
) -> Document:
    """Create or link a Document record atomically.

    If any step fails, all database changes are rolled back.
    """

    # Use native async ORM
    doc, created = await Document.objects.aget_or_create(
        filehash=fhash,
        defaults={
            "file": filepath.name,
            "filepath": str(filepath),
            "canvas_metadata": pdf_metadata_obj,
        }
    )

    if created:
        # Save file
        doc.file.save(filepath.name, ContentFiles(filepath.read_bytes()))
        await doc.asave()

    # Link to copyright item
    item.document = doc
    item.filehash = fhash
    await item.asave(update_fields=["document", "filehash"])

    return doc
```

### Step 3: Fix Batch Processor

**File:** `src/apps/ingest/services/processor.py`

**Add transaction wrapping to batch processing:**

```python
from apps.core.services.transactions import atomic_async
from django.db import transaction

class BatchProcessor:
    @atomic_async
    async def process_batch(self, batch: IngestionBatch) -> dict:
        """Process a batch atomically.

        If any item fails, entire batch is rolled back.
        """
        stats = {"total": 0, "created": 0, "updated": 0, "failed": 0}

        staged_items = await sync_to_async(list)(
            batch.staged_qlik_items.all()
        )

        for staged in staged_items:
            try:
                # Process each item
                item = await self._process_staged_item(staged)
                if item._state.adding:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
            except Exception as e:
                logger.exception(f"Failed to process item {staged.material_id}")
                # Rollback entire batch
                raise

        stats["total"] = len(staged_items)
        return stats
```

**Note:** For large batches, you might want per-item transactions instead:

```python
async def process_batch(self, batch: IngestionBatch) -> dict:
    """Process batch with per-item transactions."""
    stats = {"total": 0, "created": 0, "updated": 0, "failed": 0}

    for staged in await batch.staged_qlik_items.all():
        try:
            # Each item in its own transaction
            async with transaction.atomic():
                item = await self._process_staged_item(staged)
                if item._state.adding:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
        except Exception as e:
            logger.exception(f"Failed to process item {staged.material_id}")
            stats["failed"] += 1
            # Continue with next item

    return stats
```

### Step 4: Fix Faculty Sheet Import

**File:** `src/apps/ingest/services/faculty_processor.py`

```python
from apps.core.services.transactions import atomic_async

@atomic_async
async def apply_faculty_updates(self, batch: IngestionBatch) -> dict:
    """Apply faculty sheet updates atomically."""
    # All updates in one transaction
    # If any update fails, entire batch is rolled back
```

### Step 5: Add Savepoint for Nested Operations

For complex operations that need partial rollback:

```python
from django.db import transaction

async def complex_update():
    """Use savepoints for partial rollback on recoverable errors."""

    def _sync_complex_update():
        with transaction.atomic():
            # Outer transaction

            # Create savepoint
            sid = transaction.savepoint()

            try:
                # Risky operation
                item = CopyrightItem.objects.get(material_id=1234567)
                item.workflow_status = "Done"
                item.save()
            except RecoverableError:
                # Rollback to savepoint, continue
                transaction.savepoint_rollback(sid)
            else:
                # Commit savepoint
                transaction.savepoint_commit(sid)

    return await sync_to_async(_sync_complex_update)()
```

## Testing

### 1. Test Transaction Rollback

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_transaction_rollback_on_failure():
    """Test that failed operations roll back completely."""

    from apps.documents.services.download import create_or_link_document
    from apps.core.models import CopyrightItem, Document
    from pathlib import Path

    # Create item
    item = await CopyrightItem.objects.aget(material_id=1234567)

    # Count documents before
    doc_count_before = await Document.objects.acount()

    # Try to create document with invalid data (should fail)
    with pytest.raises(Exception):
        await create_or_link_document(
            item_data={},
            pdf_metadata_obj=None,  # This should cause failure
            fhash="test123",
            filepath=Path("/nonexistent/file.pdf"),
            item=item
        )

    # Verify no document was created (transaction rolled back)
    doc_count_after = await Document.objects.acount()
    assert doc_count_after == doc_count_before, "Transaction should have rolled back"
```

### 2. Test Atomic Operations

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_atomic_batch_processing():
    """Test that batch processing is atomic."""

    from apps.ingest.services.processor import BatchProcessor
    from apps.ingest.models import IngestionBatch, StagedQlikItem
    from apps.core.models import CopyrightItem

    processor = BatchProcessor()

    # Create batch with multiple items, including one that will fail
    batch = await Ingestion.objects.acreate(source_type="test")

    # Add valid items
    for i in range(5):
        await StagedQlikItem.objects.acreate(
            batch=batch,
            material_id=1000000 + i,
            # ... valid data ...
        )

    # Add invalid item (will cause failure)
    await StagedQlikItem.objects.acreate(
        batch=batch,
        material_id=-1,  # Invalid ID
        # ... data that will cause failure ...
    )

    # Process batch - should fail completely
    with pytest.raises(Exception):
        await processor.process_batch(batch)

    # Verify NO items were created (complete rollback)
    created_count = await CopyrightItem.objects.filter(
        material_id__in=[1000000, 1000001, 1000002, 1000003, 1000004]
    ).acount()

    assert created_count == 0, "All items should have been rolled back"
```

## Success Criteria

- [ ] Transaction utilities module created
- [ ] PDF download service uses atomic operations
- [ ] Batch processor uses atomic operations (per-item or per-batch)
- [ ] Faculty sheet import uses atomic operations
- [ ] All multi-step database operations protected
- [ ] Tests verify rollback behavior
- [ ] Tests verify atomicity
- [ ] No partial updates on failure
- [ ] Data integrity maintained

## Files Created/Modified

- `src/apps/core/services/transactions.py` - NEW: Transaction utilities
- `src/apps/documents/services/download.py` - Add atomic wrapping
- `src/apps/ingest/services/processor.py` - Add atomic wrapping
- `src/apps/ingest/services/faculty_processor.py` - Add atomic wrapping
- `src/apps/documents/tests/test_transactions.py` - NEW: Transaction tests
- `src/apps/ingest/tests/test_transactions.py` - NEW: Transaction tests

## Related Tasks

- **Task 09:** Database Schema & Indexes (data integrity)
- **Task 10:** Async/ORM Consistency (native async ORM)
- **Task 14:** Critical Bug Fixes (race conditions)

## Benefits

1. **Data integrity** - No partial updates on failure
2. **Consistency** - Database always in valid state
3. **Recovery** - Failed operations can be retried safely
4. **Debugging** - Clear error boundaries

---

**Next Task:** [Task 16: Production Readiness Essentials](16-production-readiness.md)
