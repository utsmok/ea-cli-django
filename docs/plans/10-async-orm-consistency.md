# Task 10: Async/ORM Consistency

## Overview

Fix async/sync ORM mixing issues and use Django 6.0's native async ORM consistently throughout the codebase.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)

## Issues Addressed

### 1. Sync ORM in Async Context (High)
**File:** `src/apps/documents/services/download.py:94-104, 220-246`

**Problem:**
The async `download_undownloaded_pdfs` function uses `sync_to_async` wrappers for ORM operations, but also has direct sync ORM calls without the wrapper in `create_or_link_document`.

**Current Code:**
```python
@sync_to_async
def create_metadata():
    obj, _ = PDFCanvasMetadata.objects.update_or_create(...)
    return obj

# ... later ...

@sync_to_async
def create_or_link_document():
    # Mixed sync/async - inconsistent
    Document.objects.get_or_create(...)  # This is wrapped
    item.document = doc
    item.save()  # Direct save without await!
```

**Issues:**
- Using `sync_to_async` wrappers when Django 6 has native async ORM
- Direct `.save()` call in wrapped function breaks async context
- Performance overhead from `sync_to_async` thread pool switching
- Harder to maintain and debug

**Fix:** Use Django 6's native async ORM (`aget`, `asave`, `aupdate_or_create`).

### 2. Missing Native Async ORM Usage

The codebase should use Django 6.0's native async ORM methods instead of `sync_to_async` wrappers.

**Native Async ORM Methods:**
- `aget()` vs `get()`
- `afilter()` vs `filter()`
- `asave()` vs `save()`
- `adelete()` vs `delete()`
- `aupdate_or_create()` vs `update_or_create()`
- `aget_or_create()` vs `get_or_create()`
- `acount()` vs `count()`
- `aexists()` vs `exists()`

## Implementation Steps

### Step 1: Fix PDF Download Service

**File:** `src/apps/documents/services/download.py`

**Current problematic code:**
```python
@sync_to_async
def create_metadata():
    obj, _ = PDFCanvasMetadata.objects.update_or_create(
        id=int(metadata.get("id")),
        defaults=meta_defaults,
    )
    return obj

@sync_to_async
def create_or_link_document():
    # ...
    Document.objects.get_or_create(...)
    item.document = doc
    item.save()  # ❌ Direct sync save
```

**Fixed code:**
```python
async def create_or_link_document(
    item_data: Item,
    pdf_metadata_obj: PDFCanvasMetadata,
    fhash: str,
    filepath: Path,
    item: CopyrightItem,
) -> Document:
    """Create or link a Document record using native async ORM."""

    # Use native async get_or_create
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
        doc.file.save(filepath.name, ContentFile(filepath.read_bytes()))
        await doc.asave()  # Native async save

    # Link to copyright item
    item.document = doc
    item.filehash = fhash
    await item.asave(update_fields=["document", "filehash"])  # Native async save

    return doc

async def create_or_update_canvas_metadata(metadata: dict) -> PDFCanvasMetadata:
    """Create or update canvas metadata using native async ORM."""

    meta_defaults = {
        "canvas_course_id": metadata.get("course_id"),
        "canvas_file_id": metadata.get("id"),
        "display_name": metadata.get("display_name"),
        "filename": metadata.get("filename"),
        "url": metadata.get("url"),
        "size": metadata.get("size", 0),
        "content_type": metadata.get("content-type"),
        "usage_rights": metadata.get("usage_rights"),
        "user": metadata.get("user"),
    }

    # Use native async update_or_create
    obj, _ = await PDFCanvasMetadata.objects.aupdate_or_create(
        id=int(metadata.get("id")),
        defaults=meta_defaults,
    )
    return obj
```

### Step 2: Fix Enrichment Tasks

**File:** `src/apps/enrichment/tasks.py`

**Current error handling (line ~287-302):**
```python
except Exception as e:
    logger.error(f"Critical error in enrich_item for {item_id}: {e}")
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
    except Exception:
        pass  # ❌ Silent failure
```

**Fixed error handling:**
```python
except Exception as e:
    # Use logger.exception() for full traceback
    logger.exception(f"Critical error in enrich_item for {item_id}")

    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
    except Exception as inner_e:
        logger.error(f"Failed to update error status for item {item_id}: {inner_e}")
        # Re-raise to ensure task system knows about the failure
        raise
```

### Step 3: Update All Async ORM Calls

**File:** `src/apps/documents/services/download.py`

**Complete refactor of download_undownloaded_pdfs:**

```python
async def download_undownloaded_pdfs(
    session: httpx.AsyncClient,
    items: list[Item],
    batch_size: int = 10,
) -> list[tuple[int, Path | None, str | None]]:
    """
    Download PDFs from Canvas that haven't been downloaded yet.

    Uses native Django 6 async ORM for all database operations.
    """
    results = []

    for item_data in items:
        material_id = item_data.get("material_id")
        url = item_data.get("url")

        if not url or "/files/" not in url:
            results.append((material_id, None, "No valid Canvas URL"))
            continue

        try:
            # Download the PDF
            result = await download_pdf_from_canvas(session, url, DOWNLOAD_DIR, item_data)

            if result is None:
                results.append((material_id, None, "Download failed"))
                continue

            filepath, metadata = result
            fhash = compute_file_hash(filepath)

            # Get the CopyrightItem using native async ORM
            item = await CopyrightItem.objects.aget(material_id=material_id)

            # Create or update canvas metadata using native async ORM
            pdf_metadata = await create_or_update_canvas_metadata(metadata)

            # Create or link document using native async ORM
            doc = await create_or_link_document(
                item_data=item_data,
                pdf_metadata_obj=pdf_metadata,
                fhash=fhash,
                filepath=filepath,
                item=item,
            )

            results.append((material_id, filepath, None))

        except Exception as e:
            logger.exception(f"Failed to download PDF for {material_id}: {e}")
            results.append((material_id, None, str(e)))

    return results

# Remove all sync_to_async wrappers - no longer needed
```

### Step 4: Update Other Services with Async ORM

**File:** `src/apps/enrichment/services/osiris_service.py`

**Check for any `sync_to_async` usage and replace with native async:**

```python
# BEFORE
@sync_to_async
def get_faculty_by_abbreviation(abbreviation: str) -> Faculty | None:
    return Faculty.objects.filter(abbreviation__iexact=abbreviation).first()

# AFTER
async def get_faculty_by_abbreviation(abbreviation: str) -> Faculty | None:
    return await Faculty.objects.filter(abbreviation__iexact=abbreviation).afirst()
```

**File:** `src/apps/dashboard/services/query_service.py`

**Already using async correctly - verify:**

```python
# GOOD - Already native async
async def get_paginated_items(self, filters: ItemQueryFilter) -> PaginatedResult:
    qs = self.get_filtered_queryset(filters)

    # Use async count
    total_items = await qs.acount()

    # Use async iterator
    items = [item async for item in qs[offset:offset + limit]]

    return PaginatedResult(...)
```

### Step 5: Remove sync_to_async Imports

**File:** `src/apps/documents/services/download.py`

**Remove:**
```python
from asgiref.sync import sync_to_async
```

**No longer needed** with native async ORM.

## Testing

### 1. Test Async ORM Methods

```python
# In Django shell
import asyncio
from apps.documents.models import Document
from apps.core.models import CopyrightItem

async def test_async_orm():
    # Test aget
    item = await CopyrightItem.objects.aget(material_id=1234567)
    print(f"Got item: {item.material_id}")

    # Test afilter
    items = [i async for i in CopyrightItem.objects.afilter(workflow_status="ToDo")[:10]]
    print(f"Got {len(items)} items")

    # Test asave
    item.file_exists = True
    await item.asave(update_fields=["file_exists"])
    print("Saved item")

    # Test aupdate_or_create
    doc, created = await Document.objects.aupdate_or_create(
        filehash="test123",
        defaults={"file": "test.pdf"}
    )
    print(f"Document {'created' if created else 'updated'}")

asyncio.run(test_async_orm())
```

### 2. Test PDF Download with Async ORM

```python
# Test the refactored download function
import asyncio
from apps.documents.services.download import download_undownloaded_pdfs
from apps.dashboard.services.query_service import ItemQueryService

async def test_download():
    query_service = ItemQueryService()

    # Get items needing download
    filters = ItemQueryFilter(
        status="ToDo",
        file_exists=False
    )
    result = await query_service.get_paginated_items(filters, limit=5)

    # Download them
    import httpx
    async with httpx.AsyncClient() as client:
        downloaded = await download_undownloaded_pdfs(client, result.items)

    print(f"Downloaded {len([d for d in downloaded if d[1]])} files")

asyncio.run(test_download())
```

### 3. Performance Test

```python
import asyncio
import time
from apps.core.models import CopyrightItem

async def benchmark_async_orm():
    # Warm up
    _ = [i async for i in CopyrightItem.objects.all()[:10]]

    # Benchmark async iteration
    start = time.time()
    items = [i async for i in CopyrightItem.objects.select_related("faculty").all()[:1000]]
    duration = time.time() - start

    print(f"Async ORM: Fetched {len(items)} items in {duration:.3f}s")
    # Should be significantly faster than sync_to_async

asyncio.run(benchmark_async_orm())
```

## Migration Checklist

- [ ] Identify all `sync_to_async` usage
- [ ] Replace with native async ORM (`aget`, `asave`, etc.)
- [ ] Update `download_undownloaded_pdfs` function
- [ ] Update enrichment task error handling
- [ ] Update any other services with sync wrappers
- [ ] Remove unused `sync_to_async` imports
- [ ] Run all existing tests
- [ ] Test PDF download functionality
- [ ] Test enrichment tasks
- [ ] Performance test to verify improvement

## Benefits of Native Async ORM

| Aspect | sync_to_async | Native Async ORM |
|--------|---------------|------------------|
| **Performance** | Thread pool overhead | No thread switching |
| **Memory** | Thread stack per operation | Single async context |
| **Debugging** | Complex stack traces | Clear async flow |
| **Code** | Wrapper functions | Direct async/await |
| **Django** | Compatibility layer | Native support (6.0+) |

## Common Patterns

### Getting a single object

```python
# ❌ OLD
@sync_to_async
def get_item(material_id: int):
    return CopyrightItem.objects.get(material_id=material_id)
item = await get_item(123)

# ✅ NEW
item = await CopyrightItem.objects.aget(material_id=123)
```

### Filtering with limits

```python
# ❌ OLD
@sync_to_async
def get_items():
    return list(CopyrightItem.objects.filter(status="ToDo")[:100])
items = await get_items()

# ✅ NEW
items = [i async for i in CopyrightItem.objects.filter(status="ToDo")[:100]]
```

### Creating or updating

```python
# ❌ OLD
@sync_to_async
def create_or_update():
    obj, _ = Document.objects.update_or_create(
        filehash=fhash,
        defaults={...}
    )
    return obj
doc = await create_or_update()

# ✅ NEW
doc, created = await Document.objects.aupdate_or_create(
    filehash=fhash,
    defaults={...}
)
```

### Saving changes

```python
# ❌ OLD
@sync_to_async
def save_item(item):
    item.file_exists = True
    item.save()
await save_item(item)

# ✅ NEW
item.file_exists = True
await item.asave(update_fields=["file_exists"])
```

### Counting

```python
# ❌ OLD
@sync_to_async
def count_items():
    return CopyrightItem.objects.filter(status="ToDo").count()
count = await count_items()

# ✅ NEW
count = await CopyrightItem.objects.filter(status="ToDo").acount()
```

## Success Criteria

- [ ] All `sync_to_async` wrappers removed
- [ ] Native async ORM used throughout
- [ ] PDF download service refactored
- [ ] Enrichment tasks refactored
- [ ] All existing tests pass
- [ ] Manual testing confirms PDF downloads work
- [ ] Manual testing confirms enrichment works
- [ ] Performance improved (measured)
- [ ] Code is simpler and more maintainable

## Files Modified

- `src/apps/documents/services/download.py` - Remove sync_to_async, use native async ORM
- `src/apps/enrichment/tasks.py` - Fix error handling with logger.exception()
- `src/apps/enrichment/services/osiris_service.py` - Check for sync_to_async usage
- Any other files with `sync_to_async` imports

## Post-Implementation Monitoring

Monitor for:
1. **Performance improvement** - PDF downloads should be faster
2. **Error logs** - Better tracebacks with logger.exception()
3. **Database connection pool** - Native async should use fewer connections
4. **Memory usage** - Should decrease without thread pool overhead

---

**Next Task:** [Task 11: Error Handling & Logging](11-error-handling-logging.md)
